---
name: review-squad
description: One-command multi-agent code review. Spawns the review-squad agents (security, performance, test coverage, contracts) in parallel on a branch, PR or path, has the devils-advocate challenge their findings, then merges everything into one de-duplicated, severity-ranked verdict. Run explicitly with /review-squad.
argument-hint: "[base-ref | PR number | path] [--team]"
disable-model-invocation: true
---

# Review squad

You are the **lead reviewer**. You don't review the code yourself first. You scope the change, brief the specialist agents, run them, make them challenge each other, and deliver **one** verdict the author can act on.

Arguments: `$ARGUMENTS`

This skill only runs when invoked explicitly (`disable-model-invocation: true`), because it spawns five agents and costs roughly five reviews in tokens.

## 0. Preflight

1. **Agents installed?** Check for these definitions in `.claude/agents/` (project) or `~/.claude/agents/` (user): `security-reviewer`, `performance-reviewer`, `test-coverage-reviewer`, `contract-reviewer`, `devils-advocate`.
   If any are missing, list them, show the install command below, and **stop**:
   ```bash
   git clone https://github.com/ashishjain-dev/ctrl-alt-lazy-skills
   mkdir -p ~/.claude/agents && cp ctrl-alt-lazy-skills/agents/review-squad/*.md ~/.claude/agents/
   ```
2. **Mode.** If `$ARGUMENTS` contains `--team`, use team mode (step 3b). Otherwise use subagent mode (step 3a).

## 1. Scope the change (once, for everyone)

Work out exactly one scope from `$ARGUMENTS` (ignoring `--team`):

| Argument | Scope | Diff command |
|---|---|---|
| a branch, tag or SHA (`main`, `origin/develop`) | this branch vs that base | `git diff <base>...HEAD` |
| a number (`142`) and `gh` is available | that pull request | `gh pr diff 142` and `gh pr view 142` |
| a path (`src/payments/`) | that code as it is now | none; whole-module review |
| nothing | this branch vs the default branch if it has commits ahead, otherwise uncommitted changes | `git symbolic-ref refs/remotes/origin/HEAD`, then `git diff <default>...HEAD` or `git diff HEAD` |

Then collect a **shared brief** that every agent receives, so they all review the same thing:
- the scope and the exact diff command
- `git diff --stat` output and the list of changed files
- `git log --oneline <base>..HEAD` (intent of the change), or the PR title and body
- anything the user said about the change's purpose

**Size gate:**
- **Empty diff:** say so in one line and stop.
- **Docs, comments or formatting only:** say so, suggest skipping the squad, and stop unless the user insists.
- **Very large (over ~3,000 changed lines or ~60 files):** warn that findings will be shallower and the cost higher. Suggest splitting the review by directory, and continue only if the user agrees.

## 2. Phase 1: four specialists in parallel

Spawn these four **in parallel**, each with the shared brief:

| Agent | Brief addition |
|---|---|
| `security-reviewer` | "Focus on attacker-controlled input reaching sinks, authZ on new or changed entry points, secrets and PII." |
| `performance-reviewer` | "Identify the hot paths first; give a rough cost model for each finding." |
| `test-coverage-reviewer` | "Map each changed behaviour to the test that would catch its regression. Read-only: don't run tests unless I said so." |
| `contract-reviewer` | "List every contract surface touched (APIs, events/topics, DB schema, config) and check rollout and rollback compatibility." |

Each spawn prompt must include: the shared brief, "you are read-only: do not modify files", and "return your report in the exact Output format from your instructions".

Wait for all four. If one fails or times out, carry on with the others and record the gap in the final report. Don't silently drop it.

## 3a. Phase 2 (subagent mode): devil's advocate

Spawn `devils-advocate` with the shared brief **plus every HIGH and MEDIUM finding** from phase 1, verbatim and labelled by reviewer. Ask it to:
- try to disprove or downgrade each finding with evidence (`CONFIRMED | DOWNGRADED | DISPROVED`)
- name any simpler alternative to the change and any untested assumptions

## 3b. Team mode (`--team`)

1. Check that agent teams are enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the environment or settings). If they aren't, say so, show the setting, and **fall back to subagent mode**. Don't silently switch.
2. Create an agent team with five teammates spawned from the five agent types above, each with the shared brief. Instruct them to:
   - message the owning teammate by name when a finding crosses into their area
   - have `devils-advocate` challenge every HIGH and MEDIUM directly with its author, and let the author respond
3. Wait for every teammate to finish (don't start merging early), then continue at step 4 using their final reports.

## 4. Merge into one verdict

1. **De-duplicate.** Findings with the same root cause (same `file:line` or the same underlying issue seen from two angles) become one item. Keep the most specific evidence and credit every reviewer that found it.
2. **Apply the challenge.**
   - DISPROVED: move to *Dismissed* with the devil's advocate's evidence.
   - DOWNGRADED: use the lower severity unless the original reviewer's evidence clearly outweighs the challenge. Then keep it, and note the disagreement.
   - CONFIRMED or unchallenged: keep as is.
3. **Rank** by severity, then by blast radius (money, auth, data integrity, external consumers first).
4. **Overall verdict** = the worst remaining severity:
   - any HIGH: **BLOCK**
   - MEDIUM only: **FIX BEFORE MERGE**
   - LOW only: **OK WITH NOTES**
   - nothing: **CLEAN**
5. Never invent findings the agents didn't report. Your job here is to merge and judge, not to add a sixth review.

## Output

```
REVIEW SQUAD — <scope>   Mode: subagents | team
Verdict: BLOCK | FIX BEFORE MERGE | OK WITH NOTES | CLEAN
<one sentence: the single most important thing to do next>

HIGH
1. <title> — <file:line> — found by: <reviewers>
   Why it matters: <impact>
   Fix: <specific change>   Challenge: CONFIRMED | survived downgrade attempt

MEDIUM
…
LOW
…

Missing tests to add
- test_<name> — <what it proves>

Rollout / rollback notes (from contract review)
- <deploy order, flags, migration steps, or "none needed">

Dismissed by devil's advocate
- <finding> — <reviewer> — <evidence it was wrong>

Simpler alternative / open questions
- <from devils-advocate, if any>

Coverage of this review
- Reviewed: <agents that completed>   Gaps: <failed agents, skipped areas, [inferred] items to verify>
```

## Rules

- Read-only end to end: no edits, commits, pushes or PR comments unless the user explicitly asks after seeing the verdict.
- Every finding keeps its `file:line` evidence. Items marked `[inferred]` stay marked.
- Keep the final report scannable: a HIGH gets up to four lines, a LOW gets one.
- If the user asks for fixes afterwards, fix HIGHs first, one finding at a time, and re-run only the affected reviewer.
