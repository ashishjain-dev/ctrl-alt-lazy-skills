#!/usr/bin/env python3
"""Claude Code PreToolUse guardrail: stop irreversible commands before they run.

Claude Code pipes the pending tool call to this script as JSON on stdin. If the call
matches a rule, the script answers with a JSON decision:

  deny  -> the call never runs; Claude reads the reason and changes its plan
  ask   -> you get a permission prompt with the reason (even in auto-accept modes)

No match -> no output, exit 0: the normal permission flow applies (silence never approves).

What it guards (see rules.json):
  * Bash commands: DROP/TRUNCATE, DELETE without WHERE, dropdb, ORM "reset/drop" tasks,
    terraform destroy, kubectl delete on prod contexts, force-push to protected branches,
    git reset --hard / clean -fdx, recursive rm on dangerous targets, curl | sh
  * Edits to its own config and to Claude settings (so Claude can't switch it off)

Honest limit: it matches the text of a command. A command hidden inside a script file,
or built at runtime, can slip past. It is a seatbelt, not a sandbox: least-privilege DB
grants and cloud IAM are still your real protection.

Config, merged in this order (later wins):
  1. rules.json next to this script         (defaults)
  2. ~/.claude/guardrails.json               (your personal overrides)
  3. <project>/.claude/guardrails.json       (team overrides, commit it)
Override keys: "disable": ["rule-id", ...], "rules": [extra rules], "checks": [changes to a
code check's decision/reason/instead, by id], "protected_branches", "prod_context_pattern",
"fail_open", "audit_log".

Exit codes: always 0 with JSON for a decision. On an internal error it exits 2 (blocks the
call, fail-closed) unless "fail_open": true. Exit 1 would NOT block anything.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude"))
MAX_LOG_CMD = 500
DECISIONS = ("deny", "ask")

# Code checks: detection lives in Python below, the decision and wording live in rules.json
# ("checks"). These are the fallback for a rules.json from before "checks" existed.
DEFAULT_CHECKS = {
    "force-push": {
        "decision": "deny",
        "reason": "force-push to a protected branch",
        "instead": "Push to a branch and open a PR. Use --force-with-lease on your own branch.",
    },
    "rm-recursive": {
        "decision": "deny",
        "reason": "recursive rm on a dangerous path or outside the project",
        "instead": "Delete specific paths inside the project, or ask me to do it.",
    },
    "kubectl-prod": {
        "decision": "deny",
        "reason": "destructive kubectl command on a prod context",
        "instead": "Show me the exact command and target; I'll run it.",
        "no_context": {
            "decision": "ask",
            "reason": "kubectl delete with no explicit --context (it runs on whatever context is current)",
        },
    },
    "self-protect": {
        "decision": "ask",
        "reason": "edit to the guardrails config or Claude Code settings (hooks and permissions live there)",
        "instead": "Make this change yourself if you meant it.",
    },
}


# ---------- config ----------
def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def load_config(cwd):
    cfg = _load_json(os.path.join(HERE, "rules.json"))
    if not cfg:
        raise RuntimeError(f"rules.json missing next to {__file__}")
    checks = {cid: dict(spec, **({"no_context": dict(spec["no_context"])} if "no_context" in spec else {}))
              for cid, spec in DEFAULT_CHECKS.items()}
    merge_checks(checks, cfg.get("checks"), "rules.json")
    for path in (os.path.join(CLAUDE_DIR, "guardrails.json"),
                 os.path.join(project_root(cwd), ".claude", "guardrails.json")):
        over = _load_json(path)
        if not over:
            continue
        cfg["disable"] = sorted(set(cfg.get("disable", [])) | set(over.get("disable", [])))
        cfg["rules"] = cfg.get("rules", []) + over.get("rules", [])
        merge_checks(checks, over.get("checks"), path)
        for k in ("protected_branches", "prod_context_pattern", "fail_open", "audit_log"):
            if k in over:
                cfg[k] = over[k]
    cfg["checks"] = checks
    return cfg


def merge_checks(checks, items, source):
    """Merge a "checks" list ([{"id": ..., "decision": ..., ...}]) onto the built-in checks by id.
    A malformed entry is skipped with a warning: a typo here must not block every tool call."""
    if items is None:
        return
    if not isinstance(items, list):
        print(f"guardrails: {source}: \"checks\" must be a list of objects; ignored", file=sys.stderr)
        return
    for item in items:
        if not isinstance(item, dict):
            print(f"guardrails: {source}: \"checks\" entry {item!r} is not an object; ignored", file=sys.stderr)
            continue
        cid = item.get("id")
        if cid not in checks:
            print(f"guardrails: {source}: unknown check id {cid!r} ignored "
                  f"(known: {', '.join(sorted(checks))}; regex rules go in \"rules\")", file=sys.stderr)
            continue
        spec = checks[cid]
        for k in ("decision", "reason", "instead"):
            if k in item:
                spec[k] = item[k]
        if "no_context" in spec and isinstance(item.get("no_context"), dict):
            spec["no_context"].update({k: v for k, v in item["no_context"].items()
                                       if k in ("decision", "reason", "instead")})


def check_decision(cfg, cid, detail, variant=None):
    """Build (decision, rule_id, reason, instead) for a code check from its config entry."""
    spec = cfg.get("checks", DEFAULT_CHECKS)[cid]
    default = DEFAULT_CHECKS[cid]
    if variant:
        spec, default = {**spec, **spec[variant]}, {**default, **default[variant]}
    decision = spec.get("decision")
    if decision not in DECISIONS:
        print(f"guardrails: check {cid!r} has decision {decision!r} (use deny or ask); "
              f"using {default['decision']!r}", file=sys.stderr)
        decision = default["decision"]
    reason = spec.get("reason") or default["reason"]
    return decision, cid, f"{reason}: {detail}" if detail else reason, spec.get("instead", "")


def project_root(cwd):
    d = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, ".git")) or os.path.isdir(os.path.join(d, ".claude")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.abspath(cwd or os.getcwd())
        d = parent


# ---------- checks ----------
def regex_rules(cfg, command):
    """Rules from config with a "pattern" (case-insensitive regex on the full command)."""
    hits = []
    disabled = set(cfg.get("disable", []))
    for r in cfg.get("rules", []):
        if r.get("id") in disabled or "pattern" not in r:
            continue
        if re.search(r["pattern"], command, re.IGNORECASE | re.DOTALL):
            hits.append(r)
    return hits


def segments(command):
    """Split a shell line into simple commands on ; && || | and newlines (quote-aware)."""
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError:  # unbalanced quotes: fall back to a rough split
        tokens = command.split()
    seg, out = [], []
    for t in tokens:
        if t and set(t) <= set(";&|\n"):
            if seg:
                out.append(seg)
            seg = []
        else:
            seg.append(t)
    if seg:
        out.append(seg)
    return out


def strip_wrappers(argv):
    """Drop sudo/env/time/nice/VAR=val prefixes so `sudo rm -rf /` is seen as `rm`."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("sudo", "env", "time", "nice", "nohup", "command", "builtin", "exec"):
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a):
            i += 1
        else:
            break
    return argv[i:]


