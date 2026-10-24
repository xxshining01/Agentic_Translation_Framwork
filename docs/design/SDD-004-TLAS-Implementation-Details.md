# SDD-004: TLAS Implementation Details

## 1. Introduction
เอกสาร Software Design Document (SDD) ฉบับนี้ อธิบายกลไกเชิงลึกระดับโค้ดของระบบย่อยใน TLAS ได้แก่ การสกัดรายชื่อตัวละคร การทำงานของ Generators (Profiles และ Timeline) รวมถึงเทคนิค Prompt Engineering ที่ใช้ควบคุม LLM

## 2. Speaker Extraction Mechanism (`tlas_initializer.py`)
เพื่อป้องกันปัญหา "ข้อมูลขยะ" (Garbage Data) ที่เกิดจากการกวาด System Commands ของ RPG Maker เข้ามาเป็นชื่อตัวละคร การค้นหา Speaker จะต้องถูกควบคุมด้วย Regular Expression และกฎที่เข้มงวด:

### 2.1 Filtering Rules
1. **Regex Extraction:** ดึงข้อความในวงเล็บเหลี่ยมหน้าสุดของบรรทัด: `^\[(.*?)\]`
2. **Exclusion Criteria (ห้ามดึงถ้าเข้าเงื่อนไขเหล่านี้):**
   - มีความยาวเกิน 30 ตัวอักษร
   - ขึ้นต้นด้วย `c_`, `c\d+` (เช่น `c10120162Window8`)
   - มีคำว่า `Window`, `AUTHETICATION`, `BLANK` หรือเป็นตัวพิมพ์ใหญ่ล้วนยาวๆ
   - มี Escape Codes ของ RPG Maker เช่น `\C[`, `\I[`
   - มีสัญลักษณ์พิเศษที่ไม่ใช่ตัวอักษรหรือตัวเลข (อนุญาตให้มีเว้นวรรคได้ เช่น "Affluent old man")

## 3. Narrative Timeline Generator (`tlas_timeline_generator.py`)
ทำหน้าที่เป็นกระบวนการแรกสุด (หลังจากการสร้างกรอบ JSON เปล่าๆ) เพื่อแก้ปัญหาความยาวของเนื้อเรื่องและจัดเตรียม RAG Chunk ให้พร้อมสำหรับการวิเคราะห์ตัวละคร โดยอ้างอิงการจัดกลุ่มจากข้อมูล `story_phase` และ `timeline_phase` ในไฟล์ `rpgm_scenes_v4.json`

### 3.1 Data Source & Causal Timeline Structure (`rpgm_static_routes_v2.json`)
ไฟล์โครงสร้างเนื้อเรื่องสร้างขึ้นโดย `rpgm_static_analyzer.py` ซึ่งใช้สถาปัตยกรรม **Static Dependency Analyzer**:
1. **Layer 1: Static Parsing:** การอ่าน Event Command ทั้งหมดล่วงหน้าเพื่อสร้าง Graph Node จาก Event Pages โดยสกัดเงื่อนไขการเข้าถึง (`pre_conditions`) และผลกระทบต่อสวิตช์/ตัวแปร (`post_conditions`)
2. **Layer 2: WCC Route Clustering:** ใช้อัลกอริทึม Weakly Connected Components (WCC) ในการเชื่อมโยง Event เข้าหากันผ่าน Edge แบบ `Provider -> Requirer` ทำให้ Event ที่มีความเกี่ยวข้องกัน (เช่น ตัวละครเดียวกัน) ถูกจัดกลุ่มเป็น Cluster แยกกันอย่างเด็ดขาดโดยไม่ต้องจำลองสถานะเกม (Simulator) ซึ่งช่วยลดปัญหา State Space Explosion
3. **Layer 3: Chronological Sorting:** จัดเรียงลำดับเหตุการณ์ในแต่ละ Cluster ด้วยกลไก Topological Sorting-like (อ้างอิงจากลำดับการเปิด Switch) เพื่อให้ Timeline ลำดับเหตุการณ์ถูกต้องตามความเป็นจริง

