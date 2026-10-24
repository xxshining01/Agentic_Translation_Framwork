import json
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class ThaiGrammarProcessor:
    """
    Handles Thai ending particles and vocal extensions based on sentence types and emotions.
    """
    def __init__(self):
        self.particle_rules = {
            "คะ/ค่ะ": {
                "statement": "ค่ะ",
                "question": "คะ",
                "playful_statement": "ค่า/ค่าา",
                "playful_question": "ค้า/ค้าา",
                "seductive_statement": "ค่าา~",
                "seductive_question": "ค้า~"
            },
            "ครับ": {
                "statement": "ครับ",
                "question": "ครับ",
                "lazy_statement": "คร้าบ/ค้าบ",
                "playful_statement": "คร้าบ"
            },
            "จ้ะ/จ๊ะ": {
                "statement": "จ้ะ",
                "question": "จ๊ะ",
                "seductive_statement": "จ๋า~",
                "seductive_question": "จ๊ะ~"
            },
            "ย่ะ/ยะ": {
                "statement": "ย่ะ",
                "question": "ยะ"
            },
            "วะ/เว้ย/โว้ย": {
                "statement": "วะ",
                "question": "วะ",
                "angry_statement": "โว้ย"
            }
        }

    def resolve_particles(self, root_particle: str, is_question: bool, dynamic_tags: Union[List[str], Dict[str, str]]) -> str:
        """Resolves the correct ending particle based on sentence type and emotion/tone."""
        if not root_particle:
            return ""
            
        tag_list = []
        if isinstance(dynamic_tags, dict):
            tag_list = list(dynamic_tags.values())
        elif isinstance(dynamic_tags, list):
            tag_list = dynamic_tags

        if root_particle not in self.particle_rules:
            # Fallback if unknown particle or already concrete (e.g. 'จ้ะ', 'ครับ')
            return root_particle

        rules = self.particle_rules[root_particle]
        
        is_playful = "TON_PLAYFUL" in tag_list
        is_lazy = "SPR_LAZY" in tag_list
        is_seductive = "TON_SEDUCTIVE" in tag_list or "EMO_AROUSED" in tag_list
        is_angry = "EMO_ANGER" in tag_list or "TON_AGGRESSIVE" in tag_list
        
        if root_particle == "คะ/ค่ะ":
            if is_seductive and "seductive_statement" in rules:
                return rules["seductive_question"] if is_question else rules["seductive_statement"]
            if is_playful:
                return rules["playful_question"] if is_question else rules["playful_statement"]
            return rules["question"] if is_question else rules["statement"]
            
        elif root_particle == "ครับ":
            if is_lazy or is_playful:
                return rules.get("lazy_statement", "คร้าบ")
            return rules["question"] if is_question else rules["statement"]
            
        elif root_particle == "จ้ะ/จ๊ะ":
            if is_seductive:
                return rules.get("seductive_statement", "จ๋า~")
            return rules["question"] if is_question else rules["statement"]

        elif root_particle == "วะ/เว้ย/โว้ย":
            if is_angry:
                return rules.get("angry_statement", "โว้ย")
            return rules["statement"]
            
        return root_particle


