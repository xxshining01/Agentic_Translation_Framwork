# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-008

**ชื่อระบบ:** Rule-Based Dialogue Localization Processing Pipeline (TLAS Localization Engine)

**เวอร์ชันระบบ:** 2.0

**สถานะ:** Draft / Proposed Design

---

## 1. ภาพรวมและขอบเขตเอกสาร (Overview & Scope)

เอกสาร **Software Design Document (SDD)** ฉบับนี้อธิบายรายละเอียดการออกแบบเชิงเทคนิคในระดับต่ำ (Low-Level Design) สำหรับระบบ **TLAS Localization Engine** ตามที่ระบุไว้ในเอกสารสถาปัตยกรรม SAD-004 และข้อตกลง ADR-012

เอกสารนี้ครอบคลุมการออกแบบโครงสร้างคลาส (Class Diagram/Component Structure), สกีมาข้อมูล (JSON Schemas), ตรรกะและอัลกอริทึม (Algorithms & Pseudo-code), การประมวลผลข้อความไวยากรณ์ไทย และการจัดการกรณีขอบเขต (Edge Cases)

---

## 2. นิยามโครงสร้างข้อมูลและสกีมา (Data Models & Schemas)

### 2.1 Object: `ParsedDialogueLine`

โครงสร้างข้อมูลบทสนทนาเดี่ยวที่ผ่านการ Parse และทำความสะอาดแล้ว

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ParsedDialogueLine",
  "type": "object",
  "properties": {
    "line_id": { "type": "string" },
    "source_event": { "type": "string" },
    "timeline_phase": { "type": "integer" },
    "speaker_id": { "type": "string" },
    "listener_id": { "type": ["string", "null"] },
    "raw_text": { "type": "string" },
    "cleaned_text": { "type": "string" },
    "retained_control_codes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": { "code": { "type": "string" }, "index": { "type": "integer" } }
      }
    },
    "dynamic_tags": {
      "type": "object",
      "properties": {
        "emotion": { "type": ["string", "null"] },
        "tone": { "type": ["string", "null"] },
        "intent": { "type": ["string", "null"] }
      }
    }
  },
  "required": ["line_id", "timeline_phase", "speaker_id", "cleaned_text"]
}

```

### 2.2 Object: `TranslationGuidelineOutput`

ผลลัพธ์การประมวลผลไกด์ไลน์ที่ส่งต่อไปยังตารางงานของนักแปล

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TranslationGuidelineOutput",
  "type": "object",
  "properties": {
    "line_id": { "type": "string" },
    "speaker_id": { "type": "string" },
    "listener_id": { "type": ["string", "null"] },
    "source_text_clean": { "type": "string" },
    "resolved_tier": { "type": "integer", "enum": [1, 2, 3] },
    "matching_rule_id": { "type": ["string", "null"] },
    "linguistic_guidelines": {
      "type": "object",
      "properties": {
        "self_pronoun": { "type": "string" },
        "target_pronoun": { "type": "string" },
        "root_ending_particle": { "type": "string" },
        "formality_level": { "type": "integer" },
        "recommended_tone": { "type": "string" },
        "vocal_extension_flag": { "type": "boolean" },
        "notes": { "type": "string" }
      },
      "required": ["self_pronoun", "target_pronoun", "root_ending_particle"]
    }
  }
}

```

---

## 3. รายละเอียดการออกแบบมอดูล (Detailed Component Specifications)

```
                       +-------------------------------+
                       |   RawChunkParser              |
                       +-------------------------------+
                       | + parse_chunk(json_data)      |
                       | + mask_control_codes(text)    |
                       +---------------+---------------+
                                       |
                                       v
                       +-------------------------------+
                       |   CharacterStateManager       |
                       +-------------------------------+
                       | + get_active_profile(phase)   |
                       | + apply_timeline_delta()      |
                       +---------------+---------------+
                                       |
                                       v
                       +-------------------------------+
                       |   PriorityRuleEngine          |
                       +-------------------------------+
                       | + evaluate_3tier_fallback()   |
                       | + match_target_conditions()   |
                       +---------------+---------------+
                                       |
                                       v
                       +-------------------------------+
                       |   ThaiGrammarProcessor        |
                       +-------------------------------+
                       | + resolve_particles(type)     |
                       | + apply_vocal_extensions()    |
                       +---------------+---------------+
                                       |
                                       v
                       +-------------------------------+
                       |   OutputFormatter             |
                       +-------------------------------+
                       | + render_translation_grid()   |
                       +-------------------------------+

```

