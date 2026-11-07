# Review squad (subagents and agent-team teammates)

Featured in reel #06 (what agents are) and reel #07 (*"AI reviewers that argue, so you don't have to."*).

Five read-only reviewers that share one severity scale (HIGH / MEDIUM / LOW) and one report shape, so a lead session can merge their findings without translation:

| Agent | Looks for |
|---|---|
| [`security-reviewer`](security-reviewer.md) | AuthN/AuthZ, injection, SSRF, secrets and PII, crypto, dependencies |
| [`performance-reviewer`](performance-reviewer.md) | N+1, unbounded work, blocking I/O, locks, memory, retry storms, caching |
| [`test-coverage-reviewer`](test-coverage-reviewer.md) | Changed behaviour → the test that would catch its regression; weak and flaky tests |
| [`contract-reviewer`](contract-reviewer.md) | Breaking API, event (Kafka/queue), DB and config contracts; rollout and rollback safety |
| [`devils-advocate`](devils-advocate.md) | Simpler alternatives, untested assumptions, and disproving the others' findings |

Each one cites `file:line`, marks guesses as **[inferred]**, and ends with a verdict: `BLOCK | FIX BEFORE MERGE | OK WITH NOTES | CLEAN`.

## Install

```bash
git clone https://github.com/jainashish1691/ctrl-alt-lazy-skills
mkdir -p ~/.claude/agents
cp ctrl-alt-lazy-skills/agents/review-squad/*.md ~/.claude/agents/     # all your projects
# or, to share with your team: copy into <repo>/.claude/agents/ and commit
```

Claude Code picks up edits within a few seconds. If `~/.claude/agents/` didn't exist when your session started, restart Claude Code once.

## Use 1: as subagents (works today, cheapest)

Each reviewer runs in its own context and reports back to your session:

```text
Run the security-reviewer, performance-reviewer and contract-reviewer
subagents in parallel on `git diff main...HEAD`, then merge their findings
into one list ordered by severity, with duplicates removed.
```

You can also call one directly: `@agent-contract-reviewer review the changes to the orders event schema`.

## Use 2: as an agent team (experimental, the reviewers talk to each other)

Agent teams are off by default. Enable them in `~/.claude/settings.json`:

```json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```

Then ask your session to act as lead:

```text
Create an agent team to review this branch against main. Spawn teammates
using the security-reviewer, performance-reviewer, test-coverage-reviewer,
contract-reviewer and devils-advocate agent types. Have them message each
other when a finding crosses into another's area, and have the
devils-advocate try to disprove every HIGH. Wait for all of them, then give
me one merged verdict.
```

For a bug with an unclear cause, use a debate instead:

```text
Spawn 4 teammates, each owning one hypothesis for <bug>, plus the
devils-advocate. Have them try to disprove each other's theories with
evidence. Report the hypothesis that survives and the experiment that
confirms it.
```

## Use 3: separate sessions messaging each other (built in, no setup)

From Claude Code v2.1.224 (v2.1.234 on native Windows), your separate sessions on the same machine can message each other. Name them so they're easy to target:

```text
/rename api-worker                 # in the API session
/rename web-worker                 # in the frontend session

Let @web-worker know the /orders response now includes currency_code
Tell me when the migration session finishes
/list-agents                       # see which sessions this one can reach (alias: /peers)
```

## Safe settings

```json
{
  "isolatePeerMachines": true,
  "crossSessionInbound": "hold"
}
```

- `isolatePeerMachines: true` asks for your approval before any message leaves this machine (to cloud or Remote Control sessions).
- `crossSessionInbound` controls incoming messages: `accept`, `hold` (shows a notice and waits for you), or `refuse`. The default already holds messages in sessions that bypass permission prompts.
- Messages from another session can never approve a permission prompt or change your config. Each session's own permissions still apply.

## Costs and limits (read before you go wild)

- **Tokens:** every teammate is a full Claude session, so a five-person squad costs roughly five reviews. Use subagents (Use 1) for routine PRs and teams for risky ones.
- **Experimental:** `/resume` and `/rewind` don't bring back in-process teammates. There's one team per session and no nested teams.
- **"Read-only" means no Write or Edit tools.** Bash is still available for `git diff` and friends, and your normal permission prompts still guard it. Keep auto-approve rules tight if you want a hard guarantee.
- **Same-machine messaging** goes over a local socket, never through Anthropic servers. Messages to other machines or cloud sessions go through Remote Control.
