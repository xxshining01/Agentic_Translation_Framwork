#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Game Scene & Event Boundary Tracer
วิเคราะห์และจัดกลุ่มฉาก (Scene Boundaries & Narrative Flow) จาก www/data/*.json
โดยอ่านค่าจาก data/project_manifest.json อัตโนมัติ และบันทึกลง data/tlas/rpgm_scenes_v5.json
"""

import os
import sys
import json
import shutil
from datetime import datetime
from typing import Dict, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")

# นำเข้า build_rpgm_timeline_v4 จาก testing files/rpgm_tracer_v4.py
sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "testing files"))
from rpgm_tracer_v4 import build_rpgm_timeline_v4


def main():
    print("=" * 80)
    print("      ATF RPG MAKER SCENE TRACER & BOUNDARY EXTRACTOR (v5)      ")
    print("=" * 80)

    # 1. โหลดข้อมูลจาก Manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ ไม่พบไฟล์ Manifest: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    data_dir = manifest.get("game_data_directory")
    if not data_dir or not os.path.exists(data_dir):
        print(f"❌ ไม่พบโฟลเดอร์ Data ของเกม: {data_dir}")
        sys.exit(1)

    output_path = os.path.join(WORKSPACE_ROOT, "data", "tlas", "rpgm_scenes_v5.json")
    out_dir = manifest.get("output_dir")
    if not out_dir and manifest.get("output_processed_csv"):
        out_dir = os.path.dirname(manifest.get("output_processed_csv"))

    targets_to_save = [output_path]
    if out_dir and os.path.exists(out_dir):
        targets_to_save.extend([
            os.path.join(out_dir, "tlas", "rpgm_scenes_v5.json"),
            os.path.join(out_dir, "rpgm_scenes_v5.json")
        ])

    print(f"[*] Game Data Directory: {data_dir}")
    print(f"[*] Target Scenes File:  {output_path}\n")

    # 2. สำรองไฟล์ Scene เดิมก่อน
    if os.path.exists(output_path):
        bak_file = output_path + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(output_path, bak_file)
        print(f"[*] สำรองไฟล์ Scene เดิมไว้ที่: {bak_file}\n")

    # 3. รัน State Emulation & Scene Tracing
    scenes = build_rpgm_timeline_v4(data_dir, output_path)

    # คัดลอกไปยังโฟลเดอร์ปลายทางที่ผู้ใช้ Browse ไว้
    for t_path in targets_to_save:
        if t_path != output_path:
            try:
                os.makedirs(os.path.dirname(t_path), exist_ok=True)
                shutil.copy2(output_path, t_path)
            except Exception as e:
                print(f"   [!] คัดลอกไปยัง {t_path} ไม่สำเร็จ: {e}")

    print("\n" + "=" * 80)
    print("                    SCENE TRACING SUMMARY REPORT                    ")
    print("=" * 80)
    print(f"🎬 จำนวนฉากที่สกัดและจัดกลุ่มสำเร็จ: {len(scenes):,} ฉาก")
    print(f"💾 บันทึกลงฐานข้อมูล Scene เรียบร้อยครบทุกตำแหน่ง:")
    for t_path in targets_to_save:
        print(f"   👉 {t_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
