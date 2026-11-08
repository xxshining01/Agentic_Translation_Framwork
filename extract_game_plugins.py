#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone RPG Maker Plugin Text Extractor
==============================================================
เครื่องมือสกัดข้อความส่วนติดต่อผู้ใช้ (UI Strings / Menu Texts) จากปลั๊กอินทุกตัวของเกม
ออกแบบมาสำหรับเตรียมไฟล์ `plugins_texts.csv` ก่อนเริ่มโปรเจกต์ ATF

การทำงาน:
  1. ถามหาโฟลเดอร์เกมต้นทาง (Game Directory)
  2. ตรวจหาโฟลเดอร์ /js อัตโนมัติ (รองรับทั้ง www/js และ js)
  3. สแกนและสกัดข้อความ UI จาก:
     - www/js/plugins.js (ค่าพารามิเตอร์ของปลั๊กอินทั้งหมด รวมถึง Nested JSON)
     - www/js/plugins/*.js (ข้อความภาษาและคำสั่ง UI ที่ฮาร์ดโค้ดในซอร์สโค้ดปลั๊กอิน)
  4. แสดงสรุปผลลัพธ์ และถามหาตำแหน่งบันทึกไฟล์ plugins_text.csv ปลายทาง
  5. บันทึกไฟล์ CSV มาตรฐานพร้อมสำหรับนำไปใช้กับ `python atf.py setup`
"""

import os
import sys
import re
import csv
import json
import argparse
import io
from typing import List, Dict, Tuple, Optional, Any, Set, Union

# กำหนด Console Encoding ให้รองรับภาษาไทยและ CJK ป้องกัน UnicodeEncodeError บน Windows
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


class RecursiveJsonUnpacker:
    """โมดูลแกะข้อมูล JSON ที่ซ้อนทับกันหลายชั้นใน parameters ของ plugins.js"""
    @classmethod
    def is_json_string(cls, val: Any) -> bool:
        if not isinstance(val, str):
            return False
        stripped = val.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]"))

    @classmethod
    def unpack(cls, data: Any, current_path: List[Union[str, int]]) -> List[Tuple[List[Union[str, int]], str]]:
        results: List[Tuple[List[Union[str, int]], str]] = []

        if isinstance(data, dict):
            for k, v in data.items():
                new_path = current_path + [k]
                if cls.is_json_string(v):
                    try:
                        parsed = json.loads(v)
                        results.extend(cls.unpack(parsed, new_path))
                        continue
                    except Exception:
                        pass
                results.extend(cls.unpack(v, new_path))
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                new_path = current_path + [idx]
                if cls.is_json_string(item):
                    try:
                        parsed = json.loads(item)
                        results.extend(cls.unpack(parsed, new_path))
                        continue
                    except Exception:
                        pass
                results.extend(cls.unpack(item, new_path))
        elif isinstance(data, str):
            if data.strip():
                results.append((current_path, data))

        return results


class SemanticParameterClassifier:
    """โมดูลคัดกรองความปลอดภัย: สกัดเฉพาะ Human-Readable UI Text ออกจากโค้ดและคอนฟิกเทคนิค"""
    DISALLOWED_KEY_SUFFIXES: Set[str] = {
        ":bool", ":css", ":color", ":file", ":img", ":image",
        ":variable", ":switch", ":id", ":i", ":e"
    }

    SYSTEM_KEYS_BLACKLIST: Set[str] = {
        "name", "status", "description", "folder", "filename", "skin",
        "fontFace", "formula", "renderingMode", "alwaysDash", "key",
        "right click", "show on new page", "pause until visible",
        "redZoneFillColor:str", "backColor:css", "mask", "fill", "foreground"
    }

    JAVASCRIPT_CODE_PATTERNS: List[str] = [
        r"Graphics\.", r"Window_Base\.", r"\.prototype\.",
        r"\bfunction\b", r"=>", r"[+\-*/]\s*\d+", r"===|!==|&&|\|\|",
        r"^#[0-9a-fA-F]{3,8}$", r"^rgba?\(",
        r"^(?:true|false|auto|left|center|right|on|off|control|shift|alt|tab|enter|escape|space|relative|absolute)$"
    ]

    ALLOWED_KEY_KEYWORDS: List[str] = [
        "Text", "Title", "Name", "Command", "Format", "Label", "Message",
        "Prompt", "Read", "Cancel", "Close", "Word", "Period", "Option",
        "morningPeriod", "dayPeriod", "eveningPeriod", "nightPeriod", "daysWeek", "months", "seasons",
        "anotherData", "anotherDataList", "mode", "Menu", "Help", "Vocab"
    ]

    BLACK_KEY_PATTERNS: List[str] = [
        "iconname", "icon", "image", "skin", "font", "key", "position",
        "lunatic mode", "eval", "code", "switch", "variable", "folder", "filename",
        "キー", "タイプ", "座標"
    ]

    @classmethod
    def is_translatable_ui_string(cls, key_path: List[Union[str, int]], value: str) -> Tuple[bool, str]:
        val_clean = value.strip()
        if not val_clean:
            return False, "Empty string"

        path_str = ".".join(str(p) for p in key_path).lower()
        leaf_key = str(key_path[-1]) if key_path else ""
        leaf_key_lower = leaf_key.lower()

        # 1. Reject Lunatic Mode และบล็อกโค้ดสคริปต์
        if "lunatic mode" in path_str or "eval" in path_str:
            return False, "Lunatic Mode / script block"

        # 2. Reject คอมเมนต์ในโค้ด
        if val_clean.startswith("//") or val_clean.startswith("/*") or "console.log" in val_clean:
            return False, "Code comment or console call"

        # 3. Reject ตาม Suffix ที่ระบุชนิดตัวแปรเกม
        for sfx in cls.DISALLOWED_KEY_SUFFIXES:
            if leaf_key.endswith(sfx):
                return False, f"Key suffix '{sfx}' is engine data"

        # 4. Reject ตาม System Blacklist
        is_whitelisted_name_context = leaf_key == "name" and any(
            w in path_str for w in ["daysweek", "morningperiod", "dayperiod", "eveningperiod", "nightperiod", "period", "quest", "anotherdata", "anotherdatalist", "another", "menu", "command"]
        )
        if leaf_key in cls.SYSTEM_KEYS_BLACKLIST and not is_whitelisted_name_context:
            return False, f"Key '{leaf_key}' is in system blacklist"
        for bk in cls.BLACK_KEY_PATTERNS:
            if bk in leaf_key_lower:
                return False, f"Key contains blacklisted term '{bk}'"

        # 5. Reject โค้ด JavaScript และสูตรคำนวณ
        for pat in cls.JAVASCRIPT_CODE_PATTERNS:
            if re.search(pat, val_clean):
                return False, f"Matches code pattern '{pat}'"
        if "this.fittingheight" in val_clean.lower() or "window_base" in val_clean.lower():
            return False, "JavaScript function call"

        # 6. Reject Format วันเวลา
        if re.match(r"^[%YMDdhms:, \-_/]+$", val_clean):
            return False, "Date/time format specification"

        # 7. Reject ตัวเลขหรือสัญลักษณ์ล้วน
        if re.match(r"^[-+]?\d*\.?\d+$", val_clean):
            return False, "Numeric value"
        if re.match(r"^[\s\-_.\*~!?,:;\"'()\[\]{}|\\/]+$", val_clean):
            return False, "Pure symbols"

        # 8. กรองแท็กควบคุมเพียวๆ เช่น \c[6], \i[160]%1
        clean_text_only = re.sub(r"\\[a-zA-Z]+(?:\[\d+\])?", "", val_clean)
        clean_text_only = re.sub(r"%\d+", "", clean_text_only)
        clean_text_only = re.sub(r"[\s\-_.\*~!?,:;\"'()\[\]{}|\\/]+", "", clean_text_only).strip()

        if not clean_text_only:
            return False, "Only control tags/format without human language"

        # 9. ต้องมีอักขระภาษาธรรมชาติอย่างน้อย 1 ตัว
        if not re.search(r"[a-zA-Z\u0E00-\u0E7F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", clean_text_only):
            return False, "No natural language letters"

        # 10. ตรวจสอบ Whitelist Keywords ใน Path หรือ Key หรือรูปแบบข้อความ RPG Maker
        has_whitelist = any(kw.lower() in leaf_key_lower or kw.lower() in path_str for kw in cls.ALLOWED_KEY_KEYWORDS)
        has_rpgm_text_marker = bool(re.search(r"(?:\\[iIcC]\[\d+\]|%\d+|Quests|Objective|Reward|Description|Subtext)", val_clean))
        # ถ้ามีอักษร CJK ญี่ปุ่นชัดเจน ให้ยอมรับทันที
        has_cjk = bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", val_clean))

        if has_whitelist or has_rpgm_text_marker or has_cjk:
            return True, "Valid UI text"

        return False, "Unmatched general string"


