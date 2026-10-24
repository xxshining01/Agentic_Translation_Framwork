# ADR-019: Control Code Masking and Bidirectional Parity Preservation Architecture

## Status
Approved

## Context
ในกระบวนการแปลภาษาสำหรับวิดีโอเกม (Game Localization) โดยเฉพาะเกมที่สร้างด้วยเอนจิน RPG Maker (MV/MZ), Visual Novel (Ren'Py), และ Unity TextMeshPro ข้อความบทสนทนา (Dialogue) และข้อความส่วนติดต่อผู้ใช้ (UI Text) มักไม่ได้มีเพียงภาษาธรรมชาติบริสุทธิ์ (Pure Natural Language) หากแต่มีการแทรก **รหัสสคริปต์ควบคุมการแสดงผลและจัดรูปแบบข้อความ (Message Escape Codes / Formatting Control Tags)** เข้ามาปะปนอยู่ภายในประโยค

จากการตรวจสอบข้อผิดพลาดจริงในโปรเจกต์ (`Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated (1).csv`) พบการแปลที่ผิดเพี้ยนอย่างรุนแรงเมื่อมีรหัสควบคุมแทรกอยู่ในประโยค เช่น:
*   **Original:** `If it is filled up, it means that she is \fistrongly influenced\fi by what she has experienced here.`
*   **Corrupted Translation:** `หากหัวใจเต็ม แสดงว่าเธอได้รับอิทธิพล iอย่างมากi จากสิ่งที่เธอประสบพบเจอที่นี่`
*   **Original:** `If I can bring your attention to the \C[18]\fbheart symbol\fb\C on your above right..`
*   **Corrupted Translation:** `หากมองไปทางด้านขวาบนของคุณ จะเห็น สัญลักษณ์ \C[18]bรูปหัวใจ b\C อยู่ตรงนั้น..`

---

### 1. การวิเคราะห์สาเหตุเชิงลึกของปัญหา (Root Cause Analysis - RCA)

#### RCA-1: Unmasked Tag Hallucination & Semantic Displacement (AI ย้ายตำแหน่งแท็ก)
- ในระบบเดิม มีการส่งข้อความดิบที่มีรหัสควบคุม (เช่น `\fi`, `\fb`, `\C[18]`) เข้าไปใน Prompt ของโมเดลภาษา (LLM) โดยตรงโดยไม่มีการปกป้อง (Unmasked Text)
- LLM มองเห็นเครื่องหมาย Backslash (`\`) และตัวอักษรภาษาอังกฤษที่ติดกับคำศัพท์เป็นเพียงสตริงทั่วไป ไม่เข้าใจว่า `\fi...\fi` คือคำสั่งเปิด-ปิดตัวเอียงที่ต้องครอบคลุมทั้งวลี `[strongly influenced]`
- ส่งผลให้ LLM พยายามเดาตำแหน่งเอง นำแท็กไปครอบคำผิดตำแหน่ง เช่น ครอบเฉพาะคำว่า `อย่างมาก` หรือในเคส `\fbheart symbol\fb` AI แยกคำว่า `สัญลักษณ์` ออกมาอยู่นอกแท็ก แล้วเอาแท็กไปครอบแค่ `รูปหัวใจ` ทำให้ความสวยงามและอรรถรสในการแสดงผลของตัวเกมเสียหาย

#### RCA-2: Python Escape Hazard & Form Feed Corruption (`\f` กลายเป็น `\x0c` / )
- ในภาษาโปรแกรมมิ่ง (Python, C, JavaScript) และมาตรฐาน JSON อักขระ `\f` คือรหัสหลบสากล (Escape Sequence) ของ **Form Feed (รหัส ASCII 12 / `0x0C`)**
- เมื่อระบบนำเข้า/ส่งออกข้อความที่มี `\fi` (Font Italic) หรือ `\fb` (Font Bold) โดยไม่ได้ใช้ Raw String (`r"..."`) หรือไม่ได้ทำการ Double-Escape (`\\fi`, `\\fb`):
  - ตัวอักษร `\f` จะถูกระบบมองเป็น Form Feed ทันที ทำให้คำว่า `\fi` กลายเป็น `\x0ci` (i) และ `\fb` กลายเป็น `\x0cb` (b)
  - จากการสแกน Audit จริงในไฟล์ CSV พบแถวที่ปนเปื้อน Form Feed เสียหายสูงถึง **338 แถว**

#### RCA-3: Asymmetrical Tag Destruction (การฉีกขาดของแท็กเปิด-ปิด)
- รหัสควบคุมบางประเภทใน RPG Maker มีลักษณะเปิดและปิดไม่สมมาตร เช่น `\C[18]` (เปลี่ยนเป็นสีที่ 18) ปิดด้วย `\C` หรือ `\C[0]` (คืนค่าสีเริ่มต้น)
- เมื่อ LLM แปลประโยคที่มีโครงสร้างหลายบรรทัด บ่อยครั้งที่ AI ทำแท็กปิด `\C` หลุดหายไป หรือลบ `\fb` ท้ายประโยคทิ้ง ส่งผลให้ข้อความหลังจากนั้นในหน้าต่างเกมทั้งหมดกลายเป็นตัวหนาหรือเปลี่ยนสีค้างไปตลอดทั้งฉาก

#### RCA-4: Timing & Event Paging Drift (`\.`, `\|`, `\!`, `\^`)
- รหัสควบคุมจังหวะการหยุดรอของเกม เช่น `\.` (รอ 1/4 วินาที), `\|` (รอ 1 วินาที), `\!` (รอผู้เล่นกดปุ่ม), `\^` (ปิดหน้าต่างทันที) มักถูกออกแบบให้วางไว้ที่ท้ายบรรทัดอย่างแม่นยำ
- เมื่อไม่มีระบบ Masking รหัสเหล่านี้มักถูก AI เลื่อนไปอยู่กลางประโยค หรือหายไป ทำให้จังหวะการเล่าเรื่อง (Pacing & Timing) ของตัวเกมผิดเพี้ยนไปจากต้นฉบับ

---

## Decision

ตามพันธกิจหลักของระบบใน **`.agents/AGENTS.md` (Universal Framework Paradigm)** ที่ต้องสร้างระบบสากลสำหรับรองรับทุกเกมในอนาคต เราตัดสินใจสร้างสถาปัตยกรรม **Control Code Masking and Bidirectional Parity Preservation** บรรจุลงในไปป์ไลน์เป็น **Stage 4.1: Message Code Sanitization & Protection Layer** (อยู่ก่อนหน้า Translation Runtime และหลังจาก Macro Consensus) โดยมีหลักการ 5 ประการ:

### 1. Bidirectional Semantic XML-like Masking (การแปลงเป็นแท็กความหมายคู่ขนาน)
ก่อนส่งข้อความไปยัง LLM ระบบจะต้องทำการ **Masking** รหัสควบคุมของเอนจินเกมให้กลายเป็นแท็ก XML เสมือนที่ AI คุ้นเคยและเข้าใจความหมายเชิงภาษาศาสตร์ได้ดีที่สุด:
*   `\fi...\fi` $\longrightarrow$ `<italic>...</italic>`
*   `\fb...\fb` $\longrightarrow$ `<bold>...</bold>`
*   `\C[n]...\C` $\longrightarrow$ `<color id="n">...</color>`
*   `\I[n]` $\longrightarrow$ `<icon id="n"/>`
*   `\{` / `\}` $\longrightarrow$ `<scale factor="+1"/>` / `<scale factor="-1"/>`
*   `\V[n]` $\longrightarrow$ `<variable id="n"/>`
*   `\N[n]` $\longrightarrow$ `<actor id="n"/>`
*   `\.`, `\|`, `\!`, `\^`, `\..` $\longrightarrow$ `<pause type="short"/>`, `<pause type="long"/>`, `<wait_input/>`, `<auto_close/>`

### 2. In-Prompt Natural Language Contract (สัญญาข้อตกลงใน Prompt)
ในคำสั่ง System Instruction ของ Stage 4 ให้ระบุกฎเหล็กทางไวยากรณ์:
> *"Text contains structural XML tags like `<italic>text</italic>`, `<bold>text</bold>`, `<color id="n">text</color>`, and atomic tags like `<icon id="n"/>`. You MUST keep these tags wrapping the EXACT corresponding translated words in Thai. NEVER drop, rename, or translate the tag names or IDs!"*

### 3. Strict Deterministic Unmasking & Double-Escape Guarantee
เมื่อได้รับคำแปลภาษาไทยกลับมาจาก LLM ระบบจะทำการ **Unmasking** คืนค่ากลับสู่รหัสควบคุมของ RPG Maker โดยอัตโนมัติ:
*   แปลง `<italic>ข้อความ</italic>` $\longrightarrow$ `\fiข้อความ\fi`
*   แปลง `<bold>ข้อความ</bold>` $\longrightarrow$ `\fbข้อความ\fb`
*   แปลง `<color id="n">ข้อความ</color>` $\longrightarrow$ `\C[n]ข้อความ\C`
*   **Double-Escape Defense:** ทุกฟังก์ชันที่เกี่ยวข้องกับการเขียนไฟล์หรือ Serialize ข้อมูล จะต้องจัดการสตริงผ่านโมดูลที่รับประกันว่าจะไม่มีการแปลง `\f` เป็น `\x0c` (ASCII 12) อย่างเด็ดขาด

### 4. Tag Parity & Tree Structure Assertion (การตรวจสอบความสมบูรณ์ 100%)
สร้างระบบ **Tag Parity Verifier**:
- นับจำนวนแท็กต้นฉบับเทียบกับคำแปล ($N_{\text{orig\_tags}} == N_{\text{trans\_tags}}$)
- ตรวจสอบความสมบูรณ์ของคู่เปิด-ปิด (Balanced Tag Pairs)
- หากพบว่า AI ทำแท็กหลุดหาย หรือลำดับแท็กเสียรูป ระบบจะ **ปฏิเสธคำตอบนั้นทันที (Reject)** และทำการ **Adaptive Retry** ตามกฎ No Skip Guarantee จนกว่าจะได้คำแปลที่มีแท็กสมบูรณ์ 100%

### 5. Multi-Engine Pluggable Driver (โครงสร้างรองรับทุกเอนจินเกม)
ออกแบบสถาปัตยกรรม Masker ให้เป็นแบบถอดเปลี่ยน Driver ได้ (Pluggable Architecture):
- `RPGMakerControlCodeDriver`: รองรับรหัส `\`, `\C`, `\I`, `\V`, `\N`, `\fi`, `\fb`
- `RenPyControlCodeDriver`: รองรับ `{i}`, `{b}`, `{color}`, `{size}` (สำหรับเกม Visual Novel)
- `UnityTMPControlCodeDriver`: รองรับ `<color>`, `<b>`, `<i>`, `<size>` (สำหรับเกม Unity)

---

## Consequences

### Positive
- **100% Elimination of Formatting Corruption:** ขจัดปัญหา `\fi` และ `\fb` ครอบคำผิด หรือพังเป็น Form Feed `\x0c` อย่างถาวร 100%
- **Preservation of Game Aesthetics:** ตัวอักษรสี ตัวหนา ตัวเอียง และไอคอนในเกมจะแสดงผลตรงตามตำแหน่งที่ผู้พัฒนาเกมต้นฉบับออกแบบไว้ทุกประการ
- **Universal Reusability:** สามารถนำโมดูล Masker นี้ไปใช้แปลเกม RPG Maker, Ren'Py, หรือ Unity อื่นๆ ในอนาคตได้ทันทีตามพันธกิจของระบบ
- **Zero Hallucination on Timing:** รหัสควบคุมจังหวะ (`\.`, `\|`, `\^`) จะคงอยู่ที่ตำแหน่งที่ถูกต้อง ไม่หลุดไปอยู่กลางประโยค

### Negative / Trade-offs
- **Token Overhead:** การแปลงรหัสสั้น (เช่น `\fi`) เป็นแท็ก XML (เช่น `<italic>`) ทำให้จำนวน Token ต่อ Batch เพิ่มขึ้นเล็กน้อย (~3-5%) แต่คุ้มค่าอย่างมหาศาลเมื่อเทียบกับความถูกต้องของผลงานแปล

---

## References & Related Architectural Documents
- **SAD-014:** [Control Code Masking and Sanitization Engine Architecture](../architecture/SAD-014-Control-Code-Masking-and-Sanitization-Engine.md) (พิมพ์เขียวสถาปัตยกรรมระดับระบบของ Stage 4.1)
- **SDD-016:** [MessageCodeMasker and Tag Parity Specification](../design/SDD-016-MessageCodeMasker-and-Tag-Parity-Specification.md) (รายละเอียดการออกแบบเชิงโค้ดและขั้นตอนวิธี)
- **AGENTS.md:** [Core System Mission](../../.agents/AGENTS.md) (วิสัยทัศน์ระบบสากลและการบันทึก RCA สู่สถาปัตยกรรม)
- **ADR-016:** [Smart Line Splitting and Strict Invariant Restoration](ADR-016-Smart-Line-Splitting-and-Strict-Invariant-Restoration.md) (ระบบจัดระเบียบบรรทัดใน Stage 5 ซึ่งต้องรับช่วงต่อจากข้อความที่ Unmask แล้ว)
- **SAD-010:** [TLAS Global-Relational Localization Architecture (v4.0)](../architecture/SAD-010-TLAS-Global-Relational-Architecture.md) (สถาปัตยกรรมหลัก Stage 1–4)
- **ARCHITECTURE_INDEX:** [ATF Architectural Master Index](../ARCHITECTURE_INDEX.md) (แผนที่เชื่อมโยงเอกสารทั้งหมดในระบบ)
