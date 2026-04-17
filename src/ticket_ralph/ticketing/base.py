"""Ticketing provider abstraction.

Defines the ABC that all ticketing platform implementations must satisfy.
Providers handle file sync (upload/download attachments) between agent runs.
Ticket fetching, parent context, and attachment reading are delegated to agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TicketingProvider(ABC):
    """Base class for ticketing platform sync operations.

    Subclasses: JiraProvider, NoOpProvider.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable platform name (e.g. 'Jira', 'Linear')."""
        ...

    @property
    @abstractmethod
    def cli_commands(self) -> list[str]:
        """CLI tools required by this provider (e.g. ['jira'])."""
        ...

    @abstractmethod
    def upload_attachment(self, issue_id: str, file_path: Path) -> None:
        """Upload a file as an attachment to an issue."""
        ...

    @abstractmethod
    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """Download a named attachment from an issue.

        Returns:
            True if the attachment was found and downloaded, False otherwise.
        """
        ...
