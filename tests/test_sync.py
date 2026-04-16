"""Tests for ticket_ralph.services.sync."""

from pathlib import Path
from unittest.mock import MagicMock

from ticket_ralph.services.sync import SyncService


class TestSyncTicketFiles:
    def test_uploads_prd_and_progress(self, tmp_path: Path) -> None:
        provider = MagicMock()
        (tmp_path / "PRD.json").write_text("{}")
        (tmp_path / "progress.txt").write_text("")

        sync = SyncService(provider, tmp_path)
        sync.sync_ticket_files("PROJ-1")

        assert provider.upload_attachment.call_count == 2
        call_args = [c[0] for c in provider.upload_attachment.call_args_list]
        assert ("PROJ-1", tmp_path / "PRD.json") in call_args
        assert ("PROJ-1", tmp_path / "progress.txt") in call_args


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
