#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Translation Runner Launcher (ADR-024 Compliant)
เรียกใช้งาน src/atf/tools/chatgpt_translator_runner.py อัตโนมัติ
ค่าเริ่มต้น: Unified All-in-One Pipeline (แปล Plugins UI Texts ก่อน แล้วต่อด้วย Game Dialogues ทันที)
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "chatgpt_translator_runner.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
