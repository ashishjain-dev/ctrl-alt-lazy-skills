---
name: summarize-changes
description: Summarize uncommitted git changes and suggest a commit message. Use when the user asks what changed, wants a summary of their diff, or needs a commit message.
---

# Summarize changes

You are helping a tired developer understand their own uncommitted work and write a commit message that is not "fix".

## Steps

1. Run `git status --short` to see which files changed, including untracked files.
2. Run `git diff` for unstaged changes and `git diff --staged` for staged changes.
3. Group the changes by **feature or intent**, not by file. One bullet per group, one line each.
4. Flag anything risky in its own section:
   - config, environment or secrets files
   - database migrations or schema changes
   - dependency or lockfile changes
   - deleted files or large deletions
   - leftover debug code (`console.log`, `print`, `TODO`, commented-out blocks)
5. Suggest **one** commit message:
   - Conventional Commits style (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`)
   - imperative mood, under 72 characters
   - if the changes clearly belong in separate commits, say so and suggest how to split them

## Output format

```
Changes
- <group>: <what changed> (<n> files)

Watch out
- <risky item, or "Nothing risky">

Commit message
<type>: <summary>
```

## Rules

- Do not commit, stage, or push anything unless the user explicitly asks.
- If there are no changes, say so in one line and stop.
- Keep the whole summary short enough to read in 20 seconds.
