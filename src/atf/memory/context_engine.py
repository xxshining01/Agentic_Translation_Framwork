import logging
import ahocorasick
import yaml
import re
import os
import glob
import json
from typing import Dict, List, Optional

from ..core.models import TranslationToken, ContextData

logger = logging.getLogger(__name__)

class ContextEngine:
    """
    โมดูลสำหรับสืบค้นข้อมูลและเตรียม Context (True Context-Aware RAG)
    """
    def __init__(self, tlas_dir: Optional[str] = None):
        self.glossary_automaton = ahocorasick.Automaton()
        self.is_automaton_built = False
        
        self.character_db: Dict[str, dict] = {}
        
        self.tm_db: List[Dict[str, str]] = []
        self.exact_tm_db: Dict[str, str] = {} 
        
        self.style_rules: str = ""
        self.symbol_engine_rules: str = ""
        
        self.context_scopes: Dict[str, str] = {}
        
        # New RAG fields
        self.rag_scenes: List[dict] = []
        self.scene_index: Dict[str, List[dict]] = {}
        self.story_timeline: Dict[str, dict] = {}

        if tlas_dir:
            self.load_tlas_data(tlas_dir)

    def has_scope(self, group_id: str) -> bool:
        return group_id in self.context_scopes
        
    def get_scope(self, group_id: str) -> Optional[str]:
        return self.context_scopes.get(group_id)
        
    def set_scope(self, group_id: str, scope: str):
        self.context_scopes[group_id] = scope

    def load_master_prompt_md(self, filepath: str):
        """
        โหลดกฎการแปล (Style Rules) จาก Master Prompt อย่างเดียว
        ตัวละครและ Glossary จะโหลดจาก TLAS RAG แทน
        """
        logger.info(f"[ContextEngine] Loading Master Rules from {filepath}")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            style_match = re.search(r"## 2\. STYLE_RULES.*?\"\"\"\n(.*?)\n\"\"\"", content, re.DOTALL)
            if style_match:
                self.style_rules = style_match.group(1).strip()
            
            symbol_match = re.search(r"## 3\. SYMBOL_INTEGRITY_ENGINE.*?```python\n(.*?)\n```", content, re.DOTALL)
            if symbol_match:
                self.symbol_engine_rules = symbol_match.group(1).strip()

        except Exception as e:
            logger.error(f"[ContextEngine] Failed to load Master Prompt: {e}")

    def load_tlas_data(self, tlas_dir: str):
        """โหลดข้อมูล RAG, Profiles และ Glossary จากระบบ TLAS"""
        logger.info(f"[ContextEngine] Loading TLAS RAG data from {tlas_dir}")
        
        # 1. Load Glossary (Supports both nested category schemas and flat schemas)
        glossary_path = os.path.join(tlas_dir, "tlas_glossary.json")
        if not os.path.exists(glossary_path):
            glossary_path = os.path.join(tlas_dir, "glossary.json")
        if os.path.exists(glossary_path):
            with open(glossary_path, "r", encoding="utf-8") as f:
                raw_glossary = json.load(f)
                
            terms_dict = {}
            if isinstance(raw_glossary, dict):
                for k, v in raw_glossary.items():
                    if isinstance(v, dict) and ("th" in v or "enforce" in v):
                        terms_dict[k] = v
                    elif isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            if isinstance(sub_v, dict) and ("th" in sub_v or "enforce" in sub_v):
                                terms_dict[sub_k] = sub_v
                                
            loaded_terms = 0
            for en_term, data in terms_dict.items():
                if data.get("enforce", False):
                    th_term = data.get("th", en_term)
                    if en_term and th_term:
                        self.glossary_automaton.add_word(en_term, (en_term, th_term))
                        loaded_terms += 1
                        
            if loaded_terms > 0:
                self.glossary_automaton.make_automaton()
                self.is_automaton_built = True
            logger.info(f"[ContextEngine] Loaded {loaded_terms} enforced glossary terms.")

        # 2. Load Alias Mapping
        alias_map = {}
        alias_path = os.path.join(tlas_dir, "alias_mapping.json")
        if os.path.exists(alias_path):
            try:
                with open(alias_path, "r", encoding="utf-8") as f:
                    alias_map = json.load(f)
            except Exception as e:
                logger.warning(f"[ContextEngine] Failed to load alias_mapping: {e}")

        # 3. Load Character Profiles
        profiles_dir = os.path.join(tlas_dir, "profiles")
        if os.path.exists(profiles_dir):
            profile_files = glob.glob(os.path.join(profiles_dir, "*.json"))
            for p_file in profile_files:
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        profile = json.load(f)
                    base_filename = os.path.basename(p_file).replace(".json", "")
                    name = profile.get("name") or profile.get("identity", {}).get("name") or base_filename
                    char_id = profile.get("id") or profile.get("character_id") or profile.get("identity", {}).get("id")
                    if name:
                        self.character_db[name] = profile
                        self.character_db[name.lower()] = profile
                        self.character_db[base_filename] = profile
                        self.character_db[base_filename.lower()] = profile
                    if char_id:
                        self.character_db[char_id] = profile
                        self.character_db[char_id.lower()] = profile
                except Exception as e:
                    logger.warning(f"[ContextEngine] Error loading profile {p_file}: {e}")
                    
            # Link Aliases to Profiles
            for alias, canonical in alias_map.items():
                if canonical in self.character_db:
                    self.character_db[alias] = self.character_db[canonical]
                    self.character_db[alias.lower()] = self.character_db[canonical]
            logger.info(f"[ContextEngine] Loaded {len(self.character_db)} character profile keys (including aliases).")

        # 3. Load RAG Graph
        scenes_path = os.path.join(tlas_dir, "rpgm_scenes_v5.json")
        if not os.path.exists(scenes_path):
            scenes_path = os.path.join(tlas_dir, "rpgm_scenes_v4.json")
        if not os.path.exists(scenes_path):
            scenes_path = os.path.join(tlas_dir, "rpgm_scenes_v3.json")
        if os.path.exists(scenes_path):
            with open(scenes_path, "r", encoding="utf-8") as f:
                self.rag_scenes = json.load(f)
                for scene in self.rag_scenes:
                    source = scene.get("source", "")
                    prefix = source.split("_")[0]
                    if prefix.startswith("CommonEvent"):
                        prefix = "CommonEvents"
                    if prefix not in self.scene_index:
                        self.scene_index[prefix] = []
                    self.scene_index[prefix].append(scene)
            logger.info(f"[ContextEngine] Loaded {len(self.rag_scenes)} scenes into RAG graph.")

        # 4. Load Story Timeline
        timeline_path = os.path.join(tlas_dir, "story_timeline.json")
        if os.path.exists(timeline_path):
            with open(timeline_path, "r", encoding="utf-8") as f:
                self.story_timeline = json.load(f)
            logger.info(f"[ContextEngine] Loaded {len(self.story_timeline)} narrative timeline phases.")

    def find_scene_coordinates(self, filename: str, original_text: str) -> dict:
        """Cross-references CSV coordinates to find the exact phase in RAG."""
        if not filename or not original_text:
            return {}
            
        search_prefix = filename.replace(".json", "")
        if search_prefix.startswith("CommonEvent"):
            search_prefix = "CommonEvents"
            
        candidates = self.scene_index.get(search_prefix, [])
        if not candidates:
            candidates = self.rag_scenes
            
        # Clean text for robust matching
        def _clean_for_match(s: str) -> str:
            s = re.sub(r"\\[a-zA-Z]+(\[[0-9]+\])?", "", s)
            s = re.sub(r"\\[\|\.\!\^\{\}]", "", s)
            return s.replace('\\n', '').replace('\n', '').strip().lower()

        clean_target = _clean_for_match(original_text)
        if not clean_target:
            return {}
        
        for scene in candidates:
            scene_text = scene.get("text", "")
            clean_scene_text = _clean_for_match(scene_text)
            if clean_target in clean_scene_text:
                return {
                    "source": scene.get("source"),
                    "timeline_phase": scene.get("timeline_phase", -1),
                    "story_phase": scene.get("story_phase", 2),
                    "time_period": scene.get("time_period", "Present"),
                    "category": scene.get("category", "Main")
                }
        return {}

    def populate_tm(self, tokens: List[TranslationToken]):
        count = 0
        for token in tokens:
            if token.outputs.final_output:
                self.tm_db.append({
                    "en": token.original_text,
                    "th": token.outputs.final_output
                })
                count += 1
        logger.info(f"[ContextEngine] Populated Recent TM with {count} previously translated tokens.")

    def populate_full_tm(self, tokens: List[TranslationToken]):
        count = 0
        added_to_glossary = 0
        
        for token in tokens:
            en = token.original_text.strip()
            th = token.outputs.final_output.strip()
            if not en or not th:
                continue
                
            if en not in self.exact_tm_db:
                self.exact_tm_db[en] = th
                count += 1
                
            if len(en) < 25 and len(en.split()) <= 3 and re.match(r'^[A-Za-z0-9_\-\.\s]+$', en):
                if en.istitle() or en.isupper() or (len(en.split()) == 1 and en[0].isupper()):
                    self.glossary_automaton.add_word(en, (en, th))
                    added_to_glossary += 1

        if added_to_glossary > 0:
            self.glossary_automaton.make_automaton()
            self.is_automaton_built = True
            
        logger.info(f"[ContextEngine] Full TM built: {count} unique sentences, {added_to_glossary} Auto-Glossary terms.")

    def build_context(self, token: TranslationToken) -> ContextData:
        context = ContextData()

        # 0. RAG Cross-Reference
        coords = self.find_scene_coordinates(token.metadata.get("Filename"), token.original_text)
        if coords:
            token.metadata["timeline_phase"] = coords["timeline_phase"]
            token.metadata["time_period"] = coords["time_period"]
            token.metadata["scene_source"] = coords["source"]
            logger.debug(f"[ContextEngine] Matched RAG for {token.id}: Phase {coords['timeline_phase']}")

        # 1. Glossary Matching
        if self.is_automaton_built:
            matches: Dict[str, str] = {}
            for end_index, (en_term, th_term) in self.glossary_automaton.iter(token.original_text):
                matches[en_term] = th_term
            context.glossary_matches = matches

        # 2. Character Profiling (SDD-006 Dynamic Timeline States)
        if token.speaker and token.speaker in self.character_db:
            char_data = self.character_db[token.speaker]
            traits = []
            
            identity = char_data.get("identity", {})
            base_state = char_data.get("base_state", {})
            base_speech = char_data.get("base_speech_style", {})
            
            traits.append(f"Name: {char_data.get('name', token.speaker)}")
            if identity.get("gender") and identity.get("gender") != "UNKNOWN":
                traits.append(f"Gender: {identity.get('gender')}")
            if identity.get("age") and identity.get("age") != "UNKNOWN":
                traits.append(f"Age: {identity.get('age')}")
            if identity.get("species") and identity.get("species") != "UNKNOWN":
                traits.append(f"Species: {identity.get('species')}")
                
            # Base Speech style (TLAS v4.0 & Legacy)
            if base_speech:
                p_self = base_speech.get("self_pronoun", "")
                p_target = base_speech.get("target_pronoun", "")
                p_third = base_speech.get("third_person_pronoun", "")
                p_ending = base_speech.get("ending_particle", "")
                if p_self or p_target or p_ending:
                    third_part = f", third='{p_third}'" if p_third else ""
                    traits.append(f"Base Speech Style: self='{p_self}', target='{p_target}'{third_part}, particle='{p_ending}'")
            elif base_state.get("default_pronouns"):
                p = base_state["default_pronouns"]
                traits.append(f"Pronoun: self={p.get('self')}, target={p.get('target')}, ending={p.get('ending')}")
                
            # Pairwise Speech Style from TLAS v4.0 Relationships
            listener_name = token.metadata.get("listener") or token.metadata.get("target_character") or token.metadata.get("target")
            matched_pairwise = False
            if listener_name:
                l_clean = str(listener_name).strip().upper()
                if listener_name in self.character_db:
                    l_id = self.character_db[listener_name].get("identity", {})
                    l_info = []
                    if l_id.get("gender") and l_id.get("gender") != "UNKNOWN":
                        l_info.append(f"Gender: {l_id.get('gender')}")
                    if l_id.get("age") and l_id.get("age") != "UNKNOWN":
                        l_info.append(f"Age: {l_id.get('age')}")
                    if l_info:
                        traits.append(f"Listener: {listener_name} ({', '.join(l_info)})")

                for rel in char_data.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    r_tid = str(rel.get("target_character_id") or "").upper()
                    r_name = str(rel.get("target_name") or "").upper()
                    if l_clean in r_tid or r_tid in l_clean or l_clean == r_name:
                        speech = rel.get("speech_style") or rel.get("specific_speech", {})
                        if speech and isinstance(speech, dict):
                            p_self = speech.get("self_pronoun", "")
                            p_target = speech.get("target_pronoun", "")
                            p_third = speech.get("third_person_pronoun", "")
                            p_ending = speech.get("ending_particle", "")
                            rule_name = speech.get("derivation_rule", "")
                            guidance_lines = [
                                "[TRANSLATION GUIDANCE - MANDATORY PRONOUN DIRECTIVE]",
                                f"- Pronoun (Self / บุรุษที่ 1): \"{p_self}\"",
                                f"- Pronoun (Listener / บุรุษที่ 2): \"{p_target}\""
                            ]
                            if p_third:
                                guidance_lines.append(f"- Pronoun (Third-person / บุรุษที่ 3): \"{p_third}\"")
                            guidance_lines.append(f"- Sentence Ending: \"{p_ending}\"")
                            if rule_name:
                                guidance_lines.append(f"- Relation Context: {rule_name}")
                            context.pronoun_guidance = "\n".join(guidance_lines)
                            traits.append(f"Direct Relationship ({rel.get('target_name')}): self='{p_self}', target='{p_target}', particle='{p_ending}'")
                            matched_pairwise = True
                            break

            # Fallback Pronoun Guidance to Base Speech Style if no pairwise match
            if not matched_pairwise and base_speech and base_speech.get("self_pronoun"):
                p_self = base_speech.get("self_pronoun", "")
                p_target = base_speech.get("target_pronoun", "")
                p_third = base_speech.get("third_person_pronoun", "")
                p_ending = base_speech.get("ending_particle", "")
                guidance_lines = [
                    "[TRANSLATION GUIDANCE - BASE PRONOUN DIRECTIVE]",
                    f"- Pronoun (Self / บุรุษที่ 1): \"{p_self}\"",
                    f"- Pronoun (Listener / บุรุษที่ 2): \"{p_target}\""
                ]
                if p_third:
                    guidance_lines.append(f"- Pronoun (Third-person / บุรุษที่ 3): \"{p_third}\"")
                guidance_lines.append(f"- Sentence Ending: \"{p_ending}\"")
                context.pronoun_guidance = "\n".join(guidance_lines)

            # Personality & Traits
            personality_tags = [t.get("tag") if isinstance(t, dict) else str(t) for t in base_state.get("personality", [])]
            if personality_tags:
                traits.append(f"Personality: {', '.join(personality_tags)}")
                
            # Timeline-specific state delta (Legacy fallback if present)
            curr_tp = token.metadata.get("timeline_phase")
            if curr_tp is not None and char_data.get("timeline_states"):
                for st in reversed(char_data["timeline_states"]):
                    if st.get("timeline_phase", 999999) <= curr_tp:
                        delta = st.get("delta", {})
                        if delta.get("personality"):
                            d_tags = [t.get("tag") if isinstance(t, dict) else str(t) for t in delta["personality"]]
                            traits.append(f"Current Phase State: {', '.join(d_tags)}")
                        break
            
            context.character_traits = traits
            
        # Direct Scene Context (TLAS v4.0)
        scene_ctx = token.metadata.get("direct_scene_context") or token.metadata.get("scene_context") or token.metadata.get("scene_summary")
        if scene_ctx:
            context.direct_scene_context = str(scene_ctx)

        # 3. Translation Memory (TM)
        context.translation_memory = self.tm_db[-5:] if self.tm_db else []
        
        if token.original_text in self.exact_tm_db:
            context.translation_memory.append({
                "Info": "EXACT PAST TRANSLATION",
                "en": token.original_text,
                "th": self.exact_tm_db[token.original_text]
            })

        # 4. Rules & Scopes
        context.style_rules = self.style_rules
        context.symbol_engine_rules = self.symbol_engine_rules
        
        group_id = token.metadata.get("context_group_id")
        if group_id and self.has_scope(group_id):
            context.story_summary = self.get_scope(group_id)
        else:
            context.story_summary = ""
            
        # 5. Narrative Timeline Summary
        story_phase = token.metadata.get("story_phase", 2)
        chron_sum = []
        for phase_id_str, data in self.story_timeline.items():
            try:
                pid = int(re.search(r'\d+', str(phase_id_str)).group(0)) if re.search(r'\d+', str(phase_id_str)) else 2
                if pid <= story_phase and isinstance(data, dict):
                    chron_sum.append(f"{data.get('name', f'Phase {pid}')}: {data.get('summary', '')}")
            except Exception:
                pass
                
        if chron_sum:
            context.chronological_summary = "\n".join(chron_sum)

        # Store situation if provided by summarizer
        context.situation = token.metadata.get("situation", [])

        token.context = context
        return context

    def get_resolved_profile(self, speaker: str, current_timeline_phase: int) -> dict:
        """
        Deep Merges base_state and timeline_states (Deltas) up to the current_timeline_phase.
        Returns a dictionary containing the resolved traits, 4D relationships, and speech style.
        """
        if not speaker or speaker not in self.character_db:
            return {}

        profile = self.character_db[speaker]
        resolved = {
            "character_id": profile.get("character_id", f"CHAR_{speaker.upper()}"),
            "name": profile.get("name", speaker),
            "identity": {
                "gender": profile.get("identity", {}).get("gender", "UNKNOWN"),
                "age": profile.get("identity", {}).get("age", "UNKNOWN"),
                "species": profile.get("identity", {}).get("species", "UNKNOWN")
            },
            "base_speech_style": profile.get("base_speech_style", {
                "self_pronoun": "ฉัน",
                "target_pronoun": "คุณ",
                "ending_particle": "คะ/ค่ะ",
                "formality_level": 5
            }),
            "personality": [],
            "speech_habit": [],
            "values": [],
            "relationships": []
        }

        # Load Base State
        base = profile.get("base_state", {})

        # TLAS v4.0 Fast-Path: If clean profile with no timeline_states, return consolidated directly
        if not profile.get("timeline_states"):
            resolved["personality"] = base.get("personality", [])
            resolved["speech_habit"] = base.get("speech_habit", [])
            resolved["values"] = base.get("values", [])
            resolved["relationships"] = profile.get("relationships", []) or base.get("relationships", [])
            return resolved
        
        # Helper to merge trait lists based on tag (Weight scale 1-100)
        def merge_traits(target_list, new_traits):
            tag_map = {}
            for t in target_list:
                if isinstance(t, dict) and "tag" in t:
                    tag_map[t["tag"]] = t
                elif isinstance(t, str):
                    tag_map[t] = {"tag": t, "weight": 50}
            for nt in new_traits:
                if isinstance(nt, dict) and "tag" in nt:
                    tag_map[nt["tag"]] = nt # Upsert
                elif isinstance(nt, str):
                    tag_map[nt] = {"tag": nt, "weight": 50}
            return list(tag_map.values())

        resolved["personality"] = merge_traits([], base.get("personality", []))
        resolved["speech_habit"] = merge_traits([], base.get("speech_habit", []))
        resolved["values"] = merge_traits([], base.get("values", []))
        
        # Load Base Relationships (4D Structure)
        rel_map = {}
        for r in base.get("relationships", []):
            if isinstance(r, dict):
                tid = r.get("target_character_id") or (f"CHAR_{r['target_name'].upper()}" if "target_name" in r else None)
                if tid:
                    rel_map[tid] = {
                        "target_character_id": tid,
                        "target_name": r.get("target_name", ""),
                        "roles": list(r.get("roles", [])),
                        "affinity": r.get("affinity", "AFF_NEUTRAL"),
                        "intimacy": r.get("intimacy", "INT_DISTANT"),
                        "power_dynamic": r.get("power_dynamic", "DYN_EQUAL"),
                        "specific_speech": dict(r.get("specific_speech", {})),
                        "relation_tags": list(r.get("relation_tags", []))
                    }

        # Apply Deltas sequentially
        for state in profile.get("timeline_states", []):
            if not isinstance(state, dict):
                continue
            state_phase = state.get("timeline_phase", 999999)
            if state_phase > current_timeline_phase and current_timeline_phase != -1:
                break # Stop applying deltas from future phases
                
            delta = state.get("delta", {})
            if isinstance(delta, dict):
                resolved["personality"] = merge_traits(resolved["personality"], delta.get("personality", []))
                resolved["speech_habit"] = merge_traits(resolved["speech_habit"], delta.get("speech_habit", []))
                resolved["values"] = merge_traits(resolved["values"], delta.get("values", []))
                
                # Deep Merge 4D Relationships
                for rel in delta.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    tid = rel.get("target_character_id") or (f"CHAR_{rel['target_name'].upper()}" if "target_name" in rel else None)
                    if not tid:
                        continue
                    
                    if tid in rel_map:
                        existing_rel = rel_map[tid]
                        # Merge roles (union)
                        if "roles" in rel and rel["roles"]:
                            existing_roles = set(existing_rel.get("roles", []))
                            existing_roles.update(rel["roles"])
                            existing_rel["roles"] = list(existing_roles)
                        # Override affinity, intimacy, power_dynamic if provided
                        if "affinity" in rel and rel["affinity"]:
                            existing_rel["affinity"] = rel["affinity"]
                        if "intimacy" in rel and rel["intimacy"]:
                            existing_rel["intimacy"] = rel["intimacy"]
                        if "power_dynamic" in rel and rel["power_dynamic"]:
                            existing_rel["power_dynamic"] = rel["power_dynamic"]
                        if "specific_speech" in rel and rel["specific_speech"]:
                            existing_rel.setdefault("specific_speech", {}).update(rel["specific_speech"])
                        if "relation_tags" in rel and rel["relation_tags"]:
                            existing_rel["relation_tags"] = merge_traits(existing_rel.get("relation_tags", []), rel.get("relation_tags", []))
                    else:
                        rel_map[tid] = {
                            "target_character_id": tid,
                            "target_name": rel.get("target_name", ""),
                            "roles": list(rel.get("roles", [])),
                            "affinity": rel.get("affinity", "AFF_NEUTRAL"),
                            "intimacy": rel.get("intimacy", "INT_DISTANT"),
                            "power_dynamic": rel.get("power_dynamic", "DYN_EQUAL"),
                            "specific_speech": dict(rel.get("specific_speech", {})),
                            "relation_tags": list(rel.get("relation_tags", []))
                        }

        resolved["relationships"] = list(rel_map.values())
        return resolved