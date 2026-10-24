# ADR-017: Atomic Checkpoint Persistence and Pure Untranslated Queue Filtering

## Status
Approved

## Context
ในการประมวลผลการแปลข้อความบทสนทนาขนาดใหญ่ (Large-Scale Game Dialogue Localization) สำหรับเกม RPG Maker ซึ่งมีข้อความกว่า 82,538 แถว การเรียกใช้งานโมเดลภาษาขนาดใหญ่ (LLM / ChatGPT API) จำเป็นต้องใช้เวลานานหลายชั่วโมงหรือหลายวัน การจัดการสภาวะการทำงาน (State Management), ความต่อเนื่องของการประมวลผล (Persistence & Resumption), และความบริสุทธิ์ของคิวงาน (Queue Purity) ถือเป็นหัวใจสำคัญอย่างยิ่งยวด

จากการตรวจสอบระบบและฐานข้อมูลจริงในโปรเจกต์ (`Example RPGM Game/SSPV034v1.35 - Trans - Processed_v3_translated (1).csv` และ `data/tlas/chatgpt_translation_checkpoint.json`) พบปัญหาเชิงสถาปัตยกรรมและความล้มเหลว 4 ประการ:

---

### 1. การวิเคราะห์สาเหตุเชิงลึกของปัญหาเดิม (Root Cause Analysis - RCA)

#### RCA-1: Checkpoint Fragmentation & Desynchronization (ปัญหา 1,732 แถวตกค้าง)
- **ปรากฏการณ์:** ในไฟล์ CSV ตัวไฟนอล พบแถวที่มี Role เป็น Dialogue/Story และมีสถานะ `Displayable=Yes` จำนวนถึง 1,732 แถวที่คอลัมน์ `Initial` กลายเป็นค่าว่าง (`""`) ทำให้ผู้ใช้เข้าใจว่าระบบกรองหลุดและไม่ได้แปล
- **สาเหตุรากเหง้า (Root Cause):** 
  - เมื่อตรวจสอบไฟล์ `chatgpt_translation_checkpoint.json` พบว่าทั้ง 1,732 แถวนี้ **ได้รับการแปลและเก็บอยู่ใน Checkpoint เรียบร้อยแล้ว (มีคำแปลอยู่จริง 100%)**
  - ความล้มเหลวเกิดจากโครงสร้าง Checkpoint มีการจัดเก็บแยกตามคีย์ชื่อไฟล์ (`csv_translations -> filename`) ซึ่งในประวัติการทำงานมีการเปลี่ยนชื่อไฟล์ปลายทางหลายครั้ง เช่น:
    - `"SSPV034v1.35 - Trans - Processed_v3.csv"`
    - `"SSPV034v1.35 - Trans - Processed_v3_translated.csv"`
    - `"SSPV034v1.35 - Trans - Processed_v3_translated (1).csv"`
  - สคริปต์ Translation Runner ดั้งเดิมดึงคำแปลเฉพาะคีย์ชื่อไฟล์ปัจจุบันเท่านั้น ไม่ได้รวบรวมคำแปลข้าม Section ทำให้คำแปลที่เคยประมวลผลไปแล้วไม่ถูกเขียนลงใน CSV ไฟล์ใหม่

#### RCA-2: Single-Point-of-Failure Write Hazard (ความเสี่ยง JSON เสียหาย)
- สคริปต์รุ่นเก่าใช้วิธีเปิดเขียนไฟล์ Checkpoint ทับตรงๆ:
  ```python
  # Legacy Unsafe Write
  with open(checkpoint_path, "w", encoding="utf-8") as f:
      json.dump(checkpoint_data, f)
  ```
- หากโปรเซสถูกตัดการทำงานระหว่างการเขียน (Process Interruption, Out of Memory, ไฟดับ หรือ API แครช) ข้อมูลในไฟล์ JSON จะถูกตัดขาดกลางคัน (Truncated File) ส่งผลให้โครงสร้าง JSON เสียหาย (Invalid JSON Syntax) และข้อมูลการแปลสะสมนับหมื่นแถวสูญหายทันที

#### RCA-3: Queue Pollution & Token Waste (คิวปนเปื้อนข้อมูลขยะ)
- การสร้างคิวส่งแปลเดิมพิจารณาเพียงเงื่อนไข `if not row['Initial']:`
- ส่งผลให้แถวที่ไม่ใช่ภาษาธรรมชาติ เช่น:
  - สัญลักษณ์ควบคุมเปล่าๆ: `"-"`, `"--"`, `"..."`, `"---"`
  - รหัสควบคุมเอนจินเกม: `"\^"`, `"\!"`
  - ข้อมูลตัวเลขเพียวๆ หรือสูตรคำนวณ
  ถูกส่งไปเรียก API ของ LLM ทำให้สิ้นเปลือง Token และเวลาโดยเปล่าประโยชน์ และในบางครั้ง AI ตอบกลับมาเป็นคำอธิบายหรือค่าว่าง ทำให้เกิดความสับสนในระบบ