def check_rm(argv, cwd, root):
    """Return a detail string (which target, where it resolves) for a dangerous recursive rm."""
    if not argv or os.path.basename(argv[0]) != "rm":
        return None
    flags = "".join(a.lstrip("-") for a in argv[1:] if a.startswith("-") and not a.startswith("--"))
    long_flags = {a for a in argv[1:] if a.startswith("--")}
    recursive = "r" in flags.lower() or "--recursive" in long_flags
    if not recursive:
        return None
    targets = [a for a in argv[1:] if not a.startswith("-")]
    home = os.path.expanduser("~")
    for t in targets:
        if t in ("/", "/*", "~", "~/", "$HOME", "${HOME}", "*", ".", "./", "..", "../") or t.startswith("$"):
            return f"'{t}'"
        p = os.path.abspath(os.path.join(cwd, os.path.expanduser(t)))
        if p in ("/", home) or p == root:
            return f"'{t}' resolves to {p}" + (" (the project root)" if p == root else "")
        temps = {os.path.realpath(tempfile.gettempdir()), "/tmp", "/var/tmp"}
        if any(p != tmp and (p + os.sep).startswith(tmp + os.sep) for tmp in temps):
            continue  # scratch files under a temp dir are fair game (the temp dir itself is not)
        if not (p + os.sep).startswith(root + os.sep):
            return f"'{t}' -> {p} is outside the project"
    return None


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "branch", "--show-current"], cwd=cwd, capture_output=True,
                             text=True, timeout=3)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_git(argv, cfg, cwd="."):
    """Return a detail string (the refs) for a force-push to a protected branch."""
    if len(argv) < 2 or os.path.basename(argv[0]) != "git":
        return None
    # skip global options like -C dir, -c k=v
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in ("-C", "-c") else 1
    if i >= len(argv):
        return None
    sub, rest = argv[i], argv[i + 1:]
    if sub == "push":
        force = any(a in ("-f", "--mirror") or a.startswith("--force") or (a.startswith("-") and not a.startswith("--") and "f" in a)
                    for a in rest)
        plus_ref = [a for a in rest if a.startswith("+")]
        protected = cfg.get("protected_branches", ["main", "master"])
        refs = [a.lstrip("+").split(":")[-1] for a in rest if not a.startswith("-")][1:]  # after remote
        if not refs or refs == ["HEAD"]:
            refs = [current_branch(cwd) or "?unknown"]
        hits_protected = any(re.fullmatch(p, r) for r in refs for p in protected)
        if (force or plus_ref) and (hits_protected or "?unknown" in refs):
            return f"'{', '.join(refs)}'"
    return None


