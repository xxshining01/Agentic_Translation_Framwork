# -*- coding: utf-8 -*-
"""
LQA Translation Auditor: Universal 4-Dimensional Translation Quality & Integrity Engine
Compliant with SDD-016, SAD-014, and ADR-019.

Audits LLM Translation Outputs against:
  1. Control Code & Escape Integrity (Zero Loss, No \\x0c Form Feeds, Strict Tag Parity)
  2. Glossary & Proper Noun Adherence (Exact Matching for Items, Locations, Names)
  3. TLAS Pronoun & Character Persona Consistency (Speaker -> Listener Relational Grammar)
  4. Emotion & Typography Parity (Ellipses, Punctuation ?!, Tildes, Thai-English Spacing)
"""

import re
import sys
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
    dimension: str       # "CODE", "GLOSSARY", "PRONOUN", "EMOTION"
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
    Automated 4-Dimensional Quality & Integrity Auditor for Localized Game Dialogues.
    """

    def __init__(self, glossary: Optional[Dict[str, str]] = None, character_db: Optional[Dict[str, Any]] = None):
        self.glossary = glossary or self._default_glossary()
        self.character_db = character_db or self._default_character_db()

    def _default_glossary(self) -> Dict[str, str]:
        return {
            "Gold": "โกลด์",
            "Potion": "โพชั่น",
            "Herb": "สมุนไพร",
            "Special Order": "ออเดอร์พิเศษ",
            "Ram City": "เมือง Ram",
            "Seaside Village": "หมู่บ้าน Seaside",
            "Lustrous Woods": "ป่า Lustrous Woods",
            "Bakery": "เบเกอรี่",
            "Seaside Tavern": "ทาเวิร์น Seaside",
        }

    def _default_character_db(self) -> Dict[str, Any]:
        return {
            "Dan": {
                "pronouns_to": {
                    "Shion": {"self": ["ผม"], "listener": ["คุณ", "Shion"]},
                    "Masaru": {"self": ["ผม"], "listener": ["คุณ", "คุณ Masaru", "ผู้จัดการ"]},
                    "default": {"self": ["ผม", "ฉัน"], "listener": ["คุณ", "นาย"]},
                }
            },
            "Shion": {
                "pronouns_to": {
                    "Dan": {"self": ["ฉัน"], "listener": ["คุณ", "Dan"], "particles": ["ค่ะ", "นะคะ"]},
                    "Masaru": {"self": ["ฉัน", "หนู"], "listener": ["คุณ Masaru", "ผู้จัดการ"], "particles": ["ค่ะ", "นะคะ"]},
                    "default": {"self": ["ฉัน"], "listener": ["คุณ"], "particles": ["ค่ะ", "นะคะ"]},
                }
            },
            "Masaru": {
                "pronouns_to": {
                    "Dan": {"self": ["ผม"], "listener": ["คุณ", "คุณ Dan"]},
                    "Shion": {"self": ["ผม", "พี่"], "listener": ["เธอ", "Shion"]},
                }
            },
            "Drex": {
                "pronouns_to": {
                    "all": {"self": ["ข้า", "ฉัน"], "listener": ["แก", "มึง", "พวกแก"]},
                }
            }
        }

    def audit(self, orig: str, trans: str, row_id: Any = 0, speaker: Optional[str] = None, listener: Optional[str] = None) -> AuditRowResult:
        """
        Runs comprehensive 4D audit on a single line of translation.
        """
        violations: List[AuditViolation] = []

        if not orig:
            return AuditRowResult(row_id=row_id, is_valid=True, score=100.0, violations=[])

        # -------------------------------------------------------------
        # DIMENSION 1: Control Code & Escape Integrity (FATAL IF VIOLATED)
        # -------------------------------------------------------------
        # 1.1 Check Form Feed Hazard (Must not appear in translated output)
        if "\x0c" in trans:
            violations.append(AuditViolation(
                dimension="CODE",
                severity="FATAL",
                message="ตรวจพบ Form Feed ASCII 12 (\\x0c) ตกค้างในข้อความคำแปล",
                expected="No \\x0c",
                actual="Found \\x0c in translation"
            ))

        # Sanitize orig escapes (e.g. \x0ci -> \fi) so comparison is fair
        clean_orig = orig.replace("\x0ci", "\\fi").replace("\x0cb", "\\fb").replace("\x0c", "\\f")

        # 1.2 Check Control Code Counts (Case-insensitive for color and icon codes)
        # Normalize standalone \C or \c (RPG Maker MV reset color) to \C[0] in both texts for fair parity check
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
        ]

        for pattern, label, ignore_case in critical_codes:
            flags = re.IGNORECASE if ignore_case else 0
            orig_matches = re.findall(pattern, norm_orig, flags=flags)
            trans_matches = re.findall(pattern, norm_trans, flags=flags)

            if len(orig_matches) != len(trans_matches):
                violations.append(AuditViolation(
                    dimension="CODE",
                    severity="FATAL",
                    message=f"จำนวนรหัสเกม {label} ไม่ตรงกับต้นฉบับ",
                    expected=f"{len(orig_matches)} occurrences",
                    actual=f"{len(trans_matches)} occurrences"
                ))

        # 1.3 Check Name Tag in \n<...:>
        orig_name_tag = re.search(r"\\n<([^>]+):>", orig)
        if orig_name_tag:
            trans_name_tag = re.search(r"\\n<([^>]+):>", trans)
            if not trans_name_tag:
                violations.append(AuditViolation(
                    dimension="CODE",
                    severity="FATAL",
                    message="ป้ายชื่อผู้พูด \\n<Name:> สูญหายหรือจัดรูปแบบผิด",
                    expected=orig_name_tag.group(0),
                    actual="Missing or malformed"
                ))

        # -------------------------------------------------------------
        # DIMENSION 2: Glossary & Named Entities Adherence
        # -------------------------------------------------------------
        for en_term, th_term in self.glossary.items():
            # Check if English term exists as whole word in original
            if re.search(rf"\b{re.escape(en_term)}\b", orig, flags=re.IGNORECASE):
                # The translated text should contain the required Thai term
                if th_term not in trans and en_term not in trans:
                    violations.append(AuditViolation(
                        dimension="GLOSSARY",
                        severity="WARNING",
                        message=f"ไม่พบคำแปลตาม Glossary สำหรับคำว่า '{en_term}'",
                        expected=f"'{th_term}' หรือคงรูป '{en_term}'",
                        actual="Missing in translation"
                    ))

        # -------------------------------------------------------------
        # DIMENSION 3: TLAS Pronoun & Character Persona Consistency
        # -------------------------------------------------------------
        if speaker and speaker in self.character_db:
            char_rules = self.character_db[speaker].get("pronouns_to", {})
            rules_to_use = char_rules.get(listener) or char_rules.get("default") or char_rules.get("all")

            if rules_to_use:
                # Check Self-pronoun
                expected_self = rules_to_use.get("self", [])
                # If speaker talks about self in dialogue
                if any(p in orig.lower() for p in ["i", "me", "my", "myself"]):
                    found_self = any(p in trans for p in expected_self)
                    if not found_self and expected_self:
                        # Check if forbidden self pronouns were used instead
                        forbidden_self = ["กู", "ข้า", "ฉัน"] if "ผม" in expected_self else ["ผม"]
                        if any(f in trans for f in forbidden_self):
                            violations.append(AuditViolation(
                                dimension="PRONOUN",
                                severity="WARNING",
                                message=f"{speaker} ใช้สรรพนามแทนตนเองไม่สอดคล้องกับ {listener or 'ทั่วไป'}",
                                expected=f"ควรใช้หนึ่งใน {expected_self}",
                                actual=f"พบสรรพนามขัดแย้งในประโยค"
                            ))

        # -------------------------------------------------------------
        # DIMENSION 4: Emotion, Punctuation & Typography Parity
        # -------------------------------------------------------------
        # 4.1 Check Question Mark (?) Parity
        if "?" in orig and "?" not in trans and "หรือ" not in trans and "ไหม" not in trans and "มั้ย" not in trans:
            violations.append(AuditViolation(
                dimension="EMOTION",
                severity="WARNING",
                message="ประโยคคำถามตกหล่นเครื่องหมาย '?' หรือคำบอกคำถาม",
                expected="Contains '?' or question particle",
                actual="None detected"
            ))

        # 4.2 Check Hearts ♥ or Tildes ~
        for emo in ["♥", "~"]:
            orig_cnt = orig.count(emo)
            trans_cnt = trans.count(emo)
            if orig_cnt > 0 and trans_cnt == 0:
                violations.append(AuditViolation(
                    dimension="EMOTION",
                    severity="WARNING",
                    message=f"สัญลักษณ์แสดงอารมณ์ '{emo}' สูญหาย",
                    expected=f"{orig_cnt} occurrences",
                    actual="0"
                ))

        # 4.3 Check Thai-English Glue (e.g. 'คุณDan' -> should be 'คุณ Dan')
        # First strip control codes from text so \\fi, \\fb, \\C[n] are not falsely flagged
        pure_text_for_spacing = re.sub(r"\\[a-zA-Z]+(?:\[\d+\])?", "", trans)
        pure_text_for_spacing = re.sub(r"\\[\.\!\|\^\<\>]+", "", pure_text_for_spacing)
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
    Executes unit test suite validating LQATranslationAuditor against 4 dimensions.
    """
    print("=" * 75)
    print("🧪 RUNNING COMPREHENSIVE UNIT TESTS ON LQATranslationAuditor (4D LQA)")
    print("=" * 75)

    auditor = LQATranslationAuditor()
    tests_passed = 0
    total_tests = 0

    # Test 1: Perfect Translation with Control Codes
    total_tests += 1
    print("\n--- Test 1: Perfect Translation with Codes & Pronouns ---")
    t1_orig = r"\fi<Shion:>\fi..Dan..don't you think..\. that the air here is..?"
    t1_trans = r"\fi<Shion:>\fi..Dan..คุณไม่คิดเหรอคะ..\. ว่าอากาศที่นี่มัน..?"
    res1 = auditor.audit(t1_orig, t1_trans, row_id=170, speaker="Shion", listener="Dan")
    print(f"Row 170 Score: {res1.score} | Valid: {res1.is_valid}")
    assert res1.is_valid and res1.score == 100.0
    print("✅ TEST 1 PASSED: 100% Score!")
    tests_passed += 1

    # Test 2: Fatal Code Corruption (Missing Pause Code \.)
    total_tests += 1
    print("\n--- Test 2: Fatal Code Loss (Missing \\.) ---")
    t2_orig = r"\fi<Shion:>\fi..Dan..\."
    t2_trans = r"\fi<Shion:>\fi..Dan.."  # Missing \.
    res2 = auditor.audit(t2_orig, t2_trans, row_id=171, speaker="Shion", listener="Dan")
    print(f"Row 171 Score: {res2.score} | Valid: {res2.is_valid}")
    for v in res2.violations:
        print(f"  ❌ [{v.dimension}] {v.severity}: {v.message}")
    assert not res2.is_valid
    assert any(v.dimension == "CODE" and v.severity == "FATAL" for v in res2.violations)
    print("✅ TEST 2 PASSED: Correctly caught FATAL control code loss!")
    tests_passed += 1

    # Test 3: Form Feed \x0c Hazard Detection
    total_tests += 1
    print("\n--- Test 3: Form Feed \\x0c Hazard Catch ---")
    t3_orig = "Hello world"
    t3_trans = "สวัสดี\x0cชาวโลก"
    res3 = auditor.audit(t3_orig, t3_trans, row_id=172)
    print(f"Row 172 Score: {res3.score} | Valid: {res3.is_valid}")
    assert any("Form Feed" in v.message for v in res3.violations)
    print("✅ TEST 3 PASSED: Form feed hazard instantly blocked!")
    tests_passed += 1

    # Test 4: Glossary Violation (Gold translated to something weird or lost)
    total_tests += 1
    print("\n--- Test 4: Glossary Adherence ---")
    t4_orig = r"You gained \C[2]100 Gold\C\!"
    t4_trans = r"คุณได้รับ \C[2]100 ก้อนหิน\C\!"  # Should be โกลด์
    res4 = auditor.audit(t4_orig, t4_trans, row_id=173)
    print(f"Row 173 Score: {res4.score} | Valid: {res4.is_valid}")
    for v in res4.violations:
        print(f"  ⚠️ [{v.dimension}] {v.severity}: {v.message}")
    assert any(v.dimension == "GLOSSARY" for v in res4.violations)
    print("✅ TEST 4 PASSED: Glossary deviation detected!")
    tests_passed += 1

    # Test 5: Thai-English Spacing Violation
    total_tests += 1
    print("\n--- Test 5: Thai-English Spacing ---")
    t5_orig = "Hello Dan, how are you?"
    t5_trans = "สวัสดีคุณDan สบายดีไหม?"  # No space between คุณ and Dan
    res5 = auditor.audit(t5_orig, t5_trans, row_id=174)
    print(f"Row 174 Score: {res5.score} | Valid: {res5.is_valid}")
    assert any("เขียนติดกัน" in v.message for v in res5.violations)
    print("✅ TEST 5 PASSED: Typography glued text caught!")
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
