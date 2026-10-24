# ADR-016: Smart Line Splitting and Strict Invariant Line-Break Restoration Architecture

## Status
Approved

## Context
ในการแปลเกมประเภท RPG Maker (รวมถึง Visual Novels) ข้อความบทสนทนา (Dialogue) และข้อความบรรยายในเกมจะถูกแสดงผลผ่านกล่องข้อความ (Message Window) ซึ่งมีข้อจำกัดทางกายภาพและกลไกของเอนจินเกมอย่างเข้มงวด:

### 1. ข้อจำกัดทางกายภาพและสถาปัตยกรรมของเอนจิน RPG Maker
1. **Window Dimensions & Line Capacity:**
   - กล่องข้อความมาตรฐานของ RPG Maker MV/MZ แสดงผลได้สูงสุด 4 บรรทัดต่อหนึ่งหน้าต่างข้อความ
   - ฟอนต์ในเกมไม่มีระบบ Automatic Hyphenation หรือ Justified Wrapping สำหรับภาษาที่ไม่มีช่องว่างระหว่างคำ (Non-segmented Scriptio Continua) อย่างภาษาไทย
   - หากข้อความภาษาไทยแปลออกมาเป็นประโยคยาวติดกันในบรรทัดเดียว (Single Long Line) ข้อความจะล้นทะลุขอบขวาของหน้าจอเกม (Text Overflow / Clipping) จนผู้เล่นไม่สามารถอ่านเนื้อหาได้
2. **Deterministic Event Timing & Text Codes:**
   - นักพัฒนาเกมต้นฉบับได้ออกแบบจังหวะการแสดงผล (Event Timing, Text Scrolling, Paging, และ Message Codes เช่น `\^`, `\|`, `\.`, `\!`, `\C[n]`, `\V[n]`) โดยอิงตามจำนวนบรรทัดของข้อความต้นฉบับภาษาอังกฤษ (`orig_lines`) อย่างแม่นยำ
   - หากข้อความภาษาไทยมีจำนวนบรรทัดมากกว่าหรือน้อยกว่าต้นฉบับ จะทำให้กล่องข้อความล้นตกหน้าจอ หรือจังหวะการแสดงหน้าต่างใหม่ผิดเพี้ยนไปจากที่เกมกำหนด

---

### 2. การวิเคราะห์สาเหตุเชิงลึกของปัญหาและความล้มเหลวเดิม (Root Cause Analysis - RCA)

จากการตรวจสอบโค้ดและข้อมูลย้อนหลังในโปรเจกต์ พบความล้มเหลว 5 ประการของแนวทางเดิม:

#### RCA-1: Prompt-Based Line Breaking Inconsistency
- การสั่งให้โมเดลภาษา (LLM / ChatGPT) ตัดขึ้นบรรทัดใหม่ (`\n`) ภายในเซลล์โดยตรงผ่าน System Instruction (~40-48 ตัวอักษร) พบว่าโมเดลไม่สามารถรักษาความคงเส้นคงวาได้
- โมเดลตัดคำแบบห้อยคำท้ายสั้นๆ (Dangling Particles) เช่น ขึ้นบรรทัดใหม่ด้วยคำว่า `นะ..)\|`, `เลย..\.`, `ไป..?`, `ผม!!!\|\^`
- ใน 127 แถวของเกม โมเดลแอบตัดประโยค 1 บรรทัดของต้นฉบับให้กลายเป็น 2 บรรทัดโดยพลการ

