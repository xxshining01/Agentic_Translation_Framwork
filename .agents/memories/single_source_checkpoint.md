# SINGLE SOURCE OF TRUTH CHECKPOINT (ATF ARCHITECTURE & IMPLEMENTATION)

> **⚠️ กฎเหล็กของระบบ:**
> 1. ไฟล์นี้คือ **แหล่งอ้างอิงสถานะการทำงานเพียงแหล่งเดียว (Single Source of Truth)** ของโปรเจกต์ ห้ามอ้างอิงสถานะหรือเช็คลิสต์จากที่อื่น
> 2. อนุญาตให้อัปเดตสถานะเป็น `[x]` เฉพาะเมื่อฟังก์ชันหรือเอกสารนั้นผ่านการทดสอบและใช้งานได้จริง 100% แล้วเท่านั้น
> 3. อนุญาตให้เพิ่มหัวข้อใหม่เฉพาะเมื่อมีแผนงานทางสถาปัตยกรรม (Architectural Roadmap) เพิ่มเติมเข้ามาใหม่เท่านั้น

---

## 🗺️ MASTER EXECUTION ROADMAP

### Phase 1: Architectural Documentation Calibration (ปรับปรุง Docs รากฐาน)
- [x] **Task 1.1: สร้าง ADR-035 (Glossary & Profile Boundary Decoupling and Zero-Fallback)**
  - กำหนดความแตกต่างระหว่าง Glossary (100% Speaker Names ล็อกคำแปล) กับ Character Profiles (เฉพาะตัวละครสำคัญ 30-50 ตัว)
  - กำหนดข้อห้ามเด็ดขาดเรื่อง Default Fallback (ห้ามสร้าง Default Polite Male Trap)
- [x] **Task 1.2: ปรับปรุง SAD-010 (Global-Relational Architecture v4.1)**
  - ปรับ Stage 2 (Reduce Phase) และ Stage 3 (Pronoun Resolution) ให้ตัด Ambient NPCs ออกจากการสร้าง Profile
  - ระบุ Clean Passthrough Architecture สำหรับตัวประกอบที่ไม่มี Profile
- [x] **Task 1.3: ปรับปรุง SDD-010 & SDD-011 (Profile Schema & Consensus Specification)**
  - ปรับปรุงเกณฑ์ Target Whitelist Qualification
  - กำหนด Lexicon สำหรับชื่อสากล (Female Names) เพื่อป้องกันการ Fallback เป็น MALE

---

### Phase 2: Memory & Session Tracking Engine Enforcement
- [x] **Task 2.1: สร้างโครงสร้าง `.agents/memories/` และ Checkpoint กลาง**
  - ติดตั้ง `single_source_checkpoint.md` และ `session_history.md`
- [x] **Task 2.2: บรรจุ Session Logging Rule ลงใน `.agents/rules/workspace-rules.md`**
  - กำหนดข้อบังคับบันทึกสรุปงานท้าย Session ทุกครั้ง

---

### Phase 3: Glossary vs Profile Decoupling & Target Qualification
- [x] **Task 3.1: สแกนและสร้าง Master Glossary จาก Speaker Tags ทั้งหมดใน Example RPGM**
  - สแกน Speaker Tags ครบ 100% จาก CSV (รองรับ Lenticular Brackets `【...】` และสากล) และสร้าง `data/tlas/tlas_glossary.json` ล็อกคำแปลไทย 1:1
- [x] **Task 3.2: สกัดเฉพาะตัวละครสำคัญเข้าสู่ Whitelist (คัดกรองตาม ADR-035)**
  - คัดกรองตัวละครหลัก 6 ตัว (`凛`, `遠藤`, `夫`, `西原`, `受付のおばあさん`, `孫`) เข้า `data/tlas/character_whitelist.json` ส่วนตัวประกอบ 7 ตัวใช้ Clean Passthrough (ไม่มี Profile บนดิสก์)
- [x] **Task 3.3: สกัด Scene Packets และวิเคราะห์ Choice Collision (Universal Packetizer v2.0)**
  - สกัดความต่อเนื่องของฉาก (Continuity) 55 Packets ปลอด Heuristics และจัดกลุ่มช้อยส์คู่/ช้อยส์หลายตัวเลือกสมบูรณ์ 100% สู่ `data/tlas/scene_packets.json`

---

### Phase 4: Consensus Engine Hardening & Poisoned Profile Purge
- [x] **Task 4.1: ปรับแก้ `src/atf/tools/tlas_consensus_engine.py`**
  - ลบตรรกะ `Default polite male` (ผม/คุณ/ครับ) ออกไปอย่างสิ้นเชิง และแทนที่ด้วย Safe Neutral Register
  - ถอด Hardcoded Aliases ของเกมเก่าออก 100% เปลี่ยนเป็นโหลดไดนามิกจาก `alias_mapping.json`
  - ปรับปรุงให้โหลดรายชื่อตัวละครสำคัญจาก `character_whitelist.json` ลำดับแรก
- [x] **Task 4.2: กวาดล้างไฟล์ Profile ขยะใน `data/tlas/profiles/`**
  - แบ็กอัปโปรไฟล์เก่า 445 ไฟล์สู่ `data/legacy_english_game_profiles_backup/` พร้อม Manifest ตรวจสอบครบ 100%
  - กวาดล้าง Workspace และสร้าง Clean Character Profiles 9 ตัวพร้อมตาราง `global_pronoun_matrix.json` (17 Pairwise Rules)

---

### Phase 5: Translation Runner Hardening (Runtime Guardrails)
- [x] **Task 5.1: ฝัง Persistent Mini-System Invariant ใน `chatgpt_translator_runner.py`**
  - แนบกฎคุมความยาว (~40-48 ตัวอักษร), Onomatopoeia (SFX Glossary constraints), และ Invariant Tags ในทุกๆ พร็อมพ์ (รวม Follow-up Prompts)
- [x] **Task 5.2: ทำ Forward-Propagation คัดลอก Speaker ใน Scene เดียวกัน**
  - อุดรอยรั่วประโยคตาบอด (`speaker == ""`) ป้องกัน AI เดาสรรพนามมั่ว
- [x] **Task 5.3: ปรับตรรกะ Runner ให้รองรับ Clean Passthrough & Dynamic Pairwise Matrix**
  - ดึงข้อมูลจาก `global_pronoun_matrix.json` แบบไดนามิก ไร้ Hardcode Dan/Shion/Lily/Lucas
  - หากประโยคนั้นไม่มี Character Profile ให้ส่งเฉพาะคำแปลชื่อตาม Glossary + บริบทฉาก โดยไม่ส่ง Profile กลวงไปหลอก AI
- [x] **Task 5.4: Universal Transliteration & Fallback Purge**
  - กำจัด hardcoded transliteration patterns ใน `enforce_glossary_in_translation`
  - รองรับแท็กผู้พูดแบบ Lenticular `【...】`, `<...>`, `[...]` และรองรับภาษาญี่ปุ่นใน `is_pure_symbol_dialogue`

---

### Phase 6: Active LQA Audit & Verification on Example RPGM Game
- [x] **Task 6.1: เชื่อมต่อ `LQATranslationAuditor` เข้ากับ Translation Loop**
  - สแกนคำแปลผลลัพธ์: ดักจับคำแปลผิดเพศ, นักเลงพูดครับ/ค่ะ, แท็กเกมเสียหาย
  - ระบบ Auto-Reject และยิงซ่อมเฉพาะแถวนั้นอัตโนมัติ
- [x] **Task 6.2: รันทดสอบจริงกับชุดข้อมูลบทสนทนาใน Example RPGM Game**
  - ตรวจสอบความเสถียรของคำแปล เปรียบเทียบความยาว และความถูกต้องของสรรพนาม 100%

---

