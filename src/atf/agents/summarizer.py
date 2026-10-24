import logging
import json
import os
from typing import List, Dict
from .base import BaseAgent
from ..core.models import TranslationToken
from json_repair import repair_json

logger = logging.getLogger(__name__)

class SummarizerAgent(BaseAgent):
    """
    Agent สำหรับสรุปเนื้อเรื่อง (Story Context)
    นำประโยคที่แปลเสร็จแล้วย้อนหลังมาปะติดปะต่อ แล้วให้ AI สรุปเหตุการณ์ปัจจุบัน
    เพื่อใช้เป็นบริบทส่งต่อให้ Translator และ Editor ในประโยคถัดไป
    """
    def __init__(self, model_name: str = "gpt-4o-mini", data_dir: str = None):
        super().__init__(model_name=model_name, agent_name="Summarizer (Sam)")
        self.situation_tags = []
        if not data_dir:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            data_dir = os.path.join(project_root, "data", "tlas")
            
        if data_dir:
            tax_path = os.path.join(data_dir, "taxonomy.json")
            if os.path.exists(tax_path):
                with open(tax_path, "r", encoding="utf-8") as f:
                    tax = json.load(f)
                    tags = tax.get("tags", {})
                    self.situation_tags = [k for k in tags.keys() if k.startswith("SIT_") or k.startswith("CTX_")]

    async def process(self, token: TranslationToken) -> bool:
        """Dummy process method since Summarizer does not process individual tokens."""
        return True

    async def analyze_scope(self, tokens: List[TranslationToken]) -> dict:
        """
        อ่านรายการ Token ล่วงหน้า (Original Text) และสร้าง Scope บริบทภาพรวมพร้อม Situation Tags
        """
        if not tokens:
            return {"situation": [], "summary": ""}
            
        logger.info(f"[SummarizerAgent] Analyzing scope from {len(tokens)} original tokens.")
        
        dialogues = []
        for t in tokens:
            speaker = f"{t.speaker}: " if t.speaker else "Narrator: "
            dialogues.append(f"{speaker}{t.original_text}")
            
        script_text = "\n".join(dialogues)
        
        tags_text = ", ".join(self.situation_tags) if self.situation_tags else "SIT_NORMAL, SIT_CRISIS, SIT_PRIVATE, SIT_PUBLIC"

        system_prompt = (
            "You are a Story Context Analyzer (Summarizer Agent). Read the following original English script (a chunk of sentences) "
            "and extract the Situation context.\n"
            "CRITICAL RULES:\n"
            "1. Output ONLY a valid JSON object. No markdown formatting outside of the JSON.\n"
            "2. 'situation' MUST be an array containing EXACTLY ONE OR MORE tags from this allowed list:\n"
            f"   ALLOWED TAGS: {tags_text}\n"
            "3. DO NOT extract or invent Emotion or Tone tags. Only Situation tags.\n"
            "4. 'summary' MUST be a concise description of what is happening in Thai (e.g. 'Dan is arguing with Drake in a tense situation').\n"
            "Example Output:\n"
            "{\n"
            '  "situation": ["SIT_PRIVATE"],\n'
            '  "summary": "ตัวละครกำลังคุยกันเรื่องส่วนตัวในห้อง"\n'
            "}"
        )
        
        user_prompt = f"Original Script Chunk:\n\n{script_text}"
        
        self.set_status(f"Analyzing scope for {len(tokens)} lines...")
        try:
            response = await self.call_llm(system_prompt, user_prompt, require_json=False, skip_safety_rule=True)
            if response:
                result = json.loads(repair_json(response))
                logger.debug(f"[SummarizerAgent] Scope generated: {result}")
                self.set_status("IDLE")
                return result
            self.set_status("IDLE")
            return {"situation": [], "summary": ""}
        except Exception as e:
            logger.error(f"[SummarizerAgent] Failed to analyze scope: {str(e)}")
            self.set_status("IDLE")
            return {"situation": [], "summary": ""}

