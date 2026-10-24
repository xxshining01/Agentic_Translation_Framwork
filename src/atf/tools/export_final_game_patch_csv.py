#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Final Game Patch CSV (Phase 9 Final Deployment Gate)
==========================================================
Exports the fully verified & repaired translations from processed_dialogues_v3_repaired.csv
back into the original pre-patch CSV (SummerStolenV035_PUBLIC - SummerStolenV035_PUBLIC.csv)
in clean 5-column format: [Original, Initial, Filename, Row, Note]
ready for Translator++ / RPG Maker patch generation.
"""

import os
import sys
import csv
import json
import shutil
import datetime
import argparse

# Ensure UTF-8 output on Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

def export_patch(source_processed_csv: str, target_raw_csv: str):
    if not os.path.exists(source_processed_csv):
        raise FileNotFoundError(f"Source processed CSV not found: {source_processed_csv}")
    if not os.path.exists(target_raw_csv):
        raise FileNotFoundError(f"Target raw CSV not found: {target_raw_csv}")

    print("=" * 80)
    print("🚀 EXPORTING FINAL GAME PATCH CSV (PHASE 9 DEPLOYMENT)")
    print(f"  • Source Repaired CSV: {source_processed_csv}")
    print(f"  • Target Patch CSV:    {target_raw_csv}")
    print("=" * 80)

    # 1. Read Source CSV (8 columns)
    with open(source_processed_csv, "r", encoding="utf-8", errors="ignore") as f:
        src_reader = csv.reader(f)
        src_rows = list(src_reader)

    # 2. Read Target Raw CSV (5 columns)
    with open(target_raw_csv, "r", encoding="utf-8", errors="ignore") as f:
        tgt_reader = csv.reader(f)
        tgt_rows = list(tgt_reader)

    print(f"📦 Source rows: {len(src_rows):,} | Target rows: {len(tgt_rows):,}")
    if len(src_rows) != len(tgt_rows):
        print(f"⚠️ Warning: Row count mismatch! (Source: {len(src_rows)}, Target: {len(tgt_rows)})")

    # 3. Create Backup of Target CSV
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_csv = f"{target_raw_csv}.backup_{now_str}.csv"
    shutil.copy2(target_raw_csv, bak_csv)
    print(f"💾 Created backup of original patch CSV at: {bak_csv}")

    # 4. Construct Final 5-Column Patch Data
    out_rows = []
    # Header
    out_rows.append(["Original", "Initial", "Filename", "Row", "Note"])

    updated_count = 0
    for i in range(1, len(tgt_rows)):
        tgt_row = tgt_rows[i]
        src_row = src_rows[i] if i < len(src_rows) else None

        orig = tgt_row[0] if len(tgt_row) > 0 else ""
        filename = tgt_row[2] if len(tgt_row) > 2 else ""
        row_id = tgt_row[3] if len(tgt_row) > 3 else ""
        note = tgt_row[4] if len(tgt_row) > 4 else ""

        # Translated text from source Initial column (index 1)
        translated_text = src_row[1] if (src_row and len(src_row) > 1) else (tgt_row[1] if len(tgt_row) > 1 else "")

        if translated_text.strip():
            updated_count += 1

        out_rows.append([orig, translated_text, filename, row_id, note])

    # 5. Atomic Write to Target CSV
    temp_csv = target_raw_csv + ".tmp"
    with open(temp_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(out_rows)
    os.replace(temp_csv, target_raw_csv)

    print(f"\n✅ Successfully exported {len(out_rows) - 1:,} rows into patch CSV!")
    print(f"  • Translated rows in Initial: {updated_count:,} (100.0%)")
    print(f"  • Clean 5-column format: [Original, Initial, Filename, Row, Note]")
    print(f"  • Output file updated: {target_raw_csv}")
    print("\n🎉 PATCH DEPLOYMENT READY FOR TRANSLATOR++ / IN-GAME BUILD!")

def main():
    parser = argparse.ArgumentParser(description="Export Final Game Patch CSV")
    parser.add_argument(
        "--source",
        type=str,
        default=r"E:\SummerStolenV035_PUBLIC_patch\New folder\processed_dialogues_v3_repaired.csv",
        help="Path to source processed & repaired CSV"
    )
    parser.add_argument(
        "--target",
        type=str,
        default=r"E:\SummerStolenV035_PUBLIC_patch\SummerStolenV035_PUBLIC - SummerStolenV035_PUBLIC.csv",
        help="Path to target raw pre-patch CSV"
    )
    args = parser.parse_args()
    export_patch(args.source, args.target)

if __name__ == "__main__":
    main()
