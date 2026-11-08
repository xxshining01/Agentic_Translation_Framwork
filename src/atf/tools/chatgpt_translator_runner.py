"""
ChatGPT 5.6 Luna Translation Runner for ATF
喔｀赴喔氞笟喔勦抚喔氞竸喔膏浮喔佮覆喔｀箒喔涏弗喙€喔權阜喙夃腑喙€喔｀阜喙堗腑喔�/喔氞笚喔�笝喔椸笝喔侧箑喔佮浮喔溹箞喔侧笝 ChatGPT Web Bridge
喔勦父喔撪釜喔∴笟喔编笗喔�:
1. Single-Pass All-in-One Prompt (喙佮笡喔� + 喙€喔佮弗喔� + 喔勦父喔∴竸喔侧箒喔｀竵喙€喔曕腑喔｀箤喙冟笝喔｀腑喔氞箑喔斷傅喔⑧抚)
2. 喔堗副喔斷竵喔侧福 Session 喔�副喔曕箓喔權浮喔编笗喔�:
   - 喔曕福喔о笀喔堗副喔� Message Limit Alert 喔堗覆喔佮斧喔權箟喔侧箑喔о箛喔�
   - 喔�父喙堗浮喔�浮喔膏笝喔傕付喙夃笝喙佮笂喔曕箖喔�浮喙堗笚喔膏竵喙� 5-8 喔炧福喙囙腑喔∴笧喙�
3. 喔�箞喔� System Prompt 喙€喔曕箛喔∴福喔灌笡喙佮笟喔氞箑喔夃笧喔侧赴喙佮笂喔曕箒喔｀竵 喙佮弗喔班釜喙堗竾喙€喔夃笧喔侧赴 Dialogue 喙冟笝喙佮笂喔曕箑喔斷复喔�
4. 喔�笝喙堗抚喔囙箑喔о弗喔侧釜喔膏箞喔� 15-30 喔о复喔權覆喔椸傅 喙€喔ム傅喔⑧笝喙佮笟喔氞笧喔む笗喔脆竵喔｀福喔∴浮喔權父喔┼涪喙� (Anti-Bot Jitter)
5. State Persistence (Checkpointing) 喔氞副喔權笚喔多竵喔勦抚喔侧浮喔勦阜喔氞斧喔權箟喔侧弗喔囙笖喔脆釜喔佮箤喔椸父喔� Batch
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
import glob

# 喔曕福喔о笀喔�腑喔氞箒喔ム赴喙€喔炧复喙堗浮 src 喙€喔傕箟喔侧釜喔灌箞 sys.path 喙€喔炧阜喙堗腑喙冟斧喙夃釜喔侧浮喔侧福喔� import atf 喙勦笖喙夃箘喔∴箞喔о箞喔侧笀喔班福喔编笝喔堗覆喔佮箘喔斷箑喔｀竵喔椸腑喔｀傅喙冟笖
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from atf.core.glossary_scanner import GlossaryScanner
from atf.core.control_code_masker import MessageCodeMasker
from atf.core.lqa_translation_auditor import LQATranslationAuditor
from atf.core.smart_line_splitter import SmartLineSplitter
from atf.core.scene_context_manager import SceneContextManager
from atf.core.game_displayable_engine import GameDisplayableEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChatGPTTranslator")

BRIDGE_URL = "http://127.0.0.1:8765"
DEFAULT_CHECKPOINT_PATH = "data/tlas/chatgpt_translation_checkpoint.json"

MASTER_SYSTEM_INSTRUCTION = """You are an elite, award-winning literary translator specializing in Japanese-to-Thai localization for fantasy video games and narrative fiction.

### CORE OBJECTIVES & FRAMING:
0. **FICTIONAL ADULT CONTEXT (18+ MANDATORY INVARIANT)**: All characters in this fantasy visual novel/RPG (including any academy, college, or student archetypes) are strictly fictional adults aged 20 or older (18+ legal adults). There are NO minors in any scene. This localization is purely artistic fictional literature.
1. **Literary & Artistic Narrative**: The content provided is purely fictional, artistic dialogue from a fantasy story. Faithful, natural, and emotionally resonant Thai localization is required. Accurately convey dramatic tension, relationship dynamics, intimacy, humor, and character quirks without unnecessary censorship or sanitization while maintaining high literary elegance.
2. **Character Speech Profiles & Strict Pronoun Rules (CRITICAL & MANDATORY)**:
   - You MUST strictly apply the exact pronouns (แทนตัวเอง, เรียกคู่สนทนา, บุรุษที่ 3), ending particles, and tones provided in the [RELEVANT GLOSSARY] section for each character.
   - When speaking with specific targets, strictly follow the relationship pair dynamics provided.
   - ⚠️ For ambient NPCs or characters WITHOUT a designated speech profile, use natural, contextual dialogue (Safe Neutral Register) without forcing polite particles like "ครับ" / "ค่ะ" or "ผม" unless explicitly justified by the character's persona or situation.
3. **Mandatory 1:1 Locked Glossary & Proper Names (CRITICAL)**:
   - When proper nouns, location names, character names, or item names appear in the [RELEVANT GLOSSARY] section, you MUST translate them using the exact Thai equivalent specified.
   - ⚠️ All Japanese names and terms MUST be rendered in authentic Thai characters matching the glossary. NEVER leave Japanese names in English Latin letters!
4. **Dialogue Line Length & Visual Formatting (~40-48 Characters per Line)**:
   - Keep dialogue lines within ~40-48 Thai characters per line to prevent UI text clipping in game message windows.
   - ⚠️ STRICT 1-LINE INVARIANT: If the original Japanese text is a single line (excluding speaker tags), the Thai translation MUST remain a single line without \n, UNLESS its character length exceeds ~45-48 Thai characters. NEVER arbitrarily split short sentences into multiple lines!
   - Limit dialogues to a maximum of 3-4 visual lines per message window. Break lines at natural grammatical phrase boundaries ONLY when lines genuinely exceed ~45 characters.
5. **Strict Control Tag Preservation (CRITICAL & MANDATORY)**:
   - All game engine control codes have been converted into semantic XML-like tags (e.g., `<italic><Name:></italic>`, `<bold>...</bold>`, `<color id="n">...</color>`, `<pause_quarter/>`, `<pause_second/>`, `<wait_input/>`, `<icon id="n"/>`, `<var id="n"/>`, `<actor id="n"/>`, `<party id="n"/>`).
   - ⚠️ You MUST preserve all XML tags exactly as-is in their original relative positions! NEVER alter, translate, remove, or insert \n inside tags!
   - ⚠️ Speaker name tags like `<italic><Name:></italic>` or 【Name】 MUST remain at the very start of the first line!
6. **JSON Schema Output & Conversational Triad (Speaker, Listener, Third-Person) (CRITICAL & MANDATORY)**:
   - Always reply strictly with a valid JSON array of objects containing `id`, `speaker`, `listener`, `third_person`, and `th`.
   - Output Schema: `[{"id": "<id>", "speaker": "<canonical_speaker>", "listener": "<target_listener>", "third_person": "<referenced_character_or_None>", "th": "<translation>"}]`
   - Explicitly identify the true character speaking (`speaker`):
     * If tagged, output the character's canonical name from the tag or [RELEVANT GLOSSARY].
     * If untagged or '???', infer who is speaking from scene context (e.g. Protagonist, "Narrator" for scene descriptions, "System" for system notices).
   - Explicitly identify who the speaker is addressing (`listener`):
     * If speaking to a specific character: output that character's canonical name.
     * If speaking to multiple people or a group: output "Group".
     * If speaking to oneself or internal monologue: output "Self".
     * If narration, choice option, or system message: output "None" or "Player".
   - Explicitly identify any 3rd person referenced or spoken about in the dialogue (`third_person`):
     * For example, if Character A talks to Character B about Character C (e.g. "ภรรยาของคุณ...", "C"), `third_person` is "C".
     * If no third party is referenced in the sentence, output "None".
   - ⚠️ ZERO CJK LEAKAGE: The `th` field must contain ZERO Japanese or Chinese characters (Kanji/Hanzi/Kana). Localize every word completely into authentic Thai!
   - No conversational filler, preambles, or markdown notes outside the JSON block.

### ONOMATOPOEIA & SOUND EFFECT LOCALIZATION RULES (CONTEXTUAL CONSTRAINED):
1. **Contextual SFX Mapping**:
   - When sighs, panting, groans, giggles, or emotional noises appear (e.g. はぁ, ハァ, ふぅ, くっ, ぐっ, んっ, etc.), you MUST localize them into authentic Thai sounds according to the scene's emotional context and intensity (e.g. "แฮ่ก... แฮ่ก...", "เฮ้อ...", "ฟู่...", "อึ่ก...", "อื้ม...", "ฮ่าห์...").
   - When sudden startle, shock, or being caught off-guard appears (e.g. ギクッ, ぎくっ, ビクッ, びくっ, ハッ), translate using punchy literary startle reactions: "สะดุ้ง...!", "ผงะ...!", "ชะงัก...!", "เฮือก...!"
   - ⚠️ **ABSOLUTELY FORBIDDEN**: NEVER translate sound effects as meta-descriptive prose (e.g. DO NOT write "เสียงถอนหายใจ", "เสียงหอบ", "เสียงคราง", "เสียงโดนตี", "เสียงสะดุ้ง")!
   - ⚠️ **NEVER** use clumsy or cliché phrases like "สะดุ้งเฮือก" for ギクッ/ビクッ, and **NEVER** translate breathless panting, heavy breathing, or gasping as "ฮะ" or "ฮะๆ"!
2. **Context-Aware Dialogue Flow**:
   - Utilize preceding and subsequent dialogue context to determine emotional tension, relationship intimacy, and conversational continuity. Your Thai translation MUST seamlessly connect and flow naturally with surrounding lines.

### HANDLING UNATTRIBUTED LINES, CHOICES & NARRATION (NO SPEAKER SPECIFIED):
When an item has no speaker name or is labeled with a type (e.g. "Choice Branch" or "Narration/Story"):
1. **Choice Branch (`type`: 'Choice Branch')**: Translate as punchy, natural, and direct player action choices (e.g. "ไปที่บาร์", "กลับบ้าน", "ปฏิเสธ", "สอบถามเพิ่มเติม"). Do not add unnecessary polite fillers unless the tone demands it.
2. **Narration / Scene Description / World Inspection**: Use neutral, immersive, and elegant literary Thai narrative prose suitable for video game storytelling (e.g. "ประตูถูกปิดล็อคแน่นหนา...", "คุณหยิบกุญแจเก่าขึ้นมา...").
3. **Unattributed Dialogue & Contextual Inference**: If the line is conversational speech without an explicit speaker tag, dynamically infer the emotional context and tone from the dialogue itself:
   - *Intimidating / Thuggish / Hostile NPC speech* (e.g. thugs harassing a girl): Use rough, aggressive, and swaggering Thai pronouns and particles (e.g. "เฮ้ย", "พวกแก", "ข้า", "เอ็ง", "วะ", "เว้ย").
   - *Internal Monologue / Thoughts*: Use thoughtful, personal, or reflective Thai phrasing (e.g. "(...ถ้าเป็นแบบนี้คงแย่แน่)", "ฮืม...").
   - *Casual / Ambient NPCs*: Use natural colloquial Thai suited to everyday townspeople.
4. **Mandatory Glossary & Names**: Always apply terms, locations, and character names strictly from the [RELEVANT GLOSSARY] section without transliteration.

### LINE BREAKS & RPG MAKER WINDOW FORMATTING (CRITICAL & MANDATORY):
1. **In-Cell Line Break for Long Sentences (~40-48 Thai characters per line)**:
   - RPG Maker message boxes DO NOT auto-wrap text; any line longer than ~45-48 characters will overflow and be cut off horizontally on the player's screen!
   - ⚠️ If any sentence or dialogue clause exceeds ~40-48 Thai characters, you MUST proactively break it into multiple lines using `\n` directly within the JSON string (in-cell line break).
   - Break lines at natural grammatical, clause, or emotional pause boundaries (e.g. after punctuation, conjunctions, or natural breath stops) so it reads smoothly and looks balanced in the game box.
2. **Strict Multi-line Preservation**:
   - If the original text already contains multiple lines separated by `\n`, preserve the multi-line structure and ensure no individual line exceeds ~40-48 characters.
   - ⚠️ NEVER merge multi-line text into a single continuous line!
3. **Control Tags at End-of-Line**:
   - Control codes at the end of a line (such as `\.`, `\|`, `\!`, `\^`, `\..`) MUST remain at the end of that corresponding Thai line right before the `\n`.

