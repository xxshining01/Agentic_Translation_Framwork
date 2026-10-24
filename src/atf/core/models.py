from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class TokenState(str, Enum):
    """สถานะของประโยคที่ไหลไปตาม Pipeline"""
    UNPROCESSED = "UNPROCESSED"
    PENDING = "PENDING"
    TRANSLATING = "TRANSLATING"
    EDITING = "EDITING"
    QA_VERIFYING = "QA_VERIFYING"
    QA_FAILED = "QA_FAILED"
    TIMING = "TIMING"
    VALIDATING = "VALIDATING"
    READY_TO_EXPORT = "READY_TO_EXPORT"
    EXPORTED = "EXPORTED"
    ERROR_CRITICAL = "ERROR_CRITICAL"
    ALREADY_TRANSLATED = "ALREADY_TRANSLATED"

class ContextData(BaseModel):
    """ข้อมูลบริบทที่ดึงมาจาก Database เพื่อส่งให้ AI ประกอบ Prompt"""
    character_traits: List[str] = Field(
        default_factory=list, 
        description="ลักษณะนิสัยของตัวละครที่กำลังพูด"
    )
    glossary_matches: Dict[str, str] = Field(
        default_factory=dict, 
        description="คำศัพท์เฉพาะที่พบในประโยคและคำแปลบังคับ (Key: ต้นทาง, Value: แปล)"
    )
    translation_memory: List[Dict[str, str]] = Field(
        default_factory=list, 
        description="ประวัติการแปลประโยคที่ใกล้เคียง (อ้างอิงความสม่ำเสมอ)"
    )
    story_summary: Optional[str] = Field(
        default=None, 
        description="สรุปเนื้อเรื่องของเหตุการณ์ปัจจุบัน"
    )
    chronological_summary: Optional[str] = Field(
        default=None,
        description="สรุปไทม์ไลน์และสถานะโลกตาม Story Phase"
    )
    situation: List[str] = Field(
        default_factory=list,
        description="แท็กสถานการณ์ (เช่น SIT_PRIVATE, SIT_CRISIS)"
    )
    direct_scene_context: Optional[str] = Field(
        default=None,
        description="สรุปเหตุการณ์เฉพาะหน้าในฉากปัจจุบัน (TLAS v4.0)"
    )
    pronoun_guidance: Optional[str] = Field(
        default=None,
        description="คำแนะนำสรรพนามและหางเสียงเฉพาะคู่สนทนา (TLAS v4.0)"
    )
    style_rules: str = Field(default="", description="กฎเรื่องสไตล์จาก Master Prompt")
    symbol_engine_rules: str = Field(default="", description="กฎเรื่องสัญลักษณ์จาก Master Prompt")

    class Config:
        extra = "allow"

class AgentOutputs(BaseModel):
    """ผลลัพธ์การทำงานของ AI Agent แต่ละตัว"""
    translator_output: Optional[str] = Field(default=None, description="ผลลัพธ์จากการแปลตรงตัว")
    editor_output: Optional[str] = Field(default=None, description="ผลลัพธ์จากการเกลาภาษา")
    qa_feedback: Optional[str] = Field(default=None, description="คอมเมนต์ตีกลับจาก QA (ถ้าไม่ผ่าน)")
    timing_output: Optional[str] = Field(default=None, description="ผลลัพธ์ที่ใส่สัญลักษณ์ Timing แล้ว")
    final_output: Optional[str] = Field(default=None, description="ข้อความสมบูรณ์ที่พร้อมนำไป Export")

    class Config:
        extra = "allow"

class TranslationToken(BaseModel):
    """Payload หลักที่จะวิ่งไปมาระหว่าง Agent (ตาม Data Contract)"""
    id: str = Field(..., description="ID ของประโยค (เช่น file1_line042)")
    speaker: Optional[str] = Field(default=None, description="ชื่อผู้พูด (ถ้ามี)")
    original_text: str = Field(..., description="ข้อความต้นฉบับที่ต้องแปล (เอาแท็กโค้ดออกแล้ว)")
    
    current_state: TokenState = Field(default=TokenState.UNPROCESSED)
    
    token_type: str = Field(default="GENERAL", description="ประเภทของข้อความ (HEAVY, LIGHT, CODE)")
    estimated_tokens: int = Field(default=0, description="จำนวน token คร่าวๆ")
    
    context: ContextData = Field(default_factory=ContextData)
    outputs: AgentOutputs = Field(default_factory=AgentOutputs)
    
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="เก็บข้อมูลโค้ด/แท็กของเอนจินเกมเพื่อใช้นำไปประกอบร่างคืนในภายหลัง"
    )

    class Config:
        extra = "allow"

class TranslationBatch(BaseModel):
    """ตัวแทนของกลุ่มประโยค (Batch) ที่จะถูกประมวลผลพร้อมกัน"""
    batch_id: str = Field(..., description="ID ของ Batch")
    batch_type: str = Field(default="HEAVY", description="ประเภทของ Batch (HEAVY หรือ LIGHT)")
    tokens: List[TranslationToken] = Field(..., description="ประโยคใน Batch")
    
    current_state: TokenState = Field(default=TokenState.UNPROCESSED)
    retry_count: int = Field(default=0, description="จำนวนรอบที่วนลูปกลับไปแก้ (Repair Loop)")

    class Config:
        extra = "allow"