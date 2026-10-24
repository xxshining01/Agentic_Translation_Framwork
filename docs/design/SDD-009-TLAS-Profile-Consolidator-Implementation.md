# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-009
**ชื่อระบบ:** TLAS Global Character Profile Consolidator Implementation
**เวอร์ชันระบบ:** 1.0
**สถานะ:** Approved Design
**วันที่:** 2026-08-08
**ผู้รับผิดชอบ:** ATF Core Team

---

## 1. บทนำ (Introduction)

เอกสารฉบับนี้ระบุรายละเอียดเชิงเทคนิคระดับโค้ดของสคริปต์ **`tlas_profile_consolidator.py`** เพื่อดำเนินการ Reduce และสังเคราะห์ `base_state`, `identity`, `base_speech_style` และ `relationships` ของตัวละครทั้งหมดในโปรเจกต์ให้สอดคล้องกับเนื้อเรื่องทั้งเกมตามสถาปัตยกรรม SAD-006 และ ADR-014

---

## 2. โครงสร้างโมดูลและฟังก์ชันการทำงาน (Module Specifications)

### 2.1 File Location
- **Source Script:** `src/atf/tools/tlas_profile_consolidator.py`
- **Unit Test:** `tests/test_tlas_profile_consolidator.py`

### 2.2 Core Functions Architecture

```python
class CharacterEvidenceHarvester:
    """ทำหน้าที่กวาดรวมหลักฐานบทสนทนา สถิติสรรพนาม และประวัติเหตุการณ์ของตัวละคร"""
    def harvest_character_dossier(self, character_name: str) -> dict:
        """
        Returns:
            {
                "character_name": str,
                "dialogue_samples": list[dict], # {speaker, listener, original, th_legacy, chunk}
                "pronoun_frequencies": dict,    # {listener_name: {self_pronouns: Counter, target_pronouns: Counter, endings: Counter}}
                "observed_traits": Counter,     # ความถี่ของ personality tags จาก timeline_states เดิม
                "known_co_speakers": list[str]  # รายชื่อตัวละครที่เคยคุยด้วยตลอดทั้งเกม
            }
        """

class GlobalProfileSynthesizer:
    """ส่ง Character Dossier ให้ LLM สังเคราะห์ Core Baseline Traits"""
    def synthesize_base_profile(self, dossier: dict) -> dict:
        """
        Sends targeted prompt with character evidence to LLM.
        Returns:
            {
                "identity": {"gender": "...", "age": "...", "species": "..."},
                "base_state": {
                    "personality": [{"tag": "...", "weight": int}],
                    "speech_habit": [{"tag": "...", "weight": int}],
                    "values": [{"tag": "...", "weight": int}]
                },
                "relationships": [
                    {
                        "target_name": "...",
                        "roles": ["..."],
                        "affinity": "...",
                        "intimacy": "...",
                        "power_dynamic": "..."
                    }
                ]
            }
        """

class ProfileConsolidationEngine:
    """ผสานผลลัพธ์จาก LLM เข้ากับ Priority Rule Engine และบันทึก Atomic Profile"""
    def process_character(self, character_name: str) -> bool:
        # 1. Harvest dossier
        # 2. Synthesize via LLM
        # 3. Compute base_speech_style & specific_speech via PriorityRuleEngine
        # 4. Merge with existing timeline_states
        # 5. Atomic write to data/tlas/profiles/{character_name}.json
```

---

## 3. รูปแบบ Prompt สำหรับ Global Profile Synthesis

### 3.1 System Prompt
```
You are the TLAS Global Character Profile Synthesizer.
Your mission is to analyze the complete narrative dossier of a character (comprising actual dialogue lines across the game, legacy Thai translation usage, and observed behavior) and extract their true canonical CORE BASELINE identity, personality, speech habits, values, and 4D relationships.

CRITICAL DIRECTIVES:
1. DISTINGUISH BASELINE FROM SITUATIONAL:
   - Identify who the character truly is in everyday life (Core Baseline).
   - Do NOT let a single scene of pretending, distress, or temporary politeness define their core personality.
2. STRICT TAXONOMY COMPLIANCE:
   - Use ONLY valid tags from the provided TLAS Taxonomy (e.g. PER_SOC_RUDE, PER_VIBE_CYNICAL, SPR_SARCASTIC, VAL_WEALTH).
3. 4D RELATIONSHIPS:
   - Define accurate 4D dynamics (roles, affinity, intimacy, power_dynamic) for each major character they interact with.
```

