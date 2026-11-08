#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Contextual SFX & Custom Dictionary Extractor (v6.0 - Zero Hardcode)
=======================================================================
สกัดและจัดกลุ่มเสียงเอฟเฟกต์ (Onomatopoeia / SFX) และคำศัพท์เฉพาะทาง / แสลง (Dic Glossary)
จากข้อความบทสนทนาจริงของตัวเกม

สถาปัตยกรรม:
- Grounded Scanning: สแกนบทสนทนาจริงใน CSV และ Scene Packets
- Template-Guided Disambiguation: อ้างอิงแม่แบบสากล templates/sfx_glossary.template.json
  เพื่อจับคู่กฎการแปลตามบริบท (เช่น はぁ -> เฮ้อ... / แฮ่ก... / ฮ่าห์...)
- Game-Specific Jargon Curation: สกัดคำในเครื่องหมายเน้นย้ำ หรือคำเฉพาะ เพื่อบรรจุลง dic_glossary.json
- Target Deliverables: บันทึก sfx_glossary.json และ dic_glossary.json ลงใน output_tlas_dir
"""

import os
import sys
import json
import csv
import re
from collections import Counter
from typing import Dict, Any, List, Set

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")
TEMPLATE_SFX_PATH = os.path.join(WORKSPACE_ROOT, "templates", "sfx_glossary.template.json")
TEMPLATE_DIC_PATH = os.path.join(WORKSPACE_ROOT, "templates", "dic_glossary.template.json")


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


def extract_sfx_and_dic():
    manifest = load_manifest()
    csv_path = manifest.get("raw_pre_csv") or manifest.get("output_processed_csv", "")
    tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
    
    output_sfx_path = os.path.join(tlas_dir, "sfx_glossary.json")
    output_dic_path = os.path.join(tlas_dir, "dic_glossary.json")

    print("=" * 80)
    print("      ATF CONTEXTUAL SFX & CUSTOM DICTIONARY EXTRACTOR (v6.0)      ")
    print("=" * 80)
    print(f"[*] Source CSV: {csv_path}")
    print(f"[*] Target SFX Out: {output_sfx_path}")
    print(f"[*] Target Dic Out: {output_dic_path}")

    # 1. โหลด Template SFX
    sfx_template = load_json_safe(TEMPLATE_SFX_PATH) or {}
    known_sfx = sfx_template.get("sfx_lexicon", {})

    # 2. สแกนข้อความใน CSV
    dialogue_texts = []
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():
                    dialogue_texts.append(row[0].strip())

    print(f"[*] Scanned {len(dialogue_texts):,} dialogue lines from game script.")

    # 3. จับคู่ SFX ที่พบในเกมจริง
    detected_sfx = {}
    sfx_counts = Counter()

    for text in dialogue_texts:
        # สแกนหา Onomatopoeia ที่ขึ้นต้น หรืออยู่ในประโยค
        for sfx_word, sfx_rule in known_sfx.items():
            if sfx_word in text:
                sfx_counts[sfx_word] += 1
                if sfx_word not in detected_sfx:
                    detected_sfx[sfx_word] = sfx_rule

    print(f"[✔] Detected {len(detected_sfx)} Active Onomatopoeia patterns in script:")
    for w, c in sfx_counts.most_common(10):
        print(f"    - 【{w}】 : Found {c} times | Type: {detected_sfx[w].get('type')}")

    # บันทึก sfx_glossary.json
    sfx_output_data = {
        "_metadata": {
            "version": "6.0",
            "description": "Active Contextual Onomatopoeia & Sound Effect Glossary",
            "total_active_patterns": len(detected_sfx)
        },
        "sfx_lexicon": detected_sfx
    }
    os.makedirs(os.path.dirname(output_sfx_path), exist_ok=True)
    with open(output_sfx_path, "w", encoding="utf-8") as f:
        json.dump(sfx_output_data, f, ensure_ascii=False, indent=2)

    # 4. สกัด Custom Dictionary (Idioms / Quoted terms / Special Jargon)
    dic_template = load_json_safe(TEMPLATE_DIC_PATH) or {}
    dic_entries = dic_template.get("dictionary", {})

    # สแกนหาคำที่อยู่ในเครื่องหมายคำพูด 「...」 หรือ 『...』 ที่มีความยาวไม่เกิน 10 ตัวอักษร
    quoted_terms = Counter()
    for text in dialogue_texts:
        matches = re.findall(r'「([^」\n]{2,10})」|『([^』\n]{2,10})』', text)
        for m in matches:
            term = m[0] or m[1]
            if term and not re.search(r'[\.!\?]', term):
                quoted_terms[term] += 1

    custom_dic = {}
    for term, cnt in quoted_terms.most_common(20):
        if cnt >= 2:  # ปรากฏซ้ำ 2 ครั้งขึ้นไป ถือเป็นศัพท์เฉพาะหรือวลีเน้นย้ำ
            custom_dic[term] = {
                "ja": term,
                "th": "",
                "frequency": cnt,
                "category": "Quoted Phrase / Potential Lore Term",
                "notes": f"Appears {cnt} times in game dialogues."
            }

    dic_output_data = {
        "_metadata": {
            "version": "6.0",
            "description": "ATF Game-Specific Jargon & Custom Dictionary",
            "total_terms": len(custom_dic)
        },
        "dictionary": custom_dic
    }

    with open(output_dic_path, "w", encoding="utf-8") as f:
        json.dump(dic_output_data, f, ensure_ascii=False, indent=2)

    print(f"[✔] Extracted {len(custom_dic)} Special Recurring Terms into Custom Dictionary.")
    print("=" * 80)
    print(f"💾 Saved Active SFX Glossary: {output_sfx_path}")
    print(f"💾 Saved Custom Dictionary:  {output_dic_path}\n")


if __name__ == "__main__":
    extract_sfx_and_dic()
