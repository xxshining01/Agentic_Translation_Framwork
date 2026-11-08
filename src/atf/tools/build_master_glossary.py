#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Master Glossary Builder (v6.0 - Zero Hardcode)
============================================================
สกัดคำศัพท์และชื่อเฉพาะจากฐานข้อมูลตัวเกมจริง (Actors, Items, Skills, MapInfos, System)
และจากบทสนทนา (Speaker Tags) โดยปราศจาก Hardcoded Character Definitions 100%

สถาปัตยกรรม:
- Grounded Evidence: ดึงชื่อจริงจาก Game Database และ Dialogue CSV
- User Baseline Matching: หากผู้ใช้ระบุ baseline/legacy glossary ไว้ใน setup จะทำการดึงคำแปลมาแมปให้อัตโนมัติ
- Zero Fallback Trap: ไม่เดาเพศหรือนิสัยเอง บันทึกโครงสร้างที่เป็นกลาง
- Target Deliverable: บันทึกไฟล์ tlas_glossary.json ลงใน output_glossary_json ตาม Manifest
"""

import os
import sys
import json
import csv
import re
from typing import Dict, Any, List

# Ensure UTF-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")
TEMPLATE_GLOSSARY_PATH = os.path.join(WORKSPACE_ROOT, "templates", "tlas_glossary.template.json")


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


def extract_game_entities(data_dir: str) -> Dict[str, List[str]]:
    """สกัด Entity Names จาก Game Database JSONs"""
    entities = {
        "actors": [],
        "items": [],
        "skills": [],
        "places": [],
        "system": []
    }
    if not data_dir or not os.path.exists(data_dir):
        return entities

    # 1. Actors.json
    actors_data = load_json_safe(os.path.join(data_dir, "Actors.json"))
    if isinstance(actors_data, list):
        for act in actors_data:
            if isinstance(act, dict) and act.get("name") and act["name"].strip():
                entities["actors"].append(act["name"].strip())

    # 2. Items.json, Weapons.json, Armors.json
    for item_file in ["Items.json", "Weapons.json", "Armors.json"]:
        items_data = load_json_safe(os.path.join(data_dir, item_file))
        if isinstance(items_data, list):
            for it in items_data:
                if isinstance(it, dict) and it.get("name") and it["name"].strip():
                    entities["items"].append(it["name"].strip())

    # 3. Skills.json
    skills_data = load_json_safe(os.path.join(data_dir, "Skills.json"))
    if isinstance(skills_data, list):
        for sk in skills_data:
            if isinstance(sk, dict) and sk.get("name") and sk["name"].strip():
                entities["skills"].append(sk["name"].strip())

    # 4. MapInfos.json
    map_data = load_json_safe(os.path.join(data_dir, "MapInfos.json"))
    if isinstance(map_data, list):
        for mp in map_data:
            if isinstance(mp, dict) and mp.get("name") and mp["name"].strip():
                entities["places"].append(mp["name"].strip())

    # 5. System.json
    sys_data = load_json_safe(os.path.join(data_dir, "System.json"))
    if isinstance(sys_data, dict):
        terms = sys_data.get("terms", {})
        if isinstance(terms, dict):
            for cat in ["basic", "commands", "params"]:
                vals = terms.get(cat, [])
                if isinstance(vals, list):
                    for v in vals:
                        if v and isinstance(v, str) and v.strip():
                            entities["system"].append(v.strip())

    return entities


def extract_csv_speakers(csv_path: str) -> List[str]:
    """สกัด Distinct Speakers จาก Speaker Tag ใน CSV (ป้องกันการอ่านชนคอลัมน์ Note)"""
    speakers = set()
    if not csv_path or not os.path.exists(csv_path):
        return list(speakers)

    tag_regex = re.compile(r'^[【\[]([^】\]\r\n]+)[】\]]|^<([^:>]+):?>')
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if not reader:
            return list(speakers)
        
        header_lower = [c.strip().lower() for c in reader[0]]
        speaker_idx = header_lower.index("speaker") if "speaker" in header_lower else -1

        for row in reader[1:]:
            if not row or not row[0].strip():
                continue
            text = row[0].strip()
            m = tag_regex.match(text)
            if m:
                spk = m.group(1) or m.group(2)
                if spk and spk.strip():
                    speakers.add(spk.strip())
            elif speaker_idx != -1 and len(row) > speaker_idx:
                spk_val = row[speaker_idx].strip()
                if spk_val and spk_val not in ["None", "Speaker", ""]:
                    speakers.add(spk_val)
    return sorted(list(speakers))


def build_master_glossary():
    manifest = load_manifest()
    data_dir = manifest.get("game_data_directory", "")
    csv_path = manifest.get("raw_pre_csv") or manifest.get("output_processed_csv", "")
    legacy_glossary_path = manifest.get("legacy_glossary_json", "")
    
    # พิกัดไฟล์ปลายทาง (First-Class Citizen)
    output_glossary = manifest.get("output_glossary_json")
    if not output_glossary:
        tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
        output_glossary = os.path.join(tlas_dir, "tlas_glossary.json")
    output_glossary = os.path.abspath(output_glossary)

    print("=" * 80)
    print("      ATF UNIVERSAL MASTER GLOSSARY BUILDER (v6.0 - Zero Hardcode)      ")
    print("=" * 80)
    print(f"[*] Game Data Directory: {data_dir or '(Not specified)'}")
    print(f"[*] Dialogue Source CSV: {csv_path or '(Not specified)'}")
    print(f"[*] Target Glossary Out: {output_glossary}")

    # โหลด Baseline Glossary เดิมที่ผู้ใช้เลือก (ถ้ามี)
    baseline_glossary = {}
    if legacy_glossary_path and os.path.exists(legacy_glossary_path):
        print(f"[*] Loaded User Baseline Glossary: {legacy_glossary_path}")
        baseline_glossary = load_json_safe(legacy_glossary_path) or {}

    # สกัดข้อมูลจริงจากเกม
    game_entities = extract_game_entities(data_dir)
    csv_speakers = extract_csv_speakers(csv_path)

    # รวมรายชื่อตัวละคร (Actors.json + CSV Speakers)
    all_characters = sorted(list(set(game_entities["actors"] + csv_speakers)))
    print(f"[✔] Extracted {len(all_characters)} Characters ({len(game_entities['actors'])} from Actors.json, {len(csv_speakers)} from Dialogue tags)")
    print(f"[✔] Extracted {len(game_entities['items'])} Items/Equipment")
    print(f"[✔] Extracted {len(game_entities['places'])} Places/Maps")
    print(f"[✔] Extracted {len(game_entities['skills'])} Skills")
    print(f"[✔] Extracted {len(game_entities['system'])} System Terms")

    # ประกอบ Master Glossary
    glossary = {
        "_metadata": {
            "version": "6.0",
            "description": "ATF Game Master Glossary (Zero Hardcode Evidence-Based)",
            "total_characters": len(all_characters),
            "total_items": len(game_entities["items"]),
            "total_places": len(game_entities["places"]),
            "total_skills": len(game_entities["skills"])
        },
        "Characters": {},
        "Items": {},
        "Places": {},
        "Skills": {},
        "System_UI": {}
    }

    # 1. Characters Section
    base_chars = baseline_glossary.get("Characters", {})
    for char in all_characters:
        th_val = ""
        gender_val = "UNKNOWN"
        role_val = "Dialogue Speaker"
        
        # ดึงจาก baseline ถ้ามี
        if char in base_chars:
            th_val = base_chars[char].get("th", "") if isinstance(base_chars[char], dict) else str(base_chars[char])
            gender_val = base_chars[char].get("gender", "UNKNOWN") if isinstance(base_chars[char], dict) else "UNKNOWN"
            role_val = base_chars[char].get("role", "Baseline") if isinstance(base_chars[char], dict) else "Baseline"
        
        glossary["Characters"][char] = {
            "th": th_val,
            "gender": gender_val,
            "role": role_val,
            "source": "Actors.json" if char in game_entities["actors"] else "Dialogue Tag"
        }

    # 2. Items Section
    base_items = baseline_glossary.get("Items", {})
    for item in sorted(list(set(game_entities["items"]))):
        th_val = base_items.get(item, {}).get("th", "") if isinstance(base_items.get(item), dict) else ""
        glossary["Items"][item] = {
            "th": th_val,
            "category": "Item / Equipment"
        }

    # 3. Places Section
    base_places = baseline_glossary.get("Places", {})
    for place in sorted(list(set(game_entities["places"]))):
        th_val = base_places.get(place, {}).get("th", "") if isinstance(base_places.get(place), dict) else ""
        glossary["Places"][place] = {
            "th": th_val,
            "category": "Map / Location"
        }

    # 4. Skills Section
    base_skills = baseline_glossary.get("Skills", {})
    for sk in sorted(list(set(game_entities["skills"]))):
        th_val = base_skills.get(sk, {}).get("th", "") if isinstance(base_skills.get(sk), dict) else ""
        glossary["Skills"][sk] = {
            "th": th_val,
            "category": "Skill"
        }

    # 5. System UI Section
    base_sys = baseline_glossary.get("System_UI", {})
    for term in sorted(list(set(game_entities["system"]))):
        th_val = base_sys.get(term, {}).get("th", "") if isinstance(base_sys.get(term), dict) else ""
        glossary["System_UI"][term] = {
            "th": th_val,
            "category": "System UI"
        }

    # บันทึกลง Target Output
    os.makedirs(os.path.dirname(output_glossary), exist_ok=True)
    with open(output_glossary, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"💾 Successfully Built Master Glossary: {output_glossary}\n")
    return glossary


if __name__ == "__main__":
    build_master_glossary()
