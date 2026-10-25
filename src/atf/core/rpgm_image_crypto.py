#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPG Maker MV/MZ Image Crypto Engine (ADR-027 & SAD-015 Compliant)
โมดูลถอดรหัสและเข้ารหัสไฟล์ภาพ RPG Maker (.rpgmvp <-> .png)
รองรับการตรวจจับ Encryption Key จาก www/data/System.json อัตโนมัติ
"""

import os
import sys
import json
import glob
from typing import Optional, List, Tuple, Union

# Header 16 bytes มาตรฐานของ RPG Maker MV (.rpgmvp)
# 52 50 47 4D 56 00 00 00 00 03 01 00 00 00 00 00
RPGM_HEADER: bytes = bytes([0x52, 0x50, 0x47, 0x4D, 0x56, 0x00, 0x00, 0x00, 0x00, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
PNG_MAGIC: bytes = b"\x89PNG\r\n\x1a\n"


class RPGMImageCrypto:
    """
    คลาสจัดการการถอดรหัสและเข้ารหัสไฟล์ภาพ RPG Maker MV/MZ
    """
    @staticmethod
    def extract_key_from_system_json(system_json_path: str) -> Optional[bytes]:
        """ดึง Encryption Key 16 bytes จากไฟล์ System.json"""
        if not os.path.exists(system_json_path):
            return None
        try:
            with open(system_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            hex_key = data.get("encryptionKey", "").strip()
            if hex_key and len(hex_key) == 32:
                return bytes.fromhex(hex_key)
        except Exception:
            pass
        return None

    @classmethod
    def decrypt_bytes(cls, encrypted_data: bytes, key: bytes) -> bytes:
        """
        ถอดรหัสไบต์ของไฟล์ .rpgmvp เป็นไฟล์ .png ดั้งเดิม
        - ไบต์ 0-15: Header ของ RPG Maker (ตัดทิ้ง)
        - ไบต์ 16-31: ส่วนหัวของ PNG ที่ถูก XOR ด้วย Key
        - ไบต์ 32 เป็นต้นไป: ไบต์ของ PNG แท้ที่ไม่ถูกเข้ารหัส
        """
        if len(encrypted_data) < 32:
            raise ValueError("File size too small to be a valid .rpgmvp file")

        # ตรวจสอบ Header
        if encrypted_data[:16] != RPGM_HEADER:
            # บางเกมอาจมี Header ต่างออกไปเล็กน้อย แต่ยังใช้ไบต์ 16-31 เข้ารหัส
            pass

        key_len = len(key)
        decrypted_header = bytearray(16)
        for i in range(16):
            decrypted_header[i] = encrypted_data[16 + i] ^ key[i % key_len]

        # ประกอบเป็นไฟล์ PNG
        png_data = bytes(decrypted_header) + encrypted_data[32:]
        return png_data

    @classmethod
    def encrypt_bytes(cls, png_data: bytes, key: bytes) -> bytes:
        """
        เข้ารหัสไบต์ของไฟล์ .png กลับเป็น .rpgmvp
        - ใส่ Header 16 ไบต์ของ RPG Maker
        - นำ 16 ไบต์แรกของ PNG ไป XOR ด้วย Key
        - ต่อด้วยไบต์ที่เหลือของ PNG ตั้งแต่ไบต์ที่ 16 เป็นต้นไป
        """
        if len(png_data) < 16:
            raise ValueError("File size too small to be a valid PNG")

        key_len = len(key)
        encrypted_header = bytearray(16)
        for i in range(16):
            encrypted_header[i] = png_data[i] ^ key[i % key_len]

        rpgmvp_data = RPGM_HEADER + bytes(encrypted_header) + png_data[16:]
        return rpgmvp_data

    @classmethod
    def decrypt_file(cls, input_path: str, output_path: str, key: bytes) -> bool:
        """ถอดรหัสไฟล์ .rpgmvp บันทึกเป็น .png"""
        try:
            with open(input_path, "rb") as f:
                enc_data = f.read()
            png_data = cls.decrypt_bytes(enc_data, key)
            
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(png_data)
            return True
        except Exception as e:
            print(f"❌ Error decrypting {input_path}: {e}")
            return False

    @classmethod
    def encrypt_file(cls, input_path: str, output_path: str, key: bytes) -> bool:
        """เข้ารหัสไฟล์ .png บันทึกเป็น .rpgmvp"""
        try:
            with open(input_path, "rb") as f:
                png_data = f.read()
            enc_data = cls.encrypt_bytes(png_data, key)

            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(enc_data)
            return True
        except Exception as e:
            print(f"❌ Error encrypting {input_path}: {e}")
            return False
