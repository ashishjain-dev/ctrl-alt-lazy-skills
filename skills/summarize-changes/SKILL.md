---
name: summarize-changes
description: Review a change set like a senior reviewer before it ships. Summarizes intent, flags breaking changes and production risk (API contracts, schema and data migrations, concurrency, security, config, observability), proposes commit splits and a Conventional Commit message, and drafts a PR description with rollout and rollback notes. Use for "what did I change", commit messages, PR descriptions, or pre-merge self-review.
argument-hint: "[base-ref, default: uncommitted changes]"
---

# Summarize changes (senior review mode)

Give a reviewer-grade read of a change set in under a minute: what it does, what can break in production, and how to ship it safely. Be specific and evidence-based: cite `file:line` for every risk. No praise, no filler.

## 1. Scope the diff

- No argument: uncommitted work. Run `git status --porcelain=v1`, `git diff --stat`, `git diff`, `git diff --staged`.
- With an argument (`main`, `origin/develop`, a SHA): branch review. Run `git diff --stat $ARGUMENTS...HEAD`, `git diff $ARGUMENTS...HEAD`, and `git log --oneline $ARGUMENTS..HEAD`.
- For a large diff, start from `--stat`, then read the riskiest files in full rather than skimming everything.
- Treat lockfiles, generated code, snapshots and vendored files as one line each ("lockfile updated: 3 direct deps changed"), and still name any **direct** dependency or major-version change.

## 2. Group by intent, not by file

One line per logical change: what changed and **why it matters** (behaviour, not mechanics). Mark each group as `feature`, `fix`, `refactor` (claimed behaviour-neutral), `perf`, `infra`, `test`, or `docs`.

If a group claims to be a refactor but changes behaviour (different branches, defaults, error handling, ordering), flag it. That is the most common hidden regression.

## 3. Production risk review

Check every item below that applies, and report only real findings with `file:line`.

**Contracts and compatibility**
- Public API, REST/gRPC/GraphQL, event or message schemas: removed or renamed fields, changed types, tightened validation, new required fields, changed status codes or error shapes. State whether old clients or consumers still work.
- Serialization: field order, enum additions consumers may not handle, nullability, date and number formats.
- Library or module public interfaces: signature changes, changed exceptions, changed default behaviour.

**Data and schema**
- Migrations: locking or long-running on big tables, non-null columns without defaults, renames or drops that break the currently running version during a rolling deploy. Is it expand/contract safe?
- Backfills, data rewrites, irreversible operations. Is there a down path?
- Changes to keys, partitioning or indexes, and their effect on hot queries.

**Runtime behaviour**
- Concurrency: shared mutable state, lock ordering, transaction boundaries and isolation, race windows, async error handling.
- Idempotency and retries: duplicate processing, at-least-once consumers, retry storms, missing timeouts or backoff.
- Performance: N+1 queries, unbounded loops or collections, missing pagination, sync I/O on hot paths, cache invalidation.
- Resource handling: connections, file handles, threads, memory growth.

**Security**
- AuthN/AuthZ checks added, removed or bypassed; trust boundaries; input validation; injection; SSRF; deserialization.
- Secrets, tokens or PII in code, config, logs, errors or test fixtures.
- New dependencies: maintained? Licence acceptable? Pulled from a trusted source?

**Operability**
- Config, env vars and feature flags: new keys without defaults, default flips, per-environment differences.
- Observability: logs (levels, PII), metrics, traces and alerts added or lost for the new paths.
- Leftovers: debug logging, commented-out code, TODOs without tickets, disabled or skipped tests.

**Tests**
- Which changed behaviour has no test? Name the specific case, not "add more tests".

## 4. Commit hygiene

- If the change set mixes unrelated intents (refactor + feature, formatting + logic), propose a split, listing the files or hunks for each commit in a sensible order.
- Suggest a Conventional Commit message: `type(scope): summary`, imperative, 72 characters or fewer, with a body explaining **why** when it isn't obvious. Add a `BREAKING CHANGE:` footer when any contract above breaks.

## 5. PR description

Draft one that a reviewer and an on-call engineer can both use:
- Context: why this change
- What changed (3-6 bullets)
- Risk and blast radius: which services, consumers, data
- Rollout: flag, migration order, deploy sequence across services
- Rollback: exact steps, and whether data changes make rollback unsafe
- How to verify in staging or production

## Output format

```
Summary
<one sentence: what this change does and why>

Changes
- [feature] <behavioural change> (<files>)

Risks  (highest first; "None found" if clean)
- HIGH   <risk> — <file:line> — <why it breaks, who it affects, suggested fix>
- MEDIUM ...
- LOW    ...

Untested behaviour
- <specific case>

Commits
<split proposal, or "Single commit is fine">
<type(scope): summary>

PR description
<draft>
```

## Rules

- Read-only. Never stage, commit, push, rebase or modify files unless explicitly asked.
- Every risk needs evidence from the diff. If you are inferring (for example, a consumer you cannot see), say so and state what to check.
- Prioritise by blast radius, not by count. Three precise HIGH findings beat twenty style nits; skip style unless it hides a bug.
- No changes: say so in one line and stop.
