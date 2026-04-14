"""Git operation wrappers using subprocess.

All operations run in the caller's working directory (inherited CWD),
which is the target repository the user invoked ticket-ralph from.
"""

import logging
import subprocess

from ticket_ralph.exceptions import MergeConflictError, TicketRalphError

logger = logging.getLogger("ticket-ralph")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result.

    Args:
        args: Arguments to pass after 'git'.
        check: If True, raise on non-zero exit.

    Returns:
        Completed process result.

    Raises:
        TicketRalphError: If the command fails and check is True.
    """
    cmd = ["git", *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        raise TicketRalphError(
            f"git {' '.join(args)} failed (exit {e.returncode}): {e.stderr.strip()}"
        ) from e


def fetch(remote: str = "origin") -> None:
    """Fetch from a remote."""
    _run(["fetch", remote])


def checkout(
    branch: str,
    *,
    create: bool = False,
    start_point: str | None = None,
) -> None:
    """Checkout a branch.

    Args:
        branch: Branch name to checkout.
        create: If True, create the branch.
        start_point: Starting point for a new branch.
    """
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)
    if start_point:
        args.append(start_point)
    _run(args)


def pull(remote: str = "origin", branch: str | None = None) -> None:
    """Pull from a remote.

    Args:
        remote: Remote name.
        branch: Branch to pull. If None, pulls the current branch.
    """
    args = ["pull", remote]
    if branch:
        args.append(branch)
    _run(args)


def push(
    remote: str = "origin",
    branch: str | None = None,
    *,
    set_upstream: bool = False,
) -> None:
    """Push to a remote.

    Args:
        remote: Remote name.
        branch: Branch to push. If None, pushes the current branch.
        set_upstream: If True, set the upstream tracking reference.
    """
    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.append(remote)
    if branch:
        args.append(branch)
    _run(args)


def merge_no_ff(branch: str, message: str) -> None:
    """Merge a branch with --no-ff and a commit message.

    Args:
        branch: Branch to merge.
        message: Merge commit message.

    Raises:
        MergeConflictError: If the merge fails.
    """
    result = _run(["merge", "--no-ff", branch, "-m", message], check=False)
    if result.returncode != 0:
        raise MergeConflictError(branch)


def is_clean() -> bool:
    """Check if the working directory has no uncommitted changes."""
    result = _run(["status", "--porcelain"])
    return result.stdout.strip() == ""


def check_clean() -> None:
    """Verify the working directory is clean.

    Raises:
        TicketRalphError: If there are uncommitted changes.
    """
    if not is_clean():
        status = _run(["status", "--short"]).stdout.strip()
        raise TicketRalphError(
            "Git working directory is not clean. Please commit, stash, or "
            f"discard changes before proceeding.\n{status}"
        )


def current_branch() -> str:
    """Return the current branch name."""
    result = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def branch_exists(name: str, *, remote: bool = False) -> bool:
    """Check if a branch exists locally or on a remote.

    Args:
        name: Branch name.
        remote: If True, check for remote branch (origin/).
    """
    ref = f"refs/remotes/origin/{name}" if remote else f"refs/heads/{name}"
    result = _run(["show-ref", "--verify", "--quiet", ref], check=False)
    return result.returncode == 0


def default_branch(remote: str = "origin") -> str:
    """Determine the default branch of a remote.

    Args:
        remote: Remote name.

    Returns:
        Default branch name (e.g. 'main'), falls back to 'main'.
    """
    result = _run(["remote", "show", remote], check=False)
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("HEAD branch:"):
            return line.split(":", 1)[1].strip()
    return "main"


def add_all_and_commit(message: str) -> bool:
    """Stage all changes and commit if there are any.

    Args:
        message: Commit message.

    Returns:
        True if a commit was made, False if there was nothing to commit.
    """
    if is_clean():
        return False
    _run(["add", "-A"])
    _run(["commit", "-m", message])
    return True
