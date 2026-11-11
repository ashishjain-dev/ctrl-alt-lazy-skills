#!/usr/bin/env python3
"""Install Claude Code hooks from this repo into ~/.claude (all your projects).

Every hook lives in hooks/<name>/ with a hook.json manifest. This one installer reads the
manifest, copies the hook's files to ~/.claude/hooks/<name>/, and registers it in
~/.claude/settings.json.

Safe by design: backs up settings.json first (never overwrites an earlier backup), keeps every
existing setting and hook, writes atomically, and is idempotent (re-run = update, no duplicates).

Usage:
  python3 hooks/install.py --list                   # show available hooks
  python3 hooks/install.py guardrails               # install or update one (or several) hooks
  python3 hooks/install.py --all                    # install every hook in this repo
  python3 hooks/install.py guardrails --fail-closed # crash or timeout blocks the call too
                                                    #   (adds "onFailure": "block"; Claude Code v2.1.295+)
  python3 hooks/install.py guardrails --dry-run     # print the resulting settings, change nothing
  python3 hooks/install.py guardrails --uninstall   # remove (data such as logs or archives is kept)

hook.json (see README "Add your own hook"):
  {
    "name": "my-hook",                       # must match the folder name
    "description": "one line",
    "script": "my_hook.py",                  # what Claude Code runs (.py runs with this Python)
    "files": ["my_hook.py", "rules.json"],   # copied to ~/.claude/hooks/my-hook/
    "register": [                            # one entry per event the hook listens to
      {"event": "PreToolUse", "matcher": "Bash", "timeout": 10}
    ],
    "fail_closed": true,                     # optional: allow --fail-closed for this hook
    "after_install": "message to print",     # optional
    "legacy": ["hooks/old_name.py"]          # optional: old install paths (relative to ~/.claude)
  }                                          #   to remove when migrating
"""
import json
import os
import re
import shutil
import sys
import time

HOOKS_SRC = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
SETTINGS = os.path.join(CLAUDE_DIR, "settings.json")

# Events this installer accepts. Claude Code has more; add them here if a hook needs one.
EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "Notification",
          "Stop", "SubagentStop", "SessionStart", "SessionEnd", "PreCompact", "PermissionRequest"}
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest"}


class ManifestError(Exception):
    pass


# ---------- manifests ----------
def available():
    out = {}
    for name in sorted(os.listdir(HOOKS_SRC)):
        path = os.path.join(HOOKS_SRC, name, "hook.json")
        if os.path.isfile(path):
            out[name] = path
    return out


def load_manifest(name, path):
    with open(path, encoding="utf-8") as f:
        try:
            m = json.load(f)
        except ValueError as e:
            raise ManifestError(f"{path}: invalid JSON ({e})")
    if m.get("name") != name:
        raise ManifestError(f"{path}: \"name\" must be \"{name}\" (the folder name)")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise ManifestError(f"{path}: name must be lowercase letters, digits and dashes")
    src = os.path.dirname(path)
    files = m.get("files") or [m.get("script")]
    if m.get("script") not in files:
        raise ManifestError(f"{path}: \"script\" must be one of \"files\"")
    for fn in files:
        if not fn or os.path.isabs(fn) or ".." in fn.replace("\\", "/").split("/"):
            raise ManifestError(f"{path}: bad file name {fn!r}")
        if not os.path.isfile(os.path.join(src, fn)):
            raise ManifestError(f"{path}: file not found: {fn}")
    regs = m.get("register")
    if not regs:
        raise ManifestError(f"{path}: \"register\" needs at least one event")
    for r in regs:
        if r.get("event") not in EVENTS:
            raise ManifestError(f"{path}: unknown event {r.get('event')!r} (known: {', '.join(sorted(EVENTS))})")
        if "matcher" in r and r["event"] not in TOOL_EVENTS:
            raise ManifestError(f"{path}: \"matcher\" only applies to tool events, not {r['event']}")
    m["files"], m["_src"] = files, src
    m["_dest"] = os.path.join(CLAUDE_DIR, "hooks", name)
    return m


# ---------- settings ----------
def load_settings():
    if not os.path.exists(SETTINGS):
        return {}
    with open(SETTINGS, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def owned_by(m, cmd):
    """True only for commands that run THIS hook's installed script (or a legacy copy of it)."""
    cmd = os.path.normcase(str(cmd))
    paths = [os.path.join(m["_dest"], m["script"])] + [os.path.join(CLAUDE_DIR, p) for p in m.get("legacy", [])]
    return any(os.path.normcase(p) in cmd for p in paths)


def strip(settings, m):
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            hs = [h for h in group.get("hooks", []) if not owned_by(m, h.get("command", ""))]
            if hs:
                kept.append({**group, "hooks": hs})
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event)
    if "hooks" in settings and not settings["hooks"]:
        settings.pop("hooks")
    return settings


