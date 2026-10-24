"""
TLAS v4.0 Parameter Consensus & Deterministic Pronoun Resolver
Architecture: SAD-010 | Design: SDD-010, SDD-011 | ADR: ADR-015

หน้าที่:
1. กวาดอ่านผลการสกัดจาก data/tlas/extractions/*.json ทั้งโปรเจกต์
2. ทำ Statistical Consensus (Normalized Weighted Average & Majority Voting)
3. รัน Priority Rule Engine แมปสรรพนามบุรุษที่ 1, 2, 3 (self, target, third_person) และหางเสียง
4. บันทึก Profile Clean V4 ลง data/tlas/profiles/<Name>.json (Atomic Write, ไร้ timeline_states)
5. Export สรุปตารางความสัมพันธ์ทั้งระบบ data/tlas/global_pronoun_matrix.json
"""

import os
import sys
import glob
import json
import re
import logging
from collections import defaultdict, Counter
from typing import Dict, List, Any, Optional

# Ensure project root in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

logger = logging.getLogger("tlas_consensus_engine")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [ConsensusEngine] %(message)s',
    handlers=[
        logging.FileHandler("tlas_consensus_engine.log", encoding="utf-8", mode="a"),
        logging.StreamHandler(sys.stdout)
    ]
)

# ==============================================================================
# Name Semantic Lexicon & Canonical Story Identity Tables (Universal Framework)
# ==============================================================================
MALE_NAME_KEYWORDS = {
    "man", "men", "boy", "guy", "guys", "father", "dad", "papa", "husband", "son",
    "brother", "uncle", "grandfather", "grandpa", "priest", "policeman", "policemen",
    "lumberjack", "fisherman", "fratboy", "mr", "sir", "king", "prince", "male",
    "gentleman", "groom", "playboy", "host", "courier", "barfer", "monk", "butler",
    "actor", "waiter", "lord", "emperor", "duke", "count", "baron", "thug", "ruffian"
}

FEMALE_NAME_KEYWORDS = {
    "woman", "women", "girl", "girls", "lady", "ladies", "mother", "mom", "mama",
    "wife", "daughter", "sister", "aunt", "grandmother", "grandma", "nun", "policewoman",
    "maid", "waitress", "hostess", "mrs", "ms", "miss", "queen", "princess", "female",
    "bride", "actress", "madam", "headmistress", "housewife", "salarylady",
    "fangirl", "hooker", "escort"
}

CHILD_NAME_KEYWORDS = {"little girl", "young girl", "little boy", "young boy", "child", "kid", "baby"}
ELDER_NAME_KEYWORDS = {"old man", "old lady", "elder", "senior", "grandpa", "grandma", "veteran"}
TEEN_NAME_KEYWORDS = {"jk", "student", "high school"}

# Universal Acoustic and Voice Entity Resolution Pattern
VOICE_STEM_REGEX = re.compile(
    r'^(?:the\s+)?(?P<stem>.+?)(?:\'s|\s+of|\s+from)?\s+(?:voice|whisper|groan)(?:\s+(?:from|inside|behind).*)?$',
    re.IGNORECASE
)

EXPLICIT_ALIAS_REMAP = {
    # Riley (Typo fix)
    "rylie": "Riley",

    # Sir Timonthy / Sir Timothy
    "sir timothy": "Sir Timonthy",
    "sir timonthy": "Sir Timonthy",
    "timonthy": "Sir Timonthy",
    "timothy": "Sir Timonthy",
    # Masaru (Father)
    "mr.masaru": "Masaru",
    "mr. masaru": "Masaru",
    "masarua": "Masaru",
    "nasaru": "Masaru",

    # Masgolf (Sir Masgolf - High society noble)
    "sir masgolf": "Masgolf",
    "maso golf": "Masgolf",
    "musgolf": "Masgolf",
    "masgolf": "Masgolf",
    # The Earl
    "earl": "The Earl",
    "the earl": "The Earl",
    "the earl?": "The Earl",
    "the earl": "The Earl",
    # Jordan
    "jordan's voice from inside": "Jordan",
    "jordansmoke": "Jordan",
    # Ritchie
    "boy ritche": "Ritchie",
    "boy ritchie": "Ritchie",
    "kid ritchie": "Ritchie",
    # KJ / Jikan CEO
    "jikan ceo": "KJ",
    "jikan's ceo": "KJ",
    "kj(jikan's ceo)": "KJ",
    "kj": "KJ",
    # Shion
    "shion and erica": "Shion",
    "shion?": "Shion",
    "shionbeach1": "Shion",
    "shionapron": "Shion",
    "shionnewer": "Shion",
    "shionnewera": "Shion",
    "shionnewerb": "Shion",
    "shionnewerc": "Shion",
    "shionthree": "Shion",
    "shionfour": "Shion",
    "shiontwo": "Shion",
    "shionbraless": "Shion",
    "shionkimono": "Shion",
    "shionextreme": "Shion",
    "shionnss": "Shion",
    "shionnude": "Shion",
    # Dan
    "dan": "Dan",
    # Erica
    "ericabeach": "Erica",
    # Jinnie
    "jinniea": "Jinnie",
    "jinnieb": "Jinnie",
    # Alisa
    "alisa?": "Alisa",
    # Yearl
    "y..rl": "Yearl",
    "yearling": "Yearl",
    # Shivers
    "shiver's voice": "Shivers",
    # Flugee
    "fulgee": "Flugee",
    # Godmother
    "godmother": "Godmother",
}

def infer_identity_from_name(name: str) -> dict:
    """Extracts high-confidence gender and age hints directly from character names."""
    name_lower = name.lower()
    words = set(re.findall(r'\b\w+\b', name_lower))
    inferred = {"gender": None, "age": None}
    
    # 1. Gender from name
    has_male = bool(words & MALE_NAME_KEYWORDS)
    has_female = bool(words & FEMALE_NAME_KEYWORDS)
    
    if has_female and not has_male:
        inferred["gender"] = "FEMALE"
    elif has_male and not has_female:
        inferred["gender"] = "MALE"
    elif has_male and has_female:
        # Resolve compound possession: e.g. "Fruity Girl's Brother" -> Brother
        if any(w in words for w in ["brother", "father", "husband", "son", "boy", "man"]):
            inferred["gender"] = "MALE"
        elif any(w in words for w in ["sister", "mother", "wife", "daughter", "girl", "lady"]):
            inferred["gender"] = "FEMALE"

    # 2. Age from name
    if any(k in name_lower for k in ELDER_NAME_KEYWORDS):
        inferred["age"] = "ELDER"
    elif any(k in name_lower for k in CHILD_NAME_KEYWORDS):
        if not any(w in words for w in ["hooker", "escort", "call"]):
            inferred["age"] = "CHILD"
    elif any(k in name_lower for k in TEEN_NAME_KEYWORDS):
        inferred["age"] = "TEEN"

    return inferred


