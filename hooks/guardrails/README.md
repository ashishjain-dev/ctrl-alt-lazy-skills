# guardrails: stop Claude before it runs the command that gets you fired

A Claude Code `PreToolUse` hook. Before Claude runs a shell command or edits a file, Claude Code hands the call to `guard.py`. If it matches a rule, the call is **denied** (it never runs; Claude reads why and changes its plan) or you get an **ask** prompt with the reason, even in auto-accept modes.

```
Claude: psql $DATABASE_URL -c "DROP TABLE payments;"
Hook:   guardrails [sql-drop]: destructive SQL (DROP or TRUNCATE).
        Instead: write it as a reviewed migration with a backup or rollback plan, and let a human run it.
Claude: Blocked by a hook. Here's the migration instead, for you to review…
```

From reel #11 on [@ctrl.alt.lazy](https://instagram.com/ctrl.alt.lazy).

## Install

```bash
git clone https://github.com/ashishjain-dev/ctrl-alt-lazy-skills
cd ctrl-alt-lazy-skills
python3 hooks/install.py guardrails     # same as: python3 hooks/guardrails/install.py
```

- Copies `guard.py` and `rules.json` to `~/.claude/hooks/guardrails/` and registers the hook in `~/.claude/settings.json` (all projects). Your existing settings and hooks are kept, a timestamped backup is made first, and running it again just updates it.
- `--fail-closed` also adds `"onFailure": "block"`, so a crashed or timed-out hook blocks the call instead of letting it through (needs Claude Code v2.1.295+).
- `--dry-run` prints the resulting settings without changing anything. `--uninstall` removes it.
- Restart open Claude Code sessions, then check with `/hooks`. The shared installer is explained in [hooks/README.md](../README.md).

Needs Python 3.8+. No other dependencies (no `jq`).

## What it guards

All 12 rules are listed in [`rules.json`](rules.json), with their decision, reason and `instead` message. There are two kinds:

- **`rules`**: a regex matched against the whole command. Everything about the rule lives in `rules.json`.
- **`checks`**: detection needs code (resolving paths, reading the current git branch), so it lives in `guard.py`. The decision, reason and `instead` still come from `rules.json`.

| Rule | In `rules.json` | Catches | Decision |
|---|---|---|---|
| `sql-drop` | `rules` | `DROP TABLE/DATABASE/SCHEMA…`, `TRUNCATE` (any client: psql, mysql, sqlcmd, scripts with `-c`/`-e`) | deny |
| `sql-delete-no-where` | `rules` | `DELETE FROM x;` with no `WHERE` | deny |
| `db-drop-tools` | `rules` | `dropdb`, `prisma migrate reset`, `rails db:drop/reset`, `manage.py flush`, `flyway clean`, `redis-cli FLUSHALL`, `dropDatabase` | deny |
| `terraform-destroy` | `rules` | `terraform/tofu destroy`, `apply -auto-approve` | deny |
| `git-discard` | `rules` | `git reset --hard`, `git clean -f…`, `git checkout -- .`, `git stash drop/clear` | ask |
| `pipe-to-shell` | `rules` | `curl … \| bash` | ask |
| `disk-wipe` | `rules` | `mkfs`, `dd of=/dev/…`, `chmod -R 777 /` | deny |
| `self-protect-bash` | `rules` | A shell command (`>`, `tee`, `sed -i`, `mv`, `cp`, scripts…) that touches the guardrails files or `.claude/settings*.json` | ask |
| `force-push` | `checks` | `--force`, `--force-with-lease`, `-f` or `+ref` to protected branches (`main`, `master`, `develop`, `release/*`, `prod`), including a bare `git push -f` while on one. `--force-with-lease` on your own branch is fine | deny |
| `rm-recursive` | `checks` | `rm -r` on `/`, `~`, `$HOME`, `.`, `..`, an unexpanded `$VAR`, the project root, or anything outside the project (temp dirs are allowed) | deny |
| `kubectl-prod` | `checks` | `kubectl delete/drain/patch/scale/rollout` on a context matching `prod|prd|live` (deny); `kubectl delete` with no explicit `--context` (ask, set under `no_context`) | deny / ask |
| `self-protect` | `checks` | Claude editing `~/.claude/settings.json`, `.claude/settings*.json`, or the guardrails files and config with Edit/Write | ask |

