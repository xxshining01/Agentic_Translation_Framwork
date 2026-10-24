"""
ATF Style, Idiolect & Pronoun Calibration Runner
สคริปต์ปรับแต่งและแก้ไขสไตล์ คำสรรพนาม และคำลงท้ายหางเสียง (Style & Pronoun Calibration)
โดยยึดประโยคภาษาไทยเดิมเป็นหลัก ไม่แปลใหม่ เพื่อรักษาบริบท เนื้อเรื่อง และความต่อเนื่อง 100%

รองรับกฎเฉพาะ:
1. Signature Idiolect & Catchphrases (เช่น YAHA / Yahaha -> ยะฮ่า, ยะฮ่าๆๆ)
2. บริบทหยอกล้อ/แซวสาว (ตัวละครชายสามารถใช้ 'จ๊ะ/จ้ะ' ได้หากเป็นการหยอกล้อ แซว หรือประชดประชัน)
3. กำจัดหางเสียงผิดเพศ (เช่น ตัวละครชายพูด 'ค่ะ/คะ' ในบทสนทนาปกติ เช่น Damien)
"""

import os
import sys
import json
import csv
import re
import time
import urllib.request
import urllib.error
import argparse
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
CSV_PATH = os.path.join(PROJECT_ROOT, "Example RPGM Game", "SSPV034v1.35 - Trans - Processed_v3_translated.csv")
CHECKPOINT_PATH = os.path.join(TLAS_DATA, "chatgpt_translation_checkpoint.json")
REPORT_PATH = os.path.join(TLAS_DATA, "true_style_mismatches.json")
BRIDGE_URL = "http://127.0.0.1:8765"

CALIBRATION_SYSTEM_INSTRUCTION = """You are an expert Thai Localization Editor performing Style, Idiolect & Pronoun Calibration for a story-rich RPG.
Your task is to refine the EXISTING Thai translation (current_thai) so that pronouns and ending particles match the speaker's character profile, WHILE PRESERVING 100% OF THE CONTEXT, STORY MEANING, HUMOR, AND CONVERSATIONAL FLOW.

CRITICAL DIRECTIVES:
1. IDIOLECT & SIGNATURE CATCHPHRASES:
   - If the character has a signature laugh or catchphrase in the original English (e.g. "YAHA", "Yahaha", "Yahahaha", "Hehehe", "*blurrp..*"), preserve and express it in Thai (e.g. "ยะฮ่า", "ยะฮะฮ่า", "ยะฮ่าๆๆ", "ฮิฮิ") instead of replacing it with generic particles or polite words.
2. CONTEXTUAL & PLAYFUL PARTICLES:
   - Male characters MAY use "จ๊ะ", "จ้ะ", "จ๋า" when flirting, teasing, mocking, or bantering with female characters (e.g. "ไม่อยากรู้หน่อยเหรอจ๊ะ", "ว่าไงจ๊ะคนสวย", "แน่นอนจ้ะ"). DO NOT remove "จ๊ะ/จ้ะ" if the scene tone is playful, sarcastic, or teasing.
3. REMOVE INCOMPATIBLE FORMAL PARTICLES:
   - For male characters (such as Damien), eliminate feminine polite particles ("ค่ะ", "คะ") that make them sound like a woman in normal or serious lines (e.g. change "ฉันพร้อมจะทุ่มราคาเอาชนะทุกคนค่ะ" -> "ฉันพร้อมจะทุ่มราคาเอาชนะทุกคน" or use fitting male register).
4. RETAIN 100% OF THE EXISTING THAI TRANSLATION:
   - Do NOT rewrite or translate from scratch. Keep the exact sentence structure, vocabulary, and literary tone of the current Thai text, only calibrating the pronouns and particles.
5. PRESERVE RPG MAKER CONTROL CODES:
   - Preserve all codes like \\., \\|, \\!, \\C[n], \\N[n], \\fb, \\fi, \\> \\< exactly as they appear in the original and current text.

OUTPUT FORMAT:
Return ONLY a valid JSON array of objects:
[
  {
    "id": "<id_as_string>",
    "calibrated_thai": "<refined thai dialogue>"
  }
]
"""

