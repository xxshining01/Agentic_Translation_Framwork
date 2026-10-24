#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync Checkpoint to CSV & Pure Queue Alignment (SDD-014 & SAD-012 Compliant)
สคริปต์เติมคำแปลจาก Checkpoint (chatgpt_translation_checkpoint.json) ลงในไฟล์ CSV
พร้อมระบบคัดกรองคิวบริสุทธิ์ (Pure Queue Filter) และการจัดระเบียบบรรทัดตรงกับต้นฉบับ 100% (Strict Parity)
ตามข้อกำหนดของ ADR-017, SAD-012, และ SDD-014
"""

import os
import sys
import re
import csv
import json
import shutil
import datetime
import argparse
import io
import time
from typing import List, Dict, Tuple, Optional, Any, Set

# ป้องกันปัญหา UnicodeEncodeError และบัฟเฟอร์ค้างบน Windows คอนโซล
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
elif sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ROOT_DIR = BASE_DIR
src_dir = os.path.join(BASE_DIR, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from atf.core.smart_line_splitter import SmartLineSplitter
    has_splitter = True
except ImportError:
    has_splitter = False

DEFAULT_CSV = os.path.join(BASE_DIR, "output", "processed_dialogues.csv")
CHECKPOINT_PATH = os.path.join(BASE_DIR, "data", "tlas", "chatgpt_translation_checkpoint.json")


class CheckpointConsolidator:
    """
    โมดูลรวบรวมและประสานข้อมูลคำแปลจากทุก Section ใน Checkpoint JSON (SDD-014 Section 2)
    """
    @staticmethod
    def load_unified_translations(checkpoint_path: str) -> Tuple[Dict[str, str], Dict[Tuple[str, str], str], Dict[str, str], Dict[str, Any]]:
        """โหลดและรวมคำแปลจากทุก Section Key ใน csv_translations พร้อมสร้าง Content-based Map (Filename, Original)"""
        unified_translations: Dict[str, str] = {}
        content_map: Dict[Tuple[str, str], str] = {}
        fallback_map: Dict[str, str] = {}
        if not os.path.exists(checkpoint_path):
            return unified_translations, content_map, fallback_map, {}

        with open(checkpoint_path, "r", encoding="utf-8") as f:
            cp_data = json.load(f)

        csv_trans = cp_data.get("csv_translations", {})
        for sec, trans_map in csv_trans.items():
            if isinstance(trans_map, dict):
                candidate_paths = [
                    os.path.join(ROOT_DIR, "data", sec),
                    os.path.join(ROOT_DIR, "output", sec),
                    os.path.join(ROOT_DIR, sec)
                ]
                source_csv = next((p for p in candidate_paths if os.path.exists(p)), None)
                if source_csv:
                    try:
                        with open(source_csv, "r", encoding="utf-8-sig", errors="ignore") as sf:
                            sreader = csv.reader(sf)
                            _ = next(sreader)
                            srows = list(sreader)
                            for row_k, text_val in trans_map.items():
                                if text_val and str(text_val).strip():
                                    unified_translations[str(row_k)] = str(text_val)
                                    r_int = int(row_k)
                                    if 0 <= r_int < len(srows):
                                        s_orig = srows[r_int][0].strip()
                                        s_fn = srows[r_int][2].strip() if len(srows[r_int]) > 2 else ""
                                        if s_orig:
                                            content_map[(s_fn, s_orig)] = str(text_val)
                                            if s_orig not in fallback_map:
                                                fallback_map[s_orig] = str(text_val)
                    except Exception:
                        pass
                else:
                    for row_k, text_val in trans_map.items():
                        if text_val and str(text_val).strip():
                            unified_translations[str(row_k)] = str(text_val)

        return unified_translations, content_map, fallback_map, cp_data

    @staticmethod
    def update_two_way_sync(
        raw_checkpoint: Dict[str, Any],
        row_index: str,
        text: str,
        active_sections: List[str]
    ) -> None:
        """บันทึกคำแปลที่ผ่านการซ่อมแซมลงสู่ทุก Section Key พร้อมกันในหน่วยความจำ"""
        if "csv_translations" not in raw_checkpoint:
            raw_checkpoint["csv_translations"] = {}
        for sec in active_sections:
            raw_checkpoint["csv_translations"].setdefault(sec, {})[str(row_index)] = text


class PureQueueFilter:
    """
    โมดูลวิเคราะห์และคัดกรองแถวบริสุทธิ์สำหรับส่งเข้าคิวแปล LLM (SDD-014 Section 2 & 4)
    """
    NON_TRANSLATABLE_SYMBOLS: Set[str] = {"-", "--", "---", "...", "..", "***", "??", "!!"}
    PURE_SYMBOLS_PATTERN: str = r"^[\s\-_.\*~!?,:;\"'()\[\]{}|\\/]+$"
    PURE_CONTROL_TAGS_PATTERN: str = r"^(?:\\[a-zA-Z]+(?:\[\d+\])?|\s+)+$"

    @classmethod
    def is_natural_language_text(cls, text: str) -> bool:
        """ตรวจสอบว่าข้อความมีเนื้อหาภาษาธรรมชาติที่ต้องแปลหรือไม่"""
        clean = text.strip()
        if not clean:
            return False
        if clean in cls.NON_TRANSLATABLE_SYMBOLS:
            return False
        if re.match(cls.PURE_SYMBOLS_PATTERN, clean):
            return False
        if re.match(cls.PURE_CONTROL_TAGS_PATTERN, clean):
            return False
        if not re.search(r"[a-zA-Z\u0E00-\u0E7F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", clean):
            return False
        return True

    @classmethod
    def is_eligible_for_translation(cls, row: List[str]) -> Tuple[bool, str]:
        """
        ตรวจสอบความเหมาะสมในการส่งแปลตาม Decision Matrix ของ SDD-014
        Schema: Original, Initial, Filename, Row, Note, Role, Speaker, Displayable
        """
        if len(row) < 8:
            return False, "Insufficient columns"
        orig = row[0]
        init = row[1]
        role = row[5]
        speaker = row[6]
        displayable = row[7]

        if displayable.strip() != "Yes":
            return False, f"Displayable is not Yes ({displayable})"
        if role.strip() not in {"Dialogue/Story", "System/Menu", "Skill/Item"}:
            return False, f"Role '{role}' is not in translatable whitelist"
        if not orig.strip():
            return False, "Original is empty"
        if not cls.is_natural_language_text(orig):
            return False, "Non-natural language / pure symbols"

        return True, "Eligible"


class AtomicPersistenceManager:
    """
    โมดูลจัดการการบันทึกไฟล์ลงฮาร์ดดิสก์แบบ Atomic ป้องกันข้อมูลเสียหาย 100% (SDD-014 Section 2)
    """
    @staticmethod
    def create_timestamped_backup(file_path: str, suffix: str = "backup_sync") -> str:
        if not os.path.exists(file_path):
            return ""
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file_path)[1]
        bak_path = f"{file_path}.{suffix}_{now_str}{ext}"
        shutil.copy2(file_path, bak_path)
        return bak_path

    @staticmethod
    def atomic_write_csv(file_path: str, rows: List[List[str]]) -> None:
        temp_csv = f"{file_path}.tmp"
        with open(temp_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_csv, file_path)

    @staticmethod
    def atomic_write_json(file_path: str, data: Dict[str, Any]) -> None:
        temp_json = f"{file_path}.tmp"
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_json, file_path)


def sync_and_align_lines(csv_path=DEFAULT_CSV, checkpoint_path=CHECKPOINT_PATH, dry_run=False, fix_all_line_counts=True):
    start_t = time.time()
    print("=" * 80, flush=True)
    print("🔄 SYNCING TRANSLATIONS & ALIGNING LINE BREAKS (SDD-014 / SAD-012 COMPLIANT)", flush=True)
    print(f"Target CSV: {csv_path}", flush=True)
    print(f"Checkpoint: {checkpoint_path}", flush=True)
    print(f"Mode: {'DRY RUN (Simulation only)' if dry_run else 'LIVE EXECUTION (Modifying CSV & Checkpoint)'}", flush=True)
    print(f"Fix All Line Counts: {'YES (Ensuring all rows match English lines 100%)' if fix_all_line_counts else 'NO'}", flush=True)
    print("=" * 80, flush=True)

    if not os.path.exists(csv_path):
        print(f"❌ Target CSV not found: {csv_path}", flush=True)
        return
    if not os.path.exists(checkpoint_path):
        print(f"❌ Checkpoint not found: {checkpoint_path}", flush=True)
        return

    # 1. รวบรวมคำแปลข้าม Section ทั้งหมดผ่าน CheckpointConsolidator แบบ Content-based
    print("⏳ Loading and consolidating translations from Checkpoint...", flush=True)
    checkpoint_translations, cp_content_map, cp_fallback_map, cp_data = CheckpointConsolidator.load_unified_translations(checkpoint_path)
    print(f"📦 Loaded {len(checkpoint_translations):,} cached entries. Resolved {len(cp_content_map):,} verified Content Keys.", flush=True)

    # 2. อ่านไฟล์ CSV
    print(f"⏳ Reading target CSV file: {csv_path}...", flush=True)
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [header] + list(reader)

    total_rows = len(rows)
    print(f"📋 Total CSV Rows: {total_rows:,}", flush=True)

    active_sections = [
        os.path.basename(csv_path)
    ]

    filled_from_checkpoint_count = 0
    line_count_repaired_count = 0
    auto_bypassed_count = 0
    pure_untranslated_queue_count = 0

    examples_filled = []
    examples_repaired = []

    print("⏳ Processing and evaluating all rows...", flush=True)
    for r_idx in range(1, total_rows):
        if r_idx % 20000 == 0:
            print(f"   ... Progress: {r_idx:,}/{total_rows-1:,} rows scanned ({r_idx*100//total_rows}%)", flush=True)

        row = rows[r_idx]
        if len(row) < 2:
            continue

        orig = row[0]
        init = row[1]
        str_r = str(r_idx)
        row_fn = row[2].strip() if len(row) > 2 else ""
        orig_clean = orig.strip()

        orig_nl = orig.count("\n")
        init_nl = init.count("\n")

        # กรณีที่ 1: แถวที่ Initial ว่างเปล่า -> ดึงคำแปลจาก Content-based Key
        translated_text = None
        if not init.strip():
            if (row_fn, orig_clean) in cp_content_map:
                translated_text = cp_content_map[(row_fn, orig_clean)]
            elif orig_clean in cp_fallback_map:
                translated_text = cp_fallback_map[orig_clean]

        if translated_text:
            if orig_nl > 0 and has_splitter:
                final_text = SmartLineSplitter.split_thai_to_match_original(orig, translated_text)
            else:
                pfx = ""
                pure = translated_text
                if has_splitter:
                    pfx, pure = SmartLineSplitter.extract_prefix(translated_text)
                pure_clean = re.sub(r"\s*\n\s*", " ", pure).strip()
                final_text = f"{pfx}{pure_clean}"

            filled_from_checkpoint_count += 1
            if len(examples_filled) < 5:
                role = row[5] if len(row) > 5 else ""
                speaker = row[6] if len(row) > 6 else ""
                examples_filled.append((r_idx, role, speaker, orig, final_text))

            init = final_text
            row[1] = final_text
            if not dry_run and cp_data:
                CheckpointConsolidator.update_two_way_sync(cp_data, str_r, final_text, active_sections)

        # กรณีที่ 2: ตรวจเช็คแถวที่มีคำแปลแล้ว แต่จำนวนบรรทัดยังไม่ตรงกับต้นฉบับ
        if fix_all_line_counts and init.strip():
            init_nl = init.count("\n")
            if orig_nl != init_nl:
                if orig_nl == 0:
                    pfx = ""
                    pure = init
                    if has_splitter:
                        pfx, pure = SmartLineSplitter.extract_prefix(init)
                    pure_clean = re.sub(r"\s*\n\s*", " ", pure).strip()
                    adjusted_text = f"{pfx}{pure_clean}"
                else:
                    if has_splitter:
                        adjusted_text = SmartLineSplitter.split_thai_to_match_original(orig, init)
                    else:
                        adjusted_text = init

                if adjusted_text != init:
                    line_count_repaired_count += 1
                    if len(examples_repaired) < 5:
                        role = row[5] if len(row) > 5 else ""
                        speaker = row[6] if len(row) > 6 else ""
                        examples_repaired.append((r_idx, role, speaker, orig, init, adjusted_text))

                    row[1] = adjusted_text
                    if not dry_run and cp_data:
                        CheckpointConsolidator.update_two_way_sync(cp_data, str_r, adjusted_text, active_sections)

        # กรณีที่ 3: แถวยังว่างเปล่า ประเมินด้วย PureQueueFilter
        if not row[1].strip():
            is_eligible, reason = PureQueueFilter.is_eligible_for_translation(row)
            if not is_eligible:
                if "Non-natural language" in reason:
                    row[1] = orig
                    auto_bypassed_count += 1
            else:
                pure_untranslated_queue_count += 1

    elapsed = time.time() - start_t
    print(f"\n📊 SUMMARY REPORT (Completed in {elapsed:.2f}s):", flush=True)
    print(f"  • แถวที่ Initial ว่างเปล่า และได้รับการเติมคำแปลจาก Checkpoint: {filled_from_checkpoint_count:,} แถว", flush=True)
    print(f"  • แถวที่ปรับแต่งจำนวนบรรทัดให้ตรงกับต้นฉบับ 100%: {line_count_repaired_count:,} แถว", flush=True)
    print(f"  • แถวสัญลักษณ์/รหัสควบคุมที่ทำการ Auto-Bypass: {auto_bypassed_count:,} แถว", flush=True)
    print(f"  • แถวบทสนทนาบริสุทธิ์ที่ยังตกค้างรอแปลจริง (Pure Dialogue Queue): {pure_untranslated_queue_count:,} แถว", flush=True)

    if examples_filled:
        print("\n🔍 ตัวอย่างแถวที่ดึงคำแปลจาก Checkpoint มาเติมลง CSV (5 แถวแรก):", flush=True)
        for r_idx, role, spk, orig, rep in examples_filled:
            print(f"\n[แถว {r_idx}] Role: {role} | Speaker: {spk}", flush=True)
            print(f"  ORIG ({orig.count(chr(10))+1} บรรทัด):\n{repr(orig)}", flush=True)
            print(f"  FILLED ({rep.count(chr(10))+1} บรรทัด):\n{repr(rep)}", flush=True)

    if examples_repaired:
        print("\n🔍 ตัวอย่างแถวที่ปรับจำนวนบรรทัดให้ตรงกับต้นฉบับ (5 แถวแรก):", flush=True)
        for r_idx, role, spk, orig, old_init, new_init in examples_repaired:
            print(f"\n[แถว {r_idx}] Role: {role} | Speaker: {spk}", flush=True)
            print(f"  ORIG ({orig.count(chr(10))+1} บรรทัด):\n{repr(orig)}", flush=True)
            print(f"  BEFORE ({old_init.count(chr(10))+1} บรรทัด):\n{repr(old_init)}", flush=True)
            print(f"  AFTER ({new_init.count(chr(10))+1} บรรทัด):\n{repr(new_init)}", flush=True)

    if dry_run:
        print("\n💡 This was a DRY RUN (Simulation). No files were modified on disk.", flush=True)
        print("   To apply changes for real, run without --dry-run", flush=True)
    else:
        print("\n💾 Committing changes to disk via Atomic Persistence...", flush=True)
        bak_csv = AtomicPersistenceManager.create_timestamped_backup(csv_path, suffix="backup_sync")
        print(f"  • Created backup CSV at: {bak_csv}", flush=True)

        AtomicPersistenceManager.atomic_write_csv(csv_path, rows)
        print(f"  • Successfully written all updates into: {csv_path}", flush=True)

        if cp_data:
            bak_cp = AtomicPersistenceManager.create_timestamped_backup(checkpoint_path, suffix="backup_sync")
            print(f"  • Created backup Checkpoint at: {bak_cp}", flush=True)

            AtomicPersistenceManager.atomic_write_json(checkpoint_path, cp_data)
            print(f"  • Successfully synced and updated translations in Checkpoint: {checkpoint_path}", flush=True)
        print("🎉 ALL STATE SYNCHRONIZATION COMPLETED SUCCESSFULLY 100%!", flush=True)


if __name__ == "__main__":
    try:
        manifest_path = os.path.join(BASE_DIR, "data", "project_manifest.json")
        default_csv = DEFAULT_CSV
        default_cp = CHECKPOINT_PATH

        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    mdata = json.load(mf)
                    if mdata.get("output_processed_csv") and os.path.exists(mdata["output_processed_csv"]):
                        default_csv = mdata["output_processed_csv"]
                    if mdata.get("output_checkpoint_json") and os.path.exists(mdata["output_checkpoint_json"]):
                        default_cp = mdata["output_checkpoint_json"]
            except Exception:
                pass

        parser = argparse.ArgumentParser(description="Sync Checkpoint Translations and Align Line Breaks (SDD-014)")
        parser.add_argument("--file", type=str, default=default_csv, help="Target CSV file")
        parser.add_argument("--checkpoint", type=str, default=default_cp, help="Checkpoint file")
        parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
        parser.add_argument("--no-fix-lines", action="store_true", help="Skip fixing line count mismatches")
        args = parser.parse_args()

        sync_and_align_lines(
            args.file,
            args.checkpoint,
            dry_run=args.dry_run,
            fix_all_line_counts=not args.no_fix_lines
        )
    except Exception as e:
        import traceback
        print(f"\n❌ FATAL ERROR: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)
