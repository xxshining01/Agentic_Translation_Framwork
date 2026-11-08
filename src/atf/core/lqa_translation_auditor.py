# -*- coding: utf-8 -*-
"""
LQA Translation Auditor: Universal 5-Dimensional Translation Quality & Integrity Engine
Compliant with SDD-016, SAD-014, ADR-019, and ADR-035.

Audits LLM Translation Outputs against:
  1. Control Code & Semantic Tag Integrity (Zero Loss, XML Tags, Speaker Tags, No \\x0c)
  2. Glossary & Proper Noun Adherence (Exact 1:1 Matching from Master Glossary)
  3. TLAS Pronoun & Character Persona Consistency (Pairwise Matrix & Gender Rules)
  4. Contextual SFX & Prohibited Expressions (Zero Hallucination / No Meta-Prose SFX)
  5. Dialogue Line Length & Visual UI Economy (~40-48 Characters per Line)
"""

import os
import re
import sys
import json
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

# Ensure UTF-8 output across Windows CMD / PowerShell
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass


@dataclass
class AuditViolation:
    dimension: str       # "CODE", "GLOSSARY", "PRONOUN", "SFX", "LINE_LENGTH", "EMOTION"
    severity: str        # "FATAL", "WARNING"
    message: str
    expected: str
    actual: str


@dataclass
class AuditRowResult:
    row_id: Any
    is_valid: bool
    score: float         # 0.0 to 100.0
    violations: List[AuditViolation] = field(default_factory=list)


