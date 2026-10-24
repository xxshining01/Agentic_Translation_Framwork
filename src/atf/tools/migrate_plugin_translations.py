#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Plugin Translation Migrator
สืบทอดคำแปลเดิมจาก data/plugins_texts.csv เข้าสู่ plugins_texts_v035.csv
โดยจับคู่ผ่าน Parameter Path และ Original Text เพื่อให้คงคำแปลเดิมไว้ 100%
และคัดแยกเฉพาะข้อความ UI ใหม่ที่ยังไม่ได้แปลออกมา
"""

import os
import sys
import csv
import json
from typing import Dict, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


def main():
    print("=" * 80)
    print("      ATF PLUGIN TRANSLATION MIGRATOR (LEGACY -> NEW PATCH)      ")
    print("=" * 80)

    # โหลด Manifest
    legacy_csv = os.path.join(WORKSPACE_ROOT, "data", "plugins_texts.csv")
    new_csv = None

    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            out_processed = manifest.get("output_processed_csv")
            if out_processed:
                candidate = os.path.join(os.path.dirname(out_processed), "plugins_texts_v035.csv")
                if os.path.exists(candidate):
                    new_csv = candidate

    if not new_csv:
        candidate2 = os.path.join(WORKSPACE_ROOT, "data", "plugins_texts_v035.csv")
        if os.path.exists(candidate2):
            new_csv = candidate2

    if not new_csv or not os.path.exists(new_csv):
        print("❌ ไม่พบไฟล์ plugins_texts_v035.csv กรุณารัน extract_plugins.py ก่อน")
        sys.exit(1)

    print(f"[*] ไฟล์ต้นทางคำแปลเดิม (Legacy): {legacy_csv}")
    print(f"[*] ไฟล์ปลายทางแพตช์ใหม่ (Target): {new_csv}\n")

    # 1. อ่านคำแปลเดิมจาก legacy_csv
    translations_by_path = {}
    translations_by_orig = {}

    if os.path.exists(legacy_csv):
        with open(legacy_csv, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 5:
                    orig = row[0].strip()
                    init = row[1].strip()
                    note = row[4].strip()
                    if init and init != orig:
                        if note:
                            translations_by_path[note] = init
                        translations_by_orig[orig] = init

    print(f"[1/2] โหลดคำแปลเดิมสำเร็จ: {len(translations_by_path):,} รายการตาม Path ({len(translations_by_orig):,} รายการตามข้อความ)")

    # 2. นำคำแปลเดิมใส่ลงใน new_csv
    migrated_count = 0
    untranslated_count = 0
    updated_rows = []

    with open(new_csv, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 5:
                orig = row[0].strip()
                note = row[4].strip()

                # ลองจับคู่ตาม Path ก่อน แล้วจึงตาม Original
                trans = translations_by_path.get(note) or translations_by_orig.get(orig)

                if trans:
                    row[1] = trans
                    migrated_count += 1
                else:
                    untranslated_count += 1

                updated_rows.append(row)

    # 3. เขียนทับไฟล์ใหม่
    with open(new_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(updated_rows)

    print("\n" + "=" * 80)
    print("                    MIGRATION SUMMARY REPORT                    ")
    print("=" * 80)
    print(f"📊 ข้อความทั้งหมดใน v0.35:          {len(updated_rows):,} ข้อความ")
    print(f"🟢 สืบทอดคำแปลเดิมสำเร็จ (Reused):  {migrated_count:,} ข้อความ")
    print(f"🟡 ข้อความใหม่ที่ต้องแปลเพิ่ม (New): {untranslated_count:,} ข้อความ")
    print(f"💾 อัปเดตคำแปลลงไฟล์เรียบร้อยแล้ว: {new_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
