"""Tests for ticket_ralph.services.sync."""

from pathlib import Path
from unittest.mock import MagicMock

from ticket_ralph.services.sync import SyncService


class TestSyncToTicketing:
    def test_uploads_existing_file(self, tmp_path: Path) -> None:
        provider = MagicMock()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        sync = SyncService(provider, tmp_path)
        sync.sync_to_ticketing("PROJ-1", test_file)

        provider.upload_attachment.assert_called_once_with("PROJ-1", test_file)

    def test_skips_nonexistent_file(self, tmp_path: Path) -> None:
        provider = MagicMock()
        sync = SyncService(provider, tmp_path)
        sync.sync_to_ticketing("PROJ-1", tmp_path / "nonexistent.txt")
        provider.upload_attachment.assert_not_called()


class TestSyncFromTicketing:
    def test_downloads_to_default_path(self, tmp_path: Path) -> None:
        provider = MagicMock()
        sync = SyncService(provider, tmp_path)
        sync.sync_from_ticketing("PROJ-1", "test.txt")
        provider.download_attachment.assert_called_once_with(
            "PROJ-1", "test.txt", tmp_path / "test.txt"
        )

    def test_downloads_to_custom_path(self, tmp_path: Path) -> None:
        provider = MagicMock()
        custom_path = tmp_path / "custom" / "test.txt"
        sync = SyncService(provider, tmp_path)
        sync.sync_from_ticketing("PROJ-1", "test.txt", custom_path)
        provider.download_attachment.assert_called_once_with(
            "PROJ-1", "test.txt", custom_path
        )


class TestSyncTicketFiles:
    def test_uploads_prd_and_progress(self, tmp_path: Path) -> None:
        provider = MagicMock()
        (tmp_path / "PRD.json").write_text("{}")
        (tmp_path / "progress.txt").write_text("")

        sync = SyncService(provider, tmp_path)
        sync.sync_ticket_files("PROJ-1")

        assert provider.upload_attachment.call_count == 2


class TestDownloadTicketContext:
    def test_downloads_both_files(self, tmp_path: Path) -> None:
        provider = MagicMock()
        sync = SyncService(provider, tmp_path)
        sync.download_ticket_context("PROJ-1")

        assert provider.download_attachment.call_count == 2
        calls = provider.download_attachment.call_args_list
        filenames = [c[0][1] for c in calls]
        assert "PRD.json" in filenames
        assert "progress.txt" in filenames
