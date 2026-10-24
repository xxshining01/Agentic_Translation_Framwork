# SDD-005: TLAS Taxonomy System

**Date:** 2026-07-18
**Related ADRs:** ADR-009

## 1. Overview
TLAS (Translation Linguistic Annotation System) ใช้ Taxonomy แบบรวมศูนย์ (Centralized) ในการอ้างอิงคุณลักษณะเชิงภาษาศาสตร์ ทุกการวิเคราะห์และ Metadata ที่ออกมาจาก Analyzer Agent หรือถูกกำหนดใน Character Knowledge ต้องใช้ Tag จาก Taxonomy นี้เท่านั้น

## 2. The Golden Rule
> **"ทุก Tag ในระบบ ต้องมีผลต่อการตัดสินใจด้านภาษาเท่านั้น"**

หากข้อมูลใดไม่มีผลต่อการเลือก Pronoun, Register, Honorific, Sentence Style, Tone, หรือ Vocabulary ห้ามนำมาสร้างเป็น Tag (เช่น รสนิยมความชอบที่ไม่กระทบรูปประโยค, สีผม, ส่วนสูง)

## 3. Comprehensive Taxonomy Dictionary (Strict Allowed Values)
เพื่อป้องกันไม่ให้ AI สร้าง Tag เองแบบมั่วซอว์ (เช่น `lovely`, `cutie`) เราบังคับให้ AI เลือกใช้ Tag จากพจนานุกรมด้านล่างนี้เท่านั้น โดยครอบคลุมความเป็นไปได้ทั้งหมด:

### 3.1 PER (Personality - บุคลิกภาพ)
- `PER_SOC_POLITE`: สุภาพ, อ่อนน้อม, ให้เกียรติคนอื่น
- `PER_SOC_RUDE`: หยาบคาย, ไม่สนมารยาท
- `PER_SOC_OUTGOING`: ร่าเริง, เข้าสังคมเก่ง, คุยเก่ง
- `PER_SOC_INTROVERT`: เก็บตัว, เงียบขรึม, พูดน้อย
- `PER_MIND_LOGICAL`: มีเหตุผล, คิดวิเคราะห์, เยือกเย็น
- `PER_MIND_EMOTIONAL`: ใช้อารมณ์นำ, อ่อนไหวง่าย
- `PER_MIND_CUNNING`: เจ้าเล่ห์, มีเล่ห์เหลี่ยม
- `PER_MIND_NAIVE`: ไร้เดียงสา, ซื่อตรง, อ่อนต่อโลก
- `PER_VIBE_CUTE`: น่ารัก, สดใส, น่าทะนุถนอม (ครอบคลุม kawaii, lovely)
- `PER_VIBE_SERIOUS`: จริงจัง, ดุดัน, น่าเกรงขาม
- `PER_VIBE_FLIRTY`: เจ้าชู้, ขี้หลี, ชอบหยอด
- `PER_VIBE_ARROGANT`: หยิ่งยโส, ทะนงตัว

### 3.2 SPR (Speech Habit - รูปแบบการพูด)
- `SPR_HESITANT`: พูดติดอ่าง, ลังเล, มีคำว่า อะ..เอ่อ.. บ่อยๆ
- `SPR_DIRECT`: พูดขวานผ่าซาก, ตรงไปตรงมา, ไม่อ้อมค้อม
- `SPR_SARCASTIC`: ชอบพูดประชดประชัน, แดกดัน
- `SPR_POETIC`: พูดจาภาษาสละสลวย, เหมือนบทกวี
- `SPR_LAZY`: พูดเนือยๆ, ลากเสียงยาว, ขี้เกียจพูด
- `SPR_ENERGETIC`: พูดรัวเร็ว, ตื่นเต้นตลอดเวลา
- `SPR_POLITE_SUFFIX`: ลงท้ายด้วย ครับ/ค่ะ/เจ้าค่ะ เสมอ
- `SPR_SLANG`: ชอบใช้คำสแลง, คำหยาบ, ภาษาวิบัติ

### 3.3 VAL (Values & Beliefs - ค่านิยม)
- `VAL_DUTY`: ยึดมั่นในหน้าที่, กฎระเบียบ
- `VAL_FREEDOM`: รักอิสระ, เกลียดการถูกบังคับ
- `VAL_FAMILY`: ครอบครัว/พวกพ้องต้องมาก่อน
- `VAL_POWER`: บูชาความแข็งแกร่ง, อำนาจ
- `VAL_MONEY`: หน้าเงิน, ทำทุกอย่างเพื่อผลประโยชน์
- `VAL_COMPASSION`: มีเมตตา, ชอบช่วยเหลือผู้อื่น

