"""
Scene Context Manager Module for ATF
สกัดและจับคู่บริบทของแต่ละฉาก (Scene Context, Emotional Mood, Tone, Character Relationships)
จาก rpgm_scenes_v5.json และ extractions_v4 เข้ากับชุดข้อความบทสนทนาในแต่ละ Batch
เพื่อให้ ChatGPT ทราบบริบท อารมณ์ และความสัมพันธ์ของตัวละครขณะแปลอย่างแม่นยำ 100%
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SceneContextManager")


class SceneContextManager:
    def __init__(
        self,
        scenes_path: Optional[str] = None,
        extractions_dir: Optional[str] = None,
        profiles_dir: Optional[str] = None
    ):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

        if scenes_path is None:
            scenes_path = os.path.join(base_dir, "data", "tlas", "rpgm_scenes_v5.json")
            if not os.path.exists(scenes_path):
                scenes_path = os.path.join(base_dir, "data", "tlas", "rpgm_scenes_v4.json")

        if extractions_dir is None:
            extractions_dir = os.path.join(base_dir, "data", "tlas", "extractions_v4")

        if profiles_dir is None:
            profiles_dir = os.path.join(base_dir, "data", "tlas", "profiles")

        self.scenes_path = scenes_path
        self.extractions_dir = extractions_dir
        self.profiles_dir = profiles_dir

        self.extractions: Dict[str, Any] = {}
        self.scenes_by_source: Dict[str, Any] = {}
        self.text_to_scene_id: Dict[str, str] = {}
        self.scenes_by_prefix: Dict[str, List[str]] = {}

        self._load_data()

    def _clean_text(self, text: str) -> str:
        """ล้าง Control tags, Speaker tag, และช่องว่างเพื่อใช้จับคู่ข้อความกับ Scene"""
        if not text:
            return ""
        s = re.sub(r"^(\s*\\n)?<[^>]+>\s*", "", text)
        s = re.sub(r"^\[[^\]]+\]\s*", "", s)
        s = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", s)
        s = re.sub(r"\\[\.\|\!\^\>\<\{\}\\\fb\fi\fn\fs]", "", s)
        s = re.sub(r"[\s\.\?!…\-_~,\":'’“”\(\)\[\]\{\}<>]+", "", s)
        return s.strip().lower()

    def _load_data(self):
        """โหลด Scene Extractions และ Scene Division Database พร้อมสร้าง Index ในหน่วยความจำ"""
        # 1. โหลด Extractions จาก extractions_v4
        if os.path.exists(self.extractions_dir):
            try:
                ext_files = [f for f in os.listdir(self.extractions_dir) if f.endswith(".json")]
                for f_name in ext_files:
                    scene_id = f_name[:-5]  # ตัด .json
                    f_path = os.path.join(self.extractions_dir, f_name)
                    try:
                        with open(f_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.extractions[scene_id] = data
                            # จัดหมวดหมู่ตาม prefix เช่น CommonEvent หรือ Map009
                            prefix = scene_id.split("_")[0]
                            if prefix not in self.scenes_by_prefix:
                                self.scenes_by_prefix[prefix] = []
                            self.scenes_by_prefix[prefix].append(scene_id)
                    except Exception:
                        continue
                logger.info(f"Loaded {len(self.extractions):,} scene extractions from {self.extractions_dir}")
            except Exception as e:
                logger.warning(f"Error loading extractions from {self.extractions_dir}: {e}")

        # 2. โหลด Scene Text จาก rpgm_scenes_v5.json เพื่อสร้าง Text -> Scene Index
        if os.path.exists(self.scenes_path):
            try:
                with open(self.scenes_path, "r", encoding="utf-8") as f:
                    scenes_data = json.load(f)
                for sc in scenes_data:
                    source = sc.get("source", "")
                    if not source:
                        continue
                    self.scenes_by_source[source] = sc
                    sc_text = sc.get("text", "")
                    if sc_text:
                        # แยกทีละบรรทัดเพื่อทำ index
                        for line in sc_text.split("\n"):
                            clean_line = self._clean_text(line)
                            if clean_line and len(clean_line) >= 8:
                                # แมป 30 ตัวอักษรแรกของประโยคเข้ากับ source scene
                                key = clean_line[:30]
                                if key not in self.text_to_scene_id:
                                    self.text_to_scene_id[key] = source

                logger.info(f"Loaded {len(self.scenes_by_source):,} scenes from {self.scenes_path} (Indexed {len(self.text_to_scene_id):,} text keys)")
            except Exception as e:
                logger.warning(f"Error loading scenes from {self.scenes_path}: {e}")

    def find_scene_id_for_batch(self, batch_items: List[Dict[str, Any]]) -> Optional[str]:
        """ค้นหา Scene ID ที่ตรงกับชุดข้อความใน Batch อย่างแม่นยำ"""
        if not batch_items:
            return None

        # วิธีที่ 1: แมปผ่านข้อความบทสนทนาใน Batch
        for it in batch_items:
            text = it.get("text", "")
            clean = self._clean_text(text)
            if clean and len(clean) >= 8:
                key = clean[:30]
                if key in self.text_to_scene_id:
                    return self.text_to_scene_id[key]

        # วิธีที่ 2: แมปผ่าน Filename และ Row (เช่น CommonEvents row 170 -> CommonEvent_1)
        first_item = batch_items[0]
        filename = first_item.get("file", "") or first_item.get("filename", "")
        if filename:
            norm_file = filename.replace(".json", "")
            if norm_file.startswith("CommonEvent"):
                # ค้นหาในกลุ่ม CommonEvents
                cand_scenes = self.scenes_by_prefix.get("CommonEvent", [])
                if cand_scenes:
                    return cand_scenes[0]
            elif norm_file in self.scenes_by_prefix:
                cand_scenes = self.scenes_by_prefix[norm_file]
                if cand_scenes:
                    return cand_scenes[0]

        return None

    def is_narrative_choice(self, row_idx: int, csv_rows: Optional[List[List[str]]]) -> bool:
        """
        ตรวจสอบว่า Choice Branch นี้เกิดขึ้นกลางบทสนทนาเนื้อเรื่อง (In-Dialogue Narrative Choice)
        หรือเป็นคำสั่งเมนูระบบ/การกระทำของผู้เล่นภายนอกบทสนทนา (System Menu Choice)
        """
        if not csv_rows or row_idx < 1 or row_idx >= len(csv_rows):
            return False

        cur_file = csv_rows[row_idx][2] if len(csv_rows[row_idx]) > 2 else ""
        # ตรวจสอบย้อนหลัง 1-6 แถวในไฟล์เดียวกัน
        for off in range(1, 7):
            prev_idx = row_idx - off
            if prev_idx < 1:
                break
            prev_row = csv_rows[prev_idx]
            prev_file = prev_row[2] if len(prev_row) > 2 else ""
            if prev_file != cur_file:
                break

            prev_orig = prev_row[0] if len(prev_row) > 0 else ""
            prev_role = prev_row[5] if len(prev_row) > 5 else ""

            # มีแท็กชื่อผู้พูด หรือ Role คือ Dialogue/Story
            if re.search(r"^(\s*\\n)?<[^>]+>", prev_orig):
                return True
            if prev_role == "Dialogue/Story":
                return True

        return False

    def find_scene_for_row(
        self,
        row_idx: int,
        original_text: str,
        file_name: str = "",
        csv_rows: Optional[List[List[str]]] = None
    ) -> str:
        """
        ค้นหา Scene ID (อิงตาม rpgm_scenes_v5.json) สำหรับแถวข้อมูลที่กำหนด:
        1. ตรวจสอบหมวด Database ของเกม (Enemies, Items, Skills ฯลฯ)
        2. ตรวจสอบ Choice Branch: แยกแยะระหว่าง System Menu Choice กับ In-Dialogue Narrative Choice
        3. ตรวจสอบข้อความตรงๆ ผ่าน _clean_text -> text_to_scene_id
        4. หากเป็นประโยคเนื้อเรื่อง ให้ค้นหาจากแถวข้างเคียงใน CSV (±10 แถว) ในไฟล์เดียวกัน
        """
        # 1. ตรวจสอบไฟล์ Database & Metadata ของเกม
        norm_file_lower = file_name.replace(".json", "").strip().lower() if file_name else ""
        DATABASE_FILES = {
            "enemies", "items", "skills", "weapons", "armors", "classes",
            "states", "troops", "mapinfos", "tilesets", "system"
        }
        if norm_file_lower in DATABASE_FILES:
            return f"{norm_file_lower.capitalize()}_Database"

        # 2. ตรวจสอบ Choice Branch: แยกแยะระหว่าง System Menu Choice กับ In-Dialogue Narrative Choice
        if csv_rows and 0 <= row_idx < len(csv_rows):
            cur_role = csv_rows[row_idx][5].strip() if len(csv_rows[row_idx]) > 5 else ""
            if cur_role == "Choice Branch":
                if not self.is_narrative_choice(row_idx, csv_rows):
                    # เป็นตัวเลือกเมนูระบบ/คำสั่งการกระทำของผู้เล่น (เช่น Exit, Phone, Pass Time)
                    return "System_Menu_Choices"
                # หากเป็น In-Dialogue Narrative Choice ให้ค้นหา Scene ID ตามเนื้อเรื่องต่อไป

        # 3. ค้นหาจากตัวข้อความเอง
        clean = self._clean_text(original_text)
        if clean and len(clean) >= 8:
            key = clean[:30]
            if key in self.text_to_scene_id:
                return self.text_to_scene_id[key]

        # 4. ค้นหาจากแถวข้างเคียงใน CSV (ขยายการตรวจจับรอบๆ แถวเป้าหมาย)
        if csv_rows and 0 <= row_idx < len(csv_rows):
            for offset in [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8, 9, -9, 10, -10]:
                adj_idx = row_idx + offset
                if 1 <= adj_idx < len(csv_rows):
                    adj_row = csv_rows[adj_idx]
                    adj_file = adj_row[2] if len(adj_row) > 2 else ""
                    if file_name and adj_file and adj_file.strip().lower() != file_name.strip().lower():
                        continue
                    adj_orig = adj_row[0] if len(adj_row) > 0 else ""
                    adj_clean = self._clean_text(adj_orig)
                    if adj_clean and len(adj_clean) >= 8:
                        adj_key = adj_clean[:30]
                        if adj_key in self.text_to_scene_id:
                            return self.text_to_scene_id[adj_key]

        # 5. Fallback: แมปตาม Prefix ไฟล์ (เช่น Map023 หรือ CommonEvents)
        norm_file = file_name.replace(".json", "").strip() if file_name else ""
        if norm_file:
            if norm_file.startswith("CommonEvent"):
                cand_scenes = self.scenes_by_prefix.get("CommonEvent", [])
                if cand_scenes:
                    return cand_scenes[0]
            elif norm_file in self.scenes_by_prefix:
                cand_scenes = self.scenes_by_prefix[norm_file]
                if cand_scenes:
                    return cand_scenes[0]
            return f"{norm_file}_General"

        return "General_Scene"

    def get_scene_context_by_id(
        self,
        scene_id: str,
        fallback_speakers: Optional[List[str]] = None,
        fallback_filename: str = ""
    ) -> str:
        """
        ดึงข้อมูลบริบทของฉาก (Scene Context Prompt Block) โดยตรงจาก Scene ID
        """
        try:
            if not scene_id or not isinstance(scene_id, str):
                return ""

            # กรณีตัวเลือกเมนูระบบ / UI Action Commands
            if scene_id == "System_Menu_Choices":
                return (
                    "### CONTEXT: SYSTEM UI & PLAYER MENU CHOICES\n"
                    "- **Type**: Direct Player Action Choices / System Menu Commands\n"
                    "- **Directive**: Translate as concise, natural, and punchy player action choices (e.g. 'Exit' -> 'ออก', 'Wait' -> 'รอ', 'Rest' -> 'พักผ่อน'). "
                    "If an item is an application name, proper noun, untranslatable brand, or acronym, preserve the original name as-is without transliteration."
                )

            # กรณีข้อมูล Database & Metadata ของเกม
            if scene_id.endswith("_Database"):
                db_name = scene_id.replace("_Database", "")
                db_lower = db_name.lower()
                if db_lower == "mapinfos":
                    return (
                        "### CONTEXT: GAME MAP LOCATION NAMES & ZONE LABELS (MapInfos)\n"
                        "- **Category**: Map Titles, Location Names & Room Labels\n"
                        "- **Directive**: Translate natural, player-facing room and town names cleanly into Thai (e.g. 'Office Room' -> 'ห้องออฟฟิศ', 'Central Hall' -> 'ห้องโถงกลาง'). "
                        "⚠️ CRITICAL MANDATORY: If an item is an internal engine code, technical identifier, CamelCase development tag, or developer draft note (e.g. starts with 'MAP' followed by digits, contains codes in parentheses like '(REC)', '(Useless)', or composite dev labels like 'BeachGameM2', 'BeachGameTutPurposes', 'CookInterface', 'Shinomiyalab2'), you MUST PRESERVE the exact identifier as-is without transliteration or alteration!"
                    )
                elif db_lower == "skills":
                    return (
                        "### CONTEXT: COMBAT SKILLS & BATTLE ACTION MESSAGES (Skills)\n"
                        "- **Category**: Combat Skill Names & Battle Action Templates\n"
                        "- **Directive**: Translate skill names with standard RPG action terms (e.g. 'Attack' -> 'โจมตี', 'Guard' -> 'ป้องกัน'). "
                        "⚠️ MANDATORY: Preserve placeholders like '%1' or '%2' exactly as-is in battle action templates (e.g. 'casts %1!' -> 'ร่ายเวท %1!')."
                    )
                elif db_lower == "states":
                    return (
                        "### CONTEXT: STATUS CONDITIONS & AFFLICTION MESSAGES (States)\n"
                        "- **Category**: Status Effects & Combat Affliction Messages\n"
                        "- **Directive**: Translate as standard RPG status conditions (e.g. 'Knockout' -> 'หมดสติ', 'Poison' -> 'ติดพิษ', 'falls asleep!' -> 'หลับไป!')."
                    )
                elif db_lower == "tilesets":
                    return (
                        "### CONTEXT: TILESET ENVIRONMENT LABELS (Tilesets)\n"
                        "- **Category**: Tileset Environment Labels & Zone Tags\n"
                        "- **Directive**: Translate environment tags accurately (e.g. 'Alleys' -> 'ตรอกซอย', 'Shopping2' -> 'ย่านการค้า 2')."
                    )
                elif db_lower == "system":
                    return (
                        "### CONTEXT: SYSTEM UI & CONTROLS (System)\n"
                        "- **Category**: Gameplay System Shortcuts & Interface Messages\n"
                        "- **Directive**: Translate control instructions and system tips clearly and accurately."
                    )
                else:
                    return (
                        f"### CONTEXT: GAME DATABASE ENTRIES ({db_name})\n"
                        f"- **Category**: {db_name} Names & Terminology\n"
                        f"- **Directive**: Translate accurately and faithfully as standard fantasy video game terms/names (e.g. 'Bat' -> 'ค้างคาว')."
                    )

            if not scene_id or scene_id == "General_Scene":
                if fallback_speakers:
                    return (
                        f"### SCENE NARRATIVE CONTEXT & MOOD:\n"
                        f"- **Scene / Location**: {fallback_filename or 'Game Scene'}\n"
                        f"- **Characters Present**: {', '.join(fallback_speakers)}\n"
                        f"- **Directive**: Faithfully express the conversational dynamics and intimacy between {', '.join(fallback_speakers)}."
                    )
                return ""

            extraction = self.extractions.get(scene_id)
            if not extraction:
                prefix = scene_id.split("_")[0]
                cand_scenes = self.scenes_by_prefix.get(prefix, [])
                if cand_scenes:
                    extraction = self.extractions.get(cand_scenes[0], {})

            if not isinstance(extraction, dict):
                extraction = {}

            scene_context = extraction.get("scene_context", "")
            characters_data = extraction.get("characters", [])
            dialogue_meta = extraction.get("dialogue_metadata", [])

            char_dynamics = []
            if isinstance(characters_data, list):
                for ch in characters_data:
                    if not isinstance(ch, dict):
                        continue
                    c_name = ch.get("character_name", "")
                    delta = ch.get("delta", {})
                    if not isinstance(delta, dict):
                        continue
                    relations = delta.get("relationships", [])
                    if not isinstance(relations, list):
                        continue
                    for rel in relations:
                        if not isinstance(rel, dict):
                            continue
                        t_name = rel.get("target_name", "")
                        roles_raw = rel.get("roles", [])
                        roles = ", ".join(roles_raw) if isinstance(roles_raw, list) else str(roles_raw)
                        affinity = rel.get("affinity", "")
                        intimacy = rel.get("intimacy", "")
                        speech_style = rel.get("speech_style", {})
                        derivation_rule = speech_style.get("derivation_rule", "") if isinstance(speech_style, dict) else ""
                        char_dynamics.append(
                            f"- {c_name} -> {t_name}: {roles} ({affinity}, {intimacy}) [Style: {derivation_rule}]"
                        )

            tones = set()
            emotions = set()
            if isinstance(dialogue_meta, list):
                for dm in dialogue_meta:
                    if not isinstance(dm, dict):
                        continue
                    if dm.get("tone"):
                        tones.add(str(dm["tone"]).replace("TON_", "").lower())
                    if dm.get("emotion"):
                        emotions.add(str(dm["emotion"]).replace("EMO_", "").lower())

            tone_str = ", ".join(tones) if tones else "natural narrative"
            emo_str = ", ".join(emotions) if emotions else "in-character expression"

            lines = [
                "### SCENE NARRATIVE CONTEXT & MOOD:",
                f"- **Scene ID / Location**: {scene_id}",
            ]
            if scene_context:
                lines.append(f"- **Scene Narrative Overview**: {scene_context}")
            if tone_str or emo_str:
                lines.append(f"- **Atmosphere & Emotional Tone**: Mood: {emo_str} | Tone: {tone_str}")
            if char_dynamics:
                lines.append("- **Character Relationships & Speech Dynamics**:")
                lines.extend(f"  {cd}" for cd in char_dynamics[:4])

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Notice while generating scene context by ID: {e}")
            return ""

    def get_scene_context_for_batch(self, batch_items: List[Dict[str, Any]]) -> str:
        """
        สกัดและจัดรูปแบบข้อมูลบริบทของฉาก (Scene Context Prompt Block) จาก batch_items
        """
        try:
            scene_id = self.find_scene_id_for_batch(batch_items)
            speakers = list(set(it.get("speaker") for it in batch_items if it.get("speaker")))
            filename = batch_items[0].get("file", "") or batch_items[0].get("filename", "Game Scene") if batch_items else "Game Scene"
            return self.get_scene_context_by_id(scene_id, fallback_speakers=speakers, fallback_filename=filename)
        except Exception as e:
            logger.warning(f"Notice while generating scene context: {e}")
            return ""

    def get_scene_dialogue_flow(
        self,
        scene_id: str,
        target_row_indices: List[int],
        csv_rows: Optional[List[List[str]]] = None,
        max_flow_lines: int = 15
    ) -> str:
        """
        ร้อยเรียงบทสนทนาแวดล้อมของฉาก (Scene Dialogue Flow) พร้อมคำแปลไทยเดิมที่มีอยู่ใน CSV:
        - ประโยคที่มีคำแปลไทยอยู่แล้ว จะแสดงคำแปลในวงเล็บ (Thai: ...) เพื่อให้ AI ซึมซับสำนวน
        - ไฮไลต์ประโยคเป้าหมายที่ต้องแปลด้วยเครื่องหมาย --> [TARGET #{id}]
        """
        if not target_row_indices or not scene_id or not isinstance(scene_id, str) or scene_id == "System_Menu_Choices" or scene_id.endswith("_Database"):
            return ""

        flow_lines = []

        # แนวทางที่ 1: ดึงจาก CSV โดยตรง (แม่นยำที่สุด เพราะเห็นทั้งคำแปลไทยเดิมและตำแหน่งจริง)
        if csv_rows:
            target_set = set(target_row_indices)
            selected_indices = set()
            for t_idx in target_row_indices:
                for off in range(-3, 4):
                    cand = t_idx + off
                    if 1 <= cand < len(csv_rows):
                        selected_indices.add(cand)

            sorted_indices = sorted(list(selected_indices))
            if len(sorted_indices) > max_flow_lines:
                sorted_indices = sorted_indices[:max_flow_lines]

            for r_idx in sorted_indices:
                r_data = csv_rows[r_idx]
                r_orig = re.sub(r"[\r\n]+", " ", r_data[0] if len(r_data) > 0 else "").strip()
                r_init = re.sub(r"[\r\n]+", " ", r_data[1] if len(r_data) > 1 else "").strip()
                r_disp = r_data[7].strip().lower() if len(r_data) > 7 else ""
                r_spk = r_data[6].strip() if len(r_data) > 6 and r_data[6].strip() else "Speaker"

                if not r_orig or r_disp != "yes":
                    continue

                if r_idx in target_set:
                    flow_lines.append(f"--> [TARGET #{r_idx}] [{r_spk}] {r_orig}")
                else:
                    has_th = any('\u0e00' <= ch <= '\u0e7f' for ch in r_init)
                    if has_th and r_init != r_orig:
                        flow_lines.append(f"    [{r_spk}] {r_orig} (Thai: {r_init})")
                    else:
                        flow_lines.append(f"    [{r_spk}] {r_orig}")

        # แนวทางที่ 2: ถ้าไม่มี CSV rows ให้ดึงจาก self.scenes_by_source ใน rpgm_scenes_v5.json
        elif scene_id in self.scenes_by_source:
            sc_data = self.scenes_by_source[scene_id]
            raw_text = sc_data.get("text", "")
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            for l in lines[:max_flow_lines]:
                flow_lines.append(f"    {l}")

        if not flow_lines:
            return ""

        return (
            "### SCENE DIALOGUE FLOW (SURROUNDING CONTEXT ONLY - DO NOT RE-TRANSLATE):\n" +
            "\n".join(flow_lines)
        )
