#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Game Taxonomy Generator (v6.0 - Zero Hardcode)
==================================================
สร้างไฟล์ taxonomy.json ประจำเกมโดยเฉพาะ จากแม่แบบ templates/taxonomy.template.json
โดยเว้นข้อมูลเฉพาะของเกมให้สะอาด พร้อมให้ทีมแปลหรือ AI นำไปใช้งาน

สถาปัตยกรรม:
- Clean Taxonomy: นำเฉพาะหมวดหมู่และนิยามการจัดหมวดหมู่สากล (GND, AGE, PER, REL_ROLE, etc.)
  มาเป็นฐาน ไม่นำแท็กเฉพาะกิจของเกมเก่ามาปะปน
- Target Deliverable: บันทึก taxonomy.json ลงใน output_tlas_dir ของเกมโดยตรง
"""

import os
import sys
import json
from typing import Dict, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")
TEMPLATE_TAXONOMY_PATH = os.path.join(WORKSPACE_ROOT, "templates", "taxonomy.template.json")


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


def generate_game_taxonomy():
    manifest = load_manifest()
    project_name = manifest.get("project_name", "Game Localization")
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    output_taxonomy_path = manifest.get("output_taxonomy_json") or os.path.join(tlas_dir, "taxonomy.json")

    print("=" * 80)
    print("      ATF GAME-SPECIFIC TAXONOMY GENERATOR (v6.0 - Clean Schema)      ")
    print("=" * 80)
    print(f"[*] Template Source: {TEMPLATE_TAXONOMY_PATH}")
    print(f"[*] Target Output:   {output_taxonomy_path}")

    # โหลด Template Taxonomy
    template_data = load_json_safe(TEMPLATE_TAXONOMY_PATH)
    if not template_data:
        print(f"[ERROR] Template taxonomy not found at: {TEMPLATE_TAXONOMY_PATH}")
        sys.exit(1)

    # สร้าง Taxonomy เฉพาะเกม
    game_taxonomy = {
        "_metadata": {
            "version": "6.0",
            "game_project": project_name,
            "description": "ATF Universal 4D Narrative & Relationship Taxonomy Specification"
        },
        "categories": template_data.get("categories", {}),
        "tags": template_data.get("tags", {})
    }

    os.makedirs(os.path.dirname(output_taxonomy_path), exist_ok=True)
    with open(output_taxonomy_path, "w", encoding="utf-8") as f:
        json.dump(game_taxonomy, f, ensure_ascii=False, indent=2)

    print(f"[✔] Successfully compiled clean Taxonomy with {len(game_taxonomy['categories'])} Core Categories.")
    print("=" * 80)
    print(f"💾 Saved Game Taxonomy: {output_taxonomy_path}\n")


if __name__ == "__main__":
    generate_game_taxonomy()
