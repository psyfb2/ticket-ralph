"""CLI entry point for ticket-ralph.

Provides subcommands: ticket, task, task-loop, qa.
Installed as both `ticket-ralph` and `tr` console scripts.
"""

import logging
import sys

import click

from ticket_ralph.exceptions import TicketRalphError


def _setup_logging() -> None:
    """Configure logging with the ticket-ralph format."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[ticket-ralph] %(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    logger = logging.getLogger("ticket-ralph")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@click.group()
@click.version_option(package_name="ticket-ralph")
def cli() -> None:
    """Orchestrated multi-agent workflow for ticket-driven development."""
    _setup_logging()


@cli.command()
@click.argument("ticket_id")
@click.argument("extra", nargs=-1)
def ticket(ticket_id: str, extra: tuple[str, ...]) -> None:
    """High-level planning for a ticket.

    Creates a PRD.json, story branch, and uploads artifacts to Jira.
    """
    from ticket_ralph.commands.ticket import run_ticket

    run_ticket(ticket_id, " ".join(extra))


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
def qa(ticket_id: str, extra: tuple[str, ...]) -> None:
    """Run QA after all tasks are complete."""
    from ticket_ralph.commands.qa import run_qa

    run_qa(ticket_id, " ".join(extra))


def main() -> None:
    """Entry point that handles TicketRalphError exit codes."""
    try:
        cli()
    except TicketRalphError as e:
        logger = logging.getLogger("ticket-ralph")
        logger.error("ERROR: %s", e)
        sys.exit(e.exit_code)
