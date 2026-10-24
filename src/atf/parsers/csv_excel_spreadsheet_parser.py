import csv
import logging
import re
from typing import List
import os

from .base import BaseParser
from ..core.models import TranslationToken, TokenState

logger = logging.getLogger(__name__)

class CSVParser(BaseParser):
    """
    Parser สำหรับไฟล์ .csv 5 คอลัมน์: Original, Initial, Filename, Row, Note
    """

    def __init__(self):
        super().__init__()
        self.raw_rows = []
        self.header = None

    def parse(self, filepath: str) -> List[TranslationToken]:
        tokens: List[TranslationToken] = []
        logger.info(f"[CSVParser] Parsing file: {filepath}")
        
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                self.header = next(reader, None)
                self.raw_rows = list(reader)
                
                for row_idx, row in enumerate(self.raw_rows):
                    # คาดหวัง 8 คอลัมน์: Original, Initial, Filename, Row, Note, Role, Speaker, Displayable
                    if len(row) < 5:
                        continue
                        
                    original_text = row[0].strip().replace('\n', '✎')
                    initial_text = row[1].strip().replace('\n', '✎')
                    filename = row[2].strip() if len(row) > 2 else ""
                    row_num = row[3].strip() if len(row) > 3 else ""
                    note = row[4].strip() if len(row) > 4 else ""
                    role = row[5].strip() if len(row) > 5 else ""
                    speaker_col = row[6].strip() if len(row) > 6 else ""
                    displayable = row[7].strip() if len(row) > 7 else "Yes"
                    
                    if not original_text:
                        continue
                        
                    # ข้ามแถวที่ไม่ต้องแปล
                    if "ค่าว่าง" in note or "ถูกลบออก" in note:
                        continue
                        
                    # สร้าง Unique ID สำหรับแต่ละแถว (Filename_Row)
                    token_id = f"{filename}_{row_num}"
                    if not filename and not row_num:
                        token_id = f"row_{row_idx}"
                        
                    # หาชื่อคนพูดจากแพทเทิร์น \n<Name> หรือ \n<Name:> หรือ <Name> หรือจากคอลัมน์ Speaker โดยตรง
                    speaker = speaker_col if speaker_col else None
                    if not speaker:
                        speaker_match = re.search(r"<([^>:]+):?>", original_text)
                        if speaker_match:
                            speaker = speaker_match.group(1).strip()
                            
                    token = self.create_token(
                        token_id=token_id,
                        original_text=original_text,
                        speaker=speaker,
                        metadata={
                            "row_index": str(row_idx),
                            "Filename": filename,
                            "Row": row_num,
                            "note": note,
                            "initial_text": initial_text,
                            "role": role
                        }
                    )
                    
                    # สร้าง clean_text โดยลบ \n, \., และ tag ผู้พูด เพื่อตรวจสอบ
                    clean_text = re.sub(r'\\n|<[^>]+>|\\\.', '', original_text).strip()
                    
                    # ประมาณการ Token
                    token.estimated_tokens = (len(original_text) // 4) + 1
                    
                    # เช็คว่าแปลไปแล้วหรือยัง หรือข้ามการแปล
                    if displayable.lower() == "no":
                        token.current_state = TokenState.ALREADY_TRANSLATED
                        token.outputs.final_output = original_text
                        token.token_type = "ALREADY_TRANSLATED"
                    elif initial_text:
                        token.current_state = TokenState.ALREADY_TRANSLATED
                        token.outputs.final_output = initial_text
                        token.token_type = "ALREADY_TRANSLATED"
                    else:
                        # --- CODE_ONLY Check ---
                        # 1. Alphanumeric with no spaces but allow brackets/parentheses
                        is_code = bool(re.match(r'^[A-Za-z0-9_\-\.\[\]\\\(\)]+$', clean_text))
                        # 2. Fully enclosed in tags like <addFog 1: 1> or \V[1]
                        if not is_code and re.match(r'^<[^>]+>$|^\\[A-Za-z]+\[\d+\]$', original_text.strip()):
                            is_code = True
                            
                        if is_code:
                            token.current_state = TokenState.ALREADY_TRANSLATED
                            token.outputs.final_output = original_text
                            token.token_type = "CODE_ONLY"
                        else:
                            # --- Classification Logic ---
                            has_newline = "\\n" in original_text or "\\N" in original_text
                            is_map_or_event = filename.startswith("Map") or filename.startswith("CommonEvents")
                            
                            if speaker or "\\n<" in original_text or "\\N<" in original_text:
                                token.token_type = "HEAVY_DIALOGUE" # Dialogue with explicit speaker
                            elif is_map_or_event and (has_newline or len(original_text) >= 30):
                                token.token_type = "HEAVY_DIALOGUE" # Typical NPC speech or cutscene text
                            elif has_newline and len(original_text) >= 50:
                                token.token_type = "HEAVY_DESCRIPTION" # Long description with newlines
                            elif len(original_text) >= 80:
                                token.token_type = "HEAVY_DESCRIPTION" # Very long description even without newlines
                            else:
                                token.token_type = "LIGHT_DISPLAYABLE" # UI, Item names, Choices, Short labels
                            
                    tokens.append(token)
                    
            logger.info(f"[CSVParser] Extracted {len(tokens)} tokens from {filepath}")
            return tokens
            
        except Exception as e:
            logger.error(f"[CSVParser] Failed to parse {filepath}: {str(e)}")
            return []

    def export(self, filepath: str, tokens: List[TranslationToken], output_path: str) -> bool:
        """
        นำคำแปลกลับไปใส่ในคอลัมน์ Initial แล้วเขียนลงไฟล์ใหม่
        """
        logger.info(f"[CSVParser] Exporting translated file to: {output_path}")
        
        token_map = {t.id: t.outputs.final_output for t in tokens if t.current_state in (TokenState.READY_TO_EXPORT, TokenState.ALREADY_TRANSLATED)}
        
        try:
            # อัปเดตข้อมูลในหน่วยความจำ (self.raw_rows)
            for row_idx, row in enumerate(self.raw_rows):
                if len(row) < 5:
                    continue
                    
                filename = row[2].strip()
                row_num = row[3].strip()
                
                token_id = f"{filename}_{row_num}"
                if not filename and not row_num:
                    token_id = f"row_{row_idx}"
                
                if token_id in token_map:
                    row[1] = str(token_map[token_id] or "").replace('✎', '\n')
                    
            # เขียนลง output_path อย่างปลอดภัย (Atomic Write)
            self.write_to_disk(output_path)
                        
            logger.info(f"[CSVParser] Export successful: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"[CSVParser] Export failed for {filepath}: {str(e)}")
            return False

    def update_token_in_memory(self, token: TranslationToken) -> bool:
        """
        อัปเดตข้อมูล Token ลงในหน่วยความจำ (self.raw_rows) เท่านั้น
        """
        try:
            row_idx = int(token.metadata["row_index"])
            final_out = token.outputs.final_output or token.outputs.timing_output or token.outputs.editor_output or token.outputs.translator_output or ""
            if len(self.raw_rows[row_idx]) >= 2:
                self.raw_rows[row_idx][1] = str(final_out).replace('✎', '\n')
            return True
        except Exception as e:
            logger.error(f"[CSVParser] Failed to update token in memory {token.id}: {str(e)}")
            return False

    def write_to_disk(self, output_path: str) -> bool:
        """
        เขียนข้อมูลทั้งหมดจากหน่วยความจำลงไฟล์ปลายทางอย่างปลอดภัย (Atomic Write)
        """
        import tempfile
        import shutil
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            temp_path = output_path + ".tmp"
            
            with open(temp_path, mode='w', encoding='utf-8-sig', newline='') as file_out:
                writer = csv.writer(file_out)
                if self.header:
                    writer.writerow(self.header)
                writer.writerows(self.raw_rows)
                
            os.replace(temp_path, output_path)
            return True
        except Exception as e:
            logger.error(f"[CSVParser] Failed to write to disk {output_path}: {str(e)}")
            return False

    def export_single_token(self, token: TranslationToken, output_path: str) -> bool:
        """
        บันทึก Token เดียวลงในหน่วยความจำและเขียนทับไฟล์ CSV ทันที (Continuous Saving)
        (ไม่แนะนำให้ใช้บ่อยเกินไปเพราะเขียนไฟล์ใหม่ทั้งหมดทุกรอบ แนะนำให้ใช้วิธีอัปเดตหน่วยความจำแล้วเขียนทีละ Batch)
        """
        if self.update_token_in_memory(token):
            return self.write_to_disk(output_path)
        return False