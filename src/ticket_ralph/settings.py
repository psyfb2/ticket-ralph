"""Centralized environment-variable loading via pydantic-settings.

All env vars consumed by ticket-ralph are declared here so defaults, types,
and coercion live in one place. Call sites read from these classes instead
of touching ``os.environ`` directly.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ticket_ralph.exceptions import TicketRalphError


class AppSettings(BaseSettings):
    """Application-level settings sourced from ``TR_*`` env vars.

    ``ticketing_platform`` is typed as optional here so the class can be
    constructed without it (e.g. for the autonomous-mode warning that runs
    before any command). Commands that need it should call
    ``load_app_settings()``, which enforces the required check.
    """

    model_config = SettingsConfigDict(
        env_prefix="TR_",
        extra="ignore",
        case_sensitive=False,
    )

    ticketing_platform: str | None = None
    autonomous: bool = True
    permission_mode: str = "acceptEdits"
    task_permission_mode: str = "acceptEdits"
    sync_provider: str = "noop"
    reviewer_long_context: bool = False


class JiraSettings(BaseSettings):
    """Jira-provider settings sourced from ``JIRA_*`` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="JIRA_",
        extra="ignore",
        case_sensitive=False,
    )

    base_url: str | None = None
    user: str | None = None
    api_token: str | None = None
    config_file: Path | None = None


def app_settings() -> AppSettings:
    """Construct ``AppSettings``, translating env-var errors into ``TicketRalphError``.

    Does not enforce that ``ticketing_platform`` is set — callers that need
    that should use :func:`load_app_settings`.

    Raises:
        TicketRalphError: If any ``TR_*`` env var fails pydantic validation
            (e.g. an unparseable boolean for ``TR_AUTONOMOUS``).
    """
    try:
        return AppSettings()
    except ValidationError as e:
        raise TicketRalphError(f"Invalid TR_* environment variable: {e}") from e


def load_app_settings() -> AppSettings:
    """Load ``AppSettings`` and enforce that ``ticketing_platform`` is set.

    Returns:
        A fully resolved ``AppSettings`` instance.

    Raises:
        TicketRalphError: If ``TR_TICKETING_PLATFORM`` is not set, or if any
            ``TR_*`` env var fails pydantic validation.
    """
    settings = app_settings()
    if not settings.ticketing_platform:
        raise TicketRalphError(
            "TR_TICKETING_PLATFORM env var is required but not set. "
            "Set it to your ticketing platform name (e.g. 'Jira', 'Linear')."
        )
    return settings
