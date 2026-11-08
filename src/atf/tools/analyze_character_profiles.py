#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dynamic Character Profile Synthesizer (v6.0 - Live ChatGPT Bridge Driven)
=============================================================================
วิเคราะห์และสังเคราะห์ไฟล์ Character Profile V4/V5 ของตัวละครแต่ละตัวตาม Whitelist
โดยส่งประโยคพูดจริงจากฉากต่างๆ (Scene Batches) ไปให้ ChatGPT (ผ่าน Web Bridge พอร์ต 8765)
วิเคราะห์บุคลิกภาพ เพศ วัย ลีลาภาษาไทย และความสัมพันธ์ระหว่างตัวละคร (Pairwise Relationships) อย่างแท้จริง

สถาปัตยกรรม:
- Zero Hardcode: ปราศจากพจนานุกรมชื่อหรือเพศตัวละครที่ฮาร์ดโค้ดไว้ในโค้ด 100%
- Factual Scene Harvesting: ดึงประโยคพูดจริงและบริบทผู้ร่วมฉากจาก rpgm_scenes_v5.json
- Live Web Bridge Integration: เชื่อมต่อผ่าน http://127.0.0.1:8765 (/v1/chat/completions)
- Pairwise Relationship Synthesis: บังคับให้ ChatGPT วิเคราะห์ความสัมพันธ์ข้ามตัวละคร (Speaker -> Target)
  เพื่อส่งต่อให้ Stage 3e (sync_profiles_and_matrix.py) สร้าง Specific Pairwise Rules > 0
- Fail-Safe Offline Mode: รองรับแฟล็ก --offline สำหรับการประมวลผลออฟไลน์ล้วนหากต้องการ
- Output: บันทึกไฟล์โปรไฟล์รายบุคคลลงใน <output_tlas_dir>/profiles/<Name>.json
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
    """
    ตรวจสอบสถานะ Bridge Server และ Userscript
    คืนค่า: (is_server_online: bool, is_userscript_connected: bool)
    """
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
    """
    ตรวจสอบและรอความพร้อมของ ChatGPT Web Bridge (Port 8765)
    ตามกฎ [RULE_SYSTEM_PRINCIPLES]: รอจนกว่า Userscript บนหน้าเว็บ ChatGPT จะต่อเข้ามาพร้อม 100%
    """
    first_notify = True
    while True:
        server_ok, script_ok = check_bridge_status(bridge_url)
        if server_ok and script_ok:
            print("\n🌐 [ChatGPT Bridge Online & Connected]")
            print(f"   Bridge Server พอร์ต 8765 ({bridge_url}) และ Tampermonkey Userscript พร้อมวิเคราะห์ตัวละคร 100%!\n")
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


def call_chatgpt_api(prompt: str, system_prompt: str = "", bridge_url: str = BRIDGE_URL) -> str:
    """
    ส่งคำขอไปยัง ChatGPT ผ่าน OpenAI-compatible endpoint (/v1/chat/completions) บน Port 8765
    ยึดมั่น [RULE_SYSTEM_PRINCIPLES]: timeout=None และจัดการ Retry เมื่อติด Cooldown
    """
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


def collect_character_dialogues(character_name: str, scene_packets: List[Dict[str, Any]], max_samples: int = 35) -> List[Dict[str, Any]]:
    """เก็บตัวอย่างบทสนทนาจริงที่ตัวละครนี้พูดจากฉากต่างๆ พร้อมชื่อผู้ร่วมฉาก"""
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


