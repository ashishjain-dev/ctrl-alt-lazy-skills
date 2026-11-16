# pr-babysitter (`loop.md`)

From the [@ctrl.alt.lazy](https://instagram.com/ctrl.alt.lazy) reel **/loop Part 2: "Day 400"**. Write your PR routine once, then type a bare `/loop` and Claude Code follows it on every pass: check CI, fix what's yours, answer review comments, keep the ticket current, and tell you what needs a human.

## Before you start

loop.md is only instructions. Claude follows them with the tools your Claude Code session already has, so set these up first:

1. **GitHub CLI, logged in.** Install [`gh`](https://cli.github.com/) and run `gh auth login`. Check with `gh pr checks` on your PR branch. Without it Claude can't see CI or review comments, and the loop will say so and stop.
2. **Let the loop run without asking every time.** Claude Code asks before running commands. Allow the read and re-run commands this loop uses (`gh pr view`, `gh pr checks`, `gh run view`, `gh run rerun`, `gh api`) and `git push` in your [permission settings](https://code.claude.com/docs/en/settings), or each pass will pause for your approval. Keep force-push and merge un-allowed.
3. **Other platforms.** GitLab (`glab`), Jenkins, Azure DevOps or Jira need their own CLI or MCP server. The ticket step is skipped if Claude can't reach your tracker.

## Install

Project-level (recommended, shareable with your team):

```bash
mkdir -p .claude
curl -o .claude/loop.md \
  https://raw.githubusercontent.com/ashishjain-dev/ctrl-alt-lazy-skills/main/loops/pr-babysitter/loop.md
```

Or user-level, for every project that doesn't define its own: save it as `~/.claude/loop.md`.

Then, in Claude Code on your PR branch:

```
/loop        # Claude picks the wait between passes
/loop 10m    # or a fixed interval
```

## How loop.md behaves (from the Claude Code docs)

- A bare `/loop` (or `/loop <interval>`) runs your `loop.md` instead of the built-in maintenance prompt.
- `.claude/loop.md` (project) takes precedence over `~/.claude/loop.md` (user).
- It's one default prompt, not a list of tasks. If you type a prompt after `/loop`, the file is ignored.
- Edits take effect on the next pass, so you can tune it while a loop is running. Keep it well under 25,000 bytes; longer files are truncated.
- Loops are session-scoped: they only run while that Claude Code session is open and idle, and expire after 7 days.
- On Bedrock, Vertex AI and Microsoft Foundry, `loop.md` is not read and a bare `/loop` prints usage.

Docs: https://code.claude.com/docs/en/scheduled-tasks

## Safety

The file tells Claude never to force-push, push to protected branches, merge, skip tests or touch CI config, and to stop and ask when a fix isn't clearly its own. That's guidance, not enforcement. For hard limits, pair it with the [`guardrails`](../../hooks/guardrails/) hook and your branch protection rules.

Customise it: change the steps to your workflow (your CI tool, your ticket system, your review norms). Keep the hard rules.
