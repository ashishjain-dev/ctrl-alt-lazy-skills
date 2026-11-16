Babysit the pull request for the branch I'm on. Each run is one pass; keep it short and only act on what changed since the last pass.

How to check (GitHub, via the gh CLI):
- PR for this branch: `gh pr view --json number,url,headRefName,baseRefName`
- CI status: `gh pr checks`
- Why a job failed: `gh run view <run-id> --log-failed`
- Re-run a flaky job: `gh run rerun <run-id> --failed`
- Review comments: `gh pr view --comments`, plus inline review comments via `gh api repos/{owner}/{repo}/pulls/<number>/comments`
If this repo uses another platform (GitLab, Jenkins, Azure DevOps), use its CLI or MCP tools the same way.
If you can't reach the PR or CI (gh not installed, not logged in, no access, no PR for this branch), say so in one line and stop. Don't guess the CI state.

1. CI. Check the latest run for this PR. If it's green, say so in one line. If it's red:
   - read the failing job's log and find the first real error (not the cascade after it);
   - if it's a flaky or infrastructure failure (timeout, runner lost, network, rate limit), re-run that job once and say so; never re-run more than once per pass;
   - if it's a real failure caused by this branch, fix it in the smallest change that makes it pass, run the relevant tests locally first, then commit with a clear message and push;
   - if the failure is outside this branch (main is broken, a shared dependency, secrets, infra), don't touch it: report it with the log line and stop.
2. Review comments. Read comments added since the last pass.
   - Address the ones that ask for a concrete code change: make the change, reply on the thread with what you did and the commit.
   - For questions, design debates or anything you disagree with, don't change code: reply with your reasoning, or list them for me to answer.
   - Never resolve a thread someone else opened unless they asked you to.
3. Merge conflicts. If the branch conflicts with its base, rebase or merge only when the conflict is mechanical (imports, lockfile, formatting). If it touches logic on both sides, stop and show me the conflicting hunks.
4. Ticket. If the PR links a ticket and you have a tool that can reach the tracker (a CLI or MCP server), add one short status line to it when something changed this pass (CI fixed, comments addressed, waiting on review). Skip it if nothing changed or you can't reach the tracker.
5. Report. End every pass with at most 4 lines: CI state, what you changed (commit SHAs), what needs me, and "nothing to do" if that's the case.

Hard rules:
- Never force-push, never push to main or any protected branch, never merge the PR, never delete branches.
- Never disable, skip or delete a failing test to make CI pass; never lower coverage thresholds or edit CI config unless a review comment asks for exactly that.
- Never commit secrets or files outside this repo's working tree.
- If you're unsure whether a change is safe, don't make it: ask me in the report.
- When CI is green, there are no open review comments that need a code change, and there are no conflicts, say "PR is ready for a human" and stop changing things on later passes until something new happens.

Optional rule 5, from the reel: when everything is green, tell me I'm doing great. Keep it to one line.