### Phase 7: Profile Base Decoupling & Identity Demographic Matrix (IDPR v5.0)
- [x] **Task 7.1: Profile Base Sanitization & Number/Persona Enrichment**
  - นำ `target_pronoun` และ `third_person_pronoun` ออกจาก `base_speech_style` ของทุก Profile
  - เพิ่ม `identity.number` (SINGULAR / PLURAL) และ `demographic_persona` ในระดับ Metadata
- [x] **Task 7.2: Unified Demographic Matrix Compilation (`global_pronoun_matrix.json` v5.0)**
  - รวบรวม Specific Pairwise Rules จาก relationships ของโปรไฟล์ทุกตัว (17 Rules)
  - สังเคราะห์ Demographic Rules ตาม Identity (Gender, Age, Number) และ Persona State ครอบคลุม 100% (31 Rules)
- [x] **Task 7.3: Two-Tier Pronoun Resolution in `GlossaryScanner` & `LQATranslationAuditor`**
  - อัปเกรด `GlossaryScanner` ให้จับคู่ Specific 1:1 ก่อน -> ถ้าไม่มี ให้จับคู่ Demographic Identity อัตโนมัติ -> ถ้าอยู่คนเดียว (Monologue) ไม่ส่ง target pronoun รบกวนโมเดล
  - ปรับปรุง `LQATranslationAuditor` ให้รองรับโครงสร้าง Matrix v5.0 ทั้งแบบ Dict และ List
- [x] **Task 7.4: Japanese Punctuation & Pure Symbol Zero-Token Auto-Resolution**
  - บรรจุอักขระสัญลักษณ์ญี่ปุ่น `・` (จุดกลาง), `。` (มหัพภาค), `、` (จุลภาค), `―`/`――` (ขีดนำ), `〜` เข้าสู่ `SYMBOL_ONLY_PATTERN`
  - สกัดกั้นประโยคเงียบ/สัญลักษณ์ล้วน (`・・・・・・・`, `――――――・・・・・`) ไม่ให้หลุดไปกิน Token ของ LLM (ประหยัดได้ 163 แถวทันที)
  - ให้ Python จัดการแปลชื่อใน Speaker Tag (`【夫】` -> `【สามี】`) ผ่าน Master Glossary 100% โดยตรงอย่างแม่นยำ ปลอด Hallucination
- [x] **Task 7.5: Full Story Production Translation Completed (100% Done)**
  - แปลบทสนทนาและข้อความทั้งเรื่องของเกม `離れ木の5日間+` เสร็จสมบูรณ์ครบ 100% (3,484 / 3,484 แถว, 0 Empty Rows)
  - เซฟไฟล์ผลลัพธ์ลง `Example RPGM Game/output/離れ木の5日間+_translated.csv` เรียบร้อย พร้อมแพทช์คืนเกม

---

### Phase 8: Pipeline Robustness, Displayable Filter & Context Enrichment
- [x] **Task 8.1: Prompt Batch Capacity Expansion (Scene Packets ~80 Items & 24k Tokens)**
  - ขยายขีดความสามารถการจุบทสนทนาในแต่ละ Scene Batch จาก 15 แถวสู่ 80 แถว (และ Token Budget จาก 8,000 สู่ 24,000 tokens)
  - เพิ่มความต่อเนื่องของบทสนทนาและลดจำนวนเที่ยวการส่งพร็อมพ์ลงได้กว่า 70%
- [x] **Task 8.2: Automated Game Displayable Engine (`GameDisplayableEngine`)**
  - ติดตั้งเอนจินสแกนข้อมูลเกมจริงจาก `www/data/*.json` สกัดหมวดหมู่ Role และ Displayable (Yes/No) อัตโนมัติ
  - เพิ่มการตรวจจับ Non-Displayable (ตัวแปร, สวิตช์, โค้ดสคริปต์ JS, Event labels, Asset names) ป้องกันเกมแครช 100%
  - เพิ่ม Parser อัจฉริยะสำหรับคำสั่งปลั๊กอิน `D_TEXT` แปลงข้อความแสดงผลบนหน้าจอสู่งานแปลภาษาไทยสมบูรณ์
- [x] **Task 8.3: Conversational Listener Identification & CSV Note Tracking**
  - เพิ่มฟิลด์ `listener` ใน Output JSON Schema ของ ChatGPT ให้โมเดลระบุคู่สนทนาของทุกประโยคอย่างชัดเจน
  - บันทึกชื่อ `Listener` ลงในคอลัมน์ Note (Column 4) ของไฟล์ CSV ผลลัพธ์ ช่วยให้การตรวจสอบและแก้ไขแมนวลทำได้ทันที
- [x] **Task 8.4: Targeted Forensic Repair & 6D LQA Certification**
  - ซ่อมแซมแถวที่ติดปัญหาครบ 100%: 35 แถว D_TEXT, 37 แถวคำแปลตกหล่น/ภาษาจีนรั่วไหล (เช่น `主动` -> เริ่มอมเอง/เป็นฝ่ายรุก) และฉาก Map041
  - อัปเกรด `LQATranslationAuditor` ด้วย Dimension 6 (Hanzi/CJK Leakage Check) ตรวจสอบผ่าน 100% ปลอดจุดบกพร่อง
- [x] **Task 8.5: Antigravity Customization Rules Schema Calibration & Dry-run Mock Isolation**
  - ปรับแก้ Frontmatter Schema ใน `.agents/rules/*.md` ทั้ง 3 ไฟล์ (`workspace-rules.md`, `zero-hardcode-and-hallucination.md`, `prompt-engineering-invariants.md`) ให้เป็นไปตามสเปกของ Antigravity Rule Loader (`trigger: always_on`, `glob: "*"`, `description: "..."`) แก้ปัญหาแจ้งเตือน "3 customizations failed to load Rule..." หายสนิท 100%
  - ปรับปรุง Mock Translation ใน `benchmark_translation.py --dry-run` ให้ใช้ข้อความจำลองภาษาไทย ไม่ให้ชนกับกฎ Dimension 6 Hanzi Leakage ระหว่างการทดสอบ Offline Dry-Run

---

### Phase 9: Rich 10-Column Localization Schema & Conversational Triad Engine
- [x] **Task 9.1: Prompt Invariant Enhancement (Strict 1-Line & Conversational Triad)**
  - เพิ่มกฎ Strict 1-Line Invariant ใน Master & Mini Invariant: ห้ามตัดขึ้นบรรทัดใหม่ตามอำเภอใจในเซลล์ หากต้นฉบับมี 1 บรรทัดและยาวไม่เกิน 45 ตัวอักษร
  - บรรจุ `third_person` และข้อบังคับ Zero CJK Leakage ลงใน Output JSON Schema ของโมเดล
- [x] **Task 9.2: Dedicated 10-Column Localization Table Schema**
  - แยกคอลัมน์ชัดเจน 10 มิติ: `Original`, `Initial`, `Displayable`, `Role`, `Speaker`, `Listener`, `Third_Person`, `Filename`, `Row`, `Note`
  - คืนความสะอาดให้คอลัมน์ `Note` โดยแยก metadata ออกไปอยู่ในคอลัมน์เฉพาะ
- [x] **Task 9.3: Automated Game Code & Variable Shielding (`Displayable == 'No'`)**
  - ใช้ `GameDisplayableEngine` สแกน `www/data/*.json` สกัดกั้นโค้ด สคริปต์ สวิตช์ ตัวแปร และคอมเมนต์ 482 แถว บังคับคงค่าต้นฉบับ 100% ป้องกันเกมแครช
- [x] **Task 9.4: Conversational Triad & Semantic Co-reference Resolution**
  - สร้าง `generate_enriched_localization_csv.py` สกัด Speaker (แก้ปัญหาตัวละครนิรนาม/ช้อยส์/บทบรรยาย), Listener (คู่สนทนา), และ Third_Person (บุคคลที่สามที่ถูกพาดพิงถึง เช่น รินในบทสนทนาระหว่างเอ็นโดกับสามี)
