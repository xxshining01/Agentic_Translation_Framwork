#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Investigation & Reharvest Tool for Untranslated Dialogue Lines
สคริปต์สืบสวนและรวบรวมบทสนทนาภาษาอังกฤษที่หลุดรอดการแปลใน CSV:
1. ตรวจสอบแถวที่ผู้ใช้รายงาน (Map023 และตัวอย่าง Shion)
2. สแกนหาแถวทั้งหมดใน CSV ที่:
   - Displayable == 'Yes'
   - เป็นข้อความบทสนทนา (มี Speaker Tag หรือ Role == Dialogue/Story/Choice)
   - Initial ยังเป็นภาษาอังกฤษล้วน (ไม่มีตัวอักษรภาษาไทย \u0E00-\u0E7F)
   - คัดกรอง Pure Symbols และ Single Locked Character Name ออกอย่างแม่นยำ
3. สรุปจำแนกตามตัวละคร (Shion, Dan, Jinnie, etc.)
4. บันทึกผลลัพธ์เป็น JSON Queue สำหรับส่งให้ ChatGPT Bridge Server แปลเก็บตก 100%
"""

import os
import sys
import re
import csv
import json
from collections import Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
GLOSSARY_PATH = os.path.join(TLAS_DATA, "tlas_glossary.json")
CHECKPOINT_PATH = os.path.join(TLAS_DATA, "chatgpt_translation_checkpoint.json")
OUTPUT_QUEUE_PATH = os.path.join(TLAS_DATA, "untranslated_dialogues_reharvest.json")

def contains_thai(text: str) -> bool:
    """ตรวจสอบว่าข้อความมีตัวอักษรภาษาไทยหรือไม่"""
    return bool(re.search(r'[\u0E00-\u0E7F]', text))

def extract_speaker_tag(orig_text: str):
    """สกัด Speaker Tag ทุกรูปแบบจากต้นฉบับ"""
    if not orig_text:
        return False, "", "", ""
    m = re.match(r"^(\s*\\n)?<([^>]+)>", orig_text)
    if not m:
        return False, "", "", orig_text
    full_prefix = m.group(0)
    inner_content = m.group(2)
    pure_dialogue = orig_text[len(full_prefix):].strip()
    clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content)
    clean_name = clean_name.replace(":", "").strip()
    if clean_name:
        return True, full_prefix, clean_name, pure_dialogue
    return False, "", "", orig_text

def is_pure_symbol_dialogue(text: str) -> bool:
    """ตรวจสอบว่าข้อความเป็นเฉพาะสัญลักษณ์หรือโค้ดล้วนๆ หรือไม่"""
    if not text or not text.strip():
        return True
    clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text)
    has_letters = bool(re.search(r'[A-Za-z0-9]', clean))
    return not has_letters

def is_single_locked_name(text: str, locked_terms: set, current_speaker: str = "") -> bool:
    """ตรวจสอบว่าเป็นแค่ชื่อตัวละครเดี่ยวๆ หรือไม่"""
    if not text or not text.strip():
        return True
    clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text).strip()
    clean = re.sub(r'GabText\s*', '', clean, flags=re.IGNORECASE).strip()
    letters_only = re.sub(r"[^A-Za-z0-9]", "", clean).lower()
    if not letters_only or len(letters_only) <= 1 or re.match(r"^z+$", letters_only):
        return True

    stripped = re.sub(r"^[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+|[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+$", "", clean).strip()
    stutter_match = re.match(r"^[A-Za-z]\s*[-–—]\s*(.+)$", stripped)
    cand = stutter_match.group(1).strip() if stutter_match else stripped
    cand = re.sub(r"^[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+|[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+$", "", cand).strip().lower()

    if cand in locked_terms or (current_speaker and cand == current_speaker.lower()):
        return True
    return False

def main():
    print("=" * 80)
    print("=== ATF INVESTIGATION & REHARVEST: UNTRANSLATED DIALOGUE LINES ===")
    print("=" * 80)

    if not os.path.exists(CSV_PATH):
        print(f"[!] Error: CSV file not found at {CSV_PATH}")
        return

    # 1. โหลด Locked Terms จาก Glossary
    locked_terms = {
        "dan", "shion", "masaru", "lily", "lucas", "erica", "bonnie", "drex",
        "reiko", "akane", "yearl", "toru", "ludo", "rum", "foregrave", "the earl",
        "jords", "bastio", "masgolf", "natalie", "ritchie", "rose", "drake",
        "lucy", "alisa", "arisa", "aubrie", "bazz", "big b", "mayor", "hikari",
        "jasmine", "kintah", "chisato", "patrick", "harold", "connie", "jonathan"
    }
    if os.path.exists(GLOSSARY_PATH):
        try:
            with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            chars = gdata.get("Characters", gdata.get("characters", {}))
            for k, v in chars.items():
                if isinstance(v, dict) and v.get("th", "").strip().lower() == k.strip().lower():
                    locked_terms.add(k.strip().lower())
        except Exception as e:
            print(f"[!] Warning reading glossary: {e}")

    # 2. อ่านไฟล์ CSV
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    print(f"[*] Total Rows in CSV: {len(rows):,}")

    # 3. ตัวอย่างที่ผู้ใช้รายงาน
    user_samples = [
        "T-Ten times", "O.-.Oh, okay", "Wonderful n-night", "Gurantheed",
        "Am not", "Grrr", "Hey..! Ugh, dummy", "..Oh....",
        "Right, Dan?", "W-W..What", "Get offf Daaann"
    ]

    print("\n--- CHECKING USER REPORTED SAMPLES IN CSV ---")
    matched_user_samples = []
    for r_idx, r in enumerate(rows, start=2):
        orig = r[0] if len(r) > 0 else ""
        init = r[1] if len(r) > 1 else ""
        fn = r[2] if len(r) > 2 else ""
        row_id = r[3] if len(r) > 3 else ""
        role = r[5] if len(r) > 5 else ""
        spk = r[6] if len(r) > 6 else ""

        for sample in user_samples:
            if sample.lower() in orig.lower():
                has_th = contains_thai(init)
                print(f"[Sample Found] Row {r_idx} [{fn}:{row_id}] ({spk}):")
                print(f"   ORIG:    {orig}")
                print(f"   INITIAL: {init}")
                print(f"   STATUS:  {'TRANSLATED (THAI)' if has_th else '🚨 UNTRANSLATED (ENGLISH)'}")
                matched_user_samples.append((r_idx, fn, spk, orig, init, has_th))
                break

    # 4. สแกนหาบทสนทนาภาษาอังกฤษทั้งหมดที่ยังไม่ถูกแปล
    untranslated_queue = []
    speaker_counter = Counter()
    map_counter = Counter()

    for r_idx, r in enumerate(rows, start=2):
        orig = r[0] if len(r) > 0 else ""
        init = r[1] if len(r) > 1 else ""
        fn = r[2] if len(r) > 2 else ""
        row_id = r[3] if len(r) > 3 else ""
        role = r[5] if len(r) > 5 else ""
        spk = r[6] if len(r) > 6 else ""
        disp = r[7].strip() if len(r) > 7 else ""

        # เฉพาะแถวที่แสดงผลในเกม (Displayable == 'Yes')
        if disp.lower() != "yes":
            continue

        has_tag, full_prefix, clean_spk, pure_text = extract_speaker_tag(orig)
        is_dialogue = has_tag or ("Dialogue" in role) or ("Story" in role) or (fn.startswith("Map") and role != "Event Name")

        if not is_dialogue:
            continue

        # ตรวจสอบว่าช่อง Initial มีภาษาไทยหรือไม่
        # กรณี Initial ว่างเปล่า หรือ Initial ไม่มีตัวอักษรภาษาไทยเลย
        pure_content = pure_text if has_tag else orig
        if not contains_thai(init):
            # คัดกรองตัวเลขเงิน เช่น 18G, 20G
            clean_num = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<]", "", pure_content).strip()
            if re.match(r"^\d+\s*G?$", clean_num, flags=re.IGNORECASE) or clean_num.lower() in {"wussapps", "onlyf*ps"}:
                continue

            # คัดกรองสัญลักษณ์ล้วน เช่น ........., \.\^
            if is_pure_symbol_dialogue(pure_content):
                continue

            # คัดกรองชื่อตัวละครเดี่ยวๆ
            final_spk = clean_spk if has_tag else spk
            if is_single_locked_name(pure_content, locked_terms, current_speaker=final_spk):
                continue

            # แถวนี้คือบทสนทนาเนื้อเรื่องจริงที่ยังเป็นภาษาอังกฤษและต้องแปล!
            speaker_counter[final_spk or "[No Speaker]"] += 1
            map_counter[fn] += 1
            untranslated_queue.append({
                "csv_index": r_idx,
                "filename": fn,
                "row": row_id,
                "role": role,
                "speaker": final_spk,
                "prefix": full_prefix if has_tag else "",
                "original": orig,
                "initial": init,
                "pure_text": pure_content
            })

    print("\n" + "=" * 80)
    print("=== GLOBAL UNTRANSLATED DIALOGUE AUDIT RESULTS ===")
    print("=" * 80)
    print(f"Total Meaningful Dialogue Lines Requiring Translation: {len(untranslated_queue):,} lines")

    print("\nTop 15 Characters with Untranslated Dialogues:")
    for spk, cnt in speaker_counter.most_common(15):
        print(f"  • {spk:25}: {cnt:4} lines")

    print("\nTop 10 Maps / Files with Untranslated Dialogues:")
    for m, cnt in map_counter.most_common(10):
        print(f"  • {m:25}: {cnt:4} lines")

    # บันทึกคิวสำหรับส่งแปล
    with open(OUTPUT_QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(untranslated_queue, f, ensure_ascii=False, indent=2)

    print(f"\n[v] Reharvest Queue successfully saved to: {OUTPUT_QUEUE_PATH}")
    print(f"[v] Ready for ChatGPT Batch Translation via Bridge Server!")

if __name__ == "__main__":
    main()
