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
    def __init__(self, glossary_path: Optional[str] = None, profiles_dir: Optional[str] = None, matrix_path: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        
        if glossary_path is None:
            glossary_path = os.path.join(base_dir, "data", "tlas", "tlas_glossary.json")
        if profiles_dir is None:
            profiles_dir = os.path.join(base_dir, "data", "tlas", "profiles")
        if matrix_path is None:
            matrix_path = os.path.join(base_dir, "data", "tlas", "global_pronoun_matrix.json")
            
        self.glossary_path = glossary_path
        self.profiles_dir = profiles_dir
        self.matrix_path = matrix_path
        
        self.glossary_data: Dict[str, Any] = {}
        self.characters: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.places: Dict[str, Any] = {}
        self.skills: Dict[str, Any] = {}
        self.system_ui: Dict[str, Any] = {}
        self.curated_profiles: Dict[str, Any] = {}
        self.global_pronoun_matrix: List[Dict[str, Any]] = []
        self.specific_pair_rules: List[Dict[str, Any]] = []
        self.demographic_rules: List[Dict[str, Any]] = []
        self._profile_cache: Dict[str, Any] = {}
        
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

        # โหลด Global Pronoun Matrix สากล (ถ้ามี)
        self.specific_pair_rules = []
        self.demographic_rules = []
        if self.matrix_path and os.path.exists(self.matrix_path):
            try:
                with open(self.matrix_path, "r", encoding="utf-8") as mf:
                    raw_matrix = json.load(mf)
                if isinstance(raw_matrix, dict):
                    self.specific_pair_rules = raw_matrix.get("specific_pair_rules", [])
                    self.demographic_rules = raw_matrix.get("demographic_rules", [])
                    self.global_pronoun_matrix = self.specific_pair_rules
                elif isinstance(raw_matrix, list):
                    self.specific_pair_rules = raw_matrix
                    self.demographic_rules = []
                    self.global_pronoun_matrix = raw_matrix
                logger.info(f"Loaded {len(self.specific_pair_rules)} specific pairwise rules & {len(self.demographic_rules)} demographic rules from pronoun matrix.")
            except Exception as e:
                logger.warning(f"Could not load global pronoun matrix: {e}")

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
        # ถ้าเป็นคำภาษาอังกฤษ/ตัวเลข ให้ใช้ word boundary \b
        # แต่ถ้าเป็นภาษาญี่ปุ่น/CJK ห้ามใช้ \b เพราะในภาษาญี่ปุ่นไม่มีช่องว่างคำ (เช่น 遠藤さん)
        if re.match(r'^[A-Za-z0-9_]+$', term):
            return re.compile(rf'\b{escaped}\b', re.IGNORECASE)
        return re.compile(escaped, re.IGNORECASE)

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

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """โหลดและ Cache ข้อมูล Character Profile จาก data/tlas/profiles/{name}.json"""
        if name in self._profile_cache:
            return self._profile_cache[name]

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

        self._profile_cache[name] = pdata
        return pdata

    def _infer_persona(self, pdata: Dict[str, Any]) -> str:
        """วิเคราะห์ Persona Category (THUG_VULGAR, CALM_POLITE, CHARMING_MANIPULATIVE, ELDER_AFFECTIONATE, CHILD_POLITE)"""
        if not pdata:
            return "CALM_POLITE"
        if "demographic_persona" in pdata:
            return pdata["demographic_persona"]

        ident = pdata.get("identity", {})
        age = ident.get("age", "").upper()
        if age == "CHILD":
            return "CHILD_POLITE"
        if age == "ELDER":
            return "ELDER_AFFECTIONATE"

        bs = pdata.get("base_state", {})
        per_tags = [x.get("tag", "") for x in bs.get("personality", [])]
        hab_tags = [x.get("tag", "") for x in bs.get("speech_habit", [])]
        all_tags = set(per_tags + hab_tags)

        if any(t in all_tags for t in ["PER_SOC_VULGAR", "PER_SOC_ARROGANT", "PER_SOC_PEEPING", "SPR_SLANG", "SPR_BLUNT"]):
            return "THUG_VULGAR"
        if any(t in all_tags for t in ["PER_SOC_CHARMING", "PER_MIND_MANIPULATIVE", "SPR_SMOOTH_TALK"]):
            return "CHARMING_MANIPULATIVE"

        return "CALM_POLITE"

    def _match_demographic_rule(self, speaker_persona: str, target_pdata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """จับคู่ Demographic Identity (Gender, Age, Number) กับ speaker_persona ใน demographic_rules"""
        if not self.demographic_rules:
            return None

        if not target_pdata:
            for rule in self.demographic_rules:
                if rule.get("speaker_persona") == speaker_persona and rule.get("listener_match", {}).get("age") == "ADULT":
                    return rule.get("speech_style", {})
            return None

        t_ident = target_pdata.get("identity", {})
        t_gender = t_ident.get("gender", "UNKNOWN").upper()
        t_age = t_ident.get("age", "ADULT").upper()
        t_num = t_ident.get("number", "SINGULAR").upper()

        # 1. เช็กกรณีผู้ฟังเป็นพหูพจน์ (PLURAL)
        if t_num == "PLURAL":
            for rule in self.demographic_rules:
                if rule.get("speaker_persona") == speaker_persona:
                    m = rule.get("listener_match", {})
                    if m.get("number") == "PLURAL":
                        return rule.get("speech_style", {})

        # 2. เช็กคู่เพศและช่วงวัยตรงกัน (Gender + Age)
        for rule in self.demographic_rules:
            if rule.get("speaker_persona") == speaker_persona:
                m = rule.get("listener_match", {})
                if m.get("number", "SINGULAR") == t_num:
                    if m.get("gender") == t_gender and m.get("age") == t_age:
                        return rule.get("speech_style", {})

        # 3. เช็กช่วงวัย (Age Only)
        for rule in self.demographic_rules:
            if rule.get("speaker_persona") == speaker_persona:
                m = rule.get("listener_match", {})
                if m.get("number", "SINGULAR") == t_num:
                    if "age" in m and "gender" not in m and m["age"] == t_age:
                        return rule.get("speech_style", {})

        return None

    def _enrich_character_info(self, name: str, char_data: Dict[str, Any], context_characters: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        ดึงและประกอบข้อมูล Character Profile อย่างสมบูรณ์:
        - สรรพนามพื้นฐาน: แสดงเฉพาะแทนตัวเองและคำลงท้าย (ไม่ยัดเยียด target_pronoun ลงใน base)
        - ความสัมพันธ์เฉพาะคู่ (Pairwise Relationship Dynamics) กับ Listener หรือคนที่อยู่ในฉาก:
          1. จับคู่จาก Specific Rules / relationships ก่อน
          2. หากไม่มี ให้ Match จาก Identity Demographic Matrix (Gender, Age, Number) อัตโนมัติ
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
        pdata = self.get_profile(name)

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
            # target_pronoun และ third_person_pronoun ใน base_speech_style จะถูกเว้นว่างไว้เพื่อป้องกัน Model Drift
            info["target_pronoun"] = bss.get("target_pronoun", "")
            info["third_person_pronoun"] = bss.get("third_person_pronoun", "")
            info["ending_particle"] = bss.get("ending_particle", "")

            speaker_persona = self._infer_persona(pdata)

            # ตรวจสอบความสัมพันธ์เฉพาะคู่กับ context_characters จาก Specific Pairwise Rules
            if self.specific_pair_rules and context_characters:
                for rule in self.specific_pair_rules:
                    if rule.get("speaker") == name and rule.get("listener") in context_characters and rule.get("listener") != name:
                        tgt_name = rule.get("listener")
                        sp = rule.get("speech_style", {})
                        if sp and not any(r["target"] == tgt_name for r in info["pair_rules"]):
                            tgt_self = sp.get("self_pronoun") or info["self_pronoun"]
                            tgt_target = sp.get("target_pronoun") or ""
                            tgt_end = sp.get("ending_particle") or info["ending_particle"]
                            info["pair_rules"].append({
                                "target": tgt_name,
                                "self_pronoun": tgt_self,
                                "target_pronoun": tgt_target,
                                "ending_particle": tgt_end
                            })

            # ตรวจสอบเพิ่มเติมจาก relationships ภายในตัว Profile เอง
            raw_rels = pdata.get("relationships", [])
            if not raw_rels and "base_state" in pdata:
                raw_rels = pdata.get("base_state", {}).get("relationships", [])

            for rel in raw_rels:
                tgt_name = rel.get("target_name", "")
                if tgt_name in context_characters and tgt_name != name:
                    if not any(r["target"] == tgt_name for r in info["pair_rules"]):
                        sp = rel.get("speech_style", {}) or rel.get("specific_speech", {})
                        if sp:
                            tgt_self = sp.get("self_pronoun") or info["self_pronoun"]
                            tgt_target = sp.get("target_pronoun") or ""
                            tgt_end = sp.get("ending_particle") or info["ending_particle"]
                            info["pair_rules"].append({
                                "target": tgt_name,
                                "self_pronoun": tgt_self,
                                "target_pronoun": tgt_target,
                                "ending_particle": tgt_end
                            })

            # ตรวจสอบตัวละครคู่สนทนาที่ยังไม่มี Pair Rule: ทำ Dynamic Identity Demographic Resolution
            if context_characters and self.demographic_rules:
                for tgt_name in context_characters:
                    if tgt_name != name and not any(r["target"] == tgt_name for r in info["pair_rules"]):
                        tgt_pdata = self.get_profile(tgt_name)
                        demo_style = self._match_demographic_rule(speaker_persona, tgt_pdata)
                        if demo_style:
                            tgt_target = demo_style.get("target_pronoun", "คุณ")
                            tgt_end = demo_style.get("ending_particle") or info["ending_particle"]
                            info["pair_rules"].append({
                                "target": tgt_name,
                                "self_pronoun": info["self_pronoun"],
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
                "- **Character Names (MANDATORY 1:1 Name Translation - Use exact Thai spelling specified)**:"
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
        - Angle Brackets: '\\n<Dan:>', '<Mayor>', '\\n<\\C[0]Hikari:\\C>'
        - Lenticular Brackets: '【凛】', '【夫】\\n', '\\n【西原】'
        - Square Brackets: '[Dan]', '\\n[凛]'
        """
        if not prefix:
            return ""

        # 1. Lenticular Brackets: 【...】
        m_len = re.match(r"^(\s*\\n|\s*\n)?【([^】]+)】([\s\:\n]*)", prefix)
        if m_len:
            lead = m_len.group(1) or ""
            inner = m_len.group(2)
            trailing = m_len.group(3) or ""
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner).replace(":", "").strip()
            if clean_name:
                spk_th = self.translate_speaker(clean_name)
                new_inner = inner.replace(clean_name, spk_th)
                return f"{lead}【{new_inner}】{trailing}"
            return prefix

        # 2. Angle Brackets: <...>
        m_ang = re.match(r"^(\s*\\n|\s*\n)?<([^>]+)>([\s\:\n]*)", prefix)
        if m_ang:
            lead = m_ang.group(1) or ""
            inner = m_ang.group(2)
            trailing = m_ang.group(3) or ""
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner).replace(":", "").strip()
            if clean_name:
                spk_th = self.translate_speaker(clean_name)
                new_inner = inner.replace(clean_name, spk_th)
                return f"{lead}<{new_inner}>{trailing}"
            return prefix

        # 3. Square Brackets: [...] (เมื่อไม่ใช่ RPG Maker control tags เช่น \\C[0], \\V[1])
        m_sq = re.match(r"^(\s*\\n|\s*\n)?\[([^\]]+)\]([\s\:\n]*)", prefix)
        if m_sq and not re.match(r"^\\[A-Za-z]+", prefix):
            lead = m_sq.group(1) or ""
            inner = m_sq.group(2)
            trailing = m_sq.group(3) or ""
            clean_name = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", inner).replace(":", "").strip()
            if clean_name:
                spk_th = self.translate_speaker(clean_name)
                new_inner = inner.replace(clean_name, spk_th)
                return f"{lead}[{new_inner}]{trailing}"
            return prefix

        return prefix