### 3.2 Map Phase (Adaptive Token Packing & Strict Summarization)
- **Adaptive Data Chunking:** โหลด `rpgm_static_routes_v2.json` และ Group ออบเจกต์ที่มี `cluster_id` เดียวกันเข้าด้วยกัน จากนั้นระบบจะใช้ `tiktoken` คำนวณขนาด Token ของแต่ละฉาก และรวมฉากเข้าเป็น Chunk ย่อยๆ โดยพยายามให้มีขนาดใกล้เคียง `MAX_PROMPT_TOKENS = 6000` มากที่สุด แทนการกำหนดจำนวนฉากตายตัว (Adaptive Token Packing) ข้อมูลที่ส่งให้ LLM จะเป็น **Array of Dialogue Objects** ของก้อนนั้นๆ
- **Scene Integrity Rule:** กฎเหล็กคือ ข้อมูลในแต่ละฉากจะถูกมองเป็นหน่วยย่อยที่สุด ห้ามมีการหั่นแยกข้อมูลใน 1 ฉากไปอยู่ต่าง Chunk กันเด็ดขาด เพื่อป้องกันปัญหา Timeline ผิดเพี้ยน
- **Prompt (Strict Summarization):** สั่งให้ LLM สรุปเนื้อหาของ Chunk นั้นๆ โดยบังคับว่าต้องมีรายละเอียดครบถ้วน: "ใคร" "ทำอะไร" "กับใคร" "เพราะอะไร" "ที่ไหน" "เมื่อไหร่" "อย่างไร" "ผลลัพธ์เป็นอย่างไร" "มีใครเกี่ยวข้องบ้าง" พร้อมติด Timeline Tag
- **Output:** บันทึกไฟล์ลง `data/tlas/timeline_chunks_v2/chunk_{cluster_id}_{id:04d}.json` โดยในไฟล์จะประกอบด้วย **"บทสรุป (Summary)"** คู่กับ **"Dialogue ดิบ (Raw Dialogues)"** ของ Chunk นั้น

### 3.3 Reduce Phase (Per-Cluster Causal Assembly)
- อ่านบทสรุปที่ได้จาก Map Phase ของทุก Chunk ตามลำดับ `cluster_id`
- ทำการ Reduce เนื้อเรื่องของ "แต่ละ Cluster อย่างเป็นเอกเทศ" ไม่นำไปปะปนกับ Cluster อื่น
- **Output:** บันทึกลง `data/tlas/story_timeline_v2.json`

## 4. Two-Phase Map-Reduce Character Knowledge Pipeline

เพื่อแก้ไขปัญหาการสร้าง Character Profiles ขยะนับร้อยตัว และลดจำนวน API Calls รวมของทั้งโปรเจกต์ลงอย่างมหาศาล ระบบ TLAS จึงใช้สถาปัตยกรรม **Map-Reduce Character Knowledge Pipeline (ADR-004, ADR-014, SAD-006, SDD-009)**:

### 4.1 Map Phase: Lean & Fast Scene Analysis (`tlas_analyzer.py`)
ทำหน้าที่สกัดพัฒนาการและเหตุการณ์สำคัญรายฉาก (`timeline_states delta`) ให้กับตัวละครใน Whitelist:
- **Canonical Whitelist Single Source of Truth:** โหลดรายชื่อตัวละครที่ถูกต้องจาก `tlas_glossary.json` เพื่อใช้เป็น Whitelist บังคับ
- **Token-Aware Large Sub-Chunking (`SAFE_LIMIT = 7000 - 8000`):** ขยายขนาด sub-chunk ขึ้นเป็น 7,000-8,000 ตัวอักษร เพื่อลดจำนวนรอบ API Call รวมลงกว่า 5-6 เท่า
- **3-Stage Lean Pipeline:**
  1. **Stage 1 (Speaker ID):** ใช้ LLM สกัดเฉพาะตัวละครที่อยู่ใน Whitelist หากไม่มีตัวละครใน Whitelist พูดในฉากนั้น ระบบจะทำ **Zero-Character Fast-Skip** ข้าม Stage 2 ทันทีโดยไม่ต้องเสีย API Call
  2. **Stage 2 (Lean Focused Psychological & 4D Analysis):** ส่งวิเคราะห์เฉพาะจิตวิทยาและ 4D Relationship ของตัวละครเป้าหมายในฉากนั้น โดยตัดการป้อน Pronoun Hints ออกจาก Prompt เพื่อประหยัด Token และมุ่งเน้นเฉพาะ "เกิดอะไรขึ้นในฉากนั้น" (`timeline_states delta`)
  3. **Stage 3 (Derived Speech Mapping):** ใช้ Python Priority Rule Engine คำนวณ `specific_speech` ชั่วคราวสำหรับการใช้งานเบื้องต้น
- **Profile Writer Filter Guard:** ป้องกันไม่ให้ตัวละครนอก Whitelist หรือ Placeholder ขยะ ถูกบันทึกลงฮาร์ดดิสก์ และบันทึก `timeline_states` แบบ Atomic Write ทันทีทุกฉาก