class CodeScriptScanner:
    """โมดูลสแกนสตริงจากไฟล์ซอร์สโค้ด .js ในโฟลเดอร์ plugins/ โดยเฉพาะ"""
    ASSET_EXT_REGEX = re.compile(r"\.(?:png|jpg|jpeg|ogg|wav|mp3|m4a|json|txt|css|html)$", re.IGNORECASE)
    KNOWN_CODE_TERMS = {
        "use strict", "undefined", "null", "true", "false", "this", "prototype",
        "number", "string", "boolean", "object", "function", "symbol", "bigint",
        "window", "document", "canvas", "2d", "webgl", "div", "span", "rgba", "rgb",
        "auto", "none", "block", "inline", "hidden", "visible", "absolute", "relative",
        "fixed", "static", "inherit", "px", "em", "rem", "%", "deg", "rad"
    }

    @classmethod
    def strip_comments(cls, js_content: str) -> str:
        """ลบคอมเมนต์ JavaScript ทั้ง single-line และ multi-line ออกอย่างแม่นยำ"""
        # ลบ /* ... */
        content = re.sub(r"/\*[\s\S]*?\*/", "", js_content)
        # ลบ // ...
        content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
        return content

    @classmethod
    def extract_strings_from_js(cls, file_path: str) -> List[Tuple[int, str, str]]:
        """
        สกัด String Literals ที่เข้าข่ายข้อความ UI ออกจากไฟล์ .js
        คืนค่า: List of (line_number, string_value, code_context)
        """
        results: List[Tuple[int, str, str]] = []
        if not os.path.exists(file_path):
            return results

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return results

        # รูปแบบการดึง String Literals
        # 1. Double quoted: "..."
        # 2. Single quoted: '...'
        # 3. Template string: `...`
        str_pattern = re.compile(r"""(?:["'])(.+?)(?:["'])|(?:`)(.+?)(?:`)""")

        for line_idx, line in enumerate(lines, start=1):
            line_strip = line.strip()
            # ข้ามบรรทัดคอมเมนต์เต็มบรรทัด
            if line_strip.startswith("//") or line_strip.startswith("/*") or line_strip.startswith("*"):
                continue

            matches = str_pattern.findall(line)
            for m in matches:
                val = m[0] or m[1]
                val = val.strip()
                if not val or len(val) < 2:
                    continue

                # กรอง Asset filenames (เช่น 'Actor1.png', 'bgm01.ogg')
                if cls.ASSET_EXT_REGEX.search(val) or "/" in val or "\\" in val:
                    continue

                # กรองคำศัพท์เทคนิค JavaScript
                if val.lower() in cls.KNOWN_CODE_TERMS:
                    continue

                # กรองโค้ด CSS, HTML, หรือ Regex
                if val.startswith("#") and len(val) in [4, 7, 9]:
                    continue
                if "<" in val and ">" in val and not re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", val):
                    continue

                # เงื่อนไขการยอมรับ:
                # 1. มีอักษรญี่ปุ่น/จีน (CJK) ชัดเจน (เช่น '回想モード', 'セーブしました', 'はい', 'いいえ')
                # 2. หรือ ปรากฏในฟังก์ชันเรียก UI ยอดนิยม (addCommand, drawText, showText, alert, $gameMessage)
                has_cjk = bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", val))
                is_ui_context = any(ui_fn in line for ui_fn in [
                    "addCommand", "drawText", "$gameMessage.add", "showText", "makeCommandList",
                    "Window_Command", "alert(", "confirm(", "prompt("
                ])

                if has_cjk or (is_ui_context and len(val) >= 3 and not re.match(r"^[a-zA-Z0-9_]+$", val)):
                    # เก็บผลลัพธ์
                    snippet = line_strip[:80]
                    results.append((line_idx, val, snippet))

        return results


