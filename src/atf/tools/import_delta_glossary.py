#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Delta Glossary Importer (ADR-020 / ADR-023 Compliant)
นำเข้าคำแปลไทยจาก delta_glossary_review.csv (Items, Weapons, Armors, Characters)
และ harvested_spoken_places.csv (Spoken Places) ที่ผู้ใช้ตรวจทาน/แปลแล้ว
กลับเข้าสู่ tlas_glossary.json ของโปรเจกต์อย่างปลอดภัย พร้อมสำรองไฟล์เดิมอัตโนมัติ
"""

import os
import sys
import json
import csv
import shutil
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


def main():
    print("=" * 80)
    print("         ATF MASTER GLOSSARY COMPILER & IMPORTER (CSV -> JSON)         ")
    print("=" * 80)

    # 1. ค้นหาไฟล์จาก Manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ ไม่พบไฟล์ Manifest: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    glossary_json = manifest.get("legacy_glossary_json")
    output_processed_csv = manifest.get("output_processed_csv")

    if not glossary_json or not os.path.exists(glossary_json):
        print(f"❌ ไม่พบไฟล์ tlas_glossary.json: {glossary_json}")
        sys.exit(1)

    # ค้นหาไฟล์ตารางที่พร้อมนำเข้า
    csv_files_to_import = []
    out_dir = os.path.dirname(output_processed_csv) if output_processed_csv else os.path.join(WORKSPACE_ROOT, "data")
    
    # 1. delta_glossary_review.csv (จากรอบแรกที่ผู้ใช้แปล Items, Weapons, Armors, Characters)
    for cand in [os.path.join(out_dir, "delta_glossary_review.csv"), os.path.join(WORKSPACE_ROOT, "data", "delta_glossary_review.csv")]:
        if os.path.exists(cand) and cand not in csv_files_to_import:
            csv_files_to_import.append(cand)
            break

    # 2. harvested_spoken_places.csv (จากรอบสกัดสถานที่บทสนทนาสะอาด ADR-023)
    for cand in [os.path.join(out_dir, "harvested_spoken_places.csv"), os.path.join(WORKSPACE_ROOT, "data", "harvested_spoken_places.csv")]:
        if os.path.exists(cand) and cand not in csv_files_to_import:
            csv_files_to_import.append(cand)
            break

    if not csv_files_to_import:
        print("❌ ไม่พบไฟล์ delta_glossary_review.csv หรือ harvested_spoken_places.csv")
        sys.exit(1)

    has_harvested_places = any("harvested_spoken_places" in f for f in csv_files_to_import)

    print(f"[*] พบไฟล์ Spreadsheet สำหรับนำเข้า: {len(csv_files_to_import)} ไฟล์")
    for fpath in csv_files_to_import:
        print(f"   • {fpath}")
    print(f"[*] ไฟล์ปลายทาง Master Glossary:    {glossary_json}\n")

    # 2. อ่านไฟล์ CSV ที่ผู้ใช้ตรวจแล้ว
    imported_terms = {}
    for csv_file in csv_files_to_import:
        is_delta_review = "delta_glossary_review" in csv_file
        with open(csv_file, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                orig = row.get("Original_EN", "").strip()
                init = row.get("Initial_TH", "").strip()
                cat = row.get("Category", "").strip()
                tid = row.get("ID", "").strip()

                if orig:
                    # หากมีไฟล์ harvested_spoken_places ให้ข้ามหมวด Places จาก delta_glossary_review
                    # เพื่อใช้เฉพาะสถานที่ที่สะอาดบริสุทธิ์จากบทสนทนาจริง ไม่ให้ขยะรหัสเทคนิคหลุดเข้าไป
                    if is_delta_review and has_harvested_places and cat == "Places":
                        continue

                    imported_terms[(cat, orig)] = {
                        "orig": orig,
                        "th": init if init else orig,
                        "cat": cat,
                        "id": tid
                    }

    print(f"[1/3] อ่านและรวมคำศัพท์ที่ไม่ซ้ำกันจากตารางสำเร็จ: {len(imported_terms):,} รายการ")

    # 3. สำรองไฟล์ Glossary เดิมก่อนแบบ Atomic
    bak_path = glossary_json + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(glossary_json, bak_path)
    print(f"[2/3] สำรองไฟล์เดิมไว้ที่: {bak_path}")

    # 4. โหลดและควบรวมเข้า Glossary JSON
    with open(glossary_json, "r", encoding="utf-8") as f:
        glossary_data = json.load(f)

    added_count = 0
    updated_count = 0
    cat_summary = defaultdict(lambda: {"added": 0, "updated": 0})

    for item in imported_terms.values():
        cat = item["cat"]
        orig = item["orig"]
        th = item["th"]

        # จัดลงหมวดหมู่ที่เหมาะสมใน Glossary
        target_cat = cat
        if cat in ["Weapons", "Armors"]:
            target_cat = "Items"  # ใน RPG Maker Weapons/Armors รวมอยู่ในกลุ่ม Items/Equipment

        if target_cat not in glossary_data:
            glossary_data[target_cat] = {}

        if orig in glossary_data[target_cat]:
            glossary_data[target_cat][orig]["th"] = th
            updated_count += 1
            cat_summary[target_cat]["updated"] += 1
        else:
            item_type = cat[:-1] if cat.endswith("s") else cat
            glossary_data[target_cat][orig] = {
                "th": th,
                "type": item_type,
                "enforce": True
            }
            if item.get("id"):
                glossary_data[target_cat][orig]["id"] = item["id"]
            added_count += 1
            cat_summary[target_cat]["added"] += 1

    # 5. บันทึกไฟล์ JSON ทั้งในโปรเจกต์เดิม และโฟลเดอร์ปลายทางที่ผู้ใช้ Browse ไว้
    targets_to_save = [glossary_json]
    
    if out_dir and os.path.exists(out_dir):
        # โฟลเดอร์แพตช์ปลายทาง (ทั้งแบบ New folder\tlas\ และ New folder\ ตรงๆ)
        target_patch_tlas = os.path.join(out_dir, "tlas", "tlas_glossary.json")
        target_patch_root = os.path.join(out_dir, "tlas_glossary.json")
        targets_to_save.extend([target_patch_tlas, target_patch_root])

    for t_path in targets_to_save:
        try:
            os.makedirs(os.path.dirname(t_path), exist_ok=True)
            with open(t_path, "w", encoding="utf-8") as f:
                json.dump(glossary_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   [!] คำเตือน: บันทึกลง {t_path} ไม่สำเร็จ: {e}")

    print("\n" + "=" * 80)
    print("                    IMPORT SUMMARY REPORT                    ")
    print("=" * 80)
    print(f"🟢 เพิ่มคำศัพท์ใหม่เข้าสู่ Glossary:  {added_count:,} รายการ")
    print(f"🔄 อัปเดตคำแปลคำศัพท์เดิม:           {updated_count:,} รายการ")
    print("-" * 80)
    print("📊 รายละเอียดสรุปแยกตามหมวดหมู่:")
    for c_name, stat in sorted(cat_summary.items()):
        print(f"   • {c_name:<14}: เพิ่มใหม่ {stat['added']:>3} คำ | อัปเดต {stat['updated']:>3} คำ")
    print("-" * 80)
    print(f"💾 รวมเข้าสู่ Master Glossary สำเร็จครบทุกตำแหน่ง:")
    for t_path in targets_to_save:
        print(f"   👉 {t_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
