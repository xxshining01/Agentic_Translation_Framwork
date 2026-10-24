import re
import logging
from typing import List

from .base import BaseParser
from ..core.models import TranslationToken, TokenState

logger = logging.getLogger(__name__)

class RenpyParser(BaseParser):
    """
    Parser เฉพาะทางสำหรับเกมเอนจิน Ren'Py (.rpy)
    รับผิดชอบในการสกัดเฉพาะบทสนทนา และปกป้องโค้ดคำสั่งไม่ให้หลุดไปถึง AI
    """
    
    def __init__(self):
        # Regex สำหรับจับบทสนทนาของ Ren'Py
        # รองรับรูปแบบ: <indent> <speaker_id (optional)> "<dialogue>"
        # ตัวอย่าง 1:     aila happy "นี่คือพลังของฉันงั้นเหรอ?" -> speaker='aila happy', text='นี่คือพลังของฉันงั้นเหรอ?'
        # ตัวอย่าง 2:     "วันเวลาผ่านไป..." -> speaker=None, text='วันเวลาผ่านไป...'
        self.dialogue_pattern = re.compile(
            r'^(?P<indent>\s*)(?P<speaker>[a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+)*)?\s*"(?P<text>.*?)"(?P<trailing>.*)$'
        )
        
        # Regex สำหรับข้ามบรรทัดที่เป็นโค้ดอย่างชัดเจน (Safety Check)
        self.code_pattern = re.compile(r'^\s*(image|define|transform|screen|label|init|\$|menu|jump|call|pass|return)')

    def parse(self, filepath: str) -> List[TranslationToken]:
        """อ่านไฟล์ .rpy และสกัดประโยคออกมาเป็น Token"""
        tokens: List[TranslationToken] = []
        
        logger.info(f"[RenpyParser] Parsing file: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line_idx, line in enumerate(lines):
                # 1. ข้ามบรรทัดว่างและบรรทัดที่เป็น Comment
                if not line.strip() or line.strip().startswith('#'):
                    continue
                    
                # 2. ข้ามบรรทัดที่เป็นคำสั่งระบบชัดเจน
                if self.code_pattern.match(line):
                    continue
                    
                # 3. ตรวจจับประโยคบทสนทนาด้วย Regex
                match = self.dialogue_pattern.match(line)
                if match:
                    # สกัดข้อมูลออกมา
                    indent = match.group('indent')
                    speaker = match.group('speaker')
                    original_text = match.group('text')
                    trailing = match.group('trailing')
                    
                    if not original_text.strip():
                        continue # ข้ามประโยคที่มีแต่เครื่องหมายคำพูดเปล่าๆ
                        
                    # 4. ห่อใส่ TranslationToken
                    token_id = f"{filepath}_line{line_idx}"
                    metadata = {
                        "engine": "renpy",
                        "line_number": str(line_idx),
                        "indent": indent,
                        "trailing": trailing,
                        "raw_line": line.rstrip('\n')
                    }
                    
                    token = self.create_token(
                        token_id=token_id,
                        original_text=original_text,
                        speaker=speaker.strip() if speaker else None,
                        metadata=metadata
                    )
                    tokens.append(token)
                    
            logger.info(f"[RenpyParser] Extracted {len(tokens)} tokens from {filepath}")
            return tokens
            
        except Exception as e:
            logger.error(f"[RenpyParser] Failed to parse {filepath}: {str(e)}")
            return []

    def export(self, filepath: str, tokens: List[TranslationToken], output_path: str) -> bool:
        """ประกอบคำแปลกลับเข้าไปในไฟล์ .rpy ต้นฉบับ"""
        logger.info(f"[RenpyParser] Exporting translated file to: {output_path}")
        
        # สร้าง Dictionary เพื่อให้ค้นหา Token ด้วย Line Number ได้รวดเร็ว (O(1))
        token_map = {int(t.metadata["line_number"]): t for t in tokens if t.current_state == TokenState.READY_TO_EXPORT}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # สร้างไฟล์ใหม่
            with open(output_path, 'w', encoding='utf-8') as f_out:
                for line_idx, line in enumerate(lines):
                    if line_idx in token_map:
                        # 1. ดึง Token ที่แปลเสร็จแล้วมา
                        token = token_map[line_idx]
                        translated_text = token.outputs.final_output
                        
                        # 2. ประกอบร่างใหม่ด้วยชิ้นส่วนเดิมที่เก็บไว้ใน Metadata
                        indent = token.metadata.get("indent", "")
                        speaker_part = f"{token.speaker} " if token.speaker else ""
                        trailing = token.metadata.get("trailing", "")
                        
                        # สร้างบรรทัดใหม่ที่ปลอดภัย 100%
                        new_line = f'{indent}{speaker_part}"{translated_text}"{trailing}\n'
                        f_out.write(new_line)
                    else:
                        # ถ้าไม่ใช่บรรทัดที่แปล (เป็นพวกโค้ดภาพ โค้ดเสียง) ให้เขียนกลับไปเหมือนเดิมเป๊ะๆ
                        f_out.write(line)
                        
            logger.info(f"[RenpyParser] Export successful: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"[RenpyParser] Export failed for {filepath}: {str(e)}")
            return False