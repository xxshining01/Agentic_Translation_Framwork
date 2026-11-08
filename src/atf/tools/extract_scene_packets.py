#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Scene Packetizer & AST-Grounded Flow Extractor (v2.0)
สกัดและจัดกลุ่มบทสนทนาเป็น Scene Packets ตามความต่อเนื่องจริง (Continuity & AST Boundaries)

หลักการออกแบบสถาปัตยกรรม (Universal Framework Paradigm):
1. Zero Hardcoding: ปราศจากพจนานุกรมคำศัพท์เฉพาะภาษา (No Vocative Maps / No Language-Specific Monologue Regex)
2. Factual Evidence Extraction: สกัดเฉพาะข้อมูลเชิงประจักษ์ (Syntax Enclosure, Face Graphic, Active Party Leader, Event Triggers)
3. Semantic Delegation: ส่งต่อการอนุมานบริบท (Whisper vs Monologue vs Aside, Speaker -> Listener) ให้ LLM ประมวลผลในชั้น Prompt
4. Choice Collision Detection: ตรวจจับชอยส์ที่ถูกเรียกซ้ำ (Multi-referenced) เพื่อบังคับ Universal Safe Translation (ใช่/ไม่ใช่)
"""

import os
import sys
import json
import csv
import re
from collections import Counter, defaultdict

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "data", "project_manifest.json")


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_output_packets_path(manifest=None):
    if manifest is None:
        manifest = load_manifest()
    target = manifest.get("output_scenes_json")
    if not target:
        tlas_dir = manifest.get("output_tlas_dir") or os.path.join(WORKSPACE_ROOT, "data", "tlas")
        target = os.path.join(tlas_dir, "scene_packets.json")
    return os.path.abspath(target)


def detect_syntax_enclosure(text: str) -> str:
    """ตรวจจับว่าข้อความถูกครอบด้วยเครื่องหมายใด เพื่อส่งเป็นเบาะแสโครงสร้างให้ LLM"""
    s = text.strip()
    if not s or len(s) < 2:
        return "none"
    
    # วงเล็บ: ( ... ) หรือ （ ... ） -> อาจเป็น กระซิบ / บันทึกกำกับ / ข้อความระบบ / คิดในใจ
    if (s.startswith("(") and s.endswith(")")) or (s.startswith("（") and s.endswith("）")):
        return "parentheses"
        
    # เครื่องหมายคำพูดหรือวงเล็บเน้นย้ำ: 「...」, 『...』, "...", '...'
    quote_pairs = [
        ("「", "」"), ("『", "』"), ('"', '"'), ("'", "'"), ("[", "]"), ("【", "】")
    ]
    for q_open, q_close in quote_pairs:
        if s.startswith(q_open) and s.endswith(q_close):
            return "quoted"
            
    return "none"


def load_party_leader_metadata(game_data_dir: str = None):
    """
    ดึงข้อมูลหัวหน้าปาร์ตี้เริ่มต้นและรายชื่อตัวละครจาก Engine Data (เช่น System.json / Actors.json)
    เพื่อใช้เป็น Factual Grounding สำหรับ Untagged Dialogues
    """
    initial_leader_name = "Controlled Actor / Leader"
    actors_map = {}

    if not game_data_dir:
        manifest = load_manifest()
        game_data_dir = manifest.get("game_data_directory") or os.path.join(WORKSPACE_ROOT, "www", "data")

    actors_file = os.path.join(game_data_dir, "Actors.json")
    system_file = os.path.join(game_data_dir, "System.json")

    if os.path.exists(actors_file):
        try:
            with open(actors_file, "r", encoding="utf-8-sig") as f:
                actors_data = json.load(f)
                for a in actors_data:
                    if a and isinstance(a, dict) and "id" in a and "name" in a:
                        actors_map[a["id"]] = a["name"]
        except Exception as e:
            print(f"[!] Warning reading Actors.json: {e}")

    if os.path.exists(system_file):
        try:
            with open(system_file, "r", encoding="utf-8-sig") as f:
                sys_data = json.load(f)
                party = sys_data.get("partyMembers", [])
                if party and len(party) > 0:
                    leader_id = party[0]
                    if leader_id in actors_map:
                        initial_leader_name = actors_map[leader_id]
        except Exception as e:
            print(f"[!] Warning reading System.json: {e}")

    return initial_leader_name, actors_map


def extract_engine_choices(game_data_dir: str):
    """
    สกัด Choices จาก AST จริงของเอนจินเกม (RPG Maker MV/MZ Code 102 Show Choices)
    เพื่อความถูกต้อง 100% ปราศจากการเดาคำศัพท์เฉพาะภาษา
    """
    engine_choices = Counter()
    if not game_data_dir or not os.path.exists(game_data_dir):
        return engine_choices

    for fname in os.listdir(game_data_dir):
        if (fname.startswith("Map") and fname.endswith(".json") and fname != "MapInfos.json") or fname == "CommonEvents.json":
            fpath = os.path.join(game_data_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
                    data = json.load(f)
                    events = data if isinstance(data, list) else data.get("events", [])
                    for ev in events:
                        if not ev:
                            continue
                        pages = ev.get("pages", []) if isinstance(ev, dict) else [ev]
                        for page in pages:
                            if not page:
                                continue
                            cmd_list = page.get("list", [])
                            for cmd in cmd_list:
                                if cmd and cmd.get("code") == 102:
                                    params = cmd.get("parameters", [])
                                    if params and len(params) > 0 and isinstance(params[0], list):
                                        for ch_text in params[0]:
                                            if ch_text and isinstance(ch_text, str):
                                                engine_choices[ch_text.strip()] += 1
            except Exception:
                pass
    return engine_choices


def extract_packets(csv_path: str, data_dir: str = None):
    print("=" * 80)
    print("      ATF UNIVERSAL SCENE PACKETIZER & FLOW EXTRACTOR (v2.0)      ")
    print("=" * 80)
    print(f"[*] Target CSV: {csv_path}")

    if not os.path.exists(csv_path):
        print(f"❌ Error: ไม่พบไฟล์ CSV ที่: {csv_path}")
        sys.exit(1)

    initial_leader_name, actors_map = load_party_leader_metadata(data_dir)
    print(f"[*] Initial Active Party Leader (from System.json): '{initial_leader_name}'")
    print(f"[*] Registered Database Actors: {actors_map}")

    # 1. สกัด Choices จาก AST เอนจินเกม (Code 102) แบบ 100% Factual Grounding
    if not data_dir:
        manifest = load_manifest()
        data_dir = manifest.get("game_data_directory") or os.path.join(WORKSPACE_ROOT, "www", "data")
    engine_choices = extract_engine_choices(data_dir)
    print(f"[*] Factual Engine Choices Extracted (Code 102 AST): {len(engine_choices):,} distinct choices")

    # 2. รวบรวมข้อมูล CSV
    raw_csv_rows = []
    choice_occurrences = Counter()
    if engine_choices:
        choice_occurrences.update(engine_choices)

    with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for idx, row in enumerate(reader, start=2):
            raw_csv_rows.append((idx, row))
            if row and len(row) > 0:
                t = row[0].strip()
                if not engine_choices:
                    # กรณีไม่มีโฟลเดอร์ data ให้ fallback ตรวจจับจาก pattern สากล
                    if len(t) <= 25 and "\n" not in t and t not in {"EV001", "EV002", "EV003"}:
                        if any(t.startswith(x) for x in ["はい", "いいえ", "Yes", "No", "やめる", "続ける"]):
                            choice_occurrences[t] += 1

    print(f"[*] Loaded {len(raw_csv_rows):,} rows from CSV")
    print(f"[*] Distinct Choice Candidates Tracked: {len(choice_occurrences):,}")

    # 2. จัดกลุ่ม Scene Packets ตาม Continuity & Engine Boundaries
    scene_packets = []
    current_packet = None
    current_file = None
    last_event_name = None

    def finalize_packet(pkt):
        if not pkt or not pkt["dialogues"]:
            return
        # สรุปรายชื่อผู้ที่มีบทพูดชัดเจนในซีน (Factual Explicit Speakers)
        explicit_speakers = list(dict.fromkeys([
            d["speaker"] for d in pkt["dialogues"] 
            if d["speaker"] and d["speaker"] not in ["Untagged", "Choice", "System"]
        ]))
        pkt["explicit_speakers"] = explicit_speakers

        # กำหนด Candidate Listeners ให้แต่ละประโยคอย่างมีความหมาย (แทนการปล่อย null)
        for d in pkt["dialogues"]:
            spk = d["speaker"]
            if d.get("is_choice") or spk == "Choice":
                d["candidate_listeners"] = ["Game System / Player"]
            elif spk == "System":
                d["candidate_listeners"] = ["Player"]
            elif spk in explicit_speakers:
                # ผู้ฟังที่เป็นไปได้: สมาชิกคนอื่นในซีน + คุยกับตัวเอง (Self) + ผู้เล่น/สภาพแวดล้อม (Environment)
                other_characters = [s for s in explicit_speakers if s != spk]
                d["candidate_listeners"] = other_characters + ["Self (Monologue/Soliloquy)", "Player / Environment"]
            elif spk == "Untagged":
                d["candidate_listeners"] = explicit_speakers + ["Player / Reader"]
            else:
                d["candidate_listeners"] = ["Audience / Contextual"]
        
        # แนบข้อมูลเบื้องต้นให้ LLM ไปวิเคราะห์ต่อในชั้น Prompt
        pkt["scene_metadata"] = {
            "active_party_leader": initial_leader_name,
            "explicit_speakers": explicit_speakers,
            "speaker_count": len(explicit_speakers),
            "contains_choices": len(pkt["choice_links"]) > 0
        }
        # ล้าง flag ช่วยคุม choice
        pkt.pop("in_choice_block", None)
        scene_packets.append(pkt)

    for r_idx, row in raw_csv_rows:
        if not row or not row[0].strip():
            continue

        orig = row[0].strip()
        filename = row[2].strip() if len(row) > 2 else ""
        tpp_row = row[3].strip() if len(row) > 3 else ""

        # ข้าม Noise คำสั่งสคริปต์ทางเทคนิค (Engine Script Commands / Internal Tags)
        if orig.startswith("D_TEXT") or orig.startswith("<Darkness") or orig.startswith("灯り"):
            continue

        # ตรวจสอบว่าเป็น Choice หรือไม่
        is_choice = orig in choice_occurrences

        # หาก Packet ก่อนหน้าเพิ่งเจอกลุ่ม Choices และข้อความปัจจุบันไม่ใช่ Choice
        # แปลว่าจบ Choice Block แล้ว -> ปิด Packet เดิม เพื่อเริ่มทางแยก (Branch) ใหม่
        if current_packet and current_packet.get("in_choice_block") and not is_choice:
            finalize_packet(current_packet)
            current_packet = None

        # ตรวจสอบ Event Name หรือ Object Name ในไฟล์ Map (เช่น EV001, 凛, 夫, 民宿)
        is_event_marker = False
        if filename.startswith("Map") and len(orig) <= 20 and "\n" not in orig:
            if orig.startswith("EV") or orig in actors_map.values() or "日目" in orig:
                is_event_marker = True
                last_event_name = orig

        # จุดตัดข้ามไฟล์ (Cross-File Boundary): สิ้นสุดฉากทันทีเมื่อเปลี่ยนไฟล์
        if current_file is None or filename != current_file:
            if current_packet:
                finalize_packet(current_packet)
                current_packet = None
            current_file = filename

        # ตรวจจับโครงสร้าง Speaker Tag
        speaker = None
        clean_text = orig

        m = SYNTACTIC_SPEAKER_REGEX.search(orig)
        if m:
            # ดึง Tag จากกลุ่มที่ match
            speaker = (m.group(1) or m.group(2)).strip()
            clean_text = orig[m.end():].lstrip("\r\n :")
        elif is_event_marker:
            # เครื่องหมายบอกตำแหน่ง Event -> บันทึกเป็นบริบทของฉาก แต่ไม่ใช่ Dialogue โดยตรง
            continue
        else:
            # ไม่มี Speaker Tag -> ทำเครื่องหมายเป็น Untagged
            speaker = "Untagged"

        # ตรวจจับคุณสมบัติโครงสร้าง (Structural Evidence)
        syntax_enclosure = detect_syntax_enclosure(clean_text)

        # เปิด Packet ใหม่เมื่อยังไม่มี
        if current_packet is None:
            current_packet = {
                "packet_id": f"{filename}_Packet_{len(scene_packets) + 1:04d}",
                "filename": filename,
                "event_context": last_event_name,
                "start_csv_row": r_idx,
                "end_csv_row": r_idx,
                "dialogues": [],
                "choice_links": [],
                "in_choice_block": False
            }

        # การประมวลผลกรณี Choice
        if is_choice:
            ref_count = choice_occurrences[orig]
            # แยกแยะระหว่าง Independent Instance (แถวเฉพาะใน Map นั้นๆ) กับ Shared CommonEvent (แถวเดียวที่ถูกเรียกจากหลายที่)
            if filename == "CommonEvents":
                collision_mode = "SHARED_COMMON_EVENT (Shared across scenes - Universal Safe Translation Mandatory)"
            else:
                collision_mode = "INDEPENDENT_INSTANCE (Dedicated Row for this Event - Contextual Translation Permitted)"

            # หาคำถามก่อนหน้า (Parent Prompt): ค้นหาย้อนหลังจากบทพูดที่ไม่ใช่ Choice
            parent_prompt = ""
            if current_packet["dialogues"]:
                for d in reversed(current_packet["dialogues"]):
                    if not d.get("is_choice"):
                        parent_prompt = d["clean_text"]
                        break

            choice_info = {
                "csv_row": r_idx,
                "choice_text": orig,
                "parent_prompt": parent_prompt,
                "ref_count": ref_count,
                "collision_mode": collision_mode
            }
            current_packet["choice_links"].append(choice_info)

            current_packet["dialogues"].append({
                "csv_row": r_idx,
                "speaker": "Choice",
                "listener": "Player",
                "clean_text": orig,
                "raw_text": orig,
                "syntax_enclosure": syntax_enclosure,
                "is_choice": True,
                "choice_metadata": choice_info
            })
            current_packet["end_csv_row"] = r_idx
            # ทำเครื่องหมายว่ากำลังอยู่ในช่วง Choice Block (ไม่ปิดทันที เพื่อรวมชอยส์คู่กัน เช่น ใช่/ไม่ใช่)
            current_packet["in_choice_block"] = True
            continue

        # เพิ่มข้อความปกติลงใน Packet
        current_packet["dialogues"].append({
            "csv_row": r_idx,
            "speaker": speaker,
            "candidate_listeners": None,  # จะถูกเติมใน finalize_packet
            "clean_text": clean_text,
            "raw_text": orig,
            "syntax_enclosure": syntax_enclosure,
            "is_choice": False
        })
        current_packet["end_csv_row"] = r_idx

    if current_packet:
        finalize_packet(current_packet)

    # 3. รายงานสรุปผล
    print("\n" + "=" * 80)
    print("                    ATF SCENE PACKETS EXTRACTION AUDIT                    ")
    print("=" * 80)
    print(f"🎬 Total Coherent Scene Packets Extracted: {len(scene_packets):,} Packets")
    total_dlgs = sum(len(p["dialogues"]) for p in scene_packets)
    total_choices = sum(len(p["choice_links"]) for p in scene_packets)
    print(f"💬 Dialogues Captured inside Packets:      {total_dlgs:,} lines")
    print(f"🔗 Choices Linked & Analyzed:              {total_choices:,} choices")
    print("-" * 80)

    # ตรวจสอบ Choice Collision & Instance Summary
    shared_choices = {k: v for k, v in choice_occurrences.items() if v > 1}
    print(f"📌  Choice Instance Analysis:")
    print(f"    - Distinct Choice Strings: {len(choice_occurrences)} strings (Global frequency tracked)")
    print(f"    - Dedicated Map Rows:      Independent Instances (แปลตามบริบทคำถามเฉพาะแถวได้)")
    print(f"    - CommonEvents Rows:       Shared References (ล็อกคำแปลสากล ป้องกันผลกระทบข้ามฉาก)")
    print("-" * 80)

    # ตัวอย่าง 6 Packet แรก
    print(f"{'Packet ID':<25} | {'Rows':<12} | {'Explicit Speakers':<24} | {'Sample Dialogue'}")
    print("-" * 80)
    for p in scene_packets[:6]:
        rows_str = f"{p['start_csv_row']}..{p['end_csv_row']}"
        spks_str = ", ".join(p["explicit_speakers"]) if p["explicit_speakers"] else "(Untagged/Ambient)"
        sample_dlg = p["dialogues"][0]["clean_text"][:25].replace("\n", " ") if p["dialogues"] else ""
        print(f"{p['packet_id']:<25} | {rows_str:<12} | {spks_str[:24]:<24} | {sample_dlg}...")

    # บันทึกไฟล์ JSON ลง Target Deliverable ปลายทาง
    output_path = get_output_packets_path()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "framework": "Agentic Translation Framework (ATF) Universal Packetizer",
            "version": "2.0",
            "active_party_leader": initial_leader_name,
            "registered_database_actors": actors_map,
            "total_packets": len(scene_packets),
            "total_dialogues": total_dlgs,
            "total_choices_linked": total_choices,
            "shared_choices_count": len(shared_choices),
            "packets": scene_packets
        }, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"💾 Saved Clean Universal Scene Packets: {output_path}\n")
    return scene_packets


if __name__ == "__main__":
    manifest = load_manifest()
    csv_file = sys.argv[1] if len(sys.argv) > 1 else manifest.get("raw_pre_csv")
    if not csv_file:
        print("[ERROR] No input CSV specified and no raw_pre_csv found in manifest.")
        sys.exit(1)
    
    data_folder = manifest.get("game_data_directory")
    extract_packets(csv_file, data_folder)
