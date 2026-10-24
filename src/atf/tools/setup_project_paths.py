#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Project Path Setup & Verification Tool (Enhanced Universal Architecture v2.0)
เครื่องมือสำหรับกำหนด ตรวจสอบ และจับคู่ตำแหน่งไฟล์/โฟลเดอร์ตั้งต้นของโปรเจกต์
รองรับการ Browse แหล่งข้อมูลและโมเดลภาษาทุกไฟล์ (Taxonomy, Pronoun Matrix, Aliases, Profiles, Glossary)
สอดคล้องตาม ADR-024 (Target Workspace Isolation) และ ADR-025 (Target Whitelist Invariant)
"""

import os
import sys
import json
import csv
import shutil
import glob
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

# หา Root Directory ของ Workspace
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DATA_DIR = os.path.join(WORKSPACE_ROOT, "data")
MANIFEST_PATH = os.path.join(DATA_DIR, "project_manifest.json")


def detect_defaults() -> Dict[str, str]:
    """ค้นหาค่าเริ่มต้นอัตโนมัติจากโครงสร้างโปรเจกต์และ Manifest เดิม"""
    defaults = {
        "game_dir": "",
        "pre_csv": "",
        "legacy_plugin_csv": os.path.join(DATA_DIR, "plugins_texts.csv"),
        
        # ฐานข้อมูลภาษาและแบบจำลอง Ground Truth
        "baseline_profiles_dir": os.path.join(DATA_DIR, "tlas", "profiles"),
        "baseline_taxonomy_json": os.path.join(DATA_DIR, "tlas", "taxonomy.json"),
        "baseline_pronoun_matrix_json": os.path.join(DATA_DIR, "tlas", "global_pronoun_matrix.json"),
        "baseline_alias_mapping_json": os.path.join(DATA_DIR, "tlas", "alias_mapping.json"),
        "baseline_glossary_json": os.path.join(DATA_DIR, "tlas", "tlas_glossary.json"),
        "baseline_checkpoint_json": os.path.join(DATA_DIR, "tlas", "chatgpt_translation_checkpoint.json"),
        
        # ปลายทาง
        "output_dir": os.path.join(WORKSPACE_ROOT, "output"),
        "output_processed_csv": "",
    }

    # ตรวจหาโฟลเดอร์เกมตัวอย่างเริ่มต้น
    example_game = os.path.join(WORKSPACE_ROOT, "Example RPGM Game")
    if os.path.exists(example_game):
        defaults["game_dir"] = example_game

    # ตรวจหาไฟล์ CSV ตั้งต้นที่เป็น candidate ในโปรเจกต์
    candidates_csv = [
        os.path.join(WORKSPACE_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - ชีต1.csv"),
        os.path.join(WORKSPACE_ROOT, "testing files", "SSPV034v1.35 - Trans - ชีต1.csv"),
    ]
    for c in candidates_csv:
        if os.path.exists(c):
            defaults["pre_csv"] = c
            break

    # ถ้ามี manifest เดิมที่เคยบันทึกไว้ ให้โหลดมาเป็นค่าเริ่มต้นก่อน
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("game_directory") and os.path.exists(saved["game_directory"]):
                    defaults["game_dir"] = saved["game_directory"]
                if saved.get("raw_pre_csv") and os.path.exists(saved["raw_pre_csv"]):
                    defaults["pre_csv"] = saved["raw_pre_csv"]
                if saved.get("legacy_plugin_csv") and os.path.exists(saved["legacy_plugin_csv"]):
                    defaults["legacy_plugin_csv"] = saved["legacy_plugin_csv"]
                
                # ฐานข้อมูลเดิม
                if saved.get("legacy_profiles_dir") and os.path.exists(saved["legacy_profiles_dir"]):
                    defaults["baseline_profiles_dir"] = saved["legacy_profiles_dir"]
                if saved.get("legacy_taxonomy_json") and os.path.exists(saved["legacy_taxonomy_json"]):
                    defaults["baseline_taxonomy_json"] = saved["legacy_taxonomy_json"]
                if saved.get("legacy_pronoun_matrix_json") and os.path.exists(saved["legacy_pronoun_matrix_json"]):
                    defaults["baseline_pronoun_matrix_json"] = saved["legacy_pronoun_matrix_json"]
                if saved.get("legacy_alias_mapping_json") and os.path.exists(saved["legacy_alias_mapping_json"]):
                    defaults["baseline_alias_mapping_json"] = saved["legacy_alias_mapping_json"]
                if saved.get("legacy_glossary_json") and os.path.exists(saved["legacy_glossary_json"]):
                    defaults["baseline_glossary_json"] = saved["legacy_glossary_json"]
                if saved.get("legacy_checkpoint_json") and os.path.exists(saved["legacy_checkpoint_json"]):
                    defaults["baseline_checkpoint_json"] = saved["legacy_checkpoint_json"]
                
                if saved.get("output_dir"):
                    defaults["output_dir"] = saved["output_dir"]
                if saved.get("output_processed_csv"):
                    defaults["output_processed_csv"] = saved["output_processed_csv"]
        except Exception:
            pass

    # หากยังไม่มี output_processed_csv ให้คำนวณจาก output_dir
    if not defaults["output_processed_csv"]:
        defaults["output_processed_csv"] = os.path.join(defaults["output_dir"], "processed_dialogues_v3.csv")

    return defaults


# ==============================================================================
# VALIDATION ENGINE
# ==============================================================================

def validate_game_dir(game_dir: str) -> Tuple[bool, str, Dict[str, str]]:
    """ตรวจสอบความสมบูรณ์ของโฟลเดอร์ตัวเกม RPG Maker"""
    if not game_dir or not os.path.exists(game_dir):
        return False, "ไม่พบโฟลเดอร์เกมที่ระบุ", {}

    data_dir = None
    for sub in ["www/data", "data"]:
        p = os.path.join(game_dir, sub.replace("/", os.sep))
        if os.path.exists(p) and os.path.isdir(p):
            data_dir = p
            break

    if not data_dir:
        return False, "ไม่พบโฟลเดอร์ 'data' หรือ 'www/data' ในตัวเกม", {}

    json_count = len([f for f in os.listdir(data_dir) if f.endswith(".json")])
    if json_count == 0:
        return False, f"ไม่พบไฟล์ .json ใน {data_dir}", {}

    plugins_js = None
    for sub in ["www/js/plugins.js", "js/plugins.js"]:
        p = os.path.join(game_dir, sub.replace("/", os.sep))
        if os.path.exists(p):
            plugins_js = p
            break

    subpaths = {
        "data_dir": data_dir,
        "plugins_js": plugins_js or "",
        "json_count": str(json_count)
    }
    status_msg = f"พบไฟล์ข้อมูลเกม {json_count} ไฟล์ JSON" + (" (มี plugins.js)" if plugins_js else " (ไม่มี plugins.js)")
    return True, status_msg, subpaths


def validate_pre_csv(csv_path: str) -> Tuple[bool, str, int]:
    """ตรวจสอบความสมบูรณ์ของไฟล์ Pre-CSV (ต้องมีคอลัมน์ Original, Filename, Row)"""
    if not csv_path or not os.path.exists(csv_path):
        return False, "ไม่พบไฟล์ CSV ที่ระบุ", 0

    try:
        with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return False, "ไฟล์ CSV ว่างเปล่า ไม่มี Header", 0

            header_lower = [h.strip().lower() for h in header]
            required = ["original", "filename", "row"]
            missing = [r for r in required if r not in header_lower]

            if missing:
                return False, f"Header ขาดคอลัมน์สำคัญ: {', '.join(missing)}", 0

            row_count = sum(1 for _ in reader)
            return True, f"Header สมบูรณ์ ({len(header)} คอลัมน์, {row_count:,} แถว)", row_count
    except Exception as e:
        return False, f"อ่านไฟล์ CSV ไม่สำเร็จ: {e}", 0


def validate_legacy_plugin_csv(csv_path: str) -> Tuple[bool, str]:
    """ตรวจสอบไฟล์ Plugin Text เดิม (Optional)"""
    if not csv_path:
        return True, "ไม่ระบุ (จะสกัดใหม่จาก plugins.js โดยตรง)"
    if not os.path.exists(csv_path):
        return False, "ไม่พบไฟล์ตาม Path ที่ระบุ"

    try:
        with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            count = sum(1 for _ in f) - 1
            return True, f"พบไฟล์ Plugin Text เดิม ({max(0, count):,} แถว)"
    except Exception as e:
        return False, f"อ่านไฟล์ไม่สำเร็จ: {e}"


def validate_baseline_profiles(profiles_dir: str) -> Tuple[bool, str, int]:
    """ตรวจสอบโฟลเดอร์ Character Profiles ตั้งต้น (Ground Truth)"""
    if not profiles_dir:
        return False, "ยังไม่ได้ระบุโฟลเดอร์ Profile เดิม (กรณีเกมใหม่จะสร้างใหม่จาก Consensus)", 0
    if not os.path.exists(profiles_dir) or not os.path.isdir(profiles_dir):
        return False, "ไม่พบโฟลเดอร์ Character Profiles บนดิสก์", 0

    json_files = glob.glob(os.path.join(profiles_dir, "*.json"))
    count = len(json_files)
    if count == 0:
        return False, "โฟลเดอร์มีอยู่จริงแต่ไม่มีไฟล์ Character Profile (.json)", 0

    samples = [os.path.basename(f)[:-5] for f in json_files[:4]]
    sample_text = ", ".join(samples) + ("..." if count > 4 else "")
    return True, f"พร้อมใช้งาน: พบ {count} โปรไฟล์ตัวละคร ({sample_text})", count


def validate_baseline_taxonomy(taxonomy_path: str) -> Tuple[bool, str]:
    """ตรวจสอบแบบจำลองอนุกรมวิธานบริบท/ยุคสมัย (Taxonomy JSON)"""
    if not taxonomy_path:
        return False, "ยังไม่ได้ระบุไฟล์ Taxonomy (จำเป็นต่อการกำหนดโครงสร้างสรรพนามและยุคสมัยของเกม)"
    if not os.path.exists(taxonomy_path) or not os.path.isfile(taxonomy_path):
        return False, "ไม่พบไฟล์ Taxonomy บนดิสก์"

    try:
        with open(taxonomy_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ver = data.get("version", "N/A")
        cats = len(data.get("categories", {}))
        pronouns_self = len(data.get("pronoun_options", {}).get("self", []))
        pronouns_target = len(data.get("pronoun_options", {}).get("target", []))
        return True, f"พร้อมใช้งาน: v{ver} ({cats} หมวดบริบท, สรรพนามแทนตัว {pronouns_self} คำ, สรรพนามเรียกคู่สนทนา {pronouns_target} คำ)"
    except Exception as e:
        return False, f"ไฟล์ Taxonomy เสียหายหรืออ่าน JSON ไม่สำเร็จ: {e}"


def validate_baseline_pronoun_matrix(matrix_path: str) -> Tuple[bool, str]:
    """ตรวจสอบไฟล์ตารางสรรพนามคู่สนทนาระหว่างตัวละคร (Global Pronoun Matrix JSON)"""
    if not matrix_path:
        return False, "ยังไม่ได้ระบุตาราง Pronoun Matrix (จะสร้างใหม่จาก Consensus Engine)"
    if not os.path.exists(matrix_path) or not os.path.isfile(matrix_path):
        return False, "ไม่พบไฟล์ Pronoun Matrix บนดิสก์"

    try:
        with open(matrix_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            pairs_count = len(data)
            return True, f"พร้อมใช้งาน: {pairs_count:,} คู่ความสัมพันธ์ระหว่างตัวละคร (Speaker -> Listener)"
        elif isinstance(data, dict):
            return True, f"พร้อมใช้งาน: {len(data):,} รายการสรรพนาม"
        return False, "โครงสร้าง Pronoun Matrix ไม่ถูกต้อง (ต้องเป็น JSON List หรือ Dict)"
    except Exception as e:
        return False, f"อ่านไฟล์ Pronoun Matrix ไม่สำเร็จ: {e}"


def validate_baseline_alias_mapping(alias_path: str) -> Tuple[bool, str]:
    """ตรวจสอบไฟล์จับคู่นามแฝงตัวละคร (Alias Mapping JSON)"""
    if not alias_path:
        return True, "ไม่ระบุ (จะใช้ Canonical Names ตามปกติ)"
    if not os.path.exists(alias_path) or not os.path.isfile(alias_path):
        return False, "ไม่พบไฟล์ Alias Mapping บนดิสก์"

    try:
        with open(alias_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return True, f"พร้อมใช้งาน: {len(data):,} นามแฝง (Aliases Mapping)"
    except Exception as e:
        return False, f"อ่านไฟล์ Alias Mapping ไม่สำเร็จ: {e}"


def validate_baseline_glossary(glossary_path: str) -> Tuple[bool, str, Dict[str, int]]:
    """ตรวจสอบไฟล์ Master Glossary เดิม (Characters, Places, Items)"""
    if not glossary_path:
        return False, "ยังไม่ได้ระบุไฟล์ Glossary (กรณีเกมใหม่จะสร้างใหม่จากการสกัด)", {}
    if not os.path.exists(glossary_path) or not os.path.isfile(glossary_path):
        return False, "ไม่พบไฟล์ Master Glossary บนดิสก์", {}

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chars = len(data.get("Characters", {}))
        places = len(data.get("Places", {}))
        items = len(data.get("Items", {}))
        skills = len(data.get("Skills", {}))
        sys_ui = len(data.get("System_UI", {}))

        total_terms = chars + places + items + skills + sys_ui
        stats = {
            "characters": chars,
            "places": places,
            "items": items,
            "skills": skills,
            "system_ui": sys_ui,
            "total": total_terms
        }
        msg = f"พร้อมใช้งาน: {total_terms:,} คำศัพท์ (ตัวละคร: {chars}, สถานที่: {places}, ไอเทม: {items})"
        return True, msg, stats
    except Exception as e:
        return False, f"ไฟล์ Glossary เสียหายหรืออ่าน JSON ไม่สำเร็จ: {e}", {}


def validate_baseline_checkpoint(cp_path: str) -> Tuple[bool, str, int]:
    """ตรวจสอบไฟล์ Checkpoint เดิม (แคชการแปลเดิม)"""
    if not cp_path:
        return True, "ไม่ระบุ (จะเริ่มแปลตั้งแต่ต้นโดยไม่ใช้แคชเดิม)", 0
    if not os.path.exists(cp_path) or not os.path.isfile(cp_path):
        return False, "ไม่พบไฟล์ Checkpoint บนดิสก์", 0

    try:
        with open(cp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            csv_trans = data.get("csv_translations", {})
            total_cached = sum(len(v) for v in csv_trans.values()) if isinstance(csv_trans, dict) else 0
            return True, f"พบแคชเดิม: {total_cached:,} รายการแปลที่บันทึกไว้", total_cached
    except Exception as e:
        return False, f"ไฟล์ Checkpoint เสียหายหรืออ่าน JSON ไม่สำเร็จ: {e}", 0


def validate_output_workspace(out_dir: str) -> Tuple[bool, str]:
    """ตรวจสอบความพร้อมของโฟลเดอร์ Output ปลายทาง (ตาม ADR-024)"""
    if not out_dir or not out_dir.strip():
        return False, "กรุณาระบุโฟลเดอร์ผลลัพธ์ปลายทาง (Target Output Workspace)"

    clean_dir = os.path.abspath(out_dir.strip())
    try:
        os.makedirs(clean_dir, exist_ok=True)
        test_file = os.path.join(clean_dir, ".atf_write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return True, f"พร้อมใช้งาน: โฟลเดอร์ปลายทางพร้อมบันทึก ({clean_dir})"
    except Exception as e:
        return False, f"ไม่สามารถสร้างหรือเขียนลงโฟลเดอร์ปลายทางได้: {e}"


# ==============================================================================
# MANIFEST PERSISTENCE & SEEDING ENGINE (ADR-024)
# ==============================================================================

def save_manifest(data: Dict[str, Any], seed_output_workspace: bool = False) -> Tuple[str, Dict[str, Any]]:
    """
    บันทึก Project Manifest ลง data/project_manifest.json พร้อมแยกโฟลเดอร์ผลลัพธ์แบบเอกเทศ (ADR-024)
    และทำการคัดลอก Baseline Ground Truth ไปยัง Output Workspace หากเปิดตัวเลือก seed_output_workspace
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    out_dir = os.path.abspath(data.get("output_dir", os.path.join(WORKSPACE_ROOT, "output")))
    out_tlas_dir = os.path.join(out_dir, "tlas")
    out_profiles_dir = os.path.join(out_tlas_dir, "profiles")
    out_taxonomy_json = os.path.join(out_tlas_dir, "taxonomy.json")
    out_pronoun_matrix_json = os.path.join(out_tlas_dir, "global_pronoun_matrix.json")
    out_alias_mapping_json = os.path.join(out_tlas_dir, "alias_mapping.json")
    out_glossary_json = os.path.join(out_tlas_dir, "tlas_glossary.json")
    out_scenes_json = os.path.join(out_tlas_dir, "rpgm_scenes_v5.json")
    out_checkpoint_json = os.path.join(out_tlas_dir, "chatgpt_translation_checkpoint.json")
    
    out_csv = data.get("output_processed_csv")
    if not out_csv:
        out_csv = os.path.join(out_dir, "processed_dialogues_v3.csv")
    out_csv = os.path.abspath(out_csv)

    out_plugins_csv = os.path.join(out_dir, "plugins_texts_v035.csv")

    manifest = {
        "project_name": data.get("project_name", "ATF Localization Project"),
        "timestamp": datetime.now().isoformat(),
        
        # 1. แหล่งข้อมูลตัวเกมและการสกัด
        "game_directory": data.get("game_dir", ""),
        "game_data_directory": data.get("game_data_dir", ""),
        "game_plugins_js": data.get("game_plugins_js", ""),
        "raw_pre_csv": data.get("pre_csv", ""),
        "raw_pre_csv_rows": data.get("pre_csv_rows", 0),
        "legacy_plugin_csv": data.get("legacy_plugin_csv", ""),
        
        # 2. ฐานข้อมูลตั้งต้นเดิม / Ground Truth (Baseline Knowledge)
        "legacy_tlas_dir": os.path.dirname(data.get("baseline_profiles_dir", "")) if data.get("baseline_profiles_dir") else os.path.join(DATA_DIR, "tlas"),
        "legacy_profiles_dir": data.get("baseline_profiles_dir", ""),
        "legacy_taxonomy_json": data.get("baseline_taxonomy_json", ""),
        "legacy_pronoun_matrix_json": data.get("baseline_pronoun_matrix_json", ""),
        "legacy_alias_mapping_json": data.get("baseline_alias_mapping_json", ""),
        "legacy_glossary_json": data.get("baseline_glossary_json", ""),
        "legacy_checkpoint_json": data.get("baseline_checkpoint_json", ""),
        
        # 3. โฟลเดอร์และไฟล์ผลลัพธ์ปลายทาง (Target Deliverables - ADR-024)
        "output_dir": out_dir,
        "output_processed_csv": out_csv,
        "output_tlas_dir": out_tlas_dir,
        "output_profiles_dir": out_profiles_dir,
        "output_taxonomy_json": out_taxonomy_json,
        "output_pronoun_matrix_json": out_pronoun_matrix_json,
        "output_alias_mapping_json": out_alias_mapping_json,
        "output_glossary_json": out_glossary_json,
        "output_scenes_json": out_scenes_json,
        "output_checkpoint_json": out_checkpoint_json,
        "output_plugins_csv": out_plugins_csv,
    }

    # บันทึกไฟล์ Manifest หลัก
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # ดำเนินการสร้าง Output Directories ทั้งหมด
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_tlas_dir, exist_ok=True)
    os.makedirs(out_profiles_dir, exist_ok=True)

    seed_report = {
        "profiles_copied": 0,
        "taxonomy_copied": False,
        "matrix_copied": False,
        "aliases_copied": False,
        "glossary_copied": False,
        "checkpoint_copied": False
    }

    # หากผู้ใช้เลือก Seed Output Workspace ให้ทำการคัดลอกไฟล์จาก Baseline ไปยัง Target
    if seed_output_workspace:
        # 1. คัดลอก Baseline Profiles
        src_profiles = data.get("baseline_profiles_dir")
        if src_profiles and os.path.exists(src_profiles):
            for pf in glob.glob(os.path.join(src_profiles, "*.json")):
                dst_pf = os.path.join(out_profiles_dir, os.path.basename(pf))
                shutil.copy2(pf, dst_pf)
                seed_report["profiles_copied"] += 1

        # 2. คัดลอก Taxonomy
        src_tax = data.get("baseline_taxonomy_json")
        if src_tax and os.path.exists(src_tax):
            shutil.copy2(src_tax, out_taxonomy_json)
            seed_report["taxonomy_copied"] = True

        # 3. คัดลอก Pronoun Matrix
        src_mat = data.get("baseline_pronoun_matrix_json")
        if src_mat and os.path.exists(src_mat):
            shutil.copy2(src_mat, out_pronoun_matrix_json)
            seed_report["matrix_copied"] = True

        # 4. คัดลอก Aliases Mapping
        src_alias = data.get("baseline_alias_mapping_json")
        if src_alias and os.path.exists(src_alias):
            shutil.copy2(src_alias, out_alias_mapping_json)
            seed_report["aliases_copied"] = True

        # 5. คัดลอก Glossary
        src_glossary = data.get("baseline_glossary_json")
        if src_glossary and os.path.exists(src_glossary):
            shutil.copy2(src_glossary, out_glossary_json)
            seed_report["glossary_copied"] = True

        # 6. คัดลอก Checkpoint
        src_cp = data.get("baseline_checkpoint_json")
        if src_cp and os.path.exists(src_cp):
            shutil.copy2(src_cp, out_checkpoint_json)
            seed_report["checkpoint_copied"] = True

    return MANIFEST_PATH, seed_report


def print_summary(data: Dict[str, Any], seed_report: Dict[str, Any] = None):
    """แสดงตารางสรุปผลลัพธ์บน Terminal อย่างเป็นระเบียบ"""
    print("\n" + "=" * 80)
    print("      ATF PROJECT PATH MANIFEST - VERIFIED CONFIGURATION (UNIVERSAL)      ")
    print("=" * 80)
    print("📁 [หมวดที่ 1: แหล่งข้อมูลตัวเกมและการสกัด]")
    print(f"  • โฟลเดอร์ตัวเกม:           {data.get('game_dir', 'N/A')}")
    print(f"    -> โฟลเดอร์ Data:         {data.get('game_data_dir', 'N/A')}")
    print(f"    -> ไฟล์ plugins.js:      {data.get('game_plugins_js', 'N/A')}")
    print(f"  • ไฟล์ Pre-CSV บทสนทนา:    {data.get('pre_csv', 'N/A')} ({data.get('pre_csv_rows', 0):,} แถว)")
    print(f"  • ไฟล์ Plugin Text เดิม:    {data.get('legacy_plugin_csv', 'N/A') or 'ไม่ระบุ (สกัดใหม่)'}")
    print("\n🧠 [หมวดที่ 2: ฐานข้อมูลตั้งต้นเดิม / Ground Truth (Baseline Knowledge)]")
    print(f"  • ⭐ โฟลเดอร์ Profile เดิม:   {data.get('baseline_profiles_dir', 'N/A')}")
    print(f"  • ⭐ แบบจำลอง Taxonomy:     {data.get('baseline_taxonomy_json', 'N/A')}")
    print(f"  • ⭐ ตาราง Pronoun Matrix:   {data.get('baseline_pronoun_matrix_json', 'N/A')}")
    print(f"  • ⭐ แฟ้ม Alias Mapping:     {data.get('baseline_alias_mapping_json', 'N/A')}")
    print(f"  • คลังคำศัพท์หลักเดิม:      {data.get('baseline_glossary_json', 'N/A')}")
    print(f"  • แคชประวัติการแปลเดิม:     {data.get('baseline_checkpoint_json', 'N/A') or 'ไม่ระบุ (เริ่มใหม่)'}")
    print("\n🎯 [หมวดที่ 3: โฟลเดอร์ผลลัพธ์ปลายทาง (Target Deliverables - ADR-024)]")
    print(f"  • โฟลเดอร์ผลลัพธ์หลัก:       {data.get('output_dir', 'N/A')}")
    print(f"  • ไฟล์ Processed CSV:       {data.get('output_processed_csv', 'N/A')}")
    print(f"  • โฟลเดอร์ TLAS ปลายทาง:    {os.path.join(data.get('output_dir', ''), 'tlas')}")
    if seed_report and (seed_report.get("profiles_copied") or seed_report.get("taxonomy_copied")):
        print(f"  • 📋 Seeded to Workspace:  Profiles {seed_report.get('profiles_copied')} ไฟล์, Taxonomy: {'✔' if seed_report.get('taxonomy_copied') else '✖'}, Matrix: {'✔' if seed_report.get('matrix_copied') else '✖'}")
    print("-" * 80)
    print(f"💾 บันทึก Manifest สำเร็จที่: {MANIFEST_PATH}")
    print("=" * 80 + "\n")


