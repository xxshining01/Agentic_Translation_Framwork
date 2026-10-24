"""
Scan Translation Style & Pronoun Mismatches Script
สแกนหาประโยคใน CSV ที่แปลแล้ว ซึ่งผู้พูดมีสรรพนามหรือคำลงท้ายหางเสียงขัดแย้งกับ Character Profile
(เช่น ตัวละครชายใช้ 'ค่ะ/คะ/จ้ะ/หนู' หรือ ตัวละครหญิงใช้ 'ครับ/ฮะ/กระผม' หรือ ตัวละครผู้ใหญ่/คนชราใช้ 'หนู')
"""

import os
import sys
import glob
import json
import csv
import re
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
PROFILES_DIR = os.path.join(TLAS_DATA, "profiles")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")

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

def load_profiles():
    profiles = {}
    for pf in glob.glob(os.path.join(PROFILES_DIR, "*.json")):
        cname = os.path.basename(pf).replace(".json", "")
        try:
            with open(pf, "r", encoding="utf-8") as f:
                data = json.load(f)
                profiles[cname.lower()] = {
                    "name": data.get("name", cname),
                    "gender": data.get("identity", {}).get("gender", "UNKNOWN"),
                    "age": data.get("identity", {}).get("age", "ADULT"),
                    "ending": data.get("base_speech_style", {}).get("ending_particle", ""),
                    "self_pronoun": data.get("base_speech_style", {}).get("self_pronoun", "ฉัน"),
                    "target_pronoun": data.get("base_speech_style", {}).get("target_pronoun", "นาย"),
                }
        except Exception:
            pass
    return profiles

def run_scan():
    profiles = load_profiles()
    print(f"[*] Loaded {len(profiles)} character profiles.")
    
    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV not found at {CSV_PATH}")
        return

    mismatches = []
    total_dialogues = 0

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        
        for r_idx, row in enumerate(reader, start=1):
            if len(row) < 2:
                continue
            orig_text = row[0]
            initial_text = row[1]
            filename = row[2] if len(row) > 2 else ""
            speaker_col = row[6] if len(row) > 6 else ""
            disp = row[7].strip().lower() if len(row) > 7 else ""
            
            if disp != "yes":
                continue
                
            has_tag, prefix, spk_extracted, pure_text = extract_speaker_tag(orig_text)
            speaker = spk_extracted if has_tag else (speaker_col.strip() if speaker_col else "")
            
            if not speaker:
                continue
                
            # ตัดเครื่องหมายโคลอนและสัญลักษณ์ในชื่อ
            spk_clean = re.sub(r'[:\s]+$', '', speaker).strip()
            spk_info = profiles.get(spk_clean.lower())
            
            # ถ้าไม่เจอ ลองหาแบบ substring หรือ alias
            if not spk_info:
                for k, v in profiles.items():
                    if k in spk_clean.lower() or spk_clean.lower() in k:
                        spk_info = v
                        break
                        
            if not spk_info:
                continue
                
            total_dialogues += 1
            gender = spk_info["gender"]
            age = spk_info["age"]
            
            # ตรวจสอบความขัดแย้งในคำแปลภาษาไทย (Initial)
            th_text = initial_text
            issues = []
            
            # 1. ผู้ชาย แต่ใช้คำลงท้ายหรือสรรพนามผู้หญิง
            if gender == "MALE":
                for fem_word in ["ค่ะ", "คะ", "จ้ะ", "ดิฉัน"]:
                    # หลีกเลี่ยง False Positive เช่น "นะคะ" ตรวจในคำ
                    if fem_word in th_text:
                        issues.append(f"Male using feminine particle/pronoun '{fem_word}'")
                        break
                # ถ้าผู้ชายใช้ 'หนู' แทนตัวเอง
                if re.search(r'\bหนู\b|หนู[ว่า|จะ|ขอ|ไป|ไม่]', th_text):
                    issues.append("Male using 'หนู'")

            # 2. ผู้หญิง แต่ใช้คำลงท้ายหรือสรรพนามผู้ชาย
            elif gender == "FEMALE":
                for masc_word in ["ครับ", "ฮะ", "กระผม"]:
                    if masc_word in th_text:
                        issues.append(f"Female using masculine particle/pronoun '{masc_word}'")
                        break

            # 3. ผู้ใหญ่/คนชรา แต่แทนตัวเองว่า 'หนู'
            if age in ["ADULT", "ELDER"]:
                if re.search(r'หนู[ว่า|จะ|ขอ|ไป|ไม่|ชอบ]|ตัวหนู', th_text):
                    # ยกเว้นกรณีพูดถึงหนู (สัตว์)
                    if not any(rat_w in th_text for rat_w in ["หนูสกปรก", "กับดักหนู", "ตัวหนูวิ่ง"]):
                        issues.append(f"{age} character referring to self as 'หนู'")

            if issues:
                mismatches.append({
                    "row_idx": r_idx,
                    "filename": filename,
                    "speaker": spk_clean,
                    "profile_gender": gender,
                    "profile_age": age,
                    "expected_ending": spk_info["ending"],
                    "expected_self": spk_info["self_pronoun"],
                    "original": orig_text,
                    "current_thai": th_text,
                    "issues": issues
                })

    print("="*65)
    print("=== TRANSLATION STYLE & PRONOUN MISMATCH AUDIT ===")
    print("="*65)
    print(f"Total Dialogues Scanned with Known Profiles: {total_dialogues}")
    print(f"Total Mismatches Found: {len(mismatches)}")
    print("="*65)
    
    # สรุปตามตัวละคร
    char_counts = defaultdict(int)
    for m in mismatches:
        char_counts[m["speaker"]] += 1
        
    print("\n[Mismatches by Character]:")
    for ch, cnt in sorted(char_counts.items(), key=lambda x: x[1], reverse=True):
        print(f" - {ch}: {cnt} lines")

    print("\n[Sample Mismatches (First 10)]:")
    for m in mismatches[:10]:
        print(f"\nRow {m['row_idx']} [{m['filename']}] Speaker: {m['speaker']} ({m['profile_gender']}, {m['profile_age']})")
        print(f" Issues: {', '.join(m['issues'])}")
        print(f" Orig: {m['original'][:80]}...")
        print(f" Thai: {m['current_thai'][:80]}...")

    # บันทึกรายงาน JSON
    out_report = os.path.join(TLAS_DATA, "style_mismatch_report.json")
    with open(out_report, "w", encoding="utf-8") as f:
        json.dump(mismatches, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Full report saved to: {out_report}")

if __name__ == "__main__":
    run_scan()
