# Software Design Document (SDD)

**หมายเลขเอกสาร:** SDD-013  
**ชื่อระบบ:** SmartLineSplitter and Typography Restoration Specification  
**สถานะ:** Approved Design  
**วันที่:** 2026-09-23  
**เอกสารอ้างอิง:** ADR-016, SAD-011  

---

## 1. วัตถุประสงค์ (Purpose)

เอกสารฉบับนี้กำหนดรายละเอียดการออกแบบเชิงวิศวกรรม (Detailed Engineering Specification) โครงสร้างข้อมูล และขั้นตอนวิธี (Algorithms) ของคลาส `SmartLineSplitter` และสคริปต์สนับสนุนในระบบ **Typography Alignment and Line-Break Restoration** เพื่อให้เป็นมาตรฐานการจัดวางบรรทัดบทสนทนาภาษาไทยสำหรับเกม RPG Maker MV/MZ

---

## 2. โครงสร้างคลาสและอินเทอร์เฟซ (Class Interface Specification)

```python
from typing import List, Tuple, Optional, Set

class SmartLineSplitter:
    INSEPARABLE_PATTERNS: List[str]
    ILLEGAL_LINE_STARTERS: Set[str]

    @staticmethod
    def extract_prefix(text: str) -> Tuple[str, str]:
        """
        สกัด Speaker Tag เช่น \n<Dan:> หรือ <Shion:> ออกจากข้อความ
        Input: "\\n<Dan:>Hello world"
        Output: ("\\n<Dan:>", "Hello world")
        """

    @staticmethod
    def find_tail_anchor(line_str: str) -> Optional[str]:
        """
        สกัด Control Tag หรือ Punctuation ท้ายบรรทัดของ Original
        Input: "Wait a minute..\\." -> Output: "..\\."
        Input: "What is this?!" -> Output: "?!"
        """

    @classmethod
    def get_forbidden_cut_ranges(cls, text: str) -> List[Tuple[int, int]]:
        """
        คำนวณช่วงดัชนี (start, end) ที่ห้ามตัดกลางคำเด็ดขาด
        Input: "พวกเธอสองคน" -> Output: [(1, 7)] (ห้ามตัดระหว่างตำแหน่ง 1 ถึง 6)
        """

    @classmethod
    def split_thai_to_match_original(cls, orig_text: str, init_text: str) -> str:
        """
        อัลกอริทึมแบ่งบรรทัดภาษาไทยให้ตรงกับต้นฉบับ 100% (Strict Parity)
        Input: orig_text (K lines), init_text (Unformatted Thai)
        Output: Formatted Thai text (Exact K lines)
        """
```

---

## 3. ตารางค่าน้ำหนักการให้คะแนนทางไวยากรณ์ (Grammar Scoring Weights Matrix)

ในการประเมินจุดตัดใน Stage 2 ระบบจะคำนวณคะแนนของแต่ละตำแหน่งขอบเขตคำ ($pos$) โดยใช้สูตร:
$$\text{Total Score}(pos) = 1.5 \times |pos - \text{ideal\_idx}| + \sum \text{Adjustments}$$

