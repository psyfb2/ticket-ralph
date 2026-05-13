"""Tests for ticket_ralph.settings."""

from pathlib import Path

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.settings import (
    AppSettings,
    JiraSettings,
    app_settings,
    load_app_settings,
)


class TestAppSettings:
    def test_defaults_when_only_platform_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")
        for var in (
            "TR_AUTONOMOUS",
            "TR_PERMISSION_MODE",
            "TR_TASK_PERMISSION_MODE",
            "TR_SYNC_PROVIDER",
            "TR_REVIEWER_LONG_CONTEXT",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = AppSettings()

        assert settings.ticketing_platform == "Jira"
        assert settings.autonomous is True
        assert settings.permission_mode == "acceptEdits"
        assert settings.task_permission_mode == "acceptEdits"
        assert settings.sync_provider == "noop"
        assert settings.reviewer_long_context is False

    def test_constructs_without_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TR_TICKETING_PLATFORM", raising=False)

        settings = AppSettings()

        assert settings.ticketing_platform is None
        assert settings.autonomous is True

    def test_bool_coercion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")
        monkeypatch.setenv("TR_AUTONOMOUS", "false")
        monkeypatch.setenv("TR_REVIEWER_LONG_CONTEXT", "true")

        settings = AppSettings()

        assert settings.autonomous is False
        assert settings.reviewer_long_context is True


class TestJiraSettings:
    def test_all_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in (
            "JIRA_BASE_URL",
            "JIRA_USER",
            "JIRA_API_TOKEN",
            "JIRA_CONFIG_FILE",
        ):
            monkeypatch.delenv(var, raising=False)

        settings = JiraSettings()

        assert settings.base_url is None
        assert settings.user is None
        assert settings.api_token is None
        assert settings.config_file is None

    def test_config_file_coerced_to_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JIRA_CONFIG_FILE", "/tmp/jira.yml")

        settings = JiraSettings()

        assert settings.config_file == Path("/tmp/jira.yml")


class TestAppSettingsHelper:
    def test_wraps_validation_error_for_invalid_bool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TR_AUTONOMOUS", "not-a-bool")

        with pytest.raises(TicketRalphError, match="Invalid TR_"):
            app_settings()

    def test_succeeds_without_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TR_TICKETING_PLATFORM", raising=False)

        settings = app_settings()

        assert settings.ticketing_platform is None


class TestLoadAppSettings:
    def test_raises_when_platform_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TR_TICKETING_PLATFORM", raising=False)

        with pytest.raises(TicketRalphError, match="TR_TICKETING_PLATFORM"):
            load_app_settings()

    def test_returns_settings_when_platform_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Linear")

        settings = load_app_settings()

        assert settings.ticketing_platform == "Linear"
