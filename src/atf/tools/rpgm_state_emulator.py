import json
import os
import glob
import time
from collections import defaultdict
import re

def build_rpgm_state_emulator(data_dir, output_path):
    t0 = time.time()
    print(f"\n{'='*70}")
    print(f"  [RPGM State Emulator v5] TRUE REACHABILITY ANALYSIS")
    print(f"  Source Data: {data_dir}")
    print(f"{'='*70}\n")
    
    # 1. System.json
    sys_path = os.path.join(data_dir, "System.json")
    with open(sys_path, "r", encoding="utf-8") as f:
        system = json.load(f)
        switches = system.get("switches", [])
        variables = system.get("variables", [])
        start_map_id = system.get("startMapId", 1)

    def get_sw_name(idx):
        if 0 < idx < len(switches) and switches[idx]: return switches[idx]
        return f"Switch_{idx}"

    def get_var_name(idx):
        if 0 < idx < len(variables) and variables[idx]: return variables[idx]
        return f"Var_{idx}"

    # 2. Load Maps
    maps = {}
    for mf in sorted(glob.glob(os.path.join(data_dir, "Map*.json"))):
        bname = os.path.basename(mf).replace(".json", "")
        try:
            mid = int(bname.replace("Map", ""))
            with open(mf, "r", encoding="utf-8") as f:
                maps[mid] = json.load(f)
        except ValueError:
            continue

    # 3. Load Common Events
    common_events = {}
    ce_path = os.path.join(data_dir, "CommonEvents.json")
    if os.path.exists(ce_path):
        with open(ce_path, "r", encoding="utf-8") as f:
            for ce in json.load(f):
                if ce:
                    common_events[ce["id"]] = ce

    print(f"  -> Loaded {len(maps)} Maps, {len(common_events)} Common Events.")
    print(f"  -> Starting State Emulator at Map {start_map_id:03d}")

    # 4. Command Parser
    def parse_command_list(cmd_list):
        dialogue = []
        faces = set()
        sw_sets = []
        var_mods = []
        transfers = []
        ce_calls = []
        current_speaker = "Unknown"
        
        in_skipped_choice = False
        
        for cmd in cmd_list:
            code = cmd.get("code")
            params = cmd.get("parameters", [])
            
            # Follow Branch 0
            if code == 402: 
                choice_idx = params[0]
                in_skipped_choice = (choice_idx != 0)
                continue
            elif code == 404:
                in_skipped_choice = False
                continue
                
            if in_skipped_choice:
                continue
                
            if code == 101: # Show Face
                if len(params) > 0 and params[0]:
                    face = params[0]
                    faces.add(face)
                    current_speaker = face
            elif code == 401: # Show Text
                if len(params) > 0:
                    text = params[0].replace("\\n", "").strip()
                    if "<" in text and ">" in text:
                        end_idx = text.find(">")
                        current_speaker = text[1:end_idx].strip()
                        text = text[end_idx+1:].strip()
                    dialogue.append(f"[{current_speaker}] {text}")
            elif code == 121: # Set switch
                if len(params) >= 3:
                    start, end, val = params[0], params[1], params[2]
                    state = "ON" if val == 0 else "OFF"
                    for i in range(start, end + 1):
                        sw_sets.append((i, get_sw_name(i), state))
            elif code == 122: # Mod variable
                if len(params) >= 5:
                    start, end, op, operand_type, value = params[0], params[1], params[2], params[3], params[4]
                    op_str = ["=", "+", "-", "*", "/", "%"][op] if op < 6 else "?"
                    for i in range(start, end + 1):
                        var_mods.append((i, get_var_name(i), op_str, value))
            elif code == 201: # Transfer player
                if len(params) >= 4:
                    transfers.append(params[1])
            elif code == 117: # Call Common Event
                if len(params) >= 1:
                    ce_calls.append(params[0])
                    
        return {
            "dialogue": dialogue, "faces": faces, "sw_sets": sw_sets, 
            "var_mods": var_mods, "transfers": transfers, "ce_calls": ce_calls
        }

    # 5. Extract ALL Pages as independent Nodes
    nodes = {}
    for mid, mdata in maps.items():
        for ev in mdata.get("events", []):
            if not ev: continue
            for pidx, page in enumerate(ev.get("pages", [])):
                res = parse_command_list(page.get("list", []))
                
                # We care about all pages that have dialogue OR change state OR transfer
                if res["dialogue"] or res["sw_sets"] or res["var_mods"] or res["transfers"]:
                    c = page.get("conditions", {})
                    reqs = []
                    req_switches = []
                    req_vars = {}
                    
                    if c.get("switch1Valid"):
                        reqs.append(f"Switch {c['switch1Id']} == ON")
                        req_switches.append(c['switch1Id'])
                    if c.get("switch2Valid"):
                        reqs.append(f"Switch {c['switch2Id']} == ON")
                        req_switches.append(c['switch2Id'])
                    if c.get("variableValid"):
                        reqs.append(f"Var {c['variableId']} >= {c['variableValue']}")
                        req_vars[c['variableId']] = c['variableValue']
                        
                    is_flashback = False
                    for f in res["faces"]:
                        if any(k in f.lower() for k in ["past", "young", "old", "memory", "flashback"]):
                            is_flashback = True

                    src_id = f"Map{mid:03d}_Event{ev['id']}_Page{pidx}"
                    nodes[src_id] = {
                        "source": src_id,
                        "map_id": mid,
                        "event_id": ev["id"],
                        "page_idx": pidx,
                        "trigger": page.get("trigger", 0),
                        "req_switches": req_switches,
                        "req_vars": req_vars,
                        "conditions_str": reqs,
                        "state_changes": [f"Set {name} to {st}" for _, name, st in res["sw_sets"]],
                        "sw_sets": res["sw_sets"],
                        "var_mods": res["var_mods"],
                        "transfers": res["transfers"],
                        "ce_calls": res["ce_calls"],
                        "dialogue": res["dialogue"],
                        "text": "\n".join(res["dialogue"]),
                        "is_flashback": is_flashback
                    }
                    
    # Include Common Events
    for ce_id, ce in common_events.items():
        res = parse_command_list(ce.get("list", []))
        if res["dialogue"] or res["sw_sets"] or res["transfers"]:
            req_switches = [ce['switchId']] if ce.get('trigger', 0) > 0 and ce.get('switchId', 0) > 0 else []
            src_id = f"CommonEvent_{ce['id']}"
            nodes[src_id] = {
                "source": src_id,
                "map_id": None,
                "event_id": ce["id"],
                "page_idx": 0,
                "trigger": ce.get("trigger", 0),
                "req_switches": req_switches,
                "req_vars": {},
                "conditions_str": [f"Switch {s} == ON" for s in req_switches],
                "state_changes": [f"Set {name} to {st}" for _, name, st in res["sw_sets"]],
                "sw_sets": res["sw_sets"],
                "var_mods": res["var_mods"],
                "transfers": res["transfers"],
                "ce_calls": res["ce_calls"],
                "dialogue": res["dialogue"],
                "text": "\n".join(res["dialogue"]),
                "is_flashback": False
            }

    print(f"  -> Extracted {len(nodes)} interactive nodes.")

    # 6. Reachability Engine (True Causal Dependency Depth)
    known_maps = {start_map_id, 10, 38, 39, 40} 
    known_maps_phase = {m: 0 for m in known_maps}
    
    known_switches = set() # Store ON switches
    known_switches_phase = {}
    
    known_vars = defaultdict(int)
    known_vars_phase = defaultdict(lambda: defaultdict(int)) # var_id -> {val -> phase}

    triggered_nodes = set()
    timeline_scenes = []
    
    iteration = 0
    max_iterations = 200
    
    while iteration < max_iterations:
        new_nodes_triggered = []
        
        # Scan all nodes to find playable ones
        for src, node in nodes.items():
            if src in triggered_nodes:
                continue
                
            # Check Map Constraint
            if node["map_id"] is not None and node["map_id"] not in known_maps:
                continue
                
            # Check Conditions
            valid = True
            for req_sw in node["req_switches"]:
                if req_sw not in known_switches:
                    valid = False
                    break
            if not valid: continue
            
            for req_var, req_val in node["req_vars"].items():
                if known_vars[req_var] < req_val:
                    valid = False
                    break
            if not valid: continue
            
            # Calculate Causal Phase (Depth based on dependencies)
            max_prereq_phase = 0
            if node["map_id"] is not None:
                max_prereq_phase = max(max_prereq_phase, known_maps_phase[node["map_id"]])
                
            for req_sw in node["req_switches"]:
                max_prereq_phase = max(max_prereq_phase, known_switches_phase[req_sw])
                
            for req_var, req_val in node["req_vars"].items():
                var_phases = [p for v, p in known_vars_phase[req_var].items() if v >= req_val]
                if var_phases:
                    max_prereq_phase = max(max_prereq_phase, min(var_phases))
            
            node["causal_phase"] = max_prereq_phase + 1
            
            # Node is Triggerable!
            new_nodes_triggered.append(node)
            
        if not new_nodes_triggered:
            print(f"  -> [Iteration {iteration}] Reachability converged. No new nodes unlockable.")
            break
            
        print(f"  -> [Iteration {iteration:03d}] Unlocked {len(new_nodes_triggered)} events.")
        
        # Apply State Changes
        for node in new_nodes_triggered:
            triggered_nodes.add(node["source"])
            
            if node["dialogue"]:
                out_scene = {
                    "source": node["source"],
                    "map_id": node["map_id"],
                    "event_id": node["event_id"],
                    "page_idx": node["page_idx"],
                    "conditions": node["conditions_str"],
                    "state_changes": node["state_changes"],
                    "text": node["text"],
                    "story_phase": 1 if node["is_flashback"] else 2,
                    "timeline_phase": node["causal_phase"] # Key: Depth in Causal Dependency Graph
                }
                timeline_scenes.append(out_scene)
            
            # Expand World State
            for sw_id, sw_name, state in node["sw_sets"]:
                if state == "ON":
                    if sw_id not in known_switches:
                        known_switches.add(sw_id)
                        known_switches_phase[sw_id] = node["causal_phase"]
                elif state == "OFF" and sw_id in known_switches:
                    pass
                    
            for v_id, v_name, op, val in node["var_mods"]:
                if op == "=": 
                    if known_vars[v_id] < val:
                        known_vars[v_id] = val
                        known_vars_phase[v_id][val] = node["causal_phase"]
                elif op == "+": 
                    if known_vars[v_id] < 999999:
                        known_vars[v_id] = 999999
                        known_vars_phase[v_id][999999] = node["causal_phase"]
                
            for target_map in node["transfers"]:
                if target_map not in known_maps:
                    known_maps.add(target_map)
                    known_maps_phase[target_map] = node["causal_phase"]
                
        iteration += 1

    # 7. Fallback for Unreached Nodes (Supplemental / Cheats / Debug)
    unreached_nodes = [n for s, n in nodes.items() if s not in triggered_nodes and n["dialogue"]]
    print(f"  -> Unreached Dialogue Nodes: {len(unreached_nodes)} (placed at End of Timeline)")
    
    for node in unreached_nodes:
        out_scene = {
            "source": node["source"],
            "map_id": node["map_id"],
            "event_id": node["event_id"],
            "page_idx": node["page_idx"],
            "conditions": node["conditions_str"],
            "state_changes": node["state_changes"],
            "text": node["text"],
            "story_phase": 3,
            "timeline_phase": 9000
        }
        timeline_scenes.append(out_scene)
        
    # Sort Final Timeline
    # By default, timeline_phase ensures topological ordering!
    timeline_scenes.sort(key=lambda x: (x["timeline_phase"], x["story_phase"], x.get("map_id", 0) or 0))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(timeline_scenes, f, indent=4, ensure_ascii=False)
        
    print(f"  -> Successfully saved {len(timeline_scenes)} scenes to {output_path}")
    
    with open(os.path.join(os.path.dirname(output_path), "debug_causal.json"), "w", encoding="utf-8") as f:
        json.dump({
            "maps": known_maps_phase,
            "switches": known_switches_phase
        }, f, indent=4)

if __name__ == "__main__":
    game_data = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\www\data"
    out_file = r"d:\Agentic Translation Framework (ATF) Project\data\tlas\rpgm_scenes_v5.json"
    build_rpgm_state_emulator(game_data, out_file)
