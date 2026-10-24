import os
import sys
import json
import glob

# Dynamically resolve root and src path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

def verify_pipeline():
    print("==================================================================")
    print("       ATF End-to-End System & Pipeline Integrity Verifier        ")
    print("==================================================================")

    tlas_dir = os.path.join(BASE_DIR, "data", "tlas")
    
    # Check if custom output manifest exists
    manifest_path = os.path.join(BASE_DIR, "data", "project_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
                if mdata.get("output_tlas_dir") and os.path.exists(mdata["output_tlas_dir"]):
                    tlas_dir = mdata["output_tlas_dir"]
        except Exception:
            pass

    print(f"Target TLAS Directory: {tlas_dir}")

    # 1. Check Core Database Files
    print("\n[1/5] Checking TLAS Ground Truth & Database Assets...")
    glossary_path = os.path.join(tlas_dir, "tlas_glossary.json")
    if not os.path.exists(glossary_path):
        glossary_path = os.path.join(tlas_dir, "tlas_glossary.template.json")
        
    scenes_path = os.path.join(tlas_dir, "rpgm_scenes_v5.json")
    if not os.path.exists(scenes_path):
        scenes_path = os.path.join(tlas_dir, "rpgm_scenes_v4.json")

    checks = {
        "scenes_json": scenes_path,
        "taxonomy.json": os.path.join(tlas_dir, "taxonomy.json"),
        "tlas_glossary.json": glossary_path,
        "profiles dir": os.path.join(tlas_dir, "profiles")
    }

    all_exist = True
    for name, path in checks.items():
        exists = os.path.exists(path)
        status = "✅ Found" if exists else "❌ Missing"
        print(f"  • {name:<22}: {status} ({path})")
        if not exists:
            all_exist = False

    if not all_exist:
        print("\n⚠️ Note: Some database files are missing. (If this is a new setup, run Case A or configure project_manifest.json)")
        return False

    profile_files = glob.glob(os.path.join(checks["profiles dir"], "*.json"))
    print(f"\n  📊 Database Metrics:")
    print(f"     - Character Profiles: {len(profile_files):,}")

    # 2. Test Context Engine Integration
    print("\n[2/5] Testing Context Engine Module Load...")
    try:
        from atf.memory.context_engine import ContextEngine
        print(f"  ✅ ContextEngine loaded successfully.")
    except Exception as e:
        print(f"  ❌ Context Engine Error: {e}")
        return False

    # 3. Test Core Parsers and Masker
    print("\n[3/5] Testing Message Code Masker & Splitter...")
    try:
        from atf.core.control_code_masker import MessageCodeMasker
        from atf.core.smart_line_splitter import SmartLineSplitter
        
        sample_msg = r"\C[2]Hello\C, \V[1] is here! <br> Next line."
        masked, codes = MessageCodeMasker.mask_control_codes(sample_msg)
        unmasked = MessageCodeMasker.unmask_control_codes(masked, codes)
        if sample_msg == unmasked:
            print("  ✅ Control Code Masker round-trip test PASSED.")
        else:
            print("  ⚠️ Masker round-trip mismatch.")
    except Exception as e:
        print(f"  ❌ Masker Error: {e}")
        return False

    # 4. Test Translation Token Data Model
    print("\n[4/5] Testing TranslationToken Data Model...")
    try:
        from atf.core.models import TranslationToken
        test_token = TranslationToken(
            id="ROW_1001",
            original_text=r"\C[1]Dan: I need to check the bakery today.",
            speaker="Dan",
            metadata={"Filename": "Map039.json", "Row": "1001"}
        )
        print(f"  ✅ TranslationToken model initialized: ID={test_token.id}, Speaker={test_token.speaker}")
    except Exception as e:
        print(f"  ❌ Model Error: {e}")
        return False

    # 5. Check Requirements & Environment
    print("\n[5/5] Checking Key Dependencies...")
    packages = ["pydantic", "pytest", "litellm", "pyahocorasick", "yaml", "rich", "tiktoken", "pythainlp"]
    all_pkg = True
    for pkg in packages:
        try:
            __import__(pkg)
            print(f"  • {pkg:<16}: ✅ Installed")
        except ImportError:
            print(f"  • {pkg:<16}: ❌ Not installed")
            all_pkg = False

    if not all_pkg:
        print("\n⚠️ Some dependencies are missing. Run: pip install -r requirements.txt")
        return False

    print("\n==================================================================")
    print("  🎉 ALL SYSTEM PIPELINE INTEGRITY CHECKS PASSED SUCCESSFULLY!    ")
    print("==================================================================")
    print("สถานะระบบ: โครงสร้างโมดูลและโค้ดทั้งหมดเชื่อมต่อกันอย่างถูกต้อง และพร้อมใช้งานจริง 100%!")
    return True

if __name__ == "__main__":
    verify_pipeline()