Commands are checked as a whole **and** split on `;`, `&&`, `||`, `|`, so `cd src && rm -rf /` is caught. `sudo`, `env`, and `VAR=value` prefixes are stripped before matching.

## Why exit codes matter (the bug in most hand-written guards)

| Hook result | What happens |
|---|---|
| exit 0 + JSON `"permissionDecision": "deny"` | Blocked. This is what `guard.py` does |
| exit 2 | Blocked; stderr is the reason |
| **exit 1** | **Not blocked.** It's a non-blocking error and the command runs anyway |
| timeout or crash | Not blocked, unless the hook has `"onFailure": "block"` |

`guard.py` fails closed: on an internal error it exits 2. Set `"fail_open": true` if you'd rather it never get in the way.

## Configure

**You don't need to configure anything.** Out of the box the hook uses the defaults in `rules.json`. Don't edit that file: the installer overwrites it on every update.

To change something, create an **override file** yourself. The installer never creates one. It holds only the settings you want to change:

| File | Applies to | Create it when |
|---|---|---|
| `~/.claude/guardrails.json` (Windows: `C:\Users\<you>\.claude\guardrails.json`) | you, in every project | a default gets in your way |
| `<repo>/.claude/guardrails.json` | everyone who works in that repo (commit it) | a team or repo needs different rules |

Both files are optional and you can have either, both or neither. If both exist, the repo file is read last and wins.

### Start small: one change per file

Each example below is a complete `guardrails.json`. Put in only the keys you need.

