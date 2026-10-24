# ADR-004: TLAS Narrative Timeline and Map-Reduce Summarization

## Status
Approved

## Context
ในระหว่างการพัฒนาระบบ Translation Logic and Alignment System (TLAS) สำหรับ Agentic Translation Framework (ATF) เราเผชิญปัญหา 3 ประการหลัก:
1. **Context Window Exhaustion:** บทสนทนาในเกมมีปริมาณมหาศาล (มากกว่า 90,000 บรรทัด และมีฉากกว่า 6,000 ฉาก) การนำเข้าข้อมูลทั้งหมดให้ LLM ประมวลผลรวดเดียวเพื่อสร้าง "บทสรุป" และ "เส้นเวลา (Timeline)" เป็นไปไม่ได้ในทางปฏิบัติ เนื่องจากข้อจำกัดของ Context Window
2. **Gameplay Progression vs Narrative Chronology:** ระบบเกมปลดล็อกเนื้อเรื่องตามเงื่อนไข (Gameplay Variables/Switches) ซึ่งสามารถกระโดดข้ามเส้นเวลาได้ (เช่น การเล่าย้อนอดีต ฉากความทรงจำวัยเด็ก 3 -> 4 -> 1 -> 2 -> 5) แต่ในการแปลวรรณกรรม (Narrative Translation) AI จำเป็นต้องรู้เส้นเวลาที่แท้จริงตามที่ตัวละครได้ประสบพบเจอมา (1 -> 2 -> 3 -> 4 -> 5) เพื่อให้เข้าใจถึงแรงจูงใจ (Motivations) และการเติบโตของตัวละคร (Character Arc) ได้อย่างลึกซึ้ง
3. **LLM Hallucinations on Structural Tasks:** การปล่อยให้ LLM กำหนดโครงสร้างตัวละคร (Character Profiles) หรือกำหนดลำดับเหตุการณ์เอง ทำให้เกิดผลลัพธ์ที่เป็นข้อมูลขยะ, ข้อมูลที่ไม่คงเส้นคงวา (Inconsistent), หรือการทิ้งตัวแปรจำเป็นอย่างการระบุเพศ/เผ่าพันธุ์

## Decisions

### 1. การสกัดเนื้อเรื่องด้วย Static Dependency Graph (WCC) และ Map-Reduce
เพื่อแก้ปัญหา Context Window และข้อจำกัดด้าน RAM (State Space Explosion) จากการรันแบบ State Simulator เราจึงเปลี่ยนมาใช้สถาปัตยกรรม **Static Dependency Analyzer** (`rpgm_static_analyzer.py`) อ้างอิงจากข้อมูลเกมใน `rpgm_static_routes_v2.json` และ `rpgm_scenes_all_routes.json` โดยมีกลไกดังนี้:
- **Layer 1 (Static Graph Parsing):** อ่าน Event Command ทั้งหมดแบบ Static เพื่อสร้าง Graph Node จาก Event Pages โดยสกัดเงื่อนไขที่จำเป็นต้องใช้ (`pre_conditions`) และสวิตช์/ตัวแปรที่มีการอัปเดต (`post_conditions`) เพื่อเชื่อม Edge แบบ `Provider -> Requirer`
- **Layer 2 (WCC Route Clustering):** ใช้อัลกอริทึม Weakly Connected Components (WCC) ค้นหา Subgraph ที่เป็นอิสระจากกันเพื่อจัดกลุ่ม Event ให้เป็น Story Clusters (จำแนกรูทเนื้อเรื่อง) แทนการทำ Omni-key BFS Exploration ที่กินทรัพยากรสูง
- **Layer 3 (Dependency-based Chronological Extraction):** สกัดและเรียงลำดับ Dialogue ในแต่ละ Cluster ตามความสัมพันธ์เชิงพึ่งพา (Dependency Order) ทำให้ลำดับเหตุการณ์ถูกต้องตาม Narrative Chronology จริง
- **Map Phase (การสรุปก้อนย่อย):** ใช้เทคนิค **Adaptive Token Packing** โดยใช้ `tiktoken` คำนวณขนาด Token ของแต่ละฉากก่อนที่จะนำไปรวมเป็น Chunk (แทนการกำหนด `CHUNK_SIZE` ตายตัว) เพื่อป้อนให้ LLM โดยมีกฎเหล็ก **Scene Integrity Constraint** คือห้ามแยกข้อมูลในแต่ละฉากไปอยู่ต่าง Chunk เด็ดขาด (แม้ฉากจะใหญ่จนต้องแตกฉากย่อย ฉากย่อยทั้งหมดต้องอยู่ใน Chunk เดียวกัน) เพื่อป้องกัน Timeline ผิดเพี้ยน
- **Reduce Phase (การจัดเรียง Timeline แม่):** รวมบทสรุปย่อยของแต่ละ Cluster แยกออกจากกันอย่างเป็นเอกเทศ (Per-Cluster Reduction) เพื่อสร้าง "Timeline แม่ (Story Timeline V2)" โดยห้ามเกิดการปะปนกันของเนื้อเรื่องต่างรูท

