---
name: game-engine-extractors
description: >-
  Standard Operating Procedures for extracting and packaging game dialogues, UI strings,
  and metadata across various game engines (RPG Maker, Ren'Py, Godot, Unity, Unreal Engine).
---

# Game Engine Extraction & Localization Skill

คู่มือขั้นตอนปฏิบัติงานมาตรฐาน (SOP) ในการสกัดบทสนทนา ข้อความ UI และฐานข้อมูลจากเอนจินเกมต่างๆ เข้าสู่โครงสร้างสากลของ ATF

---

## 1. RPG Maker (MV / MZ / VX Ace)
- **Engine Signature:**
  - MV/MZ: มีโฟลเดอร์ `www/data/` หรือ `data/` บรรจุไฟล์ `.json` เช่น `System.json`, `MapInfos.json`, `MapXXX.json`, `CommonEvents.json`, `Actors.json`, `Enemies.json`, `Items.json` และมี `plugins.js`
  - VX Ace / XP: มีโฟลเดอร์ `Data/` บรรจุไฟล์ `.rvdata2` หรือ `.rxdata`
- **Extraction Protocol:**
  - สกัด Dialogues และ Choices โดยจับคู่ Event Command Codes (Code 101: Speaker/Face, Code 401: Dialogue line, Code 102: Choices)
  - แปลง Game Control Codes เป็น Semantic XML Tags: `\C[n]` -> `<color id="n">`, `\N[n]` -> `<actor id="n">`, `\.` -> `<pause_quarter/>`
  - สกัด Plugin Texts จาก `plugins.js` หรือ parameter blocks ของปลั๊กอินยอดนิยม (VisuStella, Yanfly, MOG)

---

## 2. Ren'Py Visual Novel Engine
- **Engine Signature:**
  - มีโฟลเดอร์ `game/` บรรจุไฟล์สคริปต์ `.rpy` หรือไฟล์แพ็กเกจ `.rpa`
- **Extraction Protocol:**
  - Ren'Py มีระบบ Localization ในตัว: `renpy.exe <game_dir> translate <language>` หรือการ Parse ไฟล์ `.rpy` โดยตรง
  - สกัด String Translation Blocks:
    ```renpy
    translate thai strings:
        old "Start Game"
        new "เริ่มเกม"
    ```
  - สกัด Dialogue Dialogue Blocks:
    ```renpy
    translate thai scene_01_abc:
        # e "Hello, world!"
        e "สวัสดีชาวโลก!"
    ```
  - การจับคู่ Character: ดูจากคำสั่งนิยาม `define e = Character("Eileen", color="#c8ffc8")` เพื่อสร้าง Character Profile

---

## 3. Godot Engine
- **Engine Signature:**
  - มีไฟล์ `project.godot`, ไฟล์ทรัพยากร `.tscn`, `.tres`, และโฟลเดอร์ `localization/` ที่บรรจุไฟล์ `.csv` หรือ `.po` (Gettext)
- **Extraction Protocol:**
  - Godot ใช้มาตรฐาน CSV หรือ PO: คอลัมน์แรกเป็น `id` / `msgid`, คอลัมน์ถัดไปเป็นรหัสภาษา (`en`, `ja`, `th`)
  - Parse และ Generate PO/CSV ที่รองรับ RichTextLabel BBCode (เช่น `[b]...[/b]`, `[color=red]...[/color]`) โดยแปลงเป็น Masked Tags ก่อนส่งแปล

---

## 4. Unity Engine
- **Engine Signature:**
  - ไฟล์ `globalgamemanagers`, โฟลเดอร์ `Managed/`, หรือไฟล์ Asset Bundles (`.assets`, `.bundle`)
  - โครงสร้าง Localization นิยมใช้ Unity Localization Package หรือปลั๊กอินยอดนิยมอย่าง **I2 Localization**
- **Extraction Protocol:**
  - ใช้เครื่องมือ Export สตริงภาษา (เช่น AssetStudio, UABEA, หรือสคริปต์สกัด CSV จาก I2 Localization Source)
  - รองรับ Rich Text Tags (`<size=20>`, `<color=#ffffff>`, `<material=1>`) และ Smart String format parameters (`{0}`, `{playerName}`)

---

## 5. Unreal Engine
- **Engine Signature:**
  - มีโฟลเดอร์ `Content/Localization/` บรรจุไฟล์ String Tables, `.locres`, หรือไฟล์ `.po`
- **Extraction Protocol:**
  - ดึงข้อมูลจาก Portable Object (`.po`) หรือ CSV String Tables
  - ดูแลรักษา Named Arguments และ Plural Form Rules ของ Unreal Engine ให้คงรูป 100%

---

## 6. Universal ATF Pipeline Output Format
ไม่ว่าจะสกัดมาจากเอนจินใด ข้อมูลทั้งหมดจะต้องถูกแปลงเข้าสู่โครงสร้างตาราง 8 คอลัมน์สากลของ ATF เสมอ:
`RowIndex, Initial, Original, Displayable, LineRole, Speaker, SourceContext, Notes`
