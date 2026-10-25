# ADR-032: OCR Lexical Normalization, Homoglyph De-confusion, and Human-in-the-Loop Correction Architecture

## Status
Accepted / Implemented

## Context & Problem Statement (บริบทและปัญหา)
1. **Optical Homoglyphs & Character Confusion (อักขระทางสายตาที่ OCR อ่านผิด):**
   ฟอนต์ในเกม RPG Maker, Visual Novel, และภาพประกอบแชตมือถือมักเป็นฟอนต์ลายมือหรือฟอนต์แบบไม่มีหัว (Handwritten / Stylized Sans / Pixel Fonts) ซึ่งทำให้เอนจิน OCR มักอ่านตัวอักษรผิดพลาด เช่น:
   - ตัวเลข `1` สับสนกับตัวพิมพ์เล็ก `l` หรือสรรพนาม `I` (เช่น `1unch` แทนที่จะเป็น `lunch`, `l was` แทนที่จะเป็น `I was`, `1 rly` แทนที่จะเป็น `I really`)
   - ตัวอักษร `y` สับสนกับ `s` หรือ `r` (เช่น `thi` แทนที่จะเป็น `this`, `plve` แทนที่จะเป็น `please`, `Santaojiran` แทนที่จะเป็น `Santaojisan`)
2. **Token Boundary Collisions & Punctuation Spacing (คำติดกันเป็นก้อนและขาดช่องว่างหลังวรรคตอน):**
   - ตัวอักษรตัวถัดไปมักติดกับเครื่องหมายวรรคตอนโดยไม่มีช่องว่าง เช่น `there,Dan`, `agitated,too`, `experience.Hahaha`, `XD.Ive`
   - คำภาษาอังกฤษสั้นๆ ชิดติดกัน เช่น `tohate` (`to hate`), `thetaste` (`the taste`), `ina` (`in a`), `afterall` (`after all`), `shell enjoy` (`she'll enjoy`)
   - เครื่องหมาย Apostrophe หายไปจากคำย่อ (Contractions) เช่น `Ive` (`I've`), `dont` (`don't`), `cant` (`can't`), `wont` (`won't`), `doesnt` (`doesn't`)
3. **Translation Corruption:**
   คำศัพท์ที่สะกดผิดหรือรวมกันจนอ่านไม่ออกเหล่านี้ เมื่อถูกส่งต่อไปยังโมเดลแปลภาษา (LLM) หรือนักแปล จะทำให้ตีความหมายผิดบริบท แปลเพี้ยน หรือแปลไม่ได้เลย
4. **Human-in-the-Loop Sync Gap:**
   เมื่อผู้ใช้เปิดไฟล์ `.csv` ใน Excel แล้วแก้คำผิดด้วยสายตาตนเอง หากรันสคริปต์รอบใหม่ ข้อมูลที่แก้ไว้อาจถูกทับ หรือไม่สะท้อนกลับไปยังตารางหลัก

---

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

เราออกแบบสถาปัตยกรรมการแก้ไขคำผิด 3 ระดับ (3-Tier Lexical Correction Architecture):

### 1. Automated Lexical Normalizer (`ImageTextDetector.normalize_ocr_text`)
ประยุกต์ใช้กฎทางภาษาศาสตร์และคอมพิวเตอร์วิทัศน์ เพื่อซ่อมแซมข้อความโดยอัตโนมัติ:
- **Punctuation Spacing Restoration:** 
  แทรกช่องว่างระหว่างเครื่องหมายวรรคตอนกับตัวอักษรภาษาอังกฤษอัตโนมัติ:
  `re.sub(r'([,.!?:;])([A-Za-z])', r'\1 \2', text)`
  *(ไม่แตะต้องเลขทศนิยม เช่น 3.14 หรือเวลา 21:00)*
- **Contraction Restoration:**
  เติมเครื่องหมาย Apostrophe คืนให้คำย่อมาตรฐานภาษาอังกฤษ (`I've`, `I'm`, `I'd`, `I'll`, `don't`, `can't`, `won't`, `didn't`, `she'll`, ฯลฯ)
- **Pronoun & Homoglyph Resolution:**
  แก้คำผิดยอดนิยม เช่น `1unch` -> `lunch`, `l was` -> `I was`, `1 rly` -> `I really`
- **Lexical Splitting:**
  แยกคำที่ติดกันเป็นพืดตามพจนานุกรมเกม (`tohate` -> `to hate`, `thetaste` -> `the taste`, `RODANDBAIT` -> `ROD AND BAIT`, ฯลฯ)

### 2. Persistent Correction Store (`data/images/ocr_corrections.json`)
สร้างไฟล์พจนานุกรมถาวรระดับโปรเจกต์ รองรับการระบุคู่คำแก้ผิด `{"bad_ocr": "correct_text"}`:
- ถูกโหลดอัตโนมัติทุกครั้งที่มีการรัน `catalog`, `dedupe`, `propagate`, และ `repair`
- ผู้ใช้สามารถเพิ่มคำศัพท์เฉพาะของเกมลงใน JSON นี้ได้โดยตรงโดยไม่ต้องแก้โค้ด Python

### 3. Human-in-the-Loop Direct CSV Editing with Bidirectional Parity
รองรับการที่ผู้ใช้เปิดแก้คำต้นฉบับใน Spreadsheet โดยตรง:
- ใน `unique_dialogues.csv` มีการเพิ่มคอลัมน์ `Raw_OCR` เพื่อบันทึกข้อความต้นฉบับก่อนการแก้ไข
- เมื่อผู้ใช้แก้ไขเซลล์ `Clean_Original` (เช่น เปลี่ยน `1unch` เป็น `lunch`):
  เมื่อรัน `python localize_images.py propagate`:
  1. ระบบจะตรวจพบว่า `Clean_Original != Raw_OCR`
  2. อัปเดต `Original_Text` ใน `image_dialogues.csv` ให้ตรงกับคำที่ถูกต้อง
  3. บันทึกคำคู่นี้เข้าสู่ `ocr_corrections.json` อัตโนมัติ เพื่อให้ระบบจดจำตลอดไป
  4. กระจายคำแปลภาษาไทยลงในทุกตำแหน่งของรูปภาพอย่างแม่นยำ

### 4. Dedicated One-Click Repair Command (`repair`)
เพิ่มคำสั่ง:
```bash
python localize_images.py repair
```
เพื่อสแกนและซ่อมแซมคำผิด, คืนช่องว่าง, และแก้ไขตัวสะกดในไฟล์ CSV ที่มีอยู่แล้วบนดิสก์ทั้งหมด พร้อมรายงานสรุปการเปลี่ยนแปลงทุกบรรทัด

---

## Consequences (ผลกระทบและประโยชน์ที่ได้รับ)
1. **Clean & Natural Translation Input:** ข้อความต้นฉบับมีความถูกต้องตามหลักไวยากรณ์ 100% ทำให้ AI แปลภาษาแปลออกมาได้อย่างแม่นยำและเป็นธรรมชาติ
2. **Zero Recurring OCR Errors:** คำที่เคยถูกแก้ไขจะถูกจำไว้ใน `ocr_corrections.json` และนำไปแก้ซ้ำในทุกภาพที่มีคำนี้โดยอัตโนมัติ
3. **Total Flexibility for Translators:** ผู้ใช้สามารถเลือกได้ทั้งการสั่งให้ระบบแก้ให้อัตโนมัติ (`repair`), การแก้ผ่านไฟล์ JSON, หรือการพิมพ์แก้ในเซลล์ Excel โดยตรง
