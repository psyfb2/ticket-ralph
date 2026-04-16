"""Tests for ticket_ralph.ticketing.jira."""

import json
import subprocess
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


class TestGetIssueRaw:
    def test_parses_json(self, provider: JiraProvider) -> None:
        issue_data = {"key": "PROJ-1", "fields": {"summary": "test"}}
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(issue_data), stderr=""
            )
            result = provider.get_issue_raw("PROJ-1")
        assert result["key"] == "PROJ-1"


class TestGetParentStoryKey:
    def test_finds_parent(self, provider: JiraProvider) -> None:
        issue_json = {
            "fields": {
                "issuelinks": [
                    {
                        "type": {"inward": "Child of"},
                        "inwardIssue": {
                            "key": "PROJ-100",
                            "fields": {"issuetype": {"name": "Story"}},
                        },
                    }
                ]
            }
        }
        assert provider._get_parent_story_key(issue_json) == "PROJ-100"

    def test_no_parent(self, provider: JiraProvider) -> None:
        issue_json = {"fields": {"issuelinks": []}}
        assert provider._get_parent_story_key(issue_json) is None

    def test_ignores_non_story(self, provider: JiraProvider) -> None:
        issue_json = {
            "fields": {
                "issuelinks": [
                    {
                        "type": {"inward": "Child of"},
                        "inwardIssue": {
                            "key": "PROJ-50",
                            "fields": {"issuetype": {"name": "Epic"}},
                        },
                    }
                ]
            }
        }
        assert provider._get_parent_story_key(issue_json) is None


class TestGetSubtasks:
    def test_returns_issues(self, provider: JiraProvider) -> None:
        data = {"issues": [{"key": "PROJ-2"}]}
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(data), stderr=""
            )
            result = provider.get_subtasks("PROJ-1")
        assert len(result) == 1

    def test_returns_empty_on_error(self, provider: JiraProvider) -> None:
        with patch.object(provider, "_jira_cli", side_effect=TicketRalphError("fail")):
            result = provider.get_subtasks("PROJ-1")
        assert result == []


class TestTransitionIssue:
    def test_calls_jira_move(self, provider: JiraProvider) -> None:
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            provider.transition_issue("PROJ-1", "Done")
            mock.assert_called_once_with(["issue", "move", "PROJ-1", "Done"])


class TestCreateSubtask:
    def test_returns_key(self, provider: JiraProvider) -> None:
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({"key": "PROJ-5"}),
                stderr="",
            )
            key = provider.create_subtask("PROJ-1", "subtask title")
        assert key == "PROJ-5"


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


class TestHasBlockedDependencies:
    def test_has_blockers(self, provider: JiraProvider) -> None:
        issue = {
            "fields": {
                "issuelinks": [
                    {
                        "type": {"inward": "is blocked by"},
                        "inwardIssue": {
                            "key": "PROJ-10",
                            "fields": {"status": {"name": "In Progress"}},
                        },
                    }
                ]
            }
        }
        with patch.object(provider, "get_issue_raw", return_value=issue):
            assert provider.has_blocked_dependencies("PROJ-1") is True

    def test_no_blockers_all_done(self, provider: JiraProvider) -> None:
        issue = {
            "fields": {
                "issuelinks": [
                    {
                        "type": {"inward": "is blocked by"},
                        "inwardIssue": {
                            "key": "PROJ-10",
                            "fields": {"status": {"name": "Done"}},
                        },
                    }
                ]
            }
        }
        with patch.object(provider, "get_issue_raw", return_value=issue):
            assert provider.has_blocked_dependencies("PROJ-1") is False

    def test_no_links(self, provider: JiraProvider) -> None:
        issue = {"fields": {"issuelinks": []}}
        with patch.object(provider, "get_issue_raw", return_value=issue):
            assert provider.has_blocked_dependencies("PROJ-1") is False


