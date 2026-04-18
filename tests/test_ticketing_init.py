"""Tests for ticket_ralph.ticketing factory."""

from unittest.mock import patch

from ticket_ralph.ticketing import create_provider
from ticket_ralph.ticketing.jira import JiraProvider
from ticket_ralph.ticketing.noop import NoOpProvider


class TestCreateProvider:
    def test_jira_returns_jira_provider(self) -> None:
        with patch.object(JiraProvider, "from_env", return_value=JiraProvider()):
            provider = create_provider("jira")
        assert isinstance(provider, JiraProvider)

    def test_unknown_returns_noop_provider(self) -> None:
        provider = create_provider("linear")
        assert isinstance(provider, NoOpProvider)
        assert provider.provider_name == "linear"
