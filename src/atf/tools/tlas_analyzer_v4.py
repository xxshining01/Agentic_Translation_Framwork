"""
TLAS v4.0 Lean Feature Analyzer (Smart Scene Packing Architecture)
Architecture: SAD-010 | Design: SDD-010, SDD-011 | ADR: ADR-010, ADR-015

หน้าที่:
1. อ่านไฟล์ rpgm_scenes_v5.json และกรอง Speaker ตาม Whitelist จาก tlas_glossary.json
2. Fast-Skip ฉากที่มีเฉพาะ Ambient NPCs หรือไม่มีบทสนทนา (0 LLM Tokens)
3. Smart Scene Packing: แพ็คฉากที่มีตัวละครเป้าหมายต่อกันเป็นก้อน Batch จนเกือบเต็มขีดจำกัด
   โดยรักษาขอบเขตของซีน (Scene Boundary) ไว้สมบูรณ์ 100% ไม่มีการตัดกลางซีน
4. ส่งให้ LLM สกัด Macro Features ตาม Taxonomy โดยปราศจากคำสรรพนามภาษาไทย (Zero Thai Pronouns)
5. เมื่อได้คำตอบ แยกผลลัพธ์บันทึกเป็น Checkpoint รายซีนลง data/tlas/extractions_v4/{safe_id}.json
6. รองรับ Adaptive Resilience: หาก Batch มีปัญหา จะแบ่งครึ่งอัตโนมัติ (Binary Fallback) และ Retry
"""

import os
import sys
import json
import glob
import re
import time
import asyncio
import logging
from typing import List, Dict, Optional, Set, Any, Tuple

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from json_repair import repair_json
from src.atf.agents.base import BaseAgent
try:
    from src.atf.tools.tlas_consensus_engine import TLASConsensusEngine, is_invalid_or_disposable_speaker
except ImportError:
    from tlas_consensus_engine import TLASConsensusEngine, is_invalid_or_disposable_speaker


logger = logging.getLogger("tlas_analyzer_v4")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [V4-Analyzer] %(message)s',
    handlers=[
        logging.FileHandler("tlas_analyzer_v4.log", encoding="utf-8", mode="a"),
        logging.StreamHandler(sys.stdout)
    ]
)

