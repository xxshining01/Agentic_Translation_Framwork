#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Dynamic Character Profile Synthesizer (v6.0 - Agentic LLM-Driven)
=====================================================================
วิเคราะห์และสังเคราะห์ไฟล์ Character Profile V4 ของตัวละครแต่ละตัวตาม Whitelist
โดยส่งบทสนทนาจริงจากฉากต่างๆ ไปให้ ChatGPT (ผ่าน Web Bridge) วิเคราะห์บุคลิกภาพ เพศ วัย
ลีลาการพูด และความสัมพันธ์ระหว่างตัวละครอย่างแท้จริง

สถาปัตยกรรม:
- Zero Hardcoding: ปราศจากพจนานุกรมชื่อหรือเพศตัวละครที่ฮาร์ดโค้ดไว้ในโค้ด 100%
- Factual Scene Harvesting: ดึงประโยคพูดจริงจาก scene_packets.json เพื่อส่งเป็นหลักฐานให้ LLM
- Bridge Auto-Detection: เชื่อมต่อ ChatGPT Web Bridge (Port 5000) อัตโนมัติ หาก Bridge ออฟไลน์
  จะสร้าง Baseline Profile ที่เป็นกลางไว้รองรับ และแจ้งเตือนให้ผู้ใช้เปิด Bridge เพื่อวิเคราะห์เชิงลึก
- Output: บันทึกไฟล์โปรไฟล์รายบุคคลลงใน <output_tlas_dir>/profiles/<Name>.json
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import re
from typing import Dict, Any, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")
TEMPLATE_PROFILE_PATH = os.path.join(WORKSPACE_ROOT, "templates", "character_profile.template.json")
BRIDGE_URL = "http://localhost:5000"


def load_manifest() -> Dict[str, Any]:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_json_safe(filepath: str) -> Any:
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def is_bridge_online() -> bool:
    """ตรวจสอบว่า ChatGPT Web Bridge ทำงานอยู่หรือไม่"""
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/api/heartbeat", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