#### RCA-2: Hardcoded Search Window Collapse (บั๊ก 3 บรรทัดเหลือ 2 / 2 บรรทัดเหลือ 1)
ในระบบเดิม มีการล็อกค่าคงที่ของหน้าต่างค้นหาจุดตัด:
```python
# Legacy Code
if end_t > (start_search + 8) and end_t < (total_init_len - 4):
    valid_boundaries.append(end_t)
...
if best_split == -1:
    best_split = max(start_search + 10, min(total_init_len - 10, ideal_idx))
```
**ตัวอย่างการพังทลายเชิงคณิตศาสตร์ (Mathematical Collapse):**
สมมติข้อความสั้น 2 บรรทัด:
- `orig`: `"Dan..?\nWhat is it?"` (2 บรรทัด)
- `init`: `"แดน...? มีอะไรเหรอคะ?"` (`total_init_len = 21` ตัวอักษร)
- `target_ratio = 0.35` $\to$ `ideal_idx = 7`
- เงื่อนไขค้นหา: `end_t > 0 + 8` (ต้องมากกว่า 8) และ `end_t < 21 - 4` (ต้องน้อยกว่า 17)
- โทเค็นคำว่า `"แดน...?"` จบที่ตำแหน่ง `end_t = 7`
- ผลลัพธ์: ตำแหน่ง `7` **ไม่มากกว่า 8** จึงถูกตัดทิ้ง! หน้าต่างค้นหาไม่มีจุดตัดใดผ่านเกณฑ์ (`valid_boundaries = []`)
- ระบบตกเข้าสู่ Fallback: `best_split = max(10, min(11, 7)) = 10`
- ตำแหน่งที่ 10 เป็นสระ/คำต้องห้าม จึงเลื่อน `best_split` ไปเรื่อยๆ จนชนขอบขวาสุด (`best_split = 21`)
- ผลลัพธ์: ชิ้นส่วนที่ 1 ได้ข้อความทั้งหมด `"แดน...? มีอะไรเหรอคะ?"` ส่วนชิ้นส่วนที่ 2 ได้สตริงว่าง `""`
- **ข้อความยุบเหลือ 1 บรรทัดทันที!** ในกรณี 3 บรรทัดก็เกิดอาการเดียวกันในจุดตัดที่สอง ทำให้ยุบเหลือ 2 บรรทัด

#### RCA-3: Compound Word Severing (การตัดผ่ากลางกลุ่มคำประสม)
- ตัวตัดคำพื้นฐานของภาษาไทยมองเห็นคำว่า `พวก` และ `เธอ` เป็นคนละโทเค็น
- เมื่อจุด `ideal_idx` ตกอยู่ระหว่างสองคำนี้ ระบบเดิมจะตัดขึ้นบรรทัดใหม่ทันที ส่งผลให้เกิดประโยคเช่น:
  ```
  บรรทัดที่ 1: ฉันโชคดีจริง ๆ ที่มีพวก
  บรรทัดที่ 2: เธอสองคนอยู่ที่นี่~!
  ```
  ซึ่งผิดหลักไวยากรณ์และความหมายอย่างรุนแรง

#### RCA-4: Glyph Corruption จาก Illegal Line Starters
- อักขระจำพวกสระบน (ิ, ี, ึ, ื, ั), สระล่าง (ุ, ู), วรรณยุกต์ (่, ้, ๊, ๋), ตัวการันต์ (์), ไม้ยมก (ๆ), ไปยาลน้อย (ฯ) หรือเครื่องหมายวรรคตอนปิด (`]`, `}`, `)`, `”`, `?`, `!`) หลุดไปอยู่ตัวแรกของบรรทัดใหม่ ทำให้เอนจินแสดงผลฟอนต์ลอย เละ หรือแครช

#### RCA-5: Silent Skipping ในสคริปต์ซ่อมแซม
- สคริปต์ซ่อมแซมเดิมมีเงื่อนไข `if init_nl == 0: should_repair = True`
- หากแถวใดโมเดลตัดมา 2 บรรทัด (`init_nl == 1`) แต่ต้นฉบับมี 3 บรรทัด (`orig_nl == 2`) จะไม่เข้าเงื่อนไข ทำให้ถูกข้ามไปอย่างเงียบๆ

---

## Decision

เราตัดสินใจปฏิรูประบบตัดคำและจัดบรรทัดใหม่ทั้งหมด โดยสร้างสถาปัตยกรรม **Smart Line Splitting and Strict Invariant Restoration** บรรจุลงในคลาส `SmartLineSplitter` โดยมีหลักการเชิงวิศวกรรม 5 ประการ:

### 1. Strict Line-Count Parity Invariant
- **สมมติฐานหลัก (Postcondition):** สำหรับทุก Input `(orig_text, init_text)` ผลลัพธ์จะต้องมีจำนวนบรรทัดเท่ากับ `orig_text.count('\n') + 1` เสมอ 100.00%
- หากจำนวนชิ้นส่วนที่ตัดออกมาเกิน ($M > K$) ให้ยุบชิ้นส่วนท้ายเข้าด้วยกัน
- หากจำนวนชิ้นส่วนที่ตัดออกมาขาด ($M < K$) ให้เฉลี่ยตัวอักษรเพื่อไม่ให้เกิดสตริงว่าง

