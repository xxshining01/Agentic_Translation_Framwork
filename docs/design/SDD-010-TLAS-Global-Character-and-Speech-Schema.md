# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-010  
**ชื่อระบบ:** TLAS Global Character Profile and Speech Schema (v4.0)  
**สถานะ:** Approved Design  
**วันที่:** 2026-09-13  
**เอกสารอ้างอิง:** ADR-015, SAD-010, SDD-005, SDD-011  

---

## 1. บทนำ (Overview)

เอกสารฉบับนี้กำหนดมาตรฐาน JSON Schema ของข้อมูลตัวละครในสถาปัตยกรรม TLAS v4.0 เพื่อให้มั่นใจว่า:
1. ข้อมูลตัวละครไม่มี `timeline_states` หลงเหลืออยู่
2. รูปแบบการจัดเก็บสรรพนามครอบคลุมบุรุษที่ 1, 2, และ 3 ทั้งในระดับ Base และระดับคู่ความสัมพันธ์ (Directed Pairwise)
3. ข้อกำหนดของ Output ที่ได้จาก LLM Feature Extractor ต้องมีเฉพาะรหัสพารามิเตอร์เชิงนามธรรม โดยไม่มีการใส่คำสรรพนามภาษาไทยเด็ดขาด

---

## 2. โครงสร้าง Character Profile Schema (On-Disk Profile)

ไฟล์โปรไฟล์ตัวละครจะถูกบันทึกที่ `data/tlas/profiles/<Character_Name>.json` โดยมีโครงสร้างดังต่อไปนี้:

```json
{
  "character_id": "CHAR_DAN",
  "name": "Dan",
  "aliases": [
    "Dan"
  ],
  "identity": {
    "gender": "MALE",
    "age": "ADULT",
    "species": "HUMAN"
  },
  "base_speech_style": {
    "self_pronoun": "ผม",
    "target_pronoun": "คุณ",
    "third_person_pronoun": "เขา",
    "ending_particle": "ครับ",
    "formality_level": 4
  },
  "base_state": {
    "personality": [
      {
        "tag": "PER_SOC_POLITE",
        "weight": 85
      },
      {
        "tag": "PER_MIND_DETERMINED",
        "weight": 80
      }
    ],
    "speech_habit": [
      {
        "tag": "SPR_DIRECT",
        "weight": 70
      }
    ],
    "values": [
      {
        "tag": "VAL_DUTY",
        "weight": 90
      }
    ]
  },
  "relationships": [
    {
      "target_character_id": "CHAR_SHION",
      "target_name": "Shion",
      "roles": [
        "ROLE_SOC_PEER"
      ],
      "affinity": "AFF_FOND",
      "intimacy": "INT_CONFIDANT",
      "power_dynamic": "DYN_EQUAL",
      "speech_style": {
        "self_pronoun": "ผม",
        "target_pronoun": "คุณ",
        "third_person_pronoun": "เธอ",
        "ending_particle": "ครับ",
        "formality_level": 4,
        "derivation_rule": "RULE_PEER_POLITE"
      }
    },
    {
      "target_character_id": "CHAR_LILY",
      "target_name": "Lily",
      "roles": [
        "ROLE_FAM_SIBLING_YOUNGER"
      ],
      "affinity": "AFF_DEVOTED",
      "intimacy": "INT_CONFIDANT",
      "power_dynamic": "DYN_DOMINANT",
      "speech_style": {
        "self_pronoun": "พี่",
        "target_pronoun": "หนู",
        "third_person_pronoun": "น้อง",
        "ending_particle": "จ้ะ",
        "formality_level": 2,
        "derivation_rule": "RULE_OLDER_BROTHER_TO_YOUNGER_SISTER"
      }
    }
  ]
}
```

### 2.1 คำอธิบายฟิลด์ใน Character Profile
- **`identity`**:
  - `gender`: เพศชีวภาพหรือเพศสภาพ (`MALE`, `FEMALE`, `NON_BINARY`, `UNKNOWN`)
  - `age`: ช่วงวัย (`CHILD`, `TEEN`, `ADULT`, `ELDER`, `UNKNOWN`)
  - `species`: เผ่าพันธุ์ (`HUMAN`, `ELF`, `BEAST`, ฯลฯ)
- **`base_speech_style`**: สไตล์การพูดตั้งต้นของตัวละครเมื่อสนทนากับบุคคลทั่วไป หรือคนที่ไม่ได้มีความสัมพันธ์พิเศษ
  - `self_pronoun`: สรรพนามบุรุษที่ 1 พื้นฐาน (เช่น `ผม`, `ฉัน`, `เรา`, `ข้า`)
  - `target_pronoun`: สรรพนามบุรุษที่ 2 พื้นฐาน (เช่น `คุณ`, `นาย`, `เธอ`, `ท่าน`)
  - `third_person_pronoun`: สรรพนามบุรุษที่ 3 พื้นฐาน (เช่น `เขา`, `เธอ`, `มัน`, `ท่าน`)
  - `ending_particle`: คำลงท้าย/หางเสียงพื้นฐาน (เช่น `ครับ`, `ค่ะ`, `จ๊ะ`, `ขอรับ`, หรือ `""`)
  - `formality_level`: ระดับความเป็นทางการ (สเกล 1 - 5: 1 = หยาบ/กันเองสุด, 5 = ทางการ/ราชาศัพท์)