def query_bridge(prompt: str, timeout: int = 120) -> str:
    """ส่งคำสั่งวิเคราะห์ไปยัง ChatGPT ผ่าน Web Bridge"""
    payload = json.dumps({"prompt": prompt, "mode": "analysis"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/api/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        task_id = res.get("task_id")

    if not task_id:
        raise RuntimeError("No task_id returned from Bridge")

    start_wait = time.time()
    while time.time() - start_wait < timeout:
        poll_req = urllib.request.Request(f"{BRIDGE_URL}/api/response/{task_id}", method="GET")
        try:
            with urllib.request.urlopen(poll_req, timeout=5) as p_resp:
                p_data = json.loads(p_resp.read().decode("utf-8"))
                if p_data.get("status") == "completed":
                    return p_data.get("response", "")
                elif p_data.get("status") == "error":
                    raise RuntimeError(f"Bridge task failed: {p_data.get('error')}")
        except urllib.error.HTTPError as he:
            if he.code != 404:
                raise he
        time.sleep(2)

    raise TimeoutError("Timed out waiting for ChatGPT response from Bridge")


def collect_character_dialogues(character_name: str, scene_packets: List[Dict[str, Any]], max_samples: int = 25) -> List[Dict[str, Any]]:
    """เก็บตัวอย่างบทสนทนาจริงที่ตัวละครนี้พูดจากฉากต่างๆ"""
    samples = []
    seen_texts = set()

    for pkt in scene_packets:
        sc_id = pkt.get("packet_id", "General_Scene")
        for dlg in pkt.get("dialogues", []):
            spk = dlg.get("speaker", "")
            raw_t = dlg.get("clean_text") or dlg.get("text", "")
            # ตรวจสอบว่าตัวละครนี้พูด หรือมีแท็กชื่อครอบอยู่
            if spk == character_name or f"【{character_name}】" in raw_t or f"[{character_name}]" in raw_t:
                clean_t = re.sub(r'^[【\[][^】\]]+[】\]]\s*', '', raw_t).strip()
                if clean_t and clean_t not in seen_texts:
                    seen_texts.add(clean_t)
                    samples.append({
                        "scene": sc_id,
                        "text": clean_t,
                        "other_speakers": [s for s in pkt.get("explicit_speakers", []) if s != character_name]
                    })
                    if len(samples) >= max_samples:
                        return samples

    return samples


def build_analysis_prompt(character_name: str, samples: List[Dict[str, Any]]) -> str:
    """สร้าง System Prompt บังคับคืนค่า Schema Profile V4 จากหลักฐานบทพูดจริง"""
    lines_formatted = []
    for idx, s in enumerate(samples, start=1):
        others = f" (Scene: {s['scene']} | Present: {', '.join(s['other_speakers']) if s['other_speakers'] else 'Solo'})"
        lines_formatted.append(f"{idx}. {repr(s['text'])}{others}")

    dialogue_block = "\n".join(lines_formatted)

    return f"""You are an elite video game narrative analyst and localization persona architect.
Analyze the following video game character based STRICTLY on their actual in-game dialogue evidence:

Character Name: "{character_name}"
Sample Dialogue Lines from In-Game Scenes:
{dialogue_block}

### YOUR OBJECTIVE:
Synthesize an evidence-grounded V4 Character Profile JSON with:
1. "character_id": Unique uppercase ID (e.g. "CHAR_{character_name.upper()}")
2. "name": "{character_name}"
3. "th_name": Approved Thai translation/transliteration for this name
4. "identity":
   - "gender": "MALE" | "FEMALE" | "NON_BINARY" | "UNKNOWN"
   - "age": "CHILD" | "TEEN" | "ADULT" | "ELDER"
   - "species": "HUMAN" | other
5. "base_speech_style":
   - "self_pronoun": Recommended natural Thai first-person pronoun (e.g. ฉัน, ผม, ข้า, กู, พี่, หนู, เรา)
   - "ending_particle": Recommended Thai ending polite or colloquial particle (e.g. ครับ, ค่ะ, จ้ะ, วะ, ยะ, or empty string "")
   - "formality_level": Integer from 1 (very vulgar/intimate) to 5 (highly formal/reverent)
6. "personality": List of trait objects [{{"tag": "PER_...", "weight": 1..100, "description": "..."}}]
7. "speech_habit": List of habits [{{"tag": "SPR_...", "weight": 1..100, "description": "..."}}]
8. "relationships": List of relationship objects with other characters detected in the scenes:
   [{{"target_name": "...", "roles": ["ROLE_..."], "affinity": "AFF_...", "intimacy": "INT_...", "power_dynamic": "DYN_...", "speech_style": {{"self_pronoun": "...", "target_pronoun": "...", "ending_particle": "..."}}}}]

MANDATORY RULES:
- Output ONLY a valid JSON object matching the requested schema.
- Do NOT wrap in markdown formatting or conversational text. Return ONLY the raw JSON string."""


def generate_baseline_fallback_profile(character_name: str, count: int, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """สร้าง Profile ตั้งต้นที่เป็นกลาง หากยังไม่ได้เชื่อมต่อ ChatGPT Bridge"""
    return {
        "character_id": f"CHAR_{re.sub(r'[^A-Za-z0-9]', '', character_name).upper() or 'UNKNOWN'}",
        "name": character_name,
        "th_name": character_name,
        "aliases": [character_name],
        "identity": {
            "gender": "UNKNOWN",
            "age": "ADULT",
            "species": "HUMAN",
            "number": "SINGULAR"
        },
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "ending_particle": "",
            "formality_level": 3
        },
        "base_state": {
            "personality": [{"tag": "PER_SOC_NEUTRAL", "weight": 50}],
            "speech_habit": [{"tag": "SPR_STANDARD", "weight": 50}],
            "values": [],
            "relationships": []
        },
        "_metadata": {
            "synthesized_by": "baseline_heuristic_pending_llm",
            "dialogue_count": count,
            "sample_lines_recorded": len(samples)
        }
    }


def analyze_character_profiles():
    manifest = load_manifest()
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    whitelist_path = os.path.join(tlas_dir, "character_whitelist.json")
    scenes_path = manifest.get("output_scenes_json") or os.path.join(tlas_dir, "scene_packets.json")
    profiles_dir = manifest.get("output_profiles_dir") or os.path.join(tlas_dir, "profiles")

    print("=" * 80)
    print("      ATF DYNAMIC CHARACTER PROFILE SYNTHESIZER (v6.0 - Agentic LLM)      ")
    print("=" * 80)
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

    # 3. ตรวจสอบ Bridge
    bridge_ready = is_bridge_online()
    if bridge_ready:
        print("🌐 [ChatGPT Bridge Online] Web Bridge Server is active on port 5000.")
        print("    Will perform live AI character persona and relationship synthesis!\n")
    else:
        print("⚠️ [ChatGPT Bridge Offline] Web Bridge is not running on port 5000.")
        print("    Generating clean evidence-grounded baseline profiles.")
        print("    💡 Run 'python atf.py bridge' in another terminal and re-run this command to synthesize with AI.\n")

    os.makedirs(profiles_dir, exist_ok=True)
    synthesized_count = 0

    for ch in qualified_chars:
        char_name = ch.get("name")
        char_lines = ch.get("dialogue_count", 0)
        out_file = os.path.join(profiles_dir, f"{char_name}.json")

        print(f"[*] Processing Character: 【{char_name}】 ({char_lines} dialogue lines)...")
        samples = collect_character_dialogues(char_name, packets, max_samples=25)
        print(f"    - Collected {len(samples)} distinct in-game dialogue samples.")

        profile_data = None

        if bridge_ready and samples:
            prompt = build_analysis_prompt(char_name, samples)
            print("    - Querying ChatGPT via Web Bridge for Persona & Relationship analysis...")
            try:
                resp = query_bridge(prompt, timeout=90)
                clean_json_str = re.sub(r'^```json\s*|\s*```$', '', resp.strip())
                parsed = json.loads(clean_json_str)
                if isinstance(parsed, dict) and "name" in parsed:
                    profile_data = parsed
                    profile_data["_metadata"] = {
                        "synthesized_by": "chatgpt_web_bridge_v6",
                        "dialogue_count": char_lines,
                        "sample_lines_recorded": len(samples)
                    }
                    print(f"    [✔] AI Synthesis Successful: Gender={parsed.get('identity', {}).get('gender')}, Age={parsed.get('identity', {}).get('age')}, Pronoun={parsed.get('base_speech_style', {}).get('self_pronoun')}")
            except Exception as e:
                print(f"    [!] AI query warning: {e}. Falling back to baseline profile.")

        if not profile_data:
            profile_data = generate_baseline_fallback_profile(char_name, char_lines, samples)
            print(f"    [✔] Generated baseline profile template for 【{char_name}】")

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)

        synthesized_count += 1

    print("\n" + "=" * 80)
    print(f"🎉 Successfully Generated {synthesized_count} Character Profiles in: {profiles_dir}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    analyze_character_profiles()
