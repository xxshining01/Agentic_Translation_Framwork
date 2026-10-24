import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List
from litellm import acompletion

from ..core.models import TranslationBatch

logger = logging.getLogger(__name__)

trace_logger = logging.getLogger("llm_trace")
trace_logger.setLevel(logging.INFO)
if not trace_logger.handlers:
    th = logging.FileHandler("llm_trace.log", encoding="utf-8")
    th.setFormatter(logging.Formatter('%(asctime)s\n%(message)s'))
    trace_logger.addHandler(th)

class BaseAgent(ABC):
    """
    คลาสแม่ (Abstract Base Class) สำหรับ AI Agent ทุกตัว
    """
    
    # Semaphore แบบแยกตามชื่อ Model เพื่อรองรับ True Concurrency
    _model_semaphores = {}
    
    @classmethod
    def get_model_semaphore(cls, model_name: str) -> asyncio.Semaphore:
        if model_name not in cls._model_semaphores:
            cls._model_semaphores[model_name] = asyncio.Semaphore(1)
        return cls._model_semaphores[model_name]

    # กฎเหล็กที่ Agent ทุกตัวต้องเห็น (อิงจาก SDD-003)
    SAFETY_RULE = (
        "SAFETY RULE: If you see any variables in brackets (e.g., [var], {var}), "
        "HTML tags, quotes, or system commands, YOU MUST PRESERVE THEM EXACTLY AS THEY ARE. "
        "Do not translate them. Do not remove them. Do not change their casing. "
        "CRITICAL: Escape characters and control codes like \\n, \\., \\|, \\f, \\C[X], \\>, \\< MUST remain exactly as they appear in the original text. "
        "DO NOT drop the backslash. Treat these codes as transparent wrappers. Translate the human text around them while keeping the codes in the exact same relative positions. "
        "Examples:\n"
        "- '\\fbStop' -> '\\fbหยุดนะ'\n"
        "- '\"Stop\"' -> '\"หยุดนะ\"'\n"
        "- '<color=red>Fire</color>' -> '<color=red>ไฟ</color>'\n"
        "Do not render them as actual newlines or formatting in your response!"
    )

    def __init__(self, model_name: str = "chatgpt-web", agent_name: str = "Unknown Agent", api_base: str = "http://127.0.0.1:8765/v1"):
        """สามารถกำหนด Model และ API Endpoint ที่แตกต่างกันให้ Agent แต่ละตัวได้"""
        self.model_name = model_name
        self.agent_name = agent_name
        self.api_base = api_base
        self.current_task = "IDLE"
        self.broadcaster = None
        self.session_id = None
        self.human_name = None

    def set_broadcaster(self, broadcaster, session_id: str, human_name: str):
        self.broadcaster = broadcaster
        self.session_id = session_id
        self.human_name = human_name

    def set_status(self, text: str):
        self.current_task = text
        if self.broadcaster and self.session_id:
            self.broadcaster.start_typing(self.session_id, self.human_name or self.agent_name, tool_name=text)

    @abstractmethod
    async def process(self, batch: TranslationBatch) -> bool:
        """
        Method หลักที่ Agent ทุกตัว (Translator, Editor, QA, ฯลฯ) ต้องนำไปเขียนลอจิกของตัวเอง
        รับ Batch เข้ามา, ประกอบ Prompt, ยิง API, และนำผลลัพธ์ไปอัปเดตใน Tokens ใน Batch
        
        Returns:
            bool: True ถ้าทำงานสำเร็จ (ถึงแม้จะมี error ในบาง row แต่ก็ถือว่า process สำเร็จ), False ถ้ามี Error ร้ายแรง
        """
        pass

    async def call_llm(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        require_json: bool = False,
        skip_safety_rule: bool = False,
        max_tokens: int = None
    ) -> Optional[str]:
        """
        ฟังก์ชันตัวกลางสำหรับยิง API ไปหา LLM (ChatGPT Web Bridge หรือ Local LLM)
        """
        import httpx
        
        if not skip_safety_rule:
            final_system_prompt = f"{system_prompt}\n\n{self.SAFETY_RULE}"
        else:
            final_system_prompt = system_prompt
        
        if require_json:
            # ใช้คำสั่งเชิงบวก (Positive Constraint) ให้ส่งผลลัพธ์เป็น JSON Object เท่านั้น
            final_system_prompt += (
                "\n\nOutput a valid JSON object ONLY. "
                "The JSON object must contain a list of your results. "
                "End your response immediately after the closing bracket '}'."
            )
        try:
            actual_model = self.model_name
            semaphore = self.get_model_semaphore(actual_model)
            # เปลี่ยนมาใช้รูปแบบมาตรฐาน (OpenAI Compatible)
            payload = {
                "model": actual_model,
                "messages": [
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            
            logger.debug(f"Waiting for semaphore for model {actual_model}...")
            self.set_status(f"Waiting for LLM ({actual_model})...")
            async with semaphore:
                logger.debug(f"Calling LLM API ({self.api_base}) with model {actual_model}. Require JSON: {require_json}")
                self.set_status(f"Generating content with {actual_model}...")
                
                api_url = f"{self.api_base}/chat/completions"
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        api_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=None
                    )
                    response.raise_for_status()
                
                # สมมติว่า Custom API ของ LM Studio ตอบกลับมาแบบนี้
                # แต่เนื่องจากไม่ได้บอกโครงสร้าง response มา ขอตั้งสมมติฐานว่าตอบมาที่ 'response' หรือ 'content'
                data = response.json()
                
                # ลองดึงจากรูปแบบต่างๆ ที่เป็นไปได้
                if "output" in data and isinstance(data["output"], list):
                    # รูปแบบของโมเดล Gemma/Reasoning ใน LM Studio
                    # มักจะมีหลาย block เช่น type: reasoning และ type: message
                    message_content = ""
                    for block in data["output"]:
                        if isinstance(block, dict) and block.get("type") == "message":
                            message_content = block.get("content", "")
                            break
                    if not message_content and len(data["output"]) > 0:
                        # Fallback ถ้าไม่มี type message ให้เอา block สุดท้าย
                        last_block = data["output"][-1]
                        message_content = last_block.get("content", str(last_block)) if isinstance(last_block, dict) else str(last_block)
                    result_content = message_content
                elif "response" in data:
                    result_content = data["response"]
                elif "content" in data:
                    result_content = data["content"]
                elif "choices" in data and len(data["choices"]) > 0:
                     # เผื่อว่าตอบกลับมาเป็น OpenAI format แม้จะส่งไปคนละแบบ
                     result_content = data["choices"][0].get("message", {}).get("content", "")
                else:
                    # ถ้าไม่ใช่ ก็คือค่าทั้งหมดถูกส่งมาเป็น string (fallback)
                    result_content = str(data)
                
                trace_logger.info(f"{'='*50}\nMODEL: {actual_model}\n{'='*50}\nSYSTEM PROMPT:\n{final_system_prompt}\n{'-'*50}\nUSER PROMPT:\n{user_prompt}\n{'-'*50}\nRESPONSE:\n{result_content}\n{'='*50}\n")
                
                return result_content

                
        except httpx.TimeoutException:
            logger.error(f"LM Studio API Call timed out after 600s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error calling LLM: {e}. Response text: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None

    def parse_json_response(self, text: str) -> Optional[dict]:
        """พยายาม Parse JSON จาก Response ของ LLM (รองรับกรณีที่มี Markdown Code Blocks ครอบอยู่)"""
        import json
        import re
        import json_repair
        
        if not text:
            return None
            
        def sanitize_json(s: str) -> str:
            # ซ่อมแซม Invalid \escape ที่ LLM มักจะลืม double backslash
            # เช่น \. กลายเป็น \\. หรือ \C กลายเป็น \\C
            # อนุญาตเฉพาะ \n, \r, \t, \b, \f, \", \\, \/, \uXXXX
            return re.sub(r'(?<!\\)((?:\\\\)*)\\([^nrtbf"\\/u])', r'\1\\\\\2', s)
            
        # ลบ <think>...</think> ออกให้หมดก่อน
        text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
        
        # 1. ค้นหา markdown blocks
        # หาแบบระบุ ```json หรือ ```JSON หรือไม่มีระบุก็ได้
        blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', text, re.IGNORECASE)
        
        candidates = blocks[:]
        
        # 2. ถ้าไม่เจอจาก markdown หรือเผื่อต้องการ fallback ลองใช้ regex หา array หรือ object
        if not candidates:
            # หา [ { ... } ]
            match_array = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', text)
            if match_array:
                candidates.append(match_array.group(1))
                
            # หา { "key": ... } หรือ { 'key': ... }
            match_obj = re.search(r'(\{\s*(?:\"|\')[\s\S]*\}\s*)', text)
            if match_obj:
                candidates.append(match_obj.group(1))
                
        # ลอง parse candidates จากหลังไปหน้า (ให้ความสำคัญกับบล็อกสุดท้ายที่เป็นคำตอบจริง)
        for candidate in reversed(candidates):
            sanitized = sanitize_json(candidate)
            try:
                parsed = json_repair.loads(sanitized)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except Exception:
                pass
                
        # 3. ท่าไม้ตายสุดท้าย: ลอง parse text ตรงๆ ด้วย json_repair
        sanitized_text = sanitize_json(text)
        try:
            parsed = json_repair.loads(sanitized_text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass
            
        logger.error(f"Could not extract JSON from text: {text[:150]}...")
        return None

    async def execute_with_retry(self, system_prompt: str, user_prompt: str, expected_ids: List[str], max_retries: int = 3) -> Optional[List[dict]]:
        """
        ระบบ Self-Healing:
        เรียก LLM พร้อมตรวจสอบความถูกต้องของ JSON และตรวจสอบว่าลืมประโยคใดไปหรือไม่
        หากพบข้อผิดพลาด จะสั่งให้ LLM แก้ตัวใหม่จนกว่าจะครบโควต้า (max_retries)
        """

        current_user_prompt = user_prompt
        
        for attempt in range(max_retries):
            self.set_status(f"Calling LLM... (Attempt {attempt+1}/{max_retries})")
            result_text = await self.call_llm(system_prompt, current_user_prompt, require_json=True)
            if not result_text:
                logger.warning(f"[{self.agent_name}] Attempt {attempt+1}/{max_retries} failed (Empty Response). Retrying...")
                continue
                
            json_data = self.parse_json_response(result_text)
            if not json_data:
                logger.warning(f"[{self.agent_name}] Attempt {attempt+1}/{max_retries} failed (Invalid JSON). Retrying...")
                current_user_prompt += "\n\nERROR: Your previous response was not recognized as a valid JSON object. Please output a valid JSON object ONLY and end your response immediately after '}'."
                continue
                
            items = json_data if isinstance(json_data, list) else json_data.get("results", [])
            if not items and isinstance(json_data, dict):
                for k, v in json_data.items():
                    if isinstance(v, list):
                        items = v
                        break
            
            if not isinstance(items, list):
                items = [json_data] if isinstance(json_data, dict) else []
                        
            items = [x for x in items if isinstance(x, dict)]
                        
            received_ids = {str(item.get("id") or item.get("token_id")) for item in items if (item.get("id") or item.get("token_id"))}
            expected = {str(eid) for eid in expected_ids}
            missing = expected - received_ids
            
            if missing:
                logger.warning(f"[{self.agent_name}] Attempt {attempt+1}/{max_retries} failed (Missing IDs: {missing}). Retrying...")
                current_user_prompt += f"\n\nERROR: You missed the following IDs: {missing}. Please ensure your JSON object contains the results for ALL the requested IDs."
                continue
                
            # หากสมบูรณ์ 100% ให้คืนค่า
            return items
            
        logger.error(f"[{self.agent_name}] Exhausted all {max_retries} retries. Batch failed.")
        return None