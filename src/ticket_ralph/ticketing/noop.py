"""No-op ticketing provider for unsupported platforms.

Used when the configured ticketing platform has no sync implementation.
All sync operations are silently skipped.
"""

from __future__ import annotations

from pathlib import Path

from ticket_ralph.ticketing.base import TicketingProvider


class NoOpProvider(TicketingProvider):
    """No-op provider — sync calls are silently skipped."""

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

    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """No-op: nothing to download."""
        return False
