import logging
from .base import BaseAgent
from ..core.models import TranslationBatch, ContextData

logger = logging.getLogger(__name__)

class TranslatorAgent(BaseAgent):
    """
    Agent สำหรับการแปลภาษา (ด่านแรก)
    เน้นความถูกต้องของความหมาย 100% โดยยังไม่ต้องสนใจความสละสลวยมากนัก
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name, agent_name="Translator (Sophia)")

    def _build_system_prompt(self, context: ContextData) -> str:
        """
        เครื่องจักรประกอบ Prompt สำหรับ Translator (อิงจาก SDD-002)
        """
        # 1. System Layer (คำสั่งหลักจาก SDD-003)
        prompt = (
            "You are a highly accurate Translator Agent specializing in game localization (English to Thai).\n"
            "Your ONLY job is to translate the source text to Thai without losing any core meaning.\n\n"
            "CRITICAL RULES (To pass QA Evaluation):\n"
            "1. DO NOT try to make it sound overly beautiful if it changes the meaning.\n"
            "2. DO NOT add emojis, narrative thoughts, or extra context that is not in the source.\n"
            "3. MUST strictly follow the provided Glossary. Exact matches only.\n"
            "4. NO Alien Text: Do not include Chinese, Japanese, or unnecessary foreign characters.\n"
            "5. Grammar & Word Order: Ensure natural Thai phrasing. Expressions like 'เหรอเลย' are forbidden; use 'เลยเหรอ'.\n"
            "6. Thai Particles: Use 'คะ/ขา' for female questions/calling, 'ค่ะ/ค่า' for statements/answers. Use 'จ๊ะ/จ้ะ' properly.\n"
            "7. Gender & Pronouns:\n"
            "   - Standard Grammatical Pronouns (I, you, he, she, we, they, it): Strictly follow the [TRANSLATION GUIDANCE] provided for 1st/2nd/3rd person pronouns and ending particles.\n"
            "   - Specific Direct Addresses & Vocatives (Papa, Mama, Dear, Honey, Babe, That guy, Master, etc.): Translate naturally according to direct context and character nuance (e.g. ป๊ะป๋า, หม่าม้า, ที่รัก, หมอนั่น) WITHOUT overriding them with generic pronouns.\n"
            "8. Output ONLY the translated text. No explanations.\n\n"
            "FEW-SHOT EXAMPLES (Self-Correction):\n"
            "- BAD: อย่างนั้นเหรอเลย? -> GOOD: อย่างนั้นเลยเหรอ?\n"
            "- BAD (Question): ไปไหนมาคะ? -> GOOD (Statement): ไปตลาดมาค่ะ (Use 'ค่ะ' for answers)\n"
            "- BAD (Ignore Guidance): ฉันสบายดีครับ (If Guidance says Female/'ฉัน'/'ค่ะ') -> GOOD: ฉันสบายดีค่ะ\n"
        )
        
        # 2. Context Layer (ข้อมูลบริบทเฉพาะ Batch)
        if getattr(context, "pronoun_guidance", None):
            prompt += f"\n{context.pronoun_guidance}\n"
            
        if getattr(context, "direct_scene_context", None):
            prompt += f"\n[Direct Scene Context]\n{context.direct_scene_context}\n"

        if context.character_traits:
            prompt += "\n[Character Info]\n"
            traits = ", ".join(context.character_traits)
            prompt += f"Traits: {traits}\n"
                
        if context.glossary_matches:
            prompt += "\n[Mandatory Glossary]\nYou MUST use these exact translations:\n"
            for en_term, th_term in context.glossary_matches.items():
                prompt += f"- {en_term} -> {th_term}\n"
                
        if context.translation_memory:
            prompt += "\n[Reference Memory]\nSimilar translated lines for reference:\n"
            for mem in context.translation_memory:
                prompt += f"- EN: {mem.get('en', '')} | TH: {mem.get('th', '')}\n"
                
        if context.story_summary:
            prompt += f"\n[Story Context]\n{context.story_summary}\n"

        if context.chronological_summary:
            prompt += f"\n[Timeline & World State]\n{context.chronological_summary}\n"
                
        if context.style_rules:
            prompt += f"\n[STYLE RULES (Apply these semantic rules)]\n{context.style_rules}\n"
            
        if context.symbol_engine_rules:
            prompt += f"\n[SYMBOL INTEGRITY ENGINE (CRITICAL: Adhere to these code constraints)]\n{context.symbol_engine_rules}\n"
                
        return prompt

    async def process(self, batch: TranslationBatch) -> bool:
        """
        ฟังก์ชันหลักในการประมวลผล Batch
        """
        self.set_status(f"Translating Batch: {batch.batch_id} ({len(batch.tokens)} tokens)")
        logger.info(f"[TranslatorAgent] Processing batch: {batch.batch_id}")
    
        try:
            # รวบรวมประโยคที่ยังไม่ได้แปล
            tokens_to_translate = [t for t in batch.tokens if not t.outputs.translator_output]
            if not tokens_to_translate:
                self.set_status("IDLE")
                return True

            context = tokens_to_translate[0].context
            
            system_prompt = self._build_system_prompt(context)
            system_prompt += (
                "\n\nFormat your output as a JSON array of objects like this:\n"
                "[\n"
                '  {"id": "...", "thought_process": "Self-correction checking glossary, grammar, and particles...", "translated_text": "..."}\n'
                "]"
            )
            
            # 3. Task Layer
            user_prompt = "Here are the texts to translate:\n"
            for t in tokens_to_translate:
                speaker_info = f" | Speaker: {t.speaker}" if t.speaker else ""
                role_info = f" | Role: {t.metadata.get('role', 'Unknown')}" if t.metadata.get('role') else ""
                user_prompt += f'- ID: {t.id}{role_info}{speaker_info} | Text: {t.original_text}\n'
            
            expected_ids = [t.id for t in tokens_to_translate]
            items = await self.execute_with_retry(system_prompt, user_prompt, expected_ids)
            
            if not items:
                logger.error(f"[TranslatorAgent] Failed to process batch {batch.batch_id} after retries.")
                self.set_status("IDLE")
                return False
                
            success_count = 0
            for item in items:
                item_id = item.get("id")
                translated = item.get("translated_text", item.get("text", ""))
                if item_id and translated:
                    for t in tokens_to_translate:
                        if t.id == item_id:
                            t.outputs.translator_output = str(translated).replace('\n', '\\n').strip()
                            success_count += 1
                            break
            
            logger.debug(f"[TranslatorAgent] Translation success: {success_count}/{len(tokens_to_translate)} tokens")
            self.set_status("IDLE")
            return True
                
        except Exception as e:
            logger.error(f"[TranslatorAgent] Error processing batch {batch.batch_id}: {str(e)}")
            self.set_status("IDLE")
            return False