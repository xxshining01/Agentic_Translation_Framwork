# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-014  
**ชื่อระบบ:** Untranslated Queue Filter and Checkpoint Synchronization Specification  
**สถานะ:** Approved Design  
**วันที่:** 2026-09-23  
**เอกสารอ้างอิง:** ADR-017, SAD-012, SDD-013, SAD-011  

---

## 1. วัตถุประสงค์ (Purpose)

เอกสารฉบับนี้กำหนดรายละเอียดการออกแบบเชิงวิศวกรรม (Detailed Engineering Specification) โครงสร้างข้อมูล และขั้นตอนวิธี (Algorithms) ของคลาส `CheckpointConsolidator`, `PureQueueFilter`, และ `AtomicPersistenceManager` ในระบบ **Fault-Tolerant Translation Runner and State Synchronization (Stage 6)** เพื่อสร้างมาตรฐานความทนทานต่อความล้มเหลว (Fault Tolerance), การคัดกรองคิวแปลที่บริสุทธิ์, และการซิงค์ข้อมูลสอดคล้องกันแบบสองทิศทาง 100%

---

## 2. โครงสร้างคลาสและอินเทอร์เฟซ (Class Interface Specification)

```python
from typing import List, Dict, Tuple, Optional, Any, Set
import os
import json
import csv

class CheckpointConsolidator:
    """
    โมดูลรวบรวมและประสานข้อมูลคำแปลจากทุก Section ใน Checkpoint JSON
    """
    @staticmethod
    def load_unified_translations(checkpoint_path: str) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        โหลดและรวมคำแปลจากทุก Section Key ใน csv_translations
        Returns:
            unified_map: Dict[str, str] แมป {str(row_index): translated_text}
            raw_checkpoint_data: Dict[str, Any] ข้อมูลดิบทั้งหมดของ Checkpoint
        """

    @staticmethod
    def update_two_way_sync(
        raw_checkpoint: Dict[str, Any], 
        row_index: str, 
        text: str, 
        active_sections: List[str]
    ) -> None:
        """
        บันทึกคำแปลที่ผ่านการซ่อมแซมลงสู่ทุก Section Key พร้อมกันในหน่วยความจำ
        """


class PureQueueFilter:
    """
    โมดูลวิเคราะห์และคัดกรองแถวบริสุทธิ์สำหรับส่งเข้าคิวแปล LLM
    """
    NON_TRANSLATABLE_SYMBOLS: Set[str] = {"-", "--", "---", "...", "..", "***", "??", "!!"}

    @classmethod
    def is_eligible_for_translation(cls, row: List[str]) -> Tuple[bool, str]:
        """
        ตรวจสอบว่าแถวใน CSV เข้าเกณฑ์การส่งแปลหรือไม่
        Args:
            row: รายการคอลัมน์ใน CSV [Original, Initial, Filename, Row, Role, Speaker, Displayable]
        Returns:
            (is_eligible, reason)
        """

    @classmethod
    def is_natural_language_text(cls, text: str) -> bool:
        """
        ตรวจสอบว่าข้อความมีเนื้อหาภาษาธรรมชาติที่ต้องแปลหรือไม่
        (ขจัดกรณีมีเฉพาะตัวเลข, สัญลักษณ์, หรือ Control Codes)
        """


class AtomicPersistenceManager:
    """
    โมดูลจัดการการบันทึกไฟล์ลงฮาร์ดดิสก์แบบ Atomic ป้องกันข้อมูลเสียหาย 100%
    """
    @staticmethod
    def create_timestamped_backup(file_path: str, suffix: str = "backup_sync") -> str:
        """
        สร้างไฟล์สำรองระบุเวลา เช่น target.csv.backup_sync_20260923_223000.csv
        """

    @staticmethod
    def atomic_write_csv(file_path: str, rows: List[List[str]]) -> None:
        """
        เขียนข้อมูล CSV ลง .tmp และสลับไฟล์ด้วย os.replace (OS Atomic Guarantee)
        """

    @staticmethod
    def atomic_write_json(file_path: str, data: Dict[str, Any]) -> None:
        """
        เขียนข้อมูล JSON ลง .tmp และสลับไฟล์ด้วย os.replace (OS Atomic Guarantee)
        """
```

---

## 3. ตารางเกณฑ์การคัดกรองแถว (Queue Filtering Decision Matrix)

ในการประเมินแถวใน CSV แต่ละแถว คลาส `PureQueueFilter` จะทำการตัดสินใจตามกฎลำดับขั้น (Hierarchical Rules) ดังนี้:

| ลำดับเกณฑ์ (Rule Priority) | เงื่อนไขในข้อมูล (Condition) | ผลลัพธ์ (Action) | เหตุผลทางวิศวกรรม (Engineering Rationale) |
|---|---|:---:|---|
| **1. Displayable Guard** | `Displayable != "Yes"` | **SKIP** | ข้อความที่ผู้เล่นมองไม่เห็นบนจอเกม (Internal Data/Events) ไม่จำเป็นต้องแปล |
| **2. Role Whitelist** | `Role \notin {"Dialogue/Story", "System/Menu", "Skill/Item"}` | **SKIP** | ป้องกันการแปลโค้ดสคริปต์, ชื่อตัวแปร, หรือ Label ภายในเอนจิน |
| **3. Empty Original** | `not Original.strip()` | **SKIP** | ต้นฉบับไม่มีข้อความ |
| **4. Pure Symbols / Punctuation** | `Original.strip() \in NON_TRANSLATABLE_SYMBOLS` หรือมีเฉพาะเครื่องหมาย | **AUTO-FILL** | สัญลักษณ์เช่น `-` หรือ `...` ให้คัดลอกค่าจาก Original ไปใส่ Initial โดยตรง |
| **5. Pure Control Tags** | ข้อความมีเฉพาะรหัสควบคุมเกม เช่น `\^`, `\!`, `\C[0]` | **AUTO-FILL** | รหัสสั่งการของเกมที่ไม่มีตัวอักษรของมนุษย์ ให้คงรูปเดิมไว้ 100% |
| **6. Already In Checkpoint** | `str(row_index) \in checkpoint_unified_map` | **RESTORE & FORMAT** | มีคำแปลใน Checkpoint แล้ว ให้นำมาจัดบรรทัดใหม่ด้วย `SmartLineSplitter` และใส่ CSV |
| **7. Already Translated in CSV** | `Initial.strip() != ""` และบรรทัดไม่ตรง | **LINE REPAIR** | มีคำแปลแล้วแต่บรรทัดไม่ตรง ให้จัดระเบียบบรรทัดใหม่และอัปเดต Checkpoint |
| **8. Pure Untranslated Dialogue** | ผ่านเกณฑ์ 1-5 และ `Initial` ยังว่างเปล่า | **QUEUE FOR LLM** | บรรจุเข้าคิวแปลส่งไปยัง Translation Runtime (Stage 4) ทันที |

---

## 4. รายละเอียดกฎนิพจน์ปกติและรูปแบบข้อมูล (Regex & Auto-Bypass Rules)

### 4.1 ตรวจสอบสัญลักษณ์และรหัสควบคุมล้วน (`is_natural_language_text`)
```python
# รูปแบบข้อความที่ไม่ใช่ภาษาธรรมชาติ (ไม่ต้องเรียก LLM)
PURE_SYMBOLS_PATTERN = r"^[\s\-_.\*~!?,:;\"'()\[\]{}|\\/]+$"
PURE_CONTROL_TAGS_PATTERN = r"^(?:\\[a-zA-Z]+(?:\[\d+\])?|\s+)+$"

def is_natural_language_text(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return False
    # ตรวจสอบว่าเป็นสัญลักษณ์ล้วนหรือไม่
    if re.match(PURE_SYMBOLS_PATTERN, clean):
        return False
    # ตรวจสอบว่าเป็นรหัสควบคุมเกมล้วนหรือไม่
    if re.match(PURE_CONTROL_TAGS_PATTERN, clean):
        return False
    # ต้องมีอักขระตัวหนังสือภาษาอังกฤษหรือภาษาญี่ปุ่น/ไทยอย่างน้อย 1 ตัว
    if not re.search(r"[a-zA-Z\u0E00-\u0E7F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", clean):
        return False
    return True
```

---

## 5. การจำลองการทำงานทีละขั้นตอน (Step-by-Step Execution Traces)

### ตัวอย่างที่ 1: การกู้คืนบทสนทนาตกค้าง 1,732 แถว (Row 68304)
- **ข้อมูลใน CSV:**
  - `Row`: 68304
  - `Original`: `"\n<Dan:>Are you okay?\nTake a deep breath."`
  - `Initial`: `""` (ค่าว่างเปล่า!)
  - `Role`: `Dialogue/Story`, `Displayable`: `Yes`
- **การประมวลผล:**
  1. `CheckpointConsolidator` โหลดข้อมูลจาก `chatgpt_translation_checkpoint.json`
  2. พบคำแปลที่คีย์ `68304` ใน Section `"SSPV034v1.35 - Trans - Processed_v3.csv"`:
     `"\n<Dan:>เธอไม่เป็นไรใช่ไหม? หายใจเข้าลึกๆ นะ"`
  3. `PureQueueFilter` จัดแถวนี้เข้าสู่ Case 6 (Restore & Format)
  4. ส่งข้อความเข้า `SmartLineSplitter.split_thai_to_match_original`:
     - บรรทัดที่ 1: `"\n<Dan:>เธอไม่เป็นไรใช่ไหม?"`
     - บรรทัดที่ 2: `"หายใจเข้าลึกๆ นะ"`
  5. อัปเดตคำแปลที่จัดบรรทัดแล้วกลับสู่ `row[1]` ใน CSV Buffer
  6. อัปเดต `68304` ลงในทุก Section ของ Checkpoint ใน RAM