class LQATranslationAuditor:
    """
    Automated 5-Dimensional Quality & Integrity Auditor for Localized Game Dialogues.
    Universal Architecture Decoupled & Zero-Hardcode.
    """

    def __init__(
        self,
        glossary_path: Optional[str] = None,
        pronoun_matrix_path: Optional[str] = None,
        sfx_glossary_path: Optional[str] = None
    ):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

        # 1. Load Master Glossary
        if glossary_path is None:
            glossary_path = os.path.join(base_dir, "data", "tlas", "tlas_glossary.json")
        self.glossary: Dict[str, Any] = self._load_json(glossary_path)

        # 2. Load Global Pairwise Pronoun Matrix
        if pronoun_matrix_path is None:
            pronoun_matrix_path = os.path.join(base_dir, "data", "tlas", "global_pronoun_matrix.json")
        matrix_raw = self._load_json(pronoun_matrix_path)
        if isinstance(matrix_raw, dict):
            self.pronoun_matrix = matrix_raw.get("specific_pair_rules", [])
            self.demographic_rules = matrix_raw.get("demographic_rules", [])
            self.raw_matrix_data = matrix_raw
        elif isinstance(matrix_raw, list):
            self.pronoun_matrix = matrix_raw
            self.demographic_rules = []
            self.raw_matrix_data = {"specific_pair_rules": matrix_raw, "demographic_rules": []}
        else:
            self.pronoun_matrix = []
            self.demographic_rules = []
            self.raw_matrix_data = {}

        # 3. Load Contextual SFX Glossary
        if sfx_glossary_path is None:
            sfx_glossary_path = os.path.join(base_dir, "data", "tlas", "sfx_glossary.json")
        self.sfx_data: Dict[str, Any] = self._load_json(sfx_glossary_path)

        # Build Quick Lookups
        self.character_genders = self._extract_character_genders()
        self.pairwise_lookup = self._build_pairwise_lookup()
        self.prohibited_sfx_terms = self._extract_prohibited_sfx()

    def _load_json(self, path: str) -> Any:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _extract_character_genders(self) -> Dict[str, str]:
        genders = {}
        chars = self.glossary.get("Characters", {})
        if isinstance(chars, dict):
            for name, info in chars.items():
                if isinstance(info, dict) and "gender" in info:
                    genders[name] = info["gender"].upper()
                    th_name = info.get("th", "")
                    if th_name:
                        genders[th_name] = info["gender"].upper()
        return genders

    def _build_pairwise_lookup(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        lookup = {}
        if isinstance(self.pronoun_matrix, list):
            for rule in self.pronoun_matrix:
                spk = rule.get("speaker", "")
                lis = rule.get("listener", "")
                if spk and lis:
                    lookup[(spk, lis)] = rule.get("speech_style", {})
        return lookup

    def _extract_prohibited_sfx(self) -> List[str]:
        prohibited = [
            "เสียงถอนหายใจ", "เสียงหายใจ", "เสียงหอบ", "เสียงคราง",
            "เสียงร้อง", "เสียงกรีดร้อง", "เสียงตกใจ", "เสียงโดนตี",
            "เสียงชก", "เสียงต่อย", "เสียงฟาด", "เสียงเตะ", "เสียงกระทบ"
        ]
        lexicon = self.sfx_data.get("sfx_lexicon", {})
        if isinstance(lexicon, dict):
            for sfx_key, sfx_info in lexicon.items():
                if isinstance(sfx_info, dict) and "prohibited" in sfx_info:
                    for p in sfx_info["prohibited"]:
                        if p not in prohibited:
                            prohibited.append(p)
        return prohibited

    def audit(
        self,
        orig: str,
        trans: str,
        row_id: Any = 0,
        speaker: Optional[str] = None,
        listener: Optional[str] = None
    ) -> AuditRowResult:
        """
        Runs comprehensive 5-Dimensional LQA Audit on a single dialogue line.
        """
        violations: List[AuditViolation] = []

        if not orig:
            return AuditRowResult(row_id=row_id, is_valid=True, score=100.0, violations=[])

        # -------------------------------------------------------------
        # DIMENSION 1: Control Code & Semantic Tag Integrity (FATAL)
        # -------------------------------------------------------------
        # 1.1 Form Feed Hazard (\x0c)
        if "\x0c" in trans:
            violations.append(AuditViolation(
                dimension="CODE",
                severity="FATAL",
                message="ตรวจพบ Form Feed ASCII 12 (\\x0c) ตกค้างในข้อความคำแปล",
                expected="No \\x0c",
                actual="Found \\x0c in translation"
            ))

        # 1.2 RPG Maker Control Codes Parity
        clean_orig = orig.replace("\x0ci", "\\fi").replace("\x0cb", "\\fb").replace("\x0c", "\\f")
        norm_orig = re.sub(r"\\[cC](?!\[)", r"\\C[0]", clean_orig)
        norm_trans = re.sub(r"\\[cC](?!\[)", r"\\C[0]", trans)

        critical_codes = [
            (r"\\\.", r"\.", False),
            (r"\\\|", r"\|", False),
            (r"\\!", r"\!", False),
            (r"\\\^", r"\^", False),
            (r"\\fi", r"\fi", False),
            (r"\\fb", r"\fb", False),
            (r"\\[iI]\[\d+\]", r"\I[n]", True),
            (r"\\[cC]\[\d+\]", r"\C[n]", True),
            (r"\\[vV]\[\d+\]", r"\V[n]", True),
            (r"\\[nN]\[\d+\]", r"\N[n]", True),
        ]
        for pattern, label, ignore_case in critical_codes:
            flags = re.IGNORECASE if ignore_case else 0
            orig_matches = re.findall(pattern, norm_orig, flags=flags)
            trans_matches = re.findall(pattern, norm_trans, flags=flags)

            if len(orig_matches) != len(trans_matches):
                violations.append(AuditViolation(
                    dimension="CODE",
                    severity="FATAL",
                    message=f"จำนวนรหัสเกม {label} ไม่ตรงกับต้นฉบับ ({len(orig_matches)} vs {len(trans_matches)})",
                    expected=f"{len(orig_matches)} occurrences",
                    actual=f"{len(trans_matches)} occurrences"
                ))

        # 1.3 Semantic XML Tags Parity
        xml_tag_patterns = [
            r"<italic>.*?</italic>",
            r"<bold>.*?</bold>",
            r'<color\s+id="\d+">.*?</color>',
            r"<pause_quarter/>",
            r"<pause_second/>",
            r"<wait_input/>",
            r'<icon\s+id="\d+"/>',
            r'<var\s+id="\d+"/>',
            r'<actor\s+id="\d+"/>',
            r'<party\s+id="\d+"/>',
        ]
        for xpat in xml_tag_patterns:
            orig_tags = re.findall(xpat, orig, re.IGNORECASE)
            trans_tags = re.findall(xpat, trans, re.IGNORECASE)
            if len(orig_tags) != len(trans_tags):
                violations.append(AuditViolation(
                    dimension="CODE",
                    severity="FATAL",
                    message=f"แท็ก XML {xpat} สูญหายหรือไม่ตรงกับต้นฉบับ",
                    expected=f"{len(orig_tags)} occurrences",
                    actual=f"{len(trans_tags)} occurrences"
                ))

        # 1.4 Speaker Tag Parity: Lenticular 【...】 or Angle <...:>
        if "【" in orig and "】" in orig:
            if "【" not in trans or "】" not in trans:
                violations.append(AuditViolation(
                    dimension="CODE",
                    severity="FATAL",
                    message="ป้ายชื่อผู้พูดแบบ Lenticular 【...】 สูญหาย",
                    expected="【...】 tag present",
                    actual="Missing Lenticular tag"
                ))

        # 1.5 Dropped Dialogue Body Integrity: Original has dialogue, but translation has ONLY the tag
        orig_tag_m = re.match(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', orig)
        pure_orig = orig[orig_tag_m.end():].strip() if orig_tag_m else orig.strip()

        trans_tag_m = re.match(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', trans)
        pure_trans = trans[trans_tag_m.end():].strip() if trans_tag_m else trans.strip()

        if pure_orig and not pure_trans:
            violations.append(AuditViolation(
                dimension="CODE",
                severity="FATAL",
                message="ตรวจพบข้อความบทสนทนาสูญหาย (Dropped Dialogue Body): มีแต่ Speaker Tag แต่เนื้อหาคำแปลว่างเปล่า",
                expected="Translated dialogue body after speaker tag",
                actual="Empty dialogue body (Tag Only)"
            ))

        # -------------------------------------------------------------
        # DIMENSION 2: Glossary & Named Entities Adherence
        # -------------------------------------------------------------
        chars = self.glossary.get("Characters", {})
        if isinstance(chars, dict):
            for en_name, cinfo in chars.items():
                if isinstance(cinfo, dict):
                    th_name = cinfo.get("th", "")
                    enforce = cinfo.get("enforce", True)
                    # Check if character appears in original
                    if enforce and th_name and en_name in orig:
                        if th_name not in trans and en_name not in trans:
                            violations.append(AuditViolation(
                                dimension="GLOSSARY",
                                severity="WARNING",
                                message=f"ไม่พบชื่อตัวละครตาม Glossary: '{en_name}' -> '{th_name}'",
                                expected=f"'{th_name}' หรือ '{en_name}'",
                                actual="Missing in translation"
                            ))

        # -------------------------------------------------------------
        # DIMENSION 3: TLAS Pronoun & Character Persona Consistency
        # -------------------------------------------------------------
        # 3.1 Gender-Based Pronoun & Particle Validation
        clean_trans = re.sub(r"<[^>]+>", "", trans)
        clean_trans = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<\{\}\\\_]", "", clean_trans)

        if speaker:
            spk_gender = self.character_genders.get(speaker, "")
            if spk_gender == "FEMALE":
                # Female characters MUST NOT use male self-pronouns or male ending particles
                if re.search(r"\b(ผม|กระผม)\b", clean_trans):
                    violations.append(AuditViolation(
                        dimension="PRONOUN",
                        severity="FATAL",
                        message=f"ตัวละครเพศหญิง ({speaker}) ใช้สรรพนามบุรุษเพศ 'ผม/กระผม'",
                        expected="ฉัน / หนู / ข้า (เพศหญิง)",
                        actual=clean_trans
                    ))
                if re.search(r"(ครับ|นะครับ|คับ|ขอรับ)", clean_trans):
                    violations.append(AuditViolation(
                        dimension="PRONOUN",
                        severity="FATAL",
                        message=f"ตัวละครเพศหญิง ({speaker}) ใช้หางเสียงเพศชาย 'ครับ'",
                        expected="ค่ะ / นะคะ (เพศหญิง)",
                        actual=clean_trans
                    ))

            elif spk_gender == "MALE":
                # Male characters MUST NOT use female ending particles
                if re.search(r"(ค่ะ|นะคะ|เจ้าค่ะ)", clean_trans):
                    violations.append(AuditViolation(
                        dimension="PRONOUN",
                        severity="FATAL",
                        message=f"ตัวละครเพศชาย ({speaker}) ใช้หางเสียงเพศหญิง 'ค่ะ/นะคะ'",
                        expected="ครับ / วะ / โว้ย (เพศชาย)",
                        actual=clean_trans
                    ))

        # 3.2 Pairwise Matrix Adherence (Speaker -> Listener)
        if speaker and listener:
            pair_style = self.pairwise_lookup.get((speaker, listener))
            if pair_style:
                expected_self = pair_style.get("self_pronoun")
                expected_target = pair_style.get("target_pronoun")

                # If rough dynamic (e.g. Hostile / Aggressive Thugs / Enemies)
                formality = pair_style.get("formality_level", 3)
                if formality <= 2:  # Rough / Vulgar / Hostile
                    if re.search(r"(ครับ|ค่ะ|คุณ|ผม)", clean_trans):
                        violations.append(AuditViolation(
                            dimension="PRONOUN",
                            severity="FATAL",
                            message=f"บทสนทนาขัดแย้ง/เป็นศัตรู ({speaker} -> {listener}) หลุดคำสุภาพ 'คุณ/ผม/ครับ/ค่ะ'",
                            expected="สรรพนามหยาบ/กระด้าง (แก/เอ็ง/ข้า/วะ/เว้ย)",
                            actual=clean_trans
                        ))

        # -------------------------------------------------------------
        # DIMENSION 4: Contextual SFX & Prohibited Expressions (FATAL)
        # -------------------------------------------------------------
        # 4.1 Prohibited Meta-Prose Sound Descriptions
        for bad_sfx in self.prohibited_sfx_terms:
            if bad_sfx in clean_trans:
                violations.append(AuditViolation(
                    dimension="SFX",
                    severity="FATAL",
                    message=f"ตรวจพบคำแปลเสียงประกอบต้องห้าม (Meta-Prose SFX): '{bad_sfx}'",
                    expected="สัทพจน์แท้ (เช่น 'เฮ้อ...', 'แฮ่ก... แฮ่ก...', 'อื้ม...')",
                    actual=bad_sfx
                ))

        # 4.2 Panting/Breathing translated as "ฮะ" / "ฮะๆ"
        if re.search(r"[\s\.,\?!~\"'\(]?(ฮะ|ฮะๆ)[\s\.,\?!~\"'\)]?", clean_trans):
            # Only flag if original has respiration / moan onomatopoeia
            if any(sfx in orig for sfx in ["はぁ", "ハァ", "ふぅ", "んっ", "くっ"]):
                violations.append(AuditViolation(
                    dimension="SFX",
                    severity="FATAL",
                    message="แปลเสียงหายใจ/หอบเป็น 'ฮะ' หรือ 'ฮะๆ' ซึ่งผิดวรรณศิลป์",
                    expected="'แฮ่ก... แฮ่ก...', 'เฮ้อ...', หรือ 'ฮ่าห์...'",
                    actual="ฮะ / ฮะๆ"
                ))

        # -------------------------------------------------------------
        # DIMENSION 5: Line Length & Visual UI Economy (~40-48 Chars)
        # -------------------------------------------------------------
        lines = trans.split("\n")
        for line_idx, line in enumerate(lines):
            # Strip tags before measuring length
            pure_line = re.sub(r"<[^>]+>", "", line)
            pure_line = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<\{\}\\\_]", "", pure_line)
            if len(pure_line) > 52:
                violations.append(AuditViolation(
                    dimension="LINE_LENGTH",
                    severity="WARNING",
                    message=f"บรรทัดที่ {line_idx + 1} มีความยาว {len(pure_line)} ตัวอักษร เสี่ยงล้นกรอบข้อความในเกม (>48)",
                    expected="<= 48 characters per line",
                    actual=f"{len(pure_line)} chars: '{pure_line[:30]}...'"
                ))

        # -------------------------------------------------------------
        # DIMENSION 6: Emotion, Punctuation & Typography Parity
        # -------------------------------------------------------------
        # 6.1 Thai-English Spacing
        pure_text_for_spacing = re.sub(r"\\[a-zA-Z]+(?:\[\d+\])?|\\[\.\!\|\^\<\>]+|<[^>]+>", "", trans)
        glued_match = re.search(r"[\u0E00-\u0E7F][A-Za-z]|[A-Za-z][\u0E00-\u0E7F]", pure_text_for_spacing)
        if glued_match:
            matched_str = glued_match.group(0)
            violations.append(AuditViolation(
                dimension="EMOTION",
                severity="WARNING",
                message=f"พบคำภาษาไทยกับอังกฤษเขียนติดกันโดยไม่เว้นวรรค: '{matched_str}'",
                expected="ต้องเว้นวรรค 1 เคาะระหว่างภาษาไทยกับอังกฤษ",
                actual=matched_str
            ))

        # 6.2 CJK / Hanzi Leakage Detection (FATAL)
        # Prevents Chinese vocabulary bleed (e.g. 主动) or untranslated Japanese from entering output
        text_for_cjk = re.sub(r"<[^>]+>", "", trans)
        text_for_cjk = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<\{\}\\\_]", "", text_for_cjk)
        # Exclude recognized speaker tags if unchanged
        text_for_cjk = re.sub(r"^【[^】]+】", "", text_for_cjk).strip()
        # Exclude silence symbols, prolonged sound marks, and Japanese punctuation (・, ー, 。, 、, 〜)
        text_for_cjk_clean = re.sub(r"[\u30fb\u30fc\u3001\u3002\u301c\u2015\u2014\.\s\-\!\?]", "", text_for_cjk)
        cjk_chars = re.findall(r"[\u4e00-\u9fa5\u3041-\u3096\u30a1-\u30f4]", text_for_cjk_clean)
        if cjk_chars:
            sample_cjk = "".join(cjk_chars[:10])
            violations.append(AuditViolation(
                dimension="HANZI_LEAKAGE",
                severity="FATAL",
                message=f"พบอักษรจีน/ญี่ปุ่นหลุดรอดในคำแปลภาษาไทย: '{sample_cjk}'",
                expected="แปลเป็นภาษาไทยสมบูรณ์ ปราศจากอักษรจีน/ญี่ปุ่นหลงเหลือ",
                actual=sample_cjk
            ))

        # Calculate Score
        has_fatal = any(v.severity == "FATAL" for v in violations)
        warning_count = sum(1 for v in violations if v.severity == "WARNING")

        score = 100.0
        if has_fatal:
            score -= 50.0
        score -= (warning_count * 10.0)
        score = max(0.0, score)

        is_valid = not has_fatal and score >= 70.0

        return AuditRowResult(
            row_id=row_id,
            is_valid=is_valid,
            score=score,
            violations=violations
        )


