"""Tests for ticket_ralph.services.git."""

import subprocess
from unittest.mock import patch

import pytest

from ticket_ralph.exceptions import MergeConflictError, TicketRalphError
from ticket_ralph.services import git


def _mock_run(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestFetch:
    def test_calls_git_fetch(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.fetch()
            mock.assert_called_once_with(["fetch", "origin"])

    def test_custom_remote(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.fetch("upstream")
            mock.assert_called_once_with(["fetch", "upstream"])


class TestCheckout:
    def test_simple_checkout(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.checkout("main")
            mock.assert_called_once_with(["checkout", "main"])

    def test_create_branch(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.checkout("feature", create=True, start_point="main")
            mock.assert_called_once_with(["checkout", "-b", "feature", "main"])


class TestPull:
    def test_pull_with_branch(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.pull(branch="main")
            mock.assert_called_once_with(["pull", "origin", "main"])


class TestPush:
    def test_push_with_upstream(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.push(branch="feature", set_upstream=True)
            mock.assert_called_once_with(["push", "-u", "origin", "feature"])


class TestMergeNoFf:
    def test_success(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run()
            git.merge_no_ff("feature", "merge feature")

    def test_conflict_raises(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(returncode=1)
            with pytest.raises(MergeConflictError):
                git.merge_no_ff("feature", "merge feature")


class TestIsClean:
    def test_clean(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout="")
            assert git.is_clean() is True

    def test_dirty(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout=" M file.py\n")
            assert git.is_clean() is False


class TestCheckClean:
    def test_clean_passes(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout="")
            git.check_clean()

    def test_dirty_raises(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.side_effect = [
                _mock_run(stdout=" M dirty.py\n"),
                _mock_run(stdout=" M dirty.py"),
            ]
            with pytest.raises(TicketRalphError, match="not clean"):
                git.check_clean()


class TestBranchExists:
    def test_exists_locally(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(returncode=0)
            assert git.branch_exists("feature") is True
            mock.assert_called_once_with(
                ["show-ref", "--verify", "--quiet", "refs/heads/feature"],
                check=False,
            )

    def test_exists_remote(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(returncode=0)
            assert git.branch_exists("feature", remote=True) is True
            mock.assert_called_once_with(
                ["show-ref", "--verify", "--quiet", "refs/remotes/origin/feature"],
                check=False,
            )

    def test_not_exists(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(returncode=1)
            assert git.branch_exists("nonexistent") is False


class TestDefaultBranch:
    def test_parses_head_branch(self) -> None:
        output = "  HEAD branch: main\n  Remote branches:\n"
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout=output)
            assert git.default_branch() == "main"

    def test_fallback_to_main(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout="no useful info")
            assert git.default_branch() == "main"


class TestAddAllAndCommit:
    def test_nothing_to_commit(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout="")
            assert git.add_all_and_commit("test") is False

    def test_commits_changes(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.side_effect = [
                _mock_run(stdout=" M file.py\n"),  # is_clean -> False
                _mock_run(),  # git add
                _mock_run(),  # git commit
            ]
            assert git.add_all_and_commit("test commit") is True


class TestCurrentBranch:
    def test_returns_branch_name(self) -> None:
        with patch("ticket_ralph.services.git._run") as mock:
            mock.return_value = _mock_run(stdout="feature-branch\n")
            assert git.current_branch() == "feature-branch"


class TestRunError:
    def test_raises_on_failure(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git", stderr="error"),
        ):
            with pytest.raises(TicketRalphError, match="error"):
                git._run(["status"])
