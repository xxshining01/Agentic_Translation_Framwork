import json
import logging
from enum import Enum
from typing import Dict, Any

from .base import BaseAgent
from ..core.models import TranslationBatch

logger = logging.getLogger(__name__)

import os

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

# --- 3. THE ANALYZER AGENT ---
class LinguisticAnalyzerAgent(BaseAgent):
    """
    Reads lines of dialogue and tags them with TLAS Metadata using LLM.
    """
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name, agent_name="Analyzer (Frank)")

    def _build_system_prompt(self) -> str:
        taxonomy, glossary = load_tlas_data()
        
        tags = taxonomy.get("tags", {})
        intents = [k for k in tags.keys() if k.startswith("INT_")]
        emotions = [k for k in tags.keys() if k.startswith("EMO_")]
        tones = [k for k in tags.keys() if k.startswith("TON_")]
        registers = [k for k in tags.keys() if k.startswith("REG_")]
        
        valid_chars = list(glossary.get("Characters", {}).keys())
        valid_chars_str = ", ".join(valid_chars) if valid_chars else "Any Name"
        
        prompt = (
            "You are a Linguistic Analyzer Agent for game localization.\n"
            "Your job is to analyze sentences and tag them with appropriate metadata.\n"
            "Use ONLY the following tags from the taxonomy:\n"
            f"Emotion: {', '.join(emotions)}\n"
            f"Intent: {', '.join(intents)}\n"
            f"Tone: {', '.join(tones)}\n"
            f"Register: {', '.join(registers)}\n\n"
            f"VALID CHARACTERS FOR listener/referenced_characters (USE ONLY THESE): {valid_chars_str}\n\n"
            "Format your output as a JSON array of objects exactly like this:\n"
            "[\n"
            "  {\n"
            '    "id": "...",\n'
            '    "speaker": "...",\n'
            '    "listener": ["..."],\n'
            '    "referenced_characters": ["..."],\n'
            '    "metadata": {\n'
            '      "intent": ["..."],\n'
            '      "emotion": ["..."],\n'
            '      "tone": ["..."],\n'
            '      "register": "..."\n'
            '    }\n'
            "  }\n"
            "]\n"
        )
        return prompt

    async def process(self, batch: TranslationBatch) -> bool:
        """
        Processes a batch of tokens, querying the LLM for TLAS metadata.
        """
        self.set_status(f"Analyzing Batch: {batch.batch_id} ({len(batch.tokens)} tokens)")
        logger.info(f"[LinguisticAnalyzer] Analyzing batch: {batch.batch_id}")
        
        try:
            tokens_to_analyze = [t for t in batch.tokens if t.token_type.startswith("HEAVY")]
            if not tokens_to_analyze:
                self.set_status("IDLE")
                return True

            system_prompt = self._build_system_prompt()
            
            # Chunking to prevent too long context (e.g., 20 tokens per chunk)
            chunk_size = 20
            success_count = 0
            
            for i in range(0, len(tokens_to_analyze), chunk_size):
                chunk = tokens_to_analyze[i:i + chunk_size]
                self.set_status(f"Analyzing Batch: {batch.batch_id} (Chunk {i+1}-{i+len(chunk)}/{len(tokens_to_analyze)})")
                
                user_prompt = "Analyze the following dialogues:\n"
                for t in chunk:
                    speaker_info = f" | Speaker: {t.speaker}" if t.speaker else ""
                    user_prompt += f"- ID: {t.id}{speaker_info}\n  Text: {t.original_text}\n"
                
                expected_ids = [t.id for t in chunk]
                items = await self.execute_with_retry(system_prompt, user_prompt, expected_ids)
                
                if not items:
                    logger.error(f"[LinguisticAnalyzer] Failed to process chunk in batch {batch.batch_id} after retries.")
                    continue
                    
                for item in items:
                    item_id = item.get("id") or item.get("token_id")
                    if item_id:
                        for t in chunk:
                            if t.id == item_id:
                                # Save metadata exactly as SDD-006 schema
                                meta_block = item.get("metadata", {})
                                t.metadata["intent"] = meta_block.get("intent", ["INT_INFORM"])
                                t.metadata["emotion"] = meta_block.get("emotion", ["EMO_NEUTRAL"])
                                t.metadata["tone"] = meta_block.get("tone", ["TON_NEUTRAL"])
                                t.metadata["register"] = meta_block.get("register", "REG_FORMAL")
                                
                                # Set target character (listener) for MappingEngine
                                listeners = item.get("listener", [])
                                if listeners and isinstance(listeners, list) and len(listeners) > 0:
                                    t.metadata["target_character"] = str(listeners[0])
                                    t.metadata["target_character_id"] = f"CHAR_{str(listeners[0]).replace(' ', '_').upper()}"
                                
                                success_count += 1
                                break
                                
            logger.debug(f"[LinguisticAnalyzer] Analysis success: {success_count}/{len(tokens_to_analyze)} tokens")
            self.set_status("IDLE")
            return True
            
        except Exception as e:
            logger.error(f"[LinguisticAnalyzer] Error processing batch {batch.batch_id}: {str(e)}")
            self.set_status("IDLE")
            return False
