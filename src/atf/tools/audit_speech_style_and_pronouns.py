#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Speech Style & Pronoun Mismatch Inspector
เครื่องมือตรวจสอบความผิดปกติของสรรพนามและระดับความสุภาพ (Speech Register & Politeness)
โดยเฉพาะกรณีตัวละครหยาบคาย/กวน/สนิทสนม แต่หลุดใช้คำสุภาพ (ผม/คุณ/ครับ) เช่น Jords กับ Dan
"""

import os
import sys
import re
import csv
import argparse
from collections import defaultdict
from typing import List, Dict, Any

# คำสรรพนามและหางเสียงที่ต้องการตรวจสอบ
POLITE_MALE_WORDS = ["ผม", "ครับ", "นะครับ", "ขอรับ"]
POLITE_TARGET_WORDS = ["คุณ", "ท่าน"]
CASUAL_MALE_WORDS = ["กู", "ข้า", "ฉัน", "เรา", "พี่"]
CASUAL_TARGET_WORDS = ["มึง", "เอ็ง", "แก", "นาย"]
ROUGH_PARTICLES = ["วะ", "เว้ย", "โว้ย", "เหวย"]

# ลิสต์ตัวละครที่รู้แน่ชัดว่าไม่ใช่คนสุภาพ / ห้ามใช้ "ผม/ครับ/คุณ" กับตัวละครเอก (Dan)
ROUGH_CHARACTERS = {
    "jords": "Jords (บาร์เทนเดอร์/เพื่อนร่วมงานสายกวน หยาบคาย ไม่พูดครับ/ผมกับ Dan)",
    "jordan": "Jordan (ร่างหลักของ Jords)",
    "shivers": "Shivers (นักเลง/มาเฟีย)",
    "big b": "Big B (นักเลง)",
    "troy": "Troy (หนุ่มห้าว/นักเลง)",
    "drex": "Drex (หนุ่มเกเร)",
    "thug": "Thug (อันธพาล)",
    "ruffian": "Ruffian (คนพาล)",
    "fratboy": "Fratboy (เด็กบ้านรวยเกเร)",
}


def audit_speech_styles(csv_path: str, output_report: str = None):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ไม่พบไฟล์ CSV: {csv_path}")

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("ไฟล์ CSV ว่างเปล่า")

    header = [h.strip().lower() for h in rows[0]]
    init_col = header.index("initial")
    orig_col = header.index("original")
    speaker_col = header.index("speaker") if "speaker" in header else None
    role_col = header.index("role") if "role" in header else None
    row_col = header.index("row") if "row" in header else None
    file_col = header.index("filename") if "filename" in header else None

    # สถิติต่อ Speaker
    speaker_stats = defaultdict(lambda: {
        "total_lines": 0,
        "polite_self": 0,    # ผม
        "polite_particle": 0,# ครับ
        "polite_target": 0,  # คุณ
        "casual_self": 0,    # กู, ข้า, ฉัน
        "casual_target": 0,  # มึง, เอ็ง, แก, นาย
        "rough_particle": 0, # วะ, เว้ย
        "female_particle": 0,# ค่ะ, คะ
    })

    # แถวที่มีปัญหาของ Jords / Jordan
    jords_anomalies = []
    # แถวที่มีปัญหาของตัวละครห้าวอื่นๆ
    rough_char_anomalies = []
    # ตัวละครทั่วไปที่อาจหลุดสำนวน
    general_inconsistencies = []

    for idx, r in enumerate(rows[1:], start=2):
        if len(r) <= init_col:
            continue

        init_text = r[init_col].strip()
        orig_text = r[orig_col].strip() if orig_col < len(r) else ""
        speaker = r[speaker_col].strip() if speaker_col is not None and speaker_col < len(r) else ""
        role = r[role_col].strip() if role_col is not None and role_col < len(r) else ""
        row_id = r[row_col].strip() if row_col is not None and row_col < len(r) else str(idx)
        filename = r[file_col].strip() if file_col is not None and file_col < len(r) else ""

        if not init_text:
            continue

        # สกัดชื่อผู้พูดจาก Tag ในข้อความหากไม่มีในคอลัมน์ Speaker
        clean_speaker = speaker
        m_tag = re.search(r'[<\[【]([^>\]】:]+):?[>\]】]', init_text)
        if m_tag:
            clean_speaker = m_tag.group(1).strip()
        elif not clean_speaker:
            m_orig = re.search(r'[<\[【]([^>\]】:]+):?[>\]】]', orig_text)
            if m_orig:
                clean_speaker = m_orig.group(1).strip()

        speaker_lower = clean_speaker.lower()
        stats = speaker_stats[clean_speaker]
        stats["total_lines"] += 1

        # ตรวจสอบการใช้คำใน Initial
        has_phom = bool(re.search(r'\bผม\b|(?<![ก-๙])ผม(?![ก-๙])', init_text))
        has_khrap = bool(re.search(r'ครับ|นะครับ|ขอรับ', init_text))
        has_khun = bool(re.search(r'\bคุณ\b|(?<![ก-๙])คุณ(?![ก-๙])', init_text))
        
        has_casual_self = bool(re.search(r'กู|ข้า|ฉัน|เรา', init_text))
        has_casual_target = bool(re.search(r'มึง|เอ็ง|แก|นาย', init_text))
        has_rough = bool(re.search(r'วะ|เว้ย|โว้ย', init_text))
        has_female_part = bool(re.search(r'ค่ะ|คะ|นะคะ', init_text))

        if has_phom: stats["polite_self"] += 1
        if has_khrap: stats["polite_particle"] += 1
        if has_khun: stats["polite_target"] += 1
        if has_casual_self: stats["casual_self"] += 1
        if has_casual_target: stats["casual_target"] += 1
        if has_rough: stats["rough_particle"] += 1
        if has_female_part: stats["female_particle"] += 1

        # 1. ตรวจจับ Jords / Jordan หลุดสุภาพ
        if any(j in speaker_lower for j in ["jords", "jordan"]):
            if has_phom or has_khrap or has_khun:
                found_words = []
                if has_phom: found_words.append("สรรพนาม 'ผม'")
                if has_khrap: found_words.append("หางเสียง 'ครับ'")
                if has_khun: found_words.append("เรียกคู่สนทนา 'คุณ'")
                jords_anomalies.append({
                    "row_idx": idx,
                    "row_id": row_id,
                    "speaker": clean_speaker,
                    "filename": filename,
                    "issues": ", ".join(found_words),
                    "original": orig_text,
                    "initial": init_text
                })

        # 2. ตรวจจับตัวละครสายห้าว / นักเลง หลุดสุภาพ
        for rk, rdesc in ROUGH_CHARACTERS.items():
            if rk in speaker_lower and not any(j in speaker_lower for j in ["jords", "jordan"]):
                if has_phom or has_khrap or has_khun:
                    found_words = []
                    if has_phom: found_words.append("สรรพนาม 'ผม'")
                    if has_khrap: found_words.append("หางเสียง 'ครับ'")
                    if has_khun: found_words.append("เรียกคู่สนทนา 'คุณ'")
                    rough_char_anomalies.append({
                        "row_idx": idx,
                        "row_id": row_id,
                        "speaker": clean_speaker,
                        "char_type": rdesc,
                        "filename": filename,
                        "issues": ", ".join(found_words),
                        "original": orig_text,
                        "initial": init_text
                    })
                break

    # รายงานผลบนหน้าจอ Terminal
    print("\n" + "=" * 80)
    print("      ATF SPEECH STYLE & PRONOUN MISMATCH INSPECTION REPORT      ")
    print("=" * 80)
    print(f"Target CSV: {csv_path}")
    print(f"Total Rows: {len(rows):,}")
    print("-" * 80)
    print(f"🚨 [เคสที่ 1] แถวของ Jords / Jordan ที่หลุดพูดสุภาพ (ผม/คุณ/ครับ):  {len(jords_anomalies):,} แถว")
    print(f"🚨 [เคสที่ 2] แถวของตัวละครสายห้าว/นักเลงอื่นๆ ที่หลุดพูดสุภาพ:     {len(rough_char_anomalies):,} แถว")
    print("-" * 80)

    # แสดงตัวอย่าง Jords
    if jords_anomalies:
        print("\n🔍 รายการแถวที่พบของ Jords / Jordan (ตัวอย่าง 10 แถวแรก):")
        for item in jords_anomalies[:10]:
            print(f"  • [Row {item['row_idx']} | ID {item['row_id']}] ({item['issues']}):")
            print(f"    ORIG: {repr(item['original'][:70])}")
            print(f"    INIT: {repr(item['initial'][:70])}")

    # แสดงตัวอย่างตัวละครสายห้าวอื่นๆ
    if rough_char_anomalies:
        print("\n🔍 รายการแถวของตัวละครสายห้าว/นักเลงอื่นๆ ที่หลุดพูดสุภาพ (ตัวอย่าง 10 แถวแรก):")
        for item in rough_char_anomalies[:10]:
            print(f"  • [Row {item['row_idx']} | ID {item['row_id']}] Speaker: '{item['speaker']}' ({item['issues']}):")
            print(f"    ORIG: {repr(item['original'][:70])}")
            print(f"    INIT: {repr(item['initial'][:70])}")

    # สรุปภาพรวมของตัวละครที่มีบทสนทนาสูงและมีความขัดแย้งในตัวเอง
    print("\n📊 สรุปความขัดแย้งของระดับภาษาในตัวละครเด่น (Pronoun & Politeness Split):")
    for spk, st in sorted(speaker_stats.items(), key=lambda x: x[1]["total_lines"], reverse=True):
        if st["total_lines"] >= 30 and (st["polite_self"] > 0 or st["polite_particle"] > 0):
            # คำนวณอัตราส่วน
            p_rate = (st["polite_self"] + st["polite_particle"]) / st["total_lines"] * 100
            c_rate = (st["casual_self"] + st["rough_particle"]) / st["total_lines"] * 100
            if p_rate > 5 and c_rate > 5:
                print(f"  • Speaker '{spk}' ({st['total_lines']} บท): สุภาพ (ผม/ครับ) {st['polite_self'] + st['polite_particle']} ครั้ง ({p_rate:.1f}%) ⚡ กวน/หยาบ (กู/ข้า/วะ) {st['casual_self'] + st['rough_particle']} ครั้ง ({c_rate:.1f}%)")

    # ส่งออกตารางรายงานฉบับเต็มลง CSV
    if not output_report:
        output_report = os.path.join(os.path.dirname(csv_path), "audit_speech_mismatches_report.csv")

    all_anomalies = jords_anomalies + rough_char_anomalies
    with open(output_report, "w", encoding="utf-8-sig", newline="") as rf:
        writer = csv.writer(rf)
        writer.writerow(["Row_Index", "Row_ID", "Speaker", "Category", "Issues_Found", "Filename", "Original", "Initial"])
        for item in jords_anomalies:
            writer.writerow([item["row_idx"], item["row_id"], item["speaker"], "Jords/Jordan Mismatch", item["issues"], item["filename"], item["original"], item["initial"]])
        for item in rough_char_anomalies:
            writer.writerow([item["row_idx"], item["row_id"], item["speaker"], "Rough Character Mismatch", item["issues"], item["filename"], item["original"], item["initial"]])

    print(f"\n📋 ส่งออกตารางรายงานความผิดปกติทั้งหมด ({len(all_anomalies):,} แถว) ไปที่:\n   👉 {output_report}")
    return all_anomalies


def main():
    parser = argparse.ArgumentParser(description="ATF Speech Style & Pronoun Mismatch Inspector")
    parser.add_argument("--csv", type=str, required=True, help="Path to CSV file")
    parser.add_argument("--output", type=str, default=None, help="Output CSV report path")
    args = parser.parse_args()

    audit_speech_styles(args.csv, args.output)


if __name__ == "__main__":
    main()
