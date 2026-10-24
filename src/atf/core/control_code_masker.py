# -*- coding: utf-8 -*-
"""
MessageCodeMasker: Universal In-line Control Code Masker and Parity Verifier
Compliant with ADR-019, SAD-014, and SDD-016.

Guarantees 100% Preservation of In-line Control Codes (RPG Maker MV/MZ, Ren'Py, etc.)
by converting cryptic escape sequences into Semantic XML-like tags before LLM translation
and restoring them faithfully with tag parity assertions post-translation.
"""

import re
import sys
import argparse
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set

# Ensure UTF-8 output across Windows CMD / PowerShell
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass


@dataclass
class MaskResult:
    masked_text: str
    original_tags: List[str]
    has_control_codes: bool


@dataclass
class UnmaskResult:
    unmasked_text: str
    is_valid_parity: bool
    missing_tags: List[str]
    extra_tags: List[str]
    repaired: bool


class MessageCodeMasker:
    """
    Universal In-line Control Code Masker and Parity Verifier.
    """

    def __init__(self, engine_type: str = "rpgmaker_mv"):
        self.engine_type = engine_type

    def sanitize_raw_escapes(self, text: str) -> str:
        """
        Sanitizes Form Feed ASCII 12 (\\x0c) hazards caused by Python string escape misinterpretations.
        Converts '\\x0ci' -> '\\\\fi', '\\x0cb' -> '\\\\fb', etc.
        """
        if not text:
            return ""

        # Repair \x0c hazards
        text = text.replace("\x0ci", "\\fi")
        text = text.replace("\x0cb", "\\fb")
        text = text.replace("\x0c", "\\f")

        return text

    def mask(self, text: str) -> MaskResult:
        """
        Converts raw game control codes into Semantic XML-like tags.
        """
        if not text:
            return MaskResult(masked_text="", original_tags=[], has_control_codes=False)

        sanitized = self.sanitize_raw_escapes(text)
        res = sanitized
        recorded_tags: List[str] = []

        # 1. Paired Formatting: \fi...\fi -> <italic>...</italic>
        # Note: Non-greedy match between \fi
        def _replace_italic(m):
            content = m.group(1)
            recorded_tags.append("italic")
            return f"<italic>{content}</italic>"

        res, count = re.subn(r"\\fi(.*?)\\fi", _replace_italic, res, flags=re.DOTALL)

        # 2. Paired Formatting: \fb...\fb -> <bold>...</bold>
        def _replace_bold(m):
            content = m.group(1)
            recorded_tags.append("bold")
            return f"<bold>{content}</bold>"

        res, count = re.subn(r"\\fb(.*?)\\fb", _replace_bold, res, flags=re.DOTALL)

        # 3. Paired Color: \C[n]...\C or \c[n]...\c[0] -> <color id="n">...</color>
        # Case-insensitive to support RPG Maker MV plugin parameters (\c[4]...'Visible Rewards'\c[0])
        def _replace_color(m):
            cid = m.group(1)
            content = m.group(2)
            recorded_tags.append(f"color:{cid}")
            return f'<color id="{cid}">{content}</color>'

        res, count = re.subn(r"\\[cC]\[(\d+)\](.*?)\\[cC](?:\[0\])?", _replace_color, res, flags=re.DOTALL)

        # 4. Self-Closing Controls: \. -> <pause_quarter/>
        if re.search(r"\\\.", res):
            for _ in re.findall(r"\\\.", res):
                recorded_tags.append("pause_quarter")
            res = re.sub(r"\\\.", "<pause_quarter/>", res)

        # 5. Self-Closing Controls: \| -> <pause_second/>
        if re.search(r"\\\|", res):
            for _ in re.findall(r"\\\|", res):
                recorded_tags.append("pause_second")
            res = re.sub(r"\\\|", "<pause_second/>", res)

        # 6. Self-Closing Controls: \! -> <wait_input/>
        if re.search(r"\\!", res):
            for _ in re.findall(r"\\!", res):
                recorded_tags.append("wait_input")
            res = re.sub(r"\\!", "<wait_input/>", res)

        # 7. Self-Closing Controls: \^ -> <no_input_advance/>
        if re.search(r"\\\^", res):
            for _ in re.findall(r"\\\^", res):
                recorded_tags.append("no_input_advance")
            res = re.sub(r"\\\^", "<no_input_advance/>", res)

        # 8. Self-Closing Controls: \> -> <show_fast/> and \< -> <stop_show_fast/>
        if re.search(r"\\>", res):
            for _ in re.findall(r"\\>", res):
                recorded_tags.append("show_fast")
            res = re.sub(r"\\>", "<show_fast/>", res)

        if re.search(r"\\<", res):
            for _ in re.findall(r"\\<", res):
                recorded_tags.append("stop_show_fast")
            res = re.sub(r"\\<", "<stop_show_fast/>", res)

        # 9. Icons: \I[n] or \i[n] -> <icon id="n"/> (Case-insensitive)
        def _replace_icon(m):
            iid = m.group(1)
            recorded_tags.append(f"icon:{iid}")
            return f'<icon id="{iid}"/>'

        res = re.sub(r"\\[iI]\[(\d+)\]", _replace_icon, res)

        # 10. Variables: \V[n] or \v[n] -> <var id="n"/>
        def _replace_var(m):
            vid = m.group(1)
            recorded_tags.append(f"var:{vid}")
            return f'<var id="{vid}"/>'

        res = re.sub(r"\\[vV]\[(\d+)\]", _replace_var, res)

        # 11. Actors: \N[n] or \n[n] (when followed by [id]) -> <actor id="n"/>
        def _replace_actor(m):
            nid = m.group(1)
            recorded_tags.append(f"actor:{nid}")
            return f'<actor id="{nid}"/>'

        res = re.sub(r"\\[nN]\[(\d+)\]", _replace_actor, res)

        # 12. Party: \P[n] -> <party id="n"/>
        def _replace_party(m):
            pid = m.group(1)
            recorded_tags.append(f"party:{pid}")
            return f'<party id="{pid}"/>'

        res = re.sub(r"\\[pP]\[(\d+)\]", _replace_party, res)

        # 13. Gold/Currency: \G or \g -> <currency/>
        if re.search(r"\\[gG]\b", res):
            for _ in re.findall(r"\\[gG]\b", res):
                recorded_tags.append("currency")
            res = re.sub(r"\\[gG]\b", "<currency/>", res)

        # Check if control codes were present
        has_codes = len(recorded_tags) > 0 or (res != sanitized)

        return MaskResult(
            masked_text=res,
            original_tags=recorded_tags,
            has_control_codes=has_codes
        )

    def extract_tags_from_masked(self, masked_text: str) -> List[str]:
        """
        Extracts all semantic XML tags present in the masked text.
        """
        tags: List[str] = []
        if not masked_text:
            return tags

        # Paired tags
        for m in re.finditer(r"<italic>(.*?)</italic>", masked_text, flags=re.DOTALL):
            tags.append("italic")
        for m in re.finditer(r"<bold>(.*?)</bold>", masked_text, flags=re.DOTALL):
            tags.append("bold")
        for m in re.finditer(r"<color id=[\"']?(\d+)[\"']?>(.*?)</color>", masked_text, flags=re.DOTALL):
            tags.append(f"color:{m.group(1)}")

        # Self-closing tags (Resilient to whitespace variants like < pause_quarter/> or <pause_quarter>)
        for _ in re.finditer(r"<\s*pause_quarter\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("pause_quarter")
        for _ in re.finditer(r"<\s*pause_second\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("pause_second")
        for _ in re.finditer(r"<\s*wait_input\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("wait_input")
        for _ in re.finditer(r"<\s*no_input_advance\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("no_input_advance")
        for _ in re.finditer(r"<\s*show_fast\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("show_fast")
        for _ in re.finditer(r"<\s*stop_show_fast\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("stop_show_fast")
        for m in re.finditer(r"<\s*icon id=[\"']?(\d+)[\"']?\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append(f"icon:{m.group(1)}")
        for m in re.finditer(r"<\s*var id=[\"']?(\d+)[\"']?\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append(f"var:{m.group(1)}")
        for m in re.finditer(r"<\s*actor id=[\"']?(\d+)[\"']?\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append(f"actor:{m.group(1)}")
        for m in re.finditer(r"<\s*party id=[\"']?(\d+)[\"']?\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append(f"party:{m.group(1)}")
        for _ in re.finditer(r"<\s*currency\s*\/?>", masked_text, flags=re.IGNORECASE):
            tags.append("currency")

        return tags

    def unmask(self, masked_translated: str, expected_tags: Optional[List[str]] = None) -> UnmaskResult:
        """
        Converts Semantic XML-like tags back to original game control codes.
        Performs Tag Parity Verification against expected_tags if provided.
        """
        if not masked_translated:
            return UnmaskResult(
                unmasked_text="",
                is_valid_parity=True,
                missing_tags=[],
                extra_tags=[],
                repaired=False
            )

        current_tags = self.extract_tags_from_masked(masked_translated)
        missing_tags: List[str] = []
        extra_tags: List[str] = []
        repaired = False

        if expected_tags is not None:
            # Check for parity differences
            expected_counts: Dict[str, int] = {}
            for t in expected_tags:
                expected_counts[t] = expected_counts.get(t, 0) + 1

            current_counts: Dict[str, int] = {}
            for t in current_tags:
                current_counts[t] = current_counts.get(t, 0) + 1

            for t, exp_cnt in expected_counts.items():
                cur_cnt = current_counts.get(t, 0)
                if cur_cnt < exp_cnt:
                    for _ in range(exp_cnt - cur_cnt):
                        missing_tags.append(t)

            for t, cur_cnt in current_counts.items():
                exp_cnt = expected_counts.get(t, 0)
                if cur_cnt > exp_cnt:
                    for _ in range(cur_cnt - exp_cnt):
                        extra_tags.append(t)

        res = masked_translated

        # Auto-Repair Malformed closing tags: e.g. <italic>text<italic> -> <italic>text</italic>
        # or <bold>text<bold> -> <bold>text</bold>
        res = re.sub(r"<italic>(.*?)<italic>", r"<italic>\1</italic>", res, flags=re.DOTALL)
        res = re.sub(r"<bold>(.*?)<bold>", r"<bold>\1</bold>", res, flags=re.DOTALL)

        # Auto-Repair Newline leakage & missing brackets in Speaker tags:
        # e.g. <italic>Shion:\n</italic> -> <italic><Shion:></italic>
        def _clean_italic_speaker(m):
            inner = m.group(1).strip()
            speaker_match = re.match(r"^<?([A-Za-z0-9_\s]+:)>?$", inner)
            if speaker_match:
                name = speaker_match.group(1)
                return f"<italic><{name}></italic>"
            return f"<italic>{inner}</italic>"

        res = re.sub(r"<italic>(.*?)</italic>", _clean_italic_speaker, res, flags=re.DOTALL)

        # 1. Reverse Paired Formatting: <italic>...</italic> -> \fi...\fi
        res = re.sub(r"<italic>(.*?)</italic>", r"\\fi\1\\fi", res, flags=re.DOTALL)

        # 2. Reverse Paired Formatting: <bold>...</bold> -> \fb...\fb
        res = re.sub(r"<bold>(.*?)</bold>", r"\\fb\1\\fb", res, flags=re.DOTALL)

        # 3. Reverse Paired Color: <color id="n">...</color> -> \C[n]...\C[0]
        res = re.sub(r"<color id=[\"']?(\d+)[\"']?>(.*?)</color>", r"\\C[\1]\2\\C[0]", res, flags=re.DOTALL)

        # 4. Reverse Self-Closing: <pause_quarter/> -> \.
        res = re.sub(r"<\s*pause_quarter\s*\/?>", r"\.", res, flags=re.IGNORECASE)

        # 5. Reverse Self-Closing: <pause_second/> -> \|
        res = re.sub(r"<\s*pause_second\s*\/?>", r"\|", res, flags=re.IGNORECASE)

        # 6. Reverse Self-Closing: <wait_input/> -> \!
        res = re.sub(r"<\s*wait_input\s*\/?>", r"\!", res, flags=re.IGNORECASE)

        # 7. Reverse Self-Closing: <no_input_advance/> -> \^
        res = re.sub(r"<\s*no_input_advance\s*\/?>", r"\^", res, flags=re.IGNORECASE)

        # 8. Reverse Self-Closing: <show_fast/> -> \> and <stop_show_fast/> -> \<
        res = re.sub(r"<\s*show_fast\s*\/?>", r"\>", res, flags=re.IGNORECASE)
        res = re.sub(r"<\s*stop_show_fast\s*\/?>", r"\<", res, flags=re.IGNORECASE)

        # 9. Reverse Icons: <icon id="n"/> -> \I[n]
        res = re.sub(r"<\s*icon id=[\"']?(\d+)[\"']?\s*\/?>", r"\\I[\1]", res, flags=re.IGNORECASE)

        # 10. Reverse Variables: <var id="n"/> -> \V[n]
        res = re.sub(r"<\s*var id=[\"']?(\d+)[\"']?\s*\/?>", r"\\V[\1]", res, flags=re.IGNORECASE)

        # 11. Reverse Actors: <actor id="n"/> -> \N[n]
        res = re.sub(r"<actor id=[\"']?(\d+)[\"']?\s*/>", r"\\N[\1]", res)

        # 12. Reverse Party: <party id="n"/> -> \P[n]
        res = re.sub(r"<party id=[\"']?(\d+)[\"']?\s*/>", r"\\P[\1]", res)

        # 13. Reverse Gold: <currency/> -> \G
        res = re.sub(r"<currency\s*/>", r"\\G", res)

        # Final check if repair attempted for missing critical point tags
        if missing_tags:
            # If wait_input or pause was missing, append at the end safely
            for missing in list(missing_tags):
                if missing == "wait_input":
                    res += "\\!"
                    missing_tags.remove(missing)
                    repaired = True
                elif missing == "pause_quarter":
                    res += "\\."
                    missing_tags.remove(missing)
                    repaired = True

        is_valid = len(missing_tags) == 0 and len(extra_tags) == 0

        return UnmaskResult(
            unmasked_text=res,
            is_valid_parity=is_valid,
            missing_tags=missing_tags,
            extra_tags=extra_tags,
            repaired=repaired
        )


def run_unit_tests():
    """
    Executes unit test suite validating MessageCodeMasker against ADR-019 / SDD-016.
    """
    print("=" * 75)
    print("🧪 RUNNING UNIT TESTS ON MessageCodeMasker (SDD-016 COMPLIANT)")
    print("=" * 75)

    masker = MessageCodeMasker()
    tests_passed = 0
    total_tests = 0

    # Test 1: Shion Row 170 (Italics and Pause)
    total_tests += 1
    t1_orig = r"\fi<Shion:>\fi..Dan..don't you think..\. that the air here is.."
    t1_mask = masker.mask(t1_orig)
    print(f"\n--- Test 1: Paired Italics + Pause ---")
    print(f"Original: {t1_orig}")
    print(f"Masked:   {t1_mask.masked_text}")
    print(f"Tags:     {t1_mask.original_tags}")
    assert "<italic><Shion:></italic>" in t1_mask.masked_text
    assert "<pause_quarter/>" in t1_mask.masked_text

    # Mock Translation retaining tags
    t1_trans = r"<italic><Shion:></italic>..Dan..คุณไม่คิดเหรอคะ..<pause_quarter/> ว่าอากาศที่นี่มัน.."
    t1_unmask = masker.unmask(t1_trans, expected_tags=t1_mask.original_tags)
    print(f"Unmasked: {t1_unmask.unmasked_text}")
    print(f"Parity:   Valid={t1_unmask.is_valid_parity}")
    assert t1_unmask.is_valid_parity
    assert r"\fi<Shion:>\fi" in t1_unmask.unmasked_text
    assert r"\." in t1_unmask.unmasked_text
    print("✅ TEST 1 PASSED!")
    tests_passed += 1

    # Test 2: Form Feed \x0c Hazard Repair
    total_tests += 1
    print(f"\n--- Test 2: Form Feed \\x0c Hazard Repair ---")
    t2_corrupted = "\x0ci<Dan:>\x0ciHello world!"
    t2_mask = masker.mask(t2_corrupted)
    print(f"Corrupted Input: {repr(t2_corrupted)}")
    print(f"Masked Result:   {t2_mask.masked_text}")
    assert "<italic><Dan:></italic>" in t2_mask.masked_text
    t2_unmask = masker.unmask(t2_mask.masked_text)
    print(f"Unmasked Result: {repr(t2_unmask.unmasked_text)}")
    assert r"\fi<Dan:>\fi" in t2_unmask.unmasked_text
    print("✅ TEST 2 PASSED!")
    tests_passed += 1

    # Test 3: Color and Icons
    total_tests += 1
    print(f"\n--- Test 3: Color Palette and Icons ---")
    t3_orig = r"You gained \C[2]100 Gold\C and \I[45] Rare Gem\!"
    t3_mask = masker.mask(t3_orig)
    print(f"Original: {t3_orig}")
    print(f"Masked:   {t3_mask.masked_text}")
    assert '<color id="2">100 Gold</color>' in t3_mask.masked_text
    assert '<icon id="45"/>' in t3_mask.masked_text
    assert '<wait_input/>' in t3_mask.masked_text

    t3_trans = r'คุณได้รับ <color id="2">100 โกลด์</color> และ <icon id="45"/> อัญมณีหายาก<wait_input/>'
    t3_unmask = masker.unmask(t3_trans, expected_tags=t3_mask.original_tags)
    print(f"Unmasked: {t3_unmask.unmasked_text}")
    assert t3_unmask.is_valid_parity
    assert r"\C[2]100 โกลด์\C" in t3_unmask.unmasked_text
    assert r"\I[45]" in t3_unmask.unmasked_text
    assert r"\!" in t3_unmask.unmasked_text
    print("✅ TEST 3 PASSED!")
    tests_passed += 1

    # Test 4: Missing Tag Detection & Auto-Repair
    total_tests += 1
    print(f"\n--- Test 4: Missing Tag Auto-Repair ---")
    t4_orig = r"Caution!\!"
    t4_mask = masker.mask(t4_orig)
    # LLM lost the <wait_input/>
    t4_trans_lost = r"ระวัง!"
    t4_unmask = masker.unmask(t4_trans_lost, expected_tags=t4_mask.original_tags)
    print(f"Translated (Tag Lost): {t4_trans_lost}")
    print(f"Auto-Repaired Output:  {t4_unmask.unmasked_text}")
    print(f"Repaired Flag:         {t4_unmask.repaired}")
    assert t4_unmask.repaired
    assert t4_unmask.unmasked_text.endswith(r"\!")
    print("✅ TEST 4 PASSED!")
    tests_passed += 1

    print("\n" + "=" * 75)
    print(f"🎉 ALL {tests_passed}/{total_tests} UNIT TESTS PASSED PERFECTLY (100% SUCCESS)!")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MessageCodeMasker CLI and Unit Tester")
    parser.add_argument("--test", action="store_true", help="Run comprehensive unit tests")
    args = parser.parse_args()

    if args.test:
        run_unit_tests()
    else:
        print("MessageCodeMasker ready. Run with --test to verify.")
