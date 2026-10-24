#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Sound Effects (Onomatopoeia) Miner & Audit Engine
======================================================================
ระบบสแกน สำรวจ และสร้างพจนานุกรมคำแทนเสียง (Sound Effects / *...*) ครบวงจร:

หน้าที่หลัก:
1. สแกนหาคำแทนเสียงทั้งหมดใน Original ที่อยู่ในรูป *คำแทนเสียง* (Asterisks Enclosure)
2. ตรวจสอบในช่อง Initial เพื่อหาว่า:
   - แปลคำแทนเสียงออกมาโดยมี *...* ครอบถูกต้องหรือไม่
   - แถวไหนที่แปลคำแทนเสียงออกมาลอยๆ โดย "ไม่มี ** ครอบ" (Missing Asterisks)
3. รวบรวมความถี่และคำแปลภาษาไทยทั้งหมดที่เคยใช้สำหรับแต่ละคำแทนเสียง
4. สร้างไฟล์ข้อเสนอพจนานุกรมคำแทนเสียงมาตรฐาน (Sound Effects Dictionary Proposal)
   เพื่อให้สามารถนำไปล็อกและปรับแก้ให้เป็นมาตรฐานเดียวกัน 100% ทั่วทั้งเกม

ผลลัพธ์ที่สร้าง:
- sound_effects_dictionary_proposal.json: โครงสร้าง Dictionary รวบรวมคำแปลทั้งหมด + คำแนะนำมาตรฐาน
- sound_effects_audit_report.csv: ตารางแจกแจงทุกแถวที่พบคำแทนเสียง พร้อมสถานะว่าขาด ** หรือไม่
"""

import os
import sys
import re
import csv
import json
import argparse
from typing import Dict, List, Any, Tuple
from collections import Counter, defaultdict

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# Regex สกัดคำแทนเสียงที่อยู่ในรูป *...*
# ดักจับข้อความในดอกจันความยาว 1 - 60 ตัวอักษร
SFX_REGEX = re.compile(r'\*([^*]+)\*')


def clean_sfx_text(sfx: str) -> str:
    """ทำความสะอาดคำแทนเสียง ตัดจุดไข่ปลา เครื่องหมายวรรคตอนท้ายคำ และ whitespace"""
    c = sfx.strip().rstrip(".").rstrip(",").rstrip("!").rstrip("?").rstrip("-").strip()
    return c


def is_valid_sfx(sfx_raw: str) -> bool:
    """กรองข้อความที่ไม่น่าใช่คำแทนเสียง เช่น * ตัวเดียว หรือสูตรคำนวณ"""
    c = sfx_raw.strip()
    if not c or len(c) > 60:
        return False
    # ต้องไม่ใช่ tag หรือโค้ดตัวเลขล้วน
    if re.match(r'^\d+$', c):
        return False
    return True


def audit_sound_effects(csv_path: str, export_csv: str = None, export_json: str = None) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("      ATF SOUND EFFECTS (ONOMATOPOEIA) MINER & AUDIT ENGINE      ")
    print("=" * 95)
    print(f"Target CSV: {csv_path}")
    print(f"Mode: 🔍 READ-ONLY CENSUS (สำรวจคำแทนเสียง *...* และตรวจหาจุดที่ขาด **)")
    print("-" * 95)

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("❌ ไฟล์ CSV ว่างเปล่า")
        return {}

    header = rows[0]
    header_lower = [h.strip().lower() for h in header]

    init_col = header_lower.index("initial") if "initial" in header_lower else 1
    orig_col = header_lower.index("original") if "original" in header_lower else 0
    spk_col = header_lower.index("speaker") if "speaker" in header_lower else None
    row_col = header_lower.index("row") if "row" in header_lower else None

    # โครงสร้างเก็บข้อมูล
    # sfx_map[clean_en_sfx] = { "count": X, "translations": Counter(), "missing_asterisk_rows": [] }
    sfx_catalog = defaultdict(lambda: {
        "raw_forms": Counter(),
        "translations_with_asterisk": Counter(),
        "total_occurrences": 0,
        "rows_with_asterisk": [],
        "rows_missing_asterisk": []
    })

    total_orig_sfx_rows = 0
    rows_with_asterisk_count = 0
    rows_missing_asterisk_count = 0

    detailed_report_rows = []

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            continue

        init_val = r[init_col]
        orig_val = r[orig_col] if orig_col < len(r) else ""
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        if not orig_val:
            continue

        # สกัดคำแทนเสียงทั้งหมดใน Original
        orig_matches = SFX_REGEX.findall(orig_val)
        valid_orig_sfx = [m.strip() for m in orig_matches if is_valid_sfx(m)]

        if not valid_orig_sfx:
            continue

        total_orig_sfx_rows += 1

        # สกัดคำในดอกจันจาก Initial
        init_matches = SFX_REGEX.findall(init_val) if init_val else []
        valid_init_sfx = [m.strip() for m in init_matches if is_valid_sfx(m)]

        has_asterisk_in_init = len(valid_init_sfx) > 0

        if has_asterisk_in_init:
            rows_with_asterisk_count += 1
            status = "HAS_ASTERISKS"
        else:
            rows_missing_asterisk_count += 1
            status = "MISSING_ASTERISKS"

        for orig_sfx in valid_orig_sfx:
            clean_en = clean_sfx_text(orig_sfx).lower()
            sfx_entry = sfx_catalog[clean_en]
            sfx_entry["total_occurrences"] += 1
            sfx_entry["raw_forms"][orig_sfx] += 1

            if has_asterisk_in_init:
                for th_sfx in valid_init_sfx:
                    sfx_entry["translations_with_asterisk"][f"*{th_sfx}*"] += 1
                sfx_entry["rows_with_asterisk"].append(idx)
            else:
                sfx_entry["rows_missing_asterisk"].append(idx)

        # บันทึกรายละเอียดลงรายงาน
        detailed_report_rows.append({
            "row_idx": idx,
            "row_id": row_id,
            "speaker": spk_val,
            "status": status,
            "orig_sfx": " | ".join([f"*{x}*" for x in valid_orig_sfx]),
            "init_sfx_found": " | ".join([f"*{x}*" for x in valid_init_sfx]) if valid_init_sfx else "(ไม่มีดอกจันครอบ)",
            "original": orig_val,
            "initial": init_val
        })

    # -----------------------------------------------------------------
    # สรุปสถิติภาพรวม
    # -----------------------------------------------------------------
    print(f"\n📊 สรุปผลการสแกนคำแทนเสียง (*...*) ทั้งหมด ({len(rows):,} แถว):")
    print(f"  • แถวที่มีคำแทนเสียงใน Original:              {total_orig_sfx_rows:,} แถว")
    print(f"  • แถวที่ Initial มีดอกจันครอบ (*...*):        {rows_with_asterisk_count:,} แถว")
    print(f"  • ⚠️ แถวที่คำแปล 'ขาดดอกจันครอบ' (Missing **):  {rows_missing_asterisk_count:,} แถว")
    print(f"  • จำนวนคำแทนเสียงภาษาอังกฤษที่ไม่ซ้ำกัน:       {len(sfx_catalog):,} คำ")
    print("-" * 95)

    # จัดอันดับคำแทนเสียงที่พบบ่อยที่สุด
    sorted_sfx = sorted(sfx_catalog.items(), key=lambda x: x[1]["total_occurrences"], reverse=True)

    print("\n🏆 ลำดับคำแทนเสียงที่พบบ่อยที่สุด พร้อมคำแปลที่เคยใช้ (Top 25):")
    print(f"{'Sound Effect (EN)':<25} | {'จำนวนครั้ง':<10} | {'ขาด **':<8} | คำแปลที่พบส่วนใหญ่")
    print("-" * 95)

    dictionary_proposal = {}

    for en_word, data in sorted_sfx:
        top_trans = data["translations_with_asterisk"].most_common(3)
        trans_preview = ", ".join([f"{t[0]} ({t[1]})" for t in top_trans]) if top_trans else "(ยังไม่เคยครอบดอกจัน)"
        missing_cnt = len(data["rows_missing_asterisk"])

        # กำหนดคำแนะนำมาตรฐาน (Suggested Standard) จากคำที่ใช้บ่อยสุด
        suggested = top_trans[0][0] if top_trans else f"*{en_word}*"

        dictionary_proposal[en_word] = {
            "english_canonical": en_word,
            "total_occurrences": data["total_occurrences"],
            "missing_asterisk_count": missing_cnt,
            "suggested_thai_standard": suggested,
            "all_translations_found": dict(data["translations_with_asterisk"]),
            "sample_missing_rows": data["rows_missing_asterisk"][:10]
        }

    for en_word, data in sorted_sfx[:25]:
        top_trans = data["translations_with_asterisk"].most_common(3)
        trans_preview = ", ".join([f"{t[0]} ({t[1]})" for t in top_trans]) if top_trans else "(ยังไม่เคยครอบดอกจัน)"
        missing_cnt = len(data["rows_missing_asterisk"])
        print(f"*{en_word}*".ljust(25) + f" | {data['total_occurrences']:<10} | {missing_cnt:<8} | {trans_preview}")

    print("-" * 95)

    # แสดงตัวอย่างแถวที่ตกหล่นดอกจัน (Missing Asterisks)
    missing_samples = [r for r in detailed_report_rows if r["status"] == "MISSING_ASTERISKS"]
    if missing_samples:
        print(f"\n🔍 ตัวอย่างแถวที่แปลคำแทนเสียงออกมาโดย 'ไม่มี ** ครอบ' (แสดง 10 แถวแรก):")
        for s in missing_samples[:10]:
            print(f"  • [Row {s['row_idx']} | ID {s['row_id']} | Speaker: '{s['speaker']}']:")
            print(f"    - คำแทนเสียงใน Original: {s['orig_sfx']}")
            print(f"    - ORIGINAL: {repr(s['original'][:85])}")
            print(f"    - INITIAL:  {repr(s['initial'][:85])}")
            print()

    # -----------------------------------------------------------------
    # Export ผลลัพธ์
    # -----------------------------------------------------------------
    # 1. Export JSON Proposal Dictionary
    json_path = export_json or "sound_effects_dictionary_proposal.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dictionary_proposal, f, ensure_ascii=False, indent=2)
    print(f"💾 บันทึกโครงร่าง Dictionary ข้อเสนอมาตรฐานคำแทนเสียงไปที่:\n   👉 {json_path}")

    # 2. Export Detailed CSV Report
    csv_out_path = export_csv or "sound_effects_audit_report.csv"
    with open(csv_out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Row_Index", "Row_ID", "Speaker", "Status", "Original_SFX", "Initial_SFX_Found", "Original_Text", "Initial_Text"])
        for r in detailed_report_rows:
            writer.writerow([
                str(r["row_idx"]),
                str(r["row_id"]),
                r["speaker"],
                r["status"],
                r["orig_sfx"],
                r["init_sfx_found"],
                r["original"],
                r["initial"]
            ])
    print(f"💾 ส่งออกตารางแจกแจงทุกแถว ({len(detailed_report_rows):,} แถว) ไปที่:\n   👉 {csv_out_path}")

    return {
        "total_orig_sfx_rows": total_orig_sfx_rows,
        "rows_with_asterisks": rows_with_asterisk_count,
        "rows_missing_asterisks": rows_missing_asterisk_count,
        "unique_sfx_count": len(sfx_catalog),
        "dictionary_proposal": dictionary_proposal
    }


def main():
    parser = argparse.ArgumentParser(description="ATF Sound Effects Miner & Audit Engine")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file to audit")
    parser.add_argument("--export-csv", type=str, default="sound_effects_audit_report.csv", help="Path to export CSV report")
    parser.add_argument("--export-json", type=str, default="sound_effects_dictionary_proposal.json", help="Path to export JSON dictionary")
    args = parser.parse_args()

    audit_sound_effects(args.csv, export_csv=args.export_csv, export_json=args.export_json)


if __name__ == "__main__":
    main()
