# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-011  
**ชื่อระบบ:** Python Parameter Consensus and Taxonomy Pronoun Engine  
**สถานะ:** Approved Design  
**วันที่:** 2026-09-13  
**เอกสารอ้างอิง:** ADR-015, SAD-010, SDD-005, SDD-010  

---

## 1. วัตถุประสงค์ (Purpose)

เอกสารฉบับนี้อธิบายตรรกะและอัลกอริทึมการทำงานของ **Python Consensus & Pronoun Engine** ซึ่งทำหน้าที่เป็นสะพานเชื่อมระหว่างผลการวิเคราะห์พารามิเตอร์เชิงนามธรรมจาก LLM และการสร้างโปรไฟล์ตัวละครที่สมบูรณ์พร้อมสรรพนามภาษาไทยที่คงที่ตลอดทั้งโปรเจกต์

---

## 2. สถาปัตยกรรมการประมวลผล (Processing Architecture)

ระบบประกอบด้วย 2 โมดูลหลักที่ทำงานเรียงลำดับกันในภาษา Python ล้วน (Pure Python, Zero LLM Calls):

```
+-----------------------------------------------------------+
| 1. Parameter Consensus Aggregator                         |
|    - รวบรวม Delta จาก Chunk Output ทั้งหมด               |
|    - คำนวณ Trait Frequency & Weighted Score              |
|    - สรุป Majority Vote ของ 4D Relationship รายคู่       |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
| 2. Deterministic Taxonomy Pronoun Resolver                |
|    - อ่าน Taxonomy v3.5 Rules & Pronoun Matrix            |
|    - คำนวณ base_speech_style จาก Core Identity & Traits   |
|    - คำนวณ pairwise speech_style (สรรพนาม 1, 2, 3)        |
|    - บันทึก Atomic Write ลง data/tlas/profiles/*.json      |
+-----------------------------------------------------------+
```

---

## 3. ขั้นตอนที่ 1: การหาค่าเฉลี่ยทางสถิติ (Statistical Parameter Consensus)

### 3.1 การรวบรวม Personality, Habits, และ Values
สำหรับตัวละคร $C$ จาก $N$ Chunks ที่ตัวละครนั้นปรากฏ:
1. **Accumulated Weighted Score:**
   $$\text{Score}(\text{Tag}) = \sum_{i=1}^{M} \text{Weight}_i(\text{Tag})$$
2. **Normalized Average Weight:**
   $$\overline{\text{Weight}}(\text{Tag}) = \text{round}\left(\frac{\text{Score}(\text{Tag})}{\text{Frequency}(\text{Tag})}\right)$$
3. **Selection Threshold:**
   คัดเลือกเฉพาะ Tag ที่มี Frequency สูงสุด และตัด Tag แปลกแยก (Noise) ที่มีคะแนนต่ำกว่า Threshold กำหนด

### 3.2 การรวบรวมความสัมพันธ์แบบทิศทางคู่ (Directed Pairwise Relationship Consensus)
สำหรับคู่ความสัมพันธ์ $A \to B$ (ตัวละคร $A$ มีต่อ $B$):
- **Roles:** รวม Array ของ `roles` แล้วหา Majority Vote (เช่น ถ้า 15 จาก 18 ครั้งบอกว่า `ROLE_FAM_SIBLING_YOUNGER` ให้ใช้ค่านั้น)
- **Affinity:** นับความถี่ของแท็ก `affinity` และเลือกแท็กที่มีสถิติสูงสุด (Mode)
- **Intimacy:** หา Majority Vote ของ `intimacy` (`INT_CONFIDANT`, `INT_FAMILIAR`, `INT_DISTANT`, `INT_ESTRANGED`)
- **Power Dynamic:** หา Majority Vote ของ `power_dynamic` (`DYN_DOMINANT`, `DYN_EQUAL`, `DYN_SUBMISSIVE`)

---

## 4. ขั้นตอนที่ 2: การแมปสรรพนามตาม Taxonomy (Deterministic Pronoun Resolution)

