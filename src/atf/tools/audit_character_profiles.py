"""
TLAS Character Profile & Gender Audit Script
Architecture: SAD-010 | Design: SDD-010, SDD-011 | Rules: AGENTS.md

หน้าที่:
1. สแกนตรวจสอบ 442 โปรไฟล์ใน data/tlas/profiles/*.json
2. ตรวจสอบความขัดแย้งด้าน Gender (เช่น ชื่อระบุ Man/Boy/Guy/Sir/Mr แต่เพศเป็น FEMALE หรือกลับกัน)
3. ตรวจสอบความขัดแย้งด้าน Age Group (เช่น Boy/Girl/Kid แต่เป็น ADULT, Elder/Old Man แต่เป็น ADULT)
4. ตรวจสอบความขัดแย้งด้าน Ending Particle (เช่น ชายพูด 'ค่ะ'/'คะ', นักเลง/อันธพาลพูดสุภาพ 'ค่ะ'/'ครับ')
5. ตรวจสอบหลักฐานแวดล้อมจาก extractions_v4 (เช่น he/him/his/sir vs she/her/lady/miss)
6. สรุปรายงานออกเป็น JSON และข้อความสถิติ
"""

import os
import sys
import json
import glob
import re
from typing import Dict, List, Any

TLAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/tlas"))
PROFILES_DIR = os.path.join(TLAS_DIR, "profiles")
EXTRACTIONS_DIR = os.path.join(TLAS_DIR, "extractions_v4")
REPORT_PATH = os.path.join(TLAS_DIR, "character_audit_report.json")

MALE_KEYWORDS = {
    "man", "men", "boy", "guy", "guys", "father", "dad", "papa", "husband", "son",
    "brother", "uncle", "grandfather", "grandpa", "priest", "policeman", "policemen",
    "lumberjack", "fisherman", "fratboy", "mr", "sir", "king", "prince", "male",
    "gentleman", "groom", "playboy", "host", "courier", "barfer", "monk", "butler",
    "actor", "waiter", "lord", "emperor", "duke", "count", "baron"
}

FEMALE_KEYWORDS = {
    "woman", "women", "girl", "girls", "lady", "ladies", "mother", "mom", "mama",
    "wife", "daughter", "sister", "aunt", "grandmother", "grandma", "nun", "policewoman",
    "maid", "waitress", "hostess", "mrs", "ms", "miss", "queen", "princess", "female",
    "bride", "actress", "madam", "lady", "headmistress", "housewife", "salarylady",
    "fangirl", "hooker", "escort"
}

CHILD_KEYWORDS = {"boy", "girl", "child", "kid", "little", "young boy", "young girl", "baby"}
ELDER_KEYWORDS = {"old man", "old lady", "elder", "senior", "grandpa", "grandma", "veteran"}

