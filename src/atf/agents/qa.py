import json
import logging
from typing import Dict, Any

from .base import BaseAgent
from ..core.models import TranslationBatch, ContextData

logger = logging.getLogger(__name__)

class QAAgent(BaseAgent):
    """
    Agent สำหรับตรวจสอบคุณภาพ (Quality Assurance)
    ประเมินคะแนนตาม KPI และส่งกลับในรูปแบบ Strict JSON
    เพื่อให้ Orchestrator นำไปตัดสินใจเข้า Repair Loop
    """
    
    def __init__(self, model_name: str = "gpt-4o"):
        # แนะนำให้ใช้โมเดลตัวใหญ่ที่สุด (เช่น gpt-4o หรือ claude-3.5-sonnet) สำหรับงาน QA
        super().__init__(model_name=model_name, agent_name="QA (Quincy)")

    def _build_system_prompt(self, context: ContextData) -> str:
        """
        เครื่องจักรประกอบ Prompt สำหรับ QA (บังคับโหมด JSON พร้อม Reasoning)
        """
        prompt = (
            "You are a strict Quality Assurance Agent for game localization.\n"
            "Evaluate the 'Edited Translation' against the 'Original Text' and [Mandatory Glossary Check].\n"
            "You MUST think step-by-step and write your analysis in the 'reasoning' field BEFORE scoring.\n\n"
            "Check for these 5 DEADLY SINS:\n"
            "1. Glossary Violation: Names/terms MUST match the glossary exactly.\n"
            "2. Alien Text: NO Chinese, Japanese, or unwanted foreign characters (except standard English symbols if present in original).\n"
            "3. Grammar & Word Order: Ensure natural Thai phrasing. Expressions like 'เหรอเลย' (question particle followed by statement particle) are STRICTLY FORBIDDEN. 'เลยเหรอ' is correct.\n"
            "4. Thai Particles (คะ/ค่ะ/จ๊ะ/จ้ะ): MUST be used correctly. 'คะ/ขา' for questions/calling. 'ค่ะ/ค่า' for statements/answers. 'จ๊ะ/จ้ะ' similarly.\n"
            "5. Gender & Pronoun Mismatch: Pronouns and ending particles MUST match the character's gender and the strict [TRANSLATION GUIDANCE & STYLE RULES] provided below.\n\n"
            "SCORING (0-10):\n"
            "- meaning (Meaning Preservation)\n"
            "- character (Gender/Pronoun match)\n"
            "- naturalness (Grammar/Particles/Alien Text)\n"
            "- completeness (No leftover English unless intentional)\n"
            "- glossary (Glossary Compliance)\n\n"
            "CRITICAL RULES:\n"
            "- If ANY of the 5 DEADLY SINS are found, you MUST score the relevant category as 0 and set status to 'FAIL'.\n"
            "- If the translation contains alien text (Chinese/Japanese) or wrong Thai particles, 'naturalness' MUST be 0, status 'FAIL'.\n"
            "- If ANY score is below 7, set 'status' to 'FAIL'.\n"
            "- If 'FAIL', provide actionable 'feedback' for the previous agents to fix, pointing exactly to the untranslated word, incorrect name, or bad grammar.\n"
            "- Format your output as a JSON array exactly like this:\n"
            "[\n"
            "  {\n"
            '    "id": "...",\n'
            '    "reasoning": "Step-by-step analysis of the 5 deadly sins...",\n'
            '    "status": "PASS" or "FAIL",\n'
            '    "scores": {"meaning": int, "character": int, "naturalness": int, "completeness": int, "glossary": int},\n'
            '    "feedback": "string (Specific instructions if FAIL, empty if PASS)"\n'
            "  }\n"
            "]\n"
        )
        
        # ใส่ Context Guidance ให้ QA รู้ว่าถูกสั่งให้ใช้สรรพนามอะไร
        if context.style_rules:
            prompt += f"\n[TRANSLATION GUIDANCE & STYLE RULES]\n{context.style_rules}\n"
            
        if context.glossary_matches:
            prompt += "\n[Mandatory Glossary Check]\nEnsure these terms were used EXACTLY as shown:\n"
            for en_term, th_term in context.glossary_matches.items():
                prompt += f"- {en_term} -> {th_term}\n"
                
        return prompt

    async def process(self, batch: TranslationBatch) -> bool:
        """
        กระบวนการตรวจสอบคุณภาพแบบกลุ่ม
        คืนค่า True หากผ่านทุกประโยค, False หากมีประโยคใดไม่ผ่าน
        """
        self.set_status(f"QA Checking Batch: {batch.batch_id} ({len(batch.tokens)} tokens)")
        logger.info(f"[QAAgent] Evaluating batch: {batch.batch_id}")
        
        try:
            tokens_to_qa = [t for t in batch.tokens if t.outputs.editor_output]
            if not tokens_to_qa:
                self.set_status("IDLE")
                return True
                
            context = tokens_to_qa[0].context
            
            # 1. ประกอบ System Prompt
            system_prompt = self._build_system_prompt(context)
            
            # 2. เตรียมข้อความให้ AI ตรวจสอบ
            user_prompt = "Here are the translations to evaluate:\n"
            for t in tokens_to_qa:
                user_prompt += f'- ID: {t.id}\n  - Original: {t.original_text}\n  - Edited Translation: {t.outputs.editor_output}\n'
            
            # 3. ส่งให้คลาสแม่ยิง API
            expected_ids = [t.id for t in tokens_to_qa]
            items = await self.execute_with_retry(system_prompt, user_prompt, expected_ids)
            
            if not items:
                logger.error(f"[QAAgent] Failed to process batch {batch.batch_id} after retries.")
                self.set_status("IDLE")
                return False
                
            all_passed = True
            for item in items:
                item_id = item.get("id")
                status = item.get("status")
                feedback = item.get("feedback")
                
                if item_id:
                    for t in tokens_to_qa:
                        if t.id == item_id:
                            if status == "FAIL":
                                t.outputs.qa_feedback = feedback or "Failed QA without feedback."
                                logger.warning(f"[QAAgent] Token {t.id} FAILED QA: {t.outputs.qa_feedback}")
                                all_passed = False
                            else:
                                t.outputs.qa_feedback = None
                                logger.info(f"[QAAgent] Token {t.id} PASSED QA.")
                            break
                            
            self.set_status("IDLE")
            return all_passed
                
        except Exception as e:
            logger.error(f"[QAAgent] Error processing batch {batch.batch_id}: {str(e)}")
            self.set_status("IDLE")
            return False