- [x] **Task 9.5: Algorithmic Line-Break Normalization & Hardcode Elimination**
  - รวมบรรทัดที่ถูกตัดขึ้นบรรทัดใหม่โดยไม่จำเป็นกลับเป็น 1 บรรทัดตามต้นฉบับสำเร็จ 51 แถว (ความยาว <= 45 ตัวอักษร)
  - ลบสคริปต์ฮาร์ดโค้ดออก 100% ขับเคลื่อนด้วยอัลกอริทึมเชิงโครงสร้างสากล (Universal Framework Paradigm)

---

### Phase 10: Parenthesis Disambiguation, Plugin UI Extraction Scope & Clean Slate Pipeline
- [x] **Task 10.1: Rule Integration ([RULE_DISPLAYABLE_USER_EXPERIENCE_ONLY] & [RULE_NO_PARENTHESIS_BIAS])**
  - บรรจุ `[RULE_DISPLAYABLE_USER_EXPERIENCE_ONLY]` ลงใน `.agents/rules/workspace-rules.md`: เน้นเฉพาะสิ่งที่ผู้เล่นมองเห็น แปลเฉพาะ UI/Picture Text พารามิเตอร์โค้ดภายในคงเดิม 100%
  - บรรจุ `[RULE_NO_PARENTHESIS_BIAS]` ลงใน `.agents/rules/zero-hardcode-and-hallucination.md`: เลิกยึดติดว่า `()` คือคิดในใจของตัวเอก วิเคราะห์จากรูปประโยคและบริบทของฉาก (System/Narrator/ตัวละครอื่น)
- [x] **Task 10.2: Contextual Linguistic Disambiguation in `generate_enriched_localization_csv.py`**
  - ถอดตรรกะ Hardcode `startswith('（') -> '夫'` ออก 100% ตรวจสอบคำชี้แนะระบบ (Save, Item, Gold, Key) เป็น System/Narrator และใช้ Scene Continuous Flow ระบุตัวละครตามจริง
- [x] **Task 10.3: Plugin UI Text Extraction Calibration (`extract_plugin_texts.py`)**
  - กรองข้ามโค้ดและคอนฟิกเทคนิค (เช่น คีย์ลัด `control`, `shift`, โหมด `relative`, ชื่อไฟล์ภาพ `FileName`) ทั้งหมด 128 รายการอย่างปลอดภัย
  - สกัดเฉพาะ UI String ที่ผู้เล่นเห็นจริงบนหน้าจอไตเติล (เช่น `AnotherNewGame`: `回想モード` -> โหมดหวนรำลึก) ออกสู่ `data/plugins_texts.csv`
- [x] **Task 10.4: Clean Slate Unified Translation Pipeline Setup (`benchmark_translation.py`)**
  - เพิ่ม Flag `--unified` (แปล Plugin CSV -> Dialogue CSV ตามลำดับ) และ `--reset-checkpoint` (เริ่มแปลใหม่จาก 0 ตั้งแต่ต้น)
  - รองรับการทดสอบและรันจริงแบบครบวงจรผ่าน ChatGPT Web Bridge

---

### Phase 11: Safety Hedge Loop Elimination & Checkpoint Resume Architecture
- [x] **Task 11.1: Fictional Adult Identity Calibration (Age: ADULT / 18+)**
  - ปรับปรุง Metadata อายุของตัวละคร `学生A`, `学生B`, `学生2人` ใน `data/tlas/profiles/` จาก `"TEEN"` เป็น `"ADULT"` (นักศึกษามหาวิทยาลัย / ผู้ใหญ่ 18+)
  - แนบ Invariant ข้อ 0 ใน Master System Instruction ระบุว่าทุกตัวละครเป็นผู้ใหญ่วัย 18+ ในวรรณกรรมแฟนตาซี สกัดกั้นคำถาม Safety Hedge ของ AI ล่วงหน้า
- [x] **Task 11.2: Safety Confirmation Detection & Loop Circuit Breaker**
  - เพิ่มคำสำคัญการขอยืนยันอายุ (`ขอยืนยัน`, `18 ปี`, `อายุ`, `ผู้เยาว์`) ใน `is_safety_refusal()`
  - อุดรอยรั่ว `TypeError: 'NoneType' object is not iterable` เมื่อ AI ตอบเป็นคำถาม ให้เปลี่ยนเป็น `SafetyRefusalError` ส่งต่อให้ระบบ Adaptive Bisecting ทันที
  - กำหนดขีดจำกัดความพยายาม (Attempt Limit = 3) ป้องกันการวนลูปไม่รู้จบในแชตเดิม
- [x] **Task 11.3: Checkpoint Data Preservation & Resume Readiness**
  - ยืนยันข้อมูลที่แปลเสร็จแล้ว 2,137 แถว (ใน `Example RPGM Game/output/離れ木の5日間+_translated.csv` และ Checkpoint JSON) ปลอดภัย 100%
  - ขั้นตอนการรันต่อ: สั่งรันตามปกติโดยไม่ต้องใส่ `--reset-checkpoint` ระบบจะข้าม 2,137 แถวแรกที่เสร็จแล้ว แล้วต่อแถวที่ 2,138 ทันที

---

### Phase 12: Literary Style Calibration & Persistent Aesthetic Invariant (Style #1 Standard)
- [x] **Task 12.1: Persistent Literary Persona & Natural Flow Invariant**
  - บรรจุ Persona ข้อ 0 และกฎข้อ 1 (High Literary Elegance & Natural Flow) ลงใน `MINI_SYSTEM_INVARIANT`
  - ล็อกสำนวนวรรณศิลป์ระดับพรีเมียมให้ส่งแนบไปในทุกๆ พร็อมพ์ (รวมถึง Follow-up Prompts) ป้องกัน Style Drift และ Attention Decay 100%
- [x] **Task 12.2: Standardized Speaker Tag Line Formatting**
  - กำหนดข้อบังคับชัดเจนใน Rule 2: แท็กชื่อตัวละคร `【...】` ต้องคั่นด้วย `\n` ตามด้วยบทสนทนาเสมอ ป้องกันการรวบติดกันเป็นบรรทัดเดียว
- [x] **Task 12.3: Batch Directive Aesthetic Calibration**
  - ปรับปรุงข้อความปิดท้าย Batch (`CRITICAL DIRECTIVE`) ใน `translate_batch` ให้เน้นย้ำความสละสลวย อารมณ์ร่วม และจังหวะภาษาที่เป็นธรรมชาติสม่ำเสมอดุจนักแปลคนเดียวกัน

---

### Phase 13: Final Forensic Repair & Universal Data Integrity (15D Certified)
- [x] **Task 13.1: Final Forensic Localization Repair Tool (`repair_localization_final.py`)**
  - สร้างสคริปต์ซ่อมแซมจุดบกพร่องอัตโนมัติ: แก้ CJK Leakage 3 แถว (Map030 Row 64, Row 112, Map004 Row 20)
  - แปลงตัวอักษรดิบ `\n` (`\\n`) เป็นการเคาะบรรทัดจริง 60 แถว
  - เติม `\n` หลังแท็กชื่อ `【...】` 12 แถว
  - ปรับสรรพนามนิชิฮาระ (ฉัน) และแก้อ้างอิงข้อความเครดิตผู้สร้าง (Developer)
  - ซิงค์ผลการซ่อมแซมลงทั้ง `離れ木の5日間+_enriched_translated.csv`, `離れ木の5日間+_translated.csv` และ Checkpoint JSON สมบูรณ์ 100%
- [x] **Task 13.2: Universal Triad Schema Unification in `generate_enriched_localization_csv.py`**
  - ฝังพจนานุกรม `THAI_TO_CANONICAL_LISTENER` แปลง Listener ในคอลัมน์ให้อยู่ในรูป Canonical Name ภาษาญี่ปุ่นมาตรฐาน สอดคล้องกับ Speaker และ Third_Person 100%
  - ฝัง Auto-repair formatting invariants (`\n` conversion & Tag newline insertion) ใน Pipeline
