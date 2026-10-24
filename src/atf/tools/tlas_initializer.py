import json
import os
import re

def generate_volume1_taxonomy(base_dir):
    """Generates the Comprehensive TLAS Taxonomy matching SDD-005."""
    taxonomy = {
        "version": "1.2",
        "description": "TLAS Comprehensive Taxonomy (Volume 1) with Pronoun Constraints",
        "categories": {
            "GND": {"name": "Gender", "scope": "Character", "type": "Static"},
            "AGE": {"name": "Age Group", "scope": "Character", "type": "Static"},
            "SPC": {"name": "Species", "scope": "Character", "type": "Static"},
            "PER": {"name": "Personality", "scope": "Character", "type": "Timeline"},
            "SPR": {"name": "Speech Habit", "scope": "Character", "type": "Timeline"},
            "VAL": {"name": "Values & Beliefs", "scope": "Character", "type": "Timeline"},
            "REL": {"name": "Relationship", "scope": "Hybrid", "type": "Timeline"},
            "INT": {"name": "Intent", "scope": "Dialogue", "type": "Dynamic"},
            "EMO": {"name": "Emotion", "scope": "Dialogue", "type": "Dynamic"},
            "REG": {"name": "Register", "scope": "Output", "type": "Dynamic"},
            "TON": {"name": "Tone", "scope": "Dialogue", "type": "Dynamic"},
            "SIT": {"name": "Situation", "scope": "Dialogue", "type": "Dynamic"},
            "CTX": {"name": "Context", "scope": "Dialogue", "type": "Dynamic"},
            "BEL": {"name": "Beliefs", "scope": "Character", "type": "Timeline"}
        },
        "pronoun_options": {
            "self": ["ผม", "ฉัน", "เรา", "ข้า", "หนู", "กู", "ดิฉัน", "ข้าพเจ้า", "พี่", "น้อง", "ลุง", "ป้า", "ตา", "ยาย"],
            "target": ["คุณ", "นาย", "เธอ", "แก", "มึง", "ท่าน", "เอ็ง", "เจ้า", "พี่", "น้อง", "ลุง", "ป้า", "ตา", "ยาย"],
            "ending": ["ครับ", "ค่ะ", "วะ", "โว้ย", "เพคะ", "พ่ะย่ะค่ะ", "ขอรับ", "เจ้าค่ะ", "จ้ะ", "จ๊ะ", "ฮะ", "เว้ย", ""]
        },
        "pronoun_mapping_rules": [
            {"priority_score": 100, "conditions": {"gender": "MALE", "age": "CHILD"}, "pronouns": {"self": "ผม", "target": "พี่", "ending": "ครับ"}},
            {"priority_score": 100, "conditions": {"gender": "FEMALE", "age": "CHILD"}, "pronouns": {"self": "หนู", "target": "พี่", "ending": "ค่ะ"}},
            {"priority_score": 50, "conditions": {"gender": "MALE", "personality": "PER_SOC_RUDE"}, "pronouns": {"self": "ฉัน", "target": "แก", "ending": "วะ"}},
            {"priority_score": 50, "conditions": {"gender": "FEMALE", "personality": "PER_SOC_RUDE"}, "pronouns": {"self": "ฉัน", "target": "แก", "ending": "วะ"}},
            {"priority_score": 40, "conditions": {"gender": "MALE", "personality": "PER_VIBE_ARROGANT"}, "pronouns": {"self": "ข้า", "target": "เจ้า", "ending": ""}},
            {"priority_score": 30, "conditions": {"gender": "MALE", "personality": "PER_SOC_POLITE"}, "pronouns": {"self": "ผม", "target": "คุณ", "ending": "ครับ"}},
            {"priority_score": 30, "conditions": {"gender": "FEMALE", "personality": "PER_SOC_POLITE"}, "pronouns": {"self": "ดิฉัน", "target": "คุณ", "ending": "ค่ะ"}},
            {"priority_score": 10, "conditions": {"gender": "MALE"}, "pronouns": {"self": "ผม", "target": "คุณ", "ending": "ครับ"}},
            {"priority_score": 10, "conditions": {"gender": "FEMALE"}, "pronouns": {"self": "ฉัน", "target": "คุณ", "ending": "ค่ะ"}},
            {"priority_score": 1, "conditions": {}, "pronouns": {"self": "ฉัน", "target": "คุณ", "ending": ""}}
        ],
        "relationship_pronoun_rules": [
            {"priority_score": 80, "conditions": {"relation": "REL_WORK_BOSS", "gender": "MALE"}, "pronouns": {"self": "ผม", "target": "บอส", "ending": "ครับ"}},
            {"priority_score": 80, "conditions": {"relation": "REL_WORK_BOSS", "gender": "FEMALE"}, "pronouns": {"self": "ดิฉัน", "target": "บอส", "ending": "ค่ะ"}},
            {"priority_score": 90, "conditions": {"relation": "REL_FAMILY_PARENT"}, "pronouns": {"self": "หนู", "target": "พ่อ/แม่", "ending": ""}},
            {"priority_score": 70, "conditions": {"relation": "REL_ENEMY"}, "pronouns": {"self": "ฉัน", "target": "แก", "ending": ""}},
            {"priority_score": 60, "conditions": {"relation": "REL_FRIEND", "gender": "MALE"}, "pronouns": {"self": "ฉัน", "target": "นาย", "ending": ""}},
            {"priority_score": 60, "conditions": {"relation": "REL_FRIEND", "gender": "FEMALE"}, "pronouns": {"self": "ฉัน", "target": "เธอ", "ending": ""}}
        ],
        "tags": {
            # PER
            "PER_SOC_POLITE": {"desc": "สุภาพ, อ่อนน้อม, ให้เกียรติคนอื่น"},
            "PER_SOC_RUDE": {"desc": "หยาบคาย, ไม่สนมารยาท"},
            "PER_SOC_OUTGOING": {"desc": "ร่าเริง, เข้าสังคมเก่ง, คุยเก่ง"},
            "PER_SOC_INTROVERT": {"desc": "เก็บตัว, เงียบขรึม, พูดน้อย"},
            "PER_MIND_LOGICAL": {"desc": "มีเหตุผล, คิดวิเคราะห์, เยือกเย็น"},
            "PER_MIND_EMOTIONAL": {"desc": "ใช้อารมณ์นำ, อ่อนไหวง่าย"},
            "PER_MIND_CUNNING": {"desc": "เจ้าเล่ห์, มีเล่ห์เหลี่ยม"},
            "PER_MIND_NAIVE": {"desc": "ไร้เดียงสา, ซื่อตรง, อ่อนต่อโลก"},
            "PER_VIBE_CUTE": {"desc": "น่ารัก, สดใส, น่าทะนุถนอม"},
            "PER_VIBE_SERIOUS": {"desc": "จริงจัง, ดุดัน, น่าเกรงขาม"},
            "PER_VIBE_FLIRTY": {"desc": "เจ้าชู้, ขี้หลี, ชอบหยอด"},
            "PER_VIBE_ARROGANT": {"desc": "หยิ่งยโส, ทะนงตัว"},
            # SPR
            "SPR_HESITANT": {"desc": "พูดติดอ่าง, ลังเล"},
            "SPR_DIRECT": {"desc": "พูดขวานผ่าซาก, ตรงไปตรงมา"},
            "SPR_SARCASTIC": {"desc": "ชอบพูดประชดประชัน, แดกดัน"},
            "SPR_POETIC": {"desc": "พูดจาภาษาสละสลวย, เหมือนบทกวี"},
            "SPR_LAZY": {"desc": "พูดเนือยๆ, ลากเสียงยาว, ขี้เกียจพูด"},
            "SPR_ENERGETIC": {"desc": "พูดรัวเร็ว, ตื่นเต้นตลอดเวลา"},
            "SPR_POLITE_SUFFIX": {"desc": "ลงท้ายด้วย ครับ/ค่ะ/เจ้าค่ะ เสมอ"},
            "SPR_SLANG": {"desc": "ชอบใช้คำสแลง, คำหยาบ, ภาษาวิบัติ"},
            # VAL
            "VAL_DUTY": {"desc": "ยึดมั่นในหน้าที่, กฎระเบียบ"},
            "VAL_FREEDOM": {"desc": "รักอิสระ, เกลียดการถูกบังคับ"},
            "VAL_FAMILY": {"desc": "ครอบครัว/พวกพ้องต้องมาก่อน"},
            "VAL_POWER": {"desc": "บูชาความแข็งแกร่ง, อำนาจ"},
            "VAL_MONEY": {"desc": "หน้าเงิน, ทำทุกอย่างเพื่อผลประโยชน์"},
            "VAL_COMPASSION": {"desc": "มีเมตตา, ชอบช่วยเหลือผู้อื่น"},
            # REL
            "REL_FAMILY_PARENT": {"desc": "พ่อ/แม่/ผู้ปกครอง"},
            "REL_FAMILY_CHILD": {"desc": "ลูก/ผู้อยู่ใต้ปกครอง"},
            "REL_FAMILY_SIBLING": {"desc": "พี่น้อง"},
            "REL_WORK_BOSS": {"desc": "เจ้านาย/ผู้บังคับบัญชา"},
            "REL_WORK_SUBORDINATE": {"desc": "ลูกน้อง/ผู้ใต้บังคับบัญชา"},
            "REL_FRIEND": {"desc": "เพื่อน/สหาย"},
            "REL_ENEMY": {"desc": "ศัตรู/คู่อริ"},
            "REL_STRANGER": {"desc": "คนแปลกหน้า"},
            "REL_LOVER": {"desc": "คนรัก/คู่หมั้น"},
            # INT
            "INT_INFORM": {"desc": "แจ้งให้ทราบ, เล่าเรื่อง"},
            "INT_QUESTION": {"desc": "ตั้งคำถาม, สงสัย"},
            "INT_COMMAND": {"desc": "สั่งการ, บังคับ"},
            "INT_REQUEST": {"desc": "ขอร้อง, วิงวอน"},
            "INT_THREATEN": {"desc": "ข่มขู่, คุกคาม"},
            "INT_COMFORT": {"desc": "ปลอบโยน, ให้กำลังใจ"},
            "INT_MOCK": {"desc": "เยาะเย้ย, ถากถาง"},
            # EMO
            "EMO_NEUTRAL": {"desc": "ปกติ, เรียบเฉย"},
            "EMO_JOY": {"desc": "ดีใจ, มีความสุข"},
            "EMO_ANGER": {"desc": "โกรธ, หงุดหงิด"},
            "EMO_SADNESS": {"desc": "เศร้า, เสียใจ"},
            "EMO_FEAR": {"desc": "หวาดกลัว, ตระหนก"},
            "EMO_SURPRISE": {"desc": "ประหลาดใจ, ตกใจ"},
            "EMO_DISGUST": {"desc": "รังเกียจ, ขยะแขยง"},
            # REG
            "REG_ROYAL": {"desc": "คำราชาศัพท์"},
            "REG_FORMAL": {"desc": "ทางการ, สุภาพมาก"},
            "REG_POLITE": {"desc": "สุภาพทั่วไป (คนแปลกหน้า)"},
            "REG_CASUAL": {"desc": "กันเอง (เพื่อน, คนสนิท)"},
            "REG_VULGAR": {"desc": "หยาบคาย"},
            # TON
            "TON_SERIOUS": {"desc": "จริงจัง, ขึงขัง"},
            "TON_PLAYFUL": {"desc": "หยอกล้อ, ทีเล่นทีจริง"},
            "TON_SARCASTIC": {"desc": "ประชดประชัน, แดกดัน"},
            "TON_AGGRESSIVE": {"desc": "ก้าวร้าว, คุกคาม, หาเรื่อง"},
            "TON_GENTLE": {"desc": "นุ่มนวล, อ่อนโยน"},
            "TON_HESITANT": {"desc": "ลังเล, ไม่มั่นใจ"},
            "TON_COLD": {"desc": "เย็นชา, ไร้เยื่อใย"},
            # SIT
            "SIT_PUBLIC": {"desc": "อยู่ต่อหน้าสาธารณชน หรือคนหมู่มาก"},
            "SIT_PRIVATE": {"desc": "อยู่ในที่รโหฐาน หรือคุยกันส่วนตัว"},
            "SIT_CRISIS": {"desc": "สถานการณ์ฉุกเฉิน, คอขาดบาดตาย"},
            "SIT_CEREMONY": {"desc": "พิธีการ, งานทางการ"},
            "SIT_CASUAL": {"desc": "สถานการณ์ชิวๆ, สบายๆ"},
            # CTX
            "CTX_SECRET": {"desc": "กำลังพูดความลับ, กระซิบ"},
            "CTX_PERSUASION": {"desc": "กำลังโน้มน้าวใจ"},
            "CTX_INTERROGATION": {"desc": "กำลังถูกสอบสวน หรือเค้นความจริง"},
            "CTX_FAREWELL": {"desc": "การกล่าวลา, สั่งเสีย"},
            # BEL
            "BEL_RELIGIOUS": {"desc": "ศรัทธาแรงกล้า (อาจมีคำเรียกเทพเจ้า/สวดมนต์)"},
            "BEL_ATHEIST": {"desc": "ไม่เชื่อในสิ่งศักดิ์สิทธิ์"},
            "BEL_SUPERSTITION": {"desc": "เชื่อเรื่องโชคลาง, ผีสาง"}
        }
    }
    
    with open(os.path.join(base_dir, "taxonomy.json"), "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
    print("[1/3] Comprehensive Taxonomy generated.")

def clean_raw_speaker_name(speaker: str) -> str:
    """Strips RPG Maker control codes (\\C[n], \\I[n], \\fb, etc.) to get pure character name."""
    if not speaker:
        return ""
    cleaned = re.sub(r"\\[A-Za-z]+(?:\[\d+\])?", "", speaker)
    cleaned = re.sub(r"\\[\{\}\.\|\!\^\$\\]", "", cleaned)
    cleaned = cleaned.replace(":", "").strip()
    return cleaned

def is_valid_speaker(speaker: str) -> bool:
    """Strict filtering rules for speaker extraction."""
    if not speaker or speaker == "Unknown": return False
    clean_spk = clean_raw_speaker_name(speaker)
    if not clean_spk: return False
    if len(clean_spk) > 30: return False
    if re.match(r'^c_?(\d+)?', clean_spk): return False # c_, c1012, etc
    if any(bad in clean_spk for bad in ["Window", "AUTHETICATION", "BLANK"]): return False
    if clean_spk.isupper() and len(clean_spk) > 10: return False # ALL CAPS commands
    if re.search(r'[^a-zA-Z0-9\s\'\.\-]', clean_spk): return False # Special chars not allowed
    return True

def is_generic_name(name: str) -> bool:
    generics = [
        "man", "woman", "girl", "boy", "guy", "customer", "fan", "staff", "member",
        "thug", "crowd", "voice", "kid", "child", "student", "teacher", "clerk",
        "officer", "guard", "soldier", "villager", "citizen", "person", "people",
        "adult", "teenager", "player", "everyone", "all", "both", "boss", "grunt",
        "punk", "lady", "host", "hostess", "bartender", "bystander", "waitress", "waiter",
        "maid", "servant", "worker", "employee", "director", "executive", "escort"
    ]
    name_lower = name.lower()
    for g in generics:
        if re.search(rf"\b{g}\b", name_lower):
            return True
    return False

def normalize_name(name: str) -> str:
    """Strip spaces and special characters, and lowercase it."""
    return re.sub(r'[^a-zA-Z0-9]', '', name.lower())

def extract_speakers_from_scenes(scenes_path):
    """Extracts unique speaker names from rpgm_static_routes_v2.json using Scene-Based Air Time and Deduplication."""
    scene_data = {}
    try:
        with open(scenes_path, "r", encoding="utf-8") as f:
            clusters = json.load(f)
            
        s_idx = 0
        for cluster in clusters:
            for scene in cluster.get("scenes", []):
                spks = {}
                for dialogue in scene.get("dialogues", []):
                    speaker = dialogue.get("speaker", "").strip()
                    if is_valid_speaker(speaker):
                        spks[speaker] = spks.get(speaker, 0) + 1
                if spks:
                    scene_data[s_idx] = {
                        "total_lines": sum(spks.values()),
                        "speakers": spks
                    }
                s_idx += 1
    except Exception as e:
        print(f"Error reading scenes JSON: {e}")
        return {}

    if not scene_data:
        return {}

    # Global speaker counts for canonical naming
    raw_counts = {}
    for data in scene_data.values():
        for spk, c in data["speakers"].items():
            raw_counts[spk] = raw_counts.get(spk, 0) + c

    sorted_speakers = sorted(raw_counts.items(), key=lambda x: x[1], reverse=True)
    merged_groups = []
    
    import difflib
    SIMILARITY_THRESHOLD = 0.90
    
    for name, count in sorted_speakers:
        norm = normalize_name(name)
        if not norm:
            continue
            
        matched = False
        for group in merged_groups:
            if norm == group["norm"]:
                matched = True
            else:
                sim = difflib.SequenceMatcher(None, norm, group["norm"]).ratio()
                if sim >= SIMILARITY_THRESHOLD:
                    matched = True
                    
            if matched:
                group["global_lines"] += count
                group["aliases"].add(name)
                break
                
        if not matched:
            merged_groups.append({
                "canonical": name,
                "norm": norm,
                "global_lines": count,
                "aliases": {name}
            })
            
    valid_speakers = {}
    
    for group in merged_groups:
        canonical = group["canonical"]
        aliases = group["aliases"]
        
        scene_participations = []
        for data in scene_data.values():
            group_lines_in_scene = sum(data["speakers"].get(a, 0) for a in aliases)
            if group_lines_in_scene > 0:
                part = group_lines_in_scene / data["total_lines"]
                scene_participations.append(part)
                
        scene_count = len(scene_participations)
        avg_part = sum(scene_participations) / scene_count if scene_count > 0 else 0
        total_lines_spoken = sum(data["speakers"].get(a, 0) for data in scene_data.values() for a in aliases)
        
        is_generic = is_generic_name(canonical)
        char_type = "Generic" if is_generic else "ProperNoun"
        
        keep = False
        if is_generic:
            if scene_count >= 5 and avg_part >= 0.10 and total_lines_spoken >= 10:
                keep = True
        else:
            if scene_count >= 3 or (scene_count >= 1 and avg_part >= 0.20 and total_lines_spoken >= 20):
                keep = True
                
        if keep:
            aliases_list = sorted(list(aliases - {canonical}))
            valid_speakers[canonical] = {
                "type": char_type,
                "aliases": aliases_list
            }
                
    return valid_speakers

def extract_database_terms(rpgm_data_dir: str = None):
    """สกัดข้อมูล Items, Places, Skills, System_UI จากฐานข้อมูล RPG Maker JSON"""
    terms_data = {"Items": {}, "Places": {}, "Skills": {}, "System_UI": {}}
    if not rpgm_data_dir or not os.path.exists(rpgm_data_dir):
        return terms_data

    # 1. Items
    items_path = os.path.join(rpgm_data_dir, "Items.json")
    if os.path.exists(items_path):
        try:
            with open(items_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
            for item in raw_items:
                if item and isinstance(item, dict):
                    name = item.get("name", "").strip()
                    if name:
                        terms_data["Items"][name] = {
                            "th": name,
                            "type": "Item",
                            "enforce": True,
                            "id": item.get("id"),
                            "description": item.get("description", "").strip()
                        }
        except Exception:
            pass

    # 2. Places (MapInfos)
    maps_path = os.path.join(rpgm_data_dir, "MapInfos.json")
    if os.path.exists(maps_path):
        try:
            with open(maps_path, "r", encoding="utf-8") as f:
                raw_maps = json.load(f)
            for m in raw_maps:
                if m and isinstance(m, dict):
                    name = m.get("name", "").strip()
                    if name:
                        terms_data["Places"][name] = {
                            "th": name,
                            "type": "Place",
                            "enforce": True,
                            "id": m.get("id"),
                            "parentId": m.get("parentId", 0)
                        }
        except Exception:
            pass

    # 3. Skills
    skills_path = os.path.join(rpgm_data_dir, "Skills.json")
    if os.path.exists(skills_path):
        try:
            with open(skills_path, "r", encoding="utf-8") as f:
                raw_skills = json.load(f)
            for s in raw_skills:
                if s and isinstance(s, dict):
                    name = s.get("name", "").strip()
                    if name:
                        terms_data["Skills"][name] = {
                            "th": name,
                            "type": "Skill",
                            "enforce": True,
                            "id": s.get("id"),
                            "description": s.get("description", "").strip()
                        }
        except Exception:
            pass

    # 4. System_UI
    system_path = os.path.join(rpgm_data_dir, "System.json")
    if os.path.exists(system_path):
        try:
            with open(system_path, "r", encoding="utf-8") as f:
                raw_sys = json.load(f)
            raw_terms = set()
            terms = raw_sys.get("terms", {})
            for subkey in ["basic", "commands", "params"]:
                for t in terms.get(subkey, []):
                    if t and isinstance(t, str) and t.strip():
                        raw_terms.add(t.strip())
            for subkey in ["elements", "skillTypes", "weaponTypes", "armorTypes", "equipTypes"]:
                for item in raw_sys.get(subkey, []):
                    if item and isinstance(item, str) and item.strip():
                        raw_terms.add(item.strip())
            for term in sorted(raw_terms):
                terms_data["System_UI"][term] = {
                    "th": term,
                    "type": "System",
                    "enforce": True
                }
        except Exception:
            pass

    return terms_data

def generate_glossary(speakers, base_dir, rpgm_data_dir: str = None):
    """Generates the Glossary for locking character names, items, places, skills, and system terms."""
    glossary_path = os.path.join(base_dir, "tlas_glossary.json")
    existing_glossary = {}
    if os.path.exists(glossary_path):
        try:
            with open(glossary_path, "r", encoding="utf-8") as f:
                existing_glossary = json.load(f)
        except Exception:
            pass

    characters = {}
    for spk, data in speakers.items():
        # Preserve existing Thai translation if available
        existing_th = spk
        if "Characters" in existing_glossary and spk in existing_glossary["Characters"]:
            existing_th = existing_glossary["Characters"][spk].get("th", spk)

        characters[spk] = {
            "th": existing_th,
            "type": data["type"],
            "enforce": True,
            "aliases": data["aliases"]
        }
        
    db_terms = extract_database_terms(rpgm_data_dir)

    glossary = {
        "Characters": characters,
        "Items": existing_glossary.get("Items", db_terms.get("Items", {})),
        "Places": existing_glossary.get("Places", db_terms.get("Places", {})),
        "Skills": existing_glossary.get("Skills", db_terms.get("Skills", {})),
        "System_UI": existing_glossary.get("System_UI", db_terms.get("System_UI", {}))
    }
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=2, ensure_ascii=False)
    print(f"[2/3] Glossary generated with {len(speakers)} valid characters and database terms.")


def generate_character_profiles(speakers, base_dir):
    """Generates SDD-006 compliant base profiles for all characters."""
    profiles_dir = os.path.join(base_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    for spk in speakers.keys():
        safe_filename = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in spk).strip()
        if not safe_filename: continue
            
        profile = {
            "character_id": f"CHAR_{safe_filename.upper()}",
            "name": spk,
            "identity": {
                "gender": "UNKNOWN",
                "species": "UNKNOWN"
            },
            "base_state": {
                "personality": [],
                "speech_habit": [],
                "values": [],
                "relationships": [] # Should contain elements with target_character_id, relation_tags
            },
            "timeline_states": [] 
        }
        
        filepath = os.path.join(profiles_dir, f"{safe_filename}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
            
    print(f"[3/3] Created {len(speakers)} empty Character Profiles ready for RAG Analysis.")

if __name__ == "__main__":
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\Example RPMG Game\data\tlas"
    scenes_path = os.path.join(tlas_dir, "rpgm_static_routes_v2.json")
    
    os.makedirs(tlas_dir, exist_ok=True)
    
    print("Starting TLAS Initialization (Strict Schema & Garbage Filtering)...")
    generate_volume1_taxonomy(tlas_dir)
    
    speakers = extract_speakers_from_scenes(scenes_path)
    if speakers:
        generate_glossary(speakers, tlas_dir)
        generate_character_profiles(speakers, tlas_dir)
        print("\nInitialization Complete!")
    else:
        print("\nFailed to extract valid speakers. Initialization aborted.")
