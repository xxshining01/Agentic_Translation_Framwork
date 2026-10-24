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

class RPGMStaticAnalyzer:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.system = {}
        self.maps = {}
        self.map_names = {}
        self.common_events = {}
        self.nodes = {}
        self.switch_names = {}
        self.variable_names = {}
        
    def load_data(self):
        print(f"Loading data from {self.data_dir}")
        with open(os.path.join(self.data_dir, 'System.json'), encoding='utf-8') as f:
            self.system = json.load(f)
            self.switch_names = {i: n for i, n in enumerate(self.system.get('switches', []))}
            self.variable_names = {i: n for i, n in enumerate(self.system.get('variables', []))}
            
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

    def _extract_commands(self, cmd_list, is_common_event=False):
        post_sw_on = set()
        post_sw_off = set()
        post_vars = set()
        pre_sw = set()
        pre_vars = {}
        texts = []
        
        i = 0
        current_speaker = ""
        while i < len(cmd_list):
            c = cmd_list[i]
            code = c['code']
            params = c.get('parameters', [])
            
            if code == 101: # Show Text Header
                current_speaker = params[4] if len(params) > 4 else ""
            elif code == 401: # Show Text Content
                current_text = [clean_text(params[0])]
                while i + 1 < len(cmd_list) and cmd_list[i+1]['code'] == 401:
                    i += 1
                    current_text.append(clean_text(cmd_list[i]['parameters'][0]))
                texts.append((current_speaker, " ".join(current_text)))
            elif code == 102: # Show Choices
                for choice in params[0]:
                    texts.append(("[CHOICE]", clean_text(choice)))
            elif code == 356: # Plugin Command
                if params and isinstance(params[0], str):
                    cmd_str = params[0].strip()
                    if cmd_str.startswith("GabSpriteName "):
                        current_speaker = cmd_str.replace("GabSpriteName ", "").strip()
                    elif cmd_str.startswith("GabText "):
                        text_content = cmd_str.replace("GabText ", "").strip()
                        texts.append((current_speaker, text_content))
                    elif cmd_str == "ClearGab":
                        current_speaker = ""
            elif code == 111: # Conditional Branch
                if params[0] == 0: # Switch
                    pre_sw.add(params[1])
                elif params[0] == 1: # Variable
                    pre_vars[params[1]] = params[3] if len(params) > 3 else 0
            elif code == 121: # Control Switches
                start, end, op = params[0], params[1], params[2]
                for sw in range(start, end + 1):
                    if op == 0: post_sw_on.add(sw)
                    else: post_sw_off.add(sw)
            elif code == 122: # Control Variables
                start, end = params[0], params[1]
                for v in range(start, end + 1):
                    post_vars.add(v)
            elif code == 117: # Call Common Event
                ce_id = params[0]
                if ce_id in self.common_events and not is_common_event:
                    ce_list = self.common_events[ce_id].get('list', [])
                    ce_pre_sw, ce_pre_vars, ce_post_sw_on, ce_post_sw_off, ce_post_vars, ce_texts = self._extract_commands(ce_list, True)
                    pre_sw.update(ce_pre_sw)
                    pre_vars.update(ce_pre_vars)
                    post_sw_on.update(ce_post_sw_on)
                    post_sw_off.update(ce_post_sw_off)
                    post_vars.update(ce_post_vars)
                    texts.extend(ce_texts)
            i += 1
            
        return pre_sw, pre_vars, post_sw_on, post_sw_off, post_vars, texts

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
                    
                    if c.get('switch1Valid'): pre_sw.add(c.get('switch1Id'))
                    if c.get('switch2Valid'): pre_sw.add(c.get('switch2Id'))
                    if c.get('variableValid'): pre_vars[c.get('variableId')] = c.get('variableValue')
                    
                    cmd_pre_sw, cmd_pre_vars, post_sw_on, post_sw_off, post_vars, texts = self._extract_commands(page.get('list', []))
                    pre_sw.update(cmd_pre_sw)
                    pre_vars.update(cmd_pre_vars)
                    
                    if texts or post_sw_on or post_vars:
                        node_id = f"M{map_id}_E{ev_id}_P{page_idx}"
                        self.nodes[node_id] = {
                            "id": node_id,
                            "map": self.map_names.get(map_id, f"Map{map_id}"),
                            "event": ev_name,
                            "page": page_idx,
                            "pre_switches": pre_sw,
                            "pre_variables": pre_vars,
                            "post_switches_on": post_sw_on,
                            "post_switches_off": post_sw_off,
                            "post_variables": post_vars,
                            "texts": texts
                        }

        # Process All Common Events (including those triggered by Items/Skills)
        for ce_id, ce in self.common_events.items():
            cmd_pre_sw, cmd_pre_vars, post_sw_on, post_sw_off, post_vars, texts = self._extract_commands(ce.get('list', []))
            
            pre_sw = cmd_pre_sw
            pre_vars = cmd_pre_vars
            if ce.get('trigger', 0) > 0 and ce.get('switchId', 0) > 0:
                pre_sw.add(ce.get('switchId'))
                
            # If it has meaningful actions. Include even if trigger == 0 (e.g. Item/Skill triggers)
            if texts or post_sw_on or post_vars:
                node_id = f"CE_{ce_id}"
                self.nodes[node_id] = {
                    "id": node_id,
                    "map": "Common Events",
                    "event": ce.get('name', 'Unknown'),
                    "page": 0,
                    "pre_switches": pre_sw,
                    "pre_variables": pre_vars,
                    "post_switches_on": post_sw_on,
                    "post_switches_off": post_sw_off,
                    "post_variables": post_vars,
                    "texts": texts
                }

    def build_dependency_graph(self):
        print("Building Dependency Graph...")
        switch_providers = defaultdict(list)
        for nid, node in self.nodes.items():
            for sw in node['post_switches_on']:
                switch_providers[sw].append(nid)
                
        self.adj_list = defaultdict(set)
        for nid, node in self.nodes.items():
            for sw in node['pre_switches']:
                for provider_id in switch_providers.get(sw, []):
                    if provider_id != nid:
                        self.adj_list[nid].add(provider_id)
                        self.adj_list[provider_id].add(nid)

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
                        "variables": [f"{v}: {self.variable_names.get(v, '')} >= {val}" for v, val in node['pre_variables'].items()]
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
    analyzer = RPGMStaticAnalyzer(data_dir)
    analyzer.load_data()
    analyzer.parse_events()
    analyzer.build_dependency_graph()
    analyzer.export_components(r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\data\tlas\rpgm_static_routes_v2.json")
