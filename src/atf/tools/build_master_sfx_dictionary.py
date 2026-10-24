#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Master Sound Effect Dictionary Builder & Cluster Analyzer (v2.0 Positional Gap Alignment)
=============================================================================================
ระบบสำรวจและจัดกลุ่มคำแทนเสียงจากข้อมูลจริง 1,632 แถวแบบ Zero-Bias (Bottom-Up)
พร้อมนวัตกรรม 'Positional Gap Alignment' เพื่อแก้ปัญหาการแยกคำไม่ออกเมื่อไม่มี ** ครอบ

หลักการทำงาน:
1. [Verified Harvester]:
   - สแกนแถวที่ Initial มี *...* ครอบอยู่แล้ว เพื่อรวบรวมคำแปลที่แน่นอน 100% (High Confidence)
2. [Positional Gap Alignment (PGA)]:
   - สำหรับแถวที่ Initial "ไม่มี ** ครอบ":
   - แบ่งประโยคออกตาม Control Code (\\., \\|, \\!, etc.) หรือระบุ Left/Right Context รอบคำแทนเสียง
   - คำนวนหา 'คำที่ตกค้างอยู่ในช่องว่างตรงกับตำแหน่ง SFX' (Residual Gap Extraction)
   - กรองคำที่เป็นบทพูดหรือ Stopwords ออก เหลือเฉพาะคำแทนเสียงภาษาไทยที่แท้จริง
3. [Phonetic & Root Clustering]:
   - รวมทุกการสะกด (slurp, slurrrp, ssslurrpp ➡️ slurp) ไว้ในรากศัพท์เดียวกัน
4. [Master Dictionary & Catalog Export]:
   - master_sfx_dictionary.json
   - master_sfx_catalog.md
