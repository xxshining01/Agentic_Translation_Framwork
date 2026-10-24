import logging
from .base import BaseAgent
from ..core.models import TranslationBatch, ContextData

logger = logging.getLogger(__name__)

class EditorAgent(BaseAgent):
    """
    Agent สำหรับเกลาภาษา (ด่านที่สอง)
    รับคำแปลที่ถูกต้องจาก Translator มาปรับน้ำเสียง (Tone) และความเป็นธรรมชาติ
    ให้ตรงกับบุคลิกของตัวละคร (Persona)
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name, agent_name="Editor (Oliver)")

    def _build_system_prompt(self, context: ContextData) -> str:
        """
        เครื่องจักรประกอบ Prompt สำหรับ Editor (อิงจาก SDD-003)
        """
        prompt = (
            "You are a specialized Editor Agent for game localization.\n"
            "You will receive a rough Thai translation. Your job is to rewrite it to sound natural while matching the character's persona.\n\n"
            "CRITICAL RULES (To pass QA Evaluation):\n"
            "1. DO NOT change the core meaning provided in the rough translation.\n"
            "2. ADAPT the tone, pronouns, and politeness levels based on the [Character Info] and [TRANSLATION GUIDANCE].\n"
            "3. MUST strictly follow the provided Glossary. Exact matches only.\n"
            "4. NO Alien Text: Do not include Chinese, Japanese, or unnecessary foreign characters.\n"
            "5. Grammar & Word Order: Ensure natural Thai phrasing. Expressions like 'เหรอเลย' are forbidden; use 'เลยเหรอ'.\n"
            "6. Thai Particles: Use 'คะ/ขา' for female questions/calling, 'ค่ะ/ค่า' for statements/answers. Use 'จ๊ะ/จ้ะ' properly.\n"
            "7. Output ONLY the edited text.\n\n"
            "FEW-SHOT EXAMPLES (Self-Correction):\n"
            "- BAD: อย่างนั้นเหรอเลย? -> GOOD: อย่างนั้นเลยเหรอ?\n"
            "- BAD (Question): ไปไหนมาคะ? -> GOOD (Statement): ไปตลาดมาค่ะ (Use 'ค่ะ' for answers)\n"
            "- BAD (Ignore Guidance): ฉันสบายดีครับ (If Guidance says Female/'ฉัน'/'ค่ะ') -> GOOD: ฉันสบายดีค่ะ\n"
        )
        
        # ใส่บริบทของตัวละครให้ Editor รับรู้ (สำคัญมากสำหรับ Agent ตัวนี้)
        if context.character_traits:
            prompt += "\n[Character Info]\n"
            traits = ", ".join(context.character_traits)
            prompt += f"Traits: {traits}\n"
                
        # ย้ำเรื่องคำศัพท์เฉพาะอีกครั้ง ป้องกัน Editor เผลอแก้คำบังคับ
        if context.glossary_matches:
            prompt += "\n[Mandatory Glossary]\nYou MUST PRESERVE these exact translations:\n"
            for en_term, th_term in context.glossary_matches.items():
                prompt += f"- {en_term} -> {th_term}\n"
                
        if context.story_summary:
            prompt += f"\n[Story Context]\n{context.story_summary}\n"

        if context.chronological_summary:
            prompt += f"\n[Timeline & World State]\n{context.chronological_summary}\n"
                
        if context.style_rules:
            prompt += f"\n[STYLE RULES (Apply these semantic rules)]\n{context.style_rules}\n"
            
        if context.symbol_engine_rules:
            prompt += f"\n[SYMBOL INTEGRITY ENGINE (CRITICAL: Adhere to these code constraints)]\n{context.symbol_engine_rules}\n"
                
        return prompt

    def _build_translator_prompt(self, context: ContextData) -> str:
        """
        เครื่องจักรประกอบ Prompt สำหรับ Editor เมื่อต้องแปล LIGHT Batch โดยตรง (UI, Items)
        """
        prompt = (
            "You are a specialized Translator for game localization (UI, Items, and Choices).\n"
            "Your job is to translate the source text to Thai accurately and naturally.\n\n"
            "CRITICAL RULES (To pass QA Evaluation):\n"
            "1. These are usually short phrases or UI elements. Keep the translation concise.\n"
            "2. DO NOT add emojis, narrative thoughts, or extra context.\n"
            "3. MUST strictly follow the provided Glossary. Exact matches only.\n"
            "4. NO Alien Text: Do not include Chinese, Japanese, or unnecessary foreign characters.\n"
            "5. Grammar & Word Order: Ensure natural Thai phrasing. Expressions like 'เหรอเลย' are forbidden; use 'เลยเหรอ'.\n"
            "6. Output ONLY the translated text.\n"
        )
        if context.glossary_matches:
            prompt += "\n[Mandatory Glossary]\nYou MUST PRESERVE these exact translations:\n"
            for en_term, th_term in context.glossary_matches.items():
                prompt += f"- {en_term} -> {th_term}\n"
        if context.symbol_engine_rules:
            prompt += f"\n[SYMBOL INTEGRITY ENGINE (CRITICAL)]\n{context.symbol_engine_rules}\n"
        return prompt

    async def process(self, batch: TranslationBatch) -> bool:
        """
        กระบวนการเกลาภาษาแบบทำงานเป็นชุด (Batch) และซ่อมแซมเฉพาะจุด (Targeted Repair)
        """
        self.set_status(f"Editing Batch: {batch.batch_id} ({len(batch.tokens)} tokens)")
        logger.info(f"[EditorAgent] Processing batch: {batch.batch_id}")
        
        try:
            tokens_to_edit = []
            for t in batch.tokens:
                if batch.batch_type == "LIGHT" and not t.outputs.translator_output:
                    # LIGHT Batch ไม่มีผลแปลตั้งต้น Editor ต้องแปลเอง!
                    if t.outputs.qa_feedback or not t.outputs.editor_output:
                        tokens_to_edit.append(t)
                else:
                    # มีผลแปลตั้งต้นจาก Translator แล้ว (เป็น HEAVY หรือ LIGHT ที่ Translator ช่วยแปล)
                    if not t.outputs.translator_output:
                        continue # ข้ามประโยคที่ยังไม่ได้แปล
                    if t.outputs.qa_feedback or not t.outputs.editor_output:
                        tokens_to_edit.append(t)
                    
            if not tokens_to_edit:
                self.set_status("IDLE")
                return True
            
            context = tokens_to_edit[0].context
            
            # 1. ประกอบ System Prompt
            is_translator_assisted = any(t.outputs.translator_output for t in tokens_to_edit)
            if batch.batch_type == "LIGHT" and not is_translator_assisted:
                system_prompt = self._build_translator_prompt(context)
            else:
                system_prompt = self._build_system_prompt(context)
                
            system_prompt += (
                "\n\nFormat your output as a JSON array of objects like this:\n"
                "[\n"
                '  {"id": "...", "thought_process": "Self-correction checking glossary, grammar, and particles...", "edited_text": "..."}\n'
                "]"
            )
            
            # 2. ทำการ Chunking เพื่อไม่ให้ Context ยาวเกินไปจน Model สับสน (ตัดทีละ 10 tokens)
            chunk_size = 10
            success_count = 0
            
            for i in range(0, len(tokens_to_edit), chunk_size):
                chunk = tokens_to_edit[i:i + chunk_size]
                self.set_status(f"Editing Batch: {batch.batch_id} (Chunk {i+1}-{i+len(chunk)}/{len(tokens_to_edit)})")
                
                if batch.batch_type == "LIGHT":
                    user_prompt = "Here are the short texts to translate:\n"
                    for t in chunk:
                        feedback_info = f"\n  - QA Feedback (Fix this): {t.outputs.qa_feedback}" if t.outputs.qa_feedback else ""
                        user_prompt += f'- ID: {t.id}\n  - Original: {t.original_text}{feedback_info}\n'
                else:
                    user_prompt = "Here are the rough translations to edit:\n"
                    for t in chunk:
                        speaker_info = f" | Speaker: {t.speaker}" if t.speaker else ""
                        feedback_info = f"\n  - QA Feedback (Fix this): {t.outputs.qa_feedback}" if t.outputs.qa_feedback else ""
                        user_prompt += f'- ID: {t.id}{speaker_info}\n  - Original: {t.original_text}\n  - Rough: {t.outputs.translator_output}{feedback_info}\n'
                
                expected_ids = [t.id for t in chunk]
                items = await self.execute_with_retry(system_prompt, user_prompt, expected_ids)
                
                if not items:
                    logger.error(f"[EditorAgent] Failed to process chunk in batch {batch.batch_id} after retries.")
                    self.set_status("IDLE")
                    return False
                    
                for item in items:
                    item_id = item.get("id")
                    edited = item.get("edited_text", item.get("text", ""))
                    if item_id and edited:
                        for t in chunk:
                            if t.id == item_id:
                                t.outputs.editor_output = str(edited).replace('\n', '\\n').strip()
                                t.outputs.qa_feedback = None # ล้าง Feedback ทิ้งหลังแก้เสร็จ
                                success_count += 1
                                break
                            
            logger.debug(f"[EditorAgent] Editing success: {success_count}/{len(tokens_to_edit)} tokens")
            self.set_status("IDLE")
            return True
                
        except Exception as e:
            logger.error(f"[EditorAgent] Error processing batch {batch.batch_id}: {str(e)}")
            self.set_status("IDLE")
            return False