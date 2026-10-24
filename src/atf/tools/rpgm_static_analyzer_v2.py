import os
import json
import glob
import re
from collections import defaultdict

def clean_text(t):
    t = re.sub(r'\\n<\w+:>', '', t)
    t = re.sub(r'<\w+:>', '', t)
    t = re.sub(r'\\[a-zA-Z]+(\[[^\]]*\])?', '', t)
    t = re.sub(r'\\[\.\|\>\<\\!\{\}]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

class RPGMStaticAnalyzerV2:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.system = {}
        self.maps = {}
        self.map_names = {}
        self.common_events = {}
        self.nodes = {}
        self.switch_names = {}
        self.variable_names = {}
        self.item_names = {}
        
    def load_data(self):
        print(f"Loading data from {self.data_dir}")
        with open(os.path.join(self.data_dir, 'System.json'), encoding='utf-8') as f:
            self.system = json.load(f)
            self.switch_names = {i: n for i, n in enumerate(self.system.get('switches', []))}
            self.variable_names = {i: n for i, n in enumerate(self.system.get('variables', []))}
            
        with open(os.path.join(self.data_dir, 'Items.json'), encoding='utf-8') as f:
            items = json.load(f)
            self.item_names = {i['id']: i['name'] for i in items if i and 'name' in i}
            
        with open(os.path.join(self.data_dir, 'MapInfos.json'), encoding='utf-8') as f:
            for m in json.load(f):
                if m: self.map_names[m['id']] = m.get('name', '')
                
        for f in glob.glob(os.path.join(self.data_dir, 'Map[0-9][0-9][0-9].json')):
            map_id = int(os.path.basename(f)[3:6])
            with open(f, encoding='utf-8') as m:
                d = json.load(m)
                if isinstance(d, dict): self.maps[map_id] = d
                
        with open(os.path.join(self.data_dir, 'CommonEvents.json'), encoding='utf-8') as f:
            self.common_events = {e['id']: e for e in json.load(f) if e}

    def _extract_commands(self, cmd_list, map_id, ev_id):
        post_sw_on = set()
        post_sw_off = set()
        post_vars = set()
        post_self_sw_on = set()
        post_items = set()
        
        texts = []
        
        # We track preconditions dynamically inherited from `111` Conditional Branches
        # condition_stack maps indent -> list of conditions applied at that indent
        condition_stack = defaultdict(list)
        active_conditions = {
            'switches': set(),
            'variables': set(),
            'self_switches': set(),
            'items': set()
        }
        
        # When text is found, we attach the currently active conditions to it.
        # But for graph simplicity, if an Event Page has ANY text under a condition,
        # we consider the entire Page to "require" that condition.
        page_requires_sw = set()
        page_requires_var = set()
        page_requires_self_sw = set()
        page_requires_item = set()
        
        current_speaker = ""
        
        def update_active_conditions(indent):
            active_conditions['switches'].clear()
            active_conditions['variables'].clear()
            active_conditions['self_switches'].clear()
            active_conditions['items'].clear()
            for ind in range(indent + 1):
                for cond in condition_stack[ind]:
                    if cond[0] == 'sw': active_conditions['switches'].add(cond[1])
                    elif cond[0] == 'var': active_conditions['variables'].add(cond[1])
                    elif cond[0] == 'self_sw': active_conditions['self_switches'].add(cond[1])
                    elif cond[0] == 'item': active_conditions['items'].add(cond[1])
        
        i = 0
        while i < len(cmd_list):
            c = cmd_list[i]
            code = c['code']
            indent = c['indent']
            params = c.get('parameters', [])
            
            # Update active conditions for this indent level
            # Clear conditions deeper than current indent
            keys_to_remove = [k for k in condition_stack.keys() if k > indent]
            for k in keys_to_remove: del condition_stack[k]
            update_active_conditions(indent)

            if code == 111: # Conditional Branch
                cond_type = params[0]
                cond = None
                if cond_type == 0: cond = ('sw', params[1])
                elif cond_type == 1: cond = ('var', params[1])
                elif cond_type == 2: cond = ('self_sw', f"{map_id}_{ev_id}_{params[1]}")
                elif cond_type == 8: cond = ('item', params[1])
                elif cond_type == 12: # Script
                    script = params[1]
                    # Parse Check.is_any(161, ...)
                    match = re.search(r'Check\.is_any\((\d+)', script)
                    if match: cond = ('var', int(match.group(1)))
                
                if cond:
                    condition_stack[indent].append(cond)
                    
            elif code == 101: # Show Text Header
                current_speaker = params[4] if len(params) > 4 else ""
            elif code == 401: # Show Text Content
                texts.append((current_speaker, clean_text(params[0])))
                page_requires_sw.update(active_conditions['switches'])
                page_requires_var.update(active_conditions['variables'])
                page_requires_self_sw.update(active_conditions['self_switches'])
                page_requires_item.update(active_conditions['items'])
            elif code == 102: # Show Choices
                for choice in params[0]:
                    texts.append(("[CHOICE]", clean_text(choice)))
                    page_requires_sw.update(active_conditions['switches'])
                    page_requires_var.update(active_conditions['variables'])
                    page_requires_self_sw.update(active_conditions['self_switches'])
                    page_requires_item.update(active_conditions['items'])
            elif code == 356: # Plugin Command
                if params and len(params) > 0:
                    pcmd = str(params[0])
                    if pcmd.startswith("GabText"):
                        gab_text = pcmd.replace("GabText", "").strip()
                        if gab_text.startswith(":"): gab_text = gab_text[1:].strip()
                        texts.append(("[GAB]", clean_text(gab_text)))
                        page_requires_sw.update(active_conditions['switches'])
                        page_requires_var.update(active_conditions['variables'])
                        page_requires_self_sw.update(active_conditions['self_switches'])
                        page_requires_item.update(active_conditions['items'])
            elif code == 121: # Control Switches
                start, end, op = params[0], params[1], params[2]
                for sw in range(start, end + 1):
                    if op == 0: post_sw_on.add(sw)
                    else: post_sw_off.add(sw)
            elif code == 122: # Control Variables
                start, end = params[0], params[1]
                for v in range(start, end + 1):
                    post_vars.add(v)
            elif code == 123: # Control Self Switches
                sw_letter = params[0]
                op = params[1]
                if op == 0: post_self_sw_on.add(f"{map_id}_{ev_id}_{sw_letter}")
            elif code == 126: # Change Items
                item_id = params[0]
                op = params[1] # 0 = increase, 1 = decrease
                if op == 0: post_items.add(item_id)
            elif code in [355, 655]: # Script Calls
                if params and len(params) > 0:
                    script = str(params[0])
                    # Parse $gameSwitches.setValue(10, true)
                    for m in re.finditer(r'\$gameSwitches\.setValue\((\d+),\s*(true|false)\)', script):
                        sw_id = int(m.group(1))
                        is_true = m.group(2) == 'true'
                        if is_true: post_sw_on.add(sw_id)
                        else: post_sw_off.add(sw_id)
                    # Parse $gameSelfSwitches.setValue([mapId, evId, 'A'], true)
                    for m in re.finditer(r'\$gameSelfSwitches\.setValue\(\[(\d+),\s*(\d+),\s*\'([A-D])\'\],\s*(true|false)\)', script):
                        m_id = int(m.group(1))
                        e_id = int(m.group(2))
                        sw_ch = m.group(3)
                        is_true = m.group(4) == 'true'
                        if is_true: post_self_sw_on.add(f"{m_id}_{e_id}_{sw_ch}")
            i += 1
            
        return {
            "post_sw_on": post_sw_on,
            "post_sw_off": post_sw_off,
            "post_vars": post_vars,
            "post_self_sw_on": post_self_sw_on,
            "post_items": post_items,
            "texts": texts,
            "page_requires_sw": page_requires_sw,
            "page_requires_var": page_requires_var,
            "page_requires_self_sw": page_requires_self_sw,
            "page_requires_item": page_requires_item
        }

    def parse_events(self):
        print("Parsing Event Pages...")
        for map_id, map_data in self.maps.items():
            for ev in map_data.get('events', []):
                if not ev: continue
                ev_id = ev['id']
                ev_name = ev.get('name', 'Unknown')
                
                for page_idx, page in enumerate(ev.get('pages', [])):
                    c = page.get('conditions', {})
                    pre_sw = set()
                    pre_vars = {}
                    pre_self_sw = set()
                    pre_items = set()
                    
                    if c.get('switch1Valid'): pre_sw.add(c.get('switch1Id'))
                    if c.get('switch2Valid'): pre_sw.add(c.get('switch2Id'))
                    if c.get('variableValid'): pre_vars[c.get('variableId')] = c.get('variableValue')
                    if c.get('selfSwitchValid'): pre_self_sw.add(f"{map_id}_{ev_id}_{c.get('selfSwitchCh')}")
                    if c.get('itemValid'): pre_items.add(c.get('itemId'))
                    
                    extracted = self._extract_commands(page.get('list', []), map_id, ev_id)
                    
                    # Merge page conditions with in-code conditions
                    pre_sw.update(extracted['page_requires_sw'])
                    for v in extracted['page_requires_var']: pre_vars[v] = 1 # We just know it's required
                    pre_self_sw.update(extracted['page_requires_self_sw'])
                    pre_items.update(extracted['page_requires_item'])
                    
                    if extracted['texts'] or extracted['post_sw_on'] or extracted['post_vars'] or extracted['post_self_sw_on'] or extracted['post_items']:
                        node_id = f"M{map_id}_E{ev_id}_P{page_idx}"
                        self.nodes[node_id] = {
                            "id": node_id,
                            "map": self.map_names.get(map_id, f"Map{map_id}"),
                            "event": ev_name,
                            "page": page_idx,
                            "pre_switches": pre_sw,
                            "pre_variables": pre_vars,
                            "pre_self_switches": pre_self_sw,
                            "pre_items": pre_items,
                            "post_switches_on": extracted['post_sw_on'],
                            "post_variables": extracted['post_vars'],
                            "post_self_switches_on": extracted['post_self_sw_on'],
                            "post_items": extracted['post_items'],
                            "texts": extracted['texts']
                        }

    def build_dependency_graph(self):
        print("Building Dependency Graph...")
        
        switch_providers = defaultdict(list)
        self_switch_providers = defaultdict(list)
        item_providers = defaultdict(list)
        
        for nid, node in self.nodes.items():
            for sw in node['post_switches_on']: switch_providers[sw].append(nid)
            for ssw in node['post_self_switches_on']: self_switch_providers[ssw].append(nid)
            for itm in node['post_items']: item_providers[itm].append(nid)
                
        self.adj_list = defaultdict(set)
        for nid, node in self.nodes.items():
            for sw in node['pre_switches']:
                for p_id in switch_providers.get(sw, []):
                    if p_id != nid:
                        self.adj_list[nid].add(p_id)
                        self.adj_list[p_id].add(nid)
            for ssw in node['pre_self_switches']:
                for p_id in self_switch_providers.get(ssw, []):
                    if p_id != nid:
                        self.adj_list[nid].add(p_id)
                        self.adj_list[p_id].add(nid)
            for itm in node['pre_items']:
                for p_id in item_providers.get(itm, []):
                    if p_id != nid:
                        self.adj_list[nid].add(p_id)
                        self.adj_list[p_id].add(nid)
                        
    def cluster_components(self):
        print("Clustering Story Components (WCC)...")
        visited = set()
        components = []
        
        for nid in self.nodes.keys():
            if nid not in visited and len(self.nodes[nid]['texts']) > 0:
                comp_nodes = []
                queue = [nid]
                visited.add(nid)
                
                while queue:
                    curr = queue.pop(0)
                    if len(self.nodes[curr]['texts']) > 0:
                        comp_nodes.append(self.nodes[curr])
                    for neighbor in self.adj_list[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
                if comp_nodes:
                    components.append(comp_nodes)
                    
        print(f"Found {len(components)} distinct story components.")
        return components

    def export_components(self, output_path):
        components = self.cluster_components()
        
        export_data = []
        for i, comp in enumerate(components):
            comp.sort(key=lambda x: x['id'])
            comp_scenes = []
            for node in comp:
                comp_scenes.append({
                    "id": node['id'],
                    "location": f"{node['map']} - {node['event']} (Page {node['page']})",
                    "pre_conditions": {
                        "switches": [f"{sw}: {self.switch_names.get(sw, '')}" for sw in node['pre_switches']],
                        "variables": [f"{v}: {self.variable_names.get(v, '')} >= {val}" for v, val in node['pre_variables'].items()],
                        "self_switches": list(node['pre_self_switches']),
                        "items": [f"{itm}: {self.item_names.get(itm, '')}" for itm in node['pre_items']]
                    },
                    "dialogues": [{"speaker": s, "text": t} for s, t in node['texts']]
                })
            
            export_data.append({
                "cluster_id": f"Route_Cluster_{i+1}",
                "total_scenes": len(comp_scenes),
                "scenes": comp_scenes
            })
            
        export_data.sort(key=lambda x: x['total_scenes'], reverse=True)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False)
        print(f"Exported {len(export_data)} clusters to {output_path}")

if __name__ == "__main__":
    data_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\www\data"
    analyzer = RPGMStaticAnalyzerV2(data_dir)
    analyzer.load_data()
    analyzer.parse_events()
    analyzer.build_dependency_graph()
    analyzer.export_components(r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\data\tlas\rpgm_static_routes_v2.json")
