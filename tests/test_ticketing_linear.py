"""Tests for ticket_ralph.ticketing.linear."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.ticketing.linear import LinearProvider


@pytest.fixture()
def provider() -> LinearProvider:
    return LinearProvider(api_key="test-key")


def _graphql_resp(data: dict[str, Any]) -> MagicMock:
    """Build a mock httpx response for a successful GraphQL call."""
    resp = MagicMock()
    resp.is_success = True
    resp.json.return_value = {"data": data}
    return resp


def _mock_client() -> MagicMock:
    """Build a mock httpx client usable as a context manager."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


class TestHttpClient:
    def test_raises_without_api_key(self) -> None:
        p = LinearProvider()
        with pytest.raises(TicketRalphError, match="missing LINEAR_API_KEY"):
            p._http_client()

    def test_sets_authorization_header(self, provider: LinearProvider) -> None:
        client = provider._http_client()
        try:
            assert client.headers["Authorization"] == "test-key"
        finally:
            client.close()


class TestProperties:
    def test_provider_name(self, provider: LinearProvider) -> None:
        assert provider.provider_name == "Linear"

    def test_cli_commands(self, provider: LinearProvider) -> None:
        assert provider.cli_commands == ["linear"]


class TestFromEnv:
    def test_reads_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LINEAR_API_KEY", "lin_key_123")
        monkeypatch.delenv("LINEAR_API_URL", raising=False)

        p = LinearProvider.from_env()

        assert p.api_key == "lin_key_123"
        assert p.api_url == "https://api.linear.app/graphql"

    def test_custom_api_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LINEAR_API_KEY", "lin_key_123")
        monkeypatch.setenv("LINEAR_API_URL", "https://linear.test/graphql")

        p = LinearProvider.from_env()

        assert p.api_url == "https://linear.test/graphql"

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)

        p = LinearProvider.from_env()

        assert p.api_key is None


class TestGraphqlErrors:
    def test_raises_on_http_failure(self, provider: LinearProvider) -> None:
        resp = MagicMock()
        resp.is_success = False
        resp.status_code = 500
        resp.text = "boom"
        client = MagicMock()
        client.post.return_value = resp

        with pytest.raises(TicketRalphError, match="Linear GraphQL request failed"):
            provider._graphql(client, "query", {})

    def test_raises_on_graphql_errors(self, provider: LinearProvider) -> None:
        resp = MagicMock()
        resp.is_success = True
        resp.json.return_value = {"errors": [{"message": "bad"}]}
        client = MagicMock()
        client.post.return_value = resp

        with pytest.raises(TicketRalphError, match="Linear GraphQL errors"):
            provider._graphql(client, "query", {})


