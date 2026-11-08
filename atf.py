#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agentic Translation Framework (ATF) - Master Unified CLI v2.0
==============================================================
ระบบโครงร่างการแปลเกมและอัปเดตแพตช์อัตโนมัติสากล (Universal Game Localization Framework)

คำสั่งหลัก (Main Subcommands):
  1. setup       : ตั้งค่าพื้นที่ทำงาน ค้นหาเกม ไฟล์ต้นฉบับ และกำหนดโฟลเดอร์ output
  2. bridge      : เปิดเซิร์ฟเวอร์ ChatGPT Web Bridge เพื่อเชื่อมต่อ Tampermonkey
  3. scan        : สแกนรายชื่อตัวละครและ Speaker Tags ทั้งหมดจากบทสนทนาเกม
  4. glossary    : สังเคราะห์ Master Glossary ล็อกคำแปลไทย 1:1 และสร้าง Character Whitelist
  5. packets     : สกัดความต่อเนื่องของฉาก (Scene Packets) และวิเคราะห์ Choice Collisions
  6. matrix      : สังเคราะห์ Character Profiles และ Demographic Pronoun Matrix (IDPR v5.0)
  7. build-table : สร้างตารางแปลเกม 10 คอลัมน์ (Rich Schema) พร้อม Conversational Triad & Game Shielding
  8. translate   : สั่งรันการแปลผ่าน ChatGPT Web Bridge (Persistent Invariant & Auto-Repair)
  9. verify      : รันการตรวจสอบคุณภาพและความสมบูรณ์รอบด้าน 8 มิติ (8-Dimension LQA Audit)
 10. plugins     : สกัด (--extract) หรือฉีดคำแปล (--inject) ข้อความ UI ของ plugins.js
 11. export      : ส่งออกไฟล์ CSV แพตช์เกมฉบับสมบูรณ์พร้อมนำไปใช้งานในเกม
 12. prepare-all : รันขั้นตอนเตรียมข้อมูลทั้งหมด (scan -> glossary -> packets -> matrix -> build-table) ในคำสั่งเดียว
