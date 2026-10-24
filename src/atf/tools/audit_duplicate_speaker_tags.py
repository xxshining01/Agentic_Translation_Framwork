#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Master Speaker Tag & Control Code Anomaly Auditor (v3.0 Comprehensive Edition)
==================================================================================
ระบบสำรวจและตรวจสอบความผิดปกติของ Speaker Tags และ Control Codes ครบวงจร:

1. [CHECK 1: Bilingual & Multi-Speaker Collision]
   - แท็กผู้พูดซ้อนกัน 2 ภาษา หรือ 2 กล่องในเซลล์เดียว เช่น:
     <ลูกค้า:> <Customer:>, <นักเลง 1:> <Trug 1:>, <อันธพาล:><Thug:>
   - ตรวจจับเมื่อ Original มี 1 แท็ก แต่ Initial ดันมีแท็กผู้พูด >= 2 แท็ก

2. [CHECK 2: Corrupted Escape Codes Wrapped in XML (<\\.>)]
   - โค้ดควบคุม RPG Maker (เช่น \\., \\!, \\^, \\|) ที่ถูกครอบด้วย <> ผิดพลาด
   - ตัวอย่าง: <\\.>, <\\^>, <\\!>, <\\|> (เช่น แถว 89266, 89282)

3. [CHECK 3: Identical Speaker Tag Duplication]
   - แท็กตัวละครเดียวกันซ้ำซ้อน เช่น \\n<Shion:>\\n<Shion:>, <Shion><Shion>

4. [CHECK 4: Speaker Translation Glossary Mismatch]
   - ตรวจสอบชื่อตัวละครในแท็ก Initial เทียบกับ Master Glossary (tlas_glossary.json)
   - เช่น Original เป็น Thug (Glossary = 'อันธพาล') แต่แปลเป็น 'นักเลง'

5. [CHECK 5: Tail Control Code Mutation / Corruption]
   - ตรวจสอบโค้ดควบคุมท้ายประโยค เช่น \\.\\.\\.\\^ กลายเป็น \\^\\.\\.\\.\\.