### 3.1 Data Parser & Cleaner Module (`RawChunkParser`)

#### การทำงานหลัก:

1. **Line Splitting:** สกัดสายอักขระในคีย์ `text` ของแต่ก้อนข้อมูล และหั่นบรรทัดตาม `\n`
2. **Speaker Extraction Regex:**
* Pattern: `^\[([^\]]+):\]\s*(.*)$`
* Group 1 = `Speaker_ID` / Group 2 = `Dialogue_Body`


3. **Control Code Masking Regex:**
* Pattern: `(\\[|\\|\\.|\\fb|\\fi|\\C\[\d+\])`
* นำตัวอักขระควบคุมไปจัดเก็บไว้ใน `retained_control_codes` พร้อมระบุตำแหน่ง Index และแทนที่ด้วยอักขระซ่อนสัญลักษณ์ (Placeholder) เพื่อส่งข้อความสะอาดไปประมวลผลต่อ



---

### 3.2 Character Profile & State Manager (`CharacterStateManager`)

#### การทำงานหลัก:

จัดการประเมิน `timeline_phase` ของบรรทัดบทสนทนากับรายการ `timeline_states` ในโปรไฟล์ตัวละคร

```
  Base Character Profile
  ┌──────────────────────────────────────────┐
  │ ID: CHAR_ALICE_001                       │
  │ Formality: 7                             │
  │ Rel with Bob: REL_FRIEND (ฉัน - นาย)     │
  └────────────────────┬─────────────────────┘
                       │
                       │  Event: timeline_phase >= 2149
                       ▼
  Timeline State Evaluator (Apply Delta)
  ┌──────────────────────────────────────────┐
  │ State: STATE_CH2_AFTER_BETRAYAL          │
  │ Formality Override: 3                    │
  │ Rel Delta with Bob: REL_ENEMY (ฉัน - แก) │
  └────────────────────┬─────────────────────┘
                       │
                       ▼
  Active Profile (Sent to Rule Engine)

```

---

### 3.3 Context Resolution & Priority Engine (`PriorityRuleEngine`)

อัลกอริทึมหลักในการประมวลผลแบบ **3-Tier Fallback Logic**:

```python
def evaluate_3tier_fallback(speaker_profile, listener_profile, dynamic_tags, taxonomy_rules):
    # --- TIER 1: EXACT MATCH VIA RELATIONSHIPS ---
    if listener_profile is not None:
        relationship_entry = find_relationship(speaker_profile.relationships, listener_profile.character_id)
        if relationship_entry and relationship_entry.specific_speech:
            return {
                "resolved_tier": 1,
                "rule_id": "TIER1_EXACT_RELATIONSHIP",
                "guidelines": relationship_entry.specific_speech
            }

    # --- TIER 2: TARGET CONDITION & TAXONOMY MATCHING ---
    highest_score = -1
    best_matching_rule = None

    for rule in taxonomy_rules.pronoun_mapping_rules:
        # Check Speaker Conditions
        if not match_conditions(speaker_profile, rule.conditions, dynamic_tags):
            continue
        
        # Check Target (Listener) Conditions
        if listener_profile is not None:
            if not match_conditions(listener_profile, rule.target_conditions, dynamic_tags):
                continue
        elif rule.target_conditions: 
            # Rule requires target conditions but listener is unknown
            continue

        # Score Evaluation
        if rule.priority_score > highest_score:
            highest_score = rule.priority_score
            best_matching_rule = rule

    if best_matching_rule is not None:
        return {
            "resolved_tier": 2,
            "rule_id": best_matching_rule.rule_id,
            "guidelines": best_matching_rule.pronouns
        }

    # --- TIER 3: BASE PROFILE FALLBACK ---
    return {
        "resolved_tier": 3,
        "rule_id": "TIER3_BASE_FALLBACK",
        "guidelines": speaker_profile.base_speech_style
    }

```

---

### 3.4 Grammar & Extension Post-Processor (`ThaiGrammarProcessor`)

