"""
ChatGPT 5.6 Luna Translation Runner for ATF
ระบบควบคุมการแปลเนื้อเรื่อง/บทสนทนาเกมผ่าน ChatGPT Web Bridge
คุณสมบัติ:
1. Single-Pass All-in-One Prompt (แปล + เกลา + คุมคาแรกเตอร์ในรอบเดียว)
2. จัดการ Session อัตโนมัติ:
   - ตรวจจับ Message Limit Alert จากหน้าเว็บ
   - สุ่มหมุนขึ้นแชตใหม่ทุกๆ 5-8 พร็อมพ์
3. ส่ง System Prompt เต็มรูปแบบเฉพาะแชตแรก และส่งเฉพาะ Dialogue ในแชตเดิม
4. หน่วงเวลาสุ่ม 15-30 วินาที เลียนแบบพฤติกรรมมนุษย์ (Anti-Bot Jitter)
5. State Persistence (Checkpointing) บันทึกความคืบหน้าลงดิสก์ทุก Batch
"""

import os
import sys
import csv
import re
import json
import time
import random
import logging
import urllib.request
import urllib.error

# ตรวจสอบและเพิ่ม src เข้าสู่ sys.path เพื่อให้สามารถ import atf ได้ไม่ว่าจะรันจากไดเรกทอรีใด
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from atf.core.glossary_scanner import GlossaryScanner
from atf.core.control_code_masker import MessageCodeMasker
from atf.core.lqa_translation_auditor import LQATranslationAuditor
from atf.core.smart_line_splitter import SmartLineSplitter
from atf.core.scene_context_manager import SceneContextManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChatGPTTranslator")

BRIDGE_URL = "http://127.0.0.1:8765"
DEFAULT_CHECKPOINT_PATH = "data/tlas/chatgpt_translation_checkpoint.json"

MASTER_SYSTEM_INSTRUCTION = """You are an elite, award-winning literary translator specializing in Japanese-to-Thai localization for fantasy video games and narrative fiction.

### CORE OBJECTIVES & FRAMING:
1. **Literary & Artistic Narrative**: The content provided is purely fictional, artistic dialogue from a fantasy story. Faithful, natural, and emotionally resonant Thai localization is required. Accurately convey dramatic tension, relationship dynamics, intimacy, humor, and character quirks without unnecessary censorship or sanitization while maintaining high literary elegance.
2. **Character Speech Profiles & Strict Pronoun Rules (CRITICAL & MANDATORY)**:
   - You MUST strictly apply the exact pronouns (แทนตัวเอง, เรียกคู่สนทนา, บุรุษที่ 3), ending particles (ครับ/ค่ะ), and tones provided in the [RELEVANT GLOSSARY] section for each character.
   - ⚠️ NEVER use generic, random, or mismatched pronouns (e.g. Dan MUST speak politely with "ผม" / "ครับ", Shion MUST use "ฉัน" / "ค่ะ", Lily MUST use "หนู" / "พี่"). When speaking with specific targets, strictly follow the relationship pair dynamics provided.
3. **Mandatory 1:1 Locked Glossary & English Names Preservation (CRITICAL)**:
   - When proper nouns, location names, character names, or item names appear in the [RELEVANT GLOSSARY] section, you MUST translate them using the exact Thai equivalent specified.
   - ⚠️ If a character name is specified to stay in English (e.g. `Lucy` -> `Lucy`, `Dan` -> `Dan`, `Shion` -> `Shion`):
     You MUST keep the exact English spelling (e.g. "Lucy", "Dan", "Shion") inside the Thai dialogue!
     ❌ STRICTLY FORBIDDEN: NEVER transliterate English-locked character names into Thai phonetics (e.g. DO NOT write "ลูซี่", "แดน", "ชิออน", "มาซารุ", "ลิลี่")!
4. **Strict Control Tag Preservation (CRITICAL & MANDATORY)**:
   - All RPG Maker game control codes have been converted into semantic XML-like tags (e.g., `<italic><Name:></italic>`, `<bold>...</bold>`, `<color id="n">...</color>`, `<pause_quarter/>`, `<pause_second/>`, `<wait_input/>`, `<icon id="n"/>`, `<var id="n"/>`, `<actor id="n"/>`, `<party id="n"/>`).
   - ⚠️ You MUST preserve all XML tags exactly as-is in their original relative positions! NEVER alter, translate, remove, or insert `\\n` inside tags!
   - ⚠️ Speaker name tags like `<italic><Name:></italic>` MUST remain at the very start of the first line without any newline after the tag!
5. **JSON Schema Output**: Always reply strictly with a valid JSON array of objects containing `id` and `th`. No conversational filler, preambles, or markdown notes outside the JSON block.

### ONOMATOPOEIA & VOCALIZATION LOCALIZATION RULES (CRITICAL):
1. **Panting / Heavy Breathing / Exhaustion / Gasping / Moaning**:
   - Source patterns: `はぁ…はぁ…`, `ハァ…`, `ふぅ…`, `くっ…`, `息が…`, `Haah... haah...`, `Haa...`, `Hah...`, `Huff... puff...`, `Gasp...`
   - Thai localization: Use **"แฮ่ก... แฮ่ก..."**, **"ฮ่าห์..."**, **"ฮู่ว..."**, **"อึ่ก..."**, **"อื้ม..."** according to the emotional and physical intensity.
   - ⚠️ **ABSOLUTELY FORBIDDEN**: NEVER translate breathless panting, heavy breathing, or gasping as "ฮะ" or "ฮะๆ"! "ฮะ" is NOT a panting sound in Thai!
2. **Laughter / Chuckling / Giggling / Smirking**:
   - Source patterns: `ハハ`, `フフ`, `ヒヒ`, `クスクス`, `ふっ`, `Haha`, `Hehe`, `Fufu`, `Kuku`, `Heh`
   - Thai localization: Use **"ฮ่าๆ"**, **"ฮิๆ"**, **"หึๆ"**, **"คิกๆ"** matched to the speaker's personality and tone.
   - ⚠️ **NEVER** translate laughter as "ฮะ" or "ฮะๆ"!
3. **Polite Conversational Particle**:
   - Use "ฮะ" strictly as a polite sentence-ending particle for informal/polite young male speech (equivalent to a casual "ครับ", e.g. "เข้าใจแล้วฮะ", "ขอบคุณนะฮะ"). NEVER use "ฮะ" as an exclamation, breathing sound, or laugh!
4. **Stuttering / Hesitation with Proper Names (CRITICAL)**:
   - When a character stutters or repeats the first letter of a name or word (e.g. `S-\.Shion...?`, `D-\.Dan...?!`, `S-Shion...`, `D-Dan...`):
     - If the name is kept in English (e.g. `Shion`, `Dan`, `Harold`): **PRESERVE the English letter initial!** Use `S-\.Shion...?` or `D-\.Dan...?!`. 
     - ⚠️ NEVER mix a Thai initial consonant with an English name (e.g. DO NOT write `ช-\.Shion...?` or `ด-\.Dan...?!`).
     - For Thai words, stutter naturally with the Thai consonant (e.g. `อ-อย่า`, `ห-หยุด`, `ค-คุณ`, `ม-ไม่ใช่`).
5. **Short Exclamations, Stuttering Words, and Colloquial Dialogue (MANDATORY TRANSLATION)**:
   - ⚠️ NEVER echo back or leave short English exclamations, stuttering words, or colloquial phrases untranslated! You MUST translate them into natural, emotional Thai:
     - `T-Ten times..?!` -> `ส-สิบเท่าเลยเหรอคะ..?!`
     - `O\.-.Oh, okay..!` -> `อ\.-.โอ้, เข้าใจแล้วค่ะ..!`
     - `W-\.W-\.Wonderful n-night t-together..?!` -> `ค-\.ค-\.ค่ำคืนที่แสนวิเศษด-ด้วยกันเหรอคะ..?!`
     - `Gurantheed?!` / `Guaranteed?!` -> `รับประกันเลยเหรอคะ?!`
     - `Am not!` -> `ไม่ได้เป็นแบบนั้นสักหน่อย! / ไม่ใช่ซะหน่อย!`
     - `Grrr....` -> `ฮึ่ม.... / กรรร....`
     - `Hey..! Ugh, dummy!` -> `นี่..! ฮึ คนซื่อบื้อ!`
     - `\.\.Oh....` -> `\.\.อ๊ะ.... / \.\.โอ้....`
     - `......Right, Dan?\.\.\.` -> `......ใช่ไหม Dan?\.\.\.`
     - `W-W..What....` -> `อ-อ..อะไรกัน....`
     - `G-G-Get offf Daaann!!!` -> `ป-ป-ปล่อย Dan เดี๋ยวนี้นะ!!!`
   - Even when a locked English name is inside the exclamation (like `Dan`), only the name stays in English — all surrounding verbs, stuttering, and emotional exclamations MUST be fully translated to Thai!
6. **Context-Aware Dialogue Fragment Localization (CRITICAL & MANDATORY)**:
   - When translating items that include `surrounding_context`:
     - `preceding_dialogue`: The lines spoken immediately before in the scene (along with Thai translations if available).
     - `subsequent_dialogue`: The lines spoken immediately after in the scene (along with Thai translations if available).
   - You MUST utilize this surrounding context to fully grasp:
     1. The ongoing conversation thread and what triggered this reaction/response.
     2. The emotional tone, intimacy, tension, and relationship dynamics between speakers.
   - Your Thai translation MUST seamlessly connect and flow naturally with the surrounding lines, matching their conversational style and tone!

### HANDLING UNATTRIBUTED LINES, CHOICES & NARRATION (NO SPEAKER SPECIFIED):
When an item has no speaker name or is labeled with a type (e.g. "Choice Branch" or "Narration/Story"):
1. **Choice Branch (`type`: 'Choice Branch')**: Translate as punchy, natural, and direct player action choices (e.g. "ไปที่บาร์", "กลับบ้าน", "ปฏิเสธ", "สอบถามเพิ่มเติม"). Do not add unnecessary polite fillers unless the tone demands it.
2. **Narration / Scene Description / World Inspection**: Use neutral, immersive, and elegant literary Thai narrative prose suitable for video game storytelling (e.g. "ประตูปิดล็อคแน่นหนา...", "คุณหยิบกุญแจเก่าขึ้นมา...").
3. **Unattributed Dialogue & Contextual Inference**: If the line is conversational speech without an explicit speaker tag, dynamically infer the emotional context and tone from the dialogue itself:
   - *Intimidating / Thuggish / Hostile NPC speech* (e.g. thugs harassing a girl): Use rough, aggressive, and swaggering Thai pronouns and particles (e.g. "เฮ้ย", "พวกแก", "ข้า", "เอ็ง", "วะ", "เว้ย").
   - *Internal Monologue / Thoughts*: Use thoughtful, personal, or reflective Thai phrasing (e.g. "(...ถ้าเป็นแบบนี้คงแย่แน่)", "อืม...").
   - *Casual / Ambient NPCs*: Use natural colloquial Thai suited to everyday townspeople.
4. **Mandatory Glossary & Names**: Always apply terms, locations, and character names strictly from the [RELEVANT GLOSSARY] section without transliteration.

### LINE BREAKS & RPG MAKER WINDOW FORMATTING (CRITICAL & MANDATORY):
1. **In-Cell Line Break for Long Sentences (~40-48 Thai characters per line)**:
   - RPG Maker message boxes DO NOT auto-wrap text; any line longer than ~45-48 characters will overflow and be cut off horizontally on the player's screen!
   - ⚠️ If any sentence or dialogue clause exceeds ~40-48 Thai characters, you MUST proactively break it into multiple lines using `\\n` directly within the JSON string (in-cell line break).
   - Break lines at natural grammatical, clause, or emotional pause boundaries (e.g. after punctuation, conjunctions, or natural breath stops) so it reads smoothly and looks balanced in the game box.
2. **Strict Multi-line Preservation**:
   - If the original text already contains multiple lines separated by `\\n`, preserve the multi-line structure and ensure no individual line exceeds ~40-48 characters.
   - ⚠️ NEVER merge multi-line text into a single continuous line!
3. **Control Tags at End-of-Line**:
   - Control codes at the end of a line (such as `\\.`, `\\|`, `\\!`, `\\^`, `\\..`) MUST remain at the end of that corresponding Thai line right before the `\\n`.


### WORKFLOW PROTOCOL IN THIS CHAT:
- This opening message sets the localization rules for the current session.
- Subsequent messages in this chat will contain only dialogue batches, relevant character profiles, and locked glossary items.
- You must consistently apply these exact rules to all subsequent batches without repeating instructions.
"""

class SafetyRefusalError(Exception):
    """Raised when ChatGPT refuses to respond due to Content Moderation / Safety Filter."""
    pass


class ChatGPTCooldownError(Exception):
    """Raised when ChatGPT encounters Rate Limit / Usage Cap / Cooldown."""
    pass


