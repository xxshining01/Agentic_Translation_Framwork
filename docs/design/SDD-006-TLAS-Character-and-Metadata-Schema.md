# SDD-006: TLAS Character Knowledge & Dialogue Metadata Schema (v3.5)

## 1. Overview
เพื่อป้องกันไม่ให้ LLM "คิดโครงสร้างข้อมูลเอง" จนนำไปสู่ปัญหาข้อมูลขยะ (Garbage Data) หรือข้อมูลหาย ระบบ TLAS บังคับใช้ JSON Schema อย่างเคร่งครัด แบ่งเป็น 2 ส่วนหลัก:
1. **Character Knowledge (Profile Template):** ข้อมูลตัวละครที่เป็น Base + Delta (Timeline States) ซึ่งเก็บคุณลักษณะทางจิตวิทยา (**Source of Truth**) และความสัมพันธ์แบบ **4D Relationship Matrix**
2. **Dialogue Metadata:** ข้อมูลเจตนา น้ำเสียง และแท็กอารมณ์ที่สกัดออกมาแบบรายประโยคเพื่อใช้ทำ Dynamic Override (Tier 0)

---

## 2. Character Knowledge Schema (Strict Template)

โครงสร้างฐานข้อมูลตัวละครที่ต้องอิงตามไฟล์ `character_profile_template.json` อย่างสมบูรณ์:

```json
{
  "character_id": "CHAR_NAME_HERE",
  "name": "Character Name",
  "identity": {
    "gender": "MALE/FEMALE/UNKNOWN",
    "age": "CHILD/TEEN/ADULT/ELDER/UNKNOWN",
    "species": "HUMAN/ELF/BEAST/etc"
  },
  "base_speech_style": {
    "self_pronoun": "ฉัน/ผม/หนู/etc",
    "target_pronoun": "นาย/คุณ/เธอ/etc",
    "ending_particle": "คะ/ค่ะ/ครับ/จ้ะ/etc",
    "formality_level": 5
  },
  "base_state": {
    "personality": [
      {"tag": "PER_SOC_POLITE", "weight": 80},
      {"tag": "PER_VIBE_SERIOUS", "weight": 20}
    ],
    "speech_habit": [
      {"tag": "SPR_HESITANT", "weight": 60}
    ],
    "values": [
      {"tag": "VAL_DUTY", "weight": 100}
    ],
    "relationships": [
      {
        "target_character_id": "CHAR_OTHER",
        "target_name": "Other Name",
        "roles": ["ROLE_AUTH_MASTER"],
        "affinity": "AFF_HOSTILE",
        "intimacy": "INT_DISTANT",
        "power_dynamic": "DYN_SUBMISSIVE",
        "specific_speech": {
          "self_pronoun": "กระผม",
          "target_pronoun": "ท่าน",
          "ending_particle": "ครับ"
        }
      }
    ]
  },
  "timeline_states": [
    {
      "state_id": "STATE_PHASE2_CHUNK001_SUB0",
      "trigger_event_id": "chunk_p2_0001",
      "timeline_phase": 2,
      "description": "คำบรรยายการเปลี่ยนแปลงเชิงจิตวิทยาหรือเหตุการณ์สำคัญ",
      "delta": {
        "personality": [
          {"tag": "PER_SOC_RUDE", "weight": 90}
        ],
        "relationships": [
          {
            "target_character_id": "CHAR_OTHER",
            "roles": ["ROLE_CON_ENEMY"],
            "affinity": "AFF_HOSTILE",
            "intimacy": "INT_ESTRANGED",
            "power_dynamic": "DYN_EQUAL"
          }
        ]
      }
    }
  ]
}
```

### 2.1 เกณฑ์มาตรฐานของ Weight (Intensity Scale)
* **ช่วงค่า (Range):** **`1 - 100` (Integer, Percentage Scale)**
  * `100` = เด่นชัดมากที่สุด / เป็นแก่นแท้ของตัวละคร (Absolute / Definitive)
  * `70 - 90` = โดดเด่นอย่างชัดเจน (Strong / Dominant)
  * `40 - 60` = ปานกลาง (Moderate)
  * `10 - 30` = มีบ้างเล็กน้อย / แฝงอยู่ (Mild / Subtle)

