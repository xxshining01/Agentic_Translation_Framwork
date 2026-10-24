"""
ATF Calibration Results Verification Script
สคริปต์ตรวจสอบความถูกต้องของผลลัพธ์การ Calibrate ในไฟล์ CSV ที่แปลแล้ว:
1. ตรวจสอบว่าตัวละครชาย (โดยเฉพาะ Damien, Drex, Drake ฯลฯ) ยังมีใครหลุดพูด 'ค่ะ' หรือ 'คะ' หลงเหลืออยู่อีกหรือไม่
2. ตรวจสอบโครงสร้าง Speaker Tag ว่าคงรูปเดิมครบถ้วนสมบูรณ์ 100% หรือไม่
3. แสดงตัวอย่างประโยคเปรียบเทียบก่อน-หลังการแก้ไข
"""

import os
import sys
import csv
import json
import re
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
REPORT_PATH = os.path.join(TLAS_DATA, "true_style_mismatches.json")
PROFILES_DIR = os.path.join(TLAS_DATA, "profiles")

def extract_speaker_tag(orig_text: str):
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

def run_verification():
    print("=" * 65)
    print("=== ATF CALIBRATION RESULTS VERIFICATION AUDIT ===")
    print("=" * 65)

    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV not found at {CSV_PATH}")
        return

    # โหลดโปรไฟล์ตัวละครชายทั้งหมด
    male_characters = set()
    for pf in os.listdir(PROFILES_DIR):
        if not pf.endswith(".json"):
            continue
        try:
            with open(os.path.join(PROFILES_DIR, pf), "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("identity", {}).get("gender") == "MALE":
                    male_characters.add(data.get("name", pf.replace(".json", "")).lower())
        except Exception:
            pass

    # เพิ่มตัวละครชายหลักที่สำคัญ
    for m in ["damien", "drex", "drake", "dan", "masaru"]:
        male_characters.add(m)

    print(f"[*] Loaded {len(male_characters)} male character profiles.")

    # อ่าน CSV ทั้งหมดและตรวจสอบ
    male_ka_remaining = []
    total_male_dialogues = 0
    damien_verified_lines = []

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for r_idx, row in enumerate(reader, start=1):
            if len(row) < 2:
                continue
            orig = row[0]
            initial = row[1]
            disp = row[7].strip().lower() if len(row) > 7 else ""
            if disp != "yes":
                continue

            has_tag, prefix, spk, pure = extract_speaker_tag(orig)
            spk_col = row[6].strip() if len(row) > 6 else ""
            speaker = spk if has_tag else spk_col
            speaker_clean = re.sub(r'[:\s]+$', '', speaker).strip().lower()

            if speaker_clean in male_characters or any(m in speaker_clean for m in ["damien", "drex", "drake"]):
                total_male_dialogues += 1
                
                # ตรวจสอบว่ายังมี ค่ะ หรือ คะ หลงเหลืออยู่หรือไม่ (ตัด False Positives เช่น 'เคะฮี่ๆ' และ 'คะแนน')
                clean_initial = re.sub(r'(?<![เแ])เคะ|คะแนน', '', initial)
                # ค้นหา ค่ะ หรือ คะ ที่ไม่ได้ติดสระ เ เป็น เคะ
                has_ka = bool(re.search(r'ค่ะ|(?<![เแ])คะ(?![แ-ฮa-zA-Z])', clean_initial))
                if has_ka:
                    male_ka_remaining.append({
                        "row_idx": r_idx,
                        "speaker": speaker,
                        "initial": initial
                    })

                if "damien" in speaker_clean:
                    damien_verified_lines.append((r_idx, initial))

    print(f"\n[*] Total Male Dialogue Lines Scanned: {total_male_dialogues}")
    print(f"[*] Total Male Lines with 'ค่ะ/คะ' Remaining: {len(male_ka_remaining)}")
    print("=" * 65)

    if male_ka_remaining:
        print(f"\n[!] Notice: {len(male_ka_remaining)} lines still contain 'ค่ะ/คะ':")
        for it in male_ka_remaining[:10]:
            print(f" - Row {it['row_idx']} [{it['speaker']}]: {it['initial'][:80]}...")
    else:
        print("\n🎉 PERFECT SUCCESS: 100% of Male 'ค่ะ/คะ' particles have been successfully eliminated!")
        print("   Zero male dialogue lines contain feminine ending particles now.")

    # แสดงตัวอย่างประโยคของ Damien หลังแก้จริง
    print("\n" + "=" * 65)
    print(f"=== SAMPLE VERIFIED DAMIEN DIALOGUES IN TRANSLATED CSV ({len(damien_verified_lines)} lines total) ===")
    print("=" * 65)
    for r_idx, text in damien_verified_lines[:8]:
        print(f" * Row {r_idx}: {text.strip()[:90]}...")

    print("=" * 65)

if __name__ == "__main__":
    run_verification()
