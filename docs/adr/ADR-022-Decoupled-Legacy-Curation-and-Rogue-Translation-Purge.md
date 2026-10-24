# ADR-022: Decoupled Legacy Curation & Rogue Translation Purge Subsystem

## Status
Accepted

## Context
ในการดำเนินงานแปลเกมด้วย Agentic Translation Framework (ATF) ซึ่งมีการรับมรดกข้อมูลการแปลตั้งต้นมาจากผู้แปลมนุษย์หรือสเปรดชีตเดิมในอดีต (`th_legacy`) จากการสืบสวนและทำ Human Review พบความผิดปกติเชิงโครงสร้างและการแปลที่คลาดเคลื่อนจากต้นฉบับอย่างรุนแรง (Rogue / Hallucinated Translations) หลายประการ เช่น:
1. **Silent / Pause Hallucination:** แถวที่บทสนทนาต้นฉบับภาษาอังกฤษ (Original) เป็นเพียงความเงียบ จุดไข่ปลา หรือรหัสควบคุมจังหวะ (เช่น `\n<Dan:>.....!` หรือ `\n<Shion:>.........\.\.\^`) แต่ใน `th_legacy` มีการยัดข้อความบทสนทนาขนาดยาวหลายบรรทัดเข้ามา
2. **Speaker Tag Collision / Character Desynchronization:** มีการคัดลอกบทพูดข้ามแถว จนทำให้แท็กผู้พูดในบทแปลขัดแย้งกับตัวละครในต้นฉบับ (เช่น ต้นฉบับคือ `<Dan:>` แต่บทแปลไทยกลับแสดงเป็น `<Shion:>`) ส่งผลให้กล่องข้อความในเกมแสดงชื่อตัวละครผิดคนบนใบหน้าของตัวละครอื่น
3. **Consecutive Duplicate Hallucinations:** เกิดจากการคัดลอกบทแปลของแถวก่อนหน้ามาวางซ้ำในแถวถัดไป ทั้งที่ประโยคภาษาอังกฤษต้นฉบับเป็นคนละเรื่องกัน
4. **Decoupled Architecture Requirement:** การจัดการปัญหาเหล่านี้จะต้องไม่นำกฎเฉพาะกิจ (Ad-hoc hardcoded rules) ไปฝังลงใน ATF Core Translation Pipeline เพื่อรักษาหลักการ **Universal Framework Paradigm** ให้ตัวโครงข่ายแกนกลางคงความบริสุทธิ์และสามารถนำไปใช้กับเกม RPG Maker อื่นๆ ได้โดยไร้รอยต่อ

## Decision
เราตัดสินใจสร้าง **"Legacy Anomaly Curator & Purge Subsystem"** แยกส่วนออกมาเป็นอิสระ (Decoupled Layer) ตามขั้นตอนวิธีดังนี้:

### 1. Classification & Purge Rule Hierarchy
1. **Type 1: Silent/Pause Hallucination (Original ไร้คำพูด แต่คำแปลยัดบท):**
   * *เกณฑ์:* `Original` ไม่มีตัวอักษรภาษาอังกฤษ (เป็นเพียงสัญลักษณ์/จุด/รหัสควบคุม) แต่ `Initial` มีตัวอักษรภาษาไทยตั้งแต่ 3 ตัวขึ้นไป
   * *การแก้ไข:* **Reset to Original (`Initial = Original`)** คืนค่าความเงียบและจังหวะของเกมเดิมทันที โดยไม่ต้องส่งเข้าคิวแปล
2. **Type 2: Speaker Tag Collision (ผู้พูดไม่ตรงกันอย่างรุนแรง):**
   * *เกณฑ์:* แท็กผู้พูดใน `Original` ขัดแย้งกับแท็กใน `Initial` (โดยไม่ใช่ชื่อแปลไทยหรือ Alias ใน Glossary เช่น Dan vs Shion)
   * *การแก้ไข:*
     * หาก `Original` ไม่มีบทพูด -> Reset to Original
     * หาก `Original` มีบทพูดภาษาอังกฤษจริง -> **Purge to Original (`Initial = Original`)** และบรรจุเข้าสู่ Retranslation Queue เพื่อให้ LLM แปลใหม่ตามบริบทที่ถูกต้อง
3. **Type 3: Consecutive Duplicate Translations:**
   * *เกณฑ์:* ข้อความแปลใน `Initial` เหมือนกับแถวก่อนหน้าทุกตัวอักษร แต่ `Original` มีความแตกต่างกันอย่างมีนัยสำคัญ
   * *การแก้ไข:* Purge เพื่อรอส่งแปลใหม่
4. **Type 4: Retranslation Queue Generation:**
   * รวบรวมแถวที่ถูก Purge ทั้งหมด ผนวกเข้ากับแถวบทสนทนาภาษาอังกฤษแท้ที่ยังตกค้าง (Real Story Dialogue) แล้วส่งออกเป็นไฟล์โครงสร้าง JSON (`data/tlas/retranslation_queue.json`) เพื่อเตรียมป้อนเข้าสู่ ATF Translation Runner ต่อไป

### 2. State & Data Integrity Guarantees
* **Automated Pre-repair Backup:** ทุกครั้งที่มีการสั่งรันด้วยโหมด `--apply` ระบบจะต้องทำการคัดลอกไฟล์สำรองแบบ Timestamped Backup เสมอ (เช่น `.backup_legacy_purge_YYYYMMDD_HHMMSS.csv`) ก่อนการแตะต้องไฟล์ CSV จริง
* **Content-based Traceability:** รายการใน `retranslation_queue.json` จะระบุทั้ง `row_idx`, `file`, `line_id`, `speaker`, และ `reason` เพื่อให้สามารถตรวจสอบย้อนกลับ (Audit Trail) ได้อย่างโปร่งใส

## Consequences
* **ข้อดี (Positive):**
  1. ล้างไพ่บทแปลมั่วที่ยัดปากตัวละครในจังหวะเงียบได้อย่างเด็ดขาด 100% ทำให้จังหวะการเล่าเรื่องของเกมไม่เพี้ยน
  2. แก้ไขปัญหาชื่อตัวละครสลับขั้วในเกม
  3. สถาปัตยกรรม ATF Core ไม่ถูกปนเปื้อนด้วยกฎแก้บั๊กเฉพาะเกมของ `th_legacy`
  4. มี Queue ที่สะอาด ชัดเจน พร้อมสำหรับการนำไปแปลซ่อมและเก็บตกด้วยโมเดล LLM ในขั้นตอนต่อไป
* **ข้อจำกัด (Neutral):**
  * จำนวนแถวที่รอการแปล (Untranslated Queue) จะมีเพิ่มขึ้นเล็กน้อยจากรายการที่ถูก Purge ซึ่งถือเป็นเรื่องที่ถูกต้องเพื่อแลกกับความถูกต้องสมบูรณ์ของบทแปลเกม 100%
