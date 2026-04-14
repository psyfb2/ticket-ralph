"""High-level planning command — ports scripts/ticket.sh.

Fetches Jira ticket data, runs the tr-high-level-plan agent to produce
PRD.json, creates a story branch, and uploads artifacts to Jira.
"""

import json
import logging

from ticket_ralph.config import TicketRalphConfig, check_prerequisites
from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services import agent as agent_svc
from ticket_ralph.services import git
from ticket_ralph.services.sync import SyncService
from ticket_ralph.ticketing.jira import JiraProvider
from ticket_ralph.utils import _atomic_write_json, generate_branch_name

logger = logging.getLogger("ticket-ralph")


def run_ticket(ticket_id: str, user_input: str = "") -> None:
    """Orchestrate high-level planning for a Jira ticket.

    Args:
        ticket_id: Jira ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
    """
    config = TicketRalphConfig.from_env(ticket_id)
    check_prerequisites()
    git.check_clean()

    provider = JiraProvider(
        base_url=config.jira_base_url,
        user=config.jira_user,
        api_token=config.jira_api_token,
    )
    sync = SyncService(provider, config.tmp_dir)
    executor = agent_svc.AgentExecutor(config)

    logger.info("=== Starting high-level planning for %s ===", ticket_id)

    # Guard: ticket must have no existing child tasks
    existing_tasks = provider.get_subtasks(ticket_id)
    if existing_tasks:
        task_lines = "\n".join(
            f"  - {t.get('key', '?')}: {t.get('fields', {}).get('summary', '?')}"
            for t in existing_tasks
        )
        raise TicketRalphError(
            f"Ticket {ticket_id} already has {len(existing_tasks)} child task(s). "
            f"High-level planning requires a ticket with no existing child tasks.\n"
            f"Existing tasks:\n{task_lines}"
        )

    # Step 1: Fetch Jira ticket data
    logger.info("Step 1/4: Fetching Jira ticket data")
    provider.fetch_ticket_context(ticket_id, config.tmp_dir)

    # Step 2: Run high-level plan agent
    logger.info("Step 2/4: Creating high-level plan")

    context_path = config.tmp_dir / "ticket-context.json"
    context_data = json.loads(context_path.read_text())
    issue_type = context_data.get("issueType", "")
    parent_story_key = context_data.get("parentStoryKey")
    attachments = [
        a.get("localPath", "")
        for a in context_data.get("attachments", [])
        if a.get("localPath")
    ]

    agent_prompt = (
        f"Create a high-level plan for Jira {issue_type} {ticket_id}.\n\n"
        f"First, fetch the ticket details by running: jira issue view {ticket_id}"
    )

    if parent_story_key:
        parent_path = config.tmp_dir / "parent-context.json"
        if not parent_path.exists():
            raise TicketRalphError(
                f"Parent context file not found at {parent_path} — "
                f"failed to fetch parent story {parent_story_key}."
            )
        parent_data = json.loads(parent_path.read_text())
        parent_type = parent_data.get("issueType", "")
        agent_prompt += (
            f"\n\nThis ticket has a parent {parent_type}. "
            f"Also fetch the parent for additional context by running: "
            f"jira issue view {parent_story_key}"
        )

    if attachments:
        att_list = "\n".join(attachments)
        agent_prompt += (
            f"\n\nThe following attachments were downloaded from the ticket "
            f"— read them to understand their contents:\n{att_list}"
        )

    if user_input:
        agent_prompt += f"\n\nAdditional context: {user_input}"

    executor.run("tr-high-level-plan", agent_prompt, config.permission_mode)

    prd_path = config.tmp_dir / "PRD.json"
    if not prd_path.exists():
        raise TicketRalphError(
            f"Planning agent did not produce PRD.json in {config.tmp_dir}"
        )

    # Step 3: Create ticket branch
    logger.info("Step 3/4: Creating ticket branch")

    ticket_summary = context_data.get("summary", "")
    branch_suffix = generate_branch_name(ticket_summary)
    branch_name = f"{ticket_id}-{branch_suffix}"

    git.fetch()
    if git.branch_exists(branch_name):
        logger.info("Branch %s already exists locally, checking it out", branch_name)
        git.checkout(branch_name)
        git.pull(branch=branch_name)
    else:
        git.checkout(branch_name, create=True, start_point="origin/main")
    git.push(branch=branch_name, set_upstream=True)
    logger.info("Created and pushed branch: %s", branch_name)

    # Set topBranch in PRD.json
    prd = json.loads(prd_path.read_text())
    prd["topBranch"] = branch_name
    _atomic_write_json(prd_path, prd)
    logger.info("Set topBranch in PRD.json to: %s", branch_name)

    # Step 4: Upload artifacts to Jira
    logger.info("Step 4/4: Uploading artifacts to Jira")
    progress_path = config.tmp_dir / "progress.txt"
    if not progress_path.exists():
        progress_path.touch()
    sync.sync_ticket_files(ticket_id)

    logger.info("=== High-level planning complete for %s ===", ticket_id)
