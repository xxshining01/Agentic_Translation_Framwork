import re
import logging
from typing import List

from ..core.models import TranslationToken, TokenState

logger = logging.getLogger(__name__)

class SyntaxValidator:
    """
    โมดูลตรวจสอบความถูกต้องเชิงโครงสร้าง (Deterministic Validation) ด่านสุดท้าย
    อิงจาก ADR-008: ป้องกัน AI ทำลายแท็กโค้ดหรือตัวแปรในประโยค
    """
    
    def __init__(self):
        # Regex สำหรับหาตัวแปรทั่วไปในเกมเอนจิน เช่น [player_name], {color=red}, %s, \n
        self.variable_patterns = [
            re.compile(r'\[.*?\]'),       # จับ [variable]
            re.compile(r'\{.*?\}'),       # จับ {tag}
            re.compile(r'<.*?>'),         # จับ <tag>
            re.compile(r'%.'),            # จับ %s, %d (C-style formatting)
            re.compile(r'\\.'),           # จับ escape \n, \t, \.
            re.compile(r'[<>]')           # จับ < หรือ > ที่แอบเติมมา
        ]

    def _extract_variables(self, text: str) -> List[str]:
        """สกัดตัวแปรทั้งหมดออกจากข้อความ"""
        variables = []
        for pattern in self.variable_patterns:
            variables.extend(pattern.findall(text))
        return variables

    def validate(self, token: TranslationToken) -> bool:
        """
        ตรวจสอบว่าผลลัพธ์สุดท้ายมีตัวแปร/แท็ก ครบถ้วนตรงตามต้นฉบับหรือไม่
        เรียกใช้เมื่อสถานะเป็น TIMING -> VALIDATING
        """
        logger.info(f"[Validator] Validating syntax for token: {token.id}")
        
        original_text = token.original_text
        # ใช้ผลลัพธ์จาก Timing Agent (หรือ Editor หรือ Translator กรณีไม่มีขั้นตอนก่อนหน้า)
        target_text = token.outputs.timing_output or token.outputs.editor_output or token.outputs.translator_output
        
        if not target_text:
            logger.error(f"[Validator] No text to validate for token {token.id}")
            token.outputs.qa_feedback = "VALIDATION ERROR: Translation output is empty."
            return False

        # Convert actual newlines and tabs back to escape sequences to match original_text
        target_text = target_text.replace('\n', '\\n').replace('\t', '\\t').replace('\f', '\\f')

        # 1. สกัดตัวแปรจากต้นฉบับและคำแปล
        original_vars = self._extract_variables(original_text)
        translated_vars = self._extract_variables(target_text)
        
        # 2. ตรวจสอบว่าตัวแปรหายไป หรือ เกินมา หรือไม่
        original_counts = {}
        for v in original_vars:
            original_counts[v] = original_counts.get(v, 0) + 1
            
        translated_counts = {}
        for v in translated_vars:
            translated_counts[v] = translated_counts.get(v, 0) + 1
            
        missing_vars = []
        for v, count in original_counts.items():
            if translated_counts.get(v, 0) < count:
                missing_vars.append(v)
                
        extra_vars = []
        for v, count in translated_counts.items():
            if original_counts.get(v, 0) < count:
                extra_vars.append(v)
        
        if missing_vars or extra_vars:
            errors = []
            if missing_vars:
                errors.append(f"Missing variables: {', '.join(missing_vars)}")
            if extra_vars:
                errors.append(f"Extra/Invented variables: {', '.join(extra_vars)}")
                
            error_msg = f"SYNTAX ERROR: {' | '.join(errors)}"
            logger.error(f"[Validator] Token {token.id} failed validation. {error_msg}")
            
            # บันทึก Error กลับไปที่ Feedback เพื่อให้ Orchestrator ตีกลับ
            token.outputs.qa_feedback = error_msg 
            return False
            
        # 3. ถ้าผ่าน กำหนดให้เป็น final_output พร้อมส่งออก
        token.outputs.final_output = target_text
        logger.info(f"[Validator] Token {token.id} PASSED syntax validation.")
        return True