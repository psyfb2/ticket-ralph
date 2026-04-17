"""Agent execution via the Claude CLI.

Supports two modes:
- Interactive (run): user sees agent output and can approve/deny actions.
- Autonomous (run_autonomous): non-interactive with stream-json output,
  text deltas streamed to stderr for observability.
"""

import json
import logging
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ticket_ralph.config import TicketRalphConfig
from ticket_ralph.exceptions import AgentError, AutonomousBlocker, TicketRalphError

logger = logging.getLogger("ticket-ralph")


@dataclass
class AgentResult:
    """Result from an autonomous agent run."""

    exit_code: int
    structured_output: dict | None


class AgentExecutor:
    """Executes Claude Code agents via subprocess."""

    def __init__(self, config: TicketRalphConfig) -> None:
        self.config = config

    def _subprocess_env(self) -> dict[str, str]:
        """Build environment for agent subprocesses.

        Inherits the current environment and adds TR_TMP_DIR so agents
        can reference $TR_TMP_DIR in their shell commands.
        """
        return {**os.environ, "TR_TMP_DIR": str(self.config.tmp_dir)}

    def _check_agent_exists(self, agent_name: str) -> None:
        """Verify the agent file exists.

        Raises:
            TicketRalphError: If the agent file is not found.
        """
        agent_file = self.config.agents_dir / f"{agent_name}.md"
        if not agent_file.exists():
            raise TicketRalphError(
                f"Agent file not found: {agent_file}\n"
                "Run 'make tr-install' to build and install agent files."
            )

    def run(
        self,
        agent_name: str,
        prompt: str,
        permission_mode: str = "acceptEdits",
    ) -> None:
        """Run an agent interactively.

        Args:
            agent_name: Name of the agent (without .md extension).
            prompt: Prompt to send to the agent.
            permission_mode: Claude Code permission mode.

        Raises:
            AgentError: If the agent exits with a non-zero code.
        """
        self._check_agent_exists(agent_name)

        cmd = ["claude", "--agent", agent_name]
        if self.config.autonomous:
            cmd.append("--dangerously-skip-permissions")
            logger.info("Running agent: %s (autonomous, interactive)", agent_name)
        else:
            cmd.extend(["--permission-mode", permission_mode])
            logger.info(
                "Running agent: %s (permission-mode: %s)",
                agent_name,
                permission_mode,
            )

        cmd.append(prompt)

        logger.info("--- Command ---\n%s\n--- End command ---", shlex.join(cmd))
        result = subprocess.run(cmd, check=False, env=self._subprocess_env())

        if result.returncode != 0:
            logger.error("Agent %s exited with code %d", agent_name, result.returncode)
            raise AgentError(agent_name, result.returncode)

        logger.info("Agent %s complete", agent_name)

    def run_autonomous(
        self,
        agent_name: str,
        prompt: str,
        json_schema: str = "",
    ) -> AgentResult:
        """Run an agent non-interactively with stream-json output.

        Streams text deltas to stderr for observability. Extracts structured
        output from the result event if a json_schema is provided.

        Args:
            agent_name: Name of the agent (without .md extension).
            prompt: Prompt to send to the agent.
            json_schema: JSON schema for structured output.

        Returns:
            AgentResult with exit code and optional structured output.

        Raises:
            AgentError: If the agent exits with a non-zero code.
        """
        self._check_agent_exists(agent_name)

        logger.info("Running agent (autonomous, non-interactive): %s", agent_name)

        cmd = [
            "claude",
            "-p",
            "--agent",
            agent_name,
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if json_schema:
            cmd.extend(["--json-schema", json_schema])
        cmd.append(prompt)

        logger.info("--- Command ---\n%s\n--- End command ---", shlex.join(cmd))

        structured_output: dict | None = None

        with subprocess.Popen(
            cmd, stdout=subprocess.PIPE, text=True, env=self._subprocess_env()
        ) as proc:
            if proc.stdout is None:
                raise TicketRalphError(
                    f"Failed to capture stdout from agent {agent_name}"
                )
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Stream text deltas to stderr for real-time observability
                if (
                    event.get("type") == "stream_event"
                    and event.get("event", {}).get("delta", {}).get("type")
                    == "text_delta"
                ):
                    text = event["event"]["delta"]["text"]
                    print(text, end="", file=sys.stderr, flush=True)

                # Capture structured output from the result event
                if event.get("type") == "result" and json_schema:
                    structured_output = event.get("structured_output")
            print()
            proc.wait()

        if proc.returncode != 0:
            logger.error("Agent %s exited with code %d", agent_name, proc.returncode)
            raise AgentError(agent_name, proc.returncode)

        logger.info("Agent %s (autonomous) complete", agent_name)
        return AgentResult(
            exit_code=proc.returncode, structured_output=structured_output
        )


def check_autonomous_result(
    result: AgentResult,
    agent_name: str,
    tmp_dir: Path,
) -> None:
    """Check the structured result from an autonomous agent run.

    Args:
        result: The agent result to check.
        agent_name: Name of the agent (for error messages).
        tmp_dir: Ticket tmp directory (for writing blocker file).

    Raises:
        TicketRalphError: If no structured output was produced.
        AutonomousBlocker: If the agent reported done=false.
    """
    from ticket_ralph.exceptions import TicketRalphError

    if not result.structured_output:
        raise TicketRalphError(
            f"Agent {agent_name} produced no structured output — "
            "cannot determine completion status"
        )

    done = result.structured_output.get("done", False)
    overview = result.structured_output.get("overview", "")

    if not done:
        blocker_file = tmp_dir / ".blocker-overview"
        blocker_file.write_text(overview)
        raise AutonomousBlocker(overview, agent_name)

    logger.info("Agent %s completed: %s", agent_name, overview)