#### RCA-4: Violations of Fundamental System Principles (No Skip & Timeout Rules)
- ระบบเดิมไม่มีการบันทึก Checkpoint ลงฮาร์ดดิสก์แบบเรียลไทม์เป็นระยะ (Lack of Cadence Checkpointing) ทำให้หากเกิด API Error ที่แถวที่ 500 ข้อมูลแถวที่ 1-499 ที่ยังค้างในหน่วยความจำจะเสี่ยงต่อการสูญหาย
- บางโมดูลแอบตั้งค่า `timeout=30` หรือ `timeout=60` ส่งผลให้เมื่อ AI กำลังสร้างคำตอบบทพูดยาวๆ ระบบตัดการเชื่อมต่อไปเอง ทำให้การแปลล้มเหลว

---

## Decision

เราตัดสินใจปฏิรูปสถาปัตยกรรมการจัดการ State และคิวการแปลใหม่ทั้งหมด โดยกำหนดสถาปัตยกรรม **Atomic Checkpoint Persistence and Pure Untranslated Queue Filtering** บรรจุลงในไปป์ไลน์ **Stage 6 (Persistence & State Synchronization)** โดยมีหลักการ 5 ประการ:

### 1. Two-Way State Synchronization with Cross-Section Consolidation
- ระบบต้องรวมคำแปลจากทุก Section ใน Checkpoint (`SSPV034v1.35 - Trans - Processed_v3.csv`, `SSPV034v1.35 - Trans - Processed_v3_translated.csv` และชื่อไฟล์ปัจจุบัน) เข้าสู่หน่วยความจำกลางแบบ Unified Row Mapping
- เมื่อมีการซ่อมแซมหรือเติมคำแปล ระบบจะต้อง Sync ข้อมูลกลับเข้าสู่ **ทุก Section** ใน Checkpoint พร้อมทั้งเขียนลงไฟล์เป้าหมายเสมอ (Bi-directional Parity)

### 2. Atomic Persistence with Timestamped Snapshots
- การเขียนไฟล์ Checkpoint JSON และ Target CSV ทุกครั้ง **ต้องกระทำแบบ Atomic Operation ผ่าน Temporary File เสมอ**:
  1. สร้างไฟล์ชั่วคราว `.tmp` (เช่น `checkpoint.json.tmp`)
  2. เขียนข้อมูลลงไฟล์ `.tmp` และทำการ `flush()` / `os.fsync()` ให้ข้อมูลลงดิสก์อย่างสมบูรณ์
  3. สลับชื่อไฟล์ด้วย `os.replace(temp_path, target_path)` ซึ่งเป็นการดำเนินการระดับ Atomic ของระบบปฏิบัติการ (OS-level atomic operation)
- ก่อนการเขียนทับทุกครั้ง ต้องสร้าง Timestamped Backup File เสมอ:
  - `target.csv.backup_YYYYMMDD_HHMMSS.csv`
  - `checkpoint.json.backup_YYYYMMDD_HHMMSS.json`

### 3. Strict Pure Queue Filtration (ระบบคัดกรองคิวบริสุทธิ์)
สร้างตัวคัดกรองแถวบทสนทนา (Dialogue Queue Filter) ที่จำแนกประเภทข้อความอย่างแม่นยำ:
- **Translatable Candidate Criteria:**
  1. `Displayable == "Yes"` (ต้องเป็นข้อความที่ผู้เล่นมองเห็นบนจอ)
  2. `Role` ต้องเป็น `Dialogue/Story`, `System/Menu`, หรือ `Skill/Item`
  3. ต้นฉบับ (`Original`) ต้องมีอักขระภาษาธรรมชาติ (อย่างน้อย 1 ตัวอักษรที่ไม่ใช่ตัวเลขหรือสัญลักษณ์ควบคุม)
  4. คอลัมน์ `Initial` ต้องว่างเปล่า หรือยังไม่ผ่านการแปล
- **Auto-Pass Non-Translatable Rules (ข้ามอย่างปลอดภัยโดยไม่ต้องเรียก LLM):**
  - สตริงว่าง หรือช่องว่างล้วน
  - เครื่องหมายขีดหรือสัญลักษณ์เพียวๆ (`-`, `--`, `...`, `---`, `***`)
  - รหัสควบคุมเกมล้วนๆ ที่ไม่มีข้อความมนุษย์
  - สำหรับแถวเหล่านี้ ให้คัดลอกค่าจาก `Original` ไปใส่ `Initial` โดยตรงทันที ไม่ต้องส่งเข้าคิวแปล