- **`base_state`**: คุณลักษณะเชิงจิตวิทยาแกนกลางของตัวละคร (ได้มาจากค่าเฉลี่ยสถิติของทั้งโปรเจกต์)
- **`relationships` (Array of Directed Pairwise Relationships)**:
  - `target_character_id`: รหัสประจำตัวของคู่สนทนา
  - `target_name`: ชื่อคู่สนทนา
  - `roles`: บทบาทเชิงสังคมสัมพันธ์ตาม Taxonomy (`REL_ROLE_*`)
  - `affinity`: ความรู้สึก/ความผูกพันตาม Taxonomy (`REL_AFF_*`)
  - `intimacy`: ระดับความสนิทสนมตาม Taxonomy (`REL_INT_*`)
  - `power_dynamic`: อำนาจการต่อรองตาม Taxonomy (`REL_DYN_*`)
  - `speech_style`: สรรพนามและภาษาเฉพาะที่เจ้าของโปรไฟล์ใช้กับคู่สนทนานี้
    - `self_pronoun`: สรรพนามบุรุษที่ 1 ที่ใช้เรียกตัวเองเมื่อคุยกับเป้าหมายนี้
    - `target_pronoun`: สรรพนามบุรุษที่ 2 ที่ใช้เรียกเป้าหมายนี้
    - `third_person_pronoun`: สรรพนามบุรุษที่ 3 ที่ใช้เรียกคนอื่นเมื่อคุยกับเป้าหมายนี้ หรือใช้เมื่อกล่าวถึงเป้าหมายนี้
    - `ending_particle`: คำลงท้ายที่ใช้กับเป้าหมายนี้
    - `formality_level`: ระดับความเป็นทางการเฉพาะคู่นี้

---

## 3. ข้อกำหนด Output ของ LLM Feature Extractor (Lean Chunk-Level Payload)

> [!IMPORTANT]
> **Token Optimization Rule (กฎการประหยัด Token ขั้นสูงสุด):**
> - ในหน้างานวิเคราะห์จริง Field ที่ส่งไปใน Prompt ให้ LLM กรอก จะต้องส่ง **เฉพาะ Field พารามิเตอร์ที่ต้องการให้ LLM วิเคราะห์เท่านั้น**
> - **ห้ามส่งฟิลด์สรรพนามภาษาไทย (`self_pronoun`, `target_pronoun`, `third_person_pronoun`, `ending_particle`, `formality_level`) ไปใน Prompt หรือ Template ของ LLM เด็ดขาด** เพราะจะทำให้เปลืองโควต้า Token โดยไม่จำเป็น
> - ส่วนของสรรพนามภาษาไทยจริงทั้งหมด จะถูกเติม (Populate) โดย Python Rule Engine ในภายหลังเท่านั้น

### 3.1 ตัวอย่าง Payload ที่ให้ LLM กรอกและส่งกลับ (Strict Abstract Parameters Only)

```json
{
  "chunk_id": "chunk_0042",
  "characters": [
    {
      "character_name": "Dan",
      "delta": {
        "personality": [
          {
            "tag": "PER_SOC_POLITE",
            "weight": 80
          },
          {
            "tag": "PER_MIND_DETERMINED",
            "weight": 70
          }
        ],
        "speech_habit": [
          {
            "tag": "SPR_DIRECT",
            "weight": 60
          }
        ],
        "values": [
          {
            "tag": "VAL_DUTY",
            "weight": 85
          }
        ],
        "relationships": [
          {
            "target_character_id": "CHAR_LILY",
            "target_name": "Lily",
            "roles": [
              "ROLE_FAM_SIBLING_YOUNGER"
            ],
            "affinity": "AFF_DEVOTED",
            "intimacy": "INT_CONFIDANT",
            "power_dynamic": "DYN_DOMINANT",
            "speech_style": {
              "derivation_rule": "RULE_OLDER_BROTHER_TO_YOUNGER_SISTER"
            }
          }
        ]
      }
    }
  ],
  "scene_context": "Dan กำลังพูดคุยปลอบโยน Lily ในห้องนั่งเล่น",
  "dialogue_metadata": [
    {
      "dialogue_index": 0,
      "speaker": "Dan",
      "listener": "Lily",
      "emotion": "EMO_JOY",
      "tone": "TON_GENTLE"
    }
  ]
}
```

### 3.2 การเปรียบเทียบขอบเขตความรับผิดชอบ (Separation of Fields)

| ขอบเขต (Scope) | ฟิลด์ที่รับผิดชอบ | ผู้รับผิดชอบ | ส่งใน LLM Prompt? |
|---|---|---|:---:|
| **Abstract Parameters** | `roles`, `affinity`, `intimacy`, `power_dynamic`, `derivation_rule`, `personality`, `speech_habit`, `values` | **LLM Extractor** | **ส่ง (Yes)** |
| **Concrete Thai Pronouns** | `self_pronoun`, `target_pronoun`, `third_person_pronoun`, `ending_particle`, `formality_level` | **Python Consensus & Rule Engine** | **ไม่ส่งเด็ดขาด (No)** |

