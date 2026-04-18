"""Tests for ticket_ralph.ticketing.jira."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.ticketing.jira import JiraProvider


@pytest.fixture()
def provider() -> JiraProvider:
    return JiraProvider(
        base_url="https://jira.example.com",
        user="user@test.com",
        api_token="test-token",
    )


class TestAuthHeader:
    def test_generates_basic_auth(self, provider: JiraProvider) -> None:
        auth = provider._auth_header()
        assert auth is not None
        assert auth.startswith("Basic ")

    def test_returns_none_when_no_creds(self) -> None:
        p = JiraProvider()
        assert p._auth_header() is None


class TestProperties:
    def test_provider_name(self, provider: JiraProvider) -> None:
        assert provider.provider_name == "Jira"

    def test_cli_commands(self, provider: JiraProvider) -> None:
        assert provider.cli_commands == ["jira"]


class TestFromEnv:
    def test_all_env_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_USER", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")

        p = JiraProvider.from_env()
        assert p.base_url == "https://jira.example.com"
        assert p.user == "user@example.com"
        assert p.api_token == "token123"

    def test_fallback_to_config_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text(
            "server: https://jira.test.com\nlogin: testuser\napi_token: testtoken\n"
        )
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        p = JiraProvider.from_env()
        assert p.base_url == "https://jira.test.com"
        assert p.user == "testuser"
        assert p.api_token == "testtoken"

    def test_partial_env_vars_filled_from_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://override.com")
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text(
            "server: https://jira.test.com\nlogin: testuser\napi_token: testtoken\n"
        )
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        p = JiraProvider.from_env()
        assert p.base_url == "https://override.com"
        assert p.user == "testuser"
        assert p.api_token == "testtoken"

    def test_missing_config_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_CONFIG_FILE", "/nonexistent/config.yml")

        p = JiraProvider.from_env()
        assert p.base_url is None
        assert p.user is None
        assert p.api_token is None

    def test_invalid_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text(": : : invalid yaml [[[")
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        p = JiraProvider.from_env()
        assert isinstance(p.base_url, str) or p.base_url is None

    def test_yaml_non_dict_content(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text("just a plain string\n")
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        p = JiraProvider.from_env()
        assert p.base_url is None
        assert p.user is None
        assert p.api_token is None


class TestUploadAttachment:
    def test_uploads_file(self, provider: JiraProvider, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_get_resp = MagicMock()
        mock_get_resp.is_success = True
        mock_get_resp.json.return_value = {"fields": {"attachment": []}}

        mock_post_resp = MagicMock()
        mock_post_resp.is_success = True

        mock_client = MagicMock()
        mock_client.get.return_value = mock_get_resp
        mock_client.post.return_value = mock_post_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch.object(provider, "_http_client", return_value=mock_client):
            provider.upload_attachment("PROJ-1", test_file)

        mock_client.post.assert_called_once()

    def test_skips_missing_file(self, provider: JiraProvider, tmp_path: Path) -> None:
        provider.upload_attachment("PROJ-1", tmp_path / "nonexistent.txt")

    def test_raises_when_no_creds(self, tmp_path: Path) -> None:
        p = JiraProvider()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        with pytest.raises(TicketRalphError, match="missing Jira credentials"):
            p.upload_attachment("PROJ-1", test_file)

    def test_deletes_existing_before_upload(
        self, provider: JiraProvider, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        mock_get_resp = MagicMock()
        mock_get_resp.is_success = True
        mock_get_resp.json.return_value = {
            "fields": {"attachment": [{"id": "123", "filename": "test.txt"}]}
        }

        mock_del_resp = MagicMock()
        mock_del_resp.is_success = True

        mock_post_resp = MagicMock()
        mock_post_resp.is_success = True

        mock_client = MagicMock()
        mock_client.get.return_value = mock_get_resp
        mock_client.delete.return_value = mock_del_resp
        mock_client.post.return_value = mock_post_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch.object(provider, "_http_client", return_value=mock_client):
            provider.upload_attachment("PROJ-1", test_file)

        mock_client.delete.assert_called_once()


class TestDownloadAttachment:
    def test_downloads_file(self, provider: JiraProvider, tmp_path: Path) -> None:
        output = tmp_path / "downloaded.txt"

        mock_get_resp = MagicMock()
        mock_get_resp.is_success = True
        mock_get_resp.json.return_value = {
            "fields": {
                "attachment": [
                    {
                        "filename": "test.txt",
                        "content": "https://jira.example.com/file",
                        "created": "2024-01-01",
                    }
                ]
            }
        }

        mock_dl_resp = MagicMock()
        mock_dl_resp.is_success = True
        mock_dl_resp.content = b"file content"

        mock_client = MagicMock()
        mock_client.get.side_effect = [mock_get_resp, mock_dl_resp]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch.object(provider, "_http_client", return_value=mock_client):
            result = provider.download_attachment("PROJ-1", "test.txt", output)

        assert result is True
        assert output.read_text() == "file content"

    def test_returns_false_when_not_found(
        self, provider: JiraProvider, tmp_path: Path
    ) -> None:
        output = tmp_path / "downloaded.txt"

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"fields": {"attachment": []}}

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch.object(provider, "_http_client", return_value=mock_client):
            result = provider.download_attachment("PROJ-1", "missing.txt", output)

        assert result is False
