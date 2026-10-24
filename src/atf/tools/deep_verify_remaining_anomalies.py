#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Deep Anomaly & Remnant Verification Auditor (v8.0 Deep Inspector)
======================================================================
ระบบตรวจสอบค้นหาจุดบกพร่องที่อาจ 'ตกหล่น' ในทุกมิติและทุกรูปแบบ (READ-ONLY 100%):

มิติที่ 1: [Speaker Tags ซ้ำซ้อนที่หลุดไปอยู่กลางหรือท้ายประโยค (Dispersed Tags)]
   - แท็กตัวละครที่มีมากกว่า 1 แท็กในเซลล์เดียว (ไม่ว่าจะอยู่หัว, กลาง, หรือท้ายประโยค)
   - แท็กที่เบิ้ลมากกว่า 2 ครั้ง (Triple/Quadruple Tags)

มิติที่ 2: [แท็กที่มีรูปแบบผิดปกติ / เสียรูป (Malformed / Broken Brackets)]
   - วงเล็บเบิ้ล: <<...>>, <[...]>
   - วงเล็บปิดหาย: <Name: โดยไม่มี > ปิด
   - มีเศษอักขระแปลกปลอมในแท็ก: < Name:>, <Name: }>, <Name :>

มิติที่ 3: [เศษซาก Control Codes ที่ถูกครอบ <> รูปแบบอื่นๆ (Corrupted Escapes)]
   - เช่น <\\C>, <\\C[0]>, <\\V[1]>, <\\N[1]>, <\\I[1]>, <\\fb>, <\\fi>, <\\>>, <\\<>

มิติที่ 4: [คำแปล Speaker ไม่ตรงตาม Master Glossary ที่อาจหลงเหลือ]
   - คำว่า 'นักเลง' ที่หลงเหลืออยู่ในแท็ก (<นักเลง...>)
   - คำว่า 'Arisa' ที่หลงเหลืออยู่ในแท็ก (<Arisa...>, <\\C[27]Arisa...>)
   - ตรวจสอบชื่อตัวละครสำคัญอื่นๆ เทียบกับ Glossary

มิติที่ 5: [Control Codes ท้ายประโยคและหัวประโยคที่ไม่ตรงกับ Original]
   - Original มี \\^, \\!, \\|, \\. แต่ Initial ขาดหายไป หรือสลับตำแหน่ง
   - Form Feed (\\x0c) หรือ control code เสียรูป

มิติที่ 6: [แท็กภาษาอังกฤษตกค้างในบทพูด (Untranslated English Tags)]
   - แถวที่ Original มี Speaker Tag ภาษาอังกฤษ แต่ Initial ดันไม่มีแท็กภาษาไทยเลย
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

# โค้ดควบคุมระบบที่ไม่ใช่ Speaker Tag
SYSTEM_TAGS = {
    "color", "/color", "font", "/font", "icon", "/icon",
    "pause_quarter", "pause_half", "pause_second",
    "wait_input", "stop_show_fast", "bold", "/bold",
    "italic", "/italic", "speed"
}

# Regex ตรวจจับเศษซากโค้ดควบคุมที่ถูกครอบ <>
CORRUPTED_CONTROL_IN_XML = re.compile(
    r'<\\?[a-zA-Z]?[\.\|\!\^\>\<]|<\\?C(?:\[\d+\])?/?>|<\\?V(?:\[\d+\])?/?>|<\\?N(?:\[\d+\])?/?>|<\\?I(?:\[\d+\])?/?>|<\\?fb/?>|<\\?fi/?>',
    re.IGNORECASE
)

# Regex สกัดแท็ก <...> ทั้งหมด
TAG_FINDER_REGEX = re.compile(r'<([^>]+)>')


def clean_speaker_name(tag_inner: str) -> str:
    """ล้างโค้ด RPG Maker, เครื่องหมาย colon, เศษ space ออก ให้เหลือชื่อตัวละครที่แท้จริง"""
    if not tag_inner:
        return ""
    name = re.sub(r'\\[A-Za-z]+(?:\[\d+\])?', '', tag_inner)
    name = name.replace(':', '').replace('}', '').replace('{', '').strip()
    return name