### 4.2 Reduce Phase: Global Character Profile Synthesis (`tlas_profile_consolidator.py`)
ทำหน้าที่สังเคราะห์และสร้าง Root Base Profile (`base_state`, `identity`, `base_speech_style`) เมื่อ Map Phase กวาดอ่านข้อมูลครบแล้ว:
- **Character Evidence Harvesting:** รวบรวมทุกประโยคที่พูดจริง, สถิติสรรพนามจริงจาก TH Legacy และประวัติ `timeline_states` ทั้งหมดของตัวละคร
- **Global Perspective LLM Synthesis (1 Call ต่อ 1 ตัวละคร):** ส่งแฟ้มประวัติรวมให้ LLM วิเคราะห์หาตัวตนแกนกลางที่แท้จริง (Core Baseline) โดยแยกแยะพฤติกรรมปกติออกจากพฤติกรรมเฉพาะสถานการณ์
- **Deterministic Recalibration (Pure Python):** ใช้ Priority Rule Engine คำนวณ `base_speech_style` และ Re-calculate `specific_speech` ในทุก `timeline_states` ใหม่อัตโนมัติในเวลาไม่ถึง 1 วินาที โดยไม่ต้องยิง LLM ซ้ำ
- **Atomic Base Update:** อัปเดต Root Profile โดยยังคงรักษาประวัติ `timeline_states` เดิมไว้ครบถ้วน 100%

### 4.3 Recursive Adaptive Fallback (API Limit Protection)
เพื่อรับมือกับข้อจำกัด Context Window ของ LM Studio:
- **Batch Halving:** หาก LLM คืนค่า 400 Bad Request ระบบจะดักจับและทำการ **"หั่นครึ่ง (Halving)"** รายชื่อฉากออกเป็นสองฝั่ง และส่งยิง API ใหม่แบบ Recursive
- **Line-Based Scene Splitting:** หากหั่นจนเหลือ `len(raw_dialogues) == 1` แต่ฉากนั้นยาวเกินไป ระบบจะทำการ **หั่นบรรทัดในบทสนทนาตรงกลาง (Split by newline)** ออกเป็น 2 ฉากจำลอง เพื่อให้ LLM ได้อ่านครบทุกบรรทัดโดยไม่เสีย Context สำคัญไปแม้แต่บรรทัดเดียว!

## 5. RAG Integration (`ContextEngine`)
เมื่อ `ContextEngine.build_context(scene_data)` ถูกเรียก:
1. ตรวจสอบว่า `scene_data` อยู่ใน `timeline_phase` ใด
2. โหลด `story_timeline.json` และกรองเอาเฉพาะ Timeline Phase ก่อนหน้า (`timeline_phase <= current`) 
3. แทรกลงไปใน `ContextData` เพื่อส่งให้ Translator Agent รู้ว่าตัวละครนี้ผ่านอะไรมาแล้วบ้าง

## 6. Resilience, Checkpointing, and Pre-Filtering Mechanisms
เพื่อรองรับการประมวลผลข้อมูลขนาดใหญ่ที่กินเวลาหลายชั่วโมงและป้องกันการสูญเสียข้อมูลจากเหตุสุดวิสัย (ไฟดับ, 400 Bad Request, API Hang) ระบบจึงถูกออกแบบสถาปัตยกรรมความทนทานไว้ดังนี้:

### 6.0 หลักการพื้นฐาน: 1 API Call = 1 Disk Write
**กฎเหล็กของทุก RAG Engine:** ทุกครั้งที่ได้รับ Response จาก LLM ต้องบันทึกลงฮาร์ดดิสก์ทันทีด้วย **Atomic Write** (`write .tmp` → `os.replace()`) เพื่อป้องกัน:
- ข้อมูลค้างอยู่ใน RAM และหายเมื่อระบบขัดข้อง
- ไฟล์ JSON Corruption กรณีระบบพังกลางการเขียน
- ต้องให้ AI ประมวลผลงานซ้ำที่ทำเสร็จแล้ว

### 6.1 Checkpoint Architecture (ระดับ Per-API-Call)

#### Engine 1: `tlas_timeline_generator.py` — Map Phase & Reduce Phase

| ขั้นตอน | Checkpoint | รูปแบบ |
|--------|------------|--------|
| **Map Phase** (Chunk Summarization) | `timeline_chunks_v2/chunk_{cluster}_{id:04d}.json` | บันทึกทันทีหลังแต่ละ chunk summary (Adaptive limit 6000 tokens) — skip ถ้า `summary` ไม่ว่าง |
| **Output รวม** | `story_timeline_v2.json` | สร้างไฟล์สมบูรณ์ทันทีหลังกระบวนการ Reduce ภายในเสร็จสิ้น ไม่ต้องรอรันสคริปต์แยก |

#### Engine 2: `tlas_analyzer.py` — Per-Scene Profile Analysis

