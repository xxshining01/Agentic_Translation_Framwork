# Software Architecture Document (SAD)

**หมายเลขเอกสาร:** SAD-010 (v4.1 Calibrated)  
**ชื่อระบบ:** TLAS Global-Relational Localization Architecture (Decoupled & Zero-Fallback Standard)  
**สถานะ:** Approved Architecture  
**วันที่:** 2026-11-01  
**เอกสารอ้างอิง:** ADR-015, ADR-025, ADR-035, SDD-005, SDD-010, SDD-011  

---

## 1. บทนำและวิสัยทัศน์ของระบบ (System Overview & Architectural Vision)

สถาปัตยกรรม **TLAS v4.1 (Decoupled Global-Relational Architecture)** ถูกปรับปรุงขึ้นเพื่อแก้ปัญหาความสับสนระหว่างฐานข้อมูลคำศัพท์ (Glossary) และโปรไฟล์ตัวละคร (Character Profiles) รวมถึงกำจัดกับดักการเดาสรรพนามอัตโนมัติ (Default Polite Male Trap) ที่สร้างความเสียหายให้กับงานแปล โดยยึดหลักการแยกชั้นข้อมูลอย่างเด็ดขาด (Decoupled Layering):

### แกนหลักของสถาปัตยกรรม (Core Architectural Pillars)
1. **Decoupled Glossary vs. Profiles (ADR-035):**
   - **Layer 1: Master Glossary (`tlas_glossary.json`):** เก็บรวบรวมชื่อทั้งหมดใน Speaker Tags ของทั้งเกม 100% เพื่อล็อกคำแปล 1:1 ป้องกันการทับศัพท์ผิด
   - **Layer 2: Character Profiles (`profiles/<Name>.json`):** สังเคราะห์เฉพาะ **ตัวละครสำคัญแท้จริง (Core/Main Cast ~30-50 ตัวละคร)** ที่มีบทบาทขับเคลื่อนเนื้อเรื่อง ตัวประกอบทั่วไป (Ambient NPCs) ต้องไม่มีไฟล์ Profile เด็ดขาด
2. **Zero Fallback & Anti-Politeness Bias (Zero-Hardcode Invariant):**
   - ห้ามเดาหรือ Fallback ตัวละครที่ไม่ทราบนิสัยให้กลายเป็น "ชายสุภาพ (ผม/คุณ/ครับ)" โดยเด็ดขาด
   - หากตัวละครสำคัญใดไม่ทราบเพศแน่ชัด ให้ใช้ Neutral Speech Register (`ฉัน/เธอ/นาย`) ไร้หางเสียงจนกว่าจะมีหลักฐานยืนยัน
3. **Clean Passthrough Runtime:** ในขั้นตอนการแปล หากตัวละครใดไม่มี Profile ระบบจะส่งเฉพาะชื่อที่ล็อกตาม Glossary + บริบทฉาก โดยปล่อยให้ AI แปลน้ำเสียงตามธรรมชาติ ไม่ส่ง Profile กลวงไปหลอก AI
4. **Persistent Invariant Prompting:** ทุกๆ พร็อมพ์ที่ส่งไปแปล (รวม Follow-up) ต้องมี Mini-System Invariant กำกับความยาวบรรทัด (~40-48 ตัวอักษร) และคงสภาพ Tag 100%
5. **Macro-Level Parameter Consensus:** รวมผลลัพธ์พารามิเตอร์เฉพาะตัวละครสำคัญจากทุก Chunk แล้วหาค่าเฉลี่ยทางสถิติ (Majority Vote / Weighted Mode) ใน Python
6. **Deterministic Taxonomy Mapping:** แปลงค่าเฉลี่ยของพารามิเตอร์ไปเป็นคำสรรพนามบุรุษที่ 1, 2, 3 และคำลงท้าย ผ่านกฎเกณฑ์ที่ชัดเจนใน Python ก่อนเริ่มขั้นตอนแปลจริง