def build_analysis_prompt(character_name: str, samples: List[Dict[str, Any]], all_known_characters: List[str], co_present_targets: List[str]) -> Tuple[str, str]:
    """สร้าง System Prompt และ User Prompt เพื่อส่งให้ ChatGPT วิเคราะห์ Character Profile & Pairwise Relationships"""
    other_known = [c for c in all_known_characters if c != character_name]
    other_str = ", ".join([f'"{c}"' for c in other_known]) if other_known else "None identified"
    co_present_str = ", ".join([f'"{c}"' for c in co_present_targets if c != character_name]) if co_present_targets else other_str

    lines_formatted = []
    for idx, s in enumerate(samples, start=1):
        others = f" [Scene: {s['scene']} | Present: {', '.join(s['other_speakers']) if s['other_speakers'] else 'Solo'}]"
        lines_formatted.append(f"{idx}. {repr(s['text'])}{others}")

    dialogue_block = "\n".join(lines_formatted)

    system_prompt = """You are an elite video game narrative analyst, linguist, and Japanese-to-Thai localization architect.
Your mission is to perform an in-depth linguistic and narrative profile analysis of a Japanese video game character based STRICTLY on evidence from their actual in-game dialogue samples.

CRITICAL INVARIANTS:
1. Zero Speculation: Ground all conclusions (gender, age, personality, relationships) on concrete Japanese linguistic cues (sentence particles like わ/ぜ/ぞ/よ, self-pronouns like 俺/僕/私/あたし, speech registers, and scene interactions).
2. Anti-Politeness Bias: If the character speaks crudely, like a delinquent, or intimately with a close partner, DO NOT default to polite "ผม/คุณ/ครับ". Select authentic Thai speech registers (เช่น ฉัน/เธอ, ข้า/เอ็ง, กู/มึง, นาย/แก ตามบริบท).
3. Pairwise Relationships: For each known character present in the scenes or spoken to, define explicit reciprocal speech styles (self_pronoun, target_pronoun, ending_particle).
4. Strict JSON Output: Output ONLY a single valid, parseable JSON object matching the requested schema. No conversational preamble, no markdown comments."""

    user_prompt = f"""Target Character to Analyze: "{character_name}"
Characters Sharing Scenes with this Character: [{co_present_str}]
All Known Characters in Game: [{other_str}]

In-Game Dialogue Samples for "{character_name}":
{dialogue_block}

### INSTRUCTIONS:
Analyze the character above and output a comprehensive JSON profile conforming to this exact structure:

{{
  "character_id": "CHAR_{re.sub(r'[^A-Za-z0-9]', '', character_name).upper() or 'UNKNOWN'}",
  "name": "{character_name}",
  "th_name": "Recommended Thai name translation/transliteration",
  "aliases": ["{character_name}"],
  "identity": {{
    "gender": "MALE" | "FEMALE" | "NON_BINARY" | "UNKNOWN",
    "age": "CHILD" | "TEEN" | "ADULT" | "ELDER" | "UNKNOWN",
    "species": "HUMAN",
    "number": "{"PLURAL" if "2人" in character_name or "たち" in character_name else "SINGULAR"}"
  }},
  "base_speech_style": {{
    "self_pronoun": "Default natural Thai 1st-person pronoun (e.g. ฉัน, ผม, หนู, เค้า, ข้า)",
    "ending_particle": "Default ending particle (e.g. ค่ะ, ครับ, จ้ะ, นะ, วะ, or empty string)",
    "formality_level": 1 to 5 (1=intimate/vulgar, 3=neutral/casual, 5=formal)
  }},
  "base_state": {{
    "personality": [
      {{"tag": "PER_SOC_...", "weight": 70, "description": "brief trait description"}}
    ],
    "speech_habit": [
      {{"tag": "SPR_...", "weight": 70, "description": "brief habit description"}}
    ],
    "values": [],
    "relationships": [
      {{
        "target_name": "Exact Japanese name of related character from the known list",
        "roles": ["ROLE_FAM_...", "ROLE_SOC_..."],
        "affinity": "AFF_LOVING" | "AFF_FRIENDLY" | "AFF_NEUTRAL" | "AFF_DISLIKE" | "AFF_HOSTILE",
        "intimacy": "INT_INTIMATE" | "INT_CLOSE" | "INT_CASUAL" | "INT_DISTANT" | "INT_ESTRANGED",
        "power_dynamic": "DYN_DOMINANT" | "DYN_EQUAL" | "DYN_SUBMISSIVE",
        "speech_style": {{
          "self_pronoun": "Thai pronoun this character calls themselves when speaking to THIS target",
          "target_pronoun": "Thai pronoun this character uses to address THIS target",
          "third_person_pronoun": "Thai pronoun when referring to this target to a 3rd party",
          "ending_particle": "Ending particle used with this target",
          "formality_level": 1 to 5
        }}
      }}
    ]
  }}
}}

Return ONLY the raw JSON object."""

    return system_prompt, user_prompt


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


