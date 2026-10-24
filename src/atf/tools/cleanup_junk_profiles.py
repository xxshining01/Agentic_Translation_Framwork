"""
cleanup_junk_profiles.py
========================
Script for cleaning up junk character profiles, filtering invalid entries from
tlas_glossary.json, and harmonizing alias_mapping.json with the valid glossary whitelist.
"""
import os
import re
import json
import glob
import shutil
from datetime import datetime
from typing import Set, Dict, List

TLAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/tlas"))
PROFILES_DIR = os.path.join(TLAS_DIR, "profiles")
BACKUP_DIR = os.path.join(TLAS_DIR, f"profiles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
GLOSSARY_PATH = os.path.join(TLAS_DIR, "tlas_glossary.json")
ALIAS_PATH = os.path.join(TLAS_DIR, "alias_mapping.json")

# Patterns and names that are definitely garbage / system / anonymous background mob
GARBAGE_PATTERNS = [
    r"^window\d*$",
    r"^i(\[\d+\])?$",
    r"^\?+$",
    r"^unknown.*$",
    r"^_unknown_.*$",
    r"^unnamed.*$",
    r"^c_?\d+.*$",
    r"^\[?ba executive.*\]?$",
    r"^_?ba executive.*_?$",
    r"^ba executive.*$",
    r"^slut.*$",
    r"^all$",
    r"^both$",
    r"^system.*$",
    r"^narrator.*$",
    r"^choice.*$",
    r"^text.*$",
    r"^hostnpc\d*.*$",
    r"^none$",
    r"^crowd.*$",
    r"^people.*$",
    r"^someone.*$",
    r"^somebody.*$",
    r"^.*voice.*$"
]

GARBAGE_REGEX_PATTERNS = GARBAGE_PATTERNS

GENERIC_DISPOSABLE_NAMES: Set[str] = {
    "???", "unknown", "voice", "man", "woman", "villager", "boy", "girl", "all", "both",
    "system", "narrator", "text", "choice", "barfer", "customer", "staff", "npc", "none",
    "crowd", "people", "someone", "somebody", "hostess", "annoyed customer", "affluent man",
    "affluent old man", "agency staff", "anxious boy", "anxious man", "alcoholic middle aged man",
    "bald thug", "bearded man", "bearded guy", "big voice", "slut", "unnamed female",
    "unnamed female character", "unknown woman", "window5"
}

GENERIC_MOB_PREFIXES = [
    "affluent ", "anxious ", "alcoholic ", "annoyed ", "amber hair ",
    "almost noveau ", "adventurous ", "bald ", "bearded ", "blue shirt ",
    "red shirt ", "blond hair ", "pink hair ", "black hair ", "black-haired ",
    "stuck up ", "special customer", "vvip", "vulgar ", "well mannered ",
    "unwell ", "village ", "villager", "young boy", "young girl", "young man",
    "old man", "old lady", "wise man", "wealthy ", "university student ",
    "hotel staff", "agency staff", "fratboy ", "kinchao gang member",
    "kinchao gang 2", "kinchao gang 3", "big "
]

def is_garbage_or_disposable(name: str) -> bool:
    if not name or not name.strip():
        return True
    clean = name.strip()
    clean_lower = clean.lower()
    
    # 1. Regex patterns
    for pat in GARBAGE_PATTERNS:
        if re.match(pat, clean_lower):
            return True
            
    # 2. Bracket / underscore wrap
    if clean.startswith("[") and clean.endswith("]"):
        return True
    if clean.startswith("_") and clean.endswith("_"):
        return True
        
    # 3. Escape code leftovers like \I[2914] or I[2914]
    if re.search(r"\\|\/|\[\d+\]", clean):
        return True
        
    # 4. Single letter name except real initials if any
    if len(clean) == 1 and clean.isalpha():
        return True
        
    # 5. Generic background descriptions
    for prefix in GENERIC_MOB_PREFIXES:
        if clean_lower == prefix.strip() or clean_lower.startswith(prefix):
            return True
            
    return clean_lower in GENERIC_DISPOSABLE_NAMES

def clean_glossary_and_aliases():
    print("=" * 60)
    print("  TLAS Character Glossary & Profile Cleanup")
    print("=" * 60)
    
    # 1. Load Glossary
    if not os.path.exists(GLOSSARY_PATH):
        print(f"[Error] Glossary not found at {GLOSSARY_PATH}")
        return
        
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        glossary = json.load(f)
        
    raw_characters = glossary.get("Characters", {})
    print(f"\n[1] Total characters in raw glossary: {len(raw_characters)}")
    
    # Filter valid characters
    valid_characters: Dict[str, dict] = {}
    removed_chars: List[str] = []
    
    for char_name, meta in raw_characters.items():
        if is_garbage_or_disposable(char_name):
            removed_chars.append(char_name)
        else:
            valid_characters[char_name] = meta
            
    print(f"    - Kept valid characters : {len(valid_characters)}")
    print(f"    - Removed garbage/mobs  : {len(removed_chars)}")
    
    glossary["Characters"] = dict(sorted(valid_characters.items()))
    with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=2, ensure_ascii=False)
    print(f"    -> Saved cleaned glossary to {GLOSSARY_PATH}")
    
    # 2. Build Whitelist Set & Canonical Lookups
    canonical_whitelist: Set[str] = set(valid_characters.keys())
    known_essentials = {
        "Akane", "Akira", "Alisa", "Arisa", "Dan", "Desi", "Drake", "Enjo",
        "Erica", "Executive", "Foregrave", "Godmother", "Hatta", "Headmistress",
        "Honda", "Janice", "Jikan CEO", "Kin", "Kosai", "Lily", "Lyra",
        "Masaru", "Mayor", "Mike", "Natalie", "Otto", "Raven", "Reiko",
        "Rimi", "Ritchie", "Rum", "Saru", "Shion", "The Earl", "The Manager",
        "Turbo", "Wallace"
    }
    canonical_whitelist.update(known_essentials)
    
    # 3. Clean Alias Mapping
    cleaned_alias_map: Dict[str, str] = {}
    if os.path.exists(ALIAS_PATH):
        with open(ALIAS_PATH, "r", encoding="utf-8") as f:
            raw_aliases = json.load(f)
            
        print(f"\n[2] Total aliases in raw alias mapping: {len(raw_aliases)}")
        for alias, target in raw_aliases.items():
            alias_clean = alias.strip().lower()
            target_clean = target.strip()
            
            # Resolve target to whitelist
            matched_canonical = None
            for can in canonical_whitelist:
                if can.lower() == target_clean.lower():
                    matched_canonical = can
                    break
            
            # If target matches a valid canonical and alias is not garbage
            if matched_canonical and not is_garbage_or_disposable(alias):
                cleaned_alias_map[alias_clean] = matched_canonical
            elif matched_canonical and alias_clean == matched_canonical.lower():
                cleaned_alias_map[alias_clean] = matched_canonical

    # Ensure all canonical names map to themselves
    for can in canonical_whitelist:
        cleaned_alias_map[can.lower()] = can
        
    with open(ALIAS_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(cleaned_alias_map.items())), f, indent=2, ensure_ascii=False)
    print(f"    - Cleaned valid aliases : {len(cleaned_alias_map)}")
    print(f"    -> Saved cleaned alias mapping to {ALIAS_PATH}")
    
    # 4. Clean Profiles Directory
    print(f"\n[3] Cleaning profiles directory...")
    if not os.path.exists(PROFILES_DIR):
        print(f"[Error] Profiles dir not found: {PROFILES_DIR}")
        return
        
    # Backup
    if not os.path.exists(BACKUP_DIR):
        print(f"    - Creating backup at {BACKUP_DIR}...")
        shutil.copytree(PROFILES_DIR, BACKUP_DIR)
        print("    -> Backup complete.")
        
    profile_files = glob.glob(os.path.join(PROFILES_DIR, "*.json"))
    deleted_count = 0
    kept_count = 0
    
    for pf in profile_files:
        filename = os.path.basename(pf)
        char_name = filename.replace(".json", "").strip()
        
        # Check if matches valid canonical
        is_valid = False
        matched_canon = None
        for can in canonical_whitelist:
            safe_name = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in can).strip()
            if char_name.lower() == can.lower() or char_name.lower() == safe_name.lower():
                is_valid = True
                matched_canon = can
                break
                
        if not is_valid or is_garbage_or_disposable(char_name):
            print(f"    [DELETE JUNK] Removing {filename}")
            try:
                os.remove(pf)
                deleted_count += 1
            except Exception as e:
                print(f"    [Error] Could not remove {filename}: {e}")
        else:
            kept_count += 1
            
    print(f"\n[SUMMARY]")
    print(f"  Valid Profiles Kept    : {kept_count}")
    print(f"  Junk Profiles Deleted  : {deleted_count}")
    print(f"  Backup Saved At        : {BACKUP_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    clean_glossary_and_aliases()
