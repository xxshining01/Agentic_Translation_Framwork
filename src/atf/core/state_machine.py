from typing import Dict, List, Optional
from .models import TokenState, TranslationBatch

class StateMachine:
    """
    คลาสควบคุมวงจรชีวิต (Lifecycle) ของประโยคแปล
    ทำหน้าที่ป้องกันไม่ให้ State เปลี่ยนข้ามขั้นตอนอย่างผิดวิธี
    """
    def __init__(self):
        # กำหนดกฎการเปลี่ยนสถานะ (Allowed Transitions) อิงตามไดอะแกรมใน SAD-002
        self.allowed_transitions: Dict[TokenState, List[TokenState]] = {
            TokenState.UNPROCESSED: [TokenState.PENDING],
            TokenState.PENDING: [TokenState.TRANSLATING, TokenState.EDITING, TokenState.ERROR_CRITICAL],
            TokenState.TRANSLATING: [TokenState.EDITING, TokenState.ERROR_CRITICAL],
            TokenState.EDITING: [TokenState.QA_VERIFYING, TokenState.VALIDATING, TokenState.ERROR_CRITICAL],
            TokenState.QA_VERIFYING: [TokenState.TIMING, TokenState.QA_FAILED, TokenState.ERROR_CRITICAL],
            TokenState.QA_FAILED: [TokenState.EDITING, TokenState.TRANSLATING, TokenState.ERROR_CRITICAL], # Repair Loop Routes
            TokenState.TIMING: [TokenState.VALIDATING, TokenState.ERROR_CRITICAL],
            TokenState.VALIDATING: [TokenState.READY_TO_EXPORT, TokenState.TIMING, TokenState.EDITING, TokenState.TRANSLATING, TokenState.ERROR_CRITICAL], # กลับไป Timing ถ้าแท็กพัง
            TokenState.READY_TO_EXPORT: [TokenState.EXPORTED, TokenState.ERROR_CRITICAL],
            TokenState.EXPORTED: [],
            TokenState.ERROR_CRITICAL: [] # Dead end
        }
        
        # ขีดจำกัดการวนลูปซ่อมแซมเพื่อป้องกัน Infinite Loop
        self.max_retries = 3

    def can_transition(self, current_state: TokenState, next_state: TokenState) -> bool:
        """ตรวจสอบว่าอนุญาตให้เปลี่ยนจาก current_state ไปเป็น next_state หรือไม่"""
        allowed = self.allowed_transitions.get(current_state, [])
        return next_state in allowed

    def advance_state(self, batch: TranslationBatch, next_state: TokenState) -> bool:
        """
        พยายามเปลี่ยนสถานะของ Batch
        คืนค่า True หากเปลี่ยนสำเร็จ, False หากผิดกฎ
        """
        if self.can_transition(batch.current_state, next_state):
            batch.current_state = next_state
            return True
        return False

    def trigger_repair_loop(self, batch: TranslationBatch, target_agent: TokenState) -> bool:
        """
        ฟังก์ชันเฉพาะสำหรับกระตุ้น Repair Loop เมื่อไม่ผ่าน QA
        
        Args:
            batch: Batch ที่ไม่ผ่าน (ประโยคข้างในที่มีปัญหาจะถูกแปะ qa_feedback ไว้แล้ว)
            target_agent: ส่งกลับไปให้ใครแก้ (TokenState.EDITING หรือ TokenState.TRANSLATING)
        """
        if batch.current_state not in [TokenState.QA_VERIFYING, TokenState.VALIDATING]:
            return False
            
        if batch.retry_count >= self.max_retries:
            # หากวนลูปแก้จนเกินโควต้า ให้ส่งเข้า ERROR_CRITICAL ทันที
            batch.current_state = TokenState.ERROR_CRITICAL
            return True

        if batch.current_state == TokenState.QA_VERIFYING:
            if self.advance_state(batch, TokenState.QA_FAILED):
                batch.retry_count += 1
                return self.advance_state(batch, target_agent)
        elif batch.current_state == TokenState.VALIDATING:
            if self.advance_state(batch, target_agent):
                batch.retry_count += 1
                return True
            
        return False