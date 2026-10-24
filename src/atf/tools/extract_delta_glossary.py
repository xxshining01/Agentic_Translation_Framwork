#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Delta Glossary Extractor
สกัดคำศัพท์เฉพาะ (Actors, Items, Skills, Weapons, Armors, Map Places) จากโฟลเดอร์ www/data ของเกมแพตช์ใหม่
นำมาเทียบกับ tlas_glossary.json เดิม เพื่อค้นหาเฉพาะ "คำศัพท์ใหม่ (Delta)"
และส่งออกเป็น Spreadsheet CSV ให้ผู้ใช้ตรวจทานและกำหนดคำแปลไทย (Manual Curation)
"""

import os
import sys
import json
import csv
from typing import Dict, List, Any, Set

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


def load_manifest() -> Dict[str, Any]:
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(f"ไม่พบไฟล์ Manifest: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_glossary(glossary_path: str) -> Dict[str, Set[str]]:
    """โหลดคำศัพท์เดิมที่มีอยู่ใน Glossary แยกตามหมวดหมู่"""
    existing = {
        "Characters": set(),
        "Items": set(),
        "Skills": set(),
        "Weapons": set(),
        "Armors": set(),
        "Places": set(),
        "System": set()
    }

    if not glossary_path or not os.path.exists(glossary_path):
        return existing

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for cat, items in data.items():
            if isinstance(items, dict):
                norm_cat = cat if cat in existing else "System"
                for term in items.keys():
                    if term and isinstance(term, str):
                        existing[norm_cat].add(term.strip().lower())
    except Exception as e:
        print(f"   [!] คำเตือน: อ่าน Glossary เดิมไม่สำเร็จ: {e}")

    return existing


def extract_delta_terms(data_dir: str, existing_terms: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
    """สแกนไฟล์ฐานข้อมูล JSON ของเกมใหม่และค้นหาคำศัพท์ที่ยังไม่มีใน Glossary"""
    delta_list = []

    # 1. Actors (ชื่อตัวละคร)
    actors_file = os.path.join(data_dir, "Actors.json")
    if os.path.exists(actors_file):
        try:
            with open(actors_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                actors = json.load(f)
            for a in actors:
                if a and isinstance(a, dict):
                    name = a.get("name", "").strip()
                    nickname = a.get("nickname", "").strip()
                    profile = a.get("profile", "").strip()
                    aid = a.get("id", 0)

                    if name and name.lower() not in existing_terms["Characters"]:
                        delta_list.append({
                            "Category": "Characters",
                            "ID": aid,
                            "Original_EN": name,
                            "Initial_TH": name,  # Default fallback
                            "Reference_EN_Description": profile.replace("\n", " "),
                            "Context_Note": f"Actor Name (ID: {aid}, Nick: {nickname})"
                        })
        except Exception as e:
            print(f"   [!] ข้าม Actors.json: {e}")

    # 2. Items (ไอเทม)
    items_file = os.path.join(data_dir, "Items.json")
    if os.path.exists(items_file):
        try:
            with open(items_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                items = json.load(f)
            for it in items:
                if it and isinstance(it, dict):
                    name = it.get("name", "").strip()
                    desc = it.get("description", "").strip()
                    iid = it.get("id", 0)

                    if name and name.lower() not in existing_terms["Items"]:
                        delta_list.append({
                            "Category": "Items",
                            "ID": iid,
                            "Original_EN": name,
                            "Initial_TH": "",
                            "Reference_EN_Description": desc.replace("\n", " "),
                            "Context_Note": f"Item (ID: {iid})"
                        })
        except Exception as e:
            print(f"   [!] ข้าม Items.json: {e}")

    # 3. Skills (สกิล)
    skills_file = os.path.join(data_dir, "Skills.json")
    if os.path.exists(skills_file):
        try:
            with open(skills_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                skills = json.load(f)
            for s in skills:
                if s and isinstance(s, dict):
                    name = s.get("name", "").strip()
                    desc = s.get("description", "").strip()
                    sid = s.get("id", 0)

                    if name and name.lower() not in existing_terms["Skills"]:
                        delta_list.append({
                            "Category": "Skills",
                            "ID": sid,
                            "Original_EN": name,
                            "Initial_TH": "",
                            "Reference_EN_Description": desc.replace("\n", " "),
                            "Context_Note": f"Skill (ID: {sid})"
                        })
        except Exception as e:
            print(f"   [!] ข้าม Skills.json: {e}")

    # 4. Weapons & Armors (อาวุธและชุดเกราะ)
    for eq_file, eq_cat in [("Weapons.json", "Weapons"), ("Armors.json", "Armors")]:
        eq_path = os.path.join(data_dir, eq_file)
        if os.path.exists(eq_path):
            try:
                with open(eq_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    eq_data = json.load(f)
                for eq in eq_data:
                    if eq and isinstance(eq, dict):
                        name = eq.get("name", "").strip()
                        desc = eq.get("description", "").strip()
                        eid = eq.get("id", 0)

                        if name and name.lower() not in existing_terms[eq_cat]:
                            delta_list.append({
                                "Category": eq_cat,
                                "ID": eid,
                                "Original_EN": name,
                                "Initial_TH": "",
                                "Reference_EN_Description": desc.replace("\n", " "),
                                "Context_Note": f"{eq_cat} (ID: {eid})"
                            })
            except Exception as e:
                print(f"   [!] ข้าม {eq_file}: {e}")

    # 5. Places (MapInfos - แผนที่/สถานที่)
    maps_file = os.path.join(data_dir, "MapInfos.json")
    if os.path.exists(maps_file):
        try:
            with open(maps_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                maps = json.load(f)
            for m in maps:
                if m and isinstance(m, dict):
                    name = m.get("name", "").strip()
                    mid = m.get("id", 0)

                    if name and name.lower() not in existing_terms["Places"]:
                        delta_list.append({
                            "Category": "Places",
                            "ID": mid,
                            "Original_EN": name,
                            "Initial_TH": "",
                            "Reference_EN_Description": "",
                            "Context_Note": f"Map Location (ID: {mid})"
                        })
        except Exception as e:
            print(f"   [!] ข้าม MapInfos.json: {e}")

    return delta_list


def main():
    print("=" * 80)
    print("         ATF DELTA GLOSSARY EXTRACTOR & CALIBRATION TOOL         ")
    print("=" * 80)

    manifest = load_manifest()
    data_dir = manifest.get("game_data_directory")
    legacy_glossary = manifest.get("legacy_glossary_json")
    output_processed_csv = manifest.get("output_processed_csv")

    if not data_dir or not os.path.exists(data_dir):
        print(f"❌ ไม่พบโฟลเดอร์ Data ของเกม: {data_dir}")
        sys.exit(1)

    # กำหนดโฟลเดอร์ปลายทางให้อยู่ในโฟลเดอร์ของเวอร์ชันใหม่
    if output_processed_csv:
        out_dir = os.path.dirname(output_processed_csv)
    else:
        out_dir = os.path.join(WORKSPACE_ROOT, "data")

    out_csv = os.path.join(out_dir, "delta_glossary_review.csv")
    backup_workspace_csv = os.path.join(WORKSPACE_ROOT, "data", "delta_glossary_review.csv")

    print(f"[*] Game Data Directory: {data_dir}")
    print(f"[*] Baseline Glossary:   {legacy_glossary}")
    print(f"[*] Output Review CSV:   {out_csv}\n")

    print("[1/2] กำลังโหลดคลังศัพท์เดิมจาก Baseline Glossary...")
    existing = load_existing_glossary(legacy_glossary)
    total_existing = sum(len(v) for v in existing.values())
    print(f"   -> โหลดคำศัพท์เดิมทั้งหมด: {total_existing:,} คำ")
    for cat, terms in existing.items():
        if terms:
            print(f"      • {cat:<12}: {len(terms):,} คำ")

    print("\n[2/2] กำลังสแกนฐานข้อมูลเกมแพตช์ใหม่ และค้นหาคำศัพท์ใหม่ (Delta)...")
    delta_items = extract_delta_terms(data_dir, existing)
    print(f"   -> พบคำศัพท์ใหม่ที่ยังไม่มีใน Glossary: {len(delta_items):,} คำ!\n")

    # บันทึกเป็น CSV สำหรับ Review (บันทึกทั้งปลายทางและสำเนาใน data/)
    fieldnames = ["Category", "ID", "Original_EN", "Initial_TH", "Reference_EN_Description", "Context_Note"]

    for target_path in [out_csv, backup_workspace_csv]:
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(delta_items)
        except Exception:
            pass

    print("=" * 80)
    print("                         SUMMARY REPORT                         ")
    print("=" * 80)
    print(f"💾 ส่งออกตารางสำหรับตรวจสอบและใส่คำแปลไทยล่วงหน้าที่:")
    print(f"👉 {out_csv}")
    print("-" * 80)

    cat_counts = {}
    for it in delta_items:
        c = it["Category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    print("📊 รายการคำศัพท์ใหม่แยกตามหมวดหมู่:")
    for c, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {c:<15}: {cnt:,} รายการ")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