def check_kubectl(argv, cfg):
    """Return (variant, detail): variant None = prod context (deny), "no_context" = no --context (ask)."""
    if not argv or os.path.basename(argv[0]) not in ("kubectl", "oc"):
        return None
    verbs = {"delete", "drain", "replace", "patch", "scale", "rollout"}
    verb = next((a for a in argv[1:] if not a.startswith("-")), "")
    if verb not in verbs:
        return None
    joined = " ".join(argv)
    ctx = re.search(r"--context[= ](\S+)", joined)
    prod = cfg.get("prod_context_pattern", r"prod|prd|live")
    if ctx and re.search(prod, ctx.group(1), re.IGNORECASE):
        return None, f"kubectl {verb} on context '{ctx.group(1)}'"
    if verb == "delete" and not ctx:
        return "no_context", ""
    return None


def check_file_tool(tool, tool_input):
    """Edits to guardrail config or Claude settings: Claude must not switch off its own seatbelt.
    Returns the path as the detail string."""
    path = str(tool_input.get("file_path", "")).replace("\\", "/")
    name = os.path.basename(path)
    if name == "guardrails.json" or re.search(r"/guardrails/(rules\.json|guard\.py)$", path):
        return path
    own = os.path.join(CLAUDE_DIR, "settings.json").replace("\\", "/")
    if re.search(r"/\.claude/settings(\.local)?\.json$", path) or os.path.normcase(path) == os.path.normcase(own):
        return path
    return None