def register(settings, m, fail_closed):
    script = os.path.join(m["_dest"], m["script"])
    cmd = f'"{sys.executable}" "{script}"' if script.endswith(".py") else f'"{script}"'
    for r in m["register"]:
        hook = {"type": "command", "command": cmd}
        if "timeout" in r:
            hook["timeout"] = r["timeout"]
        if fail_closed and m.get("fail_closed"):
            hook["onFailure"] = "block"
        group = {"hooks": [hook]}
        if "matcher" in r:
            group = {"matcher": r["matcher"], **group}
        settings.setdefault("hooks", {}).setdefault(r["event"], []).append(group)
    return settings


def write_settings(out):
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    if os.path.exists(SETTINGS):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup, n = f"{SETTINGS}.bak-{stamp}", 1
        while os.path.exists(backup):
            backup, n = f"{SETTINGS}.bak-{stamp}-{n}", n + 1
        shutil.copy2(SETTINGS, backup)
        print(f"Backed up settings to {backup}")
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    os.replace(tmp, SETTINGS)


# ---------- files ----------
def copy_files(m):
    os.makedirs(m["_dest"], exist_ok=True)
    for fn in m["files"]:
        dst = os.path.join(m["_dest"], fn)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(m["_src"], fn), dst)
    os.chmod(os.path.join(m["_dest"], m["script"]), 0o755)
    remove_legacy(m)


def remove_files(m):
    for fn in m["files"]:
        p = os.path.join(m["_dest"], fn)
        if os.path.exists(p):
            os.remove(p)
    remove_legacy(m)
    try:
        os.rmdir(m["_dest"])  # only if empty: user config or data next to it is kept
    except OSError:
        pass


def remove_legacy(m):
    for rel in m.get("legacy", []):
        p = os.path.join(CLAUDE_DIR, rel)
        if os.path.isfile(p):
            os.remove(p)


# ---------- main ----------
def main(argv):
    flags = {a for a in argv if a.startswith("--")}
    names = [a for a in argv if not a.startswith("--")]
    unknown = flags - {"--all", "--list", "--fail-closed", "--dry-run", "--uninstall", "--help"}
    if unknown or "--help" in flags:
        print(__doc__)
        return 2 if unknown else 0

    hooks = available()
    if "--list" in flags or (not names and "--all" not in flags):
        for name, path in hooks.items():
            try:
                m = load_manifest(name, path)
                events = ", ".join(r["event"] + (f" [{r['matcher']}]" if "matcher" in r else "") for r in m["register"])
                print(f"  {name:<18} {events}\n  {'':<18} {m.get('description', '')}")
            except ManifestError as e:
                print(f"  {name:<18} BROKEN: {e}")
        if not names and "--list" not in flags:
            print("\nInstall one with: python3 hooks/install.py <name>   (or --all)")
        return 0

    if "--all" in flags:
        names = list(hooks)
    missing = [n for n in names if n not in hooks]
    if missing:
        print(f"Unknown hook(s): {', '.join(missing)}. Available: {', '.join(hooks)}", file=sys.stderr)
        return 2
    try:
        manifests = [load_manifest(n, hooks[n]) for n in names]
    except ManifestError as e:
        print(f"Nothing changed. {e}", file=sys.stderr)
        return 2
    try:
        settings = load_settings()
    except ValueError as e:
        print(f"{SETTINGS} is not valid JSON ({e}). Fix it first; nothing was changed.", file=sys.stderr)
        return 2

    uninstall = "--uninstall" in flags
    for m in manifests:
        settings = strip(settings, m)
        if not uninstall:
            settings = register(settings, m, "--fail-closed" in flags)
    out = json.dumps(settings, indent=2) + "\n"
    if "--dry-run" in flags:
        print(out, end="")
        return 0

    write_settings(out)
    for m in manifests:
        if uninstall:
            remove_files(m)
            print(f"Removed {m['name']}. Its data and any config you wrote next to it were kept.")
        else:
            copy_files(m)
            fc = " (fail-closed)" if "--fail-closed" in flags and m.get("fail_closed") else ""
            print(f"Installed {m['name']} to {m['_dest']}{fc}")
            if m.get("after_install"):
                print(f"  {m['after_install']}")
    print("Check with /hooks inside Claude Code. Restart open sessions to pick up changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