คุณสมบัติ:
- READ-ONLY 100%: สำรวจและรายงานผลเท่านั้น ไม่มีการแก้ไขหรือเขียนทับไฟล์ CSV ต้นฉบับ
- Export รายงานสรุปเป็น CSV แยกตามประเภทความผิดปกติอย่างชัดเจน
"""

import os
import sys
import re
import csv
import json
import argparse
from typing import Dict, List, Any, Tuple, Optional
from collections import Counter, defaultdict

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# แท็กระบบ/โค้ดควบคุมมาตรฐานที่ไม่ใช่ Speaker Tag
SYSTEM_TAGS = {
    "color", "/color", "font", "/font", "icon", "/icon",
    "pause_quarter", "pause_half", "pause_second",
    "wait_input", "stop_show_fast", "bold", "/bold",
    "italic", "/italic", "speed"
}

# Regex ตรวจจับเศษซากโค้ดควบคุมที่ถูกครอบด้วย <> ผิดพลาด เช่น <\.>, <\!>, <\^>, <\|>, <\>
CORRUPTED_ESCAPE_REGEX = re.compile(r'<\\?[\.\|\!\^\>\<][^>]*>', re.IGNORECASE)

# Regex สกัดแท็ก <...> ทั้งหมด
TAG_FINDER_REGEX = re.compile(r'<([^>]+)>')


def load_master_glossary(glossary_path: str = None) -> Dict[str, str]:
    """โหลด Glossary จาก tlas_glossary.json เพื่อใช้ตรวจสอบคำแปล Speaker ที่ถูกต้อง"""
    if not glossary_path:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        glossary_path = os.path.join(base_dir, "data", "tlas", "tlas_glossary.json")

    mapping = {}
    if not os.path.exists(glossary_path):
        return mapping

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chars = data.get("Characters", {})
        for name, info in chars.items():
            th = info.get("th", "").strip()
            if th:
                mapping[name.lower()] = th
                # บันทึก aliases
                aliases = info.get("aliases", [])
                if isinstance(aliases, list):
                    for a in aliases:
                        if isinstance(a, dict) and a.get("name"):
                            mapping[a["name"].lower()] = a.get("th", th)
                        elif isinstance(a, str):
                            mapping[a.lower()] = th
    except Exception as e:
        print(f"⚠️ คำเตือน: ไม่สามารถโหลด Glossary: {e}")

    return mapping


def clean_speaker_name(tag_inner: str) -> str:
    """ล้างโค้ด RPG Maker, เครื่องหมาย colon, เศษ space ออก ให้เหลือชื่อตัวละครที่แท้จริง"""
    if not tag_inner:
        return ""
    # ตัดโค้ด \C[27], \fb, \fi, \I[1]
    name = re.sub(r'\\[A-Za-z]+(?:\[\d+\])?', '', tag_inner)
    # ตัด colon, เครื่องหมายคำพูด, เศษวงเล็บปีกกา
    name = name.replace(':', '').replace('}', '').replace('{', '').strip()
    return name


def is_system_or_formatting_tag(clean_name: str) -> bool:
    """ตรวจสอบว่าเป็นแท็กระบบหรือไม่"""
    c = clean_name.lower().strip()
    if not c:
        return True
    if c in SYSTEM_TAGS:
        return True
    if c.startswith("color") or c.startswith("/color"):
        return True
    if c.startswith("font") or c.startswith("/font"):
        return True
    if c.startswith("icon") or c.startswith("/icon"):
        return True
    # ตรวจว่าเป็นเศษโค้ด \. หรือ \^ หรือไม่
    if re.match(r'^[\\\.\|\!\^\>\<]+$', c):
        return True
    return False


def extract_speaker_tags_from_text(text: str) -> List[Tuple[str, str, int, int, bool]]:
    """
    สกัดแท็กที่เป็นไปได้ว่าเป็น Speaker Tag ทั้งหมด:
    Returns: List of (full_tag, clean_name, start_idx, end_idx, has_colon)
    """
    if not text:
        return []

    results = []
    for m in TAG_FINDER_REGEX.finditer(text):
        full_tag = m.group(0)
        inner = m.group(1).strip()

        # ตรวจว่าเป็น Corrupted Escape หรือไม่ (ถ้าใช่ ให้ข้าม ไม่นับเป็น speaker tag)
        if re.match(r'^[\\\/]?[\.\|\!\^\>\<]', inner):
            continue

        clean_name = clean_speaker_name(inner)
        if not clean_name or is_system_or_formatting_tag(clean_name):
            continue

        has_colon = ":" in inner
        results.append((full_tag, clean_name, m.start(), m.end(), has_colon))

    return results


def audit_master_anomalies(csv_path: str, export_csv: str = None) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    glossary_map = load_master_glossary()

    print("=" * 90)
    print("   ATF MASTER SPEAKER TAG & CONTROL CODE ANOMALY AUDITOR (COMPREHENSIVE)   ")
    print("=" * 90)
    print(f"Target File: {csv_path}")
    print(f"Glossary Loaded: {len(glossary_map):,} character mappings")
    print(f"Mode: 🔍 READ-ONLY SURVEY (สำรวจและรายงานผลเท่านั้น)")
    print("-" * 90)

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

    # รายการความผิดปกติแยกตามประเภท
    violations = []
    cat_counts = Counter()

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            continue

        init_val = r[init_col]
        orig_val = r[orig_col] if orig_col < len(r) else ""
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        if not init_val:
            continue

        # -------------------------------------------------------------
        # 1. CHECK: Corrupted Escape Codes Wrapped in XML (<\\.>, <\\!>, etc.)
        # -------------------------------------------------------------
        corrupted_escapes = CORRUPTED_ESCAPE_REGEX.findall(init_val)
        if corrupted_escapes:
            violations.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "CORRUPTED_ESCAPE_CODE",
                "severity": "CRITICAL",
                "detected": ", ".join(corrupted_escapes),
                "issue_desc": f"พบโค้ดควบคุมถูกครอบด้วย <> ผิดพลาด: {corrupted_escapes}",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["CORRUPTED_ESCAPE_CODE"] += 1

        # -------------------------------------------------------------
        # 2. CHECK: Speaker Tags Extraction & Collision
        # -------------------------------------------------------------
        orig_spk_tags = extract_speaker_tags_from_text(orig_val)
        init_spk_tags = extract_speaker_tags_from_text(init_val)

        orig_count = len(orig_spk_tags)
        init_count = len(init_spk_tags)

        # 2.1 Bilingual or Multi-Speaker Collision (เช่น <ลูกค้า:> <Customer:>)
        # เงื่อนไข: Initial มี Speaker Tag >= 2 ตัว ในขณะที่ Original มี <= 1 ตัว
        if init_count >= 2 and orig_count <= 1:
            # ตรวจสอบว่าเป็นชื่อเดียวกัน หรือคนละชื่อ (เช่น ภาษาไทย + ภาษาอังกฤษ)
            names_in_init = [t[1] for t in init_spk_tags]
            tag_strings = [t[0] for t in init_spk_tags]
            is_same_name = len(set(n.lower() for n in names_in_init)) == 1

            sub_cat = "SAME_SPEAKER_DUP" if is_same_name else "BILINGUAL_MULTI_SPEAKER_COLLISION"
            desc = (
                f"แท็กชื่อเดียวกันเบิ้ลซ้ำ ({tag_strings})"
                if is_same_name
                else f"แท็กซ้อนกันต่างภาษา/ต่างชื่อ ({tag_strings})"
            )

            violations.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": sub_cat,
                "severity": "FATAL",
                "detected": " | ".join(tag_strings),
                "issue_desc": desc,
                "original": orig_val,
                "initial": init_val
            })
            cat_counts[sub_cat] += 1

        # 2.2 Case: Original มี 0 แต่ Initial มี 1 แท็กที่ซ้ำในตัวเอง หรือเบิ้ล
        elif orig_count > 1 and init_count > orig_count:
            tag_strings = [t[0] for t in init_spk_tags]
            violations.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "EXCESS_SPEAKER_TAGS",
                "severity": "WARNING",
                "detected": " | ".join(tag_strings),
                "issue_desc": f"Original มี {orig_count} แท็ก แต่ Initial มี {init_count} แท็ก",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["EXCESS_SPEAKER_TAGS"] += 1

        # -------------------------------------------------------------
        # 3. CHECK: Glossary Mismatch for Speaker Name (เช่น Thug -> นักเลง แทนที่จะเป็น อันธพาล)
        # -------------------------------------------------------------
        if orig_spk_tags and init_spk_tags:
            orig_name_clean = orig_spk_tags[0][1].strip().lower()
            # ตัดเลขท้าย เช่น thug 1 -> thug
            orig_base = re.sub(r'\s*\d+$', '', orig_name_clean)

            if orig_base in glossary_map:
                expected_th = glossary_map[orig_base]
                # ตรวจดูว่าใน init_spk_tags มีคำว่า expected_th หรือไม่
                found_match = any(expected_th.lower() in t[1].lower() for t in init_spk_tags)

                # ถ้าไม่พบคำแปลทางการตาม Glossary
                if not found_match:
                    actual_th_tags = [t[0] for t in init_spk_tags]
                    violations.append({
                        "row_idx": idx,
                        "row_id": row_id,
                        "speaker": spk_val,
                        "category": "SPEAKER_GLOSSARY_MISMATCH",
                        "severity": "WARNING",
                        "detected": f"Found {actual_th_tags} vs Expected '{expected_th}'",
                        "issue_desc": f"ชื่อผู้พูดไม่ตรงตาม Glossary (ควรเป็น '{expected_th}')",
                        "original": orig_val,
                        "initial": init_val
                    })
                    cat_counts["SPEAKER_GLOSSARY_MISMATCH"] += 1

        # -------------------------------------------------------------
        # 4. CHECK: Tail Control Code Mutation (เช่น \.\.\.\^ กลายเป็น \^\.\.\.\.)
        # -------------------------------------------------------------
        m_tail_orig = re.search(r'([\\\.\|\!\^\>\<]+)$', orig_val.strip())
        m_tail_init = re.search(r'([\\\.\|\!\^\>\<]+)$', init_val.strip())
        if m_tail_orig and m_tail_init:
            t_orig = m_tail_orig.group(1)
            t_init = m_tail_init.group(1)
            if t_orig != t_init and ("^" in t_orig or "^" in t_init):
                violations.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": spk_val,
                    "category": "TAIL_CODE_MUTATION",
                    "severity": "WARNING",
                    "detected": f"Orig: '{t_orig}' -> Init: '{t_init}'",
                    "issue_desc": f"โค้ดควบคุมท้ายประโยคถูกดัดแปลงลำดับ/จำนวน",
                    "original": orig_val,
                    "initial": init_val
                })
                cat_counts["TAIL_CODE_MUTATION"] += 1

    # -------------------------------------------------------------
    # สรุปรายงานผล
    # -------------------------------------------------------------
    print(f"\n📊 ผลการสำรวจความผิดปกติทั้งหมด ({len(rows):,} แถว):")
    print(f"  • จำนวนจุดที่พบความผิดปกติรวม: {len(violations):,} จุด")
    print("-" * 90)
    print(f"  [1] แท็กซ้อนกัน 2 ภาษา/ต่างชื่อ (BILINGUAL/MULTI-SPEAKER):   {cat_counts['BILINGUAL_MULTI_SPEAKER_COLLISION']:,} แถว")
    print(f"      (เช่น <ลูกค้า:> <Customer:>, <นักเลง 1:> <Trug 1:>)")
    print(f"  [2] แท็กผู้พูดชื่อเดียวกันเบิ้ลซ้ำ (SAME_SPEAKER_DUP):         {cat_counts['SAME_SPEAKER_DUP']:,} แถว")
    print(f"      (เช่น \\n<Shion:>\\n<Shion:>, <Dan><Dan>)")
    print(f"  [3] โค้ดควบคุมถูกครอบด้วย <> ผิดพลาด (CORRUPTED_ESCAPE_CODE): {cat_counts['CORRUPTED_ESCAPE_CODE']:,} แถว")
    print(f"      (เช่น <\\.>, <\\!>, <\\^> แบบแถว 89266, 89282)")
    print(f"  [4] แปลชื่อผู้พูดผิดจาก Glossary (SPEAKER_GLOSSARY_MISMATCH):  {cat_counts['SPEAKER_GLOSSARY_MISMATCH']:,} แถว")
    print(f"      (เช่น Thug แปลเป็น 'นักเลง' แทนที่จะเป็น 'อันธพาล')")
    print(f"  [5] โค้ดควบคุมท้ายประโยคถูกบิดเบือน (TAIL_CODE_MUTATION):       {cat_counts['TAIL_CODE_MUTATION']:,} แถว")
    print(f"      (เช่น \\.\\.\\.\\^ กลายเป็น \\^\\.\\.\\.\\.)")
    print("-" * 90)

    # แสดงตัวอย่างจุดที่พบ
    for cat_name, cat_title in [
        ("BILINGUAL_MULTI_SPEAKER_COLLISION", "ตัวอย่าง: แท็กซ้อนกัน 2 ภาษา / ต่างชื่อ"),
        ("CORRUPTED_ESCAPE_CODE", "ตัวอย่าง: โค้ดควบคุมที่ถูกครอบด้วย <> ผิดพลาด"),
        ("SPEAKER_GLOSSARY_MISMATCH", "ตัวอย่าง: แปลชื่อผู้พูดผิดจาก Glossary"),
        ("SAME_SPEAKER_DUP", "ตัวอย่าง: แท็กชื่อเดียวกันเบิ้ลซ้ำ")
    ]:
        sample_items = [v for v in violations if v["category"] == cat_name]
        if sample_items:
            print(f"\n🔍 {cat_title} (แสดง 5 แถวแรก):")
            for item in sample_items[:5]:
                print(f"  • Row {item['row_idx']} (ID: {item['row_id']}) | Speaker Col: '{item['speaker']}':")
                print(f"    - พบ:      {item['detected']}")
                print(f"    - รายละเอียด: {item['issue_desc']}")
                print(f"    - Original: {repr(item['original'][:70])}")
                print(f"    - Initial:  {repr(item['initial'][:75])}")

    # Export รายงานผลเป็น CSV
    if export_csv and violations:
        export_rows = [
            ["Row_Index", "Row_ID", "Speaker_Column", "Category", "Severity", "Detected_Snippet", "Issue_Description", "Original", "Initial"]
        ]
        for v in violations:
            export_rows.append([
                str(v["row_idx"]),
                str(v["row_id"]),
                v["speaker"],
                v["category"],
                v["severity"],
                v["detected"],
                v["issue_desc"],
                v["original"],
                v["initial"]
            ])

        with open(export_csv, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(export_rows)
        print(f"\n💾 ส่งออกรายงานผลฉบับสมบูรณ์ ({len(export_rows) - 1:,} แถว) ไปที่: {export_csv}")

    return {
        "total_violations": len(violations),
        "counts_by_category": dict(cat_counts),
        "violations": violations
    }


def main():
    parser = argparse.ArgumentParser(description="ATF Master Speaker Tag & Control Code Anomaly Auditor")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file to audit")
    parser.add_argument("--export", type=str, default="master_anomalies_audit.csv", help="Path to export report CSV")
    args = parser.parse_args()

    audit_master_anomalies(args.csv, export_csv=args.export)


if __name__ == "__main__":
    main()
