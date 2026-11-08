#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Image & Phone Chat Localization Engine (ADR-024, ADR-026 & ADR-027 Compliant)
ระบบประมวลผลการแปลข้อความในภาพและแชตมือถือสำหรับ RPG Maker:
1. Decrypt: ถอดรหัส .rpgmvp เป็น .png ลง Target Output Workspace (ADR-024)
2. Catalog/Extract: สกัดพิกัดกล่องข้อความและข้อความต้นฉบับจริงสู่ CSV (Real Dialogues)
3. Translate: แปลข้อความผ่าน ATF Engine คุมสรรพนามและบริบทตัวละคร
4. Render: ลบตัวหนังสือเดิมในกรอบ และวาดตัวหนังสือภาษาไทยด้วยฟอนต์คมชัดและการตัดคำไวยากรณ์ไทย
5. Encrypt: เข้ารหัสภาพ .png ภาษาไทยกลับเป็น .rpgmvp พร้อมนำเข้าเกมจริง
"""

import os
import sys
import re
import csv
import json
import glob
import time
import shutil
import argparse
import tempfile
from typing import List, Dict, Tuple, Optional, Any, Set

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from atf.core.rpgm_image_crypto import RPGMImageCrypto
from atf.core.image_text_detector import ImageTextDetector

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from pythainlp.tokenize import word_tokenize
    HAS_PYTHAINLP = True
except ImportError:
    HAS_PYTHAINLP = False


CSV_HEADER = [
    "Image_Filename", "Box_Index", "X", "Y", "Width", "Height",
    "Original_Text", "Thai_Text", "Speaker", "Role",
    "Text_Color", "Bg_Color", "Font_Size",
    "Stroke_Width", "Stroke_Color", "Alignment"
]


def safe_write_csv(file_path: str, fieldnames: List[str], rows: List[Dict[str, Any]], max_retries: int = 3) -> str:
    """
    บันทึกไฟล์ CSV อย่างปลอดภัยบน Windows (Resilient to Microsoft Excel File Locks):
    1. ป้องกันปัญหา PermissionError: [Errno 13] เมื่อผู้ใช้เปิดไฟล์ดูใน Microsoft Excel / WPS Office
    2. ทำการ Retry หน่วงเวลารอให้ผู้ใช้ปิดไฟล์
    3. หากยังล็อกอยู่ จะเขียนลงไฟล์สำรอง _updated.csv อัตโนมัติ เพื่อไม่ให้คำแปลหรือข้อมูลสูญหายเด็ดขาด
    """
    target_path = os.path.abspath(file_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    for attempt in range(max_retries):
        try:
            with open(target_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            return target_path
        except PermissionError:
            fname = os.path.basename(target_path)
            if attempt < max_retries - 1:
                print(f"⚠️ คำเตือน: ไฟล์ '{fname}' กำลังถูกเปิดใช้งานอยู่ (เช่น ใน Microsoft Excel หรือ WPS Office)")
                print(f"   ⏳ กรุณาปิดไฟล์ '{fname}' ใน Excel... ระบบกำลังลองใหม่ใน 2 วินาที (ครั้งที่ {attempt + 1}/{max_retries})")
                time.sleep(2)
            else:
                fallback_path = os.path.splitext(target_path)[0] + "_updated.csv"
                try:
                    with open(fallback_path, "w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    print(f"⚠️ แจ้งเตือน: ไม่สามารถบันทึกทับ '{fname}' ได้โดยตรงเนื่องจากโปรแกรม Excel ล็อกไฟล์ไว้")
                    print(f"   💾 ระบบได้บันทึกข้อมูลล่าสุดทั้งหมดลงใน: {os.path.basename(fallback_path)} เรียบร้อยแล้ว")
                    print(f"   👉 กรุณาปิดโปรแกรม Excel แล้วเปลี่ยนชื่อไฟล์กลับ หรือรันคำสั่งใหม่อีกครั้ง")
                    return fallback_path
                except Exception as ex:
                    print(f"❌ ไม่สามารถเขียนไฟล์สำรองได้: {ex}")
                    raise


def safe_copy_file(src: str, dst: str):
    """คัดลอกไฟล์อย่างปลอดภัยโดยไม่แครชหากไฟล์ปลายทางถูกล็อกใน Excel"""
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.copy2(src, dst)
    except PermissionError:
        print(f"⚠️ Note: Project copy '{os.path.basename(dst)}' is open in another program and could not be synced.")
    except Exception:
        pass


def resolve_workspace_paths(folder: str = "pictures", game_dir_override: Optional[str] = None) -> Dict[str, Any]:
    """
    อ่านการตั้งค่าจาก data/project_manifest.json ตามมาตรฐาน ADR-024 (Target Workspace Isolation)
    หากมีการระบุ output_dir จะใช้ output_dir ของแพตช์เป็นโฟลเดอร์หลักเสมอ
    รองรับการระบุโฟลเดอร์รูปภาพในเกม เช่น pictures, system, titles1, SumRndmDde ฯลฯ
    """
    manifest_path = os.path.join(BASE_DIR, "data", "project_manifest.json")
    game_dir = game_dir_override if game_dir_override else os.path.join(BASE_DIR, "Example RPGM Game")
    output_dir = os.path.join(BASE_DIR, "data")
    key = None

    if not game_dir_override and os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                mdata = json.load(f)
            if mdata.get("game_directory") and os.path.exists(mdata["game_directory"]):
                game_dir = mdata["game_directory"]
            if mdata.get("output_dir"):
                output_dir = mdata["output_dir"]
        except Exception:
            pass

    sys_json = os.path.join(game_dir, "www", "data", "System.json")
    if not os.path.exists(sys_json):
        sys_json = os.path.join(game_dir, "data", "System.json")

    if os.path.exists(sys_json):
        key = RPGMImageCrypto.extract_key_from_system_json(sys_json)

    # ตรวจสอบโฟลเดอร์ภาพที่ต้องการในตัวเกม
    target_img_dir = os.path.join(game_dir, "www", "img", folder)
    if not os.path.exists(target_img_dir):
        target_img_dir = os.path.join(game_dir, "img", folder)
    if not os.path.exists(target_img_dir):
        target_img_dir = os.path.join(game_dir, "www", "img", "pictures")

    # กำหนด Workspace ย่อยภายใน output_dir (ADR-024)
    images_base = os.path.join(output_dir, "images")
    raw_dir = os.path.join(images_base, "raw")
    catalog_csv = os.path.join(images_base, "image_dialogues.csv")
    rendered_dir = os.path.join(images_base, "translated")

    # สร้างโฟลเดอร์เสมอทั้งใน Target Workspace และ Project Repository
    os.makedirs(images_base, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)
    proj_images = os.path.join(BASE_DIR, "data", "images")
    os.makedirs(proj_images, exist_ok=True)
    os.makedirs(os.path.join(proj_images, "raw"), exist_ok=True)

    return {
        "game_dir": game_dir,
        "pictures_dir": target_img_dir,
        "folder": folder,
        "output_dir": output_dir,
        "images_base": images_base,
        "raw_dir": raw_dir,
        "catalog_csv": catalog_csv,
        "rendered_dir": rendered_dir,
        "key": key
    }


def load_ocr_corrections() -> Dict[str, str]:
    """โหลดพจนานุกรมการแก้ไขคำผิด OCR (ADR-032)"""
    corr: Dict[str, str] = {}
    paths = resolve_workspace_paths()
    candidates = [
        os.path.join(paths["images_base"], "ocr_corrections.json"),
        os.path.join(BASE_DIR, "data", "images", "ocr_corrections.json"),
    ]
    for cpath in candidates:
        if os.path.exists(cpath):
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    exact = data.get("exact_replacements", {})
                    if isinstance(exact, dict):
                        corr.update(exact)
                    for k, v in data.items():
                        if isinstance(v, str):
                            corr[k] = v
                break
            except Exception:
                pass
    return corr


def save_ocr_corrections(new_rules: Dict[str, str]):
    """บันทึกกฎการแก้ไขคำผิด OCR ลงไฟล์ JSON อย่างถาวร (Persistent Rule Store)"""
    if not new_rules:
        return
    paths = resolve_workspace_paths()
    corr = load_ocr_corrections()
    corr.update(new_rules)
    data = {
        "exact_replacements": corr,
        "patterns": [
            ["([,.!?:;])([A-Za-z])", "\\1 \\2"]
        ]
    }
    target_path = os.path.join(paths["images_base"], "ocr_corrections.json")
    proj_path = os.path.join(BASE_DIR, "data", "images", "ocr_corrections.json")
    for p in (target_path, proj_path):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def get_thai_font(size: int = 18, custom_font_name: Optional[str] = None) -> Any:
    """
    ค้นหาฟอนต์ภาษาไทยคุณภาพสูง:
    1. ตรวจสอบโฟลเดอร์ fonts/ หรือ data/fonts/ ในโปรเจกต์ก่อน (สำหรับฟอนต์พิเศษ เช่น Kanit, Prompt, Sarabun)
    2. ค้นหาฟอนต์มาตรฐานใน Windows (Tahoma, Leelawadee, Arial)
    """
    if not HAS_PIL:
        return None

    # 1. ตรวจสอบฟอนต์เฉพาะในโฟลเดอร์ fonts ของโปรเจกต์
    local_font_dirs = [
        os.path.join(BASE_DIR, "fonts"),
        os.path.join(BASE_DIR, "data", "fonts")
    ]
    if custom_font_name:
        for fdir in local_font_dirs:
            fp = os.path.join(fdir, custom_font_name)
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size=size)
                except Exception:
                    pass

    for fdir in local_font_dirs:
        if os.path.exists(fdir):
            for fp in glob.glob(os.path.join(fdir, "*.ttf")):
                try:
                    return ImageFont.truetype(fp, size=size)
                except Exception:
                    pass

    # 2. ตรวจสอบฟอนต์ไทยมาตรฐานประจำระบบปฏิบัติการ Windows
    font_candidates = [
        "C:\\Windows\\Fonts\\tahoma.ttf",
        "C:\\Windows\\Fonts\\leelawad.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\seguiemj.ttf"
    ]
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                pass

    return ImageFont.load_default()


def get_windows_thai_font(size: int = 18) -> Any:
    """Wrapper เพื่อความเข้ากันได้ย้อนหลัง"""
    return get_thai_font(size=size)


def wrap_thai_text(text: str, max_chars_per_line: int = 28) -> str:
    """ตัดคำภาษาไทยให้อยู่ในกรอบอย่างสวยงามโดยไม่ตัดกลางคำ (อิงจำนวนตัวอักษร)"""
    if not text:
        return ""
    if not HAS_PYTHAINLP:
        return text

    words = word_tokenize(text, engine="newmm")
    lines = []
    current_line = []
    current_len = 0

    for w in words:
        if w == "\n":
            lines.append("".join(current_line))
            current_line = []
            current_len = 0
            continue

        if current_len + len(w) > max_chars_per_line and current_line:
            lines.append("".join(current_line))
            current_line = [w]
            current_len = len(w)
        else:
            current_line.append(w)
            current_len += len(w)

    if current_line:
        lines.append("".join(current_line))

    return "\n".join(lines)


def wrap_thai_text_by_pixel(text: str, font: Any, max_pixel_width: int, draw: Any) -> str:
    """
    ตัดคำภาษาไทยตามความกว้างพิกเซลจริง (Pixel-Accurate Thai Text Wrapping)
    ใช้ความกว้างจริงของฟอนต์บนหน้าจอ ทำให้ข้อความขยายเต็มความกว้างของกล่องข้อความอย่างเป็นธรรมชาติ
    """
    if not text:
        return ""
    if not HAS_PYTHAINLP:
        return text

    words = word_tokenize(text, engine="newmm")
    lines = []
    current_line = []

    for w in words:
        if w == "\n":
            lines.append("".join(current_line))
            current_line = []
            continue

        test_line = "".join(current_line + [w])
        try:
            line_w = draw.textlength(test_line, font=font)
        except Exception:
            line_w = len(test_line) * (font.size * 0.6 if hasattr(font, "size") else 8)

        if line_w > max_pixel_width and current_line:
            lines.append("".join(current_line))
            current_line = [w]
        else:
            current_line.append(w)

    if current_line:
        lines.append("".join(current_line))

    return "\n".join(lines)


def auto_detect_box_colors(
    im: Any,
    x: int, y: int, w: int, h: int,
    csv_bg: Optional[str] = None,
    csv_text: Optional[str] = None
) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int], Optional[Tuple[int, int, int, int]], int]:
    """
    วิเคราะห์สีพื้นหลังและสีตัวอักษรจริงจากภาพ (Pixel-Level Adaptive Inpainting & Typography Harmony - ADR-033):
    1. ตรวจสอบพิกเซลรอบนอก (Perimeter Pixels) ของกล่องข้อความเพื่อระบุสีพื้นหลังแท้จริง
    2. หากสีพื้นหลังรอบกล่องเป็นสีมืด (เช่น #000000 ในหน้าจอ Tutorial/UI) จะสลับเป็นสีพื้นหลังจริง ป้องกันการเทสี่เหลี่ยมขาวทับภาพมืด 100%
    3. คำนวณความเปรียบต่าง (Luminance Contrast) เพื่อเลือกสีตัวอักษรให้อ่านง่าย คมชัด และกลมกลืนกับงานศิลป์
    4. คำนวณ Stroke/Outline อัตโนมัติเพื่อให้อักษรอ่านชัดเจนในทุกฉากหลัง
    """
    if not HAS_PIL or not hasattr(im, "size"):
        return (255, 255, 255, 255), (40, 40, 40, 255), None, 0

    img_w, img_h = im.size
    bx1 = max(0, min(x, img_w - 1))
    by1 = max(0, min(y, img_h - 1))
    bx2 = max(bx1 + 1, min(x + w, img_w))
    by2 = max(by1 + 1, min(y + h, img_h))

    # 1. สุ่มตัวอย่างพิกเซลขอบนอก (Perimeter Pixels)
    sample_points = []
    step_x = max(1, (bx2 - bx1) // 12)
    step_y = max(1, (by2 - by1) // 8)

    for px in range(bx1, bx2, step_x):
        if by1 >= 4:
            sample_points.append(im.getpixel((px, by1 - 3)))
        if by2 < img_h - 4:
            sample_points.append(im.getpixel((px, by2 + 2)))

    for py in range(by1, by2, step_y):
        if bx1 >= 4:
            sample_points.append(im.getpixel((bx1 - 3, py)))
        if bx2 < img_w - 4:
            sample_points.append(im.getpixel((bx2 + 2, py)))

    rgba_samples = []
    for sp in sample_points:
        if isinstance(sp, int):
            rgba_samples.append((sp, sp, sp, 255))
        elif len(sp) == 3:
            rgba_samples.append((sp[0], sp[1], sp[2], 255))
        elif len(sp) >= 4:
            rgba_samples.append((sp[0], sp[1], sp[2], sp[3]))

    # คำนวณสีพื้นหลังที่แท้จริงจาก Perimeter (รองรับทั้ง Alpha/Transparency และ Opaque Colors)
    if rgba_samples:
        quantized = {}
        for r, g, b, a in rgba_samples:
            k = (0, 0, 0, 0) if a < 30 else (r // 24 * 24, g // 24 * 24, b // 24 * 24, 255)
            quantized[k] = quantized.get(k, 0) + 1
        most_common_q = max(quantized.items(), key=lambda it: it[1])[0]
        matching = [sp for sp in rgba_samples if ((0, 0, 0, 0) if sp[3] < 30 else (sp[0]//24*24, sp[1]//24*24, sp[2]//24*24, 255)) == most_common_q]
        avg_a = sum(s[3] for s in matching) // len(matching)
        if avg_a < 30:
            detected_bg = (0, 0, 0, 0)
        else:
            avg_r = sum(s[0] for s in matching) // len(matching)
            avg_g = sum(s[1] for s in matching) // len(matching)
            avg_b = sum(s[2] for s in matching) // len(matching)
            detected_bg = (avg_r, avg_g, avg_b, 255)
    else:
        detected_bg = (247, 247, 247, 255)

    bg_lum = 0.299 * detected_bg[0] + 0.587 * detected_bg[1] + 0.114 * detected_bg[2]

    # ตรวจสอบสีพื้นหลังที่กำหนดใน CSV
    final_bg = detected_bg
    if csv_bg and csv_bg.lower() in ("transparent", "clear", "alpha"):
        final_bg = (0, 0, 0, 0)
    elif csv_bg and csv_bg.lower() not in ("#ffffff", "white", "#f7f7f7", "default", "", "none"):
        try:
            from PIL import ImageColor
            final_bg = ImageColor.getcolor(csv_bg, "RGBA")
        except Exception:
            final_bg = detected_bg
    else:
        # หากใน CSV เป็นสีขาว แต่ภาพจริงเป็นสีมืด (เช่น พื้นหลังเกมสีดำสนิท) ให้ใช้สีมืดจริง
        if detected_bg[3] == 0:
            final_bg = (0, 0, 0, 0)
        elif bg_lum < 110:
            final_bg = detected_bg
        elif csv_bg and csv_bg.lower() == "#f7f7f7":
            final_bg = (247, 247, 247, 255)
        else:
            final_bg = detected_bg

    # คำนวณสีตัวหนังสือ (Text Color) และ Stroke ตามสีพื้นหลัง
    if bg_lum < 115:
        final_text = (255, 255, 255, 255)
        stroke_color = (0, 0, 0, 240)
        stroke_width = 1
    else:
        final_text = (40, 40, 40, 255)
        stroke_color = None
        stroke_width = 0

    if csv_text and csv_text.lower() not in ("#000000", "black", "default", ""):
        try:
            from PIL import ImageColor
            final_text = ImageColor.getcolor(csv_text, "RGBA")
        except Exception:
            pass

    return final_bg, final_text, stroke_color, stroke_width


def fit_thai_text_to_box(
    text: str,
    avail_w: int,
    avail_h: int,
    desired_font_size: int = 18,
    min_font_size: int = 10,
    draw: Any = None
) -> Tuple[Any, str, int]:
    """
    คำนวณและปรับลดขนาดฟอนต์แบบ Adaptive เพื่อให้ข้อความภาษาไทยพอดีกับความกว้างและความสูงของกล่องข้อความ 100% (ADR-033)
    ไม่มีการล้นกรอบ ไม่ทะลักไปทับ UI หรือลูกศรอื่น
    """
    if not text:
        return get_thai_font(desired_font_size), "", desired_font_size

    # ปรับขนาดฟอนต์เริ่มต้นให้สัมพันธ์กับขนาดกล่อง
    max_allowable_size = desired_font_size
    if avail_h <= 35:
        max_allowable_size = min(desired_font_size, 14)
    elif avail_h <= 55:
        max_allowable_size = min(desired_font_size, 16)

    best_font = get_thai_font(max_allowable_size)
    best_wrapped = text
    best_size = max_allowable_size

    for cur_size in range(max_allowable_size, min_font_size - 1, -1):
        cur_font = get_thai_font(size=cur_size)
        wrapped = wrap_thai_text_by_pixel(text, font=cur_font, max_pixel_width=avail_w, draw=draw)
        lines = [ln for ln in wrapped.split("\n") if ln.strip()]

        line_height = int(cur_size * 1.25)
        total_text_h = len(lines) * line_height

        max_line_w = 0
        for ln in lines:
            try:
                lw = draw.textlength(ln, font=cur_font) if draw else len(ln) * cur_size * 0.6
            except Exception:
                lw = len(ln) * cur_size * 0.6
            if lw > max_line_w:
                max_line_w = lw

        if total_text_h <= avail_h and max_line_w <= avail_w + 4:
            return cur_font, wrapped, cur_size

        best_font = cur_font
        best_wrapped = wrapped
        best_size = cur_size

    return best_font, best_wrapped, best_size


# ==============================================================================
# GROUND TRUTH CATALOG DEFINITION (Real Phone Dialogue Sentences & Coordinates)
# ==============================================================================

def get_ground_truth_catalog_entries(with_translations: bool = False) -> List[Dict[str, str]]:
    """
    พจนานุกรมบทสนทนาจริงและพิกัดกล่องแชตโทรศัพท์มือถือของ Masaru และ Shion
    (ถอดข้อความตรงตามภาพต้นฉบับ 100% โดยค่าเริ่มต้นจะปล่อย Thai_Text ว่างไว้เพื่อเริ่มการแปลจริง)
    """
    entries = []

    # 1. RVPhoneMasaru1
    entries.append({
        "Image_Filename": "RVPhoneMasaru1.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "90",
        "Original_Text": "Ah Dan..good evening...I did try to tell Ms.Shion about you having to see to something but she's a good girl so.. 21:00",
        "Thai_Text": "อ่า แดน.. สวัสดีตอนเย็นนะ... ลุงพยายามบอกคุณชิออนแล้วว่าเธอต้องไปจัดการธุระ แต่เธอเป็นเด็กดีน่ะสิ.. 21:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })

    # 2. RVPhoneMasaru2
    entries.append({
        "Image_Filename": "RVPhoneMasaru2.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "90",
        "Original_Text": "Ah Dan..good evening...I did try to tell Ms.Shion about you having to see to something but she's a good girl so.. 21:00",
        "Thai_Text": "อ่า แดน.. สวัสดีตอนเย็นนะ... ลุงพยายามบอกคุณชิออนแล้วว่าเธอต้องไปจัดการธุระ แต่เธอเป็นเด็กดีน่ะสิ.. 21:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru2.png", "Box_Index": "2",
        "X": "412", "Y": "260", "Width": "207", "Height": "90",
        "Original_Text": "She can be pretty stubborn, haha..but don't worry, I'll be there for her and I'll watch after her. 21:01",
        "Thai_Text": "เธอก็ดื้อพอตัวเลยล่ะ ฮ่าฮ่า.. แต่ไม่ต้องห่วงนะ ลุงจะคอยอยู่เป็นเพื่อนและดูแลเธอให้เอง 21:01",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })

    # 3. RVPhoneMasaru3
    entries.append({
        "Image_Filename": "RVPhoneMasaru3.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "90",
        "Original_Text": "Ah Dan..good evening...I did try to tell Ms.Shion about you having to see to something but she's a good girl so.. 21:00",
        "Thai_Text": "อ่า แดน.. สวัสดีตอนเย็นนะ... ลุงพยายามบอกคุณชิออนแล้วว่าเธอต้องไปจัดการธุระ แต่เธอเป็นเด็กดีน่ะสิ.. 21:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru3.png", "Box_Index": "2",
        "X": "412", "Y": "260", "Width": "207", "Height": "90",
        "Original_Text": "She can be pretty stubborn, haha..but don't worry, I'll be there for her and I'll watch after her. 21:01",
        "Thai_Text": "เธอก็ดื้อพอตัวเลยล่ะ ฮ่าฮ่า.. แต่ไม่ต้องห่วงนะ ลุงจะคอยอยู่เป็นเพื่อนและดูแลเธอให้เอง 21:01",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru3.png", "Box_Index": "3",
        "X": "412", "Y": "370", "Width": "207", "Height": "115",
        "Original_Text": "Oh yes, why don't I send you the photo from today? As your uncle figure and as a man myself, I understand you'll want to see the hardworking side of your loved one. 21:12",
        "Thai_Text": "โอ้ ใช่แล้ว ทำไมลุงไม่ส่งรูปวันนี้ให้เธอดูล่ะ? ในฐานะลุงและลูกผู้ชายด้วยกัน ลุงเข้าใจดีว่าเธอคงอยากเห็นด้านที่ขยันของคนรักสินะ 21:12",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 4-6: RVPhoneMasaru4 (Empty), RVPhoneMasaru5 (Photo), RVPhoneMasaru6 (Photo+Emoji) -> No text boxes

    # 7. RVPhoneMasaru7
    entries.append({
        "Image_Filename": "RVPhoneMasaru7.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "90",
        "Original_Text": "A-As you can see, Ms.Shion doesn't seem to liked having this photo taken....or like me at all recently..... 21:12",
        "Thai_Text": "ย-อย่างที่เธอเห็นนั่นแหละ คุณชิออนดูไม่ค่อยชอบที่ถูกถ่ายรูปนี้เท่าไหร่... หรือไม่ก็ไม่ชอบลุงเลยช่วงนี้..... 21:12",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })

    # 8. RVPhoneMasaru8
    entries.append({
        "Image_Filename": "RVPhoneMasaru8.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "90",
        "Original_Text": "A-As you can see, Ms.Shion doesn't seem to liked having this photo taken....or like me at all recently..... 21:12",
        "Thai_Text": "ย-อย่างที่เธอเห็นนั่นแหละ คุณชิออนดูไม่ค่อยชอบที่ถูกถ่ายรูปนี้เท่าไหร่... หรือไม่ก็ไม่ชอบลุงเลยช่วงนี้..... 21:12",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru8.png", "Box_Index": "2",
        "X": "412", "Y": "260", "Width": "207", "Height": "115",
        "Original_Text": "But this isn't about me...haha...I wanted to show you her hardworking side even when you're busy. Although her angry side seems to be showing more.. 21:21",
        "Thai_Text": "แต่นี่ไม่ใช่เรื่องของลุงหรอก... ฮ่าฮ่า... ลุงแค่อยากให้เธอเห็นด้านที่ขยันของเธอแม้ตอนที่เธอยุ่ง ถึงด้านโกรธๆ จะโผล่มามากกว่าก็เถอะ.. 21:21",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 10. RVPhoneMasaru10
    entries.append({
        "Image_Filename": "RVPhoneMasaru10.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "125",
        "Original_Text": "Ahh! I can explain this, ah, this relic isn't so good with smartphones so...I made a mistake of taking this photo when I was zooming in too much 21:32",
        "Thai_Text": "อ๊า! ลุงอธิบายได้นะ คือคนแก่อย่างลุงไม่ค่อยถนัดใช้สมาร์ตโฟนน่ะ... ลุงเผลอถ่ายรูปนี้ตอนที่ซูมเข้าไปใกล้เกินไป 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 11. RVPhoneMasaru11
    entries.append({
        "Image_Filename": "RVPhoneMasaru11.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "125",
        "Original_Text": "Ahh! I can explain this, ah, this relic isn't so good with smartphones so...I made a mistake of taking this photo when I was zooming in too much 21:32",
        "Thai_Text": "อ๊า! ลุงอธิบายได้นะ คือคนแก่อย่างลุงไม่ค่อยถนัดใช้สมาร์ตโฟนน่ะ... ลุงเผลอถ่ายรูปนี้ตอนที่ซูมเข้าไปใกล้เกินไป 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru11.png", "Box_Index": "2",
        "X": "422", "Y": "270", "Width": "208", "Height": "80",
        "Original_Text": "I simply thought it would be a waste to delete it so I sent it to you, Dan... 21:32",
        "Thai_Text": "ลุงแค่คิดว่าถ้าลบทิ้งไปมันคงเสียดายแย่ ก็เลยส่งมาให้เธอน่ะ แดน... 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })

    # 12. RVPhoneMasaru12
    entries.append({
        "Image_Filename": "RVPhoneMasaru12.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "125",
        "Original_Text": "Ahh! I can explain this, ah, this relic isn't so good with smartphones so...I made a mistake of taking this photo when I was zooming in too much 21:32",
        "Thai_Text": "อ๊า! ลุงอธิบายได้นะ คือคนแก่อย่างลุงไม่ค่อยถนัดใช้สมาร์ตโฟนน่ะ... ลุงเผลอถ่ายรูปนี้ตอนที่ซูมเข้าไปใกล้เกินไป 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru12.png", "Box_Index": "2",
        "X": "422", "Y": "270", "Width": "208", "Height": "80",
        "Original_Text": "I simply thought it would be a waste to delete it so I sent it to you, Dan... 21:32",
        "Thai_Text": "ลุงแค่คิดว่าถ้าลบทิ้งไปมันคงเสียดายแย่ ก็เลยส่งมาให้เธอน่ะ แดน... 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru12.png", "Box_Index": "3",
        "X": "422", "Y": "360", "Width": "208", "Height": "120",
        "Original_Text": "Maybe it was a bad idea..hahaha...d-don't worry, I'll delete it, its only meant for your eyes, Dan... I only see Ms.Shion as my daughter and you my son. 21:32",
        "Thai_Text": "บางทีอาจเป็นความคิดที่ไม่ดีเท่าไหร่.. ฮ่าฮ่าฮ่า... ม-ไม่ต้องห่วงนะ ลุงจะลบมันทิ้ง มีแค่เธอที่ได้เห็นเท่านั้นแหละ แดน... ลุงมองคุณชิออนเหมือนลูกสาว และมองเธอเหมือนลูกชายนะ 21:32",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })

    # 13. RVPhoneMasaru13
    entries.append({
        "Image_Filename": "RVPhoneMasaru13.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "110",
        "Original_Text": "A-Anyway, as both you youngins father figure, I'll make sure to keep watch over Ms.Shion for you tonight and send her home safetly 22:00",
        "Thai_Text": "ย-ยังไงก็ตาม ในฐานะผู้ใหญ่ที่เหมือนพ่อของพวกเธอทั้งคู่ คืนนี้ลุงจะคอยดูแลคุณชิออนแทนเธอให้เอง และจะส่งเธอกลับบ้านอย่างปลอดภัยนะ 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 14. RVPhoneMasaru14
    entries.append({
        "Image_Filename": "RVPhoneMasaru14.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "110",
        "Original_Text": "A-Anyway, as both you youngins father figure, I'll make sure to keep watch over Ms.Shion for you tonight and send her home safetly 22:00",
        "Thai_Text": "ย-ยังไงก็ตาม ในฐานะผู้ใหญ่ที่เหมือนพ่อของพวกเธอทั้งคู่ คืนนี้ลุงจะคอยดูแลคุณชิออนแทนเธอให้เอง และจะส่งเธอกลับบ้านอย่างปลอดภัยนะ 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru14.png", "Box_Index": "2",
        "X": "422", "Y": "270", "Width": "208", "Height": "110",
        "Original_Text": "So that no weird men will lay a single finger on her except for me, her guardian, who will keep her close to me. T-To watch over here for you, yes? 22:00",
        "Thai_Text": "เพื่อไม่ให้ผู้ชายแปลกหน้าที่ไหนมาแตะต้องเธอได้แม้แต่ปลายนิ้ว เว้นแต่ลุงที่เป็นผู้ปกครองที่จะคอยดูแลเธออย่างใกล้ชิด ค-คอยเฝ้าดูเธอแทนเธอไง ใช่ไหมล่ะ? 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })

    # 15. RVPhoneMasaru15
    entries.append({
        "Image_Filename": "RVPhoneMasaru15.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "110",
        "Original_Text": "A-Anyway, as both you youngins father figure, I'll make sure to keep watch over Ms.Shion for you tonight and send her home safetly 22:00",
        "Thai_Text": "ย-ยังไงก็ตาม ในฐานะผู้ใหญ่ที่เหมือนพ่อของพวกเธอทั้งคู่ คืนนี้ลุงจะคอยดูแลคุณชิออนแทนเธอให้เอง และจะส่งเธอกลับบ้านอย่างปลอดภัยนะ 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru15.png", "Box_Index": "2",
        "X": "422", "Y": "270", "Width": "208", "Height": "110",
        "Original_Text": "So that no weird men will lay a single finger on her except for me, her guardian, who will keep her close to me. T-To watch over here for you, yes? 22:00",
        "Thai_Text": "เพื่อไม่ให้ผู้ชายแปลกหน้าที่ไหนมาแตะต้องเธอได้แม้แต่ปลายนิ้ว เว้นแต่ลุงที่เป็นผู้ปกครองที่จะคอยดูแลเธออย่างใกล้ชิด ค-คอยเฝ้าดูเธอแทนเธอไง ใช่ไหมล่ะ? 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })
    entries.append({
        "Image_Filename": "RVPhoneMasaru15.png", "Box_Index": "3",
        "X": "422", "Y": "390", "Width": "208", "Height": "90",
        "Original_Text": "ohh I'm sorry what am I saying? but please, don't worry about her, I'll take good care of her. 22:00",
        "Thai_Text": "โอ๊ะ ลุงขอโทษด้วยนะ ลุงพูดอะไรออกไปเนี่ย? แต่ได้โปรดเถอะ ไม่ต้องเป็นห่วงเธอนะ ลุงจะดูแลเธอเป็นอย่างดีเอง 22:00",
        "Speaker": "Masaru", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 16. RVPhoneShion1
    entries.append({
        "Image_Filename": "RVPhoneShion1.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "95",
        "Original_Text": "Hey, um Dan! About the Dinner...I'll get it if you can't make it so...but..if you can then...I'll wait..! 19:42",
        "Thai_Text": "นี่ เอ่อ แดน! เรื่องมื้อเย็นน่ะ... ฉันเข้าใจนะถ้าเธอมาไม่ได้... แต่.. ถ้าเธอมาได้ล่ะก็... ฉันจะรอนะ..! 19:42",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })

    # 17. RVPhoneShion2
    entries.append({
        "Image_Filename": "RVPhoneShion2.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "95",
        "Original_Text": "Hey, um Dan! About the Dinner...I'll get it if you can't make it so...but..if you can then...I'll wait..! 19:42",
        "Thai_Text": "นี่ เอ่อ แดน! เรื่องมื้อเย็นน่ะ... ฉันเข้าใจนะถ้าเธอมาไม่ได้... แต่.. ถ้าเธอมาได้ล่ะก็... ฉันจะรอนะ..! 19:42",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion2.png", "Box_Index": "2",
        "X": "422", "Y": "260", "Width": "208", "Height": "110",
        "Original_Text": "You must be really busy, right? It..it must really be something so important so...I get it! I'll entertain myself while I wait~ hehe... 20:50",
        "Thai_Text": "เธอคงจะยุ่งมากๆ เลยใช่ไหมล่ะ? ม-มันคงเป็นเรื่องที่สำคัญมากแน่ๆ... ฉันเข้าใจนะ! ฉันจะหาอะไรทำรอไปพลางๆ นะ~ ฮิฮิ... 20:50",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 18. RVPhoneShion3
    entries.append({
        "Image_Filename": "RVPhoneShion3.png", "Box_Index": "1",
        "X": "422", "Y": "150", "Width": "208", "Height": "95",
        "Original_Text": "Hey, um Dan! About the Dinner...I'll get it if you can't make it so...but..if you can then...I'll wait..! 19:42",
        "Thai_Text": "นี่ เอ่อ แดน! เรื่องมื้อเย็นน่ะ... ฉันเข้าใจนะถ้าเธอมาไม่ได้... แต่.. ถ้าเธอมาได้ล่ะก็... ฉันจะรอนะ..! 19:42",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "14"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion3.png", "Box_Index": "2",
        "X": "422", "Y": "260", "Width": "208", "Height": "110",
        "Original_Text": "You must be really busy, right? It..it must really be something so important so...I get it! I'll entertain myself while I wait~ hehe... 20:50",
        "Thai_Text": "เธอคงจะยุ่งมากๆ เลยใช่ไหมล่ะ? ม-มันคงเป็นเรื่องที่สำคัญมากแน่ๆ... ฉันเข้าใจนะ! ฉันจะหาอะไรทำรอไปพลางๆ นะ~ ฮิฮิ... 20:50",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion3.png", "Box_Index": "3",
        "X": "422", "Y": "380", "Width": "208", "Height": "130",
        "Original_Text": "I didn't have time today but I wish I took some photos of what I've made. I'm sure you'll find them cute too! Oh oh, I was thinking of making you a mochi cake when we get back, to celebrate! Hehe♥ 21:36",
        "Thai_Text": "วันนี้ไม่มีเวลาเลย แต่ฉันก็อยากถ่ายรูปของที่ทำเก็บไว้จัง เธอจะต้องคิดว่ามันน่ารักแน่ๆ! อ๊ะ อ๊ะ ฉันคิดว่าจะทำเค้กโมจิให้เธอตอนพวกเรากลับไปนะ เพื่อฉลองไง! ฮิฮิ♥ 21:36",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })

    # 19. RVPhoneShion4
    entries.append({
        "Image_Filename": "RVPhoneShion4.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "130",
        "Original_Text": "hey..um...can you give me a call, at least..? I....I want to know if it's anything serious..I know its surely.. something serious so you don't want me to worry but...give me a call, ok? 22:19",
        "Thai_Text": "นี่.. เอ่อ... โทรหาฉันหน่อยได้ไหม อย่างน้อยก็สักสาย..? ฉัน....ฉันอยากรู้ว่ามีเรื่องร้ายแรงอะไรรึเปล่า.. ฉันรู้ว่ามันต้องเป็น.. เรื่องสำคัญแน่ๆ เธอถึงไม่อยากให้ฉันเป็นห่วง แต่ว่า... โทรหาฉันหน่อยนะ ได้ไหม? 22:19",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })

    # 20. RVPhoneShion5
    entries.append({
        "Image_Filename": "RVPhoneShion5.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "130",
        "Original_Text": "hey..um...can you give me a call, at least..? I....I want to know if it's anything serious..I know its surely.. something serious so you don't want me to worry but...give me a call, ok? 22:19",
        "Thai_Text": "นี่.. เอ่อ... โทรหาฉันหน่อยได้ไหม อย่างน้อยก็สักสาย..? ฉัน....ฉันอยากรู้ว่ามีเรื่องร้ายแรงอะไรรึเปล่า.. ฉันรู้ว่ามันต้องเป็น.. เรื่องสำคัญแน่ๆ เธอถึงไม่อยากให้ฉันเป็นห่วง แต่ว่า... โทรหาฉันหน่อยนะ ได้ไหม? 22:19",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion5.png", "Box_Index": "2",
        "X": "422", "Y": "275", "Width": "208", "Height": "110",
        "Original_Text": "you must be...really busy....and held up...to not be able to return my calls.. I'm sorry, I shouldn't be pestering you like this.. 22:35",
        "Thai_Text": "เธอคงจะ...ยุ่งมากจริงๆ....แล้วก็ติดธุระอยู่สินะ...ถึงโทรกลับมาไม่ได้.. ฉันขอโทษนะ ฉันไม่ควรจะเซ้าซี้เธอแบบนี้เลย.. 22:35",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })

    # 21. RVPhoneShion6
    entries.append({
        "Image_Filename": "RVPhoneShion6.png", "Box_Index": "1",
        "X": "422", "Y": "130", "Width": "208", "Height": "130",
        "Original_Text": "hey..um...can you give me a call, at least..? I....I want to know if it's anything serious..I know its surely.. something serious so you don't want me to worry but...give me a call, ok? 22:19",
        "Thai_Text": "นี่.. เอ่อ... โทรหาฉันหน่อยได้ไหม อย่างน้อยก็สักสาย..? ฉัน....ฉันอยากรู้ว่ามีเรื่องร้ายแรงอะไรรึเปล่า.. ฉันรู้ว่ามันต้องเป็น.. เรื่องสำคัญแน่ๆ เธอถึงไม่อยากให้ฉันเป็นห่วง แต่ว่า... โทรหาฉันหน่อยนะ ได้ไหม? 22:19",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion6.png", "Box_Index": "2",
        "X": "422", "Y": "275", "Width": "208", "Height": "110",
        "Original_Text": "you must be...really busy....and held up...to not be able to return my calls.. I'm sorry, I shouldn't be pestering you like this.. 22:35",
        "Thai_Text": "เธอคงจะ...ยุ่งมากจริงๆ....แล้วก็ติดธุระอยู่สินะ...ถึงโทรกลับมาไม่ได้.. ฉันขอโทษนะ ฉันไม่ควรจะเซ้าซี้เธอแบบนี้เลย.. 22:35",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13"
    })
    entries.append({
        "Image_Filename": "RVPhoneShion6.png", "Box_Index": "3",
        "X": "422", "Y": "395", "Width": "208", "Height": "130",
        "Original_Text": "I trust you so...um...its okay, I'll see you tomorrow! I believe in you so...um, but still if you want to give me a call I'll still be waiting for it...hehe I'm your clingy girlfriend after all.. 23:29",
        "Thai_Text": "ฉันเชื่อใจเธอนะ... เอ่อ... ไม่เป็นไรจ้ะ ไว้เจอกันพรุ่งนี้นะ! ฉันเชื่อมั่นในตัวเธอนะ... แต่ถึงอย่างนั้น ถ้าเธออยากโทรหาก็ยังรอสายอยู่นะ... ฮิฮิ ก็ฉันเป็นแฟนสาวขี้อ้อนของเธอนี่นา.. 23:29",
        "Speaker": "Shion", "Role": "Phone/Chat", "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12"
    })

    # --------------------------------------------------------------------------
    # 3. MasaruEnding1_Phone (Shion Ending Apology Messages - 22 Frames)
    # --------------------------------------------------------------------------
    masaru_ending_frames = [
        ("1", [("1", 160, 45, "I'm sorry.. I'm really sorry..")]),
        ("2", [("1", 160, 45, "I'm sorry.. I'm really sorry.."),
               ("2", 220, 45, "I'm a terrible person..."),
               ("3", 280, 60, "I know you won't want to see me anymore..")]),
        ("3", [("1", 160, 45, "I'm sorry.. I'm really sorry.."),
               ("2", 220, 45, "I'm a terrible person..."),
               ("3", 280, 60, "I know you won't want to see me anymore.."),
               ("4", 355, 75, "so I decided to move out.. I'm sorry, I don't know what else I can do..")]),
        ("4", [("1", 160, 70, "I wanted to knock on your door but..I didn't because you must still hate me.")]),
        ("5", [("1", 160, 70, "I wanted to knock on your door but..I didn't because you must still hate me."),
               ("2", 240, 70, "But I'm worried about you, you've been in the room for so long...")]),
        ("6", [("1", 160, 70, "I wanted to knock on your door but..I didn't because you must still hate me."),
               ("2", 240, 70, "But I'm worried about you, you've been in the room for so long..."),
               ("3", 320, 55, "Even if you hate me won't you come out of your room..?")]),
        ("7", [("1", 160, 70, "I wanted to knock on your door but..I didn't because you must still hate me."),
               ("2", 240, 70, "But I'm worried about you, you've been in the room for so long..."),
               ("3", 320, 55, "Even if you hate me won't you come out of your room..?"),
               ("4", 385, 55, "I know you don't want to see me but..")]),
        ("8", [("1", 160, 70, "I wanted to knock on your door but..I didn't because you must still hate me."),
               ("2", 240, 70, "But I'm worried about you, you've been in the room for so long..."),
               ("3", 320, 55, "Even if you hate me won't you come out of your room..?"),
               ("4", 385, 55, "I know you don't want to see me but.."),
               ("5", 450, 55, "you need to eat..it has been days..")]),
        ("10", [("1", 160, 45, "Hi...")]),
        ("11", [("1", 160, 45, "Hi..."),
                ("2", 220, 75, "I bought some food from the convenient mart and left it outside your room....")]),
        ("12", [("1", 160, 45, "Hi..."),
                ("2", 220, 75, "I bought some food from the convenient mart and left it outside your room...."),
                ("3", 305, 45, "Please.")]),
        ("13", [("1", 160, 45, "Hi..."),
                ("2", 220, 75, "I bought some food from the convenient mart and left it outside your room...."),
                ("3", 305, 45, "Please."),
                ("4", 360, 45, "Please eat something..")]),
        ("14", [("1", 160, 60, "Um..I came back to the house again in the morning..")]),
        ("15", [("1", 160, 60, "Um..I came back to the house again in the morning.."),
                ("2", 230, 60, "I bought you a different type of bento box..")]),
        ("16", [("1", 160, 60, "Um..I came back to the house again in the morning.."),
                ("2", 230, 60, "I bought you a different type of bento box.."),
                ("3", 300, 75, "I noticed that you didn't eat the ones from yesterday so maybe you didn't like them..")]),
        ("17", [("1", 160, 60, "Um..I came back to the house again in the morning.."),
                ("2", 230, 60, "I bought you a different type of bento box.."),
                ("3", 300, 75, "I noticed that you didn't eat the ones from yesterday so maybe you didn't like them.."),
                ("4", 385, 60, "Um..you didn't touch them at all.")]),
        ("18", [("1", 160, 70, "and your room door is still closed, you haven't been out at all..?")]),
        ("19", [("1", 160, 70, "and your room door is still closed, you haven't been out at all..?"),
                ("2", 240, 60, "I'm sorry, I shouldn't have come back after leaving..")]),
        ("20", [("1", 160, 70, "and your room door is still closed, you haven't been out at all..?"),
                ("2", 240, 60, "I'm sorry, I shouldn't have come back after leaving.."),
                ("3", 310, 60, "but I wanted to know that you are alright.....I'm sorry.")]),
        ("21", [("1", 160, 70, "and your room door is still closed, you haven't been out at all..?"),
                ("2", 240, 60, "I'm sorry, I shouldn't have come back after leaving.."),
                ("3", 310, 60, "but I wanted to know that you are alright.....I'm sorry."),
                ("4", 380, 60, "But..please Dan, you have to eat something.")]),
        ("22", [("1", 160, 60, "You shouldn't...for someone like me....."),
                ("2", 230, 45, "I'm so sorry.")])
    ]
    for f_idx, bubbles in masaru_ending_frames:
        for b_idx, y_pos, h_dim, txt in bubbles:
            entries.append({
                "Image_Filename": f"MasaruEnding1_Phone{f_idx}.png",
                "Box_Index": b_idx,
                "X": "412",
                "Y": str(y_pos),
                "Width": "230",
                "Height": str(h_dim),
                "Original_Text": txt,
                "Thai_Text": "",
                "Speaker": "Shion",
                "Role": "Phone/Chat",
                "Text_Color": "#333333",
                "Bg_Color": "#FFFFFF",
                "Font_Size": "13",
                "Stroke_Width": "0",
                "Stroke_Color": "",
                "Alignment": "left"
            })

    # --------------------------------------------------------------------------
    # 4. Phone_ShionShyStripCHATBOX (Livestream Viewer Comments Overlay - 6 Frames)
    # --------------------------------------------------------------------------
    livestream_frames = [
        ("1", [
            ("1", "85", "20", "260", "25", "Ha..ha...whew, we've all missed you..", "StreamViewer", "#FF33CC", "transparent", "14", "2", "#FFFFFF", "left"),
            ("2", "85", "70", "260", "25", "What'll a man do for more? You're a 100..", "StreamViewer", "#FF9900", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "125", "260", "25", "i enjoy seeing you but its been the same", "StreamViewer", "#00CC99", "transparent", "14", "2", "#FFFFFF", "left"),
        ]),
        ("2", [
            ("1", "120", "0", "200", "28", "I'll pay her to shake them tits", "Donation", "#FFFFFF", "#FF3399", "14", "2", "#FF0066", "center"),
            ("2", "85", "50", "260", "25", "It'll be more perfect if you strip further", "StreamViewer", "#333333", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "95", "260", "25", "Will you...? Will it finally be time?", "StreamViewer", "#66FF33", "transparent", "14", "2", "#FFFFFF", "left"),
            ("4", "85", "145", "260", "25", "Strip♥♥! Strip!!!!♥", "StreamViewer", "#FF0099", "transparent", "14", "2", "#FFFFFF", "left"),
        ]),
        ("3", [
            ("1", "85", "20", "260", "25", "What a body...it'll be even better if..", "StreamViewer", "#00CCFF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("2", "85", "70", "260", "25", "Come now, we've all paid so much...", "StreamViewer", "#9933FF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "125", "260", "25", "T-That's right, I've prepared tissues", "StreamViewer", "#FF3333", "transparent", "14", "2", "#FFFFFF", "left"),
        ]),
        ("4", [
            ("1", "70", "170", "170", "35", "SummerSanta $50000: Please please show us!!!!", "Donation", "#FFFFFF", "#CC0000", "14", "2", "#990000", "center"),
            ("2", "85", "20", "260", "25", "What a body...it'll be even better if..", "StreamViewer", "#00CCFF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "70", "260", "25", "Come now, we've all paid so much...", "StreamViewer", "#9933FF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("4", "85", "125", "260", "25", "T-That's right, I've prepared tissues", "StreamViewer", "#FF3333", "transparent", "14", "2", "#FFFFFF", "left"),
        ]),
        ("5", [
            ("1", "120", "0", "200", "28", "I'll pay her to shake them tits", "Donation", "#FFFFFF", "#FF3399", "14", "2", "#FF0066", "center"),
            ("2", "85", "50", "260", "25", "SERIOUSLY? WWWWW WOWOWOOWOOOOFGFGFGF", "StreamViewer", "#333333", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "95", "260", "25", "ITS HEREEEE O_O OO.OO OHMYGOD DEEZNUTS SLAY", "StreamViewer", "#66FF33", "transparent", "14", "2", "#FFFFFF", "left"),
            ("4", "85", "145", "260", "25", "WOOOOOOOOOO♥♥♥♥♥♥♥", "StreamViewer", "#FF0099", "transparent", "14", "2", "#FFFFFF", "left"),
        ]),
        ("6", [
            ("1", "70", "175", "170", "35", "RkhardOnyx $10000: No more teasing. PLEASE!!!!", "Donation", "#FFFFFF", "#CC00CC", "14", "2", "#990099", "center"),
            ("2", "85", "20", "260", "25", "ERUPTION! ERO! ERO! EROPTION!", "StreamViewer", "#00CCFF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("3", "85", "70", "260", "25", "Don't be shy....we can't wait ♥", "StreamViewer", "#9933FF", "transparent", "14", "2", "#FFFFFF", "left"),
            ("4", "85", "125", "260", "25", "Cmon! I can see the pink alrdy..so sexy!", "StreamViewer", "#FF3333", "transparent", "14", "2", "#FFFFFF", "left"),
        ])
    ]
    for fn_num, lines in livestream_frames:
        for b_idx, x, y, w, h, txt, spk, tc, bg, fs, sw, sc, al in lines:
            entries.append({
                "Image_Filename": f"Phone_ShionShyStripCHATBOX{fn_num}.png",
                "Box_Index": b_idx,
                "X": x, "Y": y, "Width": w, "Height": h,
                "Original_Text": txt,
                "Thai_Text": "",
                "Speaker": spk,
                "Role": "Stream/Chat",
                "Text_Color": tc,
                "Bg_Color": bg,
                "Font_Size": fs,
                "Stroke_Width": sw,
                "Stroke_Color": sc,
                "Alignment": al
            })

    # --------------------------------------------------------------------------
    # 5. PhoneMasaru2 (Twitter Feed & Post Comments)
    # --------------------------------------------------------------------------
    entries.append({
        "Image_Filename": "PhoneMasaru2_1.png", "Box_Index": "1",
        "X": "420", "Y": "190", "Width": "180", "Height": "40",
        "Original_Text": "#Hotbakerbabe ♥ #Seasidevillagewhores",
        "Thai_Text": "",
        "Speaker": "M1keMoneyK", "Role": "Phone/Social", "Text_Color": "#0099FF", "Bg_Color": "transparent", "Font_Size": "13",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "PhoneMasaru2_1.png", "Box_Index": "2",
        "X": "420", "Y": "720", "Width": "190", "Height": "85",
        "Original_Text": "A really hot babe has turned up at my forest. My luck has finally changed. We're going to have a fun summer together...",
        "Thai_Text": "",
        "Speaker": "1EyeSeaKing", "Role": "Phone/Social", "Text_Color": "#333333", "Bg_Color": "transparent", "Font_Size": "12",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "PhoneMasaru2_3.png", "Box_Index": "1",
        "X": "705", "Y": "305", "Width": "195", "Height": "80",
        "Original_Text": "You have me to thank for getting you this close up, that's some nice whipped cream there, ain't it?",
        "Thai_Text": "",
        "Speaker": "M1keMoneyK", "Role": "Phone/Social", "Text_Color": "#333333", "Bg_Color": "#FFFFFF", "Font_Size": "12",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "PhoneMasaru2_3.png", "Box_Index": "2",
        "X": "705", "Y": "505", "Width": "195", "Height": "60",
        "Original_Text": "Holy shit, thank you for the good material for tonight...",
        "Thai_Text": "",
        "Speaker": "Commenter", "Role": "Phone/Social", "Text_Color": "#333333", "Bg_Color": "#FFFFFF", "Font_Size": "12",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "PhoneMasaru2_3.png", "Box_Index": "3",
        "X": "705", "Y": "655", "Width": "195", "Height": "45",
        "Original_Text": "Is this place somewhere near the Capital?",
        "Thai_Text": "",
        "Speaker": "Commenter", "Role": "Phone/Social", "Text_Color": "#333333", "Bg_Color": "#FFFFFF", "Font_Size": "12",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "PhoneMasaru2_3.png", "Box_Index": "4",
        "X": "705", "Y": "780", "Width": "195", "Height": "45",
        "Original_Text": "Damn those are some quality buns....",
        "Thai_Text": "",
        "Speaker": "Commenter", "Role": "Phone/Social", "Text_Color": "#333333", "Bg_Color": "#FFFFFF", "Font_Size": "12",
        "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "left"
    })

    # --------------------------------------------------------------------------
    # 6. Smartphone UI Navigation Buttons (p1_*.png)
    # --------------------------------------------------------------------------
    p1_buttons = [
        ("p1_close.png", "CLOSE"),
        ("p1_lockscreen.png", "LOCK SCREEN"),
        ("p1_notes.png", "NOTES"),
        ("p1_passtime.png", "PASS TIME"),
        ("p1_phone.png", "PHONE"),
        ("p1_question.png", "QUESTION"),
        ("p1_quests.png", "QUESTS"),
        ("p1_speak.png", "SPEAK"),
        ("p1_twaxtor.png", "TWAXTOR"),
        ("p1_wussapps.png", "WUSSAPPS")
    ]
    for b_fname, b_text in p1_buttons:
        entries.append({
            "Image_Filename": b_fname, "Box_Index": "1",
            "X": "40", "Y": "60", "Width": "420", "Height": "140",
            "Original_Text": b_text,
            "Thai_Text": "",
            "Speaker": "UI", "Role": "Phone/UI",
            "Text_Color": "#000000", "Bg_Color": "transparent",
            "Font_Size": "48", "Stroke_Width": "0", "Stroke_Color": "", "Alignment": "center"
        })

    # --------------------------------------------------------------------------
    # 7. Incoming Call, Notifications & Home Screen App Icons
    # --------------------------------------------------------------------------
    entries.append({
        "Image_Filename": "PhoneCallIing.png", "Box_Index": "1",
        "X": "440", "Y": "520", "Width": "400", "Height": "40",
        "Original_Text": "shion", "Thai_Text": "",
        "Speaker": "Phone", "Role": "Phone/UI",
        "Text_Color": "#FFFFFF", "Bg_Color": "transparent", "Font_Size": "28", "Alignment": "center"
    })
    entries.append({
        "Image_Filename": "PhoneCallIing.png", "Box_Index": "2",
        "X": "440", "Y": "590", "Width": "400", "Height": "30",
        "Original_Text": "CALLING....", "Thai_Text": "",
        "Speaker": "Phone", "Role": "Phone/UI",
        "Text_Color": "#FFFFFF", "Bg_Color": "transparent", "Font_Size": "16", "Alignment": "center"
    })

    for notif_fn in ["PhoneNotificationMSG.png", "PhoneNotificationTwitter.png", "PhoneNotificationXXX.png"]:
        entries.append({
            "Image_Filename": notif_fn, "Box_Index": "1",
            "X": "1085", "Y": "880", "Width": "150", "Height": "35",
            "Original_Text": "Notification", "Thai_Text": "",
            "Speaker": "Phone", "Role": "Phone/UI",
            "Text_Color": "#FFFFFF", "Bg_Color": "#DC3D7E", "Font_Size": "14", "Alignment": "center"
        })

    app_icons = [
        ("1", "400", "310", "80", "25", "TwiXter"),
        ("2", "515", "310", "85", "25", "WassApps"),
        ("3", "400", "540", "80", "25", "OnlyF*ps"),
        ("4", "520", "540", "80", "25", "Gallery"),
        ("5", "400", "775", "80", "25", "Phone"),
        ("6", "520", "775", "80", "25", "Camera"),
    ]
    for b_idx, x, y, w, h, icon_label in app_icons:
        entries.append({
            "Image_Filename": "PhoneWhatsapp.png", "Box_Index": b_idx,
            "X": x, "Y": y, "Width": w, "Height": h,
            "Original_Text": icon_label, "Thai_Text": "",
            "Speaker": "Phone", "Role": "Phone/UI",
            "Text_Color": "#FFFFFF", "Bg_Color": "transparent",
            "Font_Size": "14", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "center"
        })

    # --------------------------------------------------------------------------
    # 8. Tutorials & Special UI Graphics (Pixel-Perfect Ground Truth - ADR-033)
    # --------------------------------------------------------------------------
    # BeachBarTutorial.png
    entries.append({
        "Image_Filename": "BeachBarTutorial.png", "Box_Index": "1",
        "X": "155", "Y": "22", "Width": "340", "Height": "48",
        "Original_Text": "1. Order-Taking", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "BeachBarTutorial.png", "Box_Index": "2",
        "X": "485", "Y": "45", "Width": "285", "Height": "50",
        "Original_Text": "2. Prep", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "BeachBarTutorial.png", "Box_Index": "4",
        "X": "145", "Y": "314", "Width": "200", "Height": "48",
        "Original_Text": "3. Cook", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "BeachBarTutorial.png", "Box_Index": "5",
        "X": "518", "Y": "374", "Width": "290", "Height": "48",
        "Original_Text": "4. Serve", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })

    # Fishguide.png
    entries.append({
        "Image_Filename": "Fishguide.png", "Box_Index": "1",
        "X": "570", "Y": "25", "Width": "450", "Height": "100",
        "Original_Text": "CLICK when in the ZONE", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "20", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "Fishguide.png", "Box_Index": "2",
        "X": "940", "Y": "235", "Width": "290", "Height": "120",
        "Original_Text": "ROD AND BAIT UPGRADES THROUGH CHARACTERS YOU MEET", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "Fishguide.png", "Box_Index": "3",
        "X": "240", "Y": "425", "Width": "245", "Height": "85",
        "Original_Text": "FISHING SPOT", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "20", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "Fishguide.png", "Box_Index": "4",
        "X": "375", "Y": "580", "Width": "820", "Height": "55",
        "Original_Text": "CATCH DIFFERENT FISHES AT DIFFERENT LOCATIONS", "Thai_Text": "",
        "Speaker": "", "Role": "ui", "Text_Color": "#FFFFFF", "Bg_Color": "#000000",
        "Font_Size": "18", "Stroke_Width": "1", "Stroke_Color": "#000000", "Alignment": "left"
    })

    # ShionMessage1.png
    entries.append({
        "Image_Filename": "ShionMessage1.png", "Box_Index": "3",
        "X": "412", "Y": "150", "Width": "230", "Height": "115",
        "Original_Text": "Hihi! How's the new phone? Or \"old\" phone since it belonged to someone else, hehe XD. I've saved my contact for you yesterday!~",
        "Thai_Text": "", "Speaker": "Shion", "Role": "Phone/Chat",
        "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "ShionMessage1.png", "Box_Index": "4",
        "X": "412", "Y": "275", "Width": "230", "Height": "115",
        "Original_Text": "Oh! I also set your display picture for you.. hehe. We dun usually take photos tgt so its nice. now you'll always think of me~!",
        "Thai_Text": "", "Speaker": "Shion", "Role": "Phone/Chat",
        "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12", "Alignment": "left"
    })
    entries.append({
        "Image_Filename": "ShionMessage1.png", "Box_Index": "5",
        "X": "412", "Y": "400", "Width": "230", "Height": "95",
        "Original_Text": "Anywaaay, I'm looking to spend this summer with my bf! so let's have loads loads of fun!~",
        "Thai_Text": "", "Speaker": "Shion", "Role": "Phone/Chat",
        "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "12", "Alignment": "left"
    })

    # MessageBakeryMasaru1.png
    entries.append({
        "Image_Filename": "MessageBakeryMasaru1.png", "Box_Index": "3",
        "X": "412", "Y": "150", "Width": "230", "Height": "115",
        "Original_Text": "Ah Dan.. I thought I would update you on the progress of the mochi bun... me and Ms. Shion has been hard at work...",
        "Thai_Text": "", "Speaker": "Masaru", "Role": "Phone/Chat",
        "Text_Color": "#333333", "Bg_Color": "#F7F7F7", "Font_Size": "13", "Alignment": "left"
    })

    if not with_translations:
        for e in entries:
            e["Thai_Text"] = ""

    return entries


# ==============================================================================
# PIPELINE ACTIONS
# ==============================================================================

def run_decrypt(pattern: str = "*", output_dir: Optional[str] = None, folder: str = "pictures", auto_catalog: bool = False):
    """
    ถอดรหัสไฟล์ภาพ .rpgmvp เป็น .png ลง Target Output Workspace (ADR-024)
    รองรับ folder='all' เพื่อถอดรหัสภาพจากทุกโฟลเดอร์ในเกม (pictures, system, SumRndmDde/choices, titles1 ฯลฯ)
    และรองรับ auto_catalog=True เพื่อสร้างแคตตาล็อก CSV ต่อเนื่องทันที
    """
    paths = resolve_workspace_paths(folder=folder if folder != "all" else "pictures")
    key = paths["key"]
    game_dir = paths["game_dir"]
    target_out = output_dir if output_dir else paths["raw_dir"]

    if not key:
        print("❌ Could not locate encryption key in System.json!")
        return

    img_root = os.path.join(game_dir, "www", "img")
    if not os.path.exists(img_root):
        img_root = os.path.join(game_dir, "img")

    folders_to_search = []
    if folder == "all":
        folders_to_search = ["pictures", "system", "SumRndmDde", "SumRndmDde/choices", "chaincmd", "pSimpleFishing", "titles1", "titles2"]
    else:
        folders_to_search = [folder]

    all_matched_files = []
    for fld in folders_to_search:
        fld_path = os.path.join(img_root, fld)
        if not os.path.exists(fld_path):
            continue
        # ค้นหาแบบ Recursive เพื่อรองรับโฟลเดอร์ย่อย เช่น SumRndmDde/choices
        patt_matched = glob.glob(os.path.join(fld_path, "**", f"{pattern}.rpgmvp"), recursive=True)
        if not patt_matched:
            patt_matched = glob.glob(os.path.join(fld_path, f"{pattern}.rpgmvp"))
        all_matched_files.extend(patt_matched)

    # ขจัดรายการซ้ำหากมีโฟลเดอร์ซ้อนกัน
    all_matched_files = list(dict.fromkeys(all_matched_files))

    print("=" * 80)
    print(f"🔓 DECRYPTING GAME IMAGES (.rpgmvp -> .png) [FOLDER: {folder}] [ADR-024 COMPLIANT]")
    print(f"Game Img Root:        {img_root}")
    print(f"Filter Pattern:       {pattern}")
    print(f"Target Output Raw:    {target_out}")
    print("=" * 80)

    os.makedirs(target_out, exist_ok=True)
    print(f"📦 Found {len(all_matched_files):,} matching files to decrypt.")

    success_count = 0
    for idx, fpath in enumerate(all_matched_files, 1):
        png_name = os.path.splitext(os.path.basename(fpath))[0] + ".png"
        out_png = os.path.join(target_out, png_name)

        ok = RPGMImageCrypto.decrypt_file(fpath, out_png, key)
        if ok:
            success_count += 1
            if idx <= 10 or idx % 20 == 0 or idx == len(all_matched_files):
                print(f"  [{idx}/{len(all_matched_files)}] Decrypted: {png_name}")

    # Sync สำเนาไว้ที่ data/images/raw ภายในโปรเจกต์ด้วยเพื่อความสะดวก
    proj_raw = os.path.join(BASE_DIR, "data", "images", "raw")
    if os.path.abspath(target_out) != os.path.abspath(proj_raw):
        os.makedirs(proj_raw, exist_ok=True)
        for f in glob.glob(os.path.join(target_out, "*.png")):
            shutil.copy2(f, os.path.join(proj_raw, os.path.basename(f)))

    print(f"\n🎉 Successfully decrypted {success_count:,} images to: {target_out}")
    print(f"   Project Copy: {proj_raw}")

    if auto_catalog:
        print("\n⚡ Automatically generating dialogue catalog CSV for decrypted images...")
        run_catalog(raw_dir=target_out)


def run_catalog(raw_dir: Optional[str] = None, catalog_csv: Optional[str] = None, with_translations: bool = False, scanned_items: Optional[List[Dict[str, Any]]] = None, engine: str = "auto", rebuild: bool = False):
    """
    สร้างตารางแคตตาล็อก Bounding Box และบทสนทนาจริงแบบ Dynamic 100%:
    1. ตรวจสอบไฟล์ภาพ .png ทั้งหมดที่มีอยู่ในโฟลเดอร์ raw_dir
    2. สำหรับ RVPhone*: ผสานข้อมูลพิกัดและประโยคสนทนาจริง
    3. หากมี scanned_items จาก Deep Scan ให้นำเข้า Bounding Box และข้อความได้ทันที
    4. สำหรับภาพ uncataloged อื่นๆ: รัน Deep Learning OCR ดึงข้อความจริงและรวม Paragraph อัตโนมัติ (ADR-030 & ADR-031)
    5. ผสานรวมกับข้อมูลคำแปลเดิมที่มีอยู่แล้วใน image_dialogues.csv / unique_dialogues.csv
    6. ส่งต่อเข้าสู่ระบบ dedupe เพื่อสร้าง unique_dialogues.csv อัตโนมัติ
    """
    paths = resolve_workspace_paths()
    src_raw = raw_dir if raw_dir else paths["raw_dir"]
    out_csv = catalog_csv if catalog_csv else paths["catalog_csv"]

    # Fallback ตรวจสอบโฟลเดอร์ data/images/raw หากใน Target Output ว่าง
    if not os.path.exists(src_raw) or not glob.glob(os.path.join(src_raw, "*.png")):
        alt_raw = os.path.join(BASE_DIR, "data", "images", "raw")
        if os.path.exists(alt_raw) and glob.glob(os.path.join(alt_raw, "*.png")):
            src_raw = alt_raw

    print("=" * 80)
    print("📋 DYNAMIC CATALOGING GAME IMAGE TEXTS & BOUNDING BOXES [PARAGRAPH MERGE]")
    print(f"Raw Images Directory: {src_raw}")
    print(f"Output Catalog CSV:   {out_csv}")
    print(f"Rebuild Mode:         {'YES (Re-detect & Merge Paragraph Bubbles)' if rebuild else 'NO (Preserve existing box coordinates)'}")
    print(f"Fill Preset Translations: {'YES' if with_translations else 'NO (Blank for real translation)'}")
    print("=" * 80)

    # ดึงคำแปลเดิมที่เคยแปลไว้แล้วเพื่อไม่ให้สูญหาย
    existing_translations: Dict[str, str] = {}
    existing_entries: Dict[Tuple[str, str], Dict[str, str]] = {}
    if os.path.exists(out_csv):
        try:
            with open(out_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    fn = r.get("Image_Filename", "").strip()
                    bi = r.get("Box_Index", "1").strip()
                    txt = r.get("Original_Text", "").strip()
                    tt = r.get("Thai_Text", "").strip()
                    if ot_clean := txt:
                        if tt:
                            existing_translations[ot_clean] = tt
                            clean_k = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', ot_clean).strip()
                            existing_translations[clean_k] = tt
                    if fn and ImageTextDetector.is_text_eligible_filename(fn) and ImageTextDetector.is_valid_game_text(txt):
                        existing_entries[(fn, bi)] = r
        except Exception:
            pass

    # ตรวจสอบสำเนาในโปรเจกต์ด้วย
    proj_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
    if not existing_entries and os.path.exists(proj_csv):
        try:
            with open(proj_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    fn = r.get("Image_Filename", "").strip()
                    bi = r.get("Box_Index", "1").strip()
                    txt = r.get("Original_Text", "").strip()
                    tt = r.get("Thai_Text", "").strip()
                    if txt and tt:
                        existing_translations[txt] = tt
                        clean_k = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', txt).strip()
                        existing_translations[clean_k] = tt
                    if fn and ImageTextDetector.is_text_eligible_filename(fn) and ImageTextDetector.is_valid_game_text(txt):
                        existing_entries[(fn, bi)] = r
        except Exception:
            pass

    # ดึงคำแปลจาก unique_dialogues.csv ด้วยถ้ามี
    unique_path = os.path.join(paths["images_base"], "unique_dialogues.csv")
    if not os.path.exists(unique_path):
        unique_path = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
    if os.path.exists(unique_path):
        try:
            with open(unique_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    ot = r.get("Clean_Original", "").strip()
                    tt = r.get("Thai_Text", "").strip()
                    if ot and tt:
                        existing_translations[ot] = tt
        except Exception:
            pass

    # 2. ดึง Data พิกัดและข้อความของภาพแชตมือถือ RVPhone
    ground_truth = get_ground_truth_catalog_entries(with_translations=with_translations)
    entries: List[Dict[str, str]] = []
    processed_files: Set[str] = set()
    gt_files: Set[str] = set()

    for gt in ground_truth:
        fn = gt["Image_Filename"]
        # หากมีโฟลเดอร์ raw และผู้ใช้คัดออก/ลบไฟล์นี้ไปแล้ว ไม่ต้องนำกลับเข้ามา
        if os.path.exists(src_raw) and not os.path.exists(os.path.join(src_raw, fn)):
            continue
        bi = gt["Box_Index"]
        processed_files.add(fn)
        gt_files.add(fn)
        if (fn, bi) in existing_entries and not rebuild:
            ex = existing_entries[(fn, bi)]
            merged = dict(gt)
            if ex.get("Thai_Text"):
                merged["Thai_Text"] = ex["Thai_Text"]
            if ex.get("X"):
                merged["X"] = ex["X"]
            if ex.get("Y"):
                merged["Y"] = ex["Y"]
            if ex.get("Width"):
                merged["Width"] = ex["Width"]
            if ex.get("Height"):
                merged["Height"] = ex["Height"]
            entries.append(merged)
        else:
            gt_copy = dict(gt)
            clean_gt = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', gt_copy.get("Original_Text", "")).strip()
            if not gt_copy.get("Thai_Text") and clean_gt in existing_translations:
                gt_copy["Thai_Text"] = existing_translations[clean_gt]
            entries.append(gt_copy)

    # 2.1 หากมี scanned_items ส่งต่อมาจาก Deep Asset Scan ใน RAM ให้นำเข้า Bounding Box ได้ทันที
    if scanned_items and not rebuild:
        for it in scanned_items:
            orig_p = it.get("path", "")
            fname = os.path.splitext(os.path.basename(orig_p))[0] + ".png"
            if not ImageTextDetector.is_text_eligible_filename(fname):
                continue
            lines = it.get("lines", [])
            if lines and fname not in processed_files:
                processed_files.add(fname)
                for idx, line in enumerate(lines, 1):
                    txt = line.get("text", "").strip()
                    if not ImageTextDetector.is_valid_game_text(txt):
                        continue
                    clean_txt = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', txt).strip()
                    ex = existing_entries.get((fname, str(idx)), {})
                    th_val = ex.get("Thai_Text", "") or existing_translations.get(txt, existing_translations.get(clean_txt, ""))
                    entries.append({
                        "Image_Filename": fname,
                        "Box_Index": str(idx),
                        "X": str(ex.get("X", line.get("x", 100))),
                        "Y": str(ex.get("Y", line.get("y", 100))),
                        "Width": str(ex.get("Width", max(150, line.get("width", 200)))),
                        "Height": str(ex.get("Height", max(40, line.get("height", 50)))),
                        "Original_Text": txt,
                        "Thai_Text": th_val,
                        "Speaker": ex.get("Speaker", ""),
                        "Role": "dialogue" if len(lines) > 1 or line.get("is_merged_paragraph") else "ui",
                        "Text_Color": ex.get("Text_Color", "#000000"),
                        "Bg_Color": ex.get("Bg_Color", "#FFFFFF"),
                        "Font_Size": ex.get("Font_Size", "18"),
                        "Stroke_Width": ex.get("Stroke_Width", "0"),
                        "Stroke_Color": ex.get("Stroke_Color", "#000000"),
                        "Alignment": ex.get("Alignment", "left")
                    })

    # 3. สำหรับไฟล์ใน src_raw ที่ไม่อยู่ใน ground_truth (และรันใหม่หมดหากเปิด rebuild):
    # ใช้งาน Universal Deep Learning OCR ดึงข้อความจริงและรวม Paragraph อัตโนมัติ (ADR-030 & ADR-031)
    corr_rules = load_ocr_corrections()
    if os.path.exists(src_raw):
        raw_pngs = sorted(glob.glob(os.path.join(src_raw, "*.png")))
        uncataloged = [
            p for p in raw_pngs
            if (os.path.basename(p) not in gt_files) and (rebuild or os.path.basename(p) not in processed_files) and ImageTextDetector.is_text_eligible_filename(p)
        ]
        if uncataloged:
            print(f"  🔍 Processing {len(uncataloged)} images with Paragraph/Bubble Merger & Lexical Normalizer...")
            for idx_p, p in enumerate(uncataloged, 1):
                fname = os.path.basename(p)
                res = ImageTextDetector.detect_text(p, min_score=0.65, engine=engine, merge_paragraphs=True)
                lines = res.get("lines", [])
                if res.get("has_text") and lines:
                    processed_files.add(fname)
                    for idx, line in enumerate(lines, 1):
                        raw_t = line.get("text", "").strip()
                        txt = ImageTextDetector.normalize_ocr_text(raw_t, custom_corrections=corr_rules)
                        if not ImageTextDetector.is_valid_game_text(txt):
                            continue
                        clean_txt = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', txt).strip()
                        th_val = ""
                        if not rebuild:
                            ex = existing_entries.get((fname, str(idx)), {})
                            th_val = ex.get("Thai_Text", "")
                        if not th_val:
                            th_val = existing_translations.get(txt, existing_translations.get(clean_txt, ""))

                        box_w = max(150, line.get("width", 200))
                        box_h = max(40, line.get("height", 50))
                        entries.append({
                            "Image_Filename": fname,
                            "Box_Index": str(idx),
                            "X": str(line.get("x", 100)),
                            "Y": str(line.get("y", 100)),
                            "Width": str(box_w),
                            "Height": str(box_h),
                            "Original_Text": txt,
                            "Thai_Text": th_val,
                            "Speaker": "",
                            "Role": "dialogue" if len(lines) > 1 or line.get("is_merged_paragraph") else "ui",
                            "Text_Color": "#000000",
                            "Bg_Color": "#FFFFFF",
                            "Font_Size": "18",
                            "Stroke_Width": "0",
                            "Stroke_Color": "#000000",
                            "Alignment": "left"
                        })
                if idx_p % 50 == 0 or idx_p == len(uncataloged):
                    print(f"    [{idx_p:,}/{len(uncataloged):,}] Processed images...")

    # บันทึกไฟล์ลง Target Workspace
    safe_write_csv(out_csv, CSV_HEADER, entries)

    # Sync สำเนาไว้ที่ data/images/image_dialogues.csv ในโปรเจกต์ด้วย
    proj_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
    safe_copy_file(out_csv, proj_csv)

    print(f"💾 Catalog created successfully with {len(entries):,} entries across {len(processed_files):,} images!")
    print(f"   Target Path:  {out_csv}")
    print(f"   Project Copy: {proj_csv}")

    # รัน dedupe ต่ออัตโนมัติ เพื่อสร้าง unique_dialogues.csv ให้พร้อมแปลทันที
    run_dedupe(catalog_csv=out_csv)


def run_dedupe(catalog_csv: Optional[str] = None, output_unique_csv: Optional[str] = None):
    """
    ยุบรวมข้อความซ้ำ (Deduplication / Translation Memory Extractor):
    สกัดข้อความ Original_Text ที่ไม่ซ้ำกันทั้งหมด ออกมาเป็น unique_dialogues.csv
    เพื่อให้ผู้แปลสามารถใส่คำแปลเพียงแค่ 1 ครั้งต่อ 1 ข้อความเท่านั้น!
    """
    paths = resolve_workspace_paths()
    src_csv = catalog_csv if catalog_csv else paths["catalog_csv"]
    if not os.path.exists(src_csv):
        alt_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt_csv):
            src_csv = alt_csv

    if not os.path.exists(src_csv):
        print(f"❌ Catalog CSV not found: {src_csv}")
        return

    out_unique = output_unique_csv
    if not out_unique:
        out_unique = os.path.join(paths["images_base"], "unique_dialogues.csv")

    with open(src_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # โหลดคำแปลเดิมที่มีอยู่แล้วใน unique_dialogues.csv เพื่อไม่ให้สูญหาย
    existing_unique_translations: Dict[str, str] = {}
    if os.path.exists(out_unique):
        try:
            with open(out_unique, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for ur in reader:
                    ck = ur.get("Clean_Original", "").strip()
                    tt = ur.get("Thai_Text", "").strip()
                    if ck and tt:
                        existing_unique_translations[ck] = tt
        except Exception:
            pass

    # ตรวจสอบสำเนาในโปรเจกต์ด้วย
    proj_unique_check = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
    if not existing_unique_translations and os.path.exists(proj_unique_check):
        try:
            with open(proj_unique_check, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for ur in reader:
                    ck = ur.get("Clean_Original", "").strip()
                    tt = ur.get("Thai_Text", "").strip()
                    if ck and tt:
                        existing_unique_translations[ck] = tt
        except Exception:
            pass

    # จัดกลุ่มตาม Normalized Original Text (ตัดตัวเลขเวลาออกเพื่อจับคู่ประโยคแท้จริง และรัน Lexical Normalizer)
    corr = load_ocr_corrections()
    unique_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        orig = r.get("Original_Text", "").strip()
        if not orig:
            continue

        raw_ocr = r.get("Raw_OCR", orig)
        norm_orig = ImageTextDetector.normalize_ocr_text(orig, custom_corrections=corr)
        clean_key = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', norm_orig).strip()
        row_thai = r.get("Thai_Text", "").strip()
        th_val = row_thai or existing_unique_translations.get(clean_key, existing_unique_translations.get(orig, existing_unique_translations.get(raw_ocr, "")))

        if clean_key not in unique_map:
            unique_map[clean_key] = {
                "Text_ID": f"TXT_{len(unique_map) + 1:03d}",
                "Clean_Original": clean_key,
                "Sample_Full_Original": orig,
                "Raw_OCR": raw_ocr,
                "Thai_Text": th_val,
                "Speaker": r.get("Speaker", ""),
                "Role": r.get("Role", ""),
                "Occurrences": 1,
                "Appears_In": [r.get("Image_Filename", "")]
            }
        else:
            unique_map[clean_key]["Occurrences"] += 1
            fn = r.get("Image_Filename", "")
            if fn and fn not in unique_map[clean_key]["Appears_In"]:
                unique_map[clean_key]["Appears_In"].append(fn)
            if not unique_map[clean_key]["Thai_Text"] and th_val:
                unique_map[clean_key]["Thai_Text"] = th_val

    unique_header = [
        "Text_ID", "Clean_Original", "Thai_Text", "Speaker", "Role", "Occurrences", "Appears_In", "Raw_OCR"
    ]
    rows_to_write = [{
        "Text_ID": v["Text_ID"],
        "Clean_Original": v["Clean_Original"],
        "Thai_Text": v["Thai_Text"],
        "Speaker": v["Speaker"],
        "Role": v["Role"],
        "Occurrences": v["Occurrences"],
        "Appears_In": ", ".join(v["Appears_In"]),
        "Raw_OCR": v["Raw_OCR"]
    } for v in unique_map.values()]

    safe_write_csv(out_unique, unique_header, rows_to_write)

    # Sync สำเนาไปยัง data/images/unique_dialogues.csv ด้วย
    proj_unique = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
    safe_copy_file(out_unique, proj_unique)

    print("=" * 80)
    print("🧩 DEDUPLICATION & TRANSLATION MEMORY CREATED")
    print(f"Total Dialogues Cataloged: {len(rows):,} bubbles")
    print(f"Unique Sentences:          {len(unique_map):,} unique lines")
    saved_percent = (1 - (len(unique_map) / max(1, len(rows)))) * 100
    print(f"⚡ Workload Reduced by:     {saved_percent:.1f}% (แปลเพียงครั้งเดียวต่อประโยค)")
    print(f"💾 Unique Translation Sheet: {out_unique}")
    print(f"   Project Copy:             {proj_unique}")
    print("=" * 80)


def run_propagate(unique_csv: Optional[str] = None, catalog_csv: Optional[str] = None):
    """
    กระจายคำแปลจาก unique_dialogues.csv กลับเข้าไปใน image_dialogues.csv ทุกรูปภาพโดยอัตโนมัติ
    """
    paths = resolve_workspace_paths()
    src_catalog = catalog_csv if catalog_csv else paths["catalog_csv"]
    if not os.path.exists(src_catalog):
        alt_catalog = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt_catalog):
            src_catalog = alt_catalog

    src_unique = unique_csv
    if not src_unique:
        src_unique = os.path.join(paths["images_base"], "unique_dialogues.csv")
    if not os.path.exists(src_unique):
        alt_unique = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
        if os.path.exists(alt_unique):
            src_unique = alt_unique

    if not os.path.exists(src_unique):
        print(f"❌ Unique translation sheet not found: {src_unique}")
        return
    if not os.path.exists(src_catalog):
        print(f"❌ Catalog CSV not found: {src_catalog}")
        return

    # อ่านคำแปลและการแก้ไขต้นฉบับจาก unique_dialogues.csv
    tm: Dict[str, str] = {}
    ocr_fixes: Dict[str, str] = {}
    with open(src_unique, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            clean_orig = r.get("Clean_Original", "").strip()
            raw_ocr = r.get("Raw_OCR", "").strip()
            th = r.get("Thai_Text", "").strip()
            if clean_orig:
                if th:
                    tm[clean_orig] = th
                if raw_ocr and raw_ocr != clean_orig:
                    # ผู้ใช้แก้ไขคำต้นฉบับโดยตรงใน unique_dialogues.csv!
                    ocr_fixes[raw_ocr] = clean_orig
                    if th:
                        tm[raw_ocr] = th

    # บันทึกกฎใหม่ลง ocr_corrections.json หากตรวจพบการแก้ไข
    if ocr_fixes:
        save_ocr_corrections(ocr_fixes)
        print(f"💡 Detected {len(ocr_fixes):,} manual OCR corrections in unique sheet. Synced to ocr_corrections.json.")

    # อัปเดตคำแปลกลับเข้า image_dialogues.csv ทุกแถว
    with open(src_catalog, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or CSV_HEADER
        rows = list(reader)

    corr = load_ocr_corrections()
    updated_count = 0
    text_fixed_count = 0
    for r in rows:
        orig = r.get("Original_Text", "").strip()
        clean_key = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', orig).strip()

        # นำเข้าการแก้ไขต้นฉบับ (จาก ocr_fixes หรือ normalize)
        fixed_orig = ocr_fixes.get(orig, ocr_fixes.get(clean_key, ""))
        if not fixed_orig:
            norm_test = ImageTextDetector.normalize_ocr_text(orig, custom_corrections=corr)
            if norm_test != orig:
                fixed_orig = norm_test

        if fixed_orig and fixed_orig != orig:
            r["Original_Text"] = fixed_orig
            orig = fixed_orig
            clean_key = re.sub(r'\s*\d{1,2}:\d{2}\s*$', '', orig).strip()
            text_fixed_count += 1

        if clean_key in tm:
            r["Thai_Text"] = tm[clean_key]
            updated_count += 1
        elif orig in tm:
            r["Thai_Text"] = tm[orig]
            updated_count += 1

    # บันทึกไฟล์กลับ
    safe_write_csv(src_catalog, fieldnames, rows)

    # Sync โปรเจกต์
    proj_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
    safe_copy_file(src_catalog, proj_csv)

    print("=" * 80)
    print("🚀 PROPAGATED TRANSLATIONS & OCR CORRECTIONS TO ALL OCCURRENCES")
    print(f"Unique Translations Found:   {len(tm):,} strings")
    if text_fixed_count > 0:
        print(f"Original Texts Corrected:    {text_fixed_count:,} rows")
    print(f"Catalog Translations Updated: {updated_count:,} / {len(rows):,} bubbles")
    print(f"Target Catalog:              {src_catalog}")
    print(f"Project Copy:                {proj_csv}")
    print("=" * 80)


def run_render(raw_dir: Optional[str] = None, catalog_csv: Optional[str] = None, rendered_dir: Optional[str] = None):
    """วาดข้อความภาษาไทยลงบนภาพด้วยความคมชัดระดับพิกเซล"""
    if not HAS_PIL:
        print("❌ Pillow (PIL) is not installed! Run: pip install Pillow")
        return

    paths = resolve_workspace_paths()
    src_raw = raw_dir if raw_dir else paths["raw_dir"]
    src_csv = catalog_csv if catalog_csv else paths["catalog_csv"]
    dest_rendered = rendered_dir if rendered_dir else paths["rendered_dir"]

    # ตรวจสอบ Fallback ถ้าไฟล์ใน output_dir ยังไม่มี
    if not os.path.exists(src_csv):
        alt_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt_csv):
            src_csv = alt_csv

    if not os.path.exists(src_raw) or not glob.glob(os.path.join(src_raw, "*.png")):
        alt_raw = os.path.join(BASE_DIR, "data", "images", "raw")
        if os.path.exists(alt_raw) and glob.glob(os.path.join(alt_raw, "*.png")):
            src_raw = alt_raw

    print("=" * 80)
    print("🎨 RENDERING THAI TYPOGRAPHY ONTO IMAGES")
    print(f"Raw Images Directory: {src_raw}")
    print(f"Catalog CSV:          {src_csv}")
    print(f"Rendered Output:      {dest_rendered}")
    print("=" * 80)

    if not os.path.exists(src_csv):
        print(f"❌ Catalog CSV not found: {src_csv}")
        return

    os.makedirs(dest_rendered, exist_ok=True)

    with open(src_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    grouped_by_file: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        fn = r.get("Image_Filename", "")
        if fn:
            grouped_by_file.setdefault(fn, []).append(r)

    rendered_count = 0
    for fname, boxes in grouped_by_file.items():
        src_png = os.path.join(src_raw, fname)
        if not os.path.exists(src_png):
            continue

        im = Image.open(src_png).convert("RGBA")
        draw = ImageDraw.Draw(im)

        for b in boxes:
            thai_text = b.get("Thai_Text", "").strip()
            # หากไม่มีคำแปล หรือระบุว่าไม่ต้องแปล (เช่น ปล่อยว่าง, SKIP, IGNORE, -) ให้ข้ามและคงภาพต้นฉบับไว้ 100%
            if not thai_text or thai_text.upper() in ("SKIP", "IGNORE", "NO", "NONE", "-", "--"):
                continue

            x = int(b.get("X", 0))
            y = int(b.get("Y", 0))
            w = int(b.get("Width", 100))
            h = int(b.get("Height", 50))
            text_color = b.get("Text_Color", "#333333")
            bg_color = (b.get("Bg_Color") or "#F7F7F7").strip()
            font_size = int(b.get("Font_Size", 13) or 13)
            stroke_width = int(b.get("Stroke_Width", 0) or 0)
            stroke_color = b.get("Stroke_Color", "").strip() or None
            alignment = (b.get("Alignment") or "left").strip().lower()
            role = b.get("Role", "Phone/Chat")

            # ตรวจสอบและแยกตัวเลขเวลาแชต (Timestamp เช่น 21:00, 19:42) ออกจากข้อความบทสนทนา
            timestamp = ""
            time_match = re.search(r'\s*(\d{1,2}:\d{2})\s*$', thai_text)
            if time_match:
                timestamp = time_match.group(1)
                dialogue_text = thai_text[:time_match.start()].strip()
            else:
                dialogue_text = thai_text

            # ดึงสีพื้นหลังและสีตัวหนังสือแบบอัตโนมัติ (ADR-033: Pixel-Level Harmony)
            final_bg, final_text, auto_stroke, auto_stroke_w = auto_detect_box_colors(
                im, x, y, w, h,
                csv_bg=bg_color,
                csv_text=text_color
            )

            # 1. ทำความสะอาดข้อความเดิมบนรูป (Pre-render Cleaning & Clean Inpainting)
            # ขยายขอบเขตการลบออกไป 3 พิกเซล เพื่อไม่ให้มีเศษตัวอักษรภาษาอังกฤษเดิมโผล่ขอบ
            erase_pad = 3
            erase_x1 = max(0, min(im.width, x - erase_pad))
            erase_y1 = max(0, min(im.height, y - erase_pad))
            erase_x2 = max(erase_x1, min(im.width, x + w + erase_pad))
            erase_y2 = max(erase_y1, min(im.height, y + h + erase_pad))

            if erase_x2 <= erase_x1 or erase_y2 <= erase_y1:
                continue

            if (len(final_bg) >= 4 and final_bg[3] == 0) or bg_color.lower() in ["clear", "transparent", "alpha"]:
                clear_box = Image.new("RGBA", (max(1, erase_x2 - erase_x1), max(1, erase_y2 - erase_y1)), (0, 0, 0, 0))
                im.paste(clear_box, (erase_x1, erase_y1))
            elif bg_color.lower() in ["none", "stroke_only"]:
                pass
            else:
                draw.rectangle([erase_x1, erase_y1, erase_x2, erase_y2], fill=final_bg)

            # 2. ปรับลดขนาดฟอนต์แบบ Adaptive ไม่ให้ล้นกรอบหรือทับ UI (Fit-to-Box)
            pad_x = 8
            pad_y = 6
            avail_w = max(30, w - (pad_x * 2))
            avail_h = max(20, h - (pad_y * 2))

            font, wrapped_text, used_size = fit_thai_text_to_box(
                dialogue_text,
                avail_w=avail_w,
                avail_h=avail_h,
                desired_font_size=font_size,
                draw=draw
            )

            # 3. คำนวณตำแหน่งพิกัดและจุดยึด (Alignment: left, center, right)
            if alignment == "center":
                draw_pos = (x + w // 2, y + pad_y)
                anchor = "ma"
            elif alignment == "right":
                draw_pos = (x + w - pad_x, y + pad_y)
                anchor = "ra"
            else:
                draw_pos = (x + pad_x, y + pad_y)
                anchor = "la"

            # 4. วาดตัวหนังสือภาษาไทยพร้อมขอบตัวอักษร (Stroke/Outline) คมชัด
            eff_stroke_w = stroke_width if stroke_width > 0 else auto_stroke_w
            eff_stroke_color = stroke_color if stroke_color else auto_stroke

            draw.text(
                draw_pos,
                wrapped_text,
                fill=final_text,
                font=font,
                spacing=2,
                stroke_width=eff_stroke_w,
                stroke_fill=eff_stroke_color,
                anchor=anchor,
                align=alignment
            )

            # 5. วาดตัวเลขเวลาแชต (Timestamp) แยกต่างหากที่มุมขวาล่างของกล่องแชต
            if timestamp:
                time_font = get_thai_font(size=max(9, used_size - 3))
                bg_is_light = (0.299 * final_bg[0] + 0.587 * final_bg[1] + 0.114 * final_bg[2] > 120)
                time_color = "#8E8E93" if bg_is_light else "#CCCCCC"
                draw.text(
                    (x + w - 38, y + h - 16),
                    timestamp,
                    fill=time_color,
                    font=time_font
                )

        out_path = os.path.join(dest_rendered, fname)
        im.save(out_path, "PNG")
        rendered_count += 1

        # Sync สำเนาไปยัง data/images/translated ในโปรเจกต์ด้วยเพื่อความสะดวกในการเปิดดู
        proj_rendered = os.path.join(BASE_DIR, "data", "images", "translated")
        if os.path.abspath(dest_rendered) != os.path.abspath(proj_rendered):
            os.makedirs(proj_rendered, exist_ok=True)
            im.save(os.path.join(proj_rendered, fname), "PNG")

        print(f"  ✅ Rendered: {fname}")

    print(f"\n🎉 Successfully rendered {rendered_count:,} translated images into: {dest_rendered}")
    proj_rendered = os.path.join(BASE_DIR, "data", "images", "translated")
    if os.path.exists(proj_rendered):
        print(f"   Project Copy: {proj_rendered}")


def run_encrypt(rendered_dir: Optional[str] = None, target_dir: Optional[str] = None, folder: str = "pictures"):
    """เข้ารหัสภาพ .png ภาษาไทยกลับเป็น .rpgmvp แล้วนำไปใส่ในเกมจริง"""
    paths = resolve_workspace_paths(folder=folder)
    key = paths["key"]
    src_rendered = rendered_dir if rendered_dir else paths["rendered_dir"]
    dest_pictures = target_dir if target_dir else paths["pictures_dir"]

    if not key:
        print("❌ Could not locate encryption key in System.json!")
        return

    # Fallback ถ้า rendered_dir ใน output_dir ไม่มี
    if not os.path.exists(src_rendered) or not glob.glob(os.path.join(src_rendered, "*.png")):
        alt_rendered = os.path.join(BASE_DIR, "data", "images", "translated")
        if os.path.exists(alt_rendered) and glob.glob(os.path.join(alt_rendered, "*.png")):
            src_rendered = alt_rendered

    print("=" * 80)
    print(f"🔒 ENCRYPTING & INJECTING TRANSLATED IMAGES (.png -> .rpgmvp) [FOLDER: {folder}]")
    print(f"Rendered PNGs Directory: {src_rendered}")
    print(f"Destination Pictures:   {dest_pictures}")
    print("=" * 80)

    png_files = glob.glob(os.path.join(src_rendered, "*.png"))
    print(f"📦 Found {len(png_files):,} images ready to encrypt.")

    game_img_root = os.path.join(paths["game_dir"], "www", "img")
    if not os.path.exists(game_img_root):
        game_img_root = os.path.join(paths["game_dir"], "img")

    encrypted_count = 0
    for f in png_files:
        base_name = os.path.splitext(os.path.basename(f))[0]
        out_rpgmvp = os.path.join(dest_pictures, f"{base_name}.rpgmvp")

        # ตรวจสอบค้นหาตำแหน่งโฟลเดอร์ต้นฉบับจริงในเกมอัตโนมัติ (เช่น pictures, system, titles1 ฯลฯ)
        if not os.path.exists(out_rpgmvp) and os.path.exists(game_img_root):
            for root_dir, _, files in os.walk(game_img_root):
                if f"{base_name}.rpgmvp" in files:
                    out_rpgmvp = os.path.join(root_dir, f"{base_name}.rpgmvp")
                    break

        # สำรองไฟล์เดิมไว้ก่อนเสมอ
        if os.path.exists(out_rpgmvp) and not os.path.exists(f"{out_rpgmvp}.bak_orig"):
            shutil.copy2(out_rpgmvp, f"{out_rpgmvp}.bak_orig")

        ok = RPGMImageCrypto.encrypt_file(f, out_rpgmvp, key)
        if ok:
            encrypted_count += 1
            rel_path = os.path.relpath(out_rpgmvp, paths["game_dir"])
            print(f"  💉 Injected into game: {rel_path}")

    print(f"\n🎉 ALL {encrypted_count:,} IMAGES ENCRYPTED & INJECTED INTO GAME SUCCESSFULLY 100%!")


def run_scan(folder: Optional[str] = None, category: str = "all", auto_decrypt: bool = False, auto_catalog: bool = False, game_dir_override: Optional[str] = None, engine: str = "auto"):
    """
    Universal Deep Asset Scanner (ADR-028, ADR-029 & ADR-030 Compliant):
    สแกนลึกค้นหาเฉพาะไฟล์ภาพที่มีตัวหนังสือจริง (Human-Visible Game Text):
    1. Asset Domain Whitelisting: โฟกัสเฉพาะโฟลเดอร์ภาพที่เกี่ยวข้องกับการเล่าเรื่อง/UI (pictures, system, titles1, SumRndmDde)
       ตัดโฟลเดอร์ animations (เอฟเฟกต์ต่อสู้), characters (สไปรต์ตัวละคร), tilesets (ไทล์ฉาก) ออกล่วงหน้า 100%
    2. Asset Domain Exclusion: คัดกรองชื่อไฟล์สไปรต์ (!$*, $*), ไทล์ฉาก, และเอฟเฟกต์ (Hit, Explosion, Flame) ออกทันที
    3. Human-Vision Lexical Validator: ตรวจสอบความถูกต้องทางภาษา (ตัดตัวอักษรจีน/สัญลักษณ์หลอน เช่น 米, 十, X, 2 ออกเด็ดขาด)
    """
    import io

    paths = resolve_workspace_paths(game_dir_override=game_dir_override)
    key = paths["key"]
    game_dir = paths["game_dir"]
    target_out = paths["raw_dir"]
    img_root = os.path.join(game_dir, "www", "img")
    if not os.path.exists(img_root):
        img_root = os.path.join(game_dir, "img")
    if not os.path.exists(img_root) and os.path.exists(os.path.join(game_dir, "pictures")):
        img_root = game_dir

    print("=" * 80)
    print("🔍 UNIVERSAL GAME IMAGE TEXT SCANNER (HUMAN-VISION ENGINE)")
    print(f"Game Img Root:    {img_root}")
    print(f"Filter Category:  {category.upper()}")
    print(f"Engine:           {engine.upper()}")
    print(f"Auto Decrypt:     {'YES (Decrypted to raw/)' if auto_decrypt else 'NO (Preview only)'}")
    print("=" * 80)

    # ค้นหาไดเรกทอรีภาพเฉพาะที่เกี่ยวข้องกับตัวหนังสือในเกม
    target_dirs = []
    if folder:
        target_dirs.append(os.path.join(img_root, folder))
    else:
        # สแกนเฉพาะโฟลเดอร์ที่มีตัวหนังสือบทสนทนาหรือ UI ใน RPG Maker (Asset Domain Whitelisting)
        text_eligible_folders = ["pictures", "system", "titles1", "titles2", "SumRndmDde"]
        for dname in text_eligible_folders:
            candidate = os.path.join(img_root, dname)
            if os.path.exists(candidate):
                target_dirs.append(candidate)
        if not target_dirs:
            non_text_dirs = {"animations", "characters", "tilesets", "faces", "enemies", "sv_actors", "sv_enemies", "battlebacks1", "battlebacks2", "parallaxes"}
            for root, dirs, files in os.walk(img_root):
                rel = os.path.relpath(root, img_root).lower().replace("\\", "/")
                top_folder = rel.split("/")[0]
                if top_folder in non_text_dirs:
                    continue
                if any(f.endswith((".rpgmvp", ".png", ".jpg", ".webp")) for f in files):
                    target_dirs.append(root)

    all_image_paths = []
    for d in target_dirs:
        for ext in ("*.rpgmvp", "*.png"):
            all_image_paths.extend(glob.glob(os.path.join(d, ext)))

    # คัดกรองชื่อไฟล์ที่เป็น Character Sprite / Battle Animation / Tileset ออกล่วงหน้า 100%
    all_image_paths = [p for p in all_image_paths if ImageTextDetector.is_text_eligible_filename(p)]
    all_image_paths = sorted(list(set(all_image_paths)))
    print(f"\n📦 FOUND {len(all_image_paths):,} ELIGIBLE IMAGE FILES FOR TEXT SCANNING.")
    use_rapid = ImageTextDetector.is_rapidocr_available()
    if engine.lower() == "windows":
        print("🚀 ACTIVE ENGINE: Windows Native OCR (Snipping Tool Engine)")
    elif use_rapid:
        print("🚀 ACTIVE ENGINE: RapidOCR with Human-Vision Lexical Validator")
        print("   Mode: Direct In-Memory Scanning (Zero False Positives for CG/Sprites)")
    else:
        print("⚠️ NOTICE: RapidOCR not available. Using Windows Native OCR...")

    confirmed_images: List[Dict[str, Any]] = []
    rejected_count = 0
    total_imgs = len(all_image_paths)

    classified_files: Dict[str, List[Dict[str, Any]]] = {
        "phone": [],
        "ui": [],
        "tutorial": []
    }

    # สแกนภาพทั้งหมดใน RAM โดยตรง
    for idx, img_path in enumerate(all_image_paths, 1):
        rel_name = os.path.relpath(img_path, img_root)
        try:
            with open(img_path, "rb") as f:
                raw_bytes = f.read()

            if img_path.endswith(".rpgmvp"):
                if not key:
                    continue
                png_bytes = RPGMImageCrypto.decrypt_bytes(raw_bytes, key)
            else:
                png_bytes = raw_bytes

            ocr_res = ImageTextDetector.detect_text(png_bytes, min_score=0.65, engine=engine)
            lines = ocr_res.get("lines", [])

            if ocr_res.get("has_text") and lines:
                item = {
                    "rel_name": rel_name,
                    "path": img_path,
                    "bytes": png_bytes,
                    "lines": lines,
                    "lines_count": len(lines),
                    "ocr_score": max([l.get("confidence", 0.0) for l in lines] or [0.0])
                }
                confirmed_images.append(item)

                # จำแนกหมวดหมู่
                all_text = " ".join([l.get("text", "") for l in lines if isinstance(l, dict)]).lower()
                if len(lines) >= 2 or any(k in all_text for k in [":", "msg", "chat", "hey", "hello", "where", "you", "thanks"]):
                    classified_files["phone"].append(item)
                elif len(lines) == 1 and len(all_text) <= 25:
                    classified_files["ui"].append(item)
                else:
                    classified_files["tutorial"].append(item)
            else:
                rejected_count += 1
        except Exception:
            rejected_count += 1

        if idx % 50 == 0 or idx == total_imgs:
            print(f"  [{idx:,}/{total_imgs:,}] Text Images Found: {len(confirmed_images):,} | CG/Sprites Excluded: {rejected_count:,}")

    # สรุปผลการค้นหา
    print("=" * 80)
    print(f"🎯 CONFIRMED TEXT-BEARING IMAGES: {len(confirmed_images):,} files found across game!")
    print("=" * 80)

    print(f"📱 1. PHONE & CHAT APPS / DIALOGUES: {len(classified_files['phone']):,} files")
    for it in classified_files["phone"][:15]:
        sample_txt = ""
        if it["lines"] and isinstance(it["lines"][0], dict):
            sample_txt = f' -> "{it["lines"][0].get("text", "")}"'
        print(f"   - {it['rel_name']} ({it['lines_count']} lines){sample_txt}")
    if len(classified_files["phone"]) > 15:
        print(f"   ... and {len(classified_files['phone']) - 15} more")

    print(f"\n🎮 2. SYSTEM UI & MENUS & BUTTONS: {len(classified_files['ui']):,} files")
    for it in classified_files["ui"][:15]:
        sample_txt = ""
        if it["lines"] and isinstance(it["lines"][0], dict):
            sample_txt = f' -> "{it["lines"][0].get("text", "")}"'
        print(f"   - {it['rel_name']} ({it['lines_count']} lines){sample_txt}")
    if len(classified_files["ui"]) > 15:
        print(f"   ... and {len(classified_files['ui']) - 15} more")

    print(f"\n📖 3. TUTORIALS & GUIDE SCREENS: {len(classified_files['tutorial']):,} files")
    for it in classified_files["tutorial"][:10]:
        sample_txt = ""
        if it["lines"] and isinstance(it["lines"][0], dict):
            sample_txt = f' -> "{it["lines"][0].get("text", "")}"'
        print(f"   - {it['rel_name']} ({it['lines_count']} lines){sample_txt}")
    if len(classified_files["tutorial"]) > 10:
        print(f"   ... and {len(classified_files['tutorial']) - 10} more")
    print("=" * 80)

    # เลือกไฟล์เป้าหมายตามหมวดหมู่
    if category == "phone":
        selected_items = classified_files["phone"]
    elif category == "ui":
        selected_items = classified_files["ui"]
    elif category == "tutorial":
        selected_items = classified_files["tutorial"]
    else:
        selected_items = confirmed_images

    print(f"\n🎯 Selected for Action [{category.upper()}]: {len(selected_items):,} verified text-bearing files")

    if auto_decrypt:
        print("\n" + "=" * 80)
        print(f"🚀 AUTO-DECRYPTING {len(selected_items):,} VERIFIED TEXT IMAGES INTO WORKSPACE...")
        print(f"Target Directory: {target_out}")
        print("=" * 80)
        os.makedirs(target_out, exist_ok=True)
        proj_raw = os.path.join(BASE_DIR, "data", "images", "raw")
        os.makedirs(proj_raw, exist_ok=True)

        for it in selected_items:
            fname = os.path.basename(it["path"])
            png_name = os.path.splitext(fname)[0] + ".png"
            dest_png = os.path.join(target_out, png_name)
            with open(dest_png, "wb") as f:
                f.write(it["bytes"])
            # Sync to project raw
            if os.path.abspath(target_out) != os.path.abspath(proj_raw):
                with open(os.path.join(proj_raw, png_name), "wb") as f:
                    f.write(it["bytes"])

        print(f"🎉 Successfully saved {len(selected_items):,} verified images to: {target_out}")
        print(f"   Project Copy: {proj_raw}")

        # รัน Catalog และ Dedupe
        print("\n⚡ Generating dialogue catalog CSV and unique translation memory sheet with real text...")
        run_catalog(raw_dir=target_out, scanned_items=selected_items, engine=engine)
    else:
        print("\n💡 TIP: Run with '--decrypt' to decrypt all verified files and generate the CSV translation sheet immediately:")
        print(f"   python localize_images.py scan --category {category} --decrypt")
        print("   python localize_images.py scan --all --decrypt")


def run_purge(catalog_csv: Optional[str] = None):
    """
    คัดกรองและล้างข้อมูลขยะ (False-Positive Noise Purge):
    กำจัดแถวที่เป็นเศษกราฟิก สไปรต์ตัวละคร เอฟเฟกต์ต่อสู้ และตัวอักษรหลอน (米, 十, e, X)
    ออกจาก image_dialogues.csv และ unique_dialogues.csv ทั้งหมดอย่างสมบูรณ์
    """
    paths = resolve_workspace_paths()
    src_csv = catalog_csv if catalog_csv else paths["catalog_csv"]
    if not os.path.exists(src_csv):
        alt = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt):
            src_csv = alt

    if not os.path.exists(src_csv):
        print(f"❌ Catalog CSV not found: {src_csv}")
        return

    with open(src_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    initial_count = len(rows)
    clean_rows = []
    purged_files = set()

    for r in rows:
        fname = r.get("Image_Filename", "").strip()
        txt = r.get("Original_Text", "").strip()
        if not ImageTextDetector.is_text_eligible_filename(fname):
            purged_files.add(fname)
            continue
        if not ImageTextDetector.is_valid_game_text(txt):
            purged_files.add(fname)
            continue
        clean_rows.append(r)

    # บันทึกไฟล์กลับ
    safe_write_csv(src_csv, CSV_HEADER, clean_rows)

    proj_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
    safe_copy_file(src_csv, proj_csv)

    print("=" * 80)
    print("🧹 PURGED ALL FALSE-POSITIVE NOISE FROM DIALOGUE CATALOG")
    print(f"Initial Rows:       {initial_count:,}")
    print(f"Purged Noise Rows:  {initial_count - len(clean_rows):,} rows across {len(purged_files):,} non-text images")
    print(f"Remaining Clean:    {len(clean_rows):,} verified dialogue entries")
    print(f"Target Catalog:     {src_csv}")
    print(f"Project Copy:       {proj_csv}")
    print("=" * 80)

    # สั่ง dedupe ใหม่ทันทีเพื่ออัปเดต unique_dialogues.csv ให้สะอาด 100%
    run_dedupe(catalog_csv=src_csv)


def run_sync(raw_dir: Optional[str] = None, catalog_csv: Optional[str] = None):
    """
    ซิงค์ข้อมูลระหว่างโฟลเดอร์ภาพ raw/ กับ Spreadsheet (Disk-to-Spreadsheet Sync):
    1. ผู้ใช้สามารถลบไฟล์ภาพที่ไม่ต้องการแปลออกจาก raw/ ใน File Explorer ได้ตามสบาย
    2. คำสั่งนี้จะตรวจสอบภาพที่เหลืออยู่จริงบนดิสก์
    3. ลบแถวของภาพที่ถูกตัดทิ้งออกจาก image_dialogues.csv ทันที 100%
    4. รัน dedupe เพื่อให้ unique_dialogues.csv สะอาดหมดจด ไร้ข้อความตกค้างจากภาพที่ถูกลบ
    """
    paths = resolve_workspace_paths()
    src_raw = raw_dir if raw_dir else paths["raw_dir"]
    out_csv = catalog_csv if catalog_csv else paths["catalog_csv"]

    if not os.path.exists(src_raw) or not glob.glob(os.path.join(src_raw, "*.png")):
        alt_raw = os.path.join(BASE_DIR, "data", "images", "raw")
        if os.path.exists(alt_raw) and glob.glob(os.path.join(alt_raw, "*.png")):
            src_raw = alt_raw

    if not os.path.exists(out_csv):
        alt_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt_csv):
            out_csv = alt_csv

    if not os.path.exists(out_csv):
        print(f"❌ Catalog CSV not found: {out_csv}")
        return

    # อ่านรายชื่อไฟล์รูปภาพจริงที่มีอยู่บนดิสก์
    raw_files = set(os.path.basename(p) for p in glob.glob(os.path.join(src_raw, "*.png")))

    with open(out_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    initial_count = len(rows)
    kept_rows = []
    purged_files = set()

    for r in rows:
        fn = r.get("Image_Filename", "").strip()
        # ถ้าไม่มีไฟล์นี้ใน raw/ แล้ว (ผู้ใช้ลบทิ้ง) ให้ตัดทิ้ง
        if fn not in raw_files:
            purged_files.add(fn)
            continue
        kept_rows.append(r)

    # บันทึกไฟล์กลับอย่างปลอดภัย (ทนทานต่อการถูกเปิดค้างไว้ใน Microsoft Excel)
    safe_write_csv(out_csv, CSV_HEADER, kept_rows)

    proj_csv = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
    safe_copy_file(out_csv, proj_csv)

    print("=" * 80)
    print("🧹 DISK-TO-SPREADSHEET SYNCHRONIZATION COMPLETE")
    print(f"Active Raw Images on Disk:   {len(raw_files):,} images in {src_raw}")
    print(f"Purged Removed Images:      {len(purged_files):,} images removed from spreadsheet")
    if purged_files:
        sample_purged = sorted(list(purged_files))[:10]
        print(f"   Sample purged: {', '.join(sample_purged)}")
        if len(purged_files) > 10:
            print(f"   ... and {len(purged_files) - 10} more")
    print(f"Remaining Dialogue Rows:     {len(kept_rows):,} rows in {os.path.basename(out_csv)}")
    print("=" * 80)

    # รัน dedupe เพื่อให้ unique_dialogues.csv สะอาดหมดจด
    print("\n⚡ Updating unique translation sheet to purge orphan texts...")
    run_dedupe(catalog_csv=out_csv)


def run_repair(catalog_csv: Optional[str] = None, unique_csv: Optional[str] = None):
    """
    ซ่อมแซมและปรับปรุงคำผิดจาก OCR ในไฟล์ Spreadsheet ทั้งหมดอัตโนมัติ (ADR-032):
    1. แก้ปัญหา homoglyphs (เช่น 1unch -> lunch, l was -> I was, shell enjoy -> she'll enjoy)
    2. แก้ปัญหาขาดช่องว่างหลังเครื่องหมายวรรคตอน (Punctuation Spacing: there,Dan -> there, Dan)
    3. แก้ปัญหาคำย่อภาษาอังกฤษขาด Apostrophe (เช่น Ive -> I've, dont -> don't, cant -> can't)
    4. ตัดแยกคำที่ OCR ติดกันเป็นพืดตามพจนานุกรมเกม (tohate -> to hate, ina -> in a, ฯลฯ)
    5. ประยุกต์ใช้กฎจาก ocr_corrections.json และอัปเดตไฟล์กลับอย่างปลอดภัย
    """
    paths = resolve_workspace_paths()
    src_catalog = catalog_csv if catalog_csv else paths["catalog_csv"]
    if not os.path.exists(src_catalog):
        alt_catalog = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        if os.path.exists(alt_catalog):
            src_catalog = alt_catalog

    src_unique = unique_csv if unique_csv else os.path.join(paths["images_base"], "unique_dialogues.csv")
    if not os.path.exists(src_unique):
        alt_unique = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
        if os.path.exists(alt_unique):
            src_unique = alt_unique

    corr = load_ocr_corrections()
    print("=" * 80)
    print("🔧 OCR LEXICAL REPAIR & HOMOGLYPH DE-CONFUSION ENGINE (ADR-032)")
    print(f"Catalog CSV:  {src_catalog}")
    print(f"Unique CSV:   {src_unique}")
    print(f"Loaded Rules: {len(corr):,} exact replacements from ocr_corrections.json")
    print("=" * 80)

    # 1. ซ่อมแซม image_dialogues.csv
    repaired_catalog = 0
    catalog_changes = []
    if os.path.exists(src_catalog):
        with open(src_catalog, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or CSV_HEADER
            rows = list(reader)

        for r in rows:
            orig = r.get("Original_Text", "")
            if not orig:
                continue
            fixed = ImageTextDetector.normalize_ocr_text(orig, custom_corrections=corr)
            if fixed != orig:
                catalog_changes.append((orig, fixed))
                r["Original_Text"] = fixed
                repaired_catalog += 1

        safe_write_csv(src_catalog, fieldnames, rows)
        proj_cat = os.path.join(BASE_DIR, "data", "images", "image_dialogues.csv")
        safe_copy_file(src_catalog, proj_cat)

    # 2. ซ่อมแซม unique_dialogues.csv
    repaired_unique = 0
    unique_changes = []
    if os.path.exists(src_unique):
        with open(src_unique, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            unique_fieldnames = reader.fieldnames or ["Text_ID", "Clean_Original", "Thai_Text", "Speaker", "Role", "Occurrences", "Appears_In", "Raw_OCR"]
            if "Raw_OCR" not in unique_fieldnames:
                unique_fieldnames.append("Raw_OCR")
            u_rows = list(reader)

        for ur in u_rows:
            clean = ur.get("Clean_Original", "")
            if not clean:
                continue
            if not ur.get("Raw_OCR"):
                ur["Raw_OCR"] = clean
            fixed = ImageTextDetector.normalize_ocr_text(clean, custom_corrections=corr)
            if fixed != clean:
                unique_changes.append((clean, fixed))
                ur["Clean_Original"] = fixed
                repaired_unique += 1

        safe_write_csv(src_unique, unique_fieldnames, u_rows)
        proj_unq = os.path.join(BASE_DIR, "data", "images", "unique_dialogues.csv")
        safe_copy_file(src_unique, proj_unq)

    print(f"✅ Catalog Rows Repaired: {repaired_catalog:,} rows")
    print(f"✅ Unique Texts Repaired: {repaired_unique:,} rows")
    if unique_changes:
        print("\n📋 Sample Repaired Texts:")
        for idx, (old_t, new_t) in enumerate(unique_changes[:15], 1):
            print(f"  [{idx:02d}] ❌ \"{old_t}\"")
            print(f"       👉 \"{new_t}\"")
        if len(unique_changes) > 15:
            print(f"  ... and {len(unique_changes) - 15} more corrections applied.")
    print("=" * 80)


# ==============================================================================
# MAIN CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="ATF Image & Phone Chat Localization Engine (ADR-024 / ADR-026 / ADR-030 / ADR-031 / ADR-032)")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. Scan
    p_scan = subparsers.add_parser("scan", help="Deep scan game image directories for phone chats, UI, and tutorials")
    p_scan.add_argument("--folder", default=None, help="Specific img folder to scan (e.g. pictures, system, SumRndmDde, titles1)")
    p_scan.add_argument("--category", default="all", choices=["all", "phone", "ui", "tutorial"], help="Filter category (default: all)")
    p_scan.add_argument("--all", dest="all_cat", action="store_true", help="Scan and include all categories")
    p_scan.add_argument("--decrypt", action="store_true", help="Auto-decrypt all discovered images directly into raw directory")
    p_scan.add_argument("--game-dir", default=None, help="Game root directory override (e.g. path containing www/ or img/)")
    p_scan.add_argument("--engine", default="auto", choices=["auto", "rapidocr", "windows"], help="OCR Engine (default: auto)")

    # 2. Decrypt
    p_dec = subparsers.add_parser("decrypt", help="Decrypt .rpgmvp to .png")
    p_dec.add_argument("--pattern", default="*", help="Filename pattern to match (e.g. RVPhone*, *Tutorial*, *MENU*, GameOver*)")
    p_dec.add_argument("--folder", default="pictures", help="Game img folder (e.g. pictures, system, titles1, SumRndmDde/choices, all)")
    p_dec.add_argument("--out", default=None, help="Output directory for decrypted PNGs (default: <output_dir>/images/raw)")
    p_dec.add_argument("--catalog", action="store_true", help="Auto-generate CSV catalog after decrypting")

    # 3. Catalog
    p_cat = subparsers.add_parser("catalog", help="Generate real dialogue CSV catalog for decrypted images")
    p_cat.add_argument("--raw", default=None, help="Directory of raw decrypted PNGs")
    p_cat.add_argument("--csv", default=None, help="Catalog CSV path (default: <output_dir>/images/image_dialogues.csv)")
    p_cat.add_argument("--with-translations", action="store_true", help="Include preset translations (default: False)")
    p_cat.add_argument("--engine", default="auto", choices=["auto", "rapidocr", "windows"], help="OCR Engine (default: auto)")
    p_cat.add_argument("--rebuild", action="store_true", help="Re-scan and merge text lines into coherent paragraphs/speech bubbles")

    # 4. Dedupe (Extract Unique Text Translation Sheet)
    p_ded = subparsers.add_parser("dedupe", help="Extract unique texts into unique_dialogues.csv for single-time translation")
    p_ded.add_argument("--csv", default=None, help="Source catalog CSV")
    p_ded.add_argument("--out", default=None, help="Output unique CSV path (default: <output_dir>/images/unique_dialogues.csv)")

    # 5. Propagate (Apply Translations back to Catalog)
    p_prp = subparsers.add_parser("propagate", help="Propagate translations from unique sheet to all image catalog rows")
    p_prp.add_argument("--unique", default=None, help="Source unique dialogues CSV with translations")
    p_prp.add_argument("--catalog", default=None, help="Target catalog CSV to update")

    # 6. Render
    p_ren = subparsers.add_parser("render", help="Render translated Thai text onto images")
    p_ren.add_argument("--raw", default=None, help="Directory of raw decrypted PNGs")
    p_ren.add_argument("--csv", default=None, help="Catalog CSV with Thai translations")
    p_ren.add_argument("--out", default=None, help="Output directory for rendered PNGs")

    # 7. Encrypt
    p_enc = subparsers.add_parser("encrypt", help="Re-encrypt rendered PNGs back to .rpgmvp and deploy to game")
    p_enc.add_argument("--rendered", default=None, help="Directory of translated PNGs")
    p_enc.add_argument("--folder", default="pictures", help="Target game img folder (e.g. pictures, system, titles1, SumRndmDde/choices)")
    p_enc.add_argument("--target", default=None, help="Target game directory override (optional)")

    # 8. Clean / Purge Noise
    p_clean = subparsers.add_parser("clean", help="Purge all false-positive noise, sprite sheets, battle animations, and CJK hallucinations")
    p_clean.add_argument("--csv", default=None, help="Catalog CSV path to clean")

    # 9. Sync (Synchronize Spreadsheet with raw/ on Disk)
    p_sync = subparsers.add_parser("sync", help="Synchronize spreadsheets with raw/ on Disk (purge deleted images and orphan texts)")
    p_sync.add_argument("--raw", default=None, help="Directory of raw decrypted PNGs")
    p_sync.add_argument("--csv", default=None, help="Catalog CSV path")

    # 10. Repair (OCR Lexical Repair & Homoglyph De-confusion - ADR-032)
    p_rep = subparsers.add_parser("repair", help="Auto-repair OCR typos, missing spaces, homoglyphs, and sync corrections (ADR-032)")
    p_rep.add_argument("--catalog", default=None, help="Catalog CSV path")
    p_rep.add_argument("--unique", default=None, help="Unique dialogues CSV path")

    args = parser.parse_args()

    if args.command == "scan":
        cat = "all" if getattr(args, "all_cat", False) else args.category
        run_scan(folder=args.folder, category=cat, auto_decrypt=args.decrypt, game_dir_override=getattr(args, "game_dir", None), engine=getattr(args, "engine", "auto"))
    elif args.command == "decrypt":
        run_decrypt(pattern=args.pattern, output_dir=args.out, folder=args.folder, auto_catalog=args.catalog)
    elif args.command == "catalog":
        run_catalog(raw_dir=args.raw, catalog_csv=args.csv, with_translations=args.with_translations, engine=getattr(args, "engine", "auto"), rebuild=getattr(args, "rebuild", False))
    elif args.command == "dedupe":
        run_dedupe(catalog_csv=args.csv, output_unique_csv=args.out)
    elif args.command == "propagate":
        run_propagate(unique_csv=args.unique, catalog_csv=args.catalog)
    elif args.command == "render":
        run_render(raw_dir=args.raw, catalog_csv=args.csv, rendered_dir=args.out)
    elif args.command == "encrypt":
        run_encrypt(rendered_dir=args.rendered, target_dir=args.target, folder=args.folder)
    elif args.command == "clean":
        run_purge(catalog_csv=args.csv)
    elif args.command == "sync":
        run_sync(raw_dir=args.raw, catalog_csv=args.csv)
    elif args.command == "repair":
        run_repair(catalog_csv=args.catalog, unique_csv=args.unique)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
