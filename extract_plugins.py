#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Plugin UI Text Extractor Launcher
เรียกใช้งาน src/atf/tools/extract_plugin_texts.py โดยอ่านค่าจาก data/project_manifest.json อัตโนมัติ
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "extract_plugin_texts.py")
if not os.path.exists(script_path):
    script_path = os.path.join(os.path.dirname(__file__), "testing files", "extract_plugin_texts.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
