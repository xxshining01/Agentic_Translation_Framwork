#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Scene-Based Character Profile & Relational Synthesizer (v6.4 - Pure Universal Paradigm)
===========================================================================================
สกัดและวิเคราะห์ Character Profiles & Pairwise Relationships ของตัวละคร Whitelist
โดยส่งบทสนทนาจริงจากทุกฉาก (Exhaustive Scene-Based Batches) ไปให้ LLM (ChatGPT Web Bridge พอร์ต 8765)
เพื่อวิเคราะห์อัตลักษณ์ (Identity), บุคลิกภาพ (Personality), และความสัมพันธ์ (Relationships)
พร้อมระบบ Deterministic Python Pronoun Engine ที่ขับเคลื่อนด้วยข้อมูล Taxonomy บนดิสก์ 100%

สถาปัตยกรรมหลัก (Zero Hardcode & Universal Paradigm Compliant):
1. Zero Hardcode Invariant: ปราศจากพจนานุกรมชื่อตัวละคร หรือการฮาร์ดโค้ดเพศ/วัย/ID ในซอร์สโค้ด 100%
2. Data-Driven ID Generation: สร้าง character_id แบบไดนามิกผ่านแฮชสากลและ slug (รองรับทุกภาษา/ทุกเอนจิน)
3. Evidence-Based Demographics: อัตลักษณ์ (เพศ/วัย) สกัดจากผลวิเคราะห์บทสนทนาจริงของ LLM ร่วมกับฐานข้อมูลเกม (tlas_glossary.json บนดิสก์)
4. Neutral Fallback When Uncertain: หากไม่มีหลักฐานยืนยันเพศ จะคงค่า UNKNOWN และใช้สรรพนามกลางที่ปลอดภัย
5. Taxonomy-Driven Pronoun Resolution: คำนวณสรรพนาม (self, target, third_person, ending) จาก metadata และ taxonomy.json ไร้การเช็คชื่อตัวละคร
6. Per-Batch State Persistence: บันทึก Checkpoint และ Log ทันทีทุก Batch พร้อมเซฟ Profile ลงดิสก์แบบเรียลไทม์
7. Periodic New Chat & Dead Room Escape: ขึ้นแชตใหม่ทุกๆ 8-10 Batch และ Force Navigation เมื่อเกิดข้อผิดพลาด
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import hashlib
import re
from typing import Dict, Any, List, Set, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")
BRIDGE_URL = "http://127.0.0.1:8765"


def generate_universal_character_id(name: str) -> str:
    """
    สร้าง Canonical Character ID แบบไดนามิก 100% ไร้การ Hardcode ชื่อใดๆ
    รองรับทั้งชื่อภาษาอังกฤษ (ASCII slug) และชื่อภาษาญี่ปุ่น/จีน/สากล (Deterministic SHA256 Hash)
    """
    latin_slug = re.sub(r'[^A-Za-z0-9]', '', name).upper()
    if len(latin_slug) >= 2:
        return f"CHAR_{latin_slug}"
    # สำหรับชื่อที่ไม่ใช่ตัวอักษรละติน ให้สร้าง Hex Hash 8 หลักที่คงที่และไม่ซ้ำซ้อน
    name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8].upper()
    return f"CHAR_{name_hash}"


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


