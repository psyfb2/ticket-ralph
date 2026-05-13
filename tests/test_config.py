"""Tests for ticket_ralph.config."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_ralph.config import (
    TicketRalphConfig,
    check_prerequisites,
)
from ticket_ralph.exceptions import TicketRalphError


class TestTicketRalphConfig:
    def test_from_env_creates_tmp_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")
        for var in (
            "TR_AUTONOMOUS",
            "TR_PERMISSION_MODE",
            "TR_TASK_PERMISSION_MODE",
            "TR_SYNC_PROVIDER",
        ):
            monkeypatch.delenv(var, raising=False)

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("PROJ-123")

        assert config.ticket_id == "PROJ-123"
        assert config.tmp_dir == tickets_dir / "PROJ-123"
        assert config.tmp_dir.exists()
        assert config.autonomous is True
        assert config.permission_mode == "acceptEdits"
        assert config.task_permission_mode == "acceptEdits"
        assert config.ticketing_platform == "Jira"
        assert config.sync_provider == "noop"

    def test_autonomous_mode(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_AUTONOMOUS", "true")
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.autonomous is True

    def test_custom_permission_modes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_PERMISSION_MODE", "bypassPermissions")
        monkeypatch.setenv("TR_TASK_PERMISSION_MODE", "plan")
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.permission_mode == "bypassPermissions"
        assert config.task_permission_mode == "plan"

    def test_ticketing_platform_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Linear")

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.ticketing_platform == "Linear"

    def test_ticketing_platform_required_raises_if_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("TR_TICKETING_PLATFORM", raising=False)

        tickets_dir = tmp_path / "tickets"
        with (
            patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
            pytest.raises(TicketRalphError, match="TR_TICKETING_PLATFORM"),
        ):
            TicketRalphConfig.from_env("TEST-1")

    def test_sync_provider_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")
        monkeypatch.setenv("TR_SYNC_PROVIDER", "jira")

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.sync_provider == "jira"

    def test_sync_provider_defaults_to_noop(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")
        monkeypatch.delenv("TR_SYNC_PROVIDER", raising=False)

        tickets_dir = tmp_path / "tickets"
        with patch("ticket_ralph.config.TICKETS_DIR", tickets_dir):
            config = TicketRalphConfig.from_env("TEST-1")

        assert config.sync_provider == "noop"


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

    def test_includes_sync_provider_cli_commands(self) -> None:
        with (
            patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
            patch(
                "ticket_ralph.config.SYNC_PROVIDER_CLI_COMMANDS",
                {"testprovider": ["nonexistent_provider_cmd_xyz"]},
            ),
            pytest.raises(TicketRalphError, match="nonexistent_provider_cmd_xyz"),
        ):
            check_prerequisites("testprovider")

    def test_unknown_platform_no_extra_commands(self) -> None:
        with patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]):
            check_prerequisites("unknown_platform")

    def test_no_platform(self) -> None:
        with patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]):
            check_prerequisites(None)
