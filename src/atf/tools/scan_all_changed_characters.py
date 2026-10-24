"""
Scan All Changed Characters Script
เปรียบเทียบ Profile เดิม (ก่อนแก้) กับ Profile ใหม่ เพื่อหาตัวละครทั้งหมดที่เปลี่ยนแปลง
และสแกนตรวจสอบว่าตัวละครเหล่านั้นมีบทพูดใน CSV ที่แปลแล้วกี่บรรทัด และมีหางเสียงผิดหรือไม่
"""

import os
import sys
import glob
import json
import csv
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
PROFILES_DIR = os.path.join(TLAS_DATA, "profiles")
# Use the backup created right before our fixes
BACKUP_DIR = os.path.join(TLAS_DATA, "profiles_backup_20260927_081343")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
CHECKPOINT_PATH = os.path.join(TLAS_DATA, "chatgpt_translation_checkpoint.json")

def scan_all_changes():
    if not os.path.exists(BACKUP_DIR):
        print(f"[!] Backup dir not found at {BACKUP_DIR}")
        return

    print("="*65)
    print("=== FULL CHARACTER PROFILE DELTA SCAN ===")
    print("="*65)

    current_files = glob.glob(os.path.join(PROFILES_DIR, "*.json"))
    changed_characters = {}

    for pf in current_files:
        cname = os.path.basename(pf).replace(".json", "")
        old_pf = os.path.join(BACKUP_DIR, f"{cname}.json")
        if not os.path.exists(old_pf):
            continue

        try:
            with open(pf, "r", encoding="utf-8") as f:
                cur = json.load(f)
            with open(old_pf, "r", encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            continue

        cur_id = cur.get("identity", {})
        old_id = old.get("identity", {})
        cur_sp = cur.get("base_speech_style", {})
        old_sp = old.get("base_speech_style", {})

        diffs = []
        if cur_id.get("gender") != old_id.get("gender"):
            diffs.append(f"Gender: {old_id.get('gender')} -> {cur_id.get('gender')}")
        if cur_id.get("age") != old_id.get("age"):
            diffs.append(f"Age: {old_id.get('age')} -> {cur_id.get('age')}")
        if cur_sp.get("ending_particle") != old_sp.get("ending_particle"):
            diffs.append(f"Ending: '{old_sp.get('ending_particle')}' -> '{cur_sp.get('ending_particle')}'")
        if cur_sp.get("self_pronoun") != old_sp.get("self_pronoun"):
            diffs.append(f"Self: '{old_sp.get('self_pronoun')}' -> '{cur_sp.get('self_pronoun')}'")

        if diffs:
            changed_characters[cname] = {
                "diffs": diffs,
                "current_gender": cur_id.get("gender"),
                "current_age": cur_id.get("age"),
                "current_ending": cur_sp.get("ending_particle"),
                "old_ending": old_sp.get("ending_particle")
            }

    print(f"Total Profiles Analyzed: {len(current_files)}")
    print(f"Total Characters Changed (Gender/Age/Speech): {len(changed_characters)} characters\n")

    # Group changes
    gender_changes = [c for c, d in changed_characters.items() if any("Gender:" in x for x in d["diffs"])]
    age_changes = [c for c, d in changed_characters.items() if any("Age:" in x for x in d["diffs"])]
    ending_changes = [c for c, d in changed_characters.items() if any("Ending:" in x for x in d["diffs"])]

    print(f" - Characters with Gender Changed: {len(gender_changes)}")
    print(f" - Characters with Age Group Changed: {len(age_changes)}")
    print(f" - Characters with Ending Particle Changed: {len(ending_changes)}")

    print("\n" + "="*65)
    print("=== SCANNING GAME CSV FOR DIALOGUES OF ALL CHANGED CHARACTERS ===")
    print("="*65)

    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV not found at {CSV_PATH}")
        return

    speaker_line_counts = defaultdict(int)
    speaker_ka_lines = defaultdict(list)
    impacted_row_indices = []

    changed_names_lower = {k.lower(): k for k in changed_characters.keys()}

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            spk = row.get("Speaker", "").strip()
            if not spk:
                continue
            
            spk_matched = changed_names_lower.get(spk.lower())
            if spk_matched:
                speaker_line_counts[spk_matched] += 1
                impacted_row_indices.append(idx)
                
                # Column 'Initial' holds translated text
                trans_text = row.get("Initial", "") or row.get("Th_Trans", "")
                cur_info = changed_characters[spk_matched]
                
                # Check for particle anomalies (e.g. Male speaking 'ค่ะ'/'คะ')
                if cur_info["current_gender"] == "MALE" and any(p in trans_text for p in ["ค่ะ", "คะ"]):
                    speaker_ka_lines[spk_matched].append((idx, trans_text))

    print(f"Total Characters that actually speak in Game CSV: {len(speaker_line_counts)} characters out of {len(changed_characters)}")
    total_impacted_dialogues = sum(speaker_line_counts.values())
    print(f"Total Dialogue Lines Spoken by Changed Characters: {total_impacted_dialogues} lines")

    print("\n[Top Speaking Changed Characters]:")
    sorted_spks = sorted(speaker_line_counts.items(), key=lambda x: x[1], reverse=True)
    for spk, cnt in sorted_spks[:20]:
        diff_str = " | ".join(changed_characters[spk]["diffs"])
        print(f" * {spk}: {cnt} lines [{diff_str}]")

    print("\n" + "="*65)
    print("=== MALE CHARACTERS STILL SPEAKING 'ค่ะ' / 'คะ' IN TRANSLATED CSV ===")
    print("="*65)
    total_ka = sum(len(lines) for lines in speaker_ka_lines.values())
    print(f"Total Lines where Changed Male Characters Spoke 'ค่ะ'/'คะ': {total_ka} lines across {len(speaker_ka_lines)} characters")
    for spk, lines in speaker_ka_lines.items():
        print(f"\n * {spk} ({len(lines)} lines with 'ค่ะ'/'คะ'):")
        for idx, t in lines[:3]:
            print(f"    - Row {idx}: {t}")

    # Check Batches
    if os.path.exists(CHECKPOINT_PATH):
        batch_indices = set()
        for r_idx in impacted_row_indices:
            batch_indices.add((r_idx // 15) + 1)
        print("\n" + "="*65)
        print(f"Total Batches with Changed Characters: {len(batch_indices)} batches out of 643")
        print("="*65)

if __name__ == "__main__":
    scan_all_changes()
