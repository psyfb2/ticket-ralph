"""Tests for ticket_ralph.commands.boost."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ticket_ralph.exceptions import TicketRalphError


@pytest.fixture()
def _setup_boost_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Set up env vars and patch paths for boost command tests."""
    monkeypatch.delenv("TR_AUTONOMOUS", raising=False)
    monkeypatch.setenv("TR_TICKETING_PLATFORM", "Jira")

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "tr-boost.md").touch()

    tickets_dir = tmp_path / "tickets"

    with (
        patch("ticket_ralph.config.AGENTS_DIR", agents_dir),
        patch("ticket_ralph.config.TICKETS_DIR", tickets_dir),
        patch("ticket_ralph.config.PREREQUISITE_COMMANDS", ["python3"]),
    ):
        yield tmp_path


def _cli_provider() -> MagicMock:
    """A provider that declares a ticketing CLI, as jira/linear do."""
    return MagicMock(cli_commands=["jira"], provider_name="Jira")


def _write_boost_file(tickets_dir: Path) -> None:
    """Simulate the agent producing its refined-requirements artifact."""
    (tickets_dir / "PROJ-1" / "boost.md").write_text("## Goal\nShip it.")


class TestRunBoost:
    @pytest.mark.usefixtures("_setup_boost_env")
    def test_raises_if_no_boost_file_produced(self) -> None:
        from ticket_ralph.commands.boost import run_boost

        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=_cli_provider(),
            ),
            patch("ticket_ralph.commands.boost.agent_svc"),
            pytest.raises(TicketRalphError, match="did not produce boost.md"),
        ):
            run_boost("PROJ-1")

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_success_flow(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.boost import run_boost

        tickets_dir = tmp_path / "tickets"

        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=_cli_provider(),
            ),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            executor = mock_agent.AgentExecutor.return_value
            executor.run.side_effect = lambda *_: _write_boost_file(tickets_dir)

            run_boost("PROJ-1")

            assert executor.run.call_args[0][0] == "tr-boost"
            assert (tickets_dir / "PROJ-1" / "boost.md").exists()

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_makes_no_git_calls(self, tmp_path: Path) -> None:
        """boost creates no branch and commits nothing, so it never imports git."""
        import ticket_ralph.commands.boost as boost_module

        assert not hasattr(boost_module, "git")

        tickets_dir = tmp_path / "tickets"
        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=_cli_provider(),
            ),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            executor = mock_agent.AgentExecutor.return_value
            executor.run.side_effect = lambda *_: _write_boost_file(tickets_dir)

            # No git mock in place — a git call would hit the real repo.
            boost_module.run_boost("PROJ-1")

            executor.run.assert_called_once()

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_uploads_nothing(self, tmp_path: Path) -> None:
        """The refined requirements land on the ticket body, not as attachments."""
        from ticket_ralph.commands.boost import run_boost

        tickets_dir = tmp_path / "tickets"
        provider = _cli_provider()

        with (
            patch("ticket_ralph.commands.boost.create_provider", return_value=provider),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            executor = mock_agent.AgentExecutor.return_value
            executor.run.side_effect = lambda *_: _write_boost_file(tickets_dir)

            run_boost("PROJ-1")

            provider.upload_attachment.assert_not_called()

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_prompt_includes_platform_ticket_and_extra(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.boost import run_boost

        tickets_dir = tmp_path / "tickets"

        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=_cli_provider(),
            ),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            executor = mock_agent.AgentExecutor.return_value
            executor.run.side_effect = lambda *_: _write_boost_file(tickets_dir)

            run_boost("PROJ-1", "focus on mobile")

            prompt = executor.run.call_args[0][1]
            assert "Jira" in prompt
            assert "PROJ-1" in prompt
            assert "parent story" in prompt
            assert "Additional context: focus on mobile" in prompt

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_no_extra_context_omits_section(self, tmp_path: Path) -> None:
        from ticket_ralph.commands.boost import run_boost

        tickets_dir = tmp_path / "tickets"

        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=_cli_provider(),
            ),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            executor = mock_agent.AgentExecutor.return_value
            executor.run.side_effect = lambda *_: _write_boost_file(tickets_dir)

            run_boost("PROJ-1")

            assert "Additional context" not in executor.run.call_args[0][1]

    @pytest.mark.usefixtures("_setup_boost_env")
    def test_raises_when_provider_has_no_cli(self) -> None:
        """A no-op provider means no ticketing CLI, so boost cannot function."""
        from ticket_ralph.commands.boost import run_boost

        noop_provider = MagicMock(cli_commands=[], provider_name="noop")

        with (
            patch(
                "ticket_ralph.commands.boost.create_provider",
                return_value=noop_provider,
            ),
            patch("ticket_ralph.commands.boost.agent_svc") as mock_agent,
        ):
            with pytest.raises(TicketRalphError, match="needs a ticketing CLI"):
                run_boost("PROJ-1")

            mock_agent.AgentExecutor.assert_not_called()
