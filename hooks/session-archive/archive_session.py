#!/usr/bin/env python3
"""Claude Code SessionEnd hook: archive the session transcript outside ~/.claude.

Claude Code deletes local transcripts after `cleanupPeriodDays` (default ~30 days),
and they vanish with a reinstall, a new laptop or `rm -rf ~/.claude`. This hook copies
each finished session to a durable archive and appends a searchable index entry.

Input: the SessionEnd hook JSON on stdin (session_id, transcript_path, cwd, reason, ...).
Output: <archive>/<project>/<session_id>.jsonl.gz  (+ one line in <archive>/index.jsonl)

Design rules
- Never block or break Claude Code: every failure is logged to stderr and we exit 0.
- Idempotent: a resumed session overwrites its own archive (the newest transcript is a
  superset), and the index gets a fresh line each time it ends.
- Atomic: write to a temp file, fsync, then rename, so a crash never leaves half a file.
- Private: a new archive directory is created with 0700, files with 0600 (POSIX only; on
  Windows, access comes from the folder's ACLs). An existing directory's permissions are
  left alone. Transcripts contain your code, prompts and command output; treat the
  archive like source code.

Config (environment variables, all optional)
  CLAUDE_SESSION_ARCHIVE_DIR   archive root (default: ~/.claude-session-archive)
  CLAUDE_SESSION_ARCHIVE_SKIP  comma-separated end reasons to skip, e.g. "clear"
  CLAUDE_SESSION_ARCHIVE_MIN_BYTES  skip transcripts smaller than this (default: 2048)
"""
import datetime as dt
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

def log(msg):
    print(f"[session-archive] {msg}", file=sys.stderr)

def slug(text, limit=60):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text or "").strip("-.")
    return (s or "unknown")[:limit]

def git_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None

def first_user_prompt(path, max_lines=400):
    """Best-effort: first plain-text user prompt, for the index. The transcript format is
    internal to Claude Code and may change, so any failure just returns None."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                if not isinstance(msg, dict) or msg.get("role") != "user":
                    continue
                content = msg.get("content")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content
                                       if isinstance(c, dict) and c.get("type") == "text")
                if isinstance(content, str) and content.strip() and not content.lstrip().startswith("<"):
                    return " ".join(content.split())[:160]
    except Exception:
        pass
    return None

def main():
    try:
        event = json.load(sys.stdin)
    except Exception as e:
        log(f"could not parse hook input: {e}")
        return

    session_id = event.get("session_id") or ""
    transcript = event.get("transcript_path") or ""
    cwd = event.get("cwd") or os.getcwd()
    reason = event.get("reason") or "unknown"

    skip = {r.strip() for r in os.environ.get("CLAUDE_SESSION_ARCHIVE_SKIP", "").split(",") if r.strip()}
    if reason in skip:
        return
    if not session_id or not transcript or not os.path.isfile(transcript):
        log(f"no transcript to archive (session={session_id!r}, path={transcript!r})")
        return

    size = os.path.getsize(transcript)
    if size < int(os.environ.get("CLAUDE_SESSION_ARCHIVE_MIN_BYTES", "2048")):
        return

    root = os.path.expanduser(os.environ.get("CLAUDE_SESSION_ARCHIVE_DIR", "~/.claude-session-archive"))
    project = slug(os.path.basename(os.path.normpath(cwd)))
    dest_dir = os.path.join(root, project)
    root_existed = os.path.isdir(root)
    os.makedirs(dest_dir, mode=0o700, exist_ok=True)
    if not root_existed:  # only tighten a folder we created, never one the user already had
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
    dest = os.path.join(dest_dir, f"{slug(session_id, 80)}.jsonl.gz")

    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dest_dir)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz, open(transcript, "rb") as src:
                shutil.copyfileobj(src, gz, 1024 * 1024)
            raw.flush()
            os.fsync(raw.fileno())  # data on disk before the rename makes it visible
        os.chmod(tmp, 0o600)
        os.replace(tmp, dest)
    except Exception as e:
        log(f"archive failed: {e}")
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return

    entry = {
        "archived_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id,
        "project": project,
        "cwd": cwd,
        "git_branch": git_branch(cwd),
        "end_reason": reason,
        "bytes": size,
        "first_prompt": first_user_prompt(transcript),
        "archive": dest,
    }
    try:
        index = os.path.join(root, "index.jsonl")
        with open(index, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(index, 0o600)
    except Exception as e:
        log(f"index write failed: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let the hook break the session
        log(f"unexpected error: {e}")
    sys.exit(0)