# ==============================================================================
# TKINTER GRAPHICAL USER INTERFACE (GUI)
# ==============================================================================

def run_gui():
    """เปิดหน้าต่าง GUI ด้วย Tkinter แบบครบวงจรและรองรับการจัดวาง 3 หมวดหมู่"""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    defaults = detect_defaults()

    root = tk.Tk()
    root.title("ATF - กำหนดตำแหน่งทรัพยากรและฐานข้อมูลโปรเจกต์ (Project Path Setup v2.0)")
    root.geometry("900x800")
    root.minsize(840, 680)

    style = ttk.Style()
    style.theme_use("clam")

    # Canvas & Scrollbar สำหรับรองรับหน้าจอทุกขนาด
    canvas = tk.Canvas(root, borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding="14")

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Header
    header_lbl = ttk.Label(
        scrollable_frame,
        text="กำหนดและจับคู่ตำแหน่งไฟล์ทรัพยากรและโมเดลภาษา (Universal ATF Setup)",
        font=("Segoe UI", 12, "bold")
    )
    header_lbl.pack(anchor="w", pady=(0, 4))
    
    sub_lbl = ttk.Label(
        scrollable_frame,
        text="กำหนดแหล่งข้อมูลตั้งต้น (Inputs), ฐานความรู้เดิม (Ground Truth/Taxonomy), และพื้นที่บันทึกผลลัพธ์ (Target Workspace)",
        font=("Segoe UI", 9),
        foreground="#555555"
    )
    sub_lbl.pack(anchor="w", pady=(0, 10))

    # Path Variables
    var_game_dir = tk.StringVar(value=defaults["game_dir"])
    var_pre_csv = tk.StringVar(value=defaults["pre_csv"])
    var_plugin_csv = tk.StringVar(value=defaults["legacy_plugin_csv"])
    
    var_profiles_dir = tk.StringVar(value=defaults["baseline_profiles_dir"])
    var_taxonomy_file = tk.StringVar(value=defaults["baseline_taxonomy_json"])
    var_pronoun_matrix_file = tk.StringVar(value=defaults["baseline_pronoun_matrix_json"])
    var_alias_mapping_file = tk.StringVar(value=defaults["baseline_alias_mapping_json"])
    var_glossary_file = tk.StringVar(value=defaults["baseline_glossary_json"])
    var_checkpoint_file = tk.StringVar(value=defaults["baseline_checkpoint_json"])
    
    var_out_dir = tk.StringVar(value=defaults["output_dir"])
    var_out_csv = tk.StringVar(value=defaults["output_processed_csv"])
    var_seed_workspace = tk.BooleanVar(value=True)

    # Status Variables
    status_game = tk.StringVar(value="รอตรวจสอบ")
    status_csv = tk.StringVar(value="รอตรวจสอบ")
    status_plugin = tk.StringVar(value="รอตรวจสอบ")
    
    status_profiles = tk.StringVar(value="รอตรวจสอบ")
    status_taxonomy = tk.StringVar(value="รอตรวจสอบ")
    status_matrix = tk.StringVar(value="รอตรวจสอบ")
    status_alias = tk.StringVar(value="รอตรวจสอบ")
    status_glossary = tk.StringVar(value="รอตรวจสอบ")
    status_cp = tk.StringVar(value="รอตรวจสอบ")
    
    status_out_dir = tk.StringVar(value="รอตรวจสอบ")
    status_out_csv = tk.StringVar(value="รอตรวจสอบ")

    def create_row(parent, label_text, var, browse_cmd, status_var):
        row_frame = ttk.LabelFrame(parent, text=label_text, padding="5")
        row_frame.pack(fill=tk.X, pady=3)

        entry_frame = ttk.Frame(row_frame)
        entry_frame.pack(fill=tk.X)

        entry = ttk.Entry(entry_frame, textvariable=var, font=("Segoe UI", 9))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        btn = ttk.Button(entry_frame, text="Browse...", width=10, command=browse_cmd)
        btn.pack(side=tk.RIGHT)

        lbl_status = ttk.Label(row_frame, textvariable=status_var, font=("Segoe UI", 8), foreground="#444444")
        lbl_status.pack(anchor="w", pady=(2, 0))

    # =========================================================================
    # SECTION 1: แหล่งข้อมูลตัวเกมและการสกัด (Game & Extraction Inputs)
    # =========================================================================
    sec1_frame = ttk.LabelFrame(scrollable_frame, text="📁 หมวดที่ 1: แหล่งข้อมูลตัวเกมและการสกัด (Game & Extraction Inputs)", padding="10")
    sec1_frame.pack(fill=tk.X, pady=6)

    def browse_game():
        p = filedialog.askdirectory(title="เลือกโฟลเดอร์ตัวเกม (RPG Maker)", initialdir=var_game_dir.get() or WORKSPACE_ROOT)
        if p:
            var_game_dir.set(os.path.normpath(p))
            check_all_paths()

    def browse_csv():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Pre-CSV บทสนทนาดิบ (จาก Translator++)",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_pre_csv.get()) if var_pre_csv.get() else WORKSPACE_ROOT
        )
        if p:
            var_pre_csv.set(os.path.normpath(p))
            check_all_paths()

    def browse_plugin():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Plugin Text ของเวอร์ชันเดิม (ถ้ามี)",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_plugin_csv.get()) if var_plugin_csv.get() else DATA_DIR
        )
        if p:
            var_plugin_csv.set(os.path.normpath(p))
            check_all_paths()

    create_row(sec1_frame, "1. โฟลเดอร์ตัวเกม (ต้องมีโฟลเดอร์ data หรือ www/data):", var_game_dir, browse_game, status_game)
    create_row(sec1_frame, "2. ไฟล์ Pre-CSV บทสนทนาดิบ (มี Original, Filename, Row):", var_pre_csv, browse_csv, status_csv)
    create_row(sec1_frame, "3. ไฟล์ Plugin Text เดิม (Optional - สำหรับนำข้อความเดิมมา Map):", var_plugin_csv, browse_plugin, status_plugin)

    # =========================================================================
    # SECTION 2: ฐานความรู้และแบบจำลองภาษา Ground Truth (Baseline Knowledge Inputs)
    # =========================================================================
    sec2_frame = ttk.LabelFrame(scrollable_frame, text="🧠 หมวดที่ 2: ฐานความรู้และแบบจำลองภาษาตั้งต้นเดิม (Baseline Ground Truth Models)", padding="10")
    sec2_frame.pack(fill=tk.X, pady=6)

    def browse_profiles():
        p = filedialog.askdirectory(
            title="เลือกโฟลเดอร์ Baseline Character Profiles (เช่น data/tlas/profiles)",
            initialdir=var_profiles_dir.get() or os.path.join(DATA_DIR, "tlas", "profiles")
        )
        if p:
            var_profiles_dir.set(os.path.normpath(p))
            check_all_paths()

    def browse_taxonomy():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Baseline Taxonomy (taxonomy.json) - กำหนดบริบท/ยุคสมัย/สรรพนามของเกม",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_taxonomy_file.get()) if var_taxonomy_file.get() else os.path.join(DATA_DIR, "tlas")
        )
        if p:
            var_taxonomy_file.set(os.path.normpath(p))
            check_all_paths()

    def browse_matrix():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Global Pronoun Matrix (global_pronoun_matrix.json) - ตารางสรรพนามคู่ตัวละคร",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_pronoun_matrix_file.get()) if var_pronoun_matrix_file.get() else os.path.join(DATA_DIR, "tlas")
        )
        if p:
            var_pronoun_matrix_file.set(os.path.normpath(p))
            check_all_paths()

    def browse_alias():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Alias Mapping (alias_mapping.json) - ตารางจับคู่นามแฝงตัวละคร",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_alias_mapping_file.get()) if var_alias_mapping_file.get() else os.path.join(DATA_DIR, "tlas")
        )
        if p:
            var_alias_mapping_file.set(os.path.normpath(p))
            check_all_paths()

    def browse_glossary():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Baseline Master Glossary (tlas_glossary.json)",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_glossary_file.get()) if var_glossary_file.get() else os.path.join(DATA_DIR, "tlas")
        )
        if p:
            var_glossary_file.set(os.path.normpath(p))
            check_all_paths()

    def browse_checkpoint():
        p = filedialog.askopenfilename(
            title="เลือกไฟล์ Translation Checkpoint เดิม (chatgpt_translation_checkpoint.json)",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir=os.path.dirname(var_checkpoint_file.get()) if var_checkpoint_file.get() else os.path.join(DATA_DIR, "tlas")
        )
        if p:
            var_checkpoint_file.set(os.path.normpath(p))
            check_all_paths()

    create_row(sec2_frame, "4. ⭐ โฟลเดอร์โปรไฟล์ตัวละครเดิม (Character Profiles Directory):", var_profiles_dir, browse_profiles, status_profiles)
    create_row(sec2_frame, "5. ⭐ แบบจำลองอนุกรมวิธานบริบท/ยุคสมัย (Taxonomy JSON):", var_taxonomy_file, browse_taxonomy, status_taxonomy)
    create_row(sec2_frame, "6. ⭐ ตารางสรรพนามคู่สนทนา (Global Pronoun Matrix JSON):", var_pronoun_matrix_file, browse_matrix, status_matrix)
    create_row(sec2_frame, "7. ⭐ ตารางการจับคู่นามแฝงตัวละคร (Alias Mapping JSON):", var_alias_mapping_file, browse_alias, status_alias)
    create_row(sec2_frame, "8. คลังคำศัพท์หลักเดิม (Baseline Master Glossary JSON):", var_glossary_file, browse_glossary, status_glossary)
    create_row(sec2_frame, "9. แคชประวัติการแปลเดิม (Baseline Translation Checkpoint JSON):", var_checkpoint_file, browse_checkpoint, status_cp)

    # =========================================================================
    # SECTION 3: โฟลเดอร์ผลลัพธ์ปลายทาง (Target Output Workspace - ADR-024)
    # =========================================================================
    sec3_frame = ttk.LabelFrame(scrollable_frame, text="🎯 หมวดที่ 3: โฟลเดอร์ผลลัพธ์ปลายทาง (Target Output Workspace - ADR-024)", padding="10")
    sec3_frame.pack(fill=tk.X, pady=6)

    def browse_out_dir():
        p = filedialog.askdirectory(
            title="เลือกโฟลเดอร์สำหรับจัดเก็บผลลัพธ์ทั้งหมดของแพตช์นี้ (Target Output Workspace)",
            initialdir=var_out_dir.get() or WORKSPACE_ROOT
        )
        if p:
            var_out_dir.set(os.path.normpath(p))
            curr_filename = os.path.basename(var_out_csv.get()) if var_out_csv.get() else "processed_dialogues_v3.csv"
            var_out_csv.set(os.path.join(os.path.normpath(p), curr_filename))
            check_all_paths()

    def browse_out_csv():
        p = filedialog.asksaveasfilename(
            title="เลือกตำแหน่งบันทึกไฟล์ Processed CSV (8 คอลัมน์)",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            defaultextension=".csv",
            initialdir=os.path.dirname(var_out_csv.get()) if var_out_csv.get() else var_out_dir.get(),
            initialfile=os.path.basename(var_out_csv.get()) if var_out_csv.get() else "processed_dialogues_v3.csv"
        )
        if p:
            var_out_csv.set(os.path.normpath(p))
            check_all_paths()

    create_row(sec3_frame, "10. โฟลเดอร์ผลลัพธ์หลักของโปรเจกต์ (Target Output Directory):", var_out_dir, browse_out_dir, status_out_dir)
    create_row(sec3_frame, "11. ตำแหน่งไฟล์ Processed CSV ปลายทาง (8 คอลัมน์):", var_out_csv, browse_out_csv, status_out_csv)

    # Checkbox สำหรับ Seed Workspace
    chk_seed = ttk.Checkbutton(
        sec3_frame,
        text="📋 Seed Workspace: คัดลอก Baseline Models (Taxonomy, Pronoun Matrix, Profiles, Glossary) ไปยัง Output Workspace (สร้างเป็น Standalone Package)",
        variable=var_seed_workspace
    )
    chk_seed.pack(anchor="w", pady=(6, 4))

    preview_box = ttk.Label(
        sec3_frame,
        text="* ผลลัพธ์ที่จะถูกสร้างขึ้นอัตโนมัติ: <out_dir>\\tlas\\profiles, taxonomy.json, pronoun_matrix.json, glossary.json, scenes.json, checkpoint.json",
        font=("Segoe UI", 8),
        foreground="#666666"
    )
    preview_box.pack(anchor="w", pady=(0, 4))

    # =========================================================================
    # VALIDATION CONTROLLER
    # =========================================================================
    validation_cache = {}

    def check_all_paths():
        # 1. Game
        ok_game, msg_game, sub_game = validate_game_dir(var_game_dir.get())
        status_game.set(("✔ " if ok_game else "✖ ") + msg_game)
        validation_cache["game"] = (ok_game, sub_game)

        # 2. CSV
        ok_csv, msg_csv, rows = validate_pre_csv(var_pre_csv.get())
        status_csv.set(("✔ " if ok_csv else "✖ ") + msg_csv)
        validation_cache["csv"] = (ok_csv, rows)

        # 3. Plugin CSV
        ok_pl, msg_pl = validate_legacy_plugin_csv(var_plugin_csv.get())
        status_plugin.set(("✔ " if ok_pl else "✖ ") + msg_pl)
        validation_cache["plugin"] = ok_pl

        # 4. Baseline Profiles
        ok_prof, msg_prof, count_prof = validate_baseline_profiles(var_profiles_dir.get())
        status_profiles.set(("✔ " if ok_prof else "✖ ") + msg_prof)
        validation_cache["profiles"] = (ok_prof, count_prof)

        # 5. Baseline Taxonomy
        ok_tax, msg_tax = validate_baseline_taxonomy(var_taxonomy_file.get())
        status_taxonomy.set(("✔ " if ok_tax else "✖ ") + msg_tax)
        validation_cache["taxonomy"] = ok_tax

        # 6. Baseline Pronoun Matrix
        ok_mat, msg_mat = validate_baseline_pronoun_matrix(var_pronoun_matrix_file.get())
        status_matrix.set(("✔ " if ok_mat else "✖ ") + msg_mat)
        validation_cache["matrix"] = ok_mat

        # 7. Baseline Alias Mapping
        ok_alias, msg_alias = validate_baseline_alias_mapping(var_alias_mapping_file.get())
        status_alias.set(("✔ " if ok_alias else "✖ ") + msg_alias)
        validation_cache["alias"] = ok_alias

        # 8. Baseline Glossary
        ok_gl, msg_gl, stats_gl = validate_baseline_glossary(var_glossary_file.get())
        status_glossary.set(("✔ " if ok_gl else "✖ ") + msg_gl)
        validation_cache["glossary"] = (ok_gl, stats_gl)

        # 9. Baseline Checkpoint
        ok_cp, msg_cp, count_cp = validate_baseline_checkpoint(var_checkpoint_file.get())
        status_cp.set(("✔ " if ok_cp else "✖ ") + msg_cp)
        validation_cache["checkpoint"] = (ok_cp, count_cp)

        # 10. Output Directory
        ok_out_dir, msg_out_dir = validate_output_workspace(var_out_dir.get())
        status_out_dir.set(("✔ " if ok_out_dir else "✖ ") + msg_out_dir)
        validation_cache["out_dir"] = ok_out_dir

        # 11. Output CSV
        out_csv_val = var_out_csv.get().strip()
        if out_csv_val:
            status_out_csv.set(f"✔ ตำแหน่งไฟล์ CSV ปลายทาง: {os.path.basename(out_csv_val)}")
        else:
            status_out_csv.set("✖ กรุณาระบุชื่อไฟล์ CSV ปลายทาง")

    check_all_paths()

    # =========================================================================
    # CONFIRM & SAVE ACTION
    # =========================================================================
    def on_save():
        check_all_paths()
        ok_game, sub_game = validation_cache.get("game", (False, {}))
        ok_csv, row_count = validation_cache.get("csv", (False, 0))
        ok_out_dir = validation_cache.get("out_dir", False)

        if not ok_game:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาระบุโฟลเดอร์ตัวเกมที่ถูกต้อง (ต้องมี www/data หรือ data)")
            return

        if not ok_csv:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาระบุไฟล์ Pre-CSV บทสนทนาดิบที่ถูกต้อง (ต้องมีคอลัมน์ Original, Filename, Row)")
            return

        if not ok_out_dir or not var_out_dir.get().strip():
            messagebox.showerror("ข้อผิดพลาด", "กรุณาระบุโฟลเดอร์ผลลัพธ์ปลายทาง (Target Output Workspace)")
            return

        data = {
            "game_dir": var_game_dir.get().strip(),
            "game_data_dir": sub_game.get("data_dir", ""),
            "game_plugins_js": sub_game.get("plugins_js", ""),
            "pre_csv": var_pre_csv.get().strip(),
            "pre_csv_rows": row_count,
            "legacy_plugin_csv": var_plugin_csv.get().strip(),
            "baseline_profiles_dir": var_profiles_dir.get().strip(),
            "baseline_taxonomy_json": var_taxonomy_file.get().strip(),
            "baseline_pronoun_matrix_json": var_pronoun_matrix_file.get().strip(),
            "baseline_alias_mapping_json": var_alias_mapping_file.get().strip(),
            "baseline_glossary_json": var_glossary_file.get().strip(),
            "baseline_checkpoint_json": var_checkpoint_file.get().strip(),
            "output_dir": var_out_dir.get().strip(),
            "output_processed_csv": var_out_csv.get().strip(),
        }

        manifest_file, seed_report = save_manifest(data, seed_output_workspace=var_seed_workspace.get())
        print_summary(data, seed_report)

        seed_details = []
        if seed_report.get("profiles_copied", 0) > 0:
            seed_details.append(f"• โปรไฟล์ตัวละคร: {seed_report['profiles_copied']} ไฟล์")
        if seed_report.get("taxonomy_copied"):
            seed_details.append("• แบบจำลอง Taxonomy: คัดลอกสำเร็จ")
        if seed_report.get("matrix_copied"):
            seed_details.append("• ตาราง Pronoun Matrix: คัดลอกสำเร็จ")
        if seed_report.get("glossary_copied"):
            seed_details.append("• คลังคำศัพท์ Glossary: คัดลอกสำเร็จ")

        seed_info_msg = ("\n\n📋 การ Seed Workspace:\n" + "\n".join(seed_details)) if seed_details else ""

        messagebox.showinfo(
            "บันทึกสำเร็จ",
            f"บันทึกตำแหน่งไฟล์ลง Project Manifest เรียบร้อยแล้ว!\n\n"
            f"ไฟล์ Manifest: {manifest_file}\n"
            f"โฟลเดอร์ผลลัพธ์: {data['output_dir']}"
            f"{seed_info_msg}\n\nพร้อมสำหรับขั้นตอนการสกัด Role/Speaker ถัดไป"
        )
        root.destroy()

    btn_frame = ttk.Frame(scrollable_frame)
    btn_frame.pack(fill=tk.X, pady=(16, 12))

    btn_recheck = ttk.Button(btn_frame, text="🔄 รีเฟรช / ตรวจสอบความถูกต้องใหม่", command=check_all_paths)
    btn_recheck.pack(side=tk.LEFT)

    btn_confirm = ttk.Button(
        btn_frame,
        text="💾 บันทึก Path ลง Project Manifest",
        command=on_save
    )
    btn_confirm.pack(side=tk.RIGHT)

    root.mainloop()