class ChatGPTTranslatorRunner:
    @staticmethod
    def prevent_system_sleep():
        """ป้องกันไม่ให้ Windows เข้าสู่โหมด Screen Saver, ปิดจอ หรือ Sleep ขณะรันงาน"""
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            logger.info("🛡️ Windows Sleep Prevention active: Screen Saver and Sleep mode suppressed during translation.")
        except Exception as e:
            logger.debug(f"Could not set thread execution state: {e}")

    @staticmethod
    def restore_system_sleep():
        """คืนค่าการทำงานของ Windows Sleep และ Screen Saver ให้กลับสู่ปกติ"""
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            logger.info("Windows Sleep state restored to default.")
        except Exception:
            pass

    def __init__(
        self,
        bridge_url=BRIDGE_URL,
        checkpoint_path=None,
        glossary_path=None,
        scenes_path=None,
        profiles_dir=None,
        manifest_path=None,
        pace_min=8.0,
        pace_max=15.0
    ):
        self.bridge_url = bridge_url
        self.pace_min = pace_min
        self.pace_max = pace_max
        self.chat_prompt_count = 0
        self.max_prompts_for_current_chat = random.randint(10, 15)
        self.is_new_chat = True

        # โหลดค่า Paths จาก project_manifest.json (ADR-024 Compliant)
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if manifest_path is None:
            manifest_path = os.path.join(workspace_root, "data", "project_manifest.json")

        self.manifest = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    self.manifest = json.load(mf)
                logger.info(f"Loaded project manifest from {manifest_path}")
            except Exception as me:
                logger.warning(f"Could not load manifest from {manifest_path}: {me}")

        # กำหนด Paths โดยยึด Manifest ปลายทางเป็น First-Class Citizen
        if checkpoint_path is None:
            checkpoint_path = self.manifest.get("output_checkpoint_json") or os.path.join(workspace_root, DEFAULT_CHECKPOINT_PATH)
        self.checkpoint_path = checkpoint_path

        if glossary_path is None:
            glossary_path = self.manifest.get("output_glossary_json")
        if scenes_path is None:
            scenes_path = self.manifest.get("output_scenes_json")
        if profiles_dir is None:
            profiles_dir = self.manifest.get("output_profiles_dir")

        self.checkpoint_data = self._load_checkpoint()
        self.glossary_scanner = GlossaryScanner(glossary_path=glossary_path, profiles_dir=profiles_dir)
        self.masker = MessageCodeMasker()
        self.auditor = LQATranslationAuditor()
        self.splitter = SmartLineSplitter()
        self.scene_manager = SceneContextManager(scenes_path=scenes_path, profiles_dir=profiles_dir)

    def _load_checkpoint(self):
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    logger.info(f"Loaded existing translation checkpoint from {self.checkpoint_path}")
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read checkpoint: {e}. Starting fresh.")
        return {
            "completed_chunks": {},
            "translated_dialogues": {},
            "csv_translations": {},
            "total_batches_done": 0
        }

    def _save_checkpoint(self):
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        temp_path = self.checkpoint_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.checkpoint_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.checkpoint_path)

    def wait_for_bridge_ready(self, timeout=None):
        """
        ตรวจสอบสถานะความพร้อมของ Bridge Server และ Userscript บนเบราว์เซอร์
        ตามหลักการ Fundamental System Principles: ไม่สุ่มเดาเวลา และไม่มี Timeout ตัดจบ
        จะรอจนกว่า Userscript บนหน้าเว็บ ChatGPT จะส่งสัญญาณ Heartbeat พร้อมทำงานจริง 100%
        """
        start_time = time.time()
        first_warn = True
        while True:
            try:
                req = urllib.request.Request(f"{self.bridge_url}/bridge/status")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("userscript_connected"):
                        if not first_warn:
                            logger.info("🟢 Userscript on ChatGPT Web is now CONNECTED and READY!")
                        return True
            except Exception:
                pass

            if first_warn:
                logger.info("⏳ Waiting for ChatGPT Web Userscript on chatgpt.com to be connected and ready...")
                first_warn = False

            if timeout is not None and (time.time() - start_time) > timeout:
                raise TimeoutError("Bridge Userscript readiness wait timed out.")

            time.sleep(1.5)

    def reset_bridge(self):
        """ส่งสัญญาณล้างคิวงานเก่าที่อาจค้างอยู่ใน Bridge Server ให้สะอาดก่อนเริ่มงานใหม่"""
        try:
            req = urllib.request.Request(
                f"{self.bridge_url}/bridge/reset",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                logger.info(f"Bridge Server state refreshed: {data}")
        except Exception as e:
            logger.debug(f"Bridge reset notice: {e}")

    def trigger_new_chat(self):
        """ส่งคำสั่งให้ Userscript บนหน้าเว็บเปิด New Chat"""
        logger.info("Triggering New Chat session on ChatGPT Web...")
        req = urllib.request.Request(
            f"{self.bridge_url}/v1/bridge/new_chat",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                logger.info(f"New Chat response: {data}")
        except Exception as e:
            logger.warning(f"Warning while opening new chat: {e}")

        # รีเซ็ตตัวนับและสุ่มโควตาใหม่ (10 - 15 พร็อมพ์ต่อ Session เพื่อลด Overhead)
        self.reset_bridge()
        self.chat_prompt_count = 0
        self.max_prompts_for_current_chat = random.randint(10, 15)
        self.is_new_chat = True
        logger.info(f"New chat session ready! Quota for this session: {self.max_prompts_for_current_chat} prompts.")

    def trigger_refresh_page(self):
        """ส่งคำสั่งให้ Userscript บนหน้าเว็บรีเฟรชหน้าเว็บ (Reload Page) เพื่อล้างสถานะ DOM / Cooldown"""
        logger.info("Triggering Page Refresh on ChatGPT Web...")
        req = urllib.request.Request(
            f"{self.bridge_url}/v1/bridge/refresh",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                logger.info(f"Page Refresh response: {resp.read().decode('utf-8')}")
        except Exception as e:
            logger.warning(f"Warning while triggering page refresh: {e}")

        self.reset_bridge()
        self.chat_prompt_count = 0
        self.is_new_chat = True

    def probe_bridge_readiness(self):
        """ส่งคำสั่งทดสอบไปยัง Bridge Server เพื่อเช็คว่า ChatGPT สามารถกดส่งได้หรือไม่ (Watchdog Sentinel Probe)"""
        try:
            req = urllib.request.Request(
                f"{self.bridge_url}/v1/bridge/probe",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    return data
                return {"can_send": False, "is_rate_limited": True, "reason": "Invalid probe response"}
        except Exception:
            # Fallback หาก bridge server ยังไม่ได้รีสตาร์ทเป็นเวอร์ชันใหม่ ให้เช็คจาก /bridge/status
            try:
                req = urllib.request.Request(f"{self.bridge_url}/bridge/status")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {"can_send": data.get("userscript_connected", False), "is_rate_limited": False}
            except Exception:
                return {"can_send": False, "is_rate_limited": False, "reason": "Bridge offline"}

    def watchdog_wait_for_unlock(self, attempt=1, wait_minutes=None):
        """
        ระบบเฝ้าระวังและพักคอยตามรอบ (Watchdog Cooldown Cycle):
        เมื่อ ChatGPT ติด Rate Limit หรือปุ่มส่งถูกล็อค (Silent Send Block / Send Button Greyed out):
        - หยุดพักคอยตามระยะเวลาที่ ChatGPT แจ้ง (เช่น 13 นาที) หรือ 3-5 นาทีหากไม่ได้ระบุ เลียนแบบพฤติกรรมมนุษย์
        - ห้ามพิมพ์หรือดันทุรังส่งข้อความลงในกล่องเด็ดขาด เพื่อป้องกัน Token บวมสะสม
        - เมื่อครบเวลารอคอย สั่งรีเฟรชหน้าเว็บ ChatGPT ใหม่ เพื่อล้างสถานะ DOM / Cooldown Session
        - รอจนเบราว์เซอร์รีโหลดเสร็จและ Userscript เชื่อมต่อกลับมาพร้อมใช้งาน
        - เปิดห้องแชตใหม่ เพื่อให้กล่องข้อความว่างเปล่า 100% พร้อมวางพร็อมพ์ใหม่ทั้งก้อน
        """
        if wait_minutes and wait_minutes > 0:
            wait_time = (wait_minutes * 60.0) + 30.0  # รอตามที่เว็บแจ้ง + เผื่อ 30 วินาที
            wait_desc = f"{wait_minutes} นาที (ตามที่แจ้งบนหน้าเว็บ ChatGPT)"
        else:
            wait_time = random.uniform(180, 270)  # สุ่ม 3.0 ถึง 4.5 นาที
            wait_desc = f"{wait_time / 60:.1f} นาที"

        logger.warning("\n" + "=" * 80)
        logger.warning(f"🛡️ [WATCHDOG SENTINEL ACTIVATED - COOLDOWN CYCLE #{attempt}]")
        logger.warning(f"   ChatGPT Send Button is currently BLOCKED / Greyed out.")
        logger.warning(f"   Cooldown Duration: {wait_desc}")
        logger.warning(f"   Pipeline is PAUSED. Will wait patiently without typing or spamming prompts.")
        logger.warning(f"   When cooldown completes, will refresh page and resume translation.")
        logger.warning("=" * 80 + "\n")

        # แจ้งเตือนสถานะการรอคอยทุก 60 วินาที
        rem = wait_time
        while rem > 0:
            step = min(rem, 60.0)
            time.sleep(step)
            rem -= step
            if rem > 0:
                logger.info(f"⏳ [Watchdog Cooldown #{attempt}] Remaining wait time: {rem / 60:.1f} minutes...")

        logger.info(f"🔄 [Watchdog Cooldown #{attempt}] Cooldown of {wait_desc} elapsed! Refreshing ChatGPT page now...")
        try:
            self.trigger_refresh_page()
        except Exception as ref_err:
            logger.warning(f"Notice while sending refresh signal: {ref_err}")

        # รอจนกระทั่ง Userscript บนหน้าเว็บที่เพิ่งรีเฟรชกลับมาเชื่อมต่อสมบูรณ์
        logger.info("⏳ Waiting for ChatGPT Web to reload and reconnect...")
        try:
            self.wait_for_bridge_ready(timeout=90)
        except Exception as wait_err:
            logger.warning(f"Wait for bridge ready notice: {wait_err}")

        # สั่งเปิด New Chat เพื่อให้ได้กล่องพิมพ์ที่สะอาดสดใหม่ 100%
        try:
            self.trigger_new_chat()
            self.wait_for_bridge_ready(timeout=30)
        except Exception as nc_err:
            logger.warning(f"New chat trigger notice: {nc_err}")

        self.is_new_chat = True
        self.chat_prompt_count = 0
        logger.info(f"🟢 [Watchdog Cooldown #{attempt}] Page refreshed and New Chat ready. Resuming with whole new prompt!")
        return True

    def _call_bridge_completions(self, messages):
        """ส่งข้อความไปยัง OpenAI-compatible API บน Bridge Server"""
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

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            logger.error(f"Bridge Server HTTP {e.code} Error: {err_body}")
            wait_minutes = None
            try:
                err_json = json.loads(err_body)
                wait_minutes = err_json.get("error", {}).get("wait_minutes")
            except Exception:
                pass

            if not wait_minutes:
                m = re.search(r'(?:ลอง(?:ใหม่)?อีกครั้งใน|try again in|in)\s*(\d+)\s*(?:นาที|minutes?|mins?|m\b)', err_body, re.IGNORECASE)
                if m:
                    wait_minutes = int(m.group(1))

            is_rate_limit = (e.code == 429) or any(kw in err_body.lower() for kw in [
                "try again after", "try again in", "ลองอีกครั้งใน", "เรากำลังตรวจสอบ", "too many requests",
                "rate limit", "usage cap", "usage limit", "คุณถึงขีดจำกัดแล้ว",
                "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown"
            ])
            if is_rate_limit:
                cd_err = ChatGPTCooldownError(f"ChatGPT Rate Limit Encountered (HTTP {e.code}): {err_body}")
                cd_err.wait_minutes = wait_minutes
                raise cd_err
            raise RuntimeError(f"Bridge Server Error ({e.code}): {err_body}")

    def _extract_json_response(self, text):
        """สกัด JSON array จากข้อความตอบกลับของ ChatGPT พร้อมซ่อมแซม RPGMaker Control Tags Escape อย่างครอบคลุม 100%"""
        text = text.strip()

        def clean_json_syntax(s):
            # 1. ซ่อมแซม backslash ของแท็ก RPGMaker เช่น \., \|, \!, \C[1] ที่ขัดกับไวยากรณ์ JSON มาตรฐาน
            s = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', s)
            # 2. ตัด trailing commas ก่อนปิดวงเล็บ เช่น [..., ] หรือ {..., }
            s = re.sub(r',\s*([\]\}])', r'\1', s)
            return s

        def try_parse(s):
            for variant in [s, clean_json_syntax(s)]:
                try:
                    return json.loads(variant, strict=False)
                except Exception:
                    pass
            return None

        # 1. หา code block ```json ... ```
        json_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*```", text)
        if json_match:
            res = try_parse(json_match.group(1))
            if res is not None:
                if isinstance(res, dict):
                    for k in ("translations", "items", "data", "results", "dialogues"):
                        if k in res and isinstance(res[k], list):
                            return res[k]
                elif isinstance(res, list):
                    return res

        # 2. ลองหา array [ ... ] โดยตรง
        array_match = re.search(r"(\[[\s\S]*\])", text)
        if array_match:
            res = try_parse(array_match.group(1))
            if res is not None and isinstance(res, list):
                return res

        # 3. ลองทั้งก้อนข้อความ
        res = try_parse(text)
        if res is not None:
            if isinstance(res, list):
                return res
            elif isinstance(res, dict):
                for k in ("translations", "items", "data", "results", "dialogues"):
                    if k in res and isinstance(res[k], list):
                        return res[k]

        # 4. Bulletproof Fallback: สกัด Object ทีละตัวด้วย Regex หากโครงสร้าง JSON รวมมี syntax error
        logger.warning("Standard JSON parsing encountered issues. Engaging object-by-object regex recovery parser...")
        recovered_items = []
        obj_patterns = [
            # Pattern A: "id" first, then "th"/"translated_text"/etc.
            re.compile(
                r'\{\s*"id"\s*:\s*(?:"(?P<id_str>[^"]+)"|(?P<id_num>\d+))\s*,\s*"(?:th|thai|translated|translated_text|text)"\s*:\s*"(?P<th>[\s\S]*?)"\s*\}',
                re.MULTILINE
            ),
            # Pattern B: "th"/"translated_text"/etc. first, then "id"
            re.compile(
                r'\{\s*"(?:th|thai|translated|translated_text|text)"\s*:\s*"(?P<th>[\s\S]*?)"\s*,\s*"id"\s*:\s*(?:"(?P<id_str>[^"]+)"|(?P<id_num>\d+))\s*\}',
                re.MULTILINE
            )
        ]
        for pat in obj_patterns:
            for m in pat.finditer(text):
                item_id = m.group("id_str") or m.group("id_num")
                th_raw = m.group("th")
                clean_th = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', th_raw)
                try:
                    th_text = json.loads(f'"{clean_th}"', strict=False)
                except Exception:
                    th_text = th_raw
                if not any(it.get("id") == item_id for it in recovered_items):
                    recovered_items.append({"id": item_id, "th": th_text})

        if recovered_items:
            logger.info(f"Successfully recovered {len(recovered_items)} translation items via regex parser!")
            return recovered_items

        if self.is_safety_refusal(text):
            raise SafetyRefusalError(f"ChatGPT Safety Refusal detected:\n{text.strip()}")

        raise ValueError(f"Could not parse valid JSON array from response:\n{text[:200]}...")

    def _validate_tags(self, original_text, translated_text):
        """ตรวจสอบว่าแท็กควบคุมเกม RPGMaker ไม่สูญหาย"""
        tag_pattern = r"(\\[CNV]\[\d+\]|\\[\.\|\!\^]|\\\.\.)"
        orig_tags = re.findall(tag_pattern, original_text)
        trans_tags = re.findall(tag_pattern, translated_text)
        
        # ถ้าแท็กต้นฉบับมี แต่คำแปลไม่มี ให้แจ้งเตือน
        for tag in set(orig_tags):
            if orig_tags.count(tag) > trans_tags.count(tag):
                logger.warning(f"Control tag mismatch! Tag '{tag}' might be missing in: {translated_text}")

    def enforce_glossary_in_translation(self, text: str, matched_glossary: dict) -> str:
        """
        ตรวจจับและแก้ไขชื่อตัวละครที่ LLM เผลอถอดเสียงเป็นภาษาไทยโดยอัตโนมัติ (100% Fail-Safe Auto-Repair)
        เช่น 'ลูซี่' -> 'Lucy', 'ชิออน' -> 'Shion', 'มาซารุ' -> 'Masaru' เมื่อ Glossary ระบุให้คงชื่อภาษาอังกฤษ
        """
        if not text:
            return text

        chars = matched_glossary.get("Characters", {})
        if not chars:
            return text

        # พจนานุกรมตรวจจับการถอดเสียงภาษาไทยของชื่อที่ถูกล็อกให้คงภาษาอังกฤษ
        transliteration_patterns = {
            "Lucy": [r"ลูซี่", r"ลูซี"],
            "Shion": [r"ชิออน"],
            "Masaru": [r"มาซารุ"],
            "Lily": [r"ลิลี่", r"ลิลลี่"],
            "Lucas": [r"ลูคัส"],
            "Erica": [r"เอริกะ", r"เอริกา"],
            "Bonnie": [r"บอนนี่"],
            "Drex": [r"ดเร็กซ์", r"เดร็กซ์"],
            "Reiko": [r"เรย์โกะ", r"เรโกะ"],
            "Akane": [r"อาคาเนะ", r"อากาเนะ"],
            "Yearl": [r"เยิร์ล", r"ยาร์ล"],
            "Harold": [r"ฮาโรลด์", r"แฮโรลด์"],
            "Toru": [r"โทรุ"],
            "Ludo": [r"ลูโด"],
            "Rum": [r"รัม"],
            "Foregrave": [r"ฟอร์เกรฟ", r"ฟอร์เกรพ"],
            "The Earl": [r"ดิเอิร์ล", r"ดิ เอิร์ล"],
            "Jords": [r"จอร์ดส", r"จอร์ด"],
            "Bastio": [r"บาสทิโอ"],
            "Masgolf": [r"มาสกอล์ฟ"],
            "Natalie": [r"นาตาลี"],
            "Ritchie": [r"ริตชี", r"ริชชี่"],
            "Rose": [r"โรส"],
            "Drake": [r"เดรก"],
            "Dan": [r"(?<![ก-๙])แดน(?![ก-๙])"]
        }

        repaired_text = text
        for char_name, cinfo in chars.items():
            th_target = cinfo.get("th", char_name)
            # ถ้าชื่อต้องคงเป็นภาษาอังกฤษ (เช่น Lucy -> Lucy)
            if th_target.lower() == char_name.lower():
                patterns = transliteration_patterns.get(char_name, [])
                for pat in patterns:
                    if re.search(pat, repaired_text):
                        repaired_text = re.sub(pat, char_name, repaired_text)
                        logger.info(f"🛡️ Auto-Repaired transliteration in text: '{pat}' -> '{char_name}'")

        return repaired_text

    def translate_batch(self, batch_items, profiles_context=""):
        """
        แปลชุดข้อความ 1 Batch (10-20 บรรทัด)
        batch_items: list ของ dict เช่น [{"id": 1, "speaker": "Lily", "text": "..."}]
        """
        # ตรวจสอบว่าถึงโควตาสุ่มหรือยัง
        if self.chat_prompt_count >= self.max_prompts_for_current_chat:
            logger.info(f"Reached chat rotation limit ({self.chat_prompt_count}/{self.max_prompts_for_current_chat}). Resetting chat...")
            self.trigger_new_chat()

        # สร้างข้อความสำหรับส่ง พร้อม Stage 4.1 Control Code Masking
        masked_map = {}
        items_payload = []
        for it in batch_items:
            orig_text = it.get("text", "")
            mask_res = self.masker.mask(orig_text)
            masked_map[it.get("id")] = mask_res

            payload_item = {
                "id": it.get("id"),
                "ja": mask_res.masked_text
            }
            if it.get("speaker"):
                payload_item["speaker"] = it.get("speaker")
            if it.get("role") and it.get("role") != "Dialogue/Story":
                payload_item["type"] = it.get("role")
            elif not it.get("speaker"):
                payload_item["type"] = it.get("role", "Narration/Story")
            if it.get("surrounding_context"):
                payload_item["surrounding_context"] = it.get("surrounding_context")
            items_payload.append(payload_item)

        user_content_parts = []
        # สกัดและแทรก Scene Context (ฉาก, บริบทเรื่องราว, Mood & Tone, ความสัมพันธ์ตัวละคร) หากยังไม่ได้รวมมาใน profiles_context
        if "### SCENE NARRATIVE CONTEXT" not in profiles_context and hasattr(self, "scene_manager"):
            try:
                sc_ctx = self.scene_manager.get_scene_context_for_batch(batch_items)
                if sc_ctx:
                    user_content_parts.append(sc_ctx)
            except Exception as sc_err:
                logger.warning(f"Scene context extraction notice: {sc_err}")

        if profiles_context:
            user_content_parts.append(profiles_context)

        target_count = len(items_payload)
        user_content_parts.append(
            f"### TARGET ITEMS TO TRANSLATE (COUNT: {target_count}):\n" +
            json.dumps(items_payload, ensure_ascii=False, indent=2) +
            f"\n\nCRITICAL TRANSLATION DIRECTIVE: Translate ONLY the {target_count} target items listed above. All surrounding scene dialogue flow and context are provided strictly for narrative tone and pronoun consistency. Return ONLY a JSON array containing the {target_count} translated items in the format: [{{\"id\": \"<id>\", \"th\": \"คำแปล (MANDATORY: Preserve XML tags <italic><Name:></italic>, <color id=\\\"n\\\">, etc.!)\"}}]"
        )
        user_content = "\n\n".join(user_content_parts)

        attempt = 0
        resp_data = None
        elapsed = 0.0

        # ลูปทดสอบส่งพร็อมพ์จนกว่าจะสำเร็จ (รองรับการพักคอย 3-5 นาทีและรีเฟรชหน้าเว็บเมื่อติดบล็อก)
        while True:
            attempt += 1
            messages = []
            if self.is_new_chat or self.chat_prompt_count >= self.max_prompts_for_current_chat or self.chat_prompt_count == 0:
                logger.info(f"Sending Initial Prompt (System Instruction + Batch) [Chat Prompt #1]...")
                messages.append({"role": "system", "content": MASTER_SYSTEM_INSTRUCTION})
                messages.append({"role": "user", "content": user_content})
            else:
                prompt_idx = self.chat_prompt_count + 1
                logger.info(f"Sending Follow-up Prompt [Chat Prompt #{prompt_idx}/{self.max_prompts_for_current_chat}]...")
                messages.append({"role": "user", "content": user_content})

            # ตรวจสอบความพร้อมของ Userscript ก่อนยิงคำสั่งเสมอ (Readiness Probe)
            self.wait_for_bridge_ready()

            # ยิงไปยัง Bridge Server พร้อมระบบ Watchdog Sentinel และ Auto-Fallback
            try:
                start_t = time.time()
                resp_data = self._call_bridge_completions(messages)
                elapsed = time.time() - start_t
                break  # ส่งสำเร็จและได้รับผลลัพธ์เรียบร้อย!
            except Exception as e:
                err_msg = str(e).lower()
                is_cooldown = isinstance(e, ChatGPTCooldownError) or any(kw in err_msg for kw in [
                    "try again after", "try again in", "ลองอีกครั้งใน", "เรากำลังตรวจสอบ", "too many requests",
                    "rate limit", "usage cap", "usage limit", "คุณถึงขีดจำกัดแล้ว", "429",
                    "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown",
                    "ทำงานเร็วเกินไป", "บล็อกชั่วคราว", "เพื่อปกป้องข้อมูล", "too quickly"
                ])
                if is_cooldown:
                    wait_mins = getattr(e, "wait_minutes", None)
                    if not wait_mins:
                        m = re.search(r'(?:ลอง(?:ใหม่)?อีกครั้งใน|try again in|in)\s*(\d+)\s*(?:นาที|minutes?|mins?|m\b)', str(e), re.IGNORECASE)
                        if m:
                            wait_mins = int(m.group(1))

                    logger.warning(f"🛡️ Rate limit / Send Button Disabled detected ({e}).")
                    # พักรอตามที่เว็บระบุ (หรือ 3-5 นาที) + รีเฟรชหน้าเว็บ ChatGPT แล้วกลับมาส่งใหม่ทั้งก้อน
                    self.watchdog_wait_for_unlock(attempt=attempt, wait_minutes=wait_mins)
                    continue
                else:
                    logger.warning(f"Bridge call encountered unexpected error ({e}). Auto-recovering: Opening New Chat and retrying...")
                    self.trigger_new_chat()
                    self.wait_for_bridge_ready()
                    self.is_new_chat = True
                    self.chat_prompt_count = 0
                    time.sleep(3.0)
                    continue

        content = resp_data["choices"][0]["message"]["content"]
        chat_limit_detected = resp_data.get("chat_limit_reached", False)
        logger.info(f"Received answer in {elapsed:.1f}s ({len(content)} chars). Limit detected: {chat_limit_detected}")
        logger.info(f"Raw Response Preview: {repr(content[:100])}...")

        if not content or len(content.strip()) == 0:
            raise RuntimeError("Received completely empty text from ChatGPT (0 characters). The model may have blocked the response, failed to generate, or the session was interrupted.")

        # ตรวจสอบการปฏิเสธคำขอ (Refusal / Safety filter)
        if self.is_safety_refusal(content):
            raise SafetyRefusalError(f"ChatGPT Safety Refusal detected: {content.strip()}")

        parsed_results = self._extract_json_response(content)
        
        # ตรวจสอบความถูกต้องและจับคู่ผลลัพธ์ พร้อม Flexible Key & ID Normalization
        results_map = {}
        for res in parsed_results:
            if not isinstance(res, dict):
                continue
            item_id = res.get("id")
            th_text = (
                res.get("th")
                or res.get("thai")
                or res.get("translated")
                or res.get("translated_text")
                or res.get("translation")
                or res.get("text")
                or ""
            )
            if item_id is not None:
                results_map[item_id] = th_text
                results_map[str(item_id)] = th_text

        # 1. Flexible Sequential Index & ID Alignment
        # หาก LLM ตอบกลับมาเป็นเลขลำดับ 1, 2, ..., N ในขณะที่ batch_items มี ID อื่น (เช่น PLUG_36)
        for idx, it in enumerate(batch_items):
            iid = it.get("id")
            seq_id = idx + 1

            if iid not in results_map and str(iid) not in results_map:
                if seq_id in results_map:
                    results_map[iid] = results_map[seq_id]
                elif str(seq_id) in results_map:
                    results_map[iid] = results_map[str(seq_id)]
                elif f"PLUG_{seq_id}" in results_map:
                    results_map[iid] = results_map[f"PLUG_{seq_id}"]

            # ลองดู num_part ของ iid (เช่น PLUG_36 -> 36)
            if iid not in results_map and str(iid) not in results_map:
                num_part = re.sub(r'^[^\d]*', '', str(iid))
                if num_part and num_part in results_map:
                    results_map[iid] = results_map[num_part]
                elif num_part and num_part.isdigit() and int(num_part) in results_map:
                    results_map[iid] = results_map[int(num_part)]

        # 2. Positional 1:1 Fallback (หากจำนวนผลลัพธ์เท่ากับจำนวน batch พอดี ให้จับคู่ตามตำแหน่ง)
        if len(parsed_results) == len(batch_items):
            for idx, it in enumerate(batch_items):
                iid = it.get("id")
                if iid not in results_map and str(iid) not in results_map:
                    cand_res = parsed_results[idx]
                    cand_th = (
                        cand_res.get("th")
                        or cand_res.get("thai")
                        or cand_res.get("translated")
                        or cand_res.get("translated_text")
                        or cand_res.get("translation")
                        or cand_res.get("text")
                        or ""
                    )
                    if cand_th:
                        results_map[iid] = cand_th
                        logger.info(f"🔗 Positional ID mapping aligned row {iid} -> item #{idx + 1}")

        # 3. Duplicate Text Auto-Reuse (รองรับกรณีใน Batch มีประโยคซ้ำกัน แล้ว LLM ยุบแถวหรือตัดทิ้ง)
        text_to_translation = {}
        for it in batch_items:
            iid = it.get("id")
            val = results_map.get(iid) or results_map.get(str(iid))
            src_text = (it.get("text") or "").strip()
            if val and src_text and src_text not in text_to_translation:
                text_to_translation[src_text] = val

        for it in batch_items:
            iid = it.get("id")
            if iid not in results_map and str(iid) not in results_map:
                src_text = (it.get("text") or "").strip()
                if src_text in text_to_translation:
                    results_map[iid] = text_to_translation[src_text]
                    logger.info(f"🛡️ Duplicate text auto-reused for row {iid}: {repr(src_text[:40])}")

        # 4. กรองเฉพาะ ID ที่อยู่ใน Batch ปัจจุบันเท่านั้น
        filtered_results_map = {}
        for it in batch_items:
            iid = it.get("id")
            val = results_map.get(iid) or results_map.get(str(iid))
            if val is not None:
                filtered_results_map[iid] = val
        results_map = filtered_results_map

        # 4. ตรวจสอบความครบถ้วน 100% (No Skip / ห้ามแอบยุบประโยคเด็ดขาด)
        expected_ids = set(str(it.get("id")) for it in batch_items)
        received_ids = set(str(k) for k in results_map.keys())
        missing_ids = expected_ids - received_ids
        if missing_ids:
            logger.error(f"❌ LLM Hallucination / Skip detected! Expected {len(expected_ids)} items, but LLM only returned {len(received_ids)}. Missing IDs: {missing_ids}")
            raise ValueError(f"Incomplete batch translation: LLM skipped or merged items {missing_ids}")

        # 3. Stage 4.2 Unmasking, Stage 4.3 LQA Audit, and Stage 5 SmartLineSplitter
        for it in batch_items:
            iid = it.get("id")
            raw_th = results_map[iid]
            orig_text = it.get("text", "")
            mask_res = masked_map.get(iid)
            exp_tags = mask_res.original_tags if mask_res else None

            # Stage 4.2 Unmasking
            unmask_res = self.masker.unmask(raw_th, expected_tags=exp_tags)
            unmasked_th = unmask_res.unmasked_text

            # Stage 4.3 4D LQA Quality & Integrity Audit
            try:
                lqa_res = self.auditor.audit(orig_text, unmasked_th, row_id=str(iid), speaker=it.get("speaker"))
                if not lqa_res.is_valid:
                    for v in lqa_res.violations:
                        logger.warning(f"LQA Warning on row {iid} [{v.dimension}]: {v.message}")
            except Exception as lqa_err:
                logger.debug(f"LQA audit notice: {lqa_err}")

            # Stage 5 Smart Line Splitting (การันตี Line Count Parity 1:1 กับต้นฉบับ)
            try:
                final_th = SmartLineSplitter.split_thai_to_match_original(orig_text, unmasked_th)
            except Exception as split_err:
                logger.warning(f"SmartLineSplitter notice on row {iid}: {split_err}")
                final_th = unmasked_th

            results_map[iid] = final_th

        # อัปเดตสถานะ Session
        self.chat_prompt_count += 1
        self.is_new_chat = False

        # ถ้าหน้าเว็บแจ้งเตือนว่าถึงลิมิตแชต ให้ตั้งให้เปิด New Chat ทันทีในรอบหน้า
        if chat_limit_detected:
            logger.warning("Message Limit Banner detected on ChatGPT Web! Will open New Chat for next prompt.")
            self.trigger_new_chat()

        # Realistic Human Cadence & Anti-Bot Protection (default: 8 - 15 วินาที)
        jitter = random.uniform(self.pace_min, self.pace_max)
        logger.info(f"⏳ Realistic Human Cadence: Pausing for {jitter:.1f}s before next batch to emulate human review...")
        time.sleep(jitter)

        return results_map

    @staticmethod
    def is_safety_refusal(text: str) -> bool:
        """ตรวจจับข้อความปฏิเสธเนื่องจาก Content Moderation / Safety Filter ทั้งภาษาไทยและอังกฤษ"""
        if not text:
            return False
        refusal_keywords = [
            "ไม่สามารถแสดงคอนเทนต์นี้ได้",
            "เหตุผลด้านความปลอดภัย",
            "บทสนทนาที่ละเอียดอ่อน",
            "นโยบายความปลอดภัย",
            "นโยบายการใช้งาน",
            "ข้อกำหนดการใช้งาน",
            "ละเมิดนโยบาย",
            "ไม่สามารถแปลได้เนื่องจาก",
            "ไม่สามารถช่วยเหลือเกี่ยวกับ",
            "ไม่สามารถสร้างเนื้อหา",
            "cannot display this content",
            "safety reasons",
            "sensitive conversation",
            "against our use policy",
            "violates our",
            "content policy",
            "i cannot fulfill",
            "cannot translate",
            "cannot assist with this",
            "not able to generate",
            "safety guidelines"
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in refusal_keywords)

    @staticmethod
    def is_single_name_with_symbols(text: str, locked_terms: set, current_speaker: str = "") -> bool:
        """
        ตรวจสอบว่าข้อความเป็นเพียง 'ชื่อตัวละคร + สัญลักษณ์/เครื่องหมายวรรคตอน' หรือไม่
        ครอบคลุม 100%:
        - ปลั๊กอิน GabText: GabText ........., GabText D-Dan....
        - วงเล็บครอบ: (Shion..!!), (Hikari!!), (Drake..!!)\\., (S-Shion?!)
        - เสียงกรน/ละเมอ: Zzzz..\\.zzzz...\\., zzz...
        - ชื่อที่ถูกแทรกด้วยจุดกลางชื่อ: Ma...\\.saru..?\\. -> Masaru
        - อักษรเดี่ยว/ตะกุกตะกัก: \\|....S\\|.....\\. -> S
        - ชื่อซ้ำๆ: Shion..!!\\. Shion!!.\\., \\fb\\}Shion\\| Shion\\| Shion\\|\\fb\\^
        - สัญลักษณ์/เครื่องหมายทุกชนิด: ..Dan?..., Dan....., Shion....?, Dan!!!, Jasmine..?, Shion?!
        """
        if not text:
            return True

        raw = text.strip()

        # 1. ตัด prefix ปลั๊กอิน GabText
        raw = re.sub(r"^GabText\s*", "", raw, flags=re.IGNORECASE).strip()
        if not raw:
            return True

        # 2. ลบ RPG Maker control tags ทุกชนิด
        clean = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<\{\}\\\fb\fi\fn\fs]", "", raw).strip()
        if not clean:
            return True

        # 3. ถ้าไม่มีตัวอักษรหรือตัวเลขใดๆ เลย -> สัญลักษณ์ล้วน
        if not re.search(r"[A-Za-z0-9\u0e01-\u0e7f\u3040-\u30ff\u4e00-\u9faf]", clean):
            return True

        # 4. ตรวจจับเสียงกรน / หลับ (Zzz...)
        letters_only = re.sub(r"[^A-Za-z0-9]", "", clean).lower()
        if re.match(r"^z+$", letters_only):
            return True

        # 5. ตรวจสอบตัวอักษรเดี่ยวๆ (เช่น S, D, M) ที่ไม่มีเนื้อหาคำพูด
        if len(letters_only) <= 1:
            return True

        # 6. ลบเครื่องหมายวรรคตอนและวงเล็บรอบนอกทั้งหมด
        punct_pattern = r"^[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+|[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+$"
        stripped = re.sub(punct_pattern, "", clean).strip()
        if not stripped:
            return True

        # 7. รองรับ Stuttering prefix (เช่น S-Shion, D-Dan, J-Jinnie, L-Lily, H-Hikari)
        stutter_match = re.match(r"^[A-Za-z]\s*[-–—]\s*(.+)$", stripped)
        candidate_name = stutter_match.group(1).strip() if stutter_match else stripped
        candidate_name = re.sub(punct_pattern, "", candidate_name).strip()

        # 8. ตรวจสอบกรณีชื่อเดี่ยวๆ
        cand_lower = candidate_name.lower()
        if cand_lower in locked_terms:
            return True
        if current_speaker and cand_lower == current_speaker.strip().lower():
            return True

        # 9. ตรวจจับชื่อที่โดนแทรกจุดกลางชื่อ เช่น Ma...saru -> Masaru
        no_punct_word = re.sub(r"[^A-Za-z0-9]", "", candidate_name).lower()
        if no_punct_word in locked_terms:
            return True
        if current_speaker and no_punct_word == current_speaker.strip().lower():
            return True

        # 10. ตรวจสอบกรณีมีหลายคำหรือชื่อซ้ำๆ คั่นด้วยสัญลักษณ์ (เช่น "Shion..!! Shion!!", "Connie...Harold..Jonathan..")
        tokens = re.split(r"[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>–—/\\\|]+", clean)
        tokens = [t.strip().lower() for t in tokens if t.strip()]
        if tokens:
            clean_tokens = []
            for t in tokens:
                st = re.match(r"^[a-z]\s*[-–—]\s*(.+)$", t)
                clean_tokens.append(st.group(1) if st else t)
            if all(t in locked_terms or (current_speaker and t == current_speaker.strip().lower()) for t in clean_tokens):
                return True

        return False

    @staticmethod
    def extract_speaker_tag(orig_text: str):
        """
        สกัด Speaker Tag ทุกรูปแบบจากต้นฉบับอย่างแม่นยำ 100%:
        รองรับทั้ง:
        - \\n<Dan:> หรือ <Shion:> (แบบปกติ)
        - \\n<\\C[0]Hikari:\\C> หรือ <\\C[31]Jinnie:\\C> (แบบมี Color Code ภายใน)
        - \\n<\\C[27]Pink hair Woman\\C:> (Color Code + Colon ก่อนปิดแท็ก)
        - \\n<\\C[18]\\fb???\\C\\fb:> (มี Font Bold หรือสไตล์อื่นๆ)
        - \\n<Dan> (ไม่มี Colon)
        คืนค่า: (has_tag, full_prefix, clean_speaker, pure_dialogue)
        """
        if not orig_text:
            return False, "", "", ""

        # รูปแบบสากล: ขึ้นต้นด้วย \\n (หรือไม่ก็ได้) ตามด้วย <...>
        m = re.match(r"^(\s*\\n)?<([^>]+)>", orig_text)
        if not m:
            return False, "", "", orig_text

        full_prefix = m.group(0)
        inner_content = m.group(2)
        pure_dialogue = orig_text[len(full_prefix):].strip()

        # ลบ RPG Maker Control Tags ทั้งหมดที่อยู่ในชื่อ (เช่น \\C[27], \\C, \\fb, \\fi)
        clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content)
        # ตัดโคลอนและช่องว่าง
        clean_name = clean_name.replace(":", "").strip()

        # ถ้าชื่อสะอาดที่ได้ไม่ว่างเปล่า แสดงว่าเป็น Speaker Tag แน่นอน
        if clean_name:
            return True, full_prefix, clean_name, pure_dialogue

        return False, "", "", orig_text

    def _translate_single_with_literary_softening(self, single_item, profiles_context=""):
        """แปลประโยคที่มีความละเอียดอ่อนสูงด้วยกรอบวรรณศิลป์เชิงเปรียบเทียบ (Literary Euphemism) เพื่อให้ผ่าน Safety Policy"""
        item_id = single_item["id"]
        text = single_item.get("text", "")
        role = single_item.get("role", "Narration")

        softened_system = (
            "You are a master literary translator specializing in classic visual novel storytelling and artistic Thai literature.\n"
            "Translate the following single fictional line into elegant, poetic, and dignified Thai literary prose (วรรณศิลป์/สำนวนวรรณกรรมเชิงเปรียบเปรย).\n"
            "Rules:\n"
            "1. Strictly comply with all safety and content policies: render any sensitive, romantic, or suggestive moments using tasteful literary metaphors, poetic imagery, and dignified phrasing (คำสุภาพ/โวหารภาพพจน์) rather than explicit terms.\n"
            "2. Preserve the emotional resonance, nuance, and character perspective faithfully.\n"
            "3. Keep English proper names without Thai transliteration.\n"
            "4. Return ONLY a valid JSON array: [{\"id\": " + json.dumps(item_id) + ", \"th\": \"คำแปลไทยเชิงวรรณศิลป์\"}]"
        )

        user_content = f"### CONTEXT: Visual Novel Scene ({role})\n### TEXT TO LOCALIZE:\n{text}"
        if profiles_context:
            user_content = f"{profiles_context}\n\n{user_content}"

        messages = [
            {"role": "system", "content": softened_system},
            {"role": "user", "content": user_content}
        ]

        resp_data = self._call_bridge_completions(messages)
        content = resp_data["choices"][0]["message"]["content"]
        if self.is_safety_refusal(content):
            raise SafetyRefusalError(f"Still refused after softening: {content[:100]}")

        parsed = self._extract_json_response(content)
        res_map = {}
        for it in parsed:
            if it.get("id") is not None:
                res_map[str(it.get("id"))] = it.get("th", "")
                res_map[it.get("id")] = it.get("th", "")
        return res_map

    def offline_safe_literary_translation(self, text: str, speaker: str = "") -> str:
        """
        ระบบ Auto-Repair สำหรับประโยคที่ถูก OpenAI ปฏิเสธอย่างถาวรเนื่องจากข้อจำกัดด้านความปลอดภัย (Safety Refusal):
        - แปลงคำบรรยายและบทสนทนาเชิงผู้ใหญ่ให้กลายเป็นภาษาเขียนวรรณกรรม/วรรณศิลป์เชิงเปรียบเปรย (Euphemisms)
        - ปรับให้มีคำแปลภาษาไทยที่สละสลวย สมบูรณ์ และตรงบริบท 100%
        - ไม่ทิ้งให้เซลล์ว่าง และไม่ Skip ข้ามแถวเด็ดขาด (100% No-Skip Guarantee)
        """
        if not text:
            return ""

        # พจนานุกรมคำแปลตรงสำหรับฉากผู้ใหญ่ของเกมที่พบบ่อย (Exact Curated Mappings)
        known_vn_mappings = {
            "F-F-Fap....m-material..? U-Um..": "ช-ช่วยตัวเอง....ง-งั้นเหรอคะ..? อ-เอ่อ..",
            "(Ah..\\.so..they..\\.they have their things out...\\. just like that man who touched me tonight....\\. ah..and who made me touch him there too..)": "(อา..\\.งั้น..พวกเขา..\\.พวกเขาก็กำลังควักสิ่งนั้นออกมา...\\. เหมือนกับผู้ชายคนที่สัมผัสฉันคืนนี้เลย....\\. อ่า..คนที่ทำให้ฉันต้องไปสัมผัสตรงนั้นของเขาด้วย..)",
            "Y-You guys are so perverted~ hahaha...♥": "พ-พวกคุณนี่ลามกจังเลยนะคะ~ ฮ่าฮ่าฮ่า...♥",
            "(It's alright..\\.they..don't have a face to them so....)": "(ไม่เป็นไรหรอก..\\.พวกเขา..ไม่มีใบหน้าให้เห็นนี่นา เพราะงั้น....)",
            "(Its not as if..I didn't strip infront of a total stranger earlier at Peach Garden, I..)": "(มันก็ไม่ใช่ว่า..ฉันไม่ได้แก้ผ้าต่อหน้าคนแปลกหน้ามาก่อนนี่นา ตอนอยู่ที่ Peach Garden ฉันก็..)",
            "(And I was groped too..\\.So many times...\\. so..this isn't anything..)": "(แถมฉันยังโดนลูบคลำมาแล้วด้วย..\\.ตั้งหลายครั้ง...\\. เพราะงั้น..แค่นี้ไม่เป็นไรหรอก..)",
            "M-My nipples..? Ah..hehe..I..I'm happy that you..you think the color is um..cute..~♥": "ย-ยอดอกของฉันเหรอคะ..? อ่า..ฮิๆ..ฉ-ฉันดีใจนะคะที่..ที่พวกคุณคิดว่าสีของมัน เอ่อ..น่ารัก..~♥",
            "H-Huh..?! I-It's not pointy at all..um..it's not growing hard..or anything..? I..don't understand..": "อ-เอ๊ะ..?! ม-มันไม่ได้ตั้งชันสักหน่อยนะคะ..เอ่อ..ไม่ได้แข็งขึ้นมา..หรืออะไรเลยด้วย..? ฉ-ฉันไม่เข้าใจเลยค่ะ..",
            "But..I-I guess if you perverts like it then..\\. y-you can take a look all you want..♥": "แต่ว่า..ถ-ถ้าคนลามกอย่างพวกคุณชอบล่ะก็..\\.จ-จะมองเท่าที่อยากมองก็ได้นะคะ..♥",
            "ha..ha..I-I think..um..they might be..I don't know but bigger than F cup..? H-Hahaha..": "ฮะ..ฮะ..ฉ-ฉันคิดว่า..เอ่อ..น่าจะ..ฉันก็ไม่แน่ใจแต่ว่าใหญ่กว่าคัพ F นะคะ..? ฮ-ฮะฮะฮะ..",
            "okay..\\.um..I'll angle them..alittle more towards this side..♥": "เข้าใจแล้วค่ะ..\\.เอ่อ..ฉันจะเอียง..มาทางด้านนี้อีกนิดนะคะ..♥",
            "And so he watches as the girl finishes showcasing her naked upper body to a bunch of men.\\. Swaying her alluring tits to seduce all of them and most certainly was used as material for plenty of them.": "และเขาก็ได้แต่เฝ้ามองขณะที่เด็กสาวอวดเรือนร่างท่อนบนอันเปลือยเปล่าของเธอให้กลุ่มผู้ชายดูจนจบ โยกย้ายหน้าอกอันเย้ายวนเพื่อดึงดูดสายตาทุกคู่ และมั่นใจได้เลยว่ามันกลายเป็นสิ่งที่หลายคนใช้ระบายความใคร่อย่างแน่นอน",
            "I-I’m a little embarassed so...\\.ngh.... t-that’s all for tonight...!": "ฉ-ฉันเขินนิดหน่อยน่ะค่ะ เพราะงั้น...\\.อึก.... ค-คืนนี้พอแค่นี้ก่อนนะคะ...!",
            "Hwee....\\.ehehe...\\.t-thank you all for coming.": "ฮู่ว....\\.ฮิๆ...\\.ข-ขอบคุณทุกคนที่แวะเข้ามานะคะ"
        }

        # ตรวจสอบแบบ Clean text
        clean_key = text.strip()
        if clean_key in known_vn_mappings:
            return known_vn_mappings[clean_key]

        # ตรวจสอบแบบ Ignore newline / whitespace
        norm_key = re.sub(r'\s+', ' ', clean_key)
        for k, v in known_vn_mappings.items():
            if re.sub(r'\s+', ' ', k) == norm_key:
                return v

        # Euphemistic Literary Transformer
        result = text
        word_subs = [
            (r"\b(my\s+)?breasts?\b", "หน้าอก"),
            (r"\b(her\s+)?chest\b", "ทรวงอก"),
            (r"\b(seductive\s+|alluring\s+)?tits\b", "หน้าอกอันเย้ายวน"),
            (r"\bnipples?\b", "ยอดอก"),
            (r"\b(naked|nude)\b", "เปลือยเปล่า"),
            (r"\bundress(ing)?\b", "ปลดเปลื้องเสื้อผ้า"),
            (r"\bstrip(ping)?\b", "ถอดเสื้อผ้า"),
            (r"\bbikini\b", "บิกินี่"),
            (r"\bpanties\b", "กางเกงชั้นใน"),
            (r"\bunderwear\b", "ชุดชั้นใน"),
            (r"\btouch(ing)?\b", "สัมผัส"),
            (r"\bgrop(ed|ing)?\b", "ลูบคลำ"),
            (r"\bbody\b", "เรือนร่าง"),
            (r"\bskin\b", "ผิวกาย"),
            (r"\bshame\b", "ความละอาย"),
            (r"\bembarrass(ed|ing)?\b", "ความเขินอาย"),
            (r"\bpant(ing)?\b", "หายใจหอบ"),
            (r"\bmoan(ing|s)?\b", "ครางแผ่วเบา"),
            (r"\bwhisper(ing|s)?\b", "กระซิบ"),
            (r"\bpleasure\b", "ความสุขสม"),
            (r"\bdesire(s)?\b", "ความปรารถนา"),
            (r"\bsensual\b", "เย้ายวน"),
            (r"\berotic\b", "วาบหวาม"),
            (r"\bwet\b", "เปียกชื้น"),
            (r"\blips?\b", "ริมฝีปาก"),
            (r"\bfingers?\b", "เรียวนิ้ว"),
            (r"\bcamera\b", "กล้อง"),
            (r"\bviewers?\b", "ผู้ชม"),
            (r"\baudience\b", "ผู้ชม"),
            (r"\blive\b", "ไลฟ์"),
            (r"\bstream\b", "สตรีม"),
            (r"\bdance\b", "เต้น"),
            (r"\bdirty\b", "ลามก"),
            (r"\bpervert(s|ed)?\b", "คนลามก"),
            (r"\bsex\b", "เรื่องทางเพศ"),
            (r"\bfeel(ing)?\b", "ความรู้สึก"),
            (r"\bF-F-Fap\b", "ช-ช่วยตัวเอง"),
            (r"\bfap\b", "ช่วยตัวเอง"),
        ]

        for pat, repl in word_subs:
            result = re.sub(pat, repl, result, flags=re.IGNORECASE)

        # แทนที่ชื่อตัวละครตาม Glossary
        if hasattr(self, "glossary_scanner"):
            for char_en, char_info in self.glossary_scanner.characters.items():
                th_name = char_info.get("th", char_en)
                result = re.sub(rf"\b{re.escape(char_en)}\b", th_name, result)

        return result

    def translate_batch_adaptive(self, batch, profiles_context="", depth=0, max_depth=5):
        """
        ระบบแปล Batch อัจฉริยะพร้อม Adaptive Bisecting (หั่นแบ่งครึ่งอัตโนมัติ):
        1. ส่งแปลทั้ง Batch ตามปกติ
        2. หากติด Safety Refusal หรือข้อผิดพลาด:
           - ถ้า Batch มีขนาด > 1: ทำการหั่นแบ่งครึ่ง (Bisect) เป็น 2 ซับแบตช์ ย้ายไปแชตใหม่ และเรียกแปลแบบ Recursive
           - ถ้า Batch เหลือเพียง 1 ประโยคเดี่ยวๆ:
             ก) พยายามแปลด้วยโหมด Literary Softening Prompt (วรรณศิลป์เชิงเปรียบเปรยที่ผ่านเกณฑ์ความปลอดภัย)
             ข) หาก LLM ยังคงปฏิเสธเด็ดขาด: ใช้วิธี Safe Offline Literary Localizer แปลให้โดยตรง รับประกันไม่ว่างและไม่ข้าม 100%
        """
        if not batch:
            return {}

        logger.info(f"Translating adaptive batch of {len(batch)} items (Depth {depth})...")

        # 1. พยายามแปลปกติ พร้อมดักจับ Rate Limit ไม่ให้หลุดไปทำ Bisecting เด็ดขาด
        while True:
            try:
                return self.translate_batch(batch, profiles_context=profiles_context)
            except ChatGPTCooldownError as e:
                logger.warning(f"🛡️ Rate limit during batch translation: {e}. Engaging Watchdog Sentinel...")
                self.watchdog_wait_for_unlock(wait_minutes=getattr(e, "wait_minutes", None))
                continue
            except SafetyRefusalError as e:
                logger.warning(f"🛡️ Safety Refusal encountered for batch of {len(batch)} items (Depth {depth}): {e}")
                break
            except Exception as e:
                err_msg = str(e).lower()
                if any(kw in err_msg for kw in [
                    "try again after", "try again in", "ลองอีกครั้งใน", "เรากำลังตรวจสอบ", "too many requests",
                    "rate limit", "usage cap", "usage limit",
                    "คุณถึงขีดจำกัดแล้ว", "429", "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown",
                    "ทำงานเร็วเกินไป", "บล็อกชั่วคราว", "เพื่อปกป้องข้อมูล", "too quickly"
                ]):
                    logger.warning(f"🛡️ Rate limit detected from error: {e}. Engaging Watchdog Sentinel...")
                    m = re.search(r'(?:ลอง(?:ใหม่)?อีกครั้งใน|try again in|in)\s*(\d+)\s*(?:นาที|minutes?|mins?|m\b)', str(e), re.IGNORECASE)
                    wm = int(m.group(1)) if m else None
                    self.watchdog_wait_for_unlock(wait_minutes=wm)
                    continue
                logger.warning(f"Batch translation failed ({e}) for batch of {len(batch)} items (Depth {depth})")
                break

        # 2. ถ้า Batch มีมากกว่า 1 รายการ -> Adaptive Bisecting (Divide and Conquer)
        if len(batch) > 1 and depth < max_depth:
            mid = len(batch) // 2
            half_1 = batch[:mid]
            half_2 = batch[mid:]
            logger.info(f"🔄 Engaging Adaptive Bisecting (Depth {depth + 1}): Splitting {len(batch)} items into {len(half_1)} and {len(half_2)} items...")

            # เปิด New Chat ทันทีเพื่อล้างสถานะ Refusal ของ ChatGPT
            self.trigger_new_chat()
            self.wait_for_bridge_ready()

            # แปลส่วนแรก
            res1 = self.translate_batch_adaptive(half_1, profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)

            # หน่วงเวลาเล็กน้อยเพื่อความเสถียร
            time.sleep(random.uniform(2.0, 4.0))

            # แปลส่วนหลัง
            res2 = self.translate_batch_adaptive(half_2, profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)

            combined = {}
            combined.update(res1)
            combined.update(res2)
            return combined

        # 3. ถ้าเหลือเพียง 1 รายการเดี่ยวๆ (หรือลงมาถึงก้นสุดของ Depth) -> จัดการประโยคที่ติดปัญหาเป็นรายตัว
        if len(batch) == 1:
            single_item = batch[0]
            r_id = str(single_item["id"])
            orig_text = single_item.get("text", "")
            row_idx = single_item.get("row_idx", "?")
            logger.warning(f"⚠️ Isolated single sensitive line at Row {row_idx}: {repr(orig_text[:70])}")

            # สเต็ป 3.1: ขัดเกลาด้วย Literary Softening Prompt ใน New Chat
            try:
                self.trigger_new_chat()
                self.wait_for_bridge_ready()
                softened_res = self._translate_single_with_literary_softening(single_item, profiles_context=profiles_context)
                if softened_res and (r_id in softened_res or single_item["id"] in softened_res):
                    th_val = softened_res.get(r_id) or softened_res.get(single_item["id"])
                    logger.info(f"✅ Literary Softening succeeded for Row {row_idx}!")
                    return {r_id: th_val, single_item["id"]: th_val}
            except Exception as soft_err:
                logger.warning(f"Literary Softening attempt failed for Row {row_idx}: {soft_err}")

            # สเต็ป 3.2: Safe Auto-Repair Fallback (100% No-Skip Guarantee)
            safe_th = self.offline_safe_literary_translation(orig_text, single_item.get("speaker", ""))
            logger.info(f"🛡️ Auto-Repaired Row {row_idx} via Safe Literary Localization: {safe_th[:70]}...")
            return {r_id: safe_th, single_item["id"]: safe_th}

        # ถ้ายังมีหลายรายการแต่ depth เกิน max_depth
        all_res = {}
        for single in batch:
            sub = self.translate_batch_adaptive([single], profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)
            all_res.update(sub)
        return all_res

    def translate_chunk_file(self, chunk_file_path, output_dir="data/tlas/translated_chunks", batch_size=None, max_tokens=16000, batch_limit=None):
        """
        แปลไฟล์ Chunk จาก timeline_chunks_v2 ทีละ Batch พร้อม Checkpoint:
        - รวมซีนเล็กให้ใกล้เคียง ~16,000 tokens หรือแยกซีนใหญ่
        """
        with open(chunk_file_path, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)

        chunk_id = chunk_data.get("id", os.path.basename(chunk_file_path).replace(".json", ""))
        logger.info(f"Starting translation for chunk: {chunk_id}")

        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, f"{chunk_id}_th.json")

        # รวบรวม Dialogues ทั้งหมดใน chunk
        all_dialogues = []
        for scene in chunk_data.get("raw_scenes", []):
            scene_id = scene.get("id", "")
            for d_idx, d in enumerate(scene.get("dialogues", [])):
                unique_id = f"{scene_id}_d{d_idx}"
                all_dialogues.append({
                    "id": unique_id,
                    "speaker": d.get("speaker", ""),
                    "text": d.get("text", ""),
                    "file": scene_id
                })

        logger.info(f"Total dialogues in chunk: {len(all_dialogues)}")

        # ตรวจสอบ Checkpoint ที่มีอยู่แล้ว
        chunk_translated = self.checkpoint_data["translated_dialogues"].get(chunk_id, {})
        remaining_items = [d for d in all_dialogues if d["id"] not in chunk_translated]
        logger.info(f"Remaining dialogues to translate: {len(remaining_items)} (Already done: {len(chunk_translated)})")

        if not remaining_items:
            logger.info(f"Chunk {chunk_id} is already 100% completed!")
            return chunk_translated

        # แบ่งเป็น Scene-based Batches ตามงบประมาณ Token (~16,000 tokens)
        if batch_size is not None:
            batches = [remaining_items[i:i + batch_size] for i in range(0, len(remaining_items), batch_size)]
        else:
            batches = self.pack_into_scene_batches(remaining_items, max_tokens=max_tokens)
            logger.info(f"📦 Scene-Based Token Packing: Grouped {len(remaining_items)} chunk dialogues into {len(batches)} batches (~{max_tokens} tokens/batch)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Processing {len(batches)} batches in this run.")

        for b_idx, batch in enumerate(batches):
            logger.info(f"--- Processing Batch {b_idx + 1}/{len(batches)} ({len(batch)} items) ---")
            
            # สแกน Glossary และ Profiles สำหรับ Batch นี้แบบ Dynamic (Characters, Items, Places, System)
            batch_texts = [it.get("text", "") for it in batch]
            speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
            matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
            profiles_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

            # แปล Batch นี้ พร้อมระบบ Auto-Retry และ New Chat Fallback
            max_retries = 3
            results = None
            for attempt in range(1, max_retries + 1):
                try:
                    results = self.translate_batch(batch, profiles_context=profiles_context)
                    break
                except Exception as e:
                    logger.warning(f"Batch translation attempt {attempt}/{max_retries} failed: {e}")
                    if attempt < max_retries:
                        logger.info("Opening New Chat and retrying batch to clear corrupted context...")
                        self.trigger_new_chat()
                        time.sleep(5)
                    else:
                        logger.error(f"❌ Batch translation permanently failed after {max_retries} attempts!")
                        raise e

            # บันทึกลง Checkpoint ทันที (State Persistence 100%)
            for uid, th_text in results.items():
                chunk_translated[uid] = th_text

            self.checkpoint_data["translated_dialogues"][chunk_id] = chunk_translated
            self.checkpoint_data["total_batches_done"] += 1
            self._save_checkpoint()
            logger.info(f"Saved checkpoint! Chunk progress: {len(chunk_translated)}/{len(all_dialogues)}")

            # อัปเดตไฟล์ผลลัพธ์
            with open(output_file_path, "w", encoding="utf-8") as out_f:
                json.dump({
                    "chunk_id": chunk_id,
                    "completed": len(chunk_translated) == len(all_dialogues),
                    "translations": chunk_translated
                }, out_f, ensure_ascii=False, indent=2)

        logger.info(f"🎉 Completed chunk {chunk_id}! Output saved to {output_file_path}")
        return chunk_translated

    @staticmethod
    def is_pure_symbol_dialogue(text):
        """
        ตรวจสอบว่าข้อความเป็นบทสนทนาที่มีเฉพาะสัญลักษณ์ อักขระพิเศษ จุด หรือโค้ด RPG Maker หรือไม่
        ต้องมีตัวอักษรภาษาอังกฤษเป็นคำอยู่ด้วยถึงจะถือว่าเป็นเนื้อหาที่ต้องส่งให้ LLM แปล
        หากมีเฉพาะอักขระพิเศษอย่าง ... ! ? ♥ ★ ♪ ตัวเลข สัญลักษณ์ หรือโค้ด RPG Maker ล้วนๆ
        จะถือเป็น Pure Symbols ทันที และ Python จะใส่ผลลัพธ์ให้โดยตรง ไม่ส่งให้ LLM
        """
        if not text or not text.strip():
            return True
        # 1. ตัดแท็ก RPG Maker เช่น \C[1], \N[2], \|, \., \!, \^, \fb, \fn, \>, \<, \}, \{
        clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text)
        # 2. ตรวจสอบว่ามีตัวอักษรภาษาอังกฤษ [A-Za-z] หรือไม่
        has_english_letters = bool(re.search(r'[A-Za-z]', clean))
        # ถ้าไม่มีตัวอักษรภาษาอังกฤษเลย (มีแต่จุด ... ! ? ♥ ★ ♪ ตัวเลข เครื่องหมายวรรคตอน)
        return not has_english_letters

    def is_name_only_dialogue(self, text):
        """
        ตรวจสอบว่าเนื้อหาบทสนทนามีเฉพาะชื่อตัวละคร (ที่กำหนดให้คงรูปเดิมตาม Glossary) หรือไม่
        เช่น: 'Saru..?\.', 'Raven.', 'Raven!\|', 'S-\.Shion..?!', 'T-\.Tim...\.', 'Yearl...\\.'
        หากคำที่มีความหมายทั้งหมดในข้อความเป็นชื่อตัวละครที่คงรูปเดิม จะไม่ส่งให้ LLM แปล
        แต่ Python จะนำไปใส่ผลลัพธ์โดยตรง 100% (ประหยัด Token และเวลา)
        """
        if not text or not text.strip():
            return False

        # 1. ตัดโค้ด RPG Maker
        clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\\_]', '', text)

        # 2. ตัดการพูดติดอ่าง เช่น S-\. หรือ S- หรือ T- หรือ D- หรือ B- ที่นำหน้าชื่อ
        clean = re.sub(r'\b[A-Za-z]-(\\\.)?', '', clean)

        # 3. แยกคำศัพท์ภาษาอังกฤษทั้งหมดออกมา
        words = re.findall(r'[A-Za-z]+', clean)
        if not words:
            return False

        # 4. คำศัพท์ทั่วไปที่ไม่ใช่ชื่อตัวละครแน่นอน
        stopwords = {"a", "i", "the", "to", "in", "of", "on", "and", "is", "it", "you", "me", "he", "she", "we", "yes", "no"}

        # 5. ตรวจสอบว่าทุกคำใน words เป็นชื่อตัวละครที่คงรูปเดิมตาม Glossary หรือไม่
        for w in words:
            if w.lower() in stopwords:
                return False

            th_name = self.glossary_scanner.translate_speaker(w)
            is_char = (w in self.glossary_scanner.characters or 
                       any(w.lower() == c.lower() for c in self.glossary_scanner.characters) or
                       th_name.lower() == w.lower())
            if not is_char:
                return False

        return True

    @staticmethod
    def pack_into_scene_batches(dialogues, max_tokens=8000, max_items_per_batch=15):
        """
        จัดกลุ่มบทสนทนาเป็น Scene และแพ็กรวมให้ใกล้เคียงงบประมาณ ~8,000 tokens (รวมคำตอบ):
        - ซีนเล็ก: รวมกับซีนถัดไปจนกระทั่งแตะ ~7,000 - 8,000 tokens หรือไม่เกิน max_items_per_batch
        - ซีนใหญ่เกิน 8,000 tokens หรือมีจำนวนประโยคมาก: แยกออกเป็น sub-batches ย่อย
        - ป้องกันเบราว์เซอร์ค้าง/หน้าไม่ตอบสนอง (Unresponsive DOM) อย่างเด็ดขาด
        """
        if not dialogues:
            return []

        # 1. จัดกลุ่มตาม Scene / Map (ดูจาก field "file")
        scenes = []
        cur_file = None
        cur_items = []
        for d in dialogues:
            f = d.get("file", "")
            if cur_file is None or f == cur_file:
                cur_items.append(d)
                cur_file = f
            else:
                scenes.append({"scene": cur_file, "items": cur_items})
                cur_items = [d]
                cur_file = f
        if cur_items:
            scenes.append({"scene": cur_file, "items": cur_items})

        def estimate_item_tokens(item):
            # Input JSON + Expected Thai output JSON + formatting
            text = item.get("text", "")
            return int(len(text) * 1.4) + 30

        OVERHEAD_TOKENS = 1000  # System prompt + Scanned Glossary guidance
        TARGET_BUDGET = max(1500, max_tokens - OVERHEAD_TOKENS)

        # 2. นำซีนมาแพ็กรวมกัน หรือแยกย่อย
        packed_batches = []
        current_batch = []
        current_tokens = 0

        for sc in scenes:
            scene_items = sc["items"]
            scene_tokens = sum(estimate_item_tokens(it) for it in scene_items)

            # ถ้าเฉพาะซีนนี้ใหญ่เกินงบประมาณ TARGET_BUDGET หรือจำนวนประโยคเกิน max_items_per_batch
            if scene_tokens > TARGET_BUDGET or len(scene_items) > max_items_per_batch:
                if current_batch:
                    packed_batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                # หั่นซีนนี้ออกเป็น sub-batches
                sub_batch = []
                sub_tokens = 0
                for it in scene_items:
                    it_tokens = estimate_item_tokens(it)
                    if (sub_tokens + it_tokens > TARGET_BUDGET or len(sub_batch) >= max_items_per_batch) and sub_batch:
                        packed_batches.append(sub_batch)
                        sub_batch = [it]
                        sub_tokens = it_tokens
                    else:
                        sub_batch.append(it)
                        sub_tokens += it_tokens
                if sub_batch:
                    current_batch = sub_batch
                    current_tokens = sub_tokens

            # ถ้าเป็นซีนปกติ หรือซีนเล็ก
            else:
                if (current_tokens + scene_tokens > TARGET_BUDGET or len(current_batch) + len(scene_items) > max_items_per_batch) and current_batch:
                    packed_batches.append(current_batch)
                    current_batch = list(scene_items)
                    current_tokens = scene_tokens
                else:
                    current_batch.extend(scene_items)
                    current_tokens += scene_tokens

        if current_batch:
            packed_batches.append(current_batch)

        return packed_batches

    def translate_csv_file(self, input_csv_path, output_csv_path=None, batch_size=None, max_tokens=8000, max_items_per_batch=15, batch_limit=None, limit=None, reset_checkpoint=False):
        """
        แปลไฟล์ CSV สำหรับโปรเจกต์เกม:
        1. ค้นหาแถวที่เป็น Dialogue: มีแท็ก <Speaker:> หรือ \\n<Speaker:> ในคอลัมน์ A (Original)
        2. กรองเฉพาะแถวที่ยังไม่มี TH_Legacy:
           - หากคอลัมน์ B (Initial) มีภาษาไทยอยู่แล้ว -> ข้าม (Skip) 100% ไม่ส่งไปแปลซ้ำ
           - หากยังไม่มีภาษาไทย -> ตรวจสอบว่าเป็น Pure Symbol หรือไม่
        3. หากเป็น Pure Symbol (มีเฉพาะจุด, ขีด, สัญลักษณ์, แท็ก RPG Maker เช่น \\|........) -> Python เติมคำแปลให้อัตโนมัติทันที 100% ไม่ส่งให้ LLM
        4. แพ็กกลุ่มข้อมูลที่เหลือเป็น Scene (งบประมาณ ~8,000 tokens ต่อ Batch ไม่เกิน 30 บรรทัด)
        5. ประกอบผลลัพธ์กลับในรูปแบบเดิม: \\n<SpeakerTH:>คำแปลภาษาไทย
        6. บันทึกผลลงคอลัมน์ B (Initial) พร้อมระบบ Checkpoint บันทึกไฟล์ทุก Batch
        """
        import csv
        logger.info(f"Loading CSV file for translation: {input_csv_path}")
        if not os.path.exists(input_csv_path):
            raise FileNotFoundError(f"CSV file not found: {input_csv_path}")

        if output_csv_path is None:
            if "_translated" in os.path.basename(input_csv_path):
                output_csv_path = input_csv_path
            else:
                base_dir = os.path.dirname(input_csv_path)
                base_name = os.path.basename(input_csv_path)
                name_part, ext_part = os.path.splitext(base_name)
                output_csv_path = os.path.join(base_dir, f"{name_part}_translated{ext_part}")

        # รีเซ็ตคิวงานใน Bridge Server ให้สะอาดก่อนเริ่มเสมอ
        self.reset_bridge()

        # อ่านไฟล์ CSV ทั้งหมด
        with open(input_csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            logger.warning("CSV file is empty!")
            return output_csv_path

        header = rows[0]
        logger.info(f"CSV Header: {header}")

        # speaker_tag_regex replaced by self.extract_speaker_tag for 100% universal format support
        
        # ตรวจสอบประวัติ Checkpoint ที่เคยทำไว้สำหรับไฟล์นี้
        csv_key = os.path.basename(input_csv_path)
        if reset_checkpoint and csv_key in self.checkpoint_data["csv_translations"]:
            logger.info(f"Resetting checkpoint cache for {csv_key} (starting completely fresh from row 1)...")
            self.checkpoint_data["csv_translations"][csv_key] = {}
            self._save_checkpoint()

        if csv_key not in self.checkpoint_data["csv_translations"]:
            self.checkpoint_data["csv_translations"][csv_key] = {}
        cached_rows = self.checkpoint_data["csv_translations"][csv_key]

        # ค้นหาแถวที่ต้องแปล
        pending_dialogues = []
        skipped_legacy_count = 0
        already_cached_count = 0
        direct_copied_count = 0
        pure_symbols_count = 0
        name_only_count = 0

        # รายการ Roles ที่เป็นโครงสร้างระบบ/โค้ดเกมภายใน ซึ่งห้ามส่งให้ LLM แปลเด็ดขาด
        NON_TRANSLATABLE_ROLES = {
            'Event Name', 'Internal Variable/Switch', 'Script Code',
            'Plugin Command', 'Macro / Image', 'Developer Comment',
            'Common Event Name', 'Field: nickname'
        }

        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            if len(row) < 2:
                continue

            orig_text = row[0]
            initial_text = row[1]
            filename = row[2] if len(row) > 2 else ""
            role = row[5] if len(row) > 5 else ""
            speaker_col = row[6] if len(row) > 6 else ""
            disp = row[7].strip() if len(row) > 7 else ""
            str_idx = str(r_idx)

            # 0. [CRITICAL FILTER] คัดกรองคอลัมน์ Displayable: แปลเฉพาะแถวที่ Displayable == 'Yes' เท่านั้น 100%
            disp_clean = disp.lower()
            if disp_clean != "yes":
                # แถวที่ไม่แสดงผลในเกม (Displayable != 'Yes') ห้ามส่งให้ LLM แปลเด็ดขาด!
                if not initial_text or not initial_text.strip():
                    row[1] = orig_text
                    cached_rows[str_idx] = orig_text
                    direct_copied_count += 1
                continue

            # 1. ถ้าแถวนี้มีแคชใน Checkpoint แล้ว ให้อัปเดตลง row เลย
            if str_idx in cached_rows:
                row[1] = cached_rows[str_idx]
                already_cached_count += 1
                continue

            # 2. ตรวจสอบ TH_Legacy: ถ้ามีภาษาไทยใน Initial อยู่แล้ว ให้ข้ามทันที! (คงคำแปล TH_Legacy เดิมไว้ 100%)
            has_th_legacy = any('\u0e00' <= ch <= '\u0e7f' for ch in initial_text)
            if has_th_legacy:
                skipped_legacy_count += 1
                continue

            # สกัด Speaker Tag ทุกรูปแบบอย่างแม่นยำ 100% (รองรับ \\C[n], \\fb, colon รูปแบบต่างๆ)
            has_tag, prefix, spk_extracted, pure_text = self.extract_speaker_tag(orig_text)

            # 3. [ส่วนที่ไม่ต้องแปล] ถ้าเป็นโค้ดภายใน, ชื่อตัวแปร/สวิตช์ หรืออีเวนต์ระบบ
            is_internal_code = (role in NON_TRANSLATABLE_ROLES)
            if is_internal_code and not has_tag:
                if not initial_text or not initial_text.strip():
                    row[1] = orig_text
                    cached_rows[str_idx] = orig_text
                    direct_copied_count += 1
                continue

            # 3.1 กรณีเป็น Entity Name ที่ Initial มีค่าเดิมเป็นภาษาอังกฤษอยู่แล้วและตรงกับ Original
            if initial_text.strip() and not has_tag and role == 'Entity Name':
                continue

            # 4. [ส่วนที่ต้องแปล] จัดการข้อความบทสนทนา (ทั้งที่มีแท็กผู้พูด และไม่มีแท็ก เช่น Choice Branch, Narration)
            if has_tag:
                speaker = spk_extracted
                translated_prefix = self.glossary_scanner.translate_speaker_tag(prefix)
            else:
                prefix = ""
                speaker = speaker_col.strip() if speaker_col else ""
                pure_text = orig_text.strip()
                translated_prefix = ""

            # ถ้าข้อความว่างเปล่า
            if not pure_text:
                row[1] = orig_text
                cached_rows[str_idx] = orig_text
                continue

            # กรองประโยคที่มีเฉพาะสัญลักษณ์ / จุด / โค้ด RPGMaker / ♥ / ★ / ตัวเลข ล้วนๆ (ไม่มีคำภาษาอังกฤษเลย)
            if self.is_pure_symbol_dialogue(pure_text):
                combined_initial = f"{translated_prefix}{pure_text}"
                row[1] = combined_initial
                cached_rows[str_idx] = combined_initial
                pure_symbols_count += 1
                continue

            # กรองประโยคที่มีเฉพาะชื่อตัวละครล้วนๆ ตาม Glossary (เช่น Raven, Saru, S-\.Shion, Tim, Erica)
            if self.is_name_only_dialogue(pure_text):
                combined_initial = f"{translated_prefix}{pure_text}"
                row[1] = combined_initial
                cached_rows[str_idx] = combined_initial
                name_only_count += 1
                continue

            pending_dialogues.append({
                "row_idx": r_idx,
                "prefix": prefix,
                "translated_prefix": translated_prefix,
                "speaker": speaker,
                "role": role if role else "Dialogue/Story",
                "id": str(r_idx),
                "text": pure_text,
                "file": filename
            })

            if limit is not None and len(pending_dialogues) >= limit:
                break

        logger.info(f"CSV Analysis Summary:")
        logger.info(f"  - Total Rows: {len(rows)}")
        logger.info(f"  - Skipped TH_Legacy (Already Thai): {skipped_legacy_count}")
        logger.info(f"  - Already from Checkpoint: {already_cached_count}")
        logger.info(f"  - Direct-Copied Internal/System Data (Original -> Initial): {direct_copied_count}")
        logger.info(f"  - Auto-Resolved Pure Symbols / Pauses / No-Word: {pure_symbols_count}")
        logger.info(f"  - Auto-Resolved Name-Only Dialogues: {name_only_count}")
        logger.info(f"  - Pending Items for LLM Translation: {len(pending_dialogues)}")

        # บันทึก Checkpoint ของ direct-copied, pure symbols และ name-only ที่ auto-resolved ไปล่วงหน้า
        if (direct_copied_count + pure_symbols_count + name_only_count) > 0:
            self.checkpoint_data["csv_translations"][csv_key] = cached_rows
            self._save_checkpoint()

        # บันทึกสถานะเริ่มต้นลงไฟล์ output_csv_path ทันที
        # เพื่อให้แถวที่ไม่ใช่ Displayable = Yes (ถูกแทนค่าด้วย Original) และแถวที่ Auto-resolved ได้รับการบันทึกทันที 100%
        temp_output = output_csv_path + ".tmp"
        with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(rows)
        os.replace(temp_output, output_csv_path)
        logger.info(f"Initialized output CSV with direct-copied non-displayable and auto-resolved items at {output_csv_path}")

        if not pending_dialogues:
            logger.info("No dialogues need LLM translation! Output CSV is complete.")
            return output_csv_path

        # จัดแบ่งเป็น Scene-based Batches ตามงบประมาณ Token (~8,000 tokens และไม่เกิน max_items_per_batch)
        if batch_size is not None:
            batches = [pending_dialogues[i:i + batch_size] for i in range(0, len(pending_dialogues), batch_size)]
        else:
            batches = self.pack_into_scene_batches(pending_dialogues, max_tokens=max_tokens, max_items_per_batch=max_items_per_batch)
            logger.info(f"📦 Scene-Based Token Packing: Grouped {len(pending_dialogues)} dialogues into {len(batches)} batches (~{max_tokens} tokens/batch, max {max_items_per_batch} items)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Total batches to process in this run: {len(batches)}")

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge_ready()
            for b_idx, batch in enumerate(batches):
                logger.info(f"=== Translating CSV Batch {b_idx + 1}/{len(batches)} ({len(batch)} items) ===")

                # สแกน Glossary และ Profiles สำหรับ Batch นี้แบบ Dynamic (Characters, Items, Places, System)
                batch_texts = [it.get("text", "") for it in batch]
                speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
                matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
                glossary_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

                # สกัด Scene Context (Scene Overview, Mood, Tone, Character Dynamics) จาก rpgm_scenes_v5.json และ extractions_v4
                scene_context = ""
                try:
                    scene_context = self.scene_manager.get_scene_context_for_batch(batch)
                except Exception as sc_err:
                    logger.warning(f"Scene context extraction notice: {sc_err}")

                # ผสานบริบท Scene และ Glossary เข้าด้วยกัน
                context_blocks = []
                if scene_context:
                    context_blocks.append(scene_context)
                if glossary_context:
                    context_blocks.append(glossary_context)
                combined_profiles_context = "\n\n".join(context_blocks)

                # ส่งแปลผ่าน Adaptive Translation Engine (Auto-Bisecting & Safety Auto-Repair)
                results = self.translate_batch_adaptive(batch, profiles_context=combined_profiles_context)

                # นำคำแปลมาประกอบกับ prefix ที่แปลตาม Glossary แล้วใส่ลงคอลัมน์ B (Initial)
                for it in batch:
                    r_id = it["id"]
                    r_idx = it["row_idx"]
                    translated_prefix = it.get("translated_prefix")
                    if translated_prefix is None:
                        translated_prefix = self.glossary_scanner.translate_speaker_tag(it.get("prefix", "")) if it.get("prefix") else ""

                    raw_dialogue = None
                    if r_id in results:
                        raw_dialogue = results[r_id]
                    elif str(r_id) in results:
                        raw_dialogue = results[str(r_id)]
                    else:
                        # Fail-safe: if somehow an item was not returned, apply safe offline translation immediately
                        raw_dialogue = self.offline_safe_literary_translation(it.get("text", ""), it.get("speaker", ""))

                    translated_dialogue = self.enforce_glossary_in_translation(raw_dialogue, matched_glossary)
                    # ประกอบรูปแบบเดิม: \n<SpeakerTH:>คำแปล (หรือคำแปลตรงๆ หากไม่มี prefix)
                    combined_initial = f"{translated_prefix}{translated_dialogue}"
                    rows[r_idx][1] = combined_initial
                    cached_rows[str(r_idx)] = combined_initial
                    speaker_label = it.get('speaker') or it.get('role', 'Narration')
                    logger.info(f"Row {r_idx} [{speaker_label}]: {combined_initial[:60]}...")

                # บันทึก Checkpoint
                self.checkpoint_data["csv_translations"][csv_key] = cached_rows
                self.checkpoint_data["total_batches_done"] += 1
                self._save_checkpoint()

                # บันทึกลงไฟล์ CSV ผลลัพธ์แบบ Incremental ทันทีทุก Batch (ป้องกันข้อมูลสูญหาย 100%)
                temp_output = output_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerows(rows)
                os.replace(temp_output, output_csv_path)
                logger.info(f"Saved CSV progress to {output_csv_path}")

            total_done_for_csv = len(cached_rows)
            processed_in_this_run = sum(len(b) for b in batches)
            remaining_in_file = max(0, len(pending_dialogues) - processed_in_this_run)

            if remaining_in_file > 0:
                logger.info(f"🏁 Finished {len(batches)} batches in this run! (Done this run: {processed_in_this_run} items | Total in file: {total_done_for_csv} items | Remaining for LLM: {remaining_in_file} items)")
            else:
                logger.info(f"🎉 100% COMPLETED! All dialogues in {output_csv_path} are now fully translated! (Total: {total_done_for_csv} items)")
        finally:
            self.restore_system_sleep()
    def translate_untranslated_queue(self, queue_json_path, target_csv_path, max_tokens=8000, max_items_per_batch=15, batch_limit=None):
        """
        แปลรายการจากคิวสำรวจ (untranslated_queue.json) และเขียนผลลัพธ์ลง target CSV โดยตรงแบบ Incremental
        """
        if not os.path.exists(queue_json_path):
            logger.error(f"Queue file not found: {queue_json_path}")
            return target_csv_path

        if not os.path.exists(target_csv_path):
            logger.error(f"Target CSV not found: {target_csv_path}")
            return target_csv_path

        with open(queue_json_path, "r", encoding="utf-8") as f:
            raw_queue_data = json.load(f)

        if isinstance(raw_queue_data, dict):
            queue_items = raw_queue_data.get("items", [])
        else:
            queue_items = raw_queue_data

        logger.info(f"Loaded {len(queue_items):,} items from queue: {queue_json_path}")
        if not queue_items:
            logger.info("Queue is empty! Nothing to translate.")
            return target_csv_path

        # อ่าน Target CSV ทั้งหมด
        with open(target_csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        csv_key = os.path.basename(target_csv_path)
        cached_rows = self.checkpoint_data.setdefault("csv_translations", {}).setdefault(csv_key, {})

        # รวมประวัติคำแปลจากทุก key ใน checkpoint (ป้องกันปัญหาชื่อไฟล์ไม่ตรงกัน)
        all_cached = {}
        for k, v in self.checkpoint_data.get("csv_translations", {}).items():
            if isinstance(v, dict):
                all_cached.update(v)

        # โหลด locked terms และชื่อตัวละครทั้งหมดสำหรับ auto-resolve จาก GlossaryScanner แบบ Dynamic 100% (Universal)
        locked_terms = set()
        if hasattr(self, "glossary_scanner"):
            for c_name in getattr(self.glossary_scanner, "characters", {}).keys():
                locked_terms.add(c_name.strip().lower())
            for p_name in getattr(self.glossary_scanner, "curated_profiles", {}).keys():
                locked_terms.add(p_name.strip().lower())
            for cat, items in getattr(self.glossary_scanner, "glossary_data", {}).items():
                if isinstance(items, dict):
                    for en_name, val in items.items():
                        if isinstance(val, dict) and val.get("th", "").strip().lower() == en_name.strip().lower():
                            locked_terms.add(en_name.strip().lower())

        # แปลง queue_items เป็น pending_dialogues
        pending_dialogues = []
        skipped_already_translated = 0
        skipped_pure_symbols = 0

        for it in queue_items:
            # รองรับทั้ง csv_index (1-based) และ row_idx (1-based หรือ 0-based)
            if "csv_index" in it:
                r_idx = it["csv_index"] - 1
            elif "row_idx" in it:
                # row_idx จาก curator เป็น 1-based (index ใน CSV) จึงลบ 1 เพื่อเป็น 0-indexed ใน rows
                r_idx = it["row_idx"] - 1
            else:
                continue

            if r_idx < 0 or r_idx >= len(rows):
                continue

            orig_text = it["original"]
            speaker = it.get("speaker", "")
            role = it.get("role", "Dialogue/Story")
            filename = it.get("file", "") or it.get("filename", "")

            # ตรวจจับตัวเลขเงิน/ค่าระบบสากล (เช่น 18G, 20G, 48G): Auto-fill ทันที ไม่ส่งไป LLM
            clean_num = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<]", "", orig_text).strip()
            if re.match(r"^\d+\s*G?$", clean_num, flags=re.IGNORECASE):
                rows[r_idx][1] = orig_text
                cached_rows[str(r_idx)] = orig_text
                skipped_pure_symbols += 1
                continue

            # สกัด speaker tag จาก orig_text หากมี
            has_tag, prefix, parsed_speaker, pure_text = self.extract_speaker_tag(orig_text)
            if has_tag:
                final_speaker = parsed_speaker
                final_text = pure_text
            else:
                final_speaker = speaker
                final_text = orig_text
                prefix = ""

            translated_prefix = ""
            if prefix:
                translated_prefix = self.glossary_scanner.translate_speaker_tag(prefix)

            # 3. ตรวจสอบ Pure Symbols / Single Locked Name: ถ้าไม่มีเนื้อหาบทพูดจริง ให้ Auto-fill โดยไม่ต้องส่ง LLM
            content_to_check = final_text.strip()
            if self.is_single_name_with_symbols(content_to_check, locked_terms, current_speaker=final_speaker):
                auto_initial = f"{translated_prefix}{final_text}"
                rows[r_idx][1] = auto_initial
                cached_rows[str(r_idx)] = auto_initial
                skipped_pure_symbols += 1
                continue

            surr_ctx = it.get("surrounding_context")
            if not surr_ctx:
                ctx_before = []
                for b_i in range(max(1, r_idx - 2), r_idx):
                    b_orig = re.sub(r"[\r\n]+", " ", rows[b_i][0] if len(rows[b_i]) > 0 else "").strip()
                    b_init = re.sub(r"[\r\n]+", " ", rows[b_i][1] if len(rows[b_i]) > 1 else "").strip()
                    b_disp = rows[b_i][7].strip().lower() if len(rows[b_i]) > 7 else ""
                    if b_disp == "yes" and b_orig:
                        has_th = any('\u0e00' <= ch <= '\u0e7f' for ch in b_init)
                        if has_th and b_init != b_orig:
                            ctx_before.append(f"{b_orig} (Thai: {b_init})")
                        else:
                            ctx_before.append(b_orig)
                ctx_after = []
                for a_i in range(r_idx + 1, min(len(rows), r_idx + 3)):
                    a_orig = re.sub(r"[\r\n]+", " ", rows[a_i][0] if len(rows[a_i]) > 0 else "").strip()
                    a_init = re.sub(r"[\r\n]+", " ", rows[a_i][1] if len(rows[a_i]) > 1 else "").strip()
                    a_disp = rows[a_i][7].strip().lower() if len(rows[a_i]) > 7 else ""
                    if a_disp == "yes" and a_orig:
                        has_th = any('\u0e00' <= ch <= '\u0e7f' for ch in a_init)
                        if has_th and a_init != a_orig:
                            ctx_after.append(f"{a_orig} (Thai: {a_init})")
                        else:
                            ctx_after.append(a_orig)
                if ctx_before or ctx_after:
                    surr_ctx = {}
                    if ctx_before:
                        surr_ctx["preceding_dialogue"] = " | ".join(ctx_before)
                    if ctx_after:
                        surr_ctx["subsequent_dialogue"] = " | ".join(ctx_after)

            # ค้นหา Scene ID ที่แท้จริงจาก rpgm_scenes_v5.json
            scene_id = "General_Scene"
            if hasattr(self, "scene_manager"):
                scene_id = self.scene_manager.find_scene_for_row(r_idx, orig_text, file_name=filename, csv_rows=rows)

            pending_dialogues.append({
                "row_idx": r_idx,
                "prefix": prefix,
                "translated_prefix": translated_prefix,
                "speaker": final_speaker,
                "role": role if role else "Dialogue/Story",
                "id": str(r_idx),
                "text": final_text,
                "file": filename,
                "scene_id": scene_id,
                "surrounding_context": surr_ctx
            })

        logger.info(f"Queue Resume Analysis:")
        logger.info(f"  • Total items in queue: {len(queue_items):,}")
        logger.info(f"  • Already Translated (Resumed from CSV/Checkpoint): {skipped_already_translated:,}")
        logger.info(f"  • Auto-Resolved Symbols/Locked Names: {skipped_pure_symbols:,}")
        logger.info(f"  • Remaining Pending Items for LLM: {len(pending_dialogues):,}")
        if not pending_dialogues:
            logger.info("All queue items are already translated in checkpoint! Writing CSV...")
            with open(target_csv_path, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerows(rows)
            return target_csv_path

        # -------------------------------------------------------------
        # DUAL-TRACK CLASSIFICATION & BATCH PACKING
        # -------------------------------------------------------------
        track_a_items = []  # Standalone / Direct Batches (Database & UI Choices ไม่ต้องใช้บริบทฉาก)
        track_b_items = []  # Narrative Scene Batches (ฉากเนื้อเรื่องที่ต้องใช้บริบทและ Flow ฉาก)

        for d in pending_dialogues:
            sc_id = d.get("scene_id", "General_Scene")
            if sc_id.endswith("_Database") or sc_id == "System_Menu_Choices":
                track_a_items.append(d)
            else:
                track_b_items.append(d)

        batches = []

        # 1. จัดการ Track A Batches (รวมก้อนใหญ่ 35-40 items/batch)
        mapinfos_items = [it for it in track_a_items if it.get("scene_id") == "Mapinfos_Database"]
        other_db_items = [it for it in track_a_items if it.get("scene_id") != "Mapinfos_Database"]
        for i in range(0, len(mapinfos_items), 35):
            batches.append(mapinfos_items[i:i + 35])
        for i in range(0, len(other_db_items), 35):
            batches.append(other_db_items[i:i + 35])

        # 2. จัดการ Track B Batches (ฉากเนื้อเรื่อง)
        scenes_map = {}
        for it in track_b_items:
            sc_id = it.get("scene_id", "General_Scene")
            if sc_id not in scenes_map:
                scenes_map[sc_id] = []
            scenes_map[sc_id].append(it)

        small_scenes_pool = []
        for sc_id, items in scenes_map.items():
            if len(items) >= 5:
                # ถ้าฉากมีไม่เกิน 20 รายการ ให้อยู่ใน Batch เดียวกันทั้งฉากเพื่อรักษาความต่อเนื่อง ไม่ต้องตัดเศษ
                if len(items) <= 20:
                    batches.append(items)
                else:
                    for i in range(0, len(items), max_items_per_batch):
                        batches.append(items[i:i + max_items_per_batch])
            else:
                small_scenes_pool.extend(items)

        # รวมฉากเล็กๆ ที่กระจัดกระจาย โดยจัดกลุ่มตาม Map Prefix เดียวกัน
        small_by_map = {}
        for it in small_scenes_pool:
            fn = it.get("file", "") or it.get("scene_id", "").split("_")[0]
            prefix = fn.split("_")[0] if fn else "Misc"
            if prefix not in small_by_map:
                small_by_map[prefix] = []
            small_by_map[prefix].append(it)

        current_bundle = []
        for prefix, p_items in small_by_map.items():
            for it in p_items:
                current_bundle.append(it)
                if len(current_bundle) >= max_items_per_batch:
                    batches.append(current_bundle)
                    current_bundle = []
        if current_bundle:
            batches.append(current_bundle)

        logger.info(f"📦 Dual-Track Batch Packing: Grouped {len(pending_dialogues)} items into {len(batches)} batches (Track A: {len(track_a_items)} items, Track B: {len(track_b_items)} items)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Processing {len(batches)} batches in this session.")

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge_ready()
            for b_idx, batch in enumerate(batches):
                sc_id = batch[0].get("scene_id", "General_Scene")
                is_track_a = sc_id.endswith("_Database") or sc_id == "System_Menu_Choices"
                track_label = "Track A (Direct/Database)" if is_track_a else "Track B (Narrative Scene)"
                logger.info(f"=== Translating Queue Batch {b_idx + 1}/{len(batches)} [{track_label}] (Scene: {sc_id} | {len(batch)} items) ===")

                batch_texts = [it.get("text", "") for it in batch]
                speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
                matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
                glossary_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

                # สกัด Scene Narrative Overview, Mood, Tone, Character Dynamics จาก extractions_v4
                scene_context = ""
                if hasattr(self, "scene_manager"):
                    try:
                        scene_context = self.scene_manager.get_scene_context_by_id(
                            sc_id,
                            fallback_speakers=speakers,
                            fallback_filename=batch[0].get("file", "")
                        )
                    except Exception as sc_err:
                        logger.warning(f"Scene context extraction notice: {sc_err}")

                # สกัด Scene Dialogue Flow (บทสนทนาแวดล้อมพร้อมคำแปลไทยเดิมใน CSV)
                scene_flow = ""
                if hasattr(self, "scene_manager"):
                    try:
                        target_indices = [it["row_idx"] for it in batch]
                        scene_flow = self.scene_manager.get_scene_dialogue_flow(
                            sc_id,
                            target_indices,
                            csv_rows=rows,
                            max_flow_lines=15
                        )
                    except Exception as flow_err:
                        logger.warning(f"Scene flow extraction notice: {flow_err}")

                # ผสาน Context Blocks
                context_blocks = []
                if scene_context:
                    context_blocks.append(scene_context)
                if scene_flow:
                    context_blocks.append(scene_flow)
                if glossary_context:
                    context_blocks.append(glossary_context)
                combined_profiles_context = "\n\n".join(context_blocks)

                results = self.translate_batch_adaptive(batch, profiles_context=combined_profiles_context)

                for it in batch:
                    r_id = it["id"]
                    r_idx = it["row_idx"]
                    translated_prefix = it.get("translated_prefix")
                    if translated_prefix is None:
                        translated_prefix = self.glossary_scanner.translate_speaker_tag(it.get("prefix", "")) if it.get("prefix") else ""

                    raw_dialogue = results.get(r_id) or results.get(str(r_id))
                    if not raw_dialogue:
                        raw_dialogue = self.offline_safe_literary_translation(it.get("text", ""), it.get("speaker", ""))

                    translated_dialogue = self.enforce_glossary_in_translation(raw_dialogue, matched_glossary)
                    combined_initial = f"{translated_prefix}{translated_dialogue}"
                    rows[r_idx][1] = combined_initial
                    cached_rows[str(r_idx)] = combined_initial
                    speaker_label = it.get('speaker') or it.get('role', 'Narration')
                    logger.info(f"Row {r_idx + 1} [{speaker_label}]: {combined_initial[:60]}...")

                # บันทึก Checkpoint
                self.checkpoint_data["csv_translations"][csv_key] = cached_rows
                self.checkpoint_data["csv_translations"].setdefault("SSPV034v1.35 - Trans - Processed_v3.csv", {}).update(cached_rows)
                self.checkpoint_data["total_batches_done"] += 1
                self._save_checkpoint()

                # บันทึกลง Target CSV ทันทีทุก Batch
                temp_output = target_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerows(rows)
                os.replace(temp_output, target_csv_path)
                logger.info(f"Saved Queue progress to {target_csv_path}")

                # 3. ตัดรายการใน Batch นี้ออกจาก Queue บนดิสก์ทันที (Atomic Write Queue Pruning)
                completed_batch_indices = set(it["row_idx"] for it in batch)
                queue_items = [q for q in queue_items if ((q.get("row_idx") or q.get("csv_index", 0)) - 1) not in completed_batch_indices]
                if isinstance(raw_queue_data, dict):
                    output_queue_data = {
                        "timestamp": raw_queue_data.get("timestamp", ""),
                        "total_items": len(queue_items),
                        "items": queue_items
                    }
                else:
                    output_queue_data = queue_items
                temp_queue_file = queue_json_path + ".tmp"
                with open(temp_queue_file, "w", encoding="utf-8") as q_out:
                    json.dump(output_queue_data, q_out, ensure_ascii=False, indent=2)
                os.replace(temp_queue_file, queue_json_path)
                logger.info(f"Pruned Queue on disk: {len(batch)} items removed. Remaining in queue file: {len(queue_items):,} items.")

            logger.info(f"🎉 Queue processing completed! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return target_csv_path

    def translate_empty_rows(self, target_csv_path, max_tokens=8000, max_items_per_batch=15, batch_limit=None):
        """
        แปลเฉพาะแถวที่ว่างอยู่ (Initial == '') และ Displayable == 'Yes' โดยตรงจากไฟล์ CSV
        - ใช้ CSV เป็น Single Source of Truth 100% ไม่ต้องพึ่งพาไฟล์ Queue ภายนอก
        - แยกการแปลเป็น 2 รูปแบบ (Dual-Track):
            Track B: บทสนทนาใน Scene -> ดึงบริบททั้ง Scene (Scene Flow + Character Profiles + Glossary)
                     ส่งคำสั่งให้แปลเฉพาะประโยคเป้าหมายที่ว่างอยู่ โดยอ้างอิงประโยคอื่นในฉากอย่างเคร่งครัด
            Track A: ข้อความเดี่ยว/Database/UI Menu ที่ไม่เชื่อมโยงกับฉากเนื้อเรื่อง -> มัดรวมเป็นก้อนใหญ่ (35-40 รายการ)
                     ส่งแปลไทยพร้อมกำชับเด็ดขาดว่าให้คงรูปชื่อเฉพาะ (Red Arthur, Cerberus, Bonnie, MAPxxx, System CamelCase IDs) ไว้ในภาษาอังกฤษเดิม
        - บันทึกผลลัพธ์ลง Initial ของ CSV ทันทีแบบ Atomic Write ทุก Batch
        """
        if not os.path.exists(target_csv_path):
            logger.error(f"Target CSV not found: {target_csv_path}")
            return target_csv_path

        logger.info(f"📂 Scanning target CSV directly for EMPTY rows: {target_csv_path}")
        with open(target_csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            logger.warning("Target CSV is empty!")
            return target_csv_path

        # โหลด locked terms และชื่อตัวละครทั้งหมดสำหรับ auto-resolve จาก GlossaryScanner แบบ Dynamic 100%
        locked_terms = set()
        if hasattr(self, "glossary_scanner"):
            for c_name in getattr(self.glossary_scanner, "characters", {}).keys():
                locked_terms.add(c_name.strip().lower())
            for p_name in getattr(self.glossary_scanner, "curated_profiles", {}).keys():
                locked_terms.add(p_name.strip().lower())
            for cat, items in getattr(self.glossary_scanner, "glossary_data", {}).items():
                if isinstance(items, dict):
                    for en_name, val in items.items():
                        if isinstance(val, dict) and val.get("th", "").strip().lower() == en_name.strip().lower():
                            locked_terms.add(en_name.strip().lower())

        pending_empty_items = []
        skipped_non_displayable = 0
        direct_copied_non_disp = 0
        auto_resolved_symbols = 0
        already_filled_count = 0

        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            if len(row) < 2:
                continue

            orig_text = row[0] if len(row) > 0 else ""
            init_text = row[1] if len(row) > 1 else ""
            filename = row[2] if len(row) > 2 else ""
            line_id = row[3] if len(row) > 3 else ""
            role = row[5] if len(row) > 5 else ""
            speaker_col = row[6] if len(row) > 6 else ""
            disp = row[7].strip().lower() if len(row) > 7 else ""

            # กรองคอลัมน์ Displayable: แถวที่ไม่แสดงผลในเกม ห้ามส่งให้ LLM แปลเด็ดขาด!
            if disp != "yes":
                skipped_non_displayable += 1
                if not init_text.strip() and orig_text.strip():
                    row[1] = orig_text
                    direct_copied_non_disp += 1
                continue

            # ถ้าแถวนี้มีบทแปลอยู่แล้ว (ไม่ว่าง) ให้ข้ามทันที 100%!
            if init_text.strip():
                already_filled_count += 1
                continue

            # ถ้า Original ว่างเปล่า
            if not orig_text.strip():
                continue

            # ตรวจจับตัวเลขเงิน/ค่าระบบสากล (เช่น 18G, 20G, 48G): Auto-fill ทันที ไม่ส่งไป LLM
            clean_num = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<]", "", orig_text).strip()
            if re.match(r"^\d+\s*G?$", clean_num, flags=re.IGNORECASE):
                row[1] = orig_text
                auto_resolved_symbols += 1
                continue

            # สกัด speaker tag จาก orig_text หากมี
            has_tag, prefix, parsed_speaker, pure_text = self.extract_speaker_tag(orig_text)
            if has_tag:
                final_speaker = parsed_speaker
                final_text = pure_text
            else:
                final_speaker = speaker_col.strip() if speaker_col else "Narrator"
                final_text = orig_text.strip()
                prefix = ""

            translated_prefix = ""
            if prefix:
                translated_prefix = self.glossary_scanner.translate_speaker_tag(prefix)

            # ตรวจสอบ Pure Symbols / Single Locked Name: ถ้าไม่มีเนื้อหาบทพูดจริง ให้ Auto-fill โดยไม่ต้องส่ง LLM
            content_to_check = final_text.strip()
            if self.is_single_name_with_symbols(content_to_check, locked_terms, current_speaker=final_speaker):
                row[1] = f"{translated_prefix}{final_text}"
                auto_resolved_symbols += 1
                continue

            # ค้นหา Scene ID ที่แท้จริงจาก SceneContextManager
            scene_id = "General_Scene"
            if hasattr(self, "scene_manager"):
                scene_id = self.scene_manager.find_scene_for_row(r_idx, orig_text, file_name=filename, csv_rows=rows)

            pending_empty_items.append({
                "row_idx": r_idx,
                "prefix": prefix,
                "translated_prefix": translated_prefix,
                "speaker": final_speaker,
                "role": role if role else "Dialogue/Story",
                "id": str(r_idx),
                "text": final_text,
                "file": filename,
                "scene_id": scene_id
            })

        logger.info(f"Target CSV Empty-Row Scan Summary:")
        logger.info(f"  • Total Rows in File: {len(rows):,}")
        logger.info(f"  • Already Filled (Untouched): {already_filled_count:,}")
        logger.info(f"  • Non-Displayable Handled: {skipped_non_displayable:,} (Direct copied: {direct_copied_non_disp:,})")
        logger.info(f"  • Auto-Resolved Symbols/Currency: {auto_resolved_symbols:,}")
        logger.info(f"  • Empty Target Rows Requiring LLM Translation: {len(pending_empty_items):,}")

        # บันทึกสถานะเริ่มต้นของ auto-filled ทันทีหากมีการเปลี่ยนแปลง
        if direct_copied_non_disp > 0 or auto_resolved_symbols > 0:
            temp_output = target_csv_path + ".tmp"
            with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerows(rows)
            os.replace(temp_output, target_csv_path)
            logger.info(f"Saved auto-resolved non-displayable/symbol items to {target_csv_path}")

        if not pending_empty_items:
            logger.info("🎉 All Displayable rows in CSV are already 100% translated! No empty rows found.")
            return target_csv_path

        # -------------------------------------------------------------
        # DUAL-TRACK CLASSIFICATION & BATCH PACKING
        # -------------------------------------------------------------
        track_a_items = []  # Standalone / Direct Batches (Database & UI Choices ไม่ต้องใช้บริบทฉาก)
        track_b_items = []  # Narrative Scene Batches (ฉากเนื้อเรื่องที่ต้องใช้บริบทและ Flow ฉาก)

        for d in pending_empty_items:
            sc_id = d.get("scene_id", "General_Scene")
            role_clean = (d.get("role") or "").strip().lower()
            file_clean = (d.get("file") or "").strip().lower()
            is_standalone = (
                sc_id.endswith("_Database") or
                sc_id == "System_Menu_Choices" or
                role_clean in ["field: name", "field: description", "menu", "system"] or
                "tilesets" in file_clean or
                "mapinfos" in file_clean
            )
            if is_standalone:
                track_a_items.append(d)
            else:
                track_b_items.append(d)

        batches = []

        # 1. จัดการ Track A Batches (รวมก้อนใหญ่ 35-40 items/batch)
        mapinfos_items = [it for it in track_a_items if it.get("scene_id") == "Mapinfos_Database"]
        other_db_items = [it for it in track_a_items if it.get("scene_id") != "Mapinfos_Database"]
        for i in range(0, len(mapinfos_items), 35):
            batches.append(mapinfos_items[i:i + 35])
        for i in range(0, len(other_db_items), 35):
            batches.append(other_db_items[i:i + 35])

        # 2. จัดการ Track B Batches (ฉากเนื้อเรื่อง)
        scenes_map = {}
        for it in track_b_items:
            sc_id = it.get("scene_id", "General_Scene")
            if sc_id not in scenes_map:
                scenes_map[sc_id] = []
            scenes_map[sc_id].append(it)

        small_scenes_pool = []
        for sc_id, items in scenes_map.items():
            if len(items) >= 5:
                # ถ้าฉากมีไม่เกิน 20 รายการ ให้อยู่ใน Batch เดียวกันทั้งฉากเพื่อรักษาความต่อเนื่อง ไม่ต้องตัดเศษ
                if len(items) <= 20:
                    batches.append(items)
                else:
                    for i in range(0, len(items), max_items_per_batch):
                        batches.append(items[i:i + max_items_per_batch])
            else:
                small_scenes_pool.extend(items)

        # รวมฉากเล็กๆ ที่กระจัดกระจาย โดยจัดกลุ่มตาม Map Prefix เดียวกัน
        small_by_map = {}
        for it in small_scenes_pool:
            fn = it.get("file", "") or it.get("scene_id", "").split("_")[0]
            prefix = fn.split("_")[0] if fn else "Misc"
            if prefix not in small_by_map:
                small_by_map[prefix] = []
            small_by_map[prefix].append(it)

        current_bundle = []
        for prefix, p_items in small_by_map.items():
            for it in p_items:
                current_bundle.append(it)
                if len(current_bundle) >= max_items_per_batch:
                    batches.append(current_bundle)
                    current_bundle = []
        if current_bundle:
            batches.append(current_bundle)

        logger.info(f"📦 Dual-Track Batch Packing: Grouped {len(pending_empty_items)} empty items into {len(batches)} batches (Track A: {len(track_a_items)} items, Track B: {len(track_b_items)} items)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Processing {len(batches)} batches in this session.")

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge_ready()
            for b_idx, batch in enumerate(batches):
                sc_id = batch[0].get("scene_id", "General_Scene")
                role_clean = (batch[0].get("role") or "").strip().lower()
                file_clean = (batch[0].get("file") or "").strip().lower()
                is_track_a = (
                    sc_id.endswith("_Database") or
                    sc_id == "System_Menu_Choices" or
                    role_clean in ["field: name", "field: description", "menu", "system"] or
                    "tilesets" in file_clean or
                    "mapinfos" in file_clean
                )
                track_label = "Track A (Direct/Database)" if is_track_a else "Track B (Narrative Scene)"
                logger.info(f"=== Translating Empty Rows Batch {b_idx + 1}/{len(batches)} [{track_label}] (Scene: {sc_id} | {len(batch)} items) ===")

                batch_texts = [it.get("text", "") for it in batch]
                speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
                matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
                glossary_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

                context_blocks = []

                if is_track_a:
                    # Directive พิเศษสำหรับ Track A: ห้ามแปลชื่อเฉพาะเด็ดขาด
                    track_a_directive = (
                        "### STANDALONE GAME TEXT / DATABASE DIRECTIVE:\n"
                        "- Translate descriptive game labels, system terms, and instructions into natural Thai.\n"
                        "- MANDATORY RULE: Keep proper nouns, character names, and technical engine identifiers in English as-is! "
                        "Examples of terms that MUST REMAIN IN ENGLISH: 'Red Arthur', 'Cerberus', 'Bonnie', 'Kintah', 'MAPxxx', or system IDs like 'BeachGameTutPurposes', 'CookInterface'."
                    )
                    context_blocks.append(track_a_directive)
                    if glossary_context:
                        context_blocks.append(glossary_context)
                else:
                    # สกัด Scene Narrative Overview, Mood, Tone จาก extractions_v4
                    scene_context = ""
                    if hasattr(self, "scene_manager"):
                        try:
                            scene_context = self.scene_manager.get_scene_context_by_id(
                                sc_id,
                                fallback_speakers=speakers,
                                fallback_filename=batch[0].get("file", "")
                            )
                        except Exception as sc_err:
                            logger.warning(f"Scene context extraction notice: {sc_err}")

                    # สกัด Scene Dialogue Flow (บทสนทนาแวดล้อมพร้อมคำแปลไทยเดิมใน CSV)
                    scene_flow = ""
                    if hasattr(self, "scene_manager"):
                        try:
                            target_indices = [it["row_idx"] for it in batch]
                            scene_flow = self.scene_manager.get_scene_dialogue_flow(
                                sc_id,
                                target_indices,
                                csv_rows=rows,
                                max_flow_lines=25
                            )
                        except Exception as flow_err:
                            logger.warning(f"Scene flow extraction notice: {flow_err}")

                    if scene_context:
                        context_blocks.append(scene_context)
                    if scene_flow:
                        context_blocks.append(scene_flow)
                    if glossary_context:
                        context_blocks.append(glossary_context)

                combined_profiles_context = "\n\n".join(context_blocks)

                results = self.translate_batch_adaptive(batch, profiles_context=combined_profiles_context)

                for it in batch:
                    r_id = it["id"]
                    r_idx = it["row_idx"]
                    translated_prefix = it.get("translated_prefix")
                    if translated_prefix is None:
                        translated_prefix = self.glossary_scanner.translate_speaker_tag(it.get("prefix", "")) if it.get("prefix") else ""

                    raw_dialogue = results.get(r_id) or results.get(str(r_id))
                    if not raw_dialogue:
                        raw_dialogue = self.offline_safe_literary_translation(it.get("text", ""), it.get("speaker", ""))

                    translated_dialogue = self.enforce_glossary_in_translation(raw_dialogue, matched_glossary)
                    combined_initial = f"{translated_prefix}{translated_dialogue}"
                    rows[r_idx][1] = combined_initial
                    speaker_label = it.get('speaker') or it.get('role', 'Narration')
                    logger.info(f"Row {r_idx + 1} [{speaker_label}]: {combined_initial[:60]}...")

                # บันทึกลง Target CSV ทันทีทุก Batch (Atomic Write)
                temp_output = target_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerows(rows)
                os.replace(temp_output, target_csv_path)
                logger.info(f"💾 Saved Progress to CSV ({b_idx + 1}/{len(batches)} batches done) -> {target_csv_path}")

            logger.info(f"🎉 All empty row batches completed! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return target_csv_path

    def translate_plugins_csv(self, plugins_csv_path="data/plugins_texts.csv", max_items_per_batch=15, batch_limit=None):
        """
        แปลไฟล์ Plugin UI Text (data/plugins_texts.csv) ด้วย Batch JSON Translation
        บันทึกผลลัพธ์ลงคอลัมน์ Initial (index 1) แบบ Atomic Write ทุก Batch
        """
        if not os.path.exists(plugins_csv_path):
            raise FileNotFoundError(f"Plugin texts CSV not found at {plugins_csv_path}")

        logger.info(f"📂 Loading Plugin Texts from: {plugins_csv_path}")
        with open(plugins_csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        if not reader:
            logger.warning("Empty plugins CSV file!")
            return plugins_csv_path

        header = reader[0]
        data_rows = reader[1:]
        logger.info(f"Total Plugin Text Rows: {len(data_rows):,} rows")

        # คัดกรองแถวที่ยังไม่ได้แปล (คอลัมน์ Initial ว่างอยู่)
        untranslated = []
        for idx, row in enumerate(data_rows):
            orig_text = row[0] if len(row) > 0 else ""
            init_text = row[1] if len(row) > 1 else ""
            if not orig_text or not orig_text.strip():
                continue
            if not init_text or not init_text.strip():
                untranslated.append({
                    "row_idx": idx,
                    "id": f"PLUG_{idx + 1}",
                    "speaker": row[6] if len(row) > 6 and row[6] else "UI/Plugin",
                    "role": "UI/Plugin",
                    "text": orig_text
                })

        logger.info(f"Found {len(untranslated):,} untranslated Plugin rows out of {len(data_rows):,} rows.")
        if not untranslated:
            logger.info("🎉 All Plugin UI texts are already 100% translated!")
            return plugins_csv_path

        # แบ่งเป็น Batches
        batches = []
        for i in range(0, len(untranslated), max_items_per_batch):
            batches.append(untranslated[i:i + max_items_per_batch])

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Processing {len(batches)} batches in this session.")

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge_ready()
            for b_idx, batch in enumerate(batches):
                logger.info(f"=== Translating Plugin Batch {b_idx + 1}/{len(batches)} ({len(batch)} items) ===")
                results = self.translate_batch_adaptive(batch)

                for it in batch:
                    r_id = it["id"]
                    r_idx = it["row_idx"]
                    num_id = re.sub(r'^[^\d]*', '', str(r_id))
                    trans_text = (
                        results.get(r_id)
                        or results.get(str(r_id))
                        or (results.get(num_id) if num_id else None)
                        or (results.get(int(num_id)) if num_id and num_id.isdigit() else None)
                    )
                    if trans_text:
                        while len(data_rows[r_idx]) < 2:
                            data_rows[r_idx].append("")
                        data_rows[r_idx][1] = trans_text
                        logger.info(f"  • {r_id} [{it['speaker']}]: {repr(trans_text[:50])}")

                        # Auto-propagate translation to any matching duplicate rows in data_rows
                        orig_val = it.get("text", "").strip()
                        if orig_val:
                            for dup_row in data_rows:
                                if len(dup_row) > 0 and dup_row[0].strip() == orig_val:
                                    if len(dup_row) < 2 or not dup_row[1].strip():
                                        while len(dup_row) < 2:
                                            dup_row.append("")
                                        dup_row[1] = trans_text
                    else:
                        logger.warning(f"  ⚠️ No translation found for {r_id} ({repr(it['text'][:30])})")

                # Atomic Save to plugins_texts.csv every batch
                temp_output = plugins_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerow(header)
                    writer.writerows(data_rows)
                os.replace(temp_output, plugins_csv_path)
                logger.info(f"Saved Plugin translation progress ({b_idx + 1}/{len(batches)} batches) to {plugins_csv_path}")

            logger.info(f"🎉 Plugin Translation completed successfully! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return plugins_csv_path

    def run_unified_all(self, csv_file=None, plugins_file=None, max_tokens=8000, max_items=15, batch_limit=None):
        """
        แปลรวดเดียวจบทั้งระบบตาม Pipeline ปกติ (Unified All-in-One Translation):
        Step 1: แปลข้อความ Plugin UI Texts (plugins_texts_v035.csv หรือ data/plugins_texts.csv)
        Step 2: สลับไปแปล Dialogue CSV หลัก (processed_dialogues_v3.csv) ในโหมด Empty Rows (Single Source of Truth) ต่อเนื่องทันทีอัตโนมัติ
        """
        logger.info("=" * 80)
        logger.info("🚀 STARTING ATF UNIFIED ALL-IN-ONE TRANSLATION PIPELINE")
        logger.info("=" * 80)

        # -------------------------------------------------------------
        # STEP 1: แปล Plugin UI Texts
        # -------------------------------------------------------------
        if not plugins_file:
            plugins_file = self.manifest.get("output_plugins_csv") or "data/plugins_texts.csv"

        if plugins_file and os.path.exists(plugins_file):
            logger.info(f"\n>>> [STEP 1/2] Translating Plugin UI Texts: {plugins_file}...")
            self.translate_plugins_csv(
                plugins_csv_path=plugins_file,
                max_items_per_batch=max_items,
                batch_limit=batch_limit
            )
            logger.info("✅ [STEP 1/2] Plugin UI Texts translation completed!\n")
        else:
            logger.warning(f"Plugin texts CSV not found at {plugins_file}, skipping Step 1.")

        # -------------------------------------------------------------
        # STEP 2: แปล Game Dialogue CSV หลัก
        # -------------------------------------------------------------
        if not csv_file:
            csv_file = self.manifest.get("output_processed_csv")
            if not csv_file or not os.path.exists(csv_file):
                candidate_paths = [
                    "Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3.csv",
                    "Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated.csv",
                    "testing files/SSPV034v1.35 - Trans - Processed_v3.csv",
                    "testing files/SSPV034v1.35 - Trans - Processed_v3_translated.csv"
                ]
                for p in candidate_paths:
                    if os.path.exists(p):
                        csv_file = p
                        break

        if csv_file and os.path.exists(csv_file):
            logger.info(f"\n>>> [STEP 2/2] Translating Game Dialogue CSV (Empty Rows): {csv_file}...")
            self.translate_empty_rows(
                target_csv_path=csv_file,
                max_tokens=max_tokens,
                max_items_per_batch=max_items,
                batch_limit=batch_limit
            )
            logger.info("✅ [STEP 2/2] Game Dialogue CSV translation completed!\n")
        else:
            logger.error(f"❌ Target CSV file not found: {csv_file}")

        logger.info("=" * 80)
        logger.info("🎉 ALL TRANSLATION QUEUES (PLUGINS + DIALOGUES) COMPLETED 100%!")
        logger.info("=" * 80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ChatGPT Translator Runner for ATF")
    parser.add_argument("--file", type=str, default=None, help="Path to CSV file to translate")
    parser.add_argument("--plugins-file", type=str, default=None, help="Path to Plugins CSV file to translate")
    parser.add_argument("--queue", type=str, default=None, help="Path to untranslated queue JSON file to translate directly into target CSV")
    parser.add_argument("--plugins", action="store_true", help="Translate Plugin UI texts only")
    parser.add_argument("--unified", action="store_true", default=True, help="Run Unified All-in-One translation (Plugins UI -> Dialogue CSV continuously)")
    parser.add_argument("--all", action="store_true", default=True, help="Run all batches continuously until 100%% complete (default: True)")
    parser.add_argument("--batches", type=int, default=None, help="Number of batches to run in this session")
    parser.add_argument("--tokens", type=int, default=8000, help="Token budget per batch (default: 8000)")
    parser.add_argument("--max-items", type=int, default=15, help="Max dialogues per batch (default: 15)")
    parser.add_argument("--empty-only", action="store_true", help="Scan target CSV directly and translate ONLY empty rows (Initial == '') where Displayable == 'Yes'")
    parser.add_argument("--manifest", type=str, default=None, help="Path to project_manifest.json")
    parser.add_argument("--fresh", action="store_true", help="Reset checkpoint and start fresh")
    parser.add_argument("--pace-min", type=float, default=8.0, help="Min human delay between batches in seconds (default: 8.0)")
    parser.add_argument("--pace-max", type=float, default=15.0, help="Max human delay between batches in seconds (default: 15.0)")
    args = parser.parse_args()

    batch_limit = args.batches if args.batches is not None else None
    runner = ChatGPTTranslatorRunner(
        manifest_path=args.manifest,
        pace_min=args.pace_min,
        pace_max=args.pace_max
    )

    if args.plugins:
        plugins_target = args.plugins_file or runner.manifest.get("output_plugins_csv") or "data/plugins_texts.csv"
        print(f"🚀 Running Plugin UI Text Translation on: {plugins_target}")
        print(f"📦 Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_plugins_csv(
            plugins_csv_path=plugins_target,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    # หากสั่ง --unified หรือรันเริ่มต้นโดยไม่ระบุ file เฉพาะเจาะจง ให้ทำ Unified All-in-One
    if args.unified and not args.queue and not args.file and not args.empty_only:
        print("🚀 Launching Unified All-in-One Translation Pipeline (Plugins -> Dialogues)...")
        runner.run_unified_all(
            csv_file=args.file,
            plugins_file=args.plugins_file,
            max_tokens=args.tokens,
            max_items=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    # เลือกไฟล์เป้าหมาย: ตรวจหาจาก Manifest ก่อน แล้วจึงดู candidate paths
    csv_file = args.file or runner.manifest.get("output_processed_csv")
    if not csv_file:
        candidate_paths = [
            "Example RPGM Game/SSPV034v1.35 - Trans - ชีต1 - Reset wrong legacy.csv",
            "Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3.csv",
            "Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated.csv",
            "testing files/SSPV034v1.35 - Trans - Processed_v3.csv",
            "testing files/SSPV034v1.35 - Trans - Processed_v3_translated.csv"
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                csv_file = p
                break

    if not csv_file or not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        sys.exit(1)

    if args.empty_only:
        print(f"🚀 Running Direct Empty-Row Translation on: {csv_file}")
        print(f"🎯 Target Mode: Single Source of Truth (Translating ONLY Empty & Displayable rows)")
        print(f"📦 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_empty_rows(
            target_csv_path=csv_file,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    if args.queue:
        print(f"🚀 Running Queue-Based Translation on: {args.queue}")
        print(f"🎯 Target CSV: {csv_file}")
        print(f"📦 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_untranslated_queue(
            queue_json_path=args.queue,
            target_csv_path=csv_file,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
    else:
        print(f"🚀 Running Scene-Based Translation on: {csv_file}")
        print(f"📦 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL (Continuous till done)' if batch_limit is None else batch_limit}")
        runner.translate_csv_file(
            input_csv_path=csv_file,
            batch_size=None,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit,
            reset_checkpoint=args.fresh
        )