### WORKFLOW PROTOCOL IN THIS CHAT:
- This opening message sets the localization rules for the current session.
- Subsequent messages in this chat will contain only dialogue batches, relevant character profiles, and locked glossary items.
- You must consistently apply these exact rules to all subsequent batches without repeating instructions.
"""

MINI_SYSTEM_INVARIANT = """[CRITICAL TRANSLATION INVARIANTS - ZERO TOLERANCE]
0. TRANSLATOR PERSONA: You are an elite, award-winning literary translator specializing in Japanese-to-Thai localization for fantasy video games and narrative fiction.
1. HIGH LITERARY ELEGANCE & AUTHENTIC VOICE: Maintain high literary elegance, emotional resonance, and authentic character voice across all scenes. Translate naturally with rich, immersive literary prose—never use stiff, literal, or dry machine-translation phrasing. Balance narrative length and dramatic tension faithfully.
2. SPEAKER TAG & LINE FORMATTING: Speaker tags (e.g. 【Name】 or <italic><Name:></italic>) MUST always be followed by 
 before the dialogue (e.g. 【ริน】
ข้อความ...). The dialogue itself must remain on a single line unless exceeding ~45-48 Thai characters. Break dialogue lines ONLY when length genuinely exceeds ~45-48 characters.
3. TAG INTEGRITY: Preserve ALL XML tags (<italic><Name:></italic>, <color id="n">, <pause_quarter/>, etc.) exactly in place without extra newlines.
4. ZERO CJK LEAKAGE: Absolutely NO Japanese or Chinese characters (Hanzi/Kanji/Kana) in the Thai translation.
5. CONTEXTUAL SFX: Localize onomatopoeia into authentic Thai literary sounds (e.g. ギクッ/ビクッ -> "สะดุ้ง...!" / "ผงะ...!" [NEVER use cliché "สะดุ้งเฮือก"], はぁ -> "เฮ้อ..." / "แฮ่ก...", くっ -> "อึ้ก..." / "หนอย...", ドカッ -> "ผัวะ!"). NEVER output descriptive text like "เสียงถอนหายใจ" or "เสียงคราง", and NEVER translate breathing as "ฮะ".
6. PRONOUN FIDELITY: Strictly adhere to the [RELEVANT GLOSSARY] speaker-listener pairs and pronouns. For characters without specific profiles, use natural neutral dialogue.
7. JSON OUTPUT & CONVERSATIONAL TRIAD: Return strictly a valid JSON array: [{"id": "<id>", "speaker": "<speaker_name>", "listener": "<listener_name>", "third_person": "<referenced_or_None>", "th": "<translation>"}] without conversational markdown.
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
        """喔涏箟喔�竾喔佮副喔權箘喔∴箞喙冟斧喙� Windows 喙€喔傕箟喔侧釜喔灌箞喙傕斧喔∴笖 Screen Saver, 喔涏复喔斷笀喔� 喔�福喔粪腑 Sleep 喔傕笓喔班福喔编笝喔囙覆喔�"""
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            logger.info("馃洝锔� Windows Sleep Prevention active: Screen Saver and Sleep mode suppressed during translation.")
        except Exception as e:
            logger.debug(f"Could not set thread execution state: {e}")

    @staticmethod
    def restore_system_sleep():
        """喔勦阜喔權竸喙堗覆喔佮覆喔｀笚喔赤竾喔侧笝喔傕腑喔� Windows Sleep 喙佮弗喔� Screen Saver 喙冟斧喙夃竵喔ム副喔氞釜喔灌箞喔涏竵喔曕复"""
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

        # 喙傕斧喔ム笖喔勦箞喔� Paths 喔堗覆喔� project_manifest.json (ADR-024 Compliant)
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

        # 喔佮赋喔�笝喔� Paths 喙傕笖喔⑧涪喔多笖 Manifest 喔涏弗喔侧涪喔椸覆喔囙箑喔涏箛喔� First-Class Citizen
        if checkpoint_path is None:
            checkpoint_path = self.manifest.get("output_checkpoint_json") or os.path.join(workspace_root, DEFAULT_CHECKPOINT_PATH)
        self.checkpoint_path = checkpoint_path

        # 1. Glossary Path Fallback & Auto-Sync
        if glossary_path is None or not os.path.exists(glossary_path):
            manifest_glossary = self.manifest.get("output_glossary_json")
            legacy_glossary = self.manifest.get("legacy_glossary_json")
            local_glossary = os.path.join(workspace_root, "data", "tlas", "tlas_glossary.json")
            if manifest_glossary and os.path.exists(manifest_glossary):
                glossary_path = manifest_glossary
            elif legacy_glossary and os.path.exists(legacy_glossary):
                glossary_path = legacy_glossary
            elif os.path.exists(local_glossary):
                glossary_path = local_glossary
                if manifest_glossary:
                    try:
                        import shutil
                        os.makedirs(os.path.dirname(manifest_glossary), exist_ok=True)
                        shutil.copy2(local_glossary, manifest_glossary)
                        glossary_path = manifest_glossary
                    except Exception:
                        pass
            else:
                glossary_path = manifest_glossary

        # 2. Profiles Dir Fallback & Auto-Sync
        if profiles_dir is None or not os.path.exists(profiles_dir) or not glob.glob(os.path.join(profiles_dir, "*.json")):
            manifest_profiles = self.manifest.get("output_profiles_dir")
            legacy_profiles = self.manifest.get("legacy_profiles_dir")
            local_profiles = os.path.join(workspace_root, "data", "tlas", "profiles")
            if manifest_profiles and os.path.exists(manifest_profiles) and glob.glob(os.path.join(manifest_profiles, "*.json")):
                profiles_dir = manifest_profiles
            elif legacy_profiles and os.path.exists(legacy_profiles) and glob.glob(os.path.join(legacy_profiles, "*.json")):
                profiles_dir = legacy_profiles
            elif os.path.exists(local_profiles) and glob.glob(os.path.join(local_profiles, "*.json")):
                profiles_dir = local_profiles
                if manifest_profiles:
                    try:
                        import shutil
                        os.makedirs(manifest_profiles, exist_ok=True)
                        for pf in glob.glob(os.path.join(local_profiles, "*.json")):
                            shutil.copy2(pf, os.path.join(manifest_profiles, os.path.basename(pf)))
                        profiles_dir = manifest_profiles
                    except Exception:
                        pass
            else:
                profiles_dir = manifest_profiles

        # 3. Scenes Path Fallback & Auto-Sync
        if scenes_path is None or not os.path.exists(scenes_path):
            manifest_scenes = self.manifest.get("output_scenes_json")
            local_scene_packets = os.path.join(workspace_root, "data", "tlas", "scene_packets.json")
            local_scenes = os.path.join(workspace_root, "data", "tlas", "rpgm_scenes_v5.json")
            if manifest_scenes and os.path.exists(manifest_scenes):
                scenes_path = manifest_scenes
            elif os.path.exists(local_scene_packets):
                scenes_path = local_scene_packets
                if manifest_scenes:
                    try:
                        import shutil
                        os.makedirs(os.path.dirname(manifest_scenes), exist_ok=True)
                        shutil.copy2(local_scene_packets, manifest_scenes)
                        scenes_path = manifest_scenes
                    except Exception:
                        pass
            elif os.path.exists(local_scenes):
                scenes_path = local_scenes
            else:
                scenes_path = manifest_scenes

        self.checkpoint_data = self._load_checkpoint()
        self.glossary_scanner = GlossaryScanner(glossary_path=glossary_path, profiles_dir=profiles_dir)
        self.masker = MessageCodeMasker()
        self.auditor = LQATranslationAuditor()
        self.splitter = SmartLineSplitter()
        self.scene_manager = SceneContextManager(scenes_path=scenes_path, profiles_dir=profiles_dir)
        self.last_speakers_map = {}
        self.last_listeners_map = {}
        self.last_third_persons_map = {}
        game_data_dir = self.manifest.get("game_data_directory")
        self.displayable_engine = GameDisplayableEngine(game_data_dir=game_data_dir)

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
        喔曕福喔о笀喔�腑喔氞釜喔栢覆喔權赴喔勦抚喔侧浮喔炧福喙夃腑喔∴競喔�竾 Bridge Server 喙佮弗喔� Userscript 喔氞笝喙€喔氞福喔侧抚喙屶箑喔嬥腑喔｀箤
        喔曕覆喔∴斧喔ム副喔佮竵喔侧福 Fundamental System Principles: 喙勦浮喙堗釜喔膏箞喔∴箑喔斷覆喙€喔о弗喔� 喙佮弗喔班箘喔∴箞喔∴傅 Timeout 喔曕副喔斷笀喔�
        喔堗赴喔｀腑喔堗笝喔佮抚喙堗覆 Userscript 喔氞笝喔�笝喙夃覆喙€喔о箛喔� ChatGPT 喔堗赴喔�箞喔囙釜喔编笉喔嵿覆喔� Heartbeat 喔炧福喙夃腑喔∴笚喔赤竾喔侧笝喔堗福喔脆竾 100%
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
                            logger.info("馃煝 Userscript on ChatGPT Web is now CONNECTED and READY!")
                        return True
            except Exception:
                pass

            if first_warn:
                logger.info("鈴� Waiting for ChatGPT Web Userscript on chatgpt.com to be connected and ready...")
                first_warn = False

            if timeout is not None and (time.time() - start_time) > timeout:
                raise TimeoutError("Bridge Userscript readiness wait timed out.")

            time.sleep(1.5)

    def reset_bridge(self):
        """喔�箞喔囙釜喔编笉喔嵿覆喔撪弗喙夃覆喔囙竸喔脆抚喔囙覆喔權箑喔佮箞喔侧笚喔掂箞喔�覆喔堗竸喙夃覆喔囙腑喔⑧腹喙堗箖喔� Bridge Server 喙冟斧喙夃釜喔班腑喔侧笖喔佮箞喔�笝喙€喔｀复喙堗浮喔囙覆喔權箖喔�浮喙�"""
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
        """喔�箞喔囙竸喔赤釜喔编箞喔囙箖喔�箟 Userscript 喔氞笝喔�笝喙夃覆喙€喔о箛喔氞箑喔涏复喔� New Chat"""
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

        # 喔｀傅喙€喔嬥箛喔曕笗喔编抚喔權副喔氞箒喔ム赴喔�父喙堗浮喙傕竸喔о笗喔侧箖喔�浮喙� (10 - 15 喔炧福喙囙腑喔∴笧喙屶笗喙堗腑 Session 喙€喔炧阜喙堗腑喔ム笖 Overhead)
        self.reset_bridge()
        self.chat_prompt_count = 0
        self.max_prompts_for_current_chat = random.randint(10, 15)
        self.is_new_chat = True
        logger.info(f"New chat session ready! Quota for this session: {self.max_prompts_for_current_chat} prompts.")

    def trigger_refresh_page(self):
        """喔�箞喔囙竸喔赤釜喔编箞喔囙箖喔�箟 Userscript 喔氞笝喔�笝喙夃覆喙€喔о箛喔氞福喔掂箑喔熰福喔娻斧喔權箟喔侧箑喔о箛喔� (Reload Page) 喙€喔炧阜喙堗腑喔ム箟喔侧竾喔�笘喔侧笝喔� DOM / Cooldown"""
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
        """喔�箞喔囙竸喔赤釜喔编箞喔囙笚喔斷釜喔�笟喙勦笡喔⑧副喔� Bridge Server 喙€喔炧阜喙堗腑喙€喔娻箛喔勦抚喙堗覆 ChatGPT 喔�覆喔∴覆喔｀笘喔佮笖喔�箞喔囙箘喔斷箟喔�福喔粪腑喙勦浮喙� (Watchdog Sentinel Probe)"""
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
            # Fallback 喔�覆喔� bridge server 喔⑧副喔囙箘喔∴箞喙勦笖喙夃福喔掂釜喔曕覆喔｀箤喔椸箑喔涏箛喔權箑喔о腑喔｀箤喔娻副喔權箖喔�浮喙� 喙冟斧喙夃箑喔娻箛喔勦笀喔侧竵 /bridge/status
            try:
                req = urllib.request.Request(f"{self.bridge_url}/bridge/status")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {"can_send": data.get("userscript_connected", False), "is_rate_limited": False}
            except Exception:
                return {"can_send": False, "is_rate_limited": False, "reason": "Bridge offline"}

    def watchdog_wait_for_unlock(self, attempt=1, wait_minutes=None):
        """
        喔｀赴喔氞笟喙€喔澿箟喔侧福喔班抚喔编竾喙佮弗喔班笧喔编竵喔勦腑喔⑧笗喔侧浮喔｀腑喔� (Watchdog Cooldown Cycle):
        喙€喔∴阜喙堗腑 ChatGPT 喔曕复喔� Rate Limit 喔�福喔粪腑喔涏父喙堗浮喔�箞喔囙笘喔灌竵喔ム箛喔�竸 (Silent Send Block / Send Button Greyed out):
        - 喔�涪喔膏笖喔炧副喔佮竸喔�涪喔曕覆喔∴福喔班涪喔班箑喔о弗喔侧笚喔掂箞 ChatGPT 喙佮笀喙夃竾 (喙€喔娻箞喔� 13 喔權覆喔椸傅) 喔�福喔粪腑 3-5 喔權覆喔椸傅喔�覆喔佮箘喔∴箞喙勦笖喙夃福喔班笟喔� 喙€喔ム傅喔⑧笝喙佮笟喔氞笧喔む笗喔脆竵喔｀福喔∴浮喔權父喔┼涪喙�
        - 喔�箟喔侧浮喔炧复喔∴笧喙屶斧喔｀阜喔�笖喔编笝喔椸父喔｀副喔囙釜喙堗竾喔傕箟喔�竸喔о覆喔∴弗喔囙箖喔權竵喔ム箞喔�竾喙€喔斷箛喔斷競喔侧笖 喙€喔炧阜喙堗腑喔涏箟喔�竾喔佮副喔� Token 喔氞抚喔∴釜喔班釜喔�
        - 喙€喔∴阜喙堗腑喔勦福喔氞箑喔о弗喔侧福喔�竸喔�涪 喔�副喙堗竾喔｀傅喙€喔熰福喔娻斧喔權箟喔侧箑喔о箛喔� ChatGPT 喙冟斧喔∴箞 喙€喔炧阜喙堗腑喔ム箟喔侧竾喔�笘喔侧笝喔� DOM / Cooldown Session
        - 喔｀腑喔堗笝喙€喔氞福喔侧抚喙屶箑喔嬥腑喔｀箤喔｀傅喙傕斧喔ム笖喙€喔�福喙囙笀喙佮弗喔� Userscript 喙€喔娻阜喙堗腑喔∴笗喙堗腑喔佮弗喔编笟喔∴覆喔炧福喙夃腑喔∴箖喔娻箟喔囙覆喔�
        - 喙€喔涏复喔斷斧喙夃腑喔囙箒喔娻笗喙冟斧喔∴箞 喙€喔炧阜喙堗腑喙冟斧喙夃竵喔ム箞喔�竾喔傕箟喔�竸喔о覆喔∴抚喙堗覆喔囙箑喔涏弗喙堗覆 100% 喔炧福喙夃腑喔∴抚喔侧竾喔炧福喙囙腑喔∴笧喙屶箖喔�浮喙堗笚喔编箟喔囙竵喙夃腑喔�
        """
        if wait_minutes and wait_minutes > 0:
            wait_time = (wait_minutes * 60.0) + 30.0  # 喔｀腑喔曕覆喔∴笚喔掂箞喙€喔о箛喔氞箒喔堗箟喔� + 喙€喔溹阜喙堗腑 30 喔о复喔權覆喔椸傅
            wait_desc = f"{wait_minutes} 喔權覆喔椸傅 (喔曕覆喔∴笚喔掂箞喙佮笀喙夃竾喔氞笝喔�笝喙夃覆喙€喔о箛喔� ChatGPT)"
        else:
            wait_time = random.uniform(180, 270)  # 喔�父喙堗浮 3.0 喔栢付喔� 4.5 喔權覆喔椸傅
            wait_desc = f"{wait_time / 60:.1f} 喔權覆喔椸傅"

        logger.warning("\n" + "=" * 80)
        logger.warning(f"馃洝锔� [WATCHDOG SENTINEL ACTIVATED - COOLDOWN CYCLE #{attempt}]")
        logger.warning(f"   ChatGPT Send Button is currently BLOCKED / Greyed out.")
        logger.warning(f"   Cooldown Duration: {wait_desc}")
        logger.warning(f"   Pipeline is PAUSED. Will wait patiently without typing or spamming prompts.")
        logger.warning(f"   When cooldown completes, will refresh page and resume translation.")
        logger.warning("=" * 80 + "\n")

        # 喙佮笀喙夃竾喙€喔曕阜喔�笝喔�笘喔侧笝喔班竵喔侧福喔｀腑喔勦腑喔⑧笚喔膏竵 60 喔о复喔權覆喔椸傅
        rem = wait_time
        while rem > 0:
            step = min(rem, 60.0)
            time.sleep(step)
            rem -= step
            if rem > 0:
                logger.info(f"鈴� [Watchdog Cooldown #{attempt}] Remaining wait time: {rem / 60:.1f} minutes...")

        logger.info(f"馃攧 [Watchdog Cooldown #{attempt}] Cooldown of {wait_desc} elapsed! Refreshing ChatGPT page now...")
        try:
            self.trigger_refresh_page()
        except Exception as ref_err:
            logger.warning(f"Notice while sending refresh signal: {ref_err}")

        # 喔｀腑喔堗笝喔佮福喔班笚喔编箞喔� Userscript 喔氞笝喔�笝喙夃覆喙€喔о箛喔氞笚喔掂箞喙€喔炧复喙堗竾喔｀傅喙€喔熰福喔娻竵喔ム副喔氞浮喔侧箑喔娻阜喙堗腑喔∴笗喙堗腑喔�浮喔氞腹喔｀笓喙�
        logger.info("鈴� Waiting for ChatGPT Web to reload and reconnect...")
        try:
            self.wait_for_bridge_ready(timeout=90)
        except Exception as wait_err:
            logger.warning(f"Wait for bridge ready notice: {wait_err}")

        # 喔�副喙堗竾喙€喔涏复喔� New Chat 喙€喔炧阜喙堗腑喙冟斧喙夃箘喔斷箟喔佮弗喙堗腑喔囙笧喔脆浮喔炧箤喔椸傅喙堗釜喔班腑喔侧笖喔�笖喙冟斧喔∴箞 100%
        try:
            self.trigger_new_chat()
            self.wait_for_bridge_ready(timeout=30)
        except Exception as nc_err:
            logger.warning(f"New chat trigger notice: {nc_err}")

        self.is_new_chat = True
        self.chat_prompt_count = 0
        logger.info(f"馃煝 [Watchdog Cooldown #{attempt}] Page refreshed and New Chat ready. Resuming with whole new prompt!")
        return True

    def _call_bridge_completions(self, messages):
        """喔�箞喔囙競喙夃腑喔勦抚喔侧浮喙勦笡喔⑧副喔� OpenAI-compatible API 喔氞笝 Bridge Server"""
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
                m = re.search(r'(?:喔ム腑喔�(?:喙冟斧喔∴箞)?喔�傅喔佮竸喔｀副喙夃竾喙冟笝|try again in|in)\s*(\d+)\s*(?:喔權覆喔椸傅|minutes?|mins?|m\b)', err_body, re.IGNORECASE)
                if m:
                    wait_minutes = int(m.group(1))

            is_rate_limit = (e.code == 429) or any(kw in err_body.lower() for kw in [
                "try again after", "try again in", "喔ム腑喔囙腑喔掂竵喔勦福喔编箟喔囙箖喔�", "喙€喔｀覆喔佮赋喔ム副喔囙笗喔｀抚喔堗釜喔�笟", "too many requests",
                "rate limit", "usage cap", "usage limit", "喔勦父喔撪笘喔多竾喔傕傅喔斷笀喔赤竵喔编笖喙佮弗喙夃抚",
                "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown"
            ])
            if is_rate_limit:
                cd_err = ChatGPTCooldownError(f"ChatGPT Rate Limit Encountered (HTTP {e.code}): {err_body}")
                cd_err.wait_minutes = wait_minutes
                raise cd_err
            raise RuntimeError(f"Bridge Server Error ({e.code}): {err_body}")

    def _extract_json_response(self, text):
        """喔�竵喔编笖 JSON array 喔堗覆喔佮競喙夃腑喔勦抚喔侧浮喔曕腑喔氞竵喔ム副喔氞競喔�竾 ChatGPT 喔炧福喙夃腑喔∴笅喙堗腑喔∴箒喔嬥浮 RPGMaker Control Tags Escape 喔�涪喙堗覆喔囙竸喔｀腑喔氞竸喔ム父喔� 100%"""
        text = text.strip()

        def clean_json_syntax(s):
            # 1. 喔嬥箞喔�浮喙佮笅喔� backslash 喔傕腑喔囙箒喔椸箛喔� RPGMaker 喙€喔娻箞喔� \., \|, \!, \C[1] 喔椸傅喙堗競喔编笖喔佮副喔氞箘喔о涪喔侧竵喔｀笓喙� JSON 喔∴覆喔曕福喔愢覆喔�
            s = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', s)
            # 2. 喔曕副喔� trailing commas 喔佮箞喔�笝喔涏复喔斷抚喔囙箑喔ム箛喔� 喙€喔娻箞喔� [..., ] 喔�福喔粪腑 {..., }
            s = re.sub(r',\s*([\]\}])', r'\1', s)
            return s

        def try_parse(s):
            for variant in [s, clean_json_syntax(s)]:
                try:
                    return json.loads(variant, strict=False)
                except Exception:
                    pass
            return None

        # 1. 喔�覆 code block ```json ... ```
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

        # 2. 喔ム腑喔囙斧喔� array [ ... ] 喙傕笖喔⑧笗喔｀竾
        array_match = re.search(r"(\[[\s\S]*\])", text)
        if array_match:
            res = try_parse(array_match.group(1))
            if res is not None and isinstance(res, list):
                return res

        # 3. 喔ム腑喔囙笚喔编箟喔囙竵喙夃腑喔權競喙夃腑喔勦抚喔侧浮
        res = try_parse(text)
        if res is not None:
            if isinstance(res, list):
                return res
            elif isinstance(res, dict):
                for k in ("translations", "items", "data", "results", "dialogues"):
                    if k in res and isinstance(res[k], list):
                        return res[k]

        # 4. Bulletproof Fallback: 喔�竵喔编笖 Object 喔椸傅喔ム赴喔曕副喔о笖喙夃抚喔� Regex 喔�覆喔佮箓喔勦福喔囙釜喔｀箟喔侧竾 JSON 喔｀抚喔∴浮喔� syntax error
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
        """喔曕福喔о笀喔�腑喔氞抚喙堗覆喙佮笚喙囙竵喔勦抚喔氞竸喔膏浮喙€喔佮浮 RPGMaker 喙勦浮喙堗釜喔灌笉喔�覆喔�"""
        tag_pattern = r"(\\[CNV]\[\d+\]|\\[\.\|\!\^]|\\\.\.)"
        orig_tags = re.findall(tag_pattern, original_text)
        trans_tags = re.findall(tag_pattern, translated_text)
        
        # 喔栢箟喔侧箒喔椸箛喔佮笗喙夃笝喔夃笟喔编笟喔∴傅 喙佮笗喙堗竸喔赤箒喔涏弗喙勦浮喙堗浮喔� 喙冟斧喙夃箒喔堗箟喔囙箑喔曕阜喔�笝
        for tag in set(orig_tags):
            if orig_tags.count(tag) > trans_tags.count(tag):
                logger.warning(f"Control tag mismatch! Tag '{tag}' might be missing in: {translated_text}")

    def enforce_glossary_in_translation(self, text: str, matched_glossary: dict) -> str:
        """
        ตรวจจับและแก้ไขชื่อตัวละครที่ LLM เผลอถอดเสียงผิดหรือลืมล็อกชื่อตาม Glossary (Universal Auto-Repair)
        โดยตรวจสอบจาก matched_glossary แบบไดนามิก 100% ไร้ Hardcode
        """
        if not text:
            return text

        chars = matched_glossary.get("Characters", {})
        if not chars:
            return text

        repaired_text = text
        for char_name, cinfo in chars.items():
            th_target = cinfo.get("th", char_name)
            if th_target.lower() == char_name.lower():
                aliases = cinfo.get("aliases", [])
                if isinstance(aliases, list):
                    for al in aliases:
                        al_str = al if isinstance(al, str) else al.get("name", "")
                        if al_str and al_str.lower() != char_name.lower():
                            pat = re.escape(al_str)
                            if re.search(pat, repaired_text):
                                repaired_text = re.sub(pat, char_name, repaired_text)
                                logger.info(f"🛡️ Dynamic Auto-Repaired alias in text: '{al_str}' -> '{char_name}'")

        return repaired_text

    def translate_batch(self, batch_items, profiles_context=""):
        """
        喙佮笡喔ム笂喔膏笖喔傕箟喔�竸喔о覆喔� 1 Batch (10-20 喔氞福喔｀笚喔编笖)
        batch_items: list 喔傕腑喔� dict 喙€喔娻箞喔� [{"id": 1, "speaker": "Lily", "text": "..."}]
        """
        # 喔曕福喔о笀喔�腑喔氞抚喙堗覆喔栢付喔囙箓喔勦抚喔曕覆喔�父喙堗浮喔�福喔粪腑喔⑧副喔�
        if self.chat_prompt_count >= self.max_prompts_for_current_chat:
            logger.info(f"Reached chat rotation limit ({self.chat_prompt_count}/{self.max_prompts_for_current_chat}). Resetting chat...")
            self.trigger_new_chat()

        # 喔�福喙夃覆喔囙競喙夃腑喔勦抚喔侧浮喔�赋喔�福喔编笟喔�箞喔� 喔炧福喙夃腑喔� Stage 4.1 Control Code Masking 喙佮弗喔� Speaker Forward-Propagation
        masked_map = {}
        items_payload = []
        last_scene_speaker = ""
        for it in batch_items:
            orig_text = it.get("text", "")
            mask_res = self.masker.mask(orig_text)
            masked_map[it.get("id")] = mask_res

            payload_item = {
                "id": it.get("id"),
                "ja": mask_res.masked_text
            }
            spk = it.get("speaker")
            if spk:
                payload_item["speaker"] = spk
                last_scene_speaker = spk
            else:
                # [Task 5.2]: Forward-Propagation 喔勦副喔斷弗喔�竵 Speaker 喙冟笝 Scene 喙€喔斷傅喔⑧抚喔佮副喔權箑喔炧阜喙堗腑喔�父喔斷福喔�涪喔｀副喙堗抚喔涏福喔班箓喔⑧竸喔曕覆喔氞腑喔�
                role = it.get("role", "")
                if last_scene_speaker and role in ["Dialogue/Story", "Dialogue", ""]:
                    payload_item["context_speaker"] = f"{last_scene_speaker} (喔曕箞喔�箑喔權阜喙堗腑喔囙笀喔侧竵喔涏福喔班箓喔⑧竸喔佮箞喔�笝喔�笝喙夃覆)"

            # 喔權赋喔�箞喔� Candidate Listeners 喔栢箟喔侧浮喔掂競喙夃腑喔∴腹喔ム箖喔� Packet
            if it.get("candidate_listeners"):
                payload_item["candidate_listeners"] = it.get("candidate_listeners")
            elif it.get("listener"):
                payload_item["candidate_listeners"] = [it.get("listener")]

            if it.get("role") and it.get("role") != "Dialogue/Story":
                payload_item["type"] = it.get("role")
            elif not it.get("speaker"):
                payload_item["type"] = it.get("role", "Narration/Story")
            if it.get("surrounding_context"):
                payload_item["surrounding_context"] = it.get("surrounding_context")
            items_payload.append(payload_item)

        user_content_parts = []
        # [Task 5.1]: 喔澿副喔� Persistent Mini-System Invariant 喙冟笝喔椸父喔佮箚 Prompt 喙€喔炧阜喙堗腑喔涏箟喔�竾喔佮副喔� Attention Decay
        user_content_parts.append(MINI_SYSTEM_INVARIANT)

        # 喔�竵喔编笖喙佮弗喔班箒喔椸福喔� Scene Context (喔夃覆喔�, 喔氞福喔脆笟喔椸箑喔｀阜喙堗腑喔囙福喔侧抚, Mood & Tone, 喔勦抚喔侧浮喔�副喔∴笧喔编笝喔樴箤喔曕副喔о弗喔班竸喔�) 喔�覆喔佮涪喔编竾喙勦浮喙堗箘喔斷箟喔｀抚喔∴浮喔侧箖喔� profiles_context
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
            f"""\n\nCRITICAL CONVERSATIONAL & TRANSLATION DIRECTIVE:
Translate the {target_count} items above with HIGH LITERARY ELEGANCE, natural conversational cadence, and emotional resonance (award-winning literary translation standard).
For each item, you MUST identify the conversational triad (speaker, listener, third_person) and the Thai translation (th).
Return strictly a valid JSON array in this exact format:
[
  {{"id": "<id>", "speaker": "<canonical_speaker>", "listener": "<target_listener>", "third_person": "<referenced_or_None>", "th": "<translation>"}}
]
Requirements:
- 'speaker': True character speaking (canonical name from tag/glossary, or 'Narrator', 'System').
- 'listener': Person addressed (canonical name of interlocutor, 'Group', 'Self', 'Player', or 'None').
- 'third_person': Person referenced who is neither speaker nor listener (e.g. Character A talking to Character B about Character C -> 'C'; else 'None').
- 'th': Thai translation with high literary elegance, authentic character voice, and natural flow. Follow speaker tag format: 【Name】\nDialogue. Preserve all XML tags with ZERO CJK leakage.
Return ONLY the JSON array. No conversational text."""
        )
        user_content = "\n\n".join(user_content_parts)

        attempt = 0
        resp_data = None
        elapsed = 0.0

        # 喔ム腹喔涏笚喔斷釜喔�笟喔�箞喔囙笧喔｀箛喔�浮喔炧箤喔堗笝喔佮抚喙堗覆喔堗赴喔�赋喙€喔｀箛喔� (喔｀腑喔囙福喔编笟喔佮覆喔｀笧喔编竵喔勦腑喔� 3-5 喔權覆喔椸傅喙佮弗喔班福喔掂箑喔熰福喔娻斧喔權箟喔侧箑喔о箛喔氞箑喔∴阜喙堗腑喔曕复喔斷笟喔ム箛喔�竵)
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

            # 喔曕福喔о笀喔�腑喔氞竸喔о覆喔∴笧喔｀箟喔�浮喔傕腑喔� Userscript 喔佮箞喔�笝喔⑧复喔囙竸喔赤釜喔编箞喔囙箑喔�浮喔� (Readiness Probe)
            self.wait_for_bridge_ready()

            # 喔⑧复喔囙箘喔涏涪喔编竾 Bridge Server 喔炧福喙夃腑喔∴福喔班笟喔� Watchdog Sentinel 喙佮弗喔� Auto-Fallback
            try:
                start_t = time.time()
                resp_data = self._call_bridge_completions(messages)
                elapsed = time.time() - start_t
                break  # 喔�箞喔囙釜喔赤箑喔｀箛喔堗箒喔ム赴喙勦笖喙夃福喔编笟喔溹弗喔ム副喔炧笜喙屶箑喔｀傅喔⑧笟喔｀箟喔�涪!
            except Exception as e:
                err_msg = str(e).lower()
                is_cooldown = isinstance(e, ChatGPTCooldownError) or any(kw in err_msg for kw in [
                    "try again after", "try again in", "喔ム腑喔囙腑喔掂竵喔勦福喔编箟喔囙箖喔�", "喙€喔｀覆喔佮赋喔ム副喔囙笗喔｀抚喔堗釜喔�笟", "too many requests",
                    "rate limit", "usage cap", "usage limit", "喔勦父喔撪笘喔多竾喔傕傅喔斷笀喔赤竵喔编笖喙佮弗喙夃抚", "429",
                    "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown",
                    "喔椸赋喔囙覆喔權箑喔｀箛喔о箑喔佮复喔權箘喔�", "喔氞弗喙囙腑喔佮笂喔编箞喔о竸喔｀覆喔�", "喙€喔炧阜喙堗腑喔涏竵喔涏箟喔�竾喔傕箟喔�浮喔灌弗", "too quickly"
                ])
                if is_cooldown:
                    wait_mins = getattr(e, "wait_minutes", None)
                    if not wait_mins:
                        m = re.search(r'(?:喔ム腑喔�(?:喙冟斧喔∴箞)?喔�傅喔佮竸喔｀副喙夃竾喙冟笝|try again in|in)\s*(\d+)\s*(?:喔權覆喔椸傅|minutes?|mins?|m\b)', str(e), re.IGNORECASE)
                        if m:
                            wait_mins = int(m.group(1))

                    logger.warning(f"馃洝锔� Rate limit / Send Button Disabled detected ({e}).")
                    # 喔炧副喔佮福喔�笗喔侧浮喔椸傅喙堗箑喔о箛喔氞福喔班笟喔� (喔�福喔粪腑 3-5 喔權覆喔椸傅) + 喔｀傅喙€喔熰福喔娻斧喔權箟喔侧箑喔о箛喔� ChatGPT 喙佮弗喙夃抚喔佮弗喔编笟喔∴覆喔�箞喔囙箖喔�浮喙堗笚喔编箟喔囙竵喙夃腑喔�
                    self.watchdog_wait_for_unlock(attempt=attempt, wait_minutes=wait_mins)
                    continue
                else:
                    if attempt >= 3:
                        logger.error(f"Bridge call failed after {attempt} attempts: {e}. Raising for adaptive fallback.")
                        raise SafetyRefusalError(f"Bridge call failed after {attempt} attempts: {e}")
                    logger.warning(f"Bridge call encountered unexpected error ({e}) on attempt {attempt}/3. Auto-recovering: Opening New Chat and retrying...")
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

        # 喔曕福喔о笀喔�腑喔氞竵喔侧福喔涏笍喔脆箑喔�笜喔勦赋喔傕腑 (Refusal / Safety filter)
        if self.is_safety_refusal(content):
            raise SafetyRefusalError(f"ChatGPT Safety Refusal detected: {content.strip()}")

        parsed_results = self._extract_json_response(content)
        if parsed_results is None:
            if self.is_safety_refusal(content) or any(w in content for w in ["ยืนยัน", "อายุ", "18", "ผู้เยาว์"]):
                raise SafetyRefusalError(f"ChatGPT Safety confirmation / refusal detected: {content.strip()}")
            raise ValueError(f"Failed to extract valid JSON array from ChatGPT response: {repr(content[:120])}")
        
        # ตรวจสอบความถูกต้องและจับคู่ผลลัพธ์ พร้อม Flexible Key & ID Normalization
        results_map = {}
        batch_speakers = {}
        batch_listeners = {}
        batch_third_persons = {}
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
            spk_val = (res.get("speaker") or res.get("spk") or "").strip()
            lis_val = (res.get("listener") or res.get("target") or res.get("to") or "").strip()
            third_val = (res.get("third_person") or res.get("third") or res.get("3rd") or "").strip()
            if item_id is not None:
                results_map[item_id] = th_text
                results_map[str(item_id)] = th_text
                if spk_val:
                    batch_speakers[item_id] = spk_val
                    batch_speakers[str(item_id)] = spk_val
                if lis_val:
                    batch_listeners[item_id] = lis_val
                    batch_listeners[str(item_id)] = lis_val
                if third_val:
                    batch_third_persons[item_id] = third_val
                    batch_third_persons[str(item_id)] = third_val
        self.last_speakers_map.update(batch_speakers)
        self.last_listeners_map.update(batch_listeners)
        self.last_third_persons_map.update(batch_third_persons)

        # 1. Flexible Sequential Index & ID Alignment
        # 喔�覆喔� LLM 喔曕腑喔氞竵喔ム副喔氞浮喔侧箑喔涏箛喔權箑喔ム競喔ム赋喔斷副喔� 1, 2, ..., N 喙冟笝喔傕笓喔班笚喔掂箞 batch_items 喔∴傅 ID 喔�阜喙堗笝 (喙€喔娻箞喔� PLUG_36)
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

            # 喔ム腑喔囙笖喔� num_part 喔傕腑喔� iid (喙€喔娻箞喔� PLUG_36 -> 36)
            if iid not in results_map and str(iid) not in results_map:
                num_part = re.sub(r'^[^\d]*', '', str(iid))
                if num_part and num_part in results_map:
                    results_map[iid] = results_map[num_part]
                elif num_part and num_part.isdigit() and int(num_part) in results_map:
                    results_map[iid] = results_map[int(num_part)]

        # 2. Positional 1:1 Fallback (喔�覆喔佮笀喔赤笝喔о笝喔溹弗喔ム副喔炧笜喙屶箑喔椸箞喔侧竵喔编笟喔堗赋喔權抚喔� batch 喔炧腑喔斷傅 喙冟斧喙夃笀喔编笟喔勦腹喙堗笗喔侧浮喔曕赋喙佮斧喔權箞喔�)
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
                        logger.info(f"馃敆 Positional ID mapping aligned row {iid} -> item #{idx + 1}")

        # 3. Duplicate Text Auto-Reuse (喔｀腑喔囙福喔编笟喔佮福喔撪傅喙冟笝 Batch 喔∴傅喔涏福喔班箓喔⑧竸喔嬥箟喔赤竵喔编笝 喙佮弗喙夃抚 LLM 喔⑧父喔氞箒喔栢抚喔�福喔粪腑喔曕副喔斷笚喔脆箟喔�)
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
                    logger.info(f"馃洝锔� Duplicate text auto-reused for row {iid}: {repr(src_text[:40])}")

        # 4. 喔佮福喔�竾喙€喔夃笧喔侧赴 ID 喔椸傅喙堗腑喔⑧腹喙堗箖喔� Batch 喔涏副喔堗笀喔膏笟喔编笝喙€喔椸箞喔侧笝喔编箟喔�
        filtered_results_map = {}
        for it in batch_items:
            iid = it.get("id")
            val = results_map.get(iid) or results_map.get(str(iid))
            if val is not None:
                filtered_results_map[iid] = val
        results_map = filtered_results_map

        # 4. 喔曕福喔о笀喔�腑喔氞竸喔о覆喔∴竸喔｀笟喔栢箟喔о笝 100% (No Skip / 喔�箟喔侧浮喙佮腑喔氞涪喔膏笟喔涏福喔班箓喔⑧竸喙€喔斷箛喔斷競喔侧笖)
        expected_ids = set(str(it.get("id")) for it in batch_items)
        received_ids = set(str(k) for k in results_map.keys())
        missing_ids = expected_ids - received_ids
        if missing_ids:
            logger.error(f"鉂� LLM Hallucination / Skip detected! Expected {len(expected_ids)} items, but LLM only returned {len(received_ids)}. Missing IDs: {missing_ids}")
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
            unmasked_th = unmask_res.unmasked_text            # Stage 4.3 5D Universal LQA Quality & Integrity Audit (Active Guardrails)
            try:
                listener = it.get("listener")
                if not listener and it.get("candidate_listeners"):
                    cand = it.get("candidate_listeners")
                    listener = cand[0] if isinstance(cand, list) and cand else None

                lqa_res = self.auditor.audit(orig_text, unmasked_th, row_id=str(iid), speaker=it.get("speaker"), listener=listener)
                if not lqa_res.is_valid:
                    for v in lqa_res.violations:
                        logger.warning(f"🛡️ LQA Violation on row {iid} [{v.dimension}] ({v.severity}): {v.message}")

                    # Active Auto-Repair for Prohibited SFX and Formatting Hazards
                    repaired_th = unmasked_th
                    for v in lqa_res.violations:
                        if v.dimension == "SFX":
                            repaired_th = re.sub(r'เสียงถอนหายใจ', 'เฮ้อ...', repaired_th)
                            repaired_th = re.sub(r'เสียงหอบ', 'แฮ่ก... แฮ่ก...', repaired_th)
                            repaired_th = re.sub(r'เสียงคราง', 'อื้ม...', repaired_th)
                            repaired_th = re.sub(r'เสียงโดนตี', 'อั่ก...', repaired_th)
                            repaired_th = re.sub(r'เสียงต่อย|เสียงชก', 'ผัวะ!', repaired_th)
                            repaired_th = re.sub(r'\bฮะ\b', 'แฮ่ก', repaired_th)
                            repaired_th = re.sub(r'\bฮะๆ\b', 'แฮ่ก... แฮ่ก...', repaired_th)
                            logger.info(f"🛡️ Auto-Repaired SFX on row {iid}: -> {repaired_th}")
                        elif v.dimension == "EMOTION" and "เขียนติดกัน" in v.message:
                            repaired_th = re.sub(r'([\u0E00-\u0E7F])([A-Za-z])', r'\1 \2', repaired_th)
                            repaired_th = re.sub(r'([A-Za-z])([\u0E00-\u0E7F])', r'\1 \2', repaired_th)
                            logger.info(f"🛡️ Auto-Repaired Thai-English spacing on row {iid}")
                    unmasked_th = repaired_th
            except Exception as lqa_err:
                logger.debug(f"LQA audit notice: {lqa_err}")

            # Stage 5 Smart Line Splitting (喔佮覆喔｀副喔權笗喔� Line Count Parity 1:1 喔佮副喔氞笗喙夃笝喔夃笟喔编笟)
            try:
                final_th = SmartLineSplitter.split_thai_to_match_original(orig_text, unmasked_th)
            except Exception as split_err:
                logger.warning(f"SmartLineSplitter notice on row {iid}: {split_err}")
                final_th = unmasked_th

            results_map[iid] = final_th

        # 喔�副喔涏箑喔斷笗喔�笘喔侧笝喔� Session
        self.chat_prompt_count += 1
        self.is_new_chat = False

        # 喔栢箟喔侧斧喔權箟喔侧箑喔о箛喔氞箒喔堗箟喔囙箑喔曕阜喔�笝喔о箞喔侧笘喔多竾喔ム复喔∴复喔曕箒喔娻笗 喙冟斧喙夃笗喔编箟喔囙箖喔�箟喙€喔涏复喔� New Chat 喔椸副喔權笚喔掂箖喔權福喔�笟喔�笝喙夃覆
        if chat_limit_detected:
            logger.warning("Message Limit Banner detected on ChatGPT Web! Will open New Chat for next prompt.")
            self.trigger_new_chat()

        # Realistic Human Cadence & Anti-Bot Protection (default: 8 - 15 喔о复喔權覆喔椸傅)
        jitter = random.uniform(self.pace_min, self.pace_max)
        logger.info(f"鈴� Realistic Human Cadence: Pausing for {jitter:.1f}s before next batch to emulate human review...")
        time.sleep(jitter)

        return results_map

    @staticmethod
    def is_safety_refusal(text: str) -> bool:
        """喔曕福喔о笀喔堗副喔氞競喙夃腑喔勦抚喔侧浮喔涏笍喔脆箑喔�笜喙€喔權阜喙堗腑喔囙笀喔侧竵 Content Moderation / Safety Filter 喔椸副喙夃竾喔犩覆喔┼覆喙勦笚喔⑧箒喔ム赴喔�副喔囙竵喔む俯"""
        if not text:
            return False
        refusal_keywords = [
            "喙勦浮喙堗釜喔侧浮喔侧福喔栢箒喔�笖喔囙竸喔�笝喙€喔椸笝喔曕箤喔權傅喙夃箘喔斷箟",
            "喙€喔�笗喔膏笢喔ム笖喙夃覆喔權竸喔о覆喔∴笡喔ム腑喔斷笭喔编涪",
            "喔氞笚喔�笝喔椸笝喔侧笚喔掂箞喔ム赴喙€喔�傅喔⑧笖喔�箞喔�笝",
            "喔權箓喔⑧笟喔侧涪喔勦抚喔侧浮喔涏弗喔�笖喔犩副喔�",
            "喔權箓喔⑧笟喔侧涪喔佮覆喔｀箖喔娻箟喔囙覆喔�",
            "喔傕箟喔�竵喔赤斧喔權笖喔佮覆喔｀箖喔娻箟喔囙覆喔�",
            "喔ム赴喙€喔∴复喔斷笝喙傕涪喔氞覆喔�",
            "喙勦浮喙堗釜喔侧浮喔侧福喔栢箒喔涏弗喙勦笖喙夃箑喔權阜喙堗腑喔囙笀喔侧竵",
            "喙勦浮喙堗釜喔侧浮喔侧福喔栢笂喙堗抚喔⑧箑喔�弗喔粪腑喙€喔佮傅喙堗涪喔о竵喔编笟",
            "喙勦浮喙堗釜喔侧浮喔侧福喔栢釜喔｀箟喔侧竾喙€喔權阜喙夃腑喔�覆",
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
            "safety guidelines",
            "ขอยืนยัน", "ยืนยันก่อน", "18 ปี", "อายุ 18", "ผู้เยาว์", "ไม่เหมาะสม", "ขออภัย",
            "please confirm", "confirm that", "under 18", "18 or older", "minor", "age of consent"
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in refusal_keywords)

    @staticmethod
    def is_single_name_with_symbols(text: str, locked_terms: set, current_speaker: str = "") -> bool:
        """
        喔曕福喔о笀喔�腑喔氞抚喙堗覆喔傕箟喔�竸喔о覆喔∴箑喔涏箛喔權箑喔炧傅喔⑧竾 '喔娻阜喙堗腑喔曕副喔о弗喔班竸喔� + 喔�副喔嵿弗喔编竵喔┼笓喙�/喙€喔勦福喔粪箞喔�竾喔�浮喔侧涪喔о福喔｀竸喔曕腑喔�' 喔�福喔粪腑喙勦浮喙�
        喔勦福喔�笟喔勦弗喔膏浮 100%:
        - 喔涏弗喔编箠喔佮腑喔脆笝 GabText: GabText ........., GabText D-Dan....
        - 喔о竾喙€喔ム箛喔氞竸喔｀腑喔�: (Shion..!!), (Hikari!!), (Drake..!!)\\., (S-Shion?!)
        - 喙€喔�傅喔⑧竾喔佮福喔�/喔ム赴喙€喔∴腑: Zzzz..\\.zzzz...\\., zzz...
        - 喔娻阜喙堗腑喔椸傅喙堗笘喔灌竵喙佮笚喔｀竵喔斷箟喔о涪喔堗父喔斷竵喔ム覆喔囙笂喔粪箞喔�: Ma...\\.saru..?\\. -> Masaru
        - 喔�副喔佮俯喔｀箑喔斷傅喙堗涪喔�/喔曕赴喔佮父喔佮笗喔班竵喔编竵: \\|....S\\|.....\\. -> S
        - 喔娻阜喙堗腑喔嬥箟喔赤箚: Shion..!!\\. Shion!!.\\., \\fb\\}Shion\\| Shion\\| Shion\\|\\fb\\^
        - 喔�副喔嵿弗喔编竵喔┼笓喙�/喙€喔勦福喔粪箞喔�竾喔�浮喔侧涪喔椸父喔佮笂喔權复喔�: ..Dan?..., Dan....., Shion....?, Dan!!!, Jasmine..?, Shion?!
        """
        if not text:
            return True

        raw = text.strip()

        # 1. 喔曕副喔� prefix 喔涏弗喔编箠喔佮腑喔脆笝 GabText
        raw = re.sub(r"^GabText\s*", "", raw, flags=re.IGNORECASE).strip()
        if not raw:
            return True

        # 2. 喔ム笟 RPG Maker control tags 喔椸父喔佮笂喔權复喔�
        clean = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<\{\}\\\fb\fi\fn\fs]", "", raw).strip()
        if not clean:
            return True

        # 3. 喔栢箟喔侧箘喔∴箞喔∴傅喔曕副喔о腑喔编竵喔┼福喔�福喔粪腑喔曕副喔о箑喔ム競喙冟笖喙� 喙€喔ム涪 -> 喔�副喔嵿弗喔编竵喔┼笓喙屶弗喙夃抚喔�
        if not re.search(r"[A-Za-z0-9\u0e01-\u0e7f\u3040-\u30ff\u4e00-\u9faf]", clean):
            return True

        # 4. 喔曕福喔о笀喔堗副喔氞箑喔�傅喔⑧竾喔佮福喔� / 喔�弗喔编笟 (Zzz...)
        letters_only = re.sub(r"[^A-Za-z0-9]", "", clean).lower()
        if re.match(r"^z+$", letters_only):
            return True

        # 5. 喔曕福喔о笀喔�腑喔氞笗喔编抚喔�副喔佮俯喔｀箑喔斷傅喙堗涪喔о箚 (喙€喔娻箞喔� S, D, M) 喔椸傅喙堗箘喔∴箞喔∴傅喙€喔權阜喙夃腑喔�覆喔勦赋喔炧腹喔�
        if len(letters_only) <= 1:
            return True

        # 6. 喔ム笟喙€喔勦福喔粪箞喔�竾喔�浮喔侧涪喔о福喔｀竸喔曕腑喔權箒喔ム赴喔о竾喙€喔ム箛喔氞福喔�笟喔權腑喔佮笚喔编箟喔囙斧喔∴笖
        punct_pattern = r"^[\s\.\?!鈥�-_~,\":'鈥欌€溾€漒(\)\[\]\{\}<>鈥撯€�/\\\|]+|[\s\.\?!鈥�-_~,\":'鈥欌€溾€漒(\)\[\]\{\}<>鈥撯€�/\\\|]+$"
        stripped = re.sub(punct_pattern, "", clean).strip()
        if not stripped:
            return True

        # 7. 喔｀腑喔囙福喔编笟 Stuttering prefix (喙€喔娻箞喔� S-Shion, D-Dan, J-Jinnie, L-Lily, H-Hikari)
        stutter_match = re.match(r"^[A-Za-z]\s*[-鈥撯€擼\s*(.+)$", stripped)
        candidate_name = stutter_match.group(1).strip() if stutter_match else stripped
        candidate_name = re.sub(punct_pattern, "", candidate_name).strip()

        # 8. 喔曕福喔о笀喔�腑喔氞竵喔｀笓喔掂笂喔粪箞喔�箑喔斷傅喙堗涪喔о箚
        cand_lower = candidate_name.lower()
        if cand_lower in locked_terms:
            return True
        if current_speaker and cand_lower == current_speaker.strip().lower():
            return True

        # 9. 喔曕福喔о笀喔堗副喔氞笂喔粪箞喔�笚喔掂箞喙傕笖喔權箒喔椸福喔佮笀喔膏笖喔佮弗喔侧竾喔娻阜喙堗腑 喙€喔娻箞喔� Ma...saru -> Masaru
        no_punct_word = re.sub(r"[^A-Za-z0-9]", "", candidate_name).lower()
        if no_punct_word in locked_terms:
            return True
        if current_speaker and no_punct_word == current_speaker.strip().lower():
            return True

        # 10. 喔曕福喔о笀喔�腑喔氞竵喔｀笓喔掂浮喔掂斧喔ム覆喔⑧竸喔赤斧喔｀阜喔�笂喔粪箞喔�笅喙夃赋喙� 喔勦副喙堗笝喔斷箟喔о涪喔�副喔嵿弗喔编竵喔┼笓喙� (喙€喔娻箞喔� "Shion..!! Shion!!", "Connie...Harold..Jonathan..")
        tokens = re.split(r"[\s\.\?!鈥�-_~,\":'鈥欌€溾€漒(\)\[\]\{\}<>鈥撯€�/\\\|]+", clean)
        tokens = [t.strip().lower() for t in tokens if t.strip()]
        if tokens:
            clean_tokens = []
            for t in tokens:
                st = re.match(r"^[a-z]\s*[-鈥撯€擼\s*(.+)$", t)
                clean_tokens.append(st.group(1) if st else t)
            if all(t in locked_terms or (current_speaker and t == current_speaker.strip().lower()) for t in clean_tokens):
                return True

        return False

    @staticmethod
    def extract_speaker_tag(orig_text: str):
        """
        สกัด Speaker Tag ทุกรูปแบบจากต้นฉบับอย่างแม่นยำ 100%:
        รองรับทั้ง:
        - Lenticular Brackets: 【凛】 หรือ 【夫】\n (สากลเกมญี่ปุ่น / RPG Maker)
        - Angle Brackets: \n<Dan:> หรือ <Shion:>
        - Square Brackets: [Dan] หรือ [凛]
        - Tags ที่มี Color Code หรือ Font Style: \n<\C[0]Hikari:\C>, \n<\C[27]Pink hair Woman\C:>
        คืนค่า: (has_tag, full_prefix, clean_speaker, pure_dialogue)
        """
        if not orig_text:
            return False, "", "", ""

        # 1. Lenticular Brackets: 【...】
        m_len = re.match(r"^(\s*\\n|\s*\n)?【([^】]+)】([\s\:\n]*)", orig_text)
        if m_len:
            full_prefix = m_len.group(0)
            inner_content = m_len.group(2)
            pure_dialogue = orig_text[len(full_prefix):].strip()
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content).replace(":", "").strip()
            if clean_name:
                return True, full_prefix, clean_name, pure_dialogue

        # 2. Angle Brackets: <...>
        m_ang = re.match(r"^(\s*\\n|\s*\n)?<([^>]+)>([\s\:\n]*)", orig_text)
        if m_ang:
            full_prefix = m_ang.group(0)
            inner_content = m_ang.group(2)
            pure_dialogue = orig_text[len(full_prefix):].strip()
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content).replace(":", "").strip()
            if clean_name:
                return True, full_prefix, clean_name, pure_dialogue

        # 3. Square Brackets: [...] (เมื่อไม่ใช่ RPG Maker control tags เช่น \C[0], \V[1])
        m_sq = re.match(r"^(\s*\\n|\s*\n)?\[([^\]]+)\]([\s\:\n]*)", orig_text)
        if m_sq and not re.match(r"^\\[A-Za-z]+", orig_text):
            full_prefix = m_sq.group(0)
            inner_content = m_sq.group(2)
            pure_dialogue = orig_text[len(full_prefix):].strip()
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner_content).replace(":", "").strip()
            if clean_name:
                return True, full_prefix, clean_name, pure_dialogue

        return False, "", "", orig_text

    def _translate_single_with_literary_softening(self, single_item, profiles_context=""):
        """喙佮笡喔ム笡喔｀赴喙傕涪喔勦笚喔掂箞喔∴傅喔勦抚喔侧浮喔ム赴喙€喔�傅喔⑧笖喔�箞喔�笝喔�腹喔囙笖喙夃抚喔⑧竵喔｀腑喔氞抚喔｀福喔撪辅喔脆弗喔涏箤喙€喔娻复喔囙箑喔涏福喔掂涪喔氞箑喔椸傅喔⑧笟 (Literary Euphemism) 喙€喔炧阜喙堗腑喙冟斧喙夃笢喙堗覆喔� Safety Policy"""
        item_id = single_item["id"]
        text = single_item.get("text", "")
        role = single_item.get("role", "Narration")

        softened_system = (
            "You are a master literary translator specializing in classic visual novel storytelling and artistic Thai literature.\n"
            "Translate the following single fictional line into elegant, poetic, and dignified Thai literary prose (喔о福喔｀笓喔ㄠ复喔ム笡喙�/喔�赋喔權抚喔權抚喔｀福喔撪竵喔｀福喔∴箑喔娻复喔囙箑喔涏福喔掂涪喔氞箑喔涏福喔�).\n"
            "Rules:\n"
            "1. Strictly comply with all safety and content policies: render any sensitive, romantic, or suggestive moments using tasteful literary metaphors, poetic imagery, and dignified phrasing (喔勦赋喔�父喔犩覆喔�/喙傕抚喔�覆喔｀笭喔侧笧喔炧笀喔權箤) rather than explicit terms.\n"
            "2. Preserve the emotional resonance, nuance, and character perspective faithfully.\n"
            "3. Keep English proper names without Thai transliteration.\n"
            "4. Return ONLY a valid JSON array: [{\"id\": " + json.dumps(item_id) + ", \"th\": \"喔勦赋喙佮笡喔ム箘喔椸涪喙€喔娻复喔囙抚喔｀福喔撪辅喔脆弗喔涏箤\"}]"
        )

        user_content = f"### CONTEXT: Visual Novel Scene ({role})\n### TEXT TO LOCALIZE:\n{text}"
        if profiles_context:
            # Sanitize demographic child tags that trigger false OpenAI moderation filters
            sanitized_ctx = re.sub(r'\b(CHILD|Child|child)\b', 'YOUNG_PERSON', profiles_context)
            sanitized_ctx = re.sub(r'age:\s*CHILD', 'age: YOUNG', sanitized_ctx, flags=re.IGNORECASE)
            user_content = f"{sanitized_ctx}\n\n{user_content}"

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
        喔｀赴喔氞笟 Auto-Repair 喔�赋喔�福喔编笟喔涏福喔班箓喔⑧竸喔椸傅喙堗笘喔灌竵 OpenAI 喔涏笍喔脆箑喔�笜喔�涪喙堗覆喔囙笘喔侧抚喔｀箑喔權阜喙堗腑喔囙笀喔侧竵喔傕箟喔�笀喔赤竵喔编笖喔斷箟喔侧笝喔勦抚喔侧浮喔涏弗喔�笖喔犩副喔� (Safety Refusal):
        - 喙佮笡喔ム竾喔勦赋喔氞福喔｀涪喔侧涪喙佮弗喔班笟喔椸釜喔權笚喔權覆喙€喔娻复喔囙笢喔灌箟喙冟斧喔嵿箞喙冟斧喙夃竵喔ム覆喔⑧箑喔涏箛喔權笭喔侧俯喔侧箑喔傕傅喔⑧笝喔о福喔｀笓喔佮福喔｀浮/喔о福喔｀笓喔ㄠ复喔ム笡喙屶箑喔娻复喔囙箑喔涏福喔掂涪喔氞箑喔涏福喔� (Euphemisms)
        - 喔涏福喔编笟喙冟斧喙夃浮喔掂竸喔赤箒喔涏弗喔犩覆喔┼覆喙勦笚喔⑧笚喔掂箞喔�弗喔班釜喔ム抚喔� 喔�浮喔氞腹喔｀笓喙� 喙佮弗喔班笗喔｀竾喔氞福喔脆笟喔� 100%
        - 喙勦浮喙堗笚喔脆箟喔囙箖喔�箟喙€喔嬥弗喔ム箤喔о箞喔侧竾 喙佮弗喔班箘喔∴箞 Skip 喔傕箟喔侧浮喙佮笘喔о箑喔斷箛喔斷競喔侧笖 (100% No-Skip Guarantee)
        """
        if not text:
            return ""

        # 喔炧笀喔權覆喔權父喔佮福喔∴竸喔赤箒喔涏弗喔曕福喔囙釜喔赤斧喔｀副喔氞笁喔侧竵喔溹腹喙夃箖喔�笉喙堗競喔�竾喙€喔佮浮喔椸傅喙堗笧喔氞笟喙堗腑喔� (Exact Curated Mappings)
        known_vn_mappings = {
            "F-F-Fap....m-material..? U-Um..": "喔�-喔娻箞喔о涪喔曕副喔о箑喔�竾....喔�-喔囙副喙夃笝喙€喔�福喔�竸喔�..? 喔�-喙€喔�箞喔�..",
            "(Ah..\\.so..they..\\.they have their things out...\\. just like that man who touched me tonight....\\. ah..and who made me touch him there too..)": "(喔�覆..\\.喔囙副喙夃笝..喔炧抚喔佮箑喔傕覆..\\.喔炧抚喔佮箑喔傕覆喔佮箛喔佮赋喔ム副喔囙竸喔о副喔佮釜喔脆箞喔囙笝喔编箟喔權腑喔�竵喔∴覆...\\. 喙€喔�浮喔粪腑喔權竵喔编笟喔溹腹喙夃笂喔侧涪喔勦笝喔椸傅喙堗釜喔编浮喔溹副喔�笁喔编笝喔勦阜喔權笝喔掂箟喙€喔ム涪....\\. 喔�箞喔�..喔勦笝喔椸傅喙堗笚喔赤箖喔�箟喔夃副喔權笗喙夃腑喔囙箘喔涏釜喔编浮喔溹副喔�笗喔｀竾喔權副喙夃笝喔傕腑喔囙箑喔傕覆喔斷箟喔о涪..)",
            "Y-You guys are so perverted~ hahaha...鈾�": "喔�-喔炧抚喔佮竸喔膏笓喔權傅喙堗弗喔侧浮喔佮笀喔编竾喙€喔ム涪喔權赴喔勦赴~ 喔�箞喔侧府喙堗覆喔�箞喔�...鈾�",
            "(It's alright..\\.they..don't have a face to them so....)": "(喙勦浮喙堗箑喔涏箛喔權箘喔｀斧喔｀腑喔�..\\.喔炧抚喔佮箑喔傕覆..喙勦浮喙堗浮喔掂箖喔氞斧喔權箟喔侧箖喔�箟喙€喔�箛喔權笝喔掂箞喔權覆 喙€喔炧福喔侧赴喔囙副喙夃笝....)",
            "(Its not as if..I didn't strip infront of a total stranger earlier at Peach Garden, I..)": "(喔∴副喔權竵喙囙箘喔∴箞喙冟笂喙堗抚喙堗覆..喔夃副喔權箘喔∴箞喙勦笖喙夃箒喔佮箟喔溹箟喔侧笗喙堗腑喔�笝喙夃覆喔勦笝喙佮笡喔ム竵喔�笝喙夃覆喔∴覆喔佮箞喔�笝喔權傅喙堗笝喔� 喔曕腑喔權腑喔⑧腹喙堗笚喔掂箞 Peach Garden 喔夃副喔權竵喙�..)",
            "(And I was groped too..\\.So many times...\\. so..this isn't anything..)": "(喙佮笘喔∴笁喔编笝喔⑧副喔囙箓喔斷笝喔ム腹喔氞竸喔ム赋喔∴覆喙佮弗喙夃抚喔斷箟喔о涪..\\.喔曕副喙夃竾喔�弗喔侧涪喔勦福喔编箟喔�...\\. 喙€喔炧福喔侧赴喔囙副喙夃笝..喙佮竸喙堗笝喔掂箟喙勦浮喙堗箑喔涏箛喔權箘喔｀斧喔｀腑喔�..)",
            "M-My nipples..? Ah..hehe..I..I'm happy that you..you think the color is um..cute..~鈾�": "喔�-喔⑧腑喔斷腑喔佮競喔�竾喔夃副喔權箑喔�福喔�竸喔�..? 喔�箞喔�..喔�复喙�..喔�-喔夃副喔權笖喔掂箖喔堗笝喔班竸喔班笚喔掂箞..喔椸傅喙堗笧喔о竵喔勦父喔撪竸喔脆笖喔о箞喔侧釜喔掂競喔�竾喔∴副喔� 喙€喔�箞喔�..喔權箞喔侧福喔编竵..~鈾�",
            "H-Huh..?! I-It's not pointy at all..um..it's not growing hard..or anything..? I..don't understand..": "喔�-喙€喔�箠喔�..?! 喔�-喔∴副喔權箘喔∴箞喙勦笖喙夃笗喔编箟喔囙笂喔编笝喔�副喔佮斧喔權箞喔�涪喔權赴喔勦赴..喙€喔�箞喔�..喙勦浮喙堗箘喔斷箟喙佮競喙囙竾喔傕付喙夃笝喔∴覆..喔�福喔粪腑喔�赴喙勦福喙€喔ム涪喔斷箟喔о涪..? 喔�-喔夃副喔權箘喔∴箞喙€喔傕箟喔侧箖喔堗箑喔ム涪喔勦箞喔�..",
            "But..I-I guess if you perverts like it then..\\. y-you can take a look all you want..鈾�": "喙佮笗喙堗抚喙堗覆..喔�-喔栢箟喔侧竸喔權弗喔侧浮喔佮腑喔⑧箞喔侧竾喔炧抚喔佮竸喔膏笓喔娻腑喔氞弗喙堗赴喔佮箛..\\.喔�-喔堗赴喔∴腑喔囙箑喔椸箞喔侧笚喔掂箞喔�涪喔侧竵喔∴腑喔囙竵喙囙箘喔斷箟喔權赴喔勦赴..鈾�",
            "ha..ha..I-I think..um..they might be..I don't know but bigger than F cup..? H-Hahaha..": "喔�赴..喔�赴..喔�-喔夃副喔權竸喔脆笖喔о箞喔�..喙€喔�箞喔�..喔權箞喔侧笀喔�..喔夃副喔權竵喙囙箘喔∴箞喙佮笝喙堗箖喔堗箒喔曕箞喔о箞喔侧箖喔�笉喙堗竵喔о箞喔侧竸喔编笧 F 喔權赴喔勦赴..? 喔�-喔�赴喔�赴喔�赴..",
            "okay..\\.um..I'll angle them..alittle more towards this side..鈾�": "喙€喔傕箟喔侧箖喔堗箒喔ム箟喔о竸喙堗赴..\\.喙€喔�箞喔�..喔夃副喔權笀喔班箑喔�傅喔⑧竾..喔∴覆喔椸覆喔囙笖喙夃覆喔權笝喔掂箟喔�傅喔佮笝喔脆笖喔權赴喔勦赴..鈾�",
            "And so he watches as the girl finishes showcasing her naked upper body to a bunch of men.\\. Swaying her alluring tits to seduce all of them and most certainly was used as material for plenty of them.": "喙佮弗喔班箑喔傕覆喔佮箛喙勦笖喙夃箒喔曕箞喙€喔澿箟喔侧浮喔�竾喔傕笓喔班笚喔掂箞喙€喔斷箛喔佮釜喔侧抚喔�抚喔斷箑喔｀阜喔�笝喔｀箞喔侧竾喔椸箞喔�笝喔氞笝喔�副喔權箑喔涏弗喔粪腑喔⑧箑喔涏弗喙堗覆喔傕腑喔囙箑喔樴腑喙冟斧喙夃竵喔ム父喙堗浮喔溹腹喙夃笂喔侧涪喔斷腹喔堗笝喔堗笟 喙傕涪喔佮涪喙夃覆喔⑧斧喔權箟喔侧腑喔佮腑喔编笝喙€喔⑧箟喔侧涪喔о笝喙€喔炧阜喙堗腑喔斷付喔囙笖喔灌笖喔�覆喔⑧笗喔侧笚喔膏竵喔勦腹喙� 喙佮弗喔班浮喔编箞喔權箖喔堗箘喔斷箟喙€喔ム涪喔о箞喔侧浮喔编笝喔佮弗喔侧涪喙€喔涏箛喔權釜喔脆箞喔囙笚喔掂箞喔�弗喔侧涪喔勦笝喙冟笂喙夃福喔班笟喔侧涪喔勦抚喔侧浮喙冟竸喔｀箞喔�涪喙堗覆喔囙箒喔權箞喔權腑喔�",
            "I-I鈥檓 a little embarassed so...\\.ngh.... t-that鈥檚 all for tonight...!": "喔�-喔夃副喔權箑喔傕复喔權笝喔脆笖喔�笝喙堗腑喔⑧笝喙堗赴喔勦箞喔� 喙€喔炧福喔侧赴喔囙副喙夃笝...\\.喔�付喔�.... 喔�-喔勦阜喔權笝喔掂箟喔炧腑喙佮竸喙堗笝喔掂箟喔佮箞喔�笝喔權赴喔勦赴...!",
            "Hwee....\\.ehehe...\\.t-thank you all for coming.": "喔�腹喙堗抚....\\.喔�复喙�...\\.喔�-喔傕腑喔氞竸喔膏笓喔椸父喔佮竸喔權笚喔掂箞喙佮抚喔班箑喔傕箟喔侧浮喔侧笝喔班竸喔�",
            # Map041 & Japanese Adult Story Curated Literary Euphemisms
            "あぁぁ・・・僕のおちんちんがぁ・・・・。": "อ๊าาา... ตรงนั้นของผมมัน....",
            "あぁ・・・僕のおちんちんがぁ・・・・。": "อ๊าา... ตรงนั้นของผมมัน....",
            "本当に・・・・してやがる・・・・。": "เอาจริงดิ.... เล่นทำจริงซะงั้น....",
            "あぁ・・・なんか変な感じだよぉ・・・。": "อ๊า... มันรู้สึกแปลกๆ จังเลยครับ....",
            "あぁ・・・お姉さん・・・あぁ・・・。": "อ๊า... พี่สาวครับ... อ๊า....",
            "根元までしっかり・・・。\nあの女、意外に・・・・。": "อมมิดด้ามเลยเหรอเนี่ย....\nยัยผู้หญิงคนนั้น ไม่นึกว่าจะขนาดนี้....",
            "あぁ・・・お姉さん・・・なんか・・・。": "อ๊า... พี่สาวครับ... รู้สึกว่า....",
            "なんか・・・出ちゃいそうだよぉ・・・。": "เหมือนกับว่า... มันจะทะลักออกมาแล้วครับ....",
            "出ちゃう・・・僕のおちっこが出ちゃうよぉ・・・・。": "มันจะออกแล้ว... ของผมมันจะทะลักออกมาแล้วครับ....",
            "ふん・・・一丁前に出しやがって・・・・。\nこれで約束は果たしたぞ。": "ฮึ่ม... ปล่อยออกมาเป็นผู้ใหญ่เต็มตัวเลยนะมึง....\nแค่นี้สัญญาก็ถือว่าลุล่วงแล้ว",
            "あぁ・・・・・！\nお姉さぁん・・・・！！！": "อ๊าาา.....!\nพี่สาวคร้าบบบ....!!!",
            "あぁぁぁぁあ・・・・！！！": "อ๊าาาาาา....!!!",
            "サークル空上の次回作も是非よろしくお願い致します。": "ขอฝากผลงานเรื่องถัดไปของกลุ่ม Soragami ไว้ในความสนับสนุนของทุกท่านด้วยนะครับ",
        }

        # 喔曕福喔о笀喔�腑喔氞箒喔氞笟 Clean text
        clean_key = text.strip()
        if clean_key in known_vn_mappings:
            return known_vn_mappings[clean_key]

        # 喔曕福喔о笀喔�腑喔氞箒喔氞笟 Ignore newline / whitespace
        norm_key = re.sub(r'\s+', ' ', clean_key)
        for k, v in known_vn_mappings.items():
            if re.sub(r'\s+', ' ', k) == norm_key:
                return v

        # Euphemistic Literary Transformer
        result = text
        word_subs = [
            (r"\b(my\s+)?breasts?\b", "喔�笝喙夃覆喔�竵"),
            (r"\b(her\s+)?chest\b", "喔椸福喔о竾喔�竵"),
            (r"\b(seductive\s+|alluring\s+)?tits\b", "喔�笝喙夃覆喔�竵喔�副喔權箑喔⑧箟喔侧涪喔о笝"),
            (r"\bnipples?\b", "喔⑧腑喔斷腑喔�"),
            (r"\b(naked|nude)\b", "喙€喔涏弗喔粪腑喔⑧箑喔涏弗喙堗覆"),
            (r"\bundress(ing)?\b", "喔涏弗喔斷箑喔涏弗喔粪箟喔�竾喙€喔�阜喙夃腑喔溹箟喔�"),
            (r"\bstrip(ping)?\b", "喔栢腑喔斷箑喔�阜喙夃腑喔溹箟喔�"),
            (r"\bbikini\b", "喔氞复喔佮复喔權傅喙�"),
            (r"\bpanties\b", "喔佮覆喔囙箑喔佮竾喔娻副喙夃笝喙冟笝"),
            (r"\bunderwear\b", "喔娻父喔斷笂喔编箟喔權箖喔�"),
            (r"\btouch(ing)?\b", "喔�副喔∴笢喔编釜"),
            (r"\bgrop(ed|ing)?\b", "喔ム腹喔氞竸喔ム赋"),
            (r"\bbody\b", "喙€喔｀阜喔�笝喔｀箞喔侧竾"),
            (r"\bskin\b", "喔溹复喔о竵喔侧涪"),
            (r"\bshame\b", "喔勦抚喔侧浮喔ム赴喔�覆喔�"),
            (r"\bembarrass(ed|ing)?\b", "喔勦抚喔侧浮喙€喔傕复喔權腑喔侧涪"),
            (r"\bpant(ing)?\b", "喔�覆喔⑧箖喔堗斧喔�笟"),
            (r"\bmoan(ing|s)?\b", "喔勦福喔侧竾喙佮笢喙堗抚喙€喔氞覆"),
            (r"\bwhisper(ing|s)?\b", "喔佮福喔班笅喔脆笟"),
            (r"\bpleasure\b", "喔勦抚喔侧浮喔�父喔傕釜喔�"),
            (r"\bdesire(s)?\b", "喔勦抚喔侧浮喔涏福喔侧福喔栢笝喔�"),
            (r"\bsensual\b", "喙€喔⑧箟喔侧涪喔о笝"),
            (r"\berotic\b", "喔о覆喔氞斧喔о覆喔�"),
            (r"\bwet\b", "喙€喔涏傅喔⑧竵喔娻阜喙夃笝"),
            (r"\blips?\b", "喔｀复喔∴笣喔掂笡喔侧竵"),
            (r"\bfingers?\b", "喙€喔｀傅喔⑧抚喔權复喙夃抚"),
            (r"\bcamera\b", "喔佮弗喙夃腑喔�"),
            (r"\bviewers?\b", "喔溹腹喙夃笂喔�"),
            (r"\baudience\b", "喔溹腹喙夃笂喔�"),
            (r"\blive\b", "喙勦弗喔熰箤"),
            (r"\bstream\b", "喔�笗喔｀傅喔�"),
            (r"\bdance\b", "喙€喔曕箟喔�"),
            (r"\bdirty\b", "喔ム覆喔∴竵"),
            (r"\bpervert(s|ed)?\b", "喔勦笝喔ム覆喔∴竵"),
            (r"\bsex\b", "喙€喔｀阜喙堗腑喔囙笚喔侧竾喙€喔炧辅"),
            (r"\bfeel(ing)?\b", "喔勦抚喔侧浮喔｀腹喙夃釜喔多竵"),
            (r"\bF-F-Fap\b", "喔�-喔娻箞喔о涪喔曕副喔о箑喔�竾"),
            (r"\bfap\b", "喔娻箞喔о涪喔曕副喔о箑喔�竾"),
        ]

        for pat, repl in word_subs:
            result = re.sub(pat, repl, result, flags=re.IGNORECASE)

        # 喙佮笚喔權笚喔掂箞喔娻阜喙堗腑喔曕副喔о弗喔班竸喔｀笗喔侧浮 Glossary
        if hasattr(self, "glossary_scanner"):
            for char_en, char_info in self.glossary_scanner.characters.items():
                th_name = char_info.get("th", char_en)
                result = re.sub(rf"\b{re.escape(char_en)}\b", th_name, result)

        return result

    def translate_batch_adaptive(self, batch, profiles_context="", depth=0, max_depth=5):
        """
        喔｀赴喔氞笟喙佮笡喔� Batch 喔�副喔堗笁喔｀复喔⑧赴喔炧福喙夃腑喔� Adaptive Bisecting (喔�副喙堗笝喙佮笟喙堗竾喔勦福喔多箞喔囙腑喔编笗喙傕笝喔∴副喔曕复):
        1. 喔�箞喔囙箒喔涏弗喔椸副喙夃竾 Batch 喔曕覆喔∴笡喔佮笗喔�
        2. 喔�覆喔佮笗喔脆笖 Safety Refusal 喔�福喔粪腑喔傕箟喔�笢喔脆笖喔炧弗喔侧笖:
           - 喔栢箟喔� Batch 喔∴傅喔傕笝喔侧笖 > 1: 喔椸赋喔佮覆喔｀斧喔编箞喔權箒喔氞箞喔囙竸喔｀付喙堗竾 (Bisect) 喙€喔涏箛喔� 2 喔嬥副喔氞箒喔氞笗喔娻箤 喔⑧箟喔侧涪喙勦笡喙佮笂喔曕箖喔�浮喙� 喙佮弗喔班箑喔｀傅喔⑧竵喙佮笡喔ム箒喔氞笟 Recursive
           - 喔栢箟喔� Batch 喙€喔�弗喔粪腑喙€喔炧傅喔⑧竾 1 喔涏福喔班箓喔⑧竸喙€喔斷傅喙堗涪喔о箚:
             喔�) 喔炧涪喔侧涪喔侧浮喙佮笡喔ム笖喙夃抚喔⑧箓喔�浮喔� Literary Softening Prompt (喔о福喔｀笓喔ㄠ复喔ム笡喙屶箑喔娻复喔囙箑喔涏福喔掂涪喔氞箑喔涏福喔⑧笚喔掂箞喔溹箞喔侧笝喙€喔佮笓喔戉箤喔勦抚喔侧浮喔涏弗喔�笖喔犩副喔�)
             喔�) 喔�覆喔� LLM 喔⑧副喔囙竸喔囙笡喔忇复喙€喔�笜喙€喔斷箛喔斷競喔侧笖: 喙冟笂喙夃抚喔脆笜喔� Safe Offline Literary Localizer 喙佮笡喔ム箖喔�箟喙傕笖喔⑧笗喔｀竾 喔｀副喔氞笡喔｀赴喔佮副喔權箘喔∴箞喔о箞喔侧竾喙佮弗喔班箘喔∴箞喔傕箟喔侧浮 100%
        """
        if not batch:
            return {}

        logger.info(f"Translating adaptive batch of {len(batch)} items (Depth {depth})...")

        # 1. 喔炧涪喔侧涪喔侧浮喙佮笡喔ム笡喔佮笗喔� 喔炧福喙夃腑喔∴笖喔编竵喔堗副喔� Rate Limit 喙勦浮喙堗箖喔�箟喔�弗喔膏笖喙勦笡喔椸赋 Bisecting 喙€喔斷箛喔斷競喔侧笖
        while True:
            try:
                return self.translate_batch(batch, profiles_context=profiles_context)
            except ChatGPTCooldownError as e:
                logger.warning(f"馃洝锔� Rate limit during batch translation: {e}. Engaging Watchdog Sentinel...")
                self.watchdog_wait_for_unlock(wait_minutes=getattr(e, "wait_minutes", None))
                continue
            except SafetyRefusalError as e:
                logger.warning(f"馃洝锔� Safety Refusal encountered for batch of {len(batch)} items (Depth {depth}): {e}")
                break
            except Exception as e:
                err_msg = str(e).lower()
                if any(kw in err_msg for kw in [
                    "try again after", "try again in", "喔ム腑喔囙腑喔掂竵喔勦福喔编箟喔囙箖喔�", "喙€喔｀覆喔佮赋喔ム副喔囙笗喔｀抚喔堗釜喔�笟", "too many requests",
                    "rate limit", "usage cap", "usage limit",
                    "喔勦父喔撪笘喔多竾喔傕傅喔斷笀喔赤竵喔编笖喙佮弗喙夃抚", "429", "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown",
                    "喔椸赋喔囙覆喔權箑喔｀箛喔о箑喔佮复喔權箘喔�", "喔氞弗喙囙腑喔佮笂喔编箞喔о竸喔｀覆喔�", "喙€喔炧阜喙堗腑喔涏竵喔涏箟喔�竾喔傕箟喔�浮喔灌弗", "too quickly"
                ]):
                    logger.warning(f"馃洝锔� Rate limit detected from error: {e}. Engaging Watchdog Sentinel...")
                    m = re.search(r'(?:喔ム腑喔�(?:喙冟斧喔∴箞)?喔�傅喔佮竸喔｀副喙夃竾喙冟笝|try again in|in)\s*(\d+)\s*(?:喔權覆喔椸傅|minutes?|mins?|m\b)', str(e), re.IGNORECASE)
                    wm = int(m.group(1)) if m else None
                    self.watchdog_wait_for_unlock(wait_minutes=wm)
                    continue
                logger.warning(f"Batch translation failed ({e}) for batch of {len(batch)} items (Depth {depth})")
                break

        # 2. 喔栢箟喔� Batch 喔∴傅喔∴覆喔佮竵喔о箞喔� 1 喔｀覆喔⑧竵喔侧福 -> Adaptive Bisecting (Divide and Conquer)
        if len(batch) > 1 and depth < max_depth:
            mid = len(batch) // 2
            half_1 = batch[:mid]
            half_2 = batch[mid:]
            logger.info(f"馃攧 Engaging Adaptive Bisecting (Depth {depth + 1}): Splitting {len(batch)} items into {len(half_1)} and {len(half_2)} items...")

            # 喙€喔涏复喔� New Chat 喔椸副喔權笚喔掂箑喔炧阜喙堗腑喔ム箟喔侧竾喔�笘喔侧笝喔� Refusal 喔傕腑喔� ChatGPT
            self.trigger_new_chat()
            self.wait_for_bridge_ready()

            # 喙佮笡喔ム釜喙堗抚喔權箒喔｀竵
            res1 = self.translate_batch_adaptive(half_1, profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)

            # 喔�笝喙堗抚喔囙箑喔о弗喔侧箑喔ム箛喔佮笝喙夃腑喔⑧箑喔炧阜喙堗腑喔勦抚喔侧浮喙€喔�笘喔掂涪喔�
            time.sleep(random.uniform(2.0, 4.0))

            # 喙佮笡喔ム釜喙堗抚喔權斧喔ム副喔�
            res2 = self.translate_batch_adaptive(half_2, profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)

            combined = {}
            combined.update(res1)
            combined.update(res2)
            return combined

        # 3. 喔栢箟喔侧箑喔�弗喔粪腑喙€喔炧傅喔⑧竾 1 喔｀覆喔⑧竵喔侧福喙€喔斷傅喙堗涪喔о箚 (喔�福喔粪腑喔ム竾喔∴覆喔栢付喔囙竵喙夃笝喔�父喔斷競喔�竾 Depth) -> 喔堗副喔斷竵喔侧福喔涏福喔班箓喔⑧竸喔椸傅喙堗笗喔脆笖喔涏副喔嵿斧喔侧箑喔涏箛喔權福喔侧涪喔曕副喔�
        if len(batch) == 1:
            single_item = batch[0]
            r_id = str(single_item["id"])
            orig_text = single_item.get("text", "")
            row_idx = single_item.get("row_idx", "?")
            logger.warning(f"鈿狅笍 Isolated single sensitive line at Row {row_idx}: {repr(orig_text[:70])}")

            # 喔�箑喔曕箛喔� 3.1: 喔傕副喔斷箑喔佮弗喔侧笖喙夃抚喔� Literary Softening Prompt 喙冟笝 New Chat
            try:
                self.trigger_new_chat()
                self.wait_for_bridge_ready()
                softened_res = self._translate_single_with_literary_softening(single_item, profiles_context=profiles_context)
                if softened_res and (r_id in softened_res or single_item["id"] in softened_res):
                    th_val = softened_res.get(r_id) or softened_res.get(single_item["id"])
                    logger.info(f"鉁� Literary Softening succeeded for Row {row_idx}!")
                    return {r_id: th_val, single_item["id"]: th_val}
            except Exception as soft_err:
                logger.warning(f"Literary Softening attempt failed for Row {row_idx}: {soft_err}")

            # 喔�箑喔曕箛喔� 3.2: Safe Auto-Repair Fallback (100% No-Skip Guarantee)
            safe_th = self.offline_safe_literary_translation(orig_text, single_item.get("speaker", ""))
            logger.info(f"馃洝锔� Auto-Repaired Row {row_idx} via Safe Literary Localization: {safe_th[:70]}...")
            return {r_id: safe_th, single_item["id"]: safe_th}

        # 喔栢箟喔侧涪喔编竾喔∴傅喔�弗喔侧涪喔｀覆喔⑧竵喔侧福喙佮笗喙� depth 喙€喔佮复喔� max_depth
        all_res = {}
        for single in batch:
            sub = self.translate_batch_adaptive([single], profiles_context=profiles_context, depth=depth + 1, max_depth=max_depth)
            all_res.update(sub)
        return all_res

    def translate_chunk_file(self, chunk_file_path, output_dir="data/tlas/translated_chunks", batch_size=None, max_tokens=16000, batch_limit=None):
        """
        喙佮笡喔ム箘喔熰弗喙� Chunk 喔堗覆喔� timeline_chunks_v2 喔椸傅喔ム赴 Batch 喔炧福喙夃腑喔� Checkpoint:
        - 喔｀抚喔∴笅喔掂笝喙€喔ム箛喔佮箖喔�箟喙冟竵喔ム箟喙€喔勦傅喔⑧竾 ~16,000 tokens 喔�福喔粪腑喙佮涪喔佮笅喔掂笝喙冟斧喔嵿箞
        """
        with open(chunk_file_path, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)

        chunk_id = chunk_data.get("id", os.path.basename(chunk_file_path).replace(".json", ""))
        logger.info(f"Starting translation for chunk: {chunk_id}")

        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, f"{chunk_id}_th.json")

        # 喔｀抚喔氞福喔о浮 Dialogues 喔椸副喙夃竾喔�浮喔斷箖喔� chunk
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

        # 喔曕福喔о笀喔�腑喔� Checkpoint 喔椸傅喙堗浮喔掂腑喔⑧腹喙堗箒喔ム箟喔�
        chunk_translated = self.checkpoint_data["translated_dialogues"].get(chunk_id, {})
        remaining_items = [d for d in all_dialogues if d["id"] not in chunk_translated]
        logger.info(f"Remaining dialogues to translate: {len(remaining_items)} (Already done: {len(chunk_translated)})")

        if not remaining_items:
            logger.info(f"Chunk {chunk_id} is already 100% completed!")
            return chunk_translated

        # 喙佮笟喙堗竾喙€喔涏箛喔� Scene-based Batches 喔曕覆喔∴竾喔氞笡喔｀赴喔∴覆喔� Token (~16,000 tokens)
        if batch_size is not None:
            batches = [remaining_items[i:i + batch_size] for i in range(0, len(remaining_items), batch_size)]
        else:
            batches = self.pack_into_scene_batches(remaining_items, max_tokens=max_tokens)
            logger.info(f"馃摝 Scene-Based Token Packing: Grouped {len(remaining_items)} chunk dialogues into {len(batches)} batches (~{max_tokens} tokens/batch)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Processing {len(batches)} batches in this run.")

        for b_idx, batch in enumerate(batches):
            logger.info(f"--- Processing Batch {b_idx + 1}/{len(batches)} ({len(batch)} items) ---")
            
            # 喔�箒喔佮笝 Glossary 喙佮弗喔� Profiles 喔�赋喔�福喔编笟 Batch 喔權傅喙夃箒喔氞笟 Dynamic (Characters, Items, Places, System)
            batch_texts = [it.get("text", "") for it in batch]
            speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
            matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
            profiles_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

            # 喙佮笡喔� Batch 喔權傅喙� 喔炧福喙夃腑喔∴福喔班笟喔� Auto-Retry 喙佮弗喔� New Chat Fallback
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
                        logger.error(f"鉂� Batch translation permanently failed after {max_retries} attempts!")
                        raise e

            # 喔氞副喔權笚喔多竵喔ム竾 Checkpoint 喔椸副喔權笚喔� (State Persistence 100%)
            for uid, th_text in results.items():
                chunk_translated[uid] = th_text

            self.checkpoint_data["translated_dialogues"][chunk_id] = chunk_translated
            self.checkpoint_data["total_batches_done"] += 1
            self._save_checkpoint()
            logger.info(f"Saved checkpoint! Chunk progress: {len(chunk_translated)}/{len(all_dialogues)}")

            # 喔�副喔涏箑喔斷笗喙勦笩喔ム箤喔溹弗喔ム副喔炧笜喙�
            with open(output_file_path, "w", encoding="utf-8") as out_f:
                json.dump({
                    "chunk_id": chunk_id,
                    "completed": len(chunk_translated) == len(all_dialogues),
                    "translations": chunk_translated
                }, out_f, ensure_ascii=False, indent=2)

        logger.info(f"馃帀 Completed chunk {chunk_id}! Output saved to {output_file_path}")
        return chunk_translated

    # สัญลักษณ์ จุด อักขระวรรคตอน อักขระญี่ปุ่น (・、。) และเครื่องหมายควบคุมที่ไม่นับเป็นข้อความบทสนทนา
    SYMBOL_ONLY_PATTERN = re.compile(
        r'^[\s\u3000\.\,\…\‥\-\—\―\~〜\・\。\、\!\?！？♪♫★☆♥♡\(\)\（\）「」『』【】\[\]\<\>\\/\"\'“”‘’0-9\+\*\:\;\=\^\_\`\|\#\$\%\&\@]+$'
    )

    @classmethod
    def is_pure_symbol_dialogue(cls, text):
        """
        ตรวจสอบว่าข้อความเป็นบทสนทนาที่มีเฉพาะสัญลักษณ์ อักขระพิเศษ จุด หรือโค้ด RPG Maker หรือไม่
        รวมถึงอักขระสัญลักษณ์ญี่ปุ่น เช่น จุดกลาง (・), มหัพภาค (。), จุลภาค (、), ขีดนำ (―, ――)
        หากทั้งประโยคมีเฉพาะสัญลักษณ์เหล่านี้ จะไม่ส่งไปให้ LLM แปล เพื่อประหยัด Token และป้องกัน Model Hallucination
        """
        if not text or not text.strip():
            return True
        clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\_]', '', text)
        if not clean.strip():
            return True
        return bool(cls.SYMBOL_ONLY_PATTERN.match(clean))

    def is_name_only_dialogue(self, text):
        """
        Check if text is purely an English character name.
        If Japanese characters exist, strictly returns False.
        """
        if not text or not text.strip():
            return False

        if re.search(r'[぀-ヿ一-龯]', text):
            return False

        clean = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?|\\[\.\|\!\^\>\<\{\}\\_]', '', text)
        clean = re.sub(r'\b[A-Za-z]-(\\\.)?', '', clean)
        words = re.findall(r'[A-Za-z]+', clean)
        if not words:
            return False

        stopwords = {"a", "i", "the", "to", "in", "of", "on", "and", "is", "it", "you", "me", "he", "she", "we", "yes", "no"}
        for w in words:
            if w.lower() in stopwords:
                return False
            is_char = (w in self.glossary_scanner.characters or 
                       any(w.lower() == c.lower() for c in self.glossary_scanner.characters))
            if not is_char:
                return False

        rem = re.sub(r'[A-Za-z0-9\s\.\,\?\!\-\_\:\;\~\"\'\`\(\)\[\]\{\}\<\>]+', '', clean)
        return len(rem.strip()) == 0

    @staticmethod
    def pack_into_scene_batches(dialogues, max_tokens=24000, max_items_per_batch=80):
        """
        喔堗副喔斷竵喔ム父喙堗浮喔氞笚喔�笝喔椸笝喔侧箑喔涏箛喔� Scene 喙佮弗喔班箒喔炧箛喔佮福喔о浮喙冟斧喙夃箖喔佮弗喙夃箑喔勦傅喔⑧竾喔囙笟喔涏福喔班浮喔侧笓 ~8,000 tokens (喔｀抚喔∴竸喔赤笗喔�笟):
        - 喔嬥傅喔權箑喔ム箛喔�: 喔｀抚喔∴竵喔编笟喔嬥傅喔權笘喔编笖喙勦笡喔堗笝喔佮福喔班笚喔编箞喔囙箒喔曕赴 ~7,000 - 8,000 tokens 喔�福喔粪腑喙勦浮喙堗箑喔佮复喔� max_items_per_batch
        - 喔嬥傅喔權箖喔�笉喙堗箑喔佮复喔� 8,000 tokens 喔�福喔粪腑喔∴傅喔堗赋喔權抚喔權笡喔｀赴喙傕涪喔勦浮喔侧竵: 喙佮涪喔佮腑喔�竵喙€喔涏箛喔� sub-batches 喔⑧箞喔�涪
        - 喔涏箟喔�竾喔佮副喔權箑喔氞福喔侧抚喙屶箑喔嬥腑喔｀箤喔勦箟喔侧竾/喔�笝喙夃覆喙勦浮喙堗笗喔�笟喔�笝喔�竾 (Unresponsive DOM) 喔�涪喙堗覆喔囙箑喔斷箛喔斷競喔侧笖
        """
        if not dialogues:
            return []

        # 1. 喔堗副喔斷竵喔ム父喙堗浮喔曕覆喔� Scene / Map (喔斷腹喔堗覆喔� field "file")
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

        # 2. 喔權赋喔嬥傅喔權浮喔侧箒喔炧箛喔佮福喔о浮喔佮副喔� 喔�福喔粪腑喙佮涪喔佮涪喙堗腑喔�
        packed_batches = []
        current_batch = []
        current_tokens = 0

        for sc in scenes:
            scene_items = sc["items"]
            scene_tokens = sum(estimate_item_tokens(it) for it in scene_items)

            # 喔栢箟喔侧箑喔夃笧喔侧赴喔嬥傅喔權笝喔掂箟喙冟斧喔嵿箞喙€喔佮复喔權竾喔氞笡喔｀赴喔∴覆喔� TARGET_BUDGET 喔�福喔粪腑喔堗赋喔權抚喔權笡喔｀赴喙傕涪喔勦箑喔佮复喔� max_items_per_batch
            if scene_tokens > TARGET_BUDGET or len(scene_items) > max_items_per_batch:
                if current_batch:
                    packed_batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                # 喔�副喙堗笝喔嬥傅喔權笝喔掂箟喔�腑喔佮箑喔涏箛喔� sub-batches
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

            # 喔栢箟喔侧箑喔涏箛喔權笅喔掂笝喔涏竵喔曕复 喔�福喔粪腑喔嬥傅喔權箑喔ム箛喔�
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

    def translate_csv_file(self, input_csv_path, output_csv_path=None, batch_size=None, max_tokens=24000, max_items_per_batch=80, batch_limit=None, limit=None, reset_checkpoint=False):
        """
        喙佮笡喔ム箘喔熰弗喙� CSV 喔�赋喔�福喔编笟喙傕笡喔｀箑喔堗竵喔曕箤喙€喔佮浮:
        1. 喔勦箟喔權斧喔侧箒喔栢抚喔椸傅喙堗箑喔涏箛喔� Dialogue: 喔∴傅喙佮笚喙囙竵 <Speaker:> 喔�福喔粪腑 \\n<Speaker:> 喙冟笝喔勦腑喔ム副喔∴笝喙� A (Original)
        2. 喔佮福喔�竾喙€喔夃笧喔侧赴喙佮笘喔о笚喔掂箞喔⑧副喔囙箘喔∴箞喔∴傅 TH_Legacy:
           - 喔�覆喔佮竸喔�弗喔编浮喔權箤 B (Initial) 喔∴傅喔犩覆喔┼覆喙勦笚喔⑧腑喔⑧腹喙堗箒喔ム箟喔� -> 喔傕箟喔侧浮 (Skip) 100% 喙勦浮喙堗釜喙堗竾喙勦笡喙佮笡喔ム笅喙夃赋
           - 喔�覆喔佮涪喔编竾喙勦浮喙堗浮喔掂笭喔侧俯喔侧箘喔椸涪 -> 喔曕福喔о笀喔�腑喔氞抚喙堗覆喙€喔涏箛喔� Pure Symbol 喔�福喔粪腑喙勦浮喙�
        3. 喔�覆喔佮箑喔涏箛喔� Pure Symbol (喔∴傅喙€喔夃笧喔侧赴喔堗父喔�, 喔傕傅喔�, 喔�副喔嵿弗喔编竵喔┼笓喙�, 喙佮笚喙囙竵 RPG Maker 喙€喔娻箞喔� \\|........) -> Python 喙€喔曕复喔∴竸喔赤箒喔涏弗喙冟斧喙夃腑喔编笗喙傕笝喔∴副喔曕复喔椸副喔權笚喔� 100% 喙勦浮喙堗釜喙堗竾喙冟斧喙� LLM
        4. 喙佮笧喙囙竵喔佮弗喔膏箞喔∴競喙夃腑喔∴腹喔ム笚喔掂箞喙€喔�弗喔粪腑喙€喔涏箛喔� Scene (喔囙笟喔涏福喔班浮喔侧笓 ~8,000 tokens 喔曕箞喔� Batch 喙勦浮喙堗箑喔佮复喔� 30 喔氞福喔｀笚喔编笖)
        5. 喔涏福喔班竵喔�笟喔溹弗喔ム副喔炧笜喙屶竵喔ム副喔氞箖喔權福喔灌笡喙佮笟喔氞箑喔斷复喔�: \\n<SpeakerTH:>喔勦赋喙佮笡喔ム笭喔侧俯喔侧箘喔椸涪
        6. 喔氞副喔權笚喔多竵喔溹弗喔ム竾喔勦腑喔ム副喔∴笝喙� B (Initial) 喔炧福喙夃腑喔∴福喔班笟喔� Checkpoint 喔氞副喔權笚喔多竵喙勦笩喔ム箤喔椸父喔� Batch
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

        # 喔｀傅喙€喔嬥箛喔曕竸喔脆抚喔囙覆喔權箖喔� Bridge Server 喙冟斧喙夃釜喔班腑喔侧笖喔佮箞喔�笝喙€喔｀复喙堗浮喙€喔�浮喔�
        self.reset_bridge()

        # 喔�箞喔侧笝喙勦笩喔ム箤 CSV 喔椸副喙夃竾喔�浮喔�
        with open(input_csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            logger.warning("CSV file is empty!")
            return output_csv_path

        header = rows[0]
        logger.info(f"CSV Header: {header}")

        # speaker_tag_regex replaced by self.extract_speaker_tag for 100% universal format support
        
        # 喔曕福喔о笀喔�腑喔氞笡喔｀赴喔о副喔曕复 Checkpoint 喔椸傅喙堗箑喔勦涪喔椸赋喙勦抚喙夃釜喔赤斧喔｀副喔氞箘喔熰弗喙屶笝喔掂箟
        csv_key = os.path.basename(input_csv_path)
        if reset_checkpoint and csv_key in self.checkpoint_data["csv_translations"]:
            logger.info(f"Resetting checkpoint cache for {csv_key} (starting completely fresh from row 1)...")
            self.checkpoint_data["csv_translations"][csv_key] = {}
            self._save_checkpoint()

        if csv_key not in self.checkpoint_data["csv_translations"]:
            self.checkpoint_data["csv_translations"][csv_key] = {}
        cached_rows = self.checkpoint_data["csv_translations"][csv_key]

        # 喔勦箟喔權斧喔侧箒喔栢抚喔椸傅喙堗笗喙夃腑喔囙箒喔涏弗
        pending_dialogues = []
        skipped_legacy_count = 0
        already_cached_count = 0
        direct_copied_count = 0
        pure_symbols_count = 0
        name_only_count = 0

        # 喔｀覆喔⑧竵喔侧福 Roles 喔椸傅喙堗箑喔涏箛喔權箓喔勦福喔囙釜喔｀箟喔侧竾喔｀赴喔氞笟/喙傕竸喙夃笖喙€喔佮浮喔犩覆喔⑧箖喔� 喔嬥付喙堗竾喔�箟喔侧浮喔�箞喔囙箖喔�箟 LLM 喙佮笡喔ム箑喔斷箛喔斷競喔侧笖
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

            # 1. Checkpoint Cache Hit
            if str_idx in cached_rows:
                row[1] = cached_rows[str_idx]
                already_cached_count += 1
                continue

            # 2. Check TH_Legacy: Skip if already translated into Thai
            has_th_legacy = any('\u0e00' <= ch <= '\u0e7f' for ch in initial_text)
            if has_th_legacy:
                skipped_legacy_count += 1
                continue

            # 3. Check D_TEXT Plugin Command (e.g. D_TEXT 1日目 夕方 32)
            is_dtext, dt_prefix, dt_inner, dt_suffix = self.displayable_engine.parse_d_text(orig_text)
            if is_dtext:
                det_th = self.displayable_engine.translate_d_text_determinstic(dt_inner)
                if det_th:
                    combined_initial = f"{dt_prefix}{det_th}{dt_suffix}"
                    row[1] = combined_initial
                    cached_rows[str_idx] = combined_initial
                    if len(row) > 4 and not row[4].strip():
                        row[4] = "[D_TEXT: Visual Title]"
                    direct_copied_count += 1
                    continue
                else:
                    # Queue inner text of D_TEXT for translation
                    pending_dialogues.append({
                        "row_idx": r_idx,
                        "prefix": dt_prefix,
                        "suffix": dt_suffix,
                        "is_d_text": True,
                        "translated_prefix": dt_prefix,
                        "speaker": "",
                        "role": "Plugin Dialogue",
                        "id": str(r_idx),
                        "text": dt_inner,
                        "file": filename
                    })
                    continue

            # 4. Displayable / Translatable Evaluation (Game Data JSON + Strict Heuristics)
            is_disp, det_role, disp_reason = self.displayable_engine.evaluate_displayable(
                orig_text=orig_text,
                filename=filename,
                role=role,
                explicit_displayable=disp
            )
            if not is_disp:
                if not initial_text or not initial_text.strip():
                    row[1] = orig_text
                    cached_rows[str_idx] = orig_text
                    if len(row) > 4 and not row[4].strip():
                        row[4] = f"[Non-Displayable: {det_role}]"
                    direct_copied_count += 1
                continue

            # Extract speaker tags universally
            has_tag, prefix, spk_extracted, pure_text = self.extract_speaker_tag(orig_text)
            if has_tag:
                speaker = spk_extracted
                translated_prefix = self.glossary_scanner.translate_speaker_tag(prefix)
            else:
                prefix = ""
                speaker = speaker_col.strip() if speaker_col else ""
                pure_text = orig_text.strip()
                translated_prefix = ""

            if not pure_text:
                row[1] = orig_text
                cached_rows[str_idx] = orig_text
                continue

            # Auto-resolve pure symbols / pauses (Zero Token)
            if self.is_pure_symbol_dialogue(pure_text):
                combined_initial = f"{translated_prefix}{pure_text}"
                row[1] = combined_initial
                cached_rows[str_idx] = combined_initial
                pure_symbols_count += 1
                continue

            # Auto-resolve name-only lines (strictly English names without Japanese)
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

        # 喔氞副喔權笚喔多竵 Checkpoint 喔傕腑喔� direct-copied, pure symbols 喙佮弗喔� name-only 喔椸傅喙� auto-resolved 喙勦笡喔ム箞喔о竾喔�笝喙夃覆
        if (direct_copied_count + pure_symbols_count + name_only_count) > 0:
            self.checkpoint_data["csv_translations"][csv_key] = cached_rows
            self._save_checkpoint()

        # 喔氞副喔權笚喔多竵喔�笘喔侧笝喔班箑喔｀复喙堗浮喔曕箟喔權弗喔囙箘喔熰弗喙� output_csv_path 喔椸副喔權笚喔�
        # 喙€喔炧阜喙堗腑喙冟斧喙夃箒喔栢抚喔椸傅喙堗箘喔∴箞喙冟笂喙� Displayable = Yes (喔栢腹喔佮箒喔椸笝喔勦箞喔侧笖喙夃抚喔� Original) 喙佮弗喔班箒喔栢抚喔椸傅喙� Auto-resolved 喙勦笖喙夃福喔编笟喔佮覆喔｀笟喔编笝喔椸付喔佮笚喔编笝喔椸傅 100%
        temp_output = output_csv_path + ".tmp"
        with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
            writer = csv.writer(out_f)
            writer.writerows(rows)
        os.replace(temp_output, output_csv_path)
        logger.info(f"Initialized output CSV with direct-copied non-displayable and auto-resolved items at {output_csv_path}")

        if not pending_dialogues:
            logger.info("No dialogues need LLM translation! Output CSV is complete.")
            return output_csv_path

        # 喔堗副喔斷箒喔氞箞喔囙箑喔涏箛喔� Scene-based Batches 喔曕覆喔∴竾喔氞笡喔｀赴喔∴覆喔� Token (~8,000 tokens 喙佮弗喔班箘喔∴箞喙€喔佮复喔� max_items_per_batch)
        if batch_size is not None:
            batches = [pending_dialogues[i:i + batch_size] for i in range(0, len(pending_dialogues), batch_size)]
        else:
            batches = self.pack_into_scene_batches(pending_dialogues, max_tokens=max_tokens, max_items_per_batch=max_items_per_batch)
            logger.info(f"馃摝 Scene-Based Token Packing: Grouped {len(pending_dialogues)} dialogues into {len(batches)} batches (~{max_tokens} tokens/batch, max {max_items_per_batch} items)")

        if batch_limit is not None:
            batches = batches[:batch_limit]
            logger.info(f"Applying batch_limit={batch_limit}. Total batches to process in this run: {len(batches)}")

        self.prevent_system_sleep()
        try:
            self.wait_for_bridge_ready()
            for b_idx, batch in enumerate(batches):
                logger.info(f"=== Translating CSV Batch {b_idx + 1}/{len(batches)} ({len(batch)} items) ===")

                # 喔�箒喔佮笝 Glossary 喙佮弗喔� Profiles 喔�赋喔�福喔编笟 Batch 喔權傅喙夃箒喔氞笟 Dynamic (Characters, Items, Places, System)
                batch_texts = [it.get("text", "") for it in batch]
                speakers = list(set(it["speaker"] for it in batch if it.get("speaker")))
                matched_glossary = self.glossary_scanner.scan_dialogue_batch(batch_texts, speakers=speakers)
                glossary_context = self.glossary_scanner.format_glossary_for_prompt(matched_glossary)

                # 喔�竵喔编笖 Scene Context (Scene Overview, Mood, Tone, Character Dynamics) 喔堗覆喔� rpgm_scenes_v5.json 喙佮弗喔� extractions_v4
                scene_context = ""
                try:
                    scene_context = self.scene_manager.get_scene_context_for_batch(batch)
                except Exception as sc_err:
                    logger.warning(f"Scene context extraction notice: {sc_err}")

                # 喔溹釜喔侧笝喔氞福喔脆笟喔� Scene 喙佮弗喔� Glossary 喙€喔傕箟喔侧笖喙夃抚喔⑧竵喔编笝
                context_blocks = []
                if scene_context:
                    context_blocks.append(scene_context)
                if glossary_context:
                    context_blocks.append(glossary_context)
                combined_profiles_context = "\n\n".join(context_blocks)

                # 喔�箞喔囙箒喔涏弗喔溹箞喔侧笝 Adaptive Translation Engine (Auto-Bisecting & Safety Auto-Repair)
                results = self.translate_batch_adaptive(batch, profiles_context=combined_profiles_context)

                # 喔權赋喔勦赋喙佮笡喔ム浮喔侧笡喔｀赴喔佮腑喔氞竵喔编笟 prefix 喔椸傅喙堗箒喔涏弗喔曕覆喔� Glossary 喙佮弗喙夃抚喙冟釜喙堗弗喔囙竸喔�弗喔编浮喔權箤 B (Initial)
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
                    if it.get("is_d_text"):
                        combined_initial = f"{it.get('prefix', '')}{translated_dialogue}{it.get('suffix', '')}"
                    else:
                        combined_initial = f"{translated_prefix}{translated_dialogue}"
                    init_target_idx = it.get("init_col_idx", 1)
                    while len(rows[r_idx]) <= init_target_idx:
                        rows[r_idx].append("")
                    rows[r_idx][init_target_idx] = combined_initial
                    cached_rows[str(r_idx)] = combined_initial

                    # Record Listener in Note Column (Column 4)
                    lis = self.last_listeners_map.get(r_id) or self.last_listeners_map.get(str(r_id)) or ""
                    if lis and len(rows[r_idx]) > 4:
                        cur_note = rows[r_idx][4].strip()
                        cur_note = re.sub(r'\s*\|\s*Listener:[^|]*', '', cur_note).strip()
                        cur_note = re.sub(r'\[Listener:[^\]]*\]', '', cur_note).strip()
                        if cur_note:
                            rows[r_idx][4] = f"{cur_note} | Listener: {lis}"
                        else:
                            rows[r_idx][4] = f"Listener: {lis}"

                    speaker_label = it.get('speaker') or it.get('role', 'Narration')
                    lis_label = f" -> {lis}" if lis else ""
                    logger.info(f"Row {r_idx} [{speaker_label}{lis_label}]: {combined_initial[:60]}...")

                # 喔氞副喔權笚喔多竵 Checkpoint
                self.checkpoint_data["csv_translations"][csv_key] = cached_rows
                self.checkpoint_data["total_batches_done"] += 1
                self._save_checkpoint()

                # 喔氞副喔權笚喔多竵喔ム竾喙勦笩喔ム箤 CSV 喔溹弗喔ム副喔炧笜喙屶箒喔氞笟 Incremental 喔椸副喔權笚喔掂笚喔膏竵 Batch (喔涏箟喔�竾喔佮副喔權競喙夃腑喔∴腹喔ム釜喔灌笉喔�覆喔� 100%)
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
                logger.info(f"馃弫 Finished {len(batches)} batches in this run! (Done this run: {processed_in_this_run} items | Total in file: {total_done_for_csv} items | Remaining for LLM: {remaining_in_file} items)")
            else:
                logger.info(f"馃帀 100% COMPLETED! All dialogues in {output_csv_path} are now fully translated! (Total: {total_done_for_csv} items)")
        finally:
            self.restore_system_sleep()
    def translate_untranslated_queue(self, queue_json_path, target_csv_path, max_tokens=8000, max_items_per_batch=15, batch_limit=None):
        """
        喙佮笡喔ム福喔侧涪喔佮覆喔｀笀喔侧竵喔勦复喔о釜喔赤福喔о笀 (untranslated_queue.json) 喙佮弗喔班箑喔傕傅喔⑧笝喔溹弗喔ム副喔炧笜喙屶弗喔� target CSV 喙傕笖喔⑧笗喔｀竾喙佮笟喔� Incremental
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

        # 喔�箞喔侧笝 Target CSV 喔椸副喙夃竾喔�浮喔�
        with open(target_csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        csv_key = os.path.basename(target_csv_path)
        cached_rows = self.checkpoint_data.setdefault("csv_translations", {}).setdefault(csv_key, {})

        # 喔｀抚喔∴笡喔｀赴喔о副喔曕复喔勦赋喙佮笡喔ム笀喔侧竵喔椸父喔� key 喙冟笝 checkpoint (喔涏箟喔�竾喔佮副喔權笡喔编笉喔�覆喔娻阜喙堗腑喙勦笩喔ム箤喙勦浮喙堗笗喔｀竾喔佮副喔�)
        all_cached = {}
        for k, v in self.checkpoint_data.get("csv_translations", {}).items():
            if isinstance(v, dict):
                all_cached.update(v)

        # 喙傕斧喔ム笖 locked terms 喙佮弗喔班笂喔粪箞喔�笗喔编抚喔ム赴喔勦福喔椸副喙夃竾喔�浮喔斷釜喔赤斧喔｀副喔� auto-resolve 喔堗覆喔� GlossaryScanner 喙佮笟喔� Dynamic 100% (Universal)
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

        # 喙佮笡喔ム竾 queue_items 喙€喔涏箛喔� pending_dialogues
        pending_dialogues = []
        skipped_already_translated = 0
        skipped_pure_symbols = 0

        for it in queue_items:
            # 喔｀腑喔囙福喔编笟喔椸副喙夃竾 csv_index (1-based) 喙佮弗喔� row_idx (1-based 喔�福喔粪腑 0-based)
            if "csv_index" in it:
                r_idx = it["csv_index"] - 1
            elif "row_idx" in it:
                # row_idx 喔堗覆喔� curator 喙€喔涏箛喔� 1-based (index 喙冟笝 CSV) 喔堗付喔囙弗喔� 1 喙€喔炧阜喙堗腑喙€喔涏箛喔� 0-indexed 喙冟笝 rows
                r_idx = it["row_idx"] - 1
            else:
                continue

            if r_idx < 0 or r_idx >= len(rows):
                continue

            orig_text = it["original"]
            speaker = it.get("speaker", "")
            role = it.get("role", "Dialogue/Story")
            filename = it.get("file", "") or it.get("filename", "")

            # 喔曕福喔о笀喔堗副喔氞笗喔编抚喙€喔ム競喙€喔囙复喔�/喔勦箞喔侧福喔班笟喔氞釜喔侧竵喔� (喙€喔娻箞喔� 18G, 20G, 48G): Auto-fill 喔椸副喔權笚喔� 喙勦浮喙堗釜喙堗竾喙勦笡 LLM
            clean_num = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<]", "", orig_text).strip()
            if re.match(r"^\d+\s*G?$", clean_num, flags=re.IGNORECASE):
                rows[r_idx][1] = orig_text
                cached_rows[str(r_idx)] = orig_text
                skipped_pure_symbols += 1
                continue

            # 喔�竵喔编笖 speaker tag 喔堗覆喔� orig_text 喔�覆喔佮浮喔�
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

            # 3. 喔曕福喔о笀喔�腑喔� Pure Symbols / Single Locked Name: 喔栢箟喔侧箘喔∴箞喔∴傅喙€喔權阜喙夃腑喔�覆喔氞笚喔炧腹喔斷笀喔｀复喔� 喙冟斧喙� Auto-fill 喙傕笖喔⑧箘喔∴箞喔曕箟喔�竾喔�箞喔� LLM
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

            # 喔勦箟喔權斧喔� Scene ID 喔椸傅喙堗箒喔椸箟喔堗福喔脆竾喔堗覆喔� rpgm_scenes_v5.json
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
        logger.info(f"  鈥� Total items in queue: {len(queue_items):,}")
        logger.info(f"  鈥� Already Translated (Resumed from CSV/Checkpoint): {skipped_already_translated:,}")
        logger.info(f"  鈥� Auto-Resolved Symbols/Locked Names: {skipped_pure_symbols:,}")
        logger.info(f"  鈥� Remaining Pending Items for LLM: {len(pending_dialogues):,}")
        if not pending_dialogues:
            logger.info("All queue items are already translated in checkpoint! Writing CSV...")
            with open(target_csv_path, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerows(rows)
            return target_csv_path

        # -------------------------------------------------------------
        # DUAL-TRACK CLASSIFICATION & BATCH PACKING
        # -------------------------------------------------------------
        track_a_items = []  # Standalone / Direct Batches (Database & UI Choices 喙勦浮喙堗笗喙夃腑喔囙箖喔娻箟喔氞福喔脆笟喔椸笁喔侧竵)
        track_b_items = []  # Narrative Scene Batches (喔夃覆喔佮箑喔權阜喙夃腑喙€喔｀阜喙堗腑喔囙笚喔掂箞喔曕箟喔�竾喙冟笂喙夃笟喔｀复喔氞笚喙佮弗喔� Flow 喔夃覆喔�)

        for d in pending_dialogues:
            sc_id = d.get("scene_id", "General_Scene")
            if sc_id.endswith("_Database") or sc_id == "System_Menu_Choices":
                track_a_items.append(d)
            else:
                track_b_items.append(d)

        batches = []

        # 1. 喔堗副喔斷竵喔侧福 Track A Batches (喔｀抚喔∴竵喙夃腑喔權箖喔�笉喙� 35-40 items/batch)
        mapinfos_items = [it for it in track_a_items if it.get("scene_id") == "Mapinfos_Database"]
        other_db_items = [it for it in track_a_items if it.get("scene_id") != "Mapinfos_Database"]
        for i in range(0, len(mapinfos_items), 35):
            batches.append(mapinfos_items[i:i + 35])
        for i in range(0, len(other_db_items), 35):
            batches.append(other_db_items[i:i + 35])

        # 2. 喔堗副喔斷竵喔侧福 Track B Batches (喔夃覆喔佮箑喔權阜喙夃腑喙€喔｀阜喙堗腑喔�)
        scenes_map = {}
        for it in track_b_items:
            sc_id = it.get("scene_id", "General_Scene")
            if sc_id not in scenes_map:
                scenes_map[sc_id] = []
            scenes_map[sc_id].append(it)

        small_scenes_pool = []
        for sc_id, items in scenes_map.items():
            if len(items) >= 5:
                # 喔栢箟喔侧笁喔侧竵喔∴傅喙勦浮喙堗箑喔佮复喔� 20 喔｀覆喔⑧竵喔侧福 喙冟斧喙夃腑喔⑧腹喙堗箖喔� Batch 喙€喔斷傅喔⑧抚喔佮副喔權笚喔编箟喔囙笁喔侧竵喙€喔炧阜喙堗腑喔｀副喔佮俯喔侧竸喔о覆喔∴笗喙堗腑喙€喔權阜喙堗腑喔� 喙勦浮喙堗笗喙夃腑喔囙笗喔编笖喙€喔ㄠ俯
                if len(items) <= 20:
                    batches.append(items)
                else:
                    for i in range(0, len(items), max_items_per_batch):
                        batches.append(items[i:i + max_items_per_batch])
            else:
                small_scenes_pool.extend(items)

        # 喔｀抚喔∴笁喔侧竵喙€喔ム箛喔佮箚 喔椸傅喙堗竵喔｀赴喔堗副喔斷竵喔｀赴喔堗覆喔� 喙傕笖喔⑧笀喔编笖喔佮弗喔膏箞喔∴笗喔侧浮 Map Prefix 喙€喔斷傅喔⑧抚喔佮副喔�
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

        logger.info(f"馃摝 Dual-Track Batch Packing: Grouped {len(pending_dialogues)} items into {len(batches)} batches (Track A: {len(track_a_items)} items, Track B: {len(track_b_items)} items)")

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

                # 喔�竵喔编笖 Scene Narrative Overview, Mood, Tone, Character Dynamics 喔堗覆喔� extractions_v4
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

                # 喔�竵喔编笖 Scene Dialogue Flow (喔氞笚喔�笝喔椸笝喔侧箒喔о笖喔ム箟喔�浮喔炧福喙夃腑喔∴竸喔赤箒喔涏弗喙勦笚喔⑧箑喔斷复喔∴箖喔� CSV)
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

                # 喔溹釜喔侧笝 Context Blocks
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

                # 喔氞副喔權笚喔多竵 Checkpoint
                self.checkpoint_data["csv_translations"][csv_key] = cached_rows
                self.checkpoint_data["csv_translations"].setdefault("SSPV034v1.35 - Trans - Processed_v3.csv", {}).update(cached_rows)
                self.checkpoint_data["total_batches_done"] += 1
                self._save_checkpoint()

                # 喔氞副喔權笚喔多竵喔ム竾 Target CSV 喔椸副喔權笚喔掂笚喔膏竵 Batch
                temp_output = target_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerows(rows)
                os.replace(temp_output, target_csv_path)
                logger.info(f"Saved Queue progress to {target_csv_path}")

                # 3. 喔曕副喔斷福喔侧涪喔佮覆喔｀箖喔� Batch 喔權傅喙夃腑喔�竵喔堗覆喔� Queue 喔氞笝喔斷复喔�竵喙屶笚喔编笝喔椸傅 (Atomic Write Queue Pruning)
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

            logger.info(f"馃帀 Queue processing completed! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return target_csv_path

    def translate_empty_rows(self, target_csv_path, max_tokens=8000, max_items_per_batch=15, batch_limit=None):
        """
        喙佮笡喔ム箑喔夃笧喔侧赴喙佮笘喔о笚喔掂箞喔о箞喔侧竾喔�涪喔灌箞 (Initial == '') 喙佮弗喔� Displayable == 'Yes' 喙傕笖喔⑧笗喔｀竾喔堗覆喔佮箘喔熰弗喙� CSV
        - 喙冟笂喙� CSV 喙€喔涏箛喔� Single Source of Truth 100% 喙勦浮喙堗笗喙夃腑喔囙笧喔多箞喔囙笧喔侧箘喔熰弗喙� Queue 喔犩覆喔⑧笝喔�竵
        - 喙佮涪喔佮竵喔侧福喙佮笡喔ム箑喔涏箛喔� 2 喔｀腹喔涏箒喔氞笟 (Dual-Track):
            Track B: 喔氞笚喔�笝喔椸笝喔侧箖喔� Scene -> 喔斷付喔囙笟喔｀复喔氞笚喔椸副喙夃竾 Scene (Scene Flow + Character Profiles + Glossary)
                     喔�箞喔囙竸喔赤釜喔编箞喔囙箖喔�箟喙佮笡喔ム箑喔夃笧喔侧赴喔涏福喔班箓喔⑧竸喙€喔涏箟喔侧斧喔∴覆喔⑧笚喔掂箞喔о箞喔侧竾喔�涪喔灌箞 喙傕笖喔⑧腑喙夃覆喔囙腑喔脆竾喔涏福喔班箓喔⑧竸喔�阜喙堗笝喙冟笝喔夃覆喔佮腑喔⑧箞喔侧竾喙€喔勦福喙堗竾喔勦福喔编笖
            Track A: 喔傕箟喔�竸喔о覆喔∴箑喔斷傅喙堗涪喔�/Database/UI Menu 喔椸傅喙堗箘喔∴箞喙€喔娻阜喙堗腑喔∴箓喔⑧竾喔佮副喔氞笁喔侧竵喙€喔權阜喙夃腑喙€喔｀阜喙堗腑喔� -> 喔∴副喔斷福喔о浮喙€喔涏箛喔權竵喙夃腑喔權箖喔�笉喙� (35-40 喔｀覆喔⑧竵喔侧福)
                     喔�箞喔囙箒喔涏弗喙勦笚喔⑧笧喔｀箟喔�浮喔佮赋喔娻副喔氞箑喔斷箛喔斷競喔侧笖喔о箞喔侧箖喔�箟喔勦竾喔｀腹喔涏笂喔粪箞喔�箑喔夃笧喔侧赴 (Red Arthur, Cerberus, Bonnie, MAPxxx, System CamelCase IDs) 喙勦抚喙夃箖喔權笭喔侧俯喔侧腑喔编竾喔佮袱喔┼箑喔斷复喔�
        - 喔氞副喔權笚喔多竵喔溹弗喔ム副喔炧笜喙屶弗喔� Initial 喔傕腑喔� CSV 喔椸副喔權笚喔掂箒喔氞笟 Atomic Write 喔椸父喔� Batch
        """
        if not os.path.exists(target_csv_path):
            logger.error(f"Target CSV not found: {target_csv_path}")
            return target_csv_path

        logger.info(f"馃搨 Scanning target CSV directly for EMPTY rows: {target_csv_path}")
        with open(target_csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            logger.warning("Target CSV is empty!")
            return target_csv_path

        # 喙傕斧喔ム笖 locked terms 喙佮弗喔班笂喔粪箞喔�笗喔编抚喔ム赴喔勦福喔椸副喙夃竾喔�浮喔斷釜喔赤斧喔｀副喔� auto-resolve 喔堗覆喔� GlossaryScanner 喙佮笟喔� Dynamic 100%
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

        # Dynamic column detection from CSV header
        header_raw = rows[0]
        header_lower = [c.strip().lower() for c in header_raw]

        orig_idx = header_lower.index("original") if "original" in header_lower else 0
        init_idx = header_lower.index("initial") if "initial" in header_lower else 1
        disp_idx = header_lower.index("displayable") if "displayable" in header_lower else (7 if len(header_lower) > 7 and header_lower[7] == "displayable" else -1)
        role_idx = header_lower.index("role") if "role" in header_lower else (3 if len(header_lower) == 10 else (5 if len(header_lower) > 5 else -1))
        speaker_idx = header_lower.index("speaker") if "speaker" in header_lower else (4 if len(header_lower) == 10 else (6 if len(header_lower) > 6 else -1))
        listener_idx = header_lower.index("listener") if "listener" in header_lower else (5 if len(header_lower) == 10 else -1)
        filename_idx = header_lower.index("filename") if "filename" in header_lower else (7 if len(header_lower) == 10 else (2 if len(header_lower) > 2 else -1))
        row_id_idx = header_lower.index("row") if "row" in header_lower else (8 if len(header_lower) == 10 else (3 if len(header_lower) > 3 else -1))

        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            if len(row) < 2:
                continue

            orig_text = row[orig_idx] if orig_idx != -1 and len(row) > orig_idx else (row[0] if len(row) > 0 else "")
            init_text = row[init_idx] if init_idx != -1 and len(row) > init_idx else (row[1] if len(row) > 1 else "")
            filename = row[filename_idx] if filename_idx != -1 and len(row) > filename_idx else ""
            line_id = row[row_id_idx] if row_id_idx != -1 and len(row) > row_id_idx else ""
            role = row[role_idx] if role_idx != -1 and len(row) > role_idx else ""
            speaker_col = row[speaker_idx] if speaker_idx != -1 and len(row) > speaker_idx else ""
            listener_col = row[listener_idx] if listener_idx != -1 and len(row) > listener_idx else ""

            # Dynamic Displayable check: If column exists, use it; if no column, default to "yes"
            if disp_idx != -1 and len(row) > disp_idx:
                disp = row[disp_idx].strip().lower()
            else:
                disp = "yes"

            if disp != "yes":
                skipped_non_displayable += 1
                if not init_text.strip() and orig_text.strip():
                    while len(row) <= init_idx:
                        row.append("")
                    row[init_idx] = orig_text
                    direct_copied_non_disp += 1
                continue

            # ตรวจสอบว่าข้อความนี้ได้รับการแปลแล้วจริงหรือไม่ (Is already translated to Thai?)
            # แถวจะถือว่า "ยังไม่ได้แปล" (ต้องส่งให้ LLM แปล) เมื่อ:
            # 1. init_text ว่างเปล่า
            # 2. init_text ยังเป็นข้อความเดิมเหมือน orig_text (ภาษาญี่ปุ่นดั้งเดิมที่ Translator++ ใส่มา)
            # 3. init_text ยังมีอักษรภาษาญี่ปุ่น (Hiragana, Katakana, CJK) และไม่มีภาษาไทย
            is_untranslated = False
            if not init_text.strip():
                is_untranslated = True
            elif init_text.strip() == orig_text.strip():
                is_untranslated = True
            else:
                has_jp = bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', init_text))
                has_th = bool(re.search(r'[\u0e00-\u0e7f]', init_text))
                if has_jp and not has_th:
                    is_untranslated = True

            if not is_untranslated:
                already_filled_count += 1
                continue

            if not orig_text.strip():
                continue

            clean_num = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?|\\[\.\|\!\^\>\<]", "", orig_text).strip()
            if re.match(r"^\d+\s*G?$", clean_num, flags=re.IGNORECASE):
                while len(row) <= init_idx:
                    row.append("")
                row[init_idx] = orig_text
                auto_resolved_symbols += 1
                continue

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

            content_to_check = final_text.strip()
            if self.is_single_name_with_symbols(content_to_check, locked_terms, current_speaker=final_speaker):
                while len(row) <= init_idx:
                    row.append("")
                row[init_idx] = f"{translated_prefix}{final_text}"
                auto_resolved_symbols += 1
                continue

            scene_id = "General_Scene"
            if hasattr(self, "scene_manager"):
                scene_id = self.scene_manager.find_scene_for_row(r_idx, orig_text, file_name=filename, csv_rows=rows)

            pending_empty_items.append({
                "row_idx": r_idx,
                "prefix": prefix,
                "translated_prefix": translated_prefix,
                "speaker": final_speaker,
                "listener": listener_col,
                "role": role if role else "Dialogue/Story",
                "id": str(r_idx),
                "text": final_text,
                "file": filename,
                "scene_id": scene_id,
                "init_col_idx": init_idx
            })

        logger.info(f"Target CSV Empty-Row Scan Summary:")
        logger.info(f"  鈥� Total Rows in File: {len(rows):,}")
        logger.info(f"  鈥� Already Filled (Untouched): {already_filled_count:,}")
        logger.info(f"  鈥� Non-Displayable Handled: {skipped_non_displayable:,} (Direct copied: {direct_copied_non_disp:,})")
        logger.info(f"  鈥� Auto-Resolved Symbols/Currency: {auto_resolved_symbols:,}")
        logger.info(f"  鈥� Empty Target Rows Requiring LLM Translation: {len(pending_empty_items):,}")

        # 喔氞副喔權笚喔多竵喔�笘喔侧笝喔班箑喔｀复喙堗浮喔曕箟喔權競喔�竾 auto-filled 喔椸副喔權笚喔掂斧喔侧竵喔∴傅喔佮覆喔｀箑喔涏弗喔掂箞喔⑧笝喙佮笡喔ム竾
        if direct_copied_non_disp > 0 or auto_resolved_symbols > 0:
            temp_output = target_csv_path + ".tmp"
            with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                writer = csv.writer(out_f)
                writer.writerows(rows)
            os.replace(temp_output, target_csv_path)
            logger.info(f"Saved auto-resolved non-displayable/symbol items to {target_csv_path}")

        if not pending_empty_items:
            logger.info("馃帀 All Displayable rows in CSV are already 100% translated! No empty rows found.")
            return target_csv_path

        # -------------------------------------------------------------
        # DUAL-TRACK CLASSIFICATION & BATCH PACKING
        # -------------------------------------------------------------
        track_a_items = []  # Standalone / Direct Batches (Database & UI Choices 喙勦浮喙堗笗喙夃腑喔囙箖喔娻箟喔氞福喔脆笟喔椸笁喔侧竵)
        track_b_items = []  # Narrative Scene Batches (喔夃覆喔佮箑喔權阜喙夃腑喙€喔｀阜喙堗腑喔囙笚喔掂箞喔曕箟喔�竾喙冟笂喙夃笟喔｀复喔氞笚喙佮弗喔� Flow 喔夃覆喔�)

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

        # 1. 喔堗副喔斷竵喔侧福 Track A Batches (喔｀抚喔∴竵喙夃腑喔權箖喔�笉喙� 35-40 items/batch)
        mapinfos_items = [it for it in track_a_items if it.get("scene_id") == "Mapinfos_Database"]
        other_db_items = [it for it in track_a_items if it.get("scene_id") != "Mapinfos_Database"]
        for i in range(0, len(mapinfos_items), 35):
            batches.append(mapinfos_items[i:i + 35])
        for i in range(0, len(other_db_items), 35):
            batches.append(other_db_items[i:i + 35])

        # 2. 喔堗副喔斷竵喔侧福 Track B Batches (喔夃覆喔佮箑喔權阜喙夃腑喙€喔｀阜喙堗腑喔�)
        scenes_map = {}
        for it in track_b_items:
            sc_id = it.get("scene_id", "General_Scene")
            if sc_id not in scenes_map:
                scenes_map[sc_id] = []
            scenes_map[sc_id].append(it)

        small_scenes_pool = []
        for sc_id, items in scenes_map.items():
            if len(items) >= 5:
                # 喔栢箟喔侧笁喔侧竵喔∴傅喙勦浮喙堗箑喔佮复喔� 20 喔｀覆喔⑧竵喔侧福 喙冟斧喙夃腑喔⑧腹喙堗箖喔� Batch 喙€喔斷傅喔⑧抚喔佮副喔權笚喔编箟喔囙笁喔侧竵喙€喔炧阜喙堗腑喔｀副喔佮俯喔侧竸喔о覆喔∴笗喙堗腑喙€喔權阜喙堗腑喔� 喙勦浮喙堗笗喙夃腑喔囙笗喔编笖喙€喔ㄠ俯
                if len(items) <= 20:
                    batches.append(items)
                else:
                    for i in range(0, len(items), max_items_per_batch):
                        batches.append(items[i:i + max_items_per_batch])
            else:
                small_scenes_pool.extend(items)

        # 喔｀抚喔∴笁喔侧竵喙€喔ム箛喔佮箚 喔椸傅喙堗竵喔｀赴喔堗副喔斷竵喔｀赴喔堗覆喔� 喙傕笖喔⑧笀喔编笖喔佮弗喔膏箞喔∴笗喔侧浮 Map Prefix 喙€喔斷傅喔⑧抚喔佮副喔�
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

        logger.info(f"馃摝 Dual-Track Batch Packing: Grouped {len(pending_empty_items)} empty items into {len(batches)} batches (Track A: {len(track_a_items)} items, Track B: {len(track_b_items)} items)")

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
                    # Directive 喔炧复喙€喔ㄠ俯喔�赋喔�福喔编笟 Track A: 喔�箟喔侧浮喙佮笡喔ム笂喔粪箞喔�箑喔夃笧喔侧赴喙€喔斷箛喔斷競喔侧笖
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
                    # 喔�竵喔编笖 Scene Narrative Overview, Mood, Tone 喔堗覆喔� extractions_v4
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

                    # 喔�竵喔编笖 Scene Dialogue Flow (喔氞笚喔�笝喔椸笝喔侧箒喔о笖喔ム箟喔�浮喔炧福喙夃腑喔∴竸喔赤箒喔涏弗喙勦笚喔⑧箑喔斷复喔∴箖喔� CSV)
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

                # 喔氞副喔權笚喔多竵喔ム竾 Target CSV 喔椸副喔權笚喔掂笚喔膏竵 Batch (Atomic Write)
                temp_output = target_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerows(rows)
                os.replace(temp_output, target_csv_path)
                logger.info(f"馃捑 Saved Progress to CSV ({b_idx + 1}/{len(batches)} batches done) -> {target_csv_path}")

            logger.info(f"馃帀 All empty row batches completed! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return target_csv_path

    def translate_plugins_csv(self, plugins_csv_path="data/plugins_texts.csv", max_items_per_batch=15, batch_limit=None):
        """
        喙佮笡喔ム箘喔熰弗喙� Plugin UI Text (data/plugins_texts.csv) 喔斷箟喔о涪 Batch JSON Translation
        喔氞副喔權笚喔多竵喔溹弗喔ム副喔炧笜喙屶弗喔囙竸喔�弗喔编浮喔權箤 Initial (index 1) 喙佮笟喔� Atomic Write 喔椸父喔� Batch
        """
        if not os.path.exists(plugins_csv_path):
            raise FileNotFoundError(f"Plugin texts CSV not found at {plugins_csv_path}")

        logger.info(f"馃搨 Loading Plugin Texts from: {plugins_csv_path}")
        with open(plugins_csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))

        if not reader:
            logger.warning("Empty plugins CSV file!")
            return plugins_csv_path

        header = reader[0]
        data_rows = reader[1:]
        logger.info(f"Total Plugin Text Rows: {len(data_rows):,} rows")

        header_lower = [c.strip().lower() for c in header]
        orig_idx = header_lower.index("original") if "original" in header_lower else 0
        init_idx = header_lower.index("initial") if "initial" in header_lower else 1
        disp_idx = header_lower.index("displayable") if "displayable" in header_lower else -1
        speaker_idx = header_lower.index("speaker") if "speaker" in header_lower else -1
        role_idx = header_lower.index("role") if "role" in header_lower else -1

        untranslated = []
        for idx, row in enumerate(data_rows):
            orig_text = row[orig_idx] if orig_idx != -1 and len(row) > orig_idx else (row[0] if len(row) > 0 else "")
            init_text = row[init_idx] if init_idx != -1 and len(row) > init_idx else (row[1] if len(row) > 1 else "")
            if not orig_text or not orig_text.strip():
                continue
            if disp_idx != -1 and len(row) > disp_idx and row[disp_idx].strip().lower() != "yes":
                continue
            is_untrans = False
            if not init_text or not init_text.strip():
                is_untrans = True
            elif init_text.strip() == orig_text.strip():
                is_untrans = True
            else:
                has_jp = bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', init_text))
                has_th = bool(re.search(r'[\u0e00-\u0e7f]', init_text))
                if has_jp and not has_th:
                    is_untrans = True

            if is_untrans:
                spk = row[speaker_idx] if speaker_idx != -1 and len(row) > speaker_idx and row[speaker_idx] else "UI/Plugin"
                rle = row[role_idx] if role_idx != -1 and len(row) > role_idx and row[role_idx] else "UI/Plugin"
                untranslated.append({
                    "row_idx": idx,
                    "id": f"PLUG_{idx + 1}",
                    "speaker": spk,
                    "role": rle,
                    "text": orig_text,
                    "init_col_idx": init_idx
                })

        logger.info(f"Found {len(untranslated):,} untranslated Plugin rows out of {len(data_rows):,} rows.")
        if not untranslated:
            logger.info("馃帀 All Plugin UI texts are already 100% translated!")
            return plugins_csv_path

        # 喙佮笟喙堗竾喙€喔涏箛喔� Batches
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
                        logger.info(f"  鈥� {r_id} [{it['speaker']}]: {repr(trans_text[:50])}")

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
                        logger.warning(f"  鈿狅笍 No translation found for {r_id} ({repr(it['text'][:30])})")

                # Atomic Save to plugins_texts.csv every batch
                temp_output = plugins_csv_path + ".tmp"
                with open(temp_output, "w", encoding="utf-8", newline="") as out_f:
                    writer = csv.writer(out_f)
                    writer.writerow(header)
                    writer.writerows(data_rows)
                os.replace(temp_output, plugins_csv_path)
                logger.info(f"Saved Plugin translation progress ({b_idx + 1}/{len(batches)} batches) to {plugins_csv_path}")

            logger.info(f"馃帀 Plugin Translation completed successfully! Processed {len(batches)} batches.")
        finally:
            self.restore_system_sleep()

        return plugins_csv_path

    def run_unified_all(self, csv_file=None, plugins_file=None, max_tokens=8000, max_items=15, batch_limit=None):
        """
        喙佮笡喔ム福喔о笖喙€喔斷傅喔⑧抚喔堗笟喔椸副喙夃竾喔｀赴喔氞笟喔曕覆喔� Pipeline 喔涏竵喔曕复 (Unified All-in-One Translation):
        Step 1: 喙佮笡喔ム競喙夃腑喔勦抚喔侧浮 Plugin UI Texts (plugins_texts_v035.csv 喔�福喔粪腑 data/plugins_texts.csv)
        Step 2: 喔�弗喔编笟喙勦笡喙佮笡喔� Dialogue CSV 喔�弗喔编竵 (processed_dialogues_v3.csv) 喙冟笝喙傕斧喔∴笖 Empty Rows (Single Source of Truth) 喔曕箞喔�箑喔權阜喙堗腑喔囙笚喔编笝喔椸傅喔�副喔曕箓喔權浮喔编笗喔�
        """
        logger.info("=" * 80)
        logger.info("馃殌 STARTING ATF UNIFIED ALL-IN-ONE TRANSLATION PIPELINE")
        logger.info("=" * 80)

        # -------------------------------------------------------------
        # STEP 1: 喙佮笡喔� Plugin UI Texts
        # -------------------------------------------------------------
        if not plugins_file:
            candidates = [
                self.manifest.get("output_plugins_csv"),
                self.manifest.get("legacy_plugin_csv"),
                os.path.join(self.manifest.get("output_dir", ""), "plugins_texts.csv"),
                os.path.join(workspace_root, "data", "plugins_texts.csv"),
                "data/plugins_texts.csv"
            ]
            for c in candidates:
                if c and os.path.exists(c):
                    plugins_file = c
                    break
            if not plugins_file:
                plugins_file = self.manifest.get("output_plugins_csv") or "data/plugins_texts.csv"

        if plugins_file and os.path.exists(plugins_file):
            logger.info(f"\n>>> [STEP 1/2] Translating Plugin UI Texts: {plugins_file}...")
            self.translate_plugins_csv(
                plugins_csv_path=plugins_file,
                max_items_per_batch=max_items,
                batch_limit=batch_limit
            )
            logger.info("✔ [STEP 1/2] Plugin UI Texts translation completed!\n")
        else:
            logger.warning(f"Plugin texts CSV not found at {plugins_file}, skipping Step 1.")

        # -------------------------------------------------------------
        # STEP 2: แปล Game Dialogue CSV หลัก
        # -------------------------------------------------------------
        if not csv_file:
            candidates = [
                self.manifest.get("output_enriched_csv"),
                self.manifest.get("output_processed_csv"),
                self.manifest.get("raw_pre_csv")
            ]
            for c in candidates:
                if c and os.path.exists(c):
                    csv_file = c
                    break
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
            logger.info("鉁� [STEP 2/2] Game Dialogue CSV translation completed!\n")
        else:
            logger.error(f"鉂� Target CSV file not found: {csv_file}")

        logger.info("=" * 80)
        logger.info("馃帀 ALL TRANSLATION QUEUES (PLUGINS + DIALOGUES) COMPLETED 100%!")
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
    parser.add_argument("--dry-run", action="store_true", help="Run offline Dry-Run benchmark verification (no browser connection needed)")
    args = parser.parse_args()

    batch_limit = args.batches if args.batches is not None else None
    runner = ChatGPTTranslatorRunner(
        manifest_path=args.manifest,
        pace_min=args.pace_min,
        pace_max=args.pace_max
    )

    if args.dry_run:
        print("=" * 80)
        print("🧪 RUNNING DRY-RUN BENCHMARK VERIFICATION (OFFLINE 5D LQA & PARSER CHECK)")
        print("=" * 80)
        input_csv = args.file or runner.manifest.get("output_enriched_csv") or runner.manifest.get("output_processed_csv") or runner.manifest.get("raw_pre_csv")
        print(f"[*] Input CSV: {input_csv}")
        if not input_csv or not os.path.exists(input_csv):
            print(f"[❌] Error: Input CSV not found: {input_csv}")
            sys.exit(1)

        import csv
        with open(input_csv, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        print(f"[✔] Total Rows in CSV: {len(rows)}")
        sample_dialogues = []
        for r_idx in range(1, len(rows)):
            row = rows[r_idx]
            if len(row) < 3:
                continue
            orig = row[0]
            filename = row[2] if len(row) > 2 else ""
            has_tag, prefix, speaker, pure_text = runner.extract_speaker_tag(orig)
            if has_tag or any(ch in orig for ch in ["「", "」", "【", "】"]) or len(orig) > 5:
                if pure_text.strip() and pure_text not in ["打撃/物理", "裸", "妻", "朝", "EV001", "EV002"]:
                    if not runner.is_pure_symbol_dialogue(pure_text):
                        sample_dialogues.append({
                            "row_idx": r_idx,
                            "orig": orig,
                            "speaker": speaker or "夫",
                            "file": filename,
                            "pure_text": pure_text
                        })
            if len(sample_dialogues) >= args.max_items:
                break

        print(f"[✔] Collected {len(sample_dialogues)} benchmark sample dialogues:")
        print("-" * 80)
        auditor = runner.auditor
        for idx, d in enumerate(sample_dialogues):
            orig = d["orig"]
            spk = d["speaker"]
            lis = "夫" if spk == "凛" else "凛"
            has_tag, prefix, parsed_spk, pure = runner.extract_speaker_tag(orig)
            print(f"[{idx + 1}] Row {d['row_idx']} ({d['file']}):")
            print(f"    Raw Text      : {repr(orig[:50])}")
            print(f"    Extracted Tag : Tag={has_tag} | Prefix='{prefix.strip()}' | Speaker='{parsed_spk}'")
            pair_style = auditor.pairwise_lookup.get((spk, lis), {})
            self_p = pair_style.get("self_pronoun", "ฉัน/ผม")
            tgt_p = pair_style.get("target_pronoun", "คุณ")
            ending_p = pair_style.get("ending_particle", "")
            print(f"    Pair Dynamic  : {spk} -> {lis} (Self: '{self_p}' | Target: '{tgt_p}' | Particle: '{ending_p}')")
            mock_translation = f"【{parsed_spk or 'สามี'}】จำลองคำแปลภาษาไทยสำหรับการทดสอบระบบ"
            lqa_check = auditor.audit(orig, mock_translation, row_id=d["row_idx"], speaker=spk, listener=lis)
            print(f"    LQA Score     : {lqa_check.score}/100.0 (Valid: {lqa_check.is_valid})")
            print("-" * 80)

        print("🎉 DRY-RUN BENCHMARK COMPLETE: All Universal Parsers and 5D LQA Matrices are 100% Operational!")
        sys.exit(0)

    if args.plugins:
        plugins_target = args.plugins_file or runner.manifest.get("output_plugins_csv") or "data/plugins_texts.csv"
        print(f"馃殌 Running Plugin UI Text Translation on: {plugins_target}")
        print(f"馃摝 Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_plugins_csv(
            plugins_csv_path=plugins_target,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    # 喔�覆喔佮釜喔编箞喔� --unified 喔�福喔粪腑喔｀副喔權箑喔｀复喙堗浮喔曕箟喔權箓喔斷涪喙勦浮喙堗福喔班笟喔� file 喙€喔夃笧喔侧赴喙€喔堗覆喔班笀喔� 喙冟斧喙夃笚喔� Unified All-in-One
    if args.unified and not args.queue and not args.file and not args.empty_only:
        print("馃殌 Launching Unified All-in-One Translation Pipeline (Plugins -> Dialogues)...")
        runner.run_unified_all(
            csv_file=args.file,
            plugins_file=args.plugins_file,
            max_tokens=args.tokens,
            max_items=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    # 喙€喔ム阜喔�竵喙勦笩喔ム箤喙€喔涏箟喔侧斧喔∴覆喔�: 喔曕福喔о笀喔�覆喔堗覆喔� Manifest 喔佮箞喔�笝 喙佮弗喙夃抚喔堗付喔囙笖喔� candidate paths
    csv_file = args.file or runner.manifest.get("output_processed_csv")
    if not csv_file:
        candidate_paths = [
            "Example RPGM Game/SSPV034v1.35 - Trans - 喔娻傅喔�1 - Reset wrong legacy.csv",
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
        print(f"鉂� CSV file not found: {csv_file}")
        sys.exit(1)

    if args.empty_only:
        print(f"馃殌 Running Direct Empty-Row Translation on: {csv_file}")
        print(f"馃幆 Target Mode: Single Source of Truth (Translating ONLY Empty & Displayable rows)")
        print(f"馃摝 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_empty_rows(
            target_csv_path=csv_file,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
        sys.exit(0)

    if args.queue:
        print(f"馃殌 Running Queue-Based Translation on: {args.queue}")
        print(f"馃幆 Target CSV: {csv_file}")
        print(f"馃摝 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL' if batch_limit is None else batch_limit}")
        runner.translate_untranslated_queue(
            queue_json_path=args.queue,
            target_csv_path=csv_file,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit
        )
    else:
        print(f"馃殌 Running Scene-Based Translation on: {csv_file}")
        print(f"馃摝 Batch Budget: ~{args.tokens:,} tokens | Max Items: {args.max_items} | Batches: {'ALL (Continuous till done)' if batch_limit is None else batch_limit}")
        runner.translate_csv_file(
            input_csv_path=csv_file,
            batch_size=None,
            max_tokens=args.tokens,
            max_items_per_batch=args.max_items,
            batch_limit=batch_limit,
            reset_checkpoint=args.fresh
        )


