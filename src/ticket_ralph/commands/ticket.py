"""High-level planning command.

Runs the tr-high-level-plan agent to produce PRD.json, creates a story
branch, and uploads artifacts to the ticketing platform.
"""

import json
import logging

from ticket_ralph.config import TicketRalphConfig, check_prerequisites
from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services import agent as agent_svc
from ticket_ralph.services import git
from ticket_ralph.services.sync import SyncService
from ticket_ralph.ticketing import create_provider
from ticket_ralph.utils import atomic_write_json, generate_branch_name

logger = logging.getLogger("ticket-ralph")


def run_ticket(
    ticket_id: str,
    user_input: str = "",
    *,
    base_branch: str | None = None,
) -> None:
    """Orchestrate high-level planning for a ticket.

    Args:
        ticket_id: Ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
        base_branch: Branch to create the story branch from.
            Defaults to the remote default branch (e.g. main).
    """
    config = TicketRalphConfig.from_env(ticket_id)
    check_prerequisites(config.sync_provider)
    provider = create_provider(config.sync_provider)
    git.check_clean()

    sync = SyncService(provider, config.tmp_dir)
    executor = agent_svc.AgentExecutor(config)

    logger.info("=== Starting high-level planning for %s ===", ticket_id)

    # Step 1: Run high-level plan agent
    logger.info("Step 1/3: Creating high-level plan")

    agent_prompt = _build_ticket_prompt(ticket_id, config.ticketing_platform)

    if user_input:
        agent_prompt += f"\n\nAdditional context: {user_input}"

    executor.run("tr-high-level-plan", agent_prompt, config.permission_mode)

    prd_path = config.tmp_dir / "PRD.json"
    if not prd_path.exists():
        raise TicketRalphError(
            f"Planning agent did not produce PRD.json in {config.tmp_dir}"
        )

    # Step 2: Create ticket branch
    logger.info("Step 2/3: Creating ticket branch")

    prd = json.loads(prd_path.read_text())
    ticket_summary = prd.get("summary", "")
    if not ticket_summary:
        logger.warning(
            "PRD.json missing 'summary' field — branch will use fallback name"
        )
    branch_suffix = generate_branch_name(ticket_summary)
    branch_name = f"{ticket_id}-{branch_suffix}"

    git.fetch()
    resolved_base = base_branch or git.default_branch()
    if git.branch_exists(branch_name):
        logger.info("Branch %s already exists locally, checking it out", branch_name)
        git.checkout(branch_name)
        git.pull(branch=branch_name)
    else:
        git.checkout(branch_name, create=True, start_point=f"origin/{resolved_base}")
    git.push(branch=branch_name, set_upstream=True)
    logger.info("Created and pushed branch: %s", branch_name)

    # Set topBranch in PRD.json
    prd["topBranch"] = branch_name
    prd["baseBranch"] = resolved_base
    atomic_write_json(prd_path, prd)
    logger.info("Set topBranch in PRD.json to: %s", branch_name)
    logger.info("Set baseBranch in PRD.json to: %s", resolved_base)

    # Step 3: Upload artifacts to ticketing platform
    logger.info("Step 3/3: Uploading artifacts")
    progress_path = config.tmp_dir / "progress.txt"
    if not progress_path.exists():
        progress_path.touch()
    sync.sync_ticket_files(ticket_id)

    logger.info("=== High-level planning complete for %s ===", ticket_id)


def _build_ticket_prompt(ticket_id: str, platform_name: str) -> str:
    """Build the agent prompt for high-level planning.

    Args:
        ticket_id: Ticket ID.
        platform_name: Human-readable ticketing platform name.

    Returns:
        The prompt string for the high-level plan agent.
    """
    return (
        f"Create a high-level plan for ticket {ticket_id}.\n\n"
        f"Fetch the {platform_name} ticket details for {ticket_id}.\n"
        f"If the ticket has a parent story, also fetch the parent "
        f"for additional context.\n"
        f"If the ticket has any file attachments, download and read them "
        f"to understand their contents."
    )