def evaluate(event, cfg):
    """Return (decision, rule_id, reason, suggestion) or None."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    cwd = event.get("cwd") or os.getcwd()
    root = project_root(cwd)
    disabled = set(cfg.get("disable", []))
    found = []

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = check_file_tool(tool, tool_input)
        if path and "self-protect" not in disabled:
            found.append(check_decision(cfg, "self-protect", path))
    elif tool == "Bash":
        command = str(tool_input.get("command", ""))
        for r in regex_rules(cfg, command):
            found.append((r.get("decision", "deny"), r["id"], r["reason"], r.get("instead", "")))
        for seg in segments(command):
            argv = strip_wrappers(seg)
            if "rm-recursive" not in disabled:
                detail = check_rm(argv, cwd, root)
                if detail:
                    found.append(check_decision(cfg, "rm-recursive", detail))
            if "force-push" not in disabled:
                detail = check_git(argv, cfg, cwd)
                if detail:
                    found.append(check_decision(cfg, "force-push", detail))
            if "kubectl-prod" not in disabled:
                k = check_kubectl(argv, cfg)
                if k:
                    found.append(check_decision(cfg, "kubectl-prod", k[1], variant=k[0]))
    if not found:
        return None
    # deny beats ask; keep the first of the strongest
    found.sort(key=lambda f: 0 if f[0] == "deny" else 1)
    return found[0]


# ---------- output ----------
REDACT = [
    (re.compile(r"(://[^:/\s]+:)[^@\s]+@"), r"\1***@"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)(\s*[=:]\s*)\S+"), r"\1\2***"),
    (re.compile(r"(?<=\s)(-p)(\S+)"), r"\1***"),  # mysql -pSECRET
]


def redact(text):
    for rx, rep in REDACT:
        text = rx.sub(rep, text)
    return text


def audit(cfg, event, decision):
    path = os.path.expanduser(cfg.get("audit_log", os.path.join(CLAUDE_DIR, "guardrails", "audit.jsonl")))
    if not path:
        return
    tool_input = event.get("tool_input", {}) or {}
    target = tool_input.get("command") or tool_input.get("file_path") or ""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "session_id": event.get("session_id"),
        "cwd": event.get("cwd"),
        "tool": event.get("tool_name"),
        "decision": decision[0],
        "rule": decision[1],
        "target": redact(str(target))[:MAX_LOG_CMD],
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass  # never block a decision because the log is unwritable


def cli_test(args):
    """guard.py --test '<command>'  or  guard.py --test-edit <path>: show the decision, change nothing."""
    cwd = os.getcwd()
    if args[0] == "--test-edit":
        event = {"tool_name": "Edit", "cwd": cwd, "tool_input": {"file_path": os.path.abspath(args[1])}}
    else:
        event = {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": " ".join(args[1:])}}
    decision = evaluate(event, load_config(cwd))
    if not decision:
        print("ALLOW  no rule matched (Claude Code's normal permission flow applies)")
    else:
        verdict, rule_id, why, instead = decision
        print(f"{verdict.upper():<6} [{rule_id}] {why}" + (f"\n       Instead: {instead}" if instead else ""))
    return 0


def main():
    if len(sys.argv) > 2 and sys.argv[1] in ("--test", "--test-edit"):
        return cli_test(sys.argv[1:])
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__ + "\nTest a rule without Claude:\n  guard.py --test 'psql -c \"DROP TABLE x\"'\n  guard.py --test-edit ~/.claude/settings.json")
        return 0
    raw = sys.stdin.read()
    cfg = {}
    try:
        event = json.loads(raw) if raw.strip() else {}
        cfg = load_config(event.get("cwd"))
        if os.environ.get("CLAUDE_GUARDRAILS", "").lower() == "off":
            return 0
        decision = evaluate(event, cfg)
        if not decision:
            return 0
        verdict, rule_id, why, instead = decision
        reason = f"guardrails [{rule_id}]: {why}."
        if instead:
            reason += f" Instead: {instead}"
        if verdict == "deny":
            reason += " Do not retry this or work around it; tell the user what you wanted to run and why."
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict,
            "permissionDecisionReason": reason,
        }}))
        audit(cfg, event, decision)
        return 0
    except Exception as e:  # fail closed: exit 2 blocks; exit 1 would let the call through
        if cfg.get("fail_open"):
            print(f"guardrails: internal error, allowing (fail_open): {e}", file=sys.stderr)
            return 0
        print(f"guardrails: internal error, blocking to be safe: {e}. "
              f"Set \"fail_open\": true in guardrails.json to change this.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