---

## 2. ผังการทำงานและท่อส่งข้อมูล (Data Flow & Pipeline Stages)

```mermaid
flowchart TD
    subgraph Stage1["Stage 1: Map Phase (Independent Chunk Extraction)"]
        A["Raw Script Chunks<br>(Unordered / Parallelizable)"] --> B["LLM Feature Extractor<br>(tlas_analyzer)"]
        B -->|ส่งกลับเฉพาะ Abstract Tags| C["Chunk Extraction JSON<br>- Personality, Speech Habits, Values<br>- 4D Relationships (Roles, Affinity, Intimacy, Power)<br>- Scene Summary & Emotion/Tone"]
    end

    subgraph Stage2["Stage 2: Reduce Phase (Python Parameter Consensus)"]
        C --> D["Consensus Aggregator<br>(tlas_profile_consolidator)"]
        D -->|รวบรวมครบทุก Chunk ทั้งโปรเจกต์| E["Aggregated Trait Histogram &<br>Pairwise Relationship Graph"]
    end

    subgraph Stage3["Stage 3: Deterministic Pronoun Resolution"]
        E --> F["Taxonomy Rule Engine<br>(Deterministic Python Logic)"]
        TaxonomyJSON["taxonomy_v3.5.json"] --> F
        F --> G["Final Consolidated Character Profiles<br>(data/tlas/profiles/*.json)"]
    end

    subgraph Stage4["Stage 4: Translation Runtime Context Injection"]
        G --> H["Translator Engine Prompt"]
        SceneCtx["Direct Scene Context"] --> H
        EmoTone["Dialogue Emotion/Tone"] --> H
        RawLine["Dialogue Line to Translate"] --> H
        H --> FinalTH["Consistent Thai Game Localization"]
    end
```

---

## 3. รายละเอียดขั้นตอนการทำงาน (Pipeline Breakdown)

### Stage 1: Map Phase — Chunk-level Abstract Feature Extraction
- **Input:** ชิ้นส่วนบทสนทนา (Chunks) โดยไม่จำเป็นต้องเรียงตามลำดับเนื้อเรื่อง
- **กระบวนการ:**
  1. LLM อ่านเนื้อหาบทสนทนาและบริบทเฉพาะหน้าใน Chunk
  2. สกัดพารามิเตอร์เชิงนามธรรมของตัวละครที่ปรากฏใน Chunk ตาม Taxonomy v3.5:
     - `personality`: Array ของ `{"tag": PER_*, "weight": int}`
     - `speech_habit`: Array ของ `{"tag": SPR_*, "weight": int}`
     - `values`: Array ของ `{"tag": VAL_*, "weight": int}`
     - `relationships`: ข้อมูลความสัมพันธ์ต่อคู่สนทนา (`roles`, `affinity`, `intimacy`, `power_dynamic`)
     - `scene_context`: สรุปสถานการณ์เฉพาะหน้าในฉากนั้น
     - `dialogue_emotions`: ระดับอารมณ์และน้ำเสียงของแต่ละประโยค (`EMO_*`, `TON_*`)
  3. **ข้อห้ามเด็ดขาด:** LLM ต้องไม่สร้างหรือเสนอคำสรรพนามภาษาไทย (เช่น ผม, ฉัน, มึง, กู) ในขั้นตอนนี้

### Stage 2: Reduce Phase — Project-wide Parameter Aggregation (Python)
- รันหลังจาก LLM ประมวลผลเสร็จสิ้นครบทุก Chunk ของโปรเจกต์
- Python รวมข้อมูลพารามิเตอร์ของตัวละครแต่ละตัวจากทุกไฟล์:
  - **Personality / Values / Habits:** คำนวณความถี่และค่าน้ำหนักเฉลี่ย (Weighted Frequency Score) คัดเลือกเฉพาะ Top Tags ที่สะท้อนตัวตนแกนกลางของตัวละคร
  - **Relationships (Directed Pairwise Graph):** รวมข้อมูลการปฏิสัมพันธ์ระหว่างคู่ตัวละคร $A \to B$ เพื่อหาค่า Consensus ของ `roles`, `affinity`, `intimacy`, และ `power_dynamic`

