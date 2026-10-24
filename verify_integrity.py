#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Pipeline Integrity Verifier Launcher
เรียกใช้งาน src/atf/tools/verify_pipeline_integrity.py
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "verify_pipeline_integrity.py")
if not os.path.exists(script_path):
    script_path = os.path.join(os.path.dirname(__file__), "testing files", "verify_pipeline_integrity.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
