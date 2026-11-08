# คู่มือการใช้งานระบบ Agentic Translation Framework (ATF User Manual)
> **Enterprise-Grade Universal Game Localization & Agentic Pipeline v2.0**  
> คู่มือปฏิบัติการฉบับรวมศูนย์ (Single Master Manual): รวบรวมขั้นตอนการทำงานครบวงจรตั้งแต่การสร้าง Workspace, เชื่อมต่อ ChatGPT Bridge, สกัดและวิเคราะห์บริบทเกม, สั่งรันการแปล, จนถึงการตรวจสอบ LQA และแพตช์คืนเกม

---

## 📑 สารบัญ (Table of Contents)
- [1. สิ่งที่ต้องเตรียมพร้อม (Prerequisites)](#1-สิ่งที่ต้องเตรียมพร้อม-prerequisites)
- [2. ผังขั้นตอนการทำงานครบวงจร (Complete Pipeline Workflow)](#2-ผังขั้นตอนการทำงานครบวงจร-complete-pipeline-workflow)
- [3. ขั้นตอนที่ 1: ตั้งค่าพื้นที่ทำงานและโปรเจกต์ (Workspace & Manifest Setup)](#3-ขั้นตอนที่-1-ตั้งค่าพื้นที่ทำงานและโปรเจกต์-workspace--manifest-setup)
- [4. ขั้นตอนที่ 2: เชื่อมต่อ ChatGPT Web Bridge (Web Bridge Setup)](#4-ขั้นตอนที่-2-เชื่อมต่อ-chatgpt-web-bridge-web-bridge-setup)
- [5. ขั้นตอนที่ 3: เตรียมข้อมูลบทสนทนาและบริบทเกม (Preparation Pipeline)](#5-ขั้นตอนที่-3-เตรียมข้อมูลบทสนทนาและบริบทเกม-preparation-pipeline)
  - [3.1 รันเตรียมข้อมูลแบบอัตโนมัติครบวงจร (One-Command Automation - แนะนำ)](#31-รันเตรียมข้อมูลแบบอัตโนมัติครบวงจร-one-command-automation---แนะนำ)
  - [3.2 รันแยกทีละขั้นตอน (Step-by-Step Manual Execution)](#32-รันแยกทีละขั้นตอน-step-by-step-manual-execution)
- [6. ขั้นตอนที่ 4: สั่งรันการแปลเกม (Translation Runner)](#6-ขั้นตอนที่-4-สั่งรันการแปลเกม-translation-runner)
- [7. ขั้นตอนที่ 5: ตรวจสอบคุณภาพและความสมบูรณ์ 8 มิติ (8D LQA Audit & Verification)](#7-ขั้นตอนที่-5-ตรวจสอบคุณภาพและความสมบูรณ์-8-มิติ-8d-lqa-audit--verification)
- [8. ขั้นตอนที่ 6: ฉีดคำแปลและแพตช์คืนเกม (Game Patch Deployment)](#8-ขั้นตอนที่-6-ฉีดคำแปลและแพตช์คืนเกม-game-patch-deployment)
- [9. ตารางสรุปคำสั่งด่วน (Command Cheat Sheet)](#9-ตารางสรุปคำสั่งด่วน-command-cheat-sheet)

---

## 1. สิ่งที่ต้องเตรียมพร้อม (Prerequisites)

1. **Python 3.10 ขึ้นไป**
   - ตรวจสอบด้วยคำสั่ง: `python --version`
2. **ติดตั้งไลบรารีที่จำเป็น (Dependencies):**
   - **PowerShell / CMD:**
     ```bash
     pip install -r requirements.txt
     ```
3. **เว็บเบราว์เซอร์** (Chrome, Edge หรือ Brave)
4. **ส่วนขยาย Tampermonkey** (ติดตั้งจาก [tampermonkey.net](https://www.tampermonkey.net/))
5. **บัญชี OpenAI ChatGPT** (เข้าสู่ระบบที่ [chatgpt.com](https://chatgpt.com))

---

## 2. ผังขั้นตอนการทำงานครบวงจร (Complete Pipeline Workflow)

```mermaid
flowchart TD
    Setup["1. Setup Workspace<br/>(Game Dir, CSV, Output)"] --> Bridge["2. ChatGPT Web Bridge<br/>(Userscript on chatgpt.com)"]
    Bridge --> Prep["3. Automated Preparation<br/>(python atf.py prepare-all)"]
    subgraph Prep_Detail["รายละเอียดการเตรียมข้อมูล"]
        P1["Scan Speakers"] --> P2["Master Glossary & Whitelist"]
        P2 --> P3["Scene Packets & Choice Pair"]
        P3 --> P4["Profiles & Demographic Matrix"]
        P4 --> P5["10-Column Localization Table<br/>(Triad & Game Shielding)"]
    end
    Prep --> Trans["4. Translation Execution<br/>(python atf.py translate)"]
    Trans --> Audit["5. 8D LQA & Ground Truth Audit<br/>(python atf.py verify)"]
    Audit --> Patch["6. Game Patch Deployment<br/>(Plugins UI + Final CSV Patch)"]
```

---

## 3. ขั้นตอนที่ 1: ตั้งค่าพื้นที่ทำงานและโปรเจกต์ (Workspace & Manifest Setup)

### 3.0 ขั้นตอนเตรียมไฟล์: สกัดข้อความ UI จากปลั๊กอิน (`extract_game_plugins.py`)
> 💡 **สำหรับโปรเจกต์เกมใหม่ที่ยังไม่มีไฟล์ `plugins_texts.csv`:**  
> คุณสามารถใช้เครื่องมือสกัดอิสระ (Standalone Extractor) เพื่อดึงข้อความเมนู UI จากทุกไฟล์ใน `/js` (`plugins.js` และ `plugins/*.js`) ออกมาเป็นไฟล์ตารางก่อนเริ่มโปรเจกต์:

- **PowerShell / CMD:**
  ```bash
  python extract_game_plugins.py
  ```
- **ขั้นตอนการทำงานของโปรแกรม:**
  1. โปรแกรมจะถามหาโฟลเดอร์เกมต้นทาง: ให้ระบุพาธหรือลากโฟลเดอร์เกมมาวางในเทอร์มินัล
  2. ระบบจะตรวจหาโฟลเดอร์ `/js` อัตโนมัติ และสแกนสกัดข้อความภาษาธรรมชาติและคำสั่ง UI ออกจากปลั๊กอินทุกตัว
  3. เมื่อสกัดเสร็จแล้ว ระบบจะถามหาตำแหน่งสำหรับวางไฟล์ `plugins_texts.csv` (กด Enter เพื่อบันทึกที่ `data/plugins_texts.csv`)

---

### 3.1 การจับคู่ตำแหน่งไฟล์และสร้าง Project Manifest (`atf.py setup`)

เครื่องมือตั้งค่าจะค้นหาและจับคู่ตำแหน่งไฟล์ของเกมอัตโนมัติ:
- โฟลเดอร์เกมเป้าหมาย (`Game Directory` เช่น โฟลเดอร์เกมใหม่ของคุณ)
- โฟลเดอร์ข้อมูลเกม (`Game Data Directory` เช่น `www/data` หรือ `data`)
- สคริปต์ปลั๊กอิน (`www/js/plugins.js` หรือ `js/plugins.js`)
- ไฟล์ตารางข้อความต้นฉบับบทสนทนา (`raw_pre_csv` ที่รวมมาจาก Translator++)
- ไฟล์ตารางข้อความ UI ปลั๊กอิน (`legacy_plugin_csv` เช่น `data/plugins_texts.csv` ที่เพิ่งสกัดได้)
- โฟลเดอร์ผลลัพธ์ (`output_dir`)

### คำสั่งรันตั้งค่า Workspace:
- **PowerShell:**
  ```powershell
  python atf.py setup
  ```
- **CMD:**
  ```cmd
  python atf.py setup
  ```
*ผลลัพธ์:* ระบบจะบันทึกการตั้งค่าทั้งหมดลงใน `data/project_manifest.json` ซึ่งทุกโมดูลในระบบจะใช้เป็นค่าอ้างอิงอัตโนมัติ

---

## 4. โครงสร้างพื้นฐาน: เชื่อมต่อ ChatGPT Web Bridge (Web Bridge Setup)

> 💡 **หมายเหตุสำคัญทางสถาปัตยกรรม:**  
> คำสั่ง `atf.py bridge` เป็น **บริการทางเทคนิคอิสระ (Standalone Infrastructure Service)** ไม่ได้เป็นกระบวนการบังคับในท่อ คุณสามารถเปิดเซิร์ฟเวอร์ Bridge เมื่อใดก็ได้ตามที่ต้องการใช้งาน AI (เช่น ตอนให้ ChatGPT วิเคราะห์บุคลิกตัวละครในขั้นตอน `prepare-profiles` หรือตอนรันการแปลใน `translate`)

เทคโนโลยี **ChatGPT Web Bridge** ช่วยให้เชื่อมต่อโปรแกรมเข้ากับหน้าเว็บ `chatgpt.com` โดยตรงผ่าน Tampermonkey Userscript ทำให้ใช้งานโมเดลเรือธง (GPT-4o, o3, GPT-5) ได้ต่อเนื่องโดย **ไม่มีค่าใช้จ่าย API Token** และไม่มี Timeout

### วิธีการเปิดใช้งาน:
1. **ติดตั้ง Userscript ใน Tampermonkey:**
   - คัดลอกโค้ดทั้งหมดจากไฟล์: [atf_chatgpt_userscript.user.js](file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/src/atf/tools/atf_chatgpt_userscript.user.js)
   - ไปที่ Tampermonkey Dashboard -> สร้าง New Script -> วางโค้ดและกดบันทึก (Save)
2. **เปิดหน้าเว็บ ChatGPT:**
   - เปิดเบราว์เซอร์ไปที่ `https://chatgpt.com` และล็อกอินบัญชีของคุณค้างไว้
   - สังเกตแถบสถานะ Userscript ที่มุมจอ จะต้องขึ้นพร้อมเชื่อมต่อ
3. **เปิดเซิร์ฟเวอร์ Bridge Server (เปิดหน้าต่าง Terminal แยกค้างไว้ 1 หน้าต่าง):**
   - **PowerShell / CMD:**
     ```bash
     python atf.py bridge
     ```
   *หน้าต่างนี้จะรันรอรับ-ส่งข้อความระหว่าง Python และ Web Browser ตลอดการทำงาน*

---

## 5. ขั้นตอนที่ 2: เตรียมข้อมูลบทสนทนาและบริบทเกม (The 8 Preparation Stages)

การเตรียมข้อมูลของระบบถูกออกแบบให้เป็น **การวิเคราะห์บริบทเกมอัตโนมัติแท้จริง (True Universal Game Analyzer)** โดยแบ่งออกเป็น 8 ขั้นตอนย่อยอย่างเป็นระบบ ปราศจาก Hardcode ข้อมูลเกมเก่า 100%:

### 5.1 รันเตรียมข้อมูลแบบอัตโนมัติครบ 8 ขั้นตอน (One-Command Automation - แนะนำ)
คำสั่งเดียวจะรันต่อเนื่องครบทั้ง 8 ขั้นตอนหลัก (3a ถึง 3h):
- **PowerShell / CMD:**
  ```bash
  python atf.py prepare-all
  ```
*(หากเปิด `atf.py bridge` ไว้ ระบบจะเรียกใช้ ChatGPT วิเคราะห์โปรไฟล์ตัวละครเชิงลึกให้อัตโนมัติ หาก Bridge ออฟไลน์ ระบบจะสร้าง Baseline Profile ที่เป็นกลางไว้ให้)*

---

### 5.2 รันแยกทีละขั้นตอน (Step-by-Step Manual Execution)
หากต้องการรันเพื่อตรวจสอบผลลัพธ์ทีละส่วน สามารถรันคำสั่งย่อยตามสเต็ป 3a ถึง 3h ได้ดังนี้:

#### [3a] สกัดฉากและ Event Continuity (`prepare-scenes`)
สกัดโครงสร้างฉาก ลำดับ Event Flow และจับคู่ช้อยส์ตัวเลือก เพื่อจัดกลุ่ม Dialogue ให้ไม่ขาดตอน:
- **คำสั่ง:** `python atf.py prepare-scenes`
- **ผลลัพธ์:** `<output_dir>/tlas/scene_packets.json`

#### [3b] สกัด Master Glossary จากตัวเกมจริง (`prepare-glossary`)
สกัดชื่อตัวละคร, ไอเทม, สถานที่, สกิล และคำสั่ง UI จากฐานข้อมูลเกมจริง (`Actors.json`, `Items.json`, `Skills.json`, etc.) และดึงคำแปลจาก Baseline ที่ผู้ใช้กำหนดใน `setup` (ถ้ามี):
- **คำสั่ง:** `python atf.py prepare-glossary`
- **ผลลัพธ์:** `<output_dir>/tlas/tlas_glossary.json`

#### [3b.2 - AI] แปลคำศัพท์และชื่อเฉพาะใน Master Glossary ด้วย ChatGPT (`translate-glossary`)
ส่งชื่อตัวละคร สถานที่ และคำสั่งระบบใน `tlas_glossary.json` ไปให้ ChatGPT ช่วยแปลและทับศัพท์เป็นภาษาไทยระดับวรรณกรรม พร้อมบันทึกล็อกคำแปลไทย 1:1 กลับลงใน Glossary ทันที (ผู้ใช้สามารถเปิดตรวจแก้ชื่อที่ต้องการล็อกได้ก่อนเริ่มวิเคราะห์ตัวละคร):
- **คำสั่ง:** `python atf.py translate-glossary`
- **ผลลัพธ์:** อัปเดตฟิลด์ `"th"` ใน `<output_dir>/tlas/tlas_glossary.json` ครบถ้วน 100%

#### [3c] คัดกรอง Character Whitelist (`prepare-whitelist`)
วิเคราะห์ความถี่และบทบาทของตัวละคร เพื่อคัดแยกว่า "ใครควรถูกนำไปสร้าง Character Profile" (Core/Secondary) และใครเป็น "Ambient NPC" (Clean Passthrough ตาม ADR-035):
- **คำสั่ง:** `python atf.py prepare-whitelist`
- **ผลลัพธ์:** `<output_dir>/tlas/character_whitelist.json`

#### [3d] สังเคราะห์ Character Profiles ด้วย ChatGPT (`prepare-profiles`)
รวบรวมประโยคพูดจริงจากฉากต่างๆ ส่งไปให้ ChatGPT ผ่าน Web Bridge เพื่อวิเคราะห์เพศ, วัย, บุคลิก, สรรพนามภาษาไทย และความสัมพันธ์จริง **(Zero Hardcode)**:
- **คำสั่ง:** `python atf.py prepare-profiles`
- **ผลลัพธ์:** `<output_dir>/tlas/profiles/<Character_Name>.json`

#### [3e] สร้างตารางสรรพนามคู่สนทนาและ Demographic Matrix (`prepare-matrix`)
นำข้อมูล Profile ที่วิเคราะห์ได้มาประมวลผลเป็น Specific Pairwise Rules (Speaker $\rightarrow$ Listener) และสร้าง Demographic Identity Rules:
- **คำสั่ง:** `python atf.py prepare-matrix`
- **ผลลัพธ์:** `<output_dir>/tlas/global_pronoun_matrix.json`

#### [3f] สกัด Onomatopoeia และ Custom Dictionary (`prepare-sfx-dic`)
สแกนข้อความบทสนทนาจริงเพื่อจับคู่เสียงเอฟเฟกต์ตามบริบทฉาก (`sfx_glossary.json`) และสกัดคำเฉพาะ/แสลงที่ปรากฏซ้ำ (`dic_glossary.json`):
- **คำสั่ง:** `python atf.py prepare-sfx-dic`
- **ผลลัพธ์:** `<output_dir>/tlas/sfx_glossary.json` และ `<output_dir>/tlas/dic_glossary.json`

#### [3g] สร้างตารางแปล 10 มิติ (`prepare-table`)
ประกอบตารางมาตรฐาน 10 คอลัมน์ (`Original, Initial, Displayable, Role, Speaker, Listener, Third_Person, Filename, Row, Note`) พร้อมระบบ **Game Shielding** สกัดกั้นโค้ดและสวิตช์ระบบ (`Displayable: No`):
- **คำสั่ง:** `python atf.py prepare-table`
- **ผลลัพธ์:** `<output_dir>/<Game>_enriched.csv`

#### [3h] สร้าง Taxonomy ประจำเกม (`prepare-taxonomy`)
สร้างไฟล์ `taxonomy.json` สำหรับเกมใหม่โดยเฉพาะ จากแม่แบบสากล `templates/taxonomy.template.json` เพื่อให้พร้อมสำหรับระบุแท็กบริบทเฉพาะเกม:
- **คำสั่ง:** `python atf.py prepare-taxonomy`
- **ผลลัพธ์:** `<output_dir>/tlas/taxonomy.json`

---

## 6. ขั้นตอนที่ 4: สั่งรันการแปลเกม (Translation Runner)

ระบบแปลมาพร้อมกับ:
- **Persistent Mini-System Invariant:** ป้องกันคำสั่งล่องหนและ Style Drift
- **Zero-Token FastPath:** แปลแท็กชื่อและเครื่องหมายวรรคตอนญี่ปุ่น (`【夫】`, `・・・・`) ด้วย Python ตรง 100% ประหยัด Token
- **State Checkpointing:** บันทึกความคืบหน้าทุก Batch สามารถกดหยุดและรันต่อได้ทันที (Zero Skip Guarantee)

### 4.1 ทดสอบจำลองการแปลออฟไลน์ (Dry-Run):
ทดสอบการจัดกลุ่ม Batch, การดึงสรรพนาม, และจำลอง LQA โดยไม่ต้องต่อเน็ต:
- **PowerShell / CMD:**
  ```bash
  python atf.py translate --dry-run
  ```

### 4.2 สั่งรันแปลแบบระบุจำนวน Batch (เช่น ทดสอบ 5 แบตช์):
- **PowerShell / CMD:**
  ```bash
  python atf.py translate --batches 5
  ```

### 4.3 สั่งรันแปลจริงต่อเนื่องทั้งเรื่อง (Production Translation):
ระบบจะข้ามแถวที่แปลเสร็จแล้วอัตโนมัติ และรันต่อจนจบเรื่อง:
- **PowerShell / CMD:**
  ```bash
  python atf.py translate
  ```
*(หรือใช้คำสั่งลัด `python translate.py`)*

### ตัวเลือกเสริม (Optional Flags):
- `--unified`: แปลข้อความ UI เมนูจาก `plugins_texts.csv` ก่อน แล้วตามด้วยบทสนทนาของเกม
- `--reset-checkpoint`: ล้างความจำ Checkpoint และเริ่มแปลใหม่ตั้งแต่แถวแรก

---

## 7. ขั้นตอนที่ 5: ตรวจสอบคุณภาพและความสมบูรณ์ 8 มิติ (8D LQA Audit & Verification)

ตรวจสอบผลลัพธ์การแปลอย่างเข้มงวด 8 มิติตามหลักสากล:
1. **Explicit Tag Ground Truth:** ความถูกต้องของแท็กชื่อและบทสนทนา
2. **Triad Disjointness:** ห้ามระบุบุคคลเดียวกันเป็นทั้งผู้ฟังและบุคคลที่สามพร้อมกัน
3. **Inquiry Exclusion:** บุคคลที่ถูกถามหาต้องไม่ถูกระบุเป็นคู่สนทนา
4. **Non-Displayable Shielding:** โค้ด สวิตช์ ตัวแปรเกม ต้องคงสภาพต้นฉบับ 100%
5. **Monologue Isolation:** บทพูดคนเดียว/คิดในใจ ต้องระบุ Listener เป็น Self
6. **Active Dialogue Continuity:** บทสนทนาต้องมีความต่อเนื่อง
7. **Register & Persona Invariant:** ลีลาภาษาตรงตามบทบาท ปลอดอคติความสุภาพ (Anti-Polite Bias)
8. **Content Loss & Dropped Dialogue Shielding:** ป้องกันเนื้อหาบทสนทนาสูญหาย

### คำสั่งรันการตรวจสอบ 8 มิติ:
- **PowerShell:**
  ```powershell
  python atf.py verify
  ```
- **CMD:**
  ```cmd
  python atf.py verify
  ```
*ผลลัพธ์มาตรฐานระดับ Production: `0 Violations Certified (100% Pass)`*

---

## 8. ขั้นตอนที่ 6: ฉีดคำแปลและแพตช์คืนเกม (Game Patch Deployment)

### 8.1 สกัดและฉีดคำแปล UI เมนูของปลั๊กอิน (`plugins.js`):
- **สกัด UI Strings จากปลั๊กอิน:**
  ```bash
  python atf.py plugins --extract
  ```
- **ฉีดคำแปลภาษาไทยกลับเข้าสู่ `www/js/plugins.js` ของเกม:**
  ```bash
  python atf.py plugins --inject
  ```
  *(ระบบจะสร้างไฟล์แบ็กอัป `plugins.js.backup_plugin_<timestamp>.js` ป้องกันความเสียหายอัตโนมัติ)*

### 8.2 ส่งออกไฟล์ตารางแปลสำหรับแพตช์เกม (Final CSV Export):
ส่งออกไฟล์ CSV พร้อมนำไป Import ผ่าน Translator++ หรือ Tool ฉีดแพตช์ของ Game Engine:
- **PowerShell:**
  ```powershell
  python atf.py export
  ```
- **CMD:**
  ```cmd
  python atf.py export
  ```

---

## 9. ตารางสรุปคำสั่งด่วน (Command Cheat Sheet)

| ขั้นตอน | งานที่ทำ | คำสั่งสำหรับรัน |
| :---: | :--- | :--- |
| **0.1** | **สกัดข้อความ UI จากปลั๊กอินเกมใหม่** | `python extract_game_plugins.py` |
| **0.2** | เปิดสะพานเชื่อมต่อ ChatGPT | `python atf.py bridge` |
| **1** | ตั้งค่า Workspace & Manifest | `python atf.py setup` |
| **2** | **เตรียมข้อมูลทั้งเกมในคำสั่งเดียว** | `python atf.py prepare-all` |
| 2.1 | สแกน Speaker Tags | `python atf.py scan` |
| 2.2 | สร้าง Master Glossary & Whitelist | `python atf.py glossary` |
| 2.3 | สกัด Scene Packets | `python atf.py packets` |
| 2.4 | สร้าง Profiles & Matrix | `python atf.py matrix` |
| 2.5 | สร้างตารางแปล 10 คอลัมน์ | `python atf.py build-table` |
| **3** | ทดสอบแปลออฟไลน์ (Dry Run) | `python atf.py translate --dry-run` |
| **4** | **สั่งรันแปลจริงต่อเนื่องจนจบ** | `python atf.py translate` |
| **5** | ตรวจสอบคุณภาพ LQA 8 มิติ | `python atf.py verify` |
| **6** | ฉีดคำแปล UI คืน `plugins.js` | `python atf.py plugins --inject` |
| **7** | ส่งออกไฟล์แปลพร้อมแพตช์คืนเกม | `python atf.py export` |