def find_js_directory(game_dir: str) -> Optional[Tuple[str, str, List[str]]]:
    """
    ค้นหาตำแหน่งของโฟลเดอร์ /js และไฟล์ plugins.js อัตโนมัติ
    คืนค่า: (js_dir_path, plugins_js_path, list_of_all_plugin_js_files)
    """
    game_dir = os.path.abspath(game_dir.strip().strip('"').strip("'"))
    if not os.path.exists(game_dir):
        return None

    candidate_js_dirs = [
        os.path.join(game_dir, "www", "js"),
        os.path.join(game_dir, "js"),
        game_dir if os.path.basename(game_dir).lower() == "js" else None
    ]

    chosen_js_dir = None
    for c in candidate_js_dirs:
        if c and os.path.exists(c) and os.path.isdir(c):
            chosen_js_dir = c
            break

    # ถ้ายังไม่เจอ ลองสแกนหาโฟลเดอร์ js ในชั้นถัดไป
    if not chosen_js_dir:
        for root, dirs, files in os.walk(game_dir):
            if "js" in [d.lower() for d in dirs]:
                chosen_js_dir = os.path.join(root, "js")
                break

    if not chosen_js_dir or not os.path.exists(chosen_js_dir):
        return None

    # ตรวจหา plugins.js
    plugins_js_path = os.path.join(chosen_js_dir, "plugins.js")
    if not os.path.exists(plugins_js_path):
        plugins_js_path = ""

    # ตรวจหาไฟล์ .js ทั้งหมดใน plugins/
    plugins_folder = os.path.join(chosen_js_dir, "plugins")
    plugin_files: List[str] = []
    if os.path.exists(plugins_folder) and os.path.isdir(plugins_folder):
        for root, _, files in os.walk(plugins_folder):
            for f in files:
                if f.lower().endswith(".js"):
                    plugin_files.append(os.path.join(root, f))

    return chosen_js_dir, plugins_js_path, plugin_files


