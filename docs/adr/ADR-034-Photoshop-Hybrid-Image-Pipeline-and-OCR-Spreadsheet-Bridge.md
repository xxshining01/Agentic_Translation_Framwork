# ADR-034: Photoshop Hybrid Image Pipeline and High-Throughput OCR-Spreadsheet Bridge Architecture

## Status
Accepted / Implemented

## Context & Problem Statement (บริบทและปัญหา)

ในการพัฒนาโมดูลแปลภาพเกมของ ATF มีความพยายามสร้างระบบเรนเดอร์ตัวอักษรภาษาไทยลงบนภาพแบบอัตโนมัติ 100% (Fully Automated Pillow Rendering Engine) ผ่านการคำนวณ Inpainting ลบข้อความเดิม และวาดตัวอักษรไทยลงไปแทนที่

อย่างไรก็ตาม จากการทดสอบใช้งานจริงกับไฟล์ภาพเกมประเภทต่างๆ (Game CG, Tutorial Guides, Phone Chat Overlays, Stylized Titles, Status HUD) พบขีดจำกัดทางสถาปัตยกรรมที่สำคัญ:
1. **Artistic Variety & Layout Entropy (ความหลากหลายเชิงศิลป์ของกราฟิกเกม):**
   - รูปภาพในเกมไม่ได้มีเลย์เอาต์ที่เป็นมาตรฐานเดียวกันเหมือนหน้าเอกสาร PDF หรือกระดาษ A4
   - บางภาพมีข้อความวางเอียงตามมุมมอง Isometric, บางภาพมีแสงเงาและเกรเดียนท์ที่ซับซ้อน, บางภาพเป็นหน้าต่างกึ่งโปร่งใสซ้อนทับภาพถ่าย 3D
   - การพยายามใช้โค้ดทางคณิตศาสตร์คำนวณสี ตัดคำ และปรับสเกลฟอนต์อัตโนมัติ มีโอกาสเกิดความผิดพลาดทางความสวยงาม (Aesthetic Degradation) หรือเกิดข้อผิดพลาดขอบเขตพิกเซล (Boundary Value Errors เช่น `y1 must be greater than or equal to y0`)
2. **Human Translation & Artistic Quality Expectation:**
   - ผู้แปลและผู้พัฒนาเกมต้องการคุณภาพงานแปลภาพที่สวยงาม คมชัด วางตำแหน่งฟอนต์ได้ตามใจชอบ และกลมกลืนกับงานศิลป์ 100% ซึ่งโปรแกรมตกแต่งภาพระดับมืออาชีพอย่าง **Adobe Photoshop** มีเครื่องมือด้าน Type Tool, Layer Styles, Dropper, และ Masking ที่เหนือกว่าสคริปต์โค้ดอัตโนมัติอย่างมหาศาล
3. **Pain Points of Purely Manual Translation (ปัญหาของการทำ Photoshop มือ 100% โดยไม่มีระบบช่วย):**
   - หากต้องเปิดดูภาพในเกมทั้งหมดทีละภาพ (ซึ่งมักมีเป็นร้อยหรือเป็นพันภาพ) จะเสียเวลามากในการค้นหาว่าภาพไหนมีตัวหนังสือภาษาอังกฤษอยู่บ้าง
   - ต้องมานั่งพิมพ์ตัวหนังสือภาษาอังกฤษจากภาพด้วยมือทีละประโยคเพื่อแปล
   - ภาพหลายภาพมีบทสนทนาหรือคำอธิบายที่ซ้ำกัน (เช่น ภาพแชตมือถือหลายเฟรม) การพิมพ์แปลซ้ำๆ ซากๆ เสียเวลาและอาจใช้คำแปลไม่ตรงกัน
   - เมื่อทำภาพใน Photoshop เสร็จแล้ว ต้องมานั่งแปลงไฟล์และเข้ารหัสกลับเป็นไฟล์ของเกม (`.rpgmvp`) ทีละไฟล์ด้วยตนเอง

---

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

เราตัดสินใจปรับเปลี่ยนทิศทางสถาปัตยกรรม (Architectural Pivot) จากการพยายามเรนเดอร์ภาพด้วยโค้ดเพียวๆ มาเป็น **"Photoshop Hybrid Image Pipeline & OCR-Spreadsheet Bridge"** ซึ่งเป็นการแบ่งหน้าที่ระหว่าง "AI Automation" กับ "Human Artistry" อย่างลงตัวที่สุด:

