"""Jira ticketing provider implementation.

Uses jira-cli (subprocess) for issue operations and httpx for attachment
upload/download (since jira-cli doesn't support attachments).
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from pathlib import Path

import httpx

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.ticketing.base import TicketContext

logger = logging.getLogger("ticket-ralph")


class JiraProvider:
    """Jira implementation of the TicketingProvider protocol."""

    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.user = user
        self.api_token = api_token

    # --- Internal helpers ---

    def _auth_header(self) -> str | None:
        """Build a Basic auth header value, or None if creds are missing."""
        if self.user and self.api_token:
            encoded = base64.b64encode(
                f"{self.user}:{self.api_token}".encode()
            ).decode()
            return f"Basic {encoded}"
        return None

    def _http_client(self) -> httpx.Client:
        """Create an httpx client with Jira auth headers."""
        auth = self._auth_header()
        headers: dict[str, str] = {}
        if auth:
            headers["Authorization"] = auth
        return httpx.Client(headers=headers, follow_redirects=True, timeout=60.0)

    def _jira_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a jira-cli command.

        Args:
            args: Arguments to pass after 'jira'.

        Returns:
            Completed process result.

        Raises:
            TicketRalphError: If the command fails.
        """
        cmd = ["jira", *args]
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise TicketRalphError(
                f"jira {' '.join(args)} failed (exit {e.returncode}): "
                f"{e.stderr.strip()}"
            ) from e

    def _parse_cli_json(self, args: list[str]) -> dict:
        """Run a jira-cli command and parse its stdout as JSON.

        Args:
            args: Arguments to pass after 'jira'.

        Returns:
            Parsed JSON dict.

        Raises:
            TicketRalphError: If the command fails or returns non-JSON.
        """
        result = self._jira_cli(args)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise TicketRalphError(
                f"jira {' '.join(args)} returned invalid JSON: {e}\n"
                f"stdout: {result.stdout[:200]}"
            ) from e

    # --- Read operations ---

    def get_issue_raw(self, issue_id: str) -> dict:
        """Fetch the raw issue JSON from Jira.

        Args:
            issue_id: Jira issue key (e.g. PROJ-123).

        Returns:
            Parsed issue JSON as a dict.
        """
        return self._parse_cli_json(["issue", "view", issue_id, "--raw"])

    def _get_parent_story_key(self, issue_json: dict) -> str | None:
        """Extract the parent Story key from issue links.

        Only matches "Child of" links where the inward issue is a Story.

        Args:
            issue_json: Raw issue JSON dict.

        Returns:
            Parent story key, or None if not found.
        """
        links = issue_json.get("fields", {}).get("issuelinks") or []
        for link in links:
            if link.get("type", {}).get("inward") != "Child of":
                continue
            inward = link.get("inwardIssue", {})
            issue_type = inward.get("fields", {}).get("issuetype", {}).get("name", "")
            if issue_type == "Story":
                return inward.get("key")
        return None

    def get_subtasks(self, parent_id: str) -> list[dict]:
        """Return child issues for a parent issue.

        Args:
            parent_id: Parent issue key (e.g. PROJ-123).

        Returns:
            List of issue dicts, or empty list.
        """
        project = parent_id.split("-")[0]
        try:
            data = self._parse_cli_json(
                ["issue", "list", "-p", project, "-P", parent_id, "--raw"]
            )
            return data.get("issues") or []
        except TicketRalphError:
            return []

    # --- Write operations ---

    def transition_issue(self, issue_id: str, status: str) -> None:
        """Move an issue to a new status.

        Args:
            issue_id: Jira issue key.
            status: Target status name.
        """
        self._jira_cli(["issue", "move", issue_id, status])
        logger.info("Transitioned %s to '%s'", issue_id, status)

    def create_subtask(
        self, parent_id: str, summary: str, description: str = ""
    ) -> str:
        """Create a subtask under a parent issue.

        Args:
            parent_id: Parent issue key.
            summary: Subtask summary.
            description: Subtask description.

        Returns:
            The key of the created subtask.
        """
        project = parent_id.split("-")[0]
        args = [
            "issue",
            "create",
            "--raw",
            "--no-input",
            "-p",
            project,
            "-t",
            "Sub-task",
            "-P",
            parent_id,
            "-s",
            summary,
        ]
        if description:
            args.extend(["-b", description])
        data = self._parse_cli_json(args)
        return data.get("key", "")

    def add_comment(self, issue_id: str, comment: str) -> None:
        """Add a comment to an issue.

        Args:
            issue_id: Jira issue key.
            comment: Comment text.
        """
        self._jira_cli(["issue", "comment", "add", issue_id, comment])

    # --- Attachment operations (httpx) ---

    def upload_attachment(self, issue_id: str, file_path: Path) -> None:
        """Upload a file as an attachment, replacing any existing one with the same name.

        Args:
            issue_id: Jira issue key.
            file_path: Path to the file to upload.
        """
        if not file_path.exists():
            logger.warning("File not found, skipping upload: %s", file_path)
            return

        if not self.base_url or not self._auth_header():
            raise TicketRalphError(
                "Cannot upload attachment — missing Jira credentials or base URL"
            )

        filename = file_path.name

        with self._http_client() as client:
            # Delete existing attachments with the same filename
            resp = client.get(
                f"{self.base_url}/rest/api/2/issue/{issue_id}",
                params={"fields": "attachment"},
                headers={"Accept": "application/json"},
            )
            if resp.is_success:
                existing = resp.json().get("fields", {}).get("attachment") or []
                for att in existing:
                    if att.get("filename") == filename:
                        del_resp = client.delete(
                            f"{self.base_url}/rest/api/2/attachment/{att['id']}"
                        )
                        if del_resp.is_success:
                            logger.info(
                                "Deleted existing attachment %s (%s) from %s",
                                att["id"],
                                filename,
                                issue_id,
                            )

            # Upload the new file
            with open(file_path, "rb") as f:
                resp = client.post(
                    f"{self.base_url}/rest/api/2/issue/{issue_id}/attachments",
                    headers={"X-Atlassian-Token": "no-check"},
                    files={"file": (filename, f)},
                )

            if not resp.is_success:
                raise TicketRalphError(
                    f"Failed to upload {filename} to {issue_id}: "
                    f"HTTP {resp.status_code} — {resp.text}"
                )
            logger.info("Uploaded %s to %s", filename, issue_id)

    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """Download a named attachment from an issue.

        Downloads the most recent attachment matching the filename.

        Args:
            issue_id: Jira issue key.
            filename: Name of the attachment file.
            output_path: Local path to write the downloaded file.

        Returns:
            True if found and downloaded, False otherwise.
        """
        if not self.base_url or not self._auth_header():
            raise TicketRalphError(
                "Cannot download attachment — missing Jira credentials or base URL"
            )

        with self._http_client() as client:
            resp = client.get(
                f"{self.base_url}/rest/api/2/issue/{issue_id}",
                params={"fields": "attachment"},
                headers={"Accept": "application/json"},
            )
            if not resp.is_success:
                return False

            attachments = resp.json().get("fields", {}).get("attachment") or []
            matching = [a for a in attachments if a.get("filename") == filename]
            if not matching:
                logger.info(
                    "Attachment '%s' not found on %s (may not exist yet)",
                    filename,
                    issue_id,
                )
                return False

            # Sort by created date, take the most recent
            matching.sort(key=lambda a: a.get("created", ""))
            content_url = matching[-1].get("content")
            if not content_url:
                return False

            dl_resp = client.get(content_url)
            if dl_resp.is_success:
                output_path.write_bytes(dl_resp.content)
                logger.info("Downloaded %s from %s", filename, issue_id)
                return True

        return False

    # --- Dependency checking ---

    def has_blocked_dependencies(self, task_id: str) -> bool:
        """Check if a task has unresolved blocking dependencies.

        Args:
            task_id: Jira issue key.

        Returns:
            True if there are blockers not in Done status.
        """
        issue = self.get_issue_raw(task_id)
        links = issue.get("fields", {}).get("issuelinks") or []
        for link in links:
            if link.get("type", {}).get("inward") != "is blocked by":
                continue
            inward = link.get("inwardIssue", {})
            status = (
                inward.get("fields", {}).get("status", {}).get("name", "")
            ).lower()
            if status != "done":
                return True
        return False

    # --- Ticket context fetching ---

    def _fetch_issue_context(
        self,
        issue_id: str,
        tmp_dir: Path,
        *,
        download_attachments: bool = True,
    ) -> TicketContext:
        """Fetch issue data and optionally download attachments.

        Args:
            issue_id: Jira issue key.
            tmp_dir: Directory to store downloaded attachments.
            download_attachments: Whether to download file attachments.

        Returns:
            Normalized ticket context.
        """
        issue_json = self.get_issue_raw(issue_id)
        fields = issue_json.get("fields", {})

        summary = fields.get("summary") or ""
        description = fields.get("description") or ""
        issue_type = fields.get("issuetype", {}).get("name", "")
        parent_key = self._get_parent_story_key(issue_json)

        # Extract comments
        raw_comments = fields.get("comment", {}).get("comments") or []
        comments = [
            {
                "author": c.get("author", {}).get("displayName", ""),
                "body": c.get("body", ""),
                "created": c.get("created", ""),
            }
            for c in raw_comments
        ]

        # Extract and optionally download attachments
        raw_attachments = fields.get("attachment") or []
        attachments: list[dict[str, str]] = []

        if raw_attachments and download_attachments:
            logger.info(
                "Downloading %d attachment(s) for %s",
                len(raw_attachments),
                issue_id,
            )
            auth = self._auth_header()
            if auth:
                with self._http_client() as client:
                    for att in raw_attachments:
                        fname = att.get("filename", "")
                        content_url = att.get("content", "")
                        local_path = tmp_dir / fname
                        try:
                            resp = client.get(content_url)
                            if resp.is_success:
                                local_path.write_bytes(resp.content)
                                logger.info("Downloaded attachment: %s", fname)
                                attachments.append(
                                    {
                                        "filename": fname,
                                        "localPath": str(local_path),
                                    }
                                )
                            else:
                                logger.warning(
                                    "Failed to download %s — skipping", fname
                                )
                        except httpx.HTTPError:
                            logger.warning("Failed to download %s — skipping", fname)
        elif raw_attachments:
            # List attachments without downloading
            attachments = [
                {"filename": att.get("filename", "")} for att in raw_attachments
            ]

        return TicketContext(
            ticket_id=issue_id,
            issue_type=issue_type,
            summary=summary,
            description=description,
            comments=comments,
            attachments=attachments,
            parent_key=parent_key,
        )

    def fetch_ticket_context(
        self,
        ticket_id: str,
        tmp_dir: Path,
        *,
        download_attachments: bool = True,
    ) -> TicketContext:
        """Fetch ticket data and save context JSON files.

        Writes ticket-context.json to tmp_dir. If the ticket is a child of a
        Story, also fetches the parent and writes parent-context.json.

        Args:
            ticket_id: Jira issue key.
            tmp_dir: Directory to store context files and attachments.
            download_attachments: Whether to download file attachments.

        Returns:
            The ticket context for the main ticket.
        """
        logger.info("Fetching Jira ticket data for %s", ticket_id)

        context = self._fetch_issue_context(
            ticket_id, tmp_dir, download_attachments=download_attachments
        )
        context_path = tmp_dir / "ticket-context.json"
        context_path.write_text(json.dumps(_ticket_context_to_dict(context), indent=2))
        logger.info("Ticket context written to %s", context_path)

        if context.parent_key:
            logger.info(
                "Ticket is child of story %s — fetching story context",
                context.parent_key,
            )
            parent_context = self._fetch_issue_context(
                context.parent_key, tmp_dir, download_attachments=False
            )
            parent_path = tmp_dir / "parent-context.json"
            parent_path.write_text(
                json.dumps(_ticket_context_to_dict(parent_context), indent=2)
            )
            logger.info("Parent story context written to %s", parent_path)

        return context


def _ticket_context_to_dict(ctx: TicketContext) -> dict:
    """Convert a TicketContext to the JSON-serializable dict format.

    Matches the existing ticket-context.json schema used by agents.
    """
    return {
        "ticketId": ctx.ticket_id,
        "issueType": ctx.issue_type,
        "summary": ctx.summary,
        "description": ctx.description,
        "comments": ctx.comments,
        "attachments": ctx.attachments,
        "parentStoryKey": ctx.parent_key,
    }
