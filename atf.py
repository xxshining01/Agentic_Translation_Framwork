#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agentic Translation Framework (ATF) - Master Universal CLI (v6.0)
=================================================================
ระบบโครงร่างการแปลเกมและวิเคราะห์บริบทเกมอัตโนมัติสากล (Universal Game Localization Framework)

คำสั่งหลัก (Main Subcommands):
  0. setup              : ตั้งค่าพื้นที่ทำงาน ค้นหาเกม ไฟล์ต้นฉบับ และกำหนด project_manifest.json
  1. bridge             : เปิดสะพานเชื่อมต่อ ChatGPT Web Bridge (Port 5000 Daemon - อิสระจาก Pipeline)
  
  ขั้นตอนการเตรียมข้อมูลเกม (The 8 Preparation Stages):
  2. prepare-scenes     : [3a] สกัดฉากและความต่อเนื่องของ Event Flow สู่ scene_packets.json (Python)
  3. prepare-glossary   : [3b] สกัดชื่อตัวละคร ไอเทม สถานที่ สกิลจากฐานข้อมูลเกมสู่ tlas_glossary.json (Python)
  4. prepare-whitelist  : [3c] คัดกรองตัวละครสำคัญเข้าสู่ character_whitelist.json (ADR-035) (Python)
  5. prepare-profiles   : [3d] วิเคราะห์และสังเคราะห์ Character Profiles ผ่านบทพูดจริงด้วย ChatGPT (ChatGPT Bridge)
  6. prepare-matrix     : [3e] สร้างตารางสรรพนามคู่สนทนาและ Demographic Rules สู่ global_pronoun_matrix.json (Python)
  7. prepare-sfx-dic    : [3f] สกัด Onomatopoeia สู่ sfx_glossary.json และศัพท์เฉพาะสู่ dic_glossary.json (Python + LLM)
  8. prepare-table      : [3g] สร้างตารางแปล 10 มิติ (Conversational Triad) พร้อม Game Shielding (Python)
  9. prepare-taxonomy   : [3h] สร้าง taxonomy.json ว่างประจำเกมจากแม่แบบสากล (Python)
 10. prepare-all        : ทางลัดรันเตรียมข้อมูลทั้ง 8 ขั้นตอนต่อเนื่องกันอัตโนมัติ (3a -> 3h)

  การแปล ตรวจสอบ และแพตช์เกม:
 11. translate          : สั่งรันการแปลผ่าน ChatGPT Web Bridge (Unified Plugins + Dialogues)
 12. verify             : ตรวจสอบความถูกต้องและคุณภาพรอบด้าน 8 มิติ (8-Dimension LQA Audit)
 13. plugins            : สกัด (--extract) หรือฉีดคำแปล (--inject) ข้อความ UI ของ plugins.js
 14. export             : ส่งออกไฟล์ CSV แพตช์เกมฉบับสมบูรณ์พร้อมนำไปใช้งานในเกม
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
        description="🚀 Agentic Translation Framework (ATF) - Master Universal CLI (v6.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ตัวอย่างการใช้งาน (Usage Examples):
  python atf.py setup                     # [0] ตั้งค่าพื้นที่ทำงานและไฟล์เริ่มต้น
  python atf.py bridge                    # [1] เปิดเซิร์ฟเวอร์เชื่อมต่อ ChatGPT Web Bridge (อิสระ)
  python atf.py prepare-all               # [2] เตรียมข้อมูลทั้ง 8 ขั้นตอนอัตโนมัติ (3a ถึง 3h)
  python atf.py translate --dry-run       # [3] ทดสอบจำลองการแปลออฟไลน์ 15 แถวแรก
  python atf.py translate                 # [4] รันแปลจริงทั้งปลั๊กอินและบทสนทนาจนจบเรื่อง
  python atf.py verify                    # [5] ตรวจสอบคุณภาพ LQA 8 มิติ (0 Violations Certified)
  python atf.py plugins --inject          # [6] ฉีดคำแปล UI กลับเข้า plugins.js ของเกม
  python atf.py export                    # [7] ส่งออกตารางแปลสำหรับนำไปแพตช์เกมจริง
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="คำสั่งที่ต้องการทำงาน")

    # 0. setup
    subparsers.add_parser("setup", help="ตั้งค่าพื้นที่ทำงาน ค้นหาเกม ไฟล์ต้นฉบับ และกำหนด project_manifest.json")

    # 1. bridge
    subparsers.add_parser("bridge", help="เปิดเซิร์ฟเวอร์ ChatGPT Web Bridge (พอร์ต 5000 - อิสระจาก Pipeline)")

    # 3a. prepare-scenes
    subparsers.add_parser("prepare-scenes", help="[3a] สกัดฉากและชุด Dialogue สู่ scene_packets.json")

    # 3b. prepare-glossary
    subparsers.add_parser("prepare-glossary", help="[3b] สกัดชื่อตัวละคร ไอเทม สถานที่ สกิลจากฐานข้อมูลเกมจริง")

    # 3c. prepare-whitelist
    subparsers.add_parser("prepare-whitelist", help="[3c] คัดกรองตัวละครสำคัญเข้าสู่ character_whitelist.json (ADR-035)")

    # 3d. prepare-profiles
    subparsers.add_parser("prepare-profiles", help="[3d] สังเคราะห์ Character Profiles จากบทพูดจริงด้วย ChatGPT")

    # 3e. prepare-matrix
    subparsers.add_parser("prepare-matrix", help="[3e] สร้างตารางสรรพนามคู่สนทนาและ Demographic Pronoun Matrix")

    # 3f. prepare-sfx-dic
    subparsers.add_parser("prepare-sfx-dic", help="[3f] สกัด Onomatopoeia สู่ sfx_glossary และคำเฉพาะสู่ dic_glossary")

    # 3g. prepare-table
    subparsers.add_parser("prepare-table", help="[3g] สร้างตารางแปล 10 มิติ (Conversational Triad & Game Shielding)")

    # 3h. prepare-taxonomy
    subparsers.add_parser("prepare-taxonomy", help="[3h] สร้าง taxonomy.json สะอาดประจำเกมจากแม่แบบสากล")

    # ทางลัดคำสั่งเตรียมข้อมูลเดิม (Aliases for backwards compatibility)
    subparsers.add_parser("scan", help="[Alias: 3c] สแกนรายชื่อตัวละคร (Character Whitelist)")
    subparsers.add_parser("glossary", help="[Alias: 3b] สกัด Master Glossary จากตัวเกมจริง")
    subparsers.add_parser("packets", help="[Alias: 3a] สกัด Scene Packets")
    subparsers.add_parser("matrix", help="[Alias: 3e] สร้าง Demographic Pronoun Matrix")
    subparsers.add_parser("build-table", help="[Alias: 3g] สร้างตารางแปล 10 มิติ")

    # 10. prepare-all
    subparsers.add_parser("prepare-all", help="เตรียมข้อมูลเกมครบวงจรทั้ง 8 ขั้นตอน (3a -> 3h) อัตโนมัติ")

    # 11. translate
    parser_trans = subparsers.add_parser("translate", help="รันการแปลผ่าน ChatGPT Web Bridge")
    parser_trans.add_argument("--dry-run", action="store_true", help="จำลองการแปลออฟไลน์โดยไม่เรียก Bridge จริง")
    parser_trans.add_argument("--batches", type=int, default=0, help="จำนวน Batch ที่ต้องการรัน (0 = รันจนจบเรื่อง)")
    parser_trans.add_argument("--unified", action="store_true", help="แปล Plugins UI ก่อนแล้วตามด้วยบทสนทนา")
    parser_trans.add_argument("--reset-checkpoint", action="store_true", help="ล้าง Checkpoint เริ่มแปลใหม่ตั้งแต่แถว 0")
    parser_trans.add_argument("--skip-lqa", action="store_true", help="ข้ามการตรวจสอบ LQA อัตโนมัติ")

    # 12. verify
    subparsers.add_parser("verify", help="ตรวจสอบความสมบูรณ์และคุณภาพการแปล 8 มิติ (0 Violations Certified)")

    # 13. plugins
    parser_plugins = subparsers.add_parser("plugins", help="จัดการข้อความ UI ใน plugins.js")
    parser_plugins.add_argument("--extract", action="store_true", help="สกัดข้อความ UI จาก plugins.js ออกสู่ CSV")
    parser_plugins.add_argument("--inject", action="store_true", help="ฉีดคำแปลจาก CSV กลับเข้า plugins.js ของเกม")

    # 14. export
    subparsers.add_parser("export", help="ส่งออกไฟล์ CSV ผลลัพธ์สำหรับแพตช์คืนเกม")

    args, unknown = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmd = args.command

    # --- 0. SETUP ---
    if cmd == "setup":
        print("\n🔧 [ATF] กำลังเปิดเครื่องมือตั้งค่า Workspace & Manifest...")
        sys.exit(run_script("setup_project_paths.py", unknown))

    # --- 1. BRIDGE (INDEPENDENT) ---
    elif cmd == "bridge":
        print("\n🌐 [ATF] กำลังเริ่ม ChatGPT Web Bridge Server (พอร์ต 5000)...")
        print("💡 อย่าลืมเปิดแท็บ https://chatgpt.com และเปิดใช้งาน Tampermonkey Userscript")
        sys.exit(run_script("chatgpt_bridge_server.py", unknown))

    # --- 2. INDIVIDUAL PREPARATION STAGES (3a - 3h) ---
    elif cmd in ["prepare-scenes", "packets"]:
        print("\n🎬 [ATF Stage 3a] กำลังสกัด Scene Packets และวิเคราะห์ Event Flow...")
        sys.exit(run_script("extract_scene_packets.py", unknown))

    elif cmd in ["prepare-glossary", "glossary"]:
        print("\n📖 [ATF Stage 3b] กำลังสกัด Entity Master Glossary จากตัวเกมจริง...")
        sys.exit(run_script("build_master_glossary.py", unknown))

    elif cmd in ["prepare-whitelist", "scan"]:
        print("\n👥 [ATF Stage 3c] กำลังวิเคราะห์และคัดกรอง Character Whitelist (ADR-035)...")
        sys.exit(run_script("build_character_whitelist.py", unknown))

    elif cmd == "prepare-profiles":
        print("\n🧠 [ATF Stage 3d] กำลังวิเคราะห์สังเคราะห์ Character Profiles ด้วย ChatGPT...")
        sys.exit(run_script("analyze_character_profiles.py", unknown))

    elif cmd in ["prepare-matrix", "matrix"]:
        print("\n⚖️ [ATF Stage 3e] กำลังสร้างตารางสรรพนามคู่สนทนาและ Demographic Matrix...")
        sys.exit(run_script("sync_profiles_and_matrix.py", unknown))

    elif cmd == "prepare-sfx-dic":
        print("\n🔊 [ATF Stage 3f] กำลังสกัด Onomatopoeia และคำศัพท์เฉพาะ (SFX & Dic Glossary)...")
        sys.exit(run_script("extract_sfx_and_dic.py", unknown))

    elif cmd in ["prepare-table", "build-table"]:
        print("\n📊 [ATF Stage 3g] กำลังประกอบตาราง 10 มิติ (Conversational Triad & Game Shielding)...")
        sys.exit(run_script("generate_enriched_localization_csv.py", unknown))

    elif cmd == "prepare-taxonomy":
        print("\n🏷️ [ATF Stage 3h] กำลังสร้างไฟล์ Taxonomy เฉพาะสำหรับเกมใหม่...")
        sys.exit(run_script("generate_game_taxonomy.py", unknown))

    # --- 10. PREPARE ALL (THE COMPLETE 8-STAGE AUTOMATION) ---
    elif cmd == "prepare-all":
        print("\n" + "=" * 75)
        print("🚀 [ATF Universal Preparation Pipeline - The 8 Preparation Stages]")
        print("   ระบบจะวิเคราะห์และเตรียมข้อมูลของเกมจริงอัตโนมัติครบ 8 ขั้นตอน (3a ถึง 3h)")
        print("=" * 75)

        stages = [
            ("Stage 3a: สกัดฉากและ Event Flow (extract_scene_packets.py)", "extract_scene_packets.py"),
            ("Stage 3b: สกัด Entity Master Glossary (build_master_glossary.py)", "build_master_glossary.py"),
            ("Stage 3c: คัดกรอง Character Whitelist (build_character_whitelist.py)", "build_character_whitelist.py"),
            ("Stage 3d: วิเคราะห์สังเคราะห์ Profiles ด้วย AI (analyze_character_profiles.py)", "analyze_character_profiles.py"),
            ("Stage 3e: สร้างตารางสรรพนามคู่สนทนา (sync_profiles_and_matrix.py)", "sync_profiles_and_matrix.py"),
            ("Stage 3f: สกัด Onomatopoeia และ Dic Glossary (extract_sfx_and_dic.py)", "extract_sfx_and_dic.py"),
            ("Stage 3g: ประกอบตารางแปล 10 มิติ (generate_enriched_localization_csv.py)", "generate_enriched_localization_csv.py"),
            ("Stage 3h: สร้าง Taxonomy ประจำเกม (generate_game_taxonomy.py)", "generate_game_taxonomy.py"),
        ]

        for desc, script in stages:
            print(f"\n▶️ กำลังทำงาน: {desc}...")
            ret = run_script(script)
            if ret != 0:
                print(f"\n❌ ผิดพลาดในขั้นตอน: {desc} (Exit Code: {ret})")
                sys.exit(ret)

        print("\n" + "=" * 75)
        print("✅ [ATF Preparation Complete] เตรียมข้อมูลทั้ง 8 ขั้นตอนเสร็จสมบูรณ์ 100%!")
        print("💡 คุณสามารถเริ่มรันการแปลได้ทันที:")
        print("   1. หากยังไม่ได้เปิด Bridge ให้เปิด: python atf.py bridge  (ใน Terminal แยก)")
        print("   2. สั่งรันการแปล:                  python atf.py translate")
        print("=" * 75 + "\n")
        sys.exit(0)

    # --- 11. TRANSLATION RUNNER ---
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

    # --- 12. VERIFY ---
    elif cmd == "verify":
        print("\n🛡️ [ATF 8D LQA Engine] กำลังตรวจสอบความสมบูรณ์และคุณภาพการแปล 8 มิติ...")
        sys.exit(run_script("verify_localization_triad.py", unknown))

    # --- 13. PLUGINS ---
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

    # --- 14. EXPORT ---
    elif cmd == "export":
        print("\n📦 [ATF Export] กำลังส่งออกไฟล์ CSV ผลลัพธ์สำหรับแพตช์เกม...")
        sys.exit(run_script("export_final_game_patch_csv.py", unknown))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
