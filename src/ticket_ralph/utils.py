"""Shared utilities for ticket-ralph.

Pure functions for branch name generation, PRD parsing, review checking, and
notification.
"""

import json
import logging
import platform
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("ticket-ralph")


def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to a file atomically via write-to-tmp-then-rename.

    Args:
        path: Destination file path.
        data: Dict to serialize as JSON.
    """
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2))
    tmp_path.replace(path)


def generate_branch_name(text: str, *, max_words: int = 5) -> str:
    """Generate a git-safe branch suffix from a text string.

    Lowercases, strips non-alphanumeric characters, takes the first N words,
    and joins them with hyphens.

    Args:
        text: Input text (e.g. a ticket summary or task title).
        max_words: Maximum number of words to include.

    Returns:
        Hyphenated branch suffix, or "work" if text produces nothing.
    """
    cleaned = text.lower()
    cleaned = re.sub(r"[^a-z0-9 ]", " ", cleaned)
    words = cleaned.split()[:max_words]
    result = "-".join(words)
    return result or "work"


def is_review_clean(review_file: Path) -> bool:
    """Check if a review JSON file contains zero issues.

    Args:
        review_file: Path to a JSON file containing review results.

    Returns:
        True if the review has no issues.
    """
    if not review_file.exists():
        logger.error("Review file not found: %s", review_file)
        return False

    try:
        data = json.loads(review_file.read_text())
        count = len(data)
    except (json.JSONDecodeError, TypeError):
        logger.error("Failed to parse review file: %s", review_file)
        return False

    if count == 0:
        return True

    logger.info("Review found %d issue(s)", count)
    return False


def read_prd(prd_path: Path) -> dict:
    """Read and parse a PRD.json file.

    Args:
        prd_path: Path to the PRD.json file.

    Returns:
        Parsed PRD dict.

    Raises:
        TicketRalphError: If the file doesn't exist or can't be parsed.
    """
    from ticket_ralph.exceptions import TicketRalphError

    if not prd_path.exists():
        raise TicketRalphError(
            f"PRD.json not found at {prd_path}. Run 'ticket-ralph ticket' first."
        )
    try:
        return json.loads(prd_path.read_text())
    except json.JSONDecodeError as e:
        raise TicketRalphError(f"Failed to parse PRD.json: {e}") from e


def count_remaining_tasks(prd: dict) -> int:
    """Count tasks not yet marked done in a PRD.

    Args:
        prd: Parsed PRD dict.

    Returns:
        Number of undone tasks.
    """
    tasks = prd.get("tasks") or []
    return sum(1 for t in tasks if not t.get("done", False))


def mark_task_done(prd_path: Path, task_number: int) -> None:
    """Mark a task as done in PRD.json and write it back.

    Args:
        prd_path: Path to the PRD.json file.
        task_number: The taskNumber to mark as done.
    """
    prd = read_prd(prd_path)
    for task in prd.get("tasks", []):
        if task.get("taskNumber") == task_number:
            task["done"] = True
    atomic_write_json(prd_path, prd)
    logger.info("Marked task %d as done in PRD.json", task_number)


def get_task_info(prd: dict, task_number: int) -> dict | None:
    """Get a task dict from a PRD by task number.

    Args:
        prd: Parsed PRD dict.
        task_number: The taskNumber to look up.

    Returns:
        The task dict, or None if not found.
    """
    for task in prd.get("tasks", []):
        if task.get("taskNumber") == task_number:
            return task
    return None


def extract_task_number_from_plan(plan_file: Path) -> int:
    """Extract the task number from a plan filename like plan-3.md.

    Args:
        plan_file: Path to the plan file.

    Returns:
        The task number.

    Raises:
        TicketRalphError: If the task number can't be extracted.
    """
    from ticket_ralph.exceptions import TicketRalphError

    match = re.match(r"plan-(\d+)\.md$", plan_file.name)
    if not match:
        raise TicketRalphError(
            f"Could not extract task number from plan file: {plan_file.name}"
        )
    return int(match.group(1))


def find_latest_plan_file(tmp_dir: Path) -> Path | None:
    """Find the most recently modified plan file in the tmp directory.

    Args:
        tmp_dir: Directory to search.

    Returns:
        Path to the newest plan-*.md file, or None if none found.
    """
    plan_files = list(tmp_dir.glob("plan-*.md"))
    if not plan_files:
        return None
    return max(plan_files, key=lambda p: p.stat().st_mtime)


def notify_blocker(ticket_id: str, message: str) -> None:
    """Send a desktop notification about a blocker.

    Uses osascript on macOS. On Linux, sends a terminal bell character that
    propagates through SSH/terminal sessions to the host machine — works in
    headless VMs like Lima. Falls back to a log warning on other platforms.

    Args:
        ticket_id: The ticket identifier.
        message: Notification message.
    """
    title = f"ticket-ralph: Blocker ({ticket_id})"
    system = platform.system()

    if system == "Darwin":
        escaped_msg = message.replace("\\", "\\\\").replace('"', '\\"')
        escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{escaped_msg}" with title'
                f' "{escaped_title}" sound name "default"',
            ],
            check=False,
        )
    elif system == "Linux":
        print("\a\a\a")
        logger.warning("BLOCKER: %s — %s", title, message)
    else:
        logger.warning("No notification tool available, skipping notification")
