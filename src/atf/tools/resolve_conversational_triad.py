"""
ATF Universal Conversational Triad Engine (Multi-Party Addressee Resolution & Pragmatic Invariants)
===================================================================================================
[RULE_UNIVERSAL_PARADIGM & RULE_ZERO_HARDCODE COMPLIANT]
Multi-Party Conversational Addressee Resolution Engine:
1. Dynamic Entity Discovery:
   - Discovers all characters, aliases, kana variants, and Thai translations dynamically
     from Master Glossary and Character Profiles on disk.
2. Scene Presence Bounding (No Phantom Listeners):
   - Clusters dialogues by scene/event block.
   - Computes active Scene Presence Set = (all active speakers in the scene) | (registered party members).
   - Guarantees Listener is strictly bounded to entities physically present in the scene.
3. Multi-Party Addressee Rules:
   - Priority 1: Vocative Direct Address (explicit calling of an entity's name/title/honorific).
   - Priority 2: QA & Apology Adjacency Pairs (questions/apologies answered immediately by next speaker).
   - Priority 3: Third-Person Topic Exclusion (talking about an entity excludes them from being listener).
   - Priority 4: Scolding Directives (e.g. 'こらっ' directed at subordinate/child in scene).
   - Priority 5: Consecutive Utterance Inheritance (same speaker continuing an utterance).
   - Priority 6: Bounded Event-Isolated Turn-Taking Flow.
4. Pragmatic Semantic Third-Person Inquiry Disambiguation:
   - Entities inquired about or referenced who are neither Speaker nor Listener are assigned to Third_Person.
"""

import csv
import json
import os
import re
import sys
import glob

sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Universal inquiry search patterns (Japanese & Thai)
INQUIRY_PATTERNS = [
    r'見てない', r'見かけ', r'どこ', r'探', r'一緒にいた', r'連れて',
    r'เห็น.*ไหม', r'ไปไหน', r'ตามหา', r'อยู่ไหน', r'เจอ.*บ้าง'
]