def format_path_string(path: List[Union[str, int]]) -> str:
    tokens = []
    for p in path:
        if isinstance(p, int):
            tokens.append(f"[{p}]")
        elif " " in str(p) or "-" in str(p):
            tokens.append(f"['{p}']")
        else:
            tokens.append(f".{p}" if tokens else str(p))
    return "".join(tokens)


def extract_all_plugins(game_dir: str, output_csv: str) -> bool:
    """แกนหลักในการสกัดข้อความ UI จากทุกไฟล์ใน /js ออกสู่ไฟล์ CSV"""
    detection = find_js_directory(game_dir)
    if not detection:
        print(f"❌ ไม่พบโฟลเดอร์ /js ในตำแหน่งเกม: {game_dir}")
        return False

    js_dir, plugins_js, plugin_files = detection
    print("\n" + "=" * 75)
    print(f"🔍 [ตรวจพบโฟลเดอร์ JavaScript]: {js_dir}")
    print(f"📄 [ไฟล์ plugins.js]: {plugins_js if plugins_js else 'ไม่พบ'}")
    print(f"🧩 [ไฟล์ซอร์สโค้ดปลั๊กอินใน plugins/]: {len(plugin_files)} ไฟล์")
    print("=" * 75)

    entries: List[Dict[str, Any]] = []
    seen_unique: Set[Tuple[str, str]] = set()  # (original, speaker)

    # -------------------------------------------------------------
    # ส่วนที่ 1: สกัดจาก www/js/plugins.js (Configured Parameters)
    # -------------------------------------------------------------
    plugins_js_count = 0
    if plugins_js and os.path.exists(plugins_js):
        print("\n⏳ [1/2] กำลังสกัดค่าพารามิเตอร์จาก plugins.js...")
        try:
            with open(plugins_js, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            match = re.search(r"var\s+\$plugins\s*=\s*(\[[\s\S]*\])\s*;?", content)
            if match:
                raw_json = match.group(1)
                plugins_data = json.loads(raw_json)

                for plugin in plugins_data:
                    p_name = plugin.get("name", "UnknownPlugin")
                    p_status = plugin.get("status", False)
                    params = plugin.get("parameters", {})

                    unpacked = RecursiveJsonUnpacker.unpack(params, [])
                    for key_path, raw_value in unpacked:
                        is_ui, reason = SemanticParameterClassifier.is_translatable_ui_string(key_path, raw_value)
                        if is_ui:
                            dedupe_key = (raw_value.strip(), p_name)
                            if dedupe_key not in seen_unique:
                                seen_unique.add(dedupe_key)
                                path_repr = format_path_string(key_path)
                                entries.append({
                                    "original": raw_value,
                                    "initial": "",
                                    "filename": "plugins.js",
                                    "note": f"{p_name}.parameters{path_repr}",
                                    "role": "UI/Plugin",
                                    "speaker": p_name,
                                    "displayable": "Yes"
                                })
                                plugins_js_count += 1
            print(f"   ✔ สกัดข้อความ UI จาก plugins.js ได้: {plugins_js_count} รายการ")
        except Exception as e:
            print(f"   ⚠️ ไม่สามารถอ่าน plugins.js ได้อย่างสมบูรณ์: {e}")

    # -------------------------------------------------------------
    # ส่วนที่ 2: สแกนจากไฟล์ซอร์สโค้ดใน js/plugins/*.js (Code Literals)
    # -------------------------------------------------------------
    code_count = 0
    print(f"\n⏳ [2/2] กำลังสแกนข้อความ UI ในซอร์สโค้ดปลั๊กอิน ({len(plugin_files)} ไฟล์)...")
    for p_file in plugin_files:
        rel_path = os.path.relpath(p_file, js_dir).replace("\\", "/")
        p_name = os.path.splitext(os.path.basename(p_file))[0]

        extracted_strings = CodeScriptScanner.extract_strings_from_js(p_file)
        for line_no, str_val, code_snippet in extracted_strings:
            dedupe_key = (str_val.strip(), p_name)
            if dedupe_key not in seen_unique:
                seen_unique.add(dedupe_key)
                entries.append({
                    "original": str_val,
                    "initial": "",
                    "filename": rel_path,
                    "note": f"Line {line_no}: {code_snippet[:60]}",
                    "role": "UI/Plugin Code",
                    "speaker": p_name,
                    "displayable": "Yes"
                })
                code_count += 1

    print(f"   ✔ สกัดข้อความ UI จากซอร์สโค้ดปลั๊กอินได้: {code_count} รายการ")

    # -------------------------------------------------------------
    # ส่วนที่ 3: บันทึกออกสู่ไฟล์ CSV
    # -------------------------------------------------------------
    total_entries = len(entries)
    print("\n" + "=" * 75)
    print(f"📊 [สรุปผลการสกัดข้อความปลั๊กอิน]")
    print(f"   - จาก plugins.js (Parameters)  : {plugins_js_count} รายการ")
    print(f"   - จาก plugins/*.js (Source Code): {code_count} รายการ")
    print(f"   - รวมข้อความ UI ที่ต้องแปลทั้งหมด: {total_entries} รายการ")
    print("=" * 75)

    if total_entries == 0:
        print("⚠️ ไม่พบข้อความส่วนติดต่อผู้ใช้ในปลั๊กอินของเกมนี้")
        return False

    # สร้างไดเรกทอรีปลายทางหากยังไม่มี
    output_csv = os.path.abspath(output_csv.strip().strip('"').strip("'"))
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    header = ["Original", "Initial", "Filename", "Row", "Note", "Role", "Speaker", "Displayable"]
    try:
        with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for idx, entry in enumerate(entries, start=1):
                writer.writerow([
                    entry["original"],
                    entry.get("initial", ""),
                    entry["filename"],
                    str(idx),
                    entry["note"],
                    entry["role"],
                    entry["speaker"],
                    entry["displayable"]
                ])
        print(f"\n🎉 [สำเร็จ] สร้างไฟล์สำเร็จเรียบร้อยที่:")
        print(f"   👉 {output_csv}")
        print("\n💡 พร้อมสำหรับนำไฟล์นี้ไปใช้งานต่อในคำสั่ง:")
        print(f"   python atf.py setup")
        print("=" * 75 + "\n")
        return True
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการเขียนไฟล์ CSV: {e}")
        return False


def interactive_main():
    """ส่วนติดต่อผู้ใช้งานแบบ Interactive CLI ถาม-ตอบ ใช้งานง่าย"""
    print("\n" + "=" * 75)
    print("🚀 RPG Maker Standalone Plugin Text Extractor (Universal ATF Utility)")
    print("   เครื่องมือสกัดข้อความ UI เมนูจากปลั๊กอินเกมทุกตัวออกสู่ plugins_texts.csv")
    print("=" * 75)

    parser = argparse.ArgumentParser(description="Standalone RPG Maker Plugin Text Extractor")
    parser.add_argument("--game-dir", type=str, default=None, help="โฟลเดอร์เกมที่ต้องการสกัด (Game Directory)")
    parser.add_argument("--output", type=str, default=None, help="ตำแหน่งไฟล์ CSV ปลายทาง")
    args = parser.parse_args()

    # 1. ถามหาโฟลเดอร์เกม
    game_dir = args.game_dir
    while not game_dir:
        prompt_val = input("\n📂 กรุณาระบุโฟลเดอร์เกมต้นทางที่ต้องการสกัด (ลากโฟลเดอร์มาวางได้): ").strip()
        if not prompt_val:
            print("⚠️ กรุณาระบุพาธโฟลเดอร์เกม")
            continue
        cleaned = prompt_val.strip('"').strip("'")
        if not os.path.exists(cleaned):
            print(f"❌ ไม่พบโฟลเดอร์: {cleaned} กรุณาลองใหม่อีกครั้ง")
            continue
        game_dir = cleaned

    # 2. ทำการสแกนและตรวจสอบข้อมูล
    detection = find_js_directory(game_dir)
    if not detection:
        print(f"❌ ไม่พบโฟลเดอร์ /js ในโฟลเดอร์เกมที่ระบุ ({game_dir})")
        sys.exit(1)

    # 3. ถามหาตำแหน่งสำหรับวางไฟล์ plugins_text.csv
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    default_output = os.path.join(workspace_root, "data", "plugins_texts.csv")

    output_csv = args.output
    if not output_csv:
        print(f"\n💾 ค่าเริ่มต้นไฟล์ปลายทาง: {default_output}")
        dest_input = input(f"📍 ระบุตำแหน่งสำหรับวางไฟล์ CSV ที่สกัดได้ (กด Enter เพื่อใช้ค่าเริ่มต้น): ").strip()
        if dest_input:
            output_csv = dest_input.strip('"').strip("'")
            # ถ้าผู้ใช้พิมพ์แค่ชื่อไฟล์ ให้เอาไปวางไว้ในโฟลเดอร์ data/
            if not os.path.dirname(output_csv):
                output_csv = os.path.join(workspace_root, "data", output_csv)
        else:
            output_csv = default_output

    # 4. สกัดและสร้างไฟล์ CSV
    success = extract_all_plugins(game_dir, output_csv)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    interactive_main()
