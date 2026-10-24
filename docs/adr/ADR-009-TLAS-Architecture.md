# ADR-009: TLAS (Translation Linguistic Annotation System) Architecture

**Status:** Accepted
**Date:** 2026-07-18
**Decision Maker:** Product Owner + AI Solution Architect

---

## 1. Context and Problem Statement

จากปัญหาที่พบในการแปลด้วย AI ที่ผ่านมา เช่น AI เลือกใช้คำสรรพนาม (Pronouns) ไม่สอดคล้องกัน (เช่น แปล I เป็น ผม, ฉัน, ข้า สลับไปมา), ไม่เข้าใจระดับความสัมพันธ์ของตัวละคร, หรือใช้ระดับภาษา (Register) และคำลงท้ายผิดพลาด เนื่องจาก AI Translator ต้องรับภาระในการ "เดา" บริบทและแปลไปพร้อมๆ กัน ซึ่งนำไปสู่ความไม่คงเส้นคงวา (Inconsistency) ของคาร์แรคเตอร์

เราต้องการระบบที่บังคับให้การเลือกสรรพนามและระดับภาษาเป็นเรื่องที่ผ่านการคำนวณมาอย่างแม่นยำ (Deterministic) ก่อนที่จะส่งให้ AI ทำการเกลาหรือแปลข้อความ

## 2. Decision

เราตัดสินใจนำสถาปัตยกรรม **TLAS (Translation Linguistic Annotation System)** มาใช้เป็น Layer เพิ่มเติมก่อนการแปล โดยมีแนวคิดหลักคือ: **"TLAS เป็นระบบวิเคราะห์ ไม่ใช่ระบบแปล"** 

สถาปัตยกรรมใหม่ถูกกำหนดและ **LOCKED** ไว้ตาม Pipeline ดังนี้:

`Original Script -> Analyzer Agent -> Character Knowledge -> Dialogue Metadata -> Mapping/Decision Engine -> Translation Guidance -> Translator Agent`

**การแบ่งหน้าที่:**
1. **Summarizer Agent (ปรับปรุงหน้าที่):** ทำหน้าที่สรุปบริบทสภาพแวดล้อม (Situation Context) *แบบประโยคต่อประโยค* จากบทสนทนาก่อนหน้า เช่น ใครคุยกับใคร, บรรยากาศเป็นอย่างไร, ตัวละครรู้สึกอย่างไร เพื่อเป็นข้อมูลตั้งต้น
2. **Analyzer Agent (Agent ใหม่):** ทำหน้าที่รับ Situation Context และ Character Knowledge (ที่เก็บเป็น Timeline Base+Delta) มาวิเคราะห์ประโยคปัจจุบัน เพื่อออก `Dialogue Metadata` ที่เป็น Taxonomy Tags (เช่น `REG_FORMAL`, `TON_SARCASTIC`)
3. **Mapping / Decision Engine (Python):** รับ Metadata มาคำนวณและจับคู่หาคำสรรพนามที่ถูกต้อง (เช่น สรรพนามแทนตัว, สรรพนามแทนคู่สนทนา, คำลงท้าย) และสร้างเป็น `Translation Guidance`
4. **Translator & Editor Agent:** รับ `Translation Guidance` ไปปฏิบัติตามอย่างเคร่งครัด โดยไม่ต้องเดาบริบทเองอีกต่อไป
5. **QA Agent:** นำ `Translation Guidance` มาตรวจสอบว่า Translator ทำตามคำสั่งได้ถูกต้องหรือไม่

## 3. Rationale

การแบ่งแยกกระบวนการวิเคราะห์ (Analysis) ออกจากการแปล (Translation) ตามหลักการ Single Responsibility Principle (SRP) ช่วยลด Cognitive Load ของโมเดล AI ลงอย่างมหาศาล เมื่อ AI ไม่ต้องพะวงเรื่องการเลือกคำสรรพนาม มันจะสามารถโฟกัสไปที่ความสละสลวยและความหมายของประโยคได้อย่างเต็มที่ นอกจากนี้ การสร้าง Taxonomy กลางยังช่วยให้เราแก้ไขบั๊กเรื่องสรรพนามได้จาก Python (Decision Engine) ทันที โดยไม่ต้องไปลุ้นกับการปรับ Prompt 

## 4. Consequences

**Pros (ข้อดี):**
* **Absolute Consistency:** สรรพนามและระดับภาษาจะคงเส้นคงวา 100% ตามที่ Decision Engine กำหนด
* **Debugging Ease:** หากสรรพนามผิด สามารถตรวจสอบได้ทันทีว่าผิดที่ Character Knowledge, Metadata Tag, หรือ Mapping Engine
* **Scalability:** สามารถปรับเปลี่ยนความสัมพันธ์ (Timeline Delta) ของตัวละครได้ตามเนื้อเรื่องที่ดำเนินไป

**Cons (ข้อเสีย):**
* **Increased Token Cost & Latency:** ต้องเรียกใช้งาน AI เพิ่มขึ้นในส่วนของ Analyzer Agent และ Summarizer Agent (ประโยคต่อประโยค) ก่อนการแปล
* **Complex Setup:** ต้องสร้างฐานข้อมูล Taxonomy และ Character Profile จำนวนมากก่อนระบบจะเริ่มทำงานได้อย่างสมบูรณ์
