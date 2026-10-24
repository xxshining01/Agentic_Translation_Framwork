import json
import os
import glob
from collections import defaultdict, deque

class RPGMEmulator:
    def __init__(self, data_dir, target_character="masaru", route_name="Main"):
        self.target_character = target_character.lower()
        self.route_name = route_name
        self.data_dir = data_dir
        self.maps = {}
        self.common_events = {}
        self.system = {}
        
        self.switch_names = {}
        self.variable_names = {}
        self.map_names = {}
        self.consecutive_stuck_time = 0
        
        self.load_data()
        
        # Start at the true game entry point from System.json (Map 8 = Prologue)
        self.start_map_id = self.system.get('startMapId', 1)
        self.variables = defaultdict(int)
        self.switches = set()
        self.self_switches = set() # (map_id, event_id, 'A')
        self.items = set()
        self.gold = 0
        self.weapons = set()
        self.armors = set()
        self.actors = set()
        self.current_map = self.start_map_id

        # Maps that are definitively FLASHBACK/PAST-timeline maps (by Map ID, not Switch)
        # Using Map ID-based detection prevents global switch pollution of is_flashback flag
        self.FLASHBACK_MAPS = {136, 138, 139}
        
        self.timeline_phase = 1   # Tracks overall simulator steps (including Time Advance)
        self.dialogue_phase = 1   # Tracks only REAL dialogue scenes
        self.story_scenes = []
        self.map_history = []
        self.discovered_maps = set()
        self.fast_travel_blacklist = set()
        self.visited_autoruns = set() # To prevent infinite loops in the same phase
        self.visited_action_events = set() # To prevent infinite loops on static NPCs

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
            
        print(f"  -> Loaded {len(self.maps)} Maps, {len(self.common_events)} Common Events.")

    def is_page_active(self, map_id, event_id, page):
        c = page.get('conditions', {})
        
        if c.get('switch1Valid') and c.get('switch1Id') not in self.switches: return False
        if c.get('switch2Valid') and c.get('switch2Id') not in self.switches: return False
        
        if c.get('variableValid'):
            if self.variables[c.get('variableId')] < c.get('variableValue'): return False
            
        if c.get('selfSwitchValid'):
            if (map_id, event_id, c.get('selfSwitchCh')) not in self.self_switches: return False

        if c.get('itemValid') and c.get('itemId') not in self.items:
            return False

        if c.get('actorValid') and c.get('actorId') not in self.actors:
            return False

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
        for pidx in range(len(event['pages']) - 1, -1, -1):
            page = event['pages'][pidx]
            if self.is_page_active(map_id, event['id'], page):
                return pidx, page
        return -1, None

    def execute_event_commands(self, map_id, ev, page, event_name, visited_ces=None):
        if visited_ces is None:
            visited_ces = set()
        transfers = []
        unindented_transfers = []
        for c in page.get('list', []):
            code = c['code']
            params = c['parameters']
            indent = c.get('indent', 0)
            
            if code in [121, 122]: # Switch / Variable operations
                if code == 121:
                    start, end, op = params[0], params[1], params[2]
                    for s in range(start, end + 1):
                        if op == 0:
                            self.switches.add(s)
                        else:
                            self.switches.discard(s)
                elif code == 122:
                    start, end, op, operand, val = params[0], params[1], params[2], params[3], params[4]
                    if op == 0:
                        for v in range(start, end + 1):
                            self.variables[v] = val if operand == 0 else self.variables.get(val, 0)
            elif code == 123: # Control Self Switch
                key = params[0]  # 'A', 'B', 'C', 'D'
                op = params[1]   # 0 = ON, 1 = OFF
                ev_id = ev.get('id') if isinstance(ev, dict) else ev
                if isinstance(ev_id, int):
                    if op == 0:
                        self.self_switches.add((map_id, ev_id, key))
                    else:
                        self.self_switches.discard((map_id, ev_id, key))
            elif code == 125: # Change Gold
                op = params[0]
                operand_type = params[1]
                val = params[2] if operand_type == 0 else self.variables.get(params[2], 0)
                if op == 0:
                    self.gold += val
                else:
                    self.gold = max(0, self.gold - val)
            elif code == 126: # Change Items
                item_id = params[0]
                op = params[1]  # 0 = increase, 1 = decrease
                operand_type = params[2]
                val = params[3] if operand_type == 0 else self.variables.get(params[3], 0)
                if op == 0:
                    self.items.add(item_id)
                # Keep items in set even on decrease for condition checking
            elif code == 127: # Change Weapons
                weapon_id = params[0]
                op = params[1]
                if op == 0:
                    self.weapons.add(weapon_id)
            elif code == 128: # Change Armors
                armor_id = params[0]
                op = params[1]
                if op == 0:
                    self.armors.add(armor_id)
            elif code == 129: # Change Party Member
                actor_id = params[0]
                op = params[1]  # 0 = add, 1 = remove
                if op == 0:
                    self.actors.add(actor_id)
                else:
                    self.actors.discard(actor_id)
            elif code == 201: # Transfer Player
                dest_map_id = params[1]
                transfers.append(dest_map_id)
                if indent == 0:
                    unindented_transfers.append(dest_map_id)
            elif code == 117: # Call Common Event (Recursive)
                ce_id = params[0]
                if ce_id in self.common_events and ce_id not in visited_ces:
                    visited_ces.add(ce_id)
                    ce = self.common_events[ce_id]
                    ce_transfers = self.execute_event_commands(
                        map_id, ev, {'list': ce.get('list', [])},
                        f"{event_name}_CE{ce_id}",
                        visited_ces
                    )
                    transfers.extend(ce_transfers)
                    
        if unindented_transfers:
            return [unindented_transfers[-1]]
        return transfers

    def _collect_text_lines(self, cmd_list, visited_ces=None):
        """Recursively collects dialogue text lines from commands, following Common Event calls."""
        if visited_ces is None:
            visited_ces = set()
        text_lines = []
        for c in cmd_list:
            if c['code'] == 401:
                text_lines.append(c['parameters'][0])
            elif c['code'] == 402:
                text_lines.append("> Choice: " + str(c['parameters'][1]))
            elif c['code'] == 117: # Call Common Event — recurse to extract its dialogue
                ce_id = c['parameters'][0]
                if ce_id in self.common_events and ce_id not in visited_ces:
                    visited_ces.add(ce_id)
                    ce = self.common_events[ce_id]
                    text_lines.extend(self._collect_text_lines(ce.get('list', []), visited_ces))
        return text_lines

    def extract_dialogue(self, map_id, event_id, pidx, page, source_type="EVENT"):
        text_lines = self._collect_text_lines(page.get('list', []))
        
        if text_lines:
            text = "\n".join(text_lines)
            # is_flashback: use Map ID only - never Global Switches to avoid cross-contamination
            is_fb = map_id in self.FLASHBACK_MAPS
            self.story_scenes.append({
                "source": source_type,
                "map_id": map_id,
                "event_id": event_id,
                "event_name": "Map" + str(map_id) + "_Ev" + str(event_id) + "_Page" + str(pidx),
                "route": "Main",
                "text": text,
                "timeline_phase": self.dialogue_phase,
                "is_flashback": is_fb
            })
            self.dialogue_phase += 1

    def precondition_weight(self, event):
        """Generic: Count total number of conditions across ALL pages of an event.
        More conditions = event is deeper in the narrative = lower priority.
        This is game-agnostic — works for any RPG Maker game."""
        total = 0
        for page in event.get('pages', []):
            c = page.get('conditions', {})
            if c.get('switch1Valid'): total += 1
            if c.get('switch2Valid'): total += 1
            if c.get('variableValid'): total += 1
            if c.get('selfSwitchValid'): total += 1
            if c.get('itemValid'): total += 1
            if c.get('actorValid'): total += 1
        return total

    def heuristic_route(self, face_name, event_name):
        face_name = face_name.lower()
        event_name = event_name.lower()
        if 'shion' in face_name or 'shion' in event_name: return 'Shion'
        if 'masaru' in face_name or 'masaru' in event_name: return 'Masaru'
        if 'erica' in face_name or 'erica' in event_name: return 'Erica'
        if 'jord' in face_name or 'jord' in event_name: return 'Jords'
        if 'rum' in face_name or 'rum' in event_name: return 'Rum'
        if 'mayor' in face_name or 'mayor' in event_name: return 'Mayor'
        return 'Main/Common'

    def run_autoruns(self):
        """ Runs all active Autorun (3) and Parallel (4) events on the current map until convergence """
        executed = True
        while executed:
            map_data = self.maps.get(self.current_map)
            if not map_data:
                break
                
            executed = False
            
            # 1. Run Common Events that are Autorun/Parallel
            for ce_id, ce in self.common_events.items():
                if not ce: continue
                trigger = ce.get('trigger', 0)
                switch_id = ce.get('switchId', 0)
                if trigger in [1, 2] and switch_id > 0 and switch_id in self.switches:
                    sig = ('CE', ce_id)
                    if sig in self.visited_autoruns:
                        continue
                    
                    self.visited_autoruns.add(sig)
                    
                    transfers = self.execute_event_commands(
                        self.current_map, {'id': f'CE_{ce_id}'}, {'list': ce.get('list', [])},
                        f"CommonEvent_{ce_id}"
                    )
                    self.extract_dialogue(self.current_map, f'CE_{ce_id}', 0, {'list': ce.get('list', [])}, source_type="COMMON_EVENT_AUTORUN")
                    executed = True
                    if transfers:
                        target_map = transfers[0]
                        print(f"  -> Common Event {ce_id} transferred to Map {target_map:03d}")
                        self.current_map = target_map
            
            # 2. Run Map Events
            for ev in map_data.get('events', []):
                if not ev: continue
                pidx, page = self.get_active_page(self.current_map, ev)
                if not page: continue
                
                if page['trigger'] in [3, 4]:
                    sig = (self.current_map, ev['id'], pidx)
                    # If this exact page was already run in this phase and it's a Parallel, skip to avoid infinite loop
                    # If it's Autorun, it should have changed state to disable itself. If not, it's a hard lock.
                    if sig in self.visited_autoruns:
                        continue
                        
                    self.visited_autoruns.add(sig)
                    
                    transfers = self.execute_event_commands(
                        self.current_map, ev, page, 
                        f"Map{self.current_map:03d}_Event{ev['id']}_Page{pidx}"
                    )
                    self.extract_dialogue(self.current_map, ev['id'], pidx, page, source_type="AUTORUN")
                    
                    executed = True
                    
                    if transfers:
                        self.map_history.append(self.current_map)
                        self.current_map = transfers[-1]
                        break # Break out of event loop to restart on new map

    def find_reachable_maps(self):
        """BFS to find all reachable maps from current_map via Transfer events.
        Returns dict {map_id: bfs_distance} so the caller can prioritize
        events in closer maps over events in far-away maps.
        Only follows transfers in currently-active event pages (conditions respected).
        """
        import re
        distances = {self.current_map: 0}
        queue = deque([self.current_map])
        
        while queue:
            curr = queue.popleft()
            curr_dist = distances[curr]
            if curr not in self.maps: continue
            
            for ev in self.maps[curr].get('events', []):
                if not ev: continue
                pidx, page = self.get_active_page(curr, ev)
                if not page: continue
                
                # Only follow transfers that the player can actively trigger
                if page['trigger'] not in [0, 1, 2]: continue
                
                def extract_transfers_safely(cmd_list, visited_ces=None):
                    if visited_ces is None:
                        visited_ces = set()
                    for cmd in cmd_list:
                        if cmd['code'] == 201:
                            dest = cmd['parameters'][1]
                            if dest > 0 and dest not in distances:
                                distances[dest] = curr_dist + 1
                                queue.append(dest)
                        elif cmd['code'] in [355, 655]:
                            match = re.search(r'reserveTransfer\(\s*(\d+)', cmd.get('parameters', [''])[0])
                            if match:
                                dest = int(match.group(1))
                                if dest > 0 and dest not in distances:
                                    distances[dest] = curr_dist + 1
                                    queue.append(dest)
                        elif cmd['code'] == 117:
                            ce_id = cmd['parameters'][0]
                            if ce_id in self.common_events and ce_id not in visited_ces:
                                visited_ces.add(ce_id)
                                extract_transfers_safely(self.common_events[ce_id].get('list', []), visited_ces)
                
                extract_transfers_safely(page.get('list', []))
                            
        return distances

    def simulate(self):
        print(f"  -> Starting Engine Simulator at Map {self.current_map:03d}")
        
        # Max 25000 phases
        target_ft = None
        for _ in range(25000):
            print(f"  -> [Phase {self.timeline_phase}] Current Map: {self.current_map}")
            self.discovered_maps.add(self.current_map)
            
            # 1. Exhaust all Autoruns
            self.run_autoruns()
            
            if target_ft is not None and self.current_map != target_ft:
                self.fast_travel_blacklist.add(target_ft)
                print(f"  -> Fast Travel to {target_ft:03d} was blocked by an Autorun. Blacklisted.")
            target_ft = None
            
            # 2. Free Roam - Find reachable maps (with BFS distances)
            map_distances = self.find_reachable_maps()
            
            available_events = []
            for rmap in map_distances:
                if rmap not in self.maps: continue
                for ev in self.maps[rmap].get('events', []):
                    if not ev: continue
                    pidx, page = self.get_active_page(rmap, ev)
                    if page and page['trigger'] in [0, 1, 2]:
                        sig = (rmap, ev['id'], pidx)
                        if sig in self.visited_action_events:
                            continue
                            
                        # An event is worth executing if it has ANY meaningful command:
                        # - Text/dialogue (401), State changes (121/122/123), Transfers (201),
                        #   Common event calls (117), or Script (355)
                        # Transfer (201) is REQUIRED here: without it, the engine can't walk to new maps
                        has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                        if has_meaningful_commands:
                            available_events.append((rmap, ev, pidx, page))
                            
            if available_events:
                # Structural-priority sort (generic, no hardcoding):
                # The RPGM condition system (is_page_active) is the TRUE gate for narrative flow.
                # We only add structural/positional hints here:
                # 1. Map BFS distance from current position: closer maps first
                # 2. Current map over maps we'd need to walk to
                # 3. Dialogue presence: story scenes before silent state-changes
                # 4. Active page index: page 0 = story start, high page = deeper progress
                # 5. Event ID: deterministic tie-break
                def event_priority(item):
                    rmap, ev, pidx, page = item
                    distance = map_distances.get(rmap, 999)
                    is_current = 0 if rmap == self.current_map else 1
                    commands = [c['code'] for c in page.get('list', [])]
                    has_dialogue = 0 if 401 in commands else 1
                    has_state = 0 if (121 in commands or 122 in commands) else 1
                    return (distance, is_current, has_dialogue, has_state, pidx, ev['id'])
                
                available_events.sort(key=event_priority)
            
            if not available_events:
                # Fast Travel Check
                found_ft = False
                for dmap in self.discovered_maps:
                    if dmap not in self.maps or dmap in self.fast_travel_blacklist: continue
                    for ev in self.maps[dmap].get('events', []):
                        if not ev: continue
                        pidx, page = self.get_active_page(dmap, ev)
                        if page:
                            sig = (dmap, ev['id'], pidx)
                            is_visited = False
                            if page['trigger'] in [0, 1, 2]:
                                is_visited = sig in self.visited_action_events
                            elif page['trigger'] in [3, 4]:
                                is_visited = sig in self.visited_autoruns
                                
                            if not is_visited:
                                has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                                if has_meaningful_commands:
                                    self.current_map = dmap
                                    target_ft = dmap
                                    found_ft = True
                                    print(f"  -> Fast Travel to Map {dmap:03d} to continue exploration")
                                    break
                    if found_ft: break
                
                if found_ft:
                    continue
                else:
                    if self.consecutive_stuck_time < 24:
                        self.consecutive_stuck_time += 1
                        self.variables[44] += 1 # HOURS(Bakery)
                        if self.variables[44] >= 24:
                            self.variables[44] = 6 # Reset to Morning
                            self.variables[41] += 1 # Days
                            
                        # Manage Evening/Night switches based on HOURS
                        h = self.variables[44]
                        if 5 <= h <= 17: # Day
                            self.switches.discard(24) # Evening
                            self.switches.discard(42) # DK(Evening)
                            self.switches.discard(43) # DK(Night)
                            self.switches.discard(45) # DK(Midnight)
                        elif 17 < h <= 19: # Evening
                            self.switches.add(24)
                            self.switches.add(42)
                            self.switches.discard(43)
                            self.switches.discard(45)
                        else: # Night
                            self.switches.discard(24)
                            self.switches.discard(42)
                            self.switches.add(43)
                            if h >= 22 or h < 5: self.switches.add(45)
                            
                        self.story_scenes.append({
                            "source": "SYSTEM_MACRO",
                            "map_id": self.current_map,
                            "event_id": 0,
                            "event_name": "TIME_ADVANCE",
                            "route": self.route_name,
                            "text": "[SYSTEM] Advanced Time to Day " + str(self.variables[41]) + ", " + str(self.variables[44]).zfill(2) + ":00",
                            "timeline_phase": None,
                            "is_flashback": self.current_map in self.FLASHBACK_MAPS
                        })
                        self.timeline_phase += 1
                        self.fast_travel_blacklist.clear()
                        print(f"  -> System: Time Advance to Day {self.variables[41]}, {self.variables[44]:02d}:00")
                        continue
                    else:
                        # OMNI-KEY
                        unlocked_something = False
                        for dmap in self.discovered_maps:
                            if dmap not in self.maps: continue
                            for ev in self.maps[dmap].get('events', []):
                                if not ev: continue
                                active_pidx, _ = self.get_active_page(dmap, ev)
                                for pidx in range(len(ev['pages']) - 1, -1, -1):
                                    if pidx <= active_pidx:
                                        continue
                                        
                                    page = ev['pages'][pidx]
                                    sig = (dmap, ev['id'], pidx)
                                    if dmap == 132 and ev['id'] == 2:
                                        print(f"DEBUG: Checking Map 132 Event 2 Page {pidx}. Visited: {sig in self.visited_action_events or sig in self.visited_autoruns}")

                                    if sig in self.visited_action_events or sig in self.visited_autoruns:
                                        continue
                                        
                                    missing = self.get_missing_conditions(dmap, ev['id'], page)
                                    has_meaningful_commands = any(c['code'] in [121, 122, 123, 401, 117, 201, 355] for c in page.get('list', []))
                                    if dmap == 132 and ev['id'] == 2:
                                        print(f"DEBUG: Page {pidx} missing: {missing}, meaningful: {has_meaningful_commands}")

                                    if missing and has_meaningful_commands:
                                        backup_switches = set(self.switches)
                                        backup_vars = self.variables.copy()
                                        backup_self_switches = set(self.self_switches)
                                        
                                        break_texts = []
                                        for m in missing:
                                            if m['type'] == 'switch':
                                                self.switches.add(m['id'])
                                                name = self.switch_names.get(m['id'], f"Switch {m['id']}")
                                                break_texts.append(f"Forced {name} = ON")
                                            elif m['type'] == 'variable':
                                                self.variables[m['id']] = m['val']
                                                name = self.variable_names.get(m['id'], f"Variable {m['id']}")
                                                break_texts.append(f"Forced {name} = {m['val']}")
                                            elif m['type'] == 'self_switch':
                                                self.self_switches.add((dmap, ev['id'], m['id']))
                                                break_texts.append(f"Forced Self-Switch {m['id']} = ON")
                                            elif m['type'] == 'item':
                                                self.items.add(m['id'])
                                                break_texts.append(f"Forced Item {m['id']}")
                                            elif m['type'] == 'actor':
                                                self.actors.add(m['id'])
                                                break_texts.append(f"Forced Actor {m['id']}")
                                                
                                        test_pidx, _ = self.get_active_page(dmap, ev)
                                        if test_pidx != pidx:
                                            self.switches = backup_switches
                                            self.variables = backup_vars
                                            self.self_switches = backup_self_switches
                                            continue
                                        
                                        print(f"  -> System: Omni-Key Used! [SYSTEM] Omni-Key used on Map {dmap} Event {ev['id']} Page {pidx}: | " + " | ".join(break_texts))
                                        
                                        text_log = f"[SYSTEM] Omni-Key used on Map {dmap} Event {ev['id']} Page {pidx}:\n" + "\n".join(break_texts)
                                        self.story_scenes.append({
                                            "source": "SYSTEM_MACRO",
                                            "map_id": dmap,
                                            "event_id": ev['id'],
                                            "event_name": "OMNI_KEY",
                                            "route": self.route_name,
                                            "text": text_log,
                                            "timeline_phase": None,
                                            "is_flashback": dmap in [136, 138, 139] or 127 in self.switches
                                        })
                                        self.timeline_phase += 1
                                        self.consecutive_stuck_time = 0
                                        self.fast_travel_blacklist.clear()
                                        self.current_map = dmap # Fast travel to the unlocked event
                                        unlocked_something = True
                                        print(f"  -> System: Omni-Key Used! {text_log.replace(chr(10), ' | ')}")
                                        break
                                if unlocked_something: break
                            if unlocked_something: break
                            
                        if unlocked_something:
                            continue
                        else:
                            print("  -> Game Converged (Omni-Key failed, max time reached).")
                            break
            else:
                self.consecutive_stuck_time = 0
                
            # 5. Apply ONE available event to progress the state
            rmap, ev, pidx, page = available_events[0]
            sig = (rmap, ev['id'], pidx)
            self.visited_action_events.add(sig)
            
            # If the player had to walk to a reachable map to interact
            if rmap != self.current_map:
                self.map_history.append(self.current_map)
                self.current_map = rmap
                
            transfers = self.execute_event_commands(
                rmap, ev, page, 
                f"Map{rmap:03d}_Event{ev['id']}_Page{pidx}"
            )
            self.extract_dialogue(rmap, ev['id'], pidx, page, source_type="EVENT")
            
            # If the event explicitly teleported the player
            if transfers:
                self.map_history.append(self.current_map)
                self.current_map = transfers[-1]
                
            # Increment phase and reset phase-local states
            self.timeline_phase += 1


        print(f"  -> Extracted {len(self.story_scenes)} scenes.")
        
        # Save to JSON
        output_file = os.path.join(self.data_dir, '..', '..', 'data', 'tlas', 'rpgm_scenes_route.json')
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.story_scenes, f, indent=4, ensure_ascii=False)
            
        print(f"  -> Saved output to {output_file}")


if __name__ == "__main__":
    import sys
    print("======================================================================")
    print("  [RPGM Route Tracer] TRUE NARRATIVE ENGINE SIMULATOR (ITERATIVE)")
    print("======================================================================")
    
    # Path hardcoded for execution in the user's workspace
    data_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\www\data"
    
    routes = [
        ('masaru', 'Masaru Route'),
        ('erica', 'Erica Route'),
        ('jords', 'Jords Route'),
        ('rum', 'Rum Route')
    ]
    
    all_scenes = []
    
    for char, rname in routes:
        print(f"\n\n>>> STARTING ROUTE SIMULATION: {rname} (Priority: {char}) <<<")
        emulator = RPGMEmulator(data_dir, target_character=char, route_name=rname)
        emulator.simulate()
        all_scenes.extend(emulator.story_scenes)
        
    output_file = os.path.join(data_dir, '..', '..', 'data', 'tlas', 'rpgm_scenes_all_routes.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        import json
        json.dump(all_scenes, f, indent=4, ensure_ascii=False)
        
    print(f"\n  -> Saved {len(all_scenes)} total scenes across all routes to {output_file}")
