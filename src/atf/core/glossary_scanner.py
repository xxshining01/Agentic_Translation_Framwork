"""
Glossary Scanner Module for ATF
สแกนข้อความบทสนทนาเพื่อค้นหาชื่อตัวละคร (Characters), ไอเทม (Items), สถานที่ (Places), และศัพท์ระบบ (System/Skills)
ที่ปรากฏในบทสนทนาจริง และแปลงเป็น Prompt Block เพื่อส่งให้ LLM ล็อกคำแปล 100% แบบ 1:1
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("GlossaryScanner")

class GlossaryScanner:
    def __init__(self, glossary_path: Optional[str] = None, profiles_dir: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        
        if glossary_path is None:
            glossary_path = os.path.join(base_dir, "data", "tlas", "tlas_glossary.json")
        if profiles_dir is None:
            profiles_dir = os.path.join(base_dir, "data", "tlas", "profiles")
            
        self.glossary_path = glossary_path
        self.profiles_dir = profiles_dir
        
        self.glossary_data: Dict[str, Any] = {}
        self.characters: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.places: Dict[str, Any] = {}
        self.skills: Dict[str, Any] = {}
        self.system_ui: Dict[str, Any] = {}
        self.curated_profiles: Dict[str, Any] = {}
        
        # Regex map สำหรับการสแกนแบบ Whole-word case-insensitive
        self._compiled_regexes: Dict[str, List[tuple]] = {
            "Places": [],
            "Items": [],
            "Characters": [],
            "System": []
        }
        
        self.load_glossary()

    def _load_curated_profiles(self):
        """โหลดข้อมูล 26 ตัวละครหลักจาก Master_Prompt_Hybrid.md พร้อม Fallback เสมอ"""
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        prompt_path = os.path.join(base_dir, "testing files", "Master_Prompt_Hybrid.md")
        
        self.curated_profiles = {}
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # สกัดบล็อก YAML ของ characters แต่ละตัวใน CHARACTER_DB
                char_blocks = re.findall(r'-\s*\{([^}]+)\}', content, re.DOTALL)
                for blk in char_blocks:
                    m_name = re.search(r'name_en:\s*"?([^,\n"]+)"?', blk)
                    if not m_name:
                        continue
                    name_raw = m_name.group(1).strip()

                    m_gen = re.search(r'gender:\s*([^\s,]+)', blk)
                    m_role = re.search(r'role:\s*"([^"]+)"', blk)
                    m_pro = re.search(r'pronoun:\s*"([^"]+)"', blk)
                    m_per = re.search(r'personality:\s*"([^"]+)"', blk)
                    m_rel = re.search(r'relations:\s*"([^"]+)"', blk)

                    gen_val = m_gen.group(1).strip() if m_gen else ""
                    gender_th = "ชาย (Male)" if gen_val.upper() in ["M", "MALE"] else ("หญิง (Female)" if gen_val.upper() in ["F", "FEMALE"] else "")

                    entry = {
                        "name": name_raw,
                        "gender": gender_th,
                        "role": m_role.group(1).strip() if m_role else "",
                        "pronoun": m_pro.group(1).strip() if m_pro else "",
                        "personality": m_per.group(1).strip() if m_per else "",
                        "relations": m_rel.group(1).strip() if m_rel else ""
                    }

                    # รองรับชื่อที่มีสแลช เช่น "Rose/Rosegirl"
                    if "/" in name_raw:
                        for sub_name in name_raw.split("/"):
                            sub_clean = sub_name.strip()
                            if sub_clean:
                                self.curated_profiles[sub_clean] = entry
                    self.curated_profiles[name_raw] = entry
            except Exception as e:
                logger.warning(f"Could not parse Master_Prompt_Hybrid.md: {e}")

    def load_glossary(self):
        """โหลดและ Pre-compile คำศัพท์ทั้งหมดจาก tlas_glossary.json พร้อม Character Profiles"""
        self._load_curated_profiles()
        if not os.path.exists(self.glossary_path):
            logger.warning(f"Glossary file not found: {self.glossary_path}")
            return

        try:
            with open(self.glossary_path, "r", encoding="utf-8") as f:
                self.glossary_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load glossary: {e}")
            return

        self.characters = self.glossary_data.get("Characters", {})
        self.items = self.glossary_data.get("Items", {})
        self.places = self.glossary_data.get("Places", {})
        self.skills = self.glossary_data.get("Skills", {})
        self.system_ui = self.glossary_data.get("System_UI", {})

        self._compile_patterns()
        logger.info(
            f"GlossaryScanner ready: {len(self.characters)} Characters, "
            f"{len(self.items)} Items, {len(self.places)} Places, "
            f"{len(self.curated_profiles)} Curated Profiles"
        )

    def _compile_patterns(self):
        """สร้าง Regex สำหรับตรวจจับคำศัพท์แบบ Whole-word โดยเรียงจากคำยาวไปคำสั้น เพื่อป้องกัน Substring clashing"""
        # 1. Places
        places_sorted = sorted(self.places.keys(), key=len, reverse=True)
        self._compiled_regexes["Places"] = [
            (term, self._create_word_regex(term), self.places[term])
            for term in places_sorted if len(term.strip()) > 1
        ]

        # 2. Items
        items_sorted = sorted(self.items.keys(), key=len, reverse=True)
        self._compiled_regexes["Items"] = [
            (term, self._create_word_regex(term), self.items[term])
            for term in items_sorted if len(term.strip()) > 1
        ]

        # 3. Characters (รวมชื่อหลัก และ Aliases)
        char_patterns = []
        for char_name, cinfo in self.characters.items():
            if not isinstance(cinfo, dict):
                continue
            char_patterns.append((char_name, self._create_word_regex(char_name), cinfo, char_name))
            aliases = cinfo.get("aliases", [])
            if isinstance(aliases, list):
                for alias_obj in aliases:
                    if isinstance(alias_obj, dict):
                        alias_name = alias_obj.get("name", "")
                    elif isinstance(alias_obj, str):
                        alias_name = alias_obj
                    else:
                        continue
                    if alias_name and len(alias_name) > 1 and alias_name.lower() != char_name.lower():
                        char_patterns.append((alias_name, self._create_word_regex(alias_name), cinfo, char_name))
        
        char_patterns.sort(key=lambda x: len(x[0]), reverse=True)
        self._compiled_regexes["Characters"] = char_patterns

        # 4. Skills / System (เก็บไว้สำหรับการแปล Speaker Tag แต่ไม่ส่งเข้า Prompt บทสนทนา)
        sys_terms = {}
        sys_terms.update(self.skills)
        sys_terms.update(self.system_ui)
        sys_sorted = sorted(sys_terms.keys(), key=len, reverse=True)
        self._compiled_regexes["System"] = [
            (term, self._create_word_regex(term), sys_terms[term])
            for term in sys_sorted if len(term.strip()) > 2
        ]

    def _create_word_regex(self, term: str) -> re.Pattern:
        """สร้าง Regex เพื่อจับคำแบบ Whole Word (รองรับเครื่องหมายพิเศษ เช่น 's หรือ +)"""
        escaped = re.escape(term)
        # ถ้าขึ้นต้นด้วยตัวอักษร ให้มี word boundary นำหน้า
        prefix = r'\b' if re.match(r'^\w', term) else ''
        suffix = r'\b' if re.match(r'.*\w$', term) else ''
        return re.compile(f"{prefix}{escaped}{suffix}", re.IGNORECASE)

    def scan_text(self, text: str) -> Dict[str, Dict[str, Any]]:
        """สแกนข้อความเดียวแล้วส่งคืนคำศัพท์ที่พบแยกตามหมวดหมู่"""
        return self.scan_dialogue_batch([text])

    def scan_dialogue_batch(self, dialogue_texts: List[str], speakers: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        สแกนรายการประโยคบทสนทนาทั้งหมดใน Batch
        ส่งคืน Dict ของคำศัพท์ที่ปรากฏจริงแยกหมวดหมู่:
        - Places: เฉพาะสถานที่ที่ปรากฏในข้อความ
        - Items: เฉพาะไอเทมที่ปรากฏในข้อความ
        - Characters: ตัวละครที่เป็น Speakers, Listener และคนที่ถูกเอ่ยถึงในข้อความ
        """
        combined_text = " \n ".join(dialogue_texts)
        # ลบ Code ควบคุมของเกมเพื่อป้องกัน Regex สับสน
        clean_text = re.sub(r'\\[a-zA-Z]+(?:\[\d+\])?', ' ', combined_text)
        clean_text = re.sub(r'<.*?>', ' ', clean_text)

        matched: Dict[str, Dict[str, Any]] = {
            "Places": {},
            "Items": {},
            "Characters": {}
        }

        # 1. สแกน Places ที่ปรากฏในข้อความ
        for term, regex, data in self._compiled_regexes["Places"]:
            if regex.search(clean_text):
                matched["Places"][term] = data

        # 2. สแกน Items ที่ปรากฏในข้อความ
        for term, regex, data in self._compiled_regexes["Items"]:
            if regex.search(clean_text):
                matched["Items"][term] = data

        # 3. รวบรวมตัวละครทั้งหมดในฉาก (Speakers + ผู้ถูกเอ่ยถึง)
        context_char_names = set()
        if speakers:
            for spk in speakers:
                if spk:
                    context_char_names.add(spk.strip())

        for term, regex, data, canonical_name in self._compiled_regexes["Characters"]:
            if regex.search(clean_text):
                context_char_names.add(canonical_name)

        context_char_list = list(context_char_names)

        # เติมข้อมูล Character Profile สำหรับตัวละครแต่ละตัวที่อยู่ในบริบทของ Batch นี้
        for char_name in context_char_list:
            char_data = self.characters.get(char_name, {})
            matched["Characters"][char_name] = self._enrich_character_info(
                char_name, char_data, context_characters=context_char_list
            )

        return matched

    def _enrich_character_info(self, name: str, char_data: Dict[str, Any], context_characters: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        ดึงและประกอบข้อมูล Character Profile อย่างสมบูรณ์:
        - สรรพนาม (แทนตัวเอง, เรียกคู่สนทนา, บุรุษที่ 3), คำลงท้าย, เพศ, บทบาท, บุคลิก
        - ความสัมพันธ์เฉพาะคู่ (Pairwise Relationship Dynamics) กับ Listener หรือคนที่ถูกเอ่ยถึงใน Batch
        """
        if context_characters is None:
            context_characters = []

        curated = self.curated_profiles.get(name, {})

        info = {
            "name": name,
            "th": char_data.get("th", name),
            "gender": curated.get("gender", ""),
            "role": curated.get("role", "") or char_data.get("role_category", ""),
            "pronoun_summary": curated.get("pronoun", ""),
            "self_pronoun": "",
            "target_pronoun": "",
            "third_person_pronoun": "",
            "ending_particle": "",
            "personality": curated.get("personality", ""),
            "relations_summary": curated.get("relations", ""),
            "pair_rules": []
        }

        # 1. ดึงจาก data/tlas/profiles/{name}.json
        pdata = None
        if self.profiles_dir and os.path.exists(self.profiles_dir):
            prof_file = os.path.join(self.profiles_dir, f"{name}.json")
            if not os.path.exists(prof_file):
                for fname in os.listdir(self.profiles_dir):
                    if fname.lower() == f"{name.lower()}.json":
                        prof_file = os.path.join(self.profiles_dir, fname)
                        break

            if os.path.exists(prof_file):
                try:
                    with open(prof_file, "r", encoding="utf-8") as pf:
                        pdata = json.load(pf)
                except Exception:
                    pass

        if pdata:
            ident = pdata.get("identity", {})
            g = ident.get("gender", "").upper()
            if not info["gender"]:
                if g == "MALE":
                    info["gender"] = "ชาย (Male)"
                elif g == "FEMALE":
                    info["gender"] = "หญิง (Female)"

            bss = pdata.get("base_speech_style", {})
            info["self_pronoun"] = bss.get("self_pronoun", "")
            info["target_pronoun"] = bss.get("target_pronoun", "")
            info["third_person_pronoun"] = bss.get("third_person_pronoun", "")
            info["ending_particle"] = bss.get("ending_particle", "")

            # ตรวจสอบความสัมพันธ์เฉพาะคู่กับ context_characters
            raw_rels = pdata.get("relationships", [])
            if not raw_rels and "base_state" in pdata:
                raw_rels = pdata.get("base_state", {}).get("relationships", [])

            for rel in raw_rels:
                tgt_name = rel.get("target_name", "")
                if tgt_name in context_characters and tgt_name != name:
                    sp = rel.get("speech_style", {}) or rel.get("specific_speech", {})
                    if sp:
                        tgt_self = sp.get("self_pronoun") or info["self_pronoun"]
                        tgt_target = sp.get("target_pronoun") or info["target_pronoun"]
                        tgt_end = sp.get("ending_particle") or info["ending_particle"]
                        info["pair_rules"].append({
                            "target": tgt_name,
                            "self_pronoun": tgt_self,
                            "target_pronoun": tgt_target,
                            "ending_particle": tgt_end
                        })

        # 2. ถ้าสรรพนามยังว่าง ให้เติมจาก Curated Profiles
        if not info["self_pronoun"] and info["pronoun_summary"] and info["pronoun_summary"] != "-":
            p_parts = info["pronoun_summary"].split("(")[0].strip().split("/")
            if len(p_parts) >= 1 and p_parts[0].strip():
                info["self_pronoun"] = p_parts[0].strip()
            if len(p_parts) >= 2 and p_parts[1].strip():
                info["target_pronoun"] = p_parts[1].strip()
            if len(p_parts) >= 3 and p_parts[2].strip():
                info["third_person_pronoun"] = p_parts[2].strip()

        # คำลงท้ายเริ่มต้นถ้ายังว่าง
        if not info["ending_particle"]:
            if "ชาย" in info["gender"]:
                info["ending_particle"] = "ครับ"
            elif "หญิง" in info["gender"]:
                info["ending_particle"] = "ค่ะ"

        # เพิ่ม Curated Special Pair Dynamic สำหรับคู่สนทนาหลัก
        if name == "Dan" and "Shion" in context_characters:
            if not any(r["target"] == "Shion" for r in info["pair_rules"]):
                info["pair_rules"].append({
                    "target": "Shion",
                    "self_pronoun": "ผม",
                    "target_pronoun": "คุณ (หรือ เธอ)",
                    "ending_particle": "ครับ"
                })
        elif name == "Shion" and "Dan" in context_characters:
            if not any(r["target"] == "Dan" for r in info["pair_rules"]):
                info["pair_rules"].append({
                    "target": "Dan",
                    "self_pronoun": "ฉัน",
                    "target_pronoun": "คุณ",
                    "ending_particle": "ค่ะ"
                })
        elif name == "Lily" and ("Dan" in context_characters or "Shion" in context_characters):
            for tgt in ["Dan", "Shion"]:
                if tgt in context_characters and not any(r["target"] == tgt for r in info["pair_rules"]):
                    info["pair_rules"].append({
                        "target": tgt,
                        "self_pronoun": "หนู",
                        "target_pronoun": f"พี่ {tgt}",
                        "ending_particle": "ค่ะ / จ้ะ"
                    })
        elif name == "Lucas" and ("Dan" in context_characters or "Shion" in context_characters):
            for tgt in ["Dan", "Shion"]:
                if tgt in context_characters and not any(r["target"] == tgt for r in info["pair_rules"]):
                    info["pair_rules"].append({
                        "target": tgt,
                        "self_pronoun": "ผม",
                        "target_pronoun": f"พี่ {tgt}",
                        "ending_particle": "ครับ"
                    })

        return info

    def format_glossary_for_prompt(self, matched: Dict[str, Dict[str, Any]]) -> str:
        """
        แปลงคำศัพท์และ Character Profiles ที่ Match ได้เป็น Markdown Block ชัดเจนสำหรับส่งเข้า Prompt ให้ LLM:
        1. Character Names (MANDATORY 1:1 Name Mapping)
        2. Places & Locations (ถ้ามี)
        3. Items & Objects (ถ้ามี)
        4. Character Speech Profiles & Relationship Dynamics (STRICT PRONOUNS & TONE)
        (ไม่ใส่หมวด System / Skills ตามข้อกำหนด)
        """
        sections = []

        chars = matched.get("Characters", {})
        places = matched.get("Places", {})
        items = matched.get("Items", {})

        # 1. Character Names (MANDATORY 1:1 Name Translation - STRICT NO TRANSLITERATION)
        if chars:
            name_lines = [
                "- **Character Names (MANDATORY 1:1 Name Translation - STRICT NO TRANSLITERATION)**:",
                "  * ⚠️ CRITICAL MANDATORY RULE: If a character's mapped name is in English (e.g. `Lucy` -> **Lucy**, `Dan` -> **Dan**), you MUST preserve the exact English name (Latin letters) inside the Thai dialogue! NEVER transliterate or phonetically spell English-locked names in Thai (e.g. NEVER write 'ลูซี่', 'แดน', 'ชิออน')!"
            ]
            for name, cinfo in chars.items():
                th_name = cinfo.get("th", name)
                if th_name == name:
                    name_lines.append(f"  * `{name}` -> **{th_name}** (MUST remain '{th_name}' in English - DO NOT transliterate to Thai)")
                else:
                    name_lines.append(f"  * `{name}` -> **{th_name}**")
            sections.append("\n".join(name_lines))

        # 2. Places & Locations (Hard-Locked 1:1) - แสดงเฉพาะเมื่อมีในบทสนทนา
        if places:
            place_lines = ["- **Places & Locations (MANDATORY 1:1 LOCK - Exact Thai translation only)**:"]
            for name, pinfo in places.items():
                th_name = pinfo.get("th", "")
                place_lines.append(f"  * `{name}` -> **{th_name}**")
            sections.append("\n".join(place_lines))

        # 3. Items (Hard-Locked 1:1) - แสดงเฉพาะเมื่อมีในบทสนทนา
        if items:
            item_lines = ["- **Items (MANDATORY 1:1 LOCK - Exact Thai translation only)**:"]
            for name, iinfo in items.items():
                th_name = iinfo.get("th", "")
                item_lines.append(f"  * `{name}` -> **{th_name}**")
            sections.append("\n".join(item_lines))

        # 4. Character Speech Profiles & Relationship Dynamics (STRICT PRONOUNS & TONE)
        profile_lines = []
        for name, cinfo in chars.items():
            has_profile = bool(
                cinfo.get("personality") or
                cinfo.get("self_pronoun") or
                cinfo.get("pair_rules") or
                cinfo.get("pronoun_summary") or
                (cinfo.get("gender") and cinfo.get("role"))
            )
            if not has_profile:
                continue

            th_name = cinfo.get("th", name)
            profile_lines.append(f"  * `{name}` ({th_name}):")
            
            # บรรทัดเพศและบทบาท
            meta_parts = []
            if cinfo.get("gender"):
                meta_parts.append(f"เพศ: {cinfo['gender']}")
            if cinfo.get("role"):
                meta_parts.append(f"บทบาท: {cinfo['role']}")
            if meta_parts:
                profile_lines.append(f"    - {' | '.join(meta_parts)}")

            # บรรทัดสรรพนาม
            pro_parts = []
            if cinfo.get("self_pronoun"):
                pro_parts.append(f"แทนตัวเอง = **{cinfo['self_pronoun']}**")
            if cinfo.get("target_pronoun"):
                pro_parts.append(f"เรียกคู่สนทนา = **{cinfo['target_pronoun']}**")
            if cinfo.get("third_person_pronoun"):
                pro_parts.append(f"บุรุษที่ 3 = **{cinfo['third_person_pronoun']}**")
            elif cinfo.get("pronoun_summary") and not pro_parts:
                pro_parts.append(f"สรรพนาม: {cinfo['pronoun_summary']}")
            if pro_parts:
                profile_lines.append(f"    - คำสรรพนามพื้นฐาน: {' | '.join(pro_parts)}")

            # บรรทัดคำลงท้าย
            if cinfo.get("ending_particle"):
                profile_lines.append(f"    - คำลงท้าย: **{cinfo['ending_particle']}**")

            # บรรทัดบุคลิก/น้ำเสียง
            if cinfo.get("personality"):
                profile_lines.append(f"    - บุคลิก/น้ำเสียง: {cinfo['personality']}")

            # บรรทัดความสัมพันธ์กับตัวละครในฉากนี้
            if cinfo.get("pair_rules"):
                profile_lines.append(f"    - ความสัมพันธ์กับตัวละครในฉากนี้:")
                for rule in cinfo["pair_rules"]:
                    tgt = rule["target"]
                    r_parts = []
                    if rule.get("self_pronoun"):
                        r_parts.append(f"แทนตัวเอง = **{rule['self_pronoun']}**")
                    if rule.get("target_pronoun"):
                        r_parts.append(f"เรียกคู่สนทนา = **{rule['target_pronoun']}**")
                    if rule.get("ending_particle"):
                        r_parts.append(f"คำลงท้าย = **{rule['ending_particle']}**")
                    profile_lines.append(f"      * กับ `{tgt}`: {' | '.join(r_parts)}")

        if profile_lines:
            header_profiles = "- **Character Speech Profiles & Relationship Dynamics (STRICT PRONOUNS & TONE)**:\n"
            sections.append(header_profiles + "\n".join(profile_lines))

        if not sections:
            return ""

        header = "### RELEVANT GLOSSARY & CHARACTER GUIDANCE (MANDATORY 1:1 LOCK):\n"
        header += "Translate all occurrences of the following terms strictly using the provided Thai equivalents and speak with the exact pronouns specified below:\n"
        return header + "\n\n".join(sections)

    def translate_speaker(self, speaker: str) -> str:
        """
        แปลงชื่อ Speaker เป็นภาษาไทยตาม Glossary:
        - Dan -> Dan
        - Mayor -> นายกเทศมนตรี
        - Masaru -> Masaru
        """
        if not speaker:
            return ""

        spk_clean = speaker.strip()

        # 1. ค้นหาใน Characters ตรงๆ
        if spk_clean in self.characters:
            th = self.characters[spk_clean].get("th")
            if th:
                return th

        # 2. ค้นหาแบบ Case-insensitive หรือ Aliases
        for name, cinfo in self.characters.items():
            if not isinstance(cinfo, dict):
                continue
            if name.lower() == spk_clean.lower():
                return cinfo.get("th", name)
            aliases = cinfo.get("aliases", [])
            if isinstance(aliases, list):
                for alias_obj in aliases:
                    if isinstance(alias_obj, dict):
                        alias_name = alias_obj.get("name", "")
                        alias_th = alias_obj.get("th", cinfo.get("th", name))
                    elif isinstance(alias_obj, str):
                        alias_name = alias_obj
                        alias_th = cinfo.get("th", name)
                    else:
                        continue
                    if alias_name.lower() == spk_clean.lower():
                        return alias_th

        # 3. ค้นหาใน Places (กรณี Speaker เป็นชื่อสถานที่/ร้าน)
        if spk_clean in self.places:
            return self.places[spk_clean].get("th", spk_clean)

        # 4. ค้นหาใน System_UI
        if spk_clean in self.system_ui:
            return self.system_ui[spk_clean].get("th", spk_clean)

        return spk_clean

    def translate_speaker_tag(self, prefix: str) -> str:
        """
        แปลงทั้งแท็ก Speaker รองรับทุกรูปแบบอย่างสมบูรณ์:
        - '\\n<Dan:>' -> '\\n<Dan:>'
        - '\\n<Mayor:>' -> '\\n<นายกเทศมนตรี:>'
        - '<Mayor>' -> '<นายกเทศมนตรี>'
        - '\\n<Masaru:> ' -> '\\n<Masaru:> '
        - '\\n<\\C[0]Hikari:\\C>' -> '\\n<\\C[0]Hikari:\\C>'
        - '\\n<\\C[27]Pink hair Woman\\C:>' -> '\\n<\\C[27]หญิงผมชมพู\\C:>'
        - '\\n<\\C[18]\\fb???\\C\\fb:>' -> '\\n<\\C[18]\\fb???\\C\\fb:>'
        """
        if not prefix:
            return ""

        m = re.match(r"^(\s*\\n)?<([^>]+)>(\s*)", prefix)
        if not m:
            return prefix

        lead = m.group(1) or ""
        inner = m.group(2)
        trailing = m.group(3) or ""

        # สกัดชื่อผู้พูดโดยตัด control codes เช่น \C[27], \C, \fb, \fi และเครื่องหมายโคลอน
        clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner).replace(":", "").strip()
        if not clean_name:
            return prefix

        # แปลชื่อผู้พูดตาม Glossary
        spk_th = self.translate_speaker(clean_name)

        # แทนที่ clean_name เดิมด้วย spk_th ใน inner content โดยรักษา control codes เดิมไว้ครบถ้วน
        new_inner = inner.replace(clean_name, spk_th)
        return f"{lead}<{new_inner}>{trailing}"


