"""Requirements-refinement command.

Runs the tr-boost agent to challenge and sharpen a ticket's requirements with
the user, then write them back to the ticketing platform. Optional, and
intended to run before `ticket-ralph ticket`.
"""

import logging

from ticket_ralph.config import TicketRalphConfig, check_prerequisites
from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services import agent as agent_svc
from ticket_ralph.ticketing import create_provider

logger = logging.getLogger("ticket-ralph")

BOOST_FILE = "boost.md"


def run_boost(ticket_id: str, user_input: str = "") -> None:
    """Refine a ticket's requirements and write them back to the ticket.

    Unlike the other commands this one touches neither git nor the file-sync
    provider: it creates no branch, and its output lives in the ticket itself
    (refined description plus a comment holding the pre-boost original) rather
    than in an attachment.

    Args:
        ticket_id: Ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.

    Raises:
        TicketRalphError: If no ticketing CLI is configured, or the agent did
            not produce the refined requirements file.
    """
    config = TicketRalphConfig.from_env(ticket_id)
    check_prerequisites(config.sync_provider)

    # boost reads *and updates* the ticket through the platform CLI, so unlike
    # the other commands it cannot degrade gracefully to a no-op provider.
    if not create_provider(config.sync_provider).cli_commands:
        raise TicketRalphError(
            f"boost needs a ticketing CLI to read and update {ticket_id}, but "
            f"sync provider '{config.sync_provider}' has none. Set "
            f"TR_SYNC_PROVIDER to a CLI-backed platform (jira or linear)."
        )

    executor = agent_svc.AgentExecutor(config)

    logger.info("=== Starting requirements boost for %s ===", ticket_id)

    logger.info("Step 1/2: Refining requirements")
    agent_prompt = _build_boost_prompt(ticket_id, config.ticketing_platform)
    if user_input:
        agent_prompt += f"\n\nAdditional context: {user_input}"

    executor.run("tr-boost", agent_prompt, config.permission_mode)

    logger.info("Step 2/2: Verifying output")
    boost_path = config.tmp_dir / BOOST_FILE
    if not boost_path.exists():
        raise TicketRalphError(
            f"Boost agent did not produce {BOOST_FILE} in {config.tmp_dir}"
        )

    logger.info("=== Requirements boost complete for %s ===", ticket_id)
    logger.info("Refined requirements: %s", boost_path)
    logger.info("Next step: ticket-ralph ticket %s", ticket_id)


def _build_boost_prompt(ticket_id: str, platform_name: str) -> str:
    """Build the agent prompt for requirements refinement.

    Args:
        ticket_id: Ticket ID.
        platform_name: Human-readable ticketing platform name.

    Returns:
        The prompt string for the boost agent.
    """
    return (
        f"Boost the requirements for ticket {ticket_id}.\n\n"
        f"Fetch the {platform_name} ticket details for {ticket_id}.\n"
        f"If the ticket has a parent story, also fetch the parent "
        f"for additional context.\n"
        f"If the ticket has any file attachments, download and read them "
        f"to understand their contents.\n"
        f"Challenge the requirements, close every gap with the user, then "
        f"write the refined requirements back to the {platform_name} ticket."
    )