### 2.2 โครงสร้างความสัมพันธ์แบบ 4 มิติ (4D Relationship Matrix)
* **`roles`:** Array ของบทบาทเชิงโครงสร้างสังคม (เช่น `["ROLE_AUTH_MASTER"]`, `["ROLE_ROM_OFFICIAL"]`, `["ROLE_SOC_PEER"]`)
* **`affinity`:** สภาพจิตใจและความรู้สึกภายใน (`AFF_DEVOTED`, `AFF_FOND`, `AFF_INTRIGUED`, `AFF_NEUTRAL`, `AFF_HIDDEN_CRUSH`, `AFF_CONFLICTED`, `AFF_SUSPICIOUS`, `AFF_HOSTILE`, `AFF_PREDATORY`, `AFF_OBSESSIVE`)
* **`intimacy`:** ระดับความสนิทสนม (`INT_CONFIDANT`, `INT_FAMILIAR`, `INT_DISTANT`, `INT_ESTRANGED`)
* **`power_dynamic`:** อำนาจต่อรอง (`DYN_DOMINANT`, `DYN_EQUAL`, `DYN_SUBMISSIVE`)
* **`specific_speech`:** (Optional) สรรพนามเฉพาะเมื่อคุยกับบุคคลนี้

### 2.3 กลไก Map-Reduce Generation: State of Record vs Derived View
- **Map Phase Generation (`tlas_analyzer.py`):** สกัดและบันทึกประวัติศาสตร์รายฉากลงใน `timeline_states (delta)` ประกอบด้วยคำบรรยายเหตุการณ์ (`description`), การเปลี่ยนแปลงทางจิตวิทยา (`personality`, `speech_habit`, `values`), และ **4D Relationship Matrix (`roles`, `affinity`, `intimacy`, `power_dynamic`)** ซึ่งถือเป็น **"แก่นความจริง (State of Record)"** ที่ห้ามลบทิ้ง
- **Reduce Phase Generation (`tlas_profile_consolidator.py`):** เมื่ออ่านข้อมูลครบทั้งเกม จะสังเคราะห์ `identity`, `base_state`, และ `base_speech_style` แกนกลางขึ้นมาใหม่ จากนั้น Python Priority Rule Engine จะทำหน้าที่คำนวณ **`specific_speech`** ในทุก `timeline_states` ใหม่อัตโนมัติ (เป็น **"Derived View"** ที่ Re-calculate ได้เสมอโดยไม่ต้องเสีย Token หรือยิง LLM ซ้ำ)
- **Runtime Consumption:** เมื่อ Context Engine โหลดข้อมูลไปใช้ตาม `timeline_phase`:
  1. สำหรับ `personality`, `speech_habit`, `values`: นำ Tag ใหม่ไปอัปเดต Weight ของ Tag เดิม หรือแทรก Tag ใหม่เข้ามา (Upsert by `tag`)
  2. สำหรับ `relationships`: ใช้ `target_character_id` เป็น Primary Key ในการ Upsert/Deep-merge มิติต่างๆ (`roles`, `affinity`, `intimacy`, `power_dynamic`, `specific_speech`)

---

## 3. Dialogue Metadata Schema (Analyzer Agent Output)

ในส่วนของ Translation Runtime Pipeline เมื่อประโยคดิบเข้ามา Analyzer Agent จะวิเคราะห์และสร้าง Metadata ดังนี้:

```json
{
  "token_id": "scene1_line001",
  "speaker": "CHAR_AILA",
  "listener": ["CHAR_ARTHUR"],
  "referenced_characters": [],
  "metadata": {
    "intent": ["INT_QUESTION"],
    "emotion": ["EMO_SURPRISE"],
    "tone": ["TON_HESITANT"],
    "register": "REG_FORMAL"
  }
}
```

---

## 4. Constraint Enforcement (Justification)
1. **Single Source of Truth:** การแยก Base vs Timeline Deltas ป้องกันข้อมูลสูญหายและทำให้ย้อนดูประวัติวิวัฒนาการตัวละครได้ตลอดทั้งเรื่อง
2. **Deterministic Fallback:** กฎ Rule Engine ใช้คะแนน `weight > 50` และการประเมิน 4D Matrix ทำให้การเลือกสรรพนามไม่สุ่มเดาและสอดคล้องกับเนื้อเรื่อง 100%
