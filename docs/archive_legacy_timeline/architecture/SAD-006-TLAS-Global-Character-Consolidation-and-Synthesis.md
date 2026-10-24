# SAD-006: TLAS Global Character Profile Consolidation & Synthesis Architecture [DEPRECATED / ARCHIVED]

> [!WARNING]
> เอกสารฉบับนี้ถูกปลดระวาง (Deprecated) และย้ายเข้า Archive ตามข้อตกลงใน ADR-015
> การรวมโปรไฟล์และการสังเคราะห์สรรพนามในสถาปัตยกรรมใหม่ถูกอธิบายไว้ที่ [SAD-010-TLAS-Global-Relational-Architecture.md](../docs/architecture/SAD-010-TLAS-Global-Relational-Architecture.md) และ [SDD-011-Python-Consensus-and-Pronoun-Engine.md](../docs/design/SDD-011-Python-Consensus-and-Pronoun-Engine.md)

---

# Software Architecture Document (SAD)

**หมายเลขเอกสาร:** SAD-006
**ชื่อระบบ:** TLAS Global Character Profile Consolidation & Synthesis Architecture
**เวอร์ชันระบบ:** 1.0
**สถานะ:** Archived Architecture
**วันที่:** 2026-08-08
**ผู้รับผิดชอบ:** ATF Core Team

## 1. ภาพรวมสถาปัตยกรรม (System Overview & Architectural Vision)

สถาปัตยกรรม **TLAS Global Character Profile Consolidation & Synthesis** ถูกออกแบบขึ้นเพื่อแก้ปัญหาความไม่คงเส้นคงวาของ Character Profile (Sequential Cold-Start Drift & Lock-in) ในระบบแปลภาษาขนาดใหญ่

ในระบบประมวลผลข้อมูลขนาดใหญ่ (Big Data Systems) การสกัดความรู้จะถูกแบ่งออกเป็น 2 ช่วงตามหลักการ **Map-Reduce**:
1. **Map Phase (Evidence Extraction - `tlas_analyzer.py` & `tlas_timeline_generator.py`):** 
   - กวาดอ่านทั้ง 90,000 บรรทัดบทสนทนา
   - จัดเรียง Causal Timeline และบันทึก `story_timeline.json`
   - สกัดเหตุการณ์ จุดเปลี่ยนชีวิต และความเปลี่ยนแปลงทางอารมณ์ย่อย (`timeline_states`) ของตัวละครในแต่ละช่วงเวลา
2. **Reduce Phase (Global Character Profile Synthesis - `tlas_profile_consolidator.py`):**
   - นำ "หลักฐานทั้งหมด" (Dialogue Corpus ทั้งหมดที่พูดจริง, สถิติสรรพนามจริงจาก TH Legacy, และบันทึกเหตุการณ์ทั้งหมด) มารวมศูนย์เป็น **Character Dossier (แฟ้มประวัติรวม)**
   - สังเคราะห์ตัวตนแกนกลาง (Core Personality, Values, Speech Habits, 4D Relationships) ผ่าน LLM ในมุมมองภาพรวมทั้งเกม (Global Perspective)
   - คำนวณระบบภาษาและสรรพนามใหม่ทั้งหมดด้วย **Deterministic Priority Rule Engine**
