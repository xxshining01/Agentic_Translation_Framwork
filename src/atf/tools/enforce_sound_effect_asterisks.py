#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Sound Effect Asterisk Enforcer & Precision Auditor (v5.0 Original-Parity Master Edition)
============================================================================================
ระบบตรวจจับและเติมดอกจัน (*...*) โดยยึด Original เป็นมาตรฐานสูงสุด 100% (Strict Original Parity)
"เรามาแปลงาน ไม่ใช่แก้งาน - ทุกโค้ดและสัญลักษณ์ที่ผู้พัฒนาใส่ไว้ใน Original ต้องได้รับการสะท้อนลงใน Initial 1:1"

หลักการสำคัญของ v5.0:
1. [Original Decor Mirroring (สะท้อนสัญลักษณ์และเครื่องหมายตามต้นฉบับ 1:1)]:
   - ถ้า Original สัญลักษณ์/โค้ดอยู่ในดอกจัน (*Smash!!*, *squeelch♥*, *ssslurrpp..*, *PLAP!\C[27]♥\C*):
     - ฝั่งภาษาไทยต้องมีสัญลักษณ์นั้นอยู่ข้างในดอกจันด้วย เช่น *โครม!!*, *แฉะ♥*, *ซูดดด..*
     - ถ้าคำแปลเดิมวางสัญลักษณ์ไว้นอกดอกจัน เช่น *โครม*!! ระบบจะปรับให้ตรงกับต้นฉบับเป็น *โครม!!*
   - ถ้า Original สัญลักษณ์อยู่นอกดอกจัน (...*bzzt*...):
     - ฝั่งภาษาไทยต้องอยู่นอกดอกจันเช่นกัน เช่น ...*ซ่า*... (ไม่ดึงจุดไข่ปลาเข้าไปในดอกจัน)

2. [Data-Driven 185 Cluster Lexicon]:
   - โหลดฐานข้อมูล Master SFX Dictionary ที่สกัดจากข้อมูลจริง 1,632 แถว
   - รู้จักคำแปลจริงทุกหมวดหมู่ (เช่น crash ➡️ ตึง/โครม, bzzt ➡️ ซ่า, fap ➡️ ฟ้าว/ฟาบ/พั่บ)

3. [Non-SFX Intent Preservation]:
   - หากผู้พัฒนาใส่ *...* ครอบคำเน้นความรู้สึก (เช่น *with*, *you*) หรือข้อความระบบ (*Side quest*):
     - ระบบจะคงการครอบ *...* ไว้ตามต้นฉบับ ไม่ลบหรือตัดทิ้ง เพราะถือเป็นความตั้งใจของผู้พัฒนา

4. [Full Audit & Traceability]:
   - ส่งออกรายงานเปรียบเทียบก่อน-หลังทุกแถว พร้อมแจกแจงทุกการเปลี่ยนแปลงอย่างละเอียด
