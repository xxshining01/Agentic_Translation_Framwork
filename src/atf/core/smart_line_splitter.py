#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Line-Break Restorer for RPG Maker Translated CSVs
เครื่องมือซ่อมแซมและจัดบรรทัดบทพูดภาษาไทยให้ตรงกับต้นฉบับภาษาอังกฤษ 100% (Strict Line-Count Parity)

คุณสมบัติหลัก:
1. Dynamic Windowing & Strict Invariant Guarantee:
   - รับประกันว่าจำนวนบรรทัดของคำแปลภาษาไทยจะเท่ากับต้นฉบับภาษาอังกฤษ (num_target_lines) เสมอ 100%
   - คำนวณช่วงปลอดภัยแบบไดนามิก (lower_bound, upper_bound) ป้องกันจุดตัดซ้ำซ้อนหรือตกขอบสตริง
2. Thai Inseparable Compounds Protection:
   - คุ้มครองกลุ่มคำประสมไม่ให้ถูกตัดขาดออกจากกัน เช่น "พวกเธอ", "พวกเรา", "ไม่ได้", "เรื่องนี้", "อะไร"
3. Tail Anchor & Grammar-Aware Scoring:
   - ค้นหาจุดตัดตามสัญลักษณ์ท้ายบรรทัดเดิม (เช่น ..\\., ..., !?, ?)
   - ให้คะแนนตามธรรมชาติของภาษาไทย (ตัดที่ช่องว่าง, หลังคำลงท้าย, หน้าคำเชื่อม)
4. Comprehensive Repair by Default:
   - ซ่อมแซมทุกแถวที่จำนวนบรรทัดไม่ตรงกับต้นฉบับโดยอัตโนมัติ (ครอบคลุมทั้งกรณี 1 บรรทัด และ 2 บรรทัดที่ต้นฉบับมี 3 บรรทัด)