class StyleCalibrator:
    @staticmethod
    def prevent_system_sleep():
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            print("[+] 🛡️ Windows Sleep Prevention active: Screen Saver and Sleep suppressed.")
        except Exception:
            pass

    @staticmethod
    def restore_system_sleep():
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            print("[+] Windows Sleep state restored.")
        except Exception:
            pass

    def __init__(self, bridge_url=BRIDGE_URL):
        self.bridge_url = bridge_url
        self.checkpoint_data = self._load_checkpoint()

    def _load_checkpoint(self):
        if os.path.exists(CHECKPOINT_PATH):
            try:
                with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] Warning reading checkpoint: {e}")
        return {"completed_chunks": {}, "translated_dialogues": {}, "csv_translations": {}}

    def _save_checkpoint(self):
        temp_ckpt = CHECKPOINT_PATH + ".tmp"
        with open(temp_ckpt, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_ckpt, CHECKPOINT_PATH)

    def wait_for_bridge(self, max_wait=60):
        print("[*] Checking ChatGPT Bridge Server status...")
        start_t = time.time()
        while time.time() - start_t < max_wait:
            try:
                req = urllib.request.Request(f"{self.bridge_url}/bridge/status")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("userscript_connected") or data.get("userscript_online"):
                        print("[+] Bridge Server & Userscript are online and ready!")
                        return True
            except Exception:
                pass
            time.sleep(2)
        print("[!] Warning: Bridge readiness check timed out, attempting to proceed...")
        return True

    def call_bridge(self, messages):
        payload = {
            "model": "chatgpt-5.6-luna",
            "messages": messages
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.bridge_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=None) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def extract_json(self, text):
        text = text.strip()
        # ซ่อมแซม backslash escape
        clean = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)
        clean = re.sub(r',\s*([\]\}])', r'\1', clean)
        
        # ลอง parse json array
        m = re.search(r'\[\s*\{.*\}\s*\]', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0), strict=False)
            except Exception:
                pass
        try:
            return json.loads(clean, strict=False)
        except Exception as e:
            # fallback line by line regex
            results = []
            for row_m in re.finditer(r'"id"\s*:\s*"([^"]+)"\s*,\s*"calibrated_thai"\s*:\s*"([^"]+)"', text):
                results.append({"id": row_m.group(1), "calibrated_thai": row_m.group(2)})
            return results

    @staticmethod
    def extract_speaker_tag(text: str):
        if not text:
            return False, "", "", ""
        m = re.match(r"^(\s*\\n)?<([^>]+)>", text)
        if not m:
            return False, "", "", text
        full_prefix = m.group(0)
        inner_content = m.group(2)
        pure_dialogue = text[len(full_prefix):]
        clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content)
        clean_name = clean_name.replace(":", "").strip()
        if clean_name:
            return True, full_prefix, clean_name, pure_dialogue
        return False, "", "", text

    def calibrate_batch(self, batch_items: List[Dict[str, Any]]):
        prompt_items = []
        for it in batch_items:
            orig_text = it.get("original", "")
            th_text = it.get("current_thai", "")
            
            has_tag_th, prefix_th, _, pure_th = self.extract_speaker_tag(th_text)
            has_tag_orig, prefix_orig, _, pure_orig = self.extract_speaker_tag(orig_text)
            
            it["_saved_prefix"] = prefix_th if has_tag_th else (prefix_orig if has_tag_orig else "")

            prompt_items.append({
                "id": str(it["row_idx"]),
                "speaker": it["speaker"],
                "gender": it.get("profile_gender", "MALE"),
                "personality_tone": it.get("expected_ending", ""),
                "original_english": pure_orig if has_tag_orig else orig_text,
                "current_thai": pure_th if has_tag_th else th_text
            })

        user_content = (
            "Calibrate the following dialogue lines according to the directives. "
            "Keep the meaning, humor, and sentence structure 100% intact, adjusting only pronouns and ending particles:\n\n"
            f"```json\n{json.dumps(prompt_items, ensure_ascii=False, indent=2)}\n```"
        )

        messages = [
            {"role": "system", "content": CALIBRATION_SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_content}
        ]

        resp = self.call_bridge(messages)
        content = resp["choices"][0]["message"]["content"]
        parsed = self.extract_json(content)
        
        calibrated_map = {}
        if isinstance(parsed, list):
            for obj in parsed:
                if isinstance(obj, dict) and "id" in obj:
                    raw_cal = obj.get("calibrated_thai", "")
                    calibrated_map[str(obj["id"])] = raw_cal
        return calibrated_map

    @staticmethod
    def estimate_item_tokens(item):
        orig = item.get("original", "")
        thai = item.get("current_thai", "")
        # English ~ 0.4 tokens/char, Thai ~ 0.8 tokens/char, JSON formatting ~ 30 tokens
        # Total bidirectional tokens (input prompt + output generation):
        return int(len(orig) * 0.4 + len(thai) * 1.6) + 35

    @classmethod
    def pack_into_token_batches(cls, items, max_tokens=8000, max_items_hard_cap=60):
        OVERHEAD_TOKENS = 800  # System instruction + JSON wrapper overhead
        TARGET_BUDGET = max(2000, max_tokens - OVERHEAD_TOKENS)

        batches = []
        current_batch = []
        current_tokens = 0

        for it in items:
            it_tokens = cls.estimate_item_tokens(it)
            if ((current_tokens + it_tokens > TARGET_BUDGET) or (len(current_batch) >= max_items_hard_cap)) and current_batch:
                batches.append(current_batch)
                current_batch = [it]
                current_tokens = it_tokens
            else:
                current_batch.append(it)
                current_tokens += it_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def run(self, target_character=None, max_tokens=8000, limit=None, dry_run=False):
        if not os.path.exists(REPORT_PATH):
            print(f"[!] Mismatch report not found at {REPORT_PATH}")
            return

        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            all_mismatches = json.load(f)

        # กรองตัวละครเป้าหมาย
        selected_items = []
        filter_mode = (target_character or "all").lower()

        for it in all_mismatches:
            spk = it.get("speaker", "").strip()
            issues = it.get("issues", [])
            gender = it.get("profile_gender", "")

            if filter_mode == "all":
                # เอาทุกตัวละครที่มีในรายงานการตรวจเช็ค
                selected_items.append(it)
            elif filter_mode == "male_ka":
                # เฉพาะตัวละครชายที่หลุด ค่ะ/คะ
                has_ka_issue = any("feminine particle/pronoun 'ค่ะ'" in iss or "feminine particle/pronoun 'คะ'" in iss for iss in issues)
                if gender == "MALE" and has_ka_issue:
                    selected_items.append(it)
            else:
                # ระบุชื่อตัวละคร เช่น 'Damien', 'Drex', 'Drake'
                if filter_mode in spk.lower():
                    selected_items.append(it)

        if limit:
            selected_items = selected_items[:limit]

        # รวมกลุ่มประโยคแบบ Dynamic Token Packing ให้เต็มเพดาน ~8,000 Tokens ต่อ Batch
        batches = self.pack_into_token_batches(selected_items, max_tokens=max_tokens)

        print("="*65)
        print("=== ATF STYLE & PRONOUN CALIBRATION (DYNAMIC TOKEN PACKING) ===")
        print("="*65)
        print(f"Target Filter: {target_character}")
        print(f"Total Dialogue Items to Calibrate: {len(selected_items)}")
        print(f"Target Token Budget: ~{max_tokens} Tokens/Batch")
        print(f"Packed into: {len(batches)} Batches (avg {len(selected_items)//len(batches) if batches else 0} items/batch)")
        print(f"Dry Run Mode: {dry_run}")
        print("="*65)

        if not selected_items:
            print("[+] No items match the criteria.")
            return

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge()

            # อ่าน CSV ทั้งหมดเตรียมอัปเดต
            with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
                csv_rows = list(csv.reader(f))

            csv_key = os.path.basename(CSV_PATH)
            if csv_key not in self.checkpoint_data["csv_translations"]:
                self.checkpoint_data["csv_translations"][csv_key] = {}
            cached_rows = self.checkpoint_data["csv_translations"][csv_key]

            total_batches = len(batches)
            success_count = 0

            for b_idx, batch in enumerate(batches):
                batch_tokens_est = sum(self.estimate_item_tokens(it) for it in batch)
                print(f"\n[*] Processing Calibration Batch {b_idx + 1}/{total_batches} ({len(batch)} items, ~{batch_tokens_est} tokens)...")
                
                try:
                    results = self.calibrate_batch(batch)
                except Exception as e:
                    print(f"[!] Error calling calibration batch {b_idx + 1}: {e}")
                    continue

                for it in batch:
                    r_idx = it["row_idx"]
                    str_idx = str(r_idx)
                    old_val = it["current_thai"]
                    calibrated_pure = results.get(str_idx)
                    prefix = it.get("_saved_prefix", "")

                    if calibrated_pure and calibrated_pure.strip():
                        # ทำความสะอาดกรณี ChatGPT ใส่ชื่อหรือแท็กซ้ำมาข้างหน้า
                        cal_clean = re.sub(r"^(\s*\\n)?<[^>]+>\s*", "", calibrated_pure)
                        cal_clean = re.sub(r"^(\s*\\n)?[A-Za-z0-9_\s]+:\s*", "", cal_clean)
                        new_val = f"{prefix}{cal_clean.strip()}"

                        print(f"  [+] Row {r_idx} [{it['speaker']}]:")
                        print(f"      OLD: {old_val[:75]}...")
                        print(f"      NEW: {new_val[:75]}...")
                        
                        if not dry_run:
                            # อัปเดตลง memory CSV
                            if r_idx < len(csv_rows):
                                csv_rows[r_idx][1] = new_val
                            # อัปเดตลง Checkpoint
                            cached_rows[str_idx] = new_val
                            success_count += 1
                    else:
                        print(f"  [-] Row {r_idx} [{it['speaker']}]: No calibration returned, keeping original.")

                if not dry_run:
                    self._save_checkpoint()
                    # บันทึก CSV อัปเดตเป็นระยะ
                    temp_csv = CSV_PATH + ".tmp"
                    with open(temp_csv, "w", encoding="utf-8-sig", newline="") as out_f:
                        writer = csv.writer(out_f)
                        writer.writerows(csv_rows)
                    os.replace(temp_csv, CSV_PATH)
                    print(f"  [v] Progress saved to CSV and Checkpoint! ({success_count}/{len(selected_items)})")

                time.sleep(2)

            print("\n" + "="*65)
            print(f"🎉 Calibration Complete! Successfully updated {success_count} dialogue lines.")
            print("="*65)
        finally:
            self.restore_system_sleep()

def main():
    parser = argparse.ArgumentParser(description="ATF Style & Pronoun Calibrator")
    parser.add_argument("--character", type=str, default="all", help="Target character (e.g. Damien, Drex, or 'all')")
    parser.add_argument("--max-tokens", type=int, default=8000, help="Max tokens budget per batch (default ~8,000 tokens)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items for test")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without saving to disk")
    args = parser.parse_args()

    calibrator = StyleCalibrator()
    calibrator.run(target_character=args.character, max_tokens=args.max_tokens, limit=args.limit, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
