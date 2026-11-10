"""Tests for the shared hooks installer. Run: python3 -m unittest discover -s hooks/tests -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(HOOKS, "install.py")


class Installer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.settings = os.path.join(self.dir, "settings.json")
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_installer(self, *args, script=INSTALL):
        return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, env=self.env)

    def read(self):
        with open(self.settings) as f:
            return json.load(f)

    def commands(self, event):
        return [h["command"] for g in self.read().get("hooks", {}).get(event, []) for h in g["hooks"]]

    def test_list_shows_every_hook(self):
        out = self.run_installer("--list").stdout
        self.assertIn("guardrails", out)
        self.assertIn("session-archive", out)
        self.assertNotIn("BROKEN", out)

    def test_install_keeps_other_settings_and_is_idempotent(self):
        with open(self.settings, "w") as f:
            json.dump({"model": "opus", "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]}}, f)
        for _ in range(2):
            self.assertEqual(self.run_installer("guardrails").returncode, 0)
        s = self.read()
        self.assertEqual(s["model"], "opus")
        cmds = self.commands("PreToolUse")
        self.assertEqual(len(cmds), 2, cmds)
        self.assertIn("mine.sh", cmds)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "hooks", "guardrails", "rules.json")))
        backups = [f for f in os.listdir(self.dir) if f.startswith("settings.json.bak-")]
        self.assertEqual(len(backups), 2)  # one per run, never overwritten

    def test_all_installs_every_hook(self):
        self.assertEqual(self.run_installer("--all").returncode, 0)
        self.assertEqual(len(self.commands("PreToolUse")), 1)
        self.assertEqual(len(self.commands("SessionEnd")), 1)

    def test_fail_closed_only_where_manifest_allows(self):
        self.run_installer("--all", "--fail-closed")
        pre = self.read()["hooks"]["PreToolUse"][0]["hooks"][0]
        end = self.read()["hooks"]["SessionEnd"][0]["hooks"][0]
        self.assertEqual(pre.get("onFailure"), "block")
        self.assertNotIn("onFailure", end)

    def test_dry_run_changes_nothing(self):
        out = self.run_installer("guardrails", "--dry-run").stdout
        self.assertIn("PreToolUse", out)
        self.assertFalse(os.path.exists(self.settings))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "hooks")))

    def test_uninstall_removes_only_ours(self):
        with open(self.settings, "w") as f:
            json.dump({"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "keep.sh"}]}]}}, f)
        self.run_installer("--all")
        self.run_installer("--all", "--uninstall")
        s = self.read()
        self.assertEqual(self.commands("SessionEnd"), ["keep.sh"])
        self.assertNotIn("PreToolUse", s.get("hooks", {}))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "hooks", "guardrails")))

    def test_migrates_legacy_session_archive_install(self):
        legacy = os.path.join(self.dir, "hooks", "archive_session.py")
        os.makedirs(os.path.dirname(legacy))
        open(legacy, "w").close()
        with open(self.settings, "w") as f:
            json.dump({"hooks": {"SessionEnd": [{"hooks": [
                {"type": "command", "command": f'"{sys.executable}" "{legacy}"'}]}]}}, f)
        self.run_installer("session-archive")
        cmds = self.commands("SessionEnd")
        self.assertEqual(len(cmds), 1, cmds)
        self.assertIn(os.path.join("hooks", "session-archive", "archive_session.py"), cmds[0])
        self.assertFalse(os.path.exists(legacy))

    def test_per_hook_wrapper_still_works(self):
        r = self.run_installer("--fail-closed", script=os.path.join(HOOKS, "guardrails", "install.py"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read()["hooks"]["PreToolUse"][0]["hooks"][0].get("onFailure"), "block")

    def test_unknown_hook_and_bad_json_settings(self):
        self.assertEqual(self.run_installer("nope").returncode, 2)
        with open(self.settings, "w") as f:
            f.write("{broken")
        r = self.run_installer("guardrails")
        self.assertEqual(r.returncode, 2)
        with open(self.settings) as f:
            self.assertEqual(f.read(), "{broken")  # untouched


class Manifest(unittest.TestCase):
    """Validation runs against a throwaway copy of the hooks folder."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copy2(INSTALL, os.path.join(self.root, "install.py"))
        self.hook = os.path.join(self.root, "demo")
        os.makedirs(self.hook)
        open(os.path.join(self.hook, "demo.py"), "w").close()
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=os.path.join(self.root, "claude"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def manifest(self, **kw):
        m = {"name": "demo", "script": "demo.py", "register": [{"event": "Stop"}]}
        m.update(kw)
        with open(os.path.join(self.hook, "hook.json"), "w") as f:
            json.dump(m, f)
        return subprocess.run([sys.executable, os.path.join(self.root, "install.py"), "demo", "--dry-run"],
                              capture_output=True, text=True, env=self.env)

    def test_valid(self):
        self.assertEqual(self.manifest().returncode, 0)

    def test_rejects(self):
        for kw in ({"name": "other"}, {"register": [{"event": "Nope"}]}, {"register": []},
                   {"register": [{"event": "Stop", "matcher": "Bash"}]}, {"script": "missing.py"},
                   {"files": ["../escape.py"], "script": "../escape.py"}):
            self.assertEqual(self.manifest(**kw).returncode, 2, kw)


if __name__ == "__main__":
    unittest.main()
