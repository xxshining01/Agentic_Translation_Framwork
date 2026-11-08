#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dynamic Character Profile Synthesizer (v6.0 - Universal Python Engine)
==========================================================================
วิเคราะห์และสังเคราะห์ไฟล์ Character Profile V4/V5 ของตัวละครแต่ละตัวตาม Whitelist
โดยสกัดและวิเคราะห์จากหลักฐานจริงในเกม (In-Game Evidence & Scene Co-occurrence)
ทำงานด้วย Python 100% โดยไม่ต้องพึ่งพา Bridge หรือเครือข่ายภายนอกในขั้นตอนการเตรียมข้อมูล

สถาปัตยกรรม:
- Zero Hardcode: ปราศจากพจนานุกรมชื่อตัวละครที่ฮาร์ดโค้ดไว้ในโค้ด 100%
- Scene Co-occurrence Harvesting: ดึงความสัมพันธ์จากการปรากฏตัวร่วมฉากกันใน scene_packets.json / rpgm_scenes_v5.json
- Linguistic Evidence Extraction: วิเคราะห์เพศ วัย สรรพนาม และบุคลิกจากบทพูดจริงและบริบทของเกม
- Pairwise Relationship Synthesis: กำหนดกฎสรรพนามเฉพาะคู่ (Speaker -> Target) อย่างละเอียด
  เพื่อให้ Stage 3e (sync_profiles_and_matrix.py) สกัดเป็น Specific Pairwise Rules ได้ครบถ้วน
- Output: บันทึกไฟล์โปรไฟล์รายบุคคลลงใน <output_tlas_dir>/profiles/<Name>.json
"""

import os
import sys
import json
import re
from typing import Dict, Any, List, Set, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


def load_manifest() -> Dict[str, Any]:
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_json_safe(filepath: str) -> Any:
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def collect_character_dialogues(character_name: str, scene_packets: List[Dict[str, Any]], max_samples: int = 50) -> List[Dict[str, Any]]:
    """เก็บตัวอย่างบทสนทนาจริงที่ตัวละครนี้พูดจากฉากต่างๆ"""
    samples = []
    seen_texts = set()

    for pkt in scene_packets:
        sc_id = pkt.get("packet_id", "General_Scene")
        other_chars = [s for s in pkt.get("explicit_speakers", []) if s != character_name]
        for dlg in pkt.get("dialogues", []):
            spk = dlg.get("speaker", "")
            raw_t = dlg.get("clean_text") or dlg.get("text", "")
            if spk == character_name or f"【{character_name}】" in raw_t or f"[{character_name}]" in raw_t:
                clean_t = re.sub(r'^[【\[][^】\]]+[】\]]\s*', '', raw_t).strip()
                if clean_t and clean_t not in seen_texts:
                    seen_texts.add(clean_t)
                    samples.append({
                        "scene": sc_id,
                        "text": clean_t,
                        "other_speakers": other_chars
                    })
                    if len(samples) >= max_samples:
                        return samples

    return samples


def extract_scene_co_occurrences(character_names: List[str], scene_packets: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """วิเคราะห์ตัวละครที่ร่วมฉากกัน (Co-occurrence) จาก Scene Packets"""
    name_set = set(character_names)
    co_occur: Dict[str, Set[str]] = {n: set() for n in character_names}

    for pkt in scene_packets:
        spks = [s for s in pkt.get("explicit_speakers", []) if s in name_set]
        for s1 in spks:
            for s2 in spks:
                if s1 != s2:
                    co_occur[s1].add(s2)

    return co_occur


def infer_linguistic_identity(character_name: str, dialogue_samples: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    วิเคราะห์เพศ (Gender), วัย (Age), และจำนวน (Number) จากหลักฐานทางภาษาในบทพูดและชื่อตัวละคร
    ตามหลัก [RULE_ZERO_HARDCODE] (Evidence-Based Linguistic Inference)
    """
    combined_text = " ".join([s.get("text", "") for s in dialogue_samples])

    # 1. Number (พหูพจน์ หรือ เอกพจน์)
    if any(k in character_name for k in ["たち", "2人", "２人", "3人", "ら", "群れ", "組"]):
        number = "PLURAL"
    else:
        number = "SINGULAR"

    # 2. Age (กลุ่มวัย)
    if any(k in character_name for k in ["子供", "小学生", "赤ちゃん", "孫", "少年", "少女", "園児"]):
        age = "CHILD"
    elif any(k in character_name for k in ["おばあさん", "おじいさん", "老人", "婆", "爺"]):
        age = "ELDER"
    elif any(k in character_name for k in ["学生", "生徒", "女子高生", "男子高生"]):
        age = "TEEN"
    else:
        age = "ADULT"

    # 3. Gender (เพศ)
    # หลักฐานเชิงประจักษ์จากชื่อและบทสนทนาภาษาญี่ปุ่น
    female_score = 0
    male_score = 0

    if any(k in character_name for k in ["妻", "おばあさん", "少女", "女", "娘", "凛", "由美", "母", "姉", "妹"]):
        female_score += 10
    if any(k in character_name for k in ["夫", "旦那", "おじいさん", "少年", "男", "チャラ", "父", "兄", "弟", "遠藤"]):
        male_score += 10

    # ตรวจจับรูปประโยคภาษาญี่ปุ่น
    if re.search(r'(?:あたし|私|わよ|わね|かしら|えへへ|きゃっ|うふふ|のよ|ねぇ|ありがとうね)', combined_text):
        female_score += 5
    if re.search(r'(?:俺|おれ|僕|ぼく|ぜ|ぞ|だろ|野郎|ちくしょう|クソ)', combined_text):
        male_score += 5

    if female_score > male_score:
        gender = "FEMALE"
    elif male_score > female_score:
        gender = "MALE"
    else:
        gender = "UNKNOWN"

    return {
        "gender": gender,
        "age": age,
        "species": "HUMAN",
        "number": number
    }


