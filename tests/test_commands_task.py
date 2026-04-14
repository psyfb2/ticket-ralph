"""Tests for ticket_ralph.commands.task."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import TicketRalphError


@pytest.fixture()
def _setup_task_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up env and patches for task command tests."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.test.com")
    monkeypatch.setenv("JIRA_USER", "user@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-plan.md").touch()
    (agents_dir / "tr-software-engineer.md").touch()

    tickets_dir = tmp_path / "tickets"
    settings_file = tmp_path / "settings.json"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.SETTINGS_FILE", settings_file),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


class TestRunTask:
    @pytest.mark.usefixtures("_setup_task_env")
    def test_exits_if_all_done(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": True, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with patch("ticket_ralph.commands.task.git") as mock_git:
            mock_git.check_clean.return_value = None
            run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_raises_if_no_prd(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch("ticket_ralph.commands.task.JiraProvider"),
        ):
            mock_git.check_clean.return_value = None
            # download_ticket_context does nothing (no PRD)

            with pytest.raises(TicketRalphError, match="PRD.json not found"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_full_success_flow(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [
                {"taskNumber": 1, "done": False, "title": "Add auth"},
                {"taskNumber": 2, "done": False, "title": "Add tests"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch("ticket_ralph.commands.task.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            provider = MockProvider.return_value
            executor = mock_agent.AgentExecutor.return_value

            call_count = 0

            def fake_agent_run(agent, prompt, perm):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Plan agent writes a plan file
                    plan_file = ticket_dir / "plan-1.md"
                    plan_file.write_text("# Plan for task 1")

            executor.run.side_effect = fake_agent_run

            run_task("PROJ-1")

            updated_prd = json.loads((ticket_dir / "PRD.json").read_text())
            assert updated_prd["tasks"][0]["done"] is True

            mock_git.merge_no_ff.assert_called_once()
            provider.upload_attachment.assert_called()
