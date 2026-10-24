import json
import os
import glob
from collections import defaultdict, deque
import copy
import re

def clean_text(t):
    t = re.sub(r'\\n<\w+:>', '', t)
    t = re.sub(r'<\w+:>', '', t)
    t = re.sub(r'\\[a-zA-Z]+(\[[^\]]*\])?', '', t)
    t = re.sub(r'\\[\.\|\>\<\\!\{\}]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

def parse_ast(cmd_list):
    ast = []
    i = 0
    while i < len(cmd_list):
        c = cmd_list[i]
        
        if c['code'] == 102: # Show Choices
            choice_node = {'type': 'CHOICE', 'branches': {}, 'raw': c}
            i += 1
            while i < len(cmd_list) and cmd_list[i]['code'] in [402, 403]:
                if cmd_list[i]['code'] == 402:
                    choice_idx = cmd_list[i]['parameters'][0]
                    choice_name = cmd_list[i]['parameters'][1]
                    branch_indent = cmd_list[i]['indent'] + 1
                    
                    branch_cmds = []
                    i += 1
                    while i < len(cmd_list) and cmd_list[i]['indent'] >= branch_indent:
                        branch_cmds.append(cmd_list[i])
                        i += 1
                        
                    choice_node['branches'][choice_idx] = {
                        'name': choice_name,
                        'ast': parse_ast(branch_cmds)
                    }
                elif cmd_list[i]['code'] == 403: # Cancel
                    branch_indent = cmd_list[i]['indent'] + 1
                    branch_cmds = []
                    i += 1
                    while i < len(cmd_list) and cmd_list[i]['indent'] >= branch_indent:
                        branch_cmds.append(cmd_list[i])
                        i += 1
                    choice_node['branches']['cancel'] = {
                        'name': 'Cancel',
                        'ast': parse_ast(branch_cmds)
                    }
            if i < len(cmd_list) and cmd_list[i]['code'] == 404:
                i += 1
            ast.append(choice_node)
        else:
            ast.append({'type': 'CMD', 'data': c})
            i += 1
    return ast

class RPGMEmulator:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.maps = {}
        self.common_events = {}
        self.system = {}
        
        self.switch_names = {}
        self.variable_names = {}
        self.map_names = {}
        
        self.load_data()
        
        self.start_map_id = self.system.get('startMapId', 1)
        self.FLASHBACK_MAPS = {136, 138, 139}

    def load_data(self):
        print(f"  -> Loading Data from {self.data_dir}")
        with open(os.path.join(self.data_dir, 'System.json'), encoding='utf-8') as f:
            self.system = json.load(f)
            self.switch_names = {i: name for i, name in enumerate(self.system.get('switches', [])) if name}
            self.variable_names = {i: name for i, name in enumerate(self.system.get('variables', [])) if name}
            
        for f in glob.glob(os.path.join(self.data_dir, 'Map[0-9][0-9][0-9].json')):
            map_id = int(os.path.basename(f)[3:6])
            with open(f, encoding='utf-8') as m:
                d = json.load(m)
                if isinstance(d, dict):
                    self.maps[map_id] = d

        with open(os.path.join(self.data_dir, 'MapInfos.json'), encoding='utf-8') as f:
            minfos = json.load(f)
            if minfos:
                for m in minfos:
                    if m: self.map_names[m['id']] = m.get('name', '')

        with open(os.path.join(self.data_dir, 'CommonEvents.json'), encoding='utf-8') as f:
            self.common_events = {e['id']: e for e in json.load(f) if e}
            
        # Precompute map adjacency list for fast BFS
        self.map_adjacency_list = defaultdict(set)
        for map_id, map_data in self.maps.items():
            for ev in map_data.get('events', []):
                if not ev: continue
                for page in ev.get('pages', []):
                    def extract_transfers(cmd_list, visited_ces=None):
                        if visited_ces is None: visited_ces = set()
                        for cmd in cmd_list:
                            if cmd['code'] == 201:
                                dest = cmd['parameters'][1]
                                if dest > 0: self.map_adjacency_list[map_id].add(dest)
                            elif cmd['code'] in [355, 655]:
                                match = re.search(r'reserveTransfer\(\s*(\d+)', cmd.get('parameters', [''])[0])
                                if match:
                                    dest = int(match.group(1))
                                    if dest > 0: self.map_adjacency_list[map_id].add(dest)
                            elif cmd['code'] == 117:
                                ce_id = cmd['parameters'][0]
                                if ce_id in self.common_events and ce_id not in visited_ces:
                                    visited_ces.add(ce_id)
                                    extract_transfers(self.common_events[ce_id].get('list', []), visited_ces)
                    extract_transfers(page.get('list', []))
                    
        print(f"  -> Loaded {len(self.maps)} Maps, {len(self.common_events)} Common Events.")

class GameState:
    def __init__(self, emulator):
        self.emulator = emulator
        self.variables = defaultdict(int)
        self.switches = set()
        self.self_switches = set()
        self.items = set()
        self.gold = 0
        self.weapons = set()
        self.armors = set()
        self.actors = set()
        self.current_map = emulator.start_map_id
        
        self.timeline_phase = 1
        self.dialogue_phase = 1
        self.story_scenes = []
        self.map_history = []
        self.discovered_maps = set()
        self.fast_travel_blacklist = set()
        self.visited_autoruns = set()
        self.visited_action_events = set() # To prevent infinite loops on static NPCs
        self.consecutive_stuck_time = 0
        self.global_visited_states = set()
        
        self.active_page_cache = {}
        
        self.route_path = []
        self.route_id = "Main"
        
    def get_signature(self):
        return (
            self.current_map,
            tuple(sorted(self.switches)),
            tuple(sorted((k, v) for k, v in self.variables.items() if k not in [41, 44, 485, 494, 738, 739, 740])),
            tuple(sorted(self.items))
        )
        
    def clone(self):
        new_state = GameState(self.emulator)
        new_state.variables = self.variables.copy()
        new_state.switches = self.switches.copy()
        new_state.self_switches = self.self_switches.copy()
        new_state.items = self.items.copy()
        new_state.gold = self.gold
        new_state.weapons = self.weapons.copy()
        new_state.armors = self.armors.copy()
        new_state.actors = self.actors.copy()
        new_state.current_map = self.current_map
        
        new_state.timeline_phase = self.timeline_phase
        new_state.dialogue_phase = self.dialogue_phase
        new_state.story_scenes = list(self.story_scenes)
        new_state.map_history = list(self.map_history)
        new_state.discovered_maps = self.discovered_maps.copy()
        new_state.fast_travel_blacklist = self.fast_travel_blacklist.copy()
        new_state.visited_autoruns = self.visited_autoruns.copy()
        new_state.visited_action_events = self.visited_action_events.copy()
        new_state.consecutive_stuck_time = self.consecutive_stuck_time
        new_state.active_page_cache = self.active_page_cache.copy()
        
        new_state.route_path = list(self.route_path)
        new_state.route_id = self.route_id
        return new_state

    def is_page_active(self, map_id, event_id, page):
        c = page.get('conditions', {})
        if c.get('switch1Valid') and c.get('switch1Id') not in self.switches: return False
        if c.get('switch2Valid') and c.get('switch2Id') not in self.switches: return False
        if c.get('variableValid') and self.variables[c.get('variableId')] < c.get('variableValue'): return False
        if c.get('selfSwitchValid') and (map_id, event_id, c.get('selfSwitchCh')) not in self.self_switches: return False
        if c.get('itemValid') and c.get('itemId') not in self.items: return False
        if c.get('actorValid') and c.get('actorId') not in self.actors: return False
        return True

    def get_missing_conditions(self, map_id, event_id, page):
        missing = []
        c = page.get('conditions', {})
        if c.get('switch1Valid') and c.get('switch1Id') not in self.switches:
            missing.append({'type': 'switch', 'id': c.get('switch1Id'), 'val': True})
        if c.get('switch2Valid') and c.get('switch2Id') not in self.switches:
            missing.append({'type': 'switch', 'id': c.get('switch2Id'), 'val': True})
        if c.get('variableValid') and self.variables[c.get('variableId')] < c.get('variableValue'):
            missing.append({'type': 'variable', 'id': c.get('variableId'), 'val': c.get('variableValue')})
        if c.get('selfSwitchValid') and (map_id, event_id, c.get('selfSwitchCh')) not in self.self_switches:
            missing.append({'type': 'self_switch', 'id': c.get('selfSwitchCh'), 'val': True})
        if c.get('itemValid') and c.get('itemId') not in self.items:
            missing.append({'type': 'item', 'id': c.get('itemId'), 'val': True})
        if c.get('actorValid') and c.get('actorId') not in self.actors:
            missing.append({'type': 'actor', 'id': c.get('actorId'), 'val': True})
        return missing

    def get_active_page(self, map_id, event):
        if not event or 'pages' not in event: return -1, None
        cache_key = (map_id, event['id'])
        if cache_key in self.active_page_cache:
            return self.active_page_cache[cache_key]
            
        for pidx in range(len(event['pages']) - 1, -1, -1):
            page = event['pages'][pidx]
            if self.is_page_active(map_id, event['id'], page):
                self.active_page_cache[cache_key] = (pidx, page)
                return pidx, page
        self.active_page_cache[cache_key] = (-1, None)
        return -1, None

    def apply_state_cmd(self, c):
        self.active_page_cache.clear()
        code = c['code']
        params = c.get('parameters', [])
        if code == 121:
            start, end, op = params[0], params[1], params[2]
            for s in range(start, end + 1):
                if op == 0: self.switches.add(s)
                else: self.switches.discard(s)
        elif code == 122:
            start, end, op, operand, val = params[0], params[1], params[2], params[3], params[4]
            if op == 0:
                for v in range(start, end + 1):
                    self.variables[v] = val if operand == 0 else self.variables.get(val, 0)
        elif code == 123:
            key = params[0]
            op = params[1]
            if op == 0: self.self_switches.add((self.current_map, 0, key)) 
            else: self.self_switches.discard((self.current_map, 0, key))
        elif code == 201:
            self.map_history.append(self.current_map)
            self.current_map = params[1]

    def execute_ast_nfa(self, states, ast, source_type, event_name, map_id, ev_id):
        def contains_state_change(ast_nodes):
            for n in ast_nodes:
                if n['type'] == 'CMD':
                    if n['data']['code'] in [121, 201]: return True
                      if n['data']['code'] == 122:
                          if n['data']['parameters'][0] not in [41, 44, 485, 494, 738, 739, 740]: return True
                    if n['data']['code'] == 117:
                        ce = self.emulator.common_events.get(n['data']['parameters'][0])
                        if ce and contains_state_change(parse_ast(ce.get('list', []))): return True
                elif n['type'] == 'CHOICE':
                    for b in n['branches'].values():
                        if contains_state_change(b['ast']): return True
            return False

        for node in ast:
            if not states: break
            
            if node['type'] == 'CMD':
                next_states = []
                c = node['data']
                code = c['code']
                params = c.get('parameters', [])
                
                for state in states:
                    if code == 401:
                        text = params[0]
                        is_fb = state.current_map in state.emulator.FLASHBACK_MAPS
                        state.story_scenes.append({
                            "source": source_type,
                            "map_id": map_id,
                            "event_id": ev_id,
                            "event_name": event_name,
                            "route": state.route_id,
                            "text": text,
                            "timeline_phase": state.dialogue_phase,
                            "is_flashback": is_fb
                        })
                        state.dialogue_phase += 1
                    elif code in [121, 122, 123, 125, 126, 127, 128, 129, 201]:
                        state.apply_state_cmd(c)
                    elif code == 117:
                        ce_id = params[0]
                        if ce_id in state.emulator.common_events:
                            ce = state.emulator.common_events[ce_id]
                            ce_ast = parse_ast(ce.get('list', []))
                            result_states = state.execute_ast_nfa([state], ce_ast, "COMMON_EVENT", f"CE{ce_id}", map_id, ev_id)
                            next_states.extend(result_states)
                            continue
                    next_states.append(state)
                states = next_states
                
            elif node['type'] == 'CHOICE':
                next_states = []
                for state in states:
                    has_meaningful_branch = False
                    for b_idx, branch in node['branches'].items():
                        if contains_state_change(branch['ast']):
                            has_meaningful_branch = True
                            break
                            
                    if not has_meaningful_branch:
                        # Pruning: Just extract dialogue from all branches into current state linearly
                        for b_idx, branch in node['branches'].items():
                            if branch['name'] != 'Cancel': # Skip empty cancel branches
                                state.story_scenes.append({
                                    "source": "CHOICE_INLINE",
                                    "map_id": map_id,
                                    "event_id": ev_id,
                                    "event_name": event_name,
                                    "route": state.route_id,
                                    "text": "> Choice: " + branch['name'],
                                    "timeline_phase": state.dialogue_phase,
                                    "is_flashback": state.current_map in state.emulator.FLASHBACK_MAPS
                                })
                                state.dialogue_phase += 1
                                state.execute_ast_nfa([state], branch['ast'], source_type, event_name, map_id, ev_id)
                        next_states.append(state)
                    else:
                        for b_idx, branch in node['branches'].items():
                            if contains_state_change(branch['ast']):
                                cloned = state.clone()
                                
                                if cloned.route_id == "Main":
                                    cloned.route_id = f"Branch-{b_idx}"
                                else:
                                    cloned.route_id = f"{cloned.route_id}-{b_idx}"
                                    
                                cloned.route_path.append(branch['name'])
                                
                                cloned.story_scenes.append({
                                    "source": "CHOICE",
                                    "map_id": map_id,
                                    "event_id": ev_id,
                                    "event_name": event_name,
                                    "route": cloned.route_id,
                                    "text": "> Choice: " + branch['name'],
                                    "timeline_phase": cloned.dialogue_phase,
                                    "is_flashback": cloned.current_map in cloned.emulator.FLASHBACK_MAPS
                                })
                                cloned.dialogue_phase += 1
                                
                                branch_states = cloned.execute_ast_nfa([cloned], branch['ast'], source_type, event_name, map_id, ev_id)
                                next_states.extend(branch_states)
                states = next_states
        return states

    def run_autoruns(self):
        executed = True
        while executed:
            map_data = self.emulator.maps.get(self.current_map)
            if not map_data: break
            executed = False
            
            for ce_id, ce in self.emulator.common_events.items():
                if not ce: continue
                trigger = ce.get('trigger', 0)
                switch_id = ce.get('switchId', 0)
                if trigger in [1, 2] and switch_id > 0 and switch_id in self.switches:
                    sig = ('CE', ce_id)
                    if sig in self.visited_autoruns: continue
                    self.visited_autoruns.add(sig)
                    ast = parse_ast(ce.get('list', []))
                    next_states = self.execute_ast_nfa([self], ast, "COMMON_EVENT_AUTORUN", f"CE_{ce_id}", self.current_map, f'CE_{ce_id}')
                    if len(next_states) > 1:
                        return next_states
                    if next_states:
                        self.__dict__.update(next_states[0].__dict__)
                    executed = True
            
            for ev in map_data.get('events', []):
                if not ev: continue
                pidx, page = self.get_active_page(self.current_map, ev)
                if not page: continue
                
                if page['trigger'] in [3, 4]:
                    sig = (self.current_map, ev['id'], pidx)
                    if sig in self.visited_autoruns: continue
                    self.visited_autoruns.add(sig)
                    ast = parse_ast(page.get('list', []))
                    next_states = self.execute_ast_nfa([self], ast, "AUTORUN", f"Map{self.current_map:03d}_Event{ev['id']}_Page{pidx}", self.current_map, ev['id'])
                    if len(next_states) > 1:
                        return next_states
                    if next_states:
                        self.__dict__.update(next_states[0].__dict__)
                    executed = True
        return [self]

    def find_reachable_maps(self):
        distances = {self.current_map: 0}
        queue = deque([self.current_map])
        while queue:
            curr = queue.popleft()
            curr_dist = distances[curr]
            
            for dest in self.emulator.map_adjacency_list.get(curr, []):
                if dest not in distances and dest in self.emulator.maps:
                    distances[dest] = curr_dist + 1
                    queue.append(dest)
        return distances

def simulate_dfs(emulator):
    print(f"  -> Starting DFS Simulator at Map {emulator.start_map_id:03d}")
    initial_state = GameState(emulator)
    stack = [initial_state]
    all_routes = []
    
    max_routes = 200 # Pruning safety
    num_routes = 0
    
    MAX_DEPTH = 3000
    completed_routes = []
    
    global_visited_states = set()
    
    while stack and num_routes < max_routes:
        state = stack.pop()
        
        sig = state.get_signature()
        if sig in global_visited_states:
            continue
        global_visited_states.add(sig)
        
        if state.timeline_phase > MAX_DEPTH:
            print(f"  -> Route {state.route_id} hit MAX_DEPTH. Terminating branch.")
            completed_routes.append(state)
            num_routes += 1
            continue
        
        # Linear execution until dead end or fork
        converged = False
        while not converged and state.timeline_phase < 25000:
            if state.timeline_phase % 50 == 0:
                print(f"  -> [Route {state.route_id}] Phase {state.timeline_phase} Map {state.current_map} | Scenes: {len(state.story_scenes)} | Time: {state.consecutive_stuck_time}")
            state.discovered_maps.add(state.current_map)
            
            # 1. Autoruns
            next_states = state.run_autoruns()
            if len(next_states) > 1:
                stack.extend(next_states)
                converged = True # Forked
                break
            else:
                state = next_states[0]
            
            # 2. Find events
            map_distances = state.find_reachable_maps()
            available_events = []
            for rmap in map_distances:
                if rmap not in emulator.maps: continue
                for ev in emulator.maps[rmap].get('events', []):
                    if not ev: continue
                    pidx, page = state.get_active_page(rmap, ev)
                    if page and page['trigger'] in [0, 1, 2]:
                        sig = (rmap, ev['id'], pidx)
                        if sig in state.visited_action_events: continue
                        has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                        if has_meaningful_commands:
                            available_events.append((rmap, ev, pidx, page))
            
            if available_events:
                def event_priority(item):
                    dmap, ev, pidx, page = item
                    def event_has_dialogue(dmap, ev):
                        _, page = state.get_active_page(dmap, ev)
                        if not page: return 1
                        return 0 if any(c['code'] == 401 for c in page.get('list', [])) else 1
                    
                    has_dialogue = event_has_dialogue(dmap, ev)
                    is_current = 0 if dmap == state.current_map else 1
                    distance = map_distances.get(dmap, 999)
                    
                    has_state = 1
                    if page:
                        commands = [c['code'] for c in page.get('list', [])]
                        if 121 in commands or 122 in commands or 117 in commands:
                            has_state = 0
                            
                    name = ev.get('name', '').lower()
                    char_priority = 99
                    if 'masaru' in name: char_priority = 1
                    elif 'shion' in name: char_priority = 2
                    elif 'mayor' in name: char_priority = 3
                    elif 'erica' in name: char_priority = 4
                    elif 'jords' in name: char_priority = 5
                    elif 'rum' in name: char_priority = 6
                            
                    return (distance, char_priority, is_current, has_dialogue, has_state, pidx, ev['id'])
                available_events.sort(key=event_priority)
                
                rmap, ev, pidx, page = available_events[0]
                sig = (rmap, ev['id'], pidx)
                state.visited_action_events.add(sig)
                
                if rmap != state.current_map:
                    state.map_history.append(state.current_map)
                    state.current_map = rmap
                    
                ast = parse_ast(page.get('list', []))
                next_states = state.execute_ast_nfa([state], ast, "EVENT", f"Map{rmap:03d}_Event{ev['id']}_Page{pidx}", rmap, ev['id'])
                
                if len(next_states) > 1:
                    stack.extend(next_states)
                    converged = True # Forked
                    break
                else:
                    state = next_states[0]
                
                state.consecutive_stuck_time = 0
                state.timeline_phase += 1
                
            else:
                # Fast Travel
                found_ft = False
                for dmap in state.discovered_maps:
                    if dmap not in emulator.maps or dmap in state.fast_travel_blacklist: continue
                    for ev in emulator.maps[dmap].get('events', []):
                        if not ev: continue
                        pidx, page = state.get_active_page(dmap, ev)
                        if page:
                            sig = (dmap, ev['id'], pidx)
                            is_visited = False
                            if page['trigger'] in [0, 1, 2]: is_visited = sig in state.visited_action_events
                            elif page['trigger'] in [3, 4]: is_visited = sig in state.visited_autoruns
                            if not is_visited:
                                has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                                if has_meaningful_commands:
                                    state.current_map = dmap
                                    state.fast_travel_blacklist.add(dmap)
                                    found_ft = True
                                    break
                    if found_ft: break
                
                if found_ft: continue
                else:
                    if state.consecutive_stuck_time < 24:
                        state.consecutive_stuck_time += 1
                        state.variables[44] += 1
                        if state.variables[44] >= 24:
                            state.variables[44] = 6
                            state.variables[41] += 1
                        
                        h = state.variables[44]
                        if 5 <= h <= 17:
                            state.switches.discard(24)
                            state.switches.discard(42)
                            state.switches.discard(43)
                            state.switches.discard(45)
                        elif 17 < h <= 19:
                            state.switches.add(24)
                            state.switches.add(42)
                            state.switches.discard(43)
                            state.switches.discard(45)
                        else:
                            state.switches.discard(24)
                            state.switches.discard(42)
                            state.switches.add(43)
                            if h >= 22 or h < 5: state.switches.add(45)
                            
                        state.story_scenes.append({
                            "source": "SYSTEM_MACRO",
                            "map_id": state.current_map,
                            "event_id": 0,
                            "event_name": "TIME_ADVANCE",
                            "route": state.route_id,
                            "text": f"[SYSTEM] Advanced Time to Day {state.variables[41]}, {state.variables[44]:02d}:00",
                            "timeline_phase": None,
                            "is_flashback": state.current_map in emulator.FLASHBACK_MAPS
                        })
                        state.timeline_phase += 1
                        state.fast_travel_blacklist.clear()
                        continue
                    else:
                        # Omni-Key
                        unlocked_something = False
                        for dmap in state.discovered_maps:
                            if dmap not in emulator.maps: continue
                            for ev in emulator.maps[dmap].get('events', []):
                                if not ev: continue
                                active_pidx, _ = state.get_active_page(dmap, ev)
                                for pidx in range(len(ev['pages']) - 1, -1, -1):
                                    if pidx <= active_pidx: continue
                                    page = ev['pages'][pidx]
                                    sig = (dmap, ev['id'], pidx)
                                    if sig in state.visited_action_events or sig in state.visited_autoruns: continue
                                    
                                    missing = state.get_missing_conditions(dmap, ev['id'], page)
                                    has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                                    if missing and has_meaningful_commands:
                                        backup_switches = set(state.switches)
                                        backup_vars = state.variables.copy()
                                        backup_self_switches = set(state.self_switches)
                                        break_texts = []
                                        for m in missing:
                                            if m['type'] == 'switch':
                                                state.switches.add(m['id'])
                                                break_texts.append(f"Forced Switch {m['id']} = ON")
                                            elif m['type'] == 'variable':
                                                state.variables[m['id']] = m['val']
                                                break_texts.append(f"Forced Var {m['id']} = {m['val']}")
                                            elif m['type'] == 'self_switch':
                                                state.self_switches.add((dmap, ev['id'], m['id']))
                                                break_texts.append(f"Forced Self-Switch {m['id']} = ON")
                                            elif m['type'] == 'item':
                                                state.items.add(m['id'])
                                                break_texts.append(f"Forced Item {m['id']}")
                                        
                                        test_pidx, _ = state.get_active_page(dmap, ev)
                                        if test_pidx != pidx:
                                            state.switches = backup_switches
                                            state.variables = backup_vars
                                            state.self_switches = backup_self_switches
                                            continue
                                        
                                        text_log = f"[SYSTEM] Omni-Key used on Map {dmap} Event {ev['id']} Page {pidx}:\n" + "\n".join(break_texts)
                                        state.story_scenes.append({
                                            "source": "SYSTEM_MACRO",
                                            "map_id": dmap,
                                            "event_id": ev['id'],
                                            "event_name": "OMNI_KEY",
                                            "route": state.route_id,
                                            "text": text_log,
                                            "timeline_phase": None,
                                            "is_flashback": dmap in emulator.FLASHBACK_MAPS
                                        })
                                        state.timeline_phase += 1
                                        state.consecutive_stuck_time = 0
                                        state.fast_travel_blacklist.clear()
                                        state.current_map = dmap
                                        unlocked_something = True
                                        break
                                if unlocked_something: break
                            if unlocked_something: break
                        
                        if unlocked_something: continue
                        else:
                            print(f"  -> Route {state.route_id} Converged with {len(state.story_scenes)} scenes.")
                            all_routes.extend(state.story_scenes)
                            num_routes += 1
                            converged = True
                            break
                            
        if not converged and state.timeline_phase >= 25000:
             print(f"  -> Route {state.route_id} hit Phase Limit.")
             all_routes.extend(state.story_scenes)
             num_routes += 1

    print(f"  -> Total Scenes extracted across {num_routes} branches: {len(all_routes)}")
    all_scenes = []
    for r in completed_routes:
        all_scenes.extend(r.story_scenes)
        
    output_file = os.path.join(emulator.data_dir, '..', '..', 'data', 'tlas', 'rpgm_scenes_dfs.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_scenes, f, indent=4, ensure_ascii=False)
    print(f"  -> Saved output to {output_file}")

if __name__ == "__main__":
    data_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\www\data"
    emulator = RPGMEmulator(data_dir)
    simulate_dfs(emulator)