```
+---------------------------------------------------------------------------------------+
|                    ATF PHOTOSHOP HYBRID IMAGE LOCALIZATION PIPELINE                   |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [STEP 1: TEXT-BEARING IMAGE SCANNER & NOISE PURGE]                                   |
|  - Decrypt encrypted assets (.rpgmvp -> .png)                                         |
|  - Deep Learning Text Classifier separates text-bearing images from clean CGs/Sprites |
|  - Output: Only text-bearing images stored in raw/                                    |
|                                                                                       |
|                                  |                                                    |
|                                  v                                                    |
|                                                                                       |
|  [STEP 2: OCR TEXT EXTRACTION, LEXICAL REPAIR & UNIQUE DEDUPLICATION]                 |
|  - High-precision Deep Learning OCR extracts English sentences                        |
|  - Automated Lexical & Homoglyph Normalizer repairs OCR misrecognitions               |
|  - Deduplication Engine extracts unique sentences into unique_dialogues.csv           |
|  - Translator translates once -> Propagates to all duplicate frames automatically     |
|  - Result: Excel/Spreadsheet ready for Copy-Pasting text directly into Photoshop      |
|                                                                                       |
|                                  |                                                    |
|                                  v                                                    |
|                                                                                       |
|  [STEP 3: HUMAN ARTISTRY IN PHOTOSHOP]                                                |
|  - User opens raw/ images in Adobe Photoshop                                          |
|  - Copies Thai translations from unique_dialogues.csv into Photoshop Text Layers      |
|  - Styles typography, dropshadows, and colors with 100% artistic freedom              |
|  - Saves finalized Thai PNGs into translated/ folder                                  |
|                                                                                       |
|                                  |                                                    |
|                                  v                                                    |
|                                                                                       |
|  [STEP 4: AUTOMATED IN-GAME ENCRYPTION & DEPLOYMENT]                                  |
|  - System takes all .png files from translated/                                       |
|  - Re-encrypts with game's System.json encryption key (.png -> .rpgmvp)               |
|  - Automatically backs up originals and injects localized images into game            |
+---------------------------------------------------------------------------------------+
```

### หน้าที่หลัก 3 ประการของระบบ ATF (The 3 Core Pillars):

#### 1. สแกนและคัดกรองเฉพาะภาพที่มี Text (Text-Bearing Image Scanner & Noise Purge):
- ถอดรหัสไฟล์ภาพ `.rpgmvp` ออกมาเป็น `.png`
- รัน Deep Learning Classifier วิเคราะห์ภาพทั้งเกม และคัดกรองแยกเฉพาะภาพที่มีข้อความ (Tutorials, Phone Messages, UI, Menus) ออกมาจากภาพที่เป็น CG กราฟิก, Sprite ตัวละคร, หรือ Texture พื้นหลัง
- ผู้ใช้ไม่ต้องเสียเวลาไล่เปิดหาภาพที่มีตัวอักษรเองจากภาพนับร้อยนับพันภาพ

#### 2. แกะ Text, ซ่อมแซมคำผิด, และสร้าง Spreadsheet พร้อมระบบ Unique (Text Extraction & Translation Bridge):
- สกัดตัวอักษรจากภาพด้วย Deep Learning OCR พร้อมรวมข้อความที่เป็นประโยคเดียวกัน (Spatial Paragraph Merger)
- ซ่อมแซมคำผิด Homoglyphs และช่องว่างวรรคตอนอัตโนมัติ (`repair`)
- ยุบรวมข้อความที่ซ้ำกันออกมาเป็น `unique_dialogues.csv` (`dedupe`):
  - ผู้ใช้สามารถ Copy ข้อความภาษาอังกฤษไปแปล หรือพิมพ์คำแปลภาษาไทยลงใน Spreadsheet ได้ทันที
  - แปลเพียงแค่ 1 ครั้งต่อ 1 ข้อความ แม้ข้อความนั้นจะปรากฏในภาพ 20-30 ภาพก็ตาม
  - คำสั่ง `propagate` จะกระจายคำแปลภาษาไทยกลับไปยังทุกภาพที่ซ้ำกันโดยอัตโนมัติ

#### 3. อัดภาพภาษาไทยที่แต่งเสร็จแล้วกลับเข้าสู่ตัวเกมจริง (In-Game Injection / Encryption):
- เมื่อผู้ใช้ตกแต่งภาพใน Photoshop เสร็จแล้ว และบันทึกไฟล์เป็นชื่อเดิมแบบ `.png` วางไว้ในโฟลเดอร์ `translated/`
- รันคำสั่ง `encrypt` เพียงคำสั่งเดียว: ระบบจะดึง Encryption Key จาก `System.json` ของตัวเกม เข้ารหัสภาพ `.png` ทั้งหมดกลับเป็น `.rpgmvp` และส่งตรงเข้าโฟลเดอร์ของเกม (`www/img/pictures/`) พร้อมสำรองไฟล์เดิมไว้ให้อัตโนมัติ

---

## Consequences & Benefits (ผลลัพธ์และข้อดี)

1. **100% Visual Excellence:** ผลงานภาพภาษาไทยมีความสวยงามประณีตระดับมืออาชีพ เพราะผ่านการจัดวาง Typography และ Layer Styles ใน Photoshop โดยตรง
2. **Massive Time Savings:** ประหยัดเวลาทำงานลงกว่า 80-90%:
   - ไม่ต้องค้นหาภาพเอง (ระบบกรองภาพที่มี Text ให้)
   - ไม่ต้องพิมพ์ข้อความภาษาอังกฤษเอง (ระบบ OCR แกะ Text ใส่ Spreadsheet ให้)
   - ไม่ต้องแปลข้อความซ้ำซาก (ระบบ Unique จัดการให้แปลรอบเดียว)
   - ไม่ต้องเข้ารหัสไฟล์เอง (ระบบ Injector อัดเข้าเกมให้อัตโนมัติ)
3. **Rock-Solid Stability:** หมดปัญหาเรื่อง Script Error, Font Overflow, หรือ Inpainting หลุดขอบ เพราะระบบโค้ดทำหน้าที่ในจุดที่แข็งแกร่งที่สุด (Automation, Data Processing, Encryption) และปล่อยงานจัดวางศิลป์ให้มนุษย์ทำในเครื่องมือที่เหมาะสมที่สุด
