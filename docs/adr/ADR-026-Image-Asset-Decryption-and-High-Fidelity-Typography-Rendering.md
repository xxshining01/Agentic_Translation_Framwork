# ADR-026: Image Asset Decryption and High-Fidelity Typography Rendering

## สถานะ (Status)
**ACCEPTED (ยอมรับและบรรจุเป็นมาตรฐานหลัก)**

## บริบทและความเป็นมา (Context & Problem Statement)
ในเกมประเภท RPG Maker (MV/MZ) และ Visual Novel ยุคใหม่ มีองค์ประกอบการเล่าเรื่องส่วนสำคัญที่ถูกแสดงผลในรูปแบบไฟล์ภาพ (Image-based Texts) แทนที่จะเป็นข้อความตัวอักษรธรรมดา เช่น:
1. หน้าจอการคุยโทรศัพท์มือถือ (Mobile Chat UI) ที่มีบทสนทนาโต้ตอบผ่าน Chat Bubbles
2. หน้าจอแชตไลฟ์สตรีมสด (Livestream Chat / Viewer Comments)
3. ป้ายกราฟิก UI, โปสเตอร์, คำอธิบายมินิเกม (Tutorial Overlays)

### ปัญหาของโซลูชันเดิม:
- **การเข้ารหัสของเกม:** ไฟล์ภาพถูกเข้ารหัสเป็น `.rpgmvp` (RPG Maker Visual Package) ทำให้ผู้แปลไม่สามารถเปิดอ่าน แก้ไข หรือค้นหาข้อความได้โดยตรง
- **ความล้มเหลวของการแปลภาพอัตโนมัติด้วย AI ปัจจุบัน (Inpainting Flaws):**
  - เครื่องมือแปลภาพสำเร็จรูปส่วนใหญ่ใช้ AI ลบข้อความ (Inpainting) ซึ่งมักทิ้งคราบเบลอ ขอบมัว หรือทำลายพื้นหลังกราฟิก
  - การจัดวางตัวอักษรภาษาไทยของเครื่องมือสำเร็จรูปไม่รองรับวรรณยุกต์ไทย และมักตัดคำภาษาไทยกลางคัน (Word-split rupture)
  - ขาดบริบทของตัวละคร (Character Context): ระบบแปลภาพทั่วไปไม่เข้าใจความสัมพันธ์ 4D, ระดับความสนิท, หรือสรรพนามของตัวละคร ทำให้สำนวนแปลเพี้ยนและหางเสียงผิด

## การตัดสินใจเชิงสถาปัตยกรรม (Architectural Decision)
ATF ตัดสินใจเลือก **แนวทางที่ 1 (High-Fidelity Typography & Bounding Box Pipeline)**:

1. **Decoupled Cryptographic Core (`rpgm_image_crypto.py`):**
   - ดึง Encryption Key จาก `www/data/System.json` โดยอัตโนมัติ
   - ทำการถอดรหัสระดับไบต์ (XOR Header Decryption) แปลง `.rpgmvp` $\leftrightarrow$ `.png` อย่างรวดเร็วและไม่สูญเสียความละเอียดพิกเซล
2. **Structured Layout Cataloging (`image_dialogues.csv`):**
   - นำภาพที่ถอดรหัสแล้วมาจัดทำตารางตำแหน่ง Bounding Box `(X, Y, Width, Height, Text_Color, Bg_Color, Font_Size)`
   - เชื่อมต่อเข้าสู่ ATF Translation Engine เพื่อให้บทสนทนาในภาพได้รับการแปลโดยอ้างอิง TLAS 4D Profile, สรรพนาม, และ Master Glossary เช่นเดียวกับบทสนทนาปกติ
3. **Typography & Grammar-Aware Rendering:**
   - ใช้ Pillow (PIL) ร่วมกับ `pythainlp` ในการคำนวณการตัดบรรทัดภาษาไทยอย่างถูกต้อง
   - ปิดลบเฉพาะพื้นที่ในกรอบข้อความ (Solid Bubble Fill / Patch Clean) ทำให้ไม่มีคราบเบลอของ AI Inpainting
   - เรนเดอร์ตัวอักษรภาษาไทยแบบคมชัดสูง (Clear Anti-Aliased Typography) พร้อมการจัดตำแหน่งตรงกลาง/ชิดซ้าย
4. **Automated Game Injection:**
   - นำไฟล์ภาพที่เรนเดอร์เสร็จแล้ว เข้ารหัสกลับเป็น `.rpgmvp` อัตโนมัติ พร้อมระบบสร้างไฟล์สำรอง `.bak_orig` เสมอ

## ผลกระทบและการรับประกันคุณภาพ (Consequences & Invariants)
- **Zero Inpainting Blurriness:** ภาพคมชัด 100% ตัวหนังสืออ่านง่าย สบายตา สไตล์โมบายแชตแท้
- **Strict Character Parity:** ตัวละครในภาพแชตจะใช้สรรพนามและสำนวนตรงกับบทสนทนาในเกม 100%
- **Universal Engine Support:** รองรับการถอดรหัสและเข้ารหัสของเกม RPG Maker MV/MZ ทุกเกม
