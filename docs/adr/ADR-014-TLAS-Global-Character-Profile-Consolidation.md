# ADR-014: TLAS Global Character Profile Consolidation (Reduce Phase)

**หมายเลขเอกสาร:** ADR-014
**หัวข้อ:** การสังเคราะห์และรวมศูนย์โปรไฟล์ตัวละครระดับทั้งเกม (Global Character Profile Consolidation & Synthesis) ด้วยสถาปัตยกรรม Map-Reduce
**สถานะ:** อนุมัติ (Accepted)
**วันที่:** 2026-08-08
**ผู้รับผิดชอบ:** ATF Core Team

---

## 1. บริบทและปัญหา (Context & Problem Statement)

ในระบบ TLAS เดิม กระบวนการสกัด Character Profiles (`tlas_analyzer.py`) ทำงานแบบ **Sequential Scene-by-Scene Analysis** ซึ่งนำไปสู่ปัญหาเชิงสถาปัตยกรรม 3 ประการ:

1. **Sequential Cold-Start Lock-in:** `base_state` และ `base_speech_style` ถูกสร้างขึ้นจาก "ฉากแรกสุดที่ตัวละครนั้นปรากฏตัว" หากฉากแรกเป็นสถานการณ์เฉพาะหน้า (เช่น ตัวละครหยาบคายแต่ต้องเสแสร้งพูดเพราะ หรือตัวละครวัยรุ่นปากร้ายแต่ฉากแรกแค่ขอบคุณชามะนาว) LLM จะสกัดแท็กสุภาพ (`PER_SOC_POLITE`) และถูกล็อคค่าระดับภาษา (`formality_level: 9`, `ผม/คุณ/ครับ`) ไว้ตลอดทั้งเกม
2. **Missing Reduce / Consolidation Pass:** ในการประมวลผลฉากต่อๆ มา ระบบทำเพียงแค่เพิ่มประวัติเหตุการณ์ (`timeline_states` delta) แต่ไม่เคยมีกลไกย้อนกลับไปประเมินภาพรวมทั้งเรื่องเพื่อปรับปรุง `base_state` ให้สอดคล้องกับพฤติกรรมจริงทั้งเกม
3. **Cascading Relationship Distortion:** เมื่อ `base_speech_style` เริ่มต้นผิดพลาด ตรรกะ `TIER3_BASE_FALLBACK` ใน Priority Rule Engine จะดึงค่าที่ผิดนี้ไปใช้กับคู่สนทนาที่เป็นเพื่อนหรือคนทั่วไป ทำให้ตัวละครพูดจาผิดบุคลิกภาพไปหมด (เช่น Jords พูดกับ Dan/Shion ด้วย "ผม/ครับ")

---

## 2. การตัดสินใจ (Decision)

เราตัดสินใจนำสถาปัตยกรรม **Map-Reduce Character Synthesis** มาใช้เป็นกระบวนการสมบูรณ์แบบ (Finalization Phase) ของระบบ TLAS โดยแบ่งบทบาทหน้าที่ดังนี้:

### 2.1 นิยามบทบาทของงานที่ผ่านมา (Map Phase - Evidence Extraction)
งานที่รันมาตลอดทั้งสัปดาห์ใน `tlas_analyzer.py` และ `tlas_timeline_generator.py` คือ **Map Phase (การสกัดหลักฐานดิบ)** ซึ่งจำเป็นอย่างยิ่งและขาดไม่ได้:
- สกัดและจัดระเบียบ Dialogue ดิบทั้ง 90,000 บรรทัด เรียงลำดับตาม Narrative Causal Chronology
- จับคู่บทสนทนาต้นฉบับกับคำแปลเก่าภาษาไทย (TH Legacy Alignment)
- สกัดพัฒนาการทางอารมณ์และเหตุการณ์สำคัญรายฉาก (`timeline_states`) บันทึกเก็บไว้เป็นประวัติศาสตร์

### 2.2 สถาปัตยกรรม Reduce Phase (Global Character Profile Consolidation)
สร้างเครื่องมือรวมศูนย์ **`tlas_profile_consolidator.py`** เพื่อทำหน้าที่ Reduce ข้อมูลหลักฐานทั้งหมดเข้าสู่ Profile ที่แม่นยำ 100%:

```
[Timeline Chunks (Dialogues)] + [TH Legacy Stats] + [Observed Timeline States]
                                │
                                ▼
         [Stage 1: Python Character Evidence Harvester]
         (สร้าง Dossier รายตัว: บทพูดเด่น, สถิติสรรพนามจริง, Trait Frequency)
                                │
                                ▼
         [Stage 2: Global LLM Character Synthesizer]
         (วิเคราะห์หา Core Baseline Personality, Values, 4D Relationships 1 Call/Character)
                                │
                                ▼
         [Stage 3: Deterministic Priority Rule Engine]
         (คำนวณ base_speech_style และ specific_speech ทุกคู่สนทนาแบบ 100% Deterministic)
                                │
                                ▼
         [Stage 4: Atomic Profile Update]
         (อัปเดต Base Profile โดยคง timeline_states ประวัติศาสตร์เดิมไว้ครบถ้วน)
```

---

## 3. ผลลัพธ์และข้อดี (Consequences)

### ผลดี (Positive):
* **Global Narrative Consistency:** `base_state` และ `base_speech_style` สะท้อนตัวตนที่แท้จริงของตัวละครตลอดทั้งเกม ไม่ถูกเบี่ยงเบนจากฉากเปิดตัวฉากเดียว
* **Extreme Efficiency:** การทำ Global Synthesis ยิง LLM เพียง **1 ครั้งต่อ 1 ตัวละคร** (~30 API Calls ทั้งโปรเจกต์) ประมวลผลเสร็จสิ้นภายใน 2-3 นาที
* **Preservation of Timeline History:** ประวัติ `timeline_states` ที่สกัดมาอย่างละเอียดทุกฉากจะไม่สูญหาย แต่จะถูกผสานเข้ากับ Base Profile ที่ถูกต้องอย่างสมบูรณ์
* **Zero Manual Effort:** ไม่ต้องเปิดแก้ Profile ทีละไฟล์ด้วยมือ ระบบจะปรับปรุงทุกตัวละครใน Whitelist ให้ถูกต้องโดยอัตโนมัติ

### ผลกระทบและการจัดการ (Mitigations):
* **Dependency on Map Phase Data:** ต้องมีข้อมูล `timeline_chunks/` และ `timeline_states` ที่สกัดแล้วเป็นฐานข้อมูลตั้งต้น
* **LLM Prompt Guarding:** Prompt ของ Stage 2 ต้องสั่งให้ LLM แยกแยะระหว่าง "พฤติกรรมแกนกลางปกติ (Baseline)" กับ "พฤติกรรมเฉพาะสถานการณ์ (Situational Deviations)" อย่างชัดเจน
