# session-archive (SessionEnd hook)

From reel #04: *"Closed the terminal. Lost 2 hours of context."*

Claude Code already saves every session and lets you get back to it:

```bash
claude -n auth-refactor          # name it when you start
/rename auth-refactor            # ...or name it mid-session
claude --resume auth-refactor    # come back to it by name
claude -c                        # or just continue the latest one here
/branch try-streaming            # fork to try a risky idea; original stays intact
/rewind                          # (or Esc Esc) restore code, conversation, or both
```

The catch: those transcripts live in `~/.claude/projects/` and are **cleaned up after ~30 days** by default. They also disappear with a reinstall, a new laptop, or `rm -rf ~/.claude`.

This hook copies every finished session to an archive you control, and keeps an index you can search.

## Simpler alternative first

If you only want sessions to live longer on this machine, you don't need a hook. Add this to `~/.claude/settings.json`:

```json
{ "cleanupPeriodDays": 365 }
```

Use the hook when you also want an archive outside `~/.claude` (backups, a new machine, an encrypted disk) and a cross-project index.

## Install

```bash
git clone https://github.com/ashishjain-dev/ctrl-alt-lazy-skills
cd ctrl-alt-lazy-skills
python3 hooks/session-archive/install.py --dry-run   # preview the settings change
python3 hooks/session-archive/install.py             # install (backs up settings.json first)
```

It's idempotent, keeps all your existing settings and hooks, and can be removed with `--uninstall`. Run `/hooks` in Claude Code to confirm it's registered. Requires `python3` on your PATH.

## What you get

```
~/.claude-session-archive/
├── index.jsonl                         # one line per session end
└── <project>/<session_id>.jsonl.gz     # compressed transcript
```

Each index line looks like this:

```json
{"archived_at":"2026-11-07T06:30:00+00:00","session_id":"…","project":"payments-api","cwd":"/work/payments-api","git_branch":"feat/idempotency","end_reason":"prompt_input_exit","bytes":182344,"first_prompt":"add idempotency keys to the transfer endpoint…","archive":"…/payments-api/….jsonl.gz"}
```

Find that session from three weeks ago:

```bash
grep -i "idempotency" ~/.claude-session-archive/index.jsonl | tail -5
zcat ~/.claude-session-archive/payments-api/<session_id>.jsonl.gz | less
```

## Configure (optional environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_SESSION_ARCHIVE_DIR` | `~/.claude-session-archive` | Where archives go, e.g. an encrypted volume or backed-up folder |
| `CLAUDE_SESSION_ARCHIVE_SKIP` | *(none)* | End reasons to skip, e.g. `clear` |
| `CLAUDE_SESSION_ARCHIVE_MIN_BYTES` | `2048` | Skip trivial sessions |

## How it behaves

- **Never blocks Claude Code.** SessionEnd hooks can't block anyway, and every error is logged to stderr with exit 0.
- **Atomic and idempotent.** It writes a temp file, then renames it. A resumed session overwrites its own archive, because the newer transcript contains everything the older one did.
- **Private by default.** The folder is `0700` and files are `0600`.
- **Format-agnostic.** It copies the transcript as-is. The index's `first_prompt` is best-effort, because the transcript format is internal to Claude Code and can change between versions.

## Read this before you install it on a work machine

Transcripts contain your prompts, code, command output, and anything secret that passed through the session. Treat the archive like source code:

- Keep it on an encrypted disk, and **don't** point it at a personal cloud folder for employer or client code.
- Check your organisation's data-retention policy. Some teams *want* the 30-day cleanup.
- To scrub it, delete the folder. Nothing else depends on it.

## Limits

- `/rewind` only restores Claude's own file edits, not changes made by shell commands (`rm`, `mv`, scripts). Git is still your safety net.
- Resuming the *same* session in two terminals mixes both into one transcript. Use `/branch` instead.
- Archived transcripts are for reading and searching. Resume live sessions with `claude --resume`; copying archives back into `~/.claude` relies on internal formats and isn't supported.