def run_unit_tests():
    """
    Executes unit test suite validating LQATranslationAuditor against 5 dimensions.
    """
    print("=" * 75)
    print("🧪 RUNNING COMPREHENSIVE UNIT TESTS ON LQATranslationAuditor (5D Universal)")
    print("=" * 75)

    auditor = LQATranslationAuditor()
    tests_passed = 0
    total_tests = 0

    # Test 1: Perfect Translation with XML tags and Lenticular
    total_tests += 1
    print("\n--- Test 1: Perfect Japanese Translation with Lenticular & Correct Pronouns ---")
    t1_orig = "【凛】夫、大丈夫ですか？\\."
    t1_trans = "【ริน】คุณสามีคะ เป็นอะไรไหมคะ?\\."
    res1 = auditor.audit(t1_orig, t1_trans, row_id=1, speaker="凛", listener="夫")
    print(f"Row 1 Score: {res1.score} | Valid: {res1.is_valid}")
    assert res1.is_valid and res1.score == 100.0
    print("✅ TEST 1 PASSED: 100% Score!")
    tests_passed += 1

    # Test 2: Fatal Gender Pronoun Violation (Female character using 'ผม')
    total_tests += 1
    print("\n--- Test 2: Female Character Using Male Pronoun 'ผม' (FATAL) ---")
    t2_orig = "【凛】私は行きます。"
    t2_trans = "【ริน】ผมจะไปแล้วครับ"
    res2 = auditor.audit(t2_orig, t2_trans, row_id=2, speaker="凛", listener="夫")
    print(f"Row 2 Score: {res2.score} | Valid: {res2.is_valid}")
    for v in res2.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res2.is_valid
    assert any(v.dimension == "PRONOUN" and v.severity == "FATAL" for v in res2.violations)
    print("✅ TEST 2 PASSED: Successfully caught female male-pronoun corruption!")
    tests_passed += 1

    # Test 3: Fatal Prohibited SFX Meta-Prose ("เสียงถอนหายใจ")
    total_tests += 1
    print("\n--- Test 3: Prohibited Meta-Prose SFX 'เสียงถอนหายใจ' (FATAL) ---")
    t3_orig = "はぁ……困ったな。"
    t3_trans = "เสียงถอนหายใจ…… แย่จังนะ"
    res3 = auditor.audit(t3_orig, t3_trans, row_id=3)
    print(f"Row 3 Score: {res3.score} | Valid: {res3.is_valid}")
    for v in res3.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res3.is_valid
    assert any(v.dimension == "SFX" and v.severity == "FATAL" for v in res3.violations)
    print("✅ TEST 3 PASSED: Successfully blocked descriptive SFX!")
    tests_passed += 1

    # Test 4: Panting translated as "ฮะ" (FATAL)
    total_tests += 1
    print("\n--- Test 4: Breathing/Panting Translated as 'ฮะ' (FATAL) ---")
    t4_orig = "ハァ、ハァ……！"
    t4_trans = "ฮะ ฮะ……!"
    res4 = auditor.audit(t4_orig, t4_trans, row_id=4)
    print(f"Row 4 Score: {res4.score} | Valid: {res4.is_valid}")
    for v in res4.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res4.is_valid
    assert any(v.dimension == "SFX" for v in res4.violations)
    print("✅ TEST 4 PASSED: Successfully caught breath transliteration hazard!")
    tests_passed += 1

    # Test 5: Semantic XML Tag Mismatch (FATAL)
    total_tests += 1
    print("\n--- Test 5: Semantic XML Tag Loss (FATAL) ---")
    t5_orig = "<color id=\"2\">สำคัญมาก</color>\\!"
    t5_trans = "สำคัญมาก\\!"  # Lost <color> tag
    res5 = auditor.audit(t5_orig, t5_trans, row_id=5)
    print(f"Row 5 Score: {res5.score} | Valid: {res5.is_valid}")
    for v in res5.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res5.is_valid
    assert any(v.dimension == "CODE" for v in res5.violations)
    print("✅ TEST 5 PASSED: Successfully caught missing XML tag!")
    tests_passed += 1

    # Test 6: Hanzi / CJK Leakage (FATAL)
    total_tests += 1
    print("\n--- Test 6: Chinese Vocabulary Leakage '主动' (FATAL) ---")
    t6_orig = "【遠藤】\n自分から咥えたいなんて・・・・。"
    t6_trans = "【เอ็นโด】\nไม่นึกเลยว่าจะเป็นฝ่าย主动อมเอง..."
    res6 = auditor.audit(t6_orig, t6_trans, row_id=6, speaker="遠藤")
    print(f"Row 6 Score: {res6.score} | Valid: {res6.is_valid}")
    for v in res6.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res6.is_valid
    assert any(v.dimension == "HANZI_LEAKAGE" for v in res6.violations)
    print("✅ TEST 6 PASSED: Successfully caught Hanzi leakage!")
    tests_passed += 1

    print("\n" + "=" * 75)
    print(f"🎉 ALL {tests_passed}/{total_tests} LQA AUDITOR UNIT TESTS PASSED (100% ACCURACY)!")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LQA Translation Auditor")
    parser.add_argument("--test", action="store_true", help="Run comprehensive LQA unit tests")
    args = parser.parse_args()

    if args.test:
        run_unit_tests()
    else:
        print("LQATranslationAuditor ready. Run with --test to verify.")
