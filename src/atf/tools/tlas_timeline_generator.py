import os
import sys
import json
import asyncio
import glob
from collections import defaultdict
import tiktoken
import re

def count_tokens(text: str) -> int:
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from src.atf.agents.base import BaseAgent

class TLASTimelineAgent(BaseAgent):
    def __init__(self, model_name: str = "gemma-4-12b-it-qat"):
        super().__init__(model_name=model_name, agent_name="TLAS_Timeline")
        self.system_prompt = (
            "You are an expert narrative analyst. Your job is to analyze dialogues "
            "and provide comprehensive chronological summaries of the story events."
        )

    async def process(self, batch) -> bool:
        pass

    async def map_chunk(self, chunk_data: list) -> str:
        """Step 1: Extract exhaustive 5W1H lore from a chunk of scene objects."""
        # We pass the raw JSON stringified array to LLM (without indent to save tokens)
        chunk_text = json.dumps(chunk_data, ensure_ascii=False)
        
        user_prompt = (
            "Analyze the following array of dialogue scene objects:\n\n"
            f"{chunk_text}\n\n"
            "Provide a highly detailed summary of the events in this chunk. "
            "You MUST answer ALL of the following questions (5W1H) comprehensively:\n"
            "1. Who is involved?\n"
            "2. What did they do or say?\n"
            "3. With whom did they interact?\n"
            "4. Why did they do it (intent/motivation)?\n"
            "5. Where did it happen?\n"
            "6. When did it happen?\n"
            "7. How did it happen?\n"
            "8. What was the outcome or result?\n"
            "9. Who else is involved or mentioned?\n\n"
            "Do NOT invent details. Focus purely on extracting facts from the provided text."
        )
        try:
            return await self.call_llm(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                require_json=False,
                skip_safety_rule=False,
                max_tokens=3000
            )
        except Exception as e:
            print(f"Error mapping chunk: {e}")
            return ""

    async def reduce_phase(self, phase_name: str, phase_summaries: str) -> str:
        """Step 2: Consolidate all mini-summaries of a phase into a final summary."""
        user_prompt = (
            f"You are writing the official Chronological Story Summary for: {phase_name}\n\n"
            f"Below are the detailed summaries extracted from the game. Each summary is tagged with its CHUNK METADATA (Categories, Timeline Phases, and Conditions).\n\n"
            f"{phase_summaries}\n\n"
            "This game features complex branching narratives (Routes) based on player choices and variables. "
            "Your task is to combine these summaries into a cohesive, chronological Narrative State Machine (Flowchart-style narrative).\n\n"
            "STRICT RULES:\n"
            "1. Sort events chronologically strictly based on the [Timeline Phases] numbers (lowest to highest = oldest to newest in the lore).\n"
            "2. Group events that share the same [Conditions] and [Categories] into specific 'Routes' (e.g. 'Main Story Route', 'Branch: If Msauna21 == ON').\n"
            "3. If a specific Route contains a Flashback (e.g. it has a Timeline Phase of 5, while Present Day is 50), place that flashback chronologically AT THE BEGINNING of that specific Route's timeline. Do not mix it with the linear timeline of other routes.\n"
            "4. If events have mutually exclusive conditions or describe contradictory outcomes, DO NOT merge them! Explicitly document them as divergent branches.\n"
            "5. If branches converge back into a shared event later, state that clearly.\n"
            "6. Keep all important facts (who did what, to whom, why, outcomes).\n"
            "Produce a structured, flowchart-like narrative summary."
        )
        try:
            return await self.call_llm(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                require_json=False,
                skip_safety_rule=False,
                max_tokens=3000
            )
        except Exception as e:
            print(f"Error reducing phase {phase_name}: {e}")
            return "No summary available."

