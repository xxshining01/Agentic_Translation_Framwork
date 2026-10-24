import os
import csv
import json
import glob
import asyncio
import time
import math
import logging
import re
from typing import List, Dict, Optional, Tuple, Set
import sys
import traceback
from datetime import datetime
# Ensure the root project directory is in sys.path so it can be run directly or via -m
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import tiktoken
from src.atf.agents.base import BaseAgent
from json_repair import repair_json
from src.atf.tools.tlas_rule_engine import PriorityRuleEngine

logger = logging.getLogger(__name__)

# Thai pronoun detection patterns for Stage 1.5
THAI_SELF_PRONOUNS = ["ผม", "ฉัน", "เรา", "ข้า", "หนู", "กู", "ดิฉัน", "กระผม", "พี่", "น้อง", "ป๋า", "เฮีย", "เจ๊", "ข้าพเจ้า", "กระหม่อม"]
THAI_ENDING_PARTICLES = ["ครับ", "ค่ะ", "คะ", "วะ", "โว้ย", "เพคะ", "ขอรับ", "จ้ะ", "จ๊ะ", "ฮะ", "สิ", "นะ", "เว้ย", "คร้าบ", "จ๋า", "เจ้าค่ะ"]

def split_text_intelligently(text: str, max_len: int = 2000) -> List[str]:
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    for p in paragraphs:
        if len(p) > max_len:
            sentences = p.replace('. ', '.[SPLIT]').split('[SPLIT]')
            for s in sentences:
                if len(current_chunk) + len(s) > max_len and current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = s + " "
                else:
                    current_chunk += s + " "
        else:
            if len(current_chunk) + len(p) > max_len and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"
            else:
                current_chunk += p + "\n\n"
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

