# ADR-004: TLAS Narrative Timeline and Map-Reduce Summarization [DEPRECATED / ARCHIVED]

> [!WARNING]
> เอกสารฉบับนี้ถูกปลดระวาง (Deprecated) และย้ายเข้า Archive ตามข้อตกลงใน ADR-015
> การตัด Narrative Timeline และการประมวลผลอิสระในสถาปัตยกรรมใหม่ถูกอธิบายไว้ที่ [ADR-015-Global-Relational-Architecture-Without-Timeline.md](../docs/adr/ADR-015-Global-Relational-Architecture-Without-Timeline.md)

---

# ADR-004: TLAS Narrative Timeline and Map-Reduce Summarization

## Status
Archived (Replaced by ADR-015)

## Context
ในระหว่างการพัฒนาระบบ Translation Logic and Alignment System (TLAS) สำหรับ Agentic Translation Framework (ATF) เราเผชิญปัญหา 3 ประการหลัก:
1. **Context Window Exhaustion:** บทสนทนาในเกมมีปริมาณมหาศาล
2. **Gameplay Progression vs Narrative Chronology:** ระบบเกมปลดล็อกเนื้อเรื่องตามเงื่อนไข (Gameplay Variables/Switches) ซึ่งสามารถกระโดดข้ามเส้นเวลาได้
3. **LLM Hallucinations on Structural Tasks:** การปล่อยให้ LLM กำหนดโครงสร้างตัวละคร
