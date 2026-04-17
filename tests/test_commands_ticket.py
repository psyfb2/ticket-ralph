"""Tests for ticket_ralph.commands.ticket."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.ticketing.base import TicketContext


@pytest.fixture()
def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up env vars and patch paths for command tests."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.test.com")
    monkeypatch.setenv("JIRA_USER", "user@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-high-level-plan.md").touch()

    tickets_dir = tmp_path / "tickets"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


def _make_context(
    *,
    issue_type: str = "Task",
    summary: str = "Test ticket",
    parent_key: str | None = None,
    attachments: list[dict[str, str]] | None = None,
) -> TicketContext:
    return TicketContext(
        ticket_id="PROJ-1",
        issue_type=issue_type,
        summary=summary,
        description="",
        comments=[],
        attachments=attachments or [],
        parent_key=parent_key,
    )


class TestRunTicket:
    @pytest.mark.usefixtures("_setup_env")
    def test_raises_if_existing_subtasks(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
        ):
            mock_git.check_clean.return_value = None
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = [
                {"key": "PROJ-2", "fields": {"summary": "existing"}}
            ]

            with pytest.raises(TicketRalphError, match="already has 1 child"):
                run_ticket("PROJ-1")

    @pytest.mark.usefixtures("_setup_env")
    def test_raises_if_no_prd_produced(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.ticket.agent_svc"),
        ):
            mock_git.check_clean.return_value = None
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []
            provider.fetch_ticket_context.return_value = _make_context()

            with pytest.raises(TicketRalphError, match="did not produce PRD.json"):
                run_ticket("PROJ-1")

    @pytest.mark.usefixtures("_setup_env")
    def test_success_flow(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.default_branch.return_value = "main"
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []
            provider.fetch_ticket_context.return_value = _make_context(
                summary="Add login"
            )

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"tasks": [], "requirements": []}
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1")

            mock_git.checkout.assert_called()
            mock_git.push.assert_called()
            provider.upload_attachment.assert_called()

            updated_prd = json.loads(
                (tmp_path / "tickets" / "PROJ-1" / "PRD.json").read_text()
            )
            assert updated_prd["baseBranch"] == "main"

    @pytest.mark.usefixtures("_setup_env")
    def test_success_flow_with_base_branch(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []
            provider.fetch_ticket_context.return_value = _make_context(
                summary="Add login"
            )

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"tasks": [], "requirements": []}
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1", base_branch="develop")

            mock_git.default_branch.assert_not_called()
            mock_git.checkout.assert_any_call(
                "PROJ-1-add-login", create=True, start_point="origin/develop"
            )

            updated_prd = json.loads((tickets_dir / "PROJ-1" / "PRD.json").read_text())
            assert updated_prd["baseBranch"] == "develop"

    @pytest.mark.usefixtures("_setup_env")
    def test_with_parent_story_and_attachments(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = True
            mock_git.default_branch.return_value = "main"
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []

            tickets_dir = tmp_path / "tickets"

            context = _make_context(
                issue_type="Sub-task",
                summary="Add login",
                parent_key="PROJ-100",
                attachments=[{"localPath": "/tmp/spec.md", "filename": "spec.md"}],
            )

            def fake_fetch(tid, td, **kw):
                # Write parent-context.json (still needed by _build_ticket_prompt)
                parent_data = {"issueType": "Story"}
                (td / "parent-context.json").write_text(json.dumps(parent_data))
                return context

            provider.fetch_ticket_context.side_effect = fake_fetch
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"tasks": [], "requirements": []}
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1", "extra context")

            # Verify parent and attachment branches were hit
            call_args = executor.run.call_args[0]
            assert "PROJ-100" in call_args[1]
            assert "spec.md" in call_args[1]
            assert "extra context" in call_args[1]

    @pytest.mark.usefixtures("_setup_env")
    def test_raises_if_parent_context_missing(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.ticket.agent_svc"),
        ):
            mock_git.check_clean.return_value = None
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []

            # Return context with parent_key but don't write parent-context.json
            provider.fetch_ticket_context.return_value = _make_context(
                parent_key="PROJ-100"
            )

            with pytest.raises(TicketRalphError, match="Parent context file not found"):
                run_ticket("PROJ-1")
