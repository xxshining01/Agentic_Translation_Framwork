"""
Run Character Re-analysis & Calibration Pipeline
Architecture: SAD-010 | Design: SDD-010, SDD-011 | Rules: AGENTS.md

หน้าที่:
1. ทำสำรองข้อมูล (Backup) โฟลเดอร์ data/tlas/profiles ไว้อย่างปลอดภัยก่อนแก้ไข
2. สั่งรัน TLASConsensusEngine ด้วยอัลกอริทึม Name Semantic Lexicon & Sentence Disambiguation
3. สร้าง V4 Character Profiles ใหม่ทั้ง 442 ไฟล์ พร้อมบันทึก global_pronoun_matrix.json
4. สั่งรัน audit_character_profiles.py ทันทีเพื่อเปรียบเทียบผลลัพธ์ Before vs After
"""

import os
import sys
import shutil
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.atf.tools.tlas_consensus_engine import TLASConsensusEngine
from src.atf.tools.audit_character_profiles import audit_profiles

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    tlas_data = os.path.join(project_root, "data", "tlas")
    profiles_dir = os.path.join(tlas_data, "profiles")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(tlas_data, f"profiles_backup_{timestamp}")

    print("="*65)
    print("=== ATF TLAS CHARACTER RE-ANALYSIS & CALIBRATION PIPELINE ===")
    print("="*65)

    # 1. Backup existing profiles
    if os.path.exists(profiles_dir):
        print(f"[*] Step 1: Creating safety backup of current profiles to:\n    -> {backup_dir}")
        shutil.copytree(profiles_dir, backup_dir)
        print("[+] Backup created successfully.")
    else:
        print("[!] Profiles directory not found, skipping backup.")

    # 2. Run Consensus Engine
    print("\n[*] Step 2: Running Refactored TLASConsensusEngine (Pure Python, 0 Token Cost)...")
    engine = TLASConsensusEngine(data_dir=tlas_data)
    engine.run()
    print("[+] Consensus Engine completed successfully.")

    # 3. Re-run Audit to verify improvements
    print("\n[*] Step 3: Running Verification Audit on Newly Generated Profiles...")
    audit_profiles()

    print("\n" + "="*65)
    print("=== PIPELINE EXECUTION FINISHED SUCCESSFULLY ===")
    print("="*65)

if __name__ == "__main__":
    main()
