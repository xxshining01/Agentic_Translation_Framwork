# ADR-030: Human-Vision Text-Bearing Image Classifier & Zero-Hallucination Architecture

## Status
Accepted / Implemented

## Context & Problem Statement (บริบทและปัญหาเดิม)
ในกระบวนการสแกนและแปลภาพเกม (Image Localization) รอบก่อนหน้า ระบบประสบความล้มเหลวเชิงผลลัพธ์ (Complete Practical Failure):
1. **False-Positive Flooding (ภาพขยะทะลัก):** แคตตาล็อก `image_dialogues.csv` มีแถวขยะปูดขึ้นมามากกว่า 5,000 แถว และ `unique_dialogues.csv` มีมากกว่า 1,500 แถว ซึ่ง 98% เป็นภาพกราฟิกล้วน เช่น สไปรต์ตัวละคร (Sprite Sheets), อนิเมชันต่อสู้ (Battle VFX เช่น `Hit`, `Explosion`, `Holy`, `Darkness`), ไทล์ฉาก (Tilesets), และภาพ CG อีโรติก/อีเวนต์
2. **CJK & Character Hallucination (การหลอนตัวอักษรจีนและสัญลักษณ์):** โมเดล PP-OCRv4 ของ RapidOCR มี Dictionary ภาษาจีน (Chinese Recognizer `ppocr_keys_v1.txt`) เมื่อตรวจพบลวดลายกราฟิกที่มีคอนทราสต์สูง เช่น ประกายไฟของเวทมนตร์, เส้นผม, ขนตา, รอยพับเสื้อผ้า หรือขอบเงา ระบบจะพยายาม "เดาเทียบ" เส้นเหล่านั้นเป็นตัวอักษรจีน (เช่น `米`, `十`, `车`, `药`, `券`, `出`, `福`) หรือตัวอักษรเดี่ยว (`X`, `D`, `O`, `e`, `m`, `2`, `1`, `.`)
3. **Flawed Problem Formulation (ตั้งโจทย์ผิดทาง):** ระบบเดิมตั้งโจทย์ว่า *"ภาพนี้มี Text อะไร"* และพยายามขูด Text จากทุกภาพที่มีในเกม (หว่านแห) แทนที่จะตั้งโจทย์ว่า *"ภาพไหนบ้างที่มี Text"* โดยในความเป็นจริง ภาพส่วนใหญ่ในเกมไม่มีตัวหนังสือเลย

## Architectural Decision (การตัดสินใจเชิงสถาปัตยกรรม)

เราปรับกระบวนทัศน์ของระบบ Image Localization สู่ **"Human-Vision Text-Bearing Image Classifier"** โดยแบ่งเป็น 3 เสาหลัก:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GAME IMAGE REPOSITORY                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    [Layer 1: Asset Domain Whitelist & Structural Exclusion]
    ├── Whitelist: pictures/, system/, titles1/, titles2/, SumRndmDde/
    └── Blacklist: animations/, characters/, tilesets/, faces/, enemies/
                   !$*, $*, Actor*, Hit*, Explosion*, 0Bar_*, 3some*, 1Drex*
                                    │
                                    ▼
    [Layer 2: Dual-Engine Human-Vision Detection]
    ├── Option A: Windows Native OCR (Windows.Media.Ocr / Snipping Tool API)
    │             - Zero Chinese hallucination on English/UI text
    │             - Pure graphics and sprites return 0 lines naturally
    └── Option B: RapidOCR (PP-OCRv4) + Lexical Validator
                                    │
                                    ▼
    [Layer 3: Human-Vision Lexical Validator (Zero-Hallucination Invariant)]
    ├── Reject isolated CJK characters without Latin sentences (米, 十, 车, 药, 福)
    ├── Reject single characters/digits (X, O, D, e, m, 1, 2, .)
    ├── 2-letter strings MUST be valid English words/UI (OK, UP, HP, HI, NO, GO, ME)
    │   (Drops random 2-letter noise like CB, RE, fX, sd, da)
    └── Words >= 3 letters MUST have readable Latin structure
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               VERIFIED TEXT-BEARING IMAGES ONLY (~40-60 files)         │
│          Clean CSV Catalog & Unique Translation Memory Sheet           │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Asset Domain Whitelisting & Structural Exclusion
- **Folder Whitelist:** สแกนเฉพาะไดเรกทอรีที่มีความเป็นไปได้ที่จะมี UI, แชตมือถือ, หรือคำอธิบายบทสนทนา ได้แก่ `pictures/`, `system/`, `titles1/`, `titles2/`, และโฟลเดอร์ Plugin UI เช่น `SumRndmDde/`
- **Structural Blacklist:** กรองทิ้งโฟลเดอร์กราฟิกเกมแท้จริง 100% เช่น `animations/`, `characters/`, `tilesets/`, `faces/`, `enemies/`, `sv_actors/`
- **Pattern Blacklist (`is_text_eligible_filename`):** ปฏิเสธไฟล์สไปรต์ตัวละคร (`!$*`, `$*`, `Actor*`), เอฟเฟกต์การต่อสู้ (`Hit*`, `Explosion*`, `Darkness*`, `Cure*`, `Holy*`), ไทล์ฉาก (`Chest*`, `Tileset*`), และ CG frames (`0Bar_*`, `0BigB_*`, `1Drex*`, `1Filming*`, `3some*`, `4Some*`, `Apron*`)