Turn a rule off (any of the 12 ids in the [table above](#what-it-guards)):
```json
{ "disable": ["git-discard"] }
```

Make a force-push to a protected branch prompt you instead of being blocked:
```json
{ "checks": [{"id": "force-push", "decision": "ask"}] }
```

Protect more branches (this **replaces** the default list, so repeat the ones you want to keep):
```json
{ "protected_branches": ["main", "master", "release/.*", "hotfix/.*"] }
```

Add your own rule:
```json
{ "rules": [{"id": "no-publish", "pattern": "\\bnpm\\s+publish\\b", "decision": "ask",
             "reason": "publishing a package", "instead": "Bump the version in a PR first."}] }
```

Then check the result without starting Claude. Run it from inside the repo so the repo file is picked up:
```bash
python3 ~/.claude/hooks/guardrails/guard.py --test 'git push --force origin main'
```

On Windows, write the file as UTF-8 (in PowerShell: `Set-Content -Encoding utf8`). If the hook can't read an override file, it blocks every tool call until you fix or delete the file.

### Every key

| Key | What it does | If both files set it |
|---|---|---|
| `disable` | Rule ids to switch off | Combined: off in either file means off |
| `rules` | Extra regex rules ([fields below](#add-a-rule-no-code)) | Combined: all are added |
| `checks` | Change the decision or message of a code check ([below](#change-a-checks-decision-or-message)) | Merged by id; the repo file wins per field |
| `protected_branches` | Branch regexes that `force-push` protects | Replaced: the repo file wins |
| `prod_context_pattern` | Regex for kube contexts that count as prod (default `prod\|prd\|live`) | Replaced |
| `fail_open` | `true` = on an internal error, allow the call instead of blocking it | Replaced |
| `audit_log` | Path of the audit log, or `""` to turn it off | Replaced |

### Change a check's decision or message

`"checks"` entries are matched by `id` against the four code checks (`force-push`, `rm-recursive`, `kubectl-prod`, `self-protect`). Only the fields you give are changed:

- `decision`: `"deny"` or `"ask"`. Anything else is ignored with a warning, and the built-in decision stays. To switch a check off, put its id in `"disable"`.
- `reason`: shown to Claude. The specific target (the branch, the path, the kube context) is appended after a colon.
- `instead`: what Claude should do instead.
- `no_context`: `kubectl-prod` only. It holds the `decision`, `reason` and `instead` used when `kubectl delete` has no `--context`.

For example:
```json
{
  "checks": [
    {"id": "force-push", "decision": "ask"},
    {"id": "rm-recursive", "instead": "Run scripts/clean.sh instead."},
    {"id": "kubectl-prod", "no_context": {"decision": "deny"}}
  ]
}
```
In this file:
- A force-push to `main` prompts you instead of being blocked.
- `rm -rf` outside the project is still denied, but Claude is told to run your cleanup script.
- `kubectl delete` with no `--context` is blocked instead of asking.

```bash
python3 ~/.claude/hooks/guardrails/guard.py --test 'git push --force origin main'
# ASK    [force-push] force-push to a protected branch: 'main'
#        Instead: Push to a branch and open a PR. Use --force-with-lease on your own branch.
```

An id that isn't a check (a regex rule such as `sql-drop`) is ignored with a warning. To change a regex rule, disable it and add your own under `"rules"`.

### Add a rule (no code)

Add an entry to `"rules"` in `~/.claude/guardrails.json` or `<repo>/.claude/guardrails.json`:

| Field | Meaning |
|---|---|
| `id` | Short name, shown to Claude and in the audit log. Reuse a built-in id in `"disable"` to switch that one off |
| `pattern` | Python regex, matched case-insensitively against the **whole** Bash command (chained commands included) |
| `decision` | `"deny"` (never runs) or `"ask"` (you confirm). Default `deny` |
| `reason` | Why it's dangerous. Claude reads this |
| `instead` | What Claude should do instead. Claude usually follows it |

Then test it without starting Claude (quote the command so your shell doesn't split it):

```bash
python3 ~/.claude/hooks/guardrails/guard.py --test 'npm publish'
# ASK    [no-publish] publishing a package
#        Instead: Bump the version in a PR first.
python3 ~/.claude/hooks/guardrails/guard.py --test 'git status'
# ALLOW  no rule matched (Claude Code's normal permission flow applies)
python3 ~/.claude/hooks/guardrails/guard.py --test-edit ~/.claude/settings.json
```

Run it from inside a repo to pick up that repo's `.claude/guardrails.json`.

### Add a check in code

Some checks don't fit a regex (resolving paths, reading the current git branch). Write a function in `guard.py` that takes the split command (`argv`) and returns a detail string (what it matched) or `None`. Call it from `evaluate()` next to `check_rm` and `check_git`, and turn the match into a decision with `check_decision(cfg, "<id>", detail)`. Give it an entry in `DEFAULT_CHECKS` and in the `"checks"` list in `rules.json`, so it can be configured and disabled by id. Add a test in `tests/test_guard.py`. Then re-run `python3 hooks/install.py guardrails` to copy it into place.

### Turn it off

Turn it off for one session by starting Claude Code with `CLAUDE_GUARDRAILS=off claude`. Claude can't do this from inside a session: the variable must be set in the environment that launches Claude Code, not in a command Claude runs.

## Audit log

Every deny and ask is appended to `~/.claude/guardrails/audit.jsonl` (timestamp, session, cwd, rule, decision, command). Passwords in connection strings and `password=`/`token=`-style values are masked. Change the path with `"audit_log"` or set it to `""` to disable.

```bash
tail -5 ~/.claude/guardrails/audit.jsonl
```

## Honest limits

- **It's a seatbelt, not a sandbox.** It matches the text of a command. A `DROP TABLE` inside `cleanup.sql`, or a command assembled at runtime, can slip past. Least-privilege database grants, cloud IAM, and server-side branch protection are still your real protection. This catches the 2 AM mistake, not a determined attacker.
- **False positives are deliberate.** `echo "never DROP TABLE"` is denied. Prefer an extra prompt over a dropped table; disable or narrow a rule in `guardrails.json` if it bothers you.
- An "ask" in a non-interactive `claude -p` run has nobody to answer it, so it acts like a deny.

## Test it

```bash
python3 -m unittest discover -s hooks/guardrails/tests -v
```

Want a different kind of hook (auto-format after edits, a ping when Claude is done)? See [Add your own hook](../README.md#add-your-own-hook).

## Read before you install

It's ~420 lines of Python. Read `guard.py` and `rules.json` first: that's the one non-lazy step.
