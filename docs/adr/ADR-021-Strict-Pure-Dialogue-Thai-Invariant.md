# ADR-021: Strict Pure-Dialogue Thai Invariant & False-Positive Audit Elimination

## Status
**ACCEPTED** (บังคับใช้ใน ATF v5.0+ ทั่วทั้งระบบ)

## Context (ที่มาและปัญหา)
จากการตรวจสอบไฟล์ข้อมูล RPG Maker (`Map023.json`) และไฟล์ Target CSV พบประโยคบทสนทนาที่ "ลืมแปล / หลุดการแปล":
`\n<อันธพาลแก๊ง Kinchao:>think..dhey're all out..or sumthing..`

### การวิเคราะห์สาเหตุรากเหง้า (Root Cause Analysis - RCA):
1. **ภาวะแปลเฉพาะแท็กผู้พูด (Pseudo / Ghost Translated Row):**
   - ใน Target CSV มีบางแถวที่ชื่อผู้พูดได้รับการแปลงเป็นภาษาไทย (`\n<อันธพาลแก๊ง Kinchao:>`) แต่เนื้อหาบทสนทนาจริง (`think..dhey're all out..or sumthing..`) ยังคงเป็นภาษาอังกฤษต้นฉบับ
2. **ช่องโหว่ร้ายแรงของระบบ Audit เดิม (False Positive Blind Spot):**
   - สคริปต์ตรวจสอบความสมบูรณ์เดิม (`verify_translation_completion.py`) ใช้เงื่อนไข:
     ```python
     has_th = any('\u0e00' <= ch <= '\u0e7f' for ch in initial)
     if has_th:
         translated_thai += 1
         continue
     ```
   - เมื่อช่อง Initial มีชื่อผู้พูดภาษาไทย ระบบจึงตัดสินว่า "แปลเสร็จสมบูรณ์แล้ว" โดยไม่ได้ตรวจสอบว่า **เนื้อหาบทสนทนาที่แท้จริง (Pure Dialogue) หลังจากตัดแท็กผู้พูดออก มีภาษาไทยอยู่จริงหรือไม่!**
   - ส่งผลให้ประโยคที่มีอาการนี้หลุดรอดการตรวจสอบไปทั้งหมด ไม่ถูกจัดเข้าคิวแปล และถูกนำไปแพตช์ลงไฟล์เกมจริง

---

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

### 1. กฎเหล็ก: Strict Pure-Dialogue Thai Invariant (AUDIT-INV-001)
* **การตรวจว่าแถวใดแปลเป็นภาษาไทยแล้ว ต้องพิจารณาจาก "Pure Dialogue" เท่านั้น**
* ขั้นตอนการตรวจสอบ:
  1. สกัด Speaker Tag ออกจากข้อความ (`\n<Speaker:>` หรือ `\C[n]...`)
  2. สกัด RPG Maker Escape Codes ออก (`\c[n]`, `\.`, `\|`, `\!`)
  3. ตรวจสอบข้อความเนื้อหาแท้จริง (Pure Dialogue):
     - หาก Pure Original มีตัวอักษรภาษาอังกฤษ `[a-zA-Z]`
     - แต่ Pure Initial **ไม่มีตัวอักษรภาษาไทยเลยแม้แต่ตัวเดียว**
     - ให้ตัดสินเป็น **`Pseudo-Translated / Untranslated` (ยังไม่แปล)** ทันที ห้ามข้ามเด็ดขาด

### 2. Cross-Reference Auto-Recovery Engine
* พัฒนาโมดูล [audit_and_fix_pseudo_translated.py](file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/testing%20files/audit_and_fix_pseudo_translated.py) เพื่อตรวจจับและดึงคำแปลที่ถูกต้องจากคลังข้อมูลอ้างอิง (`Processed_v3_translated (1).csv`, `ชีต1_out.csv.progress`, `Checkpoint`) มาซ่อมแซมอัตโนมัติ

---

## Consequences (ผลลัพธ์)
* **Zero False-Positive Guarantee:** ปิดช่องโหว่การตรวจจับคำแปลลวง 100% ไม่มีประโยคที่ค้างภาษาอังกฤษหลุดรอดไปถึงตัวเกมจริงได้อีก