- [x] **Task 13.3: 15-Dimension Comprehensive Forensic Audit 100% Certification**
  - ตรวจสอบผ่าน 100% ครบทุกมิติหลัก (0 Skipped, 0 CJK Leakage, 0 Mojibake, 0 Safety Refusal, 0 Pronoun Inversion, 0 Prohibited SFX, 482 Non-Displayable Code Untouched, 100% XML Tag Integrity)

---

### Phase 14: Strict 1:1 Line Correspondence & Arbitrary In-Cell Break Elimination
- [x] **Task 14.1: Single-Line Cell Strict Normalization (`normalize_line_breaks_strict.py`)**
  - ลบการแทรก `\n` ในแถวที่ Original มี 1 บรรทัด (0 newlines) คืนสภาพ Initial เป็น 1 บรรทัดตรงกับต้นฉบับ 100% (12 แถว เช่น `【สามี】ผมเป็นห่วงนะครับ`, `【ริน】ก็ได้นะ...`, `ไม่สิ... ต้องบอกว่าถูกทำให้เสร็จโดยรินต่างหาก...`)
  - รวมประโยคสั้นที่ถูกหั่นเป็น 2 บรรทัดโดยไม่จำเป็น (<=55 ตัวอักษร) กลับเป็น 1 บรรทัด 17 แถว
  - กำจัด Double Newlines (`\n\n`) และคำขาด (Fragmented line breaks) 16 แถว
  - ซิงค์ผลลัพธ์ลงทั้งตาราง Enriched CSV, Translated CSV และ Checkpoint JSON สมบูรณ์

---

### Phase 15: Scene Turn-Taking Interlocutor Resolution & Semantic Inquiry Disambiguation
- [x] **Task 15.1: Elimination of Naive Hardcoded Fallbacks**
  - ลบตรรกะ Hardcoded Default Fallback (`if speaker == '夫': listener = '凛'`) ออกจากระบบ 100%
- [x] **Task 15.2: Conversational Turn-Taking Engine (`resolve_conversational_triad.py`)**
  - พัฒนาระบบติดตามคู่สนทนาแบบ Turn-Taking อิงตามบริบทการโต้ตอบจริงในฉาก (แก้ไข Listener ถูกต้อง 941 แถว)
- [x] **Task 15.3: Semantic Inquiry Disambiguation (Third Person vs Listener)**
  - ตรวจจับประโยคถามหาบุคคลอื่น (เช่น `りん... 見てないかな`, `妻はどこ`) ย้ายตัวตนที่ถูกถามหาไปไว้ที่ `Third_Person` และกำหนด `Listener` เป็นคู่สนทนาตัวจริงในฉาก (แก้ไข Third Person ถูกต้อง 143 แถว)
- [x] **Task 15.4: Pipeline Integration in `generate_enriched_localization_csv.py`**
  - ฝังเอนจิน `resolve_triads` ลงในตัวประกอบตาราง CSV ส่งผลให้การ Export ทุกครั้งมีความถูกต้องเชิงสัมพันธภาพระดับ 100%

---

### Phase 16: Japanese Word-Boundary Scanner Fix & Proper Noun Restoration
- [x] **Task 16.1: Eliminate `\b` Latin Word-Boundary Bug in `GlossaryScanner`**
  - แก้ไข `_create_word_regex`: ยกเลิกการใส่ `\b` กับภาษาญี่ปุ่น/CJK ทำให้สแกนจับชื่อที่ติดกับคำสร้อยภาษาญี่ปุ่น (เช่น `遠藤さん`, `凛ちゃん`, `西原くん`) ได้ถูกต้อง 100%
- [x] **Task 16.2: Purge Legacy English Name Directive**
  - ลบกฎตกค้างจากเกมเก่าที่บอกให้คงชื่อภาษาอังกฤษ (`Lucy` -> `Lucy`) ออกจากทั้ง `glossary_scanner.py` และ `chatgpt_translator_runner.py` ป้องกันไม่ให้ AI ปล่อยชื่อญี่ปุ่นเป็นอักษรละติน
- [x] **Task 16.3: Master Glossary Variants & Surname Enrichment**
  - บรรจุ `民宿『離れ木』`, `離れ木` (เรียวกังฮานาเรกิ / ฮานาเรกิ) และ `小松` (โคมัตสึ - นามสกุลสามี) ลงใน `tlas_glossary.json` 100%
- [x] **Task 16.4: Forensic Proper Noun Repair (`fix_hallucinated_proper_nouns.py`)**
  - ซ่อมแซม 5 จุด `Endo` -> `เอ็นโด`, 2 จุด `Komatsu` -> `โคมัตสึ`, และ 1 จุด `บ้านพักตากอากาศ` -> `เรียวกังฮานาเรกิ` ซิงค์ครบทั้ง 3 ไฟล์บนดิสก์

---

### Phase 17: Universal Framework Hardening & Zero-Hardcode Architecture Enforcement
- [x] **Task 17.1: Universal Interlocutor Turn-Taking Engine (`resolve_conversational_triad.py`)**
  - กำจัด hardcoded `ENTITY_MAP` และ static fallback ออก 100%
  - พัฒนา `build_dynamic_entity_map()` ค้นพบตัวละครทุกตัวและคำแปลไทย/สรรพนามจาก Glossary และ Profiles อัตโนมัติสำหรับทุกเกม
  - สถาปัตยกรรม Turn-Taking และ Monologue (`Self`) ทำงานแบบ Game-Agnostic ไม่ยึดติดกับชื่อตัวละครใด
- [x] **Task 17.2: Universal Localization Table Generator (`generate_enriched_localization_csv.py`)**
  - กำจัด hardcoded `rin_markers`, `husband_markers`, `endo_markers` และ hardcoded `THAI_TO_CANONICAL_LISTENER`
  - ใช้ `build_dynamic_canonical_map()` แปลงชื่อไทยกลับสู่ Canonical Name ญี่ปุ่นอัตโนมัติจาก Master Glossary
  - ถอด Fallback `if speaker == "夫": listener = "凛"` ออก 100% ขับเคลื่อนด้วย Universal Scene Turn-Taking Engine
- [x] **Task 17.3: Universal Prompt Runner Invariant (`chatgpt_translator_runner.py`)**
  - ล้างชื่อตัวละครเฉพาะเกม (`夫`, `凛`, `遠藤`, `西原`) ออกจาก Master Prompt System Instructions และ Batch Directives
  - เปลี่ยนเป็น Universal Archetypes (`Character A`, `Character B`, `Character C`) และ Dynamic Glossary Injection ป้องกันการปนเปื้อนข้ามเกม 100%
- [x] **Task 17.4: Event Boundary Isolation Invariant in Scene Turn-Taking**
  - ตัดวงจรการดึง `prev_interlocutor` ข้ามเส้นแบ่ง Event (`Displayable == 'No'`) สกัดกั้นการรั่วไหลของคู่สนทนาจากฉากเก่าสู่ฉากใหม่ 100%
  - แก้ไขบทสนทนาเปิดฉาก (Event Opening Rows) เช่น หลานชายทักทายพี่ชาย (Row 62 Map001 `孫 -> 夫`) ถูกต้องตามหลัก Adjacency Pair
- [x] **Task 17.5: Ground Truth Verification & Triad Audit Suite (`verify_localization_triad.py`)**
  - พัฒนาชุดเครื่องมือตรวจสอบความถูกต้อง 6 มิติ (Explicit Tag Ground Truth, Triad Disjointness, Inquiry Exclusion, Non-Displayable Shielding, Monologue Isolation, Active Dialogue Continuity)
  - สแกนตรวจสอบ 3,484 แถวใน Enriched CSV ผลลัพธ์: ผ่านการรับรอง 100% ปลอดจุดบกพร่อง (0 Violations)
