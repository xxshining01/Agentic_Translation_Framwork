#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Character Profiles Sync & Delta Enrollment Launcher (ADR-024 Compliant)
เรียกใช้งาน src/atf/tools/sync_and_enroll_patch_profiles.py
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "sync_and_enroll_patch_profiles.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
