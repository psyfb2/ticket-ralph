"""Tests for ticket_ralph.cli."""

from unittest.mock import patch

from click.testing import CliRunner

from ticket_ralph.cli import cli


class TestCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ticket" in result.output
        assert "task" in result.output
        assert "qa" in result.output

    def test_ticket_subcommand(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.ticket.run_ticket") as mock:
            runner.invoke(cli, ["ticket", "PROJ-123", "extra", "context"])
            mock.assert_called_once_with("PROJ-123", "extra context")

    def test_task_subcommand(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.task.run_task") as mock:
            runner.invoke(cli, ["task", "PROJ-123"])
            mock.assert_called_once_with("PROJ-123", "")

    def test_task_loop_subcommand(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.task_loop.run_task_loop") as mock:
            runner.invoke(cli, ["task-loop", "PROJ-123"])
            mock.assert_called_once_with("PROJ-123", "")

    def test_qa_subcommand(self) -> None:
        runner = CliRunner()
        with patch("ticket_ralph.commands.qa.run_qa") as mock:
            runner.invoke(cli, ["qa", "PROJ-123"])
            mock.assert_called_once_with("PROJ-123", "")

    def test_missing_ticket_id(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ticket"])
        assert result.exit_code != 0