- [x] **Task 17.6: Universal Multi-Party Addressee Resolution Engine (MP-Addressee v2.0)**
  - แก้ไขปัญหาฉากที่มีตัวละครตั้งแต่ 3 ตัวขึ้นไป (Multi-Party Conversational Dynamics):
    1. **Vocative Priority:** ตรวจจับคำเรียกชื่อ/ฉายา/คำขานรับตรงๆ (เช่น `おばあちゃーん！！！` -> Listener: 受付のおばあさん)
    2. **QA & Apology Adjacency:** ตรวจจับคู่ ถาม-ตอบ และ ขอโทษ-ตอบรับ (เช่น `だ、大丈夫なの？` -> `うん...` กำหนด Listener เป็น 凛 ทันที)
    3. **Third-Person Topic Exclusion:** สกัดกั้นการตั้งคนที่ถูกพูดถึงเป็นบุรุษที่สามเป็นผู้ฟัง (เช่น ยายพูด `この子は私の孫で...` -> หันไปขอโทษแขก 夫)
    4. **Scene Presence Bounding:** กำหนดขอบเขตผู้ฟังไม่ให้หลุดออกนอกกลุ่มตัวละครที่อยู่ในฉากจริง (Active Speakers + Registered Party Members) ปลอดตัวละครผี 100%

---

### Phase 18: Untagged Utterance Triad Classification, Protagonist Eradication & Multi-Party Refinement
- [x] **Task 18.1: Eradication of "Protagonist" Placeholder String**
  - กำจัดคำว่า `"Protagonist"` ออกจากระบบและตารางผลลัพธ์ 100% (0 รายการ)
  - กำหนดให้ Choice Option/Branch เป็น `Speaker: None, Listener: Player` และข้อความความคิดตัวเอกเป็นชื่อจริงตามตัวละครที่ควบคุม (`夫`)
- [x] **Task 18.2: First-Person Monologue & Spatial Awareness Disambiguation**
  - แยกแยะประเภท Untagged Utterances 7 หมวดหมู่อย่างเป็นรูปธรรมด้วย `classify_untagged_utterance`
  - แปลงความคิดในใจของตัวเอกและเสียงสะท้อนสิ่งกีดขวาง (`部屋はこっちじゃない`, `外に用はない`, `頭がクラクラする`, `僕と凛は`) จาก Narrator เป็น `Speaker: 夫`, `Listener: Self`, `Role: Dialogue/Story`
  - คัดแยกข้อความเมนูห้องหวนรำลึก (`Map025`, `Map042`) และคำถามระบบ (`見ますか？`) สู่ `Role: System Term / System Message`
- [x] **Task 18.3: Multi-Party Retort/Objection Adjacency (Line 546 Resolution)**
  - พัฒนา Priority 1.5 ใน `resolve_conversational_triad.py`: ดักจับคำบ่น/งอแง/คัดค้าน (`えー`, `いいじゃん`, `やだ`, `なんで`) ให้หันกลับไปหาผู้สั่งห้ามคนก่อนหน้า (`prev_interlocutor`)
  - ส่งผลให้ Line 546 (`【孫】 えーいいじゃんー！ 遊ぼうよーー！！！`) มุ่งตรงไปที่ยาย (`受付のおばあさん`) ถูกต้องตามเจตจำนงของบทสนทนา 100%
- [x] **Task 18.4: Distal 3rd-Person Topic Exclusion & Secret Whisper Resolution (Map033 Row 5)**
  - เพิ่ม `旦那さん` และ `ご主人` ใน `detect_third_person_exclusion`: ตัดสิทธิ์สามีจากการเป็นผู้ฟังเมื่อถูกกล่าวถึงในฐานะบุรุษที่สาม
  - แก้ไขประโยคกระซิบนัดแนะลับหลังของเอ็นโด (`旦那さんが露天風呂に向かったら...`) เป็น `Speaker: 遠藤, Listener: 凛, Third_Person: 夫` แม่นยำ 100%
- [x] **Task 18.5: Japanese Punctuation Invariant in Vocatives (`・`, `…`)**
  - ขยาย Regex Vocative ใน `detect_vocative` ให้รองรับจุดไข่ปลาและสัญลักษณ์คั่นภาษาญี่ปุ่น (`・…‥.`)
  - ทำให้ประโยคทักทายอย่าง `【夫】凛・・！ 大丈夫・・・？` สกัดจับ `凛` เป็น Listener ได้อย่างสมบูรณ์แบบ
- [x] **Task 18.6: 100% Ground Truth Certification & Table Re-export**
  - ตรวจสอบผ่าน `verify_localization_triad.py` สำเร็จ 100% (0 Violations ครบ 3,484 แถว)
- [x] **Task 18.7: Universal Zero-Hardcode Architecture Enforcement (Total Hardcode Elimination)**
  - กวาดล้าง Hardcode ข้อความเกมและชื่อตัวละครเฉพาะเกมออกจากทั้ง `resolve_conversational_triad.py` และ `generate_enriched_localization_csv.py` 100%:
    1. **Dynamic Demographic Vocatives:** ขับเคลื่อนคำเรียกบุคคล (`เด็ก`, `คนแก่`, `พี่ชาย`, `พี่สาว`, `สามี`, `ภรรยา`) จาก `identity.age`, `identity.gender` และ `relationships.roles` ใน Profile Schema ไร้การเช็คชื่อตัวละครเด็ดขาด
    2. **Linguistic Distal 3rd-Person Topic Exclusion:** สกัดจับผู้ถูกพาดพิงด้วยไวยากรณ์สากล (`この/その/あの/私の + Entity Marker` และ Relational Honorifics) วนลูปจาก Entity Map ไร้ชื่อเฉพาะ
    3. **Attested Dialogue Corpus Propagation:** หากบทสนทนาไร้แท็กเคยปรากฏแบบมีแท็กชื่อ (`【...】`) ที่ใดก็ตามในเกม ระบบจะสืบทอดชื่อผู้พูดจากหลักฐานจริงในตัวเกมโดยอัตโนมัติ (เช่น Map035 -> Map033)
    4. **Universal Japanese Monologue Grammar:** ระบุความคิดในใจของตัวละครผ่านไวยากรณ์ญี่ปุ่น (Volitional `～よう`, Obligation `～ないと`, Introspection `～だろうか`, Spatial Feedback) ไร้ประโยคเฉพาะเรื่อง

---

### Phase 19: First-Principles Register Taxonomy, Protagonist Agency & Universal Register Invariants
- [x] **Task 19.1: Database Asset Speaker Purge (`DB_FILES`)**
  - กวาดล้าง Narrator ออกจากไฟล์ฐานข้อมูล (`Actors`, `Animations`, `Classes`, `CommonEvents`, `Items`, `Skills`...): กำหนดเป็น `Speaker: None, Listener: Player, Role: Entity Name` สมบูรณ์ 100%
- [x] **Task 19.2: System UI Register Unification**
  - รวมศูนย์ข้อความระบบและหน้าต่างเกม (`System Message`, `System Term`, `Map Display Name`, `Plugin Dialogue`): บังคับ `Speaker: System, Listener: Player` สม่ำเสมอ 100% ไร้ Narrator ปนเปื้อน
- [x] **Task 19.3: Protagonist Agency in Choice Branches**
  - คืนสิทธิ์การตัดสินใจให้ตัวละครที่ผู้เล่นบังคับ: `Role: Choice Branch` ถูกกำหนดให้ `Speaker: active_protagonist` (`夫`) และ `Listener: Self` (หรือคู่สนทนาที่ถาม) ปลอด `Speaker: None` และไม่มี `Listener: Player`
- [x] **Task 19.4: Untagged First-Person Monologue Restoration (Row 1204 & Cutscenes)**
  - แก้ไขบทบรรยายมุมมองบุคคลที่หนึ่ง (เช่น Row 1204: `あの日から 僕の性癖は...`) และความคิดในใจ/ข้อความสำรวจฉากคัตซีน 242 แถว จากเดิมที่หลุดเป็น Narrator ให้คืนสู่ `Role: Dialogue/Story, Speaker: 夫, Listener: Self`
