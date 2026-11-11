# Hooks

Hooks are scripts Claude Code runs **automatically** at set moments: before a tool runs, after it runs, when a session ends, and so on. A line in `CLAUDE.md` is advice Claude may skip. A hook is code that always runs.

| Hook | Event | What it does |
|---|---|---|
| [`guardrails`](guardrails/) | `PreToolUse` | Stops irreversible commands (`DROP TABLE`, `terraform destroy`, `rm -rf` outside the project…) before Claude runs them |
| [`session-archive`](session-archive/) | `SessionEnd` | Archives every session outside `~/.claude`, with a searchable index |

## Install

One installer for every hook in this folder:

```bash
python3 hooks/install.py --list                 # what's available
python3 hooks/install.py guardrails             # one hook (several names work too)
python3 hooks/install.py --all                  # everything
python3 hooks/install.py guardrails --dry-run   # preview the settings change
python3 hooks/install.py guardrails --uninstall # remove it (logs and archives are kept)
```

It copies the hook to `~/.claude/hooks/<name>/` and registers it in `~/.claude/settings.json`. Your existing settings and hooks are kept, a backup is made first, and re-running it updates in place. `--fail-closed` adds `"onFailure": "block"` for hooks that support it (Claude Code v2.1.295+). Restart open sessions, then check with `/hooks`.

`hooks/<name>/install.py` still works as a shortcut for the same thing.

## Add your own hook

A hook is a folder with a script and a `hook.json` manifest. No installer code to write.

**1. Create the folder and script**

```
hooks/notify-done/
├── hook.json
└── notify.py
```

```python
#!/usr/bin/env python3
"""Ping me when Claude finishes and is waiting for me."""
import json, subprocess, sys

event = json.load(sys.stdin)                     # Claude Code sends the event as JSON on stdin
subprocess.run(["notify-send", "Claude Code", "Done, your turn"])   # macOS: osascript -e 'display notification ...'
sys.exit(0)                                      # 0 = fine, nothing to say
```

**2. Write `hook.json`**

```json
{
  "name": "notify-done",
  "description": "Desktop notification when Claude stops and waits for you",
  "script": "notify.py",
  "files": ["notify.py"],
  "register": [
    {"event": "Stop", "timeout": 5}
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Must equal the folder name (lowercase, digits, dashes) |
| `description` | no | Shown by `--list` |
| `script` | yes | What Claude Code runs. `.py` files run with the Python that ran the installer; anything else must be executable |
| `files` | no | Everything to copy to `~/.claude/hooks/<name>/` (defaults to just `script`). Put data files such as rules here |
| `register` | yes | One entry per event: `event`, optional `matcher` (tool events only, e.g. `"Bash"` or `"Edit\|Write"`), optional `timeout` in seconds |
| `fail_closed` | no | `true` lets `--fail-closed` add `"onFailure": "block"`. Only meaningful for blocking events like `PreToolUse` |
| `after_install` | no | A message printed after install (where data goes, how to configure) |
| `legacy` | no | Old install paths, relative to `~/.claude`, to clean up when you move a hook |

**3. Install and check**

```bash
python3 hooks/install.py notify-done --dry-run   # the installer validates hook.json first
python3 hooks/install.py notify-done
```

### Which event?

| Event | Fires | Typical use |
|---|---|---|
| `PreToolUse` | Before a tool runs (can block it) | Guardrails, protect secrets, enforce conventions |
| `PostToolUse` | After a tool succeeds | Auto-format or lint the file Claude just edited |
| `UserPromptSubmit` | When you send a prompt | Add context (ticket, branch), block prompts with secrets |
| `Notification` | When Claude needs your attention | Desktop or Slack ping |
| `Stop` | When Claude finishes its turn | "Done" ping, run tests before you look |
| `SessionStart` / `SessionEnd` | Session opens / closes | Load context / archive the transcript |

The installer accepts the events in `EVENTS` at the top of `install.py`. Claude Code has a few more; add one there if you need it.

### Rules that save you an afternoon

- **Only exit code 2 (or JSON `"permissionDecision": "deny"`) blocks.** Exit 1 is a non-blocking error: the action still happens.
- A hook that times out or crashes does **not** block unless it has `"onFailure": "block"`.
- Read the event from stdin. Paths in `tool_input.file_path` are always absolute.
- Keep hooks fast; they run on every matching event. Set a `timeout`.
- Treat stdin as untrusted: it contains whatever command or file Claude was about to touch. Never `eval` it.
- Test without Claude by piping JSON in: `echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | python3 my_hook.py`

Full reference: [Claude Code hooks docs](https://code.claude.com/docs/en/hooks).

## Tests

```bash
python3 -m unittest discover -s hooks/tests -v              # the installer
python3 -m unittest discover -s hooks/guardrails/tests -v   # guardrails
```
