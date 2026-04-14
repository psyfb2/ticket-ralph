"""Tests for ticket_ralph.utils."""

import json
from pathlib import Path

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.utils import (
    count_remaining_tasks,
    extract_task_number_from_plan,
    find_latest_plan_file,
    generate_branch_name,
    get_task_info,
    is_review_clean,
    mark_task_done,
    read_prd,
)


class TestGenerateBranchName:
    def test_basic(self) -> None:
        assert (
            generate_branch_name("Add user authentication") == "add-user-authentication"
        )

    def test_max_words(self) -> None:
        result = generate_branch_name("one two three four five six seven")
        assert result == "one-two-three-four-five"

    def test_special_characters(self) -> None:
        result = generate_branch_name("Fix bug #123 in login!")
        assert result == "fix-bug-123-in-login"

    def test_uppercase(self) -> None:
        result = generate_branch_name("UPPER Case WORDS")
        assert result == "upper-case-words"

    def test_empty_string(self) -> None:
        assert generate_branch_name("") == "work"

    def test_only_special_chars(self) -> None:
        assert generate_branch_name("!@#$%") == "work"

    def test_custom_max_words(self) -> None:
        result = generate_branch_name("one two three four", max_words=2)
        assert result == "one-two"


class TestIsReviewClean:
    def test_clean_review(self, tmp_path: Path) -> None:
        review = tmp_path / "review.json"
        review.write_text("[]")
        assert is_review_clean(review) is True

    def test_dirty_review(self, tmp_path: Path) -> None:
        review = tmp_path / "review.json"
        review.write_text('[{"issue": "bad code"}]')
        assert is_review_clean(review) is False

    def test_missing_file(self, tmp_path: Path) -> None:
        assert is_review_clean(tmp_path / "nonexistent.json") is False

    def test_invalid_json(self, tmp_path: Path) -> None:
        review = tmp_path / "review.json"
        review.write_text("not json")
        assert is_review_clean(review) is False


class TestReadPrd:
    def test_valid_prd(self, tmp_path: Path) -> None:
        prd_path = tmp_path / "PRD.json"
        prd_data = {"topBranch": "main", "tasks": []}
        prd_path.write_text(json.dumps(prd_data))

        result = read_prd(prd_path)
        assert result == prd_data

    def test_missing_prd(self, tmp_path: Path) -> None:
        with pytest.raises(TicketRalphError, match="PRD.json not found"):
            read_prd(tmp_path / "PRD.json")

    def test_invalid_json_prd(self, tmp_path: Path) -> None:
        prd_path = tmp_path / "PRD.json"
        prd_path.write_text("not json")
        with pytest.raises(TicketRalphError, match="Failed to parse"):
            read_prd(prd_path)


class TestCountRemainingTasks:
    def test_all_done(self) -> None:
        prd = {"tasks": [{"done": True}, {"done": True}]}
        assert count_remaining_tasks(prd) == 0

    def test_some_undone(self) -> None:
        prd = {"tasks": [{"done": True}, {"done": False}, {"done": False}]}
        assert count_remaining_tasks(prd) == 2

    def test_empty_tasks(self) -> None:
        assert count_remaining_tasks({"tasks": []}) == 0

    def test_no_tasks_key(self) -> None:
        assert count_remaining_tasks({}) == 0


class TestMarkTaskDone:
    def test_marks_correct_task(self, tmp_path: Path) -> None:
        prd_path = tmp_path / "PRD.json"
        prd_path.write_text(
            json.dumps(
                {
                    "tasks": [
                        {"taskNumber": 1, "done": False},
                        {"taskNumber": 2, "done": False},
                    ]
                }
            )
        )

        mark_task_done(prd_path, 1)

        result = json.loads(prd_path.read_text())
        assert result["tasks"][0]["done"] is True
        assert result["tasks"][1]["done"] is False


class TestGetTaskInfo:
    def test_found(self) -> None:
        prd = {
            "tasks": [
                {"taskNumber": 1, "title": "First"},
                {"taskNumber": 2, "title": "Second"},
            ]
        }
        assert get_task_info(prd, 2) == {"taskNumber": 2, "title": "Second"}

    def test_not_found(self) -> None:
        prd = {"tasks": [{"taskNumber": 1}]}
        assert get_task_info(prd, 99) is None


class TestExtractTaskNumberFromPlan:
    def test_valid(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan-3.md"
        plan_file.touch()
        assert extract_task_number_from_plan(plan_file) == 3

    def test_double_digit(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "plan-12.md"
        plan_file.touch()
        assert extract_task_number_from_plan(plan_file) == 12

    def test_invalid_name(self, tmp_path: Path) -> None:
        plan_file = tmp_path / "notes.md"
        plan_file.touch()
        with pytest.raises(TicketRalphError, match="Could not extract"):
            extract_task_number_from_plan(plan_file)


class TestFindLatestPlanFile:
    def test_finds_newest(self, tmp_path: Path) -> None:
        import time

        old = tmp_path / "plan-1.md"
        old.write_text("old")
        time.sleep(0.05)
        new = tmp_path / "plan-2.md"
        new.write_text("new")

        result = find_latest_plan_file(tmp_path)
        assert result is not None
        assert result.name == "plan-2.md"

    def test_no_plan_files(self, tmp_path: Path) -> None:
        assert find_latest_plan_file(tmp_path) is None


class TestAtomicWriteJson:
    def test_writes_atomically(self, tmp_path: Path) -> None:
        from ticket_ralph.utils import atomic_write_json

        target = tmp_path / "data.json"
        atomic_write_json(target, {"key": "value"})
        assert target.exists()
        data = json.loads(target.read_text())
        assert data == {"key": "value"}
        # tmp file should be cleaned up
        assert not (tmp_path / "data.json.tmp").exists()


class TestNotifyBlocker:
    def test_with_terminal_notifier(self) -> None:
        from unittest.mock import patch

        from ticket_ralph.utils import notify_blocker

        with (
            patch(
                "ticket_ralph.utils.shutil.which",
                return_value="/usr/bin/terminal-notifier",
            ),
            patch("ticket_ralph.utils.subprocess.run") as mock_run,
        ):
            notify_blocker("PROJ-1", "stuck")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "terminal-notifier" in args

    def test_without_terminal_notifier(self) -> None:
        from unittest.mock import patch

        from ticket_ralph.utils import notify_blocker

        with patch("ticket_ralph.utils.shutil.which", return_value=None):
            notify_blocker("PROJ-1", "stuck")  # should just log warning
