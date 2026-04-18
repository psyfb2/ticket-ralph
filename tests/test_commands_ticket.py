"""Tests for ticket_ralph.commands.ticket."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.exceptions import TicketRalphError


@pytest.fixture()
def _setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up env vars and patch paths for command tests."""
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)
    monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")

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


class TestRunTicket:
    @pytest.mark.usefixtures("_setup_env")
    def test_raises_if_no_prd_produced(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        mock_provider = MagicMock()
        mock_provider.cli_commands = []

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.create_provider", return_value=mock_provider),
            patch("ticket_ralph.commands.ticket.agent_svc"),
        ):
            mock_git.check_clean.return_value = None

            with pytest.raises(TicketRalphError, match="did not produce PRD.json"):
                run_ticket("PROJ-1")

    @pytest.mark.usefixtures("_setup_env")
    def test_success_flow(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        mock_provider = MagicMock()
        mock_provider.cli_commands = []
        mock_provider.provider_name = "Jira"

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.create_provider", return_value=mock_provider),
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.default_branch.return_value = "main"

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"summary": "Add login", "tasks": [], "requirements": []}
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1")

            mock_git.checkout.assert_called()
            mock_git.push.assert_called()
            mock_provider.upload_attachment.assert_called()

            updated_prd = json.loads(
                (tmp_path / "tickets" / "PROJ-1" / "PRD.json").read_text()
            )
            assert updated_prd["baseBranch"] == "main"
            assert "PROJ-1" in updated_prd["topBranch"]

    @pytest.mark.usefixtures("_setup_env")
    def test_success_flow_with_base_branch(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        mock_provider = MagicMock()
        mock_provider.cli_commands = []
        mock_provider.provider_name = "Jira"

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.create_provider", return_value=mock_provider),
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"summary": "Add login", "tasks": [], "requirements": []}
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
    def test_prompt_includes_platform_name(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        mock_provider = MagicMock()
        mock_provider.cli_commands = []
        mock_provider.provider_name = "Jira"

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.create_provider", return_value=mock_provider),
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.default_branch.return_value = "main"

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {"summary": "Test", "tasks": [], "requirements": []}
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1", "extra context")

            call_args = executor.run.call_args[0]
            assert "Jira" in call_args[1]
            assert "PROJ-1" in call_args[1]
            assert "extra context" in call_args[1]
            assert "parent story" in call_args[1]

    @pytest.mark.usefixtures("_setup_env")
    def test_branch_name_from_prd_summary(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.ticket import run_ticket

        mock_provider = MagicMock()
        mock_provider.cli_commands = []
        mock_provider.provider_name = "Jira"

        with (
            patch("ticket_ralph.commands.ticket.git") as mock_git,
            patch("ticket_ralph.commands.ticket.create_provider", return_value=mock_provider),
            patch("ticket_ralph.commands.ticket.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.default_branch.return_value = "main"

            tickets_dir = tmp_path / "tickets"
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prd = {
                    "summary": "Add user authentication",
                    "tasks": [],
                    "requirements": [],
                }
                prd_path = tickets_dir / "PROJ-1" / "PRD.json"
                prd_path.write_text(json.dumps(prd))

            executor.run.side_effect = fake_run

            run_ticket("PROJ-1")

            mock_git.checkout.assert_any_call(
                "PROJ-1-add-user-authentication",
                create=True,
                start_point="origin/main",
            )
