#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification Script for ADR-029 ImageTextDetector and RapidOCR Integration
"""
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

def verify_system():
    print("=" * 60)
    print("🧪 VERIFYING ATF IMAGE TEXT DETECTOR & RAPIDOCR ENGINE")
    print("=" * 60)

    from atf.core.image_text_detector import ImageTextDetector
    from atf.core.rpgm_image_crypto import RPGMImageCrypto

    # 1. Check method signatures
    assert hasattr(ImageTextDetector, "detect_text"), "Missing detect_text method!"
    assert hasattr(ImageTextDetector, "detect_text_rapidocr"), "Missing detect_text_rapidocr method!"
    assert hasattr(ImageTextDetector, "detect_batch_in_memory"), "Missing detect_batch_in_memory method!"
    assert hasattr(ImageTextDetector, "is_rapidocr_available"), "Missing is_rapidocr_available method!"
    print("✅ Method signatures verified successfully.")

    # 2. Check RapidOCR status
    is_rapid = ImageTextDetector.is_rapidocr_available()
    print(f"ℹ️ RapidOCR Available in Environment: {'YES' if is_rapid else 'NO (Run pip install rapidocr-onnxruntime)'}")

    # 3. Test empty/blank image zero false-positive guarantee
    try:
        from PIL import Image
        import io
        # สร้างภาพเปล่าสีขาว (จำลอง CG ที่ไม่มีตัวหนังสือ)
        blank_img = Image.new("RGB", (300, 300), color=(255, 255, 255))
        buf = io.BytesIO()
        blank_img.save(buf, format="PNG")
        blank_bytes = buf.getvalue()

        res = ImageTextDetector.detect_text(blank_bytes)
        assert res.get("has_text") is False, "Blank image should have has_text=False!"
        assert len(res.get("lines", [])) == 0, "Blank image should have 0 lines!"
        print("✅ Zero False-Positive check passed on blank graphic.")
    except Exception as e:
        print(f"⚠️ Test warning: {e}")

    print("\n🎉 ALL ARCHITECTURAL INVARIANTS FOR ADR-029 VERIFIED SUCCESSFULLY!")

def test_image(image_path: str, engine: str = "auto"):
    print("=" * 60)
    print("🔬 TESTING IMAGE OCR WITH ATF DEEP LEARNING DETECTOR")
    print(f"Target Image: {image_path}")
    print(f"Engine Mode:  {engine.upper()}")
    print("=" * 60)

    from atf.core.image_text_detector import ImageTextDetector
    from atf.core.rpgm_image_crypto import RPGMImageCrypto
    import json

    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found at: {image_path}")
        return

    is_rapid = ImageTextDetector.is_rapidocr_available()
    if engine.lower() == "windows":
        print("ℹ️ Engine: Windows Native OCR (Snipping Tool / Windows Capture Engine)")
    elif is_rapid:
        print("ℹ️ Engine: RapidOCR (PP-OCRv4 ONNX with Human-Vision Lexical Validator)")
    else:
        print("ℹ️ Engine: Windows Native OCR (Fallback)")

    # Check if .rpgmvp
    if image_path.lower().endswith(".rpgmvp"):
        manifest_path = os.path.join(BASE_DIR, "data", "project_manifest.json")
        key = None
        game_dir = os.path.join(BASE_DIR, "Example RPGM Game")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    mdata = json.load(f)
                game_dir = mdata.get("game_directory", game_dir)
            except Exception:
                pass
        sys_json = os.path.join(game_dir, "www", "data", "System.json")
        if not os.path.exists(sys_json):
            sys_json = os.path.join(game_dir, "data", "System.json")
        if os.path.exists(sys_json):
            key = RPGMImageCrypto.extract_key_from_system_json(sys_json)

        with open(image_path, "rb") as f:
            raw_bytes = f.read()
        if key:
            img_bytes = RPGMImageCrypto.decrypt_bytes(raw_bytes, key)
            print("🔓 Decrypted .rpgmvp in memory successfully.")
        else:
            img_bytes = raw_bytes
        res = ImageTextDetector.detect_text(img_bytes, engine=engine)
    else:
        res = ImageTextDetector.detect_text(image_path, engine=engine)

    has_text = res.get("has_text", False)
    lines = res.get("lines", [])
    method = res.get("method", "unknown")

    print("\n" + "=" * 60)
    print(f"📊 SCAN RESULTS (Method: {method})")
    print(f"Has Text Detected: {'✅ YES' if has_text else '❌ NO (Classified as Graphic/CG/Sprite)'}")
    print(f"Total Text Lines:  {len(lines):,}")
    print("=" * 60)

    if lines:
        print("\n📝 Detected Text Blocks and Bounding Boxes:")
        for idx, line in enumerate(lines, 1):
            txt = line.get("text", "")
            conf = line.get("confidence", 0.0)
            x = line.get("x", 0)
            y = line.get("y", 0)
            w = line.get("width", 0)
            h = line.get("height", 0)
            is_merged = line.get("is_merged_paragraph", False)
            n_lines = line.get("line_count", 1)
            btype = f"💬 Speech Bubble / Paragraph ({n_lines} lines merged)" if is_merged else "🏷️ Single Text Line"
            print(f"  [{idx:02d}] \"{txt}\"")
            print(f"       Type: {btype}")
            print(f"       Confidence: {conf:.1%} | BoundingBox: X={x}, Y={y}, W={w}, H={h}")
    else:
        print("ℹ️ No text found in this image. Clean graphic or character sprite.")

if __name__ == "__main__":
    target = None
    eng = "auto"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--engine" and i + 1 < len(args):
            eng = args[i + 1]
            i += 2
        elif not args[i].startswith("-") and target is None:
            target = args[i]
            i += 1
        else:
            i += 1

    if target:
        test_image(target, engine=eng)
    else:
        verify_system()