### 4.1 การกำหนด Base Speech Style
นำ Identity (เพศ, วัย) และ Core Traits มาประเมินเพื่อกำหนดสรรพนามพื้นฐาน:
- **Gender = MALE, Age = ADULT:**
  - สุภาพทั่วไป (`PER_SOC_POLITE`): `self` = "ผม", `target` = "คุณ", `third` = "เขา", `ending` = "ครับ", `formality` = 4
  - ห้าว/ตรงไปตรงมา (`PER_SOC_RUDE` หรือ `SPR_DIRECT` + `formality` ต่ำ): `self` = "ฉัน" / "ข้า", `target` = "นาย" / "แก", `third` = "มัน", `ending` = "", `formality` = 2
- **Gender = FEMALE, Age = ADULT:**
  - สุภาพทั่วไป: `self` = "ฉัน", `target` = "คุณ", `third` = "เธอ", `ending` = "ค่ะ", `formality` = 4
  - วัยรุ่น/เป็นกันเอง: `self` = "ฉัน", `target` = "เธอ", `third` = "เขา", `ending` = "จ้ะ", `formality` = 3
- **Age = CHILD / TEEN:**
  - หญิง: `self` = "หนู", `target` = "พี่/คุณ", `third` = "เขา/เธอ", `ending` = "ค่ะ", `formality` = 3

### 4.2 การกำหนด Pairwise Speech Style (สรรพนามบุรุษที่ 1, 2, 3 รายบุคคล)
คำนวณสรรพนามที่ $A$ ใช้กับ $B$ ตามลำดับชั้นของกฎ (5-Tier Calibrated Priority Rule Chain - อ้างอิง SDD-012):

1. **Rule Tier 1: Family Hierarchy (ลำดับขั้นครอบครัว/สายเลือด):**
   - **Child to Parent (`ROLE_FAM_DAUGHTER / CHILD` โดยผู้พูดเป็นเด็ก):**
     - `self_pronoun` = "หนู" (ถ้าหญิง) / "ผม" (ถ้าชาย)
     - `target_pronoun` = "คุณพ่อ" (ถ้าผู้ฟังเป็นชาย) / "คุณแม่" (ถ้าผู้ฟังเป็นหญิง)
     - `third_person_pronoun` = "คุณพ่อ" / "คุณแม่"
     - `ending_particle` = "ค่ะ" / "ครับ", `formality_level` = 3
   - **Younger to Older Sibling (`ROLE_FAM_SIBLING_YOUNGER` ผู้พูดเป็นน้อง):**
     - `self_pronoun` = "หนู" (ถ้าหญิง/เด็ก) / "ผม"
     - `target_pronoun` = "พี่" (หรือ "พี่" + ชื่อ $B$)
     - `third_person_pronoun` = "พี่"
     - `ending_particle` = "ค่ะ" / "ครับ", `formality_level` = 3
   - **Older to Younger Sibling (`ROLE_FAM_SIBLING_OLDER` ผู้พูดเป็นพี่):**
     - `self_pronoun` = "พี่"
     - `target_pronoun` = "หนู" (ถ้าผู้ฟังเป็นหญิง/เด็ก) / "น้อง"
     - `third_person_pronoun` = "น้อง"
     - `ending_particle` = "จ้ะ" / "ครับ", `formality_level` = 2

2. **Rule Tier 2: Romance & Marriage (คู่รักและคนสนิทเสน่หา):**
   - หาก $A \to B$ มี `ROLE_ROM_PARTNER` หรือ `ROLE_ROM_LOVER`:
     - ผู้ชายคุยกับผู้หญิง: `self` = "ผม" (หรือ "ฉัน"), `target` = "คุณ" (หรือ "เธอ"), `third` = "เธอ", `ending` = "ครับ", `formality_level` = 3
     - ผู้หญิงคุยกับผู้ชาย: `self` = "ฉัน", `target` = "คุณ" (หรือ "นาย"), `third` = "เขา", `ending` = "ค่ะ", `formality_level` = 3

