#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Project Setup Launcher
เรียกใช้งาน src/atf/tools/setup_project_paths.py
"""
import os
import sys

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "setup_project_paths.py")
if __name__ == "__main__":
    import subprocess
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
