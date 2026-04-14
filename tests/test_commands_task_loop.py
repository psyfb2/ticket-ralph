"""Tests for ticket_ralph.commands.task_loop."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import AutonomousBlocker, TicketRalphError


@pytest.fixture()
def _setup_loop_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)
    monkeypatch.setenv("JIRA_CONFIG_FILE", "/nonexistent")
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_USER", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    tickets_dir = tmp_path / "tickets"
    settings_file = tmp_path / "settings.json"

    with (
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.SETTINGS_FILE", settings_file),
    ):
        yield tmp_path


class TestRunTaskLoop:
    @pytest.mark.usefixtures("_setup_loop_env")
    def test_completes_all_tasks(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task_loop import run_task_loop

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-branch",
            "tasks": [
                {"taskNumber": 1, "done": False, "title": "First"},
                {"taskNumber": 2, "done": False, "title": "Second"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))

        call_count = 0

        def fake_run_task(tid: str, extra: str = "") -> None:
            nonlocal call_count
            call_count += 1
            current_prd = json.loads((ticket_dir / "PRD.json").read_text())
            current_prd["tasks"][call_count - 1]["done"] = True
            (ticket_dir / "PRD.json").write_text(json.dumps(current_prd))

        with patch(
            "ticket_ralph.commands.task_loop.run_task", side_effect=fake_run_task
        ):
            run_task_loop("PROJ-1")

        assert call_count == 2

    @pytest.mark.usefixtures("_setup_loop_env")
    def test_raises_on_blocker(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task_loop import run_task_loop

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-branch",
            "tasks": [{"taskNumber": 1, "done": False, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))

        def fake_run_task(tid: str, extra: str = "") -> None:
            raise AutonomousBlocker("stuck", "tr-plan")

        with (
            patch(
                "ticket_ralph.commands.task_loop.run_task", side_effect=fake_run_task
            ),
            patch("ticket_ralph.commands.task_loop.notify_blocker"),
            pytest.raises(AutonomousBlocker),
        ):
            run_task_loop("PROJ-1")

    @pytest.mark.usefixtures("_setup_loop_env")
    def test_max_iterations_safeguard(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task_loop import run_task_loop

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-branch",
            "tasks": [{"taskNumber": 1, "done": False, "title": "Stuck"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))

        def fake_run_task(tid: str, extra: str = "") -> None:
            pass  # Never marks task done

        with (
            patch(
                "ticket_ralph.commands.task_loop.run_task", side_effect=fake_run_task
            ),
            pytest.raises(TicketRalphError, match="max iterations"),
        ):
            run_task_loop("PROJ-1")

    @pytest.mark.usefixtures("_setup_loop_env")
    def test_raises_on_generic_error(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task_loop import run_task_loop

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-branch",
            "tasks": [{"taskNumber": 1, "done": False, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))

        def fake_run_task(tid: str, extra: str = "") -> None:
            raise TicketRalphError("something broke")

        with (
            patch(
                "ticket_ralph.commands.task_loop.run_task", side_effect=fake_run_task
            ),
            pytest.raises(TicketRalphError, match="something broke"),
        ):
            run_task_loop("PROJ-1")

    @pytest.mark.usefixtures("_setup_loop_env")
    def test_raises_if_prd_missing_after_task(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task_loop import run_task_loop

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        # No PRD.json

        def fake_run_task(tid: str, extra: str = "") -> None:
            pass  # doesn't create PRD.json

        with (
            patch(
                "ticket_ralph.commands.task_loop.run_task", side_effect=fake_run_task
            ),
            pytest.raises(TicketRalphError, match="PRD.json not found"),
        ):
            run_task_loop("PROJ-1")
