#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Scene-Based Character Profile & Relational Synthesizer (v6.1)
================================================================
สกัดและวิเคราะห์ Character Profiles & Pairwise Relationships ของตัวละคร Whitelist
โดยส่งบทสนทนาจริงเป็นชุดฉาก (Scene-Based Batches) ไปให้ LLM (ChatGPT Web Bridge พอร์ต 8765)
เพื่อวิเคราะห์อัตลักษณ์ (Identity), บุคลิกภาพ (Personality), และความสัมพันธ์ (Relationships)
พร้อมระบบ Deterministic Python Pronoun Engine ที่แมปปิ้งคำสรรพนามจาก taxonomy.json โดยตรง 100%

สถาปัตยกรรมหลัก:
1. Scene-Based Batching: ส่งบทสนทนาต่อเนื่องในแต่ละฉาก ให้ AI เห็น Interaction และปฏิกิริยาโต้ตอบระหว่างตัวละครพร้อมกัน
2. Clean Prompt Payload: ไม่ส่งชื่อไทยทางการไปรบกวน AI และไม่ให้ AI คิดคำสรรพนามภาษาไทยเอง ป้องกันคำนามปลอม (เช่น "สามี") หลุดเข้ามาเป็นสรรพนาม
3. Clear Formality Scale (1-5): กำหนดเกณฑ์ระดับภาษา 1-5 แบบ Deterministic ชัดเจน
4. Python Pronoun Mapping: คำนวณสรรพนามบุรุษที่ 1, 2, 3 (self, target, third_person, ending) จาก taxonomy.json 100%
5. Glossary Grounding: ดึง th_name และ verified gender จาก tlas_glossary.json มาประกอบในขั้นตอนสุดท้าย
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
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
    """ส่งคำขอไปยัง ChatGPT ผ่าน OpenAI-compatible endpoint (/v1/chat/completions) บน Port 8765"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": "chatgpt-web",
        "messages": messages
    }).encode("utf-8")

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
            if e.code == 429:
                print(f"⚠️ [ChatGPT Cooldown / Rate Limit] ({err_body})")
                print("   ระบบจะรอ 60 วินาทีก่อนลองส่งใหม่ตามระเบียบ Adaptive Resilience...")
                time.sleep(60)
                continue
            raise RuntimeError(f"Bridge HTTP Error ({e.code}): {err_body}")
        except Exception as ex:
            print(f"⚠️ [Bridge Communication Error]: {ex}. กำลังรอ 5 วินาทีก่อนลองใหม่...")
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


def select_scene_interaction_batches(scene_packets: List[Dict[str, Any]], whitelist_names: Set[str], max_batches: int = 7) -> List[Dict[str, Any]]:
    """
    คัดเลือก Scene Packets ที่ครอบคลุมตัวละคร Whitelist ทั้งหมดและมีปฏิสัมพันธ์ที่เข้มข้นที่สุด
    """
    candidate_scenes = []
    covered_characters = set()

    # วิเคราะห์แต่ละฉากเพื่อดูว่ามีตัวละคร Whitelist กี่ตัวและมีบทสนทนาอะไรบ้าง
    for pkt in scene_packets:
        pid = pkt.get("packet_id", "")
        fn = pkt.get("filename", "")
        dlgs = pkt.get("dialogues", [])
        if not dlgs:
            continue

        spks_in_scene = set()
        formatted_dialogues = []

        for d in dlgs:
            spk = d.get("speaker", "")
            raw = d.get("clean_text") or d.get("raw_text", "")
            clean_t = re.sub(r'^[【\[][^】\]]+[】\]]\s*', '', raw).strip()
            if not clean_t:
                continue

            # ตรวจจับชื่อผู้พูดจริง
            actual_spk = spk
            if actual_spk in ("Untagged", "", "None"):
                for w in whitelist_names:
                    if f"【{w}】" in raw or f"[{w}]" in raw:
                        actual_spk = w
                        break

            if actual_spk in whitelist_names:
                spks_in_scene.add(actual_spk)

            formatted_dialogues.append(f"[{actual_spk}]: {clean_t}")

        if spks_in_scene:
            candidate_scenes.append({
                "packet_id": pid,
                "filename": fn,
                "characters": sorted(list(spks_in_scene)),
                "dialogues": formatted_dialogues,
                "score": len(spks_in_scene) * 100 + min(len(formatted_dialogues), 80)
            })

    # เรียงลำดับฉากตามความเข้มข้นของตัวละคร Whitelist
    candidate_scenes.sort(key=lambda s: s["score"], reverse=True)

    selected_batches = []
    # 1. Greedy selection เพื่อให้ครอบคลุมตัวละคร Whitelist ทุกตัว
    for sc in candidate_scenes:
        chars = set(sc["characters"])
        new_chars = chars - covered_characters
        if new_chars or len(selected_batches) < max_batches:
            # จำกัดความยาวบทสนทนาในฉากไม่ให้ยาวเกินไป (ไม่เกิน 45 บรรทัดที่กระชับ)
            sample_dlgs = sc["dialogues"][:45]
            selected_batches.append({
                "scene_id": f"{sc['packet_id']} ({sc['filename']})",
                "characters": sc["characters"],
                "dialogues": sample_dlgs
            })
            covered_characters.update(chars)
            if len(covered_characters) == len(whitelist_names) and len(selected_batches) >= 5:
                break

    return selected_batches


def build_scene_prompt(batch: Dict[str, Any]) -> Tuple[str, str]:
    """สร้าง System Prompt และ User Prompt สำหรับวิเคราะห์บทสนทนาประจำฉาก"""
    scene_id = batch["scene_id"]
    chars = batch["characters"]
    chars_str = ", ".join([f'"{c}"' for c in chars])
    dlgs_str = "\n".join(batch["dialogues"])

    system_prompt = """You are a video game narrative analyst, character profiler, and Japanese dialogue linguist.
