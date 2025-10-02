from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import Mock

import pytest
import pytest_asyncio

from jira_tui.app import (
    CommandResult,
    IssueDetailPanel,
    IssueListPanel,
    JiraTUIApp,
    StatusWidget,
)
from textual.widgets import Log


class LogStub:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, line: str) -> None:
        self.lines.append(line)


class PanelStub:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.errors: list[str] = []

    def show_message(self, message: str) -> None:
        self.messages.append(message)

    def display_output(self, output: str) -> None:
        self.messages.append(output)

    def show_error(self, message: str) -> None:
        self.errors.append(message)


class StatusStub:
    def __init__(self) -> None:
        self.status = ""


class _TestableJiraTUIApp(JiraTUIApp):
    def __init__(self) -> None:
        super().__init__()
        self._log_widget = LogStub()
        self.issue_list_panel = PanelStub()
        self.issue_detail_panel = PanelStub()
        self.status_widget = StatusStub()

    def query_one(self, query, *args, **kwargs):  # type: ignore[override]
        if query is Log or query == Log:
            return self._log_widget
        if query is IssueListPanel:
            return self.issue_list_panel
        if query is IssueDetailPanel:
            return self.issue_detail_panel
        if query is StatusWidget:
            return self.status_widget
        raise LookupError(f"Unsupported selector: {query}")


@pytest_asyncio.fixture
async def app() -> AsyncIterator[_TestableJiraTUIApp]:
    instance = _TestableJiraTUIApp()
    yield instance


@pytest.mark.asyncio
async def test_run_jira_command_routes_stdout(monkeypatch: pytest.MonkeyPatch, app: _TestableJiraTUIApp) -> None:
    panel = app.issue_list_panel
    display_mock = Mock(wraps=panel.display_output)
    monkeypatch.setattr(panel, "display_output", display_mock)

    async def fake_subprocess(*_cmd, **_kwargs):
        class DummyProcess:
            returncode = 0

            async def communicate(self):
                return b"ISSUE-1\nISSUE-2\n", b""

        return DummyProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

    result = await app._run_jira_command(["issue", "list"], stdout_target=panel)

    assert result.ok
    display_mock.assert_called_once_with("ISSUE-1\nISSUE-2")


@pytest.mark.asyncio
async def test_run_jira_command_failure_logs_error(monkeypatch: pytest.MonkeyPatch, app: _TestableJiraTUIApp) -> None:
    panel = app.issue_list_panel
    error_mock = Mock(wraps=panel.show_error)
    monkeypatch.setattr(panel, "show_error", error_mock)

    async def fake_subprocess(*_cmd, **_kwargs):
        class DummyProcess:
            returncode = 1

            async def communicate(self):
                return b"", b"boom"

        return DummyProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)

    result = await app._run_jira_command(["issue", "list"], stdout_target=panel)

    assert not result.ok
    assert any("exited with code 1" in line for line in app._log_widget.lines)
    error_mock.assert_called_once()


@pytest.mark.asyncio
async def test_check_configuration_handles_missing_binary(
    monkeypatch: pytest.MonkeyPatch, app: _TestableJiraTUIApp
) -> None:
    async def raise_not_found(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(app, "_run_jira_command", raise_not_found)

    await app.check_configuration()

    assert app.configured is False
    assert "not installed" in app.status_widget.status
    assert any("Unable" in line for line in app._log_widget.lines)


@pytest.mark.asyncio
async def test_check_configuration_success(monkeypatch: pytest.MonkeyPatch, app: _TestableJiraTUIApp) -> None:
    async def fake_run(*_args, **_kwargs):
        return CommandResult(["jira", "me"], "Authenticated", "", 0)

    monkeypatch.setattr(app, "_run_jira_command", fake_run)

    await app.check_configuration()

    assert app.configured is True
    assert "authenticated" in app.status_widget.status.lower()


@pytest.mark.asyncio
async def test_action_my_issues_updates_panel(monkeypatch: pytest.MonkeyPatch, app: _TestableJiraTUIApp) -> None:
    panel = app.issue_list_panel
    display_mock = Mock(wraps=panel.display_output)
    monkeypatch.setattr(panel, "display_output", display_mock)

    async def fake_run(*_args, **kwargs):
        stdout_target = kwargs.get("stdout_target")
        if stdout_target is not None:
            stdout_target.display_output("ISSUE-123")
        return CommandResult(["jira", "issue", "list"], "ISSUE-123", "", 0)

    monkeypatch.setattr(app, "_run_jira_command", fake_run)

    await app.action_my_issues()

    display_mock.assert_called_with("ISSUE-123")
