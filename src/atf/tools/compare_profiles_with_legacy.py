"""
Compare TLAS V4 Profiles against Thai Legacy Pronoun Stats
Architecture: SAD-010 | Design: SDD-010, SDD-011 | Rules: AGENTS.md

หน้าที่:
1. อ่านความสัมพันธ์รายบุคคลจาก data/tlas/global_pronoun_matrix.json หรือ data/tlas/profiles/*.json
2. เปรียบเทียบกับสถิติการใช้จริงใน data/tlas/legacy_pronoun_stats.json
3. ออกรายงานเปรียบเทียบ Parity Report (Matching, Deviations, Rationale)
"""

import os
import sys
import json
from typing import Dict, List, Any

TLAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/tlas"))
PROFILES_DIR = os.path.join(TLAS_DIR, "profiles")
LEGACY_STATS_PATH = os.path.join(TLAS_DIR, "legacy_pronoun_stats.json")
PARITY_REPORT_PATH = os.path.join(TLAS_DIR, "legacy_profile_parity_report.json")

def compare_profiles_with_legacy():
    if not os.path.exists(LEGACY_STATS_PATH):
        print(f"[!] Legacy stats not found at {LEGACY_STATS_PATH}")
        return

    with open(LEGACY_STATS_PATH, "r", encoding="utf-8") as f:
        legacy_data = json.load(f)

    # Load all profiles
    matches = []
    discrepancies = []
    total_compared = 0

    for pair_key, leg_stat in legacy_data.items():
        speaker = leg_stat.get("speaker")
        listener = leg_stat.get("listener")
        if not speaker or not listener or listener == "GENERAL":
            continue

        spk_file = os.path.join(PROFILES_DIR, f"{speaker}.json")
        if not os.path.exists(spk_file):
            continue

        try:
            with open(spk_file, "r", encoding="utf-8") as f:
                spk_profile = json.load(f)
        except Exception:
            continue

        # Look for relationship with listener
        found_rel = None
        for rel in spk_profile.get("relationships", []):
            if rel.get("target_name") == listener:
                found_rel = rel
                break

        if not found_rel:
            continue

        total_compared += 1
        sp_style = found_rel.get("speech_style", {})
        v4_self = sp_style.get("self_pronoun", "")
        v4_target = sp_style.get("target_pronoun", "")
        v4_ending = sp_style.get("ending_particle", "")

        leg_top_self = leg_stat.get("top_self", "")
        leg_top_target = leg_stat.get("top_target", "")
        leg_top_ending = leg_stat.get("top_ending", "")

        is_self_match = (v4_self == leg_top_self)
        is_target_match = (v4_target == leg_top_target)
        is_ending_match = (v4_ending == leg_top_ending) or (not v4_ending and not leg_top_ending)

        comparison_entry = {
            "pair": f"{speaker} -> {listener}",
            "lines_in_legacy": leg_stat.get("total_lines", 0),
            "v4_style": {
                "self": v4_self,
                "target": v4_target,
                "ending": v4_ending,
                "rule": sp_style.get("derivation_rule", "")
            },
            "legacy_top": {
                "self": leg_top_self,
                "target": leg_top_target,
                "ending": leg_top_ending
            },
            "match_status": {
                "self_match": is_self_match,
                "target_match": is_target_match,
                "ending_match": is_ending_match
            }
        }

        if is_self_match and is_target_match and is_ending_match:
            matches.append(comparison_entry)
        else:
            discrepancies.append(comparison_entry)

    report = {
        "total_compared_pairs": total_compared,
        "perfect_matches_count": len(matches),
        "discrepancies_count": len(discrepancies),
        "perfect_matches": matches,
        "discrepancies": discrepancies
    }

    with open(PARITY_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("="*65)
    print("=== ATF TLAS V4 vs LEGACY PRONOUN PARITY REPORT ===")
    print("="*65)
    print(f"Total Relationship Pairs Compared: {total_compared}")
    print(f"Perfect Matches: {len(matches)} pairs ({len(matches)/total_compared*100:.1f}%)" if total_compared > 0 else "0")
    print(f"Discrepancies / Nuance Differences: {len(discrepancies)} pairs")
    print(f"Full report saved to: {PARITY_REPORT_PATH}")
    print("="*65)

    if discrepancies:
        print("\n[Sample Nuances / Differences (V4 vs Legacy)]:")
        for d in discrepancies[:10]:
            print(f" * {d['pair']} (Lines: {d['lines_in_legacy']}):")
            print(f"    - V4 Profile: self='{d['v4_style']['self']}', target='{d['v4_style']['target']}', ending='{d['v4_style']['ending']}' (Rule: {d['v4_style']['rule']})")
            print(f"    - Legacy Top: self='{d['legacy_top']['self']}', target='{d['legacy_top']['target']}', ending='{d['legacy_top']['ending']}'")

if __name__ == "__main__":
    compare_profiles_with_legacy()