async def map_chunk_with_retry(agent, chunk_name, chunk_data, max_retries=3, current_depth=0):
    summary = await agent.map_chunk(chunk_data)
    if summary:
        return summary
        
    print(f"  -> [AUTO-REPAIR] map_chunk failed at depth {current_depth} for {chunk_name}. Splitting chunk into sub-batches...")
    if len(chunk_data) > 1:
        mid = len(chunk_data) // 2
        left = chunk_data[:mid]
        right = chunk_data[mid:]
        sum_left = await map_chunk_with_retry(agent, chunk_name + "_L", left, max_retries, current_depth + 1)
        sum_right = await map_chunk_with_retry(agent, chunk_name + "_R", right, max_retries, current_depth + 1)
        return sum_left + "\n\n" + sum_right
    else:
        # Only 1 scene left, try to split its dialogues if possible
        scene = chunk_data[0]
        dialogues = scene.get("dialogues", [])
        if len(dialogues) > 1:
            mid = len(dialogues) // 2
            s_left = scene.copy()
            s_left["dialogues"] = dialogues[:mid]
            s_right = scene.copy()
            s_right["dialogues"] = dialogues[mid:]
            sum_left = await map_chunk_with_retry(agent, chunk_name + "_L", [s_left], max_retries, current_depth + 1)
            sum_right = await map_chunk_with_retry(agent, chunk_name + "_R", [s_right], max_retries, current_depth + 1)
            return sum_left + "\n\n" + sum_right
        else:
            if dialogues and "text" in dialogues[0]:
                lines = dialogues[0]["text"].split("\n")
                if len(lines) > 1:
                    mid = len(lines) // 2
                    s_left = scene.copy()
                    s_left["dialogues"] = [{"speaker": dialogues[0].get("speaker", ""), "text": "\n".join(lines[:mid])}]
                    s_right = scene.copy()
                    s_right["dialogues"] = [{"speaker": dialogues[0].get("speaker", ""), "text": "\n".join(lines[mid:])}]
                    sum_left = await map_chunk_with_retry(agent, chunk_name + "_L", [s_left], max_retries, current_depth + 1)
                    sum_right = await map_chunk_with_retry(agent, chunk_name + "_R", [s_right], max_retries, current_depth + 1)
                    return sum_left + "\n\n" + sum_right
            print(f"  -> [CRITICAL ERROR] Cannot split scene further. Aborting.")
            raise Exception("Cannot auto-repair: single dialogue line is too large or API is persistently failing. No skips allowed!")

async def run_timeline_generation(data_dir: str):
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    agent = TLASTimelineAgent()
    scenes_path = os.path.join(data_dir, "rpgm_scenes_all_routes.json")
    timeline_out_path = os.path.join(data_dir, "story_timeline_v2.json")
    chunks_dir = os.path.join(data_dir, "timeline_chunks_v2")
    os.makedirs(chunks_dir, exist_ok=True)
    
    print(f"Loading dynamic route tracing scenes from {scenes_path}...")
    with open(scenes_path, "r", encoding="utf-8") as f:
        raw_scenes = json.load(f)
        
    # Group by route and sort by timeline_phase
    clusters = {}
    for scene in raw_scenes:
        r = scene.get("route", "Main")
        if r not in clusters:
            clusters[r] = {"cluster_id": f"Route_Cluster_{r}", "scenes": []}
            
        # Parse dialogues from text
        text = scene.get("text", "")
        dialogues = []
        parts = re.split(r'(?:\\\\n|\\n)?<([^>]+):>', text)
        if parts[0].strip():
            dialogues.append({"speaker": "", "text": parts[0].strip()})
        for j in range(1, len(parts), 2):
            speaker = parts[j].strip()
            speech = parts[j+1].strip() if j+1 < len(parts) else ""
            dialogues.append({"speaker": speaker, "text": speech})
            
        new_scene = {
            "id": f"{scene.get('event_name', 'Unknown')}_{scene.get('timeline_phase') or 0}",
            "location": f"Map {scene.get('map_id')} - Event {scene.get('event_id')}",
            "timeline_phase": scene.get("timeline_phase") or 0,
            "dialogues": dialogues
        }
        clusters[r]["scenes"].append(new_scene)
        
    clusters_list = list(clusters.values())
    for cluster in clusters_list:
        # Sort scenes by timeline_phase strictly
        cluster["scenes"].sort(key=lambda x: x["timeline_phase"] or 0)
        
    # --- MAP (CHUNK SUMMARIZATION) ---
    MAX_PROMPT_TOKENS = int(os.environ.get("MAX_PROMPT_TOKENS", 5000))
    
    print(f"Total Routes: {len(clusters_list)}")
    chunk_counter = 0
    
    for cluster in clusters_list:
        cluster_id = cluster.get("cluster_id", "Unknown_Cluster")
        cluster_scenes = cluster.get("scenes", [])
        
        # Adaptive Token Packing
        phase_chunks = []
        current_chunk = []
        current_tokens = 0
        
        for scene in cluster_scenes:
            scene_text = json.dumps(scene, ensure_ascii=False)
            scene_tokens = count_tokens(scene_text)

            # If a SINGLE scene is larger than MAX_PROMPT_TOKENS, we MUST split its dialogues
            if scene_tokens > MAX_PROMPT_TOKENS:
                dialogues = scene.get("dialogues", [])
                sub_scene = scene.copy()
                sub_scene["dialogues"] = []
                sub_tokens = count_tokens(json.dumps(sub_scene, ensure_ascii=False))

                for d in dialogues:
                    d_tokens = count_tokens(json.dumps(d, ensure_ascii=False))
                    if sub_tokens + d_tokens > MAX_PROMPT_TOKENS:
                        # Flush current sub_scene
                        if current_tokens + sub_tokens > MAX_PROMPT_TOKENS and current_chunk:
                            phase_chunks.append(current_chunk)
                            current_chunk = []
                            current_tokens = 0
                        current_chunk.append(sub_scene)
                        current_tokens += sub_tokens
                        # Start new sub_scene
                        sub_scene = scene.copy()
                        sub_scene["dialogues"] = [d]
                        sub_tokens = count_tokens(json.dumps(sub_scene, ensure_ascii=False)) + d_tokens
                    else:
                        sub_scene["dialogues"].append(d)
                        sub_tokens += d_tokens
                
                # Flush the last sub_scene
                if sub_scene["dialogues"]:
                    if current_tokens + sub_tokens > MAX_PROMPT_TOKENS and current_chunk:
                        phase_chunks.append(current_chunk)
                        current_chunk = []
                        current_tokens = 0
                    current_chunk.append(sub_scene)
                    current_tokens += sub_tokens
                continue

            if current_tokens + scene_tokens > MAX_PROMPT_TOKENS and current_chunk:
                phase_chunks.append(current_chunk)
                current_chunk = [scene]
                current_tokens = scene_tokens
            else:
                current_chunk.append(scene)
                current_tokens += scene_tokens
                
        if current_chunk:
            phase_chunks.append(current_chunk)
            
        print(f"{cluster_id} divided into {len(phase_chunks)} chunks (Adaptive Packing).")
        
        for i, chunk in enumerate(phase_chunks):
            chunk_name = f"chunk_{cluster_id}_{i:04d}"
            chunk_file = os.path.join(chunks_dir, f"{chunk_name}.json")
            chunk_counter += 1
            
            # Checkpoint Skip: only skip if chunk already exists and has a non-empty summary
            if os.path.exists(chunk_file):
                try:
                    with open(chunk_file, "r", encoding="utf-8") as existing_f:
                        existing_data = json.load(existing_f)
                        if existing_data.get("summary"):
                            print(f"  -> [SKIP] {chunk_name} already exists.")
                            continue
                except Exception:
                    pass
                
            print(f"Mapping {chunk_name}...")
            
            # Filter empty dialogues
            valid_chunk_data = []
            for s in chunk:
                if s.get("dialogues"):
                    valid_chunk_data.append(s)
            
            if not valid_chunk_data:
                with open(chunk_file, "w", encoding="utf-8") as f:
                    json.dump({"id": chunk_name, "cluster_id": cluster_id, "summary": "", "raw_scenes": chunk}, f, ensure_ascii=False, indent=2)
                continue
                
            summary = await map_chunk_with_retry(agent, chunk_name, valid_chunk_data)
            
            with open(chunk_file, "w", encoding="utf-8") as f:
                json.dump({
                    "id": chunk_name,
                    "cluster_id": cluster_id,
                    "summary": summary,
                    "raw_scenes": chunk  # Store full array for RAG context
                }, f, ensure_ascii=False, indent=2)
                
            print(f"  -> Saved {chunk_name}.json")
            
            # Early break for mock testing
            if chunk_counter >= 2 and os.environ.get("DRY_RUN") == "1":
                print("Stopping early for dry run...")
                break
        if chunk_counter >= 2 and os.environ.get("DRY_RUN") == "1":
            break

    # --- REDUCE (CHRONOLOGICAL AGGREGATION) ---
    print("\nStarting Reduce Phase...")
    
    cluster_data = defaultdict(lambda: {"name": "", "summaries": []})
    
    chunk_files = sorted(glob.glob(os.path.join(chunks_dir, "chunk_*.json")))
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        cid = data.get("cluster_id")
        if not cid: continue
        
        cluster_data[cid]["name"] = cid
        if data.get("summary"):
            cluster_data[cid]["summaries"].append(data["summary"])
                
    # Per-cluster reduce checkpoint directory
    reduce_cp_dir = os.path.join(data_dir, "reduce_checkpoints_v2")
    os.makedirs(reduce_cp_dir, exist_ok=True)
    
    # Load existing story_timeline if any, to accumulate
    story_timeline = {}
    if os.path.exists(timeline_out_path):
        try:
            with open(timeline_out_path, "r", encoding="utf-8") as f:
                story_timeline = json.load(f)
        except Exception:
            story_timeline = {}
    
    for cid in sorted(cluster_data.keys()):
        p_info = cluster_data[cid]
        if not p_info["summaries"]:
            continue
        
        cluster_cp_path = os.path.join(reduce_cp_dir, f"{cid}_final.json")
        
        if os.path.exists(cluster_cp_path):
            try:
                with open(cluster_cp_path, "r", encoding="utf-8") as f:
                    cached_result = json.load(f)
                story_timeline[cid] = cached_result
                print(f"  -> [SKIP] {cid} reduce checkpoint found — loaded from disk.")
                continue
            except Exception:
                pass  # Corrupted checkpoint — re-process
            
        print(f"Reducing {p_info['name']}...")
        
        combined_text = "\n\n".join(p_info["summaries"][:50])  # limit to 50 mini-summaries for context limit
        final_summary = await agent.reduce_phase(p_info["name"], combined_text)
        
        result = {
            "name": p_info["name"],
            "summary": final_summary
        }
        
        tmp_cp = cluster_cp_path + ".tmp"
        with open(tmp_cp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        os.replace(tmp_cp, cluster_cp_path)
        print(f"  -> [CHECKPOINT] {cid} saved to {os.path.basename(cluster_cp_path)}")
        
        story_timeline[cid] = result
        
        tmp_tl = timeline_out_path + ".tmp"
        with open(tmp_tl, "w", encoding="utf-8") as f:
            json.dump(story_timeline, f, indent=2, ensure_ascii=False)
        os.replace(tmp_tl, timeline_out_path)
        
    print(f"\nTimeline Map-Reduce complete. Saved to {timeline_out_path}")

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\data\tlas"
    asyncio.run(run_timeline_generation(tlas_dir))
