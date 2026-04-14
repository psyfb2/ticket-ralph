"""Ticketing provider abstraction.

Defines the Protocol that all ticketing platform implementations must satisfy,
plus shared data classes for normalized ticket data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class TicketContext:
    """Normalized ticket data from any ticketing platform."""

    ticket_id: str
    issue_type: str
    summary: str
    description: str
    comments: list[dict[str, str]] = field(default_factory=list)
    attachments: list[dict[str, str]] = field(default_factory=list)
    parent_key: str | None = None


class TicketingProvider(Protocol):
    """Interface for ticketing platform operations.

    Implementations: JiraProvider, (future) LinearProvider, GitHubIssuesProvider.
    """

    def get_issue_raw(self, issue_id: str) -> dict:
        """Fetch the raw issue data as a dict."""
        ...

    def get_subtasks(self, parent_id: str) -> list[dict]:
        """Return child issues / subtasks for a parent issue."""
        ...

    def fetch_ticket_context(
        self,
        ticket_id: str,
        tmp_dir: Path,
        *,
        download_attachments: bool = True,
    ) -> TicketContext:
        """Fetch ticket data and optionally download attachments.

        Args:
            ticket_id: The issue identifier.
            tmp_dir: Directory to store downloaded attachments.
            download_attachments: Whether to download file attachments.

        Returns:
            Normalized ticket context.
        """
        ...

    def upload_attachment(self, issue_id: str, file_path: Path) -> None:
        """Upload a file as an attachment to an issue."""
        ...

    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """Download a named attachment from an issue.

        Returns:
            True if the attachment was found and downloaded, False otherwise.
        """
        ...

    def transition_issue(self, issue_id: str, status: str) -> None:
        """Move an issue to a new status."""
        ...

    def create_subtask(
        self, parent_id: str, summary: str, description: str = ""
    ) -> str:
        """Create a subtask under a parent issue.

        Returns:
            The key/ID of the created subtask.
        """
        ...

    def add_comment(self, issue_id: str, comment: str) -> None:
        """Add a comment to an issue."""
        ...

    def has_blocked_dependencies(self, task_id: str) -> bool:
        """Check if a task has unresolved blocking dependencies."""
        ...