### 3.2 User Prompt Payload
```json
{
  "character_name": "Jords",
  "total_dialogue_lines_analyzed": 142,
  "dialogue_samples": [
    {"listener": "Dan", "en": "Dude, WORK. Take their orders!!", "th": "เฮ้ย ทำงานดิวะ ไปรับออเดอร์ซะ!!"},
    {"listener": "Dan", "en": "What the fuck did it look like?! Sex.", "th": "คิดว่าทำอะไรอยู่ล่ะวะ?! มีเซ็กซ์ไง"},
    {"listener": "Mayor", "en": "Understood, Mr. Mayor. I'll handle the supplies.", "th": "เข้าใจแล้วครับท่านนายก เดี๋ยวผมจัดการเรื่องเสบียงให้"}
  ],
  "pronoun_frequencies": {
    "Dan": {"self": {"ฉัน": 45}, "target": {"แก": 30, "นาย": 10}, "ending": {"": 50, "วะ": 5}},
    "Mayor": {"self": {"ผม": 8}, "target": {"ท่าน": 8}, "ending": {"ครับ": 8}}
  },
  "taxonomy_reference": { ... }
}
```

---

## 4. กลไกการคำนวณระดับภาษาและสรรพนาม (Rule Engine Recalibration)

เมื่อได้รับ Core Baseline จาก LLM ตัวประมวลผล Python จะคำนวณ `base_speech_style` ด้วยตรรกะ Deterministic (สอดคล้องกับ `tlas_rule_engine.py`):

1. **คำนวณ Formality Score (1 ถึง 10):**
   - Base = 5
   - ปรับลด: `SPR_SLANG` (-3), `PER_SOC_RUDE` (-3), `SPR_SARCASTIC` (-1), `PER_VIBE_ARROGANT` (-1)
   - ปรับเพิ่ม: `SPR_POLITE_SUFFIX` (+2), `PER_SOC_POLITE` (+2), `SPR_ELOQUENT` (+2)
   - ปรับตามสถานะ: `Executive/Mayor/Lord` (ขั้นต่ำ 8), `Manager/Captain` (ขั้นต่ำ 6)
2. **จับคู่สรรพนามและหางเสียงตาม Formality & Age & Gender:**
   - Formality 1–3: สรรพนาม "ฉัน / กู / เรา", หางเสียง "" (ไม่มี)
   - Formality 4–6: สรรพนาม "ฉัน / เรา / ผม", หางเสียง "ครับ / ค่ะ" (ตามเพศและบุคลิก)
   - Formality 7–10: สรรพนาม "ผม / กระผม / ดิฉัน", หางเสียง "ครับ / ค่ะ"
3. **คำนวณ Specific Speech ในทุกคู่ความสัมพันธ์:**
   - คู่ความสัมพันธ์ที่มี Power Dynamic เป็น `DYN_SUBMISSIVE` (เช่น Jords คุยกับ Mayor/The Earl) จะถูกยกระดับ Formality ขึ้นเป็น 8 (ใช้ "ผม / ท่าน / ครับ") แม้ `base_speech_style` ของ Jords จะเป็น 2 ก็ตาม

---

## 5. การตรวจสอบความถูกต้อง (Verification & Validation)

การทดสอบใน [`tests/test_tlas_profile_consolidator.py`](file:///d:/Agentic%20Translation%20Framework%20%28ATF%29%20Project/tests/test_tlas_profile_consolidator.py) จะครอบคลุม:
1. **Harvester Accuracy:** ตรวจสอบว่าสกัดสถิติสรรพนามและตัวอย่างบทพูดได้ถูกต้องครบถ้วน
2. **Rule Engine Calibration:** ตรวจสอบว่า Jords ได้รับ `Formality = 2` ("ฉัน / แก / ไม่มีหางเสียง") ในบทสนทนากับ Dan/Shion และได้รับ `Formality = 8` ("ผม / ท่าน / ครับ") เมื่อคุยกับ Mayor/The Earl
3. **Timeline State Retention:** ตรวจสอบว่า `timeline_states` ประวัติศาสตร์เดิมไม่สูญหายและไม่ถูกเขียนทับ
