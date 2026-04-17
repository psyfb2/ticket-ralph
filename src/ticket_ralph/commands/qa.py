"""QA command.

Validates all tasks are complete, then runs the tr-qa-runner agent.
Supports "no-PRD mode" for tickets implemented outside ticket-ralph.
"""

import logging

from ticket_ralph.config import TicketRalphConfig, check_prerequisites
from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services import agent as agent_svc
from ticket_ralph.services import git
from ticket_ralph.services.sync import SyncService
from ticket_ralph.ticketing import create_provider
from ticket_ralph.utils import count_remaining_tasks, read_prd

logger = logging.getLogger("ticket-ralph")


def run_qa(
    ticket_id: str,
    user_input: str = "",
    *,
    base_branch: str | None = None,
) -> None:
    """Run QA after all tasks are complete.

    Args:
        ticket_id: Ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
        base_branch: Override the parent branch for QA diff.
            Fallback chain: CLI arg > PRD baseBranch > remote default branch.
    """
    config = TicketRalphConfig.from_env(ticket_id)
    check_prerequisites(config.ticketing_platform)
    provider = create_provider(config.ticketing_platform)
    git.check_clean()

    sync = SyncService(provider, config.tmp_dir)
    executor = agent_svc.AgentExecutor(config)

    logger.info("=== Starting QA for %s ===", ticket_id)

    # Step 1: Ensure PRD.json and progress.txt are available
    logger.info("Step 1/5: Ensuring PRD.json and progress.txt are available")

    prd_path = config.tmp_dir / "PRD.json"
    progress_path = config.tmp_dir / "progress.txt"

    if not prd_path.exists() or not progress_path.exists():
        logger.info("Downloading ticket files from %s...", ticket_id)
        sync.download_ticket_context(ticket_id)

    no_prd_mode = not prd_path.exists()
    prd_base_branch: str | None = None
    if no_prd_mode:
        logger.info(
            "PRD.json not found — running in no-PRD mode "
            "(ticket implemented outside ticket-ralph)"
        )

    if not progress_path.exists():
        progress_path.touch()

    # Step 2: Confirm all tasks are done
    if no_prd_mode:
        logger.info("Step 2/5: Skipping task completion check (no-PRD mode)")
        top_branch = ""
    else:
        logger.info("Step 2/5: Confirming all tasks are complete")

        prd = read_prd(prd_path)
        top_branch = prd.get("topBranch", "")
        prd_base_branch = prd.get("baseBranch")
        if not top_branch:
            raise TicketRalphError(
                "topBranch not set in PRD.json. Run 'ticket-ralph ticket' first."
            )

        remaining = count_remaining_tasks(prd)
        if remaining > 0:
            undone = [t for t in prd.get("tasks", []) if not t.get("done", False)]
            task_lines = "\n".join(
                f"  - Task {t.get('taskNumber', '?')}: {t.get('title', '?')}"
                for t in undone
            )
            raise TicketRalphError(
                f"{remaining} task(s) are not yet done. Complete all tasks with "
                f"'ticket-ralph task' before running QA.\n{task_lines}"
            )

        logger.info("All tasks are done. Top branch: %s", top_branch)

    # Step 3: Checkout topBranch
    if no_prd_mode:
        logger.info("Step 3/5: Using current branch (no-PRD mode)")
        top_branch = git.current_branch()
        logger.info("Current branch: %s", top_branch)
    else:
        logger.info("Step 3/5: Checking out top branch")
        git.fetch()
        git.checkout(top_branch)
        git.pull(branch=top_branch)

    # Step 4: Run tr-qa-runner agent
    logger.info("Step 4/5: Running QA agent")

    parent_branch = base_branch or prd_base_branch or git.default_branch()

    if no_prd_mode:
        qa_prompt = (
            f"This branch ({top_branch}) implements ticket {ticket_id}.\n"
            f"Fetch the {provider.provider_name} ticket details for {ticket_id} "
            f"to understand the requirements.\n"
            f"parent branch: {parent_branch}\n"
        )
    else:
        qa_prompt = (
            f"PRD: {prd_path}\n"
            f"Progress: {progress_path}\n"
            f"parent branch: {parent_branch}\n\n"
            "Read the PRD, it contains user requirements, high-level design "
            "and a set of tasks to achieve the user requirements.\n"
            "Also, read the progress.txt file, it contains learnings and useful "
            "information specific to this PRD from previously done tasks.\n"
            "The most important field is the requirements field of the PRD, "
            "the rest is there to give you more context but the source of truth "
            "is the requirements.\n\n"
            "The changes on this branch implement the requirements listed "
            "in the PRD.\n"
        )

    if user_input:
        qa_prompt += f"\nAdditional context: {user_input}"

    executor.run("tr-qa-runner", qa_prompt, config.permission_mode)

    # Step 5: Upload artifacts
    logger.info("Step 5/5: Uploading artifacts")

    if not no_prd_mode:
        sync.sync_ticket_files(ticket_id)

    qa_report_path = config.tmp_dir / "qa-report.md"
    if not qa_report_path.exists():
        raise TicketRalphError(
            f"QA agent did not produce qa-report.md in {config.tmp_dir}"
        )
    sync.sync_to_ticketing(ticket_id, qa_report_path)

    logger.info("=== QA complete for %s ===", ticket_id)
