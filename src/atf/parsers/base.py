import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from ..core.models import TranslationToken, TokenState

logger = logging.getLogger(__name__)

class BaseParser(ABC):
    """
    คลาสแม่ (Abstract Base Class) สำหรับ Parser ของทุกเอนจินเกม
    ทำหน้าที่แกะไฟล์ต้นฉบับ สกัดเฉพาะข้อความที่ต้องแปล และประกอบไฟล์กลับเมื่อแปลเสร็จ
    """

    @abstractmethod
    def parse(self, filepath: str) -> List[TranslationToken]:
        """
        [ต้องนำไปเขียนลอจิกเฉพาะของแต่ละเอนจินเกม]
        อ่านไฟล์ต้นฉบับ ใช้ Regex แยกแยะระหว่าง "โค้ด" และ "บทสนทนา"
        
        Args:
            filepath: เส้นทางไปยังไฟล์เกมต้นฉบับ
            
        Returns:
            List[TranslationToken]: รายการของประโยคที่สกัดออกมาและพร้อมส่งเข้า Event Bus
        """
        pass

    @abstractmethod
    def export(self, filepath: str, tokens: List[TranslationToken], output_path: str) -> bool:
        """
        [ต้องนำไปเขียนลอจิกเฉพาะของแต่ละเอนจินเกม]
        นำประโยคที่แปลเสร็จแล้ว (READY_TO_EXPORT) ไปแทนที่ในโครงสร้างไฟล์เดิม
        
        Args:
            filepath: เส้นทางไฟล์ต้นฉบับ (เพื่อใช้อ้างอิงโครงสร้างบรรทัดเดิม)
            tokens: รายการ Token ที่ผ่านการแปลและตรวจสอบแล้ว
            output_path: เส้นทางสำหรับบันทึกไฟล์ใหม่ที่แปลเสร็จแล้ว
            
        Returns:
            bool: สถานะความสำเร็จในการ Export
        """
        pass

    def create_token(
        self, 
        token_id: str, 
        original_text: str, 
        speaker: Optional[str] = None, 
        metadata: Optional[Dict[str, str]] = None
    ) -> TranslationToken:
        """
        ฟังก์ชันช่วยเหลือ (Utility) สำหรับสร้าง Token อย่างรวดเร็ว
        โดยจะกำหนด State เริ่มต้นเป็น UNPROCESSED เสมอ
        """
        return TranslationToken(
            id=token_id,
            speaker=speaker,
            original_text=original_text,
            current_state=TokenState.UNPROCESSED,
            metadata=metadata or {}
        )