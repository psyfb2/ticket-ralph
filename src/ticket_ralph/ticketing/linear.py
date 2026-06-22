"""Linear ticketing provider implementation.

Handles file sync (upload/download attachments) via the Linear GraphQL API
using httpx. Ticket fetching and context gathering are delegated to the agent
(via the ``linear`` CLI).

Linear attachments wrap an externally-hosted URL rather than storing a file
directly, so uploading a file is a three-step flow: request a presigned upload
URL via the ``fileUpload`` mutation, PUT the bytes to it, then link the
resulting asset URL to the issue via ``attachmentCreate``. Issues are addressed
by a UUID internally, so the human identifier (e.g. ``ENG-123``) is resolved to
a UUID first.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.settings import LinearSettings
from ticket_ralph.ticketing.base import TicketingProvider

logger = logging.getLogger("ticket-ralph")

LINEAR_API_URL_DEFAULT = "https://api.linear.app/graphql"


class LinearProvider(TicketingProvider):
    """Linear implementation of TicketingProvider."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = LINEAR_API_URL_DEFAULT,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url

    @classmethod
    def from_env(cls) -> "LinearProvider":
        """Create a LinearProvider by resolving credentials from env vars.

        Reads ``LINEAR_API_KEY`` and ``LINEAR_API_URL`` (the latter defaults to
        the public Linear GraphQL endpoint).

        Returns:
            Configured LinearProvider instance.
        """
        settings = LinearSettings()
        if not settings.api_key:
            logger.warning("LINEAR_API_KEY not set — Linear sync will be unavailable")
        return cls(settings.api_key, settings.api_url)

    # --- Properties ---

    @property
    def provider_name(self) -> str:
        """Return 'Linear'."""
        return "Linear"

    @property
    def cli_commands(self) -> list[str]:
        """Linear requires the linear CLI for agent ticket fetching."""
        return ["linear"]

    # --- Internal helpers ---

    def _http_client(self) -> httpx.Client:
        """Create an httpx client with the Linear auth header."""
        if not self.api_key:
            raise TicketRalphError(
                "Cannot reach Linear — missing LINEAR_API_KEY credential"
            )
        # Linear personal API keys are sent verbatim, without a 'Bearer' prefix.
        headers = {"Authorization": self.api_key}
        return httpx.Client(headers=headers, follow_redirects=True, timeout=60.0)

    def _graphql(
        self, client: httpx.Client, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a GraphQL query/mutation, returning its ``data`` payload.

        Args:
            client: An httpx client carrying the auth header.
            query: The GraphQL document.
            variables: Variables for the document.

        Returns:
            The ``data`` object from the response.

        Raises:
            TicketRalphError: On transport failure or a GraphQL ``errors`` array.
        """
        resp = client.post(self.api_url, json={"query": query, "variables": variables})
        if not resp.is_success:
            raise TicketRalphError(
                f"Linear GraphQL request failed: HTTP {resp.status_code} — {resp.text}"
            )
        body = resp.json()
        if body.get("errors"):
            raise TicketRalphError(f"Linear GraphQL errors: {body['errors']}")
        return body.get("data") or {}

    def _resolve_issue_uuid(self, client: httpx.Client, issue_id: str) -> str | None:
        """Resolve a human identifier (e.g. ENG-123) to the issue UUID."""
        query = "query($id: String!){ issue(id: $id){ id } }"
        data = self._graphql(client, query, {"id": issue_id})
        issue = data.get("issue")
        if not issue:
            return None
        return issue.get("id")

    def _list_attachments(
        self, client: httpx.Client, issue_uuid: str
    ) -> list[dict[str, Any]]:
        """List attachments on an issue (id, title, url, createdAt)."""
        query = (
            "query($id: String!){ issue(id: $id){ "
            "attachments(first: 50){ nodes { id title url createdAt } } } }"
        )
        data = self._graphql(client, query, {"id": issue_uuid})
        issue = data.get("issue") or {}
        return (issue.get("attachments") or {}).get("nodes") or []

    # --- Attachment operations ---

    def upload_attachment(self, issue_id: str, file_path: Path) -> None:
        """Upload a file as an attachment, replacing any existing one by name.

        Args:
            issue_id: Linear issue identifier (e.g. ENG-123).
            file_path: Path to the file to upload.
        """
        if not file_path.exists():
            logger.warning("File not found, skipping upload: %s", file_path)
            return

        filename = file_path.name

        with self._http_client() as client:
            issue_uuid = self._resolve_issue_uuid(client, issue_id)
            if not issue_uuid:
                raise TicketRalphError(
                    f"Could not resolve Linear issue {issue_id} to upload {filename}"
                )

            # Delete existing attachments with the same title (replace semantics).
            for att in self._list_attachments(client, issue_uuid):
                if att.get("title") == filename:
                    self._graphql(
                        client,
                        "mutation($id: String!){ attachmentDelete(id: $id){ success } }",
                        {"id": att["id"]},
                    )
                    logger.info(
                        "Deleted existing attachment %s (%s) from %s",
                        att["id"],
                        filename,
                        issue_id,
                    )

            asset_url = self._upload_file(client, file_path)

            self._graphql(
                client,
                (
                    "mutation($input: AttachmentCreateInput!){ "
                    "attachmentCreate(input: $input){ success } }"
                ),
                {
                    "input": {
                        "issueId": issue_uuid,
                        "title": filename,
                        "url": asset_url,
                    }
                },
            )
            logger.info("Uploaded %s to %s", filename, issue_id)

    def _upload_file(self, client: httpx.Client, file_path: Path) -> str:
        """Upload bytes to Linear storage, returning the public asset URL.

        Requests a presigned URL via ``fileUpload`` then PUTs the file content
        to it, applying the headers Linear returns.
        """
        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        size = file_path.stat().st_size

        mutation = (
            "mutation($contentType: String!, $filename: String!, $size: Int!){ "
            "fileUpload(contentType: $contentType, filename: $filename, size: $size){ "
            "success uploadFile { uploadUrl assetUrl headers { key value } } } }"
        )
        data = self._graphql(
            client,
            mutation,
            {"contentType": content_type, "filename": filename, "size": size},
        )
        upload = (data.get("fileUpload") or {}).get("uploadFile")
        if not upload or not upload.get("uploadUrl") or not upload.get("assetUrl"):
            raise TicketRalphError(
                f"Linear did not return an upload URL for {filename}"
            )

        put_headers = {"Content-Type": content_type}
        for header in upload.get("headers") or []:
            put_headers[header["key"]] = header["value"]

        put_resp = client.put(
            upload["uploadUrl"], content=file_path.read_bytes(), headers=put_headers
        )
        if not put_resp.is_success:
            raise TicketRalphError(
                f"Failed to upload {filename} to Linear storage: "
                f"HTTP {put_resp.status_code} — {put_resp.text}"
            )
        return upload["assetUrl"]

    def download_attachment(
        self, issue_id: str, filename: str, output_path: Path
    ) -> bool:
        """Download a named attachment from an issue.

        Args:
            issue_id: Linear issue identifier (e.g. ENG-123).
            filename: Title of the attachment to download.
            output_path: Local path to write the downloaded file.

        Returns:
            True if found and downloaded, False otherwise.
        """
        with self._http_client() as client:
            issue_uuid = self._resolve_issue_uuid(client, issue_id)
            if not issue_uuid:
                logger.info("Linear issue %s not found", issue_id)
                return False

            matching = [
                a
                for a in self._list_attachments(client, issue_uuid)
                if a.get("title") == filename
            ]
            if not matching:
                logger.info(
                    "Attachment '%s' not found on %s (may not exist yet)",
                    filename,
                    issue_id,
                )
                return False

            # Sort by created date, take the most recent.
            matching.sort(key=lambda a: a.get("createdAt", ""))
            asset_url = matching[-1].get("url")
            if not asset_url:
                return False

            dl_resp = client.get(asset_url)
            if dl_resp.is_success:
                output_path.write_bytes(dl_resp.content)
                logger.info("Downloaded %s from %s", filename, issue_id)
                return True

        return False