### 2. สถาปัตยกรรม Map-Reduce Character Knowledge Pipeline
เพื่อแก้ปัญหาการระเบิดของจำนวน API Calls, ปัญหาการสร้าง Profile ขยะ และปัญหา Sequential Cold-Start Lock-in เราใช้สถาปัตยกรรม **Map-Reduce Character Knowledge Pipeline (ADR-014, SAD-006, SDD-009)**:
- **Map Phase: Lean Scene-Level Extraction (`tlas_analyzer.py`):**
  - กวาดอ่านบทสนทนารายฉากและสกัดพัฒนาการทางอารมณ์/ความสัมพันธ์ (`timeline_states delta`) ให้กับตัวละครใน Whitelist จาก `tlas_glossary.json`
  - ใช้ **Token-Aware Large Sub-Chunking (`SAFE_LIMIT = 7000 - 8000`)** เพื่อลดจำนวนรอบ API Call รวมของทั้งเกมลงอย่างมหาศาล
  - ใช้ **Zero-Character Fast Skip** เพื่อข้ามฉากที่ไม่มีตัวละคร Whitelist ปรากฏตัวทันทีโดยไม่ต้องเสียเวลาประมวลผล Stage 2
  - ส่งวิเคราะห์เฉพาะจิตวิทยาและ 4D Relationship โดยตัด Pronoun Hints และข้อมูล Profile ที่เทอะทะออกจาก Prompt เพื่อประหยัด Token สูงสุด
- **Reduce Phase: Global Character Profile Synthesis (`tlas_profile_consolidator.py`):**
  - รวบรวมแฟ้มประวัติรวม (Comprehensive Dossier) ของตัวละครแต่ละตัวตลอดทั้งเรื่อง (บทพูดเด่น, สถิติสรรพนาม TH Legacy จริง, Trait Histogram)
  - ใช้ LLM สังเคราะห์ **Core Baseline Identity & Personality** เพียง **1 Call ต่อ 1 ตัวละคร** ในมุมมอง Global Perspective
  - ใช้ **Deterministic Priority Rule Engine** คำนวณ `base_speech_style` และ Re-calculate `specific_speech` ในทุก `timeline_states` ใหม่อัตโนมัติในเวลาเสี้ยววินาทีโดยไม่ต้องรัน LLM ซ้ำ
  - อัปเดต Root Base Profile แบบ Atomic Write โดยคงประวัติศาสตร์ `timeline_states` ทั้งหมดไว้ครบถ้วน 100%

### 3. การเก็บ Dialogue ดิบเป็นบริบทคู่ขนาน (Raw Dialogue Retention)
เราจะไม่พึ่งพาแค่ "บทสรุป" เพียงอย่างเดียว แต่จะเก็บ **Dialogue ดิบทั้งหมดที่ยังไม่ผ่านการสรุป** (พร้อมติด Tag ช่วงเวลา) ไว้เป็นข้อมูลอ้างอิงเคียงคู่กับบทสรุปด้วย การมี Dialogue ดิบให้ LLM (Translator Agent) อ่าน จะช่วยให้เข้าใจบริบท น้ำเสียง และบรรยากาศรอบข้างได้ดีกว่าการอ่านแค่เนื้อหาสรุปที่อาจตัดทอนอารมณ์ออกไป

