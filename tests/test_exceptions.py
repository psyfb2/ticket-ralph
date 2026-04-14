"""Tests for ticket_ralph.exceptions."""

from ticket_ralph.exceptions import (
    AgentError,
    AutonomousBlocker,
    MergeConflictError,
    TicketRalphError,
)


class TestTicketRalphError:
    def test_exit_code(self) -> None:
        err = TicketRalphError("something broke")
        assert err.exit_code == 1
        assert str(err) == "something broke"


class TestAutonomousBlocker:
    def test_exit_code(self) -> None:
        err = AutonomousBlocker("missing context", "tr-plan")
        assert err.exit_code == 2
        assert err.overview == "missing context"
        assert err.agent_name == "tr-plan"
        assert "tr-plan" in str(err)
        assert "missing context" in str(err)


class TestAgentError:
    def test_exit_code(self) -> None:
        err = AgentError("tr-plan", 42)
        assert err.exit_code == 1
        assert err.agent_name == "tr-plan"
        assert err.agent_exit_code == 42
        assert "42" in str(err)


class TestMergeConflictError:
    def test_exit_code(self) -> None:
        err = MergeConflictError("feature-branch")
        assert err.exit_code == 1
        assert err.branch == "feature-branch"
        assert "feature-branch" in str(err)
