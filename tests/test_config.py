"""Tests for ticket_ralph.config."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.config import (
    TicketRalphConfig,
    _resolve_jira_env,
    check_prerequisites,
)
from ticket_ralph.exceptions import TicketRalphError


class TestResolveJiraEnv:
    def test_all_env_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_USER", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")

        url, user, token = _resolve_jira_env()
        assert url == "https://jira.example.com"
        assert user == "user@example.com"
        assert token == "token123"

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

        url, user, token = _resolve_jira_env()
        assert url == "https://jira.test.com"
        assert user == "testuser"
        assert token == "testtoken"

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

        url, user, token = _resolve_jira_env()
        assert url == "https://override.com"
        assert user == "testuser"
        assert token == "testtoken"

    def test_missing_config_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_CONFIG_FILE", "/nonexistent/config.yml")

        url, user, token = _resolve_jira_env()
        assert url is None
        assert user is None
        assert token is None

    def test_invalid_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text(": : : invalid yaml [[[")
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        url, user, token = _resolve_jira_env()
        # Should not crash, returns whatever was found
        assert isinstance(url, str) or url is None

    def test_yaml_non_dict_content(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Covers line 131: YAML parses to non-dict (e.g. a string)."""
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        config_file = tmp_path / "config.yml"
        config_file.write_text("just a plain string\n")
        monkeypatch.setenv("JIRA_CONFIG_FILE", str(config_file))

        url, user, token = _resolve_jira_env()
        assert url is None
        assert user is None
        assert token is None


class TestTicketRalphConfig:
    def test_from_env_creates_tmp_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://j.com")
        monkeypatch.setenv("JIRA_USER", "u")
        monkeypatch.setenv("JIRA_API_TOKEN", "t")

        tickets_dir = tmp_path / "tickets"
        with (
            patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
            patch("ticket_ralph.config.SETTINGS_FILE", tmp_path / "nonexistent.json"),
        ):
            config = TicketRalphConfig.from_env("PROJ-123")

        assert config.ticket_id == "PROJ-123"
        assert config.tmp_dir == tickets_dir / "PROJ-123"
        assert config.tmp_dir.exists()
        assert config.autonomous is False
        assert config.permission_mode == "acceptEdits"

    def test_autonomous_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_AUTONOMOUS", "true")
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_CONFIG_FILE", "/nonexistent")

        tickets_dir = tmp_path / "tickets"
        with (
            patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
            patch("ticket_ralph.config.SETTINGS_FILE", tmp_path / "nonexistent.json"),
        ):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.autonomous is True

    def test_custom_permission_modes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_PERMISSION_MODE", "bypassPermissions")
        monkeypatch.setenv("TR_TASK_PERMISSION_MODE", "plan")
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_USER", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_CONFIG_FILE", "/nonexistent")

        tickets_dir = tmp_path / "tickets"
        with (
            patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
            patch("ticket_ralph.config.SETTINGS_FILE", tmp_path / "nonexistent.json"),
        ):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.permission_mode == "bypassPermissions"
        assert config.task_permission_mode == "plan"


class TestCheckPrerequisites:
    def test_all_present(self) -> None:
        with patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3", "git"]):
            check_prerequisites()

    def test_missing_command(self) -> None:
        with (
            patch(
                "ticket_ralph.config.PREREQUISITE_COMMANDS",
                ["nonexistent_command_xyz"],
            ),
            pytest.raises(TicketRalphError, match="nonexistent_command_xyz"),
        ):
            check_prerequisites()
