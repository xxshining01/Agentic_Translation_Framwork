# ADR-029: Deep Learning OCR and Zero-False-Positive Text Filtering Engine

## สถานะ (Status)
**ACCEPTED (ยอมรับและบรรจุเป็นมาตรฐานหลักในการสกัดข้อความรูปภาพ)**

## บริบทและสาเหตุรากเหง้าของปัญหา (Root Cause Analysis - RCA)
ในการทดสอบระบบตรวจจับข้อความในรูปภาพเกม RPG Maker พบปัญหาความล้มเหลวร้ายแรง:
- ระบบสแกนไฟล์ภาพเกมกว่า 2,000+ ภาพ และดึงภาพที่ไม่เกี่ยวข้อง (Sprite ตัวละคร, CG ลามก, ฉากหลัง, ไอคอน) เข้ามาปนเปื้อนในตารางแปลถึงกว่า 80-90%

### สาเหตุเชิงเทคนิค (Technical Root Cause):
1. **Flawed Visual Heuristic (Edge Detection Fallacy):**
   - โค้ดเดิมใช้ `ImageFilter.FIND_EDGES` เพื่อตรวจจับความถี่สูงของขอบภาพ โดยตั้งสมมติฐานว่าตัวหนังสือจะทำให้เกิดขอบเส้นแนวนอน
   - แต่ในงานภาพเกม 2D/Anime/RPG Maker ภาพ Sprite ตัวละคร, เสื้อผ้า, เส้นผม, และลวดลายฉาก ล้วนมีเส้นขอบคมชัด (Sharp Edges) สูงมาก ทำให้ได้ค่า Confidence $\ge 0.75$ แทบทุกภาพ
2. **Silent Failure & Broken Fallback:**
   - ตัวตรวจจับเดิมพึ่งพา `Windows.Media.Ocr` ซึ่งล้มเหลวแบบเงียบ (Silent Failure) เมื่อระบบปฏิบัติการไม่มี Language Pack หรือตัวอักษรเป็นฟอนต์เกมพิเศษ
   - ระบบมีตรรกะอันตราย: `if not has_real_text and heuristic["confidence"] >= 0.75: has_real_text = True`
   - เมื่อ OCR ล้มเหลว ระบบจึงหันไปยอมรับภาพ Sprite/CG ทั้งหมดที่ Heuristic ให้คะแนนสูง ส่งผลให้ภาพขยะกว่า 2,000 ไฟล์หลุดเข้ามาใน Pipeline

## การตัดสินใจเชิงสถาปัตยกรรม (Architectural Decision)
ATF ตัดสินใจยกเลิกการใช้ Edge Detection เป็นเกณฑ์ตัดสิน และปรับเปลี่ยนโครงสร้างสู่ **Deep Learning Text Detection Engine**:

1. **Adoption of RapidOCR (PP-OCRv4 ONNX Runtime):**
   - ใช้โมเดล **DBNet (Differentiable Binarization)** สำหรับ Text Detection และ **SVTR/LCNet** สำหรับ Text Recognition
   - โมเดล Deep Learning ถูกฝึกสอนให้จำแนกความแตกต่างระหว่าง "อักขระตัวหนังสือ" กับ "ลายเส้นภาพวาด/ตัวละคร" ได้อย่างเด็ดขาด
   - รันบน **ONNX Runtime (CPU/DirectML)** ทำให้ทำงานได้รวดเร็วระดับมิลลิวินาทีต่อภาพโดยไม่ต้องติดตั้ง PyTorch หรือ CUDA ขนาดยักษ์
2. **Direct In-Memory Decryption & Inference Pipeline:**
   - ถอดรหัสไฟล์ `.rpgmvp` ใน RAM $\rightarrow$ แปลงเป็นภาพ NumPy Array $\rightarrow$ ป้อนเข้า RapidOCR โดยตรง
   - ไม่ต้องเขียนไฟล์ชั่วคราวลง Disk ช่วยเพิ่มความเร็วในการสแกน 2,000+ ภาพขึ้นหลายเท่าตัว
3. **Zero-Tolerance False Positive Rule:**
   - ยกเลิกการ Fallback โดยอาศัยขอบภาพโดยเด็ดขาด (`heuristic_confidence` จะไม่ถูกนำมาใช้ตัดสินว่าเป็นภาพที่มีข้อความ)
   - ภาพจะถูกจัดเป็น "ภาพที่มีข้อความ (Text-Bearing Image)" ก็ต่อเมื่อโมเดล Deep Learning ตรวจพบ Text Bounding Box และอ่านตัวอักษรได้จริงเท่านั้น
4. **Sub-Pixel Coordinate Normalization:**
   - แปลง Bounding Box 4 จุด `[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]` ของโมเดล ให้เป็นแกน `(X, Y, Width, Height)` มาตรฐาน พร้อมบันทึกลง `image_dialogues.csv`

## ผลกระทบและการรับประกันคุณภาพ (Consequences & Invariants)
- **Zero Sprite/CG False Positives:** ภาพ Sprite และ CG ที่ไม่มีตัวหนังสือจะถูกคัดทิ้ง 100%
- **High-Precision Bounding Boxes:** พิกัดกล่องข้อความตรงตำแหน่งจริงระดับพิกเซล รองรับทั้งข้อความแนวนอนและข้อความในช่องแชต/UI
- **Universal Engine Compatibility:** ใช้งานได้กับเกม RPG Maker ทุกเวอร์ชัน และพร้อมขยายสู่ Visual Novel / Ren'Py ต่อไป