| Feature / Linguistic Context | Condition / Pattern | Adjustment | Rationale (เหตุผลทางภาษาศาสตร์) |
|---|---|:---:|---|
| **Proximity Penalty** | $|pos - \text{ideal\_idx}| \times 1.5$ | $+$ Variable | ยิ่งห่างจากจุดสมดุลสัดส่วนของต้นฉบับ ยิ่งถูกหักคะแนน |
| **Space Bonus (ช่องว่าง)** | `pure_init[pos] == " "` หรือ `pure_init[pos-1] == " "` | **-30** | ช่องว่างคือจุดพักประโยคที่เป็นธรรมชาติที่สุดในภาษาไทย |
| **Punctuation / Anchor Bonus** | `(\.{2,}\|[!?~♥”\"'\)\]\}]+|\\[\.\|\!\^])$` | **-25** | เครื่องหมายวรรคตอนและจุดไข่ปลาคือจุดหยุดหายใจของบทสนทนา |
| **Ending Particle Bonus** | ลงท้ายด้วย `ครับ\|ค่ะ\|นะคะ\|นะ\|จ้ะ\|จ๊ะ\|ละ\|สิ\|หรอก\|เลย\|ด้วย\|เนอะ\|ล่ะ` | **-18** | คำลงท้ายบอกอารมณ์และจังหวะจบประโยคย่อยอย่างเป็นธรรมชาติ |
| **Conjunction Bonus (คำเชื่อม)** | ขึ้นต้นด้วย `แต่\|และ\|หรือ\|เพราะ\|ถ้า\|หาก\|ดังนั้น\|แล้ว\|ก็\|ซึ่ง\|เพื่อ\|แถม\|ทั้งที่` | **-15** | การขึ้นบรรทัดใหม่ด้วยคำเชื่อมประโยคช่วยให้อ่านเข้าใจง่าย |
| **Dangling Particle Penalty** | คำถัดไปเป็นคำลงท้ายโดดเดี่ยว เช่น ขึ้นต้นบรรทัดด้วย `นะ..` หรือ `ค่ะ` | **+45** | ห้ามมีคำลงท้ายห้อยโดดเดี่ยวในบรรทัดใหม่โดยเด็ดขาด |
| **Short Next Segment Penalty** | ความยาวของข้อความท่อนถัดไปน้อยกว่า 5 ตัวอักษร | **+40** | ป้องกันการเกิดเศษคำสั้นๆ ค้างที่ปลายประโยค |
| **Forbidden Word Severing** | $pos \in [st, ed]$ ของ `forbidden_ranges` | **REJECT** | ปฏิเสธทันที (ห้ามผ่ากลุ่มคำประสมเด็ดขาด) |
| **Illegal Line Starter** | `pure_init[pos] \in ILLEGAL_LINE_STARTERS` | **REJECT** | ปฏิเสธทันที (ห้ามสระบน/ล่าง วรรณยุกต์ การันต์ ไม้ยมก ขึ้นต้นบรรทัด) |

---

## 4. รายละเอียดกฎนิพจน์ปกติ (Regular Expression Rules)

### 4.1 ชุดคำประสมห้ามผ่า (`INSEPARABLE_PATTERNS`)
```python
INSEPARABLE_PATTERNS = [
    # 1. กลุ่มคำนำหน้านามพหูพจน์ + สรรพนาม
    r"พวก(?:เธอ|เรา|เขา|มัน|ท่าน|เจ้า|นาย|นั้น|นี้|โน้น|เด็กๆ?|ผู้หญิง|ผู้ชาย|คน|สาวๆ?|อันธพาล)",
    # 2. กลุ่มคำระบุชี้เฉพาะ (Demonstratives / Pronouns)
    r"(?:คน|สิ่ง|เรื่อง|อัน|แบบ|อย่าง|ทาง|ฝ่าย|ด้าน)(?:นี้|นั้น|โน้น|อื่น|ใด|ไหน)",
    r"(?:ตอน|คราว|เวลา|สมัย|ช่วง|ยุค)(?:นี้|นั้น|โน้น|ก่อน|หลัง|ไหน)",
    r"(?:ที่|ตรง)(?:นี้|นั้น|โน้น|ไหน|ใด|แห่งนี้|แห่งนั้น)",
    # 3. คำปฏิเสธ และ กริยานุเคราะห์ผสม
    r"ไม่(?:ได้|ใช่|มี|เคย|ยอม|ว่า|อยาก|ต้อง|เป็นไร|เอา|ถูก|จริง|พอ|ทัน)",
    r"(?:กำลัง|จะต้อง|น่าจะ|อาจจะ|ควรจะ|แทบจะ|เกือบจะ)",
    # 4. คำสรรพนามและคำถามผสม
    r"(?:อะไร|อย่างไร|ทำไม|เท่าไหร่|เท่าใด|เมื่อไหร่|ใคร)",
    # 5. คำเชื่อมและวลีต่อเนื่อง
    r"(?:เหมือนกัน|เช่นกัน|ด้วยกัน|ด้วยนะ|ด้วยสิ|ด้วยค่ะ|ด้วยครับ|ด้วยล่ะ)",
    r"(?:จริง(?:ๆ|จัง)?|แน่(?:นอน|ใจ)?|ชัด(?:เจน)?|จริงหรือ)",
    r"(?:สักพัก|สักหน่อย|นิดหน่อย|นิดเดียว|อีกหน่อย|อีกนิด|สักนิด)",
    # 6. คำนามประสมทั่วไปที่พบบ่อยในบทพูด
    r"(?:ผู้หญิง|ผู้ชาย|เด็กหญิง|เด็กชาย|ทุกคน|ทุกคนที่นี่|ใครบางคน|คนแปลกหน้า)",
]
```