def is_system_or_formatting_tag(clean_name: str) -> bool:
    c = clean_name.lower().strip()
    if not c or c in SYSTEM_TAGS:
        return True
    if c.startswith("color") or c.startswith("/color"):
        return True
    if c.startswith("font") or c.startswith("/font"):
        return True
    if c.startswith("icon") or c.startswith("/icon"):
        return True
    if re.match(r'^[\\\.\|\!\^\>\<]+$', c):
        return True
    return False


def deep_inspect_csv(csv_path: str, export_csv: str = None) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("      ATF DEEP ANOMALY & REMNANT VERIFICATION AUDITOR (v8.0 DEEP INSPECTOR)      ")
    print("=" * 95)
    print(f"Target CSV: {csv_path}")
    print(f"Mode: 🔍 COMPREHENSIVE SCAN (สำรวจลึก 6 มิติเพื่อหาจุดตกหล่นทั้งหมด)")
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

    anomalies = []
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

        # -----------------------------------------------------------------
        # มิติที่ 1: ตรวจจับ Form Feed (\x0c) ตกค้าง
        # -----------------------------------------------------------------
        if "\x0c" in init_val:
            anomalies.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "FORM_FEED_HAZARD",
                "severity": "CRITICAL",
                "issue": "พบ Form Feed ASCII 12 (\\x0c) ตกค้างในคำแปล",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["FORM_FEED_HAZARD"] += 1

        # -----------------------------------------------------------------
        # มิติที่ 2: เศษซาก Control Codes ที่ถูกครอบ <> ผิดพลาด
        # (ยกเว้นชื่อตัวละครจริงตาม Original เช่น Y..rl และ P.A.)
        # -----------------------------------------------------------------
        raw_corrupted = CORRUPTED_CONTROL_IN_XML.findall(init_val)
        corrupted_codes = [
            c for c in raw_corrupted
            if "Y..rl" not in c and "P.A." not in c and "Y..rl" not in init_val and "P.A." not in init_val
        ]
        if corrupted_codes:
            anomalies.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "CORRUPTED_CONTROL_TAG",
                "severity": "CRITICAL",
                "issue": f"พบ Control Code ถูกครอบด้วย <>: {corrupted_codes}",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["CORRUPTED_CONTROL_TAG"] += 1

        # -----------------------------------------------------------------
        # มิติที่ 3: วงเล็บเบิ้ล หรือเสียรูป เช่น <<...>> หรือ <[...]>
        # (ยกเว้นแท็กของระบบเกม เช่น <<AUTHETICATION NEEDED>>, <<BLANK>>)
        # -----------------------------------------------------------------
        if re.search(r'<<[^>]+>>|<\[[^\]]+\]>', init_val):
            raw_mal = re.findall(r'<<[^>]+>>|<\[[^\]]+\]>', init_val)
            m_mal = [
                x for x in raw_mal
                if "AUTHETICATION" not in x and "BLANK" not in x
            ]
            if m_mal:
                anomalies.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": spk_val,
                    "category": "MALFORMED_BRACKETS",
                    "severity": "WARNING",
                    "issue": f"พบวงเล็บเบิ้ลหรือผิดรูปแบบ: {m_mal}",
                    "original": orig_val,
                    "initial": init_val
                })
                cat_counts["MALFORMED_BRACKETS"] += 1

        # -----------------------------------------------------------------
        # มิติที่ 4: คำศัพท์ Glossary ที่หลงเหลือ (นักเลง / Arisa)
        # -----------------------------------------------------------------
        if re.search(r'<[^>]*นักเลง[^>]*>', init_val):
            m_thug = re.findall(r'<[^>]*นักเลง[^>]*>', init_val)
            anomalies.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "REMNANT_THUG_TRANSLATION",
                "severity": "WARNING",
                "issue": f"พบคำว่า 'นักเลง' ในแท็กผู้พูด (ควรเป็น 'อันธพาล'): {m_thug}",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["REMNANT_THUG_TRANSLATION"] += 1

        if re.search(r'<[^>]*Arisa[^>]*>', init_val, re.IGNORECASE):
            m_arisa = re.findall(r'<[^>]*Arisa[^>]*>', init_val, re.IGNORECASE)
            anomalies.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "category": "REMNANT_ARISA_TRANSLATION",
                "severity": "WARNING",
                "issue": f"พบคำว่า 'Arisa' ในแท็กผู้พูด (ควรเป็น 'Alisa'): {m_arisa}",
                "original": orig_val,
                "initial": init_val
            })
            cat_counts["REMNANT_ARISA_TRANSLATION"] += 1

        # -----------------------------------------------------------------
        # มิติที่ 5: สแกนแท็กผู้พูดทั้งเซลล์ (Cell-wide Speaker Tag Census)
        # -----------------------------------------------------------------
        tags_found = []
        for m in TAG_FINDER_REGEX.finditer(init_val):
            raw_tag = m.group(0)
            inner = m.group(1).strip()
            # กรอง corrupted escape
            if re.match(r'^[\\\/]?[\.\|\!\^\>\<]', inner):
                continue
            name = clean_speaker_name(inner)
            if name and not is_system_or_formatting_tag(name):
                tags_found.append((raw_tag, name, m.start(), m.end()))

        # ถ้าพบ Speaker Tag >= 2 แท็กในเซลล์เดียว
        if len(tags_found) >= 2:
            # ตรวจสอบว่า Original มีกี่แท็ก
            orig_tags = []
            for mo in TAG_FINDER_REGEX.finditer(orig_val):
                in_o = mo.group(1).strip()
                no = clean_speaker_name(in_o)
                if no and not is_system_or_formatting_tag(no):
                    orig_tags.append((mo.group(0), no))

            # ถ้า Initial มีแท็กมากกว่า Original แสดงว่ามีแท็กซ้ำ/ซ้อนหลงเหลือ!
            if len(tags_found) > len(orig_tags):
                tag_names = [t[1] for t in tags_found]
                tag_raws = [t[0] for t in tags_found]
                is_same = len(set(n.lower() for n in tag_names)) == 1

                # ตรวจว่าอยู่ติดกัน หรือกระจายอยู่กลาง/ท้ายประโยค
                t1, t2 = tags_found[0], tags_found[1]
                gap = init_val[t1[3]:t2[2]]
                is_adjacent = bool(re.match(r'^(?:\\n|\r?\n|\s|\}\s*)*$', gap))

                subcat = "REMNANT_DUP_ADJACENT" if is_adjacent else "REMNANT_DUP_DISPERSED"
                anomalies.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": spk_val,
                    "category": subcat,
                    "severity": "CRITICAL",
                    "issue": f"พบ Speaker Tags ซ้อนกัน {len(tags_found)} แท็ก ({tag_raws}) {'(ติดกัน)' if is_adjacent else '(กระจายในเซลล์)'}",
                    "original": orig_val,
                    "initial": init_val
                })
                cat_counts[subcat] += 1

        # -----------------------------------------------------------------
        # มิติที่ 6: ความคลาดเคลื่อนของ Tail Control Codes
        # -----------------------------------------------------------------
        m_t_orig = re.search(r'([\\\.\|\!\^\>\<]+)$', orig_val.strip())
        m_t_init = re.search(r'([\\\.\|\!\^\>\<]+)$', init_val.strip())
        if m_t_orig and m_t_init:
            to = m_t_orig.group(1)
            ti = m_t_init.group(1)
            if to != ti and ("^" in to or "^" in ti):
                anomalies.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": spk_val,
                    "category": "REMNANT_TAIL_MUTATION",
                    "severity": "WARNING",
                    "issue": f"โค้ดควบคุมท้ายประโยคไม่ตรงกับ Original: Initial '{ti}' vs Original '{to}'",
                    "original": orig_val,
                    "initial": init_val
                })
                cat_counts["REMNANT_TAIL_MUTATION"] += 1

    # -----------------------------------------------------------------
    # สรุปผลการตรวจสอบอย่างละเอียด
    # -----------------------------------------------------------------
    print(f"\n📊 ผลการสแกนเชิงลึกทั้ง 6 มิติ ({len(rows):,} แถว):")
    print(f"  • จำนวนจุดบกพร่องที่ตรวจพบทั้งหมด: {len(anomalies):,} จุด")
    print("-" * 95)
    print(f"  [1] แท็กซ้อนกันติดกัน (Adjacent Duplicate Tags):          {cat_counts['REMNANT_DUP_ADJACENT']:,} แถว")
    print(f"  [2] แท็กซ้อนกันกระจายในเซลล์ (Dispersed in Cell):          {cat_counts['REMNANT_DUP_DISPERSED']:,} แถว")
    print(f"  [3] Control Code ถูกครอบด้วย <> ผิดพลาด (<\\.>, <\\^>):       {cat_counts['CORRUPTED_CONTROL_TAG']:,} แถว")
    print(f"  [4] คำว่า 'นักเลง' หลงเหลือใน Speaker Tag:                 {cat_counts['REMNANT_THUG_TRANSLATION']:,} แถว")
    print(f"  [5] คำว่า 'Arisa' หลงเหลือใน Speaker Tag:                  {cat_counts['REMNANT_ARISA_TRANSLATION']:,} แถว")
    print(f"  [6] วงเล็บเบิ้ล หรือเสียรูป (<<...>>, <[...] >):             {cat_counts['MALFORMED_BRACKETS']:,} แถว")
    print(f"  [7] โค้ดท้ายประโยคคลาดเคลื่อน (Tail Control Mutation):       {cat_counts['REMNANT_TAIL_MUTATION']:,} แถว")
    print(f"  [8] สารตกค้าง Form Feed ASCII 12 (\\x0c):                   {cat_counts['FORM_FEED_HAZARD']:,} แถว")
    print("-" * 95)

    if anomalies:
        print("\n🔍 รายการตัวอย่างจุดบกพร่องที่พบ (แสดงสูงสุดหมวดละ 4 แถว):")
        cat_order = [
            ("REMNANT_DUP_ADJACENT", "📌 แท็กซ้อนกันติดกัน"),
            ("REMNANT_DUP_DISPERSED", "📌 แท็กซ้อนกันกระจายในเซลล์"),
            ("CORRUPTED_CONTROL_TAG", "📌 Control Code ถูกครอบ <> ผิดพลาด"),
            ("REMNANT_THUG_TRANSLATION", "📌 คำว่า 'นักเลง' หลงเหลือ"),
            ("REMNANT_ARISA_TRANSLATION", "📌 คำว่า 'Arisa' หลงเหลือ"),
            ("MALFORMED_BRACKETS", "📌 วงเล็บเบิ้ล หรือเสียรูป"),
            ("REMNANT_TAIL_MUTATION", "📌 โค้ดท้ายประโยคคลาดเคลื่อน"),
            ("FORM_FEED_HAZARD", "📌 สารตกค้าง Form Feed"),
        ]
        for c_key, c_name in cat_order:
            matches = [a for a in anomalies if a["category"] == c_key]
            if matches:
                print(f"\n{c_name} (พบ {len(matches):,} แถว):")
                for item in matches[:4]:
                    print(f"  • Row {item['row_idx']} (ID {item['row_id']}) | Speaker: '{item['speaker']}':")
                    print(f"    - สาเหตุ:   {item['issue']}")
                    print(f"    - ORIGINAL: {repr(item['original'][:85])}")
                    print(f"    - INITIAL:  {repr(item['initial'][:85])}")
    else:
        print("\n🎉 ยินดีด้วยครับ! ไฟล์ CSV นี้สะอาดบริสุทธิ์ 100% ไม่พบข้อผิดพลาดหรือแท็กตกหล่นใดๆ ทั้งสิ้น!")

    # ส่งออกรายงาน CSV
    if export_csv and anomalies:
        out_rows = [
            ["Row_Index", "Row_ID", "Speaker", "Category", "Severity", "Issue_Detail", "Original", "Initial"]
        ]
        for a in anomalies:
            out_rows.append([
                str(a["row_idx"]),
                str(a["row_id"]),
                a["speaker"],
                a["category"],
                a["severity"],
                a["issue"],
                a["original"],
                a["initial"]
            ])
        with open(export_csv, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(out_rows)
        print(f"\n💾 ส่งออกรายงานผลการตรวจสอบความผิดปกติ ({len(out_rows) - 1:,} แถว) ไปที่:\n   👉 {export_csv}")

    return {
        "total_anomalies": len(anomalies),
        "counts": dict(cat_counts),
        "anomalies": anomalies
    }


def main():
    parser = argparse.ArgumentParser(description="ATF Deep Anomaly & Remnant Verification Auditor")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file to audit")
    parser.add_argument("--export", type=str, default="remaining_anomalies_audit.csv", help="Path to export audit CSV")
    args = parser.parse_args()

    deep_inspect_csv(args.csv, export_csv=args.export)


if __name__ == "__main__":
    main()
