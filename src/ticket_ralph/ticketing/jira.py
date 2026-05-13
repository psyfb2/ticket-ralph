"""Jira ticketing provider implementation.

Handles file sync (upload/download attachments) via the Jira REST API using
httpx. Ticket fetching and context gathering are delegated to the agent.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx
import yaml

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.settings import JiraSettings
from ticket_ralph.ticketing.base import TicketingProvider

logger = logging.getLogger("ticket-ralph")

JIRA_CONFIG_DEFAULT = Path.home() / ".config" / ".jira" / ".config.yml"


class JiraProvider(TicketingProvider):
    """Jira implementation of TicketingProvider."""

    def __init__(
        self,
        base_url: str | None = None,
        user: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.user = user
        self.api_token = api_token

    @classmethod
    def from_env(cls) -> "JiraProvider":
        """Create a JiraProvider by resolving credentials from env vars or jira-cli config.

        Resolution order:
            1. Environment variables: JIRA_BASE_URL, JIRA_USER, JIRA_API_TOKEN
            2. Fallback to jira-cli config at ~/.config/.jira/.config.yml

        Returns:
            Configured JiraProvider instance.
        """
        jira_settings = JiraSettings()
        base_url = jira_settings.base_url
        user = jira_settings.user
        api_token = jira_settings.api_token

        if base_url and user and api_token:
            return cls(base_url, user, api_token)

        config_path = jira_settings.config_file or JIRA_CONFIG_DEFAULT
        if not config_path.exists():
            logger.warning(
                "Jira env vars not fully set and jira-cli config not found at %s",
                config_path,
            )
            return cls(base_url, user, api_token)

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Failed to parse jira-cli config: %s", e)
            return cls(base_url, user, api_token)

        if not isinstance(config, dict):
            return cls(base_url, user, api_token)

        if not base_url and config.get("server"):
            base_url = str(config["server"])
        if not user and config.get("login"):
            user = str(config["login"])
        if not api_token and config.get("api_token"):
            api_token = str(config["api_token"])

        return cls(base_url, user, api_token)

    # --- Properties ---

    @property
    def provider_name(self) -> str:
        """Return 'Jira'."""
        return "Jira"

    @property
    def cli_commands(self) -> list[str]:
        """Jira requires the jira-cli tool."""
        return ["jira"]

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

    # --- Attachment operations ---

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
            if not resp.is_success:
                raise TicketRalphError(
                    f"Failed to list attachments for {issue_id}: "
                    f"HTTP {resp.status_code} — {resp.text}"
                )
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
