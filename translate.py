#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Translation Runner Launcher (Quick Shortcut)
ส่งต่อไปยัง `python atf.py translate` อัตโนมัติ
"""
import sys
import subprocess

if __name__ == "__main__":
    cmd = [sys.executable, "atf.py", "translate"] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