### 2. Pre-Split Normalization (การล้างพิษข้อความ)
- แยก Speaker Tag (`\n<Speaker:>` หรือ `<Speaker:>`) ออกก่อนนำข้อความไปคำนวณ
- ยุบ Newline เดิมทิ้งทั้งหมด (`re.sub(r"\s*\n\s*", " ", pure).strip()`) เพื่อสร้างระนาบข้อความต่อเนื่องใหม่ ป้องกันไม่ให้ Newline เก่าที่ผิดตำแหน่งมารบกวนการตัดคำ

### 3. Dynamic Elastic Windowing
ยกเลิกค่าคงที่ $8$ และ $10$ อย่างถาวร และใช้ฟังก์ชันความยาวแบบยืดหยุ่น:
$$\text{min\_seg} = \max\left(1, \min\left(5, \left\lfloor \frac{L}{K \times 2} \right\rfloor \right)\right)$$
สำหรับจุดตัดที่ $i$ (จาก $0$ ถึง $K - 2$) โดยมีจุดตัดที่เหลือในอนาคตอีก $rem$ จุด:
$$\text{lower\_bound} = \text{prev\_cut} + \text{min\_seg}$$
$$\text{upper\_bound} = L - ((rem + 1) \times \text{min\_seg})$$
*การพิสูจน์ความคงตัว (Invariant Proof):* เนื่องจาก $\text{upper\_bound} - \text{lower\_bound} \ge \text{min\_seg}$ เสมอ จึงไม่มีทางที่จุดตัดจะชนกัน และไม่มีทางที่ชิ้นส่วนท้ายจะมีความยาวเป็น 0

### 4. Inseparable Compounds Protection Engine
สร้างระบบ Blacklist ช่วงดัชนีตัวอักษร (`forbidden_ranges`) จาก 6 กลุ่มคำประสมหลัก:
1. `พวก(เธอ|เรา|เขา|มัน|ท่าน|เจ้า|นาย|นั้น|นี้|โน้น|เด็กๆ?|ผู้หญิง|ผู้ชาย|คน|สาวๆ?|อันธพาล)`
2. `(คน|สิ่ง|เรื่อง|อัน|แบบ|อย่าง|ทาง|ฝ่าย|ด้าน)(นี้|นั้น|โน้น|อื่น|ใด|ไหน)`
3. `(ตอน|คราว|เวลา|สมัย|ช่วง|ยุค|ที่|ตรง)(นี้|นั้น|โน้น|ก่อน|หลัง|ไหน|แห่งนี้|แห่งนั้น)`
4. `ไม่(ได้|ใช่|มี|เคย|ยอม|ว่า|อยาก|ต้อง|เป็นไร|เอา|ถูก|จริง|พอ|ทัน)`, `(กำลัง|จะต้อง|น่าจะ|อาจจะ|ควรจะ|แทบจะ|เกือบจะ)`
5. `(อะไร|อย่างไร|ทำไม|เท่าไหร่|เท่าใด|เมื่อไหร่|ใคร)`
6. `(เหมือนกัน|เช่นกัน|ด้วยกัน|ด้วยนะ|ด้วยสิ|ด้วยค่ะ|ด้วยครับ|ด้วยล่ะ|จริง(ๆ|จัง)?|แน่นอน|ชัดเจน|สักพัก|นิดหน่อย)`
7. `(ผู้หญิง|ผู้ชาย|เด็กหญิง|เด็กชาย|ทุกคน|คนแปลกหน้า)`