- **ผลลัพธ์:** บทสนทนาได้รับการกู้คืนและจัดบรรทัดเป๊ะ 100% โดยไม่ต้องเสียเงินเรียก LLM API ซ้ำ

---

### ตัวอย่างที่ 2: การคัดกรองแถวที่ไม่ใช่ภาษาธรรมชาติ (Pure Symbols)
- **ข้อมูลใน CSV:**
  - `Row`: 71200
  - `Original`: `"---"`
  - `Initial`: `""`
  - `Role`: `Dialogue/Story`, `Displayable`: `Yes`
- **การประมวลผล:**
  1. `PureQueueFilter.is_natural_language_text("---")` $\to$ คืนค่า `False` (ตรงกับ `PURE_SYMBOLS_PATTERN`)
  2. จัดเข้าสู่ Case 4 (Auto-Fill)
  3. กำหนด `row[1] = "---"` โดยตรง
- **ผลลัพธ์:** ข้ามการเรียก LLM ทันที ประหยัดเวลา 1 รอบ API Call และไม่ทำให้คิวงานปนเปื้อน

---

## 6. อัลกอริทึมการเชื่อมต่อในระดับสคริปต์ (Script Integration)

### 6.1 การบูรณาการใน `sync_checkpoint_to_csv.py`
```python
def sync_and_align_lines(csv_path, checkpoint_path, dry_run=False):
    # 1. รวบรวมคำแปลข้าม Section ทั้งหมด
    unified_map, raw_cp = CheckpointConsolidator.load_unified_translations(checkpoint_path)
    
    # 2. ประมวลผลแถวใน CSV
    rows = read_csv(csv_path)
    for r_idx in range(1, len(rows)):
        str_r = str(r_idx)
        orig = rows[r_idx][0]
        init = rows[r_idx][1]
        
        # กรณี Initial ว่าง แต่มีใน Checkpoint
        if not init.strip() and str_r in unified_map:
            formatted = SmartLineSplitter.split_thai_to_match_original(orig, unified_map[str_r])
            rows[r_idx][1] = formatted
            CheckpointConsolidator.update_two_way_sync(raw_cp, str_r, formatted, ACTIVE_SECTIONS)
            
    # 3. บันทึกผลลัพธ์แบบ Atomic พร้อม Backup เสมอ
    if not dry_run:
        AtomicPersistenceManager.create_timestamped_backup(csv_path)
        AtomicPersistenceManager.create_timestamped_backup(checkpoint_path)
        AtomicPersistenceManager.atomic_write_csv(csv_path, rows)
        AtomicPersistenceManager.atomic_write_json(checkpoint_path, raw_cp)
```

---

## 7. แผนภาพการเชื่อมโยงทางวิศวกรรม (Traceability Matrix & Cross-References)

| Document ID | Type | Title | Dependency & Traced Requirements |
|---|:---:|---|---|
| **[ADR-017](../adr/ADR-017-Atomic-Checkpoint-Persistence-and-Queue-Filtering.md)** | ADR | Atomic Checkpoint Persistence & Pure Queue Filtering | แปลงข้อกำหนดทางสถาปัตยกรรม (Two-Way Sync, Atomic Swap, Pure Queue Filter) สู่โครงสร้างคลาสและโค้ด |
| **[SAD-012](../architecture/SAD-012-Fault-Tolerant-Translation-Runner-and-State-Sync.md)** | SAD | Fault-Tolerant Translation Runner Architecture | กำหนดพิมพ์เขียว Stage 6 Persistence & State Synchronization |
| **[SDD-013](SDD-013-SmartLineSplitter-and-Typography-Restoration.md)** | SDD | SmartLineSplitter Specification | อ้างอิงและเรียกใช้งานคลาส `SmartLineSplitter` เพื่อจัดบรรทัดระหว่างการ Sync |
| **[SAD-011](../architecture/SAD-011-Typography-Alignment-and-Line-Break-Parity.md)** | SAD | Typography Alignment & Line-Break Parity Architecture | สอดรับกับมาตรฐาน Stage 5 Typography Parity Engine |
| **[SDD-004](SDD-004-TLAS-Implementation-Details.md)** | SDD | TLAS Implementation Details | ยึดตามโครงสร้าง CSV Columns 7 คอลัมน์มาตรฐานของ ATF |