### 4. ระบบ Anti-Spoiler Context Injection (รู้เท่าที่ตัวละครรู้)
Timeline Tags ที่ติดไว้กับทั้งบทสรุปและ Dialogue ดิบ จะถูกนำไปย้อนรอย (Map) กับ Dialogue ที่กำลังจะถูกแปล เมื่อ ATF จะทำการแปลเหตุการณ์ใน Timeline แม่ช่วงที่ 150 ระบบจะป้อน Context เฉพาะช่วงที่ `timeline_phase <= 150` เท่านั้น ห้ามป้อนข้อมูลจากช่วงหลังจากนั้นเด็ดขาด 
**เหตุผล:** เพื่อให้ ATF (Translator Agent) เข้าใจเรื่องราวความเป็นมาและวิเคราะห์บริบทได้อย่างถูกต้อง "แต่ไม่ล้ำหน้า" จนเผลอสปอยล์เนื้อหา หรือใช้ข้อมูลอนาคตมาตัดสินใจการแปลในปัจจุบัน (ตัวละครรู้อะไร AI รู้แค่นั้น)

### 5. บังคับใช้ JSON Template และ Strict Taxonomy
เราตัดสินใจเลิกให้ LLM เป็นผู้กำหนดโครงสร้าง JSON และคำศัพท์เองอย่างอิสระ:
- บังคับใช้แม่แบบ `character_profile_template.json` อย่างเคร่งครัด
- LLM จะต้องเลือกค่า (Values) มาเติมจาก **Comprehensive Taxonomy Dictionary (SDD-005)** เท่านั้น ห้ามคิดคำศัพท์เอง (เช่น ห้ามใช้ `lovely`, ต้องใช้ `PER_VIBE_CUTE` เท่านั้น) เพื่อให้ระบบ Mapping ทางฝั่ง Python สามารถจับคู่ค่าได้อย่างแม่นยำ 100%

## Consequences
**Positive:**
- สามารถประมวลผลข้อมูลปริมาณมหาศาลได้โดยไม่เสี่ยงต่อการหลอน (Hallucinations) หรือ Context Overload
- ระบบมีความยืดหยุ่นต่อความผิดพลาด (Resilient) ในระดับ **Per-API-Call**: ทุก Engine บันทึกผลลัพธ์ลงดิสก์ทันทีหลังทุก Response ที่ได้จาก LLM (1 API Call = 1 Checkpoint) เพื่อป้องกัน Data Loss จากเหตุขัดข้องกลางคัน
  - **`tlas_timeline_generator.py`:** บันทึก chunk (Batch ระดับ 6000 Tokens) ลงดิสก์ทันทีหลัง API Map ตอบกลับ, และบันทึก Per-Cluster checkpoint ทันทีหลัง Reduce
  - **`tlas_analyzer.py`:** บันทึก LLM Cache + Profile JSON + `analyzed_scenes.log` ทันทีหลังทุก Batch API Call — สามารถ Resume ได้ระดับ Batch/Scene อย่างแนบเนียน
  - **`tlas_chunk_repair.py`:** บันทึก Per-Batch checkpoint ทันทีทั้ง repair และ Phase 2 reduce
- งานแปลจะมีคุณภาพสูงขึ้นอย่างมาก เนื่องจาก Translator Agent จะได้รับข้อมูล Context ในส่วนของ "อดีตและประสบการณ์" ที่ตัวละครเคยเจอตามลำดับเวลาที่ถูกต้อง

**Negative:**
- การรันสร้างข้อมูล TLAS (Initialization Phase) จะใช้เวลาและ API Tokens จำนวนมาก เนื่องจากต้องทำ Map-Reduce กับข้อมูลนับพันก้อน
- โค้ดมีความซับซ้อนขึ้นเนื่องจากต้องผสานการทำงานระหว่าง Logic ของ Graph Analysis ใน Python (`rpgm_static_analyzer.py`) และ Logic การอนุมานของ LLM (แม้ปัญหา RAM เต็มแบบ Simulator จะหมดไปแล้วก็ตาม)
- Checkpoint files จำนวนมาก (`.log`, `.txt`, `.json`) จะสะสมใน `data/tlas/` — ควร cleanup หลังงาน TLAS initialization เสร็จสมบูรณ์