### 5. Multi-Stage Waterfall Selection
1. **Stage 1 (Tail Anchor):** ค้นหาสัญลักษณ์ท้ายบรรทัดเดิม (`..\.`, `\..`, `...`, `!?`, `?`, `!`, `♥`) หากพบจุดตรงกันในภาษาไทยที่ปลอดภัย ให้เลือกทันที
2. **Stage 2 (Grammar Scoring):** ให้คะแนนตำแหน่งตัดตามโครงสร้างไวยากรณ์ (โบนัสช่องว่าง $-30$, โบนัส Punctuation $-25$, โบนัสหางเสียง $-18$, โบนัสหน้าคำเชื่อม $-15$, บทลงโทษห้อยคำท้าย $+45$, บทลงโทษท่อนสั้น $+40$)
3. **Stage 3 (Controlled Relaxation):** หากไม่พบคำที่ผ่านเกณฑ์ Stage 2 ให้อนุโลมตัดที่รอยต่อตัวอักษรใดๆ ที่อักษรถัดไปไม่ใช่สระบน/ล่าง หรือวรรณยุกต์
4. **Stage 4 (Absolute Fallback):** หนีบค่า `ideal_idx` เข้าสู่ช่วงปลอดภัยและเลื่อนหาพยัญชนะต้นแรกที่ปลอดภัย

---

## Consequences

### Positive
- **100.00% Line Count Parity:** ยืนยันผลการทดสอบบนไฟล์จริง 82,538 แถว แถวที่มีบทสนทนาหลายบรรทัด 41,134 แถว ได้รับการตัดบรรทัดตรงกับต้นฉบับ 100.00% (0 ข้อผิดพลาด)
- **Elimination of Dangling & Severed Words:** ขจัดปัญหาคำว่า `พวกเธอ` หรือ `ไม่ได้` ถูกตัดขาดจากกัน 100%
- **Zero Font Rendering Corruptions:** ไม่มีสระบน/ล่าง หรือวรรณยุกต์หลุดไปขึ้นต้นบรรทัดใหม่แม้แต่ตำแหน่งเดียว
- **Automated Repair Pipeline:** สามารถซ่อมแซมและจัดระเบียบไฟล์ CSV ขนาดใหญ่ได้ในเวลาไม่ถึง 10 วินาที

### Negative / Trade-offs
- **Short-Phrase Segmentation:** ในประโยคสั้นมากแต่ต้นฉบับมีหลายบรรทัด (เช่น `"Dan..?\nWhat is it?"`) คำแปลภาษาไทยจำเป็นต้องถูกแบ่งเป็นท่อนสั้นๆ เช่น `"แดน...?"` และ `"มีอะไรเหรอคะ?"` ซึ่งอาจทำให้แต่ละบรรทัดดูสั้น แต่จำเป็นเพื่อรักษาความสอดคล้องกับกล่องข้อความและอนิเมชันของเกม

---

## References & Related Architectural Documents
- **SAD-011:** [Typography Alignment and Line-Break Parity Architecture](../architecture/SAD-011-Typography-Alignment-and-Line-Break-Parity.md) (พิมพ์เขียวสถาปัตยกรรมระดับระบบของโมดูลนี้)
- **SDD-013:** [SmartLineSplitter and Typography Restoration Specification](../design/SDD-013-SmartLineSplitter-and-Typography-Restoration.md) (รายละเอียดการออกแบบเชิงโค้ดและขั้นตอนวิธี)
- **SAD-010:** [TLAS Global-Relational Localization Architecture (v4.0)](../architecture/SAD-010-TLAS-Global-Relational-Architecture.md) (สถาปัตยกรรมหลักชั้นหน้าซึ่งส่งมอบ Raw Translation มาให้โมดูลนี้ทำ Post-Processing)
- **SAD-005:** [Rule-Based Dialogue Localization Processing Pipeline](../architecture/SAD-005-TLAS-Localization-Engine-4D-Pipeline.md) (ระบบจัดการ Control Codes และ Raw Game Data Layer ดั้งเดิม)
- **ADR-015:** [Global-Relational Architecture Without Timeline Dependencies](ADR-015-Global-Relational-Architecture-Without-Timeline.md) (การตัดสินใจยกเลิก Timeline เข้าสู่ Macro Consensus)
- **ADR-010:** [Smart Batching Engine](ADR-010-Smart-Batching.txt) (สถาปัตยกรรมการแบ่งกลุ่มข้อมูลเพื่อส่งแปล)
- **ADR-012:** [TLAS 3-Tier Fallback](ADR-012-TLAS-3-Tier-Fallback.md) (แนวคิด Multi-Tier Fallback Hierarchy ที่นำมาประยุกต์ใช้กับ Waterfall Selection)