Your mission is to analyze the in-game dialogue of a specific game scene to extract identity, personality, and interpersonal relationships for the target characters present.

CRITICAL INVARIANTS:
1. Grounded In Scene Evidence: Extract traits and dynamics strictly from how these characters speak and interact in the provided dialogue.
2. Target Focus Only: Profile ONLY the target characters listed. Do NOT invent characters.
3. Zero Thai Pronoun Hallucination: Do NOT generate Thai pronoun words (no "ฉัน", "ผม", "สามี", "นาย", etc.). The Thai pronouns will be synthesized by the downstream rule engine. Output only structural metadata.
4. Strict Formality Scale (1-5):
   - Level 1: Intimate / Vulgar / Delinquent / Slang (close friends, delinquents, enemies, no polite particles)
   - Level 2: Casual / Informal / Familiar (husband-wife, family members, classmates, gentle casual tone)
   - Level 3: Neutral / Everyday Standard (polite acquaintances, coworkers, friendly strangers)
   - Level 4: Formal / Respectful / Hierarchical (teacher-student, elder respect, client, workplace hierarchy)
   - Level 5: Honorific / Ceremonial / Ultra-Formal (royal, noble, feudal master-servant, ceremonial)
5. Output ONLY a single parseable JSON object matching the requested schema. No conversational preamble."""

    user_prompt = f"""### SCENE CONTEXT:
Scene ID: {scene_id}
Target Characters Present in This Scene: [{chars_str}]

### SCENE IN-GAME DIALOGUE:
{dlgs_str}

### INSTRUCTIONS:
Analyze the target characters present in this scene and output a JSON object adhering to this exact schema:

