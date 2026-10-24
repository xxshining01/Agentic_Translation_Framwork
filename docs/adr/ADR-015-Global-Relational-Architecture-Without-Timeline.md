# ADR-015: Global-Relational Architecture Without Timeline Dependencies

## Status
Approved

## Context
ในระบบเดิม (TLAS v3.x) มีการพยายามสร้าง Causal Story Timeline และเรียงลำดับบทสนทนา (Chronological Ordering) ผ่าน WCC Route Clustering และ Static Dependency Analysis เพื่อให้ตัวละครมี `timeline_states` เปลี่ยนแปลงตามช่วงเวลา (`timeline_phase`)

อย่างไรก็ตาม ในสถานการณ์จริงของไฟล์สคริปต์เกม (เช่น RPG Maker, Visual Novel):
1. สคริปต์เกมประกอบด้วย Branching Logic, Event Calls, Flashbacks, Sub-routes, และ Script Jump ที่ซับซ้อน ทำให้ไม่สามารถจัดเรียงลำดับ Timeline ทางกายภาพได้อย่างถูกต้องสมบูรณ์
2. การพยายามจำลองหรือเรียง Timeline นำไปสู่ปัญหาคอขวดขั้นวิกฤต (Bottleneck) ของไปป์ไลน์
3. Character Profiles สะสม `timeline_states` มากเกินความจำเป็นจนทำให้ไฟล์บวม (หลายพันบรรทัด) กิน Token ของ LLM อย่างมหาศาลโดยไม่ก่อให้เกิดประโยชน์ต่อคุณภาพการแปล
4. การให้ LLM ตัดสินใจเลือกคำสรรพนามภาษาไทยเป็นรายประโยคหรือรายซีน ทำให้เกิดปัญหา "สรรพนามแกว่ง (Pronoun Drift/Inconsistency)" เช่น ประโยคแรกเรียก "ผม-คุณ" ประโยคถัดมาเปลี่ยนเป็น "เรา-นาย"

## Decision
เราตัดสินใจปฏิรูประบบครั้งใหญ่เข้าสู่ **TLAS v4.0: Global-Relational Architecture** โดยมีหลักการสำคัญดังนี้:

1. **Elimination of Timeline Dependency (ยกเลิก Timeline 100%):**
   - ยกเลิกการเรียงลำดับ Timeline ของ Dialogue ทั้งหมด
   - ยกเลิกการพยายามแยกรูทเพื่อสร้างเหตุการณ์ก่อนหน้า-หลัง
   - ตัด `timeline_states`, `timeline_phase`, และ `story_timeline.json` ออกจากระบบอย่างถาวร

2. **Streamlined Translation Context (บริบทสำหรับการแปล 3 แกนหลัก):**
   ข้อมูลที่ใช้ประกอบการแปลจะเหลือเพียง:
   - **Consolidated Character Profile:** ข้อมูลตัวตนแกนกลาง และตารางความสัมพันธ์ระดับทิศทางคู่ (Directed Pairwise Relationships) พร้อมสรรพนามเฉพาะคู่นั้น
   - **Direct Scene Context:** สรุปเหตุการณ์เฉพาะหน้าของฉากนั้นๆ (ใครคุยกับใคร อยู่ที่ไหน ทำอะไร)
   - **Dialogue Emotion & Tone:** อารมณ์และน้ำเสียงของประโยคบทสนทนานั้น

3. **Strict Separation of Concerns between LLM and Python:**
   - **LLM Analyzer (Feature Extractor):** มีหน้าที่อ่านสคริปต์ราย Chunk และส่งกลับเฉพาะ "พารามิเตอร์เชิงนามธรรม" (Abstract Tags & Weights ตาม Taxonomy) **ห้าม LLM ส่งคำสรรพนามภาษาไทยกลับมาเด็ดขาด**
   - **Python Statistical Consensus & Rule Engine:** รอให้ LLM ประมวลผลจนครบทุก Chunk ของทั้งโปรเจกต์ จากนั้น Python จะนำพารามิเตอร์เชิงนามธรรมทั้งหมดมารวมศูนย์ คำนวณค่าเฉลี่ยทางสถิติ (Statistical Average / Majority Vote) เพื่อหาคู่ความสัมพันธ์ที่แท้จริง แล้วนำค่าเฉลี่ยนั้นไปแปลงเป็นคำสรรพนาม (Pronouns) บุรุษที่ 1, 2, 3 และคำลงท้าย ผ่านตาราง Taxonomy อย่างคงที่และแน่นอน

4. **Pairwise Directed Speech Styles (สรรพนามบุรุษที่ 1, 2, 3 รายบุคคล):**
   ใน Relationship แต่ละคู่ จะระบุชัดเจนว่าเจ้าของ Profile ใช้สรรพนามบุรุษที่ 1 (`self_pronoun`), บุรุษที่ 2 (`target_pronoun`), และบุรุษที่ 3 (`third_person_pronoun`) รวมถึงคำลงท้าย (`ending_particle`) กับคู่สนทนานั้นอย่างไร เช่น:
   - Dan คุยกับ Shion: `ผม` / `คุณ` / `เธอ` / `ครับ`
   - Dan คุยกับ Lily: `พี่` / `หนู` / `น้อง` / `จ้ะ`

## Consequences
### Positive
- **Unblock Pipeline Bottlenecks:** การประมวลผล Chunk ของสคริปต์สามารถทำแบบขนานอิสระ (Embarrassingly Parallel / Map-Reduce) ได้ทันที ไม่ต้องมี Topological Sort หรือ Dependency ลำดับก่อนหลัง
- **100% Pronoun Consistency:** กำจัดปัญหาสรรพนามแกว่งอย่างเด็ดขาด เพราะสรรพนามถูกกำหนดผ่าน Majority Vote จากข้อมูลทั้งโปรเจกต์
- **Token Efficiency:** Character Profiles มีขนาดกะทัดรัด (เหลือเพียง 50-100 บรรทัดต่อตัวละคร แทนที่จะเป็น 5,000 บรรทัด) ประหยัด Token ใน Prompt การแปลอย่างมหาศาล
- **Maintainability & Override Support:** ผู้ดูแลโปรเจกต์สามารถตรวจสอบและแก้ไขตารางสรรพนามระดับโปรเจกต์ได้ง่ายดายในจุดเดียว

### Negative / Trade-offs
- ไม่มีการเปลี่ยนสรรพนามแบบไดนามิกตามช่วงเวลา (Timeline State Mutation) แต่สามารถชดเชยได้ด้วย Scene Emotion/Tone ใน Runtime Prompt หากมีซีนที่อารมณ์รุนแรงเป็นพิเศษ
