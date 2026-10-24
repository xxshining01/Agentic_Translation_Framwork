#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Sound Effect Coverage & Deep Census Diagnostic Tool
========================================================
เครื่องมือตรวจนับสำมะโนประชากรคำแทนเสียงและวินิจฉัยความครอบคลุมทั้ง 92,228 แถว

วัตถุประสงค์:
1. ไขข้อข้องใจ: ทำไมจาก 92,228 แถว ถึงพบคำแทนเสียง 1,412 แถว?
   - สำรวจจำนวนแถวที่มี *...* ใน Original
   - สำรวจจำนวนแถวที่มี Onomatopoeia ภาษาอังกฤษแต่ต้นฉบับ "ไม่ได้ใส่ดอกจันมาตั้งแต่แรก"
   - สำรวจจำนวนแถวที่เป็นบทสนทนาปกติ / เมนู / สคริปต์ระบบ
2. วินิจฉัย 5 แถวที่ Unresolved:
   - แสดงเนื้อหาเต็มของทั้ง 5 แถวเทียบกันระหว่าง Original vs Initial
   - วิเคราะห์เหตุผลที่จับคู่ไม่ได้
3. ตรวจสอบคำภาษาอังกฤษที่ลืมแปลตกค้างใน Initial (Untranslated SFX Artifacts เช่น *bzzt*)
"""

import os
import sys
import re
import csv
import json
import argparse
from typing import Dict, List, Any
from collections import Counter, defaultdict

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

SFX_REGEX = re.compile(r'\*([^*]+)\*')

# คำ Onomatopoeia ภาษาอังกฤษทั่วไปที่อาจปรากฏโดยไม่มีดอกจัน
COMMON_ENGLISH_SFX_KEYWORDS = [
    r'\bsigh(?:s|ed|ing)?\b',
    r'\bgasp(?:s|ed|ing)?\b',
    r'\bpant(?:s|ed|ing)?\b',
    r'\bchuckle(?:s|ed|ing)?\b',
    r'\bgiggle(?:s|ed|ing)?\b',
    r'\bmoan(?:s|ed|ing)?\b',
    r'\bgroan(?:s|ed|ing)?\b',
    r'\bwhimper(?:s|ed|ing)?\b',
    r'\bsob(?:s|bed|bing)?\b',
    r'\bscream(?:s|ed|ing)?\b',
    r'\bslur+p\b',
    r'\bfa+p\b',
    r'\bsque+lch\b',
    r'\bbz+t\b',
    r'\bslap\b',
    r'\bplap\b',
    r'\bthud\b',
    r'\bthump\b',
    r'\bgulp\b',
    r'\bwhoo?sh\b',
    r'\bshoosh\b',
    r'\bshiver(?:s|ed)?\b',
    r'\bclink\b',
    r'\bcreak\b',
    r'\brustle\b',
    r'\bsmack\b'
]
COMPILED_SFX_KEYWORDS = [re.compile(p, re.IGNORECASE) for p in COMMON_ENGLISH_SFX_KEYWORDS]


def run_sfx_census(csv_path: str):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("      ATF SOUND EFFECT COVERAGE & DEEP CENSUS DIAGNOSTIC SYSTEM      ")
    print("=" * 95)
    print(f"Target CSV: {csv_path}")
    print("Mode: 🔬 DEEP DIAGNOSTIC CENSUS (สำรวจความครอบคลุมคำแทนเสียงทั้งเกม)")
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

    total_rows = len(rows) - 1

    # หมวดหมู่การนับ
    orig_with_asterisks = []
    orig_no_asterisk_but_sfx_keyword = []
    init_untranslated_english_sfx = []
    orig_sfx_frequency = Counter()

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= max(orig_col, init_col):
            continue

        orig_val = r[orig_col]
        init_val = r[init_col]
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        # 1. ตรวจสอบดอกจัน *...* ใน Original
        orig_asterisks = SFX_REGEX.findall(orig_val)
        if orig_asterisks:
            orig_with_asterisks.append((idx, row_id, spk_val, orig_val, init_val, orig_asterisks))
            for ast in orig_asterisks:
                clean_k = ast.strip().strip(".").strip(",").strip("!").strip("?").strip("♥").lower()
                orig_sfx_frequency[clean_k] += 1
        else:
            # 2. ตรวจสอบ Onomatopoeia ที่ไม่มีดอกจันใน Original
            for pat in COMPILED_SFX_KEYWORDS:
                if pat.search(orig_val):
                    orig_no_asterisk_but_sfx_keyword.append((idx, row_id, spk_val, orig_val, init_val))
                    break

        # 3. ตรวจสอบคำภาษาอังกฤษที่อยู่ในดอกจันใน Initial (Untranslated English Artifacts เช่น *bzzt*)
        init_asterisks = SFX_REGEX.findall(init_val)
        for i_ast in init_asterisks:
            # ถ้าข้างในเป็นตัวอักษรภาษาอังกฤษล้วน เช่น *bzzt*, *slurp*, *sigh*
            if re.match(r'^[a-zA-Z\s\.\-♥!]+$', i_ast.strip()):
                init_untranslated_english_sfx.append((idx, row_id, spk_val, orig_val, init_val, i_ast))

    # -----------------------------------------------------------------
    # รายงานผลการวิเคราะห์สำมะโนประชากร
    # -----------------------------------------------------------------
    print(f"\n📊 ผลการสำมะโนประชากรคำแทนเสียง (จากไฟล์ทั้งหมด {total_rows:,} แถว):")
    print(f"  1. แถวที่ Original มีเครื่องหมายดอกจัน (*...*):                {len(orig_with_asterisks):,} แถว")
    print(f"     (คิดเป็น {len(orig_with_asterisks)/total_rows*100:.2f}% ของเนื้อหาทั้งเกม)")
    print(f"  2. แถวที่ Original มีคำคีย์เวิร์ดเสียง แต่ไม่มีดอกจันมาแต่แรก:      {len(orig_no_asterisk_but_sfx_keyword):,} แถว")
    print(f"  3. แถวที่พบคำภาษาอังกฤษค้างอยู่ในดอกจันใน Initial (ลืมแปล):      {len(init_untranslated_english_sfx):,} จุด")
    print("-" * 95)

    print("\n📈 25 อันดับคำแทนเสียงในดอกจัน (*...*) ที่พบบ่อยที่สุดในเกม:")
    for rank, (sfx_name, count) in enumerate(orig_sfx_frequency.most_common(25), start=1):
        print(f"   {rank:2d}. *{sfx_name}*: {count:,} ครั้ง")

    if init_untranslated_english_sfx:
        print(f"\n⚠️ ตัวอย่างคำภาษาอังกฤษตกค้างในช่อง Initial (ลืมแปล - แสดง 10 ตัวอย่างแรก):")
        for ex in init_untranslated_english_sfx[:10]:
            print(f"  • [Row {ex[0]} | ID {ex[1]} | Speaker: '{ex[2]}']:")
            print(f"    - คำอังกฤษตกค้าง: '*{ex[5]}*'")
            print(f"    - ORIGINAL: {repr(ex[3][:85])}")
            print(f"    - INITIAL:  {repr(ex[4][:85])}")
            print()

    if orig_no_asterisk_but_sfx_keyword:
        print(f"\n💡 ตัวอย่างแถวที่มีคำกริยา/เสียงภาษาอังกฤษ แต่ไม่มี *...* ครอบมาตั้งแต่ต้นฉบับ:")
        for ex in orig_no_asterisk_but_sfx_keyword[:5]:
            print(f"  • [Row {ex[0]} | ID {ex[1]} | Speaker: '{ex[2]}']:")
            print(f"    - ORIGINAL: {repr(ex[3][:85])}")
            print(f"    - INITIAL:  {repr(ex[4][:85])}")
            print()


def main():
    parser = argparse.ArgumentParser(description="ATF Sound Effect Coverage & Deep Census Diagnostic Tool")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file")
    args = parser.parse_args()

    run_sfx_census(args.csv)


if __name__ == "__main__":
    main()
