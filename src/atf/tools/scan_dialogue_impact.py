"""
Scan Dialogue Impact Script
ตรวจเช็คจำนวนแถวและ Batch ใน CSV ที่แปลแล้ว ที่ได้รับผลกระทบจากการแก้ Character Profile
"""

import os
import sys
import csv
import json
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "data", "tlas", "chatgpt_translation_checkpoint.json")

TARGET_CHARACTERS = {"Drake", "Damien", "Drex"}

def scan():
    if not os.path.exists(CSV_PATH):
        print(f"[!] CSV not found at {CSV_PATH}")
        return

    total_rows = 0
    impacted_rows = []
    impacted_speakers = defaultdict(int)
    impacted_with_ka = [] # ตัวละครชายแต่มี ค่ะ/คะ ในคำแปล

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for idx, row in enumerate(reader):
            total_rows += 1
            speaker = row.get("Speaker", "").strip()
            th_trans = row.get("Th_Trans", "") or row.get("th", "")

            # Check if speaker is one of the target characters
            for tc in TARGET_CHARACTERS:
                if tc.lower() in speaker.lower():
                    impacted_speakers[tc] += 1
                    impacted_rows.append((idx, speaker, row.get("En", ""), th_trans))
                    if any(p in th_trans for p in ["ค่ะ", "คะ", "จ้ะ"]):
                        impacted_with_ka.append((idx, speaker, th_trans))
                    break

    print("="*65)
    print("=== DIALOGUE IMPACT SCAN RESULTS ===")
    print("="*65)
    print(f"Total Rows in Game CSV: {total_rows}")
    print(f"Total Impacted Rows for (Drake, Damien, Drex): {len(impacted_rows)} rows ({(len(impacted_rows)/total_rows)*100:.2f}%)")
    for spk, cnt in impacted_speakers.items():
        print(f" - {spk}: {cnt} dialogue lines")
    print(f"Lines where male character used feminine particles ('ค่ะ'/'คะ'/'จ้ะ'): {len(impacted_with_ka)} lines")
    print("="*65)

    if impacted_with_ka:
        print("\n[Sample Dialogue Lines with Feminine Particle Mismatch]:")
        for idx, spk, th in impacted_with_ka[:10]:
            print(f" * Row {idx} [{spk}]: {th}")

    # Check corresponding batches in checkpoint
    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                ckpt = json.load(f)
            # Batches are typically 15 items per batch
            batch_indices = set()
            for r_idx, _, _, _ in impacted_rows:
                batch_indices.add((r_idx // 15) + 1)
            print(f"\nTotal Batches Containing These Characters: {len(batch_indices)} batches out of 643 batches")
            print(f"Batch Numbers: {sorted(list(batch_indices))[:20]} ...")
        except Exception as e:
            print(f"[!] Checkpoint check error: {e}")

if __name__ == "__main__":
    scan()
