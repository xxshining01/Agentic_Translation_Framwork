#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Plugin UI Text Injector Launcher
เรียกใช้งาน src/atf/tools/inject_plugin_texts.py
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "inject_plugin_texts.py")
if not os.path.exists(script_path):
    script_path = os.path.join(os.path.dirname(__file__), "testing files", "inject_plugin_texts.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