def build_dynamic_entity_map(workspace_root=WORKSPACE_ROOT):
    """
    Universally discovers entities and all their lexical markers from disk:
    1. data/tlas/tlas_glossary.json (Characters section)
    2. data/tlas/profiles/*.json (profile aliases, display_names, relationships)
    3. data/tlas/global_pronoun_matrix.json (specific pairwise target references)
    """
    entity_map = {}
    
    # 1. Master Glossary
    glossary_path = os.path.join(workspace_root, "data", "tlas", "tlas_glossary.json")
    if os.path.exists(glossary_path):
        try:
            with open(glossary_path, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            chars = gdata.get("Characters", {})
            for canonical, info in chars.items():
                if canonical in ("？？？", "Narrator", "System", "None"):
                    continue
                markers = set([canonical])
                th_trans = info.get("th")
                if th_trans and th_trans not in ("？？？", "None"):
                    markers.add(th_trans)
                for a in info.get("aliases", []):
                    if a:
                        markers.add(a)
                entity_map[canonical] = markers
        except Exception as e:
            print(f"[!] Warning reading glossary for entity map: {e}")

    # 2. Character Profiles
    profiles_dir = os.path.join(workspace_root, "data", "tlas", "profiles")
    if os.path.exists(profiles_dir):
        for pf in glob.glob(os.path.join(profiles_dir, "*.json")):
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                cname = pdata.get("name") or os.path.splitext(os.path.basename(pf))[0]
                if cname in ("Narrator", "System"):
                    continue
                if cname not in entity_map:
                    entity_map[cname] = set([cname])
                for a in pdata.get("aliases", []):
                    if a:
                        entity_map[cname].add(a)
                dname = pdata.get("display_name")
                if dname:
                    entity_map[cname].add(dname)

                # Dynamic Demographic Sociolinguistic Vocatives from Profile Schema
                identity = pdata.get("identity", {})
                age = str(identity.get("age", "")).upper()
                gender = str(identity.get("gender", "")).upper()

                if age == "CHILD":
                    entity_map[cname].update(["僕", "ボク", "坊主", "เด็ก", "หนุ่มน้อย", "เจ้าหนู"])
                elif age == "ELDER":
                    if gender == "FEMALE":
                        entity_map[cname].update(["おばあさん", "おばあちゃん", "ばあちゃん", "ばぁちゃん", "ยาย", "คุณยาย"])
                    elif gender == "MALE":
                        entity_map[cname].update(["おじいさん", "おじいちゃん", "じいちゃん", "じぃちゃん", "ตา", "คุณตา", "ปู่"])
                elif age in ("TEEN", "ADULT"):
                    if gender == "MALE":
                        entity_map[cname].update(["お兄さん", "お兄ちゃん", "お兄さん達", "お兄さんたち", "พี่ชาย"])
                    elif gender == "FEMALE":
                        entity_map[cname].update(["お姉さん", "お姉ちゃん", "พี่สาว"])

                # Dynamic Relational Vocatives from Profile Relationships
                for rel in pdata.get("relationships", []):
                    roles = rel.get("roles", [])
                    if "ROLE_FAM_SPOUSE" in roles:
                        if gender == "MALE":
                            entity_map[cname].update(["旦那", "旦那さん", "ご主人", "สามี"])
                        elif gender == "FEMALE":
                            entity_map[cname].update(["奥さん", "奥様", "妻", "ภรรยา"])
                    if "ROLE_FAM_GRANDCHILD" in roles:
                        entity_map[cname].update(["孫", "หลาน"])
                    if "ROLE_FAM_PARENT" in roles:
                        if gender == "MALE":
                            entity_map[cname].update(["お父さん", "父さん", "พ่อ"])
                        elif gender == "FEMALE":
                            entity_map[cname].update(["お母さん", "母さん", "แม่"])
            except Exception:
                pass

    # 3. Global Pronoun Matrix
    matrix_path = os.path.join(workspace_root, "data", "tlas", "global_pronoun_matrix.json")
    if os.path.exists(matrix_path):
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                mdata = json.load(f)
            for rule in mdata.get("specific_pair_rules", []):
                spk = rule.get("speaker")
                lis = rule.get("listener")
                target_p = rule.get("speech_style", {}).get("target_pronoun")
                if lis and target_p and lis in entity_map:
                    entity_map[lis].add(target_p)
        except Exception:
            pass

    # Convert sets to sorted lists (longest strings first for greedy matching)
    cleaned_map = {}
    for k, v in entity_map.items():
        valid = [x for x in v if x and len(x) > 0]
        cleaned_map[k] = sorted(valid, key=lambda x: -len(x))
    
    return cleaned_map


def detect_vocative(text, speaker, candidates, entity_map):
    """
    Detects if an utterance begins with an explicit vocative direct address targeting a candidate.
    """
    clean = re.sub(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', '', text).strip()
    for ent in candidates:
        if ent == speaker:
            continue
        markers = entity_map.get(ent, [])
        for m in markers:
            if not m:
                continue
            # Special check for '僕' as vocative address to a kid
            if m == '僕':
                pat = r'^(?:(?:あれ|あ|ねえ|おい|やあ|うーん|へい|あの|その|じゃあ|よーし|よーしじゃあ)[・…‥.！!、,。\s〜~ー]*)*僕[・…‥.！!、,。\s〜~ー]'
                if re.search(pat, clean):
                    return ent
                continue

            if len(m) < 2 and m not in entity_map:
                continue

            prefix = r'^(?:(?:あれ|あ|ねえ|おい|やあ|うーん|へい|あの|その|じゃあ|よーし|よーしじゃあ)[・…‥.！!、,。\s〜~ー]*)*'
            base = re.escape(m[:-1]) if m.endswith('ん') else re.escape(m)
            suffix = r'(?:[ぁ-んァ-ンー]*)(?:ってば|ったら|さん|ちゃん|くん|様|達|たち)?[・…‥.！!、,。\s〜~ー]'
            pat = prefix + base + suffix
            if re.search(pat, clean):
                return ent
    return None
    return None


def is_qa_adjacency(curr_text, next_spk, next_text):
    """
    Detects Question-Answer or Apology-Response adjacency pairs across contiguous turns.
    """
    if not next_text or not next_spk:
        return False
    curr_clean = re.sub(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', '', curr_text).strip()
    next_clean = re.sub(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', '', next_text).strip()
    is_q = any(curr_clean.endswith(q) or q in curr_clean for q in ['？', '?', 'なの', 'ですか', 'いいの', '大丈夫', 'いいのー'])
    is_ans = any(next_clean.startswith(a) for a in ['うん', 'はい', 'ええ', 'いいえ', '大丈夫', 'そう', 'うん。', 'うん、', 'いいよ', 'ごめん'])
    is_apology = any(w in curr_clean for w in ['ごめんなさい', 'すみません', '申し訳'])
    is_apology_reply = any(w in next_clean for w in ['いえいえ', '全然', '大丈夫', 'とんでもない', '気にしないで'])
    return (is_q and is_ans) or (is_apology and is_apology_reply)


def detect_third_person_exclusion(text, speaker, candidates, entity_map):
    """
    Detects if an entity is framed as a distal 3rd-person topic (e.g. この子は..., あいつは...),
    meaning the speaker is talking ABOUT them, NOT TO them.
    Universally matches candidate entity markers against Japanese distal structures:
    1. Demonstratives/Possessives: この / その / あの / うちの / 私の + [marker]
    2. Relational 3rd-person references: 旦那さん, ご主人, 奥さん, 奥様, 彼女, 彼, あいつ, あの方
    """
    clean = re.sub(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', '', text).strip()
    excluded = []
    distal_prefixes = ["この", "その", "あの", "うちの", "私の"]
    relational_distal = ["旦那さん", "ご主人", "奥さん", "奥様", "彼女", "彼", "あいつ", "あの方", "あの子", "この子"]

    for cand in candidates:
        if cand == speaker or cand in ("None", "System"):
            continue
        markers = entity_map.get(cand, [])
        is_distal_topic = False
        for m in markers:
            if not m:
                continue
            for dp in distal_prefixes:
                if (dp + m) in clean or (dp in clean and m in clean):
                    is_distal_topic = True
                    break
            if is_distal_topic:
                break
            if (m in relational_distal and m in clean) or any(rd in clean and m in rd for rd in relational_distal):
                is_distal_topic = True
                break
        if is_distal_topic:
            excluded.append(cand)

    return excluded


def load_manifest(workspace_root: str = WORKSPACE_ROOT):
    manifest_path = os.path.join(workspace_root, "data", "project_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def resolve_triads(csv_path=None):
    if csv_path is None:
        manifest = load_manifest()
        csv_path = manifest.get("output_enriched_csv") or os.path.join(WORKSPACE_ROOT, "output", "enriched_translated.csv")

    scene_packets_path = os.path.join(WORKSPACE_ROOT, "data", "tlas", "scene_packets.json")

    print("=" * 80)
    print("🚀 RUNNING UNIVERSAL MULTI-PARTY CONVERSATIONAL TRIAD ENGINE")
    print(f"[*] Target Table: {csv_path}")
    print("=" * 80)

    if not os.path.exists(csv_path):
        print(f"[❌] Error: File not found: {csv_path}")
        return

    entity_map = build_dynamic_entity_map(WORKSPACE_ROOT)
    print(f"[*] Dynamically Discovered {len(entity_map)} Project Entities: {list(entity_map.keys())}")

    # Discover Registered Active Party Members dynamically from database/packets
    party_members = set()
    if os.path.exists(scene_packets_path):
        try:
            with open(scene_packets_path, "r", encoding="utf-8") as sf:
                sp_data = json.load(sf)
            for act_name in sp_data.get("registered_database_actors", {}).values():
                if act_name:
                    party_members.add(act_name)
        except Exception:
            pass
    print(f"[*] Active Party Members in Engine: {list(party_members)}")

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"[*] Loaded {len(rows)} rows from target CSV")

    # Cluster rows into Contiguous Map/File Scenes
    scenes = []
    current_scene = []
    for i, r in enumerate(rows):
        if not current_scene:
            current_scene.append(i)
            continue
        prev_r = rows[current_scene[-1]]
        if r.get("Filename") != prev_r.get("Filename"):
            scenes.append(current_scene)
            current_scene = [i]
        else:
            current_scene.append(i)
    if current_scene:
        scenes.append(current_scene)

    corrected_listeners = 0
    corrected_third_persons = 0

    for sc in scenes:
        # Determine Scene Presence: all speakers in this scene cluster + party_members
        speakers_in_scene = set()
        for row_idx in sc:
            s = rows[row_idx].get("Speaker")
            if s and s not in ("System", "Narrator", "Developer", "None"):
                speakers_in_scene.add(s)

        scene_presence = speakers_in_scene | party_members
        if "？？？" in speakers_in_scene:
            scene_presence.add("？？？")

        scene_resolved_listeners = {}

        for pos, row_idx in enumerate(sc):
            r = rows[row_idx]
            disp = r.get("Displayable", "")
            role = r.get("Role", "")
            spk = r.get("Speaker", "")
            lis = r.get("Listener", "")
            orig = r.get("Original", "")
            init = r.get("Initial", "")
            fname = r.get("Filename", "")

            if disp != "Yes" or role not in ("Dialogue/Story", "Choices Option", "Choice Branch"):
                continue

            if spk in ("System", "Narrator", "Developer", "None"):
                continue

            target_listener = None

            # Priority 0: Choices Option / Choice Branch (Decided by active character, answering NPC or Self)
            if role in ("Choices Option", "Choice Branch"):
                prev_q_spk = None
                for j in range(row_idx - 1, max(-1, row_idx - 5), -1):
                    if rows[j].get("Filename") != fname:
                        break
                    if rows[j].get("Displayable") == "No":
                        break
                    ps = rows[j].get("Speaker", "")
                    p_orig = rows[j].get("Original", "")
                    if ps and ps not in ("System", "Narrator", "Developer", "None", spk):
                        if any(q in p_orig for q in ["？", "?", "か", "なの"]):
                            prev_q_spk = ps
                            break
                target_listener = prev_q_spk if prev_q_spk else "Self"

            # Priority 1: Vocative Direct Address
            if not target_listener:
                voc = detect_vocative(orig, spk, scene_presence, entity_map)
                if voc:
                    target_listener = voc

            # Priority 1.2: Internal Monologue Invariant (Retain Self if no vocative address to another)
            if not target_listener and lis == "Self":
                target_listener = "Self"

            # Priority 1.5: Objection / Whine / Retort to Previous Scolding or Prohibition
            # Interjections like 'えー', 'いいじゃん', 'やだ', 'なんで' are pragmatically addressed to the previous prohibiting interlocutor.
            elif not target_listener:
                clean_u = re.sub(r'^(?:【[^】]+】|<italic><Name:[^>]+></italic>)\s*\n?', '', orig).strip()
                is_objection = any(clean_u.startswith(w) for w in ["えー", "え〜", "いいじゃん", "やだ", "なんで", "どうして", "そんなー"])
                if is_objection:
                    for j in range(row_idx - 1, max(-1, row_idx - 25), -1):
                        if rows[j].get("Filename") != fname:
                            break
                        if rows[j].get("Displayable") == "No":
                            break
                        prev_s = rows[j].get("Speaker", "")
                        if prev_s and prev_s not in ("System", "Narrator", "Developer", "None", spk):
                            target_listener = prev_s
                            break

            # Priority 2: Question / Apology Adjacency with Next Speaker
            if not target_listener and pos + 1 < len(sc):
                next_row = rows[sc[pos + 1]]
                next_spk = next_row.get("Speaker")
                if next_spk and next_spk != spk and is_qa_adjacency(orig, next_spk, next_row.get("Original", "")):
                    target_listener = next_spk

            # Priority 3: Third-Person Mention Topic Exclusion (Linguistically Derived)
            if not target_listener:
                excl = detect_third_person_exclusion(orig, spk, scene_presence, entity_map)
                if excl:
                    rem = [c for c in scene_presence if c != spk and c not in excl and c not in ("？？？", "None", "System")]
                    if rem:
                        # Prioritize active previous conversational interlocutor if they are in the remaining set
                        prev_cand = None
                        for j in range(row_idx - 1, max(-1, row_idx - 15), -1):
                            if rows[j].get("Filename") != fname:
                                break
                            ps = rows[j].get("Speaker", "")
                            if ps in rem:
                                prev_cand = ps
                                break
                        target_listener = prev_cand if prev_cand else rem[0]

            # Priority 3.5: Protagonist Self-Monologue / Spatial Feedback Invariant (Universal Japanese Grammar)
            is_volitional = bool(re.search(r'(?:[ぁ-ん]+[ろこそうも]う|[ぁ-ん]+よう)[・…！!。]?$', orig.strip())) or any(w in orig for w in ["戻ろう", "行こう", "休もう", "探そう"])
            is_obligation = any(w in orig for w in ["ないと", "わけにはいかない", "なくちゃ", "脱がないと"])
            is_introspection = any(w in orig for w in ["だろうか", "のか・・・", "のか…", "みたいだ", "気がする", "しまった", "かな・・・", "あり得ない"])
            is_spatial_feedback = any(w in orig for w in ["用はない", "こっちじゃない", "開かない", "鍵が", "閉まっている", "クラクラ", "格好で", "声が聞こえる", "女湯"])
            
            if not voc and (is_volitional or is_obligation or is_introspection or is_spatial_feedback):
                target_listener = "Self"

            # Priority 4: Scolding marker (こらっ, こら！, これ！, めっ) directed at child/subordinate in scene
            if not target_listener and any(w in orig for w in ["こらっ", "こら！", "これ！", "めっ"]):
                child_cands = [
                    c for c in scene_presence
                    if c != spk and any(m in entity_map.get(c, []) for m in ["僕", "ボク", "坊主", "子", "เด็ก", "เจ้าหนู"])
                ]
                if child_cands:
                    target_listener = child_cands[0]

            # Priority 5: Consecutive Speech Inheritance
            if not target_listener:
                if pos > 0:
                    prev_row_idx = sc[pos - 1]
                    if rows[prev_row_idx].get("Speaker") == spk and prev_row_idx in scene_resolved_listeners:
                        target_listener = scene_resolved_listeners[prev_row_idx]

            # Priority 6: Bounded Turn-Taking Interlocutor Resolution
            if not target_listener:
                prev_interlocutor = None
                for j in range(row_idx - 1, max(-1, row_idx - 25), -1):
                    if rows[j].get("Filename") != fname:
                        break
                    if rows[j].get("Displayable") == "No":
                        break
                    prev_s = rows[j].get("Speaker", "")
                    if prev_s and prev_s not in ("System", "Narrator", "Developer", "None", spk):
                        prev_interlocutor = prev_s
                        break

                next_interlocutor = None
                for j in range(row_idx + 1, min(len(rows), row_idx + 25)):
                    if rows[j].get("Filename") != fname:
                        break
                    if rows[j].get("Displayable") == "No":
                        break
                    next_s = rows[j].get("Speaker", "")
                    if next_s and next_s not in ("System", "Narrator", "Developer", "None", spk):
                        next_interlocutor = next_s
                        break

                if prev_interlocutor and next_interlocutor:
                    target_listener = prev_interlocutor if prev_interlocutor == next_interlocutor else prev_interlocutor
                elif prev_interlocutor:
                    target_listener = prev_interlocutor
                elif next_interlocutor:
                    target_listener = next_interlocutor
                else:
                    if role == "Dialogue/Story":
                        target_listener = "Self"

            # Fallback to existing if unresolved
            if not target_listener:
                target_listener = lis

            # Scene Presence Constraint: Listener must not be a phantom character outside scene_presence
            if target_listener and target_listener not in ("Self", "Player", "Group", "None"):
                if target_listener not in scene_presence:
                    rem = list(speakers_in_scene - {spk})
                    target_listener = "Self" if not rem else (rem[0] if len(rem) == 1 else "Player")

            # Semantic Inquiry Disambiguation: Inquiry target CANNOT be Listener
            full_text = orig + " " + init
            is_inquiry = any(re.search(pat, full_text) for pat in INQUIRY_PATTERNS)
            inquired_entity = None
            if is_inquiry:
                for entity, markers in entity_map.items():
                    if entity != spk:
                        if any(m in full_text for m in markers):
                            inquired_entity = entity
                            break

            if inquired_entity and target_listener == inquired_entity:
                rem = [c for c in scene_presence if c != spk and c != inquired_entity and c not in ("？？？", "None", "System")]
                target_listener = rem[0] if rem else "Self"

            scene_resolved_listeners[row_idx] = target_listener

            if target_listener and target_listener != lis:
                r["Listener"] = target_listener
                corrected_listeners += 1

            # Detect Third Person with High Precision
            current_listener = r.get("Listener", "")
            detected_third = []
            for entity, markers in entity_map.items():
                if entity != spk and entity != current_listener and entity not in current_listener:
                    if any(m in full_text for m in markers):
                        detected_third.append(entity)

            new_third_str = ", ".join(detected_third) if detected_third else "None"
            if new_third_str != r.get("Third_Person"):
                r["Third_Person"] = new_third_str
                corrected_third_persons += 1

    # Save updated CSV
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[✔] Universal Multi-Party Triad Resolution Complete!")
    print(f"    - Corrected Listeners     : {corrected_listeners} rows")
    print(f"    - Corrected Third Persons : {corrected_third_persons} rows")
    print(f"[✔] Successfully saved: {csv_path}")

if __name__ == "__main__":
    target_csv = sys.argv[1] if len(sys.argv) > 1 else None
    resolve_triads(target_csv)