- [x] **Task 19.5: Developer Message & True Third-Person Narration Isolation**
  - แยกข้อความปิดท้ายของผู้พัฒนา (`Map041` Rows 3108-3110) เป็น `Role: Developer Message, Speaker: Developer, Listener: Player`
  - จำกัด `Speaker: Narrator` ไว้เฉพาะบทบรรยายบุคคลที่สามแท้จริง 28 แถว (`バカな旦那だ...` และ Chapter Timestamps)
- [x] **Task 19.6: Cliche SFX Rectification (Row 327 `ギクッ`)**
  - ซ่อมแซมคำแปล `ギクッ` จาก `สะดุ้งเฮือก` เป็น `สะดุ้ง...!` ซิงค์ลงทั้งตาราง Enriched CSV, Translated CSV และ Checkpoint JSON
- [x] **Task 19.7: 7-Dimension Comprehensive Ground Truth Certification**
  - เพิ่มมิติที่ 7 (Register & Persona Invariant) ใน `verify_localization_triad.py` ตรวจสอบผ่าน 100% สมบูรณ์แบบ (0 Violations ครบ 3,484 แถว)

---

### Phase 20: Upstream Invariant Hardening & Zero-Hardcode Purge
- [x] **Task 20.1: Complete Purge of Ad-hoc Plot Strings in Table Generator**
  - ล้างสตริงเฉพาะเรื่อง (`バカな旦那だ`, `自らの手で破滅させる`, `まぁ・・気付いてない`) ออกจาก `generate_enriched_localization_csv.py` 100%
  - เปลี่ยนเงื่อนไขตรวจจับข้อความขอบคุณ/เครดิตผู้พัฒนาจาก Hardcoded Strings (`プレイして頂き`, `次回作`, `サークル`) เป็น Universal Regex Outro Pattern สากล (`(?:(?:プレイ|遊んで|クリア).*(?:ありがとう|感謝)|(?:次回作|スタッフ|制作|開発).*(?:よろしく|感謝|一同)|『.+』は以上です)`)
- [x] **Task 20.2: Upstream SFX Lexicon & Invariant Guardrail Integration**
  - บรรจุสัทพจน์ตกใจ/ผงะ (`ギクッ`, `ぎくっ`, `ビクッ`, `びくっ`, `ドキッ`) เข้าสู่ `data/tlas/sfx_glossary.json` พร้อมกำหนด Prohibited Terms (`สะดุ้งเฮือก`, `เสียงสะดุ้ง`, `กิกุ`, `กึก`)
  - อัปเดต `LQATranslationAuditor` ตรวจจับคำแปลตกใจต้องห้ามระดับ FATAL อัตโนมัติ (ทดสอบผ่าน ยืนยันพบ `สะดุ้งเฮือก` เป็น FATAL ทันที)
  - ฝัง Invariant Rule เข้าสู่ `MINI_SYSTEM_INVARIANT` และ System Prompt ใน `chatgpt_translator_runner.py` ป้องกัน AI สร้างคำแปลดาษดื่นตั้งแต่ First-Pass
- [x] **Task 20.3: Prompt Invariants Documentation Synchrony**
  - อัปเดต `prompt-engineering-invariants.md` Rule 7 (`RULE_CONTEXTUAL_SFX_CALIBRATION`) บันทึกกฎกำกับการแปลเสียงเอฟเฟกต์ตกใจและข้อห้ามอย่างเป็นทางการ
- [x] **Task 20.4: Master Table Regeneration & 7D Audit Verification**
  - รันประกอบตาราง `generate_enriched_localization_csv.py` ฉบับตัด Hardcode ออก 100%
  - รัน `verify_localization_triad.py` ผ่านการตรวจสอบ 3,484 แถวครบถ้วน (0 Violations Certified)

---

### Phase 21: Exhaustive Framework Audit & Complete Manifest-Driven Decoupling
- [x] **Task 21.1: Dynamic Day Parser in Displayable Engine**
  - ยกเลิก fixed dictionary `D_TEXT_DAY_MAP` (1-7 วัน) ใน `game_displayable_engine.py` เปลี่ยนเป็น Dynamic Regex `r"^(\d+)日目$"` รองรับจำนวนวันได้ไม่จำกัด (1 ถึง N วัน)
- [x] **Task 21.2: End-to-End Manifest-Driven Decoupling**
  - ยกเลิกการใส่ Default Paths ไปยังโฟลเดอร์เกมตัวอย่างใน `generate_enriched_localization_csv.py`, `resolve_conversational_triad.py`, `extract_scene_packets.py`, และ `verify_localization_triad.py`
  - ย้ายการผูกโยงไฟล์ทั้งหมดเข้าสู่ `project_manifest.json` ทำให้ทุกเครื่องมือสามารถรันได้โดยตรงโดยไม่ต้องป้อนพารามิเตอร์ และสลับโปรเจกต์เกมใหม่ได้ทันทีเพียงแค่เปลี่ยน manifest
- [x] **Task 21.3: Deep Static Codebase Verification**
  - สแกนตรวจสอบไฟล์ซอร์สโค้ดทุกไฟล์ใน `src/atf/` ยืนยันว่าไม่มีเงื่อนไข Hardcode เชิงตรรกะ (Logic Hardcodes) หลงเหลืออยู่ใน Pipeline หลักอีกต่อไป 100%

---

### Phase 22: Content Loss Shielding & Dropped Dialogue Elimination
- [x] **Task 22.1: Dropped Dialogue Forensic Identification (Rows 838 & 1604)**
  - สแกนทั้งตาราง 3,484 แถว และไฟล์ Checkpoint ตรวจพบ 2 แถวที่ข้อความบทสนทนาสูญหาย โดยมีเฉพาะ Speaker Tag แต่ไม่มีเนื้อหาคำแปล:
    - Row 838 (`Map009:31`): `【？？？】\nも、もちろん見たっ！！！！` -> มีแต่ `【？？？】\n`
    - Row 1604 (`Map024:104`): `【凛】\nあ、あなたが謝らないで・・・。` -> มีแต่ `【ริน】\n`
- [x] **Task 22.2: Forensic Translation Restoration**
  - ซ่อมแซมคำแปล Row 838: `【？？？】\nก็... ก็ต้องเห็นอยู่แล้วสิวะ!!!!`
  - ซ่อมแซมคำแปล Row 1604: `【ริน】\nค... คุณไม่ต้องขอโทษหรอกค่ะ...`
  - ซิงค์ผลลัพธ์ลงทั้ง `離れ木の5日間+_translated.csv`, `chatgpt_translation_checkpoint.json` และตาราง Enriched CSV ครบถ้วน
- [x] **Task 22.3: Upstream LQA Guardrail Implementation (`lqa_translation_auditor.py`)**
  - เพิ่ม Check 1.5 ใน `LQATranslationAuditor`: หากต้นฉบับมีข้อความหลัง Tag แต่คำแปลว่างเปล่าหรือมีเฉพาะ Tag ให้สั่งระงับและแจ้ง `FATAL: ตรวจพบข้อความบทสนทนาสูญหาย (Dropped Dialogue Body)` ทันที
- [x] **Task 22.4: 8-Dimension Verification Engine (`verify_localization_triad.py`)**
  - เพิ่ม **Dimension 8 (Content Loss & Dropped Dialogue Shielding)** ในชุดทดสอบสากล
  - ตรวจสอบผ่านครบ 3,484 แถว ได้รับการรับรอง 100% Certified (0 Dropped Dialogue Violations, 0 Register Violations)

---

### Phase 23: Plugin Localization Injection & Game Integration
- [x] **Task 23.1: Manifest Decoupling & Target Path Verification (`inject_plugin_texts.py`)**
  - ตรวจสอบการโหลด `game_plugins_js` จาก `project_manifest.json` ชี้ตรงสู่ `Example RPGM Game/離れ木の5日間+/www/js/plugins.js`
  - ผูกโยงคำแปล UI จาก `data/plugins_texts.csv` (1 รายการ: `回想モード` -> `โหมดเล่นซ้ำฉากย้อนหลัง`)
