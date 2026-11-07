# Ctrl Alt Lazy Skills ⌨️😴

> If it takes 5 mins, I'll spend 2 hrs automating it.

Production-grade [Claude Code skills](https://code.claude.com/docs/en/skills) from the **[@ctrl.alt.lazy](https://instagram.com/ctrl.alt.lazy)** reels. Each reel shows the idea in 30 seconds; the full `SKILL.md` lives here.

Written for senior engineers and architects: every skill matches your repo's existing conventions, reasons about production risk (contracts, data, concurrency, security, operability), backs findings with `file:line` evidence, and is read-only or non-destructive unless you say otherwise. Lazy, not sloppy.

## Install (the lazy way)

```bash
git clone https://github.com/jainashish1691/ctrl-alt-lazy-skills
cd ctrl-alt-lazy-skills
./install.sh summarize-changes   # one skill
./install.sh --all               # or everything
```

Then open Claude Code and type `/summarize-changes`, or just ask "what did I change?" and Claude picks it up on its own.

**Even lazier (no clone):**

```bash
mkdir -p ~/.claude/skills/summarize-changes
curl -o ~/.claude/skills/summarize-changes/SKILL.md \
  https://raw.githubusercontent.com/jainashish1691/ctrl-alt-lazy-skills/main/skills/summarize-changes/SKILL.md
```

Skills install to `~/.claude/skills/` (all your projects). To share one with your team instead, copy it into your repo's `.claude/skills/` folder and commit it.

## Skills

| Reel | Skill | What it does |
|---|---|---|
| #01 | [`summarize-changes`](skills/summarize-changes/SKILL.md) | Senior-reviewer pass on your diff or branch (`/summarize-changes main`): breaking API/event contracts, migration safety, concurrency, security and config risks with `file:line`, commit-split advice, Conventional Commit message, and a PR description with rollout and rollback |
| #02 | [`write-tests`](skills/write-tests/SKILL.md) | `/write-tests src/cart.js` writes high-value tests in your repo's own framework: right test level, invariants and property tests, failure modes, idempotency and concurrency, characterization mode for legacy code, run twice for flakiness |

## Agents

| Reel | Agents | What they do |
|---|---|---|
| #06 | [`review-squad`](agents/review-squad/) | Five read-only reviewers (security, performance, test coverage, API/event/DB contracts, devil's advocate) that share one severity scale and report format. Run them as parallel subagents, or as an agent team where they message each other and try to disprove each other's findings. Includes cross-session messaging prompts and safe settings |

## Hooks

| Reel | Hook | What it does |
|---|---|---|
| #04 | [`session-archive`](hooks/session-archive/) | `SessionEnd` hook that archives every Claude Code session outside `~/.claude` (beats the ~30-day cleanup), with a searchable cross-project index. Atomic, idempotent, never blocks, private by default. Install: `python3 hooks/session-archive/install.py` |

More coming with every reel. Follow [@ctrl.alt.lazy](https://instagram.com/ctrl.alt.lazy) so you don't have to check.

## How a skill works

A skill is just a folder with a `SKILL.md` file:

```
~/.claude/skills/summarize-changes/
└── SKILL.md      # frontmatter (name, description) + plain-English instructions
```

- The **folder name** becomes the command: `/summarize-changes`.
- The **description** tells Claude when to load it automatically, so make it specific.
- Edits apply live. A brand-new folder needs one Claude Code restart.

## Read before you install

Skills are instructions Claude follows, and some run commands. Read any `SKILL.md` (these included) before you install it. That's the one non-lazy step I recommend.

## Disclaimer

Community project. Not affiliated with or endorsed by Anthropic. "Claude" and "Claude Code" are Anthropic's products.

## License

[MIT](LICENSE): copy, tweak, take credit in standup.
