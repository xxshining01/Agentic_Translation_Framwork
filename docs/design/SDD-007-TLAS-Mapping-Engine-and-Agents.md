# SDD-007: TLAS Mapping Engine & Agent Boundaries

**Date:** 2026-07-18
**Related ADRs:** ADR-009

## 1. Overview
เอกสารนี้กำหนดขอบเขตที่ชัดเจนระหว่าง Agent สายวิเคราะห์ (Summarizer และ Analyzer) และกลไกการทำ Mapping ของ Python Decision Engine เพื่อสร้าง `Translation Guidance` **ในส่วนของ Phase 2: Runtime Translation Pipeline** (ดู SAD-002 ประกอบ)

## 2. Agent Boundaries (การแบ่งหน้าที่ชัดเจน)

เพื่อป้องกันการทำงานซ้ำซ้อน เรากำหนดหน้าที่ดังนี้:

### 2.1 Summarizer Agent (The "Micro/Scene" Observer)
- **หน้าที่:** มองภาพรวมของฉากจากประโยคสั้นๆ ที่เพิ่งแปลไปแล้ว (Micro Context) แตกต่างจาก Map-Reduce ที่มองระดับ Timeline ภาพรวม
- **ความรับผิดชอบ:** สร้าง **Situation Context** สำหรับบริบทแวดล้อมเท่านั้น
- **ผลลัพธ์ (ตัวอย่าง):**
  - `Situation:` ["SIT_PRIVATE"]
  - `Description:` "Shion พูดด้วยท่าทางผ่อนคลายขณะที่ Dan และ Jords อยู่ในระหว่างถกเถียงเรื่องการทำงานพิเศษด้วยความตึงเครียด"
- **กฎเหล็ก:** ห้ามสกัดอารมณ์ (Emotion/Tone) เด็ดขาด ปล่อยให้เป็นหน้าที่ของ Analyzer เพื่อป้องกันข้อมูลขัดแย้งกัน ต้องเลือก Tag จากหมวด `SIT_` เท่านั้น

### 2.2 Analyzer Agent (The "Linguistic" Tagger)
- **หน้าที่:** มองประโยคปัจจุบัน (ประโยคที่จะแปล)
- **ความรับผิดชอบ:** สกัด **Dialogue Metadata** เชิงภาษาศาสตร์รายประโยค ได้แก่ เจตนา (Intent), อารมณ์ (Emotion), น้ำเสียง (Tone), ระดับภาษา (Register)
- **กฎเหล็ก:** ห้ามสกัด Situation ของฉาก ปล่อยให้เป็นหน้าที่ของ Summarizer ห้ามแปลข้อความ ห้ามคิดเนื้อเรื่องเพิ่ม ทำหน้าที่แค่ติด Tag เท่านั้น

## 3. Mapping / Decision Engine (Python)

เป็น Python Class ล้วนๆ ไม่มี AI เข้ามาเกี่ยวข้อง หน้าที่คือรับ `Situation Context` และ `Dialogue Metadata` มาเข้าสมการเพื่อหา Pronoun

### 3.1 Mapping Logic (Weighted Score)
```python
def resolve_pronouns(character: dict, metadata: dict, rules: list) -> dict:
    best_rule = None
    max_score = -1

    for rule in rules:
        score = 0
        priority = rule.get("priority_score", 10)
        conds = rule.get("conditions", {})
        
        # กรองเงื่อนไขเบื้องต้น (เช่น ต้องตรง Gender)
        if "gender" in conds and conds["gender"] != character.get("gender"):
            continue
            
        # คำนวณคะแนนจาก Traits (ตัวอย่าง: Personality)
        if "personality" in conds:
            trait_weight = 0
            for trait in character.get("personality", []):
                if trait["tag"] == conds["personality"]:
                    trait_weight = trait["weight"]
                    break
            if trait_weight == 0:
                continue
            score += priority * trait_weight
            
        if score > max_score:
            max_score = score
            best_rule = rule
            
    return best_rule["pronouns"] if best_rule else {"self": "ฉัน", "target": "คุณ", "ending": ""}
```

### 3.2 Output: Translation Guidance
Engine จะจัดรูปแบบผลลัพธ์เป็นคำสั่งตายตัว (Deterministic String) เพื่อนำไปต่อท้าย User Prompt เช่น:

```text
[TRANSLATION GUIDANCE - STRICT COMPLIANCE REQUIRED]
- Pronoun (Self): "ผม"
- Pronoun (Listener): "ท่าน"
- Sentence Ending: "ครับ"
- Tone Constraint: "SARCASTIC (ประชดประชัน)"
- Register: "FORMAL (ทางการ)"
```

## 4. Downstream Agents

- **Translator Agent:** รับ Translation Guidance แล้วแปลตามที่สั่ง ห้ามเลือกสรรพนามอื่นเด็ดขาด
- **Editor Agent:** ขัดเกลารูปประโยคให้สละสลวยขึ้น แต่ **ต้องคงสรรพนามและน้ำเสียงตาม Translation Guidance ไว้ 100%**
- **QA Agent:** นำ Translation Guidance มาเป็น Check-list ตรวจสอบว่า "มีการใช้ 'ผม' และ 'ท่าน' รวมถึงลงท้ายด้วย 'ครับ' หรือไม่?" หาก Translator ฝ่าฝืน ให้สั่ง `Reject` กลับไปแปลใหม่ทันที
