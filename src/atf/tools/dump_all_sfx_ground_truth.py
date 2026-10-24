#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Sound Effect Ground-Truth Dumper & Complete Dataset Extractor
================================================================
สกัดแถวทั้งหมดที่มีคำแทนเสียง (SFX) จากไฟล์งานจริงออกมาเป็น JSON ละเอียด 100%
เพื่อให้ AI Assistant สามารถเปิดอ่านและวิเคราะห์พฤติกรรมโครงสร้างจริงของทุกบรรทัดได้

ข้อมูลที่สกัด:
1. แถวที่ Original มี *...* ทุกแถว
2. แถวที่ Initial มี *...* ทุกแถว
3. แถวที่พบ Onomatopoeia ภาษาอังกฤษ
4. ความสัมพันธ์ระหว่าง Original SFX tokens และ Initial text
"""

import os
import sys
import re
import csv
import json
import argparse
from typing import Dict, List, Any

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

SFX_REGEX = re.compile(r'\*([^*]+)\*')


def dump_ground_truth(csv_path: str, output_json_path: str):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("   ATF SOUND EFFECT GROUND-TRUTH DUMPER (COMPLETE DATASET EXTRACTION)   ")
    print("=" * 95)
    print(f"Source CSV: {csv_path}")
    print(f"Output JSON: {output_json_path}")
    print("-" * 95)

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("❌ ไฟล์ CSV ว่างเปล่า")
        return

    header = rows[0]
    header_lower = [h.strip().lower() for h in header]

    init_col = header_lower.index("initial") if "initial" in header_lower else 1
    orig_col = header_lower.index("original") if "original" in header_lower else 0
    spk_col = header_lower.index("speaker") if "speaker" in header_lower else None
    row_col = header_lower.index("row") if "row" in header_lower else None

    dataset = []

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= max(orig_col, init_col):
            continue

        orig_val = r[orig_col]
        init_val = r[init_col]
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        orig_sfx = SFX_REGEX.findall(orig_val)
        init_sfx = SFX_REGEX.findall(init_val)

        # เก็บเฉพาะแถวที่มี *...* ใน Original หรือใน Initial
        if orig_sfx or init_sfx:
            dataset.append({
                "line_num": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "orig_sfx_tokens": orig_sfx,
                "init_sfx_tokens": init_sfx,
                "orig_text": orig_val,
                "init_text": init_val
            })

    os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as out_f:
        json.dump({
            "total_extracted_rows": len(dataset),
            "generated_at": str(sys.platform),
            "records": dataset
        }, out_f, ensure_ascii=False, indent=2)

    print(f"✅ สกัดข้อมูลแถวที่มีคำแทนเสียงสำเร็จทั้งหมด: {len(dataset):,} แถว")
    print(f"💾 บันทึกไฟล์ Ground-Truth JSON ที่:\n   👉 {output_json_path}")
    print("=" * 95)


def main():
    parser = argparse.ArgumentParser(description="ATF SFX Ground-Truth Dumper")
    parser.add_argument("--csv", type=str, required=True, help="Path to input CSV")
    parser.add_argument("--out", type=str, required=True, help="Path to output JSON")
    args = parser.parse_args()

    dump_ground_truth(args.csv, args.out)


if __name__ == "__main__":
    main()
