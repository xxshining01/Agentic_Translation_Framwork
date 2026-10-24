import os
import re
import json

def get_safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in name).strip()

def salvage_checkpoints():
    log_path = r"d:\Agentic Translation Framework (ATF) Project\llm_trace.log"
    data_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    checkpoints_dir = os.path.join(data_dir, "reduce_checkpoints")
    os.makedirs(checkpoints_dir, exist_ok=True)
    
    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return
        
    print("Parsing llm_trace.log to salvage checkpoints...")
    
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split by the separator used in base.py
    blocks = content.split("==================================================")
    
    salvaged_data = {} # { phase_name: { level: { batch_id: response } } }
    
    for block in blocks:
        if "USER PROMPT:" not in block or "RESPONSE:" not in block:
            continue
            
        try:
            # Extract phase name, level and batch
            # Look for: You are writing the official Chronological Story Summary for: Phase 2: The Present (Main Storyline) L1 B3
            match = re.search(r"You are writing the official Chronological Story Summary for: (.*?) L(\d+) B(\d+)", block)
            if not match:
                continue
                
            phase_name = match.group(1).strip()
            level = match.group(2)
            batch_id = match.group(3)
            
            # Extract RESPONSE
            resp_parts = block.split("RESPONSE:\n")
            if len(resp_parts) > 1:
                response = resp_parts[1].strip()
                
                # Clean up any trailing ==== or empty space
                response = re.sub(r'={50,}\s*$', '', response).strip()
                
                if phase_name not in salvaged_data:
                    salvaged_data[phase_name] = {}
                if level not in salvaged_data[phase_name]:
                    salvaged_data[phase_name][level] = {}
                    
                salvaged_data[phase_name][level][batch_id] = response
                
        except Exception as e:
            print(f"Error parsing a block: {e}")
            
    # Now write the checkpoint files
    total_salvaged = 0
    for phase_name, levels in salvaged_data.items():
        safe_name = get_safe_filename(phase_name)
        for level, batches in levels.items():
            cp_path = os.path.join(checkpoints_dir, f"{safe_name}_L{level}.json")
            
            # Load existing if any
            existing_batches = {}
            if os.path.exists(cp_path):
                with open(cp_path, "r", encoding="utf-8") as f:
                    existing_batches = json.load(f)
                    
            # Merge
            for b_id, b_res in batches.items():
                existing_batches[b_id] = b_res
                total_salvaged += 1
                
            # Save
            with open(cp_path, "w", encoding="utf-8") as f:
                json.dump(existing_batches, f, ensure_ascii=False)
                
            print(f"Saved Checkpoint: {cp_path} ({len(batches)} batches salvaged)")
            
    print(f"\nSalvage Complete! Successfully recovered {total_salvaged} generated batches from logs.")

if __name__ == "__main__":
    salvage_checkpoints()
