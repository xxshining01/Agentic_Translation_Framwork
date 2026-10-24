#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dialogue-Corroborated Place Entity Harvester Launcher
เรียกใช้งาน src/atf/tools/harvest_spoken_places.py
"""
import os
import sys

script_path = os.path.join(os.path.dirname(__file__), "src", "atf", "tools", "harvest_spoken_places.py")
if __name__ == "__main__":
    import subprocess
    cmd = [sys.executable, script_path] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
