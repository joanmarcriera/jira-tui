"""Main Textual application wrapping jira-cli."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Sequence

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Log, Static

try:  # pragma: no cover - import guarded for compatibility
    from textual.widgets import Terminal  # type: ignore
except ImportError:  # pragma: no cover - fallback for Textual without Terminal
    class Terminal(Static):
        """Fallback placeholder when the Textual Terminal widget is unavailable."""

        async def run_command(self, command: Sequence[str]) -> None:
            command_text = " ".join(command)
            self.update(
                "Terminal widget not available.\n"
                "Run the following command manually in your shell:\n"
                f"$ {command_text}"
            )


@dataclass
class CommandResult:
    """Container for stdout/stderr coming from jira-cli."""

    command: Sequence[str]
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class InputDialog(ModalScreen[str | None]):
    """Simple input dialog that resolves with the entered value."""

    CSS = """
    InputDialog {
        align: center middle;
    }

    InputDialog > Container {
        padding: 2;
        width: 60;
        background: $panel;
        border: tall $primary;
    }

    InputDialog Label {
        margin-bottom: 1;
    }

    InputDialog .actions {
        margin-top: 1;
        width: 100%;
        align-horizontal: right;
    }
    """

    def __init__(self, title: str, prompt: str, placeholder: str | None = None) -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._placeholder = placeholder or ""

    def compose(self) -> ComposeResult:
        yield Container(
            Label(self._title, id="title"),
            Label(self._prompt, id="prompt"),
            Input(placeholder=self._placeholder, id="value"),
            Horizontal(
                Button("Cancel", id="cancel"),
                Button("Submit", id="submit", variant="primary"),
                classes="actions",
            ),
        )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#submit")
    def _submit(self) -> None:
        value = self.query_one(Input).value.strip()
        self.dismiss(value or None)

    @on(Input.Submitted)
    def _submit_enter(self, event: Input.Submitted) -> None:  # pragma: no cover - UI event
        self.dismiss(event.value.strip() or None)


class JiraCommandScreen(ModalScreen[None]):
    """Screen used for interactive jira-cli commands."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Close", show=False)]

    def __init__(self, command: Sequence[str]) -> None:
        super().__init__()
        self._command = command

    def compose(self) -> ComposeResult:
        yield Terminal(id="terminal")

    async def on_mount(self) -> None:
        terminal = self.query_one(Terminal)
        await terminal.run_command(list(self._command))


class StatusWidget(Static):
    """Header widget that displays jira-cli status information."""

    status = reactive("Checking jira-cli configuration…", layout=True)

    def watch_status(self, status: str) -> None:  # pragma: no cover - UI update
        self.update(status)


