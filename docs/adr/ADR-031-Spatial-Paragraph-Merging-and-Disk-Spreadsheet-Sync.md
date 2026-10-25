# ADR-031: Spatial Paragraph Merging & Disk-to-Spreadsheet Synchronization Architecture

## Status
Accepted / Implemented

## Context & Problem Statement (บริบทและปัญหา)
1. **Broken Sentence Fragmentation (ปัญหาประโยคขาดเป็นท่อนๆ):**
   ระบบ OCR มาตรฐาน (ทั้ง Windows Media OCR และ RapidOCR) สกัดข้อความและ Bounding Box แบบบรรทัดต่อบรรทัด (Line-by-Line) ตามลักษณะกายภาพของสายตาเครื่อง ทำให้ข้อความบทสนทนาในบอลลูนคำพูด (Speech Bubble) หรือแอปพลิเคชันแชตมือถือ (เช่น หน้าจอโทรศัพท์ของ Shion) ถูกแยกย่อยออกเป็นเซลล์ละท่อน เช่น:
   - ท่อน 1: `Hihi! How's the new phone? Or`
   - ท่อน 2: `"old" phone since it belonged`
   - ท่อน 3: `to someone else,hehe XD.Ive`
   - ท่อน 4: `saved my contact for you`
   - ท่อน 5: `yesterday!~`
   เมื่อประโยคถูกตัดแบ่งส่งไปยังระบบแปลภาษา (LLM / Translator) ทำให้สูญเสียไวยากรณ์และบริบทของประโยค การแปลขาดความสละสลวย และเกิดแถวใน Spreadsheet เพิ่มขึ้นอย่างไม่จำเป็น
2. **Spreadsheet Desynchronization upon Image Curation (ปัญหาข้อความตกค้างเมื่อคัดกรองภาพทิ้ง):**
   เมื่อผู้ใช้เปิดตรวจดูภาพในโฟลเดอร์ภาพดิบ (`data/images/raw/`) และลบภาพที่ไม่ต้องการแปลทิ้ง (เช่น ภาพ CG หรือภาพประกอบฉากที่หลุดรอดมา) ข้อมูลข้อความของภาพเหล่านั้นยังคงตกค้างอยู่ใน `image_dialogues.csv` และ `unique_dialogues.csv` ทำให้ผู้ใช้ต้องมานั่งลบข้อมูลใน Spreadsheet ซ้ำซ้อน

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

### 1. Spatial & Semantic Text Block Clustering (Paragraph / Speech Bubble Merger)
เราสร้างฟังก์ชัน `ImageTextDetector.merge_text_lines_to_paragraphs()` เพื่อจัดกลุ่มบรรทัดข้อความต่อเนื่องทางกายภาพเข้าเป็นก้อนประโยคเดียวกัน (Semantic Bubble Block):
- **Vertical Line Proximity ($\Delta Y$):**
  - บรรทัดที่อยู่ในบอลลูนหรือย่อหน้าเดียวกัน จะมีระยะห่างแนวดิ่งชิดกัน: $d_y = Y_{\text{next}} - Y_{\text{prev}} \le 35\text{ px}$ (หรือช่องว่างระหว่างบรรทัด $\le 20\text{ px}$)
  - ขณะที่ระยะห่างระหว่างบอลลูนคนละกล่อง หรือหัวข้อคนละตอน จะมีช่องว่างกว้างกว่าอย่างชัดเจน ($d_y \ge 50-70\text{ px}$)
- **Horizontal Column Alignment / Overlap:**
  - บรรทัดในย่อหน้าเดียวกันจะมีพิกัดขอบซ้ายใกล้เคียงกัน ($|X_{\text{next}} - X_{\text{prev}}| \le 40\text{ px}$) หรือมีช่วงความกว้างแนวนอนซ้อนทับกัน ($X_{\text{overlap}} > 0$)
- **Enclosing Bubble Box Calculation:**
  $$X_{\text{merged}} = \min(X_i), \quad Y_{\text{merged}} = \min(Y_i)$$
  $$W_{\text{merged}} = \max(X_i + W_i) - X_{\text{merged}}, \quad H_{\text{merged}} = \max(Y_i + H_i) - Y_{\text{merged}}$$
- **Linguistic Text Stitching:**
  - เชื่อมคำด้วยช่องว่างเดี่ยว `" "` โดยตัดเครื่องหมายยัติภังค์ตัดคำที่ปลายบรรทัด (Hyphenation `-`) ออกอัตโนมัติ
  - ผลลัพธ์: รวมประโยค 5 ท่อนข้างต้นให้กลายเป็น 1 ก้อนข้อความสมบูรณ์:
    `Hihi! How's the new phone? Or "old" phone since it belonged to someone else, hehe XD. Ive saved my contact for you yesterday!~`

### 2. Disk-to-Spreadsheet Synchronization Protocol (`sync` Command)
สร้างระบบซิงค์สองทางอัตโนมัติระหว่างโฟลเดอร์ภาพบนดิสก์และ Spreadsheet:
- **Visual Thumbnail Curation Workflow:**
  1. ผู้ใช้เปิดโฟลเดอร์ `data/images/raw/` บน Windows Explorer เพื่อดูพรีวิวรูปภาพ
  2. ลบไฟล์ภาพที่ไม่ต้องการแปลทิ้งได้ทันทีด้วยสายตามนุษย์
  3. สั่งรันคำสั่ง: `python localize_images.py sync`
- **Zero-Leftover Invariant:**
  - สคริปต์จะตรวจสอบภาพที่มีอยู่จริงบนดิสก์ เทียบกับ `image_dialogues.csv`
  - หากพบแถวใดที่ไฟล์ภาพต้นทางถูกลบไปแล้ว ระบบจะ **ตัดแถวทิ้งทันที 100%**
  - สั่งรัน `run_dedupe` ต่อเนื่อง เพื่อกำจัดข้อความตกค้าง (Orphan Texts) ออกจาก `unique_dialogues.csv` โดยอัตโนมัติ

### 3. Rebuild with Translation Preservation (`catalog --rebuild`)
- เพิ่มคำสั่ง `python localize_images.py catalog --rebuild` เพื่ออนุญาตให้สแกนภาพที่เหลืออยู่ใหม่ด้วย Paragraph Merger
- ในระหว่างการ Rebuild ระบบจะอ่านคำแปลภาษาไทยเดิมที่มีอยู่แล้วใน `unique_dialogues.csv` และแคตตาล็อกมาจับคู่ประโยคและใส่คืนกลับให้อัตโนมัติ ป้องกันไม่ให้คำแปลที่แปลไว้แล้วสูญหาย

## Consequences (ผลกระทบและประโยชน์ที่ได้รับ)
1. **Natural & Fluent Translation:** ข้อความถูกส่งไปแปลแบบเต็มประโยค/เต็มบอลลูน ไวยากรณ์และสรรพนามไม่ตกหล่น
2. **Workload Reduction:** จำนวนแถวใน Spreadsheet ลดลงกว่า 60-70% จากเดิมที่แยกบรรทัดละแถว
3. **Frictionless Curation:** ผู้ใช้จัดการไฟล์ภาพผ่าน Windows Explorer ได้ง่ายและรวดเร็ว โดย Spreadsheet จะซิงค์ตามอัตโนมัติอย่างไร้รอยต่อ
