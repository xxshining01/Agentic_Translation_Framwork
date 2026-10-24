"""
tlas_character_timeline_enricher.py
===================================
Targeted Character Timeline Enrichment Engine (Post-Processing Phase).
Scans all story chunks to identify Speaker, Listener, and Mentioned occurrences
for each canonical character, groups them chronologically into batches,
and uses LLM to generate comprehensive timeline_states (deltas) for Character Profiles.
"""

import os
import sys
import re
import json
import glob
import asyncio
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.atf.agents.base import BaseAgent
from src.atf.tools.tlas_rule_engine import PriorityRuleEngine
from src.atf.tools.cleanup_junk_profiles import is_garbage_or_disposable

def count_tokens(text: str) -> int:
    return max(1, len(text) // 4)

MAX_PROMPT_TOKENS = 6000

def repair_json(raw: str) -> str:
    """Extract and repair JSON array or object from LLM response."""
    text = raw.strip()
    # Strip markdown code blocks
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    
    # Try finding outer [ ... ] or { ... }
    arr_start = text.find("[")
    arr_end = text.rfind("]")
    obj_start = text.find("{")
    obj_end = text.rfind("}")

    if arr_start != -1 and arr_end != -1 and (obj_start == -1 or arr_start < obj_start):
        candidate = text[arr_start:arr_end + 1]
    elif obj_start != -1 and obj_end != -1:
        candidate = text[obj_start:obj_end + 1]
    else:
        candidate = text

    candidate = re.sub(r",\s*([\]\}])", r"\1", candidate)
    return candidate

class CharacterTimelineAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-4-12b-it-qat"):
        super().__init__(model_name=model_name, agent_name="TLAS_Timeline_Enricher")
        self.system_prompt = (
            "You are an expert narrative psychologist and character arc analyst.\n"
            "Your task is to analyze chronological story events and extract timeline milestone states "
            "and psychological/relationship shifts (deltas) for a specific target character."
        )

    async def process(self, batch) -> bool:
        pass

    async def analyze_character_timeline_batch(
        self,
        character_name: str,
        character_profile: dict,
        chunk_batch: List[dict],
        allowed_taxonomy: dict
    ) -> List[dict]:
        """Analyze a chronological batch of chunks where the character participates/is mentioned."""
        # Summarize chunks for prompt
        events_context = []
        for idx, item in enumerate(chunk_batch):
            chunk_id = item.get("chunk_id", f"chunk_{idx}")
            tl_phase = item.get("timeline_phase", 0)
            summary = item.get("summary", "")
            dialogues = item.get("dialogues", [])
            
            # Format dialogues snippet
            dial_snippets = []
            for d in dialogues[:20]: # Allow more dialogues since we pre-filtered to just the character
                spk = d.get("speaker", "Unknown")
                txt = d.get("text", "")
                if txt.strip():
                    dial_snippets.append(f"[{spk}]: {txt.strip()}")
            dial_str = "\n".join(dial_snippets)
            
            events_context.append(
                f"### EVENT {idx+1}: [Chunk: {chunk_id} | Timeline Phase: {tl_phase}]\n"
                f"Story Summary:\n{summary}\n"
                f"Key Dialogues spoken by {character_name}:\n{dial_str}\n"
            )
            
        events_text = "\n".join(events_context)
        
        # Base state info
        base_state = character_profile.get("base_state", {})
        per_tags = [t.get("tag", "") for t in base_state.get("personality", [])]
        val_tags = [t.get("tag", "") for t in base_state.get("values", [])]
        rel_list = [f"{r.get('target_name', '')} ({r.get('affinity', '')}, {r.get('power_dynamic', '')})" for r in base_state.get("relationships", [])]
        
        user_prompt = (
            f"TARGET CHARACTER: {character_name}\n"
            f"Base Personality: {', '.join(per_tags) if per_tags else 'Not specified'}\n"
            f"Base Values: {', '.join(val_tags) if val_tags else 'Not specified'}\n"
            f"Initial Relationships: {', '.join(rel_list) if rel_list else 'None known'}\n\n"
            "Below are chronological story events where this character is active, listening, or mentioned:\n\n"
            f"{events_text}\n\n"
            f"Extract chronological timeline milestone states for '{character_name}' across these events.\n"
            "For each distinct event that significantly impacts the character, output a JSON object in an array:\n"
            "[\n"
            "  {\n"
            '    "state_id": "STATE_<timeline_phase>_<chunk_id>",\n'
            '    "trigger_event_id": "<chunk_id>",\n'
            '    "timeline_phase": <integer>,\n'
            '    "description": "<Detailed explanation of the event, what happened to the character, and emotional/psychological impact>",\n'
            '    "delta": {\n'
            '      "personality": [{"tag": "<PER_TAG>", "weight": <1-100>}],\n'
            '      "speech_habit": [{"tag": "<SPR_TAG>", "weight": <1-100>}],\n'
            '      "values": [{"tag": "<VAL_TAG>", "weight": <1-100>}],\n'
            '      "relationships": [\n'
            '        {\n'
            '          "target_character_id": "CHAR_<TARGET>",\n'
            '          "target_name": "<Target Character Name>",\n'
            '          "roles": ["<ROLE_TAG>"],\n'
            '          "affinity": "<AFF_TAG>",\n'
            '          "intimacy": "<INT_TAG>",\n'
            '          "power_dynamic": "<DYN_TAG>"\n'
            '        }\n'
            '      ]\n'
            '    }\n'
            "  }\n"
            "]\n\n"
            "STRICT RULES:\n"
            "1. ONLY use valid taxonomy tags from this list:\n"
            f"   personality: {', '.join(allowed_taxonomy.get('per_tags', []))}\n"
            f"   speech_habit: {', '.join(allowed_taxonomy.get('spr_tags', []))}\n"
            f"   values: {', '.join(allowed_taxonomy.get('val_tags', []))}\n"
            f"   roles: {', '.join(allowed_taxonomy.get('role_tags', []))}\n"
            f"   affinity: {', '.join(allowed_taxonomy.get('aff_tags', []))}\n"
            f"   intimacy: {', '.join(allowed_taxonomy.get('int_tags', []))}\n"
            f"   power_dynamic: {', '.join(allowed_taxonomy.get('dyn_tags', []))}\n"
            "2. If an event causes no state/relationship changes, you may leave delta arrays empty [] but provide an accurate description.\n"
            "3. If no significant events occur for this character in these chunks, return an empty array: []\n"
            "Return ONLY the JSON array."
        )

        for attempt in range(3):
            try:
                response = await self.call_llm(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
                    require_json=False,
                    skip_safety_rule=False
                )
                if response and response.strip():
                    repaired = repair_json(response)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict) and "timeline_states" in parsed:
                        return parsed["timeline_states"]
                    elif isinstance(parsed, dict) and parsed:
                        return [parsed]
            except Exception as e:
                print(f"      [TimelineAgent] Attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2)
                
        return []

def load_taxonomy(taxonomy_path: str) -> dict:
    if not os.path.exists(taxonomy_path):
        return {}
    with open(taxonomy_path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    tags = tax.get("tags", {})
    return {
        "role_tags": [k for k in tags if k.startswith("ROLE_")],
        "aff_tags":  [k for k in tags if k.startswith("AFF_")],
        "int_tags":  ["INT_CONFIDANT", "INT_FAMILIAR", "INT_DISTANT", "INT_ESTRANGED"],
        "dyn_tags":  [k for k in tags if k.startswith("DYN_")],
        "per_tags":  [k for k in tags if k.startswith("PER_")],
        "spr_tags":  [k for k in tags if k.startswith("SPR_")],
        "val_tags":  [k for k in tags if k.startswith("VAL_")],
    }

def get_chunk_sort_key(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_scenes = data.get("raw_scenes", [])
        tl_phase = raw_scenes[0].get("timeline_phase", 999) if raw_scenes else 999
        return (tl_phase, filepath)
    except Exception:
        return (999, filepath)

async def run_timeline_enrichment(data_dir: str):
    print("=" * 60)
    print("  TLAS Targeted Character Timeline Enrichment Pipeline (V2)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Project data dir
    project_data_dir = os.path.abspath(os.path.join(data_dir, "../../../data/tlas"))
    
    profiles_dir = os.path.join(project_data_dir, "profiles")
    chunks_dir = os.path.join(data_dir, "timeline_chunks_v2")
    taxonomy_path = os.path.join(project_data_dir, "taxonomy.json")
    checkpoints_dir = os.path.join(project_data_dir, "timeline_enricher_checkpoints_v2")
    os.makedirs(checkpoints_dir, exist_ok=True)
    
    taxonomy = load_taxonomy(taxonomy_path)
    rule_engine = PriorityRuleEngine(taxonomy_path)
    agent = CharacterTimelineAgent()
    
    # 1. Load All Valid Profiles
    profile_files = sorted(glob.glob(os.path.join(profiles_dir, "*.json")))
    print(f"\n[1] Found {len(profile_files)} character profiles in {profiles_dir}")
    
    profiles_data: Dict[str, dict] = {}
    char_aliases: Dict[str, Set[str]] = {}
    
    for pf in profile_files:
        cname = os.path.basename(pf).replace(".json", "")
        if is_garbage_or_disposable(cname):
            continue
        try:
            with open(pf, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            canon = pdata.get("name", cname).strip()
            profiles_data[canon] = pdata
            
            aliases = set(pdata.get("aliases", [canon]))
            aliases.add(canon)
            char_aliases[canon] = {a.strip().lower() for a in aliases if a.strip() and not is_garbage_or_disposable(a)}
        except Exception as e:
            print(f"[Error] Loading profile {pf}: {e}")

    print(f"    - Loaded {len(profiles_data)} valid canonical characters for timeline enrichment.")

    # 2. Load and Index All Story Chunks
    chunk_files = glob.glob(os.path.join(chunks_dir, "chunk_*.json"))
    chunk_files.sort(key=get_chunk_sort_key)
    print(f"\n[2] Loaded and sorted {len(chunk_files)} story chunks.")
    
    # Pre-parse chunks into memory for fast scanning
    parsed_chunks = []
    for cf in chunk_files:
        try:
            with open(cf, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            
            raw_scenes = cdata.get("raw_scenes", [])
            tl_phase = raw_scenes[0].get("timeline_phase", 0) if raw_scenes else 0
            
            # Extract all dialogues across all scenes
            all_dialogues = []
            for scene in raw_scenes:
                all_dialogues.extend(scene.get("dialogues", []))
                
            parsed_chunks.append({
                "filepath": cf,
                "chunk_id": cdata.get("id", os.path.basename(cf).replace(".json", "")),
                "timeline_phase": tl_phase,
                "summary": cdata.get("summary", ""),
                "raw_dialogues": all_dialogues
            })
        except Exception as e:
            print(f"[Warning] Failed to parse {cf}: {e}")

    # 3. Process Each Character
    print(f"\n[3] Starting Timeline Scanning & Enrichment...")
    
    for char_idx, (char_name, profile) in enumerate(profiles_data.items()):
        print(f"\n[{char_idx+1}/{len(profiles_data)}] Processing Character: {char_name}")
        cp_file = os.path.join(checkpoints_dir, f"{char_name}_cp.json")
        
        # TEST MODE: Process only Shion for now
        if char_name.lower() != "shion":
            print(f"  -> [TEST MODE SKIP] Skipping {char_name} for now.")
            continue
            
        # Check if already completed
        if os.path.exists(cp_file):
            try:
                with open(cp_file, "r", encoding="utf-8") as f:
                    cp_data = json.load(f)
                if cp_data.get("status") == "COMPLETED":
                    print(f"  -> [SKIP] Timeline enrichment already completed for {char_name}.")
                    continue
            except Exception:
                pass
                
        aliases_set = char_aliases.get(char_name, {char_name.lower()})
        matching_chunks = []
        
        # Test mode: Process only first 50 matched chunks
        for ch in parsed_chunks:
            if len(matching_chunks) >= 50:
                break
                
            is_involved = False
            summary_lower = ch["summary"].lower()
            
            # Check 1: Mentioned in summary
            for alias in aliases_set:
                if re.search(r'\b' + re.escape(alias) + r'\b', summary_lower):
                    is_involved = True
                    break
                    
            # Check 2: Speaker or Mentioned in Raw Dialogues
            matching_dialogues = []
            for d in ch["raw_dialogues"]:
                src = str(d.get("speaker", "")).strip().lower()
                txt = str(d.get("text", "")).strip()
                txt_lower = txt.lower()
                
                spk_match = any(alias == src or alias in src for alias in aliases_set)
                
                if spk_match:
                    is_involved = True
                    matching_dialogues.append(d) # Option B: Only include lines where target character speaks
                else:
                    txt_match = any(re.search(r'\b' + re.escape(alias) + r'\b', txt_lower) for alias in aliases_set)
                    if txt_match:
                        is_involved = True
                    
            if is_involved:
                matching_chunks.append({
                    "chunk_id": ch["chunk_id"],
                    "timeline_phase": ch["timeline_phase"],
                    "summary": ch["summary"],
                    "dialogues": matching_dialogues
                })

        print(f"  -> Found {len(matching_chunks)} relevant events across story for {char_name} (Testing First {len(matching_chunks)}).")
        
        if not matching_chunks:
            print(f"  -> No events found for {char_name}. Marking complete.")
            with open(cp_file, "w", encoding="utf-8") as f:
                json.dump({"status": "COMPLETED", "events_found": 0}, f, indent=2)
            continue

        # Adaptive Batching
        chunk_batches = []
        current_batch = []
        current_tokens = 0
        
        for mc in matching_chunks:
            chunk_str = json.dumps(mc, ensure_ascii=False)
            t_count = count_tokens(chunk_str)
            
            if current_tokens + t_count > MAX_PROMPT_TOKENS and current_batch:
                chunk_batches.append(current_batch)
                current_batch = [mc]
                current_tokens = t_count
            else:
                current_batch.append(mc)
                current_tokens += t_count
                
        if current_batch:
            chunk_batches.append(current_batch)
            
        print(f"  -> Divided into {len(chunk_batches)} chronological adaptive batches (Max {MAX_PROMPT_TOKENS} tokens/batch).")
        
        accumulated_states: List[dict] = profile.get("timeline_states", [])
        existing_state_ids = {s.get("state_id") for s in accumulated_states if s.get("state_id")}

        for b_idx, batch in enumerate(chunk_batches):
            print(f"     * Analyzing Batch {b_idx+1}/{len(chunk_batches)} ({len(batch)} events)...")
            
            raw_states = await agent.analyze_character_timeline_batch(
                character_name=char_name,
                character_profile=profile,
                chunk_batch=batch,
                allowed_taxonomy=taxonomy
            )
            
            for st in raw_states:
                if not isinstance(st, dict):
                    continue
                state_id = st.get("state_id", f"STATE_{st.get('timeline_phase', 0)}_{st.get('trigger_event_id', b_idx)}")
                if state_id not in existing_state_ids:
                    # Sanitize and validate delta
                    delta = st.get("delta", {})
                    st["state_id"] = state_id
                    st["delta"] = delta
                    accumulated_states.append(st)
                    existing_state_ids.add(state_id)
            
            print(f"       -> Extracted {len(raw_states)} timeline states from batch.")

        # Sort accumulated states chronologically by timeline_phase
        accumulated_states.sort(key=lambda s: (s.get("timeline_phase", 0), str(s.get("trigger_event_id", ""))))
        profile["timeline_states"] = accumulated_states
        
        # Save enriched profile (Atomic write)
        profile_path = os.path.join(profiles_dir, f"{char_name}.json")
        tmp_profile = profile_path + ".tmp"
        with open(tmp_profile, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        os.replace(tmp_profile, profile_path)
        print(f"  -> [SAVED] Enriched profile saved with {len(accumulated_states)} timeline states to {profile_path}")
        
        # Mark character completed in checkpoint
        with open(cp_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": "COMPLETED",
                "character": char_name,
                "total_timeline_states": len(accumulated_states),
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("  Character Timeline Enrichment Complete!")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\data\tlas"
    asyncio.run(run_timeline_enrichment(tlas_dir))
