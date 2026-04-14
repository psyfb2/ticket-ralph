"""Custom exceptions for ticket-ralph with associated exit codes."""


class TicketRalphError(Exception):
    """Base exception for ticket-ralph errors (exit code 1)."""

    exit_code: int = 1


class AutonomousBlocker(TicketRalphError):
    """Agent reported a blocker in autonomous mode (exit code 2)."""

    exit_code: int = 2

    def __init__(self, overview: str, agent_name: str) -> None:
        self.overview = overview
        self.agent_name = agent_name
        super().__init__(f"Agent {agent_name} reported blocker: {overview}")


class AgentError(TicketRalphError):
    """Agent exited with a non-zero code."""

    def __init__(self, agent_name: str, exit_code: int) -> None:
        self.agent_name = agent_name
        self.agent_exit_code = exit_code
        super().__init__(f"Agent {agent_name} exited with code {exit_code}")


class MergeConflictError(TicketRalphError):
    """Git merge failed."""

    def __init__(self, branch: str) -> None:
        self.branch = branch
        super().__init__(f"Merge failed for branch {branch}")
