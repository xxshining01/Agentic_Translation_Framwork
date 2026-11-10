---
trigger: always_on
description: "Core Workspace Operational Rules, Document Adherence, Terminal Execution Protocols, and System Mission"
glob: "*"
---

# Workspace Operational Rules

## 1. Document Adherence (การยึดถือเอกสารเป็นสรณะ)
- **[RULE_DOC_ADHERENCE]**: ทุกครั้งที่มีการเขียนโค้ด ปรับปรุง หรือดำเนินการใดๆ ที่อ้างอิงถึงเอกสาร (Docs/ADR/SAD/SDD) จะต้องใช้เครื่องมือเปิดอ่านเอกสารนั้นก่อนเสมอ
- ต้องเขียนโค้ดให้ตรงตาม Structure/Schema ที่เอกสารระบุไว้โดยห้ามคิดเองหรืออนุมานเอาเองอย่างเด็ดขาด
- หากพบว่ามีจุดที่ไม่สอดคล้องกันระหว่าง Code กับเอกสาร ต้องแจ้งผู้ใช้ก่อนเสมอ

## 2. Mandatory Verification (ตรวจงานก่อนส่ง 100%)
- **[RULE_MANDATORY_VERIFICATION]**: ก่อนจะแจ้งผลลัพธ์หรือแจ้งว่าดำเนินการเสร็จเรียบร้อยแล้ว จะต้องทำการตรวจสอบทุกรายละเอียดให้ครบถ้วน:
  1. ตรวจสอบชื่อไฟล์จริงบน Disk (ห้ามเดาหรือพิมพ์ชื่อไฟล์ผิด เช่น `tlas_glossary.json` vs `glossary.json`)
  2. ตรวจสอบ Data Structure / Schema ในไฟล์จริงเทียบกับโค้ดที่ดึงข้อมูล (ห้ามสมมติโครงสร้าง JSON เอาเอง)
  3. ตรวจสอบ Logic และ Flow การทำงานทุกฟังก์ชันว่าเชื่อมต่อกันได้จริงโดยไม่มีจุดหลุด
  4. ต้องรันสคริปต์ตรวจสอบหรือสร้างคำสั่งทดสอบที่ผ่านการ Verify ทุกจุดอย่างแท้จริง

## 3. Terminal Execution Protocol (ระเบียบการสั่งรันคำสั่งบนเทอร์มินัล)
- **[RULE_USER_TERMINAL_ONLY]**: ในการทำงานจริง ห้ามรันโค้ดด้วยตนเอง ให้ส่งคำสั่งรันมาให้กับผู้ใช้เพื่อสั่งรันเองบน Terminal ทั้งแบบ **PowerShell** และ **CMD (Command Prompt)**
- ต้องจัดรูปแบบคำสั่งให้ผู้ใช้ Copy-Paste ใช้งานได้ทันทีโดยไม่ต้องแก้ไข Path เพิ่มเติม

## 4. Fundamental System Principles (หลักการพื้นฐานของระบบ)
1. **State Persistence (Checkpointing):** งานประเภท Long-running Task หรืองานประมวลผลข้อมูลแบบ Batch จะต้องมีระบบ Checkpoint (บันทึกความคืบหน้าลงฮาร์ดดิสก์เป็นระยะ) เสมอ! ห้ามเก็บข้อมูลที่ประมวลผลเป็นชั่วโมงๆ ไว้ใน RAM อย่างเดียวเด็ดขาด เพื่อป้องกันความเสียหายเมื่อระบบขัดข้องและให้สามารถรันต่อ (Resume) จากจุดเดิมได้ทันที
2. **Adaptive Resilience (Auto Repair & Fallback):** โค้ดที่เรียกใช้งาน LLM API ทั้งหมด จะต้องมีระบบ Adaptive Reduce/Fallback โดยจะต้องสามารถคาดคะเนข้อจำกัด (เช่น Token Limits) ผ่านการคำนวณจำนวนตัวอักษรเพื่อหั่นล่วงหน้า (Pre-filter)
3. **No API Timeout Limits:** ห้ามกำหนดเวลา Timeout ในการทำ API Call (เช่น ต้องใช้ `timeout=None` เสมอ) เพื่อป้องกันปัญหาระบบตัดการทำงานเองเมื่อ AI ต้องใช้เวลาประมวลผลข้อมูลหรือสร้างคำตอบที่มีขนาดยาวมากๆ
4. **No Skip / 100% Success Guarantee:** งานประมวลผลข้อมูลทุกชนิด "ห้าม Skip (ข้าม)" เด็ดขาด! หากมีไฟล์ไหนประมวลผลไม่ได้ (เช่น 400 Bad Request, API หลุด, หรือข้อมูลมีปัญหา) ระบบจะต้องทำการ Auto-repair (ซ่อมแซมและปรับขนาดข้อมูลใหม่) และ Retry จนกว่าจะสำเร็จ หากแก้ไม่ได้จริงๆ ต้องหยุดทำงาน (Crash/Abort) ห้ามแกล้งทำเป็นว่าทำงานเสร็จแล้วแอบข้ามไฟล์นั้นไปเด็ดขาด!

