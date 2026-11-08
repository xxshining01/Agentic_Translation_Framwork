#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Master Glossary & Character Whitelist Builder
สร้าง tlas_glossary.json ที่มีรายชื่อตัวละครครบ 100% จากผลการสแกน
และสร้าง character_whitelist.json สำหรับตัวละครหลักตามข้อกำหนด ADR-035
"""

import os
import sys
import json

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
SCANNED_JSON = os.path.join(WORKSPACE_ROOT, "data", "tlas", "scanned_speakers.json")
OUTPUT_GLOSSARY = os.path.join(WORKSPACE_ROOT, "data", "tlas", "tlas_glossary.json")
OUTPUT_WHITELIST = os.path.join(WORKSPACE_ROOT, "data", "tlas", "character_whitelist.json")

# พจนานุกรมคำแปลภาษาไทยมาตรฐาน 1:1 ของตัวละครในเกม 離れ木の5日間+
CHARACTER_TRANSLATIONS = {
    "凛": {
        "th": "ริน",
        "gender": "FEMALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Heroine / Wife / Main Protagonist"
    },
    "遠藤": {
        "th": "เอ็นโด",
        "gender": "MALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Innkeeper / Main Antagonist"
    },
    "夫": {
        "th": "สามี",
        "gender": "MALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Protagonist / Husband"
    },
    "西原": {
        "th": "นิชิฮาระ",
        "gender": "MALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Ex-boyfriend / Antagonist"
    },
    "？？？": {
        "th": "？？？",
        "gender": "UNKNOWN",
        "role_category": "System",
        "analysis_target": False,
        "reason": "Anonymous speaker tag placeholder"
    },
    "学生B": {
        "th": "นักศึกษา B",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Secondary mob student B"
    },
    "受付のおばあさん": {
        "th": "คุณยายพนักงานต้อนรับ",
        "gender": "FEMALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Elderly innkeeper receptionist"
    },
    "学生A": {
        "th": "นักศึกษา A",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Secondary mob student A"
    },
    "孫": {
        "th": "หลานชาย",
        "gender": "MALE",
        "role_category": "Core",
        "analysis_target": True,
        "reason": "Receptionist's young grandson / Shota"
    },
    "学生2人": {
        "th": "นักศึกษา 2 คน",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Two mob students group line"
    },
    "チャラそうなやつ①": {
        "th": "หนุ่มเพลย์บอย ①",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Flirty street mob 1"
    },
    "チャラそうなやつ②": {
        "th": "หนุ่มเพลย์บอย ②",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Flirty street mob 2"
    },
    "学生": {
        "th": "นักศึกษา",
        "gender": "MALE",
        "role_category": "Ambient",
        "analysis_target": False,
        "reason": "Single mob student"
    }
}

# คำศัพท์ระบบ / ตัวเลือกเมนู
SYSTEM_CHOICES_TRANSLATIONS = {
    "はい": {"th": "ใช่", "type": "SystemChoice", "enforce": True},
    "いいえ": {"th": "ไม่ใช่", "type": "SystemChoice", "enforce": True},
    "やめる": {"th": "ยกเลิก", "type": "SystemChoice", "enforce": True}
}


def build_glossary():
    print("=" * 80)
    print("      ATF MASTER GLOSSARY & CHARACTER WHITELIST BUILDER (ADR-035)      ")
    print("=" * 80)

    if not os.path.exists(SCANNED_JSON):
        print(f"❌ Error: ไม่พบไฟล์ผลการสแกน {SCANNED_JSON}")
        sys.exit(1)

    with open(SCANNED_JSON, "r", encoding="utf-8") as f:
        scan_data = json.load(f)

    speakers_list = scan_data.get("speakers", [])
    print(f"[*] Loaded {len(speakers_list)} distinct speakers from scanned_speakers.json")

    glossary = {
        "_metadata": {
            "version": "4.2",
            "game": "離れ木の5日間+",
            "source_language": "ja",
            "target_language": "th",
            "adr_compliance": "ADR-035 (Decoupled Glossary vs Profile)"
        },
        "Characters": {},
        "Choices": SYSTEM_CHOICES_TRANSLATIONS,
        "Places": {
            "民宿　離れ木": {"th": "เกสต์เฮาส์ ฮานาเรกิ", "type": "ProperNoun", "enforce": True},
            "露天風呂": {"th": "บ่อน้ำร้อนกลางแจ้ง", "type": "CommonNoun", "enforce": True},
            "縁側": {"th": "เฉลียงทางเดิน", "type": "CommonNoun", "enforce": True}
        },
        "Items": {},
        "Skills": {}
    }

    whitelist = []

    for item in speakers_list:
        tag = item["speaker_tag"]
        count = item["dialogue_count"]

        # ดึงการตั้งค่าแปลภาษาไทย
        info = CHARACTER_TRANSLATIONS.get(tag, {
            "th": tag,
            "gender": "UNKNOWN",
            "role_category": "Ambient",
            "analysis_target": False,
            "reason": "Scanned NPC"
        })

        is_target = info["analysis_target"]

        glossary["Characters"][tag] = {
            "th": info["th"],
            "type": "ProperNoun" if is_target else "CommonNoun",
            "role_category": info["role_category"],
            "analysis_target": is_target,
            "gender": info["gender"],
            "enforce": True,
            "dialogue_count": count,
            "aliases": [],
            "reason": info["reason"]
        }

        if is_target:
            whitelist.append({
                "name": tag,
                "th": info["th"],
                "gender": info["gender"],
                "role_category": info["role_category"],
                "dialogue_count": count,
                "reason": info["reason"]
            })

    # 1. บันทึก Master Glossary
    os.makedirs(os.path.dirname(OUTPUT_GLOSSARY), exist_ok=True)
    with open(OUTPUT_GLOSSARY, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)

    # 2. บันทึก Core Character Whitelist
    with open(OUTPUT_WHITELIST, "w", encoding="utf-8") as f:
        json.dump({
            "_description": "Core Character Whitelist for Profile Generation (ADR-035 Compliance). Ambient NPCs have ZERO profile files.",
            "total_qualified_characters": len(whitelist),
            "characters": whitelist
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("                    BUILD SUMMARY & AUDIT TRAIL                     ")
    print("=" * 80)
    print(f"📖 Master Glossary Characters Enrolled: {len(glossary['Characters'])} คน (ครอบคลุม 100%)")
    print(f"🎯 Core Character Whitelist Qualified:   {len(whitelist)} คน (เฉพาะตัวสำคัญที่มีบทบาท)")
    print("-" * 80)
    print(f"{'Speaker Tag':<20} | {'Thai Translation':<22} | {'Role':<12} | {'Profile Status'}")
    print("-" * 80)
    for c in whitelist:
        print(f"{c['name']:<20} | {c['th']:<22} | {c['role_category']:<12} | ✅ Create Profile")
    for item in speakers_list:
        tag = item["speaker_tag"]
        if tag not in [w["name"] for w in whitelist]:
            th = glossary["Characters"][tag]["th"]
            print(f"{tag:<20} | {th:<22} | {'Ambient':<12} | ⛔ Clean Passthrough (No File)")
    print("=" * 80)
    print(f"💾 Saved Master Glossary:  {OUTPUT_GLOSSARY}")
    print(f"💾 Saved Character Whitelist: {OUTPUT_WHITELIST}\n")


if __name__ == "__main__":
    build_glossary()