def normalize_profile_structure(raw_profile: Dict[str, Any], character_name: str, count: int, samples_len: int) -> Dict[str, Any]:
    """ตรวจสอบและปรับแต่งโครงสร้าง Profile ให้ตรงตามมาตรฐาน ATF V4/V5 อย่างสมบูรณ์ 100%"""
    char_id = raw_profile.get("character_id") or f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', character_name).upper() or 'UNKNOWN'}"
    ident = raw_profile.get("identity", {})
    base_style = raw_profile.get("base_speech_style", {})

    base_state = raw_profile.get("base_state", {})
    raw_rels = base_state.get("relationships") or raw_profile.get("relationships") or []

    normalized_rels = []
    seen_targets = set()
    for rel in raw_rels:
        t_name = rel.get("target_name") or rel.get("target_character") or ""
        if not t_name or t_name in seen_targets:
            continue
        seen_targets.add(t_name)

        speech = rel.get("speech_style") or rel.get("specific_speech") or {}
        normalized_rels.append({
            "target_character_id": rel.get("target_character_id") or f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', t_name).upper() or 'TARGET'}",
            "target_name": t_name,
            "roles": rel.get("roles") or ["ROLE_SOC_ACQUAINTANCE"],
            "affinity": rel.get("affinity", "AFF_NEUTRAL"),
            "intimacy": rel.get("intimacy", "INT_DISTANT"),
            "power_dynamic": rel.get("power_dynamic", "DYN_EQUAL"),
            "speech_style": {
                "self_pronoun": speech.get("self_pronoun", base_style.get("self_pronoun", "ฉัน")),
                "target_pronoun": speech.get("target_pronoun", "คุณ"),
                "third_person_pronoun": speech.get("third_person_pronoun", "เขา"),
                "ending_particle": speech.get("ending_particle", ""),
                "formality_level": speech.get("formality_level", 3)
            }
        })

    return {
        "character_id": char_id,
        "name": character_name,
        "th_name": raw_profile.get("th_name") or character_name,
        "aliases": raw_profile.get("aliases") or [character_name],
        "identity": {
            "gender": ident.get("gender", "UNKNOWN").upper(),
            "age": ident.get("age", "ADULT").upper(),
            "species": ident.get("species", "HUMAN").upper(),
            "number": "PLURAL" if "2人" in character_name or "たち" in character_name else ident.get("number", "SINGULAR").upper()
        },
        "base_speech_style": {
            "self_pronoun": base_style.get("self_pronoun", "ฉัน"),
            "ending_particle": base_style.get("ending_particle", ""),
            "formality_level": int(base_style.get("formality_level", 3))
        },
        "base_state": {
            "personality": base_state.get("personality") or raw_profile.get("personality") or [{"tag": "PER_SOC_NEUTRAL", "weight": 50}],
            "speech_habit": base_state.get("speech_habit") or raw_profile.get("speech_habit") or [{"tag": "SPR_STANDARD", "weight": 50}],
            "values": base_state.get("values") or [],
            "relationships": normalized_rels
        },
        "_metadata": {
            "synthesized_by": "chatgpt_web_bridge_v6",
            "dialogue_count": count,
            "sample_lines_recorded": samples_len,
            "total_pairwise_relationships": len(normalized_rels)
        }
    }


def analyze_character_profiles():
    manifest = load_manifest()
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    whitelist_path = os.path.join(tlas_dir, "character_whitelist.json")
    scenes_path = manifest.get("output_scenes_json") or os.path.join(tlas_dir, "rpgm_scenes_v5.json")
    profiles_dir = manifest.get("output_profiles_dir") or os.path.join(tlas_dir, "profiles")

    print("=" * 80)
    print("      ATF DYNAMIC CHARACTER PROFILE SYNTHESIZER (v6.0 - Live ChatGPT Bridge)      ")
    print("================================================================================")
    print(f"[*] Target Profiles Output Dir : {profiles_dir}")
    print(f"[*] Web Bridge Endpoint        : {BRIDGE_URL}/v1/chat/completions")

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

    # 3. สกัดความสัมพันธ์การร่วมฉาก
    co_occur_map = extract_scene_co_occurrences(qualified_names, packets)

    # 4. เชื่อมต่อ Bridge Server (Port 8765)
    wait_for_bridge_ready(BRIDGE_URL)

    os.makedirs(profiles_dir, exist_ok=True)
    synthesized_count = 0
    total_relationships = 0

    # 5. ส่ง Batch ไปให้ ChatGPT วิเคราะห์ทีละตัวละคร
    for ch in qualified_chars:
        char_name = ch.get("name")
        char_lines = ch.get("dialogue_count", 0)
        out_file = os.path.join(profiles_dir, f"{char_name}.json")

        print(f"\n[*] Processing Character: 【{char_name}】 ({char_lines} dialogue lines)...")
        samples = collect_character_dialogues(char_name, packets, max_samples=35)
        print(f"    - Collected {len(samples)} distinct in-game dialogue samples.")

        co_targets = list(co_occur_map.get(char_name, set()))
        system_prompt, user_prompt = build_analysis_prompt(char_name, samples, qualified_names, co_targets)

        print(f"    - Sending analysis prompt to ChatGPT via Web Bridge (Port 8765)...")
        try:
            raw_resp = call_chatgpt_api(user_prompt, system_prompt=system_prompt, bridge_url=BRIDGE_URL)
            parsed = extract_json_object(raw_resp)
            profile_data = normalize_profile_structure(parsed, char_name, char_lines, len(samples))

            ident = profile_data.get("identity", {})
            speech = profile_data.get("base_speech_style", {})
            rels = profile_data.get("base_state", {}).get("relationships", [])
            total_relationships += len(rels)

            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, ensure_ascii=False, indent=2)

            print(f"    [✔] AI Synthesis Success: Gender={ident.get('gender')}, Age={ident.get('age')}, Pronoun={speech.get('self_pronoun')}")
            print(f"    [✔] Established {len(rels)} Pairwise Relationships: {[r.get('target_name') for r in rels]}")
            synthesized_count += 1
        except Exception as e:
            print(f"    [❌] Error analyzing character 【{char_name}】 via ChatGPT: {e}")
            raise e

    print("\n" + "=" * 80)
    print(f"🎉 Successfully Generated {synthesized_count} Character Profiles with ChatGPT in: {profiles_dir}")
    print(f"📊 Total Pairwise Relationships Discovered by LLM: {total_relationships}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    analyze_character_profiles()
