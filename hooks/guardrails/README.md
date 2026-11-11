# guardrails: stop Claude before it runs the command that gets you fired

A Claude Code `PreToolUse` hook. Before Claude runs a shell command or edits a file, `guard.py` checks it. A dangerous call is **denied** (it never runs, and Claude is told why) or you get an **ask** prompt, even in auto-accept modes.

```
Claude: psql $DATABASE_URL -c "DROP TABLE payments;"
Hook:   guardrails [sql-drop]: destructive SQL (DROP or TRUNCATE).
        Instead: write it as a reviewed migration with a backup or rollback plan, and let a human run it.
Claude: Blocked by a hook. Here's the migration instead, for you to review…
```

From reel #11 on [@ctrl.alt.lazy](https://instagram.com/ctrl.alt.lazy).

## Install

```bash
python3 hooks/install.py guardrails
```

Then restart open Claude Code sessions. Needs Python 3.8+ and nothing else. Installer options (`--dry-run`, `--uninstall`) are in [hooks/README.md](../README.md#install).

## What it guards

All 12 rules, with their messages, are in [`rules.json`](rules.json).

| Rule | Catches | Decision |
|---|---|---|
| `sql-drop` | `DROP TABLE/DATABASE/…`, `TRUNCATE` | deny |
| `sql-delete-no-where` | `DELETE FROM x;` with no `WHERE` | deny |
| `db-drop-tools` | `dropdb`, `prisma migrate reset`, `rails db:drop`, `redis-cli FLUSHALL`, … | deny |
| `terraform-destroy` | `terraform destroy`, `apply -auto-approve` | deny |
| `disk-wipe` | `mkfs`, `dd of=/dev/…`, `chmod -R 777 /` | deny |
| `force-push` | force-push to `main`, `master`, `develop`, `release/*`, `prod` (your own branch is fine) | deny |
| `rm-recursive` | `rm -r` on `/`, `~`, `.`, an unexpanded `$VAR`, or anything outside the project | deny |
| `kubectl-prod` | `kubectl delete/drain/…` on a prod context (deny); `kubectl delete` with no `--context` (ask) | deny / ask |
| `git-discard` | `git reset --hard`, `git clean -f`, `git stash drop` | ask |
| `pipe-to-shell` | `curl … \| bash` | ask |
| `self-protect` | Claude editing Claude Code settings or the guardrails files (Edit/Write) | ask |
| `self-protect-bash` | the same, done with a shell command | ask |

Chained commands are split, so `cd src && rm -rf /` is caught.

## Try it

Check any command without starting Claude:

```bash
python3 ~/.claude/hooks/guardrails/guard.py --test 'git push --force origin main'
# DENY   [force-push] force-push to a protected branch: 'main'
#        Instead: Push to a branch and open a PR. Use --force-with-lease on your own branch.
```

Every deny and ask is also logged to `~/.claude/guardrails/audit.jsonl`, with passwords masked.

## Turn it off for one session

Start Claude Code with the variable set. Claude can't do this from inside a session.

```bash
CLAUDE_GUARDRAILS=off claude                     # bash
$env:CLAUDE_GUARDRAILS = "off"; claude           # PowerShell (lasts for that window)
```

## Configure (optional)

You don't need to. To change a default, create a `guardrails.json` yourself. Nothing creates it for you, and `guard.py` reads it on every call, so changes apply straight away:

- `~/.claude/guardrails.json`: just you, every project
- `<repo>/.claude/guardrails.json`: everyone in that repo (commit it). If both files exist, this one wins.

Put in only what you want to change:

```json
{
  "disable": ["git-discard"],
  "checks": [{"id": "force-push", "decision": "ask"}],
  "rules": [
    {"id": "docker-prune", "pattern": "\\bdocker\\s+(system|volume|image)\\s+prune\\b",
     "decision": "ask", "reason": "docker prune deletes images or volumes",
     "instead": "Show me what would be removed first."}
  ]
}
```

| Key | What it does |
|---|---|
| `disable` | Switch rules off by id |
| `checks` | Change `decision` (`deny`/`ask`), `reason` or `instead` of `force-push`, `rm-recursive`, `kubectl-prod` or `self-protect`. For kubectl with no `--context`, use `"no_context": {"decision": …}` |
| `rules` | Add your own: `id`, `pattern` (Python regex on the whole command, with `\` written as `\\`), `decision` (default `deny`), `reason`, `instead` |
| `protected_branches` | Branch regexes for `force-push`. This **replaces** the default list |
| `prod_context_pattern` | What counts as a prod kube context (default `prod\|prd\|live`) |
| `audit_log` | Log path, or `""` to turn logging off |
| `fail_open` | `true` = allow the call if the hook itself errors (default: block) |

**If the file is broken, the hook blocks every tool call** until you fix or delete it. After editing, run `--test` to check. On Windows, save it as UTF-8 **without a BOM**: VS Code does this by default. Don't use PowerShell 5.1's `Set-Content -Encoding utf8`, because it adds a BOM.

## Honest limits

- **A seatbelt, not a sandbox.** It reads the text of a command, so a `DROP TABLE` inside `cleanup.sql` slips past. Database grants, cloud IAM and branch protection are your real protection.
- **False positives are deliberate.** `echo "never DROP TABLE"` is denied. Disable or narrow the rule if it bothers you.
- An "ask" in a non-interactive `claude -p` run has nobody to answer it, so it acts like a deny.

## Contributing

- Tests: `python3 -m unittest discover -s hooks/guardrails/tests -v`
- **A new check in code** (for something a regex can't do):
  - Write a `check_*` function that returns a detail string or `None`.
  - Call it from `evaluate()` through `check_decision(cfg, "<id>", detail)`.
  - Add the id to `DEFAULT_CHECKS` and to `"checks"` in `rules.json`.
  - Add a test.
- Read `guard.py` (~420 lines) and `rules.json` before you install. That's the one non-lazy step.
