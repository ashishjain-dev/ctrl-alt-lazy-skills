#!/usr/bin/env python3
"""Install the session-archive hook. Shortcut for: python3 hooks/install.py session-archive [options]

Options: --dry-run, --uninstall. See hooks/install.py for details.
"""
import os
import runpy
import sys

sys.argv = [sys.argv[0], "session-archive"] + sys.argv[1:]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "install.py"), run_name="__main__")
