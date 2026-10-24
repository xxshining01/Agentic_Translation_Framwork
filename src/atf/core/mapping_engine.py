import os
import json
import logging

logger = logging.getLogger(__name__)

def load_tlas_data():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    tlas_dir = os.path.join(project_root, "data", "tlas")
    
    taxonomy = {}
    taxonomy_path = os.path.join(tlas_dir, "taxonomy.json")
    if os.path.exists(taxonomy_path):
        with open(taxonomy_path, "r", encoding="utf-8") as f:
            taxonomy = json.load(f)
            
    glossary = {}
    glossary_path = os.path.join(tlas_dir, "tlas_glossary.json")
    if os.path.exists(glossary_path):
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)
            
    return taxonomy, glossary

def _normalize_tag(tag: str) -> str:
    if not tag:
        return ""
    t = str(tag).upper().strip()
    for prefix in ["REL_", "PER_SOC_", "PER_MIND_", "PER_VIBE_", "PER_", "VAL_", "EMO_", "INT_", "TON_", "REG_", "SIT_", "CTX_"]:
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t

class MappingEngine:
    """
    Decides the final Pronouns based on the Priority Rule and Trait Weights.
    (Data is provided dynamically from ContextEngine and Analyzer)
    """
    def __init__(self):
        taxonomy, _ = load_tlas_data()
        self.rules = taxonomy.get("pronoun_mapping_rules", []) + taxonomy.get("relationship_pronoun_rules", [])

    def resolve_pronouns(self, speaker_profile: dict, listener_profile: dict, metadata: dict) -> str:
        """
        Calculates max_score = priority * weight and returns the winning Pronoun Guidance.
        Prioritizes direct pairwise speech_style from TLAS v4.0 Consolidated Profiles.
        """
        target_char_id = str(metadata.get("target_character_id") or metadata.get("target_character") or metadata.get("listener") or "").upper()
        target_char_name = str(metadata.get("target_character") or metadata.get("listener") or "").upper()

        # 0. TLAS v4.0 Direct Pairwise Resolution
        relationships = speaker_profile.get("relationships", [])
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            rel_tid = str(rel.get("target_character_id") or "").upper()
            rel_tname = str(rel.get("target_name") or "").upper()
            
            is_match = False
            if target_char_id and (rel_tid == target_char_id or target_char_id in rel_tid):
                is_match = True
            elif target_char_name and (rel_tname == target_char_name or target_char_name in rel_tname):
                is_match = True

            if is_match:
                speech = rel.get("speech_style") or rel.get("specific_speech")
                if speech and isinstance(speech, dict):
                    p_self = speech.get("self_pronoun", "")
                    p_target = speech.get("target_pronoun", "")
                    p_third = speech.get("third_person_pronoun", "")
                    p_ending = speech.get("ending_particle", "")
                    rule_app = speech.get("derivation_rule", "")
                    emo = metadata.get("emotion", ["EMO_NEUTRAL"])[0] if metadata.get("emotion") else "EMO_NEUTRAL"
                    guidance = (
                        "[TRANSLATION GUIDANCE - STRICT COMPLIANCE REQUIRED]\n"
                        f"- Pronoun (Self / บุรุษที่ 1): \"{p_self}\"\n"
                        f"- Pronoun (Listener / บุรุษที่ 2): \"{p_target}\"\n"
                    )
                    if p_third:
                        guidance += f"- Pronoun (Third-person / บุรุษที่ 3): \"{p_third}\"\n"
                    guidance += (
                        f"- Sentence Ending: \"{p_ending}\"\n"
                        f"- Tone Constraint: \"{str(emo).replace('EMO_', '')}\"\n"
                    )
                    if rule_app:
                        guidance += f"- Applied Rule: \"{rule_app}\"\n"
                    return guidance

        # Check V4 Base Speech Style if no specific listener matched or listener is generic
        base_speech = speaker_profile.get("base_speech_style", {})
        if base_speech and isinstance(base_speech, dict) and base_speech.get("self_pronoun"):
            p_self = base_speech.get("self_pronoun", "")
            p_target = base_speech.get("target_pronoun", "")
            p_third = base_speech.get("third_person_pronoun", "")
            p_ending = base_speech.get("ending_particle", "")
            emo = metadata.get("emotion", ["EMO_NEUTRAL"])[0] if metadata.get("emotion") else "EMO_NEUTRAL"
            guidance = (
                "[TRANSLATION GUIDANCE - STRICT COMPLIANCE REQUIRED]\n"
                f"- Pronoun (Self / บุรุษที่ 1): \"{p_self}\"\n"
                f"- Pronoun (Listener / บุรุษที่ 2): \"{p_target}\"\n"
            )
            if p_third:
                guidance += f"- Pronoun (Third-person / บุรุษที่ 3): \"{p_third}\"\n"
            guidance += (
                f"- Sentence Ending: \"{p_ending}\"\n"
                f"- Tone Constraint: \"{str(emo).replace('EMO_', '')}\"\n"
            )
            return guidance

        best_rule = None
        max_score = -1

        speaker_gender = speaker_profile.get("identity", {}).get("gender") or speaker_profile.get("gender", "UNKNOWN")
        speaker_age = speaker_profile.get("identity", {}).get("age") or speaker_profile.get("age", "UNKNOWN")

        for rule in self.rules:
            score = 0
            priority = rule.get("priority_score", 10)
            conds = rule.get("conditions", {})
            
            # 1. Hard Constraints (Must Match)
            if "gender" in conds and conds["gender"] != speaker_gender:
                continue
            if "age" in conds and conds["age"] != speaker_age:
                continue
            
            # 2. Metadata Constraints (Micro-Context from Analyzer)
            if "emotion" in conds:
                target_emo = _normalize_tag(conds["emotion"])
                matched_emo = any(_normalize_tag(e) == target_emo for e in metadata.get("emotion", []))
                if not matched_emo:
                    continue
            if "situation" in conds:
                target_sit = _normalize_tag(conds["situation"])
                matched_sit = any(_normalize_tag(s) == target_sit for s in metadata.get("situation", []))
                if not matched_sit:
                    continue
            if "register" in conds and _normalize_tag(conds["register"]) != _normalize_tag(metadata.get("register", "")):
                continue
                
            # If a rule requires emotion/situation but it matches, give it a base score multiplier
            if "emotion" in conds or "situation" in conds:
                score += priority * 100 # High impact for micro-context triggers
                
            # 3. Trait Weights (Macro-Context from Profile)
            matched_trait = False
            
            if "personality" in conds:
                target_pers = _normalize_tag(conds["personality"])
                trait_weight = 0
                for trait in speaker_profile.get("personality", []):
                    t_tag = _normalize_tag(trait.get("tag") if isinstance(trait, dict) else str(trait))
                    if t_tag == target_pers:
                        trait_weight = trait.get("weight", 5) if isinstance(trait, dict) else 5
                        matched_trait = True
                        break
                if trait_weight == 0:
                    continue
                score += priority * trait_weight
                
            if "values" in conds:
                target_val = _normalize_tag(conds["values"])
                trait_weight = 0
                for trait in speaker_profile.get("values", []):
                    t_tag = _normalize_tag(trait.get("tag") if isinstance(trait, dict) else str(trait))
                    if t_tag == target_val:
                        trait_weight = trait.get("weight", 5) if isinstance(trait, dict) else 5
                        matched_trait = True
                        break
                if trait_weight == 0:
                    continue
                score += priority * trait_weight
                
            if "relation" in conds:
                target_rel = _normalize_tag(conds["relation"])
                trait_weight = 0
                for rel in speaker_profile.get("relationships", []):
                    if not isinstance(rel, dict):
                        continue
                    # Check if this rel targets the listener by character ID or Name
                    rel_target = str(rel.get("target_character_id") or rel.get("target_name") or "").upper()
                    is_target = not target_char_id or (rel_target and (rel_target == target_char_id or rel_target == target_char_name or target_char_id in rel_target or rel_target in target_char_id))
                    if is_target:
                        for rtag in rel.get("relation_tags", []):
                            r_tag_str = _normalize_tag(rtag.get("tag") if isinstance(rtag, dict) else str(rtag))
                            if r_tag_str == target_rel:
                                trait_weight = rtag.get("weight", 5) if isinstance(rtag, dict) else 5
                                matched_trait = True
                                break
                    if trait_weight > 0:
                        break
                if trait_weight == 0:
                    continue
                score += priority * trait_weight

            # If no specific trait was required, give it a baseline score based on priority
            if not matched_trait and score == 0:
                score = priority * 50

            if score > max_score:
                max_score = score
                best_rule = rule
                
        # Fallback if no rule matches
        final_pronouns = {"self": "ฉัน/ผม", "target": "คุณ", "ending": "ค่ะ/ครับ"}
        if best_rule and "pronouns" in best_rule:
            final_pronouns = best_rule["pronouns"]

        emo = metadata.get("emotion", ["EMO_NEUTRAL"])[0] if metadata.get("emotion") else "EMO_NEUTRAL"
        reg = metadata.get("register", "REG_FORMAL")

        guidance = (
            "[TRANSLATION GUIDANCE - STRICT COMPLIANCE REQUIRED]\n"
            f"- Pronoun (Self): \"{final_pronouns.get('self', '')}\"\n"
            f"- Pronoun (Listener): \"{final_pronouns.get('target', '')}\"\n"
            f"- Sentence Ending: \"{final_pronouns.get('ending', '')}\"\n"
            f"- Tone Constraint: \"{emo.replace('EMO_', '')}\"\n"
            f"- Register Context: \"{reg.replace('REG_', '')}\"\n"
        )
        return guidance
