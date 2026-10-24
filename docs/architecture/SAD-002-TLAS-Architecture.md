# SAD-002: TLAS Unified Architecture

## 1. Introduction
เอกสาร Software Architecture Document (SAD) ฉบับนี้ อธิบายสถาปัตยกรรมแบบเบ็ดเสร็จของ **Translation Logic and Alignment System (TLAS)** โดยควบรวมกระบวนการทั้ง 2 เฟสเข้าด้วยกัน ได้แก่ **Phase 1: Context Initialization (การเตรียมฐานข้อมูล)** และ **Phase 2: Runtime Translation Pipeline (การดึงข้อมูลไปใช้ขณะแปล)** เพื่อแก้ปัญหาความซ้ำซ้อนของเอกสาร และให้เห็นภาพรวมของระบบทั้งหมดในที่เดียว

## 2. TLAS System Architecture (2-Phase Pipeline)

### Phase 1: Context Initialization (เตรียมวัตถุดิบด้วย RAG-Driven Analysis)
ทำหน้าที่ดึงข้อมูลดิบจากเกมมาสร้างเป็น "Character Knowledge" และ "Story Timeline" โดยอ้างอิงจาก `rpgm_static_routes_v2.json` และ `rpgm_scenes_all_routes.json` เป็นแหล่งความจริงสูงสุด ลำดับการทำงานมีดังนี้:

1. **`rpgm_static_analyzer.py` (Static Dependency Analyzer)**:
   - **Layer 1 (Static Graph Parsing):** อ่าน Event Command แบบ Static เพื่อสร้าง Graph Node จาก Event Pages โดยสกัดเงื่อนไขที่จำเป็น (`pre_conditions`) และสวิตช์/ตัวแปรที่มีผลกระทบ (`post_conditions`)
   - **Layer 2 (WCC Route Clustering):** ใช้อัลกอริทึม Weakly Connected Components (WCC) ในการเชื่อมโยง Edge แบบ `Provider -> Requirer` เพื่อค้นหา Subgraph ที่เป็นอิสระจากกัน ทำให้สามารถแยก Story Clusters (รูทของเกม) ได้อย่างแม่นยำ 100% โดยไม่ต้องใช้ Omni-key จำลองสถานะที่กิน RAM มหาศาล
   - **Layer 3 (Dependency-based Chronological Extraction):** เรียงลำดับเหตุการณ์ในแต่ละ Cluster ตามความสัมพันธ์เชิงพึ่งพา (Dependency Order) และสกัด Dialogue ออกมาตาม Narrative Chronology จริง
   - สกัดออกมาเป็น Cluster (อิงจากโครงสร้างการพึ่งพาของ Switch/Variables ในเกม):
     - แต่ละ Cluster คือกลุ่มเหตุการณ์ที่มีความเกี่ยวข้องกัน เช่น รูทตัวละคร A, รูทตัวละคร B, หรือเส้นเรื่องหลัก
2. **`tlas_initializer.py`**: สแกน `rpgm_scenes_all_routes.json` เพื่อสกัดรายชื่อตัวละคร (คัดกรองขยะด้วย Strict Regex และ V2 Schema) และสร้าง JSON Profile Template เปล่าๆ ทิ้งไว้
3. **`tlas_timeline_generator.py` (Map-Reduce)**:
   - **Map:** ดึงข้อมูล Dialogue จากแต่ละ Cluster โดยใช้เทคนิค **Adaptive Token Packing** (รวบรวมซีนจนกว่า Token จะใกล้เคียง `MAX_PROMPT_TOKENS = 6000`) แล้วส่งให้ LLM สรุปเนื้อเรื่อง โดยมีข้อแม้ว่าห้ามแบ่งข้อมูลใน 1 ซีนแยกไปต่าง Chunk ขาด
   - **Reduce:** นำบทสรุปย่อยมาเรียงลำดับตามโครงสร้าง Graph Dependency ของแต่ละ Cluster แบบเป็นเอกเทศ เพื่อสร้าง **"Timeline แม่ (story_timeline_v2.json)"**
4. **`tlas_analyzer.py` (The RAG Profiler)**: 
   - วนลูปอ่านข้อมูล "Timeline แม่" ทีละ Chunk (รับข้อมูล Summary + Dialogue ดิบ)
   - หาก Token ใหญ่เกินขีดจำกัด จะทำการแตก Sub-batch แบบ Atomic และวิเคราะห์พร้อมทำการ Checkpoint ย่อยระดับ API Call ทันที

### Phase 2: Runtime Translation Pipeline (ตอนแปลจริง)
แทรกอยู่ก่อนสถานะ `TRANSLATING` ใน Event Bus ของ ATF เพื่อทำหน้าที่เสิร์ฟบริบทให้ Translator Agent แบบ "รู้เท่าที่ตัวละครรู้"

```mermaid
flowchart TD
    OS[Original Script] -->|Tokenized| SUM[Summarizer Agent]
    SUM -->|Updates| SC[Situation Context]
    SC --> ANA[Analyzer Agent]
    OS --> ANA
    
    CE[Context Engine\n(Loads Profile & Timeline Phase <= Current)] --> ANA
    
    ANA -->|Extracts| DM[Dialogue Metadata\nJSON]
    DM --> DE[Mapping / Decision Engine\nPython]
    DE -->|Resolves Pronouns & Tone| TG[Translation Guidance]
    
    TG --> TRA[Translator Agent]
```

## 3. Data Flow & Chunking Mechanism

**การแบ่งก้อนข้อมูล (Chunking Strategy & Resilience):**
- ข้อมูลต้นทางคือโครงสร้าง Graph ใน `rpgm_static_routes_v2.json`
- ระบบจะทำการวนลูปและ **Group (จับกลุ่ม)** ออบเจกต์ที่มี `cluster_id` ตรงกันเข้าด้วยกัน 
- แต่ละ `cluster_id` จะถูกซอยย่อยเป็น Chunk แบบ **Adaptive Token Packing** (วัดจาก `tiktoken` แทนการ Fix จำนวนฉาก) 
- ข้อมูลในแต่ละฉากจะถือเป็นหน่วยย่อยที่สุด (Atomic Unit) ห้ามกระจัดกระจายไปอยู่คนละ Chunk (Scene Integrity)
- **1 API Call = 1 Checkpoint:** ระบบมีการ Flush ข้อมูลลงดิสก์ทันทีทุกครั้งที่ API Map ย่อยๆ ทำงานเสร็จ ป้องกัน Data Loss จากการแครชของก้อนข้อมูลขนาดใหญ่

## 4. Anti-Spoiler Injection Rule
เมื่อ `ContextEngine` ทำงานใน Phase 2 มันจะทำการเช็ค `timeline_phase` ของฉากปัจจุบันที่กำลังจะแปล 
สมมติกำลังแปลฉากที่ `timeline_phase = 150`:
- `ContextEngine` จะดึงบทสรุปและ Dialogue ดิบเฉพาะที่ Tag เป็นช่วงเวลา `timeline_phase <= 150` มาแนบเป็น Context เท่านั้น
- ข้อมูลของช่วงเวลาหลังจากนั้น จะถูก Block อย่างเด็ดขาด เพื่อป้องกันไม่ให้ LLM ใช้ข้อมูลอนาคตมาแปลประโยคในปัจจุบัน
