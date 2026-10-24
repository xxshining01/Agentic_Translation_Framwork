# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-012  
**ชื่อระบบ:** Data-Driven Taxonomy Calibration and Legacy Translation Synthesis  
**สถานะ:** Approved Design  
**วันที่:** 2026-09-18  
**เอกสารอ้างอิง:** ADR-015, SDD-005, SDD-010, SDD-011  

---

## 1. วัตถุประสงค์ (Purpose)

เอกสารฉบับนี้กำหนดสถาปัตยกรรมและกระบวนการ **Data-Driven Taxonomy Calibration (การสอบเทียบและสังเคราะห์กฎ Taxonomy จากคลังข้อมูลการแปลจริง)** เพื่อแก้ปัญหาความลักลั่นและไม่สมจริงของกฎสรรพนามเชิงทฤษฎี (เช่น การเหมารวมคู่สนทนาทั่วไปเป็น `CLOSE_PEER ("เรา - นาย")`) โดยนำข้อมูลพารามิเตอร์เชิงนามธรรมที่สกัดได้จาก 6,115 ฉาก มาสอบเทียบทางสถิติร่วมกับคลังบทแปลภาษาไทยเดิม (TH_Legacy Translation Memory) เพื่อสร้างเป็นกฎ Taxonomy สากลที่มีความสมจริงและคงเส้นคงวาตามธรรมชาติของภาษาไทย 100% โดยปราศจากการ Hardcode ชื่อตัวละคร

---

## 2. หลักการสำคัญทางสถาปัตยกรรม (Core Architectural Principles)

```
+-------------------------------------------------------------------------------+
| Layer 1: ATF Generic Taxonomy Matrix (เอนจินภาษาศาสตร์สากล 100%)              |
| - ไร้ชื่อตัวละคร ไร้การผูกติดกับเกมใดเกมหนึ่ง (Game-Agnostic)                 |
| - กำหนดความสัมพันธ์ด้วยคุณลักษณะเชิงนามธรรม:                                  |
|   (Speaker Gender/Age, Target Gender/Age, Role, Intimacy, Affinity, Formality)|
| - นำไปรันกับเกมใหม่ (Game B, Game C) ได้ทันทีโดยไม่พัง                         |
+-------------------------------------------------------------------------------+
                                      ^
                         (สอบเทียบและเหนี่ยวนำกฎ)
                                      |
+-------------------------------------------------------------------------------+
| Layer 2: Legacy Translation Memory Calibration (TH_Legacy Data Mining)        |
| - นำคลังบทแปลเดิม (200,000 บรรทัด) มาถอดสถิติสรรพนามที่มนุษย์ใช้จริง        |
| - จับคู่ Cross-Reference ระหว่าง Parameter Vector (EN) <-> Pronouns (TH)      |
| - สังเคราะห์น้ำหนักกฎและคำสรรพนามที่เหมาะสมกลับเข้าสู่ Layer 1               |
+-------------------------------------------------------------------------------+
```

### 2.1 Zero-Hardcoding & Generalizability (ความเป็นสากล)
ห้ามนำชื่อเฉพาะของตัวละคร (เช่น `Dan`, `Shion`, `Masaru`, `Lily`) หรือชื่อเฉพาะของเกม เข้าไปใส่ในโค้ดของ Taxonomy หรือ Consensus Engine เป็นอันขาด กฎทั้งหมดต้องถูกแปลงเป็น **พารามิเตอร์เชิงนามธรรม (Abstract Feature Parameters)** เสมอ

### 2.2 Separation of Concerns (การแบ่งแยกหน้าที่อย่างชัดเจน)
* **Character Profile (TLAS Engine):** มีหน้าที่บันทึกเฉพาะ **สรรพนามสามัญ (Grammatical Pronouns)** บุรุษที่ 1, 2, 3 และคำลงท้าย ตามมาตรฐานภาษาศาสตร์เท่านั้น (เช่น `self: "หนู"`, `target: "คุณพ่อ"`, `ending: "ค่ะ"`)
* **Translator Agent (Sophia Prompt):** มีหน้าที่ตัดสินใจว่าจะใช้สรรพนามสามัญจาก Profile เมื่อใด และจะแปลคำเรียกเฉพาะ (Specific Vocatives เช่น `Papa`, `Mama`, `Dear`, `Honey`, `That guy`) ตามรูปศัพท์และบริบทธรรมชาติเมื่อใด

---

## 3. ขั้นตอนการสอบเทียบ Taxonomy (Taxonomy Calibration Pipeline)

