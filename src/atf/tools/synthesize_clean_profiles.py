#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Clean Character Profile Synthesizer & Global Matrix Generator
================================================================
สถาปัตยกรรม: SAD-010 (v4.1) | SDD-010, SDD-011 | ADR-035 (Decoupled Layering)
สร้างไฟล์โปรไฟล์ตัวละคร Clean V4 เฉพาะตัวละครสำคัญที่ผ่าน Whitelist (9 ตัว)
ปราศจาก Fallback ปลอม (Zero Default Polite Male Trap)
และสร้างตารางความสัมพันธ์สากล data/tlas/global_pronoun_matrix.json
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DATA_DIR = os.path.join(WORKSPACE_ROOT, "data", "tlas")
WHITELIST_PATH = os.path.join(DATA_DIR, "character_whitelist.json")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
MATRIX_OUTPUT_PATH = os.path.join(DATA_DIR, "global_pronoun_matrix.json")

# ฐานข้อมูลตัวละครที่ผ่านการสกัดบริบทจริง 100% จากตัวเกม (Ground Truth Curation)
CHARACTER_DEFINITIONS = {
    "凛": {
        "character_id": "CHAR_RIN",
        "name": "凛",
        "th_name": "ริน",
        "aliases": ["凛", "奥さん"],
        "identity": {
            "gender": "FEMALE",
            "age": "ADULT",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "คุณ",
            "third_person_pronoun": "เขา",
            "ending_particle": "ค่ะ",
            "formality_level": 3
        },
        "personality": [
            {"tag": "PER_SOC_POLITE", "weight": 85},
            {"tag": "PER_MIND_ANXIOUS", "weight": 80},
            {"tag": "PER_VIBE_GENTLE", "weight": 75}
        ],
        "speech_habit": [
            {"tag": "SPR_POLITE_SUFFIX", "weight": 90},
            {"tag": "SPR_HESITANT", "weight": 70}
        ],
        "values": [
            {"tag": "VAL_FAMILY", "weight": 95},
            {"tag": "VAL_LOYALTY", "weight": 90}
        ]
    },
    "夫": {
        "character_id": "CHAR_HUSBAND",
        "name": "夫",
        "th_name": "สามี",
        "aliases": ["夫", "旦那さん"],
        "identity": {
            "gender": "MALE",
            "age": "ADULT",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "เธอ",
            "third_person_pronoun": "เขา",
            "ending_particle": "",
            "formality_level": 3
        },
        "personality": [
            {"tag": "PER_VIBE_CALM", "weight": 80},
            {"tag": "PER_MIND_CARING", "weight": 75}
        ],
        "speech_habit": [
            {"tag": "SPR_CASUAL", "weight": 85}
        ],
        "values": [
            {"tag": "VAL_FAMILY", "weight": 90}
        ]
    },
    "遠藤": {
        "character_id": "CHAR_ENDO",
        "name": "遠藤",
        "th_name": "เอ็นโด",
        "aliases": ["遠藤", "宿主"],
        "identity": {
            "gender": "MALE",
            "age": "ADULT",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "คุณ",
            "third_person_pronoun": "เขา",
            "ending_particle": "ครับ",
            "formality_level": 4
        },
        "personality": [
            {"tag": "PER_SOC_CHARMING", "weight": 85},
            {"tag": "PER_MIND_MANIPULATIVE", "weight": 90},
            {"tag": "PER_VIBE_CONFIDENT", "weight": 80}
        ],
        "speech_habit": [
            {"tag": "SPR_SMOOTH_TALK", "weight": 85}
        ],
        "values": [
            {"tag": "VAL_DESIRE", "weight": 95}
        ]
    },
    "西原": {
        "character_id": "CHAR_NISHIHARA",
        "name": "西原",
        "th_name": "นิชิฮาระ",
        "aliases": ["西原"],
        "identity": {
            "gender": "MALE",
            "age": "ADULT",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "เธอ",
            "third_person_pronoun": "ยัยนั่น",
            "ending_particle": "",
            "formality_level": 2
        },
        "personality": [
            {"tag": "PER_SOC_ARROGANT", "weight": 85},
            {"tag": "PER_VIBE_AGGRESSIVE", "weight": 80}
        ],
        "speech_habit": [
            {"tag": "SPR_BLUNT", "weight": 85}
        ],
        "values": [
            {"tag": "VAL_DOMINANCE", "weight": 90}
        ]
    },
    "受付のおばあさん": {
        "character_id": "CHAR_RECEPTIONIST_ELDER",
        "name": "受付のおばあさん",
        "th_name": "คุณยายพนักงานต้อนรับ",
        "aliases": ["受付のおばあさん", "おばあさん"],
        "identity": {
            "gender": "FEMALE",
            "age": "ELDER",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "เธอ",
            "third_person_pronoun": "เขา",
            "ending_particle": "จ้ะ",
            "formality_level": 3
        },
        "personality": [
            {"tag": "PER_SOC_WARM", "weight": 85},
            {"tag": "PER_VIBE_GENTLE", "weight": 80}
        ],
        "speech_habit": [
            {"tag": "SPR_ELDERLY_AFFECTIONATE", "weight": 90}
        ],
        "values": [
            {"tag": "VAL_HOSPITALITY", "weight": 90}
        ]
    },
    "孫": {
        "character_id": "CHAR_GRANDSON",
        "name": "孫",
        "th_name": "หลานชาย",
        "aliases": ["孫", "ボク"],
        "identity": {
            "gender": "MALE",
            "age": "CHILD",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ผม",
            "target_pronoun": "พี่สาว",
            "third_person_pronoun": "เขา",
            "ending_particle": "ครับ",
            "formality_level": 3
        },
        "personality": [
            {"tag": "PER_SOC_INNOCENT", "weight": 90},
            {"tag": "PER_VIBE_PLAYFUL", "weight": 85}
        ],
        "speech_habit": [
            {"tag": "SPR_CHILD_POLITE", "weight": 85}
        ],
        "values": [
            {"tag": "VAL_CURIOSITY", "weight": 90}
        ]
    },
    "学生A": {
        "character_id": "CHAR_STUDENT_A",
        "name": "学生A",
        "th_name": "นักศึกษา A",
        "aliases": ["学生A"],
        "identity": {
            "gender": "MALE",
            "age": "TEEN",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "นาย",
            "third_person_pronoun": "มัน",
            "ending_particle": "วะ",
            "formality_level": 2
        },
        "personality": [
            {"tag": "PER_SOC_VULGAR", "weight": 90},
            {"tag": "PER_VIBE_HORNY", "weight": 95}
        ],
        "speech_habit": [
            {"tag": "SPR_SLANG", "weight": 90}
        ],
        "values": [
            {"tag": "VAL_LUST", "weight": 95}
        ]
    },
    "学生B": {
        "character_id": "CHAR_STUDENT_B",
        "name": "学生B",
        "th_name": "นักศึกษา B",
        "aliases": ["学生B"],
        "identity": {
            "gender": "MALE",
            "age": "TEEN",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "นาย",
            "third_person_pronoun": "มัน",
            "ending_particle": "วะ",
            "formality_level": 2
        },
        "personality": [
            {"tag": "PER_SOC_VULGAR", "weight": 90},
            {"tag": "PER_VIBE_HORNY", "weight": 95}
        ],
        "speech_habit": [
            {"tag": "SPR_SLANG", "weight": 90}
        ],
        "values": [
            {"tag": "VAL_LUST", "weight": 95}
        ]
    },
    "学生2人": {
        "character_id": "CHAR_STUDENTS_PAIR",
        "name": "学生2人",
        "th_name": "นักศึกษา 2 คน",
        "aliases": ["学生2人"],
        "identity": {
            "gender": "MALE",
            "age": "TEEN",
            "species": "HUMAN"
        },
        "base_speech_style": {
            "self_pronoun": "พวกเรา",
            "target_pronoun": "พี่สาว",
            "third_person_pronoun": "พวกมัน",
            "ending_particle": "",
            "formality_level": 2
        },
        "personality": [
            {"tag": "PER_SOC_PEEPING", "weight": 90},
            {"tag": "PER_VIBE_NERVOUS_HORNY", "weight": 85}
        ],
        "speech_habit": [
            {"tag": "SPR_STUTTER_EXCITED", "weight": 80}
        ],
        "values": [
            {"tag": "VAL_LUST", "weight": 90}
        ]
    }
}

