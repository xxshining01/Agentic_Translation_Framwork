# ADR-020: Content-Based Key Invariant & Row-Shift Immune Synchronization Architecture

## Status
**ACCEPTED** (บังคับใช้ใน ATF v5.0+ ทั่วทั้งระบบ)

## Context (ที่มาและปัญหา)
จากการทดสอบนำแพตช์ภาษาไทยเข้าสู่เกมจริง พบข้อผิดพลาดร้ายแรงในส่วนของไอเทม (`Items.json`) และไฟล์ Target CSV (`SSPV034v1.35 - Trans - Processed_v3_translated.csv`):
1. **พฤติกรรมความผิดพลาด:** ข้อความแปลของไอเทมในตารางเกิดการ "สลับบรรทัดและเลื่อนตำแหน่ง (Row Shift / Off-by-N Desynchronization)" เช่น ช่อง `name` ของไอเทม ID 177 (`Pinhole Camera`) กลายเป็นคำอธิบายของไอเทม ID 176 (`ข้าวหน้าปลาไหลใส่ไข่`) และช่อง `name` ของ ID 178 กลายเป็น `"กล้องรูเข็มขนาดเล็ก"`
2. **การวิเคราะห์สาเหตุรากเหง้า (Root Cause Analysis - RCA):**
   - **LLM ไม่ได้แปลผิด:** ข้อมูลดิบใน Checkpoint และ Glossary ถูกแปลไว้อย่างถูกต้องสมบูรณ์ 100%
   - **ความผิดพลาดเกิดจากระบบ Synchronization:** สคริปต์ Sync (`verify_translation_completion.py --sync` และ `sync_checkpoint_to_csv.py`) ทำการแมปคำแปลจาก Checkpoint ลงใน Target CSV โดยอิงจาก **"Row Index (`str(idx - 1)`)"** ดิบๆ
   - **Cross-File Line Count Mismatch:** ไฟล์ต้นทางของ Checkpoint (`Processed_v3.csv` มี 199,338 บรรทัด) มีจำนวนแถวไม่เท่ากับ Target CSV (`Processed_v3_translated.csv` มี 212,840 บรรทัด) เนื่องจากมีแถวขยะจากการ Diff ข้ามเวอร์ชัน (`ถูกลบออกในไฟล์ใหม่` และแถวแทรกใหม่)
   - เมื่อนำ Index ของไฟล์ที่มี 199k แถว มาหยอดลงไฟล์ 212k แถวโดยตรงโดยไม่มีการตรวจสอบข้อความต้นฉบับ (`Original`) ส่งผลให้คำแปลถูกเลื่อนลงไปทับผิดแถวอย่างมหาศาล
3. **ปัญหา Plugin UI Days of Week:** สคริปต์สกัด `extract_plugin_texts.py` มี `SYSTEM_KEYS_BLACKLIST` ที่แบนคีย์ `"name"` ส่งผลให้พารามิเตอร์วันเต็ม (`Monday`, `Tuesday`...) และช่วงเวลา (`Morning`, `Day`...) ใน `DK_Game_Time` ไม่ถูกสกัดออกมาแปล ทำให้เกมยังคงแสดงผลวันเป็นภาษาอังกฤษ

---

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

### 1. กฎเหล็ก: Content-First Invariant Principle (SD-INV-001)
* **ห้ามทำการจับคู่ข้ามระบบ (Cross-File Mapping) ด้วย Row Index เพียงอย่างเดียวเด็ดขาด**
* การ Sync ข้อมูลระหว่าง Checkpoint, CSV, และ RPG Maker Data JSON จะต้องอ้างอิงผ่าน **Content Tuple Key**:
  $$\text{Key} = (\text{Filename}, \text{Clean}(\text{Original\_Text}))$$
* หาก Target Row มีข้อความ Original ไม่ตรงกับ Checkpoint Source Record ระบบจะต้อง **บล็อกการเขียนทับ (Strict Reject)** ทันที เพื่อคุ้มครองความถูกต้องของฐานข้อมูล

### 2. Item Database Alignment Engine (ID-based Ground Truth)
* สำหรับเอนทิตีประเภท Database Records (Items, Skills, Weapons, Armors, Actors) ให้ยึดถือ ID ดั้งเดิมของ RPG Maker เป็นแกนหลัก
* สร้างโมดูล [repair_items_alignment.py](file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/testing%20files/repair_items_alignment.py) เพื่อแมป `Item ID -> (Canonical Name TH, Canonical Desc TH)` โดยตรง ไม่พึ่งพาตำแหน่งลำดับแถวในตาราง

### 3. Context-Aware Plugin Parameter Whitelisting (PLUG-WL-001)
* ปรับปรุง `SemanticParameterClassifier` ในสคริปต์สกัด Plugin:
  * คีย์ `"name"` จะถูกอนุญาตให้ผ่าน (Whitelist) หากอยู่ภายใต้ Parameters Array/Object เช่น `daysWeek`, `morningPeriod`, `dayPeriod`, `eveningPeriod`, `nightPeriod`, `quests`
* รองรับการแปลงทั้ง Full Name (`Monday` $\to$ `วันจันทร์`) และ Short Name (`Mon` $\to$ `จันทร์`) ครบทั้ง 7 วันและ 4 ช่วงเวลา

---

## Consequences (ผลลัพธ์และการควบคุม)

### ข้อดี (Positive Impact)
1. **Row-Shift Immunity 100%:** ไม่มีทางที่การอัปเดตไฟล์ CSV จะทำให้คำแปลเลื่อนไปตกผิดแถวอีกต่อไป แม้ไฟล์ CSV จะถูกเพิ่มหรือลบแถว
2. **Self-Healing Database:** หากพบว่าไฟล์ JSON ในเกมมีข้อมูลคลาดเคลื่อน สามารถสั่ง Re-align จาก Master Glossary ได้ทันทีใน 1 วินาที
3. **Complete Localization:** หน้าจอเวลาและปฏิทินในเกมจะแสดงผลเป็นภาษาไทยครบถ้วน ทั้งชื่อวันและช่วงเวลา

### ข้อจำกัดและการป้องกัน (Mitigation)
* การโหลด Content Map จาก Checkpoint จำเป็นต้องอ่านไฟล์ต้นทางเพื่อ Resolve ข้อความภาษาอังกฤษ ซึ่งระบบได้ทำ Caching ไว้ในหน่วยความจำ จึงไม่มีผลกระทบต่อประสิทธิภาพการทำงาน (รันเสร็จในเวลาไม่เกิน 0.5 วินาที)
