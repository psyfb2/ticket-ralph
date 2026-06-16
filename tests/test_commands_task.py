"""Tests for ticket_ralph.commands.task."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.exceptions import TicketRalphError
from ticket_ralph.services.agent import AgentResult


@pytest.fixture()
def _setup_task_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up env and patches for task command tests."""
    monkeypatch.setenv("TR_AUTONOMOUS", "false")
    monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-plan.md").touch()
    (agents_dir / "tr-software-engineer.md").touch()

    tickets_dir = tmp_path / "tickets"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


class TestRunTask:
    @pytest.mark.usefixtures("_setup_task_env")
    def test_exits_if_all_done(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": True, "title": "First"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with patch("ticket_ralph.commands.task.git") as mock_git:
            mock_git.check_clean.return_value = None
            run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_raises_if_no_prd(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
        ):
            mock_git.check_clean.return_value = None
            # download_ticket_context does nothing (no PRD)

            with pytest.raises(TicketRalphError, match="PRD.json not found"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_full_success_flow(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        tickets_dir = tmp_path / "tickets"
        ticket_dir = tickets_dir / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [
                {"taskNumber": 1, "done": False, "title": "Add auth"},
                {"taskNumber": 2, "done": False, "title": "Add tests"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        mock_provider = MagicMock(cli_commands=[])

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider", return_value=mock_provider
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            # Pin time.time() to avoid flaky mtime comparisons on
            # filesystems with 1-second resolution (e.g. HFS+)
            mock_time.time.return_value = 1000.0

            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            executor = mock_agent.AgentExecutor.return_value

            call_count = 0

            def fake_agent_run(agent, prompt, perm):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Plan agent writes a plan file
                    plan_file = ticket_dir / "plan-1.md"
                    plan_file.write_text("# Plan for task 1")

            executor.run.side_effect = fake_agent_run

            run_task("PROJ-1")

            updated_prd = json.loads((ticket_dir / "PRD.json").read_text())
            assert updated_prd["tasks"][0]["done"] is True

            mock_git.merge_no_ff.assert_called_once()
            mock_provider.upload_attachment.assert_called()

    @pytest.mark.usefixtures("_setup_task_env")
    def test_missing_top_branch(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {"tasks": [{"taskNumber": 1, "done": False}]}
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with patch("ticket_ralph.commands.task.git") as mock_git:
            mock_git.check_clean.return_value = None
            with pytest.raises(TicketRalphError, match="topBranch not set"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_autonomous_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ticket_ralph.commands.task import run_task

        monkeypatch.setenv("TR_AUTONOMOUS", "true")

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": False, "title": "Task one"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            executor = mock_agent.AgentExecutor.return_value

            plan_result = AgentResult(
                exit_code=0,
                structured_output={"done": True, "overview": "planned"},
            )
            engineer_result = AgentResult(
                exit_code=0,
                structured_output={"done": True, "overview": "done"},
            )
            executor.run_autonomous.side_effect = [plan_result, engineer_result]
            mock_agent.check_autonomous_result.return_value = None

            # Plan agent writes plan file
            def fake_check(result, name, tmp):
                if name == "tr-plan":
                    (ticket_dir / "plan-1.md").write_text("plan")

            mock_agent.check_autonomous_result.side_effect = fake_check

            run_task("PROJ-1")
            assert executor.run_autonomous.call_count == 2

    @pytest.mark.usefixtures("_setup_task_env")
    def test_stale_plan_file(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": False, "title": "Task"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()
        # Pre-create an old plan file
        (ticket_dir / "plan-1.md").write_text("old plan")

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            # Set time.time() far in the future so plan file is "stale"
            mock_time.time.return_value = 9999999999.0
            mock_git.check_clean.return_value = None
            executor = mock_agent.AgentExecutor.return_value
            executor.run.return_value = None  # agent does nothing

            with pytest.raises(TicketRalphError, match="predates this agent run"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_raises_no_plan_file(self, tmp_path: Path) -> None:
        """Covers line 118: no plan file after agent runs."""
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": False, "title": "Task"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            executor = mock_agent.AgentExecutor.return_value
            executor.run.return_value = None  # agent doesn't create plan

            with pytest.raises(TicketRalphError, match="No plan file found"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_raises_task_not_found(self, tmp_path: Path) -> None:
        """Covers line 136: task number from plan not in PRD."""
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": False, "title": "Task"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                # Plan agent writes plan for task 99 which doesn't exist
                (ticket_dir / "plan-99.md").write_text("plan")

            executor.run.side_effect = fake_run

            with pytest.raises(TicketRalphError, match="Task 99 not found"):
                run_task("PROJ-1")

    @pytest.mark.usefixtures("_setup_task_env")
    def test_raises_task_already_done(self, tmp_path: Path) -> None:
        """Covers line 138: task already marked done."""
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [
                {"taskNumber": 1, "done": True, "title": "Done task"},
                {"taskNumber": 2, "done": False, "title": "Open task"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                # Agent picks task 1 which is already done
                (ticket_dir / "plan-1.md").write_text("plan")

            executor.run.side_effect = fake_run

            with pytest.raises(TicketRalphError, match="already marked as done"):
                run_task("PROJ-1")


class TestRunTaskResume:
    """Tests for the --continue-plan / --continue-impl resume directives."""

    @staticmethod
    def _write_prd(ticket_dir: Path) -> None:
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [
                {"taskNumber": 1, "done": False, "title": "Add auth"},
                {"taskNumber": 2, "done": False, "title": "Add tests"},
            ],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

    @pytest.mark.usefixtures("_setup_task_env")
    def test_continue_plan_targets_specific_task(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)

        mock_provider = MagicMock(cli_commands=[])
        prompts: list[tuple[str, str]] = []

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=mock_provider,
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prompts.append((agent, prompt))
                if agent == "tr-plan":
                    # Agent plans task 2; a stray newer plan must be ignored.
                    (ticket_dir / "plan-2.md").write_text("# Plan task 2")
                    (ticket_dir / "plan-5.md").write_text("# Stray plan")

            executor.run.side_effect = fake_run

            run_task(
                "PROJ-1",
                resume=ResumeDirective(ResumePhase.PLAN, 2),
            )

            # Task 2 (not the stray 5) was implemented and merged.
            updated_prd = json.loads((ticket_dir / "PRD.json").read_text())
            assert updated_prd["tasks"][1]["done"] is True
            assert updated_prd["tasks"][0]["done"] is False
            mock_git.merge_no_ff.assert_called_once()

            plan_prompt = next(p for a, p in prompts if a == "tr-plan")
            assert "Plan task 2" in plan_prompt
            eng_prompt = next(p for a, p in prompts if a == "tr-software-engineer")
            assert "partially implemented" in eng_prompt

    @pytest.mark.usefixtures("_setup_task_env")
    def test_continue_impl_skips_planning(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)
        # A plan from a prior (interrupted) run already exists.
        (ticket_dir / "plan-2.md").write_text("# Plan task 2")

        mock_provider = MagicMock(cli_commands=[])
        prompts: list[tuple[str, str]] = []

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=mock_provider,
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
        ):
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prompts.append((agent, prompt))

            executor.run.side_effect = fake_run

            run_task(
                "PROJ-1",
                resume=ResumeDirective(ResumePhase.IMPL, 2),
            )

            # Only the engineer agent ran — planning was skipped.
            assert executor.run.call_count == 1
            assert prompts[0][0] == "tr-software-engineer"
            assert "partially implemented" in prompts[0][1]

            updated_prd = json.loads((ticket_dir / "PRD.json").read_text())
            assert updated_prd["tasks"][1]["done"] is True
            mock_git.merge_no_ff.assert_called_once()

    @pytest.mark.usefixtures("_setup_task_env")
    def test_continue_impl_missing_plan_file(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)
        # No plan-2.md exists.

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc"),
        ):
            mock_git.check_clean.return_value = None

            with pytest.raises(TicketRalphError, match="No plan-2.md found"):
                run_task(
                    "PROJ-1",
                    resume=ResumeDirective(ResumePhase.IMPL, 2),
                )

    @pytest.mark.usefixtures("_setup_task_env")
    def test_continue_plan_agent_writes_no_plan(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            executor = mock_agent.AgentExecutor.return_value
            executor.run.return_value = None  # agent writes no plan file

            with pytest.raises(
                TicketRalphError, match="was not written by the tr-plan"
            ):
                run_task(
                    "PROJ-1",
                    resume=ResumeDirective(ResumePhase.PLAN, 2),
                )

    @pytest.mark.usefixtures("_setup_task_env")
    def test_resume_task_not_found(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc"),
        ):
            mock_git.check_clean.return_value = None

            with pytest.raises(TicketRalphError, match="not found in PRD.json"):
                run_task(
                    "PROJ-1",
                    resume=ResumeDirective(ResumePhase.PLAN, 99),
                )

    @pytest.mark.usefixtures("_setup_task_env")
    def test_resume_task_already_done(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import (
            ResumeDirective,
            ResumePhase,
            run_task,
        )

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        prd = {
            "topBranch": "PROJ-1-feature",
            "tasks": [{"taskNumber": 1, "done": True, "title": "Done task"}],
        }
        (ticket_dir / "PRD.json").write_text(json.dumps(prd))
        (ticket_dir / "progress.txt").touch()

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc"),
        ):
            mock_git.check_clean.return_value = None

            with pytest.raises(TicketRalphError, match="already marked as done"):
                run_task(
                    "PROJ-1",
                    resume=ResumeDirective(ResumePhase.IMPL, 1),
                )

    @pytest.mark.usefixtures("_setup_task_env")
    def test_normal_run_has_no_partial_note(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.task import run_task

        ticket_dir = tmp_path / "tickets" / "PROJ-1"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        self._write_prd(ticket_dir)

        prompts: list[tuple[str, str]] = []

        with (
            patch("ticket_ralph.commands.task.git") as mock_git,
            patch(
                "ticket_ralph.commands.task.create_provider",
                return_value=MagicMock(cli_commands=[]),
            ),
            patch("ticket_ralph.commands.task.agent_svc") as mock_agent,
            patch("ticket_ralph.commands.task.time") as mock_time,
        ):
            mock_time.time.return_value = 1000.0
            mock_git.check_clean.return_value = None
            mock_git.branch_exists.return_value = False
            mock_git.is_clean.return_value = True
            executor = mock_agent.AgentExecutor.return_value

            def fake_run(agent, prompt, perm):
                prompts.append((agent, prompt))
                if agent == "tr-plan":
                    (ticket_dir / "plan-1.md").write_text("# Plan")

            executor.run.side_effect = fake_run

            run_task("PROJ-1")

            eng_prompt = next(p for a, p in prompts if a == "tr-software-engineer")
            assert "partially implemented" not in eng_prompt