# ==============================================================================
# COMMAND LINE INTERFACE (CLI)
# ==============================================================================

def run_cli():
    """โหมด Terminal สำหรับรันผ่าน Command Line"""
    defaults = detect_defaults()
    print("=" * 80)
    print("         ATF PROJECT PATH SETUP & VERIFICATION (CLI MODE v2.0)         ")
    print("=" * 80)

    # 1. Game Dir
    print(f"\n[1] โฟลเดอร์ตัวเกม (Default: {defaults['game_dir']})")
    g_input = input("ระบุโฟลเดอร์เกม [กด Enter เพื่อใช้ Default]: ").strip()
    game_dir = g_input if g_input else defaults["game_dir"]
    ok_game, msg_game, sub_game = validate_game_dir(game_dir)
    print(f"   -> {('✔' if ok_game else '✖')} {msg_game}")

    # 2. Pre-CSV
    print(f"\n[2] ไฟล์ Pre-CSV บทสนทนาดิบ (Default: {defaults['pre_csv']})")
    c_input = input("ระบุไฟล์ CSV [กด Enter เพื่อใช้ Default]: ").strip()
    pre_csv = c_input if c_input else defaults["pre_csv"]
    ok_csv, msg_csv, rows = validate_pre_csv(pre_csv)
    print(f"   -> {('✔' if ok_csv else '✖')} {msg_csv}")

    # 3. Plugin CSV
    print(f"\n[3] ไฟล์ Plugin Text เดิม (Optional - Default: {defaults['legacy_plugin_csv']})")
    p_input = input("ระบุไฟล์ Plugin CSV [กด Enter เพื่อใช้ Default]: ").strip()
    plugin_csv = p_input if p_input else defaults["legacy_plugin_csv"]
    ok_pl, msg_pl = validate_legacy_plugin_csv(plugin_csv)
    print(f"   -> {('✔' if ok_pl else '✖')} {msg_pl}")

    # 4. Baseline Profiles Dir
    print(f"\n[4] ⭐ โฟลเดอร์ Character Profiles เดิม (Default: {defaults['baseline_profiles_dir']})")
    prof_input = input("ระบุโฟลเดอร์ Profiles [กด Enter เพื่อใช้ Default]: ").strip()
    profiles_dir = prof_input if prof_input else defaults["baseline_profiles_dir"]
    ok_prof, msg_prof, count_prof = validate_baseline_profiles(profiles_dir)
    print(f"   -> {('✔' if ok_prof else '✖')} {msg_prof}")

    # 5. Baseline Taxonomy File
    print(f"\n[5] ⭐ แบบจำลองอนุกรมวิธาน Taxonomy เดิม (Default: {defaults['baseline_taxonomy_json']})")
    tax_input = input("ระบุไฟล์ Taxonomy [กด Enter เพื่อใช้ Default]: ").strip()
    taxonomy_file = tax_input if tax_input else defaults["baseline_taxonomy_json"]
    ok_tax, msg_tax = validate_baseline_taxonomy(taxonomy_file)
    print(f"   -> {('✔' if ok_tax else '✖')} {msg_tax}")

    # 6. Baseline Pronoun Matrix File
    print(f"\n[6] ⭐ ตาราง Pronoun Matrix เดิม (Default: {defaults['baseline_pronoun_matrix_json']})")
    mat_input = input("ระบุไฟล์ Pronoun Matrix [กด Enter เพื่อใช้ Default]: ").strip()
    matrix_file = mat_input if mat_input else defaults["baseline_pronoun_matrix_json"]
    ok_mat, msg_mat = validate_baseline_pronoun_matrix(matrix_file)
    print(f"   -> {('✔' if ok_mat else '✖')} {msg_mat}")

    # 7. Baseline Alias Mapping File
    print(f"\n[7] ⭐ ตาราง Alias Mapping เดิม (Default: {defaults['baseline_alias_mapping_json']})")
    alias_input = input("ระบุไฟล์ Alias Mapping [กด Enter เพื่อใช้ Default]: ").strip()
    alias_file = alias_input if alias_input else defaults["baseline_alias_mapping_json"]
    ok_alias, msg_alias = validate_baseline_alias_mapping(alias_file)
    print(f"   -> {('✔' if ok_alias else '✖')} {msg_alias}")

    # 8. Baseline Glossary File
    print(f"\n[8] คลังคำศัพท์หลักเดิม (Default: {defaults['baseline_glossary_json']})")
    gl_input = input("ระบุไฟล์ Glossary [กด Enter เพื่อใช้ Default]: ").strip()
    glossary_file = gl_input if gl_input else defaults["baseline_glossary_json"]
    ok_gl, msg_gl, _ = validate_baseline_glossary(glossary_file)
    print(f"   -> {('✔' if ok_gl else '✖')} {msg_gl}")

    # 9. Baseline Checkpoint
    print(f"\n[9] แคชประวัติการแปลเดิม (Default: {defaults['baseline_checkpoint_json']})")
    cp_input = input("ระบุไฟล์ Checkpoint [กด Enter เพื่อใช้ Default]: ").strip()
    checkpoint_file = cp_input if cp_input else defaults["baseline_checkpoint_json"]
    ok_cp, msg_cp, _ = validate_baseline_checkpoint(checkpoint_file)
    print(f"   -> {('✔' if ok_cp else '✖')} {msg_cp}")

    # 10. Output Directory
    print(f"\n[10] โฟลเดอร์ผลลัพธ์หลักของโปรเจกต์ (Default: {defaults['output_dir']})")
    out_input = input("ระบุโฟลเดอร์ Output Workspace [กด Enter เพื่อใช้ Default]: ").strip()
    output_dir = out_input if out_input else defaults["output_dir"]
    ok_out_dir, msg_out_dir = validate_output_workspace(output_dir)
    print(f"   -> {('✔' if ok_out_dir else '✖')} {msg_out_dir}")

    # 11. Output CSV
    default_out_csv = os.path.join(output_dir, "processed_dialogues_v3.csv")
    print(f"\n[11] ตำแหน่งไฟล์ Processed CSV ปลายทาง (Default: {default_out_csv})")
    out_csv_input = input("ระบุไฟล์ CSV ปลายทาง [กด Enter เพื่อใช้ Default]: ").strip()
    output_processed_csv = out_csv_input if out_csv_input else default_out_csv

    # Seed Check
    seed_ans = input("\nต้องการ Seed / คัดลอก Baseline Models ไปยัง Output Workspace หรือไม่? [y/N]: ").strip().lower()
    do_seed = seed_ans in ["y", "yes"]

    if not ok_game or not ok_csv:
        print("\n❌ ไม่สามารถบันทึกได้ เนื่องจากโฟลเดอร์เกมหรือไฟล์ Pre-CSV ไม่ถูกต้อง")
        sys.exit(1)

    data = {
        "game_dir": game_dir,
        "game_data_dir": sub_game.get("data_dir", ""),
        "game_plugins_js": sub_game.get("plugins_js", ""),
        "pre_csv": pre_csv,
        "pre_csv_rows": rows,
        "legacy_plugin_csv": plugin_csv,
        "baseline_profiles_dir": profiles_dir,
        "baseline_taxonomy_json": taxonomy_file,
        "baseline_pronoun_matrix_json": matrix_file,
        "baseline_alias_mapping_json": alias_file,
        "baseline_glossary_json": glossary_file,
        "baseline_checkpoint_json": checkpoint_file,
        "output_dir": output_dir,
        "output_processed_csv": output_processed_csv,
    }

    manifest_file, seed_report = save_manifest(data, seed_output_workspace=do_seed)
    print_summary(data, seed_report)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        try:
            run_gui()
        except Exception as e:
            print(f"[!] ไม่สามารถเปิด GUI ได้ ({e}) -> สลับเข้าสู่โหมด CLI อัตโนมัติ\n")
            run_cli()