### Stage 3: Deterministic Pronoun Resolution (Python Rule Engine)
- นำค่าเฉลี่ยของ Trait และ Relationship ที่สรุปได้ เข้าสู่กระบวนการแมปคำสรรพนามตาม Taxonomy:
  - **Base Speech Style:** สรรพนามพื้นฐานเมื่อพูดทั่วไปหรือคุยกับคนแปลกหน้า (`self_pronoun`, `target_pronoun`, `third_person_pronoun`, `ending_particle`, `formality_level`)
  - **Pairwise Specific Speech Style:** สรรพนามเฉพาะที่ตัวละคร $A$ ใช้กับตัวละคร $B$ โดยพิจารณาจาก 4 มิติความสัมพันธ์:
    - สรรพนามบุรุษที่ 1 (`self_pronoun`): คำแทนตัวเองที่ $A$ ใช้เมื่อคุยกับ $B$
    - สรรพนามบุรุษที่ 2 (`target_pronoun`): คำที่ $A$ ใช้เรียก $B$
    - สรรพนามบุรุษที่ 3 (`third_person_pronoun`): คำที่ $A$ ใช้เรียกบุคคลอื่นเมื่อสนทนากับ $B$ หรือเมื่อกล่าวถึง $B$
    - คำลงท้าย (`ending_particle`): หางเสียงที่ $A$ ใช้กับ $B$
    - ระดับความเป็นทางการ (`formality_level`): ค่าระดับ 1 - 5 (หรือ 1 - 10)
- บันทึกผลลัพธ์เป็น Character Profile สมบูรณ์ลงดิสก์ (`data/tlas/profiles/<Name>.json`)

### Stage 4: Translation Runtime Context Injection
เมื่อเข้าสู่ขั้นตอนการแปลจริง โมเดลแปลจะได้รับ Context ที่กระชับและตรงจุด:
1. **Speaker Profile:** ตัวตนและสไตล์การพูดพื้นฐานของผู้พูด
2. **Pairwise Relationship:** สรรพนามที่ผู้พูด ($A$) ต้องใช้กับผู้ฟัง ($B$) ในฉากนั้น (บุรุษที่ 1, 2, 3 และคำลงท้าย)
3. **Direct Scene Context:** บริบทเหตุการณ์เฉพาะหน้าของฉาก
4. **Dialogue Tone & Emotion:** อารมณ์เฉพาะของประโยคเพื่อปรับแต่งรูปประโยคให้มีชีวิตชีวา

---

## 4. คุณสมบัติเชิงสถาปัตยกรรม (Architectural Quality Attributes)

1. **Scalability & Concurrency:** การตัด Timeline Dependency ทำให้การประมวลผล Chunk ทำงานแบบขนานได้อย่างสมบูรณ์ (Massive Parallel Processing)
2. **Determinism & Consistency:** ปัญหาสรรพนามแกว่งถูกกำจัดด้วยการใช้อัลกอริทึมทางสถิติและ Rule-based Logic ควบคุมแทนการเดาของ LLM
3. **Fault Tolerance & Resilience:** สามารถ Checkpoint และ Resume ได้ทุกขั้นตอน Chunk ใดล้มเหลวสามารถประมวลผลซ้ำเฉพาะ Chunk นั้นได้โดยไม่กระทบโครงสร้างของทั้งเรื่อง
4. **Human-in-the-Loop Friendly:** ตารางสรุป Pronoun และ Relationship Matrix สามารถนำออกมาแสดงผลให้ผู้ใช้ตรวจสอบและปรับแก้ (Manual Override) ก่อนเริ่มแปลได้ในจุดเดียว
