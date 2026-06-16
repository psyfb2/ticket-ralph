"""Tests for ticket_ralph.cli."""

import logging
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from ticket_ralph.cli import _warn_autonomous_mode, cli


class TestCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ticket" in result.output
        assert "task" in result.output
        assert "qa" in result.output

    def test_missing_ticket_id(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ticket"])
        assert result.exit_code != 0

    def test_task_continue_plan_forwards_resume(self) -> None:
        from ticket_ralph.commands.task import ResumePhase

        runner = CliRunner()
        with patch("ticket_ralph.commands.task.run_task") as mock_run_task:
            result = runner.invoke(cli, ["task", "PROJ-1", "--continue-plan", "3"])
        assert result.exit_code == 0
        resume = mock_run_task.call_args.kwargs["resume"]
        assert resume.phase is ResumePhase.PLAN
        assert resume.task_number == 3

    def test_task_continue_impl_forwards_resume(self) -> None:
        from ticket_ralph.commands.task import ResumePhase

        runner = CliRunner()
        with patch("ticket_ralph.commands.task.run_task") as mock_run_task:
            result = runner.invoke(cli, ["task", "PROJ-1", "--continue-impl", "2"])
        assert result.exit_code == 0
        resume = mock_run_task.call_args.kwargs["resume"]
        assert resume.phase is ResumePhase.IMPL
        assert resume.task_number == 2

    def test_task_no_resume_passes_none(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.task.run_task") as mock_run_task:
            result = runner.invoke(cli, ["task", "PROJ-1"])
        assert result.exit_code == 0
        assert mock_run_task.call_args.kwargs["resume"] is None

    def test_task_loop_forwards_resume(self) -> None:
        from ticket_ralph.commands.task import ResumePhase

        runner = CliRunner()
        with patch("ticket_ralph.commands.task_loop.run_task_loop") as mock_run_loop:
            result = runner.invoke(cli, ["task-loop", "PROJ-1", "--continue-impl", "4"])
        assert result.exit_code == 0
        resume = mock_run_loop.call_args.kwargs["resume"]
        assert resume.phase is ResumePhase.IMPL
        assert resume.task_number == 4

    def test_mutually_exclusive_continue_options(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.task.run_task") as mock_run_task:
            result = runner.invoke(
                cli,
                ["task", "PROJ-1", "--continue-plan", "1", "--continue-impl", "2"],
            )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output
        mock_run_task.assert_not_called()


class TestWarnAutonomousMode:
    def test_warns_when_autonomous(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("TR_AUTONOMOUS", "true")
        with caplog.at_level(logging.WARNING, logger="ticket-ralph"):
            _warn_autonomous_mode()
        assert "AUTONOMOUS MODE" in caplog.text
        assert "VM" in caplog.text
        assert "scoped token privileges" in caplog.text

    def test_no_warning_when_not_autonomous(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("TR_AUTONOMOUS", "false")
        with caplog.at_level(logging.WARNING, logger="ticket-ralph"):
            _warn_autonomous_mode()
        assert "AUTONOMOUS MODE" not in caplog.text


class TestMain:
    def test_handles_ticket_ralph_error(self) -> None:
        from ticket_ralph.cli import main
        from ticket_ralph.exceptions import TicketRalphError

        with (
            patch("ticket_ralph.cli.cli", side_effect=TicketRalphError("boom")),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1

    def test_handles_autonomous_blocker(self) -> None:
        from ticket_ralph.cli import main
        from ticket_ralph.exceptions import AutonomousBlocker

        with (
            patch(
                "ticket_ralph.cli.cli",
                side_effect=AutonomousBlocker("stuck", "tr-plan"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2
