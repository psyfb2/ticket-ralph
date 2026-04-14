"""File synchronization between local tmp directory and ticketing platform."""

import logging
from pathlib import Path

from ticket_ralph.ticketing.base import TicketingProvider

logger = logging.getLogger("ticket-ralph")


class SyncService:
    """Syncs files between local storage and the ticketing platform."""

    def __init__(self, provider: TicketingProvider, tmp_dir: Path) -> None:
        self.provider = provider
        self.tmp_dir = tmp_dir

    def sync_to_ticketing(self, issue_id: str, file_path: Path) -> None:
        """Upload a local file as an attachment on the issue.

        Args:
            issue_id: The issue identifier.
            file_path: Path to the local file to upload.
        """
        if file_path.exists():
            logger.info("Syncing %s -> %s", file_path.name, issue_id)
            self.provider.upload_attachment(issue_id, file_path)

    def sync_from_ticketing(
        self,
        issue_id: str,
        filename: str,
        output_path: Path | None = None,
    ) -> None:
        """Download an attachment from the issue to local storage.

        Args:
            issue_id: The issue identifier.
            filename: Name of the attachment to download.
            output_path: Where to save. Defaults to tmp_dir / filename.
        """
        dest = output_path or self.tmp_dir / filename
        logger.info("Syncing %s -> %s", issue_id, filename)
        self.provider.download_attachment(issue_id, filename, dest)

    def sync_ticket_files(self, ticket_id: str) -> None:
        """Upload PRD.json and progress.txt to the ticketing platform.

        Args:
            ticket_id: The issue identifier.
        """
        self.sync_to_ticketing(ticket_id, self.tmp_dir / "PRD.json")
        self.sync_to_ticketing(ticket_id, self.tmp_dir / "progress.txt")

    def download_ticket_context(self, ticket_id: str) -> None:
        """Download PRD.json and progress.txt from the ticketing platform.

        Args:
            ticket_id: The issue identifier.
        """
        self.sync_from_ticketing(ticket_id, "PRD.json")
        self.sync_from_ticketing(ticket_id, "progress.txt")