def clean_line_text(text: str) -> str:
    if not text:
        return ""
    # Strip RPG Maker control tags, brackets, escape codes
    text = re.sub(r"^(\n)?<[^>]+>\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(r"\\[a-zA-Z]+(\[[0-9]+\])?", "", text)
    text = re.sub(r"\\[\|\.\!\^\{\}\\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def clean_thai_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"^(\n)?<[^>]+>\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(r"\\[a-zA-Z]+(\[[0-9]+\])?", "", text)
    text = re.sub(r"\\[\|\.\!\^\{\}\\]", "", text)
    return text.strip()

class LegacyThaiMatcher:
    """Loads legacy Thai translations from CSV cell-by-cell to provide bilingual ground truth."""
    def __init__(self, csv_path: str):
        self.exact_map_index: Dict[Tuple[str, str], str] = {}
        self.global_index: Dict[str, str] = {}
        self._load_csv(csv_path)

    def _load_csv(self, csv_path: str):
        start = time.time()
        if not os.path.exists(csv_path):
            print(f"[Matcher] Warning: Legacy Thai CSV not found at {csv_path}")
            return
            
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                orig = row.get("Original", "").strip()
                th = row.get("Initial", "").strip()
                fn = row.get("Filename", "").strip().replace(".json", "")
                
                if not orig or not th or orig == th:
                    continue
                    
                # 1. Index full cell
                clean_full = clean_line_text(orig)
                clean_th_full = clean_thai_text(th)
                if clean_full:
                    self.exact_map_index[(fn, clean_full)] = clean_th_full
                    if clean_full not in self.global_index:
                        self.global_index[clean_full] = clean_th_full
                        
                # 2. Index individual lines within multi-line cells
                orig_lines = orig.split("\n")
                th_lines = th.split("\n")
                if len(orig_lines) == len(th_lines):
                    for o_l, t_l in zip(orig_lines, th_lines):
                        c_ol = clean_line_text(o_l)
                        c_tl = clean_thai_text(t_l)
                        if c_ol and c_tl:
                            self.exact_map_index[(fn, c_ol)] = c_tl
                            if c_ol not in self.global_index:
                                self.global_index[c_ol] = c_tl
                count += 1
                
        print(f"[Matcher] Loaded {count} legacy Thai translation rows into {len(self.exact_map_index)} map-specific and {len(self.global_index)} global entries ({time.time()-start:.2f}s).")

    def match_line(self, map_name: str, line: str) -> str:
        clean = clean_line_text(line)
        if not clean:
            return ""
        if (map_name, clean) in self.exact_map_index:
            return self.exact_map_index[(map_name, clean)]
        if clean in self.global_index:
            return self.global_index[clean]
        return ""

    def format_bilingual_dialogue(self, source: str, raw_text: str) -> str:
        map_name = source.split("_")[0] if "_" in source else ""
        lines = raw_text.split("\n")
        output_lines = []
        
        for line in lines:
            if not line.strip():
                continue
            m = re.match(r"^(\[[^\]]+\])\s*(.*)$", line.strip())
            if m:
                spk = m.group(1)
                content = m.group(2)
            else:
                spk = ""
                content = line.strip()
                
            th_trans = self.match_line(map_name, content)
            if th_trans:
                output_lines.append(f"{spk} {content}\n  [TH (Legacy)]: {th_trans}")
            else:
                output_lines.append(f"{spk} {content}")
                
        return "\n".join(output_lines)
def merge_scene_results(list_of_results: list) -> dict:
    merged = {}
    for res in list_of_results:
        if not isinstance(res, dict):
            continue
        for scene_id, char_dict in res.items():
            if not isinstance(char_dict, dict):
                continue
            if scene_id not in merged:
                merged[scene_id] = char_dict
            else:
                existing_scene = merged[scene_id]
                for char_name, pdata in char_dict.items():
                    if not isinstance(pdata, dict):
                        continue
                    if char_name not in existing_scene:
                        existing_scene[char_name] = pdata
                    else:
                        existing = existing_scene[char_name]
                        # Update aliases
                        existing_aliases = set(existing.get("aliases", []))
                        existing_aliases.update(pdata.get("aliases", []))
                        existing["aliases"] = sorted(list(existing_aliases))
                        
                        # Merge lists
                        for field in ["personality", "speech_habit", "values", "relationships"]:
                            existing_tags = {
                                t.get("tag") or t.get("target_name") 
                                for t in existing.get(field, []) if isinstance(t, dict)
                            }
                            for new_item in pdata.get(field, []):
                                tag_id = new_item.get("tag") or new_item.get("target_name")
                                if tag_id and tag_id not in existing_tags:
                                    existing.setdefault(field, []).append(new_item)
                                    existing_tags.add(tag_id)
    return merged

def is_no_character_response(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("status") in ("NO_CHARACTERS_FOUND", "NO_CHARACTER_FOUND"):
        return True
    if data.get("reason") in ("ไม่พบตัวละคร", "NO_CHARACTERS_FOUND"):
        return True
    for k, v in data.items():
        k_str = str(k)
        v_str = str(v)
        if "NO_CHARACTERS_FOUND" in k_str or "NO_CHARACTERS_FOUND" in v_str:
            return True
        if "ไม่พบตัวละคร" in k_str or "ไม่พบตัวละคร" in v_str:
            return True
    return False

class TLASAnalyzerAgent(BaseAgent):
    def __init__(self, taxonomy_data: dict = None):
        super().__init__()
        if not taxonomy_data:
            tax_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/tlas/taxonomy.json"))
            if os.path.exists(tax_path):
                with open(tax_path, "r", encoding="utf-8") as f:
                    taxonomy_data = json.load(f)
            else:
                taxonomy_data = {}
        self.taxonomy_data = taxonomy_data
        
        tags = self.taxonomy_data.get("tags", {})
        self.personality_tags = [k for k in tags if k.startswith("PER_")]
        self.speech_tags = [k for k in tags if k.startswith("SPR_")]
        self.values_tags = [k for k in tags if k.startswith("VAL_")]
        
        self.role_tags = [k for k in tags if k.startswith("ROLE_")]
        self.aff_tags = [k for k in tags if k.startswith("AFF_")]
        self.intimacy_tags = [k for k in tags if k.startswith("INT_")]
        self.dyn_tags = [k for k in tags if k.startswith("DYN_")]
        
        # Known LLM hallucination correction maps
        self.ROLE_CORRECTIONS: Dict[str, str] = {
            "ROLE_SOC_ACQUAINTANCE": "ROLE_SOC_PEER",
            "ROLE_FRIEND": "ROLE_SOC_PEER",
            "ROLE_ROMANTIC_INTEREST": "ROLE_ROM_OFFICIAL",
            "ROLE_ROMANTIC_PARTNER": "ROLE_ROM_OFFICIAL",
            "ROLE_SUBORDINATE": "ROLE_AUTH_SERVANT",
            "ROLE_SUPERIOR": "ROLE_AUTH_MASTER",
            "ROLE_MENTOR": "ROLE_AUTH_MENTOR",
            "ROLE_RIVAL": "ROLE_CON_RIVAL",
            "ROLE_ENEMY": "ROLE_CON_ENEMY",
            "ROLE_SIBLING": "ROLE_KIN_PEER",
            "ROLE_FAMILY": "ROLE_KIN_ELDER",
        }
        self.DYN_CORRECTIONS: Dict[str, str] = {
            "DYN_SUPERIOR": "DYN_DOMINANT",
            "DYN_INFERIOR": "DYN_SUBMISSIVE",
            "DYN_NEUTRAL": "DYN_EQUAL",
            "DYN_DOMINANT_OVER": "DYN_DOMINANT",
        }
        self.AFF_CORRECTIONS: Dict[str, str] = {
            "AFF_LOVE": "AFF_DEVOTED",
            "AFF_LIKE": "AFF_FOND",
            "AFF_HATE": "AFF_HOSTILE",
            "AFF_DISLIKE": "AFF_SUSPICIOUS",
            "AFF_CRUSH": "AFF_HIDDEN_CRUSH",
            "AFF_TSUNDERE": "AFF_CONFLICTED",
        }

        self.system_prompt = (
            "You are a master psychological profiler and narrative analyst for a Japanese Visual Novel game localization framework (TLAS).\n"
            "Your task is to analyze character psychology, core values, and 4D interpersonal relationships from game scenes.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output ONLY valid JSON according to the requested schema. No markdown explanations outside JSON.\n"
            "2. Use ONLY valid tags from the provided taxonomy. Never invent custom tag names.\n"
            "3. Focus exclusively on psychological states and 4D relationship dynamics. Do NOT include speech styles or pronouns.\n\n\n"
            "SAFETY RULE: If you see any variables in brackets (e.g., [var], {var}), HTML tags, quotes, or system commands, YOU MUST PRESERVE THEM EXACTLY AS THEY ARE. "
            "Do not translate them. Do not remove them. Do not change their casing. "
            "CRITICAL: Escape characters and control codes like \\n, \\., \\|, \\f, \\C[X], \\>, \\< MUST remain exactly as they appear in the original text. "
            "DO NOT drop the backslash. Treat these codes as transparent wrappers. Translate the human text around them while keeping the codes in the exact same relative positions. "
            "Examples:\n"
            "- '\\fbStop' -> '\\fbหยุดนะ'\n"
            "- '\"Stop\"' -> '\"หยุดนะ\"'\n"
            "- '<color=red>Fire</color>' -> '<color=red>ไฟ</color>'\n"
            "Do not render them as actual newlines or formatting in your response!\n\n"
            "Output a valid JSON object ONLY. The JSON object must contain a list of your results. End your response immediately after the closing bracket '}'."
        )

        self.speaker_id_system_prompt = (
            "You are a strict character identification assistant. Your only task is to identify which canonical characters from the provided whitelist speak in the dialogue.\n"
            "Return ONLY a JSON array of valid character names. Do not include narrators, system tags, unknown speakers, or background mobs.\n"
        )
        
    async def process(self, batch):
        pass

    async def identify_speakers_in_scene(
        self,
        bilingual_dialogue: str,
        canonical_whitelist_info: str,
        cache_key: str,
        llm_cache: dict
    ) -> List[str]:
        """Stage 1: Fast LLM call to identify which characters speak in this sub-chunk."""
        speaker_cache_key = f"{cache_key}_speakers"
        if speaker_cache_key in llm_cache:
            return llm_cache[speaker_cache_key]

        # Use sufficient dialogue context
        trimmed = bilingual_dialogue[:2500]
        user_prompt = (
            f"List of VALID CANONICAL CHARACTERS:\n{canonical_whitelist_info}\n\n"
            f"Dialogue:\n{trimmed}\n\n"
            "Identify which of the above VALID CANONICAL CHARACTERS speak in this dialogue.\n"
            "RULES:\n"
            "1. Return ONLY names from the valid character list.\n"
            "2. Do NOT identify narrators, system tags ('Window5', 'I[xxx]'), unknown speakers ('???', 'Unknown', 'Voice'), or unnamed background NPCs.\n"
            "3. If no valid named characters speak in this scene, return an empty array: []\n"
            "4. Return EXACTLY a JSON array: [\"Name1\", \"Name2\"] — nothing else."
        )
        for attempt in range(3):
            try:
                response = await self.call_llm(
                    system_prompt=self.speaker_id_system_prompt,
                    user_prompt=user_prompt,
                    require_json=False,
                    skip_safety_rule=True
                )
                if response and response.strip():
                    repaired = repair_json(response)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, list):
                        speakers = [s for s in parsed if isinstance(s, str) and s.strip() and not is_garbage_or_disposable(s)]
                        llm_cache[speaker_cache_key] = speakers
                        return speakers
            except Exception as e:
                print(f"      [Stage1] Speaker ID attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1)
        return {}
        
    async def summarize_long_text(self, text_chunk: str) -> str:
        prompt = (
            "You are summarizing a story segment to provide context for character psychological analysis.\n"
            "Summarize the following text concisely (under 500 words). Crucially, you MUST preserve:\n"
            "1. The overall atmosphere and tone of the scene (e.g. tense, romantic, hostile).\n"
            "2. The main topic of conversation and current events.\n"
            "3. Any explicitly stated emotions, motivations, or relationships between characters.\n\n"
            f"--- Text ---\n{text_chunk}"
        )
        for attempt in range(1, 4):
            try:
                await asyncio.sleep(1)
                response = await self.call_llm(
                    system_prompt="You are a helpful assistant.",
                    user_prompt=prompt,
                    skip_safety_rule=True
                )
                if response:
                    return response
            except Exception as e:
                print(f"      [AI-Pre] Summarization attempt {attempt} failed: {e}")
                if attempt == 3:
                    print("      [FATAL] Summarization failed completely!")
                    return text_chunk[:2000]
                await asyncio.sleep(2)
        return text_chunk[:2000]

    def build_focused_prompt(
        self,
        summary_text: str,
        scene_header: str,
        bilingual_dialogue: str,
        target_characters: List[str],
        profile_info: str = "",
        level: int = 0,
        feedback_message: str = None
    ) -> str:
        """Stage 2 prompt: focused on psychology + 4D only for target characters."""
        target_str = ", ".join(target_characters) if target_characters else "speaking characters"
        if level == 0:
            summary_part = summary_text[:400] + ("..." if len(summary_text) > 400 else "")
        elif level == 1:
            summary_part = summary_text[:200] + ("..." if len(summary_text) > 200 else "")
        else:
            summary_part = summary_text[:100] + ("..." if len(summary_text) > 100 else "")

        prompt = (
            f"You are analyzing character psychology and 4D relationship dynamics in a scene.\n"
            f"TARGET CHARACTER(S) TO ANALYZE: {target_str}\n\n"
            f"--- Story Summary ---\n{summary_part}\n\n"
            f"--- Prior Character States ---\n{profile_info}\n\n"
            f"--- Bilingual Scene Dialogue ---\n{scene_header}\n{bilingual_dialogue}\n\n"
            "--- STRICT OUTPUT SCHEMA ---\n"
            f"You have been provided with one or more scenes. You MUST return a valid JSON object with separate root keys for EACH Scene ID provided in the headers (e.g., \"Scene_0\", \"Scene_1\"). DO NOT merge scenes together. For each scene, include keys ONLY for target character(s) ({target_str}). Follow this exact schema:\n"
            "{\n"
            '  "Scene_ID": {\n'
            '    "CharacterName": {\n'
            '    "canonical_name": "CharacterName",\n'
            '    "aliases": ["Alias1"],\n'
            '    "gender": "MALE/FEMALE/UNKNOWN",\n'
            '    "age": "CHILD/TEEN/ADULT/ELDER/UNKNOWN",\n'
            '    "species": "HUMAN/UNKNOWN",\n'
            '    "personality": [\n'
            '      {"tag": "PER_VIBE_ARROGANT", "weight": 90},\n'
            '      {"tag": "PER_MIND_CUNNING", "weight": 85}\n'
            '    ],\n'
            '    "speech_habit": [\n'
            '      {"tag": "SPR_DIRECT", "weight": 90}\n'
            '    ],\n'
            '    "values": [\n'
            '      {"tag": "VAL_POWER", "weight": 90}\n'
            '    ],\n'
            '    "relationships": [\n'
            '      {\n'
            '        "target_name": "OtherCharacter",\n'
            '        "roles": ["ROLE_ROM_ILLICIT"],\n'
            '        "affinity": "AFF_OBSESSIVE",\n'
            '        "intimacy": "INT_CONFIDANT",\n'
            '        "power_dynamic": "DYN_DOMINANT"\n'
            '      }\n'
            '    ]\n'
            '  }\n'
            '}\n'
            "}\n\n"
            "--- STRICT MANDATORY RULES ---\n"
            "1. TAXONOMY RESTRICTION (USE ONLY EXACT TAGS LISTED BELOW — NEVER INVENT TAGS):\n"
            f"   - personality: {', '.join(self.personality_tags)}\n"
            f"   - speech_habit: {', '.join(self.speech_tags)}\n"
            f"   - values: {', '.join(self.values_tags)}\n"
            f"   - roles: {', '.join(self.role_tags)}\n"
            f"   - affinity: {', '.join(self.aff_tags)}\n"
            f"   - intimacy: {', '.join(self.intimacy_tags)}\n"
            f"   - power_dynamic: {', '.join(self.dyn_tags)}\n"
            f"2. TARGET SCOPE: Create entries ONLY for target character(s): {target_str}. Do NOT create entries for narrator, system, or background NPCs.\n"
            "3. 4D RELATIONSHIPS: Each relationship object MUST include all 4 fields: 'roles' (array), 'affinity' (string), 'intimacy' (string), 'power_dynamic' (string).\n"
            "4. NO SPEECH STYLE FIELDS: Do NOT include self_pronoun, target_pronoun, ending_particle, or formality_level.\n"
            "5. WEIGHT SCALE: 'weight' must be an integer from 1 to 100 (100 = dominant trait).\n"
            '6. NO CHARACTERS: If none of the target characters speak in this scene, output: {"status": "NO_CHARACTERS_FOUND", "reason": "No characters found"}\n'
            "7. ALIASES: If you discover a character is referred to by a different name, title, disguise, or nickname in this scene that is not their canonical_name, MUST add it to their 'aliases' array.\n"
            "8. IDENTITY: For gender, age, and species, you MUST infer them from the dialogue. If ambiguous, output 'UNKNOWN'. Do NOT blindly copy placeholders.\n"
            "9. STRICT JSON ONLY: Do NOT use <think> tags. Do NOT write any markdown text or explanations. Start your output IMMEDIATELY with the character '{'.\n"
        )
        if feedback_message:
            prompt += f"\n\n[SYSTEM ERROR - FEEDBACK FOR CORRECTION]\n{feedback_message}\n"
        return prompt

    async def analyze_scene_text(
        self,
        summary_text: str,
        scene_header: str,
        bilingual_dialogue: str,
        target_characters: List[str] = None,
        profile_info: str = "",
        attempt_level: int = 0,
        feedback_message: str = None
    ) -> dict:
        """
        Stage 2: Focused LLM analysis — psychology + 4D only (no speech_style).
        Auto-Repair: Level 0→1→2 (halving) on failure.
        """
        if target_characters is None:
            target_characters = []

        # Sub-attempts for current level
        max_sub_attempts = 2
        for sub_attempt in range(max_sub_attempts):
            user_prompt = self.build_focused_prompt(
                summary_text=summary_text,
                scene_header=scene_header,
                bilingual_dialogue=bilingual_dialogue,
                target_characters=target_characters,
                profile_info=profile_info,
                level=attempt_level,
                feedback_message=feedback_message
            )
            
            if sub_attempt == 0:
                enc = tiktoken.get_encoding("cl100k_base")
                full_prompt = self.system_prompt + "\n" + user_prompt
                base_token_count = len(enc.encode(full_prompt, disallowed_special=()))
                print(f"      [API] Assembled Prompt (Level {attempt_level}). Tiktoken Count: ~{base_token_count} tokens.")
            
            # Set max_tokens to None. Reasoning models (like DeepSeek or Gemma QAT) need thousands of tokens 
            # for their internal `<think>` process before they even start outputting the JSON.
            safe_max_tokens = None

            try:
                print(f"      [API] Calling LM Studio (Level {attempt_level}, Try {sub_attempt+1}/{max_sub_attempts})...")
                response = await self.call_llm(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    require_json=True,
                    skip_safety_rule=False,
                    max_tokens=safe_max_tokens
                )
                if response and response.strip():
                    parsed = self.parse_json_response(response)
                    if isinstance(parsed, dict):
                        # 1. ตรวจจับเคส "ไม่พบตัวละคร" -> ข้ามไปยัง sub-chunk ถัดไปทันที
                        if is_no_character_response(parsed):
                            print("      [API] Result: NO_CHARACTERS_FOUND (System UI / Sound / Disposable). Moving to next sub-chunk.")
                            return {}
                        # 2. ถ้าเจอค่าว่าง {} ให้ trigger ซ่อมแซมตามปกติ
                        if not parsed:
                            print(f"      [Warn] Received empty dict {{}} from LLM at Level {attempt_level}. Triggering auto-repair...")
                        else:
                            # parsed should be {"Scene_0": {"Dan": {...}}}
                            filtered_parsed = {}
                            for scene_id, char_dict in parsed.items():
                                if isinstance(char_dict, dict):
                                    filtered_parsed[scene_id] = {}
                                    for char_name, char_data in char_dict.items():
                                        if not is_garbage_or_disposable(char_name):
                                            filtered_parsed[scene_id][char_name] = char_data
                                            
                            # --- Early Semantic Validation (Strict Mode) ---
                            invalid_tags = self._validate_parsed_tags(filtered_parsed)
                            if invalid_tags:
                                error_msg = "Your last response was REJECTED because you hallucinated the following invalid tags: " + ", ".join(invalid_tags) + ". You MUST ONLY use the exact tags provided in the Taxonomy."
                                raise Exception(error_msg)
                                
                            print(f"      [API] Success! Parsed and validated profiles for {len(filtered_parsed)} scenes.")
                            return filtered_parsed
                print(f"      [Warn] Empty or invalid response from LLM at Level {attempt_level}.")
            except Exception as e:
                print(f"      [Error] Level {attempt_level} Try {sub_attempt+1} failed: {e}")
                feedback_message = str(e)
                await asyncio.sleep(2)
                
        # --- Smart Auto-Repair Progression ---
        if attempt_level == 0:
            print("      [Auto-Repair] Triggering Level 1 Context Reduction...")
            return await self.analyze_scene_text(
                summary_text=summary_text,
                scene_header=scene_header,
                bilingual_dialogue=bilingual_dialogue,
                target_characters=target_characters,
                attempt_level=1
            )

        if attempt_level == 1:
            lines = [l for l in bilingual_dialogue.split("\n") if l.strip()]
            if len(lines) > 1:
                mid = len(lines) // 2
                part_1 = "\n".join(lines[:mid])
                part_2 = "\n".join(lines[mid:])
                print(f"      [Auto-Repair] Triggering Level 2 Adaptive Halving: Part A ({len(part_1)} chars) & Part B ({len(part_2)} chars)...")
                res_1 = await self.analyze_scene_text(summary_text, scene_header, part_1, target_characters, attempt_level=1)
                res_2 = await self.analyze_scene_text(summary_text, scene_header, part_2, target_characters, attempt_level=1)
                merged = merge_scene_results([res_1, res_2])
                print(f"      [Auto-Repair] Level 2 Halving Merged Successfully! ({len(merged)} scenes).")
                return merged
                
        # CRITICAL: AGENTS.md Rule 4 (No Skip). Must abort if auto-repair fails completely.
        print(f"      [FATAL] Auto-Repair reached maximum depth for {scene_header}. Aborting to prevent data skipping!")
        raise Exception(f"CRITICAL FAILURE: Unable to process {scene_header} even after max auto-repair depth. Aborting to satisfy AGENTS.md Rule 4 (No Skip).")

    def _validate_parsed_tags(self, parsed: dict) -> List[str]:
        invalid_tags = []
        
        def check_tags(tags, allowed_set, corrections_set):
            for t in tags:
                tag_name = t.get("tag", "") if isinstance(t, dict) else t if isinstance(t, str) else ""
                if not tag_name:
                    continue
                if tag_name not in allowed_set and tag_name not in corrections_set:
                    invalid_tags.append(tag_name)

        for scene_id, char_dict in parsed.items():
            if not isinstance(char_dict, dict):
                continue
            for char_name, char_data in char_dict.items():
                if not isinstance(char_data, dict):
                    continue
                
                # Relationships ONLY
                for rel in char_data.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    
                    roles = rel.get("roles", [])
                    if isinstance(roles, str):
                        roles = [roles]
                    check_tags(roles, self.role_tags, self.ROLE_CORRECTIONS)
                    
                    aff = rel.get("affinity")
                    if aff:
                        check_tags([aff], self.aff_tags, self.AFF_CORRECTIONS)
                        
                    intimacy = rel.get("intimacy")
                    if intimacy:
                        check_tags([intimacy], self.intimacy_tags, {})
                        
                    dyn = rel.get("power_dynamic")
                    if dyn:
                        check_tags([dyn], self.dyn_tags, self.DYN_CORRECTIONS)
                        
        return list(set(invalid_tags))

def get_safe_filename(name: str) -> str:
    # Strip parentheses and brackets for filename
    clean_name = re.sub(r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]", "", name).strip()
    if not clean_name:
        clean_name = name
    return "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in clean_name).strip()

def dicts_differ(d1: dict, d2: dict) -> bool:
    return json.dumps(d1, sort_keys=True) != json.dumps(d2, sort_keys=True)

def get_chunk_sort_key(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            cluster_id = data.get("cluster_id", "")
            raw_scenes = data.get("raw_scenes", data.get("raw_dialogues", []))
            tl_phase = 99999
            if raw_scenes and isinstance(raw_scenes, list) and len(raw_scenes) > 0:
                tl_phase = raw_scenes[0].get("timeline_phase", 99999)
                
            # Remove cluster_id from sort key to ensure strict chronological sorting across ALL clusters
            return (tl_phase, filepath)
    except Exception:
        return (99999, filepath)

# Generic transient speakers and garbage patterns that should not create standalone profiles
GENERIC_DISPOSABLE_NAMES: Set[str] = {
    "???", "unknown", "voice", "man", "woman", "villager", "boy", "girl", "all", "both",
    "system", "narrator", "text", "choice", "barfer", "customer", "staff", "npc", "none",
    "crowd", "people", "someone", "somebody", "hostess", "annoyed customer", "affluent man",
    "affluent old man", "agency staff", "anxious boy", "anxious man", "alcoholic middle aged man",
    "bald thug", "bearded man", "bearded guy", "big voice", "slut", "unnamed female",
    "unnamed female character", "unknown woman", "window5"
}

GARBAGE_REGEX_PATTERNS = [
    r"^window\d*$",
    r"^i(\[\d+\])?$",
    r"^\?+$",
    r"^unknown.*$",
    r"^_unknown_.*$",
    r"^unnamed.*$",
    r"^c_?\d+.*$",
    r"^\[?ba executive.*\]?$",
    r"^_?ba executive.*_?$",
    r"^ba executive.*$",
    r"^slut.*$",
    r"^all$",
    r"^both$",
    r"^system.*$",
    r"^narrator.*$",
    r"^choice.*$",
    r"^text.*$",
    r"^hostnpc\d*.*$",
    r"^none$",
    r"^crowd.*$",
    r"^people.*$",
    r"^someone.*$",
    r"^somebody.*$",
    r"^.*voice.*$"
]

GENERIC_MOB_PREFIXES = [
    "affluent ", "anxious ", "alcoholic ", "annoyed ", "amber hair ",
    "almost noveau ", "adventurous ", "bald ", "bearded ", "blue shirt ",
    "red shirt ", "blond hair ", "pink hair ", "black hair ", "black-haired ",
    "stuck up ", "special customer", "vvip", "vulgar ", "well mannered ",
    "unwell ", "village ", "villager", "young boy", "young girl", "young man",
    "old man", "old lady", "wise man", "wealthy ", "university student ",
    "hotel staff", "agency staff", "fratboy ", "kinchao gang member",
    "kinchao gang 2", "kinchao gang 3", "big "
]

def is_garbage_or_disposable(name: str) -> bool:
    if not name or not name.strip():
        return True
    clean = name.strip()
    clean_lower = clean.lower()
    
    for pat in GARBAGE_REGEX_PATTERNS:
        if re.match(pat, clean_lower):
            return True
            
    if clean.startswith("[") and clean.endswith("]"):
        return True
    if clean.startswith("_") and clean.endswith("_"):
        return True
        
    if re.search(r"\\|\/|\[\d+\]", clean):
        return True
        
    if len(clean) == 1 and clean.isalpha():
        return True
        
    for prefix in GENERIC_MOB_PREFIXES:
        if clean_lower == prefix.strip() or clean_lower.startswith(prefix):
            return True
            
    return clean_lower in GENERIC_DISPOSABLE_NAMES

def is_generic_disposable(name: str) -> bool:
    return is_garbage_or_disposable(name)

# ─────────────────────────────────────────────
# Stage 1.5: Python TH Legacy Pronoun Hint Extractor
# ─────────────────────────────────────────────
THAI_PRONOUN_RE = re.compile(
    r'(?:^|\s|[\[\(])(' +
    '|'.join(re.escape(p) for p in sorted(THAI_SELF_PRONOUNS, key=len, reverse=True)) +
    r')(?:\s|$|[\]\)\.,!?])'
)
THAI_ENDING_RE = re.compile(
    r'(' +
    '|'.join(re.escape(p) for p in sorted(THAI_ENDING_PARTICLES, key=len, reverse=True)) +
    r')(?:\s|$|[\]\)\.,!?])'
)

def extract_pronoun_hints(speakers: List[str], bilingual_dialogue: str, alias_to_canonical: Dict[str, str]) -> str:
    """Stage 1.5: Scan TH Legacy lines, count pronouns per speaker, return hint string."""
    if not speakers:
        return "No speaker pronoun data available."

    # Parse lines: detect [Speaker] tag then grab next TH Legacy line
    lines = bilingual_dialogue.split("\n")
    speaker_pronouns: Dict[str, Dict[str, int]] = {s: {} for s in speakers}
    speaker_endings: Dict[str, Dict[str, int]] = {s: {} for s in speakers}

    current_speaker = None
    for i, line in enumerate(lines):
        # Check if line has a speaker tag like "[Masaru] ..."
        m = re.match(r'^\[([^\]]+)\]', line.strip())
        if m:
            raw_spk = m.group(1).strip()
            # Resolve to canonical
            canon = alias_to_canonical.get(raw_spk.lower(), raw_spk)
            current_speaker = canon if canon in speakers else None

        # Check for TH Legacy line
        if current_speaker and '[TH (Legacy)]:' in line:
            th_text = line.split('[TH (Legacy)]:')[-1].strip()
            # Count self pronouns
            for pm in THAI_PRONOUN_RE.finditer(th_text):
                p = pm.group(1)
                speaker_pronouns[current_speaker][p] = speaker_pronouns[current_speaker].get(p, 0) + 1
            # Count ending particles
            for em in THAI_ENDING_RE.finditer(th_text):
                e = em.group(1)
                speaker_endings[current_speaker][e] = speaker_endings[current_speaker].get(e, 0) + 1

    # Build hint string
    hint_parts = []
    for spk in speakers:
        self_counts = speaker_pronouns.get(spk, {})
        end_counts = speaker_endings.get(spk, {})
        if self_counts:
            top_self = sorted(self_counts.items(), key=lambda x: -x[1])[:3]
            self_str = ", ".join(f"{p}({c}x)" for p, c in top_self)
        else:
            self_str = "unknown"
        if end_counts:
            top_end = sorted(end_counts.items(), key=lambda x: -x[1])[:2]
            end_str = ", ".join(f"{p}({c}x)" for p, c in top_end)
        else:
            end_str = "unknown"
        hint_parts.append(f"  {spk}: self_pronoun likely [{self_str}] | ending_particle likely [{end_str}]")

    return "Pronoun hints (from legacy Thai translation - use as reference for base_speech_style):\n" + "\n".join(hint_parts)


def infer_base_speech_style(
    profile_data: dict,
    pronoun_hints_raw: Dict[str, Dict[str, str]],
    known_profiles: Dict[str, dict]
) -> dict:
    """
    Deterministically derive base_speech_style (self_pronoun, target_pronoun,
    ending_particle, formality_level) from:
    1. Ground truth legacy Thai hints
    2. Existing known profile data
    3. Psychological & speech habit tags + identity (gender, age)
    """
    canonical = profile_data.get("canonical_name", profile_data.get("name", ""))
    identity = profile_data.get("identity", {})
    gender = (identity.get("gender") or profile_data.get("gender") or "UNKNOWN").upper()
    age = (identity.get("age") or profile_data.get("age") or "ADULT").upper()

    # Extract tags & weights
    personality = profile_data.get("personality") or profile_data.get("base_state", {}).get("personality", [])
    speech_habit = profile_data.get("speech_habit") or profile_data.get("base_state", {}).get("speech_habit", [])
    values = profile_data.get("values") or profile_data.get("base_state", {}).get("values", [])

    per_tags = {p.get("tag"): p.get("weight", 50) for p in personality if isinstance(p, dict)}
    sp_tags = {s.get("tag"): s.get("weight", 50) for s in speech_habit if isinstance(s, dict)}
    val_tags = {v.get("tag"): v.get("weight", 50) for v in values if isinstance(v, dict)}

    # 1. Compute Formality Level (Scale 1 to 10)
    formality = 5

    # Negative modifiers (Slang, Rude, Sarcastic, Arrogant, Casual)
    if "SPR_SLANG" in sp_tags:
        w = sp_tags["SPR_SLANG"]
        formality -= 3 if w >= 70 else 2
    if "PER_SOC_RUDE" in per_tags:
        w = per_tags["PER_SOC_RUDE"]
        formality -= 3 if w >= 70 else 2
    if "SPR_SARCASTIC" in sp_tags:
        formality -= 1
    if "PER_VIBE_ARROGANT" in per_tags:
        formality -= 1
    if "SPR_DIRECT" in sp_tags and "SPR_POLITE_SUFFIX" not in sp_tags:
        formality -= 1
    if "PER_VIBE_CUTE" in per_tags and age in ("CHILD", "TEEN"):
        formality -= 1

    # Positive modifiers (Polite Suffix, Formal, Noble, Duty)
    if "SPR_POLITE_SUFFIX" in sp_tags:
        w = sp_tags["SPR_POLITE_SUFFIX"]
        formality += 2 if w >= 70 else 1
    if "PER_SOC_POLITE" in per_tags:
        formality += 2
    if "SPR_ELOQUENT" in sp_tags or "SPR_POETIC" in sp_tags:
        formality += 2
    if "VAL_DUTY" in val_tags and val_tags["VAL_DUTY"] >= 80:
        formality += 1

    # Status / Title based adjustment
    name_lower = canonical.lower()
    if any(t in name_lower for t in ["mayor", "executive", "ceo", "earl", "president", "king", "lord"]):
        formality = max(formality, 8)
    elif any(t in name_lower for t in ["manager", "officer", "captain"]):
        formality = max(formality, 6)

    formality = max(1, min(10, formality))

    # 2. Check Legacy Thai Hints (Ground Truth)
    hints = pronoun_hints_raw.get(canonical, {})
    top_self = hints.get("top_self", "")
    top_ending = hints.get("top_ending", "")

    # Check existing base in known profiles
    existing_base = known_profiles.get(canonical, {}).get("base_speech_style", {})
    existing_self = existing_base.get("self_pronoun", "")
    existing_target = existing_base.get("target_pronoun", "")
    existing_ending = existing_base.get("ending_particle", "")

    # 3. Resolve Self Pronoun
    self_pronoun = top_self or existing_self
    if not self_pronoun:
        if age in ("CHILD", "TEEN") and gender == "FEMALE":
            self_pronoun = "หนู"
        elif age in ("CHILD", "TEEN") and gender == "MALE":
            self_pronoun = "ผม" if formality >= 5 else "หนู"
        elif formality <= 2:
            self_pronoun = "กู" if "PER_SOC_RUDE" in per_tags else "เรา"
        elif formality <= 4:
            self_pronoun = "ฉัน" if gender == "FEMALE" else "เรา"
        elif gender == "FEMALE":
            self_pronoun = "ดิฉัน" if formality >= 8 else "ฉัน"
        elif gender == "MALE":
            self_pronoun = "กระผม" if formality >= 8 else "ผม"
        else:
            self_pronoun = "ผม" if formality >= 5 else "ฉัน"

    # 4. Resolve Ending Particle
    ending_particle = top_ending or existing_ending
    if not ending_particle:
        if formality <= 2 or "SPR_SLANG" in sp_tags:
            ending_particle = "วะ"
        elif formality <= 3:
            ending_particle = ""
        elif gender == "FEMALE" or age in ("CHILD", "TEEN"):
            ending_particle = "ค่ะ" if formality >= 4 else "จ้ะ"
        elif gender == "MALE":
            ending_particle = "ครับ" if formality >= 4 else ""
        else:
            ending_particle = "ครับ/ค่ะ" if formality >= 4 else ""

    # 5. Resolve Target Pronoun
    target_pronoun = existing_target
    if not target_pronoun:
        if formality <= 2:
            target_pronoun = "มึง" if "PER_SOC_RUDE" in per_tags else "แก"
        elif formality <= 4:
            target_pronoun = "นาย" if gender == "MALE" else "เธอ"
        elif formality >= 8:
            target_pronoun = "ท่าน"
        else:
            target_pronoun = "คุณ"

    return {
        "self_pronoun": self_pronoun,
        "target_pronoun": target_pronoun,
        "ending_particle": ending_particle,
        "formality_level": formality
    }


# ─────────────────────────────────────────────
# Stage 3: Python Speech Style Mapper
# ─────────────────────────────────────────────
def apply_speech_style_mapping(
    res_list: list,
    known_profiles: Dict[str, dict],
    rule_engine: PriorityRuleEngine,
    pronoun_hints_raw: Dict[str, Dict[str, str]]
) -> dict:
    """
    Stage 3: For each character in LLM results:
    1. Infer base_speech_style (formality_level, self/target pronouns, ending particle)
    2. Use PriorityRuleEngine to compute specific_speech for every relationship.
    """
    updated_res = []
    for res in res_list:
        if not isinstance(res, dict):
            updated_res.append(res)
            continue
        updated_chars = {}
        for char_key, profile_data in res.items():
            if not isinstance(profile_data, dict):
                updated_chars[char_key] = profile_data
                continue

            canonical = profile_data.get("canonical_name", char_key)
            
            # 1. Infer Base Speech Style FIRST
            inferred_base = infer_base_speech_style(profile_data, pronoun_hints_raw, known_profiles)
            profile_data["base_speech_style"] = inferred_base

            # Build rich speaker profile for PriorityRuleEngine evaluation
            speaker_profile = dict(known_profiles.get(canonical, profile_data))
            speaker_profile["base_speech_style"] = inferred_base
            if "identity" not in speaker_profile:
                speaker_profile["identity"] = {
                    "gender": profile_data.get("gender", "UNKNOWN"),
                    "age": profile_data.get("age", "UNKNOWN"),
                    "species": profile_data.get("species", "UNKNOWN")
                }

            # 2. Compute specific_speech for each relationship via PriorityRuleEngine
            new_rels = []
            for rel in profile_data.get("relationships", []):
                if not isinstance(rel, dict):
                    new_rels.append(rel)
                    continue
                target_name = rel.get("target_name", "")
                listener_profile = known_profiles.get(target_name)
                result = rule_engine.evaluate_priority_pipeline(
                    speaker_profile=speaker_profile,
                    listener_profile=listener_profile,
                    dynamic_tags=[],
                    is_question=False
                )
                guidelines = result.get("guidelines", {})
                rel["specific_speech"] = {
                    "self_pronoun": guidelines.get("self_pronoun") or inferred_base["self_pronoun"],
                    "target_pronoun": guidelines.get("target_pronoun") or inferred_base["target_pronoun"],
                    "ending_particle": guidelines.get("ending_particle") or inferred_base["ending_particle"],
                    "rule_applied": result.get("rule_id", "TIER3_BASE_FALLBACK")
                }
                new_rels.append(rel)
            profile_data["relationships"] = new_rels

            updated_chars[char_key] = profile_data
        updated_res.append(updated_chars)
    return updated_res


async def run_analyzer(data_dir: str):
    timeline_dir = os.path.join(data_dir, "timeline_chunks_v2")
    profiles_dir = os.path.join(data_dir, "profiles")
    analyzed_log_path = os.path.join(data_dir, "analyzed_chunks.log")
    alias_mapping_path = os.path.join(data_dir, "alias_mapping.json")
    glossary_path = os.path.join(data_dir, "tlas_glossary.json")
    
    os.makedirs(profiles_dir, exist_ok=True)

    # 0. Initialize Rule Engine (Stage 3)
    taxonomy_path = os.path.join(data_dir, "taxonomy.json")
    rule_engine = PriorityRuleEngine(taxonomy_path)
    print(f"[Init] PriorityRuleEngine loaded from {taxonomy_path}")

    # 0.5. Load Canonical Whitelist from Glossary (Single Source of Truth)
    canonical_whitelist: Set[str] = set()
    if os.path.exists(glossary_path):
        try:
            with open(glossary_path, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            for c in gdata.get("Characters", {}).keys():
                if not is_garbage_or_disposable(c):
                    canonical_whitelist.add(c.strip())
            print(f"[Init] Loaded {len(canonical_whitelist)} valid canonical characters from Glossary Whitelist.")
        except Exception as e:
            print(f"[Warning] Could not load glossary whitelist: {e}")
            
    # Fallback essentials if glossary is empty
    known_essentials = {
        "Akane", "Akira", "Alisa", "Arisa", "Dan", "Desi", "Drake", "Enjo",
        "Erica", "Executive", "Foregrave", "Godmother", "Hatta", "Headmistress",
        "Honda", "Janice", "Jikan CEO", "Kin", "Kosai", "Lily", "Lyra",
        "Masaru", "Mayor", "Mike", "Natalie", "Otto", "Raven", "Reiko",
        "Rimi", "Ritchie", "Rum", "Saru", "Shion", "The Earl", "The Manager",
        "Turbo", "Wallace"
    }
    canonical_whitelist.update(known_essentials)

    # 1. Initialize Legacy Thai Matcher from CSV
    csv_path = os.path.abspath(os.path.join(data_dir, "../../testing files/SSPV034v1.35 - Trans - ชีต1_out.csv"))
    if not os.path.exists(csv_path):
        csv_path = os.path.abspath(os.path.join(data_dir, "../../Example RPMG Game/SSPV034v1.35 - Trans - ชีต1_out.csv"))
    matcher = LegacyThaiMatcher(csv_path)
    
    # 2. Load Existing Profiles and Build Alias Index
    alias_to_canonical: Dict[str, str] = {}
    known_profiles: Dict[str, dict] = {}
    
    for pf in glob.glob(os.path.join(profiles_dir, "*.json")):
        try:
            with open(pf, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            cname = pdata.get("name", os.path.basename(pf).replace(".json", "")).strip()
            if is_garbage_or_disposable(cname):
                continue
            known_profiles[cname] = pdata
            alias_to_canonical[cname.lower()] = cname
            for alias in pdata.get("aliases", []):
                if not is_garbage_or_disposable(alias):
                    alias_to_canonical[alias.lower()] = cname
        except Exception as e:
            print(f"[Warning] Could not load profile {pf}: {e}")
            
    if os.path.exists(alias_mapping_path):
        try:
            with open(alias_mapping_path, "r", encoding="utf-8") as f:
                saved_aliases = json.load(f)
            for a, c in saved_aliases.items():
                if not is_garbage_or_disposable(a) and not is_garbage_or_disposable(c):
                    alias_to_canonical[a.lower()] = c
        except Exception:
            pass

    # Ensure all canonical whitelist members map to themselves
    for can in canonical_whitelist:
        alias_to_canonical[can.lower()] = can
            
    def save_alias_mapping():
        tmp = alias_mapping_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(alias_to_canonical, f, ensure_ascii=False, indent=2)
        os.replace(tmp, alias_mapping_path)
        
    def get_known_characters_summary() -> str:
        """Compact list of all valid canonical names + aliases (for Stage 1 speaker ID)."""
        items = []
        # Sort canonical whitelist for deterministic prompt
        for cname in sorted(canonical_whitelist):
            pdata = known_profiles.get(cname)
            aliases = pdata.get("aliases", [cname]) if pdata else [cname]
            other_aliases = [a for a in aliases if a.lower() != cname.lower() and not is_garbage_or_disposable(a)]
            if other_aliases:
                items.append(f"{cname} (also known as: {', '.join(other_aliases[:3])})")
            else:
                items.append(cname)
        return ", ".join(items) if items else "None"

    def get_speaker_profiles_info(speakers: List[str]) -> str:
        """Build focused profile summary for Stage 2 — only characters in this scene."""
        if not speakers:
            return "No specific speaker profiles identified."
        parts = []
        for spk in speakers:
            canon = alias_to_canonical.get(spk.lower(), spk)
            pdata = known_profiles.get(canon)
            if pdata:
                # Compact: personality tags + existing relationships
                per_tags = [t["tag"] for t in pdata.get("base_state", {}).get("personality", [])]
                rel_targets = [r.get("target_name", "") for r in pdata.get("base_state", {}).get("relationships", [])]
                aliases = [a for a in pdata.get("aliases", []) if a.lower() != canon.lower()]
                alias_str = f" (also: {', '.join(aliases[:3])}" + ")" if aliases else ""
                per_str = ", ".join(per_tags[:3]) if per_tags else "unknown"
                rel_str = ", ".join(rel_targets[:4]) if rel_targets else "none known"
                parts.append(f"  {canon}{alias_str}: personality=[{per_str}], known_relations=[{rel_str}]")
            else:
                parts.append(f"  {spk}: (new character, no prior profile)")
        return "Known profiles for scene participants:\n" + "\n".join(parts)

    def build_pronoun_hints_raw(speakers: List[str], bilingual_dialogue: str) -> Dict[str, Dict[str, str]]:
        """Build raw pronoun hint dict for Stage 3 base_speech_style injection."""
        lines = bilingual_dialogue.split("\n")
        result = {}
        current_speaker = None
        for line in lines:
            m = re.match(r'^\[([^\]]+)\]', line.strip())
            if m:
                raw_spk = m.group(1).strip()
                canon = alias_to_canonical.get(raw_spk.lower(), raw_spk)
                current_speaker = canon if canon in speakers else None
            if current_speaker and '[TH (Legacy)]:' in line:
                th_text = line.split('[TH (Legacy)]:')[-1].strip()
                sp_matches = THAI_PRONOUN_RE.findall(th_text)
                ed_matches = THAI_ENDING_RE.findall(th_text)
                if current_speaker not in result:
                    result[current_speaker] = {"self_counts": {}, "end_counts": {}}
                for p in sp_matches:
                    result[current_speaker]["self_counts"][p] = result[current_speaker]["self_counts"].get(p, 0) + 1
                for e in ed_matches:
                    result[current_speaker]["end_counts"][e] = result[current_speaker]["end_counts"].get(e, 0) + 1
        # Flatten to top candidate
        flat = {}
        for spk, counts in result.items():
            sc = counts.get("self_counts", {})
            ec = counts.get("end_counts", {})
            flat[spk] = {
                "top_self": max(sc, key=sc.get) if sc else "",
                "top_ending": max(ec, key=ec.get) if ec else ""
            }
        return flat

    # 3. Sorting Chunks
    chunk_files = glob.glob(os.path.join(timeline_dir, "chunk_*.json"))
    print(f"Sorting {len(chunk_files)} chunks chronologically...")
    chunk_files.sort(key=get_chunk_sort_key)
    
    # Removed analyzed_chunks.log logic; relying on single source of truth (analyzed_scenes.log)
    analyzed_chunks = set()
            
    llm_cache_path = os.path.join(data_dir, "llm_cache.json")
    llm_cache = {}
    if os.path.exists(llm_cache_path):
        try:
            with open(llm_cache_path, "r", encoding="utf-8") as f:
                llm_cache = json.load(f)
        except:
            llm_cache = {}

    scene_log_path = os.path.join(data_dir, "analyzed_scenes.log")
    analyzed_scenes = set()
    if os.path.exists(scene_log_path):
        with open(scene_log_path, "r", encoding="utf-8") as f:
            analyzed_scenes = set(line.strip() for line in f if line.strip())
            
    def save_cache():
        tmp = llm_cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(llm_cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, llm_cache_path)

    def mark_scene_done(cache_key: str):
        with open(scene_log_path, "a", encoding="utf-8") as f:
            f.write(cache_key + "\n")
        analyzed_scenes.add(cache_key)

    def write_profiles_immediately(res_list: list, meta: dict):
        for res in res_list:
            if not isinstance(res, dict):
                continue
            for char_key, profile_data in res.items():
                if not isinstance(profile_data, dict):
                    continue
                if char_key.lower() in ("status", "reason", "_status", "no_characters_found", "ไม่พบตัวละคร"):
                    continue
                    
                # 1. Resolve Canonical Name & Aliases
                raw_canonical = profile_data.get("canonical_name", char_key).strip()
                if not raw_canonical or "True Identity Name" in raw_canonical:
                    raw_canonical = char_key.strip()
                    
                # Clean parenthesized aliases like 'Janice (Fruity Girl)' -> 'Janice'
                clean_canonical = re.sub(r"\s*[\(\[\{][^\)\]\}]*[\)\]\}]", "", raw_canonical).strip()
                if not clean_canonical:
                    clean_canonical = raw_canonical
                    
                # Lookup in alias mapping if raw is already an alias
                if clean_canonical.lower() in alias_to_canonical:
                    canonical = alias_to_canonical[clean_canonical.lower()]
                elif char_key.lower() in alias_to_canonical:
                    canonical = alias_to_canonical[char_key.lower()]
                else:
                    canonical = clean_canonical
                    
                # 2. Filter against canonical whitelist (Strict Whitelist Guard)
                is_in_whitelist = False
                for w in canonical_whitelist:
                    if canonical.lower() == w.lower():
                        canonical = w
                        is_in_whitelist = True
                        break
                if not is_in_whitelist or is_garbage_or_disposable(canonical) or is_garbage_or_disposable(char_key):
                    print(f"      [Filter Guard] Discarding non-whitelisted / garbage character: '{char_key}' / '{canonical}'")
                    continue
                    
                # 3. Collect and Merge Aliases
                ai_aliases = profile_data.get("aliases", [])
                if isinstance(ai_aliases, str):
                    ai_aliases = [ai_aliases]
                new_aliases_set = set(ai_aliases)
                new_aliases_set.add(canonical)
                new_aliases_set.add(char_key)
                if raw_canonical != canonical:
                    new_aliases_set.add(raw_canonical)
                    
                # Register aliases
                for a in new_aliases_set:
                    a_clean = a.strip()
                    if a_clean and not is_generic_disposable(a_clean):
                        alias_to_canonical[a_clean.lower()] = canonical
                save_alias_mapping()
                
                safe_filename = get_safe_filename(canonical)
                profile_path = os.path.join(profiles_dir, f"{safe_filename}.json")

                def validate_tag(tag: str, allowed_set: list, corrections: dict, fallback: str = None) -> str:
                    """Validate a taxonomy tag. Apply correction if known hallucination, else fallback."""
                    if tag in allowed_set:
                        return tag
                    # Try correction map
                    corrected = corrections.get(tag)
                    if corrected and corrected in allowed_set:
                        logger.warning(f"[TagFix] Corrected invalid tag '{tag}' → '{corrected}'")
                        return corrected
                    # Unknown tag
                    if fallback:
                        logger.warning(f"[TagFix] Unknown tag '{tag}' — using fallback '{fallback}'")
                        return fallback
                    return None  # Will be filtered out

                def filter_weighted_tags(tags, allowed_set: list = None, corrections: dict = None):
                    res_tags = []
                    for t in tags:
                        if isinstance(t, dict) and "tag" in t:
                            w = t.get("weight", 50)
                            if isinstance(w, (int, float)):
                                if w <= 10 and w > 0:
                                    w = int(w * 10)
                                else:
                                    w = int(w)
                            else:
                                w = 50
                            raw_tag = t["tag"]
                            if allowed_set is not None and corrections is not None:
                                validated = validate_tag(raw_tag, allowed_set, corrections)
                                if validated is None:
                                    logger.warning(f"[TagFix] Dropping unknown tag '{raw_tag}' (no correction found)")
                                    continue
                                raw_tag = validated
                            res_tags.append({"tag": raw_tag, "weight": min(100, max(1, w))})
                        elif isinstance(t, str):
                            res_tags.append({"tag": t, "weight": 50})
                    return res_tags

                # Merge all valid personality/speech/values tags from taxonomy
                all_trait_tags = agent.personality_tags + agent.speech_tags + agent.values_tags
                trait_corrections = {}  # Personality/speech/values don't have known corrections
                    
                filtered_personality = filter_weighted_tags(profile_data.get("personality", []), None, trait_corrections)
                filtered_speech = filter_weighted_tags(profile_data.get("speech_habit", []), None, trait_corrections)
                filtered_values = filter_weighted_tags(profile_data.get("values", []), None, trait_corrections)
                
                filtered_rels = []
                for rel in profile_data.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    target_name = rel.get("target_name", "").strip()
                    if not target_name:
                        continue
                        
                    target_canonical = alias_to_canonical.get(target_name.lower(), target_name)
                    if is_generic_disposable(target_canonical):
                        continue
                        
                    roles = rel.get("roles", [])
                    if isinstance(roles, str):
                        roles = [roles]

                    # Validate & correct roles
                    validated_roles = []
                    for r in roles:
                        v = validate_tag(r, agent.role_tags, agent.ROLE_CORRECTIONS, fallback="ROLE_SOC_STRANGER")
                        if v:
                            validated_roles.append(v)
                    if not validated_roles:
                        validated_roles = ["ROLE_SOC_STRANGER"]

                    # Validate & correct affinity
                    raw_aff = rel.get("affinity", "AFF_NEUTRAL")
                    validated_aff = validate_tag(raw_aff, agent.aff_tags, agent.AFF_CORRECTIONS, fallback="AFF_NEUTRAL")

                    # Validate & correct intimacy
                    raw_int = rel.get("intimacy", "INT_DISTANT")
                    validated_int = validate_tag(raw_int, agent.intimacy_tags, {}, fallback="INT_DISTANT")

                    # Validate & correct power_dynamic
                    raw_dyn = rel.get("power_dynamic", "DYN_EQUAL")
                    validated_dyn = validate_tag(raw_dyn, agent.dyn_tags, agent.DYN_CORRECTIONS, fallback="DYN_EQUAL")

                    filtered_rels.append({
                        "target_character_id": f"CHAR_{get_safe_filename(target_canonical).upper()}",
                        "target_name": target_canonical,
                        "roles": validated_roles,
                        "affinity": validated_aff,
                        "intimacy": validated_int,
                        "power_dynamic": validated_dyn,
                        "specific_speech": rel.get("specific_speech", {})
                    })
                
                base_speech = profile_data.get("base_speech_style", {})
                current_state_payload = {
                    "personality": filtered_personality,
                    "speech_habit": filtered_speech,
                    "values": filtered_values,
                    "relationships": filtered_rels
                }
                
                # Load or initialize Profile
                if os.path.exists(profile_path):
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            existing_profile = json.load(f)
                    except Exception:
                        existing_profile = {
                            "character_id": f"CHAR_{safe_filename.upper()}",
                            "name": canonical,
                            "aliases": [canonical],
                            "identity": {"name": canonical},
                            "base_state": {},
                            "timeline_states": []
                        }
                else:
                    existing_profile = {
                        "character_id": f"CHAR_{safe_filename.upper()}",
                        "name": canonical,
                        "aliases": [canonical],
                        "identity": {
                            "gender": profile_data.get("gender", "UNKNOWN"),
                            "age": profile_data.get("age", "UNKNOWN"),
                            "species": profile_data.get("species", "UNKNOWN")
                        },
                        "base_speech_style": {
                            "self_pronoun": base_speech.get("self_pronoun", ""),
                            "target_pronoun": base_speech.get("target_pronoun", ""),
                            "ending_particle": base_speech.get("ending_particle", ""),
                            "formality_level": base_speech.get("formality_level", 5)
                        },
                        "base_state": {},
                        "timeline_states": []
                    }
                    
                # Merge aliases into existing profile
                curr_aliases = set(existing_profile.get("aliases", []))
                for a in new_aliases_set:
                    if a and not is_generic_disposable(a):
                        curr_aliases.add(a)
                existing_profile["aliases"] = sorted(list(curr_aliases))

                # Removed: Base state shouldn't be overwritten during Map Phase (ADR-014)

                # Update base_speech_style if missing or incomplete
                if "base_speech_style" not in existing_profile:
                    existing_profile["base_speech_style"] = dict(base_speech)
                else:
                    curr_bs = existing_profile["base_speech_style"]
                    if not curr_bs.get("self_pronoun") and base_speech.get("self_pronoun"):
                        curr_bs["self_pronoun"] = base_speech["self_pronoun"]
                    if not curr_bs.get("target_pronoun") and base_speech.get("target_pronoun"):
                        curr_bs["target_pronoun"] = base_speech["target_pronoun"]
                    if not curr_bs.get("ending_particle") and base_speech.get("ending_particle"):
                        curr_bs["ending_particle"] = base_speech["ending_particle"]
                    if (curr_bs.get("formality_level") == 5 or not curr_bs.get("formality_level")) and base_speech.get("formality_level"):
                        curr_bs["formality_level"] = base_speech["formality_level"]

                latest_state = {}
                if existing_profile.get("timeline_states"):
                    latest_state = existing_profile["timeline_states"][-1].get("delta", {})
                    
                if dicts_differ(current_state_payload, latest_state):
                    delta_entry = {
                        "state_id": f"STATE_{meta['timeline_phase']}_{meta['chunk_id']}_{meta['sub_idx']}",
                        "trigger_event_id": meta["chunk_id"],
                        "timeline_phase": meta["timeline_phase"],
                        "conditions": meta.get("conditions", []),
                        "description": meta["summary"][:200] + "...",
                        "delta": current_state_payload
                    }
                    if "timeline_states" not in existing_profile:
                        existing_profile["timeline_states"] = []
                    existing_profile["timeline_states"].append(delta_entry)
                
                # Write atomic
                tmp_path = profile_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(existing_profile, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, profile_path)
                
                # Update in-memory reference
                known_profiles[canonical] = existing_profile
            
    agent = TLASAnalyzerAgent()
    start_time = time.time()
    
    print("\n[Pre-flight] Checking checkpoint consistency...")
    analyzed_chunks = set()
    pending_files = []
    
    # Pre-flight check to determine TRUE pending files based on scene-level completion
    for cf in chunk_files:
        basename = os.path.basename(cf)
        try:
            with open(cf, "r", encoding="utf-8") as f:
                chunk_data = json.load(f)
            raw_scenes = chunk_data.get("raw_scenes", chunk_data.get("raw_dialogues", []))
            if not raw_scenes:
                analyzed_chunks.add(basename)
                continue
                
            all_scenes_done = True
            for s_idx, scene in enumerate(raw_scenes):
                if "dialogues" in scene:
                    text = "\n".join([f"[{d.get('speaker', '')}]: {d.get('text', '')}" for d in scene.get("dialogues", [])])
                else:
                    text = scene.get("text", "")
                if not text.strip(): continue
                # Basic check: if even the first sub-chunk isn't in scenes log, it's not fully done
                # A robust check will be done during the actual processing loop
                if f"{basename}_scene_{s_idx}_sub_0" not in analyzed_scenes:
                    all_scenes_done = False
                    break
            
            if all_scenes_done:
                # We assume it's fully done, the main loop will verify thoroughly
                analyzed_chunks.add(basename)
            else:
                pending_files.append(cf)
        except Exception:
            pending_files.append(cf)
            
    total_files = len(chunk_files)
    total_pending = len(pending_files)
    completed = len(analyzed_chunks)
    
    print(f"\nTotal Files: {total_files} | Already Done: {completed} | Pending: {total_pending}\n")
    
    for idx, cf in enumerate(pending_files):
        basename = os.path.basename(cf)
        print(f"\n==================================================")
        print(f"[{completed+1}/{total_files}] Processing {basename}...")
        print(f"==================================================")
        
        with open(cf, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
            
        phase = chunk_data.get("story_phase", 1)
        summary = chunk_data.get("summary", "")
        print(f"  - Loaded Summary: {len(summary)} chars")
        
        raw_scenes = chunk_data.get("raw_scenes", chunk_data.get("raw_dialogues", []))
        print(f"  - Loaded Scenes: {len(raw_scenes)}")
        
        if len(summary) > 3000:
            print(f"  [AI-Pre] Summary is too long ({len(summary)} chars). Splitting and summarizing...")
            summary_chunks = split_text_intelligently(summary, max_len=2500)
            compressed_summaries = []
            for i, schunk in enumerate(summary_chunks):
                cache_key = f"{basename}_prepost_{i}"
                if cache_key in llm_cache:
                    print(f"    -> [CACHE HIT] Loaded prepost {i+1} instantly!")
                    compressed = llm_cache[cache_key]
                else:
                    print(f"    -> Summarizing chunk {i+1}/{len(summary_chunks)} ({len(schunk)} chars)...")
                    compressed = await agent.summarize_long_text(schunk)
                    llm_cache[cache_key] = compressed
                    save_cache()
                compressed_summaries.append(compressed)
            summary = "\n\n".join(compressed_summaries)
            print(f"  [AI-Pre] Compression complete! New summary length: {len(summary)} chars.")

        if not raw_scenes:
            print("  - No dialogues. Skipping.")
            completed += 1
            continue
            
        known_chars_info = get_known_characters_summary()
        chunk_scene_done_count = 0
        chunk_scene_total = 0

        batches = []
        current_batch = []
        current_tokens = 0
        # Restored to 4000. Now that safe_max_tokens is None, reasoning models have enough space to finish 
        # their internal monologue and JSON output, so we can afford a slightly larger prompt batch.
        MAX_PROMPT_TOKENS = 4000
        
        try:
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None
            
        def count_tokens(text):
            if enc:
                return len(enc.encode(text))
            return len(text) // 3
            
        summary_tokens = count_tokens(summary)
        
        for s_idx, scene in enumerate(raw_scenes):
            if "dialogues" in scene:
                text = "\n".join([f"[{d.get('speaker', '')}]: {d.get('text', '')}" for d in scene.get("dialogues", [])])
            else:
                text = scene.get("text", "")
            if not text.strip(): continue
            source = scene.get("location", scene.get("source", "Unknown"))
            tl_phase = scene.get("timeline_phase", 0)
            story_phase = phase
            
            pre_conds = scene.get("pre_conditions", {})
            conditions = []
            if isinstance(pre_conds, dict):
                conditions.extend(pre_conds.get("switches", []))
                conditions.extend(pre_conds.get("variables", []))
            elif isinstance(pre_conds, list):
                conditions = pre_conds
            else:
                conditions = scene.get("conditions", [])
                
            cond_str = ", ".join(conditions) if conditions else "None"
            
            bilingual_dialogue = matcher.format_bilingual_dialogue(source, text)
            chunk_scene_total += 1
            
            scene_id = f"Scene_{s_idx}"
            hdr = f"--- [{scene_id}] Source: {source} | Timeline: {tl_phase} | Story: {story_phase} | Cond: {cond_str} ---\n"
            full_text = hdr + bilingual_dialogue
            scene_tokens = count_tokens(full_text)
            
            max_allowed_for_scene = MAX_PROMPT_TOKENS - summary_tokens - 1000
            if max_allowed_for_scene < 1000:
                max_allowed_for_scene = 1000  # Fallback minimum if summary is huge
            
            if scene_tokens > max_allowed_for_scene:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                
                lines = bilingual_dialogue.split('\n')
                sub_current = ""
                sub_idx = 0
                for line in lines:
                    line_text = line + "\n"
                    if count_tokens(hdr + sub_current + line_text) > max_allowed_for_scene and sub_current:
                        sub_scene_id = f"Scene_{s_idx}_sub_{sub_idx}"
                        sub_hdr = f"--- [{sub_scene_id}] Source: {source} | Timeline: {tl_phase} | Story: {story_phase} | Cond: {cond_str} ---\n"
                        batches.append([(s_idx, scene, sub_hdr + sub_current, sub_scene_id)])
                        sub_current = line_text
                        sub_idx += 1
                    else:
                        sub_current += line_text
                        
                if sub_current.strip():
                    sub_scene_id = f"Scene_{s_idx}_sub_{sub_idx}"
                    sub_hdr = f"--- [{sub_scene_id}] Source: {source} | Timeline: {tl_phase} | Story: {story_phase} | Cond: {cond_str} ---\n"
                    batches.append([(s_idx, scene, sub_hdr + sub_current, sub_scene_id)])
            else:
                if current_tokens + scene_tokens > max_allowed_for_scene and current_batch:
                    batches.append(current_batch)
                    current_batch = [(s_idx, scene, full_text, scene_id)]
                    current_tokens = scene_tokens
                else:
                    current_batch.append((s_idx, scene, full_text, scene_id))
                    current_tokens += scene_tokens
                    
        if current_batch:
            batches.append(current_batch)
            
        print(f"\n  -> Formed {len(batches)} batches for this chunk.")

        for b_idx, batch in enumerate(batches):
            all_cached = True
            for item in batch:
                s_idx, scene, text, scene_id = item
                sub_c_idx = scene_id.split('_')[-1] if 'sub' in scene_id else 0
                old_cache_key = f"{basename}_scene_{s_idx}_sub_{sub_c_idx}"
                if old_cache_key not in analyzed_scenes:
                    all_cached = False
                    break
                    
            if all_cached:
                print(f"     -> [SKIP] Batch {b_idx+1}/{len(batches)} fully cached. Skipping API.")
                chunk_scene_done_count += len(batch)
                continue
                
            print(f"\n==================================================")
            print(f"  [Batch {b_idx+1}/{len(batches)}] Processing {len(batch)} scenes together...")
            
            combined_text = "\n\n".join([item[2] for item in batch])
            batch_cache_key = f"{basename}_batch_{b_idx}"
            
            try:
                if batch_cache_key in llm_cache:
                    print(f"     -> [CACHE HIT] Loaded batch analysis (Stage 2 cached).")
                    res_dict = llm_cache[batch_cache_key]
                else:
                    print(f"     -> [Stage 1] Identifying target speakers for batch locally...")
                    
                    resolved_speakers = set()
                    for line in combined_text.split("\n"):
                        m = re.match(r'^\[([^\]]+)\]', line.strip())
                        if m:
                            raw_spk = m.group(1).replace(":", "").strip()
                            if is_garbage_or_disposable(raw_spk): continue
                            can = alias_to_canonical.get(raw_spk.lower(), raw_spk)
                            for w in canonical_whitelist:
                                if can.lower() == w.lower():
                                    resolved_speakers.add(w)
                                    break
                    
                    speakers = sorted(list(resolved_speakers))
                    
                    if speakers:
                        print(f"     -> [Stage 1] Target Canonical Characters: {', '.join(speakers)}")
                    else:
                        print(f"     -> [Stage 1] No valid canonical characters in this batch. Fast-skipping Stage 2.")
                        for item in batch:
                            s_idx, scene, text, scene_id = item
                            sub_c_idx = scene_id.split('_')[-1] if 'sub' in scene_id else 0
                            mark_scene_done(f"{basename}_scene_{s_idx}_sub_{sub_c_idx}")
                        chunk_scene_done_count += len(batch)
                        continue

                    profile_info = get_speaker_profiles_info(speakers)
                    print(f"     -> [Stage 2] Analyzing psychology + 4D for [{', '.join(speakers)}] in {len(batch)} scenes...")
                    res_dict = await agent.analyze_scene_text(
                        summary_text=summary,
                        scene_header="Multiple Scenes Batched",
                        bilingual_dialogue=combined_text,
                        target_characters=speakers,
                        profile_info=profile_info
                    )
                    llm_cache[batch_cache_key] = res_dict
                    save_cache()
                    
                # Process Stage 3 and save per scene
                for item in batch:
                    s_idx, scene, text, scene_id = item
                    sub_c_idx = scene_id.split('_')[-1] if 'sub' in scene_id else 0
                    old_cache_key = f"{basename}_scene_{s_idx}_sub_{sub_c_idx}"
                    
                    scene_res = res_dict.get(scene_id)
                    if scene_res:
                        pronoun_hints_raw = build_pronoun_hints_raw(
                            [alias_to_canonical.get(n.lower(), n) for n in known_profiles.keys()],
                            text
                        )
                        res_list = [scene_res]
                        res_list = apply_speech_style_mapping(res_list, known_profiles, rule_engine, pronoun_hints_raw)
                        
                        meta = {
                            "timeline_phase": scene.get("timeline_phase", 0),
                            "chunk_id": chunk_data.get("id", chunk_data.get("cluster_id", "Unknown")),
                            "sub_idx": f"{s_idx}_{sub_c_idx}",
                            "summary": summary,
                            "conditions": conditions
                        }
                        write_profiles_immediately(res_list, meta)
                    
                    mark_scene_done(old_cache_key)
                    chunk_scene_done_count += 1
                    
            except Exception as e:
                import traceback
                print(f"\n[FATAL] Batch processing error: {e}. ABORTING to prevent skipping!")
                fallback_log = os.path.join(data_dir, "crash_logs.txt")
                with open(fallback_log, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat()}] Batch error on {basename}\nError: {e}\n{traceback.format_exc()}\n{'-'*40}\n")
                # Do NOT mark as done! Abort the entire program so Watchdog catches it.
                sys.exit(1)
        print(f"\n  - Scenes processed: {chunk_scene_done_count}/{chunk_scene_total}")
        
        # No need to write to analyzed_chunks.log, scene log is single source of truth
            
        completed += 1
        elapsed = time.time() - start_time
        avg_time = elapsed / completed
        remaining = total_pending - completed
        eta_sec = avg_time * remaining
        
        print(f"\n[SUCCESS] {basename} completed and saved!")
        print(f"[STATUS] Progress: {completed}/{total_pending} ({completed/total_pending*100:.1f}%) | ETA: {eta_sec/60:.1f} mins | Avg: {avg_time:.1f}s/file")
        print(f"==================================================\n")
            
    print("\nTLAS Analyzer Finished Successfully 100%!")

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    asyncio.run(run_analyzer(tlas_dir))
