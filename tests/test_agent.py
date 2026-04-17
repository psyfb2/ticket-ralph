"""Tests for ticket_ralph.services.agent."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.config import TicketRalphConfig
from ticket_ralph.exceptions import AgentError, AutonomousBlocker, TicketRalphError
from ticket_ralph.services.agent import (
    AgentExecutor,
    AgentResult,
    check_autonomous_result,
)


@pytest.fixture()
def config(tmp_path: Path) -> TicketRalphConfig:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-plan.md").touch()
    (agents_dir / "tr-software-engineer.md").touch()

    cfg = TicketRalphConfig.__new__(TicketRalphConfig)
    cfg.ticket_id = "TEST-1"
    cfg.tmp_dir = tmp_path / "tickets" / "TEST-1"
    cfg.tmp_dir.mkdir(parents=True)
    cfg.agents_dir = agents_dir
    cfg.autonomous = False
    cfg.permission_mode = "acceptEdits"
    cfg.task_permission_mode = "acceptEdits"
    return cfg


class TestAgentExecutor:
    def test_run_interactive_failure(self, config: TicketRalphConfig) -> None:
        executor = AgentExecutor(config)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
            with pytest.raises(AgentError):
                executor.run("tr-plan", "test prompt")

    def test_run_agent_not_found(self, config: TicketRalphConfig) -> None:
        executor = AgentExecutor(config)
        with pytest.raises(TicketRalphError, match="make tr-install"):
            executor.run("nonexistent-agent", "test prompt")

    def test_run_autonomous_mode(
        self, config: TicketRalphConfig
    ) -> None:
        config.autonomous = True
        executor = AgentExecutor(config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            executor.run("tr-plan", "test prompt")
            cmd = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in cmd
            assert "--settings" not in cmd

    def test_run_autonomous_noninteractive(
        self, config: TicketRalphConfig
    ) -> None:
        config.autonomous = True
        executor = AgentExecutor(config)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.__enter__ = MagicMock(return_value=mock_proc)
        mock_proc.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            executor.run_autonomous("tr-plan", "test prompt")
            cmd = mock_popen.call_args[0][0]
            assert "--dangerously-skip-permissions" in cmd
            assert "--settings" not in cmd

    def test_run_autonomous_streaming(self, config: TicketRalphConfig) -> None:
        executor = AgentExecutor(config)

        stream_lines = [
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {"delta": {"type": "text_delta", "text": "hello"}},
                }
            ),
            json.dumps(
                {
                    "type": "result",
                    "structured_output": {"done": True, "overview": "completed"},
                }
            ),
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = iter([line + "\n" for line in stream_lines])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.__enter__ = MagicMock(return_value=mock_proc)
        mock_proc.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc):
            result = executor.run_autonomous(
                "tr-plan", "test prompt", '{"type":"object"}'
            )

        assert result.exit_code == 0
        assert result.structured_output == {"done": True, "overview": "completed"}

    def test_run_autonomous_failure(self, config: TicketRalphConfig) -> None:
        executor = AgentExecutor(config)

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.return_value = None
        mock_proc.returncode = 1
        mock_proc.__enter__ = MagicMock(return_value=mock_proc)
        mock_proc.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc):
            with pytest.raises(AgentError):
                executor.run_autonomous("tr-plan", "test prompt")

    def test_run_autonomous_handles_bad_json_lines(
        self, config: TicketRalphConfig
    ) -> None:
        executor = AgentExecutor(config)

        stream_lines = [
            "not json\n",
            "\n",
            json.dumps(
                {
                    "type": "result",
                    "structured_output": {"done": True, "overview": "ok"},
                }
            )
            + "\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(stream_lines)
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0
        mock_proc.__enter__ = MagicMock(return_value=mock_proc)
        mock_proc.__exit__ = MagicMock(return_value=False)

        with patch("subprocess.Popen", return_value=mock_proc):
            result = executor.run_autonomous(
                "tr-plan", "test prompt", '{"type":"object"}'
            )
        assert result.structured_output == {"done": True, "overview": "ok"}


class TestCheckAutonomousResult:
    def test_success(self, tmp_path: Path) -> None:
        result = AgentResult(
            exit_code=0, structured_output={"done": True, "overview": "all good"}
        )
        check_autonomous_result(result, "tr-plan", tmp_path)

    def test_blocker_raises(self, tmp_path: Path) -> None:
        result = AgentResult(
            exit_code=0,
            structured_output={"done": False, "overview": "missing context"},
        )
        with pytest.raises(AutonomousBlocker) as exc_info:
            check_autonomous_result(result, "tr-plan", tmp_path)
        assert exc_info.value.overview == "missing context"
        assert (tmp_path / ".blocker-overview").read_text() == "missing context"

    def test_no_structured_output(self, tmp_path: Path) -> None:
        result = AgentResult(exit_code=0, structured_output=None)
        with pytest.raises(TicketRalphError, match="no structured output"):
            check_autonomous_result(result, "tr-plan", tmp_path)
