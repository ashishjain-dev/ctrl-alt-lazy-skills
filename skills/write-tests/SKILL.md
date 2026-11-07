---
name: write-tests
description: Write high-value tests for a file, class or module the way a senior engineer would. Matches the repo's existing framework and conventions, picks the right test level, covers invariants, edge cases, failure modes, concurrency and idempotency, pins legacy behaviour with characterization tests, and runs the tests until they are green and non-flaky. Use when asked for tests, coverage, "is this tested?", or before refactoring risky code.
argument-hint: "[path | Class | Class#method] [--characterize]"
---

# Write tests (senior mode)

Write the tests a strong reviewer would ask for on $ARGUMENTS: few, sharp, and guarding real behaviour. Optimise for **defects caught per line of test**, not coverage percentage.

No target given: offer the most recently changed source files and ask which one. Use uncommitted changes first (`git diff --name-only HEAD` plus untracked files from `git status --porcelain`), then the last commit (`git show --name-only --format= HEAD`, which also works in a repo with a single commit).

## 1. Understand before writing

- Read the target and its collaborators: inputs, outputs, side effects, invariants, error contract, and who calls it (`grep` for usages).
- Read the 2-3 nearest existing test files. Copy their framework, runner, layout, naming, fixture/builder style, mocking approach and assertion library. Never introduce a new framework or library without asking.
- Find the exact command that runs one test file in this repo (package scripts, Makefile, Gradle/Maven, tox/pytest config, CI config).
- Write down the behaviours that matter, as the business would describe them, before writing any code.

## 2. Choose the right level

| Behaviour | Test level |
|---|---|
| Pure logic, calculations, mapping, validation | Unit tests, no mocks |
| Code that talks to DB, queue, cache, filesystem | Integration test against a real or containerised dependency, if the repo already does this (Testcontainers, embedded broker, in-memory DB). Otherwise unit test with a fake at the port boundary and say what is untested. |
| HTTP/gRPC handlers, message producers and consumers | Contract-style tests on the wire format: status codes, error shapes, schema, headers |
| Legacy or untested code you are about to change | Characterization tests first (see 4) |

Mock only at architectural boundaries you own (ports, adapters, clients). Never mock the unit under test, value objects, or types you don't own. Prefer fakes over deep mock chains. If a deep mock chain seems necessary, report it as a design smell.

## 3. Cases that earn their place

For each public behaviour, pick what applies:

- **Happy path**, asserted on observable outcome, not on internal calls.
- **Boundaries**: empty, single, max size, zero and negative, off-by-one, Unicode, time zones and DST, currency rounding and precision.
- **Invariants and properties**: if the repo has a property-based library (Hypothesis, fast-check, jqwik, QuickCheck), use it for round-trips (`decode(encode(x)) == x`), idempotence (`f(f(x)) == f(x)`), ordering and conservation rules (totals balance).
- **Failure modes**: invalid input, dependency timeout or error, partial failure, retries exhausted. Assert the error type and message contract **and** that no partial side effects remain.
- **Idempotency and duplicates**: processing the same message or request twice for consumers, webhooks and payment-like flows.
- **Concurrency**, where the code is concurrent: parallel calls on shared state, lost updates, ordering assumptions. Use the framework's deterministic tools (fake executors, virtual time) rather than `sleep`.
- **Regression**: if the target has a known bug or a recent fix in `git log`, pin it with a test named after the behaviour.

Skip trivial getters, pass-through delegation and framework wiring.

## 4. Characterization mode

Use this when `--characterize` is passed, or when the code is legacy and untested.

- Goal: pin **current** behaviour, including odd behaviour, so a refactor can't change it silently.
- Record actual outputs as expectations. Name suspicious ones `currently_<behaviour>` and add a comment explaining why they look wrong.
- Do not "fix" expectations to what the code should do. List suspected bugs separately.

## 5. Write them well

- One behaviour per test. Names read as specifications: `rejects_transfer_when_balance_insufficient`, `retries_then_dead_letters_after_3_failures`.
- Arrange / Act / Assert with no logic in tests. Use table-driven or parameterised tests for input variations.
- Deterministic: inject clock, random seed, UUIDs and IDs. No real network, no wall-clock sleeps, no test-order dependence, no shared mutable fixtures.
- Strong assertions: assert exact values and complete objects, not `isNotNull` or "doesn't throw". Ask yourself: would this test fail if the key line were deleted or a `<` became `<=`? If not, strengthen it.
- Build test data with the repo's builders or factories, keeping only the fields relevant to each test visible.

## 6. Run until green and stable

1. Run only the new test file with the repo's command.
2. Test wrong: fix the test. Code wrong: do **not** change production code. Mark the test skipped/xfail with a clear comment and report the bug with a minimal reproduction.
3. Run the file a second time (randomised order, if the runner supports it) to catch flakiness.
4. If the repo has coverage tooling, report coverage of the target before and after. If it has mutation testing (PIT, Stryker, mutmut), suggest the exact command; don't run it unless asked.

## Output format

```
Tests for <target>  →  <test file>
Level: <unit | integration | contract | characterization>
Result: <n> passing, <n> skipped (bugs), ran twice: stable

Covered
- <behaviour>

Deliberately not covered
- <behaviour> — <why, and what test would cover it>

Suspected bugs
- <file:line> — <behaviour> — <minimal repro>

Design notes (only if testing exposed them)
- <e.g. hidden time dependency in X; extract a Clock port>
```

## Rules

- Never modify production code, delete existing tests or weaken assertions unless explicitly asked.
- Never add dependencies or change build or CI config without asking.
- Keep secrets, real customer data and PII out of fixtures; use obviously fake data.
- If the code is untestable without a refactor, propose the smallest seam (inject the dependency, extract a pure function) and ask before doing it.
