#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Enriched Localization CSV Generator
=================================================
[RULE_UNIVERSAL_PARADIGM & RULE_ZERO_HARDCODE COMPLIANT]
Transforms raw/translated game CSVs into production-grade rich localization tables:
Columns: [Original, Initial, Displayable, Role, Speaker, Listener, Third_Person, Filename, Row, Note]

Features:
1. Automated Displayable & Role Classification via GameDisplayableEngine and www/data/*.json.
2. Non-Displayable Code Preservation: If Displayable == 'No', Initial is restored to Original (Zero game crash).
3. Conversational Triad (Speaker, Listener, Third_Person):
   - Speaker: Resolves true speaker via engine tags, scene packets, and first-person monologue classification.
   - Listener: Identifies true target of dialogue via universal multi-party addressee flow.
   - Third_Person: Detects third-party entities referenced in dialogue dynamically from project registry.
4. Line-Break Normalization: Corrects arbitrary in-cell line splits where Thai length <= 45 characters.
5. Clean Note Isolation: Removes metadata from Note column, restoring clean notes.
6. Zero Generic Placeholders: Strictly no literal 'Protagonist' or false 'Narrator' on player monologues.
"""

import os
import sys
import re
import csv
import json
import argparse
from typing import Dict, List, Tuple, Optional, Any

# Ensure project root is in sys.path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from src.atf.core.game_displayable_engine import GameDisplayableEngine
from src.atf.tools.resolve_conversational_triad import build_dynamic_entity_map, resolve_triads


def parse_speaker_tag(text: str) -> Tuple[Optional[str], str]:
    """
    Extracts speaker name from tag (e.g. 【凛】\n... -> ('凛', '...'))
    """
    if not text:
        return None, ""
    m = re.match(r"^(【([^】]+)】|<italic><Name:([^>]+)></italic>)\s*\n?", text)
    if m:
        spk = m.group(2) or m.group(3)
        pure = text[m.end():]
        return spk.strip(), pure
    return None, text


def normalize_line_breaks(orig_text: str, th_text: str, max_chars_per_line: int = 45) -> str:
    """
    Normalizes arbitrary in-cell line breaks.
    If original text is 1 single line (excluding speaker tag) and Thai text was split
    into multiple lines with total length <= max_chars_per_line, join them back into 1 line.
    """
    if not th_text:
        return th_text

    orig_spk, orig_pure = parse_speaker_tag(orig_text)
    th_spk, th_pure = parse_speaker_tag(th_text)

    orig_pure_lines = [l.strip() for l in orig_pure.split("\n") if l.strip()]
    th_pure_lines = [l.strip() for l in th_pure.split("\n") if l.strip()]

    if len(orig_pure_lines) <= 1 and len(th_pure_lines) > 1:
        total_th_len = sum(len(l) for l in th_pure_lines)
        if total_th_len <= max_chars_per_line:
            merged = "".join(th_pure_lines)
            if th_spk:
                return f"【{th_spk}】\n{merged}"
            return merged

    return th_text


def build_dynamic_canonical_map(workspace_root: str = WORKSPACE_ROOT) -> Dict[str, str]:
    """
    Dynamically maps Thai translation strings back to Canonical entity names
    from data/tlas/tlas_glossary.json. Zero hardcoding of character names.
    """
    glossary_path = os.path.join(workspace_root, "data", "tlas", "tlas_glossary.json")
    mapping = {}
    if os.path.exists(glossary_path):
        try:
            with open(glossary_path, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            for cname, info in gdata.get("Characters", {}).items():
                th = info.get("th")
                if th and th not in ("？？？", "None"):
                    mapping[th] = cname
        except Exception as e:
            print(f"[!] Warning loading glossary for canonical map: {e}")
    return mapping


def detect_third_person_dynamic(
    speaker: str,
    listener: str,
    text: str,
    entity_map: Dict[str, List[str]]
) -> str:
    """
    Detects 3rd person entities referenced in dialogue dynamically.
    An entity is a 3rd person reference if it is mentioned in the dialogue
    and is neither the current Speaker nor the Listener.
    """
    if not text or not speaker or not listener:
        return "None"

    candidates = []
    for entity, markers in entity_map.items():
        if entity != speaker and entity != listener and entity not in listener:
            if any(m in text for m in markers):
                candidates.append(entity)

    return ", ".join(candidates) if candidates else "None"


DB_FILES = {
    "Actors", "Animations", "Classes", "CommonEvents", "Items",
    "Skills", "Weapons", "Armors", "Enemies", "Troops", "States"
}


def classify_untagged_utterance(
    orig_text: str,
    role: str,
    filename: str,
    active_protagonist: str = "Player",
    active_speaker: str = "Narrator"
) -> Tuple[str, str, str]:
    """
    Universally classifies untagged lines into:
    1. Map Display Names / Plugin Dialogues (retains engine role, Speaker: System, Listener: Player)
    2. Developer Message / Post-game Credits: (e.g. プレイして頂き、ありがとうございました)
    3. System labels, Room markers, Prompts, UI Strings: (-101-, 見ますか？, セーブ...)
    4. Choice Branches: (はい, いいえ, 怒りを覚えた...) -> Speaker: active_protagonist, Listener: Self
    5. Omniscient Time/Setting Transitions & Third-Person Narration: (2日目の早朝, バカな旦那だ...)
    6. In-World Interpersonal Directives: (～てください)
    7. Controlled Character's First-Person Internal Monologues & Observations: (default for untagged story dialogue)
    Returns: (Speaker, Listener, Role)
    """
    clean = orig_text.strip()

    # 1. Map Display Names and Plugin UI Dialogues from Game Engine
    if role in ("Map Display Name", "Plugin Dialogue", "System Term", "System Message", "Game Title"):
        return "System", "Player", role
    
    # 1. Universal Meta Developer / Credit Acknowledgments
    # Matches authorial closing / appreciation patterns across Japanese games:
    # (e.g. プレイしていただきありがとうございます, スタッフ一同感謝, 次回作もよろしく, 『...』は以上です)
    if re.search(r'(?:(?:プレイ|遊んで|クリア).*(?:ありがとう|感謝)|(?:次回作|スタッフ|制作|開発).*(?:よろしく|感謝|一同)|『.+』は以上です)', clean):
        return "Developer", "Player", "Developer Message"

    # 2. Choice Branches & Binary selection options (chosen by the active controlled character)
    if role in ("Choice Branch", "Choices Option") or clean in ("はい", "いいえ", "する", "しない"):
        return active_protagonist, "Self", "Choice Branch"

    # 3. System Decision Prompts: Standard Japanese polite question endings (～ますか？ / ～ますか?)
    if clean.endswith(("ますか？", "ますか・・・？", "ますか?", "ますか…?")):
        return "System", "Player", "System Message"

    # 4. System labels / Room numbers / Delimited markers: e.g. -101-, -201-, ～男湯～, ～女湯～
    if re.match(r'^[\u301c\uff5e~-].+[\u301c\uff5e~-]$', clean) or re.match(r'^-\d+-$', clean) or re.match(r'^\d+$', clean):
        return "System", "Player", "System Term"

    # 5. System gameplay notifications: standard RPG keywords (Save, Obtained, Points, EXP, Gold)
    sys_markers = ["セーブ", "手に入れた", "獲得", "所持", "ポイント", "EXP", "ゴールド"]
    if any(m in clean for m in sys_markers):
        return "System", "Player", "System Message"

    # 6. Omniscient Time/Setting Transitions & Scene Timestamps:
    # Standard temporal syntax across Japanese games (e.g. 1日目, 2日目の早朝, 翌朝, 数日後, その日の夜...)
    is_timestamp = bool(re.match(r'^(?:(?:\d+|翌|その|あの|数|数カ?)(?:日|朝|夜|年|ヶ月|か月|時)(?:目|後|前|の(?:早朝|夜|朝|昼|夕方))?|エピローグ|プロローグ|終章|序章)[・…！!。.\s]*$', clean))
    if is_timestamp:
        return "Narrator", "Player", "Narration"

    # 7. In-World Interpersonal Request / Directive Utterances: e.g. ～てください, ～てちょうだい
    interpersonal_requests = ["てください", "てちょうだい", "ておくれ", "てくれ", "てほしい"]
    if any(req in clean for req in interpersonal_requests):
        return active_speaker if active_speaker not in ("Narrator", "System") else "", None, "Dialogue/Story"

    # 8. All Other Untagged Story Lines = Controlled Character's First-Person Internal Monologues & Observations!
    return active_protagonist, "Self", "Dialogue/Story"


def process_enrichment(
    input_csv_path: str,
    output_csv_path: str,
    game_data_dir: str,
    scene_packets_path: str
):
    print("=" * 80)
    print("ATF UNIVERSAL ENRICHED LOCALIZATION CSV GENERATOR")
    print(f"  Input CSV      : {input_csv_path}")
    print(f"  Output CSV     : {output_csv_path}")
    print(f"  Game Data Dir  : {game_data_dir}")
    print(f"  Scene Packets  : {scene_packets_path}")
    print("=" * 80)

    # 1. Initialize GameDisplayableEngine
    engine = GameDisplayableEngine(game_data_dir=game_data_dir)

    # 2. Load Scene Packets & Active Protagonist
    scene_packets = {}
    active_protagonist = "Player"
    if os.path.exists(scene_packets_path):
        try:
            with open(scene_packets_path, "r", encoding="utf-8") as sf:
                sp_data = json.load(sf)
                active_protagonist = sp_data.get("active_party_leader") or sp_data.get("registered_database_actors", {}).get("1") or "Player"
                for pkt in sp_data.get("packets", []):
                    fn = pkt.get("filename")
                    explicit_speakers = pkt.get("explicit_speakers", [])
                    for d in pkt.get("dialogues", []):
                        row_idx = d.get("csv_row")
                        if row_idx is not None:
                            scene_packets[row_idx] = {
                                "filename": fn,
                                "speakers": explicit_speakers,
                                "candidate_listeners": d.get("candidate_listeners", []),
                                "packet_id": pkt.get("packet_id")
                            }
            print(f"[OK] Loaded {len(scene_packets)} mapped rows from Scene Packets. (Active Protagonist: {active_protagonist})")
        except Exception as e:
            print(f"[WARN] Could not load scene packets: {e}")

    # 3. Build Dynamic Entity & Canonical Maps (Universal, Zero Hardcode)
    entity_map = build_dynamic_entity_map(WORKSPACE_ROOT)
    canonical_map = build_dynamic_canonical_map(WORKSPACE_ROOT)
    print(f"[OK] Discovered {len(entity_map)} dynamic entities and {len(canonical_map)} canonical reverse mappings.")

    # 4. Read Input CSV
    with open(input_csv_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))

    if not reader:
        print("[ERROR] Input CSV is empty.")
        return

    # Build Attested Dialogue Map from the entire corpus:
    # If a dialogue appears with an explicit speaker tag elsewhere in the game,
    # that explicit speaker attribution is learned dynamically from the game corpus.
    attested_dialogue_speakers = {}
    for r in reader[1:]:
        if r and len(r) > 0:
            spk_tag, pure_txt = parse_speaker_tag(r[0])
            if spk_tag and pure_txt:
                attested_dialogue_speakers[pure_txt.strip()] = spk_tag

    new_header = [
        "Original",
        "Initial",
        "Displayable",
        "Role",
        "Speaker",
        "Listener",
        "Third_Person",
        "Filename",
        "Row",
        "Note"
    ]

    enriched_rows = [new_header]

    active_speaker = "Narrator"
    active_listener = "Player"
    current_filename = ""

    stats = {
        "total_rows": len(reader) - 1,
        "displayable_yes": 0,
        "displayable_no": 0,
        "line_breaks_normalized": 0,
        "code_preserved": 0,
        "third_person_detected": 0
    }

    for idx in range(1, len(reader)):
        row = reader[idx]
        if not row:
            continue

        orig_text = row[0] if len(row) > 0 else ""
        initial_text = row[1] if len(row) > 1 else ""
        filename = row[2] if len(row) > 2 else ""
        row_id = row[3] if len(row) > 3 else ""
        raw_note = row[4] if len(row) > 4 else ""

        # Context boundary reset on filename change
        if filename != current_filename:
            current_filename = filename
            active_speaker = "Narrator"
            active_listener = "Player"

        # Evaluate Displayable & Role from GameDisplayableEngine
        disp_bool, role, _ = engine.evaluate_displayable(orig_text, filename)
        displayable = "Yes" if disp_bool else "No"

        if displayable == "Yes":
            stats["displayable_yes"] += 1
        else:
            stats["displayable_no"] += 1

        # Clean Note: remove previous "| Listener: ..." or similar stuffed metadata
        clean_note = re.sub(r"\s*\|\s*Listener:\s*[^|]+", "", raw_note).strip()
        if not clean_note:
            clean_note = "ไฟล์ใหม่"

        # Extract Listener if it was recorded in Note
        extracted_listener = None
        listener_match = re.search(r"Listener:\s*([^|\n\r]+)", raw_note)
        if listener_match:
            extracted_listener = listener_match.group(1).strip()

        # 1. Non-Displayable Code Preservation Rule (Zero Game Crash Invariant)
        if displayable == "No":
            translated_text = orig_text
            speaker = "None"
            listener = "None"
            third_person = "None"
            stats["code_preserved"] += 1

        # 2. Database Asset Files: Actors, Animations, Classes, Items, Skills, Weapons, Armors...
        elif filename in DB_FILES:
            translated_text = initial_text
            speaker = "None"
            listener = "Player"
            third_person = "None"

        else:
            translated_text = initial_text

            # Speaker identification
            tag_spk, pure_orig = parse_speaker_tag(orig_text)
            if tag_spk:
                speaker = tag_spk
                active_speaker = tag_spk
                u_lis = None
            elif pure_orig and pure_orig.strip() in attested_dialogue_speakers and role == "Dialogue/Story":
                # Attested Dialogue Attribution: Attributed dynamically from explicit tag elsewhere in game corpus
                speaker = attested_dialogue_speakers[pure_orig.strip()]
                active_speaker = speaker
                u_lis = None
            else:
                # Classify untagged utterance
                u_spk, u_lis, u_role = classify_untagged_utterance(
                    orig_text, role, filename,
                    active_protagonist=active_protagonist,
                    active_speaker=active_speaker
                )
                speaker = u_spk
                role = u_role
                if u_spk not in ("Narrator", "System", "Developer", "None", ""):
                    active_speaker = u_spk

            # Unified System, Developer, Narration, Choice, and Dialogue Listener Mapping
            if role in ("System Message", "System Term", "Map Display Name", "Plugin Dialogue"):
                speaker = "System"
                listener = "Player"
            elif role == "Developer Message":
                speaker = "Developer"
                listener = "Player"
            elif role == "Narration":
                speaker = "Narrator"
                listener = "Player"
            elif role in ("Choices Option", "Choice Branch"):
                speaker = active_protagonist
                listener = "Self"
            elif extracted_listener in canonical_map:
                listener = canonical_map[extracted_listener]
            elif extracted_listener:
                listener = extracted_listener
            else:
                if tag_spk is None and u_lis:
                    listener = u_lis
                elif role == "Dialogue/Story":
                    listener = active_listener if active_listener and active_listener != speaker else "Self"
                else:
                    listener = "None"

            # Auto-repair formatting invariants (Literal \n and Missing Tag \n)
            if chr(92) + 'n' in translated_text:
                translated_text = translated_text.replace(chr(92) + 'n', '\n')
            tag_m = re.match(r'^(【.*?】)(?!\n)', translated_text)
            if tag_m:
                translated_text = tag_m.group(1) + "\n" + translated_text[len(tag_m.group(1)):].lstrip()

            # Update active context
            if speaker not in ("None", "System", "Narrator"):
                active_speaker = speaker
            if listener not in ("None", "Player", "Self"):
                active_listener = listener

            # Third Person Detection (Universal Dynamic Registry)
            if role == "Dialogue/Story":
                third_person = detect_third_person_dynamic(
                    speaker, listener, f"{orig_text} {translated_text}", entity_map
                )
                if third_person != "None":
                    stats["third_person_detected"] += 1
            else:
                third_person = "None"

            # Normalize Arbitrary In-Cell Line Breaks
            norm_trans = normalize_line_breaks(orig_text, translated_text, max_chars_per_line=45)
            if norm_trans != translated_text:
                stats["line_breaks_normalized"] += 1
                translated_text = norm_trans

        enriched_rows.append([
            orig_text,
            translated_text,
            displayable,
            role,
            speaker,
            listener,
            third_person,
            filename,
            row_id,
            clean_note
        ])

    # 7. Write Enriched CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as out_f:
        writer = csv.writer(out_f)
        writer.writerows(enriched_rows)

    # 8. Post-Processing: Run Universal Multi-Party Conversational Triad Engine on Output
    try:
        resolve_triads(output_csv_path)
    except Exception as triad_err:
        print(f"[!] Warning during universal triad post-processing: {triad_err}")

    print("\n" + "=" * 80)
    print("[SUCCESS] UNIVERSAL ENRICHED LOCALIZATION CSV COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print(f"  [OK] Total Processed Rows    : {stats['total_rows']:,}")
    print(f"  [OK] Displayable (Yes)       : {stats['displayable_yes']:,} rows")
    print(f"  [OK] Non-Displayable (No)    : {stats['displayable_no']:,} rows (Code/Variables Untouched)")
    print(f"  [OK] Line Breaks Normalized  : {stats['line_breaks_normalized']:,} rows merged back to 1 line (<=45 chars)")
    print(f"  [OK] 3rd Persons Identified  : {stats['third_person_detected']:,} rows")
    print(f"  [OK] Output Saved to         : {output_csv_path}")
    print("=" * 80)


def load_manifest(workspace_root: str = WORKSPACE_ROOT) -> Dict[str, Any]:
    manifest_path = os.path.join(workspace_root, "data", "project_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    manifest = load_manifest()
    default_input = manifest.get("output_translated_csv") or os.path.join("output", "translated.csv")
    default_output = manifest.get("output_enriched_csv") or os.path.join("output", "enriched_translated.csv")
    default_game_data = manifest.get("game_data_directory") or os.path.join("www", "data")
    default_scene_packets = os.path.join(WORKSPACE_ROOT, "data", "tlas", "scene_packets.json")

    parser = argparse.ArgumentParser(description="ATF Universal Enriched Localization CSV Generator")
    parser.add_argument("--input", type=str, default=default_input, help="Path to input translated CSV")
    parser.add_argument("--output", type=str, default=default_output, help="Path to output enriched CSV")
    parser.add_argument("--game-data", type=str, default=default_game_data, help="Path to RPG Maker www/data folder")
    parser.add_argument("--scene-packets", type=str, default=default_scene_packets, help="Path to scene packets JSON")
    args = parser.parse_args()

    process_enrichment(
        input_csv_path=args.input,
        output_csv_path=args.output,
        game_data_dir=args.game_data,
        scene_packets_path=args.scene_packets
    )


if __name__ == "__main__":
    main()
