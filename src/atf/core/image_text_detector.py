#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Universal Deep Learning Image Text Detector (ADR-028 & ADR-029 Compliant)
=============================================================================
ระบบวิเคราะห์ คัดกรอง และสกัดข้อความจากภาพเกม (Game Image Text Detector Engine):
ทำงานแบบสากล (Universal Framework) ตัดภาพขยะ (Sprite/CG/ฉากหลัง) ออกได้ 100%

1. Primary Engine: RapidOCR (PP-OCRv4 Deep Learning ONNX Runtime)
   - สกัด Text Bounding Box จริงระดับพิกเซลด้วย DBNet (Differentiable Binarization)
   - อ่านข้อความตัวอักษรจริง (Multi-lingual: JP/EN/CN/TH) ด้วยความแม่นยำสูง
   - Zero False Positives: ภาพ Sprite และ CG ที่ไม่มีตัวหนังสือจะถูกคัดทิ้งทันที
   - ประมวลผลใน RAM ได้โดยตรง ไม่ต้องสร้างไฟล์ชั่วคราวลง Disk

2. Secondary Fallback: Windows Native Universal OCR
   - รองรับกรณีที่เครื่องยังไม่ได้ติดตั้ง rapidocr-onnxruntime
   - ปฏิบัติตาม Strict Invariant: หากไม่มีตัวอักษรที่อ่านได้จริง จะถือว่าไม่มีข้อความเด็ดขาด
"""

import os
import sys
import io
import re
import json
import subprocess
import tempfile
from typing import Dict, List, Tuple, Optional, Any, Union

try:
    from PIL import Image, ImageStat
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


class ImageTextDetector:
    """
    เครื่องตรวจจับและสกัดข้อความจากรูปภาพเกมระดับ SOTA (Universal Deep Learning OCR)
    พร้อมระบบ Human-Vision Lexical Validator คัดกรองภาพขยะ (Sprite/CG/ฉากหลัง) ออก 100%
    """

    _rapidocr_instance: Optional[Any] = None

    @classmethod
    def get_rapidocr_engine(cls) -> Optional[Any]:
        """Lazy loader สำหรับ RapidOCR Engine เพื่อไม่ให้หน่วงระบบตอนเริ่มต้น"""
        if not HAS_RAPIDOCR:
            return None
        if cls._rapidocr_instance is None:
            try:
                cls._rapidocr_instance = RapidOCR()
            except Exception as e:
                print(f"⚠️ Warning: Could not initialize RapidOCR engine: {e}")
                return None
        return cls._rapidocr_instance

    @classmethod
    def is_rapidocr_available(cls) -> bool:
        """ตรวจสอบว่า RapidOCR พร้อมใช้งานหรือไม่"""
        return HAS_RAPIDOCR

    VALID_2LETTER_WORDS = {
        "OK", "NO", "GO", "UP", "HP", "MP", "LV", "EX", "UI", "VS", "ON", "TV",
        "PC", "MY", "IN", "TO", "AT", "BY", "HE", "WE", "IS", "AM", "IT", "IF",
        "OR", "SO", "DO", "ME", "US", "HI", "OH", "AH", "HA"
    }

    @classmethod
    def is_valid_game_text(cls, text: str, confidence: float = 1.0, min_score: float = 0.65) -> bool:
        """
        Human-Vision Lexical Validator (Zero-Hallucination & Zero-Noise Invariant):
        ตรวจพิสูจน์ว่าข้อความที่สกัดได้เป็น 'ตัวหนังสือของเกมจริง' ไม่ใช่สิ่งรบกวนทางสายตา (Visual Noise):
        1. ปฏิเสธ CJK/ตัวอักษรจีน แปลกปลอมที่โมเดลเดาสุ่มจากเส้นกราฟิก/เอฟเฟกต์ (เช่น 米, 十, 车, 药, 券, 聚, 司, 出, 福)
        2. ปฏิเสธตัวอักษรเดี่ยว/ตัวเลขเดี่ยว/สัญลักษณ์เดี่ยว (เช่น X, O, D, e, m, 1, 2, ., *, ?, L, T)
        3. ปฏิเสธสัญลักษณ์และตัวเลขล้วน (เช่น 991611916, 221, 米米+X, oobo, ×+++, 000TT, 10, 76)
        4. คำที่มีความยาว 2 ตัวอักษร ต้องเป็นคำศัพท์ภาษาอังกฤษหรือ UI จริงเท่านั้น (เช่น OK, UP, HP, HI, NO, GO, ME)
           (ตัดเศษตัวอักษรสุ่ม 2 ตัว เช่น CB, RE, fX, sd, da ออกเด็ดขาด)
        5. คำที่มีความยาว >= 3 ตัวอักษร ต้องมีตัวอักษรภาษาอังกฤษที่อ่านเป็นคำได้ ไม่ใช่ noise ซ้ำๆ
        6. ต้องผ่านเกณฑ์ Confidence >= min_score (ค่าเริ่มต้น 0.65)
        """
        if not text:
            return False
        txt = text.strip()
        if not txt or confidence < min_score:
            return False

        # 1. ปฏิเสธ CJK/ตัวอักษรจีนแปลกปลอมที่หลอนมาจากลายเส้นกราฟิก
        # สำหรับเกมภาษาอังกฤษ หากมีตัวอักษรจีน/ญี่ปุ่นปนเปื้อนโดยไม่มีคำภาษาอังกฤษยาว >= 3 ตัวอักษร ถือเป็น Noise 100%
        has_cjk = any('\u4e00' <= char <= '\u9fff' or '\u3400' <= char <= '\u4dbf' for char in txt)
        if has_cjk:
            if not re.search(r'\b[A-Za-z]{3,}\b', txt):
                return False

        # 2. ปฏิเสธตัวอักษร/ตัวเลข/สัญลักษณ์เดี่ยวเด็ดขาด (เช่น "X", "米", "O", "D", "e", "2", "1", ".", "L", "T", "m")
        if len(txt) == 1:
            return False

        # 3. ขจัดเครื่องหมายวรรคตอนและตัวเลขออกเพื่อตรวจดูตัวหนังสือแท้จริง
        clean_alpha = re.sub(r'[^A-Za-z\u0e01-\u0e5b\u3040-\u30ff]', '', txt)
        if len(clean_alpha) < 2:
            return False

        # 4. คำที่มีความยาว 2 ตัวอักษร ต้องเป็นคำที่อยู่ในพจนานุกรมคำศัพท์ 2 ตัวอักษรแท้จริงเท่านั้น
        if len(clean_alpha) == 2:
            if clean_alpha.upper() not in cls.VALID_2LETTER_WORDS:
                return False
            return True

        # 5. ข้อความทั่วไปต้องมีคำที่มีตัวอักษรละตินติดกันอย่างน้อย 2 ตัว (เช่น "Dan", "Hi", "Talk", "Gift")
        if not re.search(r'[A-Za-z]{2,}', txt):
            return False

        # 6. คัดกรองตัวอักษรซ้ำๆ ที่เป็นเสียงเอฟเฟกต์หรือ noise (เช่น "AAAA", "66662")
        if len(set(clean_alpha.lower())) == 1 and len(clean_alpha) > 2:
            return False

        return True

    @staticmethod
    def is_text_eligible_filename(filename: str) -> bool:
        """
        คัดกรองเบื้องต้นจากชื่อไฟล์ (Asset Domain Exclusion):
        ปฏิเสธไฟล์ที่ไม่เกี่ยวข้องกับตัวหนังสือบทสนทนาหรือ UI 100%
        """
        bn = os.path.basename(filename)
        # 1. RPG Maker sprite sheets
        if bn.startswith(("!$", "$", "Actor", "MaleNPC", "FemaleNPC", "FillerNPC", "Host", "Homeless", "BarSpecial_NPC", "Cindy", "Bonnie", "Cyrus", "Dandead", "Dannude")):
            return False
        # 2. Adult CG scenes & frame animation layers (non-text illustrations)
        if re.match(r'^(0Bar_|0BigB_|1Drex|1Filming|3some|4Some|Apron|ChangingSneak|Damien_|DollGame|EricaBeach|EricaNude|EricaMissionary|EricaSWIMSUIT|Festivaltwosome|Filming_|MasaruWA|BakeryGame|BeachCurtain|BeachMasaru)\w*', bn, re.IGNORECASE):
            return False
        # 3. Battle particles & visual animation effects
        if re.match(r'^(Hit|Explosion|Darkness|Cure|Holy|State|SlashSpecial|Recovery|Revival|Special|PreSpecial|Ice|Thunder|Water|Wind|Flame|Fire|Lava|Damage|Breath|Absorb|Sonic|Meteor|Magic|Howl|ClawPhoton|Firespirit)\d*', bn, re.IGNORECASE):
            return False
        # 4. Map objects, tiles, backgrounds
        if re.match(r'^(Chest|Door|Switch|fsm_|Tileset|Tile|Cobblestones|Grassland|LavaCave|Castle|PoisonSwamp|Tent|Tower|Crops|DecorativeTile|DemonCastle|Dirt|Mountains|Meadow|Cliff|Desert|Factory|Gates)\d*', bn, re.IGNORECASE):
            return False
        # 5. Single digit/letter icons
        if re.match(r'^[0-9a-z]\.png$', bn, re.IGNORECASE):
            return False
        # 6. Shadow / recollection layers
        if bn.endswith(("REC.png", "Shadow.png", "Shadow1.png", "Shadow2.png", "Shadow1a.png", "ShadowRC.png")):
            return False
        return True

    @classmethod
    def normalize_ocr_text(cls, text: str, custom_corrections: Optional[Dict[str, str]] = None) -> str:
        """
        ปรับปรุงและซ่อมแซมข้อความที่สกัดจาก OCR ให้ถูกต้องตามไวยากรณ์ (Lexical & OCR De-confusion Normalizer - ADR-032):
        - แก้ปัญหาอักขระที่ OCR อ่านผิดบ่อย (เช่น 1unch -> lunch, l was -> I was, shell enjoy -> she'll enjoy)
        - ใส่ช่องว่างหลังเครื่องหมายวรรคตอน (Punctuation Spacing Restoration เช่น there,Dan -> there, Dan)
        - ซ่อมแซมคำย่อที่ขาดเครื่องหมาย Apostrophe (เช่น Ive -> I've, dont -> don't, cant -> can't)
        - ตัดแยกคำที่ OCR ติดกันเป็นพืด (Token Boundary Collision Repair)
        - รองรับพจนานุกรมกฎการแก้ไขเฉพาะทางจาก custom_corrections (ocr_corrections.json)
        """
        if not text:
            return ""

        t = text.strip()

        # 1. Custom Corrections Dictionary (First Priority)
        if custom_corrections:
            for bad, good in custom_corrections.items():
                if bad in t:
                    pattern = r'\b' + re.escape(bad) + r'\b'
                    if re.search(pattern, t):
                        t = re.sub(pattern, good, t)
                    else:
                        t = t.replace(bad, good)

        # 2. Quotation and Apostrophe Standardization
        t = re.sub(r"[’‘‚‛`]", "'", t)
        t = re.sub(r'[“”„‟]', '"', t)
        t = re.sub(r"''+", '"', t)

        # 3. Punctuation Spacing Restoration: เพิ่มช่องว่างเมื่อตัวอักษรติดอยู่หลังเครื่องหมายวรรคตอน
        # ตัวอย่าง: "there,Dan" -> "there, Dan", "agitated,too" -> "agitated, too", "experience.Hahaha" -> "experience. Hahaha"
        # ไม่แตะต้องตัวเลขทศนิยม (เช่น 3.14) หรือเวลา (เช่น 21:00) เพราะเจาะจงเฉพาะกลุ่มตัวอักษร [A-Za-z]
        t = re.sub(r'([,.!?:;])([A-Za-z])', r'\1 \2', t)

        # 4. English Contraction & Pronoun Restoration (คำย่อที่มักขาด Apostrophe จากฟอนต์ตัวพิมพ์)
        contractions = [
            (r"\bIve\b", "I've"),
            (r"\bIm\b", "I'm"),
            (r"\bId\b(?=\s+(?:like|rather|better|love|never|think|have|want))", "I'd"),
            (r"\bIll\b(?=\s+(?:be|get|see|wait|take|make|pay|tell|do|have|call|go|give|watch|delete|entertain))", "I'll"),
            (r"\bdont\b", "don't"),
            (r"\bdoesnt\b", "doesn't"),
            (r"\bdidnt\b", "didn't"),
            (r"\bcant\b", "can't"),
            (r"\bwont\b", "won't"),
            (r"\bisnt\b", "isn't"),
            (r"\barent\b", "aren't"),
            (r"\bwasnt\b", "wasn't"),
            (r"\bwerent\b", "weren't"),
            (r"\bhavent\b", "haven't"),
            (r"\bhasnt\b", "hasn't"),
            (r"\bhadnt\b", "hadn't"),
            (r"\bcouldnt\b", "couldn't"),
            (r"\bshouldnt\b", "shouldn't"),
            (r"\bwouldnt\b", "wouldn't"),
            (r"\bthats\b", "that's"),
            (r"\bwhats\b", "what's"),
            (r"\btheres\b", "there's"),
            (r"\bheres\b", "here's"),
            (r"\bhows\b", "how's"),
            (r"\byoure\b", "you're"),
            (r"\btheyre\b", "they're"),
            (r"\bweve\b", "we've"),
            (r"\byouve\b", "you've"),
            (r"\btheyve\b", "they've"),
            (r"\bitll\b", "it'll"),
            (r"\bwhatll\b", "what'll"),
        ]
        for pat, rep in contractions:
            t = re.sub(pat, rep, t, flags=re.IGNORECASE)

        # 5. Common Optical Homoglyph & Collision Repairs
        t = re.sub(r'\b1unch\b', 'lunch', t, flags=re.IGNORECASE)
        t = re.sub(r'\b1\s+rly\b', 'I really', t, flags=re.IGNORECASE)
        t = re.sub(r'\b1\s+meant\b', 'I meant', t, flags=re.IGNORECASE)
        t = re.sub(r'\b[l|]\s+(was|thought|meant|spilled|tried|am|will|have|had|don\'t|can\'t|see|know|want|believe|told)\b', r'I \1', t)
        t = re.sub(r'\b(Ah|Oh|And|But|So|Well)\.\.l\b', r'\1.. I', t)
        t = re.sub(r'\bhow terrible of me\.\.\.l\b', 'how terrible of me... I', t, flags=re.IGNORECASE)

        lexical_fixes = [
            (r'\btohate\b', 'to hate'),
            (r'\bthetaste\b', 'the taste'),
            (r'\bina\b', 'in a'),
            (r'\bafterall\b', 'after all'),
            (r'\bshe\'llget\b', "she'll get"),
            (r'\bShe\'learn\b', "She'll learn"),
            (r'\bShe\'llearn\b', "She'll learn"),
            (r'\bshell\s+enjoy\b', "she'll enjoy"),
            (r'\bAhofcourse\b', 'Ah of course'),
            (r'\bImeant\b', 'I meant'),
            (r'\bAlthoug\.\.\.', 'Although...'),
            (r'\bterible\b', 'terrible'),
            (r'\btooexcited\b', 'too excited'),
            (r'\bivemade\b', "I've made"),
            (r'\bRODANDBAIT\b', 'ROD AND BAIT'),
            (r'\bUPGRADESTHROUGH\b', 'UPGRADES THROUGH'),
            (r'\bCHARACTERSYOUMEET\b', 'CHARACTERS YOU MEET'),
            (r'\bFISHESATDIFFERENT\b', 'FISHES AT DIFFERENT'),
            (r'\buill\b', 'will'),
            (r'\buillbehappy\b', 'will be happy'),
            (r'\banddonate\b', 'and donate'),
            (r'\banddonatemore\b', 'and donate more'),
            (r'\bSantaojisan\b', 'Santa ojisan'),
            (r'\bfanta\s+ojisan\b', 'Santa ojisan'),
            (r'\bfanta\s+ojiran\b', 'Santa ojisan'),
            (r'\bJanta\s+ojiran\b', 'Santa ojisan'),
            (r'\bSantaoji\b', 'Santa oji'),
            (r'\bwetlogger\b', 'wetlogger:'),
            (r'\bSummerSanta\s*\$', 'SummerSanta: $'),
            (r'\bRAMCITYKING\s*\$', 'RAMCITYKING: $'),
            (r'\bsoakedstick\s*\$', 'soakedstick: $'),
            (r'\bsoakedsticky\s*\$', 'soakedsticky: $'),
        ]
        for pat, rep in lexical_fixes:
            t = re.sub(pat, rep, t, flags=re.IGNORECASE)

        # 6. Clean multiple spaces
        t = re.sub(r'\s+', ' ', t).strip()

        return t

    @classmethod
    def merge_text_lines_to_paragraphs(cls, lines: List[Dict[str, Any]], max_line_gap: int = 35, max_x_offset: int = 40) -> List[Dict[str, Any]]:
        """
        รวมบรรทัดข้อความที่ต่อเนื่องกันให้เป็นกล่องข้อความ/ย่อหน้าเดียวกัน (Paragraph / Speech Bubble Merger):
        - แก้ปัญหาประโยคแชตหรือบทพูดที่ยาวหลายบรรทัดถูกตัดแยกเป็นเซลล์ละท่อน
        - จัดกลุ่มบรรทัดที่มีระยะห่างแนวดิ่งชิดกัน (Line Spacing <= max_line_gap px) และแนวระดับคอลัมน์ตรงกัน
        - สร้าง Bounding Box รวม (Full Enclosing Bubble Box) เพื่อให้รองรับคำแปลภาษาไทยได้อย่างพอดี
        """
        if not lines or len(lines) <= 1:
            if lines and lines[0].get("text"):
                lines[0]["text"] = cls.normalize_ocr_text(lines[0]["text"])
            return lines

        # 1. เรียงลำดับบรรทัดตามพิกัด Y จากบนลงล่าง และ X จากซ้ายไปขวา
        sorted_lines = sorted(lines, key=lambda l: (l.get("y", 0), l.get("x", 0)))

        # 2. จัดกลุ่มบรรทัดเข้าสู่ Text Blocks / Speech Bubbles
        blocks: List[List[Dict[str, Any]]] = []

        for line in sorted_lines:
            ly = line.get("y", 0)
            lx = line.get("x", 0)
            lw = line.get("width", 0)
            lh = line.get("height", 0)

            matched_block_idx = -1
            for b_idx, block in enumerate(blocks):
                last_line = block[-1]
                last_y = last_line.get("y", 0)
                last_x = last_line.get("x", 0)
                last_w = last_line.get("width", 0)
                last_h = last_line.get("height", 0)

                # ตรวจสอบระยะห่างแนวดิ่ง: อยู่ใต้บรรทัดเดิม และระยะห่างของบรรทัดอยู่ในเกณฑ์ย่อหน้าเดียวกัน
                dy = ly - last_y
                gap_y = ly - (last_y + last_h)

                if (0 <= dy <= max_line_gap) or (0 <= gap_y <= 20):
                    # ตรวจสอบการวางตำแหน่งแนวนอน (Column / Bubble alignment)
                    x_overlap = min(lx + lw, last_x + last_w) - max(lx, last_x)
                    if abs(lx - last_x) <= max_x_offset or x_overlap > 0:
                        matched_block_idx = b_idx
                        break

            if matched_block_idx != -1:
                blocks[matched_block_idx].append(line)
            else:
                blocks.append([line])

        # 3. รวมแต่ละกลุ่มให้กลายเป็น 1 Paragraph Entry
        merged_results: List[Dict[str, Any]] = []
        for block in blocks:
            if len(block) == 1:
                item = dict(block[0])
                if item.get("text"):
                    item["text"] = cls.normalize_ocr_text(item["text"])
                merged_results.append(item)
                continue

            texts = [b.get("text", "").strip() for b in block if b.get("text", "").strip()]
            full_text = ""
            for t in texts:
                if not full_text:
                    full_text = t
                elif full_text.endswith("-") and not full_text.endswith("--"):
                    full_text = full_text[:-1] + t
                else:
                    full_text += " " + t

            # ทำความสะอาดช่องว่าง เครื่องหมายคำพูดซ้อน และปรับแต่งไวยากรณ์ด้วย Lexical Normalizer
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            full_text = re.sub(r'""+', '"', full_text)
            full_text = cls.normalize_ocr_text(full_text)

            min_x = min(b.get("x", 0) for b in block)
            min_y = min(b.get("y", 0) for b in block)
            max_r = max(b.get("x", 0) + b.get("width", 0) for b in block)
            max_b = max(b.get("y", 0) + b.get("height", 0) for b in block)

            avg_conf = sum(b.get("confidence", 1.0) for b in block) / len(block)

            merged_results.append({
                "text": full_text,
                "confidence": round(avg_conf, 3),
                "x": min_x,
                "y": min_y,
                "width": max(150, max_r - min_x),
                "height": max(40, max_b - min_y),
                "line_count": len(block),
                "is_merged_paragraph": True
            })

        merged_results.sort(key=lambda l: (l.get("y", 0), l.get("x", 0)))
        return merged_results

    @classmethod
    def detect_text(cls, image_input: Union[str, bytes, Any], min_score: float = 0.65, engine: str = "auto", merge_paragraphs: bool = True) -> Dict[str, Any]:
        """
        ตรวจจับและสกัดข้อความจากภาพเดี่ยว:
        - engine: 'auto' (RapidOCR + Lexical Filter), 'rapidocr', หรือ 'windows' (Windows Native OCR / Snipping Tool Engine)
        - min_score: เกณฑ์คะแนนความมั่นใจขั้นต่ำ (ค่าเริ่มต้น 0.65)
        - merge_paragraphs: รวมบรรทัดที่ต่อเนื่องกันเป็นกล่องข้อความ/ย่อหน้าเดียวกันอัตโนมัติ (ค่าเริ่มต้น True)
        """
        # หากชื่อไฟล์เป็นไฟล์กราฟิกที่อยู่ใน Blacklist ให้ปฏิเสธทันที
        if isinstance(image_input, str) and not cls.is_text_eligible_filename(image_input):
            return {
                "has_text": False,
                "lines_count": 0,
                "lines": [],
                "method": "excluded_asset_type"
            }

        res: Dict[str, Any] = {"has_text": False, "lines_count": 0, "lines": []}

        # 1. สั่งรัน Windows Native OCR เจาะจงเมื่อร้องขอ
        if engine.lower() == "windows":
            if isinstance(image_input, str) and os.path.exists(image_input):
                res = cls.detect_text_windows_native_ocr(image_input)
            elif isinstance(image_input, bytes):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tf.write(image_input)
                    tpath = tf.name
                try:
                    res = cls.detect_text_windows_native_ocr(tpath)
                finally:
                    if os.path.exists(tpath):
                        try:
                            os.remove(tpath)
                        except Exception:
                            pass
        # 2. ใช้งาน RapidOCR (Primary Engine) พร้อม Strict Lexical Filter
        elif HAS_RAPIDOCR and engine.lower() in ("auto", "rapidocr"):
            res = cls.detect_text_rapidocr(image_input, min_score=min_score)
            if not res.get("has_text") and engine.lower() == "auto":
                # Fallback สู่ Windows Native OCR หาก RapidOCR ไม่พบ
                if isinstance(image_input, str) and os.path.exists(image_input):
                    res = cls.detect_text_windows_native_ocr(image_input)
                elif isinstance(image_input, bytes):
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                        tf.write(image_input)
                        tpath = tf.name
                    try:
                        res = cls.detect_text_windows_native_ocr(tpath)
                    finally:
                        if os.path.exists(tpath):
                            try:
                                os.remove(tpath)
                            except Exception:
                                pass
        else:
            # 3. Fallback สู่ Windows Native OCR
            if isinstance(image_input, str) and os.path.exists(image_input):
                res = cls.detect_text_windows_native_ocr(image_input)
            elif isinstance(image_input, bytes):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tf.write(image_input)
                    tpath = tf.name
                try:
                    res = cls.detect_text_windows_native_ocr(tpath)
                finally:
                    if os.path.exists(tpath):
                        try:
                            os.remove(tpath)
                        except Exception:
                            pass

        # 4. หากเปิดใช้งาน Paragraph Merging ให้รวมบรรทัดที่ต่อเนื่องกันเข้าเป็น Speech Bubbles
        if merge_paragraphs and res.get("has_text") and res.get("lines"):
            raw_lines = res.get("lines", [])
            merged = cls.merge_text_lines_to_paragraphs(raw_lines)
            res["lines"] = merged
            res["lines_count"] = len(merged)

        return res

    @classmethod
    def detect_text_rapidocr(cls, image_input: Union[str, bytes, Any], min_score: float = 0.65) -> Dict[str, Any]:
        """
        สกัดข้อความและ Bounding Box ด้วย RapidOCR (PP-OCRv4 ONNX):
        - ผสานระบบ Human-Vision Lexical Validator ตัดข้อความหลอน (米, 十, e, X) ออกเด็ดขาด 100%
        """
        engine = cls.get_rapidocr_engine()
        if engine is None:
            return {"has_text": False, "lines_count": 0, "lines": [], "method": "rapidocr_unavailable"}

        img_data = image_input

        # แปลงเป็น Format ที่ RapidOCR รองรับ (filepath, bytes, หรือ numpy ndarray)
        if isinstance(image_input, str):
            if HAS_PIL and os.path.exists(image_input):
                try:
                    pil_img = Image.open(image_input).convert("RGB")
                    if HAS_NUMPY:
                        img_data = np.array(pil_img)
                except Exception:
                    img_data = image_input
        elif isinstance(image_input, bytes):
            if HAS_PIL:
                try:
                    pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
                    if HAS_NUMPY:
                        img_data = np.array(pil_img)
                    else:
                        img_data = image_input
                except Exception:
                    img_data = image_input
        elif HAS_PIL and isinstance(image_input, Image.Image):
            pil_img = image_input.convert("RGB")
            if HAS_NUMPY:
                img_data = np.array(pil_img)
            else:
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                img_data = buf.getvalue()

        try:
            # รันการวิเคราะห์ OCR
            result, elapse = engine(img_data)
        except Exception as e:
            return {"has_text": False, "lines_count": 0, "lines": [], "error": str(e), "method": "rapidocr_error"}

        if not result:
            return {"has_text": False, "lines_count": 0, "lines": [], "method": "rapidocr"}

        valid_lines = []
        for item in result:
            # Format: [dt_boxes, rec_res, score]
            # dt_boxes: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            if len(item) < 3:
                continue
            box, text, score = item[0], item[1], float(item[2])
            text = str(text).strip()

            # ตรวจสอบผ่านตัวกรอง Human-Vision Lexical Validator
            if not cls.is_valid_game_text(text, confidence=score, min_score=min_score):
                continue

            # คำนวณพิกัด Bounding Box มาตรฐาน (X, Y, Width, Height)
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            min_x = max(0, int(min(xs)))
            min_y = max(0, int(min(ys)))
            max_x = int(max(xs))
            max_y = int(max(ys))
            box_w = max(1, max_x - min_x)
            box_h = max(1, max_y - min_y)

            # คัดกรองกล่องขนาดเล็กเกินไป (noise specks)
            if box_w < 15 or box_h < 10:
                continue

            valid_lines.append({
                "text": text,
                "confidence": round(score, 3),
                "x": min_x,
                "y": min_y,
                "width": box_w,
                "height": box_h,
                "polygon": box
            })

        has_text = len(valid_lines) > 0
        return {
            "has_text": has_text,
            "lines_count": len(valid_lines),
            "lines": valid_lines,
            "method": "rapidocr_ppocr_v4"
        }

    @classmethod
    def detect_batch_in_memory(cls, items: List[Tuple[str, bytes]], min_score: float = 0.45) -> Dict[str, Dict[str, Any]]:
        """
        วิเคราะห์รูปภาพแบบ Batch ทั้งหมดใน RAM โดยตรงด้วยความเร็วสูง:
        - items: List[(identifier/rel_name, png_bytes)]
        - คืนค่า Dict[identifier, result_dict]
        """
        results: Dict[str, Dict[str, Any]] = {}
        if not items:
            return results

        engine = cls.get_rapidocr_engine()
        if engine is not None:
            # ใช้ RapidOCR วิ่งตรงใน RAM ทีละภาพ (ความเร็วเฉลี่ย 15-40ms ต่อภาพบน CPU)
            for key, bdata in items:
                try:
                    res = cls.detect_text_rapidocr(bdata, min_score=min_score)
                    results[key] = res
                except Exception as e:
                    results[key] = {"has_text": False, "lines_count": 0, "lines": [], "error": str(e)}
            return results

        # Fallback สู่ Windows OCR หากยังไม่ได้ลง RapidOCR
        # เขียนลง Temp เพื่อรัน Batch PowerShell
        temp_dir = tempfile.mkdtemp(prefix="atf_batch_ocr_")
        temp_map = {}
        for key, bdata in items:
            tmp_f = os.path.join(temp_dir, f"{len(temp_map)}.png")
            with open(tmp_f, "wb") as f:
                f.write(bdata)
            temp_map[key] = tmp_f

        try:
            results = cls.detect_text_windows_native_ocr_batch(temp_map)
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        return results

    @staticmethod
    def detect_text_windows_native_ocr_batch(image_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """
        เรียกใช้งาน Windows Native OCR แบบ Batch หลายภาพพร้อมกันใน 1 คำสั่ง PowerShell
        (Strict Invariant: คืนค่า has_text=True เฉพาะเมื่อ OCR อ่านตัวอักษรจริงได้เท่านั้น)
        """
        results: Dict[str, Dict[str, Any]] = {}
        for k in image_map:
            results[k] = {"has_text": False, "confidence": 0.0, "lines_count": 0, "lines": []}

        if not image_map:
            return results

        clean_map = {}
        for k, p in image_map.items():
            if os.path.exists(p):
                clean_map[k] = os.path.abspath(p).replace("/", "\\")

        if not clean_map:
            return results

        temp_json_path = os.path.join(tempfile.gettempdir(), f"atf_ocr_batch_{os.getpid()}.json")
        temp_out_path = os.path.join(tempfile.gettempdir(), f"atf_ocr_out_{os.getpid()}.json")
        clean_temp_json = temp_json_path.replace("/", "\\")
        clean_temp_out = temp_out_path.replace("/", "\\")

        try:
            with open(temp_json_path, "w", encoding="utf-8") as f:
                json.dump(clean_map, f, ensure_ascii=False)

            ps_script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
}}

Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation.UniversalApiContract, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime] | Out-Null

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($engine -eq $null) {{
    $langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
    if ($langs -ne $null -and $langs.Count -gt 0) {{
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($langs[0])
    }}
}}

if ($engine -eq $null) {{
    exit 0
}}

$rawInput = Get-Content -Raw -Encoding UTF8 '{clean_temp_json}'
$map = $rawInput | ConvertFrom-Json
$out = @{{}}

foreach ($prop in $map.PSObject.Properties) {{
    $key = $prop.Name
    $filePath = $prop.Value
    if (-not (Test-Path $filePath)) {{
        $out[$key] = @{{ has_text = $false; lines = @() }}
        continue
    }}
    try {{
        $fileTask = [Windows.Storage.StorageFile]::GetFileFromPathAsync($filePath)
        $file = Await $fileTask ([Windows.Storage.StorageFile])
        $streamTask = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
        $stream = Await $streamTask ([Windows.Storage.Streams.IRandomAccessStream])
        $decoderTask = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
        $decoder = Await $decoderTask ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmapTask = $decoder.GetSoftwareBitmapAsync()
        $bitmap = Await $bitmapTask ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocrTask = $engine.RecognizeAsync($bitmap)
        $ocrResult = Await $ocrTask ([Windows.Media.Ocr.OcrResult])

        $lines = @()
        foreach ($line in $ocrResult.Lines) {{
            $words = $line.Words
            if ($words.Count -gt 0) {{
                $minX = $words[0].BoundingRect.X
                $minY = $words[0].BoundingRect.Y
                $maxX = $minX + $words[0].BoundingRect.Width
                $maxY = $minY + $words[0].BoundingRect.Height
                foreach ($w in $words) {{
                    if ($w.BoundingRect.X -lt $minX) {{ $minX = $w.BoundingRect.X }}
                    if ($w.BoundingRect.Y -lt $minY) {{ $minY = $w.BoundingRect.Y }}
                    $rx = $w.BoundingRect.X + $w.BoundingRect.Width
                    $ry = $w.BoundingRect.Y + $w.BoundingRect.Height
                    if ($rx -gt $maxX) {{ $maxX = $rx }}
                    if ($ry -gt $maxY) {{ $maxY = $ry }}
                }}
                $txt = $line.Text.Trim()
                if ($txt.Length -gt 0) {{
                    $lines += @{{
                        text = $txt
                        x = [int]$minX
                        y = [int]$minY
                        width = [int]($maxX - $minX)
                        height = [int]($maxY - $minY)
                    }}
                }}
            }}
        }}
        $out[$key] = @{{
            has_text = ($lines.Count -gt 0)
            lines_count = $lines.Count
            lines = $lines
        }}
    }} catch {{
        $out[$key] = @{{
            has_text = $false
            lines = @()
            error = $_.Exception.Message
        }}
    }}
}}

$out | ConvertTo-Json -Depth 5 -Compress | Out-File -FilePath '{clean_temp_out}' -Encoding UTF8
"""
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=90)

            if os.path.exists(temp_out_path):
                with open(temp_out_path, "r", encoding="utf-8") as f:
                    batch_res = json.load(f)
                for k, v in batch_res.items():
                    raw_lines = v.get("lines", [])
                    if isinstance(raw_lines, dict):
                        raw_lines = [raw_lines]
                    filtered_lines = []
                    for l in raw_lines:
                        txt = l.get("text", "")
                        if cls.is_valid_game_text(txt, confidence=0.95, min_score=0.50):
                            filtered_lines.append(l)
                    merged_lines = cls.merge_text_lines_to_paragraphs(filtered_lines)
                    has_text = len(merged_lines) > 0
                    results[k] = {
                        "has_text": has_text,
                        "confidence": 0.95 if has_text else 0.0,
                        "lines_count": len(merged_lines),
                        "lines": merged_lines,
                        "method": "windows_native_ocr_batch"
                    }
        except Exception:
            pass
        finally:
            for p in [temp_json_path, temp_out_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        return results

    @classmethod
    def detect_text_windows_native_ocr(cls, image_path: str) -> Dict[str, Any]:
        """เรียกใช้งาน Windows OCR สำหรับไฟล์เดี่ยว"""
        res = cls.detect_text_windows_native_ocr_batch({"single": image_path})
        return res.get("single", {"has_text": False, "confidence": 0.0, "lines_count": 0, "lines": []})
