#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Character Profile Ingestion & Delta Speaker Enrollment Tool
(ADR-024 / SAD-010 / SDD-010 Compliant)

หน้าที่:
1. ซิงค์และคัดลอก Baseline Character Profiles (442 โปรไฟล์เดิม)
   เข้าสู่ไดเรกทอรีปลายทางของแพตช์ v0.35 (E:\\SummerStolenV035_PUBLIC_patch\\New folder\\tlas\\profiles)
2. สแกน Speakers ทั้งหมดใน processed_dialogues_v3.csv โดยเฉพาะแถวบทสนทนาใหม่ของ v0.35
3. ตรวจจับ Speakers ใหม่ที่ยังไม่มีโปรไฟล์ หรือไม่มีใน Master Glossary
4. สกัดและสร้าง Character Profiles ใหม่ (Gender, Age, Pronouns, Tone, Speech Habits) อัตโนมัติ
5. ลงทะเบียนตัวละครใหม่เข้าสู่ tlas_glossary.json ทั้งปลายทางและโฟลเดอร์หลักของโปรเจกต์
"""

import os
import sys
import csv
import json
import re
import shutil
from typing import Dict, Any, Set

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")

# เพิ่ม src เข้าสู่ sys.path
src_dir = os.path.join(WORKSPACE_ROOT, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from atf.tools.tlas_consensus_engine import infer_identity_from_name, MALE_NAME_KEYWORDS, FEMALE_NAME_KEYWORDS


def clean_speaker_name(raw_name: str) -> str:
    """ล้าง Control Codes เช่น \\C[18], \\fb, เครื่องหมายโคลอน และช่องว่าง"""
    if not raw_name:
        return ""
    s = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", raw_name)
    s = re.sub(r"\\[\.\!\|\^\<\>\{\}\\]", "", s)
    s = s.replace(":", "").strip()
    return s


def build_character_profile(name: str, gender: str, age: str, role_cat: str) -> Dict[str, Any]:
    """สร้าง Profile JSON ตาม Schema V4 มาตรฐานของ ATF TLAS"""
    gender_upper = (gender or "NEUTRAL").upper()
    age_upper = (age or "ADULT").upper()

    # กำหนดสรรพนามเริ่มต้นตามเพศและวัย
    if gender_upper == "MALE":
        self_pronoun = "ผม" if age_upper in ["ADULT", "ELDER"] else "ผม"
        target_pronoun = "คุณ"
        particle = "ครับ"
    elif gender_upper == "FEMALE":
        self_pronoun = "ฉัน" if age_upper == "ADULT" else ("หนู" if age_upper == "CHILD" else "ฉัน")
        target_pronoun = "เธอ" if age_upper in ["CHILD", "TEEN"] else "คุณ"
        particle = "ค่ะ"
    else:
        self_pronoun = "ฉัน"
        target_pronoun = "คุณ"
        particle = ""

    return {
        "name": name,
        "clean_name": clean_name_for_file(name),
        "source": "v035_patch_enrollment",
        "gender": gender_upper,
        "age": age_upper,
        "role_category": role_cat,
        "identity": {
            "gender": gender_upper,
            "age": age_upper,
            "role": role_cat,
            "archetype": "Townsperson/NPC" if role_cat == "Ambient" else "Story Character"
        },
        "speech_profile": {
            "self_pronoun": self_pronoun,
            "target_pronoun": target_pronoun,
            "ending_particles": [particle] if particle else [],
            "tone": "Casual" if role_cat == "Ambient" else "Polite",
            "relationship_pairs": {}
        },
        "personality": {
            "politeness": 60 if particle == "ครับ" or particle == "ค่ะ" else 40,
            "confidence": 50,
            "emotional_stability": 50
        }
    }


def clean_name_for_file(name: str) -> str:
    """แปลงชื่อให้ปลอดภัยสำหรับเป็นชื่อไฟล์บน Windows"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def main():
    print("=" * 80)
    print("   ATF CHARACTER PROFILE INGESTION & DELTA SPEAKER ENROLLMENT TOOL   ")
    print("=" * 80)

    # 1. โหลด Manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ ไม่พบไฟล์ Manifest: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    legacy_profiles_dir = manifest.get("legacy_profiles_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas", "profiles")
    output_profiles_dir = manifest.get("output_profiles_dir")
    output_csv = manifest.get("output_processed_csv")
    output_glossary_json = manifest.get("output_glossary_json")
    legacy_glossary_json = manifest.get("legacy_glossary_json")

    print(f"[*] Baseline Profiles Dir: {legacy_profiles_dir}")
    print(f"[*] Target Profiles Dir:   {output_profiles_dir}")
    print(f"[*] Target CSV File:       {output_csv}")
    print(f"[*] Target Master Glossary:{output_glossary_json}")

    # 2. ซิงค์ Baseline Profiles เดิมเข้าสู่ Target Workspace (ADR-024)
    os.makedirs(output_profiles_dir, exist_ok=True)
    existing_profiles: Set[str] = set()

    if os.path.exists(legacy_profiles_dir):
        legacy_files = [f for f in os.listdir(legacy_profiles_dir) if f.endswith(".json")]
        print(f"\n[1/4] ซิงค์ Baseline Profiles เดิม ({len(legacy_files)} ไฟล์) ไปยัง Target Workspace...")
        for f in legacy_files:
            src_f = os.path.join(legacy_profiles_dir, f)
            dst_f = os.path.join(output_profiles_dir, f)
            if not os.path.exists(dst_f):
                shutil.copy2(src_f, dst_f)
            char_key = f[:-5].strip().lower()
            existing_profiles.add(char_key)
        print(f"   -> ซิงค์และพร้อมใช้งาน Baseline Profiles รวม: {len(existing_profiles)} โปรไฟล์")
    else:
        print(f"⚠️ ไม่พบ Baseline Profiles Dir: {legacy_profiles_dir}")

    # 3. โหลด Master Glossary
    glossary = {}
    if output_glossary_json and os.path.exists(output_glossary_json):
        with open(output_glossary_json, "r", encoding="utf-8") as gf:
            glossary = json.load(gf)
    elif legacy_glossary_json and os.path.exists(legacy_glossary_json):
        with open(legacy_glossary_json, "r", encoding="utf-8") as gf:
            glossary = json.load(gf)

    chars_dict = glossary.get("Characters", {})
    glossary_names_lower = {k.strip().lower() for k in chars_dict.keys()}

    # 4. สแกน Speakers ทั้งหมดใน processed_dialogues_v3.csv และจับคู่ Delta Scenes
    print(f"\n[2/4] สแกนบทสนทนาใหม่ 14,908 แถว และจับคู่ Delta Scenes จาก: {output_csv}...")
    if not output_csv or not os.path.exists(output_csv):
        print(f"❌ ไม่พบไฟล์ CSV: {output_csv}")
        sys.exit(1)

    all_speakers = set()
    displayable_speakers = set()
    delta_empty_speakers = set()
    delta_empty_row_count = 0

    with open(output_csv, "r", encoding="utf-8-sig", errors="ignore") as cf:
        reader = csv.reader(cf)
        header = next(reader)
        for r_idx, r in enumerate(reader):
            if len(r) > 6:
                raw_spk = r[6].strip()
                orig_text = r[0].strip() if len(r) > 0 else ""
                init_text = r[1].strip() if len(r) > 1 else ""
                disp = r[7].strip().lower() if len(r) > 7 else ""
                clean_spk = clean_speaker_name(raw_spk)

                if clean_spk:
                    all_speakers.add(clean_spk)
                    if disp == "yes":
                        displayable_speakers.add(clean_spk)

                # ตรวจสอบเฉพาะแถวใหม่ของ v0.35 (Empty Rows ที่ Displayable == 'Yes')
                if disp == "yes" and not init_text and orig_text:
                    delta_empty_row_count += 1
                    if clean_spk:
                        delta_empty_speakers.add(clean_spk)

    print(f"   -> พบ Distinct Speakers ทั้งหมดในเกม: {len(all_speakers)} คน")
    print(f"   -> มีบทสนทนาแสดงผลจริง (Displayable == 'Yes'): {len(displayable_speakers)} คน")
    print(f"   -> แถวบทสนทนาใหม่ที่รอการแปล (Delta Rows): {delta_empty_row_count:,} แถว (พบผู้พูด {len(delta_empty_speakers)} คน)")

    # ตรวจสอบกับ rpgm_scenes_v5.json
    output_scenes_json = manifest.get("output_scenes_json")
    if output_scenes_json and os.path.exists(output_scenes_json):
        try:
            with open(output_scenes_json, "r", encoding="utf-8") as sc_f:
                scenes_data = json.load(sc_f)
            print(f"   -> เชื่อมต่อฐานข้อมูลฉากสำเร็จ: {len(scenes_data):,} ฉาก จาก {output_scenes_json}")
        except Exception as sc_err:
            print(f"   ⚠️ ไม่สามารถอ่านฐานข้อมูลฉาก: {sc_err}")

    # 5. คัดกรองตัวละครใหม่ที่ยังไม่มี Profile
    print("\n[3/4] ตรวจสอบและสกัด Character Profiles สำหรับตัวละครใหม่ของ v0.35...")
    new_characters = []
    ignored_technical_tags = {
        "- beach area -", "<authetication needed", "<blank", "?", "???", "all", "everyone",
        "future update", "system", "menu", "narration", "none"
    }

    for spk in sorted(displayable_speakers):
        spk_lower = spk.lower()
        if spk_lower in ignored_technical_tags or spk_lower.startswith("<") or spk_lower.startswith("-"):
            continue

        clean_file_key = clean_name_for_file(spk).lower()
        if clean_file_key not in existing_profiles:
            new_characters.append(spk)

    print(f"   -> คัดแยกพบตัวละครใหม่ที่ยังไม่มี Profile: {len(new_characters)} คน")

    # 6. สร้าง Profile และลงทะเบียนเข้า Glossary
    added_profiles_count = 0
    added_glossary_count = 0

    # กฎอนุมานเฉพาะสำหรับตัวละครในแพตช์นี้
    custom_character_hints = {
        "kj(jikan's ceo)": {"th": "KJ", "gender": "MALE", "age": "ADULT", "role": "Main", "proper": True},
        "boy ritche": {"th": "Ritchie วัยเด็ก", "gender": "MALE", "age": "CHILD", "role": "Main", "proper": True},
        "boy ritchie": {"th": "Ritchie วัยเด็ก", "gender": "MALE", "age": "CHILD", "role": "Main", "proper": True},
        "kid ritchie": {"th": "Ritchie วัยเด็ก", "gender": "MALE", "age": "CHILD", "role": "Main", "proper": True},
        "girl in shrine dress": {"th": "หญิงสาวในชุดศาลเจ้า", "gender": "FEMALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "jinnie's \"friend\"": {"th": "\"เพื่อน\" ของ Jinnie", "gender": "FEMALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "jordan's voice from inside": {"th": "Jordan", "gender": "MALE", "age": "ADULT", "role": "Main", "proper": True},
        "kinchao gang member": {"th": "สมาชิกแก๊ง Kinchao", "gender": "MALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "kinchao thug?": {"th": "อันธพาลแก๊ง Kinchao?", "gender": "MALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "rough-looking man": {"th": "ชายท่าทางดุดัน", "gender": "MALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "shion and erica": {"th": "Shion และ Erica", "gender": "FEMALE", "age": "ADULT", "role": "Main", "proper": True},
        "shion?": {"th": "Shion", "gender": "FEMALE", "age": "ADULT", "role": "Main", "proper": True},
        "the earl?": {"th": "The Earl", "gender": "MALE", "age": "ADULT", "role": "Main", "proper": True},
        "thug 1": {"th": "อันธพาล 1", "gender": "MALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "thug 2": {"th": "อันธพาล 2", "gender": "MALE", "age": "ADULT", "role": "Ambient", "proper": False},
        "twintails girl": {"th": "สาวผมทวินเทล", "gender": "FEMALE", "age": "TEEN", "role": "Ambient", "proper": False},
        "alisa?": {"th": "Alisa", "gender": "FEMALE", "age": "ADULT", "role": "Main", "proper": True},
        "arisa": {"th": "Alisa", "gender": "FEMALE", "age": "ADULT", "role": "Main", "proper": True},
        "y..rl": {"th": "Yearl", "gender": "MALE", "age": "ADULT", "role": "Main", "proper": True},
        "yearling": {"th": "Yearling", "gender": "MALE", "age": "ADULT", "role": "Main", "proper": True},
    }

    for char_name in new_characters:
        c_lower = char_name.lower()
        hint = custom_character_hints.get(c_lower)

        if hint:
            gender = hint["gender"]
            age = hint["age"]
            role_cat = hint["role"]
            th_name = hint["th"]
            is_proper = hint["proper"]
        else:
            inferred = infer_identity_from_name(char_name)
            gender = inferred.get("gender") or "NEUTRAL"
            age = inferred.get("age") or "ADULT"
            role_cat = "Ambient"
            th_name = char_name
            is_proper = True if char_name.istitle() and " " not in char_name else False

        # 1. เขียน Profile JSON
        profile_data = build_character_profile(char_name, gender, age, role_cat)
        file_name = f"{clean_name_for_file(char_name)}.json"
        profile_path = os.path.join(output_profiles_dir, file_name)

        with open(profile_path, "w", encoding="utf-8") as pf:
            json.dump(profile_data, pf, ensure_ascii=False, indent=2)
        added_profiles_count += 1
        print(f"   [+] Profile Created: {file_name:<30} ({gender}, {age}, Role: {role_cat})")

        # 2. ลงทะเบียนเข้า Glossary หากยังไม่มี
        if c_lower not in glossary_names_lower:
            chars_dict[char_name] = {
                "th": th_name,
                "type": "ProperNoun" if is_proper else "Generic",
                "role_category": role_cat,
                "analysis_target": True if role_cat == "Main" else False,
                "enforce": True,
                "reason": "Enrolled from v0.35 patch delta speaker scan"
            }
            glossary_names_lower.add(c_lower)
            added_glossary_count += 1

    # 7. บันทึก Master Glossary กลับสู่ดิสก์
    if added_glossary_count > 0:
        print(f"\n[4/4] บันทึก {added_glossary_count} ตัวละครใหม่เข้าสู่ Master Glossary...")
        glossary["Characters"] = chars_dict

        # บันทึก Target Glossary
        if output_glossary_json:
            os.makedirs(os.path.dirname(output_glossary_json), exist_ok=True)
            with open(output_glossary_json, "w", encoding="utf-8") as out_gf:
                json.dump(glossary, out_gf, ensure_ascii=False, indent=2)
            print(f"   -> บันทึก Target Glossary สำเร็จ: {output_glossary_json}")

        # บันทึก Legacy Glossary สำรองใน Project
        if legacy_glossary_json and os.path.exists(os.path.dirname(legacy_glossary_json)):
            with open(legacy_glossary_json, "w", encoding="utf-8") as out_gf:
                json.dump(glossary, out_gf, ensure_ascii=False, indent=2)
            print(f"   -> อัปเดต Project Glossary สำเร็จ: {legacy_glossary_json}")

    print("\n" + "=" * 80)
    print("🎉 CHARACTER PROFILE INGESTION & DELTA ENROLLMENT COMPLETED 100%!")
    print(f"   • Baseline Profiles Synced:  {len(existing_profiles)} โปรไฟล์")
    print(f"   • New v0.35 Profiles Created:{added_profiles_count} โปรไฟล์")
    print(f"   • New Characters in Glossary:{added_glossary_count} รายการ")
    total_profiles = len([f for f in os.listdir(output_profiles_dir) if f.endswith('.json')])
    print(f"   • Total Active Profiles:     {total_profiles} โปรไฟล์ (ใน {output_profiles_dir})")
    print("=" * 80)


if __name__ == "__main__":
    main()
