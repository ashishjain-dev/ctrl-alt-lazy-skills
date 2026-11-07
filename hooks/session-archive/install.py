#!/usr/bin/env python3
"""Register the session-archive SessionEnd hook in ~/.claude/settings.json.

Safe by design: backs up settings.json first, keeps every existing setting and hook,
and is idempotent (running it twice does not add a second entry).

Usage:
  python3 hooks/session-archive/install.py             # install for all projects
  python3 hooks/session-archive/install.py --uninstall # remove it again
  python3 hooks/session-archive/install.py --dry-run   # print the resulting settings
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "archive_session.py")
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
DEST = os.path.join(CLAUDE_DIR, "hooks", "archive_session.py")
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")

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
    groups = settings.get("hooks", {}).get("SessionEnd", [])
    kept = []
    for g in groups:
        hooks = [h for h in g.get("hooks", []) if not ours(h.get("command", ""))]
        if hooks:
            kept.append({**g, "hooks": hooks})
    if kept:
        settings.setdefault("hooks", {})["SessionEnd"] = kept
    else:
        settings.get("hooks", {}).pop("SessionEnd", None)
        if settings.get("hooks") == {}:
            settings.pop("hooks")
    return settings

def main():
    args = set(sys.argv[1:])
    try:
        settings = load()
    except ValueError as e:
        sys.exit(f"{SETTINGS} is not valid JSON ({e}). Fix it first; nothing was changed.")

    if "--uninstall" in args and not os.path.exists(SETTINGS) and not os.path.exists(DEST):
        print("Nothing to uninstall.")
        return

    settings = strip_ours(settings)
    if "--uninstall" not in args:
        # Use the interpreter running this installer: it is known to exist. A bare "python3"
        # is often missing on Windows (or is the Microsoft Store stub) and fails silently.
        cmd = f'"{sys.executable}" "{DEST}"'
        settings.setdefault("hooks", {}).setdefault("SessionEnd", []).append(
            {"hooks": [{"type": "command", "command": cmd}]})

    out = json.dumps(settings, indent=2) + "\n"
    if "--dry-run" in args:
        print(out, end="")
        return

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.exists(SETTINGS):
        backup = f"{SETTINGS}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(SETTINGS, backup)
        print(f"Backed up settings to {backup}")
    if "--uninstall" in args:
        if os.path.exists(DEST):
            os.remove(DEST)
        print("Removed the session-archive hook. Your archive folder was left untouched.")
    else:
        shutil.copy2(SRC, DEST)
        os.chmod(DEST, 0o755)
        print(f"Installed hook script to {DEST}")
        print("Registered SessionEnd hook. New sessions are archived when they end.")
        print("Archive: $CLAUDE_SESSION_ARCHIVE_DIR as seen by Claude Code, default ~/.claude-session-archive")
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    os.replace(tmp, SETTINGS)
    print("Check it any time with /hooks inside Claude Code.")

if __name__ == "__main__":
    main()
