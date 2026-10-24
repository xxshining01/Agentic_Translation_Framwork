# Software Architecture Document (SAD)

**หมายเลขเอกสาร:** SAD-004

**ชื่อระบบ:** Rule-Based Dialogue Localization Processing Pipeline (TLAS Localization Engine)

**เวอร์ชันระบบ:** 2.0

**สถานะ:** Draft / Proposed Architecture

---

## 1. ภาพรวมสถาปัตยกรรมระบบ (System Overview & Architectural Vision)

ระบบ **Rule-Based Dialogue Localization Processing Pipeline** ถูกออกแบบขึ้นเพื่อเป็นโครงสร้างพื้นฐานในการประมวลผล บริหารจัดการ และสกัดบริบทสไตล์ภาษาไทยสำหรับการแปลสคริปต์บทสนทนาในเกม RPGM และ Ren'Py ที่มีขนาดใหญ่

แนวคิดหลักของสถาปัตยกรรมนี้คือ **Data-Driven Processing Pipeline** ที่แยกการทำงานออกเป็น 3 ส่วนหลักโดยเด็ดขาด:

1. **Raw Game Data (Input Layer):** ไฟล์สคริปต์ดิบจากเอนจิ้นเกม (เช่น `chunk_p1_0000.json`) ที่ระบุข้อมูล Map, Event Conditions, Timeline Phase, Control Codes และก้อนเนื้อหาบทสนทนา
2. **Context & Business Logic Layer (Processing Engine):** ฐานข้อมูลตัวละคร (`character_profile.json`) และฐานข้อมูลกฎทางภาษา (`taxonomy.json`) ที่ประมวลผลผ่านตรรกะ **3-Tier Fallback Resolution**
3. **Localization Guideline Output Layer (Output Interface):** ผลลัพธ์ข้อมูลบทสนทนาที่ถูกทำความสะอาด แยกผู้พูด-ผู้ฟัง พร้อมแนบไกด์ไลน์สรรพนาม หางเสียง และโทนภาษาเพื่อส่งต่อให้นักแปล

```
[Raw Chunk JSON] 
       │
       ▼
[1. Data Parser & Cleaner] ──(Strip Control Codes / Extract Speaker & Listener)
       │
       ▼
[2. Character State Evaluator] ──(Check Timeline Phase -> Load Base / Delta Profile)
       │
       ▼
[3. Rule Engine & Priority Evaluator] ──(Evaluate Tier 1 -> Tier 2 -> Tier 3)
       │
       ▼
[4. Output Formatter] ──(Generate Structured Translation Grid / Guidelines)

```

---

## 2. เป้าหมายและข้อจำกัดทางสถาปัตยกรรม (Architectural Goals & Constraints)

### 2.1 เป้าหมายหลัก (Core Goals)

* **High Maintainability & Decoupling:** สามารถปรับแต่งกฎภาษาไทยใน `taxonomy.json` ได้โดยไม่ต้องแก้ไขข้อมูลใน Character Profile หรือโค้ดตัวประมวลผล
* **Context Consistency:** รับประกันความแม่นยำของการใช้สรรพนามและหางเสียงตามสถานะความสัมพันธ์และพัฒนาการของตัวละครข้าม Timeline Phase
* **Scalability for Generic NPCs:** จัดการสรรพนามสำหรับตัวละครประกอบหรือคนแปลกหน้าได้อย่างสมบูรณ์ โดยไม่ต้องเพิ่มข้อมูลขยะลงใน Character Profile
* **Preservation of Game Syntax:** รักษารหัสควบคุม (Control Codes) ของเอนจิ้นเกม (เช่น `\|`, `\fb`, `\C[0]`) ไม่ให้เสียหายระหว่างกระบวนการแปล

### 2.2 ข้อจำกัด (Constraints)

* **Input Structure Variation:** ไฟล์ Chunk Input สกัดมาจากเอนจิ้นเกมที่มีการรวบรวมประโยคสนทนาหลายบรรทัดไว้ในก้อน `text` เดียวกัน จึงต้องมีกระบวนการ Line-by-Line Parsing ก่อนนำไปประมวลผล
* **Human-in-the-Loop Dependency:** ระบบทำการสร้าง "ไกด์ไลน์" เพื่อช่วยเหลือและควบคุมกรอบการแปล แต่การตัดสินใจขั้นสุดท้ายเกี่ยวกับความสละสลวยทางไวยากรณ์ (เช่น การเลือกรูปประโยค คะ/ค่ะ) ยังต้องใช้นักแปลมนุษย์เป็นผู้ตรวจทาน