ทำการปรับปรุงคำลงท้าย (Ending Particles) ตามประเภทประโยคและสภาวะอารมณ์

#### กฎการปรับใช้คำลงท้ายภาษาไทย:

| Root Particle | Sentence Type (ประเภทประโยค) | Dynamic Tag / Emotion | Output Guideline (ผลลัพธ์) |
| --- | --- | --- | --- |
| **คะ/ค่ะ** | ประโยคบอกเล่า / ตอบรับ | Normal | **ค่ะ** (เช่น "รับทราบค่ะ") |
| **คะ/ค่ะ** | ประโยคคำถาม / เรียกขาน | Normal | **คะ** (เช่น "อะไรนะคะ", "พี่คะ") |
| **คะ/ค่ะ** | ประโยคบอกเล่า / ตอบรับ | `TON_PLAYFUL` | **ค่า / ค่าา** (ลากเสียง) |
| **ครับ** | ประโยคบอกเล่า / คำถาม | Normal | **ครับ** |
| **ครับ** | ประโยคบอกเล่า | `SPR_LAZY` / `TON_PLAYFUL` | **คร้าบ / ค้าบ** (ลากเสียง) |
| **จ้ะ/จ๊ะ** | ประโยคบอกเล่า | Normal | **จ้ะ** |
| **จ้ะ/จ๊ะ** | ประโยคคำถาม | Normal | **จ๊ะ** |

---

## 4. การจัดการกรณีขอบเขตและการกู้คืนข้อผิดพลาด (Edge Cases & Exception Handling)

```
               [Incoming Line Processing]
                           │
             Is Speaker ID Identified?
            ┌──────────────┴──────────────┐
           YES                            NO
            │                             │
            ▼                             ▼
   [Process Standard          [Apply Unknown/Narrator
    3-Tier Pipeline]           Fallback Guidelines]
            │                             │
            └──────────────┬──────────────┘
                           │
             Are Control Codes Intact?
            ┌──────────────┴──────────────┐
           YES                            NO
            │                             │
            ▼                             ▼
   [Proceed to Output          [Trigger Code Recovery
    Formatting]                 & Alert Log]

```

### 4.1 Missing Listener Context

* **Scenario:** ผู้พูดกำลังพูดลอยๆ (Monologue) หรือสคริปต์ไม่ได้ระบุ `Listener_ID`
* **Handling:** ระบบจะตั้งค่า `listener_id = null` และข้ามการประมวลผล Tier 1 เพื่อให้ระบบเข้าสู่ Tier 2 โดยประเมินกฎที่ไม่อ้างอิง `target_conditions` หรือตกไปใช้ Tier 3 (Base Speech Style)

### 4.2 Code Corruption / Missing Tag Recovery

* **Scenario:** นักแปลเผลอลบแท็กสั่งการของเอนจิ้นเกม (เช่น `\C[0]` หรือ `\|`) ในขั้นตอนการแปล
* **Handling:** ระบบ Re-assembly จะเปรียบเทียบ `retained_control_codes` จากไฟล์ `ParsedDialogueLine` ต้นฉบับ หากพบว่าแท็กหายไป ระบบจะทำการแจ้งเตือน (Warning Flag) พร้อมระบุตำแหน่งบรรทัดเพื่อให้ทำการแก้ไขทันที

---

## 5. สรุปความเชื่อมโยงของระบบ (Execution Flow Summary)

โครงสร้างทั้งหมดในเอกสาร ADR, SAD และ SDD นี้ ทำงานร่วมกันเพื่อเปลี่ยน **ไฟล์สคริปต์เกมดิบ (Raw Chunks)** ให้กลายเป็น **ตารางไกด์ไลน์การแปลภาษาไทยที่แม่นยำ**:

1. **ADR-012:** กำหนดทิศทางและตรรกะระดับนโยบาย (3-Tier Fallback, Timeline Delta, Thai Grammar Handling)
2. **SAD-004:** กำหนดโครงสร้างระบบและสถาปัตยกรรมไปป์ไลน์การประมวลผลข้อมูล 5 มอดูล
3. **SDD-008:** กำหนดสกีมาข้อมูล คลาส อัลกอริทึม และตรรกะภาษาไทยในระดับโค้ดเพื่อนำไปพัฒนาระบบจริง