EXTRACTION_SYSTEM_PROMPT = """You are an expert game narrative and psychological profiling AI.
Your task is to analyze multiple distinct game scenes and extract psychological traits, social dynamics, and scene context for the specified target characters.

### STRICT RULES:
1. Output ONLY a valid JSON object matching the requested schema with a "scenes" array.
2. DO NOT include any Thai pronouns (like ผม, ฉัน, เรา, นาย, เธอ, ครับ, ค่ะ). Thai pronouns are strictly handled by downstream systems.
3. Use tags ONLY from the provided Taxonomy standard:
   - Personality: PER_SOC_*, PER_MIND_*, PER_VIBE_* (e.g. PER_SOC_POLITE, PER_SOC_RUDE, PER_MIND_LOGICAL, PER_VIBE_SERIOUS)
   - Speech Habit: SPR_* (e.g. SPR_DIRECT, SPR_HESITANT, SPR_POLITE_SUFFIX, SPR_SARCASTIC, SPR_INTERNAL)
   - Values: VAL_* (e.g. VAL_DUTY, VAL_FREEDOM, VAL_FAMILY, VAL_POWER, VAL_COMPASSION)
   - Roles: ROLE_FAM_*, ROLE_WORK_*, ROLE_SOC_*, ROLE_ROM_* (e.g. ROLE_FAM_SIBLING_YOUNGER, ROLE_SOC_PEER, ROLE_WORK_BOSS)
   - Affinity: AFF_DEVOTED, AFF_FOND, AFF_NEUTRAL, AFF_CONFLICTED, AFF_HOSTILE
   - Intimacy: INT_CONFIDANT, INT_FAMILIAR, INT_DISTANT, INT_ESTRANGED
   - Power Dynamic: DYN_DOMINANT, DYN_EQUAL, DYN_SUBMISSIVE
   - Emotion: EMO_NEUTRAL, EMO_JOY, EMO_ANGER, EMO_SADNESS, EMO_FEAR, EMO_SURPRISE, EMO_DISGUST
   - Tone: TON_SERIOUS, TON_PLAYFUL, TON_SARCASTIC, TON_GENTLE, TON_AGGRESSIVE, TON_COLD
4. Weight range is strictly 1 to 100 (Integer).
5. In speech_style of relationships, specify ONLY the derivation rule (e.g., 'RULE_OLDER_BROTHER_TO_YOUNGER_SISTER', 'RULE_PEER_POLITE', 'RULE_SUBORDINATE_TO_BOSS').
6. For EACH scene, extract traits and relationships ONLY for the specified Target Characters. DO NOT create character objects for ambient NPCs or background characters.

### REQUIRED JSON SCHEMA:
{
  "scenes": [
    {
      "scene_id": "Exact Scene ID from the prompt header (e.g. CommonEvent_1)",
      "characters": [
        {
          "character_name": "Speaker Name",
          "delta": {
            "personality": [{"tag": "PER_...", "weight": 80}],
            "speech_habit": [{"tag": "SPR_...", "weight": 70}],
            "values": [{"tag": "VAL_...", "weight": 90}],
            "relationships": [
              {
                "target_character_id": "CHAR_TARGET",
                "target_name": "Target Name",
                "roles": ["ROLE_..."],
                "affinity": "AFF_...",
                "intimacy": "INT_...",
                "power_dynamic": "DYN_...",
                "speech_style": {
                  "derivation_rule": "RULE_..."
                }
              }
            ]
          }
        }
      ],
      "scene_context": "Concise 1-2 sentence description of what happens in this scene and who is present.",
      "dialogue_metadata": [
        {
          "dialogue_index": 0,
          "speaker": "Speaker Name",
          "listener": "Target Name",
          "emotion": "EMO_...",
          "tone": "TON_..."
        }
      ]
    }
  ]
}
"""

