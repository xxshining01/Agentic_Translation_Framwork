#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Speaker & Entity Scanner
สแกนค้นหารายชื่อตัวละคร (Speaker Tags) และจำแนกประเภทข้อความจากไฟล์ CSV ทุกภาษา
รองรับทั้งสไตล์ญี่ปุ่น (【名前】) และสากล (<Name:>) พร้อมวิเคราะห์ความถี่ตามกฎ ADR-035
"""

import os
import sys
import csv
import json
import re
from collections import Counter, defaultdict

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")

# Regex สำหรับตรวจจับ Speaker Tags รูปแบบต่างๆ
SPEAKER_PATTERNS = [
    # ญี่ปุ่น: 【夫】, 【凛】, 【遠藤】, 【？？？】
    re.compile(r'^[【\[]([^】\]\r\n]+)[】\]]'),
    # สากล/Plugin: \n<Name:>, \n<Name>, <Name:>
    re.compile(r'^(?:\\n)?<([^:>]+):?>'),
    # RPG Maker Name Code: \N[1], \n[1]
    re.compile(r'^(?:\\n)?\\N\[(\d+)\]', re.IGNORECASE)
]

# คำสั่งระบบ/ปลั๊กอิน ที่ไม่ใช่บทสนทนาแสดงผล
ENGINE_NOISE_PATTERNS = [
    re.compile(r'^EV\d+', re.IGNORECASE),
    re.compile(r'^<[^>]+>$'),                 # เช่น <Darkness:100>
    re.compile(r'^灯り\s+\d+'),                # คำสั่งแสงสว่างปลั๊กอิน
    re.compile(r'^D_TEXT\s+', re.IGNORECASE),  # คำสั่งแสดงข้อความปลั๊กอิน
    re.compile(r'^[・…―\-~～\.\s]+$'),         # เครื่องหมายวรรคตอนล้วน
]

CHOICE_KEYWORDS = {"はい", "いいえ", "yes", "no", "やめる", "続ける", "決定", "キャンセル"}


def clean_tag(raw_name: str) -> str:
    """ทำความสะอาดชื่อ ลบช่องว่างหรืออักขระพิเศษส่วนเกิน"""
    return raw_name.strip()


def scan_csv(csv_path: str, data_dir: str = None):
    print("=" * 80)
    print("        ATF UNIVERSAL SPEAKER & ENTITY EXTRACTION ENGINE (v1.0)        ")
    print("=" * 80)
    print(f"[*] Analyzing Target CSV: {csv_path}")

    if not os.path.exists(csv_path):
        print(f"❌ Error: ไม่พบไฟล์ CSV ที่: {csv_path}")
        sys.exit(1)

    # โหลด Actors.json เพื่อใช้อ้างอิงรายชื่อตั้งต้นของระบบ
    known_actors = {}
    if data_dir and os.path.exists(os.path.join(data_dir, "Actors.json")):
        try:
            with open(os.path.join(data_dir, "Actors.json"), "r", encoding="utf-8") as f:
                actors_data = json.load(f)
                for act in actors_data:
                    if act and "name" in act and act["name"]:
                        known_actors[act["name"]] = act
            print(f"[*] Loaded {len(known_actors)} predefined actors from Actors.json: {list(known_actors.keys())}")
        except Exception as e:
            print(f"[!] Warning: ไม่สามารถอ่าน Actors.json: {e}")

    speaker_counts = Counter()
    speaker_samples = defaultdict(list)
    system_choices = Counter()
    engine_commands = Counter()
    unnamed_dialogues = 0
    total_rows = 0

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        
        for r_idx, row in enumerate(reader, start=2):
            total_rows += 1
            if not row or not row[0].strip():
                continue

            orig = row[0].strip()
            filename = row[2].strip() if len(row) > 2 else ""

            # 1. ตรวจสอบว่าเป็น Engine Command หรือไม่
            is_noise = False
            for pat in ENGINE_NOISE_PATTERNS:
                if pat.search(orig):
                    engine_commands[orig] += 1
                    is_noise = True
                    break
            if is_noise:
                continue

            # 2. ตรวจสอบว่าเป็น Choice หรือไม่
            if orig in CHOICE_KEYWORDS:
                system_choices[orig] += 1
                continue

            # 3. ค้นหา Speaker Tag
            matched_speaker = None
            pure_text = orig

            for pat in SPEAKER_PATTERNS:
                m = pat.search(orig)
                if m:
                    matched_speaker = clean_tag(m.group(1))
                    # ตัด tag ออกเพื่อให้ได้บทสนทนาเพียวๆ
                    pure_text = orig[m.end():].lstrip("\r\n :")
                    break

            if matched_speaker:
                speaker_counts[matched_speaker] += 1
                if len(speaker_samples[matched_speaker]) < 3 and pure_text:
                    clean_sample = pure_text.replace("\n", " ")[:60]
                    speaker_samples[matched_speaker].append(clean_sample)
            else:
                # ถ้าไม่มี Tag แต่มีข้อความและไม่ได้อยู่ในไฟล์ระบบ
                if any(k in orig for k in ["「", "」", "。", "、", "？", "！", "..."]) or len(orig) > 6:
                    unnamed_dialogues += 1

    print("\n" + "=" * 80)
    print("                    DISTINCT SPEAKERS AUDIT REPORT                    ")
    print("=" * 80)
    print(f"{'Speaker Tag':<25} | {'Lines':<8} | {'Category (ADR-035)':<20} | {'Sample Text'}")
    print("-" * 80)

    results_for_export = []
    
    # เกณฑ์ ADR-035 สำหรับเกมขนาดกะทัดรัด: >= 20 บรรทัด = Core / Main Story
    for spk, count in speaker_counts.most_common():
        category = "Core / Main Story" if count >= 20 else "Secondary / Transient"
        sample_str = speaker_samples[spk][0] if speaker_samples[spk] else ""
        print(f"{spk:<25} | {count:<8} | {category:<20} | {sample_str[:25]}...")

        results_for_export.append({
            "speaker_tag": spk,
            "dialogue_count": count,
            "category": category,
            "samples": speaker_samples[spk]
        })

    print("-" * 80)
    print(f"📊 สรุปผลการสแกน:")
    print(f"   - แถวทั้งหมดใน CSV:          {total_rows:,} แถว")
    print(f"   - บทสนทนาที่มี Speaker Tag:   {sum(speaker_counts.values()):,} แถว ({len(speaker_counts)} ตัวละคร)")
    print(f"   - บทบรรยาย/ประโยคไม่มี Tag:   {unnamed_dialogues:,} แถว")
    print(f"   - ตัวเลือกเมนู (Choices):       {sum(system_choices.values()):,} แถว")
    print(f"   - คำสั่งระบบ/Noise ในโค้ด:      {sum(engine_commands.values()):,} แถว")
    print("=" * 80 + "\n")

    # บันทึกผลลัพธ์ลง data/tlas/scanned_speakers.json
    out_dir = os.path.join(WORKSPACE_ROOT, "data", "tlas")
    os.makedirs(out_dir, exist_ok=True)
    out_json = os.path.join(out_dir, "scanned_speakers.json")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "target_csv": csv_path,
            "total_rows": total_rows,
            "distinct_speakers_count": len(speaker_counts),
            "speakers": results_for_export,
            "system_choices": dict(system_choices),
            "engine_commands_sample": dict(engine_commands.most_common(20))
        }, f, ensure_ascii=False, indent=2)

    print(f"💾 บันทึกรายงานการสแกนฉบับสมบูรณ์ลง: {out_json}")
    return results_for_export


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else None
    game_data = None

    if not csv_file and os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
                csv_file = m_data.get("raw_pre_csv")
                game_data = m_data.get("game_data_directory")
        except Exception:
            pass

    if not csv_file:
        # Default ไปยังเกมใหม่ใน Example RPGM Game
        csv_file = os.path.join(WORKSPACE_ROOT, "Example RPGM Game", "離れ木の5日間+ - ชีต1.csv")
        game_data = os.path.join(WORKSPACE_ROOT, "Example RPGM Game", "離れ木の5日間+", "www", "data")

    scan_csv(csv_file, game_data)
