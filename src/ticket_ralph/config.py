"""Configuration resolution for ticket-ralph.

Resolves environment variables and sets up per-ticket temporary directories.
Ticketing provider credentials are resolved by each provider's own factory.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ticket-ralph")

AGENTS_DIR = Path.home() / ".claude" / "agents"
TICKETS_DIR = Path.home() / ".ticket-ralph" / "tickets"

AUTONOMOUS_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "done": {
                "type": "boolean",
                "description": (
                    "true if the task completed successfully, false if you hit a "
                    "blocker and need human intervention (e.g. missing context, "
                    "need access to a tool or service you cannot reach)"
                ),
            },
            "overview": {
                "type": "string",
                "description": (
                    "If done=true: brief summary of what was accomplished. "
                    "If done=false: clear explanation of what blocked you and "
                    "what you need from the human to proceed"
                ),
            },
        },
        "required": ["done", "overview"],
    }
)

PREREQUISITE_COMMANDS = ["claude", "git"]

SYNC_PROVIDER_CLI_COMMANDS: dict[str, list[str]] = {
    "jira": ["jira"],
}


@dataclass
class TicketRalphConfig:
    """Resolved configuration for a ticket-ralph run."""

    ticket_id: str
    ticketing_platform: str
    tmp_dir: Path = field(init=False)
    agents_dir: Path = field(default_factory=lambda: AGENTS_DIR)
    autonomous: bool = field(default=True)
    permission_mode: str = field(default="acceptEdits")
    task_permission_mode: str = field(default="acceptEdits")
    sync_provider: str = field(default="noop")

    def __post_init__(self) -> None:
        self.tmp_dir = TICKETS_DIR / self.ticket_id
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, ticket_id: str) -> "TicketRalphConfig":
        """Create config by resolving environment variables via ``AppSettings``.

        Args:
            ticket_id: The ticket ID (e.g. PROJ-123).

        Returns:
            Fully resolved configuration.
        """
        from ticket_ralph.settings import load_app_settings

        settings = load_app_settings()
        return cls(
            ticket_id=ticket_id,
            ticketing_platform=settings.ticketing_platform,
            agents_dir=AGENTS_DIR,
            autonomous=settings.autonomous,
            permission_mode=settings.permission_mode,
            task_permission_mode=settings.task_permission_mode,
            sync_provider=settings.sync_provider,
        )


def check_prerequisites(sync_provider: str | None = None) -> None:
    """Verify that required CLI tools are available on PATH.

    Args:
        sync_provider: Optional sync provider name whose CLI commands
            are also checked (looked up from SYNC_PROVIDER_CLI_COMMANDS).

    Raises:
        TicketRalphError: If any required command is missing.
    """
    from ticket_ralph.exceptions import TicketRalphError

    required = list(PREREQUISITE_COMMANDS)
    if sync_provider:
        required.extend(SYNC_PROVIDER_CLI_COMMANDS.get(sync_provider, []))

    missing = [cmd for cmd in required if shutil.which(cmd) is None]
    if missing:
        raise TicketRalphError(
            f"Required commands not found: {', '.join(missing)}. "
            "Install them before running ticket-ralph."
        )
