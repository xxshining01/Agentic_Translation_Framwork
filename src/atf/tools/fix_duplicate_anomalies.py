#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix Duplicate Anomalies in ATF Processed CSV
===========================================
Deterministic correction of the verified duplicate overwrite rows caught by Master LQA Audit.
"""

import os
import sys
import csv
import argparse

CORRECTIONS = {
    735: "เมนูโทรศัพท์",
    3288: "เฝ้าดู",
    38972: "Damien, Shion 1",
    38982: "HJ1",
    74678: "Big B, Shivers 1",
    74688: "Troy",
    74691: "Damien, Shion 1",
    74839: "\\n<Shion:>Dan....",
    79652: "\\n<Dan:>Shion..?\\.",
    83307: "\\n<Dan:>Jinnie..?\\.",
    85959: "\\n<Dan:>Jinnie!!!",
    90544: "ประกายไฟ",
    90548: "ฟื้นคืนชีพ!",
    90554: "อมตะ",
    90585: "หลับใหล"
}

def fix_duplicates(csv_path: str, output_path: str = None):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    target_out = output_path or csv_path

    print(f"🔧 Applying deterministic fixes to {len(CORRECTIONS)} duplicate overwrite rows in: {csv_path}")
    
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    fixed_count = 0
    for row_idx, new_trans in CORRECTIONS.items():
        if row_idx < len(rows):
            orig = rows[row_idx][0]
            old_trans = rows[row_idx][1]
            rows[row_idx][1] = new_trans
            fixed_count += 1
            print(f"  • Row {row_idx:5d} [{orig}] : '{old_trans}' ➡️ '{new_trans}'")

    temp_out = target_out + ".tmp"
    with open(temp_out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    os.replace(temp_out, target_out)

    print(f"\n✅ Successfully updated {fixed_count} rows in: {target_out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix duplicate anomalies in processed CSV")
    parser.add_argument("--csv", type=str, default=r"E:\SummerStolenV035_PUBLIC_patch\New folder\processed_dialogues_v3_repaired.csv")
    args = parser.parse_args()
    fix_duplicates(args.csv)
