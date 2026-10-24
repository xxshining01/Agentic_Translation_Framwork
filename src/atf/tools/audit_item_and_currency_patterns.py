#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Item & Currency Quantity Pattern Inspector
เครื่องมือตรวจสอบและรวบรวมรูปแบบการเอ่ยถึงไอเทม/ค่าเงินในเกม (Quantity & Currency Syntax Audit)
ช่วยแยกแยะระหว่าง:
  - Pattern 1: [ตัวเลข] [ไอเทม]         (เช่น 20 หิน, 10 ไม้, 500 เหรียญ)
  - Pattern 2: [ไอเทม] [ตัวเลข] [ลักษณนาม] (เช่น หิน 20 ก้อน, ไม้ 10 ท่อน, กาแฟ 3 กระป๋อง)
  - Pattern 3: [ไอเทม] x[ตัวเลข]         (เช่น หิน x20, Gold x50)
  - Pattern 4: x[ตัวเลข] [ไอเทม]         (เช่น x20 หิน, x5 ปลา)
  - Pattern 5: System Notification Phrase (เช่น "ได้รับ 20 หินแล้ว", "ต้องการ หิน 20 ก้อน")
โดยไม่มีการแก้ไขไฟล์จริงแต่อย่างใด เพื่อให้ผู้ใช้สามารถตรวจทานและตัดสินใจรูปแบบมาตรฐานได้
"""

import os
import sys
import re
import csv
import argparse
from typing import List, Dict, Any, Set

# คำลักษณนามทั่วไปในภาษาไทย
CLASSIFIERS = [
    "ก้อน", "ชิ้น", "อัน", "ท่อน", "ขวด", "เหรียญ", "เล่ม", "แผ่น", "ใบ", "ดอก",
    "หัว", "ตัว", "กระป๋อง", "ถุง", "ฟอง", "ชุด", "กล่อง", "ม้วน", "แท่ง", "เม็ด"
]
CLASSIFIER_REGEX = "|".join(CLASSIFIERS)

# คำนำหน้าประเภท System / Quest
ACTION_PREFIXES = ["ได้รับ", "ได้", "สูญเสีย", "เสีย", "รวบรวม", "ต้องการ", "ส่งมอบ", "มอบ", "เก็บ", "ซื้อ", "ขาย", "ใช้"]
ACTION_REGEX = "|".join(ACTION_PREFIXES)

# คำบอกค่าเงิน / ทรัพยากรพื้นฐาน
COMMON_RESOURCES = [
    "หิน", "ไม้", "ทอง", "เงิน", "เหรียญ", "แร่", "ปลา", "เหยื่อ", "ยา", "เบ็ด",
    "gold", "g", "coin", "coins", "stone", "wood", "ore", "fish", "bait"
]


def load_known_items(workspace_root: str) -> Set[str]:
    """โหลดรายชื่อไอเทมภาษาไทยและอังกฤษจากคลังคำศัพท์"""
    items = set(COMMON_RESOURCES)
    
    # 1. โหลดจาก items_glossary_with_descriptions.csv
    csv_path = os.path.join(workspace_root, "data", "tlas", "items_glossary_with_descriptions.csv")
    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    th = (r.get("Item_Name_TH") or "").strip()
                    en = (r.get("Item_Name_EN") or "").strip()
                    if th: items.add(th.lower())
                    if en: items.add(en.lower())
        except Exception:
            pass

    # 2. โหลดจาก tlas_glossary.json
    json_path = os.path.join(workspace_root, "data", "tlas", "tlas_glossary.json")
    if os.path.exists(json_path):
        try:
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                gdata = json.load(f)
                for k, v in gdata.get("Items", {}).items():
                    items.add(k.lower())
                    if isinstance(v, dict) and v.get("th"):
                        items.add(v["th"].lower())
        except Exception:
            pass

    return items


def audit_item_patterns(csv_path: str, output_report: str = None):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    known_items = load_known_items(workspace_root)

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("ไฟล์ CSV ว่างเปล่า")

    header = [h.strip().lower() for h in rows[0]]
    init_col = header.index("initial")
    orig_col = header.index("original")
    speaker_col = header.index("speaker") if "speaker" in header else None
    role_col = header.index("role") if "role" in header else None
    row_col = header.index("row") if "row" in header else None

    # รายการผลลัพธ์
    detected_rows = []
    pattern_counts = {
        "PATTERN_1_NUMBER_FIRST": 0,    # [ตัวเลข] [ไอเทม] (เช่น 20 หิน)
        "PATTERN_2_CLASSIFIER": 0,      # [ไอเทม] [ตัวเลข] [ลักษณนาม] (เช่น หิน 20 ก้อน)
        "PATTERN_3_ITEM_X_NUM": 0,      # [ไอเทม] x[ตัวเลข] (เช่น หิน x20)
        "PATTERN_4_X_NUM_ITEM": 0,      # x[ตัวเลข] [ไอเทม] (เช่น x20 หิน)
        "PATTERN_5_NOTIFICATION": 0,    # ได้รับ/ต้องการ ...
    }

    # Regex สำหรับแต่ละ Pattern
    re_pat1 = re.compile(r'(?<![xX\*\d])\b(?P<num>\d+)\s*(?P<item>[ก-๙a-zA-Z]+)\b')
    re_pat2 = re.compile(rf'(?P<item>[ก-๙a-zA-Z]+)\s*(?P<num>\d+)\s*(?P<cls>{CLASSIFIER_REGEX})\b')
    re_pat3 = re.compile(r'(?P<item>[ก-๙a-zA-Z]+)\s*[xX*×]\s*(?P<num>\d+)')
    re_pat4 = re.compile(r'[xX*×]\s*(?P<num>\d+)\s*(?P<item>[ก-๙a-zA-Z]+)')
    re_action = re.compile(rf'(?:{ACTION_REGEX})\s+[^,\.\!\?\n]+', re.IGNORECASE)

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            continue

        init_text = r[init_col].strip()
        orig_text = r[orig_col].strip() if orig_col < len(r) else ""
        speaker = r[speaker_col].strip() if speaker_col is not None and speaker_col < len(r) else ""
        role = r[role_col].strip() if role_col is not None and role_col < len(r) else ""
        row_id = r[row_col].strip() if row_col is not None and row_col < len(r) else str(idx)

        if not init_text:
            continue

        found_patterns = []

        # 1. ตรวจจับ Pattern 3: [ไอเทม] x[ตัวเลข]
        for m in re_pat3.finditer(init_text):
            item = m.group("item")
            num = m.group("num")
            # กรองคำทั่วๆ ไป
            found_patterns.append({
                "type": "PATTERN_3_ITEM_X_NUM",
                "matched": m.group(0),
                "item": item,
                "desc": f"ไอเทมตามด้วย x: '{item} x{num}'"
            })
            pattern_counts["PATTERN_3_ITEM_X_NUM"] += 1

        # 2. ตรวจจับ Pattern 4: x[ตัวเลข] [ไอเทม]
        for m in re_pat4.finditer(init_text):
            item = m.group("item")
            num = m.group("num")
            found_patterns.append({
                "type": "PATTERN_4_X_NUM_ITEM",
                "matched": m.group(0),
                "item": item,
                "desc": f"x ตามด้วยไอเทม: 'x{num} {item}'"
            })
            pattern_counts["PATTERN_4_X_NUM_ITEM"] += 1

        # 3. ตรวจจับ Pattern 2: [ไอเทม] [ตัวเลข] [ลักษณนาม]
        for m in re_pat2.finditer(init_text):
            item = m.group("item")
            num = m.group("num")
            cls = m.group("cls")
            found_patterns.append({
                "type": "PATTERN_2_CLASSIFIER",
                "matched": m.group(0),
                "item": item,
                "desc": f"มีลักษณนาม: '{item} {num} {cls}'"
            })
            pattern_counts["PATTERN_2_CLASSIFIER"] += 1

        # 4. ตรวจจับ Pattern 1: [ตัวเลข] [ไอเทม] (กรองเฉพาะคำที่เป็นไอเทมหรือทรัพยากร)
        for m in re_pat1.finditer(init_text):
            num = m.group("num")
            item = m.group("item")
            item_clean = item.lower()
            # เช็คว่าตรงกับไอเทมที่รู้จัก หรือคำทรัพยากร เช่น หิน, ไม้, เหรียญ, ทอง
            is_item = (
                item_clean in known_items or
                any(r in item_clean for r in COMMON_RESOURCES)
            )
            # กรองกรณีตัวเลขบอกเวลา หรือเปอร์เซ็นต์
            if is_item and item_clean not in ["ปี", "วัน", "นาที", "โมง", "คน", "ครั้ง", "จุด", "ชั้น"]:
                found_patterns.append({
                    "type": "PATTERN_1_NUMBER_FIRST",
                    "matched": m.group(0),
                    "item": item,
                    "desc": f"ตัวเลขนำหน้าไอเทม: '{num} {item}'"
                })
                pattern_counts["PATTERN_1_NUMBER_FIRST"] += 1

        # 5. ตรวจจับข้อความ System / Notification ที่มีการเอ่ยถึงการได้รับ/ส่งมอบ
        if any(act in init_text for act in ACTION_PREFIXES) and re.search(r'\d+|[xX]\d+', init_text):
            m_act = re_action.search(init_text)
            if m_act:
                found_patterns.append({
                    "type": "PATTERN_5_NOTIFICATION",
                    "matched": m_act.group(0).strip(),
                    "item": "Notification Context",
                    "desc": f"ประโยคแจ้งเตือน: '{m_act.group(0).strip()}'"
                })
                pattern_counts["PATTERN_5_NOTIFICATION"] += 1

        if found_patterns:
            detected_rows.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": speaker,
                "role": role,
                "patterns": found_patterns,
                "original": orig_text,
                "initial": init_text
            })

    # รายงานผลบน Terminal
    print("\n" + "=" * 80)
    print("      ATF ITEM & CURRENCY QUANTITY PATTERN AUDIT REPORT      ")
    print("=" * 80)
    print(f"Target CSV: {csv_path}")
    print(f"Total Rows: {len(rows):,}")
    print(f"พบแถวที่มีการเอ่ยถึงไอเทม/ค่าเงิน: {len(detected_rows):,} แถว")
    print("-" * 80)
    print("📊 สถิติการใช้งานแต่ละรูปแบบ (Distribution):")
    print(f"  • Pattern 1 (ตัวเลขนำหน้าไอเทม เช่น '20 หิน', '500 เหรียญ'):    {pattern_counts['PATTERN_1_NUMBER_FIRST']:,} จุด")
    print(f"  • Pattern 2 (มีลักษณนามต่อท้าย เช่น 'หิน 20 ก้อน', 'ไม้ 10 ท่อน'): {pattern_counts['PATTERN_2_CLASSIFIER']:,} จุด")
    print(f"  • Pattern 3 (ไอเทมตามด้วย x เช่น 'หิน x20', 'Gold x50'):        {pattern_counts['PATTERN_3_ITEM_X_NUM']:,} จุด")
    print(f"  • Pattern 4 (x ตามด้วยไอเทม เช่น 'x20 หิน'):                    {pattern_counts['PATTERN_4_X_NUM_ITEM']:,} จุด")
    print(f"  • Pattern 5 (ประโยคแจ้งเตือน/เควส เช่น 'ได้รับ 20 หินแล้ว'):       {pattern_counts['PATTERN_5_NOTIFICATION']:,} จุด")
    print("-" * 80)

    # แสดงตัวอย่าง
    print("\n🔍 ตัวอย่างแต่ละ Pattern ที่พบในไฟล์จริง:")
    for p_type, p_name in [
        ("PATTERN_1_NUMBER_FIRST", "Pattern 1 (ตัวเลขนำหน้า เช่น '20 หิน')"),
        ("PATTERN_2_CLASSIFIER", "Pattern 2 (มีลักษณนาม เช่น 'หิน 20 ก้อน')"),
        ("PATTERN_3_ITEM_X_NUM", "Pattern 3 (ไอเทมตามด้วย x เช่น 'หิน x20')"),
        ("PATTERN_4_X_NUM_ITEM", "Pattern 4 (x นำหน้าไอเทม เช่น 'x20 หิน')"),
    ]:
        sample_count = 0
        print(f"\n  👉 {p_name}:")
        for row in detected_rows:
            matched_items = [p for p in row["patterns"] if p["type"] == p_type]
            if matched_items:
                for mi in matched_items:
                    print(f"     [Row {row['row_idx']} | ID {row['row_id']}]: {mi['desc']}")
                    print(f"       ORIG: {repr(row['original'][:65])}")
                    print(f"       INIT: {repr(row['initial'][:65])}")
                    sample_count += 1
                    if sample_count >= 3:
                        break
            if sample_count >= 3:
                break

    # ส่งออกตารางรายการทั้งหมดลง CSV
    if not output_report:
        output_report = os.path.join(os.path.dirname(csv_path), "audit_item_currency_patterns_report.csv")

    with open(output_report, "w", encoding="utf-8-sig", newline="") as rf:
        writer = csv.writer(rf)
        writer.writerow(["Row_Index", "Row_ID", "Speaker", "Role", "Pattern_Type", "Matched_Phrase", "Detected_Item", "Original", "Initial"])
        for row in detected_rows:
            for p in row["patterns"]:
                writer.writerow([
                    row["row_idx"],
                    row["row_id"],
                    row["speaker"],
                    row["role"],
                    p["type"],
                    p["matched"],
                    p["item"],
                    row["original"],
                    row["initial"]
                ])

    print(f"\n📋 ส่งออกตารางรายงานรูปแบบไอเทมทั้งหมด ({len(detected_rows):,} แถว) ไปที่:\n   👉 {output_report}")
    return detected_rows


def main():
    parser = argparse.ArgumentParser(description="ATF Item & Currency Quantity Pattern Inspector")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file")
    parser.add_argument("--output", type=str, default=None, help="Output CSV report path")
    args = parser.parse_args()

    audit_item_patterns(args.csv, args.output)


if __name__ == "__main__":
    main()