### 2. Dual-Engine OCR Integration (Windows Native OCR vs. RapidOCR)
- **Windows Native OCR (`Windows.Media.Ocr.OcrEngine`):** เป็น Engine เดียวกับที่ใช้ขับเคลื่อนระบบ Windows Capture (Snipping Tool) ของ Windows 10/11:
  - อ่านข้อความบทสนทนา UI ได้คมชัดสูง
  - **Zero Chinese Hallucination:** ไม่มีการหลอนภาษาจีนบนข้อความภาษาอังกฤษ/ไทย
  - หากนำภาพกราฟิกเปล่า สไปรต์ หรือประกายไฟเข้ามา Windows OCR จะคืนค่า `Lines = 0` (ไม่เห็นตัวหนังสือ) โดยธรรมชาติ
- **RapidOCR with Lexical Validation:** รองรับการประมวลผลเร็วใน RAM ผ่าน PP-OCRv4 เมื่อผสานกับ Lexical Validator

### 3. Human-Vision Lexical Validator (`is_valid_game_text`)
ตรวจพิสูจน์ข้อความก่อนยอมรับเข้าแคตตาล็อก:
1. หากมีตัวอักษรจีน/ญี่ปุ่นโดยไม่มีประโยคภาษาอังกฤษ $\ge 3$ ตัวอักษร -> ถือเป็น Noise ปฏิเสธ 100%
2. ปฏิเสธตัวอักษร/ตัวเลข/สัญลักษณ์เดี่ยว (`len(txt) == 1`) เด็ดขาด
3. หากข้อความมีตัวหนังสือภาษาอังกฤษ 2 ตัวอักษร ต้องตรงกับคำศัพท์ใน `VALID_2LETTER_WORDS` (`OK`, `UP`, `HP`, `HI`, `NO`, `GO`, `ME`, `MY`, `UI`, `VS`, `ON`, `TV`, `PC`) เท่านั้น (ตัด `CB`, `RE`, `fX`, `sd`)
4. ข้อความยาว $\ge 3$ ตัวอักษร ต้องมีโครงสร้างคำที่อ่านได้ ไม่ใช่ตัวอักษรซ้ำหรือสัญลักษณ์สุ่ม

### 4. Noise Purge Protocol (`localize_images.py clean`)
สร้าง Subcommand ทำความสะอาดไฟล์ `image_dialogues.csv` และ `unique_dialogues.csv` เดิมที่ถูกปนเปื้อน โดยคัดกรองข้อมูลทุกแถวผ่าน `is_text_eligible_filename` และ `is_valid_game_text` เพื่อชะล้างแถวขยะออกกว่า 4,800 แถว และ Rebuild คำแปลแท้จริงกลับคืนมา

## Consequences (ผลกระทบและประโยชน์ที่ได้รับ)
1. **Zero Garbage Rows:** ปริมาณภาพที่ต้องแปลลดลงจาก 5,000+ เหลือเฉพาะภาพบทสนทนาจริงราว 40-60 ภาพ (`RVPhone*`, `Phone*`, `p1_*`, `Giftguide*`)
2. **True Human-Vision Classification:** รูปที่ไม่มีตัวหนังสือจะถูกจัดประเภทเป็น `Clean graphic or character sprite` และไม่ถูกนำเข้าแคตตาล็อก
3. **Pluggable & Universal:** สถาปัตยกรรมนี้ใช้ได้กับทุกเกม RPG Maker และเกมอื่นๆ โดยไม่มีการ Hardcode เฉพาะกิจ