# กำหนดความสัมพันธ์รายคู่เฉพาะ (Pairwise Specific Relationship Rules)
PAIRWISE_MATRIX = [
    # 凛 <-> 夫 (สามีภรรยา)
    {
        "speaker": "凛", "target": "夫",
        "roles": ["ROLE_ROM_PARTNER", "ROLE_FAM_SPOUSE"],
        "affinity": "AFF_DEVOTED", "intimacy": "INT_INTIMATE", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "คุณ", "third_person_pronoun": "เขา",
            "ending_particle": "ค่ะ", "formality_level": 3, "derivation_rule": "RULE_WIFE_TO_HUSBAND"
        }
    },
    {
        "speaker": "夫", "target": "凛",
        "roles": ["ROLE_ROM_PARTNER", "ROLE_FAM_SPOUSE"],
        "affinity": "AFF_DEVOTED", "intimacy": "INT_INTIMATE", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "เธอ", "third_person_pronoun": "เขา",
            "ending_particle": "", "formality_level": 3, "derivation_rule": "RULE_HUSBAND_TO_WIFE"
        }
    },

    # 凛 <-> 遠藤 (แขกผู้หญิง vs เจ้าของที่พัก)
    {
        "speaker": "凛", "target": "遠藤",
        "roles": ["ROLE_SOC_GUEST", "ROLE_SOC_ACQUAINTANCE"],
        "affinity": "AFF_CAUTIOUS", "intimacy": "INT_DISTANT", "power_dynamic": "DYN_SUBMISSIVE",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "คุณเอ็นโด", "third_person_pronoun": "เขา",
            "ending_particle": "ค่ะ", "formality_level": 4, "derivation_rule": "RULE_GUEST_TO_HOST"
        }
    },
    {
        "speaker": "遠藤", "target": "凛",
        "roles": ["ROLE_SOC_HOST", "ROLE_VIBE_PREDATORY"],
        "affinity": "AFF_OBSESSED", "intimacy": "INT_FAMILIAR", "power_dynamic": "DYN_DOMINANT",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "คุณนาย", "third_person_pronoun": "เขา",
            "ending_particle": "ครับ", "formality_level": 4, "derivation_rule": "RULE_HOST_TO_FEMALE_GUEST"
        }
    },

    # 凛 <-> 西原 (อดีตแฟนเก่าคุกคาม)
    {
        "speaker": "凛", "target": "西原",
        "roles": ["ROLE_SOC_EX_LOVER", "ROLE_SOC_ENEMY"],
        "affinity": "AFF_HOSTILE", "intimacy": "INT_AVERSIVE", "power_dynamic": "DYN_DEFENSIVE",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "นาย", "third_person_pronoun": "เขา",
            "ending_particle": "", "formality_level": 2, "derivation_rule": "RULE_DEFENSIVE_EX"
        }
    },
    {
        "speaker": "西原", "target": "凛",
        "roles": ["ROLE_SOC_EX_LOVER", "ROLE_VIBE_COERCIVE"],
        "affinity": "AFF_OBSESSED", "intimacy": "INT_UNINVITED_INTIMATE", "power_dynamic": "DYN_DOMINANT",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "เธอ", "third_person_pronoun": "ยัยนั่น",
            "ending_particle": "", "formality_level": 2, "derivation_rule": "RULE_COERCIVE_EX"
        }
    },

    # 凛 <-> 受付のおばあさん
    {
        "speaker": "凛", "target": "受付のおばあさん",
        "roles": ["ROLE_SOC_GUEST", "ROLE_SOC_ELDER_RESPECT"],
        "affinity": "AFF_FRIENDLY", "intimacy": "INT_POLITE", "power_dynamic": "DYN_RESPECTFUL",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "คุณยาย", "third_person_pronoun": "ท่าน",
            "ending_particle": "ค่ะ", "formality_level": 4, "derivation_rule": "RULE_RESPECT_ELDER"
        }
    },
    {
        "speaker": "受付のおばあさん", "target": "凛",
        "roles": ["ROLE_SOC_HOST_ELDER"],
        "affinity": "AFF_WARM", "intimacy": "INT_FAMILIAR", "power_dynamic": "DYN_ELDER_GUIDE",
        "speech_style": {
            "self_pronoun": "ฉัน", "target_pronoun": "คุณผู้หญิง", "third_person_pronoun": "เขา",
            "ending_particle": "จ้ะ", "formality_level": 3, "derivation_rule": "RULE_ELDER_TO_YOUNG_WOMAN"
        }
    },

    # 凛 <-> 孫 (หญิงสาว vs เด็กชาย)
    {
        "speaker": "凛", "target": "孫",
        "roles": ["ROLE_SOC_ADULT_TO_CHILD"],
        "affinity": "AFF_KIND", "intimacy": "INT_WARM", "power_dynamic": "DYN_ADULT",
        "speech_style": {
            "self_pronoun": "พี่ / ฉัน", "target_pronoun": "เธอ / หนู", "third_person_pronoun": "เขา",
            "ending_particle": "จ้ะ", "formality_level": 3, "derivation_rule": "RULE_ADULT_TO_BOY"
        }
    },
    {
        "speaker": "孫", "target": "凛",
        "roles": ["ROLE_SOC_CHILD_TO_ADULT"],
        "affinity": "AFF_FRIENDLY", "intimacy": "INT_CHILDISH", "power_dynamic": "DYN_CHILD",
        "speech_style": {
            "self_pronoun": "ผม", "target_pronoun": "พี่สาว", "third_person_pronoun": "เขา",
            "ending_particle": "ครับ", "formality_level": 3, "derivation_rule": "RULE_BOY_TO_OLDER_WOMAN"
        }
    },

    # 夫 <-> 遠藤
    {
        "speaker": "夫", "target": "遠藤",
        "roles": ["ROLE_SOC_GUEST", "ROLE_SOC_PEER"],
        "affinity": "AFF_NEUTRAL", "intimacy": "INT_DISTANT", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "ผม", "target_pronoun": "คุณเอ็นโด", "third_person_pronoun": "เขา",
            "ending_particle": "ครับ", "formality_level": 4, "derivation_rule": "RULE_GUEST_TO_HOST"
        }
    },
    {
        "speaker": "遠藤", "target": "夫",
        "roles": ["ROLE_SOC_HOST"],
        "affinity": "AFF_POLITE", "intimacy": "INT_DISTANT", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "ผม", "target_pronoun": "คุณ", "third_person_pronoun": "เขา",
            "ending_particle": "ครับ", "formality_level": 4, "derivation_rule": "RULE_HOST_TO_GUEST"
        }
    },

    # 学生A <-> 学生B (เพื่อนสนิทวัยรุ่นห่าม)
    {
        "speaker": "学生A", "target": "学生B",
        "roles": ["ROLE_SOC_CLOSE_PEER", "ROLE_SOC_FRIEND"],
        "affinity": "AFF_CLOSE", "intimacy": "INT_CONFIDANT", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "กู", "target_pronoun": "มึง", "third_person_pronoun": "มัน",
            "ending_particle": "วะ", "formality_level": 1, "derivation_rule": "RULE_CLOSE_THUG_PEER"
        }
    },
    {
        "speaker": "学生B", "target": "学生A",
        "roles": ["ROLE_SOC_CLOSE_PEER", "ROLE_SOC_FRIEND"],
        "affinity": "AFF_CLOSE", "intimacy": "INT_CONFIDANT", "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": "กู", "target_pronoun": "มึง", "third_person_pronoun": "มัน",
            "ending_particle": "วะ", "formality_level": 1, "derivation_rule": "RULE_CLOSE_THUG_PEER"
        }
    },

    # 学生A / 学生B -> 凛 (วัยรุ่นหื่นแทะโลม)
    {
        "speaker": "学生A", "target": "凛",
        "roles": ["ROLE_VIBE_LUST", "ROLE_SOC_STRANGER"],
        "affinity": "AFF_LUSTFUL", "intimacy": "INT_UNINVITED", "power_dynamic": "DYN_PREDATORY",
        "speech_style": {
            "self_pronoun": "ผม / เรา", "target_pronoun": "พี่สาว / คุณนาย", "third_person_pronoun": "เขา",
            "ending_particle": "", "formality_level": 2, "derivation_rule": "RULE_HORNY_COLLEGE_STUDENT"
        }
    },
    {
        "speaker": "学生B", "target": "凛",
        "roles": ["ROLE_VIBE_LUST", "ROLE_SOC_STRANGER"],
        "affinity": "AFF_LUSTFUL", "intimacy": "INT_UNINVITED", "power_dynamic": "DYN_PREDATORY",
        "speech_style": {
            "self_pronoun": "ผม / เรา", "target_pronoun": "พี่สาว / คุณนาย", "third_person_pronoun": "เขา",
            "ending_particle": "", "formality_level": 2, "derivation_rule": "RULE_HORNY_COLLEGE_STUDENT"
        }
    },
    {
        "speaker": "学生2人", "target": "凛",
        "roles": ["ROLE_VIBE_LUST", "ROLE_SOC_STRANGER"],
        "affinity": "AFF_LUSTFUL", "intimacy": "INT_UNINVITED", "power_dynamic": "DYN_PREDATORY",
        "speech_style": {
            "self_pronoun": "พวกเรา / ผม", "target_pronoun": "พี่สาว / คุณนาย", "third_person_pronoun": "เขา",
            "ending_particle": "", "formality_level": 2, "derivation_rule": "RULE_HORNY_COLLEGE_STUDENTS"
        }
    }
]


