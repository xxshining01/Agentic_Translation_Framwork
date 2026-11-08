#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Master Glossary Translator (v6.0 - Live ChatGPT Web Bridge)
================================================================
ส่งรายชื่อตัวละคร (Characters), สถานที่ (Places), ไอเทม (Items), สกิล (Skills), 
และคำสั่งระบบ (System_UI) ใน tlas_glossary.json ที่ยังว่างอยู่
ไปให้ ChatGPT แปลและแปลทับศัพท์เป็นภาษาไทยระดับวรรณกรรมเกมอย่างเป็นทางการ

สถาปัตยกรรม:
- Bridge Transport: ส่งผ่าน http://127.0.0.1:8765 (/v1/chat/completions)
- Role-Aware Localization: แปลตามบทบาท (เช่น 夫 -> สามี, 凛 -> ริน, 遠藤 -> เอนโด, 受付のおばあさん -> คุณยายพนักงานต้อนรับ)
- In-Place Glossary Update: อัปเดตฟิลด์ "th" ใน tlas_glossary.json ทันที
- Zero Hallucination: คงชื่อคีย์เดิมของภาษาญี่ปุ่นไว้ 100% แก้เฉพาะคำแปลไทย
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import re
from typing import Dict, Any, List, Tuple

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
    try:
        req = urllib.request.Request(f"{bridge_url}/bridge/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "online", bool(data.get("userscript_connected"))
    except Exception:
        return False, False


def wait_for_bridge_ready(bridge_url: str = BRIDGE_URL) -> bool:
    first_notify = True
    while True:
        server_ok, script_ok = check_bridge_status(bridge_url)
        if server_ok and script_ok:
            print(f"🌐 [ChatGPT Bridge Online] พอร์ต 8765 ({bridge_url}) พร้อมแปล Glossary แล้ว!\n")
            return True

        if first_notify:
            print("\n" + "=" * 80)
            print("⏳ [Waiting for ChatGPT Bridge on Port 8765]")
            print(f"   กำลังรอการเชื่อมต่อจาก Bridge Server และ Tampermonkey บนหน้าเว็บ ChatGPT...")
            print("   👉 ตรวจสอบว่าเปิด: python atf.py bridge")
            print("   👉 และเปิดแท็บ:   https://chatgpt.com (จุดสถานะเขียว)")
            print("=" * 80 + "\n")
            first_notify = False

        time.sleep(2.0)


def call_chatgpt_api(prompt: str, system_prompt: str = "", bridge_url: str = BRIDGE_URL) -> str:
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
                print(f"⚠️ [ChatGPT Rate Limit / Cooldown] กำลังรอ 60 วินาที...")
                time.sleep(60)
                continue
            raise RuntimeError(f"Bridge HTTP Error ({e.code}): {err_body}")
        except Exception as ex:
            print(f"⚠️ [Bridge Communication Warning]: {ex}. กำลังลองใหม่ใน 5 วินาที...")
            time.sleep(5)


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    clean_text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    clean_text = re.sub(r'\s*```$', '', clean_text, flags=re.MULTILINE)
    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(clean_text)


def translate_master_glossary():
    manifest = load_manifest()
    output_glossary = manifest.get("output_glossary_json")
    if not output_glossary:
        tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
        output_glossary = os.path.join(tlas_dir, "tlas_glossary.json")

    print("=" * 80)
    print("      ATF MASTER GLOSSARY TRANSLATOR (v6.0 - Live ChatGPT Bridge)      ")
    print("========================================================================")
    print(f"[*] Target Glossary File: {output_glossary}")

    if not os.path.exists(output_glossary):
        print(f"[❌] Glossary file not found: {output_glossary}")
        print("Please run 'python atf.py prepare-glossary' first.")
        sys.exit(1)

    glossary_data = load_json_safe(output_glossary)
    if not isinstance(glossary_data, dict):
        print("[❌] Invalid glossary JSON format.")
        sys.exit(1)

    # รวบรวมคำศัพท์ที่ยังไม่มีคำแปล (th == "")
    untranslated_chars = {}
    for name, info in glossary_data.get("Characters", {}).items():
        if not info.get("th") or info.get("th").strip() == "":
            untranslated_chars[name] = info.get("role", "Character")

    untranslated_places = {}
    for place, info in glossary_data.get("Places", {}).items():
        if not info.get("th") or info.get("th").strip() == "":
            untranslated_places[place] = "Location / Map"

    untranslated_system = {}
    for term, info in glossary_data.get("System_UI", {}).items():
        if not info.get("th") or info.get("th").strip() == "":
            untranslated_system[term] = "Game System UI"

    total_pending = len(untranslated_chars) + len(untranslated_places) + len(untranslated_system)
    print(f"[*] Total Terms to Localize: {total_pending} terms")
    print(f"    - Characters : {len(untranslated_chars)} names")
    print(f"    - Places     : {len(untranslated_places)} locations")
    print(f"    - System UI  : {len(untranslated_system)} terms\n")

    if total_pending == 0:
        print("🎉 [✔] All terms in tlas_glossary.json are already translated into Thai!")
        return

    # รอการเชื่อมต่อ Bridge
    wait_for_bridge_ready(BRIDGE_URL)

    system_prompt = """You are an elite Japanese-to-Thai video game localization linguist and narrative editor.
Your mission is to provide accurate, natural, and authentic Thai localization for video game entity names and system terms.

LOCALIZATION GUIDELINES:
1. Character Names:
   - Proper names (e.g. 凛, 遠藤, 由美): Transliterate into natural Thai phonetics (เช่น 凛 -> ริน, 遠藤 -> เอนโด, 由美 -> ยูมิ).
   - Relational/Descriptive names (e.g. 夫, 旦那さん, 受付のおばあさん, 先生, 子供1, 学生A): Translate semantically according to their real narrative identity:
     * 夫 -> สามี
     * 旦那さん -> คุณสามี
     * 受付のおばあさん -> คุณยายพนักงานต้อนรับ
     * 先生 -> อาจารย์
     * 子供1 -> เด็ก 1
     * 子供たち -> พวกเด็กๆ
     * 学生A -> นักเรียน A
     * チャラそうなやつ① -> หนุ่มเจ้าสำราญ ① / วัยรุ่นท่าทางเกเร ①
2. Places / Locations:
   - Localize for maximum fantasy/narrative immersion (e.g. 民宿　離れ木 -> บ้านพักมินชูกุ ฮานาเรกิ, 縁側 -> ชานเรือน, 山道 -> ทางขึ้นเขา).
3. System UI:
   - Use standard professional Thai gaming UI terminology (e.g. 攻撃 -> โจมตี, 防御 -> ป้องกัน, 逃げる -> หลบหนี, アイテム -> ไอเทม).
4. Output Schema:
   - Return STRICTLY a valid JSON object matching the input keys:
     {
       "Characters": {"<Original_JP>": "<Thai_Translation>", ...},
       "Places": {"<Original_JP>": "<Thai_Translation>", ...},
       "System_UI": {"<Original_JP>": "<Thai_Translation>", ...}
     }
   - No conversational text, no markdown preamble."""

    user_payload = {
        "Characters": untranslated_chars,
        "Places": untranslated_places,
        "System_UI": untranslated_system
    }

    user_prompt = f"""Please localize all the following video game entities into authentic Thai:

{json.dumps(user_payload, ensure_ascii=False, indent=2)}

Return ONLY the raw JSON object."""

    print("🚀 Sending Master Glossary batch to ChatGPT Web Bridge...")
    raw_resp = call_chatgpt_api(user_prompt, system_prompt=system_prompt, bridge_url=BRIDGE_URL)

    try:
        translated_dict = extract_json_object(raw_resp)
    except Exception as e:
        print(f"[❌] Error parsing ChatGPT JSON response: {e}")
        print("Raw response:\n", raw_resp)
        sys.exit(1)

    # นำคำแปลกลับมาใส่ใน tlas_glossary.json
    updated_count = 0

    trans_chars = translated_dict.get("Characters", {})
    for jp, th_val in trans_chars.items():
        if jp in glossary_data.get("Characters", {}):
            glossary_data["Characters"][jp]["th"] = str(th_val).strip()
            updated_count += 1
            print(f"  [Character] {jp:15} -> {th_val}")

    trans_places = translated_dict.get("Places", {})
    for jp, th_val in trans_places.items():
        if jp in glossary_data.get("Places", {}):
            glossary_data["Places"][jp]["th"] = str(th_val).strip()
            updated_count += 1
            print(f"  [Place]     {jp:15} -> {th_val}")

    trans_sys = translated_dict.get("System_UI", {})
    for jp, th_val in trans_sys.items():
        if jp in glossary_data.get("System_UI", {}):
            glossary_data["System_UI"][jp]["th"] = str(th_val).strip()
            updated_count += 1

    # Atomic write บันทึกลง tlas_glossary.json
    temp_path = output_glossary + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as fp:
        json.dump(glossary_data, fp, ensure_ascii=False, indent=2)
    os.replace(temp_path, output_glossary)

    print("\n" + "=" * 80)
    print(f"🎉 Successfully Translated & Locked {updated_count} Glossary Terms in:")
    print(f"   {output_glossary}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    translate_master_glossary()

