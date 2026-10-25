#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Image & Phone Chat Localizer Launcher
เรียกใช้งาน src/atf/tools/image_chat_localizer.py อัตโนมัติ
"""
import os
import sys
import subprocess

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "image_chat_localizer.py")

if __name__ == "__main__":
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
