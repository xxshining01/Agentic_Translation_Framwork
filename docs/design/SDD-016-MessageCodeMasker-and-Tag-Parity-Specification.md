# SDD-016: MessageCodeMasker and Tag Parity Specification

## 1. Component Specification
- **Component Name:** `MessageCodeMasker` (Stage 4.1 & Stage 4.2)
- **Module Location:** `testing files/control_code_masker.py` (และ `src/atf/core/control_code_masker.py`)
- **Implements Architecture:** [ADR-019](file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/docs/adr/ADR-019-Control-Code-Masking-and-Bidirectional-Parity-Preservation.md), [SAD-014](file:///d:/Agentic%20Translation%20Framework%20(ATF)%20Project/docs/architecture/SAD-014-Control-Code-Masking-and-Sanitization-Engine.md)
- **Primary Mission:** แปลง In-line Control Codes ของเกมให้อยู่ในรูป Semantic XML Tags ก่อนส่ง LLM และแปลงคืนสู่รหัสเดิมหลังแปลเสร็จ พร้อมตรวจสอบ Tag Parity 100%

---

## 2. API Signature & Class Design

```python
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

@dataclass
class MaskResult:
    masked_text: str
    original_tags: List[str]
    has_control_codes: bool

@dataclass
class UnmaskResult:
    unmasked_text: str
    is_valid_parity: bool
    missing_tags: List[str]
    extra_tags: List[str]
    repaired: bool

class MessageCodeMasker:
    """
    Universal In-line Control Code Masker and Parity Verifier.
    Supports RPG Maker MV/MZ, Ren'Py, and custom game engine codes.
    """
    def __init__(self, engine_type: str = "rpgmaker_mv"):
        self.engine_type = engine_type
        self._init_rules()

    def sanitize_raw_escapes(self, text: str) -> str:
        """Sanitizes \\x0c Form Feed hazards and double-backslash anomalies."""
        ...

    def mask(self, text: str) -> MaskResult:
        """Converts raw game control codes into XML-like tags."""
        ...

    def unmask(self, masked_translated: str, expected_tags: Optional[List[str]] = None) -> UnmaskResult:
        """Converts XML-like tags back to original game control codes with validation."""
        ...

    def verify_tag_parity(self, masked_original: str, masked_translated: str) -> Tuple[bool, List[str], List[str]]:
        """Compares tag occurrences between masked original and masked translated."""
        ...
```

---

## 3. Transformation Rules & Regular Expressions

### 3.1 Paired Formatting Tags
1. **Italics (`\fi`):**
   - Pattern: `r"\\fi(.*?)\\fi"` (Non-greedy)
   - Replacement: `<italic>\1</italic>`
   - Reverse Pattern: `r"<italic>(.*?)</italic>"`
   - Reverse Replacement: `r"\\fi\1\\fi"`

2. **Bold (`\fb`):**
   - Pattern: `r"\\fb(.*?)\\fb"`
   - Replacement: `<bold>\1</bold>`
   - Reverse Pattern: `r"<bold>(.*?)</bold>"`
   - Reverse Replacement: `r"\\fb\1\\fb"`

3. **Color (`\C[n]...\C` or `\C[n]...\C[0]`):**
   - Pattern: `r"\\C\[(\d+)\](.*?)\\C(?:\[0\])?"`
   - Replacement: `<color id="\1">\2</color>`
   - Reverse Pattern: `r"<color id=[\"']?(\d+)[\"']?>(.*?)</color>"`
   - Reverse Replacement: `r"\\C[\1]\2\\C"`

### 3.2 Self-Closing Tags
1. **Pause 1/4 sec (`\.`):**
   - Pattern: `r"\\\."`
   - Replacement: `<pause_quarter/>`
   - Reverse: `r"<pause_quarter\s*/>"` $\to$ `r"\."`

2. **Pause 1 sec (`\|`):**
   - Pattern: `r"\\\|"`
   - Replacement: `<pause_second/>`
   - Reverse: `r"<pause_second\s*/>"` $\to$ `r"\|"`

3. **Wait for Input (`\!`):**
   - Pattern: `r"\\!"`
   - Replacement: `<wait_input/>`
   - Reverse: `r"<wait_input\s*/>"` $\to$ `r"\!"`

4. **Icons (`\I[n]`):**
   - Pattern: `r"\\I\[(\d+)\]"`
   - Replacement: `<icon id="\1"/>`
   - Reverse: `r"<icon id=[\"']?(\d+)[\"']?\s*/>"` $\to$ `r"\I[\1]"`

5. **Variables / Actors (`\V[n]`, `\N[n]`):**
   - Pattern: `r"\\V\[(\d+)\]"` $\to$ `<var id="\1"/>`
   - Pattern: `r"\\N\[(\d+)\]"` $\to$ `<actor id="\1"/>`

---

## 4. Resilience & Auto-Repair Logic

หากตรวจพบว่า LLM แปลแล้วลืมแท็ก หรือวางแท็กผิดตำแหน่ง:
1. **Missing Tag Repair:** หากใน Original มี `<wait_input/>` ท้ายประโยค แต่ผลลัพธ์ของ AI ไม่มี ให้แทรก Tag นั้นกลับเข้าไปที่ตำแหน่งใกล้เคียงที่สุด (เช่น ท้ายประโยค)
2. **Malformed Tag Repair:** หาก AI พิมพ์ `<italic>ข้อความ<italic>` (ลืม slash ปิด) หรือ `<italic>ข้อความ</italic` (ขาดวงเล็บ) ตัว Regex Parser จะต้องตรวจจับและ Normalize ให้เป็นแท็กที่ถูกต้องก่อน Unmask
3. **Emergency Fallback:** หากโครงสร้างแท็กพังยับเยินจนไม่สามารถคงความสมบูรณ์ได้ ระบบจะปฏิเสธคำแปลนั้น และส่งเข้าคิว Auto-Repair หรือแจ้ง Error ตามหลักการ *No Skip / 100% Success Guarantee*
