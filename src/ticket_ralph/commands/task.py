"""Single task implementation command.

Picks the next available task from PRD.json, runs the planning and
engineering agents, marks the task done, and merges it into the story branch.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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


class ResumePhase(Enum):
    """Phase of a task to resume when an earlier run was interrupted."""

    PLAN = "plan"
    IMPL = "impl"


@dataclass(frozen=True)
class ResumeDirective:
    """Directive to resume a specific task at a specific phase.

    Attributes:
        phase: Which phase to resume from (planning or implementation).
        task_number: The taskNumber from PRD.json to resume.
    """

    phase: ResumePhase
    task_number: int


def run_task(
    ticket_id: str,
    user_input: str = "",
    *,
    resume: ResumeDirective | None = None,
) -> None:
    """Implement the next task from a PRD.

    Args:
        ticket_id: Ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
        resume: Optional directive to resume a specific task at a specific
            phase (planning or implementation). When ``None``, the planning
            agent auto-picks the next available task.
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

    # When resuming a specific task, validate the target up front so the user
    # gets a precise error instead of the generic "all tasks done" short-circuit.
    if resume is not None:
        _validate_resume_target(prd, resume)
    else:
        remaining = count_remaining_tasks(prd)
        if remaining == 0:
            logger.info("All tasks in PRD.json are already done. Nothing to implement.")
            return
        logger.info("Found %d undone task(s). Top branch: %s", remaining, top_branch)

    # Step 2: Checkout topBranch and resolve the task to work on
    logger.info("Step 2/5: Resolving task to implement")

    git.fetch()
    git.checkout(top_branch)
    git.pull(branch=top_branch)

    # Step 3: Run the planning agent (unless skipped) and pick the task number
    logger.info("Step 3/5: Determining chosen task")

    task_number, prd = _resolve_task_number(
        config, executor, prd_path, progress_path, resume, user_input
    )

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

    branch_suffix = generate_branch_name(task_title, strip_prefix=ticket_id)
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

    if resume is not None:
        engineer_prompt += (
            "\n\nThis task may be partially implemented from an interrupted run. "
            f"Before writing code, review the current state with "
            f"`git diff {top_branch}...HEAD` and `git status`, and continue from "
            "where it left off rather than restarting from scratch."
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


def _validate_resume_target(prd: dict, resume: ResumeDirective) -> None:
    """Validate that a resume target exists in the PRD and isn't already done."""
    task_info = get_task_info(prd, resume.task_number)
    if not task_info:
        raise TicketRalphError(
            f"Cannot resume task {resume.task_number}: not found in PRD.json"
        )
    if task_info.get("done"):
        raise TicketRalphError(
            f"Cannot resume task {resume.task_number}: already marked as done "
            "in PRD.json"
        )


def _build_plan_prompt(
    prd_path: Path,
    progress_path: Path,
    resume: ResumeDirective | None,
    user_input: str,
    autonomous: bool,
) -> str:
    """Build the prompt for the tr-plan agent.

    Auto-picks the next task unless ``resume`` targets the planning phase, in
    which case the agent is told to plan that specific task.
    """
    if resume is not None and resume.phase == ResumePhase.PLAN:
        plan_prompt = (
            f"Plan task {resume.task_number} for the PRD at {prd_path} "
            f"(progress: {progress_path}). Write the plan to "
            f"plan-{resume.task_number}.md for this specific task."
        )
    else:
        plan_prompt = (
            f"Plan the next task for the PRD at {prd_path} (progress: {progress_path})."
        )

    if user_input:
        plan_prompt += f"\n\nAdditional context: {user_input}"

    if autonomous:
        plan_prompt += (
            "\n\nYou are running in autonomous mode (non-interactive). "
            "Your final output MUST be a JSON object with {done, overview}. "
            "Set done=false with a clear explanation if you hit a blocker."
        )

    return plan_prompt


def _resolve_task_number(
    config: TicketRalphConfig,
    executor: agent_svc.AgentExecutor,
    prd_path: Path,
    progress_path: Path,
    resume: ResumeDirective | None,
    user_input: str,
) -> tuple[int, dict]:
    """Resolve the task number to implement, running tr-plan when needed.

    Returns the chosen task number and the (possibly re-read) PRD. For an
    implementation-phase resume the planning agent is skipped and the existing
    plan file is reused; otherwise tr-plan runs and the task number is derived
    from the resume directive (continue-plan) or the newest plan file.
    """
    # Implementation-phase resume: skip planning, reuse the existing plan file.
    if resume is not None and resume.phase == ResumePhase.IMPL:
        task_number = resume.task_number
        plan_file = config.tmp_dir / f"plan-{task_number}.md"
        if not plan_file.exists():
            raise TicketRalphError(
                f"No plan-{task_number}.md found for task {task_number}. "
                f"Run with --continue-plan {task_number} first to generate the "
                f"plan, then --continue-impl {task_number}."
            )
        logger.info(
            "Resuming implementation for task %d (skipping planning)", task_number
        )
        return task_number, read_prd(prd_path)

    # Run the planning agent (normal auto-pick or targeted continue-plan).
    plan_prompt = _build_plan_prompt(
        prd_path, progress_path, resume, user_input, config.autonomous
    )
    plan_agent_start = time.time()

    if config.autonomous:
        plan_result = executor.run_autonomous("tr-plan", plan_prompt, AUTONOMOUS_SCHEMA)
        agent_svc.check_autonomous_result(plan_result, "tr-plan", config.tmp_dir)
    else:
        executor.run("tr-plan", plan_prompt, config.task_permission_mode)

    # Re-read PRD in case the plan agent modified task order/titles.
    prd = read_prd(prd_path)

    # Planning-phase resume: the agent was told to plan a specific task.
    if resume is not None and resume.phase == ResumePhase.PLAN:
        task_number = resume.task_number
        plan_file = config.tmp_dir / f"plan-{task_number}.md"
        if not plan_file.exists() or plan_file.stat().st_mtime < plan_agent_start:
            raise TicketRalphError(
                f"Plan file plan-{task_number}.md was not written by the tr-plan "
                f"agent — re-planning task {task_number} may have failed."
            )
        logger.info("Re-planned task %d (plan: %s)", task_number, plan_file.name)
        return task_number, prd

    # Normal mode: the agent chose the task via the newest plan file.
    plan_file = find_latest_plan_file(config.tmp_dir)
    if not plan_file:
        raise TicketRalphError(
            f"No plan file found in {config.tmp_dir} after running tr-plan agent"
        )

    if plan_file.stat().st_mtime < plan_agent_start:
        raise TicketRalphError(
            f"Plan file {plan_file.name} predates this agent run — "
            "the tr-plan agent may have failed to write a new plan."
        )

    task_number = extract_task_number_from_plan(plan_file)
    logger.info("Planning agent chose task %d (plan: %s)", task_number, plan_file.name)
    return task_number, prd