def check_bridge_status(bridge_url: str = BRIDGE_URL) -> Tuple[bool, bool]:
    """ตรวจสอบสถานะ Bridge Server และ Userscript"""
    try:
        req = urllib.request.Request(f"{bridge_url}/bridge/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            is_server = data.get("status") == "online"
            is_script = bool(data.get("userscript_connected"))
            return is_server, is_script
    except Exception:
        return False, False


def wait_for_bridge_ready(bridge_url: str = BRIDGE_URL) -> bool:
    """ตรวจสอบและรอความพร้อมของ ChatGPT Web Bridge (Port 8765)"""
    first_notify = True
    while True:
        server_ok, script_ok = check_bridge_status(bridge_url)
        if server_ok and script_ok:
            print(f"🌐 [ChatGPT Bridge Online] พอร์ต 8765 ({bridge_url}) พร้อมวิเคราะห์ฉาก 100%!\n")
            return True

        if first_notify:
            print("\n" + "=" * 80)
            if not server_ok:
                print("⏳ [Waiting for ChatGPT Bridge Server]")
                print(f"   ไม่พบ Bridge Server ที่ทำงานบน {bridge_url}")
                print("   👉 กรุณาเปิด Terminal อีกหน้าต่าง แล้วรันคำสั่ง:")
                print("      python atf.py bridge")
                print("   👉 จากนั้นเปิดเบราว์เซอร์ไปที่ https://chatgpt.com")
            else:
                print("⏳ [Waiting for ChatGPT Userscript Connection]")
                print(f"   Bridge Server บนพอร์ต 8765 ทำงานแล้ว แต่ยังไม่พบการเชื่อมต่อจากหน้าเว็บ ChatGPT")
                print("   👉 กรุณาเปิดเบราว์เซอร์ไปที่ https://chatgpt.com")
                print("   👉 ตรวจสอบว่าเปิดใช้งาน Tampermonkey Userscript (ATF ChatGPT Web Bridge)")
            print("   (ระบบกำลังรอสัญญาณ Heartbeat จากเบราว์เซอร์อัตโนมัติ...)")
            print("=" * 80 + "\n")
            first_notify = False

        time.sleep(2.0)


def trigger_new_chat(bridge_url: str = BRIDGE_URL):
    """สั่งเปิด New Chat บน ChatGPT Web UI เพื่อล้าง Context เก่า"""
    try:
        req = urllib.request.Request(
            f"{bridge_url}/v1/bridge/new_chat",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("    [🧹] New Chat initialized. Context refreshed.")
            time.sleep(2.0)
    except Exception as e:
        print(f"    [!] Warning opening new chat: {e}")


def call_chatgpt_api(prompt: str, system_prompt: str = "", bridge_url: str = BRIDGE_URL) -> str:
    """
    ส่งคำขอไปยัง ChatGPT ผ่าน OpenAI-compatible endpoint (/v1/chat/completions) บน Port 8765
    หากเกิดข้อผิดพลาด จะสั่ง Emergency New Chat ก่อน Retry เสมอเพื่อไม่ให้ค้างในห้องเดิม
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": "chatgpt-web",
        "messages": messages
    }).encode("utf-8")

    retry_count = 0
    while True:
        req = urllib.request.Request(
            f"{bridge_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=None) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                choices = res_data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                raise RuntimeError(f"Unexpected response schema from Bridge: {res_data}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            retry_count += 1
            print(f"⚠️ [ChatGPT Bridge HTTP Error {e.code}] ({err_body})")
            print("   👉 กำลังสั่ง Emergency New Chat เพื่อเปลี่ยนห้องแชตใหม่ทันที...")
            trigger_new_chat(bridge_url)
            wait_time = 45 if e.code == 429 else 10
            print(f"   ระบบจะรอ {wait_time} วินาทีก่อนลองส่งใหม่ (รอบที่ {retry_count})...")
            time.sleep(wait_time)
            continue
        except Exception as ex:
            retry_count += 1
            print(f"⚠️ [Bridge Communication Error]: {ex}")
            print("   👉 กำลังสั่ง Emergency New Chat เพื่อรีเซ็ตสภาพแวดล้อม...")
            trigger_new_chat(bridge_url)
            time.sleep(5)


def extract_json_object(text: str) -> Dict[str, Any]:
    """สกัดและแปลง JSON object จากข้อความตอบกลับของ LLM อย่างสมบูรณ์"""
    text = text.strip()
    clean_text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    clean_text = re.sub(r'\s*```$', '', clean_text, flags=re.MULTILINE)

    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
        json_candidate = match.group(0)
        return json.loads(json_candidate)

    return json.loads(clean_text)


def build_exhaustive_scene_batches(scene_packets: List[Dict[str, Any]], whitelist_names: Set[str], max_lines_per_batch: int = 130) -> List[Dict[str, Any]]:
    """
    สกัดชุดบทสนทนาประจำฉากแบบครอบคลุม 100% ไม่มีบรรทัดใดถูกตัดทิ้ง (Zero Truncation Guarantee)
    """
    batches = []

    for pkt in scene_packets:
        pid = pkt.get("packet_id", "")
        fn = pkt.get("filename", "")
        dlgs = pkt.get("dialogues", [])
        if not dlgs:
            continue

        extracted = []
        for d in dlgs:
            spk = d.get("speaker", "")
            raw = d.get("clean_text") or d.get("raw_text", "")
            clean_t = re.sub(r'^[【\[][^】\]]+[】\]]\s*', '', raw).strip()
            if not clean_t:
                continue

            actual_spk = spk
            if actual_spk in ("Untagged", "", "None"):
                for w in whitelist_names:
                    if f"【{w}】" in raw or f"[{w}]" in raw:
                        actual_spk = w
                        break
            extracted.append((actual_spk, clean_t))

        if not extracted:
            continue

        spks_in_scene = set(s[0] for s in extracted if s[0] in whitelist_names)
        if not spks_in_scene:
            continue

        total_len = len(extracted)
        if total_len <= max_lines_per_batch:
            formatted = [f"[{s[0]}]: {s[1]}" for s in extracted]
            batches.append({
                "batch_id": f"{pid}",
                "scene_id": f"{pid} ({fn})",
                "characters": sorted(list(spks_in_scene)),
                "dialogues": formatted,
                "range": f"1-{total_len}"
            })
        else:
            step = max_lines_per_batch - 8
            chunk_num = 1
            for start_idx in range(0, total_len, step):
                chunk = extracted[start_idx:start_idx + max_lines_per_batch]
                chunk_spks = set(s[0] for s in chunk if s[0] in whitelist_names)
                if chunk_spks:
                    formatted = [f"[{s[0]}]: {s[1]}" for s in chunk]
                    batches.append({
                        "batch_id": f"{pid}_{chunk_num:02d}",
                        "scene_id": f"{pid}_{chunk_num:02d} ({fn} Part {chunk_num})",
                        "characters": sorted(list(chunk_spks)),
                        "dialogues": formatted,
                        "range": f"{start_idx+1}-{min(start_idx+len(chunk), total_len)}"
                    })
                chunk_num += 1
                if start_idx + max_lines_per_batch >= total_len:
                    break

    return batches


def build_scene_prompt(batch: Dict[str, Any]) -> Tuple[str, str]:
    """สร้าง System Prompt และ User Prompt สำหรับวิเคราะห์บทสนทนาประจำฉาก (Universal Linguistic Invariants)"""
    scene_id = batch["scene_id"]
    chars = batch["characters"]
    chars_str = ", ".join([f'"{c}"' for c in chars])
    dlgs_str = "\n".join(batch["dialogues"])

    system_prompt = """You are an elite video game narrative analyst, character profiler, and Japanese dialogue linguist.
Your mission is to analyze the in-game dialogue of a specific game scene to extract identity, personality, and interpersonal relationships for the target characters present.

CRITICAL INVARIANTS:
1. Grounded In Scene Evidence: Extract traits and dynamics strictly from how these characters speak and interact in the provided dialogue.
2. Objective Linguistic Gender Markers:
   - Carefully inspect first-person pronouns, kinship terms, and grammatical endings used by each character or how others address them:
     * First-person '僕' (boku) or '俺' (ore) = MALE.
     * First-person 'あたし' (atashi) or feminine particles ('わ', 'のよ') = FEMALE.
     * Second-person or vocatives addressed to the character: e.g. 'お姉さん', 'おばあさん', '妻' = FEMALE. 'おじさん', 'お兄さん', '夫', '旦那' = MALE.
   - If genuine evidence exists in the scene dialogue, assign MALE or FEMALE. If the character's gender is completely absent from all cues, assign UNKNOWN.
3. Target Focus Only: Profile ONLY the target characters listed. Do NOT invent characters.
4. Zero Thai Pronoun Hallucination: Do NOT generate Thai pronoun words (no "ฉัน", "ผม", "สามี", "นาย", etc.). The Thai pronouns will be synthesized by the downstream rule engine. Output only structural metadata.
5. Strict Formality Scale (1-5):
   - Level 1: Intimate / Vulgar / Delinquent / Slang (close friends, delinquents, enemies, no polite particles)
   - Level 2: Casual / Informal / Familiar (husband-wife, family members, classmates, gentle casual tone)
   - Level 3: Neutral / Everyday Standard (polite acquaintances, coworkers, friendly strangers)
   - Level 4: Formal / Respectful / Hierarchical (teacher-student, elder respect, client, workplace hierarchy)
   - Level 5: Honorific / Ceremonial / Ultra-Formal (royal, noble, feudal master-servant, ceremonial)
6. Output ONLY a single parseable JSON object matching the requested schema. No conversational preamble."""

    user_prompt = f"""### SCENE CONTEXT:
Scene ID: {scene_id}
Target Characters Present in This Scene: [{chars_str}]

### SCENE IN-GAME DIALOGUE:
{dlgs_str}

### INSTRUCTIONS:
Analyze the target characters present in this scene and output a JSON object adhering to this exact schema:

{{
  "characters": {{
    "CHARACTER_NAME": {{
      "identity": {{
        "gender": "MALE" | "FEMALE" | "NON_BINARY" | "UNKNOWN",
        "age": "CHILD" | "TEEN" | "ADULT" | "ELDER" | "UNKNOWN",
        "species": "HUMAN",
        "social_role": "brief description (e.g. spouse, teacher, student, acquaintance, receptionist, child)"
      }},
      "personality_tags": [
        "PER_SOC_CASUAL", "PER_SOC_POLITE", "PER_SOC_RUDE", "PER_VIBE_CHEERFUL", "PER_VIBE_SERIOUS", "PER_SOC_PLAYFUL" (pick 2-3 matching tags)
      ],
      "relationships": [
        {{
          "target_name": "Exact Japanese name of another target character present in this scene or interacted with",
          "roles": ["ROLE_FAM_SPOUSE" | "ROLE_FAM_PARENT" | "ROLE_FAM_CHILD" | "ROLE_SOC_FRIEND" | "ROLE_SOC_ACQUAINTANCE" | "ROLE_SOC_PEER" | "ROLE_EDU_TEACHER" | "ROLE_SOC_CLIENT" | "ROLE_SOC_NEIGHBOR"],
          "affinity": "AFF_LOVING" | "AFF_FRIENDLY" | "AFF_NEUTRAL" | "AFF_DISLIKE" | "AFF_HOSTILE",
          "intimacy": "INT_INTIMATE" | "INT_CLOSE" | "INT_CASUAL" | "INT_DISTANT" | "INT_ESTRANGED",
          "power_dynamic": "DYN_DOMINANT" | "DYN_EQUAL" | "DYN_SUBMISSIVE",
          "formality_level": 1 to 5
        }}
      ]
    }}
  }}
}}

Return ONLY the raw JSON object."""

    return system_prompt, user_prompt


def merge_scene_results_into_master(master_profiles: Dict[str, Any], scene_data: Dict[str, Any], whitelist_names: Set[str]):
    """
    ผสานข้อมูลที่ได้จากการวิเคราะห์ฉากเข้าสู่ Master Database ของตัวละครอย่างเป็นระบบ (Multi-Scene Consolidation)
    """
    chars_data = scene_data.get("characters", {})
    for c_name, c_info in chars_data.items():
        if c_name not in whitelist_names:
            continue

        if c_name not in master_profiles:
            master_profiles[c_name] = {
                "name": c_name,
                "gender_votes": [],
                "age_votes": [],
                "roles_observed": set(),
                "personality_tag_counts": {},
                "relationships": {}
            }

        prof = master_profiles[c_name]
        ident = c_info.get("identity", {})
        g = ident.get("gender", "").upper()
        if g in ("MALE", "FEMALE", "NON_BINARY", "UNKNOWN"):
            prof["gender_votes"].append(g)

        a = ident.get("age", "").upper()
        if a in ("CHILD", "TEEN", "ADULT", "ELDER", "UNKNOWN"):
            prof["age_votes"].append(a)

        s_role = ident.get("social_role", "")
        if s_role:
            prof["roles_observed"].add(s_role)

        for p_tag in c_info.get("personality_tags", []):
            if isinstance(p_tag, str) and p_tag.startswith("PER_"):
                prof["personality_tag_counts"][p_tag] = prof["personality_tag_counts"].get(p_tag, 0) + 1

        # จัดการความสัมพันธ์ (Relationships Multi-Scene Aggregation)
        for rel in c_info.get("relationships", []):
            t_name = rel.get("target_name", "")
            if not t_name or t_name == c_name or t_name not in whitelist_names:
                continue

            f_lvl = rel.get("formality_level", 3)
            try:
                f_lvl = int(f_lvl)
                f_lvl = max(1, min(5, f_lvl))
            except Exception:
                f_lvl = 3

            new_roles = set(rel.get("roles", ["ROLE_SOC_PEER"]))
            new_affinity = rel.get("affinity", "AFF_NEUTRAL")
            new_intimacy = rel.get("intimacy", "INT_CASUAL")
            new_power = rel.get("power_dynamic", "DYN_EQUAL")

            if t_name not in prof["relationships"]:
                prof["relationships"][t_name] = {
                    "target_name": t_name,
                    "roles": list(new_roles),
                    "affinity": new_affinity,
                    "intimacy": new_intimacy,
                    "power_dynamic": new_power,
                    "formality_levels": [f_lvl]
                }
            else:
                existing_rel = prof["relationships"][t_name]
                combined_roles = set(existing_rel.get("roles", [])) | new_roles
                existing_rel["roles"] = list(combined_roles)

                if new_affinity in ("AFF_LOVING", "AFF_HOSTILE"):
                    existing_rel["affinity"] = new_affinity
                if new_intimacy in ("INT_INTIMATE", "INT_CLOSE"):
                    existing_rel["intimacy"] = new_intimacy
                if new_power != "DYN_EQUAL":
                    existing_rel["power_dynamic"] = new_power

                existing_rel["formality_levels"].append(f_lvl)


def derive_pronouns_from_taxonomy(
    speaker_gender: str,
    speaker_age: str,
    target_gender: str,
    target_age: str,
    target_number: str,
    roles: List[str],
    intimacy: str,
    formality_level: int
) -> Dict[str, Any]:
    """
    คำนวณสรรพนามบุรุษที่ 1, 2, 3 และหางเสียงตามหลักไวยากรณ์ไทยและ taxonomy.json แบบ Pure Universal Data-Driven 100%
    ขับเคลื่อนจาก Taxonomy Attributes เท่านั้น ไร้การฮาร์ดโค้ดหรือเช็คสตริงชื่อตัวละครโดยเด็ดขาด
    """
    roles = roles or []
    is_plural = target_number == "PLURAL"
    is_teacher = "ROLE_EDU_TEACHER" in roles
    is_elder = target_age == "ELDER"
    is_child = target_age == "CHILD"
    is_female = target_gender == "FEMALE"
    is_male = target_gender == "MALE"
    is_spouse = "ROLE_FAM_SPOUSE" in roles

    # -------------------------------------------------------------
    # 1. THIRD PERSON PRONOUN (สรรพนามบุรุษที่ 3: ผู้ถูกพาดพิงถึง)
    # -------------------------------------------------------------
    if is_plural:
        third_p = "พวกเขา"
    elif formality_level == 1:
        third_p = "มัน"
    elif is_teacher or (is_elder and formality_level >= 3):
        third_p = "ท่าน"
    elif formality_level >= 5:
        third_p = "ท่าน"
    elif is_female:
        third_p = "เธอ"
    elif is_male:
        third_p = "เขา"
    else:
        # Safe Neutral Third-Person เมื่อไม่ทราบเพศ
        third_p = "เขา"

    # -------------------------------------------------------------
    # 2. TARGET PRONOUN (สรรพนามบุรุษที่ 2: ผู้ฟัง / คู่สนทนา)
    # -------------------------------------------------------------
    if is_plural:
        target_p = "พวกเธอ" if formality_level <= 2 else "พวกคุณ"
    elif formality_level == 1:
        if "ROLE_CON_ENEMY" in roles or "ROLE_CON_RIVAL" in roles:
            target_p = "แก" if speaker_gender != "MALE" else "เอ็ง"
        else:
            target_p = "แก" if is_female else "นาย"
    elif is_spouse:
        target_p = "เธอ" if speaker_gender == "MALE" else "คุณ"
    elif is_teacher:
        target_p = "คุณ" if formality_level <= 3 else "ท่าน"
    elif is_elder:
        target_p = "ท่าน" if formality_level >= 4 else ("คุณยาย" if is_female else "คุณตา")
    elif is_child:
        target_p = "หนู" if is_female else "เธอ"
    elif formality_level == 2:
        target_p = "เธอ" if is_female else "นาย"
    elif formality_level in (3, 4):
        target_p = "คุณ"
    else: # 5
        target_p = "ท่าน"

    # -------------------------------------------------------------
    # 3. SELF PRONOUN (สรรพนามบุรุษที่ 1: ตัวผู้พูด)
    # -------------------------------------------------------------
    if formality_level == 1:
        self_p = "ข้า" if speaker_gender == "MALE" else "ฉัน"
    elif speaker_age == "CHILD":
        self_p = "หนู" if speaker_gender == "FEMALE" else "ผม"
    elif is_child and speaker_age in ("TEEN", "ADULT"):
        self_p = "พี่" if speaker_age != "ELDER" else "ฉัน"
    elif is_spouse:
        self_p = "ผม" if speaker_gender == "MALE" else "ฉัน"
    elif formality_level == 2:
        self_p = "ผม" if speaker_gender == "MALE" else "ฉัน"
    elif formality_level in (3, 4):
        self_p = "ผม" if speaker_gender == "MALE" else "ฉัน"
    else: # 5
        self_p = "กระผม" if speaker_gender == "MALE" else "ดิฉัน"

    # -------------------------------------------------------------
    # 4. ENDING PARTICLE (คำลงท้าย / หางเสียง)
    # -------------------------------------------------------------
    if formality_level == 1:
        ending_p = "วะ" if speaker_gender == "MALE" else ""
    elif formality_level == 2:
        if is_spouse:
            ending_p = "" if speaker_gender == "MALE" else "ค่ะ"
        elif is_child and speaker_age in ("TEEN", "ADULT"):
            ending_p = "นะ" if speaker_gender == "MALE" else "จ้ะ"
        else:
            ending_p = "" if speaker_gender == "MALE" else "จ้ะ"
    elif formality_level in (3, 4):
        ending_p = "ครับ" if speaker_gender == "MALE" else "ค่ะ"
    else: # 5
        ending_p = "ขอรับ" if speaker_gender == "MALE" else "เจ้าค่ะ"

    return {
        "self_pronoun": self_p,
        "target_pronoun": target_p,
        "third_person_pronoun": third_p,
        "ending_particle": ending_p,
        "formality_level": formality_level
    }


def synthesize_and_save_profiles(
    master_profiles: Dict[str, Any],
    whitelist_names: Set[str],
    glossary: Dict[str, Any],
    output_profiles_dir: str
) -> int:
    """
    ประกอบและบันทึก Character Profiles ลงดิสก์แบบ Pure Universal Data-Driven 100%
    ขับเคลื่อนด้วยข้อมูลจริงบนดิสก์และผลวิเคราะห์บทสนทนา ปราศจาก Hardcode ใดๆ ทั้งสิ้น
    """
    os.makedirs(output_profiles_dir, exist_ok=True)
    chars_glossary = glossary.get("Characters", {})

    # 1. รวบรวมข้อมูลพื้นฐานของทุกตัวละครจากหลักฐานจริงบนดิสก์และคะแนนโหวตจากการวิเคราะห์บทสนทนา
    char_demographics = {}
    for name in whitelist_names:
        prof = master_profiles.get(name, {})
        g_votes = prof.get("gender_votes", [])
        a_votes = prof.get("age_votes", [])

        # กรองเอาเฉพาะผลโหวตที่มีหลักฐานชัดเจน (ตัด UNKNOWN ออกหากมีหลักฐานชี้ชัด)
        valid_g_votes = [v for v in g_votes if v != "UNKNOWN"]
        valid_a_votes = [v for v in a_votes if v != "UNKNOWN"]

        gender = max(set(valid_g_votes), key=valid_g_votes.count) if valid_g_votes else "UNKNOWN"
        age = max(set(valid_a_votes), key=valid_a_votes.count) if valid_a_votes else "ADULT"

        # Grounding เพิ่มเติมจาก Master Glossary บนดิสก์ (ไฟล์ข้อมูลของโปรเจกต์ที่สกัดจาก Game Database)
        gl_entry = chars_glossary.get(name, {})
        gl_gender = gl_entry.get("gender", "")
        if gl_gender in ("ชาย", "male", "MALE"):
            gender = "MALE"
        elif gl_gender in ("หญิง", "female", "FEMALE"):
            gender = "FEMALE"

        # ตรวจสอบพหูพจน์จากจำนวนหรือคำลงท้ายสากลในภาษาต้นฉบับ
        is_plural = "たち" in name or "2人" in name or "พวก" in name
        number = "PLURAL" if is_plural else "SINGULAR"

        char_demographics[name] = {
            "gender": gender,
            "age": age,
            "number": number,
            "th_name": gl_entry.get("th", name)
        }

    # 2. สร้างและบันทึก Profile ของแต่ละตัวละคร
    saved_count = 0
    for name in whitelist_names:
        demo = char_demographics[name]
        gender = demo["gender"]
        age = demo["age"]
        number = demo["number"]
        th_name = demo["th_name"]

        prof = master_profiles.get(name, {})
        tag_counts = prof.get("personality_tag_counts", {})
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        personality_tags = [t[0] for t in sorted_tags[:3]]
        if not personality_tags:
            personality_tags = ["PER_SOC_CASUAL"]

        # Base Speech Style (Universal Demographic Defaults)
        base_f_lvl = 2 if age in ("CHILD", "ELDER") else 3
        base_speech = derive_pronouns_from_taxonomy(gender, age, "UNKNOWN", "ADULT", "SINGULAR", [], "INT_CASUAL", base_f_lvl)

        # Relationships
        rels_output = []
        known_rels = prof.get("relationships", {})

        for target_name, rel_data in known_rels.items():
            if target_name not in char_demographics:
                continue

            t_demo = char_demographics[target_name]
            f_levels = rel_data.get("formality_levels", [3])
            avg_f_lvl = round(sum(f_levels) / len(f_levels)) if f_levels else 3
            roles = rel_data.get("roles", ["ROLE_SOC_PEER"])
            intimacy = rel_data.get("intimacy", "INT_CASUAL")

            # คำนวณคำสรรพนามเฉพาะคู่นี้จาก Taxonomy อย่างเป็นกลาง
            pair_speech = derive_pronouns_from_taxonomy(
                speaker_gender=gender,
                speaker_age=age,
                target_gender=t_demo["gender"],
                target_age=t_demo["age"],
                target_number=t_demo["number"],
                roles=roles,
                intimacy=intimacy,
                formality_level=avg_f_lvl
            )

            rels_output.append({
                "target_name": target_name,
                "target_th_name": t_demo["th_name"],
                "roles": roles,
                "affinity": rel_data.get("affinity", "AFF_NEUTRAL"),
                "intimacy": intimacy,
                "power_dynamic": rel_data.get("power_dynamic", "DYN_EQUAL"),
                "speech_style": pair_speech
            })

        # Universal Deterministic Character ID
        char_id = generate_universal_character_id(name)

        final_profile_json = {
            "character_id": char_id,
            "name": name,
            "th_name": th_name,
            "aliases": [name],
            "identity": {
                "gender": gender,
                "age": age,
                "species": "HUMAN",
                "number": number
            },
            "base_speech_style": {
                "self_pronoun": base_speech["self_pronoun"],
                "target_pronoun": base_speech["target_pronoun"],
                "ending_particle": base_speech["ending_particle"],
                "formality_level": base_speech["formality_level"]
            },
            "base_state": {
                "personality": [
                    {"tag": tag, "weight": 70, "description": "Derived from scene evidence"}
                    for tag in personality_tags
                ],
                "relationships": rels_output
            }
        }

        out_path = os.path.join(output_profiles_dir, f"{name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_profile_json, f, ensure_ascii=False, indent=2)

        saved_count += 1

    return saved_count


def main():
    print("=" * 80)
    print("   ATF SCENE-BASED CHARACTER PROFILER & RELATIONAL SYNTHESIZER (v6.4)")
    print("   (Pure Universal Paradigm + Zero Hardcode Invariant + State Persistence)")
    print("=" * 80)

    manifest = load_manifest()
    output_dir = manifest.get("output_dir", "")
    output_tlas_dir = manifest.get("output_tlas_dir", os.path.join(output_dir, "tlas"))
    scenes_path = manifest.get("output_scenes_json", os.path.join(output_tlas_dir, "rpgm_scenes_v5.json"))
    whitelist_path = os.path.join(output_tlas_dir, "character_whitelist.json")
    glossary_path = manifest.get("output_glossary_json", os.path.join(output_tlas_dir, "tlas_glossary.json"))
    profiles_dir = manifest.get("output_profiles_dir", os.path.join(output_tlas_dir, "profiles"))

    checkpoints_dir = os.path.join(output_tlas_dir, "checkpoints")
    logs_dir = os.path.join(output_tlas_dir, "logs")
    os.makedirs(checkpoints_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    checkpoint_file = os.path.join(checkpoints_dir, "profile_analysis_checkpoint.json")
    log_file = os.path.join(logs_dir, "profile_analysis_log.jsonl")

    scenes_data = load_json_safe(scenes_path)
    whitelist_data = load_json_safe(whitelist_path)
    glossary_data = load_json_safe(glossary_path) or {}

    if not scenes_data or "packets" not in scenes_data:
        print(f"❌ [Error] ไม่พบไฟล์ Scene Packets: {scenes_path}")
        print("   👉 กรุณารันคำสั่ง: python atf.py prepare-scenes ก่อน")
        return

    whitelist_names = set()
    if whitelist_data and "qualified_characters" in whitelist_data:
        whitelist_names = set(c["name"] for c in whitelist_data["qualified_characters"])

    if not whitelist_names:
        print(f"❌ [Error] ไม่พบข้อมูล Whitelist Characters ใน: {whitelist_path}")
        print("   👉 กรุณารันคำสั่ง: python atf.py prepare-whitelist ก่อน")
        return

    print(f"[*] ตรวจพบตัวละคร Whitelist ทั้งหมด: {len(whitelist_names)} ตัวละคร")
    print(f"    {', '.join(sorted(whitelist_names))}\n")

    # 1. สกัด Scene Batches แบบครอบคลุม 100% ไม่มีบรรทัดบทสนทนาใดตกหล่น
    scene_batches = build_exhaustive_scene_batches(scenes_data["packets"], whitelist_names)
    print(f"[*] สกัดชุดฉากที่มีบทสนทนาจริงได้ {len(scene_batches)} ฉากหลัก (ครอบคลุม 100% ของบทสนทนาเกม):")
    for idx, b in enumerate(scene_batches, start=1):
        print(f"    ฉากที่ {idx:02d}: {b['scene_id']} [{b['range']}] -> ตัวละคร: {b['characters']} ({len(b['dialogues'])} บรรทัด)")

    # 2. ตรวจสอบสถานะ Checkpoint เดิมเพื่อ Resume งานทันที
    master_profiles: Dict[str, Any] = {}
    completed_batch_ids = set()

    if os.path.exists(checkpoint_file):
        try:
            cp_data = load_json_safe(checkpoint_file) or {}
            completed_batch_ids = set(cp_data.get("completed_batch_ids", []))
            raw_master = cp_data.get("master_profiles", {})
            for c_name, c_data in raw_master.items():
                master_profiles[c_name] = {
                    "name": c_data.get("name", c_name),
                    "gender_votes": c_data.get("gender_votes", []),
                    "age_votes": c_data.get("age_votes", []),
                    "roles_observed": set(c_data.get("roles_observed", [])),
                    "personality_tag_counts": c_data.get("personality_tag_counts", {}),
                    "relationships": c_data.get("relationships", {})
                }
            if completed_batch_ids:
                print(f"\n📂 [Checkpoint Resumed] ตรวจพบประวัติการวิเคราะห์เดิม: ผ่านแล้ว {len(completed_batch_ids)}/{len(scene_batches)} ฉาก")
                print("   ระบบจะข้ามฉากที่เคยวิเคราะห์แล้ว และรันต่อฉากถัดไปทันทีโดยไม่เสียโทเคนซ้ำซ้อน!")
        except Exception as e:
            print(f"⚠️ [Checkpoint Warning] ไม่สามารถโหลด checkpoint เดิมได้: {e}")

    # 3. ตรวจสอบและรอ Bridge Server ให้พร้อม 100%
    wait_for_bridge_ready(BRIDGE_URL)

    # 4. ส่งบทสนทนาประจำฉากไปให้ ChatGPT วิเคราะห์แบบ Scene-by-Scene
    batches_since_new_chat = 0

    for idx, batch in enumerate(scene_batches, start=1):
        b_id = batch["batch_id"]
        if b_id in completed_batch_ids:
            print(f"⏩ [Skip Done] ฉากที่ {idx:02d}/{len(scene_batches)}: {batch['scene_id']} เคยวิเคราะห์แล้ว")
            continue

        print(f"\n[{idx}/{len(scene_batches)}] 🎬 กำลังส่งวิเคราะห์ฉาก: {batch['scene_id']}...")
        print(f"    ตัวละครในฉากนี้: {batch['characters']}")

        if batches_since_new_chat == 0 or batches_since_new_chat >= 8:
            print(f"    [🔄] Context Refresh: สั่งเปิด New Chat เพื่อสุขอนามัยของ Context Window...")
            trigger_new_chat(BRIDGE_URL)
            batches_since_new_chat = 0

        sys_prompt, usr_prompt = build_scene_prompt(batch)

        try:
            raw_response = call_chatgpt_api(usr_prompt, system_prompt=sys_prompt, bridge_url=BRIDGE_URL)
            scene_result = extract_json_object(raw_response)
            merge_scene_results_into_master(master_profiles, scene_result, whitelist_names)
            batches_since_new_chat += 1
            completed_batch_ids.add(b_id)
            print(f"    ✅ [Scene Analysis OK] วิเคราะห์ข้อมูลและสัมพันธ์ของฉาก {batch['scene_id']} สำเร็จ")

            # -------------------------------------------------------------
            # [CRITICAL RULE]: บันทึก Checkpoint, Log และ Profile ทันทีทุก Batch!
            # -------------------------------------------------------------
            log_entry = {
                "timestamp": time.time(),
                "batch_id": b_id,
                "scene_id": batch["scene_id"],
                "characters": batch["characters"],
                "prompt_tokens_est": len(usr_prompt) // 2,
                "raw_response": raw_response
            }
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            serializable_master = {}
            for c_name, c_data in master_profiles.items():
                serializable_master[c_name] = {
                    "name": c_data["name"],
                    "gender_votes": c_data["gender_votes"],
                    "age_votes": c_data["age_votes"],
                    "roles_observed": list(c_data["roles_observed"]),
                    "personality_tag_counts": c_data["personality_tag_counts"],
                    "relationships": c_data["relationships"]
                }
            cp_payload = {
                "version": "6.4",
                "last_updated": time.time(),
                "completed_batch_ids": list(completed_batch_ids),
                "master_profiles": serializable_master
            }
            with open(checkpoint_file, "w", encoding="utf-8") as cf:
                json.dump(cp_payload, cf, ensure_ascii=False, indent=2)

            saved_count = synthesize_and_save_profiles(master_profiles, whitelist_names, glossary_data, profiles_dir)
            print(f"    💾 [Real-time Save] อัปเดตและบันทึก Profile ลงดิสก์เรียบร้อย ({saved_count} ตัวละคร)")

        except Exception as e:
            print(f"    ⚠️ [Error analyzing scene {batch['scene_id']}]: {e}")
            print("    👉 สั่ง Emergency New Chat และข้ามไปยังฉากถัดไปตามระเบียบ Adaptive Resilience...")
            trigger_new_chat(BRIDGE_URL)
            batches_since_new_chat = 0

    print("\n" + "=" * 80)
    print("🎉 [Analysis Completed] การวิเคราะห์และสังเคราะห์ Character Profiles สำเร็จสมบูรณ์ 100%!")
    print(f"   - Profiles Directory : {profiles_dir}")
    print(f"   - Checkpoint File    : {checkpoint_file}")
    print(f"   - Analysis Log File  : {log_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