class TestUploadAttachment:
    def test_uploads_file(self, provider: LinearProvider, tmp_path: Path) -> None:
        test_file = tmp_path / "PRD.json"
        test_file.write_text("{}")

        client = _mock_client()
        client.post.side_effect = [
            _graphql_resp({"issue": {"id": "uuid-1"}}),  # resolve uuid
            _graphql_resp({"issue": {"attachments": {"nodes": []}}}),  # list
            _graphql_resp(  # fileUpload
                {
                    "fileUpload": {
                        "uploadFile": {
                            "uploadUrl": "https://upload.linear/abc",
                            "assetUrl": "https://assets.linear/abc",
                            "headers": [{"key": "x-amz", "value": "1"}],
                        }
                    }
                }
            ),
            _graphql_resp({"attachmentCreate": {"success": True}}),  # create
        ]
        put_resp = MagicMock()
        put_resp.is_success = True
        client.put.return_value = put_resp

        with patch.object(provider, "_http_client", return_value=client):
            provider.upload_attachment("ENG-1", test_file)

        client.put.assert_called_once()
        assert client.post.call_count == 4

    def test_deletes_existing_before_upload(
        self, provider: LinearProvider, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "PRD.json"
        test_file.write_text("{}")

        client = _mock_client()
        client.post.side_effect = [
            _graphql_resp({"issue": {"id": "uuid-1"}}),  # resolve uuid
            _graphql_resp(  # list — one matching attachment
                {
                    "issue": {
                        "attachments": {"nodes": [{"id": "att-9", "title": "PRD.json"}]}
                    }
                }
            ),
            _graphql_resp({"attachmentDelete": {"success": True}}),  # delete
            _graphql_resp(  # fileUpload
                {
                    "fileUpload": {
                        "uploadFile": {
                            "uploadUrl": "https://upload.linear/abc",
                            "assetUrl": "https://assets.linear/abc",
                            "headers": [],
                        }
                    }
                }
            ),
            _graphql_resp({"attachmentCreate": {"success": True}}),  # create
        ]
        put_resp = MagicMock()
        put_resp.is_success = True
        client.put.return_value = put_resp

        with patch.object(provider, "_http_client", return_value=client):
            provider.upload_attachment("ENG-1", test_file)

        assert client.post.call_count == 5

    def test_skips_missing_file(self, provider: LinearProvider, tmp_path: Path) -> None:
        provider.upload_attachment("ENG-1", tmp_path / "nope.json")

    def test_raises_when_issue_unresolved(
        self, provider: LinearProvider, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "PRD.json"
        test_file.write_text("{}")

        client = _mock_client()
        client.post.return_value = _graphql_resp({"issue": None})

        with patch.object(provider, "_http_client", return_value=client):
            with pytest.raises(TicketRalphError, match="Could not resolve"):
                provider.upload_attachment("ENG-404", test_file)

    def test_raises_when_no_upload_url(
        self, provider: LinearProvider, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "PRD.json"
        test_file.write_text("{}")

        client = _mock_client()
        client.post.side_effect = [
            _graphql_resp({"issue": {"id": "uuid-1"}}),
            _graphql_resp({"issue": {"attachments": {"nodes": []}}}),
            _graphql_resp({"fileUpload": {"uploadFile": None}}),
        ]

        with patch.object(provider, "_http_client", return_value=client):
            with pytest.raises(TicketRalphError, match="did not return an upload URL"):
                provider.upload_attachment("ENG-1", test_file)


class TestDownloadAttachment:
    def test_downloads_file(self, provider: LinearProvider, tmp_path: Path) -> None:
        output = tmp_path / "out.json"

        client = _mock_client()
        client.post.side_effect = [
            _graphql_resp({"issue": {"id": "uuid-1"}}),  # resolve uuid
            _graphql_resp(  # list
                {
                    "issue": {
                        "attachments": {
                            "nodes": [
                                {
                                    "id": "att-1",
                                    "title": "PRD.json",
                                    "url": "https://assets.linear/abc",
                                    "createdAt": "2024-01-01",
                                }
                            ]
                        }
                    }
                }
            ),
        ]
        dl_resp = MagicMock()
        dl_resp.is_success = True
        dl_resp.content = b"file content"
        client.get.return_value = dl_resp

        with patch.object(provider, "_http_client", return_value=client):
            result = provider.download_attachment("ENG-1", "PRD.json", output)

        assert result is True
        assert output.read_text() == "file content"

    def test_returns_false_when_issue_missing(
        self, provider: LinearProvider, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.json"

        client = _mock_client()
        client.post.return_value = _graphql_resp({"issue": None})

        with patch.object(provider, "_http_client", return_value=client):
            result = provider.download_attachment("ENG-404", "PRD.json", output)

        assert result is False

    def test_returns_false_when_not_found(
        self, provider: LinearProvider, tmp_path: Path
    ) -> None:
        output = tmp_path / "out.json"

        client = _mock_client()
        client.post.side_effect = [
            _graphql_resp({"issue": {"id": "uuid-1"}}),
            _graphql_resp({"issue": {"attachments": {"nodes": []}}}),
        ]

        with patch.object(provider, "_http_client", return_value=client):
            result = provider.download_attachment("ENG-1", "missing.json", output)

        assert result is False
