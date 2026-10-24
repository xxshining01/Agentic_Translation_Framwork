#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Missing Speakers Enrollment & Synchronization Tool
เครื่องมือลงทะเบียนตัวละครที่มี Control Code หรือตกสำรวจเข้าสู่ TLAS Glossary, Character Profiles,
และซิงค์การแปล Speaker Tags ลงสู่ไฟล์ CSV และ Checkpoint อย่างสมบูรณ์ 100%
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
PROFILES_DIR = os.path.join(TLAS_DATA, "profiles")

def enroll_glossary_characters():
    print("[*] Reading Glossary from:", GLOSSARY_PATH)
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        glossary = json.load(f)

    target_dict = glossary.get("Characters", glossary)

    # 1. Pink hair Woman
    if "Pink hair Woman" not in target_dict:
        target_dict["Pink hair Woman"] = {
            "th": "หญิงสาวผมชมพู",
            "type": "Generic",
            "role_category": "Ambient",
            "analysis_target": False,
            "enforce": True,
            "aliases": ["Pink hair Woman", "\\C[27]Pink hair Woman\\C", "\\C[27]Pink hair Woman\\C:"],
            "reason": "Recovered from abnormal control code audit"
        }
    else:
        target_dict["Pink hair Woman"]["th"] = "หญิงสาวผมชมพู"
        target_dict["Pink hair Woman"]["aliases"] = ["Pink hair Woman", "\\C[27]Pink hair Woman\\C", "\\C[27]Pink hair Woman\\C:"]

    # 2. Alisa (Alisa / Peach Garden Camgirl Streamer)
    target_dict["Alisa"] = {
        "th": "Alisa",
        "type": "ProperNoun",
        "role_category": "Main",
        "analysis_target": True,
        "enforce": True,
        "aliases": ["Alisa", "Arisa", "\\C[27]Arisa\\C", "\\C[27]Arisa:\\C", "\\C[27]Alisa\\C", "\\C[27]Alisa:\\C"],
        "reason": "Main streamer character in Peach Garden (Map159)"
    }

    # 3. Both (ทั้งสองคน)
    target_dict["Both"] = {
        "th": "ทั้งสองคน",
        "type": "Generic",
        "role_category": "Ambient",
        "analysis_target": False,
        "enforce": True,
        "aliases": ["Both", "\\C[0]Both\\C", "\\C[0]Both:\\C"],
        "reason": "Dual speakers dialogue tag"
    }

    # 4. ??? (???)
    target_dict["???"] = {
        "th": "???",
        "type": "Generic",
        "role_category": "Ambient",
        "analysis_target": False,
        "enforce": True,
        "aliases": ["???", "\\C[18]\\fb???\\C\\fb:", "\\C[27]???:\\C:", "\\C[21]???:\\C", "\\C[27]???\\C:", "\\C[27]???:\\C"],
        "reason": "Unknown speaker dialogue tag"
    }

    # บันทึกสำรอง
    shutil.copy2(GLOSSARY_PATH, GLOSSARY_PATH + ".backup_before_enroll")

    temp_glossary = GLOSSARY_PATH + ".tmp"
    with open(temp_glossary, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
    os.replace(temp_glossary, GLOSSARY_PATH)
    print(f"[v] Glossary successfully updated with 4 characters at: {GLOSSARY_PATH}")

def sync_csv_and_checkpoint():
    print(f"\n[*] Synchronizing CSV and Checkpoint with updated Glossary...")

    # นำเข้า GlossaryScanner หลังอัปเดต Glossary
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
    from atf.core.glossary_scanner import GlossaryScanner
    glossary_scanner = GlossaryScanner(TLAS_DATA)

    # อ่าน CSV
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = rows[0]
    data_rows = rows[1:]

    # อ่าน Checkpoint
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

    updated_count = 0
    pink_hair_fixed = 0
    arisa_fixed = 0
    both_fixed = 0

    for idx, row in enumerate(data_rows, start=1):
        if len(row) < 2:
            continue

        orig_thai = row[1]
        if not orig_thai:
            continue

        current_thai = orig_thai
        row_modified = False

        # 1. จัดการ Pink hair Woman (เพศหญิง + หางเสียง + แปลแท็ก)
        if "Pink hair Woman" in current_thai:
            current_thai = current_thai.replace("เรากำลังทำเรื่องซนๆ กันอยู่เหรอครับ", "เรากำลังทำเรื่องซนๆ กันอยู่เหรอคะ")
            current_thai = current_thai.replace("การแสดงตามแผนการ..ใช่ไหมครับ", "การแสดงตามแผนการ..ใช่ไหมคะ")
            current_thai = current_thai.replace("ฉ-ผมชินแล้วล่ะครับ", "ฉ-ฉันชินแล้วล่ะค่ะ")
            current_thai = current_thai.replace("ไม่กระทบกับงานครับ", "ไม่กระทบกับงานค่ะ")
            current_thai = current_thai.replace("เขาถึงตีผมแค่ตรงนั้นไงครับ", "เขาถึงตีฉันแค่ตรงนั้นไงคะ")
            current_thai = current_thai.replace("Pink hair Woman", "หญิงสาวผมชมพู")
            pink_hair_fixed += 1
            row_modified = True

        if len(row) > 6 and "Pink hair Woman" in row[6]:
            row[6] = row[6].replace("Pink hair Woman", "หญิงสาวผมชมพู")
            row_modified = True

        # 2. จัดการ Both -> ทั้งสองคน
        if "Both:" in current_thai or "Both" in current_thai:
            # เช็คว่าอยู่ในแท็ก <\C[0]Both:\C>
            m_both = re.search(r"<(\\C\[\d+\])?Both:?(\\C)?>", current_thai)
            if m_both:
                old_tag = m_both.group(0)
                new_tag = old_tag.replace("Both", "ทั้งสองคน")
                current_thai = current_thai.replace(old_tag, new_tag)
                both_fixed += 1
                row_modified = True

        if len(row) > 6 and "Both" in row[6]:
            row[6] = row[6].replace("Both", "ทั้งสองคน")
            row_modified = True

        # 3. จัดการ Arisa (คงรูปแท็ก \C[27]Arisa:\C ไว้อย่างถูกต้อง)
        if "Arisa" in current_thai:
            arisa_fixed += 1

        # 4. แปลง Speaker Tag ทั่วไปตาม Glossary Scanner
        m_tag = re.match(r"^(\s*\\n)?<([^>]+)>(\s*)", current_thai)
        if m_tag:
            prefix_orig = m_tag.group(0)
            prefix_trans = glossary_scanner.translate_speaker_tag(prefix_orig)
            if prefix_trans != prefix_orig:
                current_thai = prefix_trans + current_thai[len(prefix_orig):]
                row_modified = True

        # 5. แก้ไข Literal \n ในเนื้อความบทพูดให้เป็น Newline จริง
        m_dialogue = re.match(r"^(\s*\\n)?<([^>]+)>", current_thai)
        if m_dialogue:
            prefix = m_dialogue.group(0)
            pure = current_thai[len(prefix):]
        else:
            prefix = ""
            pure = current_thai

        if "\\n" in pure or "\\r\\n" in pure:
            pure = pure.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")
            current_thai = f"{prefix}{pure}"
            row_modified = True

        if row_modified:
            row[1] = current_thai
            cached_rows[str(idx)] = current_thai
            updated_count += 1

    print("\n" + "=" * 70)
    print("=== SYNCHRONIZATION SUMMARY ===")
    print("=" * 70)
    print(f"[+] Total Rows Synchronized: {updated_count}")
    print(f"  - Pink hair Woman Lines Processed: {pink_hair_fixed}")
    print(f"  - Both Lines Processed:            {both_fixed}")
    print(f"  - Arisa Lines Audited:             {arisa_fixed}")
    print("=" * 70)

    # บันทึกไฟล์ CSV
    backup_csv = CSV_PATH + ".backup_enroll"
    shutil.copy2(CSV_PATH, backup_csv)

    temp_csv = CSV_PATH + ".tmp"
    with open(temp_csv, "w", encoding="utf-8-sig", newline="") as out_f:
        writer = csv.writer(out_f)
        writer.writerow(header)
        writer.writerows(data_rows)
    os.replace(temp_csv, CSV_PATH)
    print(f"[v] CSV successfully saved: {CSV_PATH}")

    # บันทึก Checkpoint
    temp_ckpt = CHECKPOINT_PATH + ".tmp"
    with open(temp_ckpt, "w", encoding="utf-8") as out_ckpt:
        json.dump(checkpoint_data, out_ckpt, ensure_ascii=False, indent=2)
    os.replace(temp_ckpt, CHECKPOINT_PATH)
    print(f"[v] Checkpoint successfully synchronized: {CHECKPOINT_PATH}")

def main():
    print("=" * 70)
    print("=== ATF ENROLL MISSING SPEAKERS & DUAL-STATE SYNC ===")
    print("=" * 70)
    enroll_glossary_characters()
    sync_csv_and_checkpoint()
    print("\n🎉 All missing speakers enrolled and synchronized 100%!")

if __name__ == "__main__":
    main()