{{
  "characters": {{
    "CHARACTER_JAPANESE_NAME": {{
      "identity": {{
        "gender": "MALE" | "FEMALE" | "NON_BINARY" | "UNKNOWN",
        "age": "CHILD" | "TEEN" | "ADULT" | "ELDER" | "UNKNOWN",
        "species": "HUMAN",
        "social_role": "brief description (e.g. husband, wife, teacher, acquaintance, child)"
      }},
      "personality_tags": [
        "PER_SOC_CASUAL", "PER_SOC_POLITE", "PER_SOC_RUDE", "PER_VIBE_CHEERFUL", "PER_VIBE_SERIOUS", "PER_SOC_PLAYFUL" (pick 2-3 matching tags)
      ],
      "relationships": [
        {{
          "target_name": "Exact Japanese name of another target character present in this scene",
          "roles": ["ROLE_FAM_SPOUSE" | "ROLE_FAM_PARENT" | "ROLE_FAM_CHILD" | "ROLE_SOC_FRIEND" | "ROLE_SOC_ACQUAINTANCE" | "ROLE_SOC_PEER" | "ROLE_EDU_TEACHER" | "ROLE_SOC_NEIGHBOR"],
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
    """ผสานข้อมูลที่ได้จากการวิเคราะห์ฉากเข้าสู่ Master Database ของตัวละคร"""
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
                "personality_tags": set(),
                "relationships": {}
            }

        prof = master_profiles[c_name]
        ident = c_info.get("identity", {})
        g = ident.get("gender", "").upper()
        if g in ("MALE", "FEMALE", "NON_BINARY"):
            prof["gender_votes"].append(g)

        a = ident.get("age", "").upper()
        if a in ("CHILD", "TEEN", "ADULT", "ELDER"):
            prof["age_votes"].append(a)

        s_role = ident.get("social_role", "")
        if s_role:
            prof["roles_observed"].add(s_role)

        for p_tag in c_info.get("personality_tags", []):
            if isinstance(p_tag, str) and p_tag.startswith("PER_"):
                prof["personality_tags"].add(p_tag)

        # จัดการความสัมพันธ์ (Relationships)
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

            prof["relationships"][t_name] = {
                "target_name": t_name,
                "roles": rel.get("roles", ["ROLE_SOC_PEER"]),
                "affinity": rel.get("affinity", "AFF_NEUTRAL"),
                "intimacy": rel.get("intimacy", "INT_CASUAL"),
                "power_dynamic": rel.get("power_dynamic", "DYN_EQUAL"),
                "formality_level": f_lvl
            }


def derive_pronouns_from_taxonomy(
    speaker_gender: str,
    speaker_age: str,
    target_gender: str,
    target_age: str,
    roles: List[str],
    intimacy: str,
    formality_level: int,
    target_name: str = ""
) -> Dict[str, Any]:
    """
    คำนวณสรรพนามบุรุษที่ 1, 2, 3 และหางเสียงตามหลักไวยากรณ์ไทยและ taxonomy.json แบบ Deterministic 100%
    ไม่มีคำนามอื่นอย่าง 'สามี' หรือ 'ภรรยา' หลุดเข้ามาในช่องสรรพนามเด็ดขาด
    """
    roles = roles or []
    is_plural = "たち" in target_name or "2人" in target_name or "พวก" in target_name

    self_p = "ฉัน"
    target_p = "คุณ"
    third_p = "เขา"
    ending_p = ""

    if formality_level == 1:
        # Intimate / Vulgar / Slang
        if "ROLE_CON_ENEMY" in roles or "ROLE_CON_RIVAL" in roles:
            self_p = "ข้า" if speaker_gender == "MALE" else "ฉัน"
            target_p = "แก" if speaker_gender != "MALE" else "เอ็ง"
            third_p = "มัน"
            ending_p = "วะ"
        else:
            self_p = "เรา" if speaker_gender == "MALE" else "ฉัน"
            target_p = "แก" if target_gender == "FEMALE" else "นาย"
            third_p = "มัน"
            ending_p = ""

    elif formality_level == 2:
        # Casual / Familiar / Spouse / Family
        if "ROLE_FAM_SPOUSE" in roles:
            if speaker_gender == "MALE":
                self_p = "ผม"
                target_p = "เธอ"
                third_p = "เขา"
                ending_p = ""
            else:
                self_p = "ฉัน"
                target_p = "คุณ"
                third_p = "เขา"
                ending_p = "ค่ะ"
        elif speaker_age == "CHILD":
            self_p = "หนู" if speaker_gender == "FEMALE" else "ผม"
            target_p = "พี่" if target_age in ("TEEN", "ADULT") else "เธอ"
            third_p = "เขา"
            ending_p = "ค่ะ" if speaker_gender == "FEMALE" else "ครับ"
        else:
            if speaker_gender == "MALE":
                self_p = "ผม"
                target_p = "เธอ" if target_gender == "FEMALE" else "นาย"
                third_p = "เขา"
                ending_p = ""
            else:
                self_p = "ฉัน"
                target_p = "เธอ" if target_gender == "FEMALE" else "นาย"
                third_p = "เขา"
                ending_p = "จ้ะ"

    elif formality_level == 3:
        # Neutral Polite
        if speaker_gender == "MALE":
            self_p = "ผม"
            target_p = "คุณ"
            third_p = "เขา"
            ending_p = "ครับ"
        else:
            self_p = "ฉัน"
            target_p = "คุณ"
            third_p = "เขา"
            ending_p = "ค่ะ"

    elif formality_level == 4:
        # Formal / Respectful / Hierarchy / Teacher / Elder
        if "ROLE_EDU_TEACHER" in roles or "先生" in target_name:
            self_p = "ผม" if speaker_gender == "MALE" else "ฉัน"
            target_p = "คุณ"
            third_p = "ท่าน"
            ending_p = "ครับ" if speaker_gender == "MALE" else "ค่ะ"
        elif "受付のおばあさん" in target_name or target_age == "ELDER":
            self_p = "ผม" if speaker_gender == "MALE" else "ฉัน"
            target_p = "คุณยาย" if "おばあさん" in target_name else "คุณ"
            third_p = "ท่าน"
            ending_p = "ครับ" if speaker_gender == "MALE" else "ค่ะ"
        else:
            self_p = "ผม" if speaker_gender == "MALE" else "ดิฉัน"
            target_p = "คุณ"
            third_p = "เขา"
            ending_p = "ครับ" if speaker_gender == "MALE" else "ค่ะ"

    elif formality_level == 5:
        # Honorific / Ultra-Formal
        self_p = "กระผม" if speaker_gender == "MALE" else "ดิฉัน"
        target_p = "ท่าน"
        third_p = "ท่าน"
        ending_p = "ขอรับ" if speaker_gender == "MALE" else "เจ้าค่ะ"

    if is_plural:
        third_p = "พวกเขา"

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
):
    """ประกอบ Profile ขั้นสุดท้ายพร้อมแมปปิ้งสรรพนามและบันทึกไฟล์ JSON"""
    os.makedirs(output_profiles_dir, exist_ok=True)
    chars_glossary = glossary.get("Characters", {})

    # 1. รวบรวมข้อมูลพื้นฐานของทุกตัวละครเพื่อใช้เป็นตารางอ้างอิงข้ามบุคคล
    char_demographics = {}
    for name in whitelist_names:
        prof = master_profiles.get(name, {})
        g_votes = prof.get("gender_votes", [])
        a_votes = prof.get("age_votes", [])

        # มติเสียงส่วนมากสำหรับเพศและวัย
        gender = max(set(g_votes), key=g_votes.count) if g_votes else "UNKNOWN"
        age = max(set(a_votes), key=a_votes.count) if a_votes else "ADULT"

        # Grounding เพิ่มเติมจาก Glossary ถ้ามีระบุไว้
        gl_entry = chars_glossary.get(name, {})
        gl_gender = gl_entry.get("gender", "")
        if gl_gender == "ชาย":
            gender = "MALE"
        elif gl_gender == "หญิง":
            gender = "FEMALE"

        if "子供" in name or "小学生" in name:
            age = "CHILD"
        elif "おばあさん" in name:
            age = "ELDER"

        char_demographics[name] = {
            "gender": gender,
            "age": age,
            "th_name": gl_entry.get("th", name)
        }

    # 2. สร้างและบันทึก Profile ของแต่ละตัวละคร
    saved_count = 0
    for name in whitelist_names:
        demo = char_demographics[name]
        gender = demo["gender"]
        age = demo["age"]
        th_name = demo["th_name"]

        prof = master_profiles.get(name, {})
        personality_tags = list(prof.get("personality_tags", []))
        if not personality_tags:
            personality_tags = ["PER_SOC_CASUAL"]

        # Base Speech Style
        base_f_lvl = 2 if age in ("CHILD", "ELDER") else 3
        base_speech = derive_pronouns_from_taxonomy(gender, age, "UNKNOWN", "ADULT", [], "INT_CASUAL", base_f_lvl, "")

        # Relationships
        rels_output = []
        known_rels = prof.get("relationships", {})

        for target_name, rel_data in known_rels.items():
            if target_name not in char_demographics:
                continue

            t_demo = char_demographics[target_name]
            f_lvl = rel_data.get("formality_level", 3)
            roles = rel_data.get("roles", ["ROLE_SOC_PEER"])
            intimacy = rel_data.get("intimacy", "INT_CASUAL")

            # คำนวณคำสรรพนามเฉพาะคู่นี้จาก Taxonomy
            pair_speech = derive_pronouns_from_taxonomy(
                speaker_gender=gender,
                speaker_age=age,
                target_gender=t_demo["gender"],
                target_age=t_demo["age"],
                roles=roles,
                intimacy=intimacy,
                formality_level=f_lvl,
                target_name=target_name
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

        # โครงสร้าง Profile JSON ตามมาตรฐาน ATF V4/V5
        final_profile_json = {
            "character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', name).upper() or 'UNKNOWN'}",
            "name": name,
            "th_name": th_name,
            "aliases": [name],
            "identity": {
                "gender": gender,
                "age": age,
                "species": "HUMAN",
                "number": "PLURAL" if ("たち" in name or "2人" in name) else "SINGULAR"
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
                    for tag in personality_tags[:3]
                ],
                "relationships": rels_output
            }
        }

        out_path = os.path.join(output_profiles_dir, f"{name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_profile_json, f, ensure_ascii=False, indent=2)

        print(f"  ✅ [Profile Saved] {name} (ไทย: {th_name}) -> เพศ: {gender}, วัย: {age}, สัมพันธ์กับ: {len(rels_output)} ตัวละคร")
        saved_count += 1

    print(f"\n🎉 บันทึก Character Profiles ทั้งหมดเรียบร้อยแล้ว: {saved_count} ตัวละคร ใน {output_profiles_dir}")


def main():
    print("=" * 80)
    print("   ATF SCENE-BASED CHARACTER PROFILER & RELATIONAL SYNTHESIZER (v6.1)")
    print("   (Universal Scene Batching + Deterministic Python Pronoun Engine)")
    print("=" * 80)

    manifest = load_manifest()
    output_dir = manifest.get("output_dir", "")
    output_tlas_dir = manifest.get("output_tlas_dir", os.path.join(output_dir, "tlas"))
    scenes_path = manifest.get("output_scenes_json", os.path.join(output_tlas_dir, "rpgm_scenes_v5.json"))
    whitelist_path = os.path.join(output_tlas_dir, "character_whitelist.json")
    glossary_path = manifest.get("output_glossary_json", os.path.join(output_tlas_dir, "tlas_glossary.json"))
    profiles_dir = manifest.get("output_profiles_dir", os.path.join(output_tlas_dir, "profiles"))

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

    # 1. คัดเลือก Scene Batches ที่ครอบคลุมตัวละคร Whitelist
    scene_batches = select_scene_interaction_batches(scenes_data["packets"], whitelist_names)
    print(f"[*] สกัดชุดฉากที่มีการสนทนาจริงได้ {len(scene_batches)} ฉากหลัก เพื่อส่งวิเคราะห์:")
    for idx, b in enumerate(scene_batches, start=1):
        print(f"    ฉากที่ {idx}: {b['scene_id']} -> ตัวละคร: {b['characters']} ({len(b['dialogues'])} บรรทัด)")

    # 2. ตรวจสอบและรอ Bridge Server ให้พร้อม 100%
    wait_for_bridge_ready(BRIDGE_URL)

    # 3. ส่งบทสนทนาประจำฉากไปให้ ChatGPT วิเคราะห์แบบ Scene-by-Scene
    master_profiles: Dict[str, Any] = {}

    for idx, batch in enumerate(scene_batches, start=1):
        print(f"\n[{idx}/{len(scene_batches)}] 🎬 กำลังส่งวิเคราะห์ฉาก: {batch['scene_id']}...")
        print(f"    ตัวละครในฉากนี้: {batch['characters']}")

        # เปิด New Chat ล้าง Context ก่อนเริ่มฉากใหม่
        trigger_new_chat(BRIDGE_URL)

        sys_prompt, usr_prompt = build_scene_prompt(batch)

        try:
            raw_response = call_chatgpt_api(usr_prompt, system_prompt=sys_prompt, bridge_url=BRIDGE_URL)
            scene_result = extract_json_object(raw_response)
            merge_scene_results_into_master(master_profiles, scene_result, whitelist_names)
            print(f"    ✅ [Scene Analysis OK] วิเคราะห์ข้อมูลและสัมพันธ์ของฉาก {batch['scene_id']} สำเร็จ")
        except Exception as e:
            print(f"    ⚠️ [Error analyzing scene {batch['scene_id']}]: {e}")
            print("    ระบบจะไปต่อยังฉากถัดไปตามระเบียบ Adaptive Resilience...")

    # 4. สังเคราะห์ผลลัพธ์สุดท้ายด้วย Python และบันทึก Character Profiles
    print("\n" + "=" * 80)
    print("⚙️ [Phase 2] กำลังสังเคราะห์ Character Profiles และแมปปิ้งคำสรรพนามด้วย Python...")
    print("=" * 80)

    synthesize_and_save_profiles(master_profiles, whitelist_names, glossary_data, profiles_dir)


if __name__ == "__main__":
    main()
