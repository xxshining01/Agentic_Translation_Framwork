#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Enrich Roles Launcher
เรียกใช้งาน src/atf/tools/enrich_csv_with_rpgm_roles.py
"""
import os
import sys

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "enrich_csv_with_rpgm_roles.py")
if __name__ == "__main__":
    import subprocess
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