### 4.2 ชุดอักขระต้องห้ามขึ้นต้นบรรทัดใหม่ (`ILLEGAL_LINE_STARTERS`)
```python
ILLEGAL_LINE_STARTERS = set("ิีึืุูั่้๊๋์็๎ํะาำๆฯ)]}>”\"'’,~?!♥")
```

---

## 5. การจำลองการทำงานทีละขั้นตอน (Step-by-Step Execution Traces)

### ตัวอย่างที่ 1: การคุ้มครองคำประสม (Jinnie Row 465)
- **Original (2 บรรทัด):**
  ```
  \n<Jinnie:>I got lucky with you two here~!
  \fiWe'll\fi help solve all of that.
  ```
- **Input Initial (บรรทัดเดียว):**
  ```
  \n<Jinnie:>ฉันโชคดีจริง ๆ ที่มีพวกเธอสองคนอยู่ที่นี่~! \fiพวกเรา\fiจะช่วยกันแก้ปัญหาทั้งหมดนั่นเองค่ะ
  ```
- **การประมวลผล:**
  1. `extract_prefix`: ได้ prefix = `\n<Jinnie:>`, `pure_init` = `"ฉันโชคดีจริง ๆ ที่มีพวกเธอสองคนอยู่ที่นี่~! \fiพวกเรา\fiจะช่วยกันแก้ปัญหาทั้งหมดนั่นเองค่ะ"`
  2. `forbidden_ranges`: ตรวจพบคำว่า `พวกเธอ` (ตำแหน่ง 21–27) และ `พวกเรา` (ตำแหน่ง 47–53)
  3. `ideal_idx`: คำนวณตามสัดส่วนต้นฉบับ ตกอยู่ที่ตำแหน่งประมาณ 24 (ซึ่งอยู่กลางคำว่า `พวกเธอ`)
  4. Stage 2 Evaluation: ตำแหน่ง 24 โดนบล็อกโดย `forbidden_ranges`! ระบบจึงขยับไปเลือกขอบเขตคำหลังเครื่องหมายวรรคตอน `~!` ที่ตำแหน่ง 41 (ได้โบนัส Punctuation -25 และ Space -30)
- **ผลลัพธ์ (2 บรรทัดตรงกับต้นฉบับเป๊ะ):**
  ```
  \n<Jinnie:>ฉันโชคดีจริง ๆ ที่มีพวกเธอสองคนอยู่ที่นี่~!
  \fiพวกเรา\fiจะช่วยกันแก้ปัญหาทั้งหมดนั่นเองค่ะ
  ```

---

### ตัวอย่างที่ 2: ข้อความสั้น 2 บรรทัด (Short Dialogue)
- **Original (2 บรรทัด):**
  ```
  Dan..?
  What is it?
  ```
