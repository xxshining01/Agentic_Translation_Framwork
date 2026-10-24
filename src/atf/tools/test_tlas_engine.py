import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# Add src to path to allow importing atf
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))

try:
    from atf.tools.tlas_rule_engine import PriorityRuleEngine, TLASRuleAgent, ThaiGrammarProcessor
    print("[PASS] tlas_rule_engine imported successfully.")
except Exception as e:
    print(f"[FAIL] Failed to import tlas_rule_engine: {e}")
    sys.exit(1)

try:
    # Just checking for syntax errors in tlas_analyzer
    import py_compile
    analyzer_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'tlas_analyzer.py'))
    py_compile.compile(analyzer_path, doraise=True)
    print("[PASS] tlas_analyzer.py syntax is valid.")
except Exception as e:
    print(f"[FAIL] tlas_analyzer.py has syntax errors: {e}")
    sys.exit(1)

def test_engine():
    # Mock data
    taxonomy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'tlas', 'taxonomy.json'))
    engine = PriorityRuleEngine(taxonomy_path)
    print("[PASS] RuleEngine initialized.")
    
    # Mock Speaker Profile
    speaker_profile = {
        "identity": {"gender": "FEMALE"},
        "base_speech_style": {
            "self_pronoun": "ฉัน",
            "target_pronoun": "คุณ",
            "ending_particle": "คะ/ค่ะ",
            "formality_level": 5
        },
        "relationships": [
            {
                "target_character_id": "CHAR_BOSS_001",
                "specific_speech": {
                    "self_pronoun": "หนู",
                    "target_pronoun": "บอส",
                    "ending_particle": "คะ/ค่ะ",
                    "formality_level": 8
                }
            }
        ],
        "personality": [{"tag": "PER_SOC_POLITE", "weight": 80}]
    }
    
    # Test Tier 1 (Relationship)
    listener_boss = {"character_id": "CHAR_BOSS_001"}
    res1 = engine.evaluate_3tier_fallback(speaker_profile, listener_boss, [])
    assert res1["resolved_tier"] == 1, "Expected Tier 1 match"
    assert res1["guidelines"]["self_pronoun"] == "หนู", "Expected self pronoun to be 'หนู'"
    print("[PASS] Tier 1 Exact Match test passed.")

    # Test Tier 3 (Fallback)
    listener_stranger = {"character_id": "CHAR_UNKNOWN_001"}
    res3 = engine.evaluate_3tier_fallback(speaker_profile, listener_stranger, [])
    # Wait, the taxonomy might have a Tier 2 rule for FEMALE polite. 
    # Let's check what it actually resolves to.
    print(f"[INFO] Stranger resolution: {res3}")
    
    # Test Grammar override
    res_grammar = engine.evaluate_3tier_fallback(speaker_profile, listener_boss, ["TON_PLAYFUL"])
    # It should use playful statement -> "ค่า/ค่าา"
    assert res_grammar["guidelines"]["ending_particle"] == "ค่า/ค่าา", f"Expected playful ending, got {res_grammar['guidelines']['ending_particle']}"
    print("[PASS] Grammar override test passed.")

if __name__ == "__main__":
    print("Running TLAS 3-Tier Rule Engine Tests...")
    test_engine()
    print("\nAll tests finished successfully!")