| ขั้นตอน | Checkpoint | รูปแบบ |
|--------|------------|--------|
| **LLM Response Cache** | `llm_cache.json` | Atomic write ทันทีหลัง API Call ทุกครั้ง |
| **Per-Scene Completion** | `analyzed_scenes.log` | บันทึก `{chunk_basename}_scene_{s_idx}_sub_{c_idx}` ทันทีหลังเขียน Profile สำเร็จ |
| **Profile JSON** | `profiles/{CharacterName}.json` | Atomic write ทันทีหลังทุก API Call — ไม่รอ batch ครบ |
| **Chunk Completion** | `analyzed_chunks.log` | บันทึกเมื่อ **ทุก scene ใน chunk นั้น** เสร็จครบแล้ว |

**กลไก Skip ระดับ Scene:** เมื่อรันต่อ ระบบตรวจสอบ `analyzed_scenes.log` ก่อนส่ง API — ถ้า scene นั้นเขียน Profile เรียบร้อยแล้ว จะข้ามทั้ง API Call และ Disk Write ทันที

#### Engine 3: `tlas_chunk_repair.py` — Empty Chunk Repair & Phase 2 Reduce

| ขั้นตอน | Checkpoint | รูปแบบ |
|--------|------------|--------|
| **Repair Batch Summary** | `repair_checkpoints/{chunk_name}/batch_{j:04d}.txt` | Atomic write ทันทีหลังทุก batch API Call |
| **Phase 2 Level-1 Batch** | `reduce_checkpoints/phase2_batches/level1_batch_{i:04d}.txt` | Atomic write ทันทีหลัง compress แต่ละ batch |
| **Chunk JSON (หลัง repair)** | `timeline_chunks/chunk_*.json` | Atomic write หลัง final reduce เสร็จ |
| **Output รวม** | `story_timeline.json` | Atomic write หลัง Phase 2 reduce เสร็จ |

#### Checkpoint Directory Structure
```
data/tlas/
├── profiles/                        ← Profile JSON (Atomic write ทันทีทุก API Call)
├── timeline_chunks_v2/              ← Chunk JSON (Atomic write ทันทีทุก chunk)
├── llm_cache.json                   ← API Response Cache (Atomic write ทันทีทุก call)
├── analyzed_chunks.log              ← Chunk-level completion log
├── analyzed_scenes.log              ← Batch-level completion log (per-batch atomic skip)
├── reduce_checkpoints/
│   ├── phase_0_final.json           ← Phase 0 reduce result
│   ├── phase_1_final.json           ← Phase 1 reduce result
│   ├── phase_2_final.json           ← Phase 2 reduce result (from timeline_gen)
│   └── phase2_batches/              ← Per-batch Phase 2 reduce checkpoints
│       ├── level1_batch_0000.txt
│       └── level1_batch_0001.txt
└── repair_checkpoints/              ← Per-batch repair checkpoints
    └── chunk_p2_0038/
        ├── batch_0000.txt
        └── batch_0001.txt
```

### 6.2 Proactive Token Pre-Filtering
เพื่อป้องกันไม่ให้ Request ทะลุ Context Length Limit (8192) ของโมเดลแบบ Local ระบบจะคำนวณ Token ของ Prompt "ทั้งหมด" (รวม System Prompt + กฎ + ข้อมูล + Glossary) ด้วย `tiktoken` (cl100k_base) ก่อนยิง API
- **สมการหา Safe Limit:** `Max Context (8192) - Response Space (e.g. 1500) = Safe Limit (6692)`
- หากนับ Token แล้วเกิน Safe Limit ระบบจะทำ **Proactive Splitting** (หั่นก้อนข้อมูลออกเป็นสองส่วนแล้วประมวลผลแยกกัน) ทันทีตั้งแต่ก่อนยิง API เพื่อหลีกเลี่ยง Error 400 ล่วงหน้า

### 6.3 Reactive Adaptive Fallback & Hang Protection
- **Timeout Trap:** การเชื่อมต่อ API ถูกตั้งค่า Timeout ไว้ (เช่น 3 นาที) หากโมเดล Local เกิดอาการค้าง (Infinite Generation Loop) โค้ดจะตัดการเชื่อมต่อและถือว่าเป็น Error
- **Recursive Splitting:** หากเกิด Error ใดๆ ระหว่างประมวลผล (รวมถึง 400 Bad Request) ระบบจะกระโดดเข้าโหมด Fallback เพื่อหั่นข้อมูล (Batches/Dialogues) ออกเป็นสองส่วนและทำ Recursive Call จนกว่าจะเล็กพอที่ AI จะประมวลผลได้สำเร็จ
