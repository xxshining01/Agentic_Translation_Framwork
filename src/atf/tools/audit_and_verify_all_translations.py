#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Master Translation Quality & Integrity Auditor (Phase 6 Compliant)
======================================================================
Comprehensive 6-Dimensional Verification & Auto-Repair Engine for Game Translations.

Audits:
  1. Leaked XML / Unmask Failures (<color id=...>, <pause_.../>, <icon id=.../>, etc.)
  2. Duplicate Row Overwrite (trans[i] == trans[i-1] while orig[i] != orig[i-1], all lengths)
  3. Double Speaker Tags (\\n<Speaker:><Speaker:>)
  4. Code Clumping / Accumulation (\\.\\.\\.\\. piled at tail/head not present in orig)
  5. Contextual Pronouns & Particles (Female using ครับ/ผม, Male using ค่ะ/คะ, Male using จ้ะ contextually analyzed)
  6. Completion & Empty Displayable Rows (Displayable == 'Yes' must not have empty Initial)
  7. Form Feed ASCII 12 (\\x0c) Hazard

Supports:
  - Auditing current patch CSV or any legacy translation CSV
  - Safe Auto-Repair for deterministic defects (Checks 1, 3, 7)
  - Exporting a streamlined Manual Review Queue (CSV/JSON) for nuanced issues (Checks 2, 4, 5)