def synthesize_clean_profiles():
    print("=" * 80)
    print("   ATF CLEAN CHARACTER PROFILE SYNTHESIZER & GLOBAL MATRIX ENGINE (v4.1)   ")
    print("=" * 80)

    # 1. อ่าน Whitelist
    with open(WHITELIST_PATH, "r", encoding="utf-8") as f:
        whitelist_data = json.load(f)

    target_chars = [c["name"] for c in whitelist_data.get("characters", [])]
    print(f"[*] Loaded {len(target_chars)} Qualified Target Characters from: {WHITELIST_PATH}")
    for idx, c in enumerate(target_chars, start=1):
        print(f"    {idx}. 【{c}】 ({CHARACTER_DEFINITIONS[c]['th_name']})")

    os.makedirs(PROFILES_DIR, exist_ok=True)

    generated_count = 0
    matrix_records = []

    # 2. สังเคราะห์ Profile รายบุคคล
    for char_name in target_chars:
        if char_name not in CHARACTER_DEFINITIONS:
            print(f"[!] Warning: No definition found for {char_name}, skipping.")
            continue

        defn = CHARACTER_DEFINITIONS[char_name]

        # ดึงความสัมพันธ์เฉพาะที่ตัวละครนี้เป็น Speaker
        char_rels = []
        for rel in PAIRWISE_MATRIX:
            if rel["speaker"] == char_name:
                tgt_name = rel["target"]
                tgt_id = CHARACTER_DEFINITIONS.get(tgt_name, {}).get("character_id", f"CHAR_{tgt_name.upper()}")
                
                char_rels.append({
                    "target_character_id": tgt_id,
                    "target_name": tgt_name,
                    "roles": rel["roles"],
                    "affinity": rel["affinity"],
                    "intimacy": rel["intimacy"],
                    "power_dynamic": rel["power_dynamic"],
                    "speech_style": rel["speech_style"]
                })

                matrix_records.append({
                    "speaker": char_name,
                    "listener": tgt_name,
                    "roles": rel["roles"],
                    "affinity": rel["affinity"],
                    "intimacy": rel["intimacy"],
                    "power_dynamic": rel["power_dynamic"],
                    "speech_style": rel["speech_style"]
                })

        profile_data = {
            "character_id": defn["character_id"],
            "name": defn["name"],
            "th_name": defn["th_name"],
            "aliases": defn["aliases"],
            "identity": defn["identity"],
            "base_speech_style": defn["base_speech_style"],
            "base_state": {
                "personality": defn["personality"],
                "speech_habit": defn["speech_habit"],
                "values": defn["values"],
                "relationships": char_rels
            }
        }

        # เขียนไฟล์ Profile ลง profiles/<Name>.json
        out_file = os.path.join(PROFILES_DIR, f"{char_name}.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)

        generated_count += 1
        print(f"[✔] Generated Clean Profile: {char_name}.json (Relationships: {len(char_rels)})")

    # 3. บันทึก Global Pronoun Matrix
    with open(MATRIX_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(matrix_records, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"🎉 Successfully Synthesized {generated_count} Clean Character Profiles in: {PROFILES_DIR}")
    print(f"🌐 Saved Global Pronoun Matrix ({len(matrix_records)} Pairwise Rules): {MATRIX_OUTPUT_PATH}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    synthesize_clean_profiles()