"""

import os
import sys
import argparse
import subprocess
from typing import List

# กำหนด Root Directory
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
TOOLS_DIR = os.path.join(ROOT_DIR, "src", "atf", "tools")


def run_script(script_name: str, extra_args: List[str] = None) -> int:
    """รันสคริปต์ใน tools directory ผ่าน Python interpreter เดียวกัน"""
    script_path = os.path.join(TOOLS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"❌ ไม่พบสคริปต์: {script_path}")
        return 1
    
    cmd = [sys.executable, script_path]
    if extra_args:
        cmd.extend(extra_args)
    
    return subprocess.call(cmd)


def main():
    parser = argparse.ArgumentParser(
        prog="python atf.py",
        description="🚀 Agentic Translation Framework (ATF) - Master Universal CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน (Usage Examples):
  python atf.py setup                  # ตั้งค่าโฟลเดอร์เกมและไฟล์เริ่มต้น
  python atf.py bridge                 # เปิดสะพานเชื่อมต่อ ChatGPT Web Bridge
  python atf.py prepare-all            # เตรียมข้อมูลทั้งเกม (สแกนชื่อ, ศัพท์, ฉาก, เมทริกซ์, สร้างตาราง 10 คอลัมน์)
  python atf.py translate --dry-run    # ทดสอบจำลองการแปลออฟไลน์ 15 แถวแรก
  python atf.py translate --batches 5  # รันแปลจริง 5 แบตช์ผ่าน ChatGPT Bridge
  python atf.py translate              # รันแปลต่อเนื่องจนจบทั้งเกม
  python atf.py verify                 # ตรวจสอบความถูกต้องและคุณภาพ 8 มิติ
  python atf.py plugins --inject       # ฉีดคำแปล UI กลับเข้า plugins.js ของเกม
  python atf.py export                 # ส่งออกไฟล์ตารางแปลสำหรับแพตช์เกม
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="คำสั่งที่ต้องการทำงาน")

    # 1. setup
    subparsers.add_parser("setup", help="ตั้งค่าพื้นที่ทำงาน ค้นหาเกม ไฟล์ต้นฉบับ และกำหนด project_manifest.json")

    # 2. bridge
    subparsers.add_parser("bridge", help="เปิดเซิร์ฟเวอร์ ChatGPT Web Bridge (พอร์ต 5000)")

    # 3. scan
    subparsers.add_parser("scan", help="สแกนรายชื่อตัวละครทั้งหมดจากบทสนทนา (scanned_speakers.json)")

    # 4. glossary
    subparsers.add_parser("glossary", help="สร้าง Master Glossary ล็อกชื่อไทย 1:1 และ character_whitelist.json")

    # 5. packets
    subparsers.add_parser("packets", help="สกัดความต่อเนื่องของฉาก (Scene Packets) และวิเคราะห์ Choice Collision")

    # 6. matrix
    subparsers.add_parser("matrix", help="สร้างโปรไฟล์ตัวละครและตาราง Demographic Pronoun Matrix (v5.0)")

    # 7. build-table
    subparsers.add_parser("build-table", help="สร้างตาราง 10 คอลัมน์ (Speaker, Listener, Third_Person, Displayable)")

    # 8. translate
    parser_trans = subparsers.add_parser("translate", help="รันการแปลผ่าน ChatGPT Web Bridge")
    parser_trans.add_argument("--dry-run", action="store_true", help="จำลองการแปลออฟไลน์โดยไม่เรียก Bridge จริง")
    parser_trans.add_argument("--batches", type=int, default=0, help="จำนวน Batch ที่ต้องการรัน (0 = รันจนจบเรื่อง)")
    parser_trans.add_argument("--unified", action="store_true", help="แปล Plugins UI ก่อนแล้วตามด้วยบทสนทนา")
    parser_trans.add_argument("--reset-checkpoint", action="store_true", help="ล้าง Checkpoint เริ่มแปลใหม่ตั้งแต่แถว 0")
    parser_trans.add_argument("--skip-lqa", action="store_true", help="ข้ามการตรวจสอบ LQA อัตโนมัติ")

    # 9. verify
    subparsers.add_parser("verify", help="ตรวจสอบความสมบูรณ์และคุณภาพการแปล 8 มิติ (0 Violations Certified)")

    # 10. plugins
    parser_plugins = subparsers.add_parser("plugins", help="จัดการข้อความ UI ใน plugins.js")
    parser_plugins.add_argument("--extract", action="store_true", help="สกัดข้อความ UI จาก plugins.js ออกสู่ CSV")
    parser_plugins.add_argument("--inject", action="store_true", help="ฉีดคำแปลจาก CSV กลับเข้า plugins.js ของเกม")

    # 11. export
    subparsers.add_parser("export", help="ส่งออกไฟล์ CSV ผลลัพธ์สำหรับแพตช์คืนเกม")

    # 12. prepare-all
    subparsers.add_parser("prepare-all", help="เตรียมข้อมูลทั้งเกมครบวงจร (scan -> glossary -> packets -> matrix -> build-table)")

    args, unknown = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmd = args.command

    if cmd == "setup":
        print("\n🔧 [ATF] กำลังเปิดเครื่องมือตั้งค่า Workspace & Manifest...")
        sys.exit(run_script("setup_project_paths.py", unknown))

    elif cmd == "bridge":
        print("\n🌐 [ATF] กำลังเริ่ม ChatGPT Web Bridge Server (พอร์ต 5000)...")
        print("💡 อย่าลืมเปิดแท็บ https://chatgpt.com และเปิดใช้งาน Tampermonkey Userscript")
        sys.exit(run_script("chatgpt_bridge_server.py", unknown))

    elif cmd == "scan":
        print("\n🔎 [ATF Step 1] กำลังสแกน Speaker Tags จากบทสนทนาเกม...")
        sys.exit(run_script("scan_universal_speakers.py", unknown))

    elif cmd == "glossary":
        print("\n📖 [ATF Step 2] กำลังสังเคราะห์ Master Glossary และ Character Whitelist...")
        sys.exit(run_script("build_master_glossary.py", unknown))

    elif cmd == "packets":
        print("\n🎬 [ATF Step 3] กำลังสกัด Scene Packets และจับคู่ Choice Collision...")
        sys.exit(run_script("extract_scene_packets.py", unknown))

    elif cmd == "matrix":
        print("\n👥 [ATF Step 4] กำลังสังเคราะห์ Character Profiles และ Demographic Pronoun Matrix...")
        sys.exit(run_script("sync_profiles_and_matrix.py", unknown))

    elif cmd == "build-table":
        print("\n📊 [ATF Step 5] กำลังประกอบตาราง 10 คอลัมน์ (Conversational Triad & Game Shielding)...")
        sys.exit(run_script("generate_enriched_localization_csv.py", unknown))

    elif cmd == "prepare-all":
        print("\n" + "="*70)
        print("🚀 [ATF Automated Preparation Pipeline]")
        print("   ระบบจะเตรียมข้อมูลทั้งหมดโดยอัตโนมัติ 5 ขั้นตอน")
        print("="*70)

        steps = [
            ("Step 1: สแกนรายชื่อตัวละคร (Speaker Tags)", "scan_universal_speakers.py"),
            ("Step 2: สังเคราะห์ Master Glossary & Whitelist", "build_master_glossary.py"),
            ("Step 3: สกัด Scene Packets & Token Budget", "extract_scene_packets.py"),
            ("Step 4: สร้าง Profiles & Demographic Pronoun Matrix", "sync_profiles_and_matrix.py"),
            ("Step 5: สร้างตารางแปล 10 มิติ (Conversational Triad)", "generate_enriched_localization_csv.py"),
        ]

        for desc, script in steps:
            print(f"\n▶️ กำลังทำงาน: {desc}...")
            ret = run_script(script)
            if ret != 0:
                print(f"\n❌ ผิดพลาดในขั้นตอน: {desc} (Exit Code: {ret})")
                sys.exit(ret)

        # ซิงค์ไฟล์ TLAS ที่สร้างทั้งหมดไปยัง output_tlas_dir ใน manifest (ถ้ามี)
        manifest_path = os.path.join(ROOT_DIR, "data", "project_manifest.json")
        if os.path.exists(manifest_path):
            try:
                import json
                import shutil
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    mf_data = json.load(mf)
                target_tlas = mf_data.get("output_tlas_dir")
                local_tlas = os.path.join(ROOT_DIR, "data", "tlas")
                if target_tlas and os.path.abspath(target_tlas) != os.path.abspath(local_tlas):
                    os.makedirs(target_tlas, exist_ok=True)
                    for root, dirs, files in os.walk(local_tlas):
                        rel_path = os.path.relpath(root, local_tlas)
                        dest_dir = os.path.join(target_tlas, rel_path)
                        os.makedirs(dest_dir, exist_ok=True)
                        for f in files:
                            shutil.copy2(os.path.join(root, f), os.path.join(dest_dir, f))
                    print(f"\n📦 [TLAS Sync] ซิงค์ไฟล์ฐานข้อมูลทั้งหมดไปยัง {target_tlas} เรียบร้อยแล้ว")
            except Exception as sync_err:
                print(f"\n⚠️ Warning during TLAS sync: {sync_err}")

        print("\n" + "="*70)
        print("✅ [ATF Preparation Complete] เตรียมข้อมูลทั้งเกมเสร็จสมบูรณ์ 100%!")
        print("💡 ขั้นตอนถัดไป:")
        print("   1. เปิด Bridge Server:  python atf.py bridge  (ใน Terminal แยก)")
        print("   2. สั่งรันการแปล:       python atf.py translate")
        print("="*70 + "\n")
        sys.exit(0)

    elif cmd == "translate":
        runner_args = []
        if args.dry_run:
            runner_args.append("--dry-run")
        if args.batches > 0:
            runner_args.extend(["--batches", str(args.batches)])
        if args.unified:
            runner_args.append("--unified")
        if args.reset_checkpoint:
            runner_args.append("--fresh")
        runner_args.extend(unknown)

        print("\n🤖 [ATF Translation Runner] เริ่มต้นระบบการแปลผ่าน ChatGPT Web Bridge...")
        sys.exit(run_script("chatgpt_translator_runner.py", runner_args))

    elif cmd == "verify":
        print("\n🛡️ [ATF 8D LQA Engine] กำลังตรวจสอบความสมบูรณ์และคุณภาพการแปล 8 มิติ...")
        sys.exit(run_script("verify_localization_triad.py", unknown))

    elif cmd == "plugins":
        if args.extract:
            print("\n🧩 [ATF Plugins] กำลังสกัดข้อความ UI จาก plugins.js ออกสู่ CSV...")
            sys.exit(run_script("extract_plugin_texts.py", unknown))
        elif args.inject:
            print("\n🧩 [ATF Plugins] กำลังฉีดคำแปลจาก CSV กลับเข้าสู่ plugins.js ของเกม...")
            sys.exit(run_script("inject_plugin_texts.py", unknown))
        else:
            print("⚠️ กรุณาระบุ --extract (สกัดข้อความ) หรือ --inject (ฉีดคำแปล)")
            sys.exit(1)

    elif cmd == "export":
        print("\n📦 [ATF Export] กำลังส่งออกไฟล์ CSV ผลลัพธ์สำหรับแพตช์เกม...")
        sys.exit(run_script("export_final_game_patch_csv.py", unknown))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