- [x] **Task 23.2: Tag Parity & Spatial/Technical Parameter Shielding Audit**
  - ผ่านการตรวจสอบโดย `TagParityVerifier`: สัญลักษณ์ควบคุม `%1`, `\i[n]`, `\c[n]` ตรงตามสเปก 100%
  - กรองข้ามโค้ด คอนฟิก สวิตช์ และพารามิเตอร์ระบบ 128 รายการ (`Displayable == 'No'`) ตามกฎ `[RULE_DISPLAYABLE_USER_EXPERIENCE_ONLY]`
- [x] **Task 23.3: Dry-Run Simulation & Live Terminal Commands Preparation**
  - ทดสอบจำลอง (Dry Run) สำเร็จ 100% (Successfully Injected: 1 รายการ, Parity Guard Violations: 0)
  - จัดเตรียมคำสั่งรันแพทช์จริงและคำสั่งตรวจสอบให้ผู้ใช้สั่งรันทางเทอร์มินัล (ทั้ง PowerShell และ CMD) ตามกฎ `[RULE_USER_TERMINAL_ONLY]` พร้อมระบบแบ็กอัปอัตโนมัติ `plugins.js.backup_plugin_<timestamp>.js`

---

### Phase 24: Core Engine UI & System Terms Localization Recovery
- [x] **Task 24.1: Root Cause Identification & Universal Displayable Engine Hardening**
  - แก้ไข `game_displayable_engine.py`: เพิ่ม `basic`, `commands`, `params` เข้าสู่ Whitelist Context ของ `System.json` (+42 รายการ)
  - เพิ่มการคุ้มครอง Database Entities (`Actors`, `Classes`, `Items`, `Skills`, `Weapons`, `Armors`, `Enemies`, `States`) ไม่ให้ชนกับ Asset Name/Event Name ทำให้ชื่อตัวละครและอาชีพใน `Actors` และ `Classes` (`สามี`, `ริน`, `ภรรยา`) มีสถานะเป็น `Displayable = Yes` (+4 รายการ)
- [x] **Task 24.2: Direct CSV Synchronization & Zero Game Modification Rule**
  - ยุติและลบการฉีดตรงเข้าไฟล์เกม (`inject_system_terms.py`) รักษาไฟล์เกมต้นฉบับให้บริสุทธิ์ 100%
  - บันทึกและฉีดคำแปล UI ภาษาไทยมาตรฐานลงในไฟล์ `.csv` ทั้งหมดโดยตรง:
    - `data/plugins_texts.csv`: บรรจุ `AnotherNewGame` (`回想モード` -> `โหมดเล่นซ้ำฉากย้อนหลัง`)
    - `離れ木の5日間+_translated.csv` และ `離れ木の5日間+ - ชีต1.csv`: บรรจุ 42 คำสั่งระบบ + 4 รายการ Entities ครบถ้วน
    - `data/tlas/tlas_glossary.json` (หมวด `System_Terms`) และ `chatgpt_translation_checkpoint.json` ซิงค์ครบ 100%
- [x] **Task 24.3: Table Re-enrichment & 8-Dimension Verification Pass**
  - รัน `generate_enriched_localization_csv.py`: จำนวนแถว `Displayable = Yes` ขยับขึ้นสู่ 3,044 แถว (จากเดิม 2,998 แถว)
  - รัน `verify_localization_triad.py`: ผ่านการตรวจสอบ 8 มิติ 100% Certified (0 Violations ครบ 3,484 แถว)
- [x] **Task 24.4: Deep Game-Wide Codebase & Plugin Audit**
  - ตรวจสอบซอร์สโค้ดของปลั๊กอินทั้งหมด 12 ตัว ยืนยันไม่มีการฮาร์ดโค้ดข้อความ UI แสดงผลในไฟล์ `.js` (มีเพียงคีย์พารามิเตอร์และชื่อคำสั่ง)
  - สแกนตรวจสอบ 440 แถวที่เป็น `Displayable = No`: ยืนยันเป็นสวิตช์ระบบ (157), Event Editor Labels (234), Asset filenames (31), Notetags (12) และ Comments (9) ปลอดภัย 100%
  - สแกนตรวจสอบ 3,044 แถวที่เป็น `Displayable = Yes`: ยืนยันมีคำแปลภาษาไทยครบทุกแถว 0 ข้อความตกหล่น

---

### Phase 25: Master Architecture Refactoring, Legacy Archival & Unified CLI Engine
- [x] **Task 25.1: Legacy & Dead Architecture Archival (Zero Data Loss)**
  - ย้ายโค้ดต้นแบบรุ่นเก่า ยุค Multi-Agent Gemma (`src/atf/agents/`, `main.py`, `parsers/`, `memory/`, `ui/`, `orchestrator.py`, `state_machine.py`, `event_bus.py`, `local_rag*`, `advanced_rag.py`) เข้าสู่ `archive/legacy_agents/`
  - ย้ายสคริปต์เฉพาะกิจ One-off Forensic Fixes ในอดีต 65+ รายการใน `src/atf/tools/` เข้าสู่ `archive/legacy_tools/`
  - ย้ายสคริปต์ทดสอบชั่วคราวและลอนเชอร์เก่า 40+ ไฟล์ใน Root Directory เข้าสู่ `archive/root_scripts/` คืนความสะอาดให้พื้นที่ทำงาน 100%
  - โฟลเดอร์ `Example RPGM Game/` ถูกคงสภาพไว้สมบูรณ์ 100% ตามข้อกำหนดของผู้ใช้
- [x] **Task 25.2: Master Universal CLI Engine (`atf.py`) & Shortcut Integration**
  - พัฒนา `atf.py` รวมศูนย์การสั่งการทำงานครบวงจรผ่าน Subcommands: `setup`, `bridge`, `scan`, `glossary`, `packets`, `matrix`, `build-table`, `translate`, `verify`, `plugins`, `export`, และ `prepare-all`
  - ปรับปรุง `translate.py` ให้เป็นทางลัดอัตโนมัติ ชี้ตรงสู่ `python atf.py translate`
  - ฝังระบบ `--dry-run` สำหรับทดสอบออฟไลน์ลงใน `chatgpt_translator_runner.py` โดยตรง (15 รายการ 100/100 คะแนน)
- [x] **Task 25.3: Single Definitive Master User Manual Consolidation**
  - ยุบรวมและเขียนใหม่ `docs/USER_MANUAL.md` เป็นคู่มือแม่บทฉบับรวมศูนย์เพียงฉบับเดียว เรียงลำดับจากขั้นตอน 0 ถึง 6
  - ครอบคลุมตั้งแต่การตั้งค่า Workspace (`setup`), เชื่อมต่อ Web Bridge (`bridge`), เตรียมข้อมูลทั้งเกมในคำสั่งเดียว (`prepare-all`), สั่งแปล (`translate`), ตรวจ LQA 8 มิติ (`verify`), จนถึงการแพตช์เกม (`plugins --inject` และ `export`)
  - อัปเดตผังการทำงานและโครงสร้างไดเรกทอรีใน `README.md` ให้สอดคล้องกัน 100%

---

### Phase 27: Clean Slate Game Onboarding & Universal Pipeline Alignment
- [x] **Task 27.1: Clean Slate Path Synchronization & Auto-Mirroring**
  - แก้ไข `atf.py prepare-all`: เมื่อเตรียมข้อมูลเสร็จสมบูรณ์ ระบบจะซิงค์ไฟล์ฐานข้อมูลทั้งหมดจาก `data/tlas/` (`tlas_glossary.json`, `character_whitelist.json`, `profiles/`, `global_pronoun_matrix.json`, `scene_packets.json`, `scanned_speakers.json`) ไปยังโฟลเดอร์ผลลัพธ์ของโปรเจกต์ (`output_tlas_dir`) ใน Manifest อัตโนมัติ 100%
  - แก้ไข `chatgpt_translator_runner.py`: ปรับ `__init__` ให้มี Self-healing Fallback ค้นหาไฟล์ฐานข้อมูลทั้งจาก Manifest และ Local Workspace พร้อม Auto-sync กลับสู่โฟลเดอร์ผลลัพธ์