def clean_dialogue_text(text: str) -> str:
    """Removes RPG Maker control codes and tags for clean analysis."""
    if not text:
        return ""
    text = re.sub(r"^(\n)?<[^>]+>\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(r"\\[a-zA-Z]+(\[[0-9]+\])?", "", text)
    text = re.sub(r"\\[\|\.\!\^\{\}\\]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def get_safe_id(source: str) -> str:
    return "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in source)

class TLASAnalyzerAgentV4(BaseAgent):
    def __init__(self, model_name: str = "chatgpt-web", api_base: str = "http://127.0.0.1:8765/v1"):
        super().__init__(model_name=model_name, agent_name="TLAS-Analyzer-V4", api_base=api_base)

    async def process(self, input_data: Any) -> Any:
        return {}

class TLASAnalyzerV4:
    def __init__(
        self,
        data_dir: str,
        model_name: str = "chatgpt-web",
        api_base: str = "http://127.0.0.1:8765/v1",
        max_batch_chars: int = 24000,
        max_scenes_per_batch: int = 10
    ):
        self.data_dir = data_dir
        self.scenes_path = os.path.join(data_dir, "rpgm_scenes_v5.json")
        self.extractions_dir = os.path.join(data_dir, "extractions_v4")
        self.max_batch_chars = max_batch_chars
        self.max_scenes_per_batch = max_scenes_per_batch
        os.makedirs(self.extractions_dir, exist_ok=True)
        
        self.agent = TLASAnalyzerAgentV4(model_name=model_name, api_base=api_base)
        
        # Integrate Non-Hardcoded Universal Consensus Engine for Canonical Resolution & Whitelisting
        self.consensus = TLASConsensusEngine(data_dir=self.data_dir)
        self.whitelist: Set[str] = set(self.consensus.target_whitelist)
        self.alias_to_canonical: Dict[str, str] = dict(self.consensus.alias_to_canonical)
        logger.info(f"Loaded {len(self.whitelist)} canonical whitelist target characters via ConsensusEngine (Zero-Hardcoding Master Glossary).")

    def get_canonical_name(self, name: str) -> str:
        """Resolves raw speaker names, acoustic cues, aliases, or RPG Maker codes to canonical names."""
        if not name:
            return ""
        return self.consensus.get_canonical_name(name)

    def parse_scene_dialogues(self, text: str) -> list:
        """Parses [Speaker:] speech pairs from scene text."""
        parts = re.split(r'\[([^:\]\n]+):?\]', text)
        dialogues = []
        for j in range(1, len(parts), 2):
            spk = parts[j].strip()
            speech = parts[j+1].strip() if j+1 < len(parts) else ""
            if spk and not spk.isdigit():
                dialogues.append({"speaker": spk, "speech": speech})
        return dialogues

    def get_scene_targets(self, dialogues: list) -> Set[str]:
        """
        Identifies which target characters (whitelist) are present in the scene.
        Strictly filters out ambient mobs (e.g. Customer, Passerby, Police A), generic counters, and disposable symbols.
        Example: Customer + Dan + Shion -> returns ONLY {Dan, Shion}.
        """
        targets = set()
        for d in dialogues:
            raw_spk = d.get("speaker", "")
            canon = self.get_canonical_name(raw_spk)
            if is_invalid_or_disposable_speaker(canon):
                continue
            if canon in self.whitelist:
                targets.add(canon)
        return targets

    def format_scene_block(self, scene_data: dict, dialogues: list, targets: Set[str], max_lines: int = 80) -> Tuple[str, int]:
        """Formats a single scene block for packed batch prompt (Optimized for 16k context)."""
        source = scene_data.get("source", "Unknown_Scene")
        map_id = scene_data.get("map_id", "null")
        event_id = scene_data.get("event_id", "null")
        targets_str = ", ".join(sorted(targets))

        header = f"=== SCENE: {source} (Map: {map_id}, Event: {event_id}) | Target Characters: [{targets_str}] ==="
        lines = [header]

        for idx, d in enumerate(dialogues[:max_lines]):
            raw_spk = d.get("speaker", "")
            canon_spk = self.get_canonical_name(raw_spk)
            # Clearly designate ambient non-targets so the LLM does not profile them
            display_spk = canon_spk if canon_spk in targets else f"{canon_spk} (Ambient/NPC)"
            txt = clean_dialogue_text(d.get("speech", ""))
            if txt:
                lines.append(f"[{idx}] {display_spk}: {txt}")

        block_str = "\n".join(lines)
        return block_str, len(block_str)

    def write_scene_checkpoint(self, source: str, result_dict: dict):
        """Atomically saves a single scene extraction checkpoint."""
        safe_id = get_safe_id(source)
        out_path = os.path.join(self.extractions_dir, f"{safe_id}.json")
        tmp_out = out_path + ".tmp"
        with open(tmp_out, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        os.replace(tmp_out, out_path)

    async def analyze_packed_batch(self, batch_items: List[dict]) -> bool:
        """
        Sends a packed batch of scenes to the LLM and writes individual checkpoints.
        Implements Adaptive Binary Reduce if the batch fails.
        """
        if not batch_items:
            return True

        # Build combined user prompt with strict non-target exclusion instructions
        prompt_lines = [
            "### BATCH ANALYSIS INSTRUCTION:",
            "Analyze the following distinct scenes. Each scene begins with '=== SCENE: <scene_id> ==='.",
            "CRITICAL RULES:",
            "1. Extract delta traits and relationships ONLY for the specified Target Characters of each scene.",
            "2. DO NOT create character objects for ambient NPCs, customers, bystanders, or background characters (marked Ambient/NPC).",
            "3. Any character not explicitly listed in 'Target Characters: [...]' for that scene MUST be completely ignored.",
            "4. Output the result in the 'scenes' array with exact matching 'scene_id'.\n"
        ]

        target_map = {}
        for item in batch_items:
            prompt_lines.append(item["block_str"])
            prompt_lines.append("") # Empty line separator
            target_map[item["source"]] = item["targets"]

        user_prompt = "\n".join(prompt_lines)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                raw_resp = await self.agent.call_llm(
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    require_json=True,
                    skip_safety_rule=True
                )

                cleaned_json = repair_json(raw_resp)
                parsed = json.loads(cleaned_json)

                # Handle case where LLM returned dictionary directly or scenes list
                scenes_result = parsed.get("scenes", [])
                if not scenes_result and isinstance(parsed, list):
                    scenes_result = parsed
                elif not scenes_result and "scene_id" in parsed:
                    scenes_result = [parsed]

                # Map extracted results back to individual scene checkpoints
                results_by_id = {}
                for sc_res in scenes_result:
                    sid = sc_res.get("scene_id", "")
                    if sid:
                        results_by_id[sid] = sc_res

                # Save checkpoints for all scenes in this batch with Strict Extraction Guard
                saved_count = 0
                for item in batch_items:
                    sid = item["source"]
                    allowed_targets = item["targets"]  # Set[str]
                    res = results_by_id.get(sid)
                    if not res:
                        # Fallback for missing scene in LLM response
                        res = {
                            "scene_id": sid,
                            "characters": [],
                            "scene_context": "Analyzed in batch (no specific traits)",
                            "dialogue_metadata": []
                        }
                    else:
                        # STRICT EXTRACTION GUARD: Strip any ambient or unrequested characters
                        raw_chars = res.get("characters", [])
                        filtered_chars = []
                        for c in raw_chars:
                            c_name = c.get("character_name", "")
                            canon_c = self.get_canonical_name(c_name)
                            if canon_c in allowed_targets:
                                c["character_name"] = canon_c
                                # Sanitize relationships in delta to prevent ambient pollution
                                delta = c.get("delta", {})
                                rels = delta.get("relationships", [])
                                filtered_rels = []
                                for r in rels:
                                    rt = r.get("target_name", "")
                                    canon_rt = self.get_canonical_name(rt)
                                    if canon_rt in self.whitelist and not is_invalid_or_disposable_speaker(canon_rt):
                                        r["target_name"] = canon_rt
                                        r["target_character_id"] = f"CHAR_{canon_rt.upper()}"
                                        filtered_rels.append(r)
                                delta["relationships"] = filtered_rels
                                filtered_chars.append(c)
                            else:
                                logger.info(f"[EXTRACTION GUARD] Filtered out ambient/unrequested character '{c_name}' from scene '{sid}'.")
                        res["characters"] = filtered_chars

                    res["scene_id"] = sid
                    res["targets_analyzed"] = sorted(list(allowed_targets))
                    self.write_scene_checkpoint(sid, res)
                    saved_count += 1

                logger.info(f"[SUCCESS] Packed Batch of {len(batch_items)} scenes saved successfully ({saved_count} checkpoints written).")
                return True

            except Exception as e:
                logger.warning(f"[BATCH ATTEMPT {attempt+1}/{max_retries} FAILED]: {e}")
                await asyncio.sleep(2 * (attempt + 1))

        # Adaptive Resilience: Binary Reduce Fallback
        if len(batch_items) > 1:
            mid = len(batch_items) // 2
            logger.info(f"[ADAPTIVE REDUCE] Splitting batch of {len(batch_items)} scenes into [{mid}] and [{len(batch_items)-mid}]...")
            ok1 = await self.analyze_packed_batch(batch_items[:mid])
            ok2 = await self.analyze_packed_batch(batch_items[mid:])
            return ok1 and ok2
        else:
            # Single scene failed after retries
            sid = batch_items[0]["source"]
            logger.error(f"[FAILED] Scene {sid} completely failed after retries.")
            return False

    async def run_all(self):
        """Processes all scenes with Smart Scene Packing and Checkpointing."""
        if not os.path.exists(self.scenes_path):
            logger.error(f"Scenes file not found: {self.scenes_path}")
            return

        with open(self.scenes_path, "r", encoding="utf-8") as f:
            scenes = json.load(f)

        logger.info(f"Starting TLAS v4.0 Smart Scene Packing: Loaded {len(scenes)} total scenes from {self.scenes_path}")

        # Step 1: Pre-filter and identify scenes to process
        scenes_to_pack = []
        fast_skip_count = 0
        already_done_count = 0

        for sc in scenes:
            source = sc.get("source", "")
            safe_id = get_safe_id(source)
            out_path = os.path.join(self.extractions_dir, f"{safe_id}.json")

            if os.path.exists(out_path):
                already_done_count += 1
                continue

            dialogues = self.parse_scene_dialogues(sc.get("text", ""))
            if not dialogues:
                # Fast skip empty dialogues
                self.write_scene_checkpoint(source, {"scene_id": source, "characters": [], "scene_context": "No speech", "dialogue_metadata": []})
                fast_skip_count += 1
                continue

            targets = self.get_scene_targets(dialogues)
            if not targets:
                # Fast skip ambient-only scenes (0 Tokens)
                self.write_scene_checkpoint(source, {"scene_id": source, "characters": [], "scene_context": "Ambient scene without target characters", "dialogue_metadata": []})
                fast_skip_count += 1
                continue

            # This scene contains target characters
            block_str, block_len = self.format_scene_block(sc, dialogues, targets)
            scenes_to_pack.append({
                "source": source,
                "targets": targets,
                "block_str": block_str,
                "block_len": block_len
            })

        logger.info(f"Pre-filter Summary: {already_done_count} already completed, {fast_skip_count} fast-skipped (0 tokens).")
        logger.info(f"Target Scenes to analyze with LLM: {len(scenes_to_pack)} scenes.")

        if not scenes_to_pack:
            logger.info("[FINISH] All scenes are already processed or skipped!")
            return

        # Step 2: Pack scenes into batches preserving scene boundaries
        batches = []
        current_batch = []
        current_chars = 0

        for item in scenes_to_pack:
            # If adding this scene exceeds max_batch_chars or max_scenes_per_batch and batch is not empty, start a new batch
            is_char_overflow = (current_chars + item["block_len"] > self.max_batch_chars)
            is_count_overflow = (len(current_batch) >= self.max_scenes_per_batch)
            if (is_char_overflow or is_count_overflow) and len(current_batch) > 0:
                batches.append(current_batch)
                current_batch = [item]
                current_chars = item["block_len"]
            else:
                current_batch.append(item)
                current_chars += item["block_len"]

        if current_batch:
            batches.append(current_batch)

        logger.info(f"Smart Scene Packing complete: {len(scenes_to_pack)} scenes packed into {len(batches)} batches (Limit: {self.max_batch_chars} chars/batch).")

        # Step 3: Process batches
        success_batches = 0
        for b_idx, batch in enumerate(batches):
            logger.info(f"Processing Batch {b_idx+1}/{len(batches)} ({len(batch)} scenes)...")
            ok = await self.analyze_packed_batch(batch)
            if ok:
                success_batches += 1

            if (b_idx + 1) % 10 == 0 or (b_idx + 1) == len(batches):
                logger.info(f"Batch Progress: {b_idx+1}/{len(batches)} batches completed ({success_batches} succeeded).")

        logger.info(f"[FINISH] Analyzer V4 Finished! {success_batches}/{len(batches)} batches processed successfully.")

if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    manifest_path = os.path.join(project_root, "data", "project_manifest.json")
    
    tlas_data = os.path.join(project_root, "data", "tlas")
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        tlas_data = sys.argv[1]
    elif os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
            tlas_data = mdata.get("output_tlas_dir", tlas_data)
        except Exception:
            pass

    logger.info(f"Target TLAS Data Directory: {tlas_data}")
    analyzer = TLASAnalyzerV4(data_dir=tlas_data)
    asyncio.run(analyzer.run_all())
