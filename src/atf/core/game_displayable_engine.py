#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATF Game Displayable Engine
===========================
Automated Game Data Analyzer & Displayable/Translatable Filter.
Compliant with SDD-010, SAD-014, and ADR-035.

Features:
1. RPG Maker JSON Scanner: Reads www/data/*.json to classify Role and Displayable (Yes/No).
2. Plugin Dialogue Aware: Recognizes D_TEXT (DTextPicture.js) and plugin dialogues as Displayable.
3. Heuristic Non-Displayable Classifier: Detects variables, switches, script calls, event labels,
   and developer comments for 5-column CSVs without crashing the game engine.
4. Smart D_TEXT Parser: Extracts inner Japanese text from D_TEXT <Text> <Size>, enables Thai translation,
   and seamlessly reconstructs valid RPG Maker plugin command syntax.
"""

import os
import re
import json
from collections import defaultdict
from typing import Dict, Set, Tuple, Optional, Any, List


ROLE_PRIORITY = {
    "Dialogue/Story": 1,
    "Plugin Dialogue": 2,
    "Choices Option": 3,
    "Choice Branch": 4,
    "System Term": 5,
    "System Message": 5,
    "Message Speaker Name": 6,
    "Entity Name": 7,
    "Description": 8,
    "Profile": 9,
    "Battle Message": 10,
    "Map Display Name": 11,
    "Change Name": 12,
    "Change Nickname": 12,
    "Change Profile": 12,
    "Developer Comment": 13,
    "Script Code": 14,
    "Plugin Command": 15,
    "Internal Variable/Switch": 16,
    "Asset Name": 17,
    "Event Name": 18,
    "Common Event Name": 18,
    "Troop Name": 18,
    "Control Variables": 19,
    "Note/Metadata": 20,
    "Macro / Image": 21,
    "Field: ": 22,
    "List Item": 23,
    "System Setting": 24,
    "Unknown": 99
}

D_TEXT_TIME_MAP = {
    "早朝": "เช้าตรู่",
    "朝": "เช้า",
    "昼": "กลางวัน",
    "夕方": "เย็น",
    "夜": "กลางคืน",
    "夜中": "กลางดึก"
}


def _resolve_d_text_day(token: str) -> Optional[str]:
    """Dynamically translates any day marker (e.g. 1日目 -> วันที่ 1, 30日目 -> วันที่ 30)."""
    m = re.match(r"^(\d+)日目$", token)
    if m:
        return f"วันที่ {m.group(1)}"
    return None


class GameDisplayableEngine:
    def __init__(self, game_data_dir: Optional[str] = None):
        self.game_data_dir = game_data_dir
        self.json_cache: Dict[str, Dict[str, Set[Tuple[str, str]]]] = {}
        self.global_roles_map: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        self.is_loaded = False

        if game_data_dir and os.path.exists(game_data_dir):
            self.load_game_data(game_data_dir)

    @staticmethod
    def is_just_macro(text: str) -> bool:
        t = text.strip()
        cleaned = re.sub(r'\\[a-zA-Z]+\[[^\]]*\]', '', t)
        cleaned = re.sub(r'\\[!\\.|><\^]', '', cleaned)
        cleaned = re.sub(r'\\n', '', cleaned)
        return not bool(re.search(r'\w|[\u3040-\u30ff\u4e00-\u9faf]', cleaned))

    @staticmethod
    def parse_d_text(text: str) -> Tuple[bool, str, str, str]:
        """
        Parses RPG Maker D_TEXT command: 'D_TEXT <InnerString> <Size>'
        Returns: (is_d_text, prefix, inner_text, suffix)
        Example: 'D_TEXT 2日目　夕方 32' -> (True, 'D_TEXT ', '2日目　夕方', ' 32')
        """
        if not text:
            return False, "", "", ""
        m = re.match(r'^(D_TEXT\s+)(.+?)(\s+\d+)?$', text.strip(), re.IGNORECASE)
        if m:
            prefix = m.group(1)
            inner = m.group(2)
            suffix = m.group(3) or ""
            return True, prefix, inner, suffix
        return False, "", text, ""

    @staticmethod
    def translate_d_text_determinstic(inner_text: str) -> Optional[str]:
        """
        Deterministically translates standard RPG Maker date/time indicators:
        e.g. '1日目　夕方' -> 'วันที่ 1 เย็น'
        """
        cleaned = inner_text.replace('\u3000', ' ').strip()
        parts = cleaned.split()
        if len(parts) == 2:
            day_part, time_part = parts[0], parts[1]
            th_day = _resolve_d_text_day(day_part)
            th_time = D_TEXT_TIME_MAP.get(time_part)
            if th_day and th_time:
                return f"{th_day} {th_time}"
        elif len(parts) == 1:
            th_day = _resolve_d_text_day(parts[0])
            if th_day:
                return th_day
            if parts[0] in D_TEXT_TIME_MAP:
                return D_TEXT_TIME_MAP[parts[0]]
        return None

    def _build_string_roles(self, data: Any, filename: str, roles_map: Dict[str, Set[Tuple[str, str]]], context: str = ""):
        if isinstance(data, dict):
            if "code" in data and "parameters" in data:
                code = data["code"]
                for p in data["parameters"]:
                    if isinstance(p, str) and p.strip():
                        role = "Event Command"
                        display = "No"

                        if code in (401, 405):  # Show Text
                            role = "Dialogue/Story"
                            display = "Yes"
                        elif code == 102:  # Show Choices
                            role = "Choices Option"
                            display = "Yes"
                            if isinstance(p, list):
                                for choice_text in p:
                                    if isinstance(choice_text, str) and choice_text.strip():
                                        c_role = "Macro / Image" if self.is_just_macro(choice_text) else role
                                        c_disp = "No" if self.is_just_macro(choice_text) else display
                                        roles_map[choice_text.strip()].add((c_role, c_disp))
                            continue
                        elif code == 402:  # When [Choice]
                            role = "Choice Branch"
                            display = "Yes"
                        elif code in (108, 408):  # Comment
                            role = "Developer Comment"
                            display = "No"
                        elif code in (355, 655):  # Script Call
                            role = "Script Code"
                            display = "No"
                        elif code == 356:  # Plugin Command
                            p_lower = p.lower()
                            if p_lower.startswith("d_text"):
                                role = "Plugin Dialogue"
                                display = "Yes"  # DTextPicture.js displays text on screen!
                            elif p_lower.startswith("gabtext") or p_lower.startswith("gabname") or p_lower.startswith("msg"):
                                role = "Plugin Dialogue"
                                display = "Yes"
                            else:
                                role = "Plugin Command"
                                display = "No"
                        elif code == 122:  # Control Variables
                            role = "Control Variables"
                            display = "No"
                        elif code == 320:  # Change Name
                            role = "Change Name"
                            display = "Yes"
                        elif code == 324:  # Change Nickname
                            role = "Change Nickname"
                            display = "Yes"
                        elif code == 325:  # Change Profile
                            role = "Change Profile"
                            display = "Yes"
                        elif code == 101:  # Show Text Header / Speaker
                            role = "Message Speaker Name"
                            display = "Yes"

                        if display == "Yes" and self.is_just_macro(p):
                            role = "Macro / Image"
                            display = "No"

                        roles_map[p.strip()].add((role, display))

            for k, v in data.items():
                if isinstance(v, str) and v.strip():
                    k_lower = k.lower()
                    role = f"Field: {k}"
                    display = "No"

                    if k_lower == "name":
                        if filename.startswith("Map") and filename != "MapInfos":
                            role = "Event Name"
                            display = "No"
                        elif filename == "CommonEvents":
                            role = "Common Event Name"
                            display = "No"
                        elif filename == "Troops":
                            role = "Troop Name"
                            display = "No"
                        else:
                            role = "Entity Name"
                            display = "Yes"
                    elif k_lower == "displayname" and filename.startswith("Map"):
                        role = "Map Display Name"
                        display = "Yes"
                    elif k_lower == "description":
                        role = "Description"
                        display = "Yes"
                    elif k_lower == "note":
                        role = "Note/Metadata"
                        display = "No"
                    elif k_lower == "profile":
                        role = "Profile"
                        display = "Yes"
                    elif k_lower.startswith("message"):
                        role = "Battle Message"
                        display = "Yes"
                    elif filename == "System":
                        if k_lower == "gametitle":
                            role = "Game Title"
                            display = "Yes"
                        elif k_lower == "currencyunit":
                            role = "System Term"
                            display = "Yes"
                        elif context == "messages":
                            role = "System Message"
                            display = "Yes"
                    elif k in ["bgm", "bgs", "me", "se", "characterName", "faceName", "battlerName", "parallaxName", "title1Name", "title2Name"]:
                        role = "Asset Name"
                        display = "No"

                    roles_map[v.strip()].add((role, display))
                else:
                    self._build_string_roles(v, filename, roles_map, context=k)

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str) and item.strip():
                    role = "List Item"
                    display = "No"

                    if filename == "System":
                        if context in ["switches", "variables"]:
                            role = "Internal Variable/Switch"
                            display = "No"
                        elif context in [
                            "terms", "basic", "commands", "params", "messages",
                            "elements", "skillTypes", "weaponTypes", "armorTypes", "equipTypes"
                        ]:
                            role = "System Term"
                            display = "Yes"

                    roles_map[item.strip()].add((role, display))
                else:
                    self._build_string_roles(item, filename, roles_map, context=context)

    def load_game_data(self, data_dir: str):
        self.game_data_dir = data_dir
        json_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]

        for f_name in json_files:
            name = f_name[:-5]
            f_path = os.path.join(data_dir, f_name)
            try:
                with open(f_path, "r", encoding="utf-8-sig", errors="ignore") as jf:
                    data = json.load(jf)
                    roles_map = defaultdict(set)
                    self._build_string_roles(data, name, roles_map)
                    self.json_cache[name] = roles_map
                    for text_key, rset in roles_map.items():
                        self.global_roles_map[text_key].update(rset)
            except Exception:
                pass

        self.is_loaded = True

    def get_best_role(self, roles_set: Set[Tuple[str, str]]) -> Tuple[str, str]:
        if not roles_set:
            return "Unknown", "No"
        sorted_roles = sorted(roles_set, key=lambda x: ROLE_PRIORITY.get(x[0], 99))
        return sorted_roles[0]

    def evaluate_displayable(
        self,
        orig_text: str,
        filename: str = "",
        role: str = "",
        explicit_displayable: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Comprehensive evaluation whether a given text is Displayable ('Yes' / 'No').
        Returns: (is_displayable, role_name, reason)
        """
        text = orig_text.strip()
        if not text:
            return False, "Empty Text", "Blank string"

        # 1. Explicit Displayable column provided (e.g. from 8-column CSV)
        if explicit_displayable:
            disp_lower = explicit_displayable.strip().lower()
            if disp_lower == "yes":
                return True, role or "Dialogue/Story", "Explicit Displayable column is Yes"
            elif disp_lower == "no":
                return False, role or "Internal System", "Explicit Displayable column is No"

        # 2. Check D_TEXT plugin command
        is_dt, _, inner_txt, _ = self.parse_d_text(text)
        if is_dt:
            return True, "Plugin Dialogue", "D_TEXT visual screen title"

        # 3. Game JSON Exact Lookup
        if self.is_loaded:
            file_key = filename.replace(".json", "").strip() if filename else ""
            if file_key in ("Actors", "Classes", "Items", "Skills", "Weapons", "Armors", "Enemies", "States"):
                # Database rows extracted for localization are player-facing entity names/descriptions, not internal asset files
                if not text.lower().endswith(('.png', '.ogg', '.wav', '.m4a', '.json')):
                    return True, "Entity Name", f"Database Entity ({file_key})"
            elif file_key and file_key in self.json_cache and text in self.json_cache[file_key]:
                best_r, best_disp = self.get_best_role(self.json_cache[file_key][text])
                return (best_disp == "Yes"), best_r, f"Exact Game JSON match ({file_key})"
            elif text in self.global_roles_map:
                best_r, best_disp = self.get_best_role(self.global_roles_map[text])
                return (best_disp == "Yes"), best_r, "Global Game JSON match"

        # 4. Strict Heuristic Rules (Non-Displayable Detection)
        # 4.1 Internal RPG Maker Script Calls
        if re.search(r'^\s*(\$gameVariables|\$gameSwitches|\$gameParty|\$gameActors|SceneManager|AudioManager|ImageManager|Input\.|\$data\w+)', text):
            return False, "Script Code", "JavaScript RPG Maker script expression"

        # 4.2 Internal Variables / Switches / Assignments
        if re.match(r'^(s\[\d+\]|v\[\d+\]|[a-zA-Z_]\w*\s*=\s*[\d\w\'\"]+)', text):
            return False, "Internal Variable/Switch", "Variable or Switch Assignment"

        # 4.3 Engine Event Codes & Map Labels
        if re.match(r'^(EV\d+|CommonEvent\d*|Actor\d+|Troop\d+|Label:\w+|Jump to Label)', text, re.IGNORECASE):
            return False, "Event Name", "Engine internal event/map label"

        # 4.4 Developer Comments
        if re.match(r'^(//|/\*|#|\/\/|Developer Comment:)', text):
            return False, "Developer Comment", "Developer source comment"

        # 4.5 Asset Filenames
        if re.search(r'\.(png|ogg|m4a|wav|mp3|rpgmvp|rpgmvo|json)$', text, re.IGNORECASE):
            return False, "Asset Name", "Audio or Image asset path"

        # 4.6 Pure Macros or Control Code only without letters
        if self.is_just_macro(text):
            return False, "Macro / Image", "Pure engine control codes without characters"

        # 5. Default: If it contains Japanese characters or conversational quotes, it is Displayable
        if re.search(r'[\u3040-\u30ff\u4e00-\u9faf]', text) or re.search(r'^[「『【<]', text):
            return True, role or "Dialogue/Story", "Detected narrative dialogue"

        return True, role or "Dialogue/Story", "Default translatable text"