"""

import os
import sys
import re
import csv
import json
import shutil
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

# Stopwords ภาษาไทยที่ห้ามจับคู่มั่ว
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

ROOT_CANONICAL_MAP = {
    "ssslurrpp": "slurp", "slurrp": "slurp", "slurrrp": "slurp", "slurp": "slurp", "slurpp": "slurp",
    "faap": "fap", "faaap": "fap", "faaaap": "fap", "fapp": "fap", "fap": "fap",
    "squeelch": "squelch", "squelch": "squelch", "squeeich": "squelch",
    "chuu": "chu", "chuuu": "chu", "chu": "chu", "smooch": "smooch", "kiss": "kiss",
    "lick": "lick", "suck": "suck", "rub": "rub", "sigh": "sigh", "siiigh": "sigh",
    "pant": "pant", "paant": "pant", "gasp": "gasp", "gaasp": "gasp", "gulp": "gulp", "gulpp": "gulp",
    "moan": "moan", "mooan": "moan", "groan": "groan", "grooan": "groan", "sob": "sob",
    "whimper": "whimper", "shiver": "shiver", "chuckle": "chuckle", "giggle": "giggle",
    "snicker": "snicker", "laugh": "laugh", "bzzt": "bzzt", "bzz": "bzzt", "bzzz": "bzzt",
    "bzzzt": "bzzt", "buzz": "bzzt", "slap": "slap", "plap": "plap", "plaap": "plap",
    "shoosh": "shoosh", "woosh": "woosh", "whoosh": "woosh", "smack": "smack", "thud": "thud",
    "thump": "thud", "crack": "crack", "crunch": "crunch", "crash": "crash", "slam": "slam",
    "smash": "smash", "knock": "knock", "creak": "creak", "rustle": "rustle", "splash": "splash",
    "drip": "drip", "beep": "beep", "ring": "ring", "click": "click", "clack": "click",
    "tap": "tap", "hum": "hum", "grumble": "grumble"
}


def get_canonical_root(token: str) -> str:
    letters = re.sub(r'[^a-zA-Z]', '', token).lower()
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


def parse_token_structure(raw_token: str) -> Tuple[str, str, str]:
    """
    แยกโครงสร้างของ token ใน *...*:
    Returns: (leading_decor, core_word, trailing_decor)
    ตัวอย่าง:
      "Smash!!" ➡️ ("", "Smash", "!!")
      "squeelch♥" ➡️ ("", "squeelch", "♥")
      "ssslurrpp.." ➡️ ("", "ssslurrpp", "..")
      "PLAP!\C[27]♥\C" ➡️ ("", "PLAP", "!\C[27]♥\C")
      "bzzt" ➡️ ("", "bzzt", "")
    """
    # หา leading symbols
    m_lead = re.match(r'^([^a-zA-Z0-9\u0E00-\u0E7F]+)(.*)$', raw_token)
    if m_lead:
        leading = m_lead.group(1)
        rest = m_lead.group(2)
    else:
        leading = ""
        rest = raw_token

    # หา trailing symbols/codes
    m_trail = re.search(r'([^a-zA-Z0-9\u0E00-\u0E7F\s].*)$', rest)
    if m_trail:
        trailing = m_trail.group(1)
        core = rest[:m_trail.start()]
    else:
        trailing = ""
        core = rest

    return leading, core, trailing


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


def load_master_dictionary(dict_json_path: str) -> Dict[str, List[str]]:
    """โหลด Dictionary 185 คลัสเตอร์ แปลงเป็น mapping root_word ➡️ list of thai translations"""
    if not os.path.exists(dict_json_path):
        return {}

    with open(dict_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dict_map = defaultdict(list)
    clusters = data.get("clusters", {})
    for root, info in clusters.items():
        candidates = []
        rec_th = info.get("recommended_thai", "")
        if rec_th:
            candidates.append(rec_th)
        for w in info.get("thai_verified_with_asterisks", {}).keys():
            if w not in candidates:
                candidates.append(w)
        for w in info.get("thai_unwrapped_discovered_by_pga", {}).keys():
            if w not in candidates:
                candidates.append(w)
        for w in info.get("all_known_thai_words", []):
            if w not in candidates:
                candidates.append(w)

        # กรองคำใน Blacklist, กรองคำสั้น < 2 ตัวอักษร, และต้องมีพยัญชนะหรือตัวอักษร
        valid_candidates = []
        for c in candidates:
            c_str = c.strip()
            if not c_str or len(c_str) < 2 or len(c_str) > 30:
                continue
            if c_str in THAI_STOPWORDS:
                continue
            if not re.search(r'[a-zA-Zก-ฮ]', c_str):
                continue
            valid_candidates.append(c_str)

        dict_map[root] = sorted(valid_candidates, key=len, reverse=True)

    return dict_map


def align_and_repair_cell(
    orig_text: str,
    init_text: str,
    dict_map: Dict[str, List[str]]
) -> Tuple[str, bool, List[str], List[str], str]:
    """
    ปรับแต่งและเติมดอกจันโดยสะท้อน Original Parity 100%:
    Returns: (repaired_text, had_modification, details, unresolved, status)
    """
    if not orig_text or not init_text:
        return init_text, False, [], [], "NO_SFX"

    orig_matches = SFX_REGEX.findall(orig_text)
    if not orig_matches:
        return init_text, False, [], [], "NO_SFX"

    current = init_text
    modified = False
    details = []
    unresolved = []

    # -----------------------------------------------------------------
    # STEP 1: ปรับแต่งแถวที่มี *...* อยู่แล้วแต่เครื่องหมายหลุดออกนอกดอกจัน
    # ตัวอย่าง: Original '*Smash!!*' vs Initial '*โครม*!!' ➡️ ปรับเป็น '*โครม!!*'
    # -----------------------------------------------------------------
    for raw_o_sfx in orig_matches:
        o_lead, o_core, o_trail = parse_token_structure(raw_o_sfx)
        if o_trail: # Original มีเครื่องหมายต่อท้ายในดอกจัน เช่น !! หรือ .. หรือ ♥
            esc_trail = re.escape(o_trail)
            fix_pattern = re.compile(rf'\*([^*]+)\*{esc_trail}')
            m_fix = fix_pattern.search(current)
            if m_fix:
                inner_word = m_fix.group(1)
                full_fixed = f"*{inner_word}{o_trail}*"
                current = current[:m_fix.start()] + full_fixed + current[m_fix.end():]
                modified = True
                details.append(f"[Parity Mirror] ดึงเครื่องหมายเข้าดอกจันตาม Original: '*{inner_word}*{o_trail}' ➡️ '{full_fixed}' (จาก '*{raw_o_sfx}*')")

    # -----------------------------------------------------------------
    # OCCURRENCE GUARD: ถ้าใน current มีดอกจันครบตามจำนวน Original แล้ว
    # ให้หยุดการเติมเพิ่มทันที ป้องกันการแทรกดอกจันเกินเด็ดขาด!
    # -----------------------------------------------------------------
    cur_init_matches = SFX_REGEX.findall(current)
    if len(cur_init_matches) >= len(orig_matches):
        status = "SAFELY_ENCLOSED" if modified else "ALREADY_PERFECT"
        return current, modified, details, unresolved, status

    # -----------------------------------------------------------------
    # STEP 2: เติมดอกจันครอบคำที่ยังไม่มีดอกจัน โดยอิงตาม 185 คลัสเตอร์ และโครงสร้าง 1:1
    # -----------------------------------------------------------------
    orig_segs = split_into_segments(orig_text)
    init_segs = split_into_segments(current)
    clean_orig_segs = [(s, p) for s, p in orig_segs if s.strip() or p]
    clean_init_segs = [(s, p) for s, p in init_segs if s.strip() or p]

    # การจับคู่ตาม Segment 1:1
    if len(clean_orig_segs) == len(clean_init_segs) and len(clean_orig_segs) > 0:
        reconstructed_parts = []
        seg_mod = False
        for (o_seg, o_sep), (i_seg, i_sep) in zip(clean_orig_segs, clean_init_segs):
            o_tokens = SFX_REGEX.findall(o_seg)
            cur_i_seg = i_seg

            # ถ้าใน segment นี้มีดอกจันครบตาม o_tokens อยู่แล้ว ข้ามทันที!
            cur_i_tokens = SFX_REGEX.findall(cur_i_seg)
            if len(cur_i_tokens) >= len(o_tokens):
                reconstructed_parts.append(cur_i_seg + i_sep)
                continue

            for raw_o in o_tokens:
                # เช็คซ้ำอีกครั้งว่าดอกจันใน segment ครบหรือยัง
                if len(SFX_REGEX.findall(cur_i_seg)) >= len(o_tokens):
                    break

                o_lead, o_core, o_trail = parse_token_structure(raw_o)
                root = get_canonical_root(raw_o)
                cands = dict_map.get(root, []) + [raw_o.strip()]

                # ค้นหาคำแปลใน cur_i_seg ที่ยังไม่มีดอกจันครอบ
                for cand in cands:
                    if len(cand) < 2:
                        continue
                    esc_cand = re.escape(cand)

                    # ใช้ Thai Word Boundary Protection:
                    # ป้องกันการครอบคำที่เป็นส่วนย่อยของคำอื่น (เช่น 'บ' ใน 'ตรวจสอบ' หรือ 'ซ่า' ใน 'รักษา')
                    if re.search(r'[\u0E00-\u0E7F]', cand):
                        pat = re.compile(rf'(?<!\*|<)(?<![ก-ฮะ-ูเ-ไ]){esc_cand}(?![ก-ฮะ-ูเ-ไ])(?!\*|>)')
                    else:
                        pat = re.compile(rf'(?<!\*|<)\b{esc_cand}\b(?!\*|>)')

                    m = pat.search(cur_i_seg)
                    if not m and re.search(r'[\u0E00-\u0E7F]', cand):
                        # ลองแบบ stretched สำหรับภาษาไทย
                        cand_st = re.sub(r'([ก-ฮะ-ูเ-ไ])', r'\1+', esc_cand)
                        try:
                            pat_st = re.compile(rf'(?<!\*|<)(?<![ก-ฮะ-ูเ-ไ]){cand_st}(?![ก-ฮะ-ูเ-ไ])(?!\*|>)')
                            m = pat_st.search(cur_i_seg)
                        except Exception:
                            m = None

                    if m:
                        st, en = m.start(), m.end()
                        matched_w = cur_i_seg[st:en]

                        # ตรวจสอบเครื่องหมายตาม Original
                        if o_trail:
                            esc_ot = re.escape(o_trail)
                            m_after = re.match(rf'^{esc_ot}', cur_i_seg[en:])
                            if m_after:
                                en += len(m_after.group(0))
                                matched_w = cur_i_seg[st:en]

                        new_enclosed = f"*{matched_w}*"
                        cur_i_seg = cur_i_seg[:st] + new_enclosed + cur_i_seg[en:]
                        seg_mod = True
                        details.append(f"[Segment 1:1 Enforce] เติมดอกจันครอบ: '{matched_w}' ➡️ '{new_enclosed}' (จาก '*{raw_o}*')")
                        break

            reconstructed_parts.append(cur_i_seg + i_sep)

        if seg_mod:
            current = "".join(reconstructed_parts)
            modified = True

    # -----------------------------------------------------------------
    # STEP 3: Fallback Contextual Scan across Full String
    # -----------------------------------------------------------------
    for raw_o in orig_matches:
        cur_init_matches = SFX_REGEX.findall(current)
        if len(cur_init_matches) >= len(orig_matches):
            break

        o_lead, o_core, o_trail = parse_token_structure(raw_o)
        root = get_canonical_root(raw_o)
        cands = dict_map.get(root, []) + [raw_o.strip()]

        for cand in cands:
            if len(cand) < 2:
                continue
            esc_cand = re.escape(cand)

            if re.search(r'[\u0E00-\u0E7F]', cand):
                pat = re.compile(rf'(?<!\*|<)(?<![ก-ฮะ-ูเ-ไ]){esc_cand}(?![ก-ฮะ-ูเ-ไ])(?!\*|>)')
            else:
                pat = re.compile(rf'(?<!\*|<)\b{esc_cand}\b(?!\*|>)')

            m = pat.search(current)
            if not m and re.search(r'[\u0E00-\u0E7F]', cand):
                cand_st = re.sub(r'([ก-ฮะ-ูเ-ไ])', r'\1+', esc_cand)
                try:
                    pat_st = re.compile(rf'(?<!\*|<)(?<![ก-ฮะ-ูเ-ไ]){cand_st}(?![ก-ฮะ-ูเ-ไ])(?!\*|>)')
                    m = pat_st.search(current)
                except Exception:
                    m = None

            if m:
                st, en = m.start(), m.end()

                # ตรวจว่าไม่อยู่ในแท็ก <...>
                left_text = current[:st]
                right_text = current[en:]
                if "<" in left_text and ">" in right_text:
                    if left_text.rfind("<") > left_text.rfind(">"):
                        continue

                matched_w = current[st:en]
                if o_trail:
                    esc_ot = re.escape(o_trail)
                    m_after = re.match(rf'^{esc_ot}', current[en:])
                    if m_after:
                        en += len(m_after.group(0))
                        matched_w = current[st:en]

                new_enclosed = f"*{matched_w}*"
                current = current[:st] + new_enclosed + current[en:]
                modified = True
                details.append(f"[Lexicon Match] เติมดอกจันครอบ: '{matched_w}' ➡️ '{new_enclosed}' (จาก '*{raw_o}*')")
                break

    # ตรวจสอบขั้นสุดท้าย
    final_init_matches = SFX_REGEX.findall(current)
    if len(final_init_matches) < len(orig_matches):
        for o_m in orig_matches:
            unresolved.append(f"*{o_m}*")

    status = "SAFELY_ENCLOSED" if modified else ("ALREADY_PERFECT" if not unresolved else "UNRESOLVED_SFX")
    return current, modified, details, unresolved, status


def process_enforcement_v5(
    csv_path: str,
    dict_path: str,
    dry_run: bool = True,
    output_path: str = None,
    audit_export_path: str = None
):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    print("=" * 95)
    print("   ATF SOUND EFFECT ENFORCER (v5.0 ORIGINAL-PARITY MASTER EDITION)   ")
    print("=" * 95)
    print(f"Target CSV: {csv_path}")
    print(f"Master Dict: {dict_path}")
    print(f"Mode: {'🔍 DRY-RUN (ตรวจสอบและรายงานตัวอย่าง - ยังไม่แก้ไขไฟล์)' if dry_run else '🛠️ LIVE APPLY (ดำเนินการเติมดอกจันและบันทึกไฟล์จริง)'}")
    print("-" * 95)

    # โหลด Master Dictionary
    dict_map = load_master_dictionary(dict_path)
    print(f"✅ โหลด Master SFX Dictionary สำเร็จ: {len(dict_map):,} คลัสเตอร์")

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("❌ ไฟล์ CSV ว่างเปล่า")
        return

    header = rows[0]
    header_lower = [h.strip().lower() for h in header]

    init_col = header_lower.index("initial") if "initial" in header_lower else 1
    orig_col = header_lower.index("original") if "original" in header_lower else 0
    spk_col = header_lower.index("speaker") if "speaker" in header_lower else None
    row_col = header_lower.index("row") if "row" in header_lower else None

    repaired_records = []
    unresolved_records = []
    already_perfect_count = 0
    new_rows = [header]
    audit_rows = [
        ["Row", "Row_ID", "Speaker", "Status", "Original_SFX", "Details", "ORIGINAL", "BEFORE", "AFTER"]
    ]

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            new_rows.append(r)
            continue

        init_val = r[init_col]
        orig_val = r[orig_col] if orig_col < len(r) else ""
        spk_val = r[spk_col] if spk_col is not None and spk_col < len(r) else ""
        row_id = r[row_col] if row_col is not None and row_col < len(r) else str(idx)

        if not init_val or not orig_val or not SFX_REGEX.search(orig_val):
            new_rows.append(r)
            continue

        cleaned_text, had_mod, details, unresolved, status = align_and_repair_cell(
            orig_val, init_val, dict_map
        )

        if status == "ALREADY_PERFECT":
            already_perfect_count += 1

        if had_mod:
            repaired_records.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "original": orig_val,
                "before": init_val,
                "after": cleaned_text,
                "details": details
            })
            new_r = list(r)
            new_r[init_col] = cleaned_text
            new_rows.append(new_r)
        else:
            new_rows.append(r)

        if unresolved:
            unresolved_records.append({
                "row_idx": idx,
                "row_id": row_id,
                "speaker": spk_val,
                "unresolved_sfx": unresolved,
                "original": orig_val,
                "initial": cleaned_text
            })

        orig_sfx_list = SFX_REGEX.findall(orig_val)
        audit_rows.append([
            str(idx),
            str(row_id),
            spk_val,
            status,
            "; ".join(orig_sfx_list),
            " | ".join(details) if details else ("Already Perfect" if status == "ALREADY_PERFECT" else f"Unresolved: {'; '.join(unresolved)}"),
            orig_val,
            init_val,
            cleaned_text
        ])

    print(f"\n📊 สรุปผลการประมวลผล (จากทั้งหมด {len(rows):,} แถว):")
    print(f"  • แถวที่มีคำแทนเสียงสมบูรณ์อยู่แล้ว (Already Perfect): {already_perfect_count:,} แถว")
    print(f"  • จำนวนแถวที่ปรับแต่งและเติมดอกจันสำเร็จ:             {len(repaired_records):,} แถว")
    print(f"  • แถวที่มีคำแทนเสียงแต่ยังจับคู่ไม่ได้ (Unresolved):          {len(unresolved_records):,} แถว")
    print("-" * 95)

    if repaired_records:
        print("\n🔍 ตัวอย่างแถวที่ได้รับการปรับแต่งและเติมดอกจันอย่างแม่นยำ (แสดง 15 แถวแรก):")
        for ex in repaired_records[:15]:
            print(f"  • [Row {ex['row_idx']} | ID {ex['row_id']} | Speaker: '{ex['speaker']}']:")
            for d in ex["details"]:
                print(f"    - {d}")
            print(f"    - ORIGINAL: {repr(ex['original'][:95])}")
            print(f"    - BEFORE:   {repr(ex['before'][:95])}")
            print(f"    - AFTER:    {repr(ex['after'][:95])}")
            print()

    # แสดงแถวที่ Unresolved ถ้ามี
    if unresolved_records:
        print(f"\n⚠️ รายละเอียดแถวที่คำแทนเสียงยังจับคู่ไม่ได้ (Unresolved) ทั้งหมด {len(unresolved_records)} แถว:")
        for u in unresolved_records[:10]:
            print(f"  • [Row {u['row_idx']} | ID {u['row_id']} | Speaker: '{u['speaker']}']:")
            print(f"    - คำแทนเสียงใน Original: {u['unresolved_sfx']}")
            print(f"    - ORIGINAL: {repr(u['original'])}")
            print(f"    - INITIAL:  {repr(u['initial'])}")
            print()

    # ส่งออก Audit Report CSV
    actual_audit_path = audit_export_path or os.path.join(
        os.path.dirname(csv_path), "sfx_enforcement_detailed_audit_v5.csv"
    )
    try:
        with open(actual_audit_path, "w", encoding="utf-8-sig", newline="") as af:
            writer = csv.writer(af)
            writer.writerows(audit_rows)
        print(f"📋 ส่งออกรายงาน Audit ละเอียด 100% สำเร็จที่:\n   👉 {actual_audit_path}")
    except Exception as e:
        print(f"⚠️ ไม่สามารถส่งออกไฟล์ Audit Report ได้: {e}")

    # Live Apply
    if not dry_run and len(repaired_records) > 0:
        target_out = output_path or csv_path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{csv_path}.backup_sfx_v5_{ts}.csv"
        shutil.copy2(csv_path, backup_path)
        print(f"\n💾 สำรองไฟล์ต้นฉบับอย่างปลอดภัยไว้ที่:\n   👉 {backup_path}")

        temp_out = target_out + ".tmp"
        with open(temp_out, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(new_rows)
        os.replace(temp_out, target_out)
        print(f"💾 บันทึกผลการเติมดอกจันลงไฟล์สำเร็จ:\n   👉 {target_out}")


def main():
    parser = argparse.ArgumentParser(description="ATF Sound Effect Enforcer v5.0")
    parser.add_argument("--csv", type=str, required=True, help="Path to input CSV")
    parser.add_argument("--dict", type=str, default="data/audit/master_sfx_dictionary.json", help="Path to master SFX dictionary JSON")
    parser.add_argument("--apply", action="store_true", help="Apply fixes to CSV (default is Dry-run)")
    parser.add_argument("--out", type=str, default=None, help="Custom output CSV path")
    parser.add_argument("--export-audit", type=str, default=None, help="Path to export audit CSV")
    args = parser.parse_args()

    process_enforcement_v5(
        args.csv,
        dict_path=args.dict,
        dry_run=not args.apply,
        output_path=args.out,
        audit_export_path=args.export_audit
    )


if __name__ == "__main__":
    main()
