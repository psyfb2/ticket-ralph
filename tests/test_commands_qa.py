"""Tests for ticket_ralph.commands.qa."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import TicketRalphError


@pytest.fixture()
def _setup_qa_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("JIRA_BASE_URL", "https://jira.test.com")
    monkeypatch.setenv("JIRA_USER", "user@test.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-qa-runner.md").touch()

    tickets_dir = tmp_path / "tickets"
    settings_file = tmp_path / "settings.json"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.SETTINGS_FILE", settings_file),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


class TestRunQa:
    @pytest.mark.usefixtures("_setup_qa_env")
    def test_raises_if_tasks_incomplete(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.qa import run_qa

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [
                {"taskNumber": 1, "done": True, "title": "First"},
                {"taskNumber": 2, "done": False, "title": "Second"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with patch("ticket_ralph.commands.qa.git") as mock_git:
            mock_git.check_clean.return_value = None
            with pytest.raises(TicketRalphError, match="not yet done"):
                run_qa("PROJ-1")

    @pytest.mark.usefixtures("_setup_qa_env")
    def test_no_prd_mode(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.qa import run_qa

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.qa.git") as mock_git,
            patch("ticket_ralph.commands.qa.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.qa.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.current_branch.return_value = "feature-branch"
            mock_git.default_branch.return_value = "main"
            provider = MockProvider.return_value
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                (ticket_dir / "qa-report.md").write_text("# QA Report")

            executor.run.side_effect = fake_run

            run_qa("PROJ-1")
            provider.upload_attachment.assert_called()

    @pytest.mark.usefixtures("_setup_qa_env")
    def test_raises_if_no_qa_report(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.qa import run_qa

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": True, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.qa.git") as mock_git,
            patch("ticket_ralph.commands.qa.JiraProvider"),
            patch("ticket_ralph.commands.qa.agent_svc"),
        ):
            mock_git.check_clean.return_value = None
            mock_git.default_branch.return_value = "main"

            with pytest.raises(TicketRalphError, match="qa-report.md"):
                run_qa("PROJ-1")

    @pytest.mark.usefixtures("_setup_qa_env")
    def test_success_with_prd(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.qa import run_qa

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": True, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.qa.git") as mock_git,
            patch("ticket_ralph.commands.qa.JiraProvider") as MockProvider,
            patch("ticket_ralph.commands.qa.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.default_branch.return_value = "main"
            provider = MockProvider.return_value
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                (ticket_dir / "qa-report.md").write_text("# QA Report")

            executor.run.side_effect = fake_run

            run_qa("PROJ-1")
            # Should sync ticket files + qa report
            assert provider.upload_attachment.call_count >= 1
