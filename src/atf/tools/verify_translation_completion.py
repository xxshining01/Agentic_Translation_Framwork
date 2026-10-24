#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script to audit translation completion of SSPV034v1.35 - Trans - Processed_v3_translated.csv
Uses the exact same speaker extraction and symbol/name classification as ChatGPTTranslatorRunner.
"""
import os
import csv
import re
import json
from collections import Counter

CSV_PATH = os.path.join("Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
GLOSSARY_PATH = os.path.join("data", "tlas", "tlas_glossary.json")
CHECKPOINT_PATH = os.path.join("data", "tlas", "chatgpt_translation_checkpoint.json")

def extract_speaker_tag(orig_text: str):
    if not orig_text:
        return False, "", "", ""
    m = re.match(r"^(\s*\\n)?<([^>]+)>", orig_text)
    if not m:
        return False, "", "", orig_text

    full_prefix = m.group(0)
    inner_content = m.group(2)
    pure_dialogue = orig_text[len(full_prefix):].strip()

    clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content)
    clean_name = clean_name.replace(":", "").strip()

    if clean_name:
        return True, full_prefix, clean_name, pure_dialogue

    return False, "", "", orig_text

def is_pure_symbol_dialogue(text: str) -> bool:
    if not text or not text.strip():
        return True
    clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text)
    has_english_letters = bool(re.search(r'[A-Za-z]', clean))
    return not has_english_letters

def is_name_only_dialogue(text: str, character_names: set, locked_terms: set) -> bool:
    if not text or not text.strip():
        return False

    clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text)
    clean = re.sub(r'\b[A-Za-z]-(\\\.)?', '', clean)
    words = re.findall(r'[A-Za-z]+', clean)
    if not words:
        return False

    stopwords = {"a", "i", "the", "to", "in", "of", "on", "and", "is", "it", "you", "me", "he", "she", "we", "yes", "no"}
    for w in words:
        if w.lower() in stopwords:
            return False
        w_lower = w.lower()
        if w_lower not in character_names and w_lower not in locked_terms:
            return False

    return True

def main():
    print("=" * 80)
    print("=== ATF TRANSLATION COMPLETION AUDIT & DEEP VERIFICATION ===")
    print("=" * 80)

    if not os.path.exists(CSV_PATH):
        print(f"[!] Target CSV not found: {CSV_PATH}")
        return

    # 1. โหลด Glossary Characters & Locked Terms
    locked_terms = {
        "harold", "connie", "jonathan", "dan", "shion", "masaru", "lily", "lucas",
        "erica", "bonnie", "drex", "reiko", "akane", "yearl", "toru", "ludo",
        "rum", "foregrave", "the earl", "jords", "bastio", "masgolf", "natalie",
        "ritchie", "rose", "drake", "lucy", "alisa", "aubrie", "bazz", "big b",
        "mayor", "jasmine", "chisato", "kintah", "wussapps", "onlyf*ps", "onlyfans",
        "twixs", "twaxtor"
    }
    character_names = set(locked_terms)

    if os.path.exists(GLOSSARY_PATH):
        try:
            with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            chars = gdata.get("characters", {})
            for c_name in chars.keys():
                character_names.add(c_name.strip().lower())
                character_names.add(re.sub(r"[^A-Za-z0-9]", "", c_name).lower())

            for cat, items in gdata.items():
                if isinstance(items, dict):
                    for en_k, val in items.items():
                        if isinstance(val, dict):
                            th_val = val.get("th", "")
                            if th_val and th_val.strip().lower() == en_k.strip().lower():
                                locked_terms.add(en_k.strip().lower())
        except Exception as e:
            print(f"[!] Warning reading glossary: {e}")

    # 2. โหลด Checkpoint Data แบบ Content-based Matching (SDD-016 / SAD-014 Compliant)
    # ห้ามแมปด้วย Row Index ดิบข้ามไฟล์ที่มีจำนวนแถวต่างกันเด็ดขาด
    checkpoint_content_map: Dict[Tuple[str, str], str] = {}
    checkpoint_fallback_map: Dict[str, str] = {}
    total_cached_items = 0

    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                cp_data = json.load(f)

            csv_trans_sections = cp_data.get("csv_translations", {})
            for sec_name, row_map in csv_trans_sections.items():
                if not isinstance(row_map, dict):
                    continue
                total_cached_items += len(row_map)

                # ค้นหาไฟล์ CSV ต้นทางของ Section เพื่อสกัด Original Text ประจำแต่ละแถว
                candidate_paths = [
                    os.path.join(ROOT_DIR, "testing files", sec_name),
                    os.path.join(ROOT_DIR, "Example RPGM Game", sec_name),
                    os.path.join(ROOT_DIR, sec_name)
                ]
                source_csv = next((p for p in candidate_paths if os.path.exists(p)), None)

                if source_csv:
                    try:
                        with open(source_csv, "r", encoding="utf-8-sig", errors="ignore") as sf:
                            sreader = csv.reader(sf)
                            _ = next(sreader) # header
                            srows = list(sreader)
                            for r_k, th_val in row_map.items():
                                if not th_val or not any('\u0e00' <= ch <= '\u0e7f' for ch in str(th_val)):
                                    continue
                                r_idx_int = int(r_k)
                                if 0 <= r_idx_int < len(srows):
                                    s_orig = srows[r_idx_int][0].strip()
                                    s_fn = srows[r_idx_int][2].strip() if len(srows[r_idx_int]) > 2 else ""
                                    if s_orig:
                                        checkpoint_content_map[(s_fn, s_orig)] = str(th_val)
                                        if s_orig not in checkpoint_fallback_map:
                                            checkpoint_fallback_map[s_orig] = str(th_val)
                    except Exception as ex:
                        print(f"[!] Note: Could not index source CSV {source_csv} for content mapping: {ex}")

            print(f"[*] Checkpoint loaded: {total_cached_items:,} cached entries. Resolved {len(checkpoint_content_map):,} verified Content Keys.")
        except Exception as e:
            print(f"[!] Warning reading checkpoint: {e}")

    print(f"[*] Reading Target CSV: {CSV_PATH}...")
    with open(CSV_PATH, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    total_rows = len(rows)
    displayable_yes = 0
    displayable_no = 0

    translated_thai = 0
    checkpoint_synced = 0
    pure_symbols_count = 0
    name_only_count = 0
    locked_terms_count = 0

    untranslated_by_role = Counter()
    untranslated_dialogues = []
    untranslated_others = []

    NON_TRANSLATABLE_ROLES = {
        'Event Name', 'Internal Variable/Switch', 'Script Code',
        'Plugin Command', 'Macro / Image', 'Developer Comment',
        'Common Event Name', 'Field: nickname'
    }

    import sys
    import argparse
    parser = argparse.ArgumentParser(description="ATF Translation Audit & Sync")
    parser.add_argument("--sync", action="store_true", help="Sync translations from Checkpoint into Target CSV")
    parser.add_argument("--show-all", action="store_true", default=True, help="Show all remaining dialogue items")
    args = parser.parse_args()

    # A. ตรวจสอบ Pure SFX (เช่น Zzz, zzzz, Ahhh, Uhhh) และ Currency (เช่น 650 GOLD!)
    def is_sfx_or_currency(text: str) -> bool:
        clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text).strip()
        # Snoring / Sleep SFX
        if re.match(r"^[Zz\.\s\!\,\|]+$", clean):
            return True
        # Currency rewards (e.g. 650 GOLD!, 200 GOLD)
        if re.match(r"^\d+\s*GOLD\!?$", clean, flags=re.IGNORECASE):
            return True
        # Puzzle / Math formula (e.g. (K = -5, V= 3, D = 14.))
        if re.match(r"^[\(\)\w\s\=\-\+\,\.]+$", clean) and any(op in clean for op in ["=", "+", "-"]):
            if not any(w in clean.lower() for w in ["the", "is", "you", "that", "this", "what", "are"]):
                return True
        return False

    sfx_currency_count = 0
    synced_count = 0

    for idx, row in enumerate(rows, start=1):
        if len(row) < 8:
            continue
        orig = row[0]
        initial = row[1]
        role = row[5] if row[5] else "Dialogue/Story"
        disp = row[7].strip().lower()

        if disp != "yes":
            displayable_no += 1
            continue

        displayable_yes += 1

        # A. ตรวจสอบว่าช่อง Initial มีภาษาไทยจริงในเนื้อหาบทสนทนาหรือไม่ (ป้องกัน Pseudo-Translated)
        has_tag_o, _, _, pure_orig = extract_speaker_tag(orig)
        has_tag_i, _, _, pure_init = extract_speaker_tag(initial)

        clean_pure_o = re.sub(r"\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]", "", pure_orig).strip()
        clean_pure_i = re.sub(r"\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]", "", pure_init).strip()

        has_th_pure = any('\u0e00' <= ch <= '\u0e7f' for ch in clean_pure_i)
        is_pseudo_translated = False

        if has_tag_i and not has_th_pure and re.search(r"[a-zA-Z]", clean_pure_o):
            # มีแท็กชื่อผู้พูด แต่เนื้อหาบทสนทนายังเป็นภาษาอังกฤษ -> หลุดการแปล (Pseudo-Translated)
            is_pseudo_translated = True

        has_th = any('\u0e00' <= ch <= '\u0e7f' for ch in initial)
        if has_th and not is_pseudo_translated:
            translated_thai += 1
            continue

        # B. ตรวจสอบว่าใน Checkpoint มีคำแปลหรือไม่ (จับคู่ด้วย Content-based Key เสมอ)
        row_fn = row[2].strip() if len(row) > 2 else ""
        orig_clean = orig.strip()
        cp_val = checkpoint_content_map.get((row_fn, orig_clean)) or checkpoint_fallback_map.get(orig_clean)

        if cp_val and any('\u0e00' <= ch <= '\u0e7f' for ch in cp_val):
            checkpoint_synced += 1
            if args.sync:
                row[1] = cp_val
                synced_count += 1
            continue

        # C. สกัด Speaker Tag
        has_tag, prefix, spk, pure_dialogue = extract_speaker_tag(orig)
        text_to_eval = pure_dialogue if has_tag else orig

        # D. ตรวจสอบ Pure Symbols / RPG Maker Codes / Numbers
        if is_pure_symbol_dialogue(text_to_eval):
            pure_symbols_count += 1
            continue

        # D.2 ตรวจสอบ SFX (Zzz) / Currency (650 GOLD!) / Puzzle Formula
        if is_sfx_or_currency(text_to_eval):
            sfx_currency_count += 1
            continue

        # E. ตรวจสอบ Name-Only Dialogue (เช่น Shion....?, Dan!, Raven.)
        if is_name_only_dialogue(text_to_eval, character_names, locked_terms):
            name_only_count += 1
            continue

        # F. ตรวจสอบ Locked Name / Term ตรงๆ
        clean_eval = re.sub(r"[^A-Za-z0-9]", "", text_to_eval).lower()
        if clean_eval in locked_terms or clean_eval in character_names:
            locked_terms_count += 1
            continue

        # G. ตรวจสอบ Non-translatable Role
        if role in NON_TRANSLATABLE_ROLES:
            pure_symbols_count += 1
            continue

        # H. หากหลุดมาถึงตรงนี้ แสดงว่าเป็นเนื้อหาที่ยังไม่ได้แปลจริงๆ
        untranslated_by_role[role] += 1
        if role == "Dialogue/Story":
            untranslated_dialogues.append((idx, role, spk, orig, initial))
        else:
            untranslated_others.append((idx, role, spk, orig, initial))

    # ถ้ามีการสั่ง --sync ให้เขียนลงไฟล์ CSV จริง
    if args.sync and synced_count > 0:
        temp_csv = CSV_PATH + ".tmp"
        with open(temp_csv, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerow(header)
            writer.writerows(rows)
        os.replace(temp_csv, CSV_PATH)
        print(f"\n[💾 SYNC COMPLETE] Flushed {synced_count:,} cached translations from Checkpoint into {CSV_PATH}!")
        translated_thai += checkpoint_synced
        checkpoint_synced = 0

    print(f"\n[*] Global Audit Summary:")
    print(f"  • Total CSV Rows:                         {total_rows:,}")
    print(f"  • Non-Displayable (Internal System):       {displayable_no:,}")
    print(f"  • Displayable ('Yes') Rows:               {displayable_yes:,}")
    print(f"  -------------------------------------------------------------")
    print(f"  • Fully Translated to Thai (In CSV):       {translated_thai:,}")
    if checkpoint_synced > 0:
        print(f"  • Checkpoint Cached Translations:          {checkpoint_synced:,} (Run with --sync to write to CSV)")
    print(f"  • Pure Symbols / Pauses:                   {pure_symbols_count:,}")
    print(f"  • SFX (Zzz) / Currency Rewards:            {sfx_currency_count:,}")
    print(f"  • Name-Only Calls (e.g. 'Shion...?'):      {name_only_count:,}")
    print(f"  • Locked English Terms / Names:            {locked_terms_count:,}")
    print(f"  -------------------------------------------------------------")
    total_resolved = (translated_thai + checkpoint_synced + pure_symbols_count + sfx_currency_count + name_only_count + locked_terms_count)
    completion_rate = (total_resolved / displayable_yes) * 100 if displayable_yes > 0 else 0
    print(f"  • Total Resolved / Completed:             {total_resolved:,} / {displayable_yes:,} ({completion_rate:.2f}%)")
    print(f"  • TRUE Untranslated Dialogues:            {len(untranslated_dialogues):,}")
    print(f"  • Other Roles (Items/Skills/UI):          {len(untranslated_others):,}")

    if untranslated_by_role:
        print(f"\n[*] Remaining Breakdown by Role:")
        for r_name, r_cnt in untranslated_by_role.most_common():
            print(f"  - {r_name:<28}: {r_cnt:,} items")

    if len(untranslated_dialogues) == 0:
        print("\n" + "=" * 80)
        print("🎉 100% DIALOGUE TRANSLATION COMPLETION CONFIRMED!")
        print("Every single game dialogue line in 'Dialogue/Story' is fully resolved!")
        print("=" * 80)
    else:
        print(f"\n[!] Samples of TRUE Untranslated Dialogues ({len(untranslated_dialogues)} items):")
        for u_idx, u_role, u_spk, u_orig, u_init in untranslated_dialogues:
            clean_snippet = re.sub(r"[\r\n]+", " ", u_orig)[:90]
            print(f"  - Row {u_idx:<5} [{u_spk}]: {clean_snippet}")

if __name__ == "__main__":
    main()