## 5. Core System Mission (วิสัยทัศน์และเป้าหมายหลักของระบบ)
- **Universal Framework Paradigm (ไม่ใช่แค่เกมเดียว แต่ต้องรองรับทุกเกมในอนาคต 100%):**
  เป้าหมายสูงสุดของ Agentic Translation Framework (ATF) ไม่ใช่การแก้ปัญหาเฉพาะหน้าหรือการ Hardcode เพื่อให้แปลเกมตัวอย่างผ่าน แต่คือการสร้าง **"ระบบโครงร่างการแปลเกมอัตโนมัติสากล (Universal Game Localization Framework)"** ที่มีความยืดหยุ่น แข็งแกร่ง และสามารถนำไปเสียบใช้งาน (Plug-and-Play) กับเกมภาษา (RPG Maker / Visual Novel / Godot / Unity / Unreal) อื่นๆ ทั้งหมดหลังจากนี้ได้อย่างไร้รอยต่อ
- **Root Cause & Solution Documentation Requirement (บันทึกบทเรียนสู่งานสถาปัตยกรรมเสมอ):**
  ทุกครั้งที่มีการค้นพบปัญหา บั๊ก หรือขอบเขตความล้มเหลวใหม่ๆ (เช่น ปัญหา In-line Control Codes, ปัญหา Form Feed `\x0c`, ปัญหา Nested Plugin JSON, หรือปัญหา System Prompt Decay) ระบบจะต้องทำการวิเคราะห์สาเหตุรากเหง้า (RCA), บันทึกพฤติกรรมความล้มเหลวเดิม, และออกแบบขั้นตอนวิธีแก้ไขเชิงสถาปัตยกรรม บรรจุลงในเอกสาร ADR, SAD, และ SDD เสมอ เพื่อให้ตัว Framework เติบโตอย่างมีมาตรฐาน มีเอกสารอ้างอิงชัดเจน และป้องกันไม่ให้เกิดปัญหาเดิมซ้ำในเกมอื่นๆ อีกต่อไป

## 6. Session Memory & Single Source Checkpoint Adherence (ระเบียบความจำและการบันทึก Session)
- **[RULE_SINGLE_SOURCE_CHECKPOINT]**: ให้ยึดถือไฟล์ `file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/.agents/memories/single_source_checkpoint.md` เป็น **"แหล่งอ้างอิงสถานะการทำงานเพียงแหล่งเดียว (Single Source of Truth)"** ของระบบ ห้ามอ้างอิงสถานะงานหรือความคืบหน้าจากแหล่งอื่นโดยเด็ดขาด:
  - อัปเดตการติ๊ก `[x]` เฉพาะเมื่องานหรือฟังก์ชันนั้นผ่านการ Verify และใช้งานได้จริง 100% แล้วเท่านั้น
  - อนุญาตให้เพิ่มหัวข้อเช็คลิสต์ใหม่ได้เฉพาะตอนที่มีแผนงานหรือสถาปัตยกรรมใหม่เพิ่มเข้ามาเท่านั้น
- **[RULE_SESSION_MEMORY_LOGGING]**: ทุกครั้งที่เสร็จสิ้นการทำงานในแต่ละ Session ก่อนจะจบการสนทนา จะต้องทำการบันทึกสรุปผลลงใน `file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/.agents/memories/session_history.md` ให้ครบถ้วนทั้ง 6 มิติเสมอ:
  1. **สิ่งที่ทำ (Actions Executed):** โค้ดหรือเอกสารที่สร้าง/แก้ไข
  2. **แนวคิดเชิงสถาปัตยกรรม (Architectural Rationale):** เหตุผลและหลักการเบื้องหลัง
  3. **ความคืบหน้า (Progress & Milestones):** อ้างอิงเทียบกับ `single_source_checkpoint.md`
  4. **ผลการทดสอบ (Verification & Test Results):** ผลการรันตรวจสอบและไฟล์จริงบนดิสก์
  5. **สิ่งที่ต้องแก้ไข / อุปสรรค (Remaining Blockers / Next Fixes):** ประเด็นที่ต้องทำต่อ
  6. **สิ่งที่ใช้งานได้จริงแล้ว (Working Deliverables):** รายการผลงานที่เสร็จสมบูรณ์ 100%

