"""
test_tlas_optimization_verification.py
======================================
Automated verification test script for TLAS Analyzer Optimization
and Character Timeline Enrichment Pipeline.
"""

import os
import sys
import json
import unittest

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from src.atf.tools.cleanup_junk_profiles import (
    is_garbage_or_disposable as cleanup_is_garbage,
    GARBAGE_REGEX_PATTERNS
)
from src.atf.tools.tlas_analyzer import (
    is_garbage_or_disposable as analyzer_is_garbage,
    TLASAnalyzerAgent
)
from src.atf.tools.tlas_character_timeline_enricher import (
    CharacterTimelineAgent,
    load_taxonomy,
    get_chunk_sort_key
)

class TestTLASOptimization(unittest.TestCase):

    def test_01_garbage_filtering_accuracy(self):
        """Test that garbage names are rejected and canonical names are preserved."""
        garbage_samples = [
            "Window5", "window8", "I", "I[32]", "\\I[123]", "???", "????",
            "Unknown", "unknown", "_unknown_", "Unnamed", "unnamed female",
            "c_1203", "c10120162Window8", "[BA Executive]", "Ba Executive",
            "ba executive__", "_ba executive_", "SLUT", "slut", "ALL", "BOTH",
            "System", "Narrator", "Text", "Choice", "HostNPC1", "NONE",
            "Affluent old man", "Affluent man", "Anxious boy", "Bald thug",
            "Bearded guy", "Big voice", "Hotel staff", "Village chief",
            "Young boy", "Kinchao gang member", "Slut"
        ]

        canonical_samples = [
            "Masaru", "Shion", "Dan", "Janice", "Akane", "Akira", "Alisa",
            "Drake", "Enjo", "Erica", "Foregrave", "Godmother", "Hatta",
            "Headmistress", "Honda", "Jikan CEO", "Kin", "Kosai", "Lily",
            "Lyra", "Mayor", "Mike", "Natalie", "Otto", "Raven", "Reiko",
            "Rimi", "Ritchie", "Rum", "Saru", "The Earl", "The Manager",
            "Turbo", "Wallace"
        ]

        # Verify cleanup tool
        for g in garbage_samples:
            self.assertTrue(cleanup_is_garbage(g), f"Cleanup filter should reject garbage: '{g}'")
        for c in canonical_samples:
            self.assertFalse(cleanup_is_garbage(c), f"Cleanup filter should keep canonical: '{c}'")

        # Verify analyzer tool
        for g in garbage_samples:
            self.assertTrue(analyzer_is_garbage(g), f"Analyzer filter should reject garbage: '{g}'")
        for c in canonical_samples:
            self.assertFalse(analyzer_is_garbage(c), f"Analyzer filter should keep canonical: '{c}'")

    def test_02_analyzer_agent_prompts(self):
        """Test that Stage 1 and Stage 2 prompts in TLASAnalyzerAgent are strict."""
        agent = TLASAnalyzerAgent()
        
        # Test Stage 1 Speaker ID system prompt
        self.assertIn("whitelist", agent.speaker_id_system_prompt.lower())

        # Test Stage 2 Focused prompt
        prompt = agent.build_focused_prompt(
            summary_text="Story summary text here...",
            scene_header="[Scene: test]",
            bilingual_dialogue="[Masaru]: Hello.\n[Shion]: Hi.",
            target_characters=["Masaru", "Shion"]
        )
        self.assertIn("Masaru, Shion", prompt)
        self.assertIn("ONLY for target character(s)", prompt)
        self.assertIn("NO SPEECH STYLE FIELDS", prompt)

    def test_03_timeline_enricher_components(self):
        """Test CharacterTimelineAgent and helper functions."""
        enricher_agent = CharacterTimelineAgent()
        self.assertEqual(enricher_agent.agent_name, "TLAS_Timeline_Enricher")
        
        taxonomy_path = os.path.join(PROJECT_ROOT, "data/tlas/taxonomy.json")
        tax = load_taxonomy(taxonomy_path)
        self.assertTrue("per_tags" in tax)
        self.assertTrue("dyn_tags" in tax)
        self.assertTrue("aff_tags" in tax)

    def test_04_template_schema_conformance(self):
        """Verify character_profile_template.json schema exists and has expected keys."""
        template_path = os.path.join(PROJECT_ROOT, "data/tlas/character_profile_template.json")
        self.assertTrue(os.path.exists(template_path), "Template must exist on disk")
        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)
        self.assertIn("character_id", template)
        self.assertIn("name", template)
        self.assertIn("identity", template)
        self.assertIn("base_speech_style", template)
        self.assertIn("base_state", template)
        self.assertIn("timeline_states", template)

if __name__ == "__main__":
    unittest.main()