class TestFetchTicketContext:
    def test_writes_context_files(self, provider: JiraProvider, tmp_path: Path) -> None:
        issue_data = {
            "fields": {
                "summary": "Test ticket",
                "description": "Description",
                "issuetype": {"name": "Task"},
                "comment": {
                    "comments": [
                        {
                            "author": {"displayName": "User"},
                            "body": "A comment",
                            "created": "2024-01-01",
                        }
                    ]
                },
                "attachment": [],
                "issuelinks": [],
            }
        }
        with patch.object(provider, "get_issue_raw", return_value=issue_data):
            ctx = provider.fetch_ticket_context("PROJ-1", tmp_path)

        assert ctx.ticket_id == "PROJ-1"
        assert ctx.summary == "Test ticket"
        assert ctx.parent_key is None

        context_path = tmp_path / "ticket-context.json"
        assert context_path.exists()
        data = json.loads(context_path.read_text())
        assert data["ticketId"] == "PROJ-1"
        assert data["parentStoryKey"] is None

    def test_fetches_parent_context(
        self, provider: JiraProvider, tmp_path: Path
    ) -> None:
        child_data = {
            "fields": {
                "summary": "Child",
                "description": "",
                "issuetype": {"name": "Sub-task"},
                "comment": {"comments": []},
                "attachment": [],
                "issuelinks": [
                    {
                        "type": {"inward": "Child of"},
                        "inwardIssue": {
                            "key": "PROJ-100",
                            "fields": {"issuetype": {"name": "Story"}},
                        },
                    }
                ],
            }
        }
        parent_data = {
            "fields": {
                "summary": "Parent Story",
                "description": "Story desc",
                "issuetype": {"name": "Story"},
                "comment": {"comments": []},
                "attachment": [],
                "issuelinks": [],
            }
        }
        with patch.object(
            provider, "get_issue_raw", side_effect=[child_data, parent_data]
        ):
            ctx = provider.fetch_ticket_context("PROJ-1", tmp_path)

        assert ctx.parent_key == "PROJ-100"
        assert (tmp_path / "parent-context.json").exists()


class TestParseCliJson:
    def test_raises_on_non_json_output(self, provider: JiraProvider) -> None:
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Authentication failed", stderr=""
            )
            with pytest.raises(TicketRalphError, match="invalid JSON"):
                provider._parse_cli_json(["issue", "view", "PROJ-1", "--raw"])

    def test_parses_valid_json(self, provider: JiraProvider) -> None:
        with patch.object(provider, "_jira_cli") as mock:
            mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout='{"key": "PROJ-1"}', stderr=""
            )
            result = provider._parse_cli_json(["issue", "view", "PROJ-1", "--raw"])
        assert result == {"key": "PROJ-1"}


class TestFetchIssueContextAttachmentDownloads:
    def _make_issue_json(self, attachments: list[dict] | None = None) -> dict:
        return {
            "fields": {
                "summary": "Test",
                "description": "Desc",
                "issuetype": {"name": "Task"},
                "comment": {"comments": []},
                "attachment": attachments or [],
                "issuelinks": [],
            }
        }

    def test_downloads_attachments_successfully(
        self, provider: JiraProvider, tmp_path: Path
    ) -> None:
        issue = self._make_issue_json(
            [
                {
                    "filename": "data.json",
                    "content": "https://jira.example.com/att/1",
                }
            ]
        )
        mock_dl_resp = MagicMock()
        mock_dl_resp.is_success = True
        mock_dl_resp.content = b'{"key": "value"}'

        mock_client = MagicMock()
        mock_client.get.return_value = mock_dl_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(provider, "get_issue_raw", return_value=issue),
            patch.object(provider, "_http_client", return_value=mock_client),
        ):
            ctx = provider._fetch_issue_context("PROJ-1", tmp_path)

        assert len(ctx.attachments) == 1
        assert ctx.attachments[0]["filename"] == "data.json"
        assert (tmp_path / "data.json").exists()

    def test_skips_attachment_on_http_failure(
        self, provider: JiraProvider, tmp_path: Path
    ) -> None:
        issue = self._make_issue_json(
            [
                {
                    "filename": "fail.txt",
                    "content": "https://jira.example.com/att/2",
                }
            ]
        )
        mock_dl_resp = MagicMock()
        mock_dl_resp.is_success = False

        mock_client = MagicMock()
        mock_client.get.return_value = mock_dl_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(provider, "get_issue_raw", return_value=issue),
            patch.object(provider, "_http_client", return_value=mock_client),
        ):
            ctx = provider._fetch_issue_context("PROJ-1", tmp_path)

        assert len(ctx.attachments) == 0