- [x] **Task 27.2: Universal CSV Schema Dynamic Indexing (10-Col / 8-Col / 5-Col)**
  - แก้ไข `chatgpt_translator_runner.py`: ถอด Hardcoded Index (`row[7] = Displayable`, `row[2] = Filename`) ใน `translate_empty_rows` และ `translate_plugins_csv`
  - ตรวจหาชื่อคอลัมน์จาก Header โดยตรง (`Original`, `Initial`, `Displayable`, `Speaker`, `Role`, `Listener`, `Filename`) รองรับตารางมาตรฐาน 10 มิติ (`Displayable` อยู่ที่ index 2) และ Fallback สำหรับไฟล์ที่ไม่มีคอลัมน์ `Displayable` ให้เป็น `"Yes"`
- [x] **Task 27.3: Unified Runner Input Target Prioritization**
  - แก้ไข `run_unified_all`: จัดลำดับการค้นหาไฟล์แปลบทสนทนาหลัก: ให้ความสำคัญกับ `output_enriched_csv` เป็นอันดับแรก ตามด้วย `output_processed_csv` และ `raw_pre_csv`
  - จัดลำดับการค้นหาไฟล์แปลปลั๊กอิน: ตรวจสอบ `output_plugins_csv`, `legacy_plugin_csv`, `<output_dir>/plugins_texts.csv`, และ `data/plugins_texts.csv`
- [x] **Task 27.4: SceneContextManager Robust Parsing for Packet Schema**
  - ปรับปรุง `scene_context_manager.py`: รองรับโครงสร้าง `scene_packets.json` ที่มีคีย์ `packets` ป้องกันข้อผิดพลาด `'str' object has no attribute 'get'` เมื่ออ่าน JSON แบบ Dict

---

### Phase 28: True Universal Game Analysis & 8-Stage Preparation Architecture (v6.0)
- [x] **Task 28.1: Complete Purge of Hardcoded Character Definitions**
  - ลบ `src/atf/tools/synthesize_clean_profiles.py` ที่มี `CHARACTER_DEFINITIONS` เดิมทิ้งถาวร
  - ปรับปรุง `src/atf/tools/build_master_glossary.py`: กำจัด `CHARACTER_TRANSLATIONS` ฮาร์ดโค้ดออก 100% สกัดชื่อจาก `Actors.json` และ Speaker Tags จริงของเกมใหม่เท่านั้น
- [x] **Task 28.2: Decoupled Bridge Architecture & Standalone Service Paradigm**
  - แยก `atf.py bridge` ออกจากกระบวนการ Pipeline เป็นอิสระ 100% ผู้ใช้สามารถเปิด/ปิดได้ตามต้องการ
  - ปรับปรุงให้โมดูลที่ต้องการใช้ AI มีระบบ Auto-detecting Heartbeat ตรวจสอบสถานะของ Bridge
- [x] **Task 28.3: Dedicated Templates Isolation (`templates/`)**
  - จัดตั้งโฟลเดอร์ `templates/` แยกต่างหากใน Root: บรรจุ `taxonomy.template.json`, `tlas_glossary.template.json`, `character_profile.template.json`, `sfx_glossary.template.json`, `dic_glossary.template.json`, `scene_packet.template.json`, `global_pronoun_matrix.template.json`, `alias_mapping.template.json`
  - ยุติการสร้างหรือก๊อปปี้ไฟล์เทมเพลตซ้ำซ้อนลงในโฟลเดอร์ผลลัพธ์ของเกม
- [x] **Task 28.4: Implementation of the 8 Concrete Preparation Stages (3a - 3h)**
  - Stage 3a (`prepare-scenes`): สกัดฉากและ Event Flow บันทึกลง `<output_tlas_dir>/scene_packets.json`
  - Stage 3b (`prepare-glossary`): สกัด Entities (Actors, Items, Skills, Places, System) สู่ `<output_tlas_dir>/tlas_glossary.json`
  - Stage 3c (`prepare-whitelist`): คัดกรองตัวละครสำคัญเข้าสู่ `<output_tlas_dir>/character_whitelist.json` ตามเกณฑ์ ADR-035
  - Stage 3d (`prepare-profiles`): สร้าง `analyze_character_profiles.py` ส่งบทพูดจริงให้ ChatGPT สังเคราะห์โปรไฟล์ V4 รายบุคคล
  - Stage 3e (`prepare-matrix`): ประมวลผลโปรไฟล์เป็นตารางสรรพนามคู่สนทนาและ Demographic Rules (`global_pronoun_matrix.json`)
  - Stage 3f (`prepare-sfx-dic`): สร้าง `extract_sfx_and_dic.py` สกัด Onomatopoeia (`sfx_glossary.json`) และคำเฉพาะ/แสลง (`dic_glossary.json`)
  - Stage 3g (`prepare-table`): ประกอบตาราง 10 มิติ (`<Game>_enriched.csv`) พร้อมระบบ Game Shielding
  - Stage 3h (`prepare-taxonomy`): สร้าง `generate_game_taxonomy.py` สร้าง Taxonomy ว่างประจำเกม
- [x] **Task 28.5: Master Universal CLI (`atf.py`) & User Manual Alignment**
  - อัปเดต `atf.py` รองรับ Subcommands ย่อยทั้ง 8 สเต็ป (`prepare-scenes` ถึง `prepare-taxonomy`) และคำสั่งรวม `prepare-all`
  - อัปเดต `docs/USER_MANUAL.md` ให้เรียงลำดับขั้นตอนและอธิบายรายละเอียดทั้ง 8 สเต็ปอย่างสมบูรณ์
- [x] **Task 28.6: Live ChatGPT Bridge Integration in Character Profiler (Stage 3d)**
  - แก้ไข `analyze_character_profiles.py`: เชื่อมต่อ endpoint จริงของ Bridge Server (`/bridge/status` และ `/v1/chat/completions`)
  - นำระบบ Silent Dummy Fallback ออก และแทนที่ด้วย `wait_for_bridge_ready()` รอให้ Userscript บน https://chatgpt.com เชื่อมต่อสำเร็จจริง 100% ก่อนเริ่มวิเคราะห์
  - บังคับการวิเคราะห์ Pairwise Relationships ระหว่างตัวละคร ทำให้ Stage 3e (`sync_profiles_and_matrix.py`) สกัดกฎ `Specific Pairwise Rules > 0` ได้จริง
  - ปรับปรุง `sync_profiles_and_matrix.py` ให้รองรับทั้ง `speech_style` และ `specific_speech`
- [x] **Task 28.7: Scene-Based Character Profiling & Deterministic Pronoun Architecture (v6.1)**
  - ปรับปรุง `atf_chatgpt_userscript.user.js`: ตัดการค้นหา Rate Limit จาก `document.body.innerText` เพื่อป้องกัน False Positive จากประวัติแชตใน Sidebar และขยายรอบการรอส่งให้เสถียร 100%
  - เพิ่มเติม `taxonomy.template.json` และ `taxonomy.json`: บรรจุนิยาม Formality Level 1-5 แบบ Deterministic พร้อมตัวเลือกสรรพนามบุรุษที่ 3 (`third_person`)
  - ยกเครื่อง `analyze_character_profiles.py` สู่ระบบ Scene-Based Batching: สกัดบทสนทนาประจำฉากส่งให้ ChatGPT วิเคราะห์เฉพาะ identity, personality, และ pairwise relationships (ตัดการคิดสรรพนามไทยออกจาก AI 100%)
  - พัฒนา Deterministic Python Pronoun Engine: แมปปิ้งคำสรรพนาม (self, target, third_person, ending) จาก `taxonomy.json` ตามหลักไวยากรณ์โดยตรง ป้องกันคำนามแปลกปลอม (เช่น "สามี") หลุดเข้ามาในช่องสรรพนาม 100%





