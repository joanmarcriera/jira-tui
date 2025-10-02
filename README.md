# jira-tui

A Textual terminal user interface (TUI) that wraps [`jira-cli`](https://github.com/ankitpokhrel/jira-cli)
so you can execute common JIRA workflows without leaving the terminal. The application checks
that `jira-cli` is configured, offers shortcuts for day-to-day actions (listing, viewing,
creating and updating issues) and exposes a terminal window for interactive commands such as
`jira init` or `jira issue create`.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
jira-tui
```

### Requirements

* Python 3.11+
* [`jira-cli`](https://github.com/ankitpokhrel/jira-cli) installed and available on `PATH`

When `jira-tui` launches it verifies that `jira` is available. If the configuration is missing,
press `g` to open an interactive session running `jira init`.

## Key bindings (MVP)

| Key | Action |
| --- | ------ |
| `g` | Run `jira init` inside the embedded terminal |
| `R` | Re-check authentication status |
| `/` | Execute a JQL search (`jira issue list --jql ... --plain`) |
| `i` | List issues assigned to you |
| `v` | View issue details |
| `c` | Run `jira issue create` in the embedded terminal |
| `C` | Add a comment to an issue |
| `t` | Transition an issue to a new state |
| `?` | Display available shortcuts in the log |
| `q` | Quit the application |

## Roadmap / Task list

- [x] Package skeleton with Textual dependency and CLI entrypoint
- [x] Configuration status check with `jira me`
- [x] Embedded terminal for interactive commands (`jira init`, `jira issue create`)
- [x] Keyboard shortcuts for common flows (list/view/comment/transition)
- [ ] Persist user preferences (favourite JQLs, default project)
- [x] Dedicated panes for issue lists and detailed views
- [x] Tests (mocked subprocess calls)
- [x] Richer error handling for non-zero exit codes
- [x] Document sync workflow to avoid accidental merge conflicts
- [ ] Configurable key bindings and command palette
- [ ] Support offline caching for last issue queries
- [ ] Automate a pre-work sync check (pre-commit/pre-push hook)

## Development

Run linting (optional if `ruff` is installed):

```bash
ruff check .
```

Launch the TUI in development mode with live reload:

```bash
textual run --dev jira_tui.app:JiraTUIApp
```

### Working with Git without conflicts

To avoid surprises when collaborating:

1. Always update your local branch before making changes:

   ```bash
   git fetch origin
   git checkout main
   git pull --rebase
   git checkout -
   git rebase origin/main
   ```

   Rebase keeps the history linear and minimises the likelihood of merge conflicts in pull
   requests.

2. If you already have local commits, re-run the rebase before pushing to ensure they sit on
   top of the latest `origin/main` changes.

3. When conflicts do occur, resolve them locally and run the full test suite (`pytest`) before
   pushing.

These steps make sure everyone is working with the same base and significantly reduce the
chance of the conflict we hit earlier.

