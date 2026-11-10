#!/usr/bin/env python3
"""Register the guardrails PreToolUse hook in ~/.claude/settings.json (all your projects).

Safe by design: backs up settings.json first, keeps every existing setting and hook,
and is idempotent (running it twice does not add a second entry). Updating = run it again.

Usage:
  python3 hooks/guardrails/install.py                # install or update
  python3 hooks/guardrails/install.py --fail-closed  # also block if the hook crashes or times out
                                                     #   (adds "onFailure": "block", Claude Code v2.1.295+)
  python3 hooks/guardrails/install.py --dry-run      # print the resulting settings, change nothing
  python3 hooks/guardrails/install.py --uninstall    # remove it (your audit log is kept)
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
DEST_DIR = os.path.join(CLAUDE_DIR, "hooks", "guardrails")
DEST = os.path.join(DEST_DIR, "guard.py")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")
MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit"
EVENT = "PreToolUse"


def ours(cmd):
    """True only for a command that runs OUR installed script, not any file sharing its name."""
    return os.path.normcase(DEST) in os.path.normcase(str(cmd))


def load():
    if not os.path.exists(SETTINGS):
        return {}
    with open(SETTINGS, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def strip_ours(settings):
    groups = settings.get("hooks", {}).get(EVENT, [])
    kept = []
    for g in groups:
        hooks = [h for h in g.get("hooks", []) if not ours(h.get("command", ""))]
        if hooks:
            kept.append({**g, "hooks": hooks})
    if kept:
        settings.setdefault("hooks", {})[EVENT] = kept
    else:
        settings.get("hooks", {}).pop(EVENT, None)
        if settings.get("hooks") == {}:
            settings.pop("hooks")
    return settings


def main():
    args = set(sys.argv[1:])
    unknown = args - {"--fail-closed", "--dry-run", "--uninstall"}
    if unknown:
        sys.exit(f"Unknown option(s): {' '.join(sorted(unknown))}\n{__doc__}")
    try:
        settings = load()
    except ValueError as e:
        sys.exit(f"{SETTINGS} is not valid JSON ({e}). Fix it first; nothing was changed.")

    if "--uninstall" in args and not os.path.exists(DEST):
        print("Nothing to uninstall.")
        return

    settings = strip_ours(settings)
    if "--uninstall" not in args:
        # The interpreter running this installer is known to exist; a bare "python3" is often
        # missing on Windows and a hook that can't start does not block anything.
        hook = {"type": "command", "command": f'"{sys.executable}" "{DEST}"', "timeout": 10}
        if "--fail-closed" in args:
            hook["onFailure"] = "block"
        settings.setdefault("hooks", {}).setdefault(EVENT, []).append({"matcher": MATCHER, "hooks": [hook]})

    out = json.dumps(settings, indent=2) + "\n"
    if "--dry-run" in args:
        print(out, end="")
        return

    if os.path.exists(SETTINGS):
        backup, n = f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}", 1
        while os.path.exists(backup):  # never overwrite an earlier backup from the same second
            backup, n = f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}-{n}", n + 1
        shutil.copy2(SETTINGS, backup)
        print(f"Backed up settings to {backup}")
    if "--uninstall" in args:
        for name in ("guard.py", "rules.json"):
            p = os.path.join(DEST_DIR, name)
            if os.path.exists(p):
                os.remove(p)
        print("Removed the guardrails hook. Audit log and your guardrails.json overrides were kept.")
    else:
        os.makedirs(DEST_DIR, exist_ok=True)
        for name in ("guard.py", "rules.json"):
            shutil.copy2(os.path.join(HERE, name), os.path.join(DEST_DIR, name))
        os.chmod(DEST, 0o755)
        print(f"Installed guardrails to {DEST_DIR}")
        print(f"Registered {EVENT} hook for {MATCHER}" + (" (fail-closed)" if "--fail-closed" in args else ""))
        print("Overrides: ~/.claude/guardrails.json (you) or <repo>/.claude/guardrails.json (team).")
    tmp = SETTINGS + ".tmp"
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    os.replace(tmp, SETTINGS)
    print("Check it with /hooks inside Claude Code. Restart open sessions to pick it up.")


if __name__ == "__main__":
    main()