### 3.4 REL (Relationship - ความสัมพันธ์)
- `REL_FAMILY_PARENT`: พ่อ/แม่/ผู้ปกครอง
- `REL_FAMILY_CHILD`: ลูก/ผู้อยู่ใต้ปกครอง
- `REL_FAMILY_SIBLING`: พี่น้อง
- `REL_WORK_BOSS`: เจ้านาย/ผู้บังคับบัญชา
- `REL_WORK_SUBORDINATE`: ลูกน้อง/ผู้ใต้บังคับบัญชา
- `REL_FRIEND`: เพื่อน/สหาย
- `REL_ENEMY`: ศัตรู/คู่อริ
- `REL_STRANGER`: คนแปลกหน้า
- `REL_LOVER`: คนรัก/คู่หมั้น

### 3.5 INT (Intent - เจตนาการพูด)
- `INT_INFORM`: แจ้งให้ทราบ, เล่าเรื่อง
- `INT_QUESTION`: ตั้งคำถาม, สงสัย
- `INT_COMMAND`: สั่งการ, บังคับ
- `INT_REQUEST`: ขอร้อง, วิงวอน
- `INT_THREATEN`: ข่มขู่, คุกคาม
- `INT_COMFORT`: ปลอบโยน, ให้กำลังใจ
- `INT_MOCK`: เยาะเย้ย, ถากถาง

### 3.6 EMO (Emotion - อารมณ์)
- `EMO_NEUTRAL`: ปกติ, เรียบเฉย
- `EMO_JOY`: ดีใจ, มีความสุข
- `EMO_ANGER`: โกรธ, หงุดหงิด
- `EMO_SADNESS`: เศร้า, เสียใจ
- `EMO_FEAR`: หวาดกลัว, ตระหนก
- `EMO_SURPRISE`: ประหลาดใจ, ตกใจ
- `EMO_DISGUST`: รังเกียจ, ขยะแขยง

### 3.7 REG (Register - ระดับภาษา)
- `REG_ROYAL`: คำราชาศัพท์
- `REG_FORMAL`: ทางการ, สุภาพมาก
- `REG_POLITE`: สุภาพทั่วไป (คนแปลกหน้า)
- `REG_CASUAL`: กันเอง (เพื่อน, คนสนิท)
- `REG_VULGAR`: หยาบคาย

### 3.8 TON (Tone - น้ำเสียงแฝง)
- `TON_SERIOUS`: จริงจัง, ขึงขัง
- `TON_PLAYFUL`: หยอกล้อ, ทีเล่นทีจริง
- `TON_SARCASTIC`: ประชดประชัน, แดกดัน
- `TON_AGGRESSIVE`: ก้าวร้าว, คุกคาม, หาเรื่อง
- `TON_GENTLE`: นุ่มนวล, อ่อนโยน
- `TON_HESITANT`: ลังเล, ไม่มั่นใจ
- `TON_COLD`: เย็นชา, ไร้เยื่อใย

### 3.9 SIT (Situation - สถานการณ์แวดล้อม)
- `SIT_PUBLIC`: อยู่ต่อหน้าสาธารณชน หรือคนหมู่มาก
- `SIT_PRIVATE`: อยู่ในที่รโหฐาน หรือคุยกันส่วนตัว
- `SIT_CRISIS`: สถานการณ์ฉุกเฉิน, คอขาดบาดตาย
- `SIT_CEREMONY`: พิธีการ, งานทางการ
- `SIT_CASUAL`: สถานการณ์ชิวๆ, สบายๆ

### 3.10 CTX (Context - บริบทพิเศษ)
- `CTX_SECRET`: กำลังพูดความลับ, กระซิบ
- `CTX_PERSUASION`: กำลังโน้มน้าวใจ
- `CTX_INTERROGATION`: กำลังถูกสอบสวน หรือเค้นความจริง
- `CTX_FAREWELL`: การกล่าวลา, สั่งเสีย

### 3.11 BEL (Belief - ความเชื่อที่มีผลต่อภาษา)
- `BEL_RELIGIOUS`: ศรัทธาแรงกล้า (อาจมีคำเรียกเทพเจ้า/สวดมนต์)
- `BEL_ATHEIST`: ไม่เชื่อในสิ่งศักดิ์สิทธิ์
- `BEL_SUPERSTITION`: เชื่อเรื่องโชคลาง, ผีสาง

