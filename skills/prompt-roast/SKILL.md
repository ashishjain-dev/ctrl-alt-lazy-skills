---
name: prompt-roast
description: Roast a vague coding prompt before Claude runs it, show what will break if executed as-is, and rewrite it into a scoped senior-engineer prompt with explicit file boundaries, invariants, and a verification test. Read-only — never edits code or runs the prompt. Use for "roast my prompt", "tighten this prompt", or before handing a risky task to Claude Code.
argument-hint: "<draft prompt> [--strict]"
---

# Prompt Roast

Audit a draft coding prompt **before** Claude touches a file. Most bad AI diffs are not model failures — they are underspecified prompts with no file boundary, no invariant to protect, and no proof of done.

Arguments: `$ARGUMENTS`

## 1. Capture the draft

- If `$ARGUMENTS` contains a prompt (ignoring `--strict`), audit that text verbatim.
- If no prompt is given, ask the user to paste the prompt they are about to run and stop. Do not invent one.
- Never execute the draft prompt, edit files, or run mutating commands.

## 2. Ground lightly in the repo (read-only)

Spend at most a quick pass (glob + targeted grep/read) to see if the prompt maps to real paths in the current repo:
- Likely target files or modules mentioned or implied by the prompt.
- Nearest existing test file and single-file test runner command (e.g. `pytest path`, `npm test -- file`, `go test ./pkg`).
- Adjacent contracts that could silently break (API schemas, DB migrations, auth/token formats, public types, event payloads).

If the repo does not contain a clear match, say so and keep `[fill in path/command]` placeholders instead of guessing filenames.

## 3. Audit against 5 production failure modes

Score the draft silently against each check and surface only the gaps that actually matter for this task:

1. **Blast radius (Scope):** Does it name which file(s) or module(s) to touch — and what is off-limits? Without a fence, a 5-line bug fix turns into a 12-file refactor.
2. **Invariants (Do not break):** Does it state contracts that must stay compatible — wire/JSON/token formats, DB schema, public signatures, idempotency, error semantics, latency/memory budgets?
3. **Verification oracle (Proof):** Does it require reproducing the bug in a failing test (or running a concrete benchmark/check) *before* editing? Without an oracle, the agent can weaken assertions or ship an unverified guess.
4. **Hidden decisions (Ambiguity):** What will the model silently guess if left unstated (edge cases, retry behavior, backward compatibility, rollout strategy)? Force a stop-and-ask gate on those.
5. **Context hygiene:** Is the prompt too thin ("fix it", "make it faster") or dumping noisy logs without isolating the entry point and first real error?

With `--strict` (prod-critical / schema / auth / distributed systems): also require explicit failure-mode handling, concurrency/idempotency guarantees, and rollback safety in the rewrite.

## 4. Output

Always use this exact structure:

```text
Roast
<One dry, honest sentence naming the laziest flaw in the prompt. Sarcastic, not cruel.>

What breaks if you run this as-is
- <Concrete failure mode tied to a missing boundary, invariant, or test — max 3 bullets>

Senior rewrite (paste-ready)
<Ready-to-run prompt using the 4 compact blocks below:>
- Task: <one-sentence outcome>
- Scope: <exact file(s)/module(s) to touch; explicitly state what NOT to touch>
- Do not break: <contracts, schemas, public interfaces, or behavior invariants>
- Verify: <write failing test first / exact command to run; stop and report if blocked>

Answer before running
- <At most 2 blocking unknowns that would force a guess — or "none">
```

## Rules

- **Strictly read-only.** Never apply the rewritten prompt, edit files, or run destructive commands.
- **No beginner fluff.** Never tell the user to "be polite", "assign a persona", or "give more context" without naming the exact missing file, invariant, or test.
- **Match the task size.** A genuine one-line typo fix does not need a 30-line spec — if the draft is already tight and scoped, say "Clean prompt. Ship it." and stop.
- **Evidence over guesses.** Only cite files, symbols, or test commands you actually observed in the repo; mark unverified assumptions `[inferred]` or use `[fill in]`.
- Keep the entire response scannable in under 20 seconds so the user actually uses it before hitting enter.