class PriorityRuleEngine:
    """
    Core engine implementing the 4-Tier Fallback Logic (Tier 0 Dynamic -> Tier 1 4D Exact -> Tier 2 Taxonomy -> Tier 3 Base) for TLAS.
    """
    def __init__(self, taxonomy_path: str):
        self.taxonomy = self._load_taxonomy(taxonomy_path)
        self.tier1_rules = self.taxonomy.get("relationship_pronoun_rules", [])
        self.tier2_rules = self.taxonomy.get("pronoun_mapping_rules", [])
        self.grammar_processor = ThaiGrammarProcessor()

    def _load_taxonomy(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load taxonomy from {path}: {e}")
            return {}

    def _match_dynamic_tags(self, dynamic_tags: Union[List[str], Dict[str, str]], required_dynamic: Any) -> bool:
        if not required_dynamic:
            return True
        
        current_tags = set()
        if isinstance(dynamic_tags, dict):
            current_tags = set(dynamic_tags.values())
        elif isinstance(dynamic_tags, list):
            current_tags = set(dynamic_tags)

        if isinstance(required_dynamic, dict):
            for k, req_tag in required_dynamic.items():
                if req_tag not in current_tags:
                    return False
            return True
        elif isinstance(required_dynamic, list):
            for req_tag in required_dynamic:
                if req_tag not in current_tags:
                    return False
            return True
        elif isinstance(required_dynamic, str):
            return required_dynamic in current_tags

        return False

    def _match_relation(self, rel_obj: Dict[str, Any], rule_relation_reqs: Union[str, Dict[str, Any]]) -> bool:
        if not rule_relation_reqs or not rel_obj:
            return False

        if isinstance(rule_relation_reqs, str):
            legacy_map = {
                "REL_WORK_BOSS": {"roles": ["ROLE_AUTH_MASTER", "ROLE_AUTH_MENTOR"]},
                "REL_FAMILY_PARENT": {"roles": ["ROLE_KIN_ELDER"]},
                "REL_ENEMY": {"roles": ["ROLE_CON_ENEMY", "ROLE_CON_RIVAL"]},
                "REL_FRIEND": {"roles": ["ROLE_SOC_PEER", "ROLE_KIN_PEER"], "intimacy": "INT_CONFIDANT"},
                "REL_LOVER": {"roles": ["ROLE_ROM_OFFICIAL", "ROLE_ROM_ILLICIT"]},
                "REL_STRANGER": {"roles": ["ROLE_SOC_STRANGER"]}
            }
            rule_relation_reqs = legacy_map.get(rule_relation_reqs, {})

        if not rule_relation_reqs:
            return False

        # Match roles
        if "roles" in rule_relation_reqs:
            req_roles = rule_relation_reqs["roles"]
            if isinstance(req_roles, str):
                req_roles = [req_roles]
            rel_roles = rel_obj.get("roles", [])
            # If any required role matches
            if not any(r in rel_roles for r in req_roles):
                return False

        # Match affinity
        if "affinity" in rule_relation_reqs:
            if rel_obj.get("affinity") != rule_relation_reqs["affinity"]:
                return False

        # Match intimacy
        if "intimacy" in rule_relation_reqs:
            if rel_obj.get("intimacy") != rule_relation_reqs["intimacy"]:
                return False

        # Match power_dynamic
        if "power_dynamic" in rule_relation_reqs:
            if rel_obj.get("power_dynamic") != rule_relation_reqs["power_dynamic"]:
                return False

        return True

    def _match_speaker_conditions(self, profile: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        if not conditions:
            return True
            
        if "gender" in conditions and profile.get("identity", {}).get("gender") != conditions["gender"]:
            return False
        if "age" in conditions and profile.get("identity", {}).get("age") != conditions["age"]:
            return False
            
        # Check weighted personality / speech_habit / values (weight > 50)
        for tag_type in ["personality", "speech_habit", "values"]:
            if tag_type in conditions:
                expected_tag = conditions[tag_type]
                profile_tags = [t["tag"] for t in profile.get(tag_type, []) if t.get("weight", 0) > 50]
                if expected_tag not in profile_tags:
                    return False
                    
        return True

    def evaluate_priority_pipeline(self, 
                                   speaker_profile: Dict[str, Any], 
                                   listener_profile: Optional[Dict[str, Any]], 
                                   dynamic_tags: Union[List[str], Dict[str, str]],
                                   is_question: bool = False) -> Dict[str, Any]:
        """
        Executes the 4-Tier resolution logic:
        - Tier 0: Dynamic Context Override (EMO/TON)
        - Tier 1: Exact Match (4D Relationship Matrix & Specific Speech)
        - Tier 2: Taxonomy Social & Condition Match
        - Tier 3: Base Profile Fallback
        """
        rules = self.taxonomy.get("pronoun_mapping_rules", [])

        # -------------------------------------------------------------
        # Tier 0: Dynamic Context Overrides (Priority Score >= 98 or TIER0)
        # -------------------------------------------------------------
        for rule in rules:
            rule_id = rule.get("rule_id", "")
            score = rule.get("priority_score", 0)
            if score >= 98 or rule_id.startswith("TIER0"):
                conds = rule.get("conditions", {})
                req_dynamic = conds.get("dynamic_tags")
                if req_dynamic and self._match_dynamic_tags(dynamic_tags, req_dynamic):
                    guideline = rule.get("pronouns", {})
                    return {
                        "resolved_tier": 0,
                        "rule_id": rule_id,
                        "guidelines": {
                            "self_pronoun": guideline.get("self", ""),
                            "target_pronoun": guideline.get("target", ""),
                            "ending_particle": self.grammar_processor.resolve_particles(guideline.get("ending", ""), is_question, dynamic_tags),
                            "formality_level": 1
                        },
                        "notes": rule.get("notes", "Tier 0 Dynamic Override Active")
                    }

        # -------------------------------------------------------------
        # Tier 1: Exact Match (Relationship 4D & Specific Speech)
        # -------------------------------------------------------------
        if listener_profile:
            listener_id = listener_profile.get("character_id") or listener_profile.get("id")
            speaker_rels = speaker_profile.get("relationships", [])
            target_rel = None
            for rel in speaker_rels:
                if rel.get("target_character_id") == listener_id:
                    target_rel = rel
                    break

            if target_rel:
                # 1.1 Direct specific_speech in character profile
                spec_speech = target_rel.get("specific_speech", {})
                if spec_speech and (spec_speech.get("self_pronoun") or spec_speech.get("target_pronoun")):
                    return {
                        "resolved_tier": 1,
                        "rule_id": "TIER1_EXACT_SPECIFIC_SPEECH",
                        "guidelines": {
                            "self_pronoun": spec_speech.get("self_pronoun", ""),
                            "target_pronoun": spec_speech.get("target_pronoun", ""),
                            "ending_particle": self.grammar_processor.resolve_particles(spec_speech.get("ending_particle", ""), is_question, dynamic_tags),
                            "formality_level": spec_speech.get("formality_level", speaker_profile.get("base_speech_style", {}).get("formality_level", 5))
                        },
                        "relationship_state": target_rel
                    }

                # 1.2 Evaluate 4D Taxonomy Tier 1 Rules
                best_t1_rule = None
                best_t1_score = -1
                for rule in self.tier1_rules:
                    rule_id = rule.get("rule_id", "")
                    score = rule.get("priority_score", 0)
                    conds = rule.get("conditions", {})
                    rel_reqs = conds.get("relation")
                    
                    if rel_reqs and (rule_id.startswith("TIER1") or (score >= 90 and score < 98)):
                        if self._match_relation(target_rel, rel_reqs):
                            req_dynamic = conds.get("dynamic_tags")
                            if req_dynamic and not self._match_dynamic_tags(dynamic_tags, req_dynamic):
                                continue
                            if score > best_t1_score:
                                best_t1_score = score
                                best_t1_rule = rule

                if best_t1_rule:
                    guideline = best_t1_rule.get("pronouns", {})
                    return {
                        "resolved_tier": 1,
                        "rule_id": best_t1_rule.get("rule_id"),
                        "guidelines": {
                            "self_pronoun": guideline.get("self", ""),
                            "target_pronoun": guideline.get("target", ""),
                            "ending_particle": self.grammar_processor.resolve_particles(guideline.get("ending", ""), is_question, dynamic_tags),
                            "formality_level": speaker_profile.get("base_speech_style", {}).get("formality_level", 5)
                        },
                        "relationship_state": target_rel,
                        "notes": best_t1_rule.get("notes", "")
                    }

        # -------------------------------------------------------------
        # Tier 2: Taxonomy Matching (Social Role & General Conditions)
        # -------------------------------------------------------------
        best_t2_rule = None
        best_t2_score = -1
        
        for rule in self.tier2_rules:
            rule_id = rule.get("rule_id", "")
            score = rule.get("priority_score", 0)
            if score >= 98 or rule_id.startswith("TIER0"):
                continue
                
            conds = rule.get("conditions", {})
            
            # Check relation condition if present
            if "relation" in conds:
                if not listener_profile:
                    continue
                # Check with any relation or listener roles
                listener_id = listener_profile.get("character_id") or listener_profile.get("id")
                rel_obj = next((r for r in speaker_profile.get("relationships", []) if r.get("target_character_id") == listener_id), None)
                if not rel_obj or not self._match_relation(rel_obj, conds["relation"]):
                    continue

            # Check speaker conditions (flattened)
            if not self._match_speaker_conditions(speaker_profile, conds):
                continue
                
            # Check dynamic tags
            req_dynamic = conds.get("dynamic_tags")
            if req_dynamic and not self._match_dynamic_tags(dynamic_tags, req_dynamic):
                continue

            if score > best_t2_score:
                best_t2_score = score
                best_t2_rule = rule

        if best_t2_rule:
            guideline = best_t2_rule.get("pronouns", {})
            return {
                "resolved_tier": 2,
                "rule_id": best_t2_rule.get("rule_id", f"TIER2_SCORE_{best_t2_score}"),
                "guidelines": {
                    "self_pronoun": guideline.get("self", ""),
                    "target_pronoun": guideline.get("target", ""),
                    "ending_particle": self.grammar_processor.resolve_particles(guideline.get("ending", ""), is_question, dynamic_tags),
                    "formality_level": speaker_profile.get("base_speech_style", {}).get("formality_level", 5)
                },
                "notes": best_t2_rule.get("notes", "")
            }

        # -------------------------------------------------------------
        # Tier 3: Base Profile Fallback
        # -------------------------------------------------------------
        base_style = speaker_profile.get("base_speech_style", {})
        return {
            "resolved_tier": 3,
            "rule_id": "TIER3_BASE_FALLBACK",
            "guidelines": {
                "self_pronoun": base_style.get("self_pronoun") or "ฉัน",
                "target_pronoun": base_style.get("target_pronoun") or "คุณ",
                "ending_particle": self.grammar_processor.resolve_particles(base_style.get("ending_particle") or "คะ/ค่ะ", is_question, dynamic_tags),
                "formality_level": base_style.get("formality_level", 5)
            }
        }

    # Backward compatibility alias
    def evaluate_3tier_fallback(self, *args, **kwargs):
        return self.evaluate_priority_pipeline(*args, **kwargs)


class TLASRuleAgent:
    """
    Entry point for the Agentic Pipeline. 
    This can be plugged into the Event Bus before the TRANSLATING state.
    """
    def __init__(self, taxonomy_path: str):
        self.engine = PriorityRuleEngine(taxonomy_path)
        
    def process_translation_token(self, token: Dict[str, Any], speaker_profile: Dict[str, Any], listener_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Intercepts a TranslationToken, calculates the guidelines, and injects them into the token's context.
        """
        text = token.get("source_text", "")
        is_question = "?" in text
        dynamic_tags = token.get("dynamic_tags", []) 
        
        result = self.engine.evaluate_priority_pipeline(speaker_profile, listener_profile, dynamic_tags, is_question)
        
        if "context" not in token:
            token["context"] = {}
            
        token["context"]["tlas_guidelines"] = result
        return token
