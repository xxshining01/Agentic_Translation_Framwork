# SAD-004: Rule-Based Dialogue Localization Processing Pipeline [DEPRECATED / ARCHIVED]

> [!WARNING]
> เอกสารฉบับนี้ถูกปลดระวาง (Deprecated) และย้ายเข้า Archive ตามข้อตกลงใน ADR-015
> โปรดอ้างอิงเอกสารสถาปัตยกรรมปัจจุบันที่ [SAD-010-TLAS-Global-Relational-Architecture.md](../docs/architecture/SAD-010-TLAS-Global-Relational-Architecture.md)

---

# Software Architecture Document (SAD)

**หมายเลขเอกสาร:** SAD-004
**ชื่อระบบ:** Rule-Based Dialogue Localization Processing Pipeline (TLAS Localization Engine)
**เวอร์ชันระบบ:** 2.0
**สถานะ:** Archived Architecture

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
