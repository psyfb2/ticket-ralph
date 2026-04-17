"""Configuration resolution for ticket-ralph.

Resolves environment variables and sets up per-ticket temporary directories.
Ticketing provider credentials are resolved by each provider's own factory.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ticket_ralph.ticketing.base import TicketingProvider

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


@dataclass
class TicketRalphConfig:
    """Resolved configuration for a ticket-ralph run."""

    ticket_id: str
    tmp_dir: Path = field(init=False)
    agents_dir: Path = field(default_factory=lambda: AGENTS_DIR)
    autonomous: bool = field(default=False)
    permission_mode: str = field(default="acceptEdits")
    task_permission_mode: str = field(default="acceptEdits")
    ticketing_platform: str = field(default="jira")

    def __post_init__(self) -> None:
        self.tmp_dir = TICKETS_DIR / self.ticket_id
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, ticket_id: str) -> "TicketRalphConfig":
        """Create config by resolving environment variables.

        Args:
            ticket_id: The ticket ID (e.g. PROJ-123).

        Returns:
            Fully resolved configuration.
        """
        autonomous = os.environ.get("TR_AUTONOMOUS", "true").lower() == "true"
        permission_mode = os.environ.get("TR_PERMISSION_MODE", "acceptEdits")
        task_permission_mode = os.environ.get("TR_TASK_PERMISSION_MODE", "acceptEdits")
        ticketing_platform = os.environ.get("TR_TICKETING_PLATFORM", "jira")

        return cls(
            ticket_id=ticket_id,
            agents_dir=AGENTS_DIR,
            autonomous=autonomous,
            permission_mode=permission_mode,
            task_permission_mode=task_permission_mode,
            ticketing_platform=ticketing_platform,
        )


def check_prerequisites(provider: TicketingProvider | None = None) -> None:
    """Verify that required CLI tools are available on PATH.

    Args:
        provider: Optional ticketing provider whose CLI commands are also checked.

    Raises:
        TicketRalphError: If any required command is missing.
    """
    from ticket_ralph.exceptions import TicketRalphError

    required = list(PREREQUISITE_COMMANDS)
    if provider:
        required.extend(provider.cli_commands)

    missing = [cmd for cmd in required if shutil.which(cmd) is None]
    if missing:
        raise TicketRalphError(
            f"Required commands not found: {', '.join(missing)}. "
            "Install them before running ticket-ralph."
        )