---

## 3. ส่วนประกอบหลักของระบบ (System Component Architecture)

ระบบประกอบด้วย 5 มอดูลหลักที่ทำงานร่วมกันแบบ Sequential Pipeline:

```
+-----------------------------------------------------------------------+
|                       TLAS LOCALIZATION ENGINE                        |
+-----------------------------------------------------------------------+
|                                                                       |
|  +------------------------+        +-------------------------------+  |
|  |  1. Data Parser &      | -----> |  2. Character Profile & State |  |
|  |     Cleaner            |        |     Manager                   |  |
|  +------------------------+        +-------------------------------+  |
|               │                                    │                  |
|               ▼                                    ▼                  |
|  +-----------------------------------------------------------------+  |
|  |  3. Context Resolution & Priority Engine                        |  |
|  |     - Tier 1: Exact Relationship Match                          |  |
|  |     - Tier 2: Target Condition & Social Taxonomy Match           |  |
|  |     - Tier 3: Base Profile Fallback                             |  |
|  +-----------------------------------------------------------------+  |
|                               │                                       |
|                               ▼                                       |
|  +-----------------------------------------------------------------+  |
|  |  4. Grammar & Extension Post-Processor                          |  |
|  |     - Thai Particle Base Resolution (คะ/ค่ะ/ครับ/จ้ะ/จ๊ะ)           |  |
|  |     - Vocal Extension & Tone Guidelines (คร้าบ/ค่าา)             |  |
|  +-----------------------------------------------------------------+  |
|                               │                                       |
|                               ▼                                       |
|  +-----------------------------------------------------------------+  |
|  |  5. Translation Output Formatter (Grid / Spreadsheet / API)     |  |
|  +-----------------------------------------------------------------+  |
|                                                                       |
+-----------------------------------------------------------------------+

```

### 3.1 Data Parser & Cleaner Module

* **หน้าที่:** รับไฟล์ `chunk_px_xxxx.json` สกัดข้อมูลในอาร์เรย์ `raw_dialogues`
* **การทำงาน:**
1. อ่านค่า `timeline_phase`, `source`, `category`, และ `faces_used`
2. ใช้ Regular Expression สกัดผู้พูดออกจากรูปแบบ `[Speaker:] Text`
3. หั่นก้อนข้อความ (`text`) ออกเป็นรายการประโยคย่อย (Line-by-Line Dialogues)
4. ตรวจจับและทำ Masking รหัสควบคุมการแสดงผลของเกม (`\|`, `\fb`, `\C[x]`, `\n`) เพื่อแยกออกจากเนื้อหาข้อความจริง



### 3.2 Character Profile & State Manager

* **หน้าที่:** จัดการข้อมูลตัวละคร และประเมินสภาวะของตัวละครตามกาลเวลา
* **การทำงาน:**
1. ดึงข้อมูล Base Identity (`gender`, `age`, `species`) และ `base_speech_style`
2. ตรวจสอบค่า `timeline_phase` จากสคริปต์ หากพบว่าตรงกับเงื่อนไขใน `timeline_states` ระบบจะทำการซ้อนทับข้อมูล (Apply Delta Overrides) เช่น ปรับปรุงค่า `relationships` หรือเปลี่ยนระดับความทางการ (`formality_level`)



### 3.3 Context Resolution & Priority Engine (Core Rule Engine)

* **หน้าที่:** ประมวลผลหาชุดสรรพนามและหางเสียงที่ถูกต้องที่สุดด้วยตรรกะ **3-Tier Fallback**
* **การทำงาน:**
* **Tier 1 (Exact Match):** ค้นหา `Listener_ID` ในรายการ `relationships` ของ `Speaker_Profile` หากพบ ให้ดึงค่า `specific_speech` มาใช้งานทันที
* **Tier 2 (Target Condition Match):** หากไม่พบใน Tier 1 ให้ดึงข้อมูลคุณลักษณะของผู้ฟัง (`Listener_Profile`) ไปจับคู่กับ `target_conditions` ใน `taxonomy.json` ร่วมกับแท็กบริบท (เช่น `EMO`, `TON`, `SIT`) เพื่อคำนวณหา Rule ที่ได้ `priority_score` สูงสุด
* **Tier 3 (Base Fallback):** หากไม่เข้าเงื่อนไขใด ให้ดึงค่าจาก `base_speech_style` ของผู้พูดมาใช้เป็นค่าตั้งต้น



### 3.4 Grammar & Extension Post-Processor

