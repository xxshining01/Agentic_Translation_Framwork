#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Abnormal Speaker Scanner & Parity Audit Tool
เครื่องมือค้นหาและตรวจสอบตัวละครทั้งหมดในเกมที่มีรูปแบบ Speaker ผิดปกติ
(เช่น ถูกครอบด้วย Color Code \\C[n], Font Code \\fb, Icon Code \\I[n], ฯลฯ)
พร้อมตรวจสอบว่า:
1. ตัวละครเหล่านี้มีใน tlas_glossary.json หรือไม่
2. มี Character Profile หรือยัง
3. เพศ (Gender) สอดคล้องกับชื่อหรือไม่ (เช่น มีคำว่า Woman, Girl, Lady แต่ถูกตั้งเป็น MALE หรือไม่)
"""

import os
import sys
import re
import csv
import json
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
GLOSSARY_PATH = os.path.join(TLAS_DATA, "tlas_glossary.json")
PROFILES_DIR = os.path.join(TLAS_DATA, "profiles")

def strip_control_codes(text: str) -> str:
    """ลบรหัสควบคุม RPG Maker ทั้งหมดออกจากชื่อ"""
    if not text:
        return ""
    # ลบ \C[n], \I[n], \N[n], \V[n], \C, \fb, \fi, \{, \}, \., \|, \!, \^, \$, etc.
    cleaned = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", text)
    cleaned = re.sub(r"\\[\{\}\.\|\!\^\$\\]", "", cleaned)
    cleaned = cleaned.replace(":", "").strip()
    return cleaned

def main():
    print("=" * 75)
    print("=== ATF ABNORMAL SPEAKER AUDIT & SCANNER ===")
    print("=" * 75)

    # 1. โหลด Glossary
    glossary = {}
    if os.path.exists(GLOSSARY_PATH):
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            glossary = json.load(f)
    chars_glossary = glossary.get("Characters", glossary)
    all_glossary_keys = set(glossary.keys()) | set(chars_glossary.keys())
    # สร้าง map จากคำแปลภาษาไทย -> ชื่ออังกฤษ
    th_to_en_map = {}
    for en_k, val in chars_glossary.items():
        if isinstance(val, dict) and "th" in val:
            th_to_en_map[val["th"]] = en_k
    for en_k, val in glossary.items():
        if isinstance(val, dict) and "th" in val:
            th_to_en_map[val["th"]] = en_k

    # 2. โหลด Profiles
    existing_profiles = set()
    profile_genders = {}
    if os.path.exists(PROFILES_DIR):
        for pf in os.listdir(PROFILES_DIR):
            if pf.endswith(".json"):
                char_name = pf[:-5]
                existing_profiles.add(char_name)
                try:
                    with open(os.path.join(PROFILES_DIR, pf), "r", encoding="utf-8") as pf_f:
                        pdata = json.load(pf_f)
                        profile_genders[char_name] = pdata.get("identity", {}).get("gender", "UNKNOWN")
                except Exception:
                    pass

    print(f"[*] Total Characters in Glossary: {len(chars_glossary)} (Top-level: {len(glossary)})")
    print(f"[*] Total Profiles loaded: {len(existing_profiles)}")

    # 3. สแกน CSV หา Speaker Tags ทั้งหมด
    print(f"[*] Scanning CSV: {CSV_PATH}")
    abnormal_speakers = defaultdict(lambda: {"count": 0, "raw_samples": set(), "maps": set()})
    all_speakers = defaultdict(int)

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row_idx, row in enumerate(reader, start=2):
            if not row or len(row) < 2:
                continue

            orig_text = row[0]
            speaker_col = row[6] if len(row) > 6 else ""
            map_name = row[2] if len(row) > 2 else ""

            # ดึงจาก Speaker Column
            candidates = []
            if speaker_col:
                candidates.append(speaker_col)

            # ดึงจาก Tag ใน Original text เช่น \n<\C[27]Pink hair Woman\C:>
            m = re.match(r"^(\s*\\n)?<([^>]+)>", orig_text)
            if m:
                candidates.append(m.group(2))

            for cand in candidates:
                cand_clean = cand.strip()
                all_speakers[cand_clean] += 1

                # ตรวจสอบว่ามี Control Code หรือรูปแบบผิดปกติหรือไม่
                has_code = bool(re.search(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\{\}\.\|\!\^\$\\]", cand_clean))
                if has_code:
                    stripped = strip_control_codes(cand_clean)
                    if stripped:
                        abnormal_speakers[stripped]["count"] += 1
                        abnormal_speakers[stripped]["raw_samples"].add(cand_clean)
                        if map_name:
                            abnormal_speakers[stripped]["maps"].add(map_name)

    print("\n" + "=" * 75)
    print(f"=== FOUND {len(abnormal_speakers)} CHARACTERS WITH CONTROL CODES / ABNORMAL TAGS ===")
    print("=" * 75)

    female_keywords = ["woman", "girl", "lady", "maid", "female", "mother", "sister", "daughter", "queen", "princess", "hooker", "housewife", "actress"]
    male_keywords = ["man", "boy", "lord", "male", "father", "brother", "son", "king", "prince", "priest", "uncle", "grandfather", "gentleman"]

    report_items = []

    for stripped_name, info in sorted(abnormal_speakers.items(), key=lambda x: x[1]["count"], reverse=True):
        canonical_en = th_to_en_map.get(stripped_name, stripped_name)
        in_glossary = stripped_name in chars_glossary or stripped_name in glossary or stripped_name in th_to_en_map
        glossary_th = ""
        if stripped_name in chars_glossary:
            glossary_th = chars_glossary[stripped_name].get("th", "")
        elif stripped_name in glossary:
            glossary_th = glossary[stripped_name].get("th", "")
        elif stripped_name in th_to_en_map:
            glossary_th = stripped_name

        has_profile = stripped_name in existing_profiles or canonical_en in existing_profiles
        gender = profile_genders.get(stripped_name, profile_genders.get(canonical_en, "NO_PROFILE"))

        # ตรวจสอบความขัดแย้งทางเพศ
        name_lower = stripped_name.lower()
        gender_conflict = False
        inferred_gender = "UNKNOWN"
        if any(kw in name_lower for kw in female_keywords):
            inferred_gender = "FEMALE"
            if gender == "MALE":
                gender_conflict = True
        elif any(kw in name_lower for kw in male_keywords):
            inferred_gender = "MALE"
            if gender == "FEMALE":
                gender_conflict = True

        report_items.append({
            "name": stripped_name,
            "count": info["count"],
            "raw_samples": list(info["raw_samples"]),
            "maps": list(info["maps"])[:3],
            "in_glossary": in_glossary,
            "glossary_th": glossary_th,
            "has_profile": has_profile,
            "gender": gender,
            "inferred_gender": inferred_gender,
            "gender_conflict": gender_conflict
        })

        status_glossary = f"TH: '{glossary_th}'" if in_glossary else "[MISSING GLOSSARY]"
        status_profile = f"Profile: {gender}" if has_profile else "[MISSING PROFILE]"
        status_conflict = " ⚠️ GENDER CONFLICT!" if gender_conflict else ""

        print(f"\n[!] Character: '{stripped_name}' (Lines: {info['count']})")
        print(f"    Raw Formats: {list(info['raw_samples'])}")
        print(f"    Maps: {list(info['maps'])[:3]}")
        print(f"    Glossary: {status_glossary} | {status_profile}{status_conflict}")

    print("\n" + "=" * 75)
    print("=== SUMMARY OF ISSUES ===")
    missing_gloss = [r["name"] for r in report_items if not r["in_glossary"]]
    missing_prof = [r["name"] for r in report_items if not r["has_profile"]]
    conflicts = [r["name"] for r in report_items if r["gender_conflict"]]

    print(f"1. Total Characters with Control Codes: {len(report_items)}")
    print(f"2. Missing from Glossary: {len(missing_gloss)} -> {missing_gloss}")
    print(f"3. Missing Profile: {len(missing_prof)} -> {missing_prof}")
    print(f"4. Gender Conflicts: {len(conflicts)} -> {conflicts}")
    print("=" * 75)

    # บันทึกรายงานเป็น JSON
    report_file = os.path.join(TLAS_DATA, "abnormal_speakers_audit.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_items, f, ensure_ascii=False, indent=2)
    print(f"[v] Full audit report saved to: {report_file}")

if __name__ == "__main__":
    main()
