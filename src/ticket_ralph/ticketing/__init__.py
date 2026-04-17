"""Ticketing provider package.

Use ``create_provider`` to obtain the right provider for the configured
ticketing platform.
"""

from __future__ import annotations

import logging

from ticket_ralph.ticketing.base import TicketingProvider
from ticket_ralph.ticketing.noop import NoOpProvider

logger = logging.getLogger("ticket-ralph")

__all__ = ["TicketingProvider", "create_provider"]


def create_provider(platform: str) -> TicketingProvider:
    """Create a ticketing provider by platform name.

    Recognized platforms get their full provider. Unrecognized platforms
    get a NoOpProvider (sync is skipped with a warning).

    Args:
        platform: Platform identifier (e.g. 'jira', 'linear').

    Returns:
        A TicketingProvider instance.
    """
    if platform == "jira":
        from ticket_ralph.ticketing.jira import JiraProvider

        return JiraProvider.from_env()

    logger.warning(
        "Ticketing platform '%s' is not supported for file syncing. "
        "PRD.json and progress.txt will only be stored locally.",
        platform,
    )
    return NoOpProvider(platform)
