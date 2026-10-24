"""
Filter True Style Mismatches Script
คัดกรองเฉพาะประโยคที่ผิดพลาดจริง (ตัด False Positives เช่น คำว่า 'แฮะ', สัตว์ 'หนู' mouse/rat, และการเรียกคนอื่นว่าหนู)
เพื่อจำแนกกลุ่มประโยคที่ต้องส่งให้ AI ปรับแก้สไตล์และสรรพนาม (Style & Pronoun Calibration)
"""

import os
import sys
import json
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
TLAS_DATA = os.path.join(PROJECT_ROOT, "data", "tlas")
REPORT_PATH = os.path.join(TLAS_DATA, "style_mismatch_report.json")
TRUE_REPORT_PATH = os.path.join(TLAS_DATA, "true_style_mismatches.json")

def is_false_positive(item):
    orig = item.get("original", "").lower()
    thai = item.get("current_thai", "")
    issues = item.get("issues", [])
    spk = item.get("speaker", "")
    gender = item.get("profile_gender", "")
    age = item.get("profile_age", "")

    # 1. กรณี 'ฮะ' แต่จริงๆ คือ 'แฮะ' (เช่น เลยแฮะ, จริงแฮะ, ยากแฮะ)
    if any("masculine particle/pronoun 'ฮะ'" in iss for iss in issues):
        # ถ้ามี 'ฮะ' แต่ติดกับ 'แ' ข้างหน้าเป็น 'แฮะ' ทั้งหมด
        # ค้นหาว่ามีคำว่า 'ฮะ' เดี่ยวๆ หรือลงท้ายประโยคด้วย 'ฮะ' จริงหรือไม่
        ha_matches = re.findall(r'(?<![เแ])ฮะ', thai)
        if not ha_matches:
            # ทั้งหมดคือ แฮะ -> False positive
            return True

    # 2. กรณี 'หนู' แต่ต้นฉบับภาษาอังกฤษคือ mouse หรือ rat (สัตว์)
    if any("หนู" in iss for iss in issues):
        if any(w in orig for w in ["mouse", "rat", "mice"]):
            return True
        # กรณีลูกค้า/ผู้ใหญ่ เรียกผู้หญิงหรือเด็กว่า 'หนู' (เช่น 'หนูจ๋า', 'แม่หนู', 'หนู, เสื้อผ้า')
        # ไม่ใช่การแทนตัวเอง
        if age in ["ADULT", "ELDER"]:
            # ถ้าเป็นคำเรียก เช่น "หนู,", "แม่หนู", "เด็กหนู"
            if re.search(r'แม่หนู|หนู\s*\,|หนู\.\.|หนูจ๊ะ|หนูจ๋า|ยัยหนู', thai):
                # ตรวจว่าไม่มีการแทนตัวเอง เช่น "หนูว่า", "หนูขอ", "ตัวหนูเอง"
                if not re.search(r'หนูว่า|หนูขอ|หนูคิด|หนูเอง|ตัวหนู|หนูจะ', thai):
                    return True

    # 3. กรณี 'จ้ะ' สำหรับคนแก่ใจดี หรือลูกค้าที่หยอกล้อ (เช่น Special Customer, Godmother)
    if spk in ["Godmother"]:
        # Godmother เป็นแม่ทูนหัว ผู้หญิงสูงวัย ใช้ 'จ้ะ' ได้ถูกต้องแล้ว (Profile อาจเป็น FEMALE อยู่แล้ว)
        if gender == "FEMALE":
            return True

    return False

def filter_mismatches():
    if not os.path.exists(REPORT_PATH):
        print(f"[!] Report not found at {REPORT_PATH}")
        return

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[*] Input raw mismatches: {len(data)}")

    true_mismatches = []
    false_positives = 0

    for item in data:
        if is_false_positive(item):
            false_positives += 1
        else:
            true_mismatches.append(item)

    print("="*65)
    print("=== TRUE STYLE & PRONOUN MISMATCHES (AFTER FILTERING FALSE POSITIVES) ===")
    print("="*65)
    print(f"Total Raw Items: {len(data)}")
    print(f"False Positives Filtered (แฮะ, mouse/rat, vocative 'หนู'): {false_positives}")
    print(f"True Mismatches Needing Calibration: {len(true_mismatches)}")
    print("="*65)

    # จัดกลุ่มตามตัวละคร
    from collections import defaultdict
    char_counts = defaultdict(int)
    batch_indices = set()
    for m in true_mismatches:
        char_counts[m["speaker"]] += 1
        batch_indices.add((m["row_idx"] // 15) + 1)

    print("\n[True Mismatches by Character]:")
    for ch, cnt in sorted(char_counts.items(), key=lambda x: x[1], reverse=True)[:25]:
        print(f" - {ch}: {cnt} lines")

    print(f"\nTotal Batches Impacted: {len(batch_indices)} batches (out of 643 batches)")

    with open(TRUE_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(true_mismatches, f, ensure_ascii=False, indent=2)

    print(f"[+] True mismatches saved to: {TRUE_REPORT_PATH}")

if __name__ == "__main__":
    filter_mismatches()
