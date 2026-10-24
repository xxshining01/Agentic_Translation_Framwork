import os
import sys
import json
import asyncio
import glob
from collections import defaultdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.atf.tools.tlas_timeline_generator import TLASTimelineAgent

def get_safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in name).strip()

# Enhanced Resilient Reduce based on tlas_chunk_repair.py logic
async def resilient_reduce(agent, phase_name, summaries, data_dir, batch_size=20):
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
        
    checkpoints_dir = os.path.join(data_dir, "reduce_checkpoints")
    os.makedirs(checkpoints_dir, exist_ok=True)
    
    current_summaries = summaries
    level = 1
    
    while len(current_summaries) > 1:
        print(f"    [Adaptive Reduce] Hierarchical Level {level} (Total: {len(current_summaries)} summaries)", flush=True)
        next_level = []
        
        level_cp_path = os.path.join(checkpoints_dir, f"{get_safe_filename(phase_name)}_L{level}.json")
        processed_batches = {}
        if os.path.exists(level_cp_path):
            try:
                with open(level_cp_path, "r", encoding="utf-8") as f:
                    processed_batches = json.load(f)
                    print(f"      -> Loaded checkpoint for Level {level} ({len(processed_batches)} batches done)", flush=True)
            except Exception as e:
                print(f"      -> Warning: Failed to load checkpoint: {e}", flush=True)
                processed_batches = {}
                
        for i in range(0, len(current_summaries), batch_size):
            batch_id = str(i // batch_size + 1)
            
            if batch_id in processed_batches:
                next_level.append(processed_batches[batch_id])
                continue
                
            batch = current_summaries[i:i+batch_size]
            
            if len(batch) == 1:
                next_level.append(batch[0])
                processed_batches[batch_id] = batch[0]
                with open(level_cp_path, "w", encoding="utf-8") as f:
                    json.dump(processed_batches, f, ensure_ascii=False)
                continue
                
            combined = "\n\n".join(batch)
            
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(combined))
            
            if token_count > 3000 and batch_size > 1:
                print(f"      -> [Pre-Filter] Batch {batch_id} is too large ({token_count} tokens). Proactively halving batch size...", flush=True)
                smaller_batch_res = await resilient_reduce(agent, phase_name, batch, data_dir, max(1, batch_size//2))
                next_level.append(smaller_batch_res)
                processed_batches[batch_id] = smaller_batch_res
                with open(level_cp_path, "w", encoding="utf-8") as f:
                    json.dump(processed_batches, f, ensure_ascii=False)
                continue
            
            print(f"      -> Reducing batch {batch_id}/{(len(current_summaries) + batch_size - 1)//batch_size}...", flush=True)
            res = await agent.reduce_phase(f"{phase_name} L{level} B{batch_id}", combined)
            
            if not res or res == "No summary available.":
                if batch_size > 1:
                    print("      -> [Adaptive Reduce] Batch reduction failed. Halving batch size and retrying...", flush=True)
                    smaller_batch_res = await resilient_reduce(agent, phase_name, batch, data_dir, max(1, batch_size//2))
                    next_level.append(smaller_batch_res)
                    processed_batches[batch_id] = smaller_batch_res
                else:
                    print("      -> [Adaptive Reduce] Reduction failed completely for this part. Falling back to concatenation.", flush=True)
                    next_level.append(combined)
                    processed_batches[batch_id] = combined
            else:
                next_level.append(res)
                processed_batches[batch_id] = res
                
            with open(level_cp_path, "w", encoding="utf-8") as f:
                json.dump(processed_batches, f, ensure_ascii=False)
                
        if len(next_level) >= len(current_summaries):
            print("    [Adaptive Reduce] No reduction progress could be made. Aborting hierarchical reduce.", flush=True)
            return "\n\n".join(next_level)
            
        current_summaries = next_level
        level += 1
        
    return current_summaries[0]

async def run_reduce_phase(data_dir: str):
    print("Starting Macro-Timeline Reduction Phase...", flush=True)
    agent = TLASTimelineAgent(model_name="local-model")
    chunks_dir = os.path.join(data_dir, "timeline_chunks")
    timeline_out_path = os.path.join(data_dir, "story_timeline.json")
    
    chunk_files = sorted(glob.glob(os.path.join(chunks_dir, "chunk_*.json")))
    
    phase_data = {
        0: {"name": "Phase 0: The Prologue (Opening Flow & Setup)", "summaries": []},
        1: {"name": "Phase 1: The Past (Flashbacks & History)", "summaries": []},
        2: {"name": "Phase 2: The Present (Main Storyline & Arcs)", "summaries": []},
        3: {"name": "Phase 3: Supplemental & Bonus Content", "summaries": []}
    }
    
    missing_chunks = 0
    valid_chunks_count = 0
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        phase = data.get("story_phase")
        summary = data.get("summary", "")
        raw_dialogues = data.get("raw_dialogues", [])
        
        if summary and summary != "No summary available.":
            conditions = set()
            categories = set()
            timeline_phases = set()
            
            for d in raw_dialogues:
                if "category" in d and d["category"]:
                    categories.add(d["category"])
                if "timeline_phase" in d:
                    timeline_phases.add(str(d["timeline_phase"]))
                if "conditions" in d and isinstance(d["conditions"], list):
                    for c in d["conditions"]:
                        conditions.add(c)
                        
            meta_header = ""
            if categories:
                meta_header += f"[Categories: {', '.join(categories)}]\n"
            if timeline_phases:
                meta_header += f"[Timeline Phases: {', '.join(sorted(timeline_phases, key=lambda x: int(x) if x.isdigit() else 0))}]\n"
            if conditions:
                meta_header += f"[Conditions: {', '.join(conditions)}]\n"
                
            enhanced_summary = f"--- CHUNK METADATA ---\n{meta_header}--- SUMMARY ---\n{summary}\n"
            
            if phase in phase_data:
                phase_data[phase]["summaries"].append(enhanced_summary)
                valid_chunks_count += 1
        else:
            missing_chunks += 1
            
    if missing_chunks > 0:
        print(f"WARNING: There are still {missing_chunks} chunks without summaries. Reduction might be incomplete.", flush=True)
        
    story_timeline = {}
    for phase_id, p_info in phase_data.items():
        if not p_info["summaries"]:
            continue
            
        print(f"\nProcessing {p_info['name']} (Total Chunk Summaries: {len(p_info['summaries'])})", flush=True)
        final_summary = await resilient_reduce(agent, p_info["name"], p_info["summaries"], data_dir, batch_size=20)
        
        story_timeline[str(phase_id)] = {
            "name": p_info["name"],
            "summary": final_summary
        }
        
    story_timeline["_meta"] = {
        "total_chunks_processed": valid_chunks_count
    }
        
    with open(timeline_out_path, "w", encoding="utf-8") as f:
        json.dump(story_timeline, f, indent=2, ensure_ascii=False)
        
    print(f"\nMacro-Timeline Complete. Saved to {timeline_out_path}", flush=True)

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    asyncio.run(run_reduce_phase(tlas_dir))
