"""Configuration resolution for ticket-ralph.

Resolves environment variables, Jira credentials (with fallback to jira-cli
config), and sets up per-ticket temporary directories.
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("ticket-ralph")

AGENTS_DIR = Path.home() / ".claude" / "agents"
SETTINGS_FILE = Path.home() / ".ticket-ralph" / "settings.json"
TICKETS_DIR = Path.home() / ".ticket-ralph" / "tickets"
JIRA_CONFIG_DEFAULT = Path.home() / ".config" / ".jira" / ".config.yml"

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

PREREQUISITE_COMMANDS = ["claude", "git", "jira"]


@dataclass
class TicketRalphConfig:
    """Resolved configuration for a ticket-ralph run."""

    ticket_id: str
    tmp_dir: Path = field(init=False)
    agents_dir: Path = field(default_factory=lambda: AGENTS_DIR)
    settings_file: Path | None = field(default=None)
    autonomous: bool = field(default=False)
    permission_mode: str = field(default="acceptEdits")
    task_permission_mode: str = field(default="acceptEdits")
    jira_base_url: str | None = field(default=None)
    jira_user: str | None = field(default=None)
    jira_api_token: str | None = field(default=None)

    def __post_init__(self) -> None:
        self.tmp_dir = TICKETS_DIR / self.ticket_id
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, ticket_id: str) -> "TicketRalphConfig":
        """Create config by resolving environment variables and jira-cli config.

        Args:
            ticket_id: The Jira ticket ID (e.g. PROJ-123).

        Returns:
            Fully resolved configuration.
        """
        autonomous = os.environ.get("TR_AUTONOMOUS", "false").lower() == "true"
        permission_mode = os.environ.get("TR_PERMISSION_MODE", "acceptEdits")
        task_permission_mode = os.environ.get("TR_TASK_PERMISSION_MODE", "acceptEdits")

        settings_file = SETTINGS_FILE if SETTINGS_FILE.exists() else None

        jira_base_url, jira_user, jira_api_token = _resolve_jira_env()

        return cls(
            ticket_id=ticket_id,
            agents_dir=AGENTS_DIR,
            settings_file=settings_file,
            autonomous=autonomous,
            permission_mode=permission_mode,
            task_permission_mode=task_permission_mode,
            jira_base_url=jira_base_url,
            jira_user=jira_user,
            jira_api_token=jira_api_token,
        )


def _resolve_jira_env() -> tuple[str | None, str | None, str | None]:
    """Resolve Jira credentials from env vars or jira-cli config.

    Returns:
        Tuple of (base_url, user, api_token). Any may be None if not found.
    """
    base_url = os.environ.get("JIRA_BASE_URL")
    user = os.environ.get("JIRA_USER")
    api_token = os.environ.get("JIRA_API_TOKEN")

    if base_url and user and api_token:
        return base_url, user, api_token

    config_path = Path(os.environ.get("JIRA_CONFIG_FILE", str(JIRA_CONFIG_DEFAULT)))
    if not config_path.exists():
        logger.warning(
            "Jira env vars not fully set and jira-cli config not found at %s",
            config_path,
        )
        return base_url, user, api_token

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Failed to parse jira-cli config: %s", e)
        return base_url, user, api_token

    if not isinstance(config, dict):
        return base_url, user, api_token

    if not base_url and config.get("server"):
        base_url = str(config["server"])
    if not user and config.get("login"):
        user = str(config["login"])
    if not api_token and config.get("api_token"):
        api_token = str(config["api_token"])

    return base_url, user, api_token


def check_prerequisites() -> None:
    """Verify that required CLI tools are available on PATH.

    Raises:
        TicketRalphError: If any required command is missing.
    """
    from ticket_ralph.exceptions import TicketRalphError

    missing = [cmd for cmd in PREREQUISITE_COMMANDS if shutil.which(cmd) is None]
    if missing:
        raise TicketRalphError(
            f"Required commands not found: {', '.join(missing)}. "
            "Install them before running ticket-ralph."
        )
