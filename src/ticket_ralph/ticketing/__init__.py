"""Ticketing provider package.

Use ``create_provider`` to obtain the right provider for the configured
ticketing platform.
"""

from __future__ import annotations

from ticket_ralph.ticketing.base import TicketingProvider
from ticket_ralph.ticketing.noop import NoOpProvider

__all__ = ["TicketingProvider", "create_provider"]


def create_provider(sync_provider: str) -> TicketingProvider:
    """Create a ticketing provider by sync provider name.

    Recognized providers get their full implementation. Unrecognized
    providers get a NoOpProvider (sync is skipped with a warning).

    Args:
        sync_provider: Sync provider identifier (e.g. 'jira', 'noop').

    Returns:
        A TicketingProvider instance.
    """
    if sync_provider == "jira":
        from ticket_ralph.ticketing.jira import JiraProvider

        return JiraProvider.from_env()

    return NoOpProvider(sync_provider)
