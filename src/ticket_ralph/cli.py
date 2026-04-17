"""CLI entry point for ticket-ralph.

Provides subcommands: ticket, task, task-loop, qa.
Installed as both `ticket-ralph` and `tr` console scripts.
"""

import logging
import os
import sys

import click

from ticket_ralph.exceptions import TicketRalphError


def _setup_logging() -> None:
    """Configure logging with the ticket-ralph format."""
    logger = logging.getLogger("ticket-ralph")
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[ticket-ralph] %(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _warn_autonomous_mode() -> None:
    """Log a one-time warning when autonomous mode is active."""
    if os.environ.get("TR_AUTONOMOUS", "true").lower() != "true":
        return
    logger = logging.getLogger("ticket-ralph")
    logger.warning(
        "AUTONOMOUS MODE — agents will run with --dangerously-skip-permissions "
        "and no sandbox.\n"
        "Only run autonomous mode on a VM. Ensure CLIs (az, bkt, etc.) have scoped "
        "token privileges that prevent catastrophic actions (e.g. force-push to main, "
        "rewrite git history, change repo settings). Use PIM so az cannot delete "
        "production infrastructure."
    )


@click.group()
@click.version_option(package_name="ticket-ralph")
def cli() -> None:
    """Orchestrated multi-agent workflow for ticket-driven development."""
    _setup_logging()
    _warn_autonomous_mode()


@cli.command()
@click.argument("ticket_id")
@click.argument("extra", nargs=-1)
@click.option(
    "--base-branch",
    default=None,
    help="Branch to create the story branch from (defaults to remote default branch).",
)
def ticket(ticket_id: str, extra: tuple[str, ...], base_branch: str | None) -> None:
    """High-level planning for a ticket.

    Creates a PRD.json, story branch, and uploads artifacts to Jira.
    """
    from ticket_ralph.commands.ticket import run_ticket

    run_ticket(ticket_id, " ".join(extra), base_branch=base_branch)


@cli.command()
@click.argument("ticket_id")
@click.argument("extra", nargs=-1)
def task(ticket_id: str, extra: tuple[str, ...]) -> None:
    """Implement the next task from the PRD."""
    from ticket_ralph.commands.task import run_task

    run_task(ticket_id, " ".join(extra))


@cli.command("task-loop")
@click.argument("ticket_id")
@click.argument("extra", nargs=-1)
def task_loop(ticket_id: str, extra: tuple[str, ...]) -> None:
    """Run tasks in a loop until all PRD tasks are complete."""
    from ticket_ralph.commands.task_loop import run_task_loop

    run_task_loop(ticket_id, " ".join(extra))


@cli.command()
@click.argument("ticket_id")
@click.argument("extra", nargs=-1)
@click.option(
    "--base-branch",
    default=None,
    help="Override the parent branch for QA diff (defaults to PRD baseBranch, then remote default branch).",
)
def qa(ticket_id: str, extra: tuple[str, ...], base_branch: str | None) -> None:
    """Run QA after all tasks are complete."""
    from ticket_ralph.commands.qa import run_qa

    run_qa(ticket_id, " ".join(extra), base_branch=base_branch)


def main() -> None:
    """Entry point that handles TicketRalphError exit codes."""
    try:
        cli()
    except TicketRalphError as e:
        logger = logging.getLogger("ticket-ralph")
        logger.error("ERROR: %s", e)
        sys.exit(e.exit_code)
