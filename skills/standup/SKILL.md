---
name: standup
description: Write today's standup update (Yesterday / Today / Blockers) from what you actually did, using git history, your pull requests and CI status since your last working day. Groups work by outcome, flags real blockers, and never inflates a quiet day. Use for "write my standup", "what did I do yesterday", or daily status updates.
argument-hint: "[repo paths...] [--since <date>] [--slack]"
---

# Standup

Write the user's standup update from **evidence**, not memory. It must take 20 seconds to read out loud and survive a follow-up question from a sharp manager.

Arguments: `$ARGUMENTS`

## 1. Work out the time window

- `--since <date>` given: use it.
- Otherwise use the **last working day**: Monday covers Friday, Saturday and Sunday. Any other weekday covers the previous day. Start the window at 00:00 local time of that day.
- Say the window you used in one line at the top, so the user can sanity-check it.

## 2. Collect evidence (read-only)

Repos: the paths in `$ARGUMENTS`, or the current repo if none are given. For each repo:

1. **Who is "me"?** `git config user.email` (fall back to `user.name`). If neither is set, ask.
2. **Commits:** `git log --all --no-merges --author="<email>" --since="<window start>" --pretty=format:'%h|%ad|%s' --date=iso`
3. **Pull requests** (only if `gh` is installed and authenticated; otherwise skip and say so):
   - Open: `gh pr list --author "@me" --state open --json number,title,createdAt,updatedAt,isDraft,reviewDecision,mergeable,statusCheckRollup,reviewRequests,url`
   - Merged in the window: `gh pr list --author "@me" --state merged --search "merged:>=<YYYY-MM-DD>" --json number,title,mergedAt,url`
   - Reviews you were asked for: `gh pr list --search "review-requested:@me" --state open --json number,title,createdAt,url`
4. **Uncommitted work in progress:** `git status --short` and the current branch name (`git branch --show-current`).

Never run commands that change anything: no fetch with prune, no checkout, no commit, no push, no PR comments.

## 3. Turn evidence into outcomes

- **Group by outcome, not by commit.** Five commits fixing one bug become one line: "Fixed login timeout on slow networks (PR #142, merged)". Use PR titles and commit messages to infer the outcome, and keep to what the evidence supports.
- **Link the proof:** PR number or short SHA in brackets on each line, so anyone can check.
- **Today** comes from open PRs, the current branch, uncommitted work, and anything the user mentions. If there's no signal, write "Today: (tell me your plan)" rather than inventing one.
- **Blockers** are real, evidenced problems only:
  - an open PR with no approving review for more than 24 hours, or with `reviewDecision: CHANGES_REQUESTED`
  - failing or pending checks in `statusCheckRollup`
  - `mergeable: CONFLICTING`
  - review requests waiting on the user (they block someone else, so mention them too)
  If there are none, write "Blockers: none".

## 4. Honest mode (always on)

- **Never inflate.** A day with one commit "fix typo" is reported as exactly that.
- If the user asks you to "make it sound bigger", decline politely and offer something useful instead: mention context the evidence supports (reviews done, investigations visible in branch names or WIP), or ask what non-code work happened (meetings, design, debugging, helping teammates) and include it **only** if they tell you.
- Don't pad with filler ("worked on various tasks", "continued progress").

## 5. Output

Default (spoken standup):
```
Standup — <window, e.g. Fri 7 Nov → now>

Yesterday
- <outcome> (<PR #/sha>)

Today
- <plan> (<PR #/branch>)

Blockers
- <blocker with evidence and who can unblock> | none
```

With `--slack`: the same content as one compact message with bold section labels and no code block, ready to paste.

Keep the whole update under about 8 lines. If there's more, keep the three most important outcomes and add "+N smaller changes".

## Rules

- Read-only. Never modify the repo or post anywhere.
- Every line is backed by evidence (commit, PR or CI). Anything inferred is marked "(probably)".
- No names of reviewers or teammates unless they appear in the PR data and naming them is needed to unblock.
- If the window has no activity at all, say so in one line and ask what they worked on.
