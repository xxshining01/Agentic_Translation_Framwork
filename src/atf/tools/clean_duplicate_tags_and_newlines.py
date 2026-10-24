#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dialogue Cleaner & Anomaly Repair Engine (v7.1 Master Multi-Category Edition)
==================================================================================
ระบบซ่อมแซมความผิดปกติของ Speaker Tags และ Control Codes ครบวงจร:

1. [หมวด 1: โค้ดควบคุมถูกครอบ <> ผิดพลาด และ Tail Mutation]
   - กู้คืน <\\.> ➡️ \\. (ใช้ lambda ป้องกัน re.sub กลืน backslash)
   - กู้คืน <\\!> ➡️ \\!, <\\^> ➡️ \\^, <\\|> ➡️ \\|
   - กู้คืนโค้ดควบคุมท้ายประโยคที่ถูกสลับ เช่น \\^\\.\\.\\.\\. ➡️ \\.\\.\\.\\^ ตาม Original (เช่น แถว 89266, 89282)

2. [หมวด 2: แท็กผู้พูดซ้อนกัน 2 ภาษา / ต่างชื่อ (Bilingual & Multi-Speaker Collision)]
   - เช่น <ลูกค้า:> <Customer:>, <นักเลง 1:> <Trug 1:>, <อันธพาล 1:> <Thug 1:>
   - ยุบเหลือแท็กภาษาไทยตัวเดียว พร้อมจัดคำนำหน้า \\n ตาม Original 100%

3. [หมวด 3: แท็กผู้พูดชื่อเดียวกันเบิ้ลซ้ำ (Same Speaker Duplication)]
   - เช่น \\n<Shion:>\\n<Shion:>, \\n<Shion:>}\\n<Shion:>, <Shion><Shion>
   - ยุบเหลือแท็กมาตรฐานตัวเดียว

4. [หมวด 4: ปรับแก้คำแปลชื่อผู้พูดให้ตรงตาม Master Glossary]
   - 'นักเลง' ➡️ 'อันธพาล' (เช่น <นักเลง:>, <นักเลง 1:>, <นักเลง 2:>, <นักเลงแก๊ง Kinchao:>)
   - 'Arisa' ➡️ 'Alisa' (เช่น <Arisa:>, <\\C[27]Arisa:\\C>)

5. [หมวด 5: เติม \\n นำหน้า Speaker Tag]
   - เติม \\n นำหน้าแท็กเดี่ยวที่ขาดไป หาก Original มี \\n