## 4. Pronoun Options & Mapping Matrix (Weighted Priority System)
เพื่อป้องกันปัญหา Array Order Dependency และลดความซ้ำซ้อนของข้อมูล (Redundancy) เราจะใช้ระบบ **Weighted Priority** ร่วมกับคุณลักษณะ (Traits) ของตัวละคร:

### 4.1 Pronoun Options (ตัวเลือกคำสรรพนาม)
- **Self (แทนตัวผู้พูด):** `"ผม", "ฉัน", "เรา", "ข้า", "หนู", "กู", "ดิฉัน", "ข้าพเจ้า", "พี่", "น้อง", "ลุง", "ป้า", "ตา", "ยาย"`
- **Target (แทนตัวผู้ฟัง):** `"คุณ", "นาย", "เธอ", "แก", "มึง", "ท่าน", "เอ็ง", "เจ้า", "พี่", "น้อง", "ลุง", "ป้า", "ตา", "ยาย"`
- **Ending (คำลงท้าย):** `"ครับ", "ค่ะ", "วะ", "โว้ย", "เพคะ", "พ่ะย่ะค่ะ", "ขอรับ", "เจ้าค่ะ", "จ้ะ", "จ๊ะ", "ฮะ", "เว้ย", ""` (ค่าว่างคือไม่มีคำลงท้าย)

### 4.2 Runtime Pronoun Resolution (การคำนวณสรรพนามแบบ Real-time)
ใน `taxonomy.json` จะมีตาราง `pronoun_mapping_rules` ซึ่งแต่ละกฎจะมี `priority_score` (น้ำหนักความสำคัญของกฎ) และจะถูกประเมินร่วมกับ `weight` ของ Character Traits (เช่น นิสัยก้าวร้าว 80%):
- `Rule A:` `IF Relation=REL_WORK_BOSS (Priority 100) -> "ผม/บอส/ครับ"`
- `Rule B:` `IF Personality=PER_SOC_RUDE (Priority 50) + Gender=MALE -> "ฉัน/แก/วะ"`

ระบบ Python Decision Engine จะทำการรันกฎทั้งหมดแล้วนำคะแนน (Rule Priority * Trait Weight) มาหาผู้ชนะ (Max Score) และเลือกสรรพนามนั้นไปใช้ตอนสั่งแปล (Phase 2) โดย **ไม่เซฟ** สรรพนามลงใน Profile Data เพื่อให้ระบบ Deterministic และไม่พึ่งพาลำดับของ Array

## 5. Tag Naming Convention
รูปแบบการตั้งชื่อ: `CATEGORY_NAME` ตาม Dictionary ด้านบน ห้าม AI สร้าง Tag นอกเหนือจากรายการนี้เด็ดขาด หากต้องการเพิ่ม Tag ใหม่ ต้องมาเพิ่มในรหัส Source Code ก่อนเท่านั้น

## 5. Tag Schema
ทุกๆ Tag จะถูกเก็บในรูปแบบ JSON ฐานข้อมูลกลาง (Taxonomy Database) โดยต้องมี Fields ดังนี้:

```json
{
  "id": "REG_FORMAL",
  "display_name": "Formal Register",
  "description": "ระดับภาษาทางการ ใช้โครงสร้างประโยคสมบูรณ์และคำศัพท์สุภาพ",
  "aliases": ["ทางการ", "สุภาพ"],
  "related": ["SIT_CEREMONY", "PER_SOC_POLITE"],
  "opposite": "REG_CASUAL",
  "version": "1.0",
  "deprecated": false
}
```

## 6. How It Impacts Pronouns
Taxonomy เป็นกลไกหลักที่ Decision Engine ใช้พิจารณา ตัวอย่างเช่น:
- หาก `REL = REL_WORK_BOSS` และ `SIT = SIT_PUBLIC`: สรรพนามคือ "ผม/ท่าน" (REG_FORMAL)
- หาก `REL = REL_WORK_BOSS` และ `SIT = SIT_PRIVATE` ควบคู่กับ `EMO = EMO_NEG_ANGER`: สรรพนามอาจเปลี่ยนเป็น "ฉัน/แก" (REG_CASUAL + TON_AGGRESSIVE)

การมี Taxonomy ที่รัดกุมทำให้เราสามารถสร้าง Matrix หรือ Decision Tree ในฝั่ง Python เพื่อควบคุมการแปลได้อย่างสมบูรณ์แบบ
