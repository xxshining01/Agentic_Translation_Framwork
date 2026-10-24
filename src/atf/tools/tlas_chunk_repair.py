import os
import sys
import json
import asyncio
import glob

class Tee(object):
    def __init__(self, name, mode):
        self.file = open(name, mode, encoding='utf-8')
        self.stdout = sys.stdout
    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()
    def flush(self):
        self.stdout.flush()
        self.file.flush()
sys.stdout = Tee('repair_log.txt', 'a')
sys.stderr = sys.stdout

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from src.atf.tools.tlas_timeline_generator import TLASTimelineAgent

async def resilient_map_single(agent, scene_dict, max_chars=1500):
    text = scene_dict.get("text", "")
    if not text.strip():
        return ""
        
    try:
        res = await agent.map_chunk([scene_dict])
    except Exception:
        res = ""

    if res and res.strip() and res != "No summary available.":
        return res
        
    print(f"    [Adaptive] Mapping failed. Splitting text (length {len(text)}) into smaller parts...", flush=True)
    
    lines = text.split("\n")
    parts = []
    current_part = ""
    for line in lines:
        if len(current_part) + len(line) > max_chars:
            if current_part:
                parts.append(current_part)
            current_part = line + "\n"
        else:
            current_part += line + "\n"
    if current_part:
        parts.append(current_part)
        
    part_summaries = []
    for i, part in enumerate(parts):
        print(f"      -> Mapping part {i+1}/{len(parts)}...", flush=True)
        temp_scene = scene_dict.copy()
        temp_scene["text"] = part
        
        system_prompt = "You are an expert narrative analyst."
        user_prompt = f"Summarize the key events in this dialogue fragment concisely. Do not invent details:\n\n{json.dumps([temp_scene], ensure_ascii=False, indent=2)}"
        
        try:
            part_res = await agent.call_llm(
                system_prompt=system_prompt, 
                user_prompt=user_prompt, 
                require_json=False, 
                skip_safety_rule=False
            )
        except Exception as e:
            part_res = ""
            
        if not part_res or not part_res.strip() or part_res == "No summary available.":
            if max_chars > 200:
                print(f"      -> [Adaptive] Part {i+1} failed. Self-repairing by halving chunk size to {max_chars // 2}...", flush=True)
                part_res = await resilient_map_single(agent, temp_scene, max_chars=max_chars // 2)
            else:
                print(f"      -> [Adaptive] Part {i+1} failed and is too small to split. Skipping.", flush=True)
                part_res = ""

        if part_res and part_res.strip() and part_res != "No summary available.":
            part_summaries.append(part_res)
            
    if not part_summaries:
        return ""
    
    combined = "\n\n".join(part_summaries)
    final_res = await agent.reduce_phase("Scene Fragment", combined)
    if final_res and final_res != "No summary available.":
        return final_res
    return combined

async def resilient_map_batch(agent, batch_scenes):
    if not batch_scenes:
        return ""
        
    if len(batch_scenes) == 1:
        # If it's just 1 scene, fallback to the single scene string-splitting logic
        return await resilient_map_single(agent, batch_scenes[0])
        
    try:
        # Try mapping the whole batch at once
        res = await agent.map_chunk(batch_scenes)
        if res and res.strip() and res != "No summary available.":
            return res
    except Exception:
        pass
        
    # If the batch fails, we halve the batch and recursively try again
    print(f"    [Adaptive] Batch of {len(batch_scenes)} scenes failed. Halving batch...", flush=True)
    mid = len(batch_scenes) // 2
    
    res1 = await resilient_map_batch(agent, batch_scenes[:mid])
    res2 = await resilient_map_batch(agent, batch_scenes[mid:])
    
    results = []
    if res1: results.append(res1)
    if res2: results.append(res2)
    
    if not results:
        return ""
    
    combined = "\n\n".join(results)
    # Reduce the two halves back together to maintain concise output
    final_res = await agent.reduce_phase("Scene Batch Fragment", combined)
    if final_res and final_res != "No summary available.":
        return final_res
    return combined

async def resilient_reduce(agent, chunk_name, summaries, batch_size=8):
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
        
    current_summaries = summaries
    level = 1
    
    while len(current_summaries) > 1:
        print(f"    [Adaptive] Hierarchical Reduction Level {level} (Total: {len(current_summaries)} summaries)", flush=True)
        next_level = []
        for i in range(0, len(current_summaries), batch_size):
            batch = current_summaries[i:i+batch_size]
            
            # If batch has only 1 element, no need to reduce it with itself
            if len(batch) == 1:
                next_level.append(batch[0])
                continue
                
            combined = "\n\n".join(batch)
            print(f"      -> Reducing batch {i//batch_size + 1}/{(len(current_summaries) + batch_size - 1)//batch_size}...", flush=True)
            res = await agent.reduce_phase(f"{chunk_name} L{level} B{i//batch_size+1}", combined)
            
            if not res or res == "No summary available.":
                if batch_size > 1:
                    print("      -> [Adaptive] Batch reduction failed. Halving batch size and retrying...", flush=True)
                    smaller_batch_res = await resilient_reduce(agent, chunk_name, batch, max(1, batch_size//2))
                    next_level.append(smaller_batch_res)
                else:
                    print("      -> [Adaptive] Reduction failed completely for this part. Falling back to concatenation.", flush=True)
                    next_level.append(combined)
            else:
                next_level.append(res)
                
        # Anti-infinite-loop: if we didn't manage to reduce the array size, just concatenate everything and abort.
        if len(next_level) >= len(current_summaries):
            print("    [Adaptive] No reduction progress could be made. Aborting hierarchical reduce.", flush=True)
            return "\n\n".join(next_level)
            
        current_summaries = next_level
        level += 1
        
    return current_summaries[0]

async def repair_chunks(data_dir: str):
    print("Starting chunk repair...", flush=True)
    agent = TLASTimelineAgent(model_name="local-model")
    chunks_dir = os.path.join(data_dir, "timeline_chunks")
    repair_cp_root = os.path.join(data_dir, "repair_checkpoints")
    os.makedirs(repair_cp_root, exist_ok=True)
    
    chunk_files = sorted(glob.glob(os.path.join(chunks_dir, "chunk_*.json")))
    empty_chunks = []
    
    # 1. Identify empty chunks
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if not data.get("summary") and data.get("raw_dialogues"):
                    has_text = any(d.get("text", "").strip() for d in data.get("raw_dialogues", []))
                    if has_text:
                        empty_chunks.append(cf)
            except Exception as e:
                print(f"Error reading {cf}: {e}")

    print(f"Found {len(empty_chunks)} chunks needing repair.")
    
    # 2. Repair chunks — per-batch checkpoint
    for i, cf in enumerate(empty_chunks):
        chunk_name = os.path.basename(cf).replace(".json", "")
        print(f"Repairing [{i+1}/{len(empty_chunks)}]: {chunk_name}", flush=True)
        
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        valid_chunk_data = [s for s in data["raw_dialogues"] if s.get("text", "").strip()]
        if not valid_chunk_data:
            continue
            
        # Deduplicate by text
        seen_texts = set()
        dedup_chunk_data = []
        for scene in valid_chunk_data:
            txt = scene["text"].strip()
            if txt not in seen_texts:
                seen_texts.add(txt)
                dedup_chunk_data.append(scene)
                
        print(f"  -> Deduplicated from {len(valid_chunk_data)} to {len(dedup_chunk_data)} scenes.", flush=True)

        # Checkpoint dir สำหรับ chunk นี้
        chunk_cp_dir = os.path.join(repair_cp_root, chunk_name)
        os.makedirs(chunk_cp_dir, exist_ok=True)

        # Group into batches
        batches = []
        current_batch = []
        current_chars = 0
        MAX_BATCH_CHARS = 3000
        
        for scene in dedup_chunk_data:
            scene_chars = len(scene.get("text", ""))
            if current_batch and current_chars + scene_chars > MAX_BATCH_CHARS:
                batches.append(current_batch)
                current_batch = [scene]
                current_chars = scene_chars
            else:
                current_batch.append(scene)
                current_chars += scene_chars
                
        if current_batch:
            batches.append(current_batch)
            
        print(f"  -> Grouped into {len(batches)} batches.", flush=True)
        
        sub_summaries = []
        for j, batch in enumerate(batches):
            batch_cp_path = os.path.join(chunk_cp_dir, f"batch_{j:04d}.txt")
            
            # Skip ถ้า batch นี้เสร็จแล้ว
            if os.path.exists(batch_cp_path):
                with open(batch_cp_path, "r", encoding="utf-8") as f:
                    cached = f.read().strip()
                if cached:
                    sub_summaries.append(cached)
                    print(f"  -> [SKIP] Batch {j+1} loaded from checkpoint.", flush=True)
                    continue
            
            print(f"  -> Mapping batch {j+1}/{len(batches)} (Scenes: {len(batch)})...", flush=True)
            res = await resilient_map_batch(agent, batch)
            if res:
                # บันทึก batch checkpoint ทันที (Atomic) — 1 API Call = 1 Disk Write
                tmp = batch_cp_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(res)
                os.replace(tmp, batch_cp_path)
                sub_summaries.append(res)
                print(f"  -> [CHECKPOINT] Batch {j+1} saved.", flush=True)
                    
        if not sub_summaries:
            print(" -> Failed (All scenes returned empty)", flush=True)
            continue
            
        final_chunk_summary = await resilient_reduce(agent, chunk_name, sub_summaries)
        
        if final_chunk_summary:
            data["summary"] = final_chunk_summary
            # Atomic write chunk JSON
            tmp = cf + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cf)
            print(" -> Success", flush=True)
        else:
            print(" -> Failed at reduction step (Unexpected)", flush=True)
                
    print("\nChunk repair finished!")
    
    # 3. Hierarchical Reduce for Phase 2 — per-batch checkpoint
    print("\nStarting Hierarchical Reduce for Phase 2...")
    timeline_out_path = os.path.join(data_dir, "story_timeline.json")
    story_timeline = {}
    if os.path.exists(timeline_out_path):
        with open(timeline_out_path, "r", encoding="utf-8") as f:
            story_timeline = json.load(f)
        
    phase2_summaries = []
    for cf in chunk_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("story_phase") == 2 and data.get("summary"):
                phase2_summaries.append(data["summary"])
                
    print(f"Gathered {len(phase2_summaries)} chunk summaries for Phase 2.")
    
    # Per-batch checkpoint dir สำหรับ Phase 2 reduce
    phase2_cp_dir = os.path.join(data_dir, "reduce_checkpoints", "phase2_batches")
    os.makedirs(phase2_cp_dir, exist_ok=True)
    
    compressed_summaries = []
    batch_size = 10
    
    print("Level 1 Compression...")
    for i in range(0, len(phase2_summaries), batch_size):
        batch_key = f"level1_batch_{i//batch_size:04d}"
        batch_cp_path = os.path.join(phase2_cp_dir, f"{batch_key}.txt")
        
        # Skip ถ้า batch นี้เสร็จแล้ว
        if os.path.exists(batch_cp_path):
            with open(batch_cp_path, "r", encoding="utf-8") as f:
                cached = f.read().strip()
            if cached:
                compressed_summaries.append(cached)
                print(f"  -> [SKIP] {batch_key} loaded from checkpoint.", flush=True)
                continue
        
        batch = phase2_summaries[i:i+batch_size]
        combined = "\n\n".join(batch)
        print(f"  Compressing batch {i//batch_size + 1}/{(len(phase2_summaries)//batch_size)+1}...")
        c_sum = await agent.reduce_phase("Phase 2 - Level 1", combined)
        if c_sum:
            # บันทึกทันที (Atomic)
            tmp = batch_cp_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(c_sum)
            os.replace(tmp, batch_cp_path)
            compressed_summaries.append(c_sum)
            print(f"  -> [CHECKPOINT] {batch_key} saved.", flush=True)
            
    print(f"\nLevel 2 Compression (Finalizing {len(compressed_summaries)} summaries)...")
    final_combined = "\n\n".join(compressed_summaries[:20])
    final_summary = await agent.reduce_phase("Phase 2: The Present", final_combined)
    
    story_timeline["2"] = {
        "name": "Phase 2: The Present (Main Storyline)",
        "summary": final_summary
    }
    
    # Atomic write
    tmp_tl = timeline_out_path + ".tmp"
    with open(tmp_tl, "w", encoding="utf-8") as f:
        json.dump(story_timeline, f, indent=2, ensure_ascii=False)
    os.replace(tmp_tl, timeline_out_path)
        
    print("\nPhase 2 Reduce complete! Saved to story_timeline.json")

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    asyncio.run(repair_chunks(tlas_dir))
