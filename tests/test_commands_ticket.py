"""Tests for ticket_ralph.commands.ticket."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import TicketRalphError


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
    settings_file = tmp_path / "settings.json"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.SETTINGS_FILE", settings_file),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


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

            context_data = {
                "issueType": "Task",
                "parentStoryKey": None,
                "summary": "Test ticket",
                "attachments": [],
            }
            provider.fetch_ticket_context.side_effect = lambda tid, td, **kw: Path(
                td / "ticket-context.json"
            ).write_text(json.dumps(context_data))

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
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []

            tickets_dir = tmp_path / "tickets"

            def fake_fetch(tid, td, **kw):
                context_data = {
                    "issueType": "Task",
                    "parentStoryKey": None,
                    "summary": "Add login",
                    "attachments": [],
                }
                (td / "ticket-context.json").write_text(json.dumps(context_data))

            provider.fetch_ticket_context.side_effect = fake_fetch

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
            provider = MockProvider.return_value
            provider.get_subtasks.return_value = []

            tickets_dir = tmp_path / "tickets"

            def fake_fetch(tid, td, **kw):
                context_data = {
                    "issueType": "Sub-task",
                    "parentStoryKey": "PROJ-100",
                    "summary": "Add login",
                    "attachments": [
                        {"localPath": "/tmp/spec.md"},
                    ],
                }
                (td / "ticket-context.json").write_text(json.dumps(context_data))
                parent_data = {
                    "issueType": "Story",
                    "parentStoryKey": None,
                    "summary": "Parent story",
                }
                (td / "parent-context.json").write_text(json.dumps(parent_data))

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

            def fake_fetch(tid, td, **kw):
                context_data = {
                    "issueType": "Sub-task",
                    "parentStoryKey": "PROJ-100",
                    "summary": "Child task",
                    "attachments": [],
                }
                (td / "ticket-context.json").write_text(json.dumps(context_data))
                # parent-context.json deliberately NOT written

            provider.fetch_ticket_context.side_effect = fake_fetch

            with pytest.raises(TicketRalphError, match="Parent context file not found"):
                run_ticket("PROJ-1")
