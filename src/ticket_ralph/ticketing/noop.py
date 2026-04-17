"""No-op ticketing provider for unsupported platforms.

Used when the configured ticketing platform has no sync implementation.
All sync operations are skipped with a warning.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ticket_ralph.ticketing.base import TicketingProvider

logger = logging.getLogger("ticket-ralph")


class NoOpProvider(TicketingProvider):
    """No-op provider — sync calls are skipped with a warning."""

    def __init__(self, platform_name: str) -> None:
        self._platform_name = platform_name

    @property
    def provider_name(self) -> str:
        """Return the platform name passed at construction."""
        return self._platform_name

    @property
    def cli_commands(self) -> list[str]:
        """No CLI tools required."""
        return []

    def upload_attachment(self, issue_id: str, file_path: Path) -> None:
        """No-op: skip upload."""
        logger.warning(
            "Sync skipped for platform '%s' — upload of %s to %s not available.",
            self._platform_name,
            file_path.name,
            issue_id,
        )

    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """No-op: nothing to download."""
        logger.warning(
            "Sync skipped for platform '%s' — download of %s from %s not available.",
            self._platform_name,
            filename,
            issue_id,
        )
        return False
