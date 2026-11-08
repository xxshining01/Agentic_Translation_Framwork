#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Character Whitelist Engine (v6.0 - Zero Hardcode)
=====================================================
วิเคราะห์ความถี่และบทบาทของตัวละครในเกมจริง เพื่อคัดกรองตัวละครเข้า Whitelist (ADR-035)
คัดแยกว่า "ใครควรถูกนำไปสร้าง Character Profile" และใครเป็น "Ambient NPC (Clean Passthrough)"
โดยปราศจาก Hardcoded Name Lists 100%
"""

import os
import sys
import json
import csv
import re
from collections import Counter
from typing import Dict, Any, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


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


def count_speaker_dialogues(csv_path: str) -> Counter:
    """นับจำนวนประโยคพูดของตัวละครแต่ละตัวจาก CSV (ป้องกันการอ่านชนคอลัมน์ Note)"""
    counts = Counter()
    if not csv_path or not os.path.exists(csv_path):
        return counts

    tag_regex = re.compile(r'^[【\[]([^】\]\r\n]+)[】\]]|^<([^:>]+):?>')
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if not reader:
            return counts

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
                    counts[spk.strip()] += 1
            elif speaker_idx != -1 and len(row) > speaker_idx:
                spk_val = row[speaker_idx].strip()
                if spk_val and spk_val not in ["None", "Speaker", ""]:
                    counts[spk_val] += 1

    return counts


def build_character_whitelist():
    manifest = load_manifest()
    data_dir = manifest.get("game_data_directory", "")
    csv_path = manifest.get("raw_pre_csv") or manifest.get("output_processed_csv", "")
    
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    output_whitelist = os.path.join(tlas_dir, "character_whitelist.json")

    print("=" * 80)
    print("      ATF DYNAMIC CHARACTER WHITELIST BUILDER (v6.0 - Evidence Based)      ")
    print("=" * 80)

    # 1. อ่าน Actors.json จาก Engine
    actors_list = []
    actors_path = os.path.join(data_dir, "Actors.json") if data_dir else ""
    actors_data = load_json_safe(actors_path)
    if isinstance(actors_data, list):
        for act in actors_data:
            if isinstance(act, dict) and act.get("name") and act["name"].strip():
                actors_list.append(act["name"].strip())

    # 2. นับความถี่บทสนทนาจริง
    speaker_counts = count_speaker_dialogues(csv_path)

    # รวม Distinct Speakers ทั้งหมด
    all_speakers = set(list(speaker_counts.keys()) + actors_list)
    print(f"[*] Total Detected Distinct Characters: {len(all_speakers)}")
    print(f"[*] Pre-defined Party Actors in Actors.json: {len(actors_list)}")

    whitelist_entries = []
    ambient_entries = []

    # เกณฑ์การคัดกรอง (ADR-035 Specification):
    # - Defined in Actors.json -> CORE
    # - Dialogue count >= 10 -> CORE / SECONDARY
    # - Dialogue count 3..9 แต่ไม่ใช่คำสั่งระบบ หรือเครื่องหมาย ? -> SECONDARY
    # - Dialogue count < 3 หรือ Placeholder/Mob -> AMBIENT (Clean Passthrough)
    
    placeholder_patterns = re.compile(r'^[？\?]+$|^システム$|^ナレーション$|^none$', re.IGNORECASE)

    for spk in sorted(all_speakers, key=lambda x: speaker_counts.get(x, 0), reverse=True):
        count = speaker_counts.get(spk, 0)
        is_actor = spk in actors_list

        if placeholder_patterns.match(spk):
            # สัญลักษณ์นิรนาม / ผู้บรรยาย ไม่ต้องทำ Profile
            continue

        if is_actor:
            category = "Core"
            qualifies = True
            reason = f"Defined in Actors.json (Party Member / Main Actor) | {count} lines"
        elif count >= 10:
            category = "Core"
            qualifies = True
            reason = f"High dialogue presence ({count} lines in script)"
        elif count >= 4 and not re.match(r'^(男|女|村人|兵士|客|学生)[A-Z0-9]?$', spk):
            category = "Secondary"
            qualifies = True
            reason = f"Unique recurring named character ({count} lines)"
        else:
            category = "Ambient"
            qualifies = False
            reason = f"Low frequency ({count} lines) - Clean Passthrough rule applies"

        entry = {
            "name": spk,
            "dialogue_count": count,
            "role_category": category,
            "analysis_target": qualifies,
            "reason": reason
        }

        if qualifies:
            whitelist_entries.append(entry)
        else:
            ambient_entries.append(entry)

    print("\n" + "-" * 80)
    print(f"{'Character Name':<20} | {'Lines':<8} | {'Category':<12} | {'Profile Target':<15} | Reason")
    print("-" * 80)
    for e in whitelist_entries:
        print(f"{e['name']:<20} | {e['dialogue_count']:<8} | {e['role_category']:<12} | {'YES [Target]':<15} | {e['reason']}")
    for e in ambient_entries[:8]:
        print(f"{e['name']:<20} | {e['dialogue_count']:<8} | {e['role_category']:<12} | {'NO (Passthrough)':<15} | {e['reason']}")
    if len(ambient_entries) > 8:
        print(f"... and {len(ambient_entries) - 8} more ambient NPCs.")

    result_data = {
        "_metadata": {
            "version": "6.0",
            "description": "Evidence-Based Character Whitelist (ADR-035 Compliance)",
            "total_qualified": len(whitelist_entries),
            "total_ambient_passthrough": len(ambient_entries)
        },
        "qualified_characters": whitelist_entries,
        "ambient_passthrough_characters": ambient_entries
    }

    os.makedirs(os.path.dirname(output_whitelist), exist_ok=True)
    with open(output_whitelist, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print("-" * 80)
    print(f"🎉 Whitelist Compilation Completed:")
    print(f"    - Qualified for Character Profile (AI Analysis) : {len(whitelist_entries)} characters")
    print(f"    - Ambient Passthrough (Zero False Profiles)    : {len(ambient_entries)} characters")
    print(f"💾 Saved Character Whitelist: {output_whitelist}\n")
    return result_data


if __name__ == "__main__":
    build_character_whitelist()

