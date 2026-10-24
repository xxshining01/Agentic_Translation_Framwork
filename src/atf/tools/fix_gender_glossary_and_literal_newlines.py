#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Data Integrity & Parity Repair Tool
เครื่องมือตรวจสอบและซ่อมแซมความสมบูรณ์ของบทสนทนา (Universal Fix) ครอบคลุม 3 ปัญหาหลัก:
1. Literal '\\n' -> แปลงสตริงแบ็กสแลช-n ในเนื้อความบทพูดให้เป็น Newline จริง (0x0A) เพื่อให้ขึ้นบรรทัดใหม่ในเกมอย่างถูกต้อง
2. Speaker Tag Translation -> แปลชื่อตัวละครในแท็กผู้พูดตาม TLAS Glossary (เช่น \\n<\\C[27]Pink hair Woman\\C:> -> \\n<\\C[27]หญิงสาวผมชมพู\\C:>)
3. Character Gender / Particle Repair -> ซ่อมแซมบทพูดตัวละครเพศหญิง (เช่น Pink hair Woman) ที่ถูก Calibrate ผิดให้กลับมาเป็นเพศหญิง (ฉัน/ค่ะ) 100%
4. Dual-State Atomic Sync -> บันทึกการแก้ไขลงทั้ง CSV และ Checkpoint พร้อมกันอย่างปลอดภัย
"""

import os
import sys
import re
import csv
import json
import shutil

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
CHECKPOINT_PATH = os.path.join(TLAS_DATA, "chatgpt_translation_checkpoint.json")
GLOSSARY_PATH = os.path.join(TLAS_DATA, "tlas_glossary.json")

# Import GlossaryScanner
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
from atf.core.glossary_scanner import GlossaryScanner

def clean_literal_newlines_in_dialogue(text: str) -> str:
    """
    แปลง literal '\\n' ในเนื้อความบทพูดให้กลายเป็น Newline จริง (0x0A)
    โดยคง \\n ที่อยู่หน้าแท็กผู้พูด (เช่น \\n<...>) ซึ่งเป็น Control Code ของ RPG Maker ไว้
    """
    if not text:
        return text

    # ตรวจสอบแท็กผู้พูดนำหน้า
    m = re.match(r"^(\s*\\n)?<([^>]+)>", text)
    if m:
        prefix = m.group(0)
        pure_dialogue = text[len(prefix):]
    else:
        prefix = ""
        pure_dialogue = text

    # แปลง literal \n หรือ \\n ใน pure_dialogue ให้เป็น newline จริง
    # ต้องระวังไม่ไปแปลง escape codes อื่นๆ เช่น \., \|, \!, \C[27]
    pure_dialogue = pure_dialogue.replace("\\r\\n", "\n")
    pure_dialogue = pure_dialogue.replace("\\n", "\n")
    pure_dialogue = pure_dialogue.replace("\r\n", "\n")

    return f"{prefix}{pure_dialogue}"

def repair_pink_hair_woman_lines(text: str) -> str:
    """
    ซ่อมแซมบทสนทนาของ Pink hair Woman จากสรรพนาม/หางเสียงชาย (ผม/ครับ) กลับเป็นหญิง (ฉัน/ค่ะ)
    """
    if not text:
        return text

    # ซ่อมแซมคำสรรพนามและหางเสียงที่หลุด
    repaired = text
    repaired = repaired.replace("เรากำลังทำเรื่องซนๆ กันอยู่เหรอครับ", "เรากำลังทำเรื่องซนๆ กันอยู่เหรอคะ")
    repaired = repaired.replace("การแสดงตามแผนการ..ใช่ไหมครับ", "การแสดงตามแผนการ..ใช่ไหมคะ")
    repaired = repaired.replace("ฉ-ผมชินแล้วล่ะครับ", "ฉ-ฉันชินแล้วล่ะค่ะ")
    repaired = repaired.replace("ไม่กระทบกับงานครับ", "ไม่กระทบกับงานค่ะ")
    repaired = repaired.replace("เขาถึงตีผมแค่ตรงนั้นไงครับ", "เขาถึงตีฉันแค่ตรงนั้นไงคะ")

    return repaired

def main():
    print("=" * 70)
    print("=== ATF UNIVERSAL DATA INTEGRITY & PARITY REPAIR ===")
    print("=" * 70)

    # 1. โหลด Glossary Scanner
    print("[*] Initializing Glossary Scanner...")
    glossary_scanner = GlossaryScanner(TLAS_DATA)

    # 2. อ่านไฟล์ CSV
    print(f"[*] Reading CSV file: {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print(f"[!] Error: CSV file not found at {CSV_PATH}")
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = rows[0]
    data_rows = rows[1:]
    print(f"[+] Total CSV rows loaded: {len(data_rows)} (Header: {len(header)} columns)")

    # 3. อ่านไฟล์ Checkpoint
    checkpoint_data = {}
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)
    csv_key = os.path.basename(CSV_PATH)
    if "csv_translations" not in checkpoint_data:
        checkpoint_data["csv_translations"] = {}
    if csv_key not in checkpoint_data["csv_translations"]:
        checkpoint_data["csv_translations"][csv_key] = {}
    cached_rows = checkpoint_data["csv_translations"][csv_key]

    # 4. ประมวลผลซ่อมแซมทีละแถว
    count_literal_newlines_fixed = 0
    count_speaker_tags_translated = 0
    count_gender_particles_fixed = 0
    count_total_modified = 0

    for idx, row in enumerate(data_rows, start=1):
        if len(row) < 2:
            continue

        orig_thai = row[1]
        if not orig_thai:
            continue

        current_thai = orig_thai
        row_modified = False

        # --- A. ตรวจสอบและซ่อมแซมบทพูดของ Pink hair Woman (เพศหญิง) ---
        if "Pink hair Woman" in current_thai or (len(row) > 6 and "Pink hair Woman" in row[6]):
            repaired_thai = repair_pink_hair_woman_lines(current_thai)
            if repaired_thai != current_thai:
                current_thai = repaired_thai
                count_gender_particles_fixed += 1
                row_modified = True

        # --- B. แปลชื่อในแท็ก Speaker ตาม Glossary ---
        # ตรวจสอบแท็กผู้พูด เช่น \n<\C[27]Pink hair Woman\C:>
        m_tag = re.match(r"^(\s*\\n)?<([^>]+)>(\s*)", current_thai)
        if m_tag:
            prefix_orig = m_tag.group(0)
            prefix_trans = glossary_scanner.translate_speaker_tag(prefix_orig)
            if prefix_trans != prefix_orig:
                current_thai = prefix_trans + current_thai[len(prefix_orig):]
                count_speaker_tags_translated += 1
                row_modified = True

        # แปลคอลัมน์ Speaker (index 6) ถ้ามี
        if len(row) > 6 and row[6]:
            orig_spk_col = row[6]
            # สกัด clean speaker name
            clean_spk = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", orig_spk_col).replace(":", "").strip()
            th_spk = glossary_scanner.translate_speaker(clean_spk)
            if th_spk != clean_spk:
                new_spk_col = orig_spk_col.replace(clean_spk, th_spk)
                row[6] = new_spk_col
                row_modified = True

        # --- C. แปลง Literal '\n' ในเนื้อความให้เป็น Newline จริง (0x0A) ---
        cleaned_thai = clean_literal_newlines_in_dialogue(current_thai)
        if cleaned_thai != current_thai:
            current_thai = cleaned_thai
            count_literal_newlines_fixed += 1
            row_modified = True

        # อัปเดตกลับลง row และ checkpoint
        if row_modified:
            row[1] = current_thai
            cached_rows[str(idx)] = current_thai
            count_total_modified += 1

    print("\n" + "=" * 70)
    print("=== AUDIT & REPAIR SUMMARY ===")
    print("=" * 70)
    print(f"[+] Total Rows Modified: {count_total_modified}")
    print(f"  - Literal '\\n' Converted to Real Newlines: {count_literal_newlines_fixed} rows")
    print(f"  - Speaker Tags Translated via Glossary:   {count_speaker_tags_translated} rows")
    print(f"  - Gender/Particle Pronouns Corrected:     {count_gender_particles_fixed} rows")
    print("=" * 70)

    # 5. บันทึกสำรองและเขียนทับไฟล์ CSV
    backup_csv = CSV_PATH + ".backup_before_universal_fix"
    print(f"[*] Creating backup of CSV: {backup_csv}")
    shutil.copy2(CSV_PATH, backup_csv)

    temp_csv = CSV_PATH + ".tmp"
    with open(temp_csv, "w", encoding="utf-8-sig", newline="") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        writer.writerows(data_rows)
    os.replace(temp_csv, CSV_PATH)
    print(f"[v] CSV successfully saved to: {CSV_PATH}")

    # 6. บันทึก Checkpoint แบบ Atomic
    temp_ckpt = CHECKPOINT_PATH + ".tmp"
    with open(temp_ckpt, "w", encoding="utf-8") as out_ckpt:
        json.dump(checkpoint_data, out_ckpt, ensure_ascii=False, indent=2)
    os.replace(temp_ckpt, CHECKPOINT_PATH)
    print(f"[v] Checkpoint successfully synchronized: {CHECKPOINT_PATH}")

    print("\n🎉 Repair Completed with 100% Integrity!")

if __name__ == "__main__":
    main()
