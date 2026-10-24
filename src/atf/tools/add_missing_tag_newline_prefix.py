#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Speaker Tag Prefix Restorer
สคริปต์สำหรับตรวจสอบและเติม \\n นำหน้า Speaker Tags ในช่อง Initial ให้ตรงตาม Original 100%
ทำงานเฉพาะเจาะจงเรื่องนี้เรื่องเดียว ไม่แตะต้องอักขระพิเศษหรือข้อความส่วนอื่นในประโยค
พร้อมระบบสำรองไฟล์ Backup อัตโนมัติก่อนบันทึกจริง
"""

import os
import sys
import re
import csv
import shutil
import argparse
from datetime import datetime
from typing import List, Dict, Tuple, Any

# Pattern ตรวจจับ Speaker Tag ที่ต้นข้อความของ Original
# รองรับทั้ง <Name:>, <Name>, [Name:], [Name]
ORIG_TAG_REGEX = re.compile(
    r'^(?P<lead>(?:\\n|\r?\n|\s)*)(?P<open>[<\[【])(?P<name>[^>\]】:]+)(?P<colon>:)?\s*(?P<close>[>\]】])',
    re.IGNORECASE
)

# Pattern ตรวจจับ Speaker Tag ที่ต้นข้อความของ Initial
INIT_TAG_REGEX = re.compile(
    r'^(?P<lead>(?:\\n|\r?\n|\s)*)(?P<open>[<\[【])(?P<name>[^>\]】:]+)(?P<colon>:)?\s*(?P<close>[>\]】])',
    re.IGNORECASE
)


def clean_name(raw: str) -> str:
    """ทำความสะอาดชื่อเพื่อเทียบความตรงกันแบบ Case-insensitive"""
    return re.sub(r'[^a-zA-Z0-9ก-๙]', '', raw).strip().lower()


def check_and_repair_prefix(orig_text: str, init_text: str) -> Tuple[str, bool, str]:
    """
    ตรวจสอบว่า Initial ขาด newline prefix หรือไม่เทียบกับ Original:
    - ถ้า Original ขึ้นต้นด้วยแท็กที่มี \\n หรือ \n นำหน้า
    - และ Initial ขึ้นต้นด้วยแท็กของตัวละครเดียวกัน แต่ขาด \\n หรือ \n นำหน้า
    - ให้เติม prefix ที่ถูกต้องลงไปที่หัวของ Initial ทันที
    """
    if not orig_text or not init_text:
        return init_text, False, ""

    m_orig = ORIG_TAG_REGEX.match(orig_text.lstrip())
    if not m_orig:
        return init_text, False, ""

    orig_lead = m_orig.group("lead")
    has_orig_newline = ("\\n" in orig_lead or "\n" in orig_lead)
    if not has_orig_newline:
        return init_text, False, ""

    orig_name_clean = clean_name(m_orig.group("name"))
    if not orig_name_clean:
        return init_text, False, ""

    m_init = INIT_TAG_REGEX.match(init_text.lstrip())
    if not m_init:
        return init_text, False, ""

    init_lead = m_init.group("lead")
    has_init_newline = ("\\n" in init_lead or "\n" in init_lead)
    init_name_clean = clean_name(m_init.group("name"))

    # เงื่อนไข: Initial ยังไม่มี newline prefix และเป็นแท็กของตัวละครเดียวกันกับ Original
    if not has_init_newline and orig_name_clean == init_name_clean:
        # ตัดสินใจใช้ prefix รูปแบบเดียวกับ Original (\n หรือ \\n)
        desired_prefix = "\\n" if "\\n" in orig_lead else "\n"
        repaired_text = desired_prefix + init_text.lstrip()
        detail = f"เติม '{desired_prefix}' นำหน้าแท็ก <{m_init.group('name')}>"
        return repaired_text, True, detail

    return init_text, False, ""


def process_file(csv_path: str, apply_fixes: bool = False):
    if not os.path.exists(csv_path):
        print(f"❌ ไม่พบไฟล์: {csv_path}")
        return

    print("\n" + "=" * 80)
    print("      ATF SPEAKER TAG PREFIX RESTORER (TARGETED TASK)      ")
    print("=" * 80)
    print(f"Target CSV: {csv_path}")
    print(f"Mode: {'🛠️ LIVE APPLY (สำรองไฟล์และบันทึกผลจริง)' if apply_fixes else '🔍 DRY-RUN (ตรวจสอบและนับยอดอย่างเดียว ยังไม่แก้ไขไฟล์)'}")
    print("-" * 80)

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("❌ ไฟล์ CSV ว่างเปล่า")
        return

    header = rows[0]
    header_lower = [h.strip().lower() for h in header]

    try:
        init_col = header_lower.index("initial")
        orig_col = header_lower.index("original")
    except ValueError as e:
        print(f"❌ ไม่พบคอลัมน์สำคัญ: {e}")
        return

    row_col = header_lower.index("row") if "row" in header_lower else None
    spk_col = header_lower.index("speaker") if "speaker" in header_lower else None

    repaired_items = []
    new_rows = [header]

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col or len(r) <= orig_col:
            new_rows.append(r)
            continue

        init_val = r[init_col]
        orig_val = r[orig_col]
        row_id = r[row_col] if row_col is not None and len(r) > row_col else str(idx)
        speaker = r[spk_col] if spk_col is not None and len(r) > spk_col else ""

        repaired_text, had_change, detail = check_and_repair_prefix(orig_val, init_val)

        if had_change:
            repaired_items.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": speaker,
                "detail": detail,
                "before": init_val,
                "after": repaired_text
            })
            new_r = list(r)
            new_r[init_col] = repaired_text
            new_rows.append(new_r)
        else:
            new_rows.append(r)

    print(f"📊 สรุปผลการตรวจสอบ:")
    print(f"  • จำนวนแถวทั้งหมดในไฟล์:                {len(rows):,} แถว")
    print(f"  • แถวที่ขาด '\\n' นำหน้าแท็ก (ต้องได้รับการเติม): {len(repaired_items):,} แถว")
    print("-" * 80)

    if repaired_items:
        print("\n🔍 ตัวอย่างแถวที่ต้องเติม '\\n' นำหน้าแท็ก (ตัวอย่าง 15 แถวแรก):")
        for ex in repaired_items[:15]:
            print(f"  • [Row {ex['row_idx']} | ID {ex['row_id']}] {ex['detail']}")
            print(f"    BEFORE: {repr(ex['before'][:70])}")
            print(f"    AFTER:  {repr(ex['after'][:70])}")

    # ดำเนินการสำรองไฟล์และบันทึกจริงเมื่อสั่ง --apply
    if apply_fixes:
        if len(repaired_items) == 0:
            print("\n✔ ทุกแถวมี prefix '\\n' ครบถ้วนสมบูรณ์แล้ว ไม่จำเป็นต้องแก้ไขใดๆ")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{csv_path}.backup_prefix_{ts}.csv"
        try:
            shutil.copy2(csv_path, backup_path)
            print(f"\n💾 [1/2] สำรองไฟล์ต้นฉบับสำเร็จที่:\n   👉 {backup_path}")
        except Exception as e:
            print(f"\n❌ การสำรองไฟล์ล้มเหลว ({e}) -> ยกเลิกการเขียนไฟล์เพื่อความปลอดภัย 100%")
            return

        try:
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(new_rows)
            print(f"💾 [2/2] บันทึกผลการเติม '\\n' ครบ {len(repaired_items):,} แถวลงไฟล์สำเร็จ:\n   👉 {csv_path}")
        except Exception as e:
            print(f"❌ เขียนไฟล์ไม่สำเร็จ: {e}")
    else:
        print(f"\n💡 นี่คือโหมด DRY-RUN ไฟล์จริงยังไม่ถูกเปลี่ยนแปลง")
        print(f"   หากตรวจสอบตัวอย่างด้านบนแล้วถูกต้อง ให้เติมพารามิเตอร์ '--apply' เพื่อบันทึกจริงพร้อมสำรองไฟล์")


def main():
    parser = argparse.ArgumentParser(description="ATF Speaker Tag Prefix Restorer")
    parser.add_argument("--csv", type=str, required=True, help="Path to target CSV file")
    parser.add_argument("--apply", action="store_true", help="Backup file and apply fixes live")
    args = parser.parse_args()

    process_file(args.csv, apply_fixes=args.apply)


if __name__ == "__main__":
    main()