คุณสมบัติการรายงาน:
- แสดงสถิติแจกแจงแยกตามทั้ง 5 หมวดหมู่อย่างโปร่งใส
- แสดงตัวอย่างของแต่ละหมวดหมู่ (ไม่กระจุกตัวเฉพาะ 20 แถวแรก)
- มีระบบ Backup อัตโนมัติเมื่อสั่งรันด้วย --apply
"""

import os
import sys
import re
import csv
import shutil
import argparse
from datetime import datetime
from typing import List, Dict, Tuple, Any
from collections import defaultdict, Counter

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass


def repair_single_cell(orig_text: str, init_text: str) -> Tuple[str, bool, List[Tuple[str, str]]]:
    """
    ซ่อมแซมข้อความใน Initial ให้ถูกต้องสมบูรณ์ 100%:
    Returns: (repaired_text, had_modification, list_of_(category, detail))
    """
    if not init_text:
        return init_text, False, []

    current = init_text
    modified = False
    details = []  # List of (Category, Description)

    orig_has_nl = bool(re.match(r'^(?:\\n|\r?\n)', orig_text.strip())) if orig_text else False

    # -----------------------------------------------------------------
    # หมวด 0: ซ่อมแซมเศษซากแท็ก XML ตกค้างจากการแปล (XML Remnants Repair)
    # -----------------------------------------------------------------
    # 0.1 แถว 86677: <b>ข้อความ</b> ➡️ \fbข้อความ\fb (RPG Maker Font Bold)
    if re.search(r'<b>(.*?)</b>', current, re.IGNORECASE):
        current = re.sub(r'<b>(.*?)</b>', r'\\fb\1\\fb', current, flags=re.IGNORECASE)
        modified = True
        details.append(('XML_REMNANT_FIX', "แปลงแท็ก <b>...</b> ➡️ '\\fb...\\fb' (Font Bold)"))

    # 0.2 แถว 89267: ลบ <\_> หรือ <\\_> ทิ้ง
    if re.search(r'<\\?_>', current):
        current = re.sub(r'<\\?_>', '', current)
        modified = True
        details.append(('XML_REMNANT_FIX', "ลบเศษแท็ก <\\_> ส่วนเกินทิ้ง"))

    # 0.3 แถว 85548: ลบ <supplied/> หรือ <supplied> ทิ้ง
    if re.search(r'</?supplied/?>', current, re.IGNORECASE):
        current = re.sub(r'</?supplied/?>', '', current, flags=re.IGNORECASE)
        modified = True
        details.append(('XML_REMNANT_FIX', "ลบแท็กส่วนเกิน <supplied/> ทิ้ง"))

    # 0.4 แถว 85789, 81365, 83753: จัดการ <break/> หรือ <break>
    if re.search(r'</?break/?>', current, re.IGNORECASE):
        if r'\.' in orig_text:
            current = re.sub(r'</?break/?>', lambda m: r'\.', current, flags=re.IGNORECASE)
            modified = True
            details.append(('XML_REMNANT_FIX', "แปลง <break> ➡️ '\\.' ตาม Original"))
        elif '.' in orig_text and r'\.' not in orig_text:
            current = re.sub(r'</?break/?>', '.', current, flags=re.IGNORECASE)
            modified = True
            details.append(('XML_REMNANT_FIX', "แปลง <break/> ➡️ '.' ตาม Original"))
        else:
            current = re.sub(r'</?break/?>', '', current, flags=re.IGNORECASE)
            modified = True
            details.append(('XML_REMNANT_FIX', "ลบ <break/> ส่วนเกินทิ้ง"))

    # 0.5 แถว 79940: <space/> หรือ <space></space>
    if re.search(r'</?space/?>', current, re.IGNORECASE):
        if '.' in orig_text:
            current = re.sub(r'</?space/?>', '.', current, flags=re.IGNORECASE)
            modified = True
            details.append(('XML_REMNANT_FIX', "แปลง <space/> ➡️ '.' ตาม Original"))
        else:
            current = re.sub(r'</?space/?>', ' ', current, flags=re.IGNORECASE)
            modified = True
            details.append(('XML_REMNANT_FIX', "แปลง <space/> ➡️ ช่องว่าง"))

    # 0.6 แถว 75547: <...> ถูกแปลงมาจาก ..\.
    if '<...>' in current:
        if r'..\.' in orig_text or r'...\.' in orig_text:
            current = current.replace('<...>', r'..\.')
            modified = True
            details.append(('XML_REMNANT_FIX', "กู้คืนแท็ก <...> ➡️ '..\\.' ตาม Original"))
        else:
            current = current.replace('<...>', r'...')
            modified = True
            details.append(('XML_REMNANT_FIX', "กู้คืนแท็ก <...> ➡️ '...'"))

    # 0.7 ตัด \. ท้ายประโยคที่เป็นส่วนเกินใน Initial ถ้า Original ไม่มี \. ท้ายประโยค (เช่น แถว 75547)
    if orig_text and not orig_text.strip().endswith(r'\.') and not orig_text.strip().endswith(r'\\.'):
        if current.strip().endswith(r'\.') or current.strip().endswith(r'\\.'):
            current = re.sub(r'\\\.+\s*$', '', current)
            modified = True
            details.append(('TAIL_CONTROL_MUTATION', "ตัด '\\.' ส่วนเกินท้ายประโยคออกให้ตรงตาม Original"))

    # -----------------------------------------------------------------
    # หมวด 1: ซ่อมแซมโค้ดควบคุมที่ถูกครอบ <> ผิดพลาด (<\\.>, <\\!>, <\\^>, <\\|>)
    # ใช้ lambda เพื่อป้องกัน re.sub กลืน backslash บน Python
    # -----------------------------------------------------------------
    escape_fixes = [
        (re.compile(r'<\\?\.>'), r'\.', 'CORRUPTED_ESCAPE'),
        (re.compile(r'<\\?!>'), r'\!', 'CORRUPTED_ESCAPE'),
        (re.compile(r'<\\?\^>'), r'\^', 'CORRUPTED_ESCAPE'),
        (re.compile(r'<\\?\|>'), r'\|', 'CORRUPTED_ESCAPE'),
    ]
    for pat, repl_str, cat in escape_fixes:
        if pat.search(current):
            cnt = len(pat.findall(current))
            current = pat.sub(lambda m, r=repl_str: r, current)
            modified = True
            details.append((cat, f"กู้คืนโค้ดควบคุม {pat.pattern} ➡️ '{repl_str}' ({cnt} จุด)"))

    # กู้คืนโค้ดควบคุมท้ายประโยคที่ถูกสลับ (เช่น \\^\\.\\.\\.\\. ➡️ \\.\\.\\.\\^ ในแถว 89266, 89282)
    if orig_text:
        m_tail_orig = re.search(r'([\\\.\|\!\^\>\<]+)$', orig_text.strip())
        m_tail_curr = re.search(r'([\\\.\|\!\^\>\<]+)$', current.strip())
        if m_tail_orig and m_tail_curr:
            t_orig = m_tail_orig.group(1)
            t_curr = m_tail_curr.group(1)
            if t_orig != t_curr and ("^" in t_orig and "^" in t_curr):
                current = current.rstrip()[:-len(t_curr)] + t_orig
                modified = True
                details.append(('TAIL_CONTROL_MUTATION', f"กู้คืนโค้ดควบคุมท้ายประโยค: '{t_curr}' ➡️ '{t_orig}'"))

    # -----------------------------------------------------------------
    # หมวด 2: ซ่อมแซมแท็กซ้อน 2 ภาษา / ต่างชื่อ (Bilingual & Multi-Speaker Collision)
    # เช่น <ลูกค้า:> <Customer:>, <นักเลง 1:> <Trug 1:>, <อันธพาล 1:> <Thug 1:>
    # ดักจับแท็กเปิด 2 ตัวติดกันที่หัวประโยค โดยไม่จำกัดตัวอักษร
    # -----------------------------------------------------------------
    multi_tag_head_regex = re.compile(
        r'^(?P<lead>(?:\\n|\r?\n|\s)*)'
        r'<(?P<tag1>[^>]+)>'
        r'(?P<sep>(?:\\n|\r?\n|\s|\}\s*|\\n\}\s*|\}\s*\\n)*)'
        r'<(?P<tag2>[^>]+)>',
        re.IGNORECASE
    )
    m_multi = multi_tag_head_regex.match(current.lstrip())
    if m_multi:
        t1_raw = m_multi.group("tag1").strip()
        t2_raw = m_multi.group("tag2").strip()

        # กรองแท็กระบบ เช่น color, font
        is_sys1 = t1_raw.lower().startswith("color") or t1_raw.lower().startswith("font")
        is_sys2 = t2_raw.lower().startswith("color") or t2_raw.lower().startswith("font")

        if not is_sys1 and not is_sys2:
            # ตรวจสอบว่าอันไหนเป็นภาษาไทย / คำแปล
            has_th1 = any('\u0e00' <= ch <= '\u0e7f' for ch in t1_raw)
            has_th2 = any('\u0e00' <= ch <= '\u0e7f' for ch in t2_raw)

            # Clean names
            c1 = re.sub(r'\\[A-Za-z]+(?:\[\d+\])?', '', t1_raw).replace(':', '').replace('}', '').strip()
            c2 = re.sub(r'\\[A-Za-z]+(?:\[\d+\])?', '', t2_raw).replace(':', '').replace('}', '').strip()

            is_same = (c1.lower() == c2.lower())

            # กรณีที่ 2.1: ชื่อเดียวกันเบิ้ล (Same Speaker Duplication)
            if is_same:
                chosen_tag = t1_raw.rstrip(":").strip() + ":"
                canonical = f"\\n<{chosen_tag}>" if orig_has_nl else f"<{chosen_tag}>"
                remainder = current.lstrip()[m_multi.end():]
                current = canonical + remainder
                modified = True
                details.append(('SAME_SPEAKER_DUP', f"ยุบแท็กชื่อเดียวกันเบิ้ล: '<{t1_raw}><{t2_raw}>' ➡️ '{canonical}'"))

            # กรณีที่ 2.2: แท็ก 2 ภาษา (Bilingual Collision) หรือต่างชื่อ
            else:
                # เลือกแท็กที่มีภาษาไทยเป็นหลัก
                if has_th1 and not has_th2:
                    chosen_inner = t1_raw.rstrip(":").strip() + ":"
                elif has_th2 and not has_th1:
                    chosen_inner = t2_raw.rstrip(":").strip() + ":"
                else:
                    # ถ้าไทยทั้งคู่ หรืออังกฤษทั้งคู่ ให้ยึดตัวแรก
                    chosen_inner = t1_raw.rstrip(":").strip() + ":"

                canonical = f"\\n<{chosen_inner}>" if orig_has_nl else f"<{chosen_inner}>"
                remainder = current.lstrip()[m_multi.end():]
                current = canonical + remainder
                modified = True
                details.append(('BILINGUAL_COLLISION', f"ยุบแท็กเบิ้ล 2 ภาษา/ต่างชื่อ: '<{t1_raw}><{t2_raw}>' ➡️ '{canonical}'"))

    # -----------------------------------------------------------------
    # หมวด 4: ปรับแก้คำแปลชื่อผู้พูดให้ตรงตาม Master Glossary
    # -----------------------------------------------------------------
    # 4.1 'นักเลง' ➡️ 'อันธพาล'
    glossary_rules = [
        (re.compile(r'<(\s*(?:\\n)?\s*)นักเลง\s*แก๊ง\s*Kinchao(\s*\??\s*:?\s*)>', re.IGNORECASE), r'<\1อันธพาลแก๊ง Kinchao\2>', 'GLOSSARY_THUG'),
        (re.compile(r'<(\s*(?:\\n)?\s*)นักเลง\s*1(\s*:?\s*)>', re.IGNORECASE), r'<\1อันธพาล 1\2>', 'GLOSSARY_THUG'),
        (re.compile(r'<(\s*(?:\\n)?\s*)นักเลง\s*2(\s*:?\s*)>', re.IGNORECASE), r'<\1อันธพาล 2\2>', 'GLOSSARY_THUG'),
        (re.compile(r'<(\s*(?:\\n)?\s*)นักเลง(\s*:?\s*)>', re.IGNORECASE), r'<\1อันธพาล\2>', 'GLOSSARY_THUG'),
        # 4.2 'Arisa' ➡️ 'Alisa'
        (re.compile(r'<(\s*(?:\\n)?\s*(?:\\C\[\d+\])?)Arisa(\s*:?\s*(?:\\C)?\s*)>', re.IGNORECASE), r'<\1Alisa\2>', 'GLOSSARY_ALISA'),
        (re.compile(r'<(\s*(?:\\n)?\s*)Arisa(\s*:?\s*)>', re.IGNORECASE), r'<\1Alisa\2>', 'GLOSSARY_ALISA'),
    ]
    for pat, repl, cat in glossary_rules:
        if pat.search(current):
            old_str = pat.search(current).group(0)
            current = pat.sub(repl, current)
            modified = True
            details.append((cat, f"ปรับคำแปลชื่อผู้พูดตาม Glossary: '{old_str}' ➡️ '{repl}'"))

    # -----------------------------------------------------------------
    # หมวด 5: เติม \n นำหน้า Speaker Tag ถ้า Original มี \n
    # -----------------------------------------------------------------
    if orig_has_nl and not current.startswith("\\n"):
        m_single_tag = re.match(r'^<([^>]+:?)>', current)
        if m_single_tag:
            # ไม่ใช่ tag formatting
            tag_content = m_single_tag.group(1).lower()
            if not tag_content.startswith("color") and not tag_content.startswith("font"):
                current = "\\n" + current
                modified = True
                details.append(('ADD_NEWLINE_PREFIX', f"เติม \\n นำหน้าแท็กเดี่ยว: '{m_single_tag.group(0)}'"))

    return current, modified, details


def process_repair_csv(csv_path: str, dry_run: bool = True, output_path: str = None) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("   ATF MASTER SPEAKER TAG & ANOMALY REPAIR ENGINE (v7.1 MULTI-CATEGORY)   ")
    print("=" * 95)
    print(f"Target CSV: {csv_path}")
    print(f"Mode: {'🔍 DRY-RUN (ตรวจสอบและรายงานสถิติ - ยังไม่แก้ไขไฟล์)' if dry_run else '🛠️ LIVE REPAIR (ดำเนินการแก้ไขและบันทึกไฟล์จริง)'}")
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

    repaired_records = []
    category_buckets = defaultdict(list)
    new_rows = [header]

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            new_rows.append(r)
            continue

        init_val = r[init_col]
        orig_val = r[orig_col] if orig_col < len(r) else ""
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        if not init_val:
            new_rows.append(r)
            continue

        cleaned_text, had_mod, details = repair_single_cell(orig_val, init_val)

        if had_mod:
            rec = {
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "original": orig_val,
                "before": init_val,
                "after": cleaned_text,
                "details": details
            }
            repaired_records.append(rec)
            for cat, desc in details:
                category_buckets[cat].append((rec, desc))

            new_r = list(r)
            new_r[init_col] = cleaned_text
            new_rows.append(new_r)
        else:
            new_rows.append(r)

    # -----------------------------------------------------------------
    # สรุปสถิติแยกตามหมวดหมู่
    # -----------------------------------------------------------------
    print(f"\n📊 สรุปผลการซ่อมแซมทั้งหมด ({len(rows):,} แถว):")
    print(f"  • จำนวนแถวที่ได้รับการซ่อมแซมรวม: {len(repaired_records):,} แถว")
    print("-" * 95)
    print(f"  [หมวด 0] ซ่อมแซมเศษซากแท็ก XML ตกค้าง (<b>, <break>, <space>, <...>): {len(category_buckets['XML_REMNANT_FIX']):,} จุด")
    print(f"  [หมวด 1] กู้คืนโค้ดควบคุมผิดพลาด (<\\.>, <\\!>, <\\^>):       {len(category_buckets['CORRUPTED_ESCAPE']):,} จุด")
    print(f"  [หมวด 1b] กู้คืนโค้ดควบคุมท้ายประโยคที่ถูกสลับ (Tail Mutation): {len(category_buckets['TAIL_CONTROL_MUTATION']):,} จุด")
    print(f"  [หมวด 2] ยุบแท็กเบิ้ล 2 ภาษา (Bilingual / Multi-Speaker):      {len(category_buckets['BILINGUAL_COLLISION']):,} จุด")
    print(f"  [หมวด 3] ยุบแท็กชื่อเดียวกันเบิ้ลซ้ำ (Same Speaker Duplication): {len(category_buckets['SAME_SPEAKER_DUP']):,} จุด")
    print(f"  [หมวด 4a] ปรับชื่อผู้พูดตาม Glossary (นักเลง ➡️ อันธพาล):       {len(category_buckets['GLOSSARY_THUG']):,} จุด")
    print(f"  [หมวด 4b] ปรับชื่อผู้พูดตาม Glossary (Arisa ➡️ Alisa):         {len(category_buckets['GLOSSARY_ALISA']):,} จุด")
    print(f"  [หมวด 5] เติม \\n นำหน้า Speaker Tag ให้ตรงตาม Original:       {len(category_buckets['ADD_NEWLINE_PREFIX']):,} จุด")
    print("-" * 95)

    # แสดงตัวอย่างแถวแยกตามหมวดหมู่อย่างโปร่งใส (หมวดละ 4-5 แถว)
    cat_titles = [
        ('XML_REMNANT_FIX', "🔍 ตัวอย่าง: ซ่อมแซมเศษซากแท็ก XML ตกค้าง (<b>, <break>, <space>, <...>)"),
        ('CORRUPTED_ESCAPE', "🔍 ตัวอย่าง: กู้คืนโค้ดควบคุมที่ถูกครอบ <> (<\\.>, <\\^>)"),
        ('TAIL_CONTROL_MUTATION', "🔍 ตัวอย่าง: กู้คืนโค้ดควบคุมท้ายประโยคที่ถูกสลับ (Tail Mutation)"),
        ('BILINGUAL_COLLISION', "🔍 ตัวอย่าง: ยุบแท็กเบิ้ล 2 ภาษา / ต่างชื่อ (<ลูกค้า:><Customer:>, <นักเลง 1:><Trug 1:>)"),
        ('SAME_SPEAKER_DUP', "🔍 ตัวอย่าง: ยุบแท็กชื่อเดียวกันเบิ้ลซ้ำ (\\n<Shion:>\\n<Shion:>)"),
        ('GLOSSARY_THUG', "🔍 ตัวอย่าง: ปรับคำแปลชื่อผู้พูด (นักเลง ➡️ อันธพาล)"),
        ('GLOSSARY_ALISA', "🔍 ตัวอย่าง: ปรับคำแปลชื่อผู้พูด (Arisa ➡️ Alisa)"),
        ('ADD_NEWLINE_PREFIX', "🔍 ตัวอย่าง: เติม \\n นำหน้า Speaker Tag"),
    ]

    for cat_key, title in cat_titles:
        items = category_buckets[cat_key]
        if items:
            print(f"\n{title} (พบทั้งหมด {len(items):,} จุด - แสดง 5 แถวแรก):")
            seen_rows = set()
            shown = 0
            for rec, desc in items:
                if rec["row_idx"] in seen_rows:
                    continue
                seen_rows.add(rec["row_idx"])
                print(f"  • [Row {rec['row_idx']} | ID {rec['row_id']} | Speaker: '{rec['speaker']}']:")
                print(f"    - รายละเอียด: {desc}")
                print(f"    - ORIGINAL: {repr(rec['original'][:85])}")
                print(f"    - BEFORE:   {repr(rec['before'][:85])}")
                print(f"    - AFTER:    {repr(rec['after'][:85])}")
                shown += 1
                if shown >= 5:
                    break

    # ดำเนินการบันทึกไฟล์จริง (เฉพาะโหมด Live Apply)
    if not dry_run and len(repaired_records) > 0:
        target_out = output_path or csv_path

        # สำรองไฟล์ต้นฉบับก่อนเสมอ
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{csv_path}.backup_v71_{ts}.csv"
        shutil.copy2(csv_path, backup_path)
        print(f"\n💾 สำรองไฟล์ต้นฉบับอย่างปลอดภัยไว้ที่:\n   👉 {backup_path}")

        # บันทึกไฟล์ที่ซ่อมแซมแล้ว
        temp_out = target_out + ".tmp"
        with open(temp_out, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(new_rows)
        os.replace(temp_out, target_out)
        print(f"💾 บันทึกผลการซ่อมแซมลงไฟล์สำเร็จ:\n   👉 {target_out}")

    return {
        "total_rows": len(rows),
        "repaired_count": len(repaired_records),
        "category_counts": {k: len(v) for k, v in category_buckets.items()}
    }


def main():
    parser = argparse.ArgumentParser(description="ATF Master Speaker Tag & Anomaly Repair Engine (v7.1)")
    parser.add_argument("--csv", type=str, required=True, help="Path to target CSV file")
    parser.add_argument("--apply", action="store_true", help="Apply fixes to CSV (default is Dry-run)")
    parser.add_argument("--out", type=str, default=None, help="Custom output CSV path (optional)")
    args = parser.parse_args()

    process_repair_csv(args.csv, dry_run=not args.apply, output_path=args.out)


if __name__ == "__main__":
    main()