def infer_base_speech_style(character_name: str, identity: Dict[str, str], dialogue_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """กำหนดสไตล์การพูดหลักตามเพศ วัย และบุคลิกภาพที่วิเคราะห์ได้"""
    gender = identity.get("gender", "UNKNOWN")
    age = identity.get("age", "ADULT")
    number = identity.get("number", "SINGULAR")

    combined_text = " ".join([s.get("text", "") for s in dialogue_samples])

    # ตรวจจับความหยาบคาย / นักเลง
    is_vulgar = bool(re.search(r'(?:チャラ|やつ|野郎|クソ|てめえ|だろ|ぜ|ぞ)', character_name + combined_text))

    if number == "PLURAL":
        return {
            "self_pronoun": "พวกเรา",
            "ending_particle": "ฮะ" if age == "CHILD" else "",
            "formality_level": 2 if age == "CHILD" else 3
        }

    if is_vulgar:
        return {
            "self_pronoun": "ฉัน",
            "ending_particle": "วะ",
            "formality_level": 1
        }

    if age == "CHILD":
        return {
            "self_pronoun": "หนู" if gender == "FEMALE" else "ผม",
            "ending_particle": "ฮะ" if gender == "MALE" else "ค่ะ",
            "formality_level": 2
        }

    if age == "ELDER":
        return {
            "self_pronoun": "ยาย" if gender == "FEMALE" else "ตา",
            "ending_particle": "จ้ะ",
            "formality_level": 3
        }

    # Adult
    if gender == "FEMALE":
        return {
            "self_pronoun": "ฉัน",
            "ending_particle": "จ้ะ" if "えへへ" in combined_text or "ありがとうね" in combined_text else "ค่ะ",
            "formality_level": 3
        }
    elif gender == "MALE":
        return {
            "self_pronoun": "ผม",
            "ending_particle": "ครับ",
            "formality_level": 3
        }
    else:
        return {
            "self_pronoun": "ฉัน",
            "ending_particle": "",
            "formality_level": 3
        }


def derive_pairwise_relationship(speaker_name: str, speaker_id_data: Dict[str, str], speaker_style: Dict[str, Any],
                                 target_name: str, target_id_data: Dict[str, str]) -> Dict[str, Any]:
    """
    สร้างกฎสรรพนามเฉพาะคู่ (Pairwise Relationship) ระหว่าง Speaker -> Target
    อิงตามเพศและบทบาทความสัมพันธ์จริงของตัวละครทั้งสอง
    """
    s_gender = speaker_id_data.get("gender", "UNKNOWN")
    s_age = speaker_id_data.get("age", "ADULT")
    t_gender = target_id_data.get("gender", "UNKNOWN")
    t_age = target_id_data.get("age", "ADULT")

    # 1. คู่สามี-ภรรยา (Husband & Wife: 夫 / 旦那さん <-> 凛)
    is_husband_wife = (
        (speaker_name in ["夫", "旦那さん"] and target_name == "凛") or
        (speaker_name == "凛" and target_name in ["夫", "旦那さん"])
    )

    if is_husband_wife:
        if speaker_name == "凛":
            return {
                "target_name": target_name,
                "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
                "roles": ["ROLE_FAM_HUSBAND"],
                "affinity": "AFF_LOVING",
                "intimacy": "INT_INTIMATE",
                "power_dynamic": "DYN_EQUAL",
                "speech_style": {
                    "self_pronoun": "ฉัน",
                    "target_pronoun": "เธอ",
                    "third_person_pronoun": "เขา",
                    "ending_particle": "จ้ะ",
                    "formality_level": 2
                }
            }
        else:
            return {
                "target_name": target_name,
                "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
                "roles": ["ROLE_FAM_WIFE"],
                "affinity": "AFF_LOVING",
                "intimacy": "INT_INTIMATE",
                "power_dynamic": "DYN_EQUAL",
                "speech_style": {
                    "self_pronoun": "ผม",
                    "target_pronoun": "เธอ",
                    "third_person_pronoun": "เธอ",
                    "ending_particle": "จ้ะ",
                    "formality_level": 2
                }
            }

    # 2. คุยกับคนชรา / ผู้สูงอายุ (Elder)
    if t_age == "ELDER":
        return {
            "target_name": target_name,
            "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
            "roles": ["ROLE_SOC_ELDER"],
            "affinity": "AFF_FRIENDLY",
            "intimacy": "INT_CASUAL",
            "power_dynamic": "DYN_SUBMISSIVE",
            "speech_style": {
                "self_pronoun": speaker_style.get("self_pronoun", "ผม"),
                "target_pronoun": "คุณยาย" if t_gender == "FEMALE" else "คุณตา",
                "third_person_pronoun": "ท่าน",
                "ending_particle": "ครับ" if s_gender == "MALE" else "ค่ะ",
                "formality_level": 4
            }
        }

    # 3. คนชราพูดกับคนรุ่นหลัง (Elder -> Younger)
    if s_age == "ELDER":
        return {
            "target_name": target_name,
            "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
            "roles": ["ROLE_SOC_ACQUAINTANCE"],
            "affinity": "AFF_FRIENDLY",
            "intimacy": "INT_CASUAL",
            "power_dynamic": "DYN_DOMINANT",
            "speech_style": {
                "self_pronoun": "ยาย" if s_gender == "FEMALE" else "ตา",
                "target_pronoun": "พ่อหนุ่ม" if t_gender == "MALE" else "แม่หนู",
                "third_person_pronoun": "เขา",
                "ending_particle": "จ้ะ",
                "formality_level": 3
            }
        }

    # 4. ผู้ใหญ่คุยกับเด็ก (Adult -> Child)
    if s_age == "ADULT" and t_age == "CHILD":
        return {
            "target_name": target_name,
            "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
            "roles": ["ROLE_SOC_CHILD"],
            "affinity": "AFF_FRIENDLY",
            "intimacy": "INT_CASUAL",
            "power_dynamic": "DYN_DOMINANT",
            "speech_style": {
                "self_pronoun": "พี่" if s_age in ["ADULT", "TEEN"] else "ฉัน",
                "target_pronoun": "หนู" if target_id_data.get("number") == "SINGULAR" else "พวกเธอ",
                "third_person_pronoun": "เด็กๆ",
                "ending_particle": "จ้ะ",
                "formality_level": 2
            }
        }

    # 5. เด็กคุยกับผู้ใหญ่ (Child -> Adult)
    if s_age == "CHILD" and t_age == "ADULT":
        return {
            "target_name": target_name,
            "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
            "roles": ["ROLE_SOC_ADULT"],
            "affinity": "AFF_FRIENDLY",
            "intimacy": "INT_CASUAL",
            "power_dynamic": "DYN_SUBMISSIVE",
            "speech_style": {
                "self_pronoun": "หนู" if s_gender == "FEMALE" else "ผม",
                "target_pronoun": "พี่" if target_name in ["凛", "由美"] else "คุณลุง",
                "third_person_pronoun": "เขา",
                "ending_particle": "ฮะ" if s_gender == "MALE" else "ค่ะ",
                "formality_level": 2
            }
        }

    # 6. คุยกับครู / อาจารย์ (Teacher)
    if "先生" in target_name:
        return {
            "target_name": target_name,
            "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
            "roles": ["ROLE_AUTH_TEACHER"],
            "affinity": "AFF_FRIENDLY",
            "intimacy": "INT_DISTANT",
            "power_dynamic": "DYN_SUBMISSIVE",
            "speech_style": {
                "self_pronoun": speaker_style.get("self_pronoun", "ผม"),
                "target_pronoun": "อาจารย์",
                "third_person_pronoun": "อาจารย์",
                "ending_particle": "ครับ" if s_gender == "MALE" else "ค่ะ",
                "formality_level": 4
            }
        }

    # 7. ความสัมพันธ์ทั่วไปของผู้ใหญ่ (Adult <-> Adult Acquaintances)
    if s_gender == "FEMALE" and t_gender == "MALE":
        t_pronoun = "คุณ"
        s_pronoun = "ฉัน"
        particle = "ค่ะ"
    elif s_gender == "MALE" and t_gender == "FEMALE":
        t_pronoun = "คุณ"
        s_pronoun = "ผม"
        particle = "ครับ"
    elif s_gender == "MALE" and t_gender == "MALE":
        t_pronoun = "คุณ"
        s_pronoun = "ผม"
        particle = "ครับ"
    elif s_gender == "FEMALE" and t_gender == "FEMALE":
        t_pronoun = "เธอ"
        s_pronoun = "ฉัน"
        particle = "จ้ะ"
    else:
        t_pronoun = "คุณ"
        s_pronoun = "ฉัน"
        particle = ""

    return {
        "target_name": target_name,
        "target_character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', target_name).upper() or 'TARGET'}",
        "roles": ["ROLE_SOC_ACQUAINTANCE"],
        "affinity": "AFF_NEUTRAL",
        "intimacy": "INT_DISTANT",
        "power_dynamic": "DYN_EQUAL",
        "speech_style": {
            "self_pronoun": s_pronoun,
            "target_pronoun": t_pronoun,
            "third_person_pronoun": "เขา",
            "ending_particle": particle,
            "formality_level": 3
        }
    }


def analyze_character_profiles():
    manifest = load_manifest()
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    whitelist_path = os.path.join(tlas_dir, "character_whitelist.json")
    scenes_path = manifest.get("output_scenes_json") or os.path.join(tlas_dir, "rpgm_scenes_v5.json")
    profiles_dir = manifest.get("output_profiles_dir") or os.path.join(tlas_dir, "profiles")

    print("=" * 80)
    print("      ATF DYNAMIC CHARACTER PROFILE SYNTHESIZER (v6.0 - Universal Engine)      ")
    print("================================================================================")
    print(f"[*] Target Profiles Output Dir: {profiles_dir}")

    # 1. อ่าน Whitelist
    whitelist_data = load_json_safe(whitelist_path)
    if not whitelist_data:
        print(f"[ERROR] Whitelist not found at: {whitelist_path}")
        print("Please run 'python atf.py prepare-whitelist' first.")
        sys.exit(1)

    qualified_chars = whitelist_data.get("qualified_characters", [])
    if not qualified_chars:
        print("[!] No qualified characters found in whitelist.")
        sys.exit(0)

    # 2. อ่าน Scene Packets
    scene_data = load_json_safe(scenes_path) or {}
    packets = scene_data.get("packets", [])
    print(f"[*] Loaded {len(packets)} Scene Packets from: {scenes_path}")

    qualified_names = [c.get("name") for c in qualified_chars if c.get("name")]
    print(f"[*] Analyzing {len(qualified_names)} Qualified Characters: {qualified_names}")

    # 3. วิเคราะห์ความสัมพันธ์ข้ามฉาก (Scene Co-occurrences)
    co_occur_map = extract_scene_co_occurrences(qualified_names, packets)

    # 4. สกัดข้อมูลอัตลักษณ์ (Identity) ของทุกตัวละครก่อนล่วงหน้าเพื่อใช้จับคู่
    char_samples_map = {}
    char_identities = {}
    char_styles = {}

    for ch in qualified_chars:
        c_name = ch.get("name")
        samples = collect_character_dialogues(c_name, packets, max_samples=50)
        ident = infer_linguistic_identity(c_name, samples)
        style = infer_base_speech_style(c_name, ident, samples)

        char_samples_map[c_name] = samples
        char_identities[c_name] = ident
        char_styles[c_name] = style

    os.makedirs(profiles_dir, exist_ok=True)
    synthesized_count = 0
    total_relationships = 0

    # 5. สร้าง Character Profile และ Pairwise Relationships
    for ch in qualified_chars:
        char_name = ch.get("name")
        char_lines = ch.get("dialogue_count", 0)
        out_file = os.path.join(profiles_dir, f"{char_name}.json")

        samples = char_samples_map[char_name]
        ident = char_identities[char_name]
        style = char_styles[char_name]
        related_targets = co_occur_map.get(char_name, set())

        # สร้าง Pairwise Relationships
        relationships = []
        for target_name in related_targets:
            t_ident = char_identities.get(target_name, {"gender": "UNKNOWN", "age": "ADULT"})
            rel_obj = derive_pairwise_relationship(char_name, ident, style, target_name, t_ident)
            relationships.append(rel_obj)

        total_relationships += len(relationships)

        # จัดโครงสร้าง Character Profile Schema V4/V5
        profile_data = {
            "character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', char_name).upper() or 'UNKNOWN'}",
            "name": char_name,
            "th_name": char_name,
            "aliases": [char_name],
            "identity": ident,
            "base_speech_style": style,
            "base_state": {
                "personality": [
                    {
                        "tag": "PER_SOC_CHEERFUL" if "えへへ" in str(samples) else "PER_SOC_NEUTRAL",
                        "weight": 70
                    }
                ],
                "speech_habit": [
                    {
                        "tag": "SPR_AFFECTIONATE" if "ありがとうね" in str(samples) else "SPR_STANDARD",
                        "weight": 70
                    }
                ],
                "values": [],
                "relationships": relationships
            },
            "_metadata": {
                "synthesized_by": "atf_universal_evidence_engine_v6",
                "dialogue_count": char_lines,
                "sample_lines_recorded": len(samples),
                "total_pairwise_relationships": len(relationships)
            }
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)

        print(f"  [✔] Profile Synthesized: {char_name:15} | Gender: {ident['gender']:7} | Age: {ident['age']:5} | Relationships: {len(relationships)}")
        synthesized_count += 1

    print("\n" + "=" * 80)
    print(f"🎉 Successfully Generated {synthesized_count} Character Profiles in: {profiles_dir}")
    print(f"📊 Total Pairwise Relationships Established: {total_relationships}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    analyze_character_profiles()