"""

import os
import sys
import re
import csv
import json
import glob
import argparse
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter

# Ensure UTF-8 output on Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass


class TranslationAuditor:
    def __init__(self, profiles_dir: Optional[str] = None, manifest_path: Optional[str] = None):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.manifest: Dict[str, Any] = {}
        
        # Load Manifest
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
        elif os.path.exists("data/project_manifest.json"):
            with open("data/project_manifest.json", "r", encoding="utf-8") as f:
                self.manifest = json.load(f)

        # Determine Profiles Directory
        p_dir = (
            profiles_dir
            or self.manifest.get("output_profiles_dir")
            or self.manifest.get("legacy_profiles_dir")
            or "data/tlas/profiles"
        )
        self.load_profiles(p_dir)

    def load_profiles(self, p_dir: str):
        if not os.path.exists(p_dir):
            print(f"⚠️ Profiles directory not found: {p_dir}")
            return

        for pf in glob.glob(os.path.join(p_dir, "*.json")):
            cname = os.path.splitext(os.path.basename(pf))[0].strip().lower()
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profiles[cname] = {
                        "name": data.get("name", cname),
                        "gender": (data.get("identity", {}).get("gender") or "UNKNOWN").upper(),
                        "age": (data.get("identity", {}).get("age") or "ADULT").upper(),
                        "ending": data.get("base_speech_style", {}).get("ending_particle", ""),
                        "self_pronoun": data.get("base_speech_style", {}).get("self_pronoun", ""),
                        "target_pronoun": data.get("base_speech_style", {}).get("target_pronoun", "")
                    }
            except Exception:
                pass

        print(f"✅ Loaded {len(self.profiles)} character profiles from {p_dir}")

    @staticmethod
    def extract_speaker(orig_text: str, speaker_col: str) -> str:
        """Extract clean speaker name from text prefix \\n<Speaker:> or column."""
        m = re.match(r"^(\s*\\n)?<([^>]+)>", orig_text)
        if m:
            clean = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", m.group(2))
            clean = clean.replace(":", "").strip()
            if clean:
                return clean
        if speaker_col and speaker_col.strip():
            return speaker_col.strip()
        return "Narrator"

    def audit_csv(self, csv_path: str, auto_repair: bool = False, output_repaired_csv: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Target CSV file not found: {csv_path}")

        print(f"\n{'=' * 80}")
        print(f"🔍 AUDITING TRANSLATION QUALITY: {csv_path}")
        print(f"{'=' * 80}")

        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            print("❌ CSV file is empty!")
            return {}

        header = rows[0]
        # Identify columns
        orig_idx = 0
        init_idx = 1
        speaker_idx = 6 if len(header) > 6 else -1
        disp_idx = 7 if len(header) > 7 else -1

        total_rows = len(rows) - 1
        displayable_yes_count = 0
        translated_count = 0

        # Violation Buckets
        violations = {
            "leaked_xml_tags": [],          # Check 1
            "duplicate_substitutions": [],  # Check 2
            "double_speaker_tags": [],      # Check 3
            "code_clumping": [],            # Check 4
            "gender_mismatches": [],        # Check 5
            "untranslated_empty": [],       # Check 6
            "form_feed_hazard": [],         # Check 7
        }

        repaired_rows_count = 0
        repaired_data = [list(rows[0])] if auto_repair else None

        prev_orig = None
        prev_trans = None
        prev_row_idx = None

        for r_num in range(1, len(rows)):
            row = list(rows[r_num])
            orig = row[orig_idx] if orig_idx < len(row) else ""
            trans = row[init_idx] if init_idx < len(row) else ""
            speaker_col = row[speaker_idx] if (speaker_idx >= 0 and speaker_idx < len(row)) else ""
            disp = row[disp_idx].strip() if (disp_idx >= 0 and disp_idx < len(row)) else "Yes"
            speaker = self.extract_speaker(orig, speaker_col)

            is_displayable = (disp == "Yes")
            if is_displayable:
                displayable_yes_count += 1

            trans_clean = trans.strip()
            if trans_clean:
                translated_count += 1

            row_had_repair = False
            repaired_trans = trans

            # -----------------------------------------------------------------
            # CHECK 6: Untranslated / Empty Displayable Row
            # -----------------------------------------------------------------
            if is_displayable and not trans_clean and orig.strip():
                violations["untranslated_empty"].append({
                    "row": r_num,
                    "speaker": speaker,
                    "orig": orig[:100]
                })

            # Only audit text if there is translated text
            if trans_clean:
                # -------------------------------------------------------------
                # CHECK 7: Form Feed ASCII 12 Hazard (\x0c)
                # -------------------------------------------------------------
                if "\x0c" in trans:
                    violations["form_feed_hazard"].append({
                        "row": r_num,
                        "speaker": speaker,
                        "sample": trans[:80]
                    })
                    if auto_repair:
                        repaired_trans = repaired_trans.replace("\x0ci", "\\fi").replace("\x0cb", "\\fb").replace("\x0c", "\\f")
                        row_had_repair = True

                # -------------------------------------------------------------
                # CHECK 1: Leaked XML / Unmask Failures (<color id=...>, etc.)
                # -------------------------------------------------------------
                leaked_xml_patterns = [
                    r"<color\s+id=[\"']?(\d+)[\"']?>",
                    r"</color>",
                    r"<pause_(?:quarter|half|second)/>",
                    r"<wait_input/>",
                    r"<icon\s+id=[\"']?(\d+)[\"']?>",
                    r"<(?:bold|italic)>",
                    r"</(?:bold|italic)>",
                    r"<stop_show_fast/>"
                ]
                has_leaked_xml = any(re.search(pat, trans, re.IGNORECASE) for pat in leaked_xml_patterns)
                if has_leaked_xml:
                    found_tags = re.findall(r"</?[a-zA-Z_]+(?:\s+id=[\"']?\d+[\"']?)?/?>", trans)
                    violations["leaked_xml_tags"].append({
                        "row": r_num,
                        "speaker": speaker,
                        "tags": list(set(found_tags)),
                        "trans_snippet": trans[:120]
                    })
                    if auto_repair:
                        repaired_trans = re.sub(r"<color\s+id=[\"']?(\d+)[\"']?>", r"\\C[\1]", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"</color>", r"\\C[0]", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<icon\s+id=[\"']?(\d+)[\"']?>", r"\\I[\1]", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<pause_quarter/>", r"\\.", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<pause_half/>", r"\\|", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<pause_second/>", r"\\|\\|", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<wait_input/>", r"\\!", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<stop_show_fast/>", r"\\>", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<bold>|</bold>", r"\\fb", repaired_trans, flags=re.IGNORECASE)
                        repaired_trans = re.sub(r"<italic>|</italic>", r"\\fi", repaired_trans, flags=re.IGNORECASE)
                        row_had_repair = True

                # -------------------------------------------------------------
                # CHECK 3: Double Speaker Tags (\n<Speaker:><Speaker:>)
                # -------------------------------------------------------------
                if re.search(r"<[^>]+:>\s*<[^>]+:>", trans):
                    violations["double_speaker_tags"].append({
                        "row": r_num,
                        "speaker": speaker,
                        "trans_snippet": trans[:100]
                    })
                    if auto_repair:
                        # Collapse double tags into single tag
                        repaired_trans = re.sub(r"(<[^>]+:>)\s*<[^>]+:>", r"\1", repaired_trans)
                        row_had_repair = True

                # -------------------------------------------------------------
                # CHECK 2: Duplicate Translation Overwrite
                # trans[i] == trans[i-1] while orig[i] != orig[i-1] (All lengths!)
                # -------------------------------------------------------------
                if prev_trans is not None and prev_orig is not None:
                    # Strip name tags for fair comparison
                    pure_trans = re.sub(r"^(\s*\\n)?<[^>]+>", "", trans).strip()
                    pure_prev_trans = re.sub(r"^(\s*\\n)?<[^>]+>", "", prev_trans).strip()
                    pure_orig = re.sub(r"^(\s*\\n)?<[^>]+>", "", orig).strip()
                    pure_prev_orig = re.sub(r"^(\s*\\n)?<[^>]+>", "", prev_orig).strip()

                    if pure_trans and pure_trans == pure_prev_trans and pure_orig != pure_prev_orig:
                        violations["duplicate_substitutions"].append({
                            "row": r_num,
                            "prev_row": prev_row_idx,
                            "speaker": speaker,
                            "orig": pure_orig,
                            "prev_orig": pure_prev_orig,
                            "duplicate_trans": pure_trans
                        })

                # -------------------------------------------------------------
                # CHECK 4: Code Clumping / Accumulation (\.\.\.\. piled up)
                # -------------------------------------------------------------
                clump_pat = r"(\\\.){3,}|(\\\|){3,}"
                trans_has_clump = bool(re.search(clump_pat, trans))
                orig_has_clump = bool(re.search(clump_pat, orig))
                if trans_has_clump and not orig_has_clump:
                    violations["code_clumping"].append({
                        "row": r_num,
                        "speaker": speaker,
                        "orig": orig[:80],
                        "trans_snippet": trans[:100]
                    })

                # -------------------------------------------------------------
                # CHECK 5: Contextual Pronouns & Particles Audit
                # -------------------------------------------------------------
                spk_clean = speaker.strip().lower()
                profile = self.profiles.get(spk_clean)
                if profile:
                    gender = profile.get("gender")
                    # Remove name tag prefix so we only check dialogue body
                    body_text = re.sub(r"^(\s*\\n)?<[^>]+>", "", trans)
                    # Strip out text inside quotes (often quoting other characters)
                    body_no_quotes = re.sub(r'[\"“\'][^\"”\']+[\"”\']', '', body_text)

                    if gender == "FEMALE":
                        # Female using male pronouns / endings
                        # 1. Check "ครับ" / "กระผม"
                        found_m = []
                        if "ครับ" in body_no_quotes:
                            found_m.append("ครับ")
                        if "กระผม" in body_no_quotes:
                            found_m.append("กระผม")

                        # 2. Check "ฮะ" (must not be "แฮะ", laughter like "ฮะฮะ", or interjections like "อา ฮะ")
                        clean_for_ha = re.sub(r'แฮะ', '', body_no_quotes)
                        clean_for_ha = re.sub(r'ฮะ[ฮะๆ]+|ฮ-ฮะ|เอเฮะ+|อา\s*ฮะ|อืม\s*ฮะ', '', clean_for_ha)
                        if re.search(r'(?<![แก])ฮะ(?![ฮะๆ])', clean_for_ha):
                            # Ensure it's not panting or laughter like "ฮะ...ฮะ..."
                            if not re.search(r'ฮะ[\.\s\,]*ฮะ', clean_for_ha):
                                found_m.append("ฮะ")

                        # 3. Check "ผม" as pronoun (not hair/haircut/hair color)
                        hair_words = [
                            "เส้นผม", "ทรงผม", "ตัดผม", "สีผม", "ผมแดง", "ผมบลอนด์", 
                            "ผมทอง", "ผมสั้น", "ผมยาว", "ผมยุ่ง", "ผมเปีย", "ผมหงอก", 
                            "ผมหยิก", "ผมดำ", "ผมสี"
                        ]
                        if "ผม" in body_no_quotes and not any(w in body_no_quotes for w in hair_words):
                            found_m.append("ผม")

                        if found_m:
                            violations["gender_mismatches"].append({
                                "row": r_num,
                                "speaker": speaker,
                                "gender": "FEMALE",
                                "severity": "WARNING",
                                "classification": "FEMALE_USING_MALE_SPEECH",
                                "found_words": found_m,
                                "orig": orig[:80],
                                "trans": trans[:120]
                            })

                    elif gender == "MALE":
                        # Male using formal female particles
                        female_hard = ["ค่ะ", "นะคะ"]
                        found_f = [f for f in female_hard if f in body_no_quotes]
                        if found_f:
                            violations["gender_mismatches"].append({
                                "row": r_num,
                                "speaker": speaker,
                                "gender": "MALE",
                                "severity": "WARNING",
                                "classification": "MALE_USING_FEMALE_SPEECH",
                                "found_words": found_f,
                                "orig": orig[:80],
                                "trans": trans[:120]
                            })

                        # Male using playful "จ้ะ/จ๊ะ/นะจ๊ะ" -> Contextual check!
                        if any(w in body_no_quotes for w in ["จ้ะ", "จ๊ะ", "นะจ๊ะ"]):
                            # Context check: speaking to child, girl, or affectionate scene
                            orig_low = orig.lower()
                            is_playful_context = any(kw in orig_low for kw in [
                                "little", "girl", "child", "kid", "daughter", "sweetie", "honey", "darling", "baby", "sister"
                            ])
                            violations["gender_mismatches"].append({
                                "row": r_num,
                                "speaker": speaker,
                                "gender": "MALE",
                                "severity": "INFO" if is_playful_context else "WARNING",
                                "classification": "MALE_PLAYFUL_OR_AFFECTIONATE" if is_playful_context else "MALE_UNVERIFIED_JA_PARTICLE",
                                "found_words": ["จ้ะ/จ๊ะ"],
                                "orig": orig[:80],
                                "trans": trans[:120]
                            })

            # Update tracked state
            prev_orig = orig
            prev_trans = trans
            prev_row_idx = r_num

            if auto_repair:
                if row_had_repair:
                    repaired_rows_count += 1
                row[init_idx] = repaired_trans
                repaired_data.append(row)

        # -----------------------------------------------------------------
        # OUTPUT AUDIT DASHBOARD
        # -----------------------------------------------------------------
        completion_pct = (translated_count / displayable_yes_count * 100) if displayable_yes_count > 0 else 100.0

        print(f"\n📊 SUMMARY METRICS FOR {os.path.basename(csv_path)}:")
        print(f"  • Total CSV Rows:                 {total_rows:,}")
        print(f"  • Displayable (Yes) Rows:         {displayable_yes_count:,}")
        print(f"  • Translated Rows in Initial:     {translated_count:,} ({completion_pct:.2f}%)")

        # Separate fatal gender violations from contextual nuances
        f_fatal = [x for x in violations["gender_mismatches"] if x.get("classification") == "FEMALE_USING_MALE_SPEECH"]
        m_fatal = [x for x in violations["gender_mismatches"] if x.get("classification") == "MALE_USING_FEMALE_SPEECH"]
        ja_nuance = [x for x in violations["gender_mismatches"] if "JA_PARTICLE" in x.get("classification", "") or "PLAYFUL" in x.get("classification", "")]

        print(f"\n🚨 DEFECT & VULNERABILITY BREAKDOWN:")
        print(f"  [1] Leaked XML Tags (<color>, <pause>):         {len(violations['leaked_xml_tags']):,} rows  (Fatal XML leak)")
        print(f"  [2] Duplicate Row Substitutions (All size):    {len(violations['duplicate_substitutions']):,} rows  (Suspicious duplicate)")
        print(f"  [3] Double Speaker Tags (\\n<Name:><Name:>):     {len(violations['double_speaker_tags']):,} rows  (Duplicate tag)")
        print(f"  [4] Code Clumping (\\.\\.\\.\\. piled up):         {len(violations['code_clumping']):,} rows  (Escapes clustered)")
        print(f"  [5a] FATAL Female using Male Speech (ครับ/ผม):  {len(f_fatal):,} rows  (CRITICAL GENDER DEFECT!)")
        print(f"  [5b] FATAL Male using Female Speech (ค่ะ/คะ):    {len(m_fatal):,} rows  (CRITICAL GENDER DEFECT!)")
        print(f"  [5c] Male Contextual Nuance (จ้ะ/จ๊ะ):          {len(ja_nuance):,} rows  (Review Queue)")
        print(f"  [6] Untranslated Displayable Empty Rows:       {len(violations['untranslated_empty']):,} rows  (Missing initial)")
        print(f"  [7] Form Feed ASCII 12 Hazard (\\x0c):           {len(violations['form_feed_hazard']):,} rows  (Game crash hazard)")

        # -----------------------------------------------------------------
        # AUTO-REPAIR EXECUTION
        # -----------------------------------------------------------------
        if auto_repair and repaired_data:
            out_path = output_repaired_csv or (os.path.splitext(csv_path)[0] + "_repaired.csv")
            print(f"\n🔧 Auto-Repair Mode Active: Repaired {repaired_rows_count:,} rows with deterministic fixes.")
            temp_out = out_path + ".tmp"
            with open(temp_out, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerows(repaired_data)
            os.replace(temp_out, out_path)
            print(f"💾 Repaired CSV saved to: {out_path}")

        return {
            "csv_path": csv_path,
            "total_rows": total_rows,
            "displayable_yes": displayable_yes_count,
            "translated_rows": translated_count,
            "completion_pct": completion_pct,
            "violations": violations
        }

    def export_manual_review_queue(self, violations: Dict[str, Any], output_queue_path: str):
        """Exports Check 2 and Check 5 into an easily readable CSV for rapid manual verification."""
        review_rows = []
        review_rows.append([
            "Row_Number", "Category", "Severity", "Speaker", "Original_Text", "Translated_Text", "Audit_Note"
        ])

        # Add Check 2 (Duplicates)
        for item in violations.get("duplicate_substitutions", []):
            review_rows.append([
                str(item["row"]),
                "Duplicate Row Overwrite",
                "WARNING",
                item["speaker"],
                f"Current: {item['orig']} | Prev: {item['prev_orig']}",
                item["duplicate_trans"],
                f"Identical translation copied from previous row #{item['prev_row']} despite different original!"
            ])

        # Add Check 5 (Gender & Pronoun Nuances)
        for item in violations.get("gender_mismatches", []):
            review_rows.append([
                str(item["row"]),
                "Pronoun/Particle Nuance",
                item["severity"],
                item["speaker"],
                item["orig"],
                item["trans"],
                f"{item['classification']}: Found {item['found_words']} for {item['gender']} speaker"
            ])

        # Add Check 4 (Code Clumping)
        for item in violations.get("code_clumping", []):
            review_rows.append([
                str(item["row"]),
                "Code Clumping at Tail/Head",
                "WARNING",
                item["speaker"],
                item["orig"],
                item["trans_snippet"],
                "Multiple control codes (\\., \\|) clustered together not present in original"
            ])

        with open(output_queue_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(review_rows)

        print(f"📋 Exported Manual Review Queue ({len(review_rows) - 1:,} items) to: {output_queue_path}")


def main():
    parser = argparse.ArgumentParser(description="ATF Master Translation Quality & Integrity Auditor")
    parser.add_argument("--csv", type=str, default=None, help="Path to CSV file to audit")
    parser.add_argument("--profiles", type=str, default=None, help="Path to character profiles directory")
    parser.add_argument("--manifest", type=str, default="data/project_manifest.json", help="Path to project_manifest.json")
    parser.add_argument("--auto-repair", action="store_true", help="Automatically repair deterministic defects (XML leaks, double tags, \\x0c)")
    parser.add_argument("--output-repaired", type=str, default=None, help="Custom output path for repaired CSV")
    parser.add_argument("--export-review", type=str, default="manual_review_queue.csv", help="Path to export manual review queue CSV")
    parser.add_argument("--json-report", type=str, default="audit_report.json", help="Path to save detailed JSON audit report")
    args = parser.parse_args()

    auditor = TranslationAuditor(profiles_dir=args.profiles, manifest_path=args.manifest)

    # Determine CSV target
    target_csv = args.csv
    if not target_csv:
        target_csv = (
            auditor.manifest.get("output_processed_csv")
            or "Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated.csv"
        )

    results = auditor.audit_csv(
        csv_path=target_csv,
        auto_repair=args.auto_repair,
        output_repaired_csv=args.output_repaired
    )

    if results:
        # Save JSON Report
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"📄 Full JSON audit report saved to: {args.json_report}")

        # Export Manual Review Queue
        auditor.export_manual_review_queue(results["violations"], args.export_review)


if __name__ == "__main__":
    main()