- **Input Initial:** `"แดน...? มีอะไรเหรอคะ?"` (`L = 21`)
- **การประมวลผล:**
  1. `min_seg = max(1, min(5, 21 // 4)) = 5`
  2. `lower_bound = 0 + 5 = 5`, `upper_bound = 21 - 5 = 16`
  3. Stage 1 (Tail Anchor): ตรวจพบ Anchor `..?` ในต้นฉบับบรรทัดแรก แมปตรงกับ `...?` ในภาษาไทยที่ตำแหน่ง 7
  4. ตรวจสอบเงื่อนไข: $5 \le 7 \le 16$ (อยู่ในช่วงปลอดภัย!)
  5. เลือกลงจุดตัดที่ตำแหน่ง 7 ทันที
- **ผลลัพธ์ (2 บรรทัดตรงกับต้นฉบับเป๊ะ):**
  ```
  แดน...?
  มีอะไรเหรอคะ?
  ```

---

## 6. อัลกอริทึมการเชื่อมต่อในระดับสคริปต์ (Script Integration)

### 6.1 `repair_file` ใน `repair_line_breaks.py`
```python
# ตรวจจับทุกแถวที่จำนวนบรรทัดไม่ตรงกับต้นฉบับ
if orig_nl > 0 and init.strip() and init_nl != orig_nl:
    new_init = SmartLineSplitter.split_thai_to_match_original(orig, init)
    if new_init != init:
        row[1] = new_init
        checkpoint_data["csv_translations"][csv_key][str(r_idx)] = new_init
```

### 6.2 `sync_and_align_lines` ใน `sync_checkpoint_to_csv.py`
```python
# เติมคำแปลจาก Checkpoint พร้อมจัดระเบียบบรรทัดในตัว
if not init.strip() and str_r in checkpoint_translations:
    translated_text = checkpoint_translations[str_r]
    if orig_nl > 0:
        row[1] = SmartLineSplitter.split_thai_to_match_original(orig, translated_text)
    else:
        pfx, pure = SmartLineSplitter.extract_prefix(translated_text)
        row[1] = f"{pfx}{re.sub(r'\s*\n\s*', ' ', pure).strip()}"
```

---

## 7. แผนภาพการเชื่อมโยงทางวิศวกรรม (Traceability Matrix & Cross-References)

เอกสารฉบับนี้เป็นข้อกำหนดการออกแบบระดับล่าง (Low-Level Design - LLD) ที่แปลงมาจากข้อกำหนดสถาปัตยกรรมระดับบน (High-Level Design - HLD) ดังนี้:

| Document ID | Type | Title | Dependency & Traced Requirements |
|---|:---:|---|---|
| **[ADR-016](../adr/ADR-016-Smart-Line-Splitting-and-Strict-Invariant-Restoration.md)** | ADR | Smart Line Splitting & Strict Invariant Restoration | แปลง Decision ข้อ 1-5 (Parity Invariant, Dynamic Windowing, Inseparable Protection, Waterfall Selection) สู่ Implementation Code |
| **[SAD-011](../architecture/SAD-011-Typography-Alignment-and-Line-Break-Parity.md)** | SAD | Typography Alignment & Line-Break Parity Architecture | กำหนด Component Specification ของ Core Typography Engine ใน Stage 5 ของ ATF Pipeline |
| **[SDD-004](SDD-004-TLAS-Implementation-Details.md)** | SDD | TLAS Implementation Details | สอดรับกับโครงสร้าง CSV Columns (`Original, Initial, Filename, Row, Role, Speaker, Displayable`) |
| **[SDD-008](SDD-008-TLAS-Rule-Based-Engine.md)** | SDD | Rule-Based Engine Specification | ใช้มาตรฐานการจัดการ Thai Particles และ Tokenizer Engine เดียวกัน |
| **[SDD-010](SDD-010-TLAS-Global-Character-and-Speech-Schema.md)** | SDD | Global Character & Speech Schema | อ้างอิงคำลงท้าย (`ending_particle`) เพื่อใช้เป็น Positive Bonus ใน Grammar Scoring Matrix |
