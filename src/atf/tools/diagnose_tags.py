#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dialogue Tag Diagnostic Tool
เครื่องมือตรวจสอบและพิมพ์แถวที่มี Speaker Tags ซ้ำซ้อน, แท็กเบิ้ล, หรือมีเศษขยะ '}' ให้เห็นข้อมูลจริง 100%
"""

import os
import sys
import re
import csv
import argparse


def diagnose_csv(csv_path: str, max_samples: int = 25):
    if not os.path.exists(csv_path):
        print(f"❌ ไม่พบไฟล์: {csv_path}")
        return

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("❌ ไฟล์ CSV ว่างเปล่า")
        return

    header = [h.strip().lower() for h in rows[0]]
    init_col = header.index("initial")
    orig_col = header.index("original")
    row_col = header.index("row") if "row" in header else None
    spk_col = header.index("speaker") if "speaker" in header else None

    # สแกนหาแถวที่มีลักษณะน่าสงสัย
    double_bracket_rows = []      # มี < หรือ [ มากกว่า 1 ตัว
    curly_bracket_near_tag_rows = [] # มี } อยู่ใกล้ tag
    duplicate_name_rows = []      # มีชื่อเดียวกันปรากฏซ้ำใน Initial

    tag_extract_regex = re.compile(r'[<\[【]([^>\]】]+)[>\]】]')

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            continue
        init_text = r[init_col].strip()
        orig_text = r[orig_col].strip() if orig_col < len(r) else ""
        row_id = r[row_col].strip() if row_col is not None and row_col < len(r) else str(idx)
        speaker = r[spk_col].strip() if spk_col is not None and spk_col < len(r) else ""

        if not init_text:
            continue

        # 1. ตรวจสอบแท็กทั้งหมดที่พบใน Initial
        tags = tag_extract_regex.findall(init_text)
        if len(tags) >= 2:
            # ดึงเฉพาะชื่อตัด : และ space
            clean_names = [re.sub(r'[^a-zA-Z0-9ก-๙]', '', t).lower() for t in tags]
            # ตรวจสอบว่ามีชื่อเดียวกันซ้ำหรือไม่
            has_dup_name = len(clean_names) != len(set(clean_names))
            
            double_bracket_rows.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": speaker,
                "tags": tags,
                "has_dup_name": has_dup_name,
                "orig": orig_text,
                "init": init_text
            })

            if has_dup_name:
                duplicate_name_rows.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": speaker,
                    "tags": tags,
                    "orig": orig_text,
                    "init": init_text
                })

        # 2. ตรวจสอบว่ามี } อยู่ใน Initial หรือไม่
        if "}" in init_text and ("<" in init_text or "[" in init_text):
            curly_bracket_near_tag_rows.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": speaker,
                "orig": orig_text,
                "init": init_text
            })

    print("\n" + "=" * 80)
    print("      ATF SPEAKER TAG & DUPLICATION DIAGNOSTIC REPORT      ")
    print("=" * 80)
    print(f"Target CSV: {csv_path}")
    print(f"Total Rows: {len(rows):,}")
    print("-" * 80)
    print(f"  • แถวที่มีแท็ก <...> หรือ [...] ตั้งแต่ 2 ตัวขึ้นไป:      {len(double_bracket_rows):,} แถว")
    print(f"  • ในจำนวนนี้ มีชื่อแท็กเดียวกันซ้ำซ้อนแน่นอน (Duplicate Tags): {len(duplicate_name_rows):,} แถว")
    print(f"  • แถวที่มีเครื่องหมาย '}}' ร่วมกับแท็ก:                 {len(curly_bracket_near_tag_rows):,} แถว")
    print("=" * 80)

    # แสดงตัวอย่าง Duplicate Name Tags
    if duplicate_name_rows:
        print(f"\n🔍 ตัวอย่างแถวที่พบ Duplicate Speaker Tags แน่นอน ({min(len(duplicate_name_rows), max_samples)} แถวแรก):")
        for ex in duplicate_name_rows[:max_samples]:
            print(f"  • [Row {ex['row_idx']} | ID {ex['row_id']}] Speaker: '{ex['speaker']}' Tags: {ex['tags']}")
            print(f"    ORIG: {repr(ex['orig'][:75])}")
            print(f"    INIT: {repr(ex['init'][:75])}")

    # แสดงตัวอย่าง Curly Brackets
    if curly_bracket_near_tag_rows:
        print(f"\n🔍 ตัวอย่างแถวที่มีเครื่องหมาย '}}' ({min(len(curly_bracket_near_tag_rows), 10)} แถวแรก):")
        for ex in curly_bracket_near_tag_rows[:10]:
            print(f"  • [Row {ex['row_idx']} | ID {ex['row_id']}] Speaker: '{ex['speaker']}'")
            print(f"    ORIG: {repr(ex['orig'][:75])}")
            print(f"    INIT: {repr(ex['init'][:75])}")


def main():
    parser = argparse.ArgumentParser(description="Diagnose Speaker Tags in CSV")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file")
    parser.add_argument("--limit", type=int, default=20, help="Max sample output")
    args = parser.parse_args()

    diagnose_csv(args.csv, args.limit)


if __name__ == "__main__":
    main()
