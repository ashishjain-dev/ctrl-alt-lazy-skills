---
name: write-tests
description: Write unit tests for a file or function using the project's existing test framework, then run them until they pass. Use when the user asks for tests, test coverage, or "is this tested?".
argument-hint: [file or function]
---

# Write tests

Write useful unit tests for $ARGUMENTS, in the style this repo already uses, and leave them passing.

If no file was given, ask which file to test, or offer the most recently changed source file (`git diff --name-only`).

## Steps

1. **Read the target.** Read $ARGUMENTS and the files it imports, so you know its real behaviour and dependencies.
2. **Match the repo.** Find the existing test setup before writing anything:
   - framework and runner (Jest, Vitest, pytest, JUnit, Go `testing`, etc.) from config files and existing tests
   - where tests live and how they are named (`*.test.ts`, `test_*.py`, `*Test.java`, `__tests__/`)
   - how existing tests mock dependencies and build fixtures
   Copy those conventions. Do not add a new framework or library unless the repo has none, and if so, ask first.
3. **Plan the cases.** For each public function or method, cover:
   - the happy path
   - edge cases: empty, zero, null/undefined, boundaries, very large inputs
   - error paths: invalid input, thrown exceptions, failed dependencies
   Skip trivial getters and code with no logic.
4. **Write the tests.**
   - one behaviour per test, named after what it checks ("rejects negative quantity")
   - Arrange, Act, Assert; no logic or loops in assertions
   - mock only external boundaries (network, database, clock, filesystem), not the code under test
   - deterministic: no real time, randomness or network
5. **Run them.** Run only the new test file with the repo's test command.
   - If a test fails because the test is wrong, fix the test.
   - If a test fails because the code looks wrong, do **not** change the source. Keep the test, mark it clearly (skip or `xfail` with a comment), and report the likely bug.
6. **Report** in this format:

```
Tests: <file>
- <n> written, <n> passing
- Covered: <short list>
- Not covered: <what and why>
- Possible bug: <only if found>
```

## Rules

- Never edit source code to make a test pass unless the user asks.
- Never delete or weaken existing tests.
- Keep the new test file focused on $ARGUMENTS.
