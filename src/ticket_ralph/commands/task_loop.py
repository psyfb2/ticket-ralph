"""Task loop command — ports scripts/task-loop.sh.

Runs task implementation in a loop until all PRD tasks are complete.
Max iterations = 2x initial task count to prevent infinite loops.
"""

import logging

from ticket_ralph.commands.task import ResumeDirective, run_task
from ticket_ralph.config import TicketRalphConfig
from ticket_ralph.exceptions import AutonomousBlocker, TicketRalphError
from ticket_ralph.utils import count_remaining_tasks, notify_blocker, read_prd

logger = logging.getLogger("ticket-ralph")


def run_task_loop(
    ticket_id: str,
    user_input: str = "",
    *,
    resume: ResumeDirective | None = None,
) -> None:
    """Run tasks in a loop until all PRD tasks are complete.

    Args:
        ticket_id: Jira ticket ID (e.g. PROJ-123).
        user_input: Optional extra context from the user.
        resume: Optional directive to resume a specific task at a specific
            phase. Applied to the first iteration only; subsequent iterations
            let the planning agent auto-pick the next available task.
    """
    config = TicketRalphConfig.from_env(ticket_id)
    prd_path = config.tmp_dir / "PRD.json"

    iteration = 0
    max_iterations = 0

    logger.info("=== Starting task loop for %s ===", ticket_id)

    while True:
        iteration += 1
        logger.info("--- Task loop iteration %d ---", iteration)

        try:
            # Apply the resume directive only on the first iteration; later
            # iterations let the planning agent auto-pick the next task.
            if iteration == 1 and resume is not None:
                run_task(ticket_id, user_input, resume=resume)
            else:
                run_task(ticket_id, user_input)
        except AutonomousBlocker as e:
            logger.error("AUTONOMOUS: Agent hit a blocker on iteration %d", iteration)
            logger.error("Overview: %s", e.overview)
            notify_blocker(ticket_id, e.overview)
            raise
        except TicketRalphError:
            logger.error("task failed on iteration %d", iteration)
            raise

        # PRD.json is guaranteed to exist after a successful run_task call.
        prd = read_prd(prd_path)

        # Set the iteration safeguard once after the first successful run.
        if iteration == 1:
            initial_tasks = len(prd.get("tasks", []))
            max_iterations = max(initial_tasks * 2, 1)
            logger.info(
                "Initial task count: %d — max iterations set to %d",
                initial_tasks,
                max_iterations,
            )

        remaining = count_remaining_tasks(prd)

        if remaining == 0:
            logger.info(
                "=== All tasks complete after %d iteration(s) for %s ===",
                iteration,
                ticket_id,
            )
            return

        logger.info("%d task(s) remaining after iteration %d.", remaining, iteration)

        if iteration >= max_iterations:
            raise TicketRalphError(
                f"Reached max iterations ({max_iterations}) with {remaining} "
                "task(s) still incomplete. Aborting."
            )
