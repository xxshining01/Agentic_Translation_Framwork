#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF RPG Maker CSV Enricher (Role, Speaker & Displayable Classifier)
สคริปต์สกัดและเติมคอลัมน์ Role, Speaker, Displayable ให้กับไฟล์ Pre-CSV (8 คอลัมน์มาตรฐาน)
โดยอ่านค่าจาก data/project_manifest.json และวิเคราะห์ Event Command จาก www/data/*.json ของตัวเกมจริง
"""

import os
import sys
import csv
import json
import re
from collections import defaultdict, Counter
from typing import Dict, Set, Tuple, List, Any

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")

# ลำดับความสำคัญของบทบาท (Role Priority: ค่าน้อย = ความสำคัญสูงสุด)
ROLE_PRIORITY = {
    "Dialogue/Story": 1,
    "Plugin Dialogue": 2,
    "Choices Option": 3,
    "Choice Branch": 4,
    "System Term": 5,
    "System Message": 5,
    "Message Speaker Name": 6,
    "Entity Name": 7,
    "Description": 8,
    "Profile": 9,
    "Battle Message": 10,
    "Map Display Name": 11,
    "Change Name": 12,
    "Change Nickname": 12,
    "Change Profile": 12,
    "Developer Comment": 13,
    "Script Code": 14,
    "Plugin Command": 15,
    "Internal Variable/Switch": 16,
    "Asset Name": 17,
    "Event Name": 18,
    "Common Event Name": 18,
    "Troop Name": 18,
    "Control Variables": 19,
    "Note/Metadata": 20,
    "Macro / Image": 21,
    "Field: ": 22,
    "List Item": 23,
    "System Setting": 24,
    "Unknown": 99,
    "Unmatched": 100
}


def get_priority(role_name: str) -> int:
    if role_name.startswith("Field: "):
        return ROLE_PRIORITY["Field: "]
    return ROLE_PRIORITY.get(role_name, 99)


def is_just_macro(text: str) -> bool:
    """ตรวจสอบว่าข้อความเป็นเพียงรหัสควบคุม/รูปภาพ โดยไม่มีตัวอักษรเนื้อหาหรือไม่"""
    t = text.strip()
    cleaned = re.sub(r'\\[a-zA-Z]+\[[^\]]*\]', '', t)
    cleaned = re.sub(r'\\[!\\.|><\^]', '', cleaned)
    cleaned = re.sub(r'\\n', '', cleaned)
    if not re.search(r'\w', cleaned):
        return True
    return False


def build_string_roles(data: Any, filename: str, roles_map: Dict[str, Set[Tuple[str, str]]], context: str = ""):
    """แกะโครงสร้าง RPG Maker JSON เพื่อจัดหมวดหมู่ Role และ Displayable ของแต่ละข้อความ"""
    if isinstance(data, dict):
        if "code" in data and "parameters" in data:
            code = data["code"]
            for p in data["parameters"]:
                if isinstance(p, str) and p.strip():
                    role = "Event Command"
                    display = "No"

                    if code in (401, 405):  # Show Text
                        role = "Dialogue/Story"
                        display = "Yes"
                    elif code == 102:  # Show Choices
                        role = "Choices Option"
                        display = "Yes"
                        if isinstance(p, list):
                            for choice_text in p:
                                if isinstance(choice_text, str) and choice_text.strip():
                                    c_role = "Macro / Image" if is_just_macro(choice_text) else role
                                    c_disp = "No" if is_just_macro(choice_text) else display
                                    roles_map[choice_text.strip()].add((c_role, c_disp))
                        continue
                    elif code == 402:  # When [Choice]
                        role = "Choice Branch"
                        display = "Yes"
                    elif code in (108, 408):  # Comment
                        role = "Developer Comment"
                        display = "No"
                    elif code in (355, 655):  # Script Call
                        role = "Script Code"
                        display = "No"
                    elif code == 356:  # Plugin Command
                        p_lower = p.lower()
                        if p_lower.startswith("gabtext") or p_lower.startswith("gabname") or p_lower.startswith("msg"):
                            role = "Plugin Dialogue"
                            display = "Yes"
                        else:
                            role = "Plugin Command"
                            display = "No"
                    elif code == 122:  # Control Variables
                        role = "Control Variables"
                        display = "No"
                    elif code == 320:  # Change Name
                        role = "Change Name"
                        display = "Yes"
                    elif code == 324:  # Change Nickname
                        role = "Change Nickname"
                        display = "Yes"
                    elif code == 325:  # Change Profile
                        role = "Change Profile"
                        display = "Yes"
                    elif code == 101:  # Show Text Header / Speaker
                        role = "Message Speaker Name"
                        display = "Yes"

                    if display == "Yes" and is_just_macro(p):
                        role = "Macro / Image"
                        display = "No"

                    roles_map[p.strip()].add((role, display))

        # ตรวจสอบ Dict Keys ต่างๆ
        for k, v in data.items():
            if isinstance(v, str) and v.strip():
                k_lower = k.lower()
                role = f"Field: {k}"
                display = "No"

                if k_lower == "name":
                    if filename.startswith("Map") and not filename == "MapInfos":
                        role = "Event Name"
                        display = "No"
                    elif filename == "CommonEvents":
                        role = "Common Event Name"
                        display = "No"
                    elif filename == "Troops":
                        role = "Troop Name"
                        display = "No"
                    else:
                        role = "Entity Name"
                        display = "Yes"  # Actors, Items, Weapons, Skills, Classes
                elif k_lower == "displayname" and filename.startswith("Map"):
                    role = "Map Display Name"
                    display = "Yes"
                elif k_lower == "description":
                    role = "Description"
                    display = "Yes"
                elif k_lower == "note":
                    role = "Note/Metadata"
                    display = "No"
                elif k_lower == "profile":
                    role = "Profile"
                    display = "Yes"
                elif k_lower.startswith("message"):
                    role = "Battle Message"
                    display = "Yes"
                elif filename == "System":
                    if k_lower == "gametitle":
                        role = "Game Title"
                        display = "Yes"
                    elif k_lower == "currencyunit":
                        role = "System Term"
                        display = "Yes"
                    elif context == "messages":
                        role = "System Message"
                        display = "Yes"
                elif k in ["bgm", "bgs", "me", "se", "characterName", "faceName", "battlerName", "parallaxName", "title1Name", "title2Name"]:
                    role = "Asset Name"
                    display = "No"

                roles_map[v.strip()].add((role, display))
            else:
                build_string_roles(v, filename, roles_map, context=k)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                role = "List Item"
                display = "No"

                if filename == "System":
                    if context in ["switches", "variables"]:
                        role = "Internal Variable/Switch"
                        display = "No"
                    elif context in ["terms", "messages", "elements", "skillTypes", "weaponTypes", "armorTypes", "equipTypes"]:
                        role = "System Term"
                        display = "Yes"
                    else:
                        role = "System Setting"
                        display = "No"
                elif filename in ["Disciplines", "Recipes"]:
                    if context.lower() in ["categories", "category"]:
                        role = "Crafting Category"
                        display = "Yes"

                roles_map[item.strip()].add((role, display))
            else:
                build_string_roles(item, filename, roles_map, context=context)


def get_best_role(found_roles: Set[Tuple[str, str]]) -> Tuple[str, str]:
    """เลือก Role ที่มี Priority สูงสุด"""
    sorted_roles = sorted(found_roles, key=lambda x: get_priority(x[0]))
    if sorted_roles:
        return sorted_roles[0]
    return ("Unknown", "Unknown")


def extract_speaker(original_text: str) -> str:
    """สกัดชื่อตัวละครผู้พูดจาก Tag ในข้อความ"""
    # 1. รูปแบบ \n<Name:> หรือ \n<Name>
    m1 = re.search(r'\\n<([^>:]+):?>', original_text)
    if m1:
        return m1.group(1).strip()
    # 2. รูปแบบ <Name:> หรือ <Name> ต้นประโยค
    m2 = re.search(r'^<([^>:]+):?>', original_text.strip())
    if m2:
        return m2.group(1).strip()
    # 3. รูปแบบ [Name]
    m3 = re.search(r'^\s*\[([^\]]+)\]', original_text.strip())
    if m3:
        candidate = m3.group(1).strip()
        # ข้ามถ้าเป็น macro control code เช่น [1] หรือ [C1]
        if not re.match(r'^[0-9]+$', candidate):
            return candidate
    return ""


def main():
    print("=" * 80)
    print("      ATF RPG MAKER CSV ENRICHER: ROLE, SPEAKER & DISPLAYABLE      ")
    print("=" * 80)

    # 1. โหลดการตั้งค่าจาก Manifest
    if not os.path.exists(MANIFEST_PATH):
        print(f"❌ ไม่พบไฟล์ Manifest ที่: {MANIFEST_PATH}")
        print("💡 กรุณารันคำสั่ง 'python setup_paths.py' เพื่อเลือกตำแหน่งไฟล์ก่อน")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    csv_in = manifest.get("raw_pre_csv")
    data_dir = manifest.get("game_data_directory")
    csv_out = manifest.get("output_processed_csv")

    if not csv_in or not os.path.exists(csv_in):
        print(f"❌ ไม่พบไฟล์ Pre-CSV ตามที่ระบุใน Manifest: {csv_in}")
        sys.exit(1)

    if not data_dir or not os.path.exists(data_dir):
        print(f"❌ ไม่พบโฟลเดอร์เกม Data ตามที่ระบุใน Manifest: {data_dir}")
        sys.exit(1)

    print(f"[*] Input Pre-CSV:   {csv_in}")
    print(f"[*] Game Data Dir:   {data_dir}")
    print(f"[*] Target Output:   {csv_out}\n")

    # 2. โหลดและสร้าง Roles Map จาก JSON ของตัวเกมจริงทั้งหมด
    print("[1/3] กำลังสแกนไฟล์ JSON ของเกมทั้งหมด และสร้าง Event Command Map...")
    json_cache: Dict[str, Dict[str, Set[Tuple[str, str]]]] = {}
    json_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]

    for idx, f_name in enumerate(json_files, 1):
        name = f_name[:-5]
        f_path = os.path.join(data_dir, f_name)
        try:
            with open(f_path, "r", encoding="utf-8-sig", errors="ignore") as jf:
                data = json.load(jf)
                roles_map = defaultdict(set)
                build_string_roles(data, name, roles_map)
                json_cache[name] = roles_map
        except Exception as e:
            print(f"   [!] ข้ามไฟล์ {f_name} เนื่องจากอ่านไม่สำเร็จ: {e}")

    print(f"   -> โหลดโครงสร้างเกมสำเร็จครบ {len(json_cache)} ไฟล์ JSON!\n")

    # 3. ประมวลผลตาราง CSV ทีละบรรทัด พร้อมระบุ Role, Speaker, Displayable
    print("[2/3] กำลังจับคู่และเติมคอลัมน์ Role, Speaker, Displayable ลงใน CSV...")
    role_counter = Counter()
    disp_counter = Counter()
    note_counter = Counter()
    total_rows = 0

    os.makedirs(os.path.dirname(csv_out), exist_ok=True)

    with open(csv_in, "r", encoding="utf-8-sig", errors="ignore") as fin, \
         open(csv_out, "w", encoding="utf-8-sig", newline="") as fout:

        reader = csv.reader(fin)
        writer = csv.writer(fout)

        headers = next(reader, None)
        if not headers:
            print("❌ ไฟล์ CSV ต้นฉบับไม่มี Header")
            sys.exit(1)

        # ตัดคอลัมน์ Role/Speaker/Displayable เดิมออกหากมี เพื่อสร้างใหม่ให้ถูกต้อง 100%
        clean_headers = []
        for h in headers:
            h_clean = h.strip()
            if h_clean in ["Role", "Speaker", "Displayable"]:
                break
            clean_headers.append(h_clean)

        # เติม 3 คอลัมน์มาตรฐาน
        out_headers = clean_headers + ["Role", "Speaker", "Displayable"]
        writer.writerow(out_headers)

        for row_idx, row in enumerate(reader, 1):
            total_rows += 1
            if len(row) < 3:
                writer.writerow(row)
                continue

            original = row[0]
            initial = row[1] if len(row) > 1 else ""
            filename = row[2] if len(row) > 2 else ""
            row_num = row[3] if len(row) > 3 else ""
            note = row[4] if len(row) > 4 else ""

            clean_row = [original, initial, filename, row_num, note]

            # นับสถิติ Note สำหรับการอัปเดตเวอร์ชัน
            note_trimmed = note.strip()
            if note_trimmed:
                note_counter[note_trimmed] += 1

            role = "Unknown"
            displayable = "Unknown"
            speaker = ""

            # ดึง Speaker
            speaker = extract_speaker(original)

            # ค้นหาใน Cache ของ Filename นั้น
            if filename in json_cache:
                roles_map = json_cache[filename]
                search_str = original.strip()
                found_roles = set()

                if search_str in roles_map:
                    found_roles = roles_map[search_str].copy()
                else:
                    # ค้นหาแบบรายบรรทัด (เผื่อติด In-line newlines)
                    lines = [l.strip() for l in search_str.split("\n") if l.strip()]
                    for l in lines:
                        if l in roles_map:
                            found_roles.update(roles_map[l])

                    if not found_roles and lines:
                        first_line = lines[0]
                        for k, v in roles_map.items():
                            if first_line in k:
                                found_roles.update(v)

                if found_roles:
                    role, displayable = get_best_role(found_roles)
                else:
                    role = "Unmatched"
                    displayable = "No"
            else:
                # กรณี Filename ไม่อยู่ใน JSON หรือเป็นไฟล์พิเศษ
                if "Actors" in filename or "Items" in filename or "Skills" in filename:
                    role = "Entity Name"
                    displayable = "Yes"
                else:
                    role = "Unmatched"
                    displayable = "No"

            # ตรวจสอบข้อยกเว้น: หากเป็นแถวที่ถูกลบออกในไฟล์ใหม่
            if "ถูกลบออก" in note:
                displayable = "No"
                role = "Deleted / Deprecated"

            role_counter[role] += 1
            disp_counter[displayable] += 1

            clean_row.extend([role, speaker, displayable])
            writer.writerow(clean_row)

            if total_rows % 20000 == 0:
                print(f"   ...ประมวลผลแล้ว {total_rows:,} แถว...")

    print(f"\n[3/3] สำเร็จเรียบร้อย! ส่งออกตาราง CSV มาตรฐาน 8 คอลัมน์:")
    print(f"👉 ไฟล์ผลลัพธ์: {csv_out}")

    # 4. อัปเดต Manifest ด้วยสถิติใหม่
    manifest["processed_csv_rows"] = total_rows
    manifest["displayable_yes_rows"] = disp_counter.get("Yes", 0)
    manifest["displayable_no_rows"] = disp_counter.get("No", 0)
    manifest["new_inserted_rows"] = sum(count for k, count in note_counter.items() if "แทรกเข้ามา" in k or "ใหม่" in k)

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 5. พิมพ์สรุปผลลัพธ์
    print("\n" + "=" * 80)
    print("                    ATF CSV ENRICHER SUMMARY REPORT                    ")
    print("=" * 80)
    print(f"📊 จำนวนแถวทั้งหมด:              {total_rows:,} แถว")
    print(f"🟢 ต้องแปล (Displayable == 'Yes'):  {disp_counter.get('Yes', 0):,} แถว (เข้าคิวแปล)")
    print(f"⚪ ข้าม (Displayable == 'No'):     {disp_counter.get('No', 0):,} แถว (ขยะระบบ/รหัสเกม)")
    print("-" * 80)
    print("📌 สรุปบทบาทแถวข้อความ (Top Roles):")
    for r_name, r_cnt in role_counter.most_common(8):
        print(f"   • {r_name:<28}: {r_cnt:,} แถว")
    print("-" * 80)
    print("📌 สรุปสถานะการอัปเดตเวอร์ชันจากคอลัมน์ Note:")
    if note_counter:
        for n_name, n_cnt in note_counter.most_common(6):
            print(f"   • {n_name:<28}: {n_cnt:,} แถว")
    else:
        print("   (ไม่พบ Note การเปลี่ยนแปลง - นับเป็นฐานข้อมูลใหม่ทั้งหมด)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