```
+------------------------------------+     +------------------------------------+
|  1. Macro Parameters (6,115 Chunks) |     |  2. TH_Legacy Dialogues (CSV)      |
|  - Speaker / Target Demographics   |     |  - Speaker / Target Lines          |
|  - Roles, Affinity, Intimacy       |     |  - Actual Pronouns (1st, 2nd, 3rd) |
|  - Formality & Power Dynamic       |     |  - Ending Particles & Politeness   |
+------------------------------------+     +------------------------------------+
                   \                                 /
                    \                               /
                     v                             v
       +---------------------------------------------------------+
       | 3. Statistical Cross-Referencer & Parameter Matcher     |
       |    - รวมกลุ่มคู่ตัวละครที่มีพารามิเตอร์เหมือนกัน        |
       |    - คำนวณสถิติความถี่คำสรรพนามที่คนแปลใช้จริง          |
       +---------------------------------------------------------+
                                   |
                                   v
       +---------------------------------------------------------+
       | 4. Inductive Taxonomy Rule Synthesis                    |
       |    - สร้างกฎ Mapping สากลใหม่ใน taxonomy.json           |
       |    - กำหนด Priority และ Thresholds ที่แม่นยำ            |
       +---------------------------------------------------------+
```

### 3.1 การสกัดสถิติจาก TH_Legacy (Data Mining Phase)
สคริปต์ `TH_Legacy Pronoun Miner` จะทำการสแกนไฟล์บทแปลภาษาไทยเดิม โดยตรวจจับ:
1. **สรรพนามบุรุษที่ 1 (Self Pronouns):** `ผม`, `ฉัน`, `เรา`, `ข้า`, `หนู`, `กู`, `ดิฉัน`, `พี่`
2. **สรรพนามบุรุษที่ 2 (Target Pronouns):** `คุณ`, `นาย`, `เธอ`, `แก`, `มึง`, `ท่าน`, `พี่`, `น้อง`
3. **สรรพนามบุรุษที่ 3 (Third Person):** `เขา`, `เธอ`, `มัน`, `ท่าน`, `หล่อน`, `หมอนั่น`, `ยัยนั่น`
4. **คำลงท้าย (Ending Particles):** `ครับ`, `ค่ะ`, `จ้ะ`, `จ๊ะ`, `วะ`, `ยะ`, `โว้ย`, `""`
5. **ระดับความเป็นทางการ (Formality Ratio):** คำนวณจากสัดส่วนการใช้คำสุภาพ (ครับ/ค่ะ) ต่อจำนวนประโยคทั้งหมด

### 3.2 การจับคู่สอบเทียบ (Parameter Cross-Referencing)
นำผลลัพธ์ที่ได้ไปชนกับพารามิเตอร์ที่ LLM วิเคราะห์ไว้ใน `extractions_v4`:
* คู่ที่มี `ROLE_ROM_PARTNER` + `AFF_DEVOTED` $\to$ ตรวจพบใน TH_Legacy ว่าใช้ `ผม / คุณ / เธอ / ครับ` (Dan $\to$ Shion) และ `ฉัน / คุณ / เขา / ค่ะ` (Shion $\to$ Dan)
* คู่ที่มี `ROLE_SOC_PEER` + `AFF_HOSTILE` $\to$ ตรวจพบใน TH_Legacy ว่าใช้ `ฉัน / เธอ / หล่อน / วะ` (Jords $\to$ Shion) และ `ฉัน / นาย / หมอนั่น / ยะ` (Shion $\to$ Jords)
* คู่ที่มีความต่างทางวัยวุฒิ (`ROLE_WORK_BOSS` หรือ `AFF_NEUTRAL`) $\to$ ตรวจพบใน TH_Legacy ว่าใช้ `ผม / คุณ / ครับ` (Dan $\to$ Masaru/Erica)

---

## 4. โครงสร้าง Taxonomy Rules ที่ปรับปรุงใหม่ (Calibrated 5-Tier Rule Matrix)

ปรับปรุงลำดับชั้นของกฎใน Taxonomy ให้สอดคล้องกับธรรมชาติของภาษาไทย:

### Tier 1: Family Hierarchy (ลำดับขั้นครอบครัว)
* **Child to Parent (`ROLE_FAM_DAUGHTER / CHILD` โดยผู้พูดเป็นเด็ก):**
  * `self` = "หนู" (ถ้าหญิง) / "ผม" (ถ้าชาย), `target` = "คุณพ่อ" / "คุณแม่", `ending` = "ค่ะ" / "ครับ", `formality` = 3
* **Younger to Older Sibling (`ROLE_FAM_SIBLING_YOUNGER`):**
  * `self` = "หนู" (ถ้าหญิง/เด็ก) / "ผม", `target` = "พี่", `ending` = "ค่ะ" / "ครับ", `formality` = 3