"""

import os
import sys
import re
import csv
import json
import argparse
import io

from typing import List, Tuple, Optional, Set

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


class SmartLineSplitter:
    @staticmethod
    def extract_prefix(text: str) -> Tuple[str, str]:
        """สกัด Speaker Prefix เช่น \\n<Shion:> หรือ <Dan:>"""
        m = re.match(r"^(\s*\\n)?<[^>]+>", text)
        if m:
            prefix = m.group(0)
            pure = text[len(prefix):]
            return prefix, pure
        return "", text

    @staticmethod
    def find_tail_anchor(line_str: str) -> Optional[str]:
        """ค้นหาสัญลักษณ์หรือแท็กท้ายบรรทัดของ Original เพื่อใช้เป็น Anchor"""
        line_clean = line_str.rstrip()
        # 1. แท็กควบคุม RPG Maker ท้ายบรรทัด เช่น ..\., \., \|, \!, \^, \..
        m = re.search(r"(\.{2,}\\[\.\|\!\^]|\\\.\.|\\[\.\|\!\^]|\\[CNV]\[\d+\])+$", line_clean)
        if m:
            return m.group(0)
        # 2. จุดไข่ปลา หรือ เครื่องหมายคำพูด/อารมณ์ ท้ายบรรทัด เช่น ..., .., !?, ?, !, ♥, ~
        m = re.search(r"(\.{2,}|[!?~♥]+)+$", line_clean)
        if m:
            return m.group(0)
        return None

    INSEPARABLE_PATTERNS: List[str] = [
        # 1. กลุ่มคำนำหน้านามพหูพจน์ + สรรพนาม (เช่น พวกเธอ, พวกเรา, พวกเขา, พวกมัน, พวกนั้น, พวกนี้)
        r"พวก(?:เธอ|เรา|เขา|มัน|ท่าน|เจ้า|นาย|นั้น|นี้|โน้น|เด็กๆ?|ผู้หญิง|ผู้ชาย|คน|สาวๆ?|อันธพาล)",
        # 2. กลุ่มคำระบุชี้เฉพาะ (Demonstratives / Pronouns)
        r"(?:คน|สิ่ง|เรื่อง|อัน|แบบ|อย่าง|ทาง|ฝ่าย|ด้าน)(?:นี้|นั้น|โน้น|อื่น|ใด|ไหน)",
        r"(?:ตอน|คราว|เวลา|สมัย|ช่วง|ยุค)(?:นี้|นั้น|โน้น|ก่อน|หลัง|ไหน)",
        r"(?:ที่|ตรง)(?:นี้|นั้น|โน้น|ไหน|ใด|แห่งนี้|แห่งนั้น)",
        # 3. คำปฏิเสธ และ กริยานุเคราะห์ผสม
        r"ไม่(?:ได้|ใช่|มี|เคย|ยอม|ว่า|อยาก|ต้อง|เป็นไร|เอา|ถูก|จริง|พอ|ทัน)",
        r"(?:กำลัง|จะต้อง|น่าจะ|อาจจะ|ควรจะ|แทบจะ|เกือบจะ)",
        # 4. คำสรรพนามและคำคำถามผสม
        r"(?:อะไร|อย่างไร|ทำไม|เท่าไหร่|เท่าใด|เมื่อไหร่|ใคร)",
        # 5. คำเชื่อมและวลีต่อเนื่อง
        r"(?:เหมือนกัน|เช่นกัน|ด้วยกัน|ด้วยนะ|ด้วยสิ|ด้วยค่ะ|ด้วยครับ|ด้วยล่ะ)",
        r"(?:จริง(?:ๆ|จัง)?|แน่(?:นอน|ใจ)?|ชัด(?:เจน)?|จริงหรือ)",
        r"(?:สักพัก|สักหน่อย|นิดหน่อย|นิดเดียว|อีกหน่อย|อีกนิด|สักนิด)",
        # 6. คำนามประสมทั่วไปที่พบบ่อยในบทพูด
        r"(?:ผู้หญิง|ผู้ชาย|เด็กหญิง|เด็กชาย|ทุกคน|ทุกคนที่นี่|ใครบางคน|คนแปลกหน้า)",
    ]

    # ห้ามขึ้นต้นบรรทัดด้วยสระบน/ล่าง วรรณยุกต์ การันต์ ไม้ยมก หรือสระตามหลังเด็ดขาด
    ILLEGAL_LINE_STARTERS: Set[str] = set("ิีึืุูั่้๊๋์็๎ํะาำๆฯ)]}>”\"'’,~?!♥")

    @classmethod
    def get_forbidden_cut_ranges(cls, text: str) -> List[Tuple[int, int]]:
        """คำนวณช่วงดัชนีตัวอักษรที่ห้ามตัดตรงกลางคำเด็ดขาด"""
        ranges = []
        for pat in cls.INSEPARABLE_PATTERNS:
            for m in re.finditer(pat, text):
                ranges.append((m.start() + 1, m.end()))
        return ranges

    @classmethod
    def split_thai_to_match_original(cls, orig_text: str, init_text: str) -> str:
        """
        แบ่งข้อความภาษาไทย (init_text) ให้มีจำนวนบรรทัดเท่ากับ orig_text 100% (Strict Parity)
        พร้อมการเลือกจุดตัดที่สมบูรณ์แบบตามไวยากรณ์และความหมาย
        """
        if not orig_text or not init_text:
            return init_text

        orig_lines = orig_text.split("\n")
        num_target_lines = len(orig_lines)

        # ถ้าต้นฉบับมีบรรทัดเดียว ไม่ต้องตัด
        if num_target_lines <= 1:
            return init_text

        # สกัด prefix ของบรรทัดแรก
        orig_prefix, pure_orig_first = cls.extract_prefix(orig_lines[0])
        init_prefix, pure_init = cls.extract_prefix(init_text)

        # ยุบ newlines เดิมใน pure_init เป็นช่องว่างเดี่ยวเพื่อให้ตัดใหม่อย่างแม่นยำ
        pure_init = re.sub(r"\s*\n\s*", " ", pure_init).strip()

        # สร้าง pure_orig_lines (บรรทัดแรกตัด prefix ออก)
        pure_orig_lines = [pure_orig_first] + orig_lines[1:]

        # คำนวณสัดส่วนความยาวของแต่ละบรรทัดใน Original
        total_orig_len = max(1, sum(len(l.strip()) for l in pure_orig_lines))
        orig_proportions = [len(l.strip()) / total_orig_len for l in pure_orig_lines]

        cum_ratios = []
        c = 0.0
        for p in orig_proportions[:-1]:
            c += p
            cum_ratios.append(c)

        total_init_len = len(pure_init)

        # กรณีข้อความสั้นกว่าจำนวนบรรทัดที่ต้องการตัด (Edge Case ป้องกันแครช)
        if total_init_len < num_target_lines:
            lines = [f"{init_prefix}{pure_init}"] + [""] * (num_target_lines - 1)
            return "\n".join(lines)

        # นำเข้า PyThaiNLP สำหรับการตัดคำระดับพจนานุกรม
        try:
            from pythainlp.tokenize import word_tokenize
            tokens = word_tokenize(pure_init, engine="newmm")
        except Exception:
            tokens = [c for c in pure_init]

        token_spans = []
        cur_pos = 0
        for tok in tokens:
            token_spans.append((cur_pos, cur_pos + len(tok), tok))
            cur_pos += len(tok)

        # สกัดช่วงกลุ่มคำต้องห้ามที่ไม่ให้ตัดกลางคำ
        forbidden_ranges = cls.get_forbidden_cut_ranges(pure_init)

        # คำนวณความยาวขั้นต่ำของแต่ละบรรทัดแบบยืดหยุ่นตามความยาวจริงของข้อความ
        min_seg = max(1, min(5, total_init_len // (num_target_lines * 2)))

        split_indices = []
        prev_cut = 0

        for b_idx, target_ratio in enumerate(cum_ratios):
            orig_line_above = pure_orig_lines[b_idx]
            anchor = cls.find_tail_anchor(orig_line_above)

            # จุดตัดที่เหลือหลังจากจุดนี้
            rem_cuts = (num_target_lines - 1) - (b_idx + 1)

            # กำหนดขอบเขตที่ปลอดภัยเพื่อการันตีว่าจุดตัดจะไม่ชนกันและไม่ตกขอบ
            lower_bound = prev_cut + min_seg
            upper_bound = total_init_len - ((rem_cuts + 1) * min_seg)

            if lower_bound >= upper_bound:
                lower_bound = prev_cut + 1
                upper_bound = total_init_len - (rem_cuts + 1)
                if lower_bound >= upper_bound:
                    lower_bound = prev_cut + 1
                    upper_bound = prev_cut + 2

            ideal_idx = int(target_ratio * total_init_len)
            ideal_idx = max(lower_bound, min(upper_bound, ideal_idx))

            best_split = -1

            # ----------------------------------------------------
            # Stage 1: ค้นหา Tail Anchor เดิมที่ตรงกันในคำแปลไทย
            # ----------------------------------------------------
            if anchor:
                anchor_matches = [m.end() for m in re.finditer(re.escape(anchor), pure_init)]
                valid_anchors = [pos for pos in anchor_matches if lower_bound <= pos <= upper_bound]
                valid_anchors = [pos for pos in valid_anchors if not any(st <= pos < ed for st, ed in forbidden_ranges)]
                if valid_anchors:
                    best_split = min(valid_anchors, key=lambda pos: abs(pos - ideal_idx))

            # ----------------------------------------------------
            # Stage 2: ไวยากรณ์และขอบเขตคำ (Grammar-Aware Scoring)
            # ----------------------------------------------------
            if best_split == -1:
                valid_boundaries = []
                for start_t, end_t, tok in token_spans:
                    if lower_bound <= end_t <= upper_bound:
                        # ห้ามตัดผ่ากลางกลุ่มคำต้องห้าม
                        if any(st <= end_t < ed for st, ed in forbidden_ranges):
                            continue

                        # ตรวจสอบตัวอักษรแรกของคำถัดไป ต้องไม่เป็นสระบน/ล่าง วรรณยุกต์ หรือไม้ยมก
                        if end_t < len(pure_init):
                            next_ch = pure_init[end_t]
                            if next_ch in cls.ILLEGAL_LINE_STARTERS:
                                continue

                        score = abs(end_t - ideal_idx) * 1.5

                        # โบนัสตัดที่ช่องว่าง (Space): สูงสุด
                        if end_t < len(pure_init) and pure_init[end_t] == " ":
                            score -= 30
                        elif end_t > 0 and pure_init[end_t - 1] == " ":
                            score -= 30

                        # โบนัสตัดหลังเครื่องหมายวรรคตอน / จุดไข่ปลา
                        before_tok = pure_init[:end_t].rstrip()
                        if re.search(r"(\.{2,}|[!?~♥”\"'\)\]\}]+|\\[\.\|\!\^])$", before_tok):
                            score -= 25

                        # โบนัสตัดหลังคำลงท้าย / หางเสียง
                        if re.search(r"(?:ครับ|ค่ะ|นะคะ|นะ|จ้ะ|จ๊ะ|ละ|สิ|หรอก|เลย|ด้วย|เนอะ|ล่ะ)$", tok):
                            score -= 18

                        # โบนัสตัดหน้าคำเชื่อมประโยค (Conjunction)
                        after_text = pure_init[end_t:].lstrip()
                        if re.match(r"^(?:แต่|และ|หรือ|เพราะ|ถ้า|หาก|ดังนั้น|แล้ว|ก็|ซึ่ง|เพื่อ|แถม|ทั้งที่)\b", after_text):
                            score -= 15

                        # บทลงโทษหากคำถัดไปเป็นคำลงท้ายโดดๆ (Dangling particle)
                        first_after_word = after_text.split()[0] if after_text.split() else ""
                        if re.match(r"^(?:ครับ|ค่ะ|นะคะ|นะ|จ้ะ|จ๊ะ|ละ|สิ|หรอก|ล่ะ)$", first_after_word):
                            score += 45

                        valid_boundaries.append((score, end_t))

                if valid_boundaries:
                    valid_boundaries.sort(key=lambda x: x[0])
                    best_split = valid_boundaries[0][1]

            # ----------------------------------------------------
            # Stage 3: Relaxation (ผ่อนปรนหากไม่พบขอบเขตคำ)
            # ----------------------------------------------------
            if best_split == -1:
                candidates = []
                for pos in range(lower_bound, upper_bound + 1):
                    # กฎเหล็ก: ตัวอักษรถัดไปห้ามเป็นสระบน/ล่าง หรือวรรณยุกต์เด็ดขาด
                    if pos < len(pure_init) and pure_init[pos] in cls.ILLEGAL_LINE_STARTERS:
                        continue
                    penalty = abs(pos - ideal_idx)
                    # ให้คะแนนพิเศษหากพ้นกลุ่มคำต้องห้าม
                    if any(st <= pos < ed for st, ed in forbidden_ranges):
                        penalty += 50
                    if pos < len(pure_init) and pure_init[pos] == " ":
                        penalty -= 20
                    candidates.append((penalty, pos))

                if candidates:
                    candidates.sort(key=lambda x: x[0])
                    best_split = candidates[0][1]

            # ----------------------------------------------------
            # Stage 4: Absolute Safety Fallback
            # ----------------------------------------------------
            if best_split == -1:
                best_split = max(lower_bound, min(upper_bound, ideal_idx))
                # ขยับให้ไม่ชนสระบน/ล่าง
                while best_split < upper_bound and pure_init[best_split] in cls.ILLEGAL_LINE_STARTERS:
                    best_split += 1

            split_indices.append(best_split)
            prev_cut = best_split

        # --------------------------------------------------------
        # Strict Invariant Verification: รับประกันจำนวนชิ้นส่วน 100%
        # --------------------------------------------------------
        # เรียงลำดับและขจัดจุดซ้ำ
        split_indices = sorted(list(set(split_indices)))

        # หากจำนวนจุดตัดน้อยกว่าที่ต้องการ ให้กระจายจุดตัดใหม่แบบการันตีระยะห่าง
        if len(split_indices) < num_target_lines - 1:
            step = max(1, total_init_len // num_target_lines)
            split_indices = [step * (i + 1) for i in range(num_target_lines - 1)]

        # ตัดข้อความออกเป็นส่วนๆ
        parts = []
        prev = 0
        for s_idx in split_indices:
            seg = pure_init[prev:s_idx].strip()
            parts.append(seg)
            prev = s_idx
        parts.append(pure_init[prev:].strip())

        # ป้องกันกรณีมี segment ใดเป็นสตริงว่าง
        for i in range(len(parts)):
            if not parts[i] and i + 1 < len(parts) and len(parts[i + 1]) > 2:
                # ดึงตัวอักษรบางส่วนมาเติม
                parts[i] = parts[i + 1][:1]
                parts[i + 1] = parts[i + 1][1:]

        # ปรับแก้จำนวน parts ให้เท่ากับ num_target_lines เสมอ
        while len(parts) > num_target_lines:
            parts[-2] = f"{parts[-2]} {parts[-1]}".strip()
            parts.pop()
        while len(parts) < num_target_lines:
            parts.append("")

        # ประกอบกลับเป็นข้อความหลายบรรทัด
        final_lines = []
        for idx, p in enumerate(parts):
            if idx == 0:
                final_lines.append(f"{init_prefix}{p}")
            else:
                final_lines.append(p)

        return "\n".join(final_lines)


def run_tests():
    """ทดสอบกรณีตัวอย่างจริงและ Edge Cases ทั้งหมด"""
    test_cases = [
        # เคส 1: 2 บรรทัดพร้อม ..\.
        {
            "name": "Shion Row 170 (2 lines with ..\\.)",
            "orig": "\\n<Shion:>..Dan..don't you think..\\.\nthat the air here is.. ",
            "init": "\\n<Shion:>..Dan..คุณไม่คิดเหรอคะ..\\. ว่าอากาศที่นี่มัน.."
        },
        # เคส 2: 2 บรรทัดพร้อม ..\.
        {
            "name": "Shion Row 171 (2 lines with ..\\.)",
            "orig": "\\n<Shion:>I..don't know how to put it..\\.\nbut ha..\\.it just feels so..",
            "init": "\\n<Shion:>ฉัน..ไม่รู้จะอธิบายยังไงดีค่ะ..\\. แต่ฮะ..\\. มันให้ความรู้สึกเหมือน.."
        },
        # เคส 3: 3 บรรทัดยาว
        {
            "name": "Shion Row 173 (3 lines long prose)",
            "orig": "\\n<Shion:>Knowing that you can have that kind \nof excitement everyday might be why everyone\nhere is so lively..",
            "init": "\\n<Shion:>การที่รู้ว่าทุกวันอาจได้เจอเรื่องน่าตื่นเต้นแบบนั้น อาจเป็นเหตุผลว่าทำไมทุกคนที่นี่ถึงดูคึกคักกันขนาดนี้ก็ได้นะคะ.."
        },
        # เคส 4: 3 บรรทัดพร้อม \\.
        {
            "name": "Shion Row 174 (3 lines with \\.)",
            "orig": "\\n<Shion:>I'm being weird..huh?\\.\nHahah..s-sorry..it's just being here..\\.\nbut even if its only for awhile...\\.",
            "init": "\\n<Shion:>ฉันพูดอะไรแปลกๆ ใช่ไหมคะ..\\. ฮ่าๆ..ข-ขอโทษค่ะ.. แค่การได้มาอยู่ที่นี่..\\. ถึงจะเป็นเพียงช่วงเวลาสั้นๆ ก็เถอะ...\\."
        },
        # เคส 5: คำประสมห้ามผ่า (พวกเธอ / พวกเรา)
        {
            "name": "Jinnie Row 465 (พวกเธอ / พวกเรา Inseparable Compound Test)",
            "orig": "\\n<Jinnie:>I got lucky with you two here~!\n\\fiWe'll\\fi help solve all of that.",
            "init": "\\n<Jinnie:>ฉันโชคดีจริง ๆ ที่มีพวกเธอสองคนอยู่ที่นี่~! \\fiพวกเรา\\fiจะช่วยกันแก้ปัญหาทั้งหมดนั่นเองค่ะ"
        },
        # เคส 6: 2 บรรทัดข้อความสั้นมาก
        {
            "name": "Short Dialogue (2 lines)",
            "orig": "Dan..?\nWhat is it?",
            "init": "\\n<Shion:>แดน...? มีอะไรเหรอคะ?"
        },
        # เคส 7: 3 บรรทัดข้อความสั้น
        {
            "name": "Short Dialogue (3 lines)",
            "orig": "One...\nTwo...\nThree!",
            "init": "หนึ่ง... สอง... สาม!"
        },
        # เคส 8: เดิมแปลมา 2 บรรทัด แต่ต้นฉบับมี 3 บรรทัด (แก้ไขเคส 3 บรรทัดมีแค่ 2)
        {
            "name": "Mismatched 2 lines input vs 3 lines original",
            "orig": "Wait a minute...\nAre you serious?\nI can't believe this!",
            "init": "\\n<Dan:>เดี๋ยวนะ... นี่เธอพูดจริงเหรอ?\nฉันไม่อยากจะเชื่อเลย!"
        },
    ]

    print("=" * 75)
    print("🧪 RUNNING COMPREHENSIVE UNIT TESTS ON LINE SPLITTER")
    print("=" * 75)

    passed = 0
    for tc in test_cases:
        print(f"\n--- Test: {tc['name']} ---")
        orig_count = tc["orig"].count("\n") + 1
        repaired = SmartLineSplitter.split_thai_to_match_original(tc["orig"], tc["init"])
        rep_count = repaired.count("\n") + 1

        print(f"Original ({orig_count} lines):\n{repr(tc['orig'])}")
        print(f"Input Initial:\n{repr(tc['init'])}")
        print(f"Repaired Output ({rep_count} lines):\n{repr(repaired)}")
        print(f"Formatted Output:\n{repaired}")

        if orig_count == rep_count:
            print("✅ PASSED: Line count matches target perfectly!")
            passed += 1
        else:
            print(f"❌ FAILED: Expected {orig_count} lines, got {rep_count} lines!")

    print("\n" + "=" * 75)
    print(f"🏁 SUMMARY: {passed}/{len(test_cases)} tests passed.")
    if passed == len(test_cases):
        print("🎉 ALL TESTS PASSED SUCCESSFULLY 100%!")
    print("=" * 75)


def repair_file(csv_path, checkpoint_path=None, dry_run=False, limit=None, only_single_lines=False):
    """
    ตรวจสอบและซ่อมแซมจำนวนบรรทัดในไฟล์ CSV ให้ตรงกับต้นฉบับ
    Default: ซ่อมแซมทุกแถวที่จำนวนบรรทัดไม่ตรงกับต้นฉบับ (init_nl != orig_nl)
    """
    print("=" * 75)
    print(f"🛠️ REPAIR LINE BREAKS: {csv_path}")
    print(f"Mode: {'DRY RUN (Simulation only)' if dry_run else 'LIVE REPAIR (Modifying CSV & Checkpoint)'}")
    print(f"Target: {'Only un-split single lines (init_nl == 0)' if only_single_lines else 'All differing line counts (Comprehensive Parity)'}")
    print("=" * 75)

    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [header] + list(reader)

    print(f"Total CSV Rows: {len(rows)}")

    checkpoint_data = None
    csv_key = os.path.basename(csv_path)
    if checkpoint_path and os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
                print(f"Loaded checkpoint from: {checkpoint_path}")
        except Exception as e:
            print(f"Warning reading checkpoint: {e}")

    repaired_count = 0
    examples = []

    for r_idx in range(1, len(rows)):
        row = rows[r_idx]
        if len(row) < 2:
            continue
        orig = row[0]
        init = row[1]

        orig_nl = orig.count("\n")
        init_nl = init.count("\n")

        # ตรวจจับแถวที่ต้องตัดแบ่งบรรทัดใหม่
        should_repair = False
        if orig_nl > 0 and init.strip():
            if only_single_lines:
                if init_nl == 0:
                    should_repair = True
            else:
                # ซ่อมแซมทุกแถวที่จำนวนบรรทัดไม่ตรงกับต้นฉบับ
                if init_nl != orig_nl:
                    should_repair = True

        if should_repair:
            new_init = SmartLineSplitter.split_thai_to_match_original(orig, init)
            if new_init != init:
                repaired_count += 1
                if len(examples) < 15:
                    examples.append((r_idx, orig, init, new_init))
                if not dry_run:
                    row[1] = new_init
                    if checkpoint_data and "csv_translations" in checkpoint_data:
                        checkpoint_data["csv_translations"].setdefault(csv_key, {})[str(r_idx)] = new_init
                        checkpoint_data["csv_translations"].setdefault("SSPV034v1.35 - Trans - Processed_v3.csv", {})[str(r_idx)] = new_init
                        checkpoint_data["csv_translations"].setdefault("SSPV034v1.35 - Trans - Processed_v3_translated.csv", {})[str(r_idx)] = new_init

                if limit and repaired_count >= limit:
                    break

    print(f"\n📊 RESULTS:")
    print(f"  • Total Mismatched Rows Found & Repaired: {repaired_count}")

    print("\n🔍 SAMPLE REPAIRS (First 5 examples):")
    for r_idx, orig, old_init, new_init in examples[:5]:
        orig_cnt = orig.count("\n") + 1
        old_cnt = old_init.count("\n") + 1
        new_cnt = new_init.count("\n") + 1
        print(f"\n[Row {r_idx}]")
        print(f"  ORIG ({orig_cnt} lines):\n{orig}")
        print(f"  BEFORE ({old_cnt} lines):\n{old_init}")
        print(f"  AFTER ({new_cnt} lines):\n{new_init}")

    if dry_run:
        print("\n💡 This was a DRY RUN (Simulation). NO files were modified.")
        print("   To apply changes for real, run without --dry-run")
    else:
        import shutil
        import datetime
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. สำรองไฟล์ CSV เดิมแบบ Timestamped ทุกครั้งที่รันจริง
        bak_csv = f"{csv_path}.backup_{now_str}.csv"
        shutil.copy2(csv_path, bak_csv)
        print(f"\n💾 Created full CSV backup at: {bak_csv}")

        # 2. สำรองไฟล์ Checkpoint แบบ Timestamped
        if checkpoint_data and checkpoint_path and os.path.exists(checkpoint_path):
            bak_cp = f"{checkpoint_path}.backup_{now_str}.json"
            shutil.copy2(checkpoint_path, bak_cp)
            print(f"💾 Created full Checkpoint backup at: {bak_cp}")

        # 3. เขียนไฟล์ CSV ใหม่แบบ Atomic (.tmp -> replace)
        temp_csv = csv_path + ".tmp"
        with open(temp_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        os.replace(temp_csv, csv_path)
        print(f"✅ Successfully wrote repaired lines to: {csv_path}")

        # 4. อัปเดต Checkpoint
        if checkpoint_data and checkpoint_path:
            temp_cp = checkpoint_path + ".tmp"
            with open(temp_cp, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            os.replace(temp_cp, checkpoint_path)
            print(f"✅ Successfully synced repaired translations into checkpoint: {checkpoint_path}")


def restore_backup(backup_csv_path, target_csv_path=None, backup_cp_path=None, target_cp_path=None):
    """กู้คืนไฟล์จาก Backup ในกรณีที่ต้องการย้อนกลับ (Rollback)"""
    import shutil
    print("=" * 75)
    print("🔄 RESTORING FROM BACKUP")
    print("=" * 75)
    if not os.path.exists(backup_csv_path):
        print(f"❌ Backup file not found: {backup_csv_path}")
        return

    if not target_csv_path:
        target_csv_path = backup_csv_path.split(".backup_")[0]

    shutil.copy2(backup_csv_path, target_csv_path)
    print(f"✅ Restored CSV to: {target_csv_path}")

    if backup_cp_path and target_cp_path and os.path.exists(backup_cp_path):
        shutil.copy2(backup_cp_path, target_cp_path)
        print(f"✅ Restored Checkpoint to: {target_cp_path}")
    print("🎉 Rollback completed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Line-Break Restorer for RPG Maker Translations")
    parser.add_argument("--test", action="store_true", help="Run unit tests on sample rows")
    parser.add_argument("--file", type=str, default="Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated (1).csv", help="Target CSV file")
    parser.add_argument("--checkpoint", type=str, default="data/tlas/chatgpt_translation_checkpoint.json", help="Checkpoint path")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without modifying files")
    parser.add_argument("--only-single-lines", action="store_true", help="Only repair single un-split lines (init_nl == 0)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to repair")
    parser.add_argument("--restore", type=str, default=None, help="Restore from specified backup CSV file")
    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.restore:
        restore_backup(args.restore, target_csv_path=args.file)
    else:
        repair_file(args.file, checkpoint_path=args.checkpoint, dry_run=args.dry_run, limit=args.limit, only_single_lines=args.only_single_lines)