### 4. Cadence-Based Checkpointing & Resume Architecture
- ในระหว่างการรันคำสั่งแปลแบบ Batch:
  - ต้องบันทึก Checkpoint ลงดิสก์ทุกๆ $N$ แถวที่แปลเสร็จ (เช่น ทุก 10 แถว หรือทุก 1 นาที)
  - ห้ามเก็บข้อมูลไว้ใน RAM เป็นชั่วโมงๆ เด็ดขาด (State Persistence Principle)
  - เมื่อเปิดสคริปต์รันใหม่ ระบบต้องอ่าน Checkpoint และตรวจสอบสถานะล่าสุดเพื่อทำงานต่อ (Resume) จากจุดที่ค้างอยู่ได้ทันทีในเวลาไม่เกิน 1 วินาที

### 5. Compliance with Fundamental System Principles
- **No API Timeout Limits:** การเรียก LLM API ทุกครั้งต้องกำหนด `timeout=None` อย่างเคร่งครัด
- **No Skip Guarantee:** ห้ามข้ามแถวที่แปลไม่ผ่านเด็ดขาด! หากพบปัญหา 400 Bad Request หรือ API ขัดข้อง ระบบต้องใช้ Adaptive Reduce (หั่นขนาด Prompt) และ Retry จนกว่าจะสำเร็จ หากไม่สำเร็จต้องหยุดทำงาน (Abort) อย่างปลอดภัยโดยบันทึก Checkpoint แถวล่าสุดไว้

---

## Consequences

### Positive
- **100% Recovery of Missing Dialogues:** กู้คืนบทสนทนาที่ตกค้างใน Checkpoint ทั้ง 1,732 แถวกลับเข้าสู่ CSV ตัวไฟนอลได้ครบถ้วน 100%
- **Zero Risk of Data Corruption:** ขจัดความเสี่ยงเรื่อง Checkpoint พังหรือไฟล์ CSV ขาดหายเมื่อเกิดอุบัติเหตุด้วย Atomic File Replacement และ Timestamped Backups
- **Significant Token & Time Savings:** ตัวกรอง Pure Queue Filter ช่วยคัดแยกข้อความที่ไม่จำเป็นต้องแปลออกไป ทำให้ประหยัด Token และลดรอบการเรียก API ลงอย่างมีนัยสำคัญ
- **Instant Resume Capability:** ระบบสามารถหยุดและรันต่อจากจุดเดิมได้ทันที ไม่ว่าจะรันผ่านเครื่องใดหรือหยุดไปนานเท่าใด

### Negative / Trade-offs
- **Disk I/O Overhead:** การสร้าง Timestamped Backup และการเขียนแบบ Atomic ทุกระยะทำให้มีการใช้งานพื้นที่ฮาร์ดดิสก์เพิ่มขึ้นเล็กน้อย (ไฟล์ Checkpoint ขนาด ~15-20 MB ต่อ Backup หนึ่งชุด) ซึ่งแก้ไขได้ด้วยการเพิ่มสคริปต์ทำความสะอาด Backup เก่า (Rotation Policy)

---

## References & Related Architectural Documents
- **SAD-012:** [Fault-Tolerant Translation Runner and State Synchronization Architecture](../architecture/SAD-012-Fault-Tolerant-Translation-Runner-and-State-Sync.md) (พิมพ์เขียวสถาปัตยกรรมระดับระบบของ Stage 6)
- **SDD-014:** [Untranslated Queue Filter and Checkpoint Synchronization Specification](../design/SDD-014-Untranslated-Queue-Filter-and-Checkpoint-Sync-Specification.md) (ข้อกำหนดการออกแบบเชิงวิศวกรรมของตัวกรองและระบบ Sync)
- **ADR-016:** [Smart Line Splitting and Strict Invariant Restoration](ADR-016-Smart-Line-Splitting-and-Strict-Invariant-Restoration.md) (สถาปัตยกรรมจัดระเบียบบรรทัดใน Stage 5 ที่ต้องทำงานร่วมกับการ Sync)
- **SAD-011:** [Typography Alignment and Line-Break Parity Architecture](../architecture/SAD-011-Typography-Alignment-and-Line-Break-Parity.md) (พิมพ์เขียว Stage 5)
- **ADR-010:** [Smart Batching Engine](ADR-010-Smart-Batching.txt) (สถาปัตยกรรมการแบ่ง Batch เพื่อส่งแปล)
- **ARCHITECTURE_INDEX:** [ATF Architectural Master Index](../ARCHITECTURE_INDEX.md) (แผนที่เชื่อมโยงเอกสารทั้งหมดในระบบ)
