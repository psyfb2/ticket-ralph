"""Tests for ticket_ralph.ticketing.noop."""

from pathlib import Path

from ticket_ralph.ticketing.noop import NoOpProvider


class TestNoOpProvider:
    def test_provider_name(self) -> None:
        p = NoOpProvider("linear")
        assert p.provider_name == "linear"

    def test_cli_commands_empty(self) -> None:
        p = NoOpProvider("linear")
        assert p.cli_commands == []

    def test_upload_attachment_is_noop(self, tmp_path: Path) -> None:
        p = NoOpProvider("trello")
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        p.upload_attachment("TICKET-1", test_file)

    def test_download_attachment_returns_false(self, tmp_path: Path) -> None:
        p = NoOpProvider("trello")
        result = p.download_attachment("TICKET-1", "file.txt", tmp_path / "out.txt")
        assert result is False