"""

import os
import sys
import re
import csv
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set, Optional
from collections import defaultdict, Counter

# บังคับ UTF-8 output บน Windows Terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

SFX_REGEX = re.compile(r'\*([^*]+)\*')

# Stopwords ภาษาไทยที่ห้ามดึงเป็นคำแทนเสียงเด็ดขาด
THAI_STOPWORDS = {
    "ฉัน", "เธอ", "เขา", "เรา", "พวกเรา", "นาย", "คุณ", "มึง", "กู", "มัน",
    "ไป", "มา", "ไม่", "ใช่", "ได้", "ให้", "จะ", "ก็", "แล้ว", "แต่", "และ",
    "คือ", "มี", "เป็น", "อยู่", "ที่", "ซึ่ง", "อัน", "ทำ", "พูด", "บอก", "ว่า",
    "อะไร", "ทำไม", "ยังไง", "ที่ไหน", "เมื่อไหร่", "ตอนไหน", "ตรงนี้", "ตรงนั้น",
    "นี่", "นั่น", "นู่น", "จริง", "เหรอ", "หรอ", "นะ", "คะ", "ครับ", "จ้ะ", "ล่ะ",
    "ก่อน", "หลัง", "ด้วย", "กัน", "กันนะ", "เถอะ", "เลย", "มาก", "น้อย", "ดี",
    "สวัสดี", "ขอบคุณ", "ขอโทษ", "เข้าใจ", "รู้", "เห็น", "คิด", "รู้สึก",
    "ได้ยิน", "ได้ยินคุณ", "จำ", "จำได้", "ได้ไหม", "ทุกคน", "ใคร", "หรือ", "ถ้า"
}

# Canonical Root Aliases
ROOT_CANONICAL_MAP = {
    "ssslurrpp": "slurp",
    "slurrp": "slurp",
    "slurrrp": "slurp",
    "slurp": "slurp",
    "slurpp": "slurp",
    "faap": "fap",
    "faaap": "fap",
    "faaaap": "fap",
    "fapp": "fap",
    "fap": "fap",
    "squeelch": "squelch",
    "squelch": "squelch",
    "squeeich": "squelch",
    "chuu": "chu",
    "chuuu": "chu",
    "chu": "chu",
    "smooch": "smooch",
    "kiss": "kiss",
    "lick": "lick",
    "suck": "suck",
    "rub": "rub",
    "sigh": "sigh",
    "siiigh": "sigh",
    "pant": "pant",
    "paant": "pant",
    "gasp": "gasp",
    "gaasp": "gasp",
    "gulp": "gulp",
    "gulpp": "gulp",
    "moan": "moan",
    "mooan": "moan",
    "groan": "groan",
    "grooan": "groan",
    "sob": "sob",
    "whimper": "whimper",
    "shiver": "shiver",
    "chuckle": "chuckle",
    "giggle": "giggle",
    "snicker": "snicker",
    "laugh": "laugh",
    "bzzt": "bzzt",
    "bzz": "bzzt",
    "bzzz": "bzzt",
    "bzzzt": "bzzt",
    "buzz": "bzzt",
    "slap": "slap",
    "plap": "plap",
    "plaap": "plap",
    "shoosh": "shoosh",
    "woosh": "woosh",
    "whoosh": "woosh",
    "smack": "smack",
    "thud": "thud",
    "thump": "thud",
    "crack": "crack",
    "crunch": "crunch",
    "crash": "crash",
    "slam": "slam",
    "smash": "smash",
    "knock": "knock",
    "creak": "creak",
    "rustle": "rustle",
    "splash": "splash",
    "drip": "drip",
    "beep": "beep",
    "ring": "ring",
    "click": "click",
    "clack": "click",
    "tap": "tap",
    "hum": "hum",
    "grumble": "grumble",
}


def extract_core_letters(token: str) -> str:
    """สกัดเฉพาะตัวอักษรภาษาอังกฤษล้วน"""
    letters = re.sub(r'[^a-zA-Z]', '', token).lower()
    return letters


def get_canonical_root(token: str) -> str:
    """แปลง Token ใดๆ ให้เป็น Canonical Root Word"""
    letters = extract_core_letters(token)
    if not letters:
        return token.strip().lower()

    if letters in ROOT_CANONICAL_MAP:
        return ROOT_CANONICAL_MAP[letters]

    collapsed = re.sub(r'([a-zA-Z])\1+', r'\1', letters)
    if collapsed in ROOT_CANONICAL_MAP:
        return ROOT_CANONICAL_MAP[collapsed]

    for key, root in ROOT_CANONICAL_MAP.items():
        if re.sub(r'([a-zA-Z])\1+', r'\1', key) == collapsed:
            return root

    return collapsed if collapsed else letters


def split_into_segments(text: str) -> List[Tuple[str, str]]:
    """แบ่งข้อความเป็นท่อนๆ ตาม Control Code"""
    parts = re.split(r'(\\\.|\\\||\\!|\\\^|\\>|\\<)', text)
    segments = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        sep = parts[i+1] if i + 1 < len(parts) else ""
        if seg or sep:
            segments.append((seg, sep))
        i += 2
    return segments


def extract_unwrapped_candidate(o_seg: str, i_seg: str, raw_o_sfx: str) -> Optional[str]:
    """
    Positional Gap Alignment (PGA):
    สกัดคำแปลภาษาไทยที่ไม่มี ** ครอบ โดยเทียบตำแหน่งกับ Original Segment
    """
    # ตัด speaker tag ออกจาก i_seg
    clean_i = re.sub(r'^(?:\\n)?<[^>]+>', '', i_seg).strip()
    clean_o = re.sub(r'^(?:\\n)?<[^>]+>', '', o_seg).strip()

    # กรณีที่ทั้งท่อนใน Original มีแค่ *SFX* และจุดไข่ปลา/สัญลักษณ์ (Pure SFX Segment)
    # เช่น *faap..* หรือ *shoosh* หรือ *squeelch♥*
    core_o_no_sfx = SFX_REGEX.sub('', clean_o).strip(".").strip(",").strip("!").strip("?").strip()
    if not core_o_no_sfx: # ท่อนนี้ไม่มีคำอื่นเลยนอกจาก SFX
        # ในฝั่ง Initial ท่อนนี้ย่อมเป็นคำแปลของ SFX ล้วนๆ!
        clean_word = clean_i.strip(".").strip(",").strip("!").strip("?").strip("♥").strip()
        if clean_word and 2 <= len(clean_word) <= 25 and clean_word not in THAI_STOPWORDS:
            # ต้องมีพยัญชนะไทยอย่างน้อย 1 ตัว
            if re.search(r'[ก-ฮ]', clean_word):
                return clean_word

    # กรณีที่มีข้อความอื่นปะปน (Mixed Segment) เช่น "...h..hello..*bzzt*.." ↔️ "...ฮ..ฮัลโหล..ซ่า.."
    # แยกส่วนก่อนและหลัง SFX ใน Original
    sfx_pattern = re.escape(f"*{raw_o_sfx}*")
    parts = re.split(sfx_pattern, clean_o, maxsplit=1)
    if len(parts) == 2:
        prefix_o, suffix_o = parts[0], parts[1]
        # ถ้า suffix_o เป็นเครื่องหมาย เช่น ".." หรือ "..."
        if suffix_o.strip().startswith(".."):
            # ใน Initial ท้ายประโยคควรเป็น ".." ด้วย
            # คำแทนเสียงจะอยู่ก่อนหน้าเครื่องหมายท้ายประโยค
            m_tail = re.search(r'([ก-ฮะ-ูเ-ไ]+(?:\.\.|♥|!|\?)?)\s*$', clean_i)
            if m_tail:
                cand = m_tail.group(1).strip(".").strip("♥").strip("!").strip("?").strip()
                if cand and 2 <= len(cand) <= 20 and cand not in THAI_STOPWORDS:
                    if re.search(r'[ก-ฮ]', cand):
                        return cand

    return None


def build_master_dictionary(ground_truth_json_path: str, output_json: str, output_md: str):
    if not os.path.exists(ground_truth_json_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ Ground-Truth: {ground_truth_json_path}")

    print("=" * 95)
    print("   ATF MASTER SOUND EFFECT DICTIONARY BUILDER (v2.0 POSITIONAL GAP ALIGNMENT)   ")
    print("=" * 95)
    print(f"Ground-Truth Source: {ground_truth_json_path}")
    print("-" * 95)

    with open(ground_truth_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    print(f"📊 โหลดข้อมูลจริงทั้งหมด: {len(records):,} แถว")

    clusters = defaultdict(lambda: {
        "total_occurrences": 0,
        "variants": Counter(),
        "thai_verified": Counter(),         # คำแปลที่ผู้แปลครอบ *...* ไว้แล้ว (ความมั่นใจ 100%)
        "thai_unwrapped_pga": Counter(),     # คำแปลที่สกัดได้จาก Gap Alignment (ไม่มีดอกจัน)
        "sample_rows": []
    })

    untranslated_english_in_initial = Counter()

    for rec in records:
        line_num = rec["line_num"]
        row_id = rec.get("row_id", "")
        speaker = rec.get("speaker", "")
        orig_sfx_list = rec.get("orig_sfx_tokens", [])
        init_sfx_list = rec.get("init_sfx_tokens", [])
        orig_text = rec.get("orig_text", "")
        init_text = rec.get("init_text", "")

        # เก็บคำภาษาอังกฤษที่ตกค้างใน Initial
        for i_sfx in init_sfx_list:
            if re.match(r'^[a-zA-Z\s\.\-♥!]+$', i_sfx.strip()):
                untranslated_english_in_initial[i_sfx.strip()] += 1

        if not orig_sfx_list:
            continue

        # ทำ Segment Alignment
        orig_segs = split_into_segments(orig_text)
        init_segs = split_into_segments(init_text)
        clean_orig_segs = [(s, p) for s, p in orig_segs if s.strip() or p]
        clean_init_segs = [(s, p) for s, p in init_segs if s.strip() or p]

        for o_idx, raw_o_sfx in enumerate(orig_sfx_list):
            root = get_canonical_root(raw_o_sfx)
            cl = clusters[root]
            cl["total_occurrences"] += 1
            cl["variants"][raw_o_sfx] += 1

            # 1. เช็คว่าใน Initial มี *...* ครอบอยู่ตรงกันหรือไม่ (Verified)
            if o_idx < len(init_sfx_list):
                th_token = init_sfx_list[o_idx].strip()
                if not re.match(r'^[a-zA-Z\s\.\-♥!]+$', th_token):
                    # ทำความสะอาดตัดจุด/สัญลักษณ์เพื่อดูแก่นคำ
                    core_th = th_token.strip(".").strip(",").strip("!").strip("?").strip("♥").strip()
                    if core_th and core_th not in THAI_STOPWORDS:
                        cl["thai_verified"][core_th] += 1

            # 2. กรณีที่ไม่มี *...* ครอบ: ใช้ Positional Gap Alignment
            if len(clean_orig_segs) == len(clean_init_segs) and len(clean_orig_segs) > 0:
                # หา segment ที่ตรงกัน
                for (o_s, _), (i_s, _) in zip(clean_orig_segs, clean_init_segs):
                    if f"*{raw_o_sfx}*" in o_s and not SFX_REGEX.search(i_s):
                        cand_th = extract_unwrapped_candidate(o_s, i_s, raw_o_sfx)
                        if cand_th:
                            cl["thai_unwrapped_pga"][cand_th] += 1

            if len(cl["sample_rows"]) < 5:
                cl["sample_rows"].append({
                    "line_num": line_num,
                    "row_id": row_id,
                    "speaker": speaker,
                    "orig_token": raw_o_sfx,
                    "orig_text": orig_text,
                    "init_text": init_text
                })

    # รวมผลลัพธ์และวิเคราะห์คำแปลแนะนำ
    final_dictionary = {}
    for root, cl in sorted(clusters.items(), key=lambda x: x[1]["total_occurrences"], reverse=True):
        all_thai_counter = Counter()
        # ให้น้ำหนัก Verified มากกว่า PGA
        for w, c in cl["thai_verified"].items():
            all_thai_counter[w] += c * 3
        for w, c in cl["thai_unwrapped_pga"].items():
            all_thai_counter[w] += c

        top_candidates = [item[0] for item in all_thai_counter.most_common(10)]
        recommended_thai = top_candidates[0] if top_candidates else ""

        final_dictionary[root] = {
            "root_word": root,
            "total_occurrences": cl["total_occurrences"],
            "recommended_thai": recommended_thai,
            "thai_verified_with_asterisks": dict(cl["thai_verified"]),
            "thai_unwrapped_discovered_by_pga": dict(cl["thai_unwrapped_pga"]),
            "all_known_thai_words": top_candidates,
            "variants_in_original": dict(cl["variants"]),
            "sample_rows": cl["sample_rows"]
        }

    # บันทึก JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as jf:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_clusters": len(final_dictionary),
            "untranslated_english_in_initial": dict(untranslated_english_in_initial),
            "clusters": final_dictionary
        }, jf, ensure_ascii=False, indent=2)

    # บันทึก Markdown
    with open(output_md, "w", encoding="utf-8") as mf:
        mf.write("# 📖 ATF Master Sound Effect Dictionary & Cluster Catalog (v2.0)\n\n")
        mf.write(f"> **สร้างเมื่อ:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        mf.write(f"> **จำนวนคลัสเตอร์คำแทนเสียงทั้งหมด:** {len(final_dictionary)} กลุ่ม  \n")
        mf.write(f"> **สกัดจากข้อมูลจริง:** {len(records):,} แถวในโปรเจกต์\n\n")

        mf.write("## 🏆 ตารางกลุ่มคำแทนเสียงและการแปลภาษาไทย (วิเคราะห์จากข้อมูลจริงทั้งแบบมีและไม่มี **)\n\n")
        mf.write("| อันดับ | Root Word | ความถี่รวม | คำแปลที่ได้รับการยืนยัน (มี \*\*) | คำแปลที่ตรวจพบจากบริบท (PGA) | รูปแบบใน Original (Variants) |\n")
        mf.write("| :--- | :--- | :---: | :--- | :--- | :--- |\n")

        for rank, (root, data) in enumerate(final_dictionary.items(), start=1):
            ver_th = ", ".join([f"`{th}` ({cnt})" for th, cnt in list(data["thai_verified_with_asterisks"].items())[:4]]) or "-"
            pga_th = ", ".join([f"`{th}` ({cnt})" for th, cnt in list(data["thai_unwrapped_discovered_by_pga"].items())[:4]]) or "-"
            top_vars = ", ".join([f"`*{var}*` ({cnt})" for var, cnt in list(data["variants_in_original"].items())[:4]])
            mf.write(f"| {rank} | **{root}** (แนะนำ: `{data['recommended_thai']}`) | {data['total_occurrences']:,} | {ver_th} | {pga_th} | {top_vars} |\n")

        if untranslated_english_in_initial:
            mf.write("\n\n## ⚠️ คำแทนเสียงภาษาอังกฤษที่หลุดค้างในช่อง Initial (ลืมแปล)\n\n")
            mf.write("| คำภาษาอังกฤษที่ค้าง | จำนวนครั้งที่พบ |\n")
            mf.write("| :--- | :---: |\n")
            for eng_w, cnt in untranslated_english_in_initial.most_common(25):
                mf.write(f"| `*{eng_w}*` | {cnt:,} |\n")

    print(f"\n✅ สร้าง Master SFX Dictionary สำเร็จ:")
    print(f"  • จัดกลุ่มคำแทนเสียงได้ทั้งหมด: {len(final_dictionary)} คลัสเตอร์")
    print(f"  • บันทึก JSON ที่: {output_json}")
    print(f"  • บันทึก Markdown ที่: {output_md}")
    print("=" * 95)


def main():
    parser = argparse.ArgumentParser(description="ATF Master Sound Effect Dictionary Builder")
    parser.add_argument("--input-json", type=str, default="data/audit/sfx_all_ground_truth.json", help="Path to input ground truth JSON")
    parser.add_argument("--out-json", type=str, default="data/audit/master_sfx_dictionary.json", help="Path to output dictionary JSON")
    parser.add_argument("--out-md", type=str, default="data/audit/master_sfx_catalog.md", help="Path to output catalog Markdown")
    args = parser.parse_args()

    build_master_dictionary(args.input_json, args.out_json, args.out_md)


if __name__ == "__main__":
    main()