* **หน้าที่:** ตรวจสอบโครงสร้างประโยคภาษาไทยและแนะนำรูปแบบการลงท้าย
* **การทำงาน:**
1. วิเคราะห์รูปประโยค (ประโยคบอกเล่า/ตอบรับ vs ประโยคคำถาม/เรียกขาน) เพื่อกำหนดการใช้รูปคำ "คะ" หรือ "ค่ะ" และ "จ๊ะ" หรือ "จ้ะ"
2. ตรวจสอบแท็กอารมณ์/สไตล์การพูด (เช่น `TON_PLAYFUL`, `SPR_LAZY`) เพื่อสร้างคำแนะนำการลากเสียง (เช่น เปลี่ยน "ครับ" เป็น "คร้าบ" หรือ "ค่ะ" เป็น "ค่าา")



### 3.5 Translation Output Formatter

* **หน้าที่:** จัดรูปแบบข้อมูลให้อยู่ในโครงสร้างตารางที่พร้อมสำหรับการทำงานของนักแปล (ตารางแสดงประโยคต้นฉบับ, รหัสควบคุม, สรรพนามแนะนำ, หางเสียงแนะนำ, และช่องสำหรับพิมพ์คำแปล)

---

## 4. แผนผังการไหลของข้อมูล (Data Flow Architecture)

```
[Input: Raw Chunk Entry]
  │
  ├─> Extract Metadata: timeline_phase = 2149, faces_used = ["JinniePast", "JinniePastA"]
  │
  ├─> Parse Raw Text Line: "[Lyra:] Thought you were toooo busy being a pomeranian doggo for Hikari."
  │     ├─> Speaker_ID: "CHAR_LYRA_001"
  │     ├─> Listener_ID: "CHAR_DAN_001" (Derived from Context / Face Array)
  │     └─> Cleaned Text: "Thought you were toooo busy being a pomeranian doggo for Hikari."
  │
  ├─> Evaluate Character State (Timeline Phase: 2149)
  │     └─> Load Lyra Profile @ State 2149 -> Personality: PER_SOC_RUDE, Tone: TON_SARCASTIC
  │
  ├─> Process 3-Tier Resolution Logic
  │     ├─> Check Tier 1: Is Dan in Lyra.relationships? -> Found (REL_WORK_COLLEAGUE)
  │     ├─> Check Specific Speech Override:
  │     │     ├─> self_pronoun: "ฉัน"
  │     │     ├─> target_pronoun: "นาย"
  │     │     └─> tone: TON_SARCASTIC
  │     └─> Resolution Output: { Self: "ฉัน", Target: "นาย", Ending: "ย่ะ/หรอกนะ" }
  │
  └─> Generate Output Matrix Row:
        ┌─────────────┬───────────┬──────────┬──────────────────────┬──────────────────────────────────┐
        │ Speaker     │ Listener  │ Tone/EMO │ Linguistic Guideline │ Target Translation Text          │
        ├─────────────┼───────────┼──────────┼──────────────────────┼──────────────────────────────────┤
        │ Lyra        │ Dan       │ Sarcastic│ ฉัน - นาย / หรอกนะ   │ [รอการประมวลผลแปลโดยนักแปล]     │
        └─────────────┴───────────┴──────────┴──────────────────────┴──────────────────────────────────┘

```

---

## 5. การจัดการกรณีขอบเขตและข้อผิดพลาด (Edge Cases & Error Handling)

1. **ไม่พบ Listener ID ในสคริปต์ (Unidentified Listener):**
* *การจัดการ:* ระบบจะกำหนดให้ Listener มีสถานะเป็น `REL_STRANGER` อัตโนมัติ เพื่อส่งข้อมูลเข้ากระบวนการ Tier 2 (Target Condition Match)


2. **ประโยคที่ไม่มีผู้พูดชัดเจน (System Text / Narration / Monologue):**
* *การจัดการ:* หากประโยคขึ้นต้นด้วย `[Unknown]` หรือไม่มีแท็กผู้พูด ระบบจะบายพาสการคำนวณสรรพนาม และกำหนดสไตล์เป็นภาษาบรรยาย (Neutral Register)


3. **การพบ Control Codes แปลกปลอม:**
* *การจัดการ:* ตัว Parser จะทำการใช้ Regular Expression สกัดแยก Control Codes ทั้งหมดไปเก็บไว้ในอาร์เรย์ `retained_tags` และใช้อักขระแทนที่ (Placeholder) ก่อนส่งข้อความเข้ากระบวนการแปล และนำ Control Codes กลับมาใส่ตำแหน่งเดิมในขั้นตอนการสร้างไฟล์ประกอบกลับเข้าเกม (Re-assembly)
