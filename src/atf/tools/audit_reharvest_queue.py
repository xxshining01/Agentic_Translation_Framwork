#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit & Refine Reharvest Queue with Deep Dialogue Context
ตรวจสอบ, คัดกรอง, และเติมเต็มบริบทแวดล้อมให้กับ untranslated_dialogues_reharvest.json:
1. ตัด MapInfos และบทบาทที่เป็นขยะระบบ (Internal Engine Data) ออก 100%
2. ดึงบริบทบทสนทนาก่อนหน้า (Context Before) และถัดไป (Context After) จาก CSV
   รวมทั้งคำแปลภาษาไทยของประโยครอบข้าง เพื่อให้โมเดล AI เห็นภาพรวมของบทสนทนาที่ต่อเนื่อง
3. สรุปจำแนกตามตัวละคร และแสดงตัวอย่างประโยคพร้อมบริบท
4. บันทึกผลลัพธ์เป็น Reharvest Queue ฉบับสมบูรณ์ (Context-Enriched Queue)
"""

import os
import re
import csv
import json
from collections import Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
QUEUE_PATH = os.path.join(TLAS_DATA, "untranslated_dialogues_reharvest.json")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")

def clean_dialogue_line(text: str) -> str:
    """ทำความสะอาดข้อความสำหรับการแสดงบริบท"""
    if not text:
        return ""
    # แทนที่ newline ด้วย space
    s = re.sub(r"[\r\n]+", " ", text).strip()
    return s

def main():
    print("=" * 80)
    print("=== ATF REHARVEST QUEUE AUDIT & DEEP CONTEXT ENRICHMENT ===")
    print("=" * 80)

    if not os.path.exists(QUEUE_PATH):
        print(f"[!] Queue file not found: {QUEUE_PATH}")
        return

    if not os.path.exists(CSV_PATH):
        print(f"[!] Target CSV file not found: {CSV_PATH}")
        return

    # 1. โหลดไฟล์ CSV ทั้งหมดเพื่อใช้สกัดบริบทแวดล้อม
    print(f"[*] Loading CSV for surrounding context extraction: {os.path.basename(CSV_PATH)}...")
    with open(CSV_PATH, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        csv_rows = list(reader)
    print(f"[*] Loaded {len(csv_rows):,} CSV rows.")

    # 2. โหลด Queue เดิม
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    print(f"[*] Raw Items in Reharvest Queue: {len(items):,}")

    # 3. คัดกรองขยะระบบ และเติมบริบทบทสนทนาแวดล้อม (Context Enrichment)
    refined_items = []
    dropped_non_dialogue = []

    for it in items:
        fn = it.get("filename", "")
        role = it.get("role", "")
        orig = it.get("original", "")
        prefix = it.get("prefix", "")
        r_idx = it.get("csv_index", 0) - 2 # 0-indexed in csv_rows (header is row 1)

        # 3.1 ตัด MapInfos (ชื่อโฟลเดอร์/แมพในระบบ RPG Maker)
        if fn == "MapInfos":
            dropped_non_dialogue.append((fn, role, orig, "MapInfos internal tree"))
            continue

        # 3.2 ถ้าเป็น Entity Name แต่ไม่มีแท็กผู้พูด และเป็นชื่อสั้นๆ โดดๆ ของระบบ
        if role == "Entity Name" and not prefix:
            dropped_non_dialogue.append((fn, role, orig, "Entity Name without speaker"))
            continue

        # 3.3 สกัดบริบทแวดล้อมก่อนหน้า (Context Before) 1-2 บรรทัด
        ctx_before = []
        if 0 <= r_idx < len(csv_rows):
            for b_i in range(max(0, r_idx - 2), r_idx):
                b_orig = clean_dialogue_line(csv_rows[b_i][0] if len(csv_rows[b_i]) > 0 else "")
                b_init = clean_dialogue_line(csv_rows[b_i][1] if len(csv_rows[b_i]) > 1 else "")
                b_disp = csv_rows[b_i][7].strip().lower() if len(csv_rows[b_i]) > 7 else ""
                if b_disp == "yes" and b_orig:
                    has_th = bool(re.search(r'[\u0E00-\u0E7F]', b_init))
                    if has_th and b_init != b_orig:
                        ctx_before.append(f"{b_orig} [คำแปลไทย: {b_init}]")
                    else:
                        ctx_before.append(b_orig)

            # 3.4 สกัดบริบทแวดล้อมถัดไป (Context After) 1-2 บรรทัด
            ctx_after = []
            for a_i in range(r_idx + 1, min(len(csv_rows), r_idx + 3)):
                a_orig = clean_dialogue_line(csv_rows[a_i][0] if len(csv_rows[a_i]) > 0 else "")
                a_init = clean_dialogue_line(csv_rows[a_i][1] if len(csv_rows[a_i]) > 1 else "")
                a_disp = csv_rows[a_i][7].strip().lower() if len(csv_rows[a_i]) > 7 else ""
                if a_disp == "yes" and a_orig:
                    has_th = bool(re.search(r'[\u0E00-\u0E7F]', a_init))
                    if has_th and a_init != a_orig:
                        ctx_after.append(f"{a_orig} [คำแปลไทย: {a_init}]")
                    else:
                        ctx_after.append(a_orig)

            surrounding_context = {}
            if ctx_before:
                surrounding_context["preceding_dialogue"] = " | ".join(ctx_before)
            if ctx_after:
                surrounding_context["subsequent_dialogue"] = " | ".join(ctx_after)

            it["surrounding_context"] = surrounding_context

        refined_items.append(it)

    print(f"\n[*] Filter Summary:")
    print(f"  • Dropped Non-Dialogue / System Tree Items: {len(dropped_non_dialogue):,}")
    print(f"  • Clean & Context-Enriched Dialogue Items:   {len(refined_items):,}")

    # สถิติตามตัวละคร
    speaker_counter = Counter()
    role_counter = Counter()
    map_counter = Counter()

    for it in refined_items:
        spk = it.get("speaker") or "[Narration / Ambient]"
        speaker_counter[spk] += 1
        role_counter[it.get("role", "Unknown")] += 1
        map_counter[it.get("filename", "Unknown")] += 1

    print("\n--- TOP 15 SPEAKERS IN ENRICHED QUEUE ---")
    for spk, cnt in speaker_counter.most_common(15):
        print(f"  • {spk:25}: {cnt:4} lines")

    # ตัวอย่างพร้อมบริบทแวดล้อม (Context Demonstration)
    print("\n" + "=" * 80)
    print("=== DEMONSTRATION: RESIDUAL FRAGMENTS WITH SURROUNDING CONTEXT ===")
    print("=" * 80)
    samples_to_show = ["T-Ten times", "W-.W-.Wonderful", "Hey..! Ugh, dummy", "Gurantheed", "Am not"]
    shown = 0
    for it in refined_items:
        orig = it.get("original", "")
        for s in samples_to_show:
            if s.lower() in orig.lower():
                spk = it.get("speaker") or "Unknown"
                ctx = it.get("surrounding_context", {})
                print(f"\n[Dialogue Fragment #{it.get('csv_index')}] {it.get('filename')}:{it.get('row')} ({spk})")
                print(f"  ◀ Context Before: {ctx.get('preceding_dialogue', 'N/A')}")
                print(f"  ⭐ TARGET FRAGMENT: {orig}")
                print(f"  ▶ Context After:  {ctx.get('subsequent_dialogue', 'N/A')}")
                shown += 1
                break
        if shown >= 5:
            break

    # อัปเดต Queue ด้วยชุดที่สมบูรณ์พร้อมบริบท
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(refined_items, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"[v] Successfully saved {len(refined_items):,} context-enriched dialogue lines to:")
    print(f"    {QUEUE_PATH}")
    print("[v] Ready for Context-Aware Translation!")

if __name__ == "__main__":
    main()
