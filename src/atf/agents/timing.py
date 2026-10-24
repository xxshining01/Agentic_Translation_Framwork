import logging
from .base import BaseAgent
from ..core.models import TranslationBatch

logger = logging.getLogger(__name__)

class TimingAgent(BaseAgent):
    """
    Agent สำหรับจัดการจังหวะการเล่าเรื่อง (Timing)
    รับข้อความภาษาไทยที่ผ่าน QA แล้ว มาเทียบกับต้นฉบับ
    เพื่อแทรกสัญลักษณ์กำหนดจังหวะ (เช่น ✎, |, .) ให้พอดีกันโดยไม่เปลี่ยนคำ
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name, agent_name="Timing (Timmy)")

    def _build_system_prompt(self) -> str:
        """
        เครื่องจักรประกอบ Prompt สำหรับ Timing Agent (อิงจาก SDD-003)
        ไม่มี Context ตัวละครหรือ Glossary เพราะแค่ใส่สัญลักษณ์เท่านั้น
        """
        prompt = (
            "You are a Syntax & Timing Repair Agent for game localization (RPG Maker Engine).\n"
            "Your job is to insert missing timing pauses, control codes, and fix syntax errors in the translated Thai dialogue to EXACTLY match the original pacing and control symbols.\n\n"
            "COMMON RPG MAKER CONTROL CODES:\n"
            "- \\\\. = 1/4 second pause\n"
            "- \\\\| = 1 second pause\n"
            "- \\\\n = New line\n"
            "- \\\\f = Form feed / Page break\n"
            "- \\\\> and \\\\< = Instant text display toggles\n"
            "- \\\\C[X] = Change text color\n"
            "- \\\\! = Wait for input\n\n"
            "CRITICAL RULES:\n"
            "1. If you receive a 'QA Feedback' starting with 'SYNTAX ERROR', you MUST read the error message. It will tell you which variables/codes are missing or which ones you invented.\n"
            "2. Compare the 'Original' text with the 'Translated Text'. You MUST insert the EXACT missing control codes (including their backslashes!) into the translated text at the correct positions, or remove the invented ones.\n"
            "3. DO NOT remove the backslashes from the control codes. For example, use '\\.' instead of '.' if the original has '\\.'.\n"
            "4. DO NOT change any actual Thai words from the translated text. ONLY fix the symbols and control codes.\n"
            "5. Format your output as a JSON array of objects like this:\n"
            "[\n"
            "  {\n"
            '    "id": "...", "timing_text": "..."}\n'
            "]\n"
            "6. Ensure your output contains only the JSON array with the final text.\n"
        )
        return prompt

    async def process(self, batch: TranslationBatch) -> bool:
        """
        กระบวนการแทรกสัญลักษณ์ Timing แบบกลุ่ม
        """
        self.set_status(f"Timing Adjust Batch: {batch.batch_id}")
        logger.info(f"[TimingAgent] Processing batch: {batch.batch_id}")
        
        try:
            tokens_to_time = []
            for t in batch.tokens:
                if t.outputs.editor_output and (t.outputs.qa_feedback or not t.outputs.timing_output):
                    tokens_to_time.append(t)
            if not tokens_to_time:
                self.set_status("IDLE")
                return True
            
            # 1. ประกอบ System Prompt
            system_prompt = self._build_system_prompt()
            
            # 2. ส่งทั้ง Original Text และ Translated Text
            user_prompt = "Here are the translations to adjust timing:\n"
            for t in tokens_to_time:
                feedback_info = f"\n  - QA Feedback (Fix this): {t.outputs.qa_feedback}" if t.outputs.qa_feedback else ""
                user_prompt += f'- ID: {t.id}\n  - Original (Look at pacing symbols): {t.original_text}\n  - Translated Text (Insert symbols here): {t.outputs.editor_output}{feedback_info}\n'
            
            # 3. ส่งให้คลาสแม่ยิง API
            expected_ids = [t.id for t in tokens_to_time]
            items = await self.execute_with_retry(system_prompt, user_prompt, expected_ids)
            
            if not items:
                logger.error(f"[TimingAgent] Failed to process batch {batch.batch_id} after retries.")
                self.set_status("IDLE")
                return False
                
            for item in items:
                item_id = item.get("id")
                timing_text = item.get("timing_text")
                
                if item_id and timing_text:
                    for t in tokens_to_time:
                        if t.id == item_id:
                            t.outputs.timing_output = str(timing_text).replace('\n', '\\n').strip()
                            t.outputs.final_output = t.outputs.timing_output
                            t.outputs.qa_feedback = None # Clear feedback after fixing
                            break
                            
            self.set_status("IDLE")
            return True
                
        except Exception as e:
            logger.error(f"[TimingAgent] Error processing batch {batch.batch_id}: {str(e)}")
            self.set_status("IDLE")
            return False
