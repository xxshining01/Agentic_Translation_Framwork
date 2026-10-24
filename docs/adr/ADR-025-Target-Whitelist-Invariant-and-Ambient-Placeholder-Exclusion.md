# ADR-025: Target Whitelist Invariant, Canonical Alias Consolidation, and Ambient Mob Exclusion

## Status
Approved & Enforced (Architecture Standard)

## Context & Problem Statement
ในระหว่างการรันสถาปัตยกรรม TLAS v4.0 ขั้นตอน Consensus Engine (`tlas_consensus_engine.py`) สำหรับการอัปเดตแพทช์ v0.35 พบปัญหาเชิงคุณภาพและความซับซ้อน 3 ประการ:
1. **Unsanitized Placeholder Crash:** เกิด `OSError: [Errno 22]` จากการพยายามบันทึกไฟล์ `???.json.tmp` เนื่องจากเครื่องหมาย `?` เป็นอักขระต้องห้ามบน Windows
2. **Alias Fragmentation (ตัวละครเดียวกันแตกเป็นหลายโปรไฟล์):** ตัวละครคนเดียวกันถูกสร้างโปรไฟล์แยกซ้ำซ้อน เช่น:
   - `Mr.Masaru` แยกกับ `Masaru`
   - `Earl`, `The Earl?` แยกกับ `The Earl`
   - `Jordan's voice from inside` แยกกับ `Jordan`
   - `Kid Ritchie`, `Boy Ritchie` แยกกับ `Ritchie`
   - `KJ(Jikan's CEO)` แยกกับ `KJ`
   สาเหตุเกิดจาก `tlas_consensus_engine.py` ในอดีตไม่ได้โหลด `alias_mapping.json` และไม่มีกลไก Canonical Name Merging
3. **Ambient/Generic Mobs Contamination:** ตัวประกอบที่ไม่มี Impact ต่อเนื้อเรื่อง (เช่น `Customer*`, `Girl*`, `Man*`, `Fratboy*`, `Thug*`, `Police*`) ถูกสร้างเป็นไฟล์ Character Profile มากกว่า 380 ไฟล์ ทำให้บวมเกินความจำเป็น กิน Token ของ LLM และเสี่ยงต่อการหลอนสรรพนาม

## Decision & Architectural Invariants (ข้อกำหนดเชิงสถาปัตยกรรมสากล)

1. **Canonical Story Character Whitelist:**
   - กำหนดชุดตัวละครสำคัญแท้จริงของเนื้อเรื่อง (`CANONICAL_STORY_CHARACTERS`) ซึ่งมีบทบาทต่อเนื้อเรื่องหลัก (~74 ตัวละคร)
   - ตัวประกอบทั่วไปที่ไม่มีชื่อเฉพาะหรือบทบาทขับเคลื่อนเนื้อเรื่อง จะถูกจัดเป็น Ambient NPCs และ **ห้ามสร้างไฟล์ Profile JSON เด็ดขาด**

2. **Explicit Canonical Alias Consolidation:**
   - ฝังระบบ `EXPLICIT_ALIAS_REMAP` และโหลด `alias_mapping.json` เข้าสู่ Consensus Engine โดยตรง
   - เมื่อพบชื่อย่อย ฉายา หรือคำนำหน้า (เช่น `Mr.Masaru`, `Earl`, `Jordan's voice from inside`):
     - **สถิติและหลักฐานทั้งหมด (Traits, 4D Relationships) จะถูกหลอมรวมเข้าสู่ Canonical Name ตัวหลักตัวเดียว**
     - **ชื่อย่อยทั้งหมดจะถูกบันทึกเก็บไว้ในอาร์เรย์ `"aliases"` ของโปรไฟล์ตัวละครหลักนั้นอย่างครบถ้วน**
     - ไม่มีการสร้างไฟล์โปรไฟล์แยกสำหรับ Alias ย่อยอีกต่อไป

3. **Automated Ambient & Junk Profile Purging:**
   - เพิ่มกระบวนการ `purge_ambient_and_junk_profiles()` เมื่อ Consensus Engine สังเคราะห์โปรไฟล์หลักเสร็จสิ้น จะทำการลบไฟล์โปรไฟล์ของตัวประกอบและ Alias ที่แตกสาขาออกจากดิสก์โดยอัตโนมัติ

4. **Windows-Safe Filename Sanitization Invariant:**
   - การบันทึกไฟล์ Profile ทุกไฟล์ต้องผ่าน `sanitize_profile_filename()` เพื่อตัดอักขระต้องห้ามของ Windows ออกเสมอ ป้องกันความล้มเหลวระดับ OS

## Consequences
- ลดจำนวน Character Profiles จาก 455 ไฟล์ เหลือเพียง **74 ตัวละครหลักแท้จริง**
- รวมข้อมูลความสัมพันธ์และลักษณะนิสัยของตัวละครให้เป็นเอกภาพ 100% สรรพนามไม่แกว่ง
- ข้อมูล Alias ทั้งหมดถูกจัดเก็บอย่างเป็นระเบียบในโปรไฟล์ของตัวละครหลัก ทำให้ขั้นตอนการแปลภาษา (Translation Stage) สามารถดึง Pronoun Matrix มาใช้ได้อย่างแม่นยำ
- ป้องกันปัญหาระบบหลอนสรรพนามของตัวประกอบ และประหยัด Token ใน Prompt ของขั้นตอนการแปลได้อย่างมหาศาล