def is_invalid_or_disposable_speaker(name: str) -> bool:
    """Identifies anonymous placeholders, invalid symbols, or disposable system names."""
    if not name or not str(name).strip():
        return True
    clean = str(name).strip()
    clean_lower = clean.lower()

    # 1. Question marks only or placeholder symbols (e.g. "???", "?", "----")
    if re.match(r"^[\?\.\s_\-]+$", clean):
        return True

    # 2. Generic disposable / system placeholders
    if clean_lower in {
        "???", "unknown", "none", "system", "narrator", "text", "choice",
        "voice", "all", "both", "crowd", "people", "someone", "somebody"
    }:
        return True

    # 3. Escape code leftovers like \I[2914] or [1]
    if re.search(r"\\|\/|\[\d+\]", clean):
        return True

    return False


def sanitize_profile_filename(name: str) -> str:
    """Sanitizes filename for Windows OS while preserving readable character name."""
    # Strip illegal Windows characters: \ / : * ? " < > |
    safe = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return safe


class TLASConsensusEngine:
    def __init__(self, data_dir: str, extractions_dir: str = None):
        self.data_dir = data_dir
        if extractions_dir and os.path.exists(extractions_dir):
            self.extractions_dir = extractions_dir
        else:
            v4_dir = os.path.join(data_dir, "extractions_v4")
            self.extractions_dir = v4_dir if os.path.exists(v4_dir) else os.path.join(data_dir, "extractions")
        self.profiles_dir = os.path.join(data_dir, "profiles")
        self.matrix_output_path = os.path.join(data_dir, "global_pronoun_matrix.json")
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        # Alias Mapping & Canonical Name Index
        self.alias_to_canonical: Dict[str, str] = dict(EXPLICIT_ALIAS_REMAP)
        self.char_collected_aliases: Dict[str, Set[str]] = defaultdict(set)
        self._load_alias_mapping()

        # Target Character Whitelist (Invariants: analysis_target=True, Ambient excluded)
        self.target_whitelist: Set[str] = set()
        self._load_target_whitelist()

        # In-memory aggregators
        self.char_identities: Dict[str, dict] = {}
        self.personality_scores: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        self.speech_habit_scores: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        self.values_scores: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        
        # Directed Pairwise: (Speaker, Target) -> stats
        self.pairwise_relationships: Dict[tuple, Dict[str, List[Any]]] = defaultdict(lambda: defaultdict(list))

        # Evidence accumulators for dynamic identity & kinship inference
        self.gender_votes = defaultdict(lambda: Counter())
        self.age_votes = defaultdict(lambda: Counter())
        self.kinship_graph = defaultdict(lambda: defaultdict(list))

    def _load_alias_mapping(self):
        """Loads and merges alias mappings from alias_mapping.json."""
        alias_path = os.path.join(self.data_dir, "alias_mapping.json")
        if not os.path.exists(alias_path):
            alias_path = os.path.join(os.path.dirname(__file__), "../../../data/tlas/alias_mapping.json")
        if os.path.exists(alias_path):
            try:
                with open(alias_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for a, c in data.items():
                    a_clean = a.strip().lower()
                    c_clean = c.strip()
                    c_resolved = EXPLICIT_ALIAS_REMAP.get(c_clean.lower(), c_clean)
                    if a_clean not in self.alias_to_canonical:
                        self.alias_to_canonical[a_clean] = c_resolved
                logger.info(f"Loaded {len(self.alias_to_canonical)} alias mappings into Consensus Engine.")
            except Exception as e:
                logger.warning(f"Failed loading alias mapping: {e}")

    def get_canonical_name(self, name: str) -> str:
        """Resolves any variant, prefix, voice cue, or alias to canonical character name and accumulates aliases."""
        if not name:
            return ""
        # Strip RPG Maker inline control codes e.g. \C[27], \N[1]
        clean = re.sub(r'\\[A-Za-z]+\[\d*\]|\\[A-Za-z]+', '', str(name)).strip().rstrip(":")
        if not clean:
            return ""
        lower = clean.lower()

        # 1. Voice-to-Entity Resolution (Acoustic Stemming)
        v_match = VOICE_STEM_REGEX.match(clean)
        if v_match:
            stem = v_match.group("stem").strip()
            stem_lower = stem.lower()
            stem_canon = self.alias_to_canonical.get(stem_lower, stem)
            if stem_canon in self.target_whitelist:
                self.char_collected_aliases[stem_canon].add(clean)
                return stem_canon
            elif f"{stem_canon}s" in self.target_whitelist:
                target = f"{stem_canon}s"
                self.char_collected_aliases[target].add(clean)
                return target

        # 2. Romaji L/R & Phonetic Collision Normalization
        if lower in ("arisa", "alisa", "\\c[27]arisa\\c", "\\c[27]arisa:\\c"):
            canon = "Alisa"
        elif lower in ("rylie", "riley"):
            canon = "Riley"
        else:
            canon = self.alias_to_canonical.get(lower, self.alias_to_canonical.get(clean, clean))

        # 3. Specific prefix and suffix normalizations
        if canon.lower() in ("the earl?", "earl", "the earl"):
            canon = "The Earl"
        elif canon.lower() in ("mr.masaru", "mr. masaru", "masarua", "nasaru"):
            canon = "Masaru"
        elif canon.lower() in ("sir masgolf", "maso golf", "musgolf", "masgolf"):
            canon = "Masgolf"
        elif canon.lower() in ("jordan's voice from inside", "jordansmoke"):
            canon = "Jordan"
        elif canon.lower() in ("boy ritche", "boy ritchie", "kid ritchie"):
            canon = "Ritchie"
        elif canon.lower() in ("jikan ceo", "jikan's ceo", "kj(jikan's ceo)"):
            canon = "KJ"
        elif canon.lower() in ("fulgee", "flugee"):
            canon = "Flugee"

        # Accumulate alias if valid
        if canon in self.target_whitelist and clean != canon:
            self.char_collected_aliases[canon].add(clean)
        return canon

    def _load_target_whitelist(self):
        """Dynamically loads canonical whitelist from Master Glossary (Zero-Hardcoding Invariant)."""
        glossary_path = os.path.join(self.data_dir, "tlas_glossary.json")
        if not os.path.exists(glossary_path):
            glossary_path = os.path.join(self.data_dir, "glossary.json")

        if os.path.exists(glossary_path):
            try:
                with open(glossary_path, "r", encoding="utf-8-sig") as f:
                    gdata = json.load(f)
                chars = gdata.get("Characters", gdata.get("characters", {}))
                
                # Anonymous counter pattern to prevent mobs from getting whitelisted
                counter_pattern = re.compile(r'^(?:man|men|girl|girls|boy|boys|guy|guys|lady|ladies|customer|staff|clerk|worker|thug|thugs|host|fan|fans|housekeeper|employee|grunt|police|student)\s+(?:[a-d]|\d+)$', re.IGNORECASE)
                
                for k, v in chars.items():
                    if not isinstance(v, dict):
                        continue
                    clean_k = re.sub(r'\\[A-Za-z]+\[\d*\]|\\[A-Za-z]+', '', k).strip().rstrip(":")
                    if is_invalid_or_disposable_speaker(clean_k):
                        continue
                    if counter_pattern.match(clean_k) and clean_k.lower() != "big b":
                        continue

                    role = v.get("role_category", "")
                    target = v.get("analysis_target", True)
                    lines = v.get("stats", {}).get("lines", 0)

                    # Volume Invariant: Any character with >= 15 lines is an active speaking entity (e.g. Owl with 1030 lines)
                    is_high_volume = (lines >= 15)

                    words_in_name = set(re.findall(r'\b\w+\b', clean_k.lower()))
                    is_generic_word = bool(words_in_name & {
                        'man', 'men', 'girl', 'girls', 'boy', 'boys', 'guy', 'guys',
                        'lady', 'ladies', 'woman', 'women', 'customer', 'staff', 'clerk',
                        'worker', 'thug', 'thugs', 'host', 'fan', 'fans', 'escort', 'hooker',
                        'housekeeper', 'voice', 'voices', 'parent', 'student', 'grunt', 'cop',
                        'passerby', 'bystander', 'citizen', 'guard', 'officer', 'police'
                    })

                    # Non-hardcoded generic mob exclusion rule:
                    # Generic descriptor mobs (Customer, Middle aged man, Host, Thug, etc.) are always excluded
                    # unless they are explicitly non-generic sentient entities with high dialogue volume (e.g. Owl)
                    if is_generic_word or target is False or role == "Ambient":
                        if is_generic_word or not is_high_volume:
                            continue

                    c_name = v.get("name", clean_k)
                    canon = self.get_canonical_name(c_name.strip())
                    
                    if not is_invalid_or_disposable_speaker(canon) and not counter_pattern.match(canon):
                        self.target_whitelist.add(canon)
                        if clean_k != canon:
                            self.char_collected_aliases[canon].add(clean_k)

                logger.info(f"Target Character Whitelist dynamically loaded: {len(self.target_whitelist)} characters (Zero-Hardcoding Master Glossary).")
            except Exception as e:
                logger.warning(f"Failed loading dynamic glossary whitelist: {e}")

    def purge_ambient_and_junk_profiles(self):
        """Purges any non-canonical ambient NPC profiles from disk (Target Workspace Isolation)."""
        if not os.path.exists(self.profiles_dir):
            return
        purged = 0
        for f in glob.glob(os.path.join(self.profiles_dir, "*.json")):
            fname = os.path.basename(f)
            char_name = fname[:-5]
            if char_name not in self.target_whitelist or is_invalid_or_disposable_speaker(char_name):
                try:
                    os.remove(f)
                    purged += 1
                except Exception as e:
                    logger.warning(f"Could not purge {fname}: {e}")
        logger.info(f"Purged {purged} ambient/junk profiles from disk. Kept {len(self.target_whitelist)} canonical profiles.")

    def process_all_extractions(self):
        """Standard pipeline: loads identities, harvests extractions, and resolves identities."""
        self.load_existing_identities()
        self.harvest_extractions()
        self._resolve_evidence_identities()

    def load_existing_identities(self):
        """Pre-loads identities only for target whitelist characters."""
        # 1. From backup legacy profiles
        backup_dir = os.path.join(self.data_dir, "profiles_backup_legacy")
        if os.path.exists(backup_dir):
            for pf in glob.glob(os.path.join(backup_dir, "*.json")):
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        p = json.load(f)
                    raw_name = p.get("name") or os.path.basename(pf).replace(".json", "")
                    cname = self.get_canonical_name(raw_name)
                    if cname not in self.target_whitelist:
                        continue
                    ident = p.get("identity", {})
                    base_aliases = list(p.get("aliases", [cname]))
                    if cname in self.char_collected_aliases:
                        base_aliases.extend(list(self.char_collected_aliases[cname]))
                    self.char_identities[cname] = {
                        "gender": ident.get("gender", "UNKNOWN"),
                        "age": ident.get("age", "UNKNOWN"),
                        "species": ident.get("species", "HUMAN"),
                        "character_id": p.get("character_id", f"CHAR_{cname.upper()}"),
                        "aliases": sorted(list(set(base_aliases)))
                    }
                except Exception as e:
                    logger.warning(f"Failed reading backup identity from {pf}: {e}")

        # 1.1 From character_identities.json
        identities_path = os.path.join(self.data_dir, "character_identities.json")
        if os.path.exists(identities_path):
            try:
                with open(identities_path, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                for cname, ident in cdata.items():
                    if cname not in self.target_whitelist:
                        continue
                    if cname not in self.char_identities or self.char_identities[cname].get("gender") == "UNKNOWN":
                        self.char_identities[cname] = {
                            "gender": ident.get("gender", "UNKNOWN"),
                            "age": ident.get("age", "UNKNOWN"),
                            "species": ident.get("species", "HUMAN"),
                            "character_id": ident.get("character_id", f"CHAR_{cname.upper()}"),
                            "aliases": ident.get("aliases", [cname])
                        }
            except Exception as e:
                logger.warning(f"Failed reading character_identities.json: {e}")

        # 2. From tlas_glossary.json for any newly discovered characters
        glossary_path = os.path.join(self.data_dir, "tlas_glossary.json")
        if os.path.exists(glossary_path):
            try:
                with open(glossary_path, "r", encoding="utf-8") as f:
                    gdata = json.load(f)
                chars = gdata.get("Characters", {})
                for cname, cdata in chars.items():
                    if cname not in self.target_whitelist:
                        continue
                    if cname not in self.char_identities:
                        aliases_list = [cname]
                        for al in cdata.get("aliases", []):
                            al_name = al["name"] if isinstance(al, dict) else al
                            if al_name not in aliases_list:
                                aliases_list.append(al_name)
                        self.char_identities[cname] = {
                            "gender": "UNKNOWN",
                            "age": "UNKNOWN",
                            "species": "HUMAN",
                            "character_id": f"CHAR_{cname.upper()}",
                            "aliases": aliases_list
                        }
                logger.info(f"Identity database loaded with {len(self.char_identities)} target characters.")
            except Exception as e:
                logger.warning(f"Failed reading glossary identities: {e}")

    def harvest_extractions(self):
        """Reads all chunk extraction JSONs and accumulates statistical frequencies."""
        extraction_files = glob.glob(os.path.join(self.extractions_dir, "*.json"))
        logger.info(f"Harvesting evidence from {len(extraction_files)} extraction files...")

        for ef in extraction_files:
            try:
                with open(ef, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            ctx = data.get("scene_context", "")
            if ctx:
                # Split into sentence clauses to prevent cross-character pronoun pollution
                sentences = re.split(r'[.!?;\n]+', ctx)
                for s in sentences:
                    s_clean = s.strip()
                    if not s_clean:
                        continue
                    s_lower = s_clean.lower()
                    for char_info in data.get("characters", []):
                        cname = char_info.get("character_name") if isinstance(char_info, dict) else None
                        if not cname:
                            continue
                        
                        pattern = r'\b' + re.escape(cname.lower()) + r'\b'
                        if re.search(pattern, s_lower):
                            # Direct Title clues (e.g. Sir Damien, Mr. Masaru, Lady Fiona)
                            if re.search(r'\b(sir|lord|mr)\s+' + re.escape(cname.lower()) + r'\b', s_lower):
                                self.gender_votes[cname]["MALE"] += 10
                            if re.search(r'\b(lady|madam|mrs|ms|miss)\s+' + re.escape(cname.lower()) + r'\b', s_lower):
                                self.gender_votes[cname]["FEMALE"] += 10

                            # Sentence level pronoun scan
                            m_hits = len(re.findall(r'\b(he|him|his|man|boy|gentleman|male)\b', s_lower))
                            f_hits = len(re.findall(r'\b(she|her|hers|woman|girl|lady|female)\b', s_lower))
                            
                            # Only vote if one dominates in this sentence clause
                            if m_hits > f_hits:
                                self.gender_votes[cname]["MALE"] += (m_hits - f_hits)
                            elif f_hits > m_hits:
                                self.gender_votes[cname]["FEMALE"] += (f_hits - m_hits)

                            if re.search(r'\b(child|little girl|young girl|kid|baby)\b', s_lower):
                                self.age_votes[cname]["CHILD"] += 1
                            if re.search(r'\b(old man|elder|senior|grandpa|elderly)\b', s_lower):
                                self.age_votes[cname]["ELDER"] += 1

            for char_info in data.get("characters", []):
                if not isinstance(char_info, dict):
                    continue
                raw_cname = char_info.get("character_name")
                if not raw_cname or is_invalid_or_disposable_speaker(raw_cname):
                    continue
                cname = self.get_canonical_name(raw_cname)
                if cname not in self.target_whitelist:
                    continue

                raw_delta = char_info.get("delta", {})
                if isinstance(raw_delta, list):
                    delta = {}
                    for item in raw_delta:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                if k not in delta:
                                    delta[k] = []
                                if isinstance(v, list):
                                    delta[k].extend(v)
                                else:
                                    delta[k].append(v)
                elif isinstance(raw_delta, dict):
                    delta = raw_delta
                else:
                    delta = {}

                # Fallback if traits are directly on char_info
                for k in ["personality", "speech_habit", "values", "relationships"]:
                    if k not in delta and k in char_info:
                        delta[k] = char_info[k]

                def _safe_int(val, default=50):
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                # Personality
                pers_list = delta.get("personality", [])
                if isinstance(pers_list, list):
                    for p in pers_list:
                        if isinstance(p, dict):
                            tag, weight = p.get("tag"), _safe_int(p.get("weight", 50))
                        elif isinstance(p, str):
                            tag, weight = p, 50
                        else:
                            continue
                        if tag:
                            self.personality_scores[cname][str(tag)].append(weight)

                # Speech habits
                sh_list = delta.get("speech_habit", [])
                if isinstance(sh_list, list):
                    for sh in sh_list:
                        if isinstance(sh, dict):
                            tag, weight = sh.get("tag"), _safe_int(sh.get("weight", 50))
                        elif isinstance(sh, str):
                            tag, weight = sh, 50
                        else:
                            continue
                        if tag:
                            self.speech_habit_scores[cname][str(tag)].append(weight)

                # Values
                vals_list = delta.get("values", [])
                if isinstance(vals_list, list):
                    for v in vals_list:
                        if isinstance(v, dict):
                            tag, weight = v.get("tag"), _safe_int(v.get("weight", 50))
                        elif isinstance(v, str):
                            tag, weight = v, 50
                        else:
                            continue
                        if tag:
                            self.values_scores[cname][str(tag)].append(weight)

                # 4D Relationships (Handle nested lists or non-dict items safely)
                raw_rels = delta.get("relationships", [])
                flat_rels = []
                if isinstance(raw_rels, list):
                    for item in raw_rels:
                        if isinstance(item, list):
                            flat_rels.extend([x for x in item if isinstance(x, dict)])
                        elif isinstance(item, dict):
                            flat_rels.append(item)
                elif isinstance(raw_rels, dict):
                    flat_rels.append(raw_rels)

                for rel in flat_rels:
                    raw_target = rel.get("target_name")
                    if not raw_target or is_invalid_or_disposable_speaker(raw_target):
                        continue
                    target_name = self.get_canonical_name(raw_target)
                    if target_name not in self.target_whitelist or target_name == cname:
                        continue

                    pair_key = (cname, target_name)
                    roles = rel.get("roles", [])
                    if isinstance(roles, list):
                        for r in roles:
                            if r:
                                self.pairwise_relationships[pair_key]["roles"].append(str(r))
                    elif isinstance(roles, str) and roles:
                        self.pairwise_relationships[pair_key]["roles"].append(roles)

                    roles_list = roles if isinstance(roles, list) else [roles] if isinstance(roles, str) else []
                    for r in roles_list:
                        if not r:
                            continue
                        self.kinship_graph[cname][target_name].append(str(r))
                        
                        # Speaker gender clues
                        if r in ["ROLE_FAM_MOTHER", "ROLE_FAM_WIFE", "ROLE_FAM_DAUGHTER", "ROLE_FAM_SISTER", "ROLE_ROM_GIRLFRIEND"]:
                            self.gender_votes[cname]["FEMALE"] += 5
                        elif r in ["ROLE_FAM_FATHER", "ROLE_FAM_HUSBAND", "ROLE_FAM_SON", "ROLE_FAM_BROTHER", "ROLE_ROM_BOYFRIEND"]:
                            self.gender_votes[cname]["MALE"] += 5
                        
                        # Speaker age clues
                        if r in ["ROLE_FAM_CHILD", "ROLE_FAM_DAUGHTER", "ROLE_FAM_SON"]:
                            self.age_votes[cname]["CHILD"] += 4
                        elif r in ["ROLE_FAM_FATHER", "ROLE_FAM_MOTHER", "ROLE_FAM_HUSBAND", "ROLE_FAM_WIFE", "ROLE_WORK_BOSS"]:
                            self.age_votes[cname]["ADULT"] += 3
                        elif r in ["ROLE_SOC_ELDER", "ROLE_SOC_MENTOR"]:
                            self.age_votes[cname]["ELDER"] += 2

                        # Target clues
                        if target_name and target_name not in ["Unknown", "Someone"]:
                            if r in ["ROLE_FAM_MOTHER", "ROLE_FAM_WIFE", "ROLE_FAM_SISTER"]:
                                self.gender_votes[target_name]["FEMALE"] += 5
                            elif r in ["ROLE_FAM_FATHER", "ROLE_FAM_HUSBAND", "ROLE_FAM_BROTHER"]:
                                self.gender_votes[target_name]["MALE"] += 5
                            
                            if r in ["ROLE_OLDER_SIBLING_TO_YOUNGER", "ROLE_FAM_SIBLING_OLDER"]:
                                self.age_votes[target_name]["CHILD"] += 3
                                self.age_votes[cname]["ADULT"] += 2

                    if rel.get("affinity"):
                        self.pairwise_relationships[pair_key]["affinity"].append(str(rel["affinity"]))
                    if rel.get("intimacy"):
                        self.pairwise_relationships[pair_key]["intimacy"].append(str(rel["intimacy"]))
                    if rel.get("power_dynamic"):
                        self.pairwise_relationships[pair_key]["power_dynamic"].append(str(rel["power_dynamic"]))
                    
                    sp_style = rel.get("speech_style")
                    if isinstance(sp_style, dict):
                        rule = sp_style.get("derivation_rule")
                        if rule:
                            self.pairwise_relationships[pair_key]["derivation_rule"].append(str(rule))

        logger.info(f"Harvesting complete: Found {len(self.personality_scores)} active characters and {len(self.pairwise_relationships)} relationship pairs.")
        self._resolve_evidence_identities()

    def harvest_from_existing_profiles(self):
        """
        Gathers evidence directly from existing legacy profiles that already have
        rich timeline_states (deltas) analyzed by LLM. This saves 100% of LLM calls!
        """
        profile_files = glob.glob(os.path.join(self.profiles_dir, "*.json"))
        logger.info(f"Harvesting evidence from {len(profile_files)} existing profiles on disk...")
        harvested_states = 0

        for pf in profile_files:
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    p = json.load(f)
            except Exception:
                continue

            cname = p.get("name") or os.path.basename(pf).replace(".json", "")
            timeline_states = p.get("timeline_states", [])
            if not timeline_states:
                continue

            for state in timeline_states:
                delta = state.get("delta", {})
                harvested_states += 1

                # Personality
                for trait in delta.get("personality", []):
                    tag = trait.get("tag") if isinstance(trait, dict) else str(trait)
                    weight = trait.get("weight", 50) if isinstance(trait, dict) else 50
                    if tag:
                        self.personality_scores[cname][tag].append(weight)

                # Speech habits
                for sh in delta.get("speech_habit", []):
                    tag = sh.get("tag") if isinstance(sh, dict) else str(sh)
                    weight = sh.get("weight", 50) if isinstance(sh, dict) else 50
                    if tag:
                        self.speech_habit_scores[cname][tag].append(weight)

                # Values
                for val in delta.get("values", []):
                    tag = val.get("tag") if isinstance(val, dict) else str(val)
                    weight = val.get("weight", 50) if isinstance(val, dict) else 50
                    if tag:
                        self.values_scores[cname][tag].append(weight)

                # 4D Relationships
                for rel in delta.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    target_name = rel.get("target_name")
                    if not target_name or target_name == "Unknown" or target_name == cname:
                        continue

                    pair_key = (cname, target_name)
                    for r in rel.get("roles", []):
                        if r:
                            self.pairwise_relationships[pair_key]["roles"].append(r)
                    if rel.get("affinity"):
                        self.pairwise_relationships[pair_key]["affinity"].append(rel["affinity"])
                    if rel.get("intimacy"):
                        self.pairwise_relationships[pair_key]["intimacy"].append(rel["intimacy"])
                    if rel.get("power_dynamic"):
                        self.pairwise_relationships[pair_key]["power_dynamic"].append(rel["power_dynamic"])
                    rule = rel.get("specific_speech", {}).get("rule_applied") or rel.get("speech_style", {}).get("derivation_rule")
                    if rule:
                        self.pairwise_relationships[pair_key]["derivation_rule"].append(rule)

        logger.info(f"Harvested {harvested_states} timeline states from existing profiles. Found {len(self.personality_scores)} characters and {len(self.pairwise_relationships)} relationship pairs.")
        self._resolve_evidence_identities()

    def _resolve_evidence_identities(self):
        """Synthesizes identities (gender, age) from accumulated evidence and resolves kinships."""
        logger.info("Resolving identities and kinships from harvested evidence...")
        all_chars = set(self.personality_scores.keys()).union(self.char_identities.keys()).union(self.gender_votes.keys())
        
        for cname in all_chars:
            current_id = self.char_identities.get(cname, {})
            current_gender = current_id.get("gender", "UNKNOWN")
            current_age = current_id.get("age", "UNKNOWN")

            # Tier 1: Known identity from pre-loaded identities or glossary
            if current_gender != "UNKNOWN" and current_age != "UNKNOWN":
                final_gender = current_gender
                final_age = current_age
            else:
                name_inferred = infer_identity_from_name(cname)
                
                # Context / Evidence votes (Sentence-level He/Him vs She/Her and Titles)
                g_votes = self.gender_votes[cname]
                m_score = g_votes.get("MALE", 0)
                f_score = g_votes.get("FEMALE", 0)

                # Name clue contributes moderate prior weight (+3) rather than absolute override
                if name_inferred["gender"] == "MALE":
                    m_score += 3
                elif name_inferred["gender"] == "FEMALE":
                    f_score += 3

                # Weighted Linguistic Resolution:
                if m_score > f_score:
                    final_gender = "MALE"
                elif f_score > m_score:
                    final_gender = "FEMALE"
                elif current_gender != "UNKNOWN":
                    final_gender = current_gender
                elif name_inferred["gender"]:
                    final_gender = name_inferred["gender"]
                else:
                    final_gender = "MALE"

                # Age Resolution: Default to ADULT unless explicitly a child/elder
                a_votes = self.age_votes[cname]
                inferred_age = a_votes.most_common(1)[0][0] if a_votes else None
                if name_inferred["age"]:
                    final_age = name_inferred["age"]
                elif current_age != "UNKNOWN":
                    final_age = current_age
                elif inferred_age:
                    final_age = inferred_age
                else:
                    final_age = "ADULT"

            self.char_identities[cname] = {
                "gender": final_gender,
                "age": final_age,
                "species": current_id.get("species", "HUMAN"),
                "character_id": current_id.get("character_id", f"CHAR_{cname.upper()}"),
                "aliases": current_id.get("aliases", [cname])
            }

        # Generic Kinship & Relative-Term Resolver across all characters
        relative_terms_mother = {"mama", "mom", "mother"}
        relative_terms_father = {"papa", "dad", "father"}
        
        for speaker in list(all_chars):
            speaker_rels = self.kinship_graph.get(speaker, {})
            target_names = list(speaker_rels.keys())
            has_gen_mother = [t for t in target_names if t.lower() in relative_terms_mother]
            has_gen_father = [t for t in target_names if t.lower() in relative_terms_father]

            if not has_gen_mother and not has_gen_father:
                continue

            # 1. Discover True Mother from Social Graph
            mother_candidates = []
            for cand, roles in speaker_rels.items():
                if cand.lower() not in relative_terms_mother and cand.lower() not in relative_terms_father:
                    if any(r in ["ROLE_FAM_DAUGHTER", "ROLE_FAM_CHILD", "ROLE_FAM_SON"] for r in roles):
                        if self.char_identities.get(cand, {}).get("gender") == "FEMALE":
                            mother_candidates.append(cand)

            # 2. Discover True Father from direct role or mother's spouse
            father_candidates = []
            for cand, roles in speaker_rels.items():
                if cand.lower() not in relative_terms_father and cand.lower() not in relative_terms_mother:
                    if any(r in ["ROLE_FAM_FATHER"] for r in roles):
                        father_candidates.append(cand)

            if not father_candidates and mother_candidates:
                first_mom = mother_candidates[0]
                spouses = [
                    sp for sp, r_list in self.kinship_graph.get(first_mom, {}).items()
                    if any(r in ["ROLE_FAM_HUSBAND", "ROLE_FAM_SPOUSE", "ROLE_ROM_PARTNER"] for r in r_list)
                    and self.char_identities.get(sp, {}).get("gender") == "MALE"
                ]
                father_candidates.extend(spouses)

            # 3. Perform Generic Remap
            if has_gen_mother and mother_candidates:
                real_mom = mother_candidates[0]
                for term in has_gen_mother:
                    logger.info(f"Generic Kinship Remap: '{speaker}' relative '{term}' -> Real Mother '{real_mom}'")
                    if (speaker, term) in self.pairwise_relationships:
                        for k, v in self.pairwise_relationships[(speaker, term)].items():
                            self.pairwise_relationships[(speaker, real_mom)][k].extend(v)
                        del self.pairwise_relationships[(speaker, term)]
                    self.pairwise_relationships[(real_mom, speaker)]["roles"].append("ROLE_FAM_PARENT")

            if has_gen_father and father_candidates:
                real_dad = father_candidates[0]
                for term in has_gen_father:
                    logger.info(f"Generic Kinship Remap: '{speaker}' relative '{term}' -> Real Father '{real_dad}'")
                    if (speaker, term) in self.pairwise_relationships:
                        for k, v in self.pairwise_relationships[(speaker, term)].items():
                            self.pairwise_relationships[(speaker, real_dad)][k].extend(v)
                        del self.pairwise_relationships[(speaker, term)]
                    self.pairwise_relationships[(real_dad, speaker)]["roles"].append("ROLE_FAM_PARENT")

        # Clean generic / non-character targets from relationships
        garbage_targets = {"Papa", "Mama", "Unknown", "Someone", "Guy"}
        clean_keys = [k for k in self.pairwise_relationships.keys() if k[1] in garbage_targets]
        for k in clean_keys:
            del self.pairwise_relationships[k]

        # Save to character_identities.json
        ident_path = os.path.join(self.data_dir, "character_identities.json")
        try:
            with open(ident_path, "w", encoding="utf-8") as f:
                json.dump(self.char_identities, f, indent=2, ensure_ascii=False)
            logger.info(f"Master character identities saved to {ident_path}")
        except Exception as e:
            logger.warning(f"Failed saving character_identities.json: {e}")

    def _aggregate_traits(self, score_dict: Dict[str, List[int]], top_k: int = 5) -> List[dict]:
        """Calculates normalized average weight and returns top K tags."""
        aggregated = []
        for tag, weights in score_dict.items():
            clean_weights = []
            for w in weights:
                try:
                    clean_weights.append(int(w))
                except (ValueError, TypeError):
                    clean_weights.append(50)
            freq = len(clean_weights)
            if freq == 0:
                continue
            avg_weight = round(sum(clean_weights) / freq)
            aggregated.append({"tag": tag, "weight": avg_weight, "freq": freq})
        # Sort by frequency then average weight
        aggregated.sort(key=lambda x: (x["freq"], x["weight"]), reverse=True)
        return [{"tag": item["tag"], "weight": item["weight"]} for item in aggregated[:top_k]]

    def _resolve_base_speech_style(self, identity: dict, personality: list) -> dict:
        """Determines baseline default pronouns according to gender, age and personality (SDD-011)."""
        gender = identity.get("gender", "MALE")
        age = identity.get("age", "ADULT")
        
        has_polite = any(p.get("tag") == "PER_SOC_POLITE" for p in personality)
        has_rude = any(p.get("tag") in ["PER_SOC_RUDE", "PER_VIBE_AGGRESSIVE"] for p in personality)

        if gender == "FEMALE":
            if age == "CHILD":
                return {"self_pronoun": "หนู", "target_pronoun": "คุณ", "third_person_pronoun": "เขา", "ending_particle": "ค่ะ", "formality_level": 3}
            elif age == "ELDER":
                # หญิงชรา: ผู้ใหญ่คุยกับผู้น้อย แทนตัวเองว่า "ฉัน" ไม่มีหางเสียง
                return {"self_pronoun": "ฉัน", "target_pronoun": "เธอ", "third_person_pronoun": "เขา", "ending_particle": "", "formality_level": 3}
            elif has_rude:
                return {"self_pronoun": "ฉัน", "target_pronoun": "แก", "third_person_pronoun": "มัน", "ending_particle": "", "formality_level": 2}
            elif has_polite:
                return {"self_pronoun": "ฉัน", "target_pronoun": "คุณ", "third_person_pronoun": "เธอ", "ending_particle": "ค่ะ", "formality_level": 4}
            else:
                return {"self_pronoun": "ฉัน", "target_pronoun": "เธอ", "third_person_pronoun": "เขา", "ending_particle": "จ้ะ", "formality_level": 3}
        else: # MALE or UNKNOWN
            if age == "CHILD":
                return {"self_pronoun": "ผม", "target_pronoun": "คุณ", "third_person_pronoun": "เขา", "ending_particle": "ครับ", "formality_level": 3}
            elif age == "ELDER":
                # ชายชรา: ผู้ใหญ่คุยกับผู้น้อย แทนตัวเองว่า "ฉัน" ไม่มีหางเสียง
                return {"self_pronoun": "ฉัน", "target_pronoun": "เธอ", "third_person_pronoun": "เขา", "ending_particle": "", "formality_level": 3}
            elif has_rude:
                return {"self_pronoun": "ฉัน", "target_pronoun": "นาย", "third_person_pronoun": "มัน", "ending_particle": "", "formality_level": 2}
            elif has_polite:
                return {"self_pronoun": "ผม", "target_pronoun": "คุณ", "third_person_pronoun": "เขา", "ending_particle": "ครับ", "formality_level": 4}
            else: # Default polite male
                return {"self_pronoun": "ผม", "target_pronoun": "คุณ", "third_person_pronoun": "เขา", "ending_particle": "ครับ", "formality_level": 4}

    def _resolve_pairwise_speech(self, speaker_name: str, target_name: str, stats: dict, base_speech: dict, 
                                speaker_gender: str, speaker_age: str = "ADULT", 
                                target_gender: str = "MALE", target_age: str = "ADULT") -> dict:
        """Evaluates 5-Tier Priority Rule Chain (SDD-011) to determine directed pronouns."""
        # Find Majority Vote / Mode for each dimension
        roles_counter = Counter(stats.get("roles", []))
        top_roles = [r for r, c in roles_counter.most_common(2)]
        
        affinity = Counter(stats.get("affinity", [])).most_common(1)[0][0] if stats.get("affinity") else "AFF_NEUTRAL"
        intimacy = Counter(stats.get("intimacy", [])).most_common(1)[0][0] if stats.get("intimacy") else "INT_DISTANT"
        power_dyn = Counter(stats.get("power_dynamic", [])).most_common(1)[0][0] if stats.get("power_dynamic") else "DYN_EQUAL"
        suggested_rule = Counter(stats.get("derivation_rule", [])).most_common(1)[0][0] if stats.get("derivation_rule") else None

        # Tier 1: Family Hierarchy
        # 1.1 Child to Parent (Generic: Child role towards an adult in family)
        if speaker_age == "CHILD" and any(r in ["ROLE_FAM_DAUGHTER", "ROLE_FAM_CHILD", "ROLE_FAM_SON"] for r in top_roles):
            parent_term = "คุณพ่อ" if target_gender == "MALE" else "คุณแม่"
            return {
                "roles": top_roles or ["ROLE_FAM_CHILD"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "หนู" if speaker_gender == "FEMALE" else "ผม",
                    "target_pronoun": parent_term,
                    "third_person_pronoun": parent_term,
                    "ending_particle": "ค่ะ" if speaker_gender == "FEMALE" else "ครับ",
                    "formality_level": 3,
                    "derivation_rule": "RULE_CHILD_TO_PARENT"
                }
            }

        # 1.2 Parent to Child (Generic: Adult parent speaking to child)
        if target_age == "CHILD" and any(r in ["ROLE_FAM_PARENT", "ROLE_FAM_FATHER", "ROLE_FAM_MOTHER"] for r in top_roles):
            parent_self = "พ่อ" if speaker_gender == "MALE" else "แม่"
            return {
                "roles": top_roles or ["ROLE_FAM_PARENT"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": parent_self,
                    "target_pronoun": "หนู",
                    "third_person_pronoun": "ลูก",
                    "ending_particle": "จ้ะ" if speaker_gender == "FEMALE" else "ครับ",
                    "formality_level": 2,
                    "derivation_rule": "RULE_PARENT_TO_CHILD"
                }
            }

        # 1.3 Younger to Older Sibling (Speaker is Younger)
        if "ROLE_FAM_SIBLING_YOUNGER" in top_roles or (suggested_rule and "CHILD_TO_PEER" in suggested_rule):
            older_term = "พี่"
            return {
                "roles": top_roles or ["ROLE_FAM_SIBLING_YOUNGER"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "หนู" if speaker_gender == "FEMALE" or speaker_age == "CHILD" else "ผม",
                    "target_pronoun": older_term,
                    "third_person_pronoun": older_term,
                    "ending_particle": "ค่ะ" if speaker_gender == "FEMALE" else "ครับ",
                    "formality_level": 3,
                    "derivation_rule": "RULE_YOUNGER_SIBLING_TO_OLDER"
                }
            }

        # 1.4 Older to Younger Sibling (Speaker is Older)
        if "ROLE_FAM_SIBLING_OLDER" in top_roles or (suggested_rule and "OLDER" in suggested_rule):
            younger_term = "หนู" if target_gender == "FEMALE" or target_age == "CHILD" else "น้อง"
            return {
                "roles": top_roles or ["ROLE_FAM_SIBLING_OLDER"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "พี่",
                    "target_pronoun": younger_term,
                    "third_person_pronoun": "น้อง",
                    "ending_particle": "ครับ" if speaker_gender == "MALE" else "จ้ะ",
                    "formality_level": 2,
                    "derivation_rule": "RULE_OLDER_SIBLING_TO_YOUNGER"
                }
            }

        # Tier 2: Romance / Intimate Partner (e.g. Lovers / Married couples)
        if "ROLE_ROM_PARTNER" in top_roles or "ROLE_ROM_LOVER" in top_roles or (suggested_rule and "ROMANTIC" in suggested_rule):
            if speaker_gender == "MALE":
                self_p = "ผม" if intimacy != "INT_CONFIDANT" else "ฉัน"
                target_p = "คุณ" if intimacy != "INT_CONFIDANT" else "เธอ"
                return {
                    "roles": top_roles or ["ROLE_ROM_PARTNER"],
                    "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                    "speech_style": {
                        "self_pronoun": self_p,
                        "target_pronoun": target_p,
                        "third_person_pronoun": "เธอ",
                        "ending_particle": "ครับ",
                        "formality_level": 3,
                        "derivation_rule": "RULE_ROMANTIC_PARTNER"
                    }
                }
            else: # FEMALE speaker
                return {
                    "roles": top_roles or ["ROLE_ROM_PARTNER"],
                    "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                    "speech_style": {
                        "self_pronoun": "ฉัน",
                        "target_pronoun": "คุณ",
                        "third_person_pronoun": "เขา",
                        "ending_particle": "ค่ะ",
                        "formality_level": 3,
                        "derivation_rule": "RULE_ROMANTIC_PARTNER"
                    }
                }

        # Child Protection: If speaker is CHILD and speaking to an adult
        if speaker_age == "CHILD":
            return {
                "roles": top_roles or ["ROLE_SOC_PEER"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "หนู" if speaker_gender == "FEMALE" else "ผม",
                    "target_pronoun": "คุณ" if target_age != "CHILD" else "เธอ",
                    "third_person_pronoun": "เขา",
                    "ending_particle": "ค่ะ" if speaker_gender == "FEMALE" else "ครับ",
                    "formality_level": 3,
                    "derivation_rule": "RULE_CHILD_POLITE"
                }
            }

        # Tier 3: Authority & Hierarchy
        # 3.1 Subordinate to Superior (Speaking to VIP, Master, Boss, or Leader)
        is_speaking_to_vip = any(r in ["ROLE_SOC_VIP", "ROLE_AUTH_MASTER", "ROLE_SOC_ELDER"] for r in top_roles) or (power_dyn == "DYN_SUBMISSIVE" and "ROLE_WORK_BOSS" in top_roles)
        if is_speaking_to_vip or "ROLE_WORK_SUBORDINATE" in top_roles or (power_dyn == "DYN_SUBMISSIVE"):
            return {
                "roles": top_roles or ["ROLE_WORK_SUBORDINATE"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "ผม" if speaker_gender == "MALE" else "ฉัน",
                    "target_pronoun": "ท่าน" if is_speaking_to_vip else "คุณ",
                    "third_person_pronoun": "ท่าน",
                    "ending_particle": "ครับ" if speaker_gender == "MALE" else "ค่ะ",
                    "formality_level": 4,
                    "derivation_rule": "RULE_SUBORDINATE_TO_AUTHORITY"
                }
            }

        # 3.2 Rival / Hostile interaction takes precedence for Peers (e.g. Jords -> Shion)
        if affinity in ["AFF_CONFLICTED", "AFF_HOSTILE"]:
            target_p = "เธอ" if target_gender == "FEMALE" else "นาย"
            third_p = "ยัยนั่น" if target_gender == "FEMALE" else "หมอนั่น"
            ending_p = "วะ" if speaker_gender == "MALE" else "ยะ"
            return {
                "roles": top_roles or ["ROLE_SOC_PEER"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "ฉัน",
                    "target_pronoun": target_p,
                    "third_person_pronoun": third_p,
                    "ending_particle": ending_p,
                    "formality_level": 2,
                    "derivation_rule": "RULE_RIVAL_PEER"
                }
            }

        # 3.3 Superior to Subordinate (Strictly dominant authority talking down to lower rank)
        if "ROLE_WORK_BOSS" in top_roles and power_dyn == "DYN_DOMINANT":
            target_p = "เธอ" if target_gender == "FEMALE" else "นาย"
            return {
                "roles": top_roles or ["ROLE_WORK_BOSS"],
                "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                "speech_style": {
                    "self_pronoun": "ฉัน",
                    "target_pronoun": target_p,
                    "third_person_pronoun": "เขา",
                    "ending_particle": "",
                    "formality_level": 3,
                    "derivation_rule": "RULE_AUTHORITY_TO_SUBORDINATE"
                }
            }

        # Tier 4: Peer & Social Relationships (Refined Sociolinguistic Hierarchy - SDD-012)
        if "ROLE_SOC_PEER" in top_roles or intimacy in ["INT_CONFIDANT", "INT_FAMILIAR"] or "ROLE_WORK_BOSS" in top_roles:
            # 4.1 Close Peer: Strictly for same-age close friends with mutual confidant intimacy (SDD-012)
            if intimacy == "INT_CONFIDANT" and speaker_age == target_age:
                target_p = "เธอ" if target_gender == "FEMALE" else "นาย"
                return {
                    "roles": top_roles or ["ROLE_SOC_PEER"],
                    "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                    "speech_style": {
                        "self_pronoun": "เรา" if speaker_gender == "MALE" else "ฉัน",
                        "target_pronoun": target_p,
                        "third_person_pronoun": "เขา",
                        "ending_particle": "",
                        "formality_level": 3,
                        "derivation_rule": "RULE_CLOSE_PEER"
                    }
                }
            # 4.2 General / Polite Peer: Default sociolinguistic baseline in Thai for adult acquaintances & polite coworkers
            else:
                return {
                    "roles": top_roles or ["ROLE_SOC_PEER"],
                    "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
                    "speech_style": {
                        "self_pronoun": "ผม" if speaker_gender == "MALE" else "ฉัน",
                        "target_pronoun": "คุณ",
                        "third_person_pronoun": "เขา",
                        "ending_particle": "ครับ" if speaker_gender == "MALE" else "ค่ะ",
                        "formality_level": 4,
                        "derivation_rule": "RULE_POLITE_PEER"
                    }
                }

        # Tier 5: Fallback to Base Speech Style
        return {
            "roles": top_roles or ["ROLE_SOC_PEER"],
            "affinity": affinity, "intimacy": intimacy, "power_dynamic": power_dyn,
            "speech_style": {
                "self_pronoun": base_speech.get("self_pronoun", "ผม"),
                "target_pronoun": base_speech.get("target_pronoun", "คุณ"),
                "third_person_pronoun": base_speech.get("third_person_pronoun", "เขา"),
                "ending_particle": base_speech.get("ending_particle", "ครับ"),
                "formality_level": base_speech.get("formality_level", 4),
                "derivation_rule": "RULE_BASE_FALLBACK"
            }
        }

    def build_and_save_profiles(self):
        """Synthesizes all aggregated data into V4 Character Profiles and global matrix."""
        all_speakers = {
            spk for spk in set(self.personality_scores.keys()).union(self.char_identities.keys())
            if spk in self.target_whitelist and not is_invalid_or_disposable_speaker(spk)
        }
        global_matrix = []

        logger.info(f"Synthesizing TLAS v4.0 profiles for {len(all_speakers)} characters...")

        for spk in sorted(all_speakers):
            if is_invalid_or_disposable_speaker(spk):
                logger.info(f"Skipping disposable placeholder / invalid speaker from profile generation: '{spk}'")
                continue

            safe_fname = sanitize_profile_filename(spk)
            if not safe_fname:
                logger.warning(f"Skipping speaker with invalid filename after sanitize: '{spk}'")
                continue

            ident = self.char_identities.get(spk, {
                "gender": "MALE", "age": "ADULT", "species": "HUMAN",
                "character_id": f"CHAR_{spk.upper()}", "aliases": [spk]
            })
            
            personality = self._aggregate_traits(self.personality_scores[spk], top_k=5)
            speech_habit = self._aggregate_traits(self.speech_habit_scores[spk], top_k=3)
            values = self._aggregate_traits(self.values_scores[spk], top_k=3)
            
            base_speech = self._resolve_base_speech_style(ident, personality)

            # Build Pairwise Relationships
            relationships = []
            for (speaker, target), stats in self.pairwise_relationships.items():
                if speaker == spk:
                    tgt_ident = self.char_identities.get(target, {
                        "gender": "MALE", "age": "ADULT", "species": "HUMAN"
                    })
                    rel_resolved = self._resolve_pairwise_speech(
                        speaker_name=spk,
                        target_name=target,
                        stats=stats,
                        base_speech=base_speech,
                        speaker_gender=ident.get("gender", "MALE"),
                        speaker_age=ident.get("age", "ADULT"),
                        target_gender=tgt_ident.get("gender", "MALE"),
                        target_age=tgt_ident.get("age", "ADULT")
                    )
                    rel_resolved["target_character_id"] = f"CHAR_{target.upper()}"
                    rel_resolved["target_name"] = target
                    relationships.append(rel_resolved)
                    
                    # Record into Global Matrix
                    global_matrix.append({
                        "speaker": spk,
                        "listener": target,
                        "roles": rel_resolved["roles"],
                        "affinity": rel_resolved["affinity"],
                        "intimacy": rel_resolved["intimacy"],
                        "speech_style": rel_resolved["speech_style"]
                    })

            # Construct Clean V4 Profile Object with merged aliases
            all_aliases = set(ident.get("aliases", [spk]))
            all_aliases.add(spk)
            all_aliases.update(self.char_collected_aliases.get(spk, set()))
            cleaned_aliases = sorted([a for a in all_aliases if a and not is_invalid_or_disposable_speaker(a)])

            profile_v4 = {
                "character_id": ident.get("character_id", f"CHAR_{spk.upper()}"),
                "name": spk,
                "aliases": cleaned_aliases,
                "identity": {
                    "gender": ident.get("gender", "UNKNOWN"),
                    "age": ident.get("age", "UNKNOWN"),
                    "species": ident.get("species", "UNKNOWN")
                },
                "base_speech_style": base_speech,
                "base_state": {
                    "personality": personality,
                    "speech_habit": speech_habit,
                    "values": values
                },
                "relationships": relationships
            }

            # Atomic Profile Write
            out_file = os.path.join(self.profiles_dir, f"{safe_fname}.json")
            tmp_file = out_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(profile_v4, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, out_file)
            logger.info(f"[SUCCESS] Saved clean V4 profile: {safe_fname}.json ({len(relationships)} relationships)")

        # Export Centralized Pronoun Matrix
        tmp_matrix = self.matrix_output_path + ".tmp"
        with open(tmp_matrix, "w", encoding="utf-8") as f:
            json.dump(global_matrix, f, ensure_ascii=False, indent=2)
        os.replace(tmp_matrix, self.matrix_output_path)
        logger.info(f"[FINISH] Exported centralized matrix to {self.matrix_output_path} ({len(global_matrix)} pairwise mappings).")

        # Purge ambient and junk profiles from disk
        self.purge_ambient_and_junk_profiles()

    def run(self):
        self.load_existing_identities()
        # 1. Harvest all extractions evidence from extractions_v4
        self.harvest_extractions()
        # 2. Calculate statistical consensus, resolve pronouns and write V4 profiles
        self.build_and_save_profiles()

if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    manifest_path = os.path.join(project_root, "data", "project_manifest.json")
    
    tlas_data = os.path.join(project_root, "data", "tlas")
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        tlas_data = sys.argv[1]
    elif os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
            tlas_data = mdata.get("output_tlas_dir", tlas_data)
        except Exception:
            pass

    logger.info(f"Target TLAS Data Directory: {tlas_data}")
    engine = TLASConsensusEngine(data_dir=tlas_data)
    engine.run()