class IssuePanel(Log):
    """Base log panel for issue list/detail content."""

    def __init__(self, placeholder: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder

    def on_mount(self) -> None:  # pragma: no cover - UI update
        self.show_message(self._placeholder)

    def show_message(self, message: str) -> None:
        self.clear()
        for line in message.splitlines() or [""]:
            self.write(line)

    def show_error(self, message: str) -> None:
        self.show_message(f"Error: {message}")

    def display_output(self, output: str) -> None:
        text = output.strip() or "No data returned."
        self.show_message(text)


class IssueListPanel(IssuePanel):
    """Panel displaying results from issue list queries."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Issue lists will appear here.", *args, **kwargs)


class IssueDetailPanel(IssuePanel):
    """Panel displaying detailed issue information."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__("Issue details will appear here.", *args, **kwargs)


class JiraTUIApp(App[None]):
    """Textual-based TUI that wraps ``jira-cli`` shortcuts."""

    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("g", "init", "Configure jira-cli"),
        Binding("R", "refresh", "Re-check auth"),
        Binding("/", "search", "JQL search"),
        Binding("i", "my_issues", "My issues"),
        Binding("v", "view_issue", "View issue"),
        Binding("c", "create_issue", "Create issue"),
        Binding("C", "comment_issue", "Add comment"),
        Binding("t", "transition_issue", "Transition"),
        Binding("?", "show_help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    status_text = reactive("Checking jira-cli configuration…", layout=True)
    configured = reactive(False, layout=True)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            StatusWidget(id="status"),
            Horizontal(
                Log(id="log", classes="pane"),
                Container(
                    IssueListPanel(id="issue-list"),
                    IssueDetailPanel(id="issue-detail"),
                    classes="issue-panes",
                ),
                id="content",
            ),
        )
        yield Footer()

    async def on_mount(self) -> None:
        await self.check_configuration()
        self.set_focus(self.query_one(Log))

    async def check_configuration(self) -> None:
        """Check jira-cli availability and authentication."""
        status_widget = self.query_one(StatusWidget)
        status_widget.status = "Checking jira-cli configuration…"
        try:
            result = await self._run_jira_command(["me"])
        except FileNotFoundError:
            self.configured = False
            status_widget.status = "jira-cli (jira) is not installed or in PATH."
            self._log("Unable to find `jira` binary. Install https://github.com/ankitpokhrel/jira-cli")
            return

        if result.returncode == 0:
            self.configured = True
            status_widget.status = "jira-cli is authenticated ✅"
            if result.stdout:
                self._log(result.stdout)
        else:
            self.configured = False
            status_widget.status = "jira-cli configuration missing. Press 'g' to run jira init."
            if result.stderr:
                self._log(result.stderr)

    async def _run_jira_command(
        self,
        args: Iterable[str],
        *,
        capture_output: bool = True,
        log_command: bool = True,
        stdout_target: IssuePanel | None = None,
    ) -> CommandResult:
        """Execute jira-cli with the given arguments."""

        cmd = ["jira", *args]
        if log_command:
            self._log("$ " + " ".join(cmd))

        if capture_output:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                self._handle_missing_binary(stdout_target)
                raise
            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode().strip()
            stderr = stderr_bytes.decode().strip()
            if stdout:
                if stdout_target is not None:
                    stdout_target.display_output(stdout)
                else:
                    self._log(stdout)
            if stderr:
                self._log(stderr)
            result = CommandResult(cmd, stdout, stderr, process.returncode)
            if not result.ok:
                self._handle_command_failure(result, stdout_target)
            return result

        try:
            process = await asyncio.create_subprocess_exec(*cmd)
        except FileNotFoundError:
            self._handle_missing_binary(stdout_target)
            raise
        await process.wait()
        result = CommandResult(cmd, "", "", process.returncode)
        if not result.ok:
            self._handle_command_failure(result, stdout_target)
        return result

    def _log(self, message: str) -> None:
        log_widget = self.query_one(Log)
        for line in message.splitlines():
            log_widget.write(line)

    def _handle_command_failure(
        self, result: CommandResult, stdout_target: IssuePanel | None = None
    ) -> None:
        message = "Command '{}' exited with code {}".format(
            " ".join(result.command), result.returncode
        )
        self._log(message)
        if stdout_target is not None:
            stdout_target.show_error(message)

    def _handle_missing_binary(self, stdout_target: IssuePanel | None) -> None:
        message = "Unable to execute `jira`. Ensure jira-cli is installed and on PATH."
        self._log(message)
        if stdout_target is not None:
            stdout_target.show_error(message)

    async def action_refresh(self) -> None:
        await self.check_configuration()

    async def action_init(self) -> None:
        await self.push_screen(JiraCommandScreen(["jira", "init"]))
        await self.check_configuration()

    async def action_show_help(self) -> None:
        commands = [
            "g – configure jira-cli (runs `jira init`)",
            "R – re-check authentication",
            "/ – run an arbitrary JQL search",
            "i – list issues assigned to you",
            "v – view an issue",
            "c – create a new issue",
            "C – add a comment to an issue",
            "t – transition an issue",
            "q – quit",
        ]
        self._log("Available shortcuts:\n" + "\n".join(commands))

    async def action_search(self) -> None:
        query = await self._prompt("JQL Search", "Enter a JQL query", placeholder="project = KEY ORDER BY updated DESC")
        if not query:
            return
        try:
            await self._run_jira_command(["issue", "list", "--jql", query, "--plain"])
        except FileNotFoundError:
            return

    async def action_my_issues(self) -> None:
        panel = self.query_one(IssueListPanel)
        panel.show_message("Loading issues assigned to you…")
        try:
            result = await self._run_jira_command(
                ["issue", "list", "--assignee", "me", "--order-by", "updated", "--reverse", "--plain"],
                stdout_target=panel,
            )
        except FileNotFoundError:
            return
        if result.ok and not result.stdout:
            panel.show_message("No issues assigned to you.")

    async def action_view_issue(self) -> None:
        key = await self._prompt("View Issue", "Enter issue key", placeholder="ABC-123")
        if not key:
            return
        panel = self.query_one(IssueDetailPanel)
        panel.show_message(f"Loading issue {key}…")
        try:
            await self._run_jira_command(["issue", "view", key, "--plain"], stdout_target=panel)
        except FileNotFoundError:
            return

    async def action_create_issue(self) -> None:
        await self.push_screen(JiraCommandScreen(["jira", "issue", "create"]))
        await self.check_configuration()

    async def action_comment_issue(self) -> None:
        key = await self._prompt("Add Comment", "Issue key", placeholder="ABC-123")
        if not key:
            return
        comment = await self._prompt("Add Comment", "Comment body")
        if not comment:
            return
        try:
            result = await self._run_jira_command([
                "issue",
                "comment",
                "add",
                key,
                "--comment",
                comment,
            ])
        except FileNotFoundError:
            return
        if result.ok:
            self._log(f"Comment added to {key}.")

    async def action_transition_issue(self) -> None:
        key = await self._prompt("Transition Issue", "Issue key", placeholder="ABC-123")
        if not key:
            return
        state = await self._prompt("Transition Issue", "Target state", placeholder="In Progress")
        if not state:
            return
        try:
            result = await self._run_jira_command([
                "issue",
                "transition",
                key,
                "--state",
                state,
            ])
        except FileNotFoundError:
            return
        if result.ok:
            self._log(f"Transitioned {key} to {state}.")

    async def _prompt(self, title: str, prompt: str, *, placeholder: str | None = None) -> str | None:
        return await self.push_screen_wait(InputDialog(title, prompt, placeholder))


if __name__ == "__main__":  # pragma: no cover - manual invocation
    JiraTUIApp().run()