## 7. Displayable & Player Experience Invariant (แปลเฉพาะสิ่งที่ผู้เล่นมองเห็นเท่านั้น)
- **[RULE_DISPLAYABLE_USER_EXPERIENCE_ONLY]**:
  1. **Player Experience Focus:** วัตถุประสงค์ของการแปลเกมคือการถ่ายทอดเนื้อเรื่องและอารมณ์ให้ผู้เล่นเสพประสบการณ์เป็นภาษาไทย ไม่ใช่การแปลงซอร์สโค้ดของเกมเป็นภาษาไทย
  2. **Zero Modification of Game Internals:** ข้อมูลใดๆ ที่เป็นกลไกการควบคุมเกมเบื้องหลังที่ผู้เล่นมองไม่เห็น (`Displayable == 'No'`) เช่น โค้ดคำสั่ง (Script Code), ตัวแปร (Variables), สวิตช์ (Switches), ชื่อ Event ภายใน, พารามิเตอร์ระบบ หรือ Developer Comments ต้องคงสภาพต้นฉบับภาษาเดิม 100% ห้ามแปลเด็ดขาด เพื่อป้องกันปัญหาเกมแครช (Zero Game Crash)
  3. **Plugin Text Localization Scope:** สำหรับปลั๊กอิน (Plugin Texts / Parameters) ให้สกัดและแปลเฉพาะข้อความในส่วนติดต่อผู้ใช้ (UI Strings, Menu Text, Command Labels, Displayed Picture Text) ที่แสดงผลบนหน้าจอให้ผู้เล่นเห็นเท่านั้น พารามิเตอร์เชิงเทคนิค ตัวแปร และฟังก์ชันภายในปลั๊กอินห้ามแตะต้องเด็ดขาด

## 8. Rule Compliance Pre-Delivery Verification & Audit Reporting (การตรวจสอบและรายงานการปฏิบัติตามกฎทุกข้อ)
- **[RULE_PRE_DELIVERY_COMPLIANCE_AUDIT]**:
  1. **Mandatory Self-Audit Before Reporting:** ก่อนส่งมอบงานหรือรายงานผลลัพธ์ให้ผู้ใช้ทุกครั้ง AI Assistant จะต้องทำการตรวจสอบตนเองซ้ำ (Self-Audit) เทียบกับกฎเหล็กทุกข้อใน `.agents/rules/` และ `.agents/AGENTS.md` อย่างเข้มงวด 100%
  2. **Explicit Compliance Section in Response:** ในข้อความรายงานสรุปผลงาน ต้องมีส่วน **"รายงานการตรวจสอบความสอดคล้องกับกฎของระบบ (Rule Compliance Audit Report)"** อธิบายอย่างเป็นรูปธรรมว่าทำไมโค้ดหรือการกระทำในแต่ละส่วนถึงไม่ละเมิดกฎ:
     - ทำไมถึงสอดคล้องกับ `[RULE_ZERO_HARDCODE]` (ไม่มีการฮาร์ดโค้ดชื่อตัวละคร, เพศ, หรือค่าเฉพาะเกมในซอร์สโค้ด)
     - ทำไมถึงสอดคล้องกับ `[RULE_UNIVERSAL_PARADIGM]` (ทำงานได้กับทุกเกมแบบ Plug-and-Play ขับเคลื่อนจาก Data บน Disk เท่านั้น)
     - ทำไมถึงสอดคล้องกับ `[RULE_SYSTEM_PRINCIPLES]` (มี State Persistence Checkpoint, Adaptive Resilience, No Timeout, No Skip)
     - ทำไมถึงสอดคล้องกับ `[RULE_USER_TERMINAL_ONLY]` (เตรียมคำสั่งรันให้ผู้ใช้สั่งเอง ทั้ง PowerShell และ CMD)
     - ทำไมถึงสอดคล้องกับ `[RULE_DOC_ADHERENCE]` & `[RULE_MANDATORY_VERIFICATION]` (ตรวจสอบไฟล์จริงบนดิสก์และ Schema ครบถ้วน)



