#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Identity-Driven Demographic Matrix & Profile Cleaner (v5.0 Unified)
========================================================================
1. นำ target_pronoun และ third_person_pronoun ออกจาก base_speech_style ในทุก Profile
2. ตรวจสอบและระบุ identity.number (SINGULAR / PLURAL)
3. กำหนด demographic_persona สำหรับการจับคู่กลุ่มประชากร
4. สกัด Specific Pairwise Rules จาก relationships ของโปรไฟล์ทุกตัว
5. สร้าง Demographic Matrix (Speaker Persona x Listener Demographic) ครอบคลุม 100%
6. อัปเดต data/tlas/global_pronoun_matrix.json
"""

import os
import sys
import json
import glob

# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PROFILES_DIR = os.path.join(BASE_DIR, "data", "tlas", "profiles")
MATRIX_FILE = os.path.join(BASE_DIR, "data", "tlas", "global_pronoun_matrix.json")


def infer_demographic_persona(pdata):
    """วิเคราะห์ Persona Category จาก Identity และ Base State Personality/Habits"""
    ident = pdata.get("identity", {})
    age = ident.get("age", "").upper()
    if age == "CHILD":
        return "CHILD_POLITE"
    if age == "ELDER":
        return "ELDER_AFFECTIONATE"

    bs = pdata.get("base_state", {})
    per_tags = [x.get("tag", "") for x in bs.get("personality", [])]
    hab_tags = [x.get("tag", "") for x in bs.get("speech_habit", [])]
    all_tags = set(per_tags + hab_tags)

    if any(t in all_tags for t in ["PER_SOC_VULGAR", "PER_SOC_ARROGANT", "PER_SOC_PEEPING", "SPR_SLANG", "SPR_BLUNT"]):
        return "THUG_VULGAR"
    if any(t in all_tags for t in ["PER_SOC_CHARMING", "PER_MIND_MANIPULATIVE", "SPR_SMOOTH_TALK"]):
        return "CHARMING_MANIPULATIVE"

    return "CALM_POLITE"


def clean_profiles_and_enrich():
    """
    1. นำ target_pronoun และ third_person_pronoun ออกจาก base_speech_style
    2. เติม identity.number และ demographic_persona
    """
    print("[*] Processing and sanitizing character profiles on disk...")
    profile_files = glob.glob(os.path.join(PROFILES_DIR, "*.json"))

    cleaned_count = 0
    all_profiles = {}

    for pfile in profile_files:
        try:
            with open(pfile, "r", encoding="utf-8") as f:
                data = json.load(f)

            char_name = data.get("name") or os.path.splitext(os.path.basename(pfile))[0]
            base_style = data.get("base_speech_style", {})

            # 1. นำ target_pronoun และ third_person_pronoun ออกจาก base
            if "target_pronoun" in base_style:
                del base_style["target_pronoun"]
            if "third_person_pronoun" in base_style:
                del base_style["third_person_pronoun"]
            data["base_speech_style"] = base_style

            # 2. ตั้งค่า identity.number
            ident = data.setdefault("identity", {})
            if "2人" in char_name or "PAIR" in data.get("character_id", ""):
                ident["number"] = "PLURAL"
            else:
                ident.setdefault("number", "SINGULAR")

            # 3. กำหนด demographic_persona
            persona = infer_demographic_persona(data)
            data["demographic_persona"] = persona

            all_profiles[char_name] = data

            # บันทึกลงไฟล์
            with open(pfile, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            cleaned_count += 1
            print(f"  [✔] Profile updated: {char_name:15} | Persona: {persona:20} | Number: {ident.get('number')}")
        except Exception as e:
            print(f"  [❌] Error processing {pfile}: {e}")

    print(f"[✔] Successfully sanitized and calibrated {cleaned_count} profile files.\n")
    return all_profiles


def build_unified_matrix(all_profiles):
    """
    สร้าง Unified Pronoun Matrix (v5.0):
    1. Specific Pairwise Rules จาก relationships ในโปรไฟล์ทุกตัว
    2. Identity Demographic Rules (Speaker Persona x Listener Demographic)
    """
    print("[*] Synthesizing Unified Pronoun Matrix (Specific Pairs + Demographic ID Rules)...")

    specific_rules = []
    seen_pairs = set()

    # 1. รวบรวม Specific Rules จาก relationships
    for speaker_name, pdata in all_profiles.items():
        base_state = pdata.get("base_state", {})
        relationships = base_state.get("relationships", [])
        if not relationships:
            relationships = pdata.get("relationships", [])

        for rel in relationships:
            target_name = rel.get("target_name")
            if not target_name:
                continue

            pair_key = (speaker_name, target_name)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            speech_style = rel.get("speech_style", {})
            specific_rules.append({
                "type": "SPECIFIC_PAIR",
                "speaker": speaker_name,
                "listener": target_name,
                "roles": rel.get("roles", []),
                "affinity": rel.get("affinity", "AFF_NEUTRAL"),
                "intimacy": rel.get("intimacy", "INT_DISTANT"),
                "power_dynamic": rel.get("power_dynamic", "DYN_EQUAL"),
                "speech_style": {
                    "self_pronoun": speech_style.get("self_pronoun", "ฉัน"),
                    "target_pronoun": speech_style.get("target_pronoun", "คุณ"),
                    "third_person_pronoun": speech_style.get("third_person_pronoun", "เขา"),
                    "ending_particle": speech_style.get("ending_particle", ""),
                    "formality_level": speech_style.get("formality_level", 3),
                    "derivation_rule": speech_style.get("derivation_rule", "RULE_PAIRWISE_OVERRIDE")
                }
            })

    # 2. Demographic Rules ครอบคลุมทุกความสัมพันธ์
    demographic_rules = [
        # =============================================================
        # Persona 1: THUG_VULGAR (นักเลง / คะนอง / หยาบคาย)
        # ตัวอย่าง: 学生A, 学生B, 学生2人, 西原
        # =============================================================
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_GROUP",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"number": "PLURAL"},
            "speech_style": {
                "target_pronoun": "พวกแก / พวกมึง / พวกเธอ",
                "third_person_pronoun": "พวกมัน / พวกนั้น",
                "ending_particle": "วะ / โว้ย",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_MALE_CHILD",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "MALE", "age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "ไอ้หนู / เจ้าหนู",
                "third_person_pronoun": "เจ้าหนูนั่น / มัน",
                "ending_particle": "วะ / โว้ย",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_FEMALE_CHILD",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "FEMALE", "age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "หนูน้อย / ยัยหนู",
                "third_person_pronoun": "ยัยหนูนั่น / มัน",
                "ending_particle": "วะ / โว้ย",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_FEMALE_TEEN",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "FEMALE", "age": "TEEN", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "สาวน้อย / น้องสาว / เธอ",
                "third_person_pronoun": "ยัยนั่น / เธอ",
                "ending_particle": "วะ",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_FEMALE_ADULT",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "FEMALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "พี่สาว / คุณนาย / เธอ",
                "third_person_pronoun": "เธอ / ยัยคนสวย",
                "ending_particle": "ครับ / วะ",
                "formality_level": 2
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_MALE_ADULT",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "MALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "แก / นาย / มึง",
                "third_person_pronoun": "หมอนั่น / มัน",
                "ending_particle": "วะ / โว้ย",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_MALE_TEEN",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "MALE", "age": "TEEN", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "แก / นาย / มึง",
                "third_person_pronoun": "หมอนั่น / มัน",
                "ending_particle": "วะ / โว้ย",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_MALE_ELDER",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "MALE", "age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "ลุง / ตาแก่ / คุณลุง",
                "third_person_pronoun": "ลุงนั่น / ตาแก่นั่น",
                "ending_particle": "วะ",
                "formality_level": 1
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_THUG_TO_FEMALE_ELDER",
            "speaker_persona": "THUG_VULGAR",
            "listener_match": {"gender": "FEMALE", "age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "ยาย / ยายแก่ / คุณยาย",
                "third_person_pronoun": "ยายแก่นั่น / ป้านั่น",
                "ending_particle": "วะ",
                "formality_level": 1
            }
        },

        # =============================================================
        # Persona 2: CALM_POLITE (สุภาพชนทั่วไป / ผู้ใหญ่ใจดี)
        # ตัวอย่าง: 夫, 凛
        # =============================================================
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_GROUP",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"number": "PLURAL"},
            "speech_style": {
                "target_pronoun": "พวกคุณ / ทุกคน",
                "third_person_pronoun": "พวกเขา / ทุกคน",
                "ending_particle": "ครับ / ค่ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_CHILD",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "หนูน้อย / เจ้าหนู / เธอ",
                "third_person_pronoun": "เด็กคนนั้น / เขา / เธอ",
                "ending_particle": "จ้ะ / ครับ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_MALE_ELDER",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"gender": "MALE", "age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "คุณลุง / คุณตา",
                "third_person_pronoun": "คุณลุง / เขา",
                "ending_particle": "ครับ / ค่ะ",
                "formality_level": 4
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_FEMALE_ELDER",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"gender": "FEMALE", "age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "คุณป้า / คุณยาย",
                "third_person_pronoun": "คุณยาย / เธอ",
                "ending_particle": "ครับ / ค่ะ",
                "formality_level": 4
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_PEER_ADULT",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "คุณ",
                "third_person_pronoun": "เขา / เธอ",
                "ending_particle": "ครับ / ค่ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_POLITE_TO_TEEN",
            "speaker_persona": "CALM_POLITE",
            "listener_match": {"age": "TEEN", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "เธอ / นาย",
                "third_person_pronoun": "เขา / เธอ",
                "ending_particle": "ครับ / ค่ะ",
                "formality_level": 3
            }
        },

        # =============================================================
        # Persona 3: CHARMING_MANIPULATIVE (เจ้าเล่ห์ / มีเสน่ห์)
        # ตัวอย่าง: 遠藤
        # =============================================================
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_GROUP",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"number": "PLURAL"},
            "speech_style": {
                "target_pronoun": "พวกคุณ / ทุกคน",
                "third_person_pronoun": "พวกเขา",
                "ending_particle": "",
                "formality_level": 2
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_FEMALE_ADULT",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"gender": "FEMALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "เธอ / คุณ",
                "third_person_pronoun": "เธอ / คุณผู้หญิง",
                "ending_particle": "ครับ / นะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_FEMALE_TEEN",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"gender": "FEMALE", "age": "TEEN", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "สาวน้อย / เธอ",
                "third_person_pronoun": "เธอ / เด็กสาวคนนั้น",
                "ending_particle": "นะ / ครับ",
                "formality_level": 2
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_MALE_ADULT",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"gender": "MALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "นาย / คุณ",
                "third_person_pronoun": "เขา / หมอนั่น",
                "ending_particle": "",
                "formality_level": 2
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_CHILD",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "เจ้าหนู / หนูน้อย",
                "third_person_pronoun": "เด็กคนนั้น",
                "ending_particle": "นะ",
                "formality_level": 2
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHARMING_TO_ELDER",
            "speaker_persona": "CHARMING_MANIPULATIVE",
            "listener_match": {"age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "คุณลุง / คุณป้า / คุณยาย",
                "third_person_pronoun": "ท่าน / คุณยาย",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        },

        # =============================================================
        # Persona 4: ELDER_AFFECTIONATE (ผู้อาวุโสใจดี / คุณยาย)
        # ตัวอย่าง: 受付のおばあさん
        # =============================================================
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_ELDER_TO_GROUP",
            "speaker_persona": "ELDER_AFFECTIONATE",
            "listener_match": {"number": "PLURAL"},
            "speech_style": {
                "target_pronoun": "พวกเธอ / ทุกคน",
                "third_person_pronoun": "พวกเด็กๆ / พวกเขา",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_ELDER_TO_CHILD",
            "speaker_persona": "ELDER_AFFECTIONATE",
            "listener_match": {"age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "หลาน / เจ้าหนู / หนู",
                "third_person_pronoun": "เจ้าหนู / หลาน",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_ELDER_TO_FEMALE_ADULT",
            "speaker_persona": "ELDER_AFFECTIONATE",
            "listener_match": {"gender": "FEMALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "แม่หนู / คุณผู้หญิง / เธอ",
                "third_person_pronoun": "แม่หนู / เธอ",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_ELDER_TO_MALE_ADULT",
            "speaker_persona": "ELDER_AFFECTIONATE",
            "listener_match": {"gender": "MALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "พ่อหนุ่ม / นาย / เธอ",
                "third_person_pronoun": "พ่อหนุ่ม / เขา",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_ELDER_TO_TEEN",
            "speaker_persona": "ELDER_AFFECTIONATE",
            "listener_match": {"age": "TEEN", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "พ่อหนุ่ม / แม่หนู / พวกเธอ",
                "third_person_pronoun": "เด็กคนนั้น / พวกเขา",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        },

        # =============================================================
        # Persona 5: CHILD_POLITE (เด็ก / เด็กเล็ก)
        # ตัวอย่าง: 孫
        # =============================================================
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHILD_TO_GROUP",
            "speaker_persona": "CHILD_POLITE",
            "listener_match": {"number": "PLURAL"},
            "speech_style": {
                "target_pronoun": "พวกพี่ๆ / ทุกคน",
                "third_person_pronoun": "พวกพี่ๆ / พวกเขา",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHILD_TO_FEMALE_ADULT",
            "speaker_persona": "CHILD_POLITE",
            "listener_match": {"gender": "FEMALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "พี่สาว / น้าสาว",
                "third_person_pronoun": "พี่สาว / น้าสาว",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHILD_TO_MALE_ADULT",
            "speaker_persona": "CHILD_POLITE",
            "listener_match": {"gender": "MALE", "age": "ADULT", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "พี่ชาย / ลุง",
                "third_person_pronoun": "พี่ชาย / ลุง",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHILD_TO_ELDER",
            "speaker_persona": "CHILD_POLITE",
            "listener_match": {"age": "ELDER", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "คุณตา / คุณยาย / คุณปู่",
                "third_person_pronoun": "คุณตา / คุณยาย",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        },
        {
            "type": "DEMOGRAPHIC_RULE",
            "rule_id": "DEMO_CHILD_TO_CHILD",
            "speaker_persona": "CHILD_POLITE",
            "listener_match": {"age": "CHILD", "number": "SINGULAR"},
            "speech_style": {
                "target_pronoun": "นาย / เธอ",
                "third_person_pronoun": "เขา / เธอ",
                "ending_particle": "ครับ",
                "formality_level": 3
            }
        }
    ]

    unified_matrix = {
        "_metadata": {
            "version": "5.0",
            "description": "Unified TLAS Pronoun Matrix (Specific Pairs + Identity Demographic Rules)",
            "specific_pair_rules_count": len(specific_rules),
            "demographic_rules_count": len(demographic_rules)
        },
        "specific_pair_rules": specific_rules,
        "demographic_rules": demographic_rules
    }

    with open(MATRIX_FILE, "w", encoding="utf-8") as mf:
        json.dump(unified_matrix, mf, ensure_ascii=False, indent=2)

    print(f"[✔] Successfully generated Unified Matrix (v5.0):")
    print(f"    - Specific Pairwise Rules : {len(specific_rules)}")
    print(f"    - Demographic Matching    : {len(demographic_rules)}")
    print(f"    - Saved to: {MATRIX_FILE}")


if __name__ == "__main__":
    profiles = clean_profiles_and_enrich()
    build_unified_matrix(profiles)
