"""Single task implementation command.

Picks the next available task from PRD.json, runs the planning and
engineering agents, marks the task done, and merges it into the story branch.
"""

import logging
import time

from ticket_ralph.config import (
    AUTONOMOUS_SCHEMA,
    TicketRalphConfig,
    check_prerequisites,
)
from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services import agent as agent_svc
from ticket_ralph.services import git
from ticket_ralph.services.sync import SyncService
from ticket_ralph.ticketing import create_provider
from ticket_ralph.utils import (
    count_remaining_tasks,
    extract_task_number_from_plan,
    find_latest_plan_file,
    generate_branch_name,
    get_task_info,
    mark_task_done,
    read_prd,
)

logger = logging.getLogger("ticket-ralph")


def run_task(ticket_id: str, user_input: str = "") -> None:
    """Implement the next task from a PRD.

    Args:
        ticket_id: Ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
    """
    config = TicketRalphConfig.from_env(ticket_id)
    check_prerequisites(config.sync_provider)
    provider = create_provider(config.sync_provider)
    git.check_clean()

    sync = SyncService(provider, config.tmp_dir)
    executor = agent_svc.AgentExecutor(config)

    logger.info("=== Starting task implementation for %s ===", ticket_id)

    # Step 1: Ensure PRD.json and progress.txt are available
    logger.info("Step 1/5: Ensuring PRD.json and progress.txt are available")

    prd_path = config.tmp_dir / "PRD.json"
    progress_path = config.tmp_dir / "progress.txt"

    if not prd_path.exists() or not progress_path.exists():
        logger.info("Downloading ticket files from %s...", ticket_id)
        sync.download_ticket_context(ticket_id)

    prd = read_prd(prd_path)

    # Create empty progress.txt if it doesn't exist (first task run)
    if not progress_path.exists():
        progress_path.touch()

    top_branch = prd.get("topBranch")
    if not top_branch:
        raise TicketRalphError(
            "topBranch not set in PRD.json. Run 'ticket-ralph ticket' first."
        )

    remaining = count_remaining_tasks(prd)
    if remaining == 0:
        logger.info("All tasks in PRD.json are already done. Nothing to implement.")
        return

    logger.info("Found %d undone task(s). Top branch: %s", remaining, top_branch)

    # Step 2: Checkout topBranch and run tr-plan agent
    logger.info("Step 2/5: Running planning agent")

    git.fetch()
    git.checkout(top_branch)
    git.pull(branch=top_branch)

    plan_prompt = (
        f"Plan the next task for the PRD at {prd_path} (progress: {progress_path})."
    )

    if user_input:
        plan_prompt += f"\n\nAdditional context: {user_input}"

    plan_agent_start = time.time()

    if config.autonomous:
        plan_prompt += (
            "\n\nYou are running in autonomous mode (non-interactive). "
            "Your final output MUST be a JSON object with {done, overview}. "
            "Set done=false with a clear explanation if you hit a blocker."
        )
        plan_result = executor.run_autonomous("tr-plan", plan_prompt, AUTONOMOUS_SCHEMA)
        agent_svc.check_autonomous_result(plan_result, "tr-plan", config.tmp_dir)
    else:
        executor.run("tr-plan", plan_prompt, config.task_permission_mode)

    # Step 3: Determine chosen task number from newest plan file
    logger.info("Step 3/5: Determining chosen task from plan file")

    # Re-read PRD in case the plan agent modified task order/titles
    prd = read_prd(prd_path)

    plan_file = find_latest_plan_file(config.tmp_dir)
    if not plan_file:
        raise TicketRalphError(
            f"No plan file found in {config.tmp_dir} after running tr-plan agent"
        )

    # Verify the plan file was written by this agent run
    file_mtime = plan_file.stat().st_mtime
    if file_mtime < plan_agent_start:
        raise TicketRalphError(
            f"Plan file {plan_file.name} predates this agent run — "
            "the tr-plan agent may have failed to write a new plan."
        )

    task_number = extract_task_number_from_plan(plan_file)
    logger.info("Planning agent chose task %d (plan: %s)", task_number, plan_file.name)

    # Verify task exists and isn't already done
    task_info = get_task_info(prd, task_number)
    if not task_info:
        raise TicketRalphError(f"Task {task_number} not found in PRD.json")
    if task_info.get("done"):
        raise TicketRalphError(
            f"Task {task_number} is already marked as done in PRD.json"
        )

    task_title = task_info.get("title", "")

    # Step 4: Create task branch and run tr-software-engineer agent
    logger.info("Step 4/5: Creating task branch and running software engineer agent")

    branch_suffix = generate_branch_name(task_title)
    branch_name = f"{ticket_id}-task-{task_number}-{branch_suffix}"

    if git.branch_exists(branch_name):
        logger.info("Branch %s exists locally, checking it out", branch_name)
        git.checkout(branch_name)
        git.pull(branch=branch_name)
    elif git.branch_exists(branch_name, remote=True):
        logger.info("Branch %s exists on remote, checking it out", branch_name)
        git.checkout(branch_name, create=True, start_point=f"origin/{branch_name}")
    else:
        git.checkout(branch_name, create=True, start_point=top_branch)
    git.push(branch=branch_name, set_upstream=True)
    logger.info("Created and pushed task branch: %s", branch_name)

    engineer_prompt = (
        f"Implement task {task_number} from the PRD.\n\n"
        f"PRD: {prd_path}\n"
        f"Progress: {progress_path}\n"
        f"Plan: {config.tmp_dir / f'plan-{task_number}.md'}\n"
        f"Implement taskNumber: {task_number}"
    )

    if user_input:
        engineer_prompt += f"\n\nAdditional context: {user_input}"

    if config.autonomous:
        engineer_prompt += (
            "\n\nYou are running in autonomous mode (non-interactive). "
            "Your final output MUST be a JSON object with {done, overview}. "
            "Set done=false with a clear explanation if you hit a blocker."
        )
        engineer_result = executor.run_autonomous(
            "tr-software-engineer", engineer_prompt, AUTONOMOUS_SCHEMA
        )
        agent_svc.check_autonomous_result(
            engineer_result, "tr-software-engineer", config.tmp_dir
        )
    else:
        executor.run(
            "tr-software-engineer", engineer_prompt, config.task_permission_mode
        )

    # Step 5: Mark done, push, merge, and upload
    logger.info("Step 5/5: Finalizing task %d", task_number)

    mark_task_done(prd_path, task_number)

    # Commit any uncommitted changes
    git.add_all_and_commit(f"chore: finalize task {task_number}")

    git.push(branch=branch_name)
    logger.info("Pushed task branch: %s", branch_name)

    # Merge task branch into topBranch
    git.checkout(top_branch)
    git.pull(branch=top_branch)
    merge_message = f"feat: complete task {task_number} - {task_title}"
    git.merge_no_ff(branch_name, merge_message)
    git.push(branch=top_branch)
    logger.info("Merged %s into %s", branch_name, top_branch)

    # Upload updated artifacts
    sync.sync_ticket_files(ticket_id)

    logger.info(
        "=== Task %d implementation complete for %s ===", task_number, ticket_id
    )