3. **Rule Tier 3: Authority & Hierarchy (ลำดับอำนาจและตำแหน่งงาน):**
   - เจ้านายคุยกับลูกน้อง (`ROLE_WORK_BOSS` หรือ `DYN_DOMINANT` + `INT_DISTANT`):
     - `self_pronoun` = "ฉัน", `target_pronoun` = "เธอ" (ถ้าผู้ฟังเป็นหญิง) / "นาย" (ถ้าผู้ฟังเป็นชาย), `third_person_pronoun` = "เขา", `ending_particle` = ""
   - ลูกน้องคุยกับเจ้านาย (`ROLE_WORK_SUBORDINATE` หรือ `DYN_SUBMISSIVE`):
     - `self_pronoun` = "ผม/ดิฉัน", `target_pronoun` = "คุณ / ท่าน", `third_person_pronoun` = "ท่าน", `ending_particle` = "ครับ/ค่ะ", `formality_level` = 4

4. **Rule Tier 4: Peer & Social Relationships (เพื่อนและคนรู้จัก - Sociolinguistically Refined):**
   - **4.1 Close Peer (`ROLE_SOC_PEER` + `INT_CONFIDANT / AFF_FOND` และอยู่ในวัยเดียวกัน):**
     - `self_pronoun` = "เรา" (ถ้าชาย) / "ฉัน" (ถ้าหญิง), `target_pronoun` = "เธอ" (ถ้าหญิง) / "นาย" (ถ้าชาย), `third_person_pronoun` = "เขา", `ending_particle` = "", `formality_level` = 3
   - **4.2 Strained / Rival Peer (`ROLE_SOC_PEER` + `AFF_HOSTILE / AFF_CONFLICTED`):**
     - ชายคุยกับหญิง: `self` = "ฉัน", `target` = "เธอ", `third` = "หล่อน", `ending` = "วะ", `formality_level` = 2
     - หญิงคุยกับชาย: `self` = "ฉัน", `target` = "นาย", `third` = "หมอนั่น", `ending` = "ยะ", `formality_level` = 2
   - **4.3 Polite / General Peer (`ROLE_SOC_PEER` + `AFF_NEUTRAL` คนรู้จักทั่วไป - Thai Baseline):**
     - `self_pronoun` = "ผม" (ถ้าชาย) / "ฉัน" (ถ้าหญิง), `target_pronoun` = "คุณ", `third_person_pronoun` = "เขา", `ending_particle` = "ครับ/ค่ะ", `formality_level` = 4

5. **Rule Tier 5: Demographic & Base Speech Style Fallback:**
   - หากไม่เข้าเกณฑ์ข้างต้น ให้ใช้ค่ามาตรฐานจาก `base_speech_style` ของตัวละคร

---

## 5. การบันทึกข้อมูลแบบ Atomic และการสนับสนุน Manual Override

1. **Atomic Write Protection:**
   การบันทึกไฟล์ Profile ทุกครั้งจะต้องเขียนลงไฟล์ชั่วคราว (`.tmp`) ก่อน แล้วใช้ `os.replace()` เพื่อป้องกันไฟล์เสียหายกรณีระบบขัดข้อง
2. **Separation of Concerns (Profile vs Translator Guidance):**
   - ใน Character Profile บันทึกเฉพาะสรรพนามสามัญ (I, you, he, she, etc.)
   - ส่วนคำเรียกเฉพาะและคำแสดงความผูกพัน (Specific Vocatives: Papa, Mama, Dear, Honey) ให้ Translator Agent แปลตามรูปศัพท์และบริบทธรรมชาติ (SDD-012)
3. **Centralized Pronoun Matrix Export:**
   Engine จะทำการ Export สรุปตารางความสัมพันธ์และสรรพนามทั้งหมดของทั้งโปรเจกต์ออกมาเป็นไฟล์ `data/tlas/global_pronoun_matrix.json` เพื่อให้มนุษย์ (Localizer) สามารถเปิดดู ตรวจสอบ และแก้ไข (Manual Override) ก่อนที่ระบบแปลจริงจะดึงข้อมูลไปใช้