def audit_profiles():
    profile_files = glob.glob(os.path.join(PROFILES_DIR, "*.json"))
    print(f"[*] Found {len(profile_files)} profiles to audit in {PROFILES_DIR}...")

    # Load extraction context evidence for deeper cross-check
    char_evidence = {}
    if os.path.exists(EXTRACTIONS_DIR):
        print(f"[*] Loading scene context evidence from {EXTRACTIONS_DIR}...")
        for ef in glob.glob(os.path.join(EXTRACTIONS_DIR, "*.json")):
            try:
                with open(ef, "r", encoding="utf-8") as f:
                    edata = json.load(f)
            except Exception:
                continue
            ctx = edata.get("scene_context", "")
            if not ctx:
                continue
            # Look for exact character occurrences in sentence
            sentences = re.split(r'[.!?]+', ctx)
            for s in sentences:
                for char_info in edata.get("characters", []):
                    cname = char_info.get("character_name") if isinstance(char_info, dict) else None
                    if not cname:
                        continue
                    if cname not in char_evidence:
                        char_evidence[cname] = {"male_clues": 0, "female_clues": 0, "sample_clues": []}
                    
                    # If character name is in sentence, check pronouns in that exact sentence
                    pattern = r'\b' + re.escape(cname) + r'\b'
                    if re.search(pattern, s, re.IGNORECASE):
                        m_hits = len(re.findall(r'\b(he|him|his|man|sir|mr|boy)\b', s, re.IGNORECASE))
                        f_hits = len(re.findall(r'\b(she|her|hers|woman|lady|miss|girl)\b', s, re.IGNORECASE))
                        char_evidence[cname]["male_clues"] += m_hits
                        char_evidence[cname]["female_clues"] += f_hits
                        if m_hits > 0 or f_hits > 0:
                            if len(char_evidence[cname]["sample_clues"]) < 3:
                                char_evidence[cname]["sample_clues"].append(s.strip())

    issues = []
    gender_mismatches = []
    speech_mismatches = []
    age_mismatches = []

    for pf in profile_files:
        try:
            with open(pf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            issues.append({"file": pf, "issue": f"Invalid JSON: {e}"})
            continue

        cname = data.get("name", os.path.basename(pf).replace(".json", ""))
        identity = data.get("identity", {})
        gender = identity.get("gender", "UNKNOWN")
        age = identity.get("age", "UNKNOWN")
        speech = data.get("base_speech_style", {})
        ending = speech.get("ending_particle", "")
        self_p = speech.get("self_pronoun", "")
        target_p = speech.get("target_pronoun", "")
        relationships = data.get("relationships", [])

        # 1. Name Semantic Clues
        name_words = set(re.findall(r'\b\w+\b', cname.lower()))
        has_male_word = bool(name_words & MALE_KEYWORDS)
        has_female_word = bool(name_words & FEMALE_KEYWORDS)

        # Context evidence
        ev = char_evidence.get(cname, {"male_clues": 0, "female_clues": 0, "sample_clues": []})

        suspected_gender = None
        reasons = []

        if has_male_word and not has_female_word:
            if gender == "FEMALE":
                suspected_gender = "MALE"
                reasons.append(f"Name contains male keyword ({name_words & MALE_KEYWORDS}) but gender is FEMALE")
        elif has_female_word and not has_male_word:
            if gender == "MALE":
                suspected_gender = "FEMALE"
                reasons.append(f"Name contains female keyword ({name_words & FEMALE_KEYWORDS}) but gender is MALE")

        # Context clue check (only if name doesn't already strongly define gender)
        if not has_male_word and not has_female_word:
            if ev["male_clues"] >= 3 and ev["female_clues"] == 0 and gender == "FEMALE":
                suspected_gender = "MALE"
                reasons.append(f"Scene context has {ev['male_clues']} male pronouns (he/him/his/sir) and 0 female pronouns")
            elif ev["female_clues"] >= 3 and ev["male_clues"] == 0 and gender == "MALE":
                suspected_gender = "FEMALE"
                reasons.append(f"Scene context has {ev['female_clues']} female pronouns (she/her) and 0 male pronouns")

        # Specific known male characters from game narrative
        KNOWN_MALES = {"Drake", "Damien", "Drex", "Bob", "Bruno", "Cyrus", "Lucas", "Oswald", "Wallace", "Troy", "Ritchie"}
        if cname in KNOWN_MALES and gender != "MALE":
            suspected_gender = "MALE"
            reasons.append("Known male key character in story narrative")

        KNOWN_FEMALES = {"Natalie", "Jinnie", "Shion", "Lily", "Hikari", "Erica", "Reiko", "Chisato", "Bonnie", "Lapina", "Lyra"}
        if cname in KNOWN_FEMALES and gender != "FEMALE":
            suspected_gender = "FEMALE"
            reasons.append("Known female key character in story narrative")

        if suspected_gender and suspected_gender != gender:
            gender_mismatches.append({
                "character": cname,
                "current_gender": gender,
                "expected_gender": suspected_gender,
                "reasons": reasons,
                "sample_clues": ev["sample_clues"]
            })

        # 2. Speech Particle vs Gender Mismatch
        if gender == "MALE" and ending in ["ค่ะ", "คะ", "จ้ะ"]:
            speech_mismatches.append({
                "character": cname,
                "gender": gender,
                "ending_particle": ending,
                "self_pronoun": self_p,
                "issue": f"MALE character using female particle '{ending}'"
            })
        elif gender == "FEMALE" and ending in ["ครับ", "ฮะ"]:
            speech_mismatches.append({
                "character": cname,
                "gender": gender,
                "ending_particle": ending,
                "self_pronoun": self_p,
                "issue": f"FEMALE character using male particle '{ending}'"
            })

        # 3. Aggressive/Rude character speaking politely with 'ค่ะ'
        is_rude = False
        base_state = data.get("base_state", {})
        for p in base_state.get("personality", []):
            if p.get("tag") in ["PER_SOC_RUDE", "PER_VIBE_AGGRESSIVE"] and p.get("weight", 0) >= 80:
                is_rude = True
                break
        if is_rude and ending in ["ค่ะ", "คะ"] and age != "CHILD":
            speech_mismatches.append({
                "character": cname,
                "gender": gender,
                "ending_particle": ending,
                "issue": f"Rude/Aggressive character using ultra-polite feminine particle '{ending}'"
            })

        # 4. Age checks
        has_child_word = any(w in cname.lower() for w in CHILD_KEYWORDS) and not any(w in name_words for w in ["hooker", "escort", "call"])
        has_elder_word = any(w in cname.lower() for w in ELDER_KEYWORDS)
        if has_child_word and age == "ADULT":
            age_mismatches.append({"character": cname, "current_age": age, "expected_age": "CHILD", "reason": "Name indicates child/kid"})
        elif has_elder_word and age == "ADULT":
            age_mismatches.append({"character": cname, "current_age": age, "expected_age": "ELDER", "reason": "Name indicates elder/old man"})

    report = {
        "total_profiles": len(profile_files),
        "gender_mismatches_count": len(gender_mismatches),
        "gender_mismatches": gender_mismatches,
        "speech_mismatches_count": len(speech_mismatches),
        "speech_mismatches": speech_mismatches,
        "age_mismatches_count": len(age_mismatches),
        "age_mismatches": age_mismatches,
        "file_issues": issues
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print("=== CHARACTER PROFILE AUDIT RESULTS ===")
    print("="*60)
    print(f"Total Profiles Audited: {len(profile_files)}")
    print(f"Gender Mismatches Detected: {len(gender_mismatches)}")
    print(f"Speech/Particle Mismatches Detected: {len(speech_mismatches)}")
    print(f"Age Group Mismatches Detected: {len(age_mismatches)}")
    print(f"Report saved to: {REPORT_PATH}")
    print("="*60)

    if gender_mismatches:
        print("\n[Sample Gender Mismatches]:")
        for gm in gender_mismatches[:15]:
            print(f" - {gm['character']}: Current={gm['current_gender']} -> Expected={gm['expected_gender']} | {', '.join(gm['reasons'])}")

    if speech_mismatches:
        print("\n[Sample Speech Particle Mismatches]:")
        for sm in speech_mismatches[:10]:
            print(f" - {sm['character']} ({sm['gender']}): ending='{sm['ending_particle']}' | {sm['issue']}")

    if age_mismatches:
        print("\n[Sample Age Mismatches]:")
        for am in age_mismatches[:10]:
            print(f" - {am['character']}: Current={am['current_age']} -> Expected={am['expected_age']} | {am['reason']}")

if __name__ == "__main__":
    audit_profiles()
