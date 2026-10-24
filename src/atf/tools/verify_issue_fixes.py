#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification Script for ATF Issue Fixes:
1. Check for remaining literal '\\n' in dialogue content.
2. Check if 'Pink hair Woman' speaker tag is translated.
3. Check if 'Pink hair Woman' still has masculine particles (ผม/ครับ).
"""

import os
import sys
import re
import csv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")

def main():
    print("=" * 70)
    print("=== ATF ISSUE FIXES AUDIT & VERIFICATION ===")
    print("=" * 70)

    if not os.path.exists(CSV_PATH):
        print(f"[!] Error: CSV file not found at {CSV_PATH}")
        return

    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = rows[0]
    data_rows = rows[1:]
    print(f"[*] Scanning {len(data_rows)} rows in CSV...")

    literal_nl_issues = []
    untranslated_pink_hair = []
    pink_hair_masculine_lines = []
    pink_hair_samples = []

    for idx, row in enumerate(data_rows, start=1):
        if len(row) < 2:
            continue
        thai = row[1]
        if not thai:
            continue

        # แยกแท็กนำหน้า
        m = re.match(r"^(\s*\\n)?<([^>]+)>", thai)
        if m:
            prefix = m.group(0)
            dialogue = thai[len(prefix):]
        else:
            prefix = ""
            dialogue = thai

        # 1. เช็ค literal \n ในเนื้อความบทพูด
        if "\\n" in dialogue or "\\r\\n" in dialogue:
            literal_nl_issues.append((idx, row[2] if len(row) > 2 else "", thai[:80]))

        # 2. เช็ค Pink hair Woman ที่ยังไม่ถูกแปล (ต้องไม่เหลือ Pink hair Woman หรือ หญิงสาวผมชมพู ในแท็ก)
        if "Pink hair Woman" in thai or (len(row) > 6 and "Pink hair Woman" in row[6]) or "หญิงสาวผมชมพู" in thai:
            untranslated_pink_hair.append((idx, row[2] if len(row) > 2 else "", thai[:80]))

        # 3. เช็คบทพูดของ ผู้หญิงผมชมพู ว่ามี ผม/ครับ หรือไม่
        if "ผู้หญิงผมชมพู" in thai or (len(row) > 6 and "ผู้หญิงผมชมพู" in row[6]):
            # ตรวจสอบคำสรรพนามหรือหางเสียงชาย โดยยกเว้นคำว่า "เส้นผม", "ทรงผม"
            clean_diag = dialogue.replace("เส้นผม", "").replace("ทรงผม", "")
            if re.search(r"ครับ|ผม(?![า-๙])|ฮะ", clean_diag):
                pink_hair_masculine_lines.append((idx, row[2] if len(row) > 2 else "", thai))
            pink_hair_samples.append((idx, row[2] if len(row) > 2 else "", thai))

    print("\n--- RESULTS ---")
    print(f"1. Literal '\\n' remaining in dialogue content: {len(literal_nl_issues)} rows")
    if literal_nl_issues:
        for idx, fn, sample in literal_nl_issues[:5]:
            print(f"   - Row {idx} [{fn}]: {sample}")

    print(f"\n2. Untranslated 'Pink hair Woman' speaker tags: {len(untranslated_pink_hair)} rows")
    if untranslated_pink_hair:
        for idx, fn, sample in untranslated_pink_hair[:5]:
            print(f"   - Row {idx} [{fn}]: {sample}")

    print(f"\n3. 'Pink hair Woman' using masculine particles (ผม/ครับ): {len(pink_hair_masculine_lines)} rows")
    if pink_hair_masculine_lines:
        for idx, fn, sample in pink_hair_masculine_lines[:5]:
            print(f"   - Row {idx} [{fn}]: {sample}")

    print(f"\n[+] Total dialogue lines found for 'หญิงสาวผมชมพู': {len(pink_hair_samples)} rows")
    if pink_hair_samples:
        print("    Sample verified lines:")
        for idx, fn, sample in pink_hair_samples[:3]:
            # แสดงเฉพาะบรรทัดแรกของ sample เพื่อความกระชับ
            clean_display = sample.replace("\n", " [NL] ")
            print(f"    - Row {idx} [{fn}]: {clean_display[:100]}...")

    print("=" * 70)
    if not literal_nl_issues and not untranslated_pink_hair and not pink_hair_masculine_lines:
        print("🎉 ALL 3 ISSUES ARE FULLY RESOLVED! PASS 100%!")
    else:
        print("⚠️ Some issues still require attention.")
    print("=" * 70)

if __name__ == "__main__":
    main()