* **Older to Younger Sibling (`ROLE_FAM_SIBLING_OLDER`):**
  * `self` = "พี่", `target` = "หนู" (ถ้าผู้ฟังเป็นหญิง/เด็ก) / "น้อง", `ending` = "จ้ะ" / "ครับ", `formality` = 2

### Tier 2: Romance & Marriage (คู่รักและคู่สมรส)
* **Romantic Partners (`ROLE_ROM_PARTNER / LOVER`):**
  * ชายคุยกับหญิง: `self` = "ผม" (หรือ "ฉัน"), `target` = "คุณ" (หรือ "เธอ"), `third` = "เธอ", `ending` = "ครับ" (หรือ ""), `formality` = 3
  * หญิงคุยกับชาย: `self` = "ฉัน", `target` = "คุณ" (หรือ "นาย"), `third` = "เขา", `ending` = "ค่ะ" (หรือ ""), `formality` = 3

### Tier 3: Authority & Hierarchy (ลำดับอำนาจและตำแหน่งงาน)
* **Superior to Subordinate (`ROLE_WORK_BOSS` หรือ `DYN_DOMINANT` + `INT_DISTANT`):**
  * `self` = "ฉัน", `target` = "เธอ" (ถ้าหญิง) / "นาย" (ถ้าชาย), `third` = "เขา", `ending` = "", `formality` = 3
* **Subordinate to Superior (`ROLE_WORK_SUBORDINATE` หรือ `DYN_SUBMISSIVE`):**
  * `self` = "ผม" (ถ้าชาย) / "ดิฉัน" (ถ้าหญิง), `target` = "คุณ / ท่าน", `third` = "ท่าน", `ending` = "ครับ" / "ค่ะ", `formality` = 4

### Tier 4: Peer & Social Relationships (คนรุ่นเดียวกันและคนรู้จัก)
* **4.1 Close Peer (`ROLE_SOC_PEER` + `AFF_FOND / INT_CONFIDANT` + วัยเดียวกัน):**
  * `self` = "เรา" (ถ้าชาย) / "ฉัน" (ถ้าหญิง), `target` = "เธอ" (ถ้าหญิง) / "นาย" (ถ้าชาย), `third` = "เขา", `ending` = "", `formality` = 3
* **4.2 Strained / Rival Peer (`ROLE_SOC_PEER` + `AFF_HOSTILE / AFF_CONFLICTED`):**
  * ชายคุยกับหญิง: `self` = "ฉัน", `target` = "เธอ", `third` = "หล่อน", `ending` = "วะ", `formality` = 2
  * หญิงคุยกับชาย: `self` = "ฉัน", `target` = "นาย", `third` = "หมอนั่น", `ending` = "ยะ", `formality` = 2
* **4.3 Polite / General Peer (`ROLE_SOC_PEER` + `AFF_NEUTRAL` ทั่วไป - Default Sociolinguistic Baseline):**
  * `self` = "ผม" (ถ้าชาย) / "ฉัน" (ถ้าหญิง), `target` = "คุณ", `third` = "เขา", `ending` = "ครับ" / "ค่ะ", `formality` = 4

### Tier 5: Demographic & Base Speech Style Fallback
* หากไม่เข้ากฎข้างต้น ให้ใช้ค่ามาตรฐานตามเพศและวัยของตัวละคร

---

## 5. กฎเกณฑ์สำหรับ ATF Translation Agent (Prompt Guidance Integration)

ใน System Prompt ของ Agent นักแปล (Translator Agent) ต้องมีคำสั่งกำกับอย่างเข้มงวด:
1. **สรรพนามสามัญ (Common Grammatical Pronouns: I, you, he, she, we, they, it):**
   * บังคับให้ใช้คำสรรพนามและคำลงท้ายตามที่ระบุใน `[TRANSLATION GUIDANCE]` ของ Character Profile 100%
2. **คำเรียกเฉพาะและคำแสดงความผูกพัน (Specific Vocatives / Direct Addresses: Papa, Mama, Dear, Honey, Babe, That guy, Master, etc.):**
   * ห้ามบังคับเปลี่ยนคำเฉพาะเหล่านี้ให้กลายเป็นสรรพนามสามัญของ Profile
   * ให้แปลตามรูปศัพท์และบริบทธรรมชาติ เช่น `Papa` $\to$ "ป๊ะป๋า / ป๊า", `Mama` $\to$ "หม่าม้า / ม้า", `Dear` $\to$ "ที่รัก", `That guy` $\to$ "หมอนั่น"
