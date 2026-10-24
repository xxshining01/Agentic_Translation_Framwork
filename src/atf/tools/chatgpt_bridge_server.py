"""
ChatGPT Web Bridge Server for ATF (Agentic Translation Framework)
ทำหน้าที่เป็น Local Bridge Server จำลอง OpenAI-compatible API
รับคำสั่งจาก ATF แล้วส่งต่อให้ Tampermonkey Userscript บนหน้าเว็บ ChatGPT (chatgpt.com)
"""

import json
import time
import uuid
import queue
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChatGPTBridge")

# คิวงานและที่เก็บผลลัพธ์
TASK_QUEUE = queue.Queue()
ACTIVE_TASKS = {}
CLIENT_CONNECTED = {"last_seen": 0, "active": False}

class BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # ปิด access log เริ่มต้นของ BaseHTTPRequestHandler เพื่อไม่ให้รกหน้าจอ
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/bridge/status":
            # ตรวจสอบสถานะการเชื่อมต่อของ Userscript
            now = time.time()
            is_active = (now - CLIENT_CONNECTED["last_seen"]) < 10.0
            data = {
                "status": "online",
                "userscript_connected": is_active,
                "seconds_since_ping": round(now - CLIENT_CONNECTED["last_seen"], 1) if CLIENT_CONNECTED["last_seen"] > 0 else -1,
                "pending_tasks": TASK_QUEUE.qsize()
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path == "/bridge/poll":
            # Tampermonkey Userscript มา Polling หางานใหม่
            CLIENT_CONNECTED["last_seen"] = time.time()
            CLIENT_CONNECTED["active"] = True

            try:
                # ลองดึงงานจากคิว (รอไม่เกิน 2.5 วินาที เพื่อให้เป็น Long-polling เบาๆ)
                task = TASK_QUEUE.get(timeout=2.5)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"has_task": True, "task": task}).encode("utf-8"))
            except queue.Empty:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"has_task": False}).encode("utf-8"))
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/bridge/ping":
            # Userscript ping มาบอกว่ายังอยู่
            CLIENT_CONNECTED["last_seen"] = time.time()
            CLIENT_CONNECTED["active"] = True
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        elif path == "/bridge/result":
            # Userscript ส่งคำตอบที่สกัดจากหน้าเว็บกลับมา
            CLIENT_CONNECTED["last_seen"] = time.time()
            task_id = payload.get("task_id")
            content = payload.get("content", "")
            status = payload.get("status", "done")
            error_msg = payload.get("error")
            chat_limit_reached = payload.get("chat_limit_reached", False)

            if task_id in ACTIVE_TASKS:
                task_obj = ACTIVE_TASKS[task_id]
                task_obj["response"] = {
                    "status": status,
                    "content": content,
                    "error": error_msg,
                    "chat_limit_reached": chat_limit_reached
                }
                task_obj["event"].set()
                if status == "error":
                    logger.error(f"Task {task_id} FAILED from ChatGPT Web! Error: {error_msg}")
                else:
                    logger.info(f"Task {task_id} completed from ChatGPT Web! (Limit detected: {chat_limit_reached})")
            
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"received"}')
            return

        elif path in ("/bridge/reset", "/v1/bridge/reset"):
            # เคลียร์คิวงานเก่าที่ตกค้างทั้งหมด
            cleared_count = 0
            while not TASK_QUEUE.empty():
                try:
                    TASK_QUEUE.get_nowait()
                    cleared_count += 1
                except queue.Empty:
                    break

            for tid, tobj in list(ACTIVE_TASKS.items()):
                tobj["event"].set()
                if tid in ACTIVE_TASKS:
                    del ACTIVE_TASKS[tid]

            logger.info(f"Bridge State Reset: Cleared {cleared_count} stale queue tasks.")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "cleared_tasks": cleared_count}).encode("utf-8"))
            return

        elif path in ("/v1/bridge/new_chat", "/bridge/new_chat"):
            # สั่งให้ Userscript บนหน้าเว็บเปิด New Chat
            task_id = str(uuid.uuid4())
            task_item = {
                "task_id": task_id,
                "action": "new_chat",
                "created_at": time.time()
            }
            completion_event = threading.Event()
            ACTIVE_TASKS[task_id] = {
                "event": completion_event,
                "response": None
            }
            logger.info(f"Triggering New Chat action on ChatGPT Web UI (Task {task_id})...")
            TASK_QUEUE.put(task_item)

            while not completion_event.wait(timeout=5.0):
                if (time.time() - CLIENT_CONNECTED["last_seen"]) > 30.0:
                    logger.warning("Userscript seems disconnected or inactive on chatgpt.com!")

            res_data = ACTIVE_TASKS[task_id]["response"] if task_id in ACTIVE_TASKS else {"status": "done", "content": "New chat initialized"}
            if task_id in ACTIVE_TASKS:
                del ACTIVE_TASKS[task_id]

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res_data).encode("utf-8"))
            return

        elif path in ("/v1/bridge/refresh", "/bridge/refresh"):
            # สั่งให้ Userscript บนหน้าเว็บทำการรีเฟรชหน้า (Reload Page) เพื่อเคลียร์ Cooldown / DOM
            task_id = str(uuid.uuid4())
            task_item = {
                "task_id": task_id,
                "action": "refresh_page",
                "created_at": time.time()
            }
            completion_event = threading.Event()
            ACTIVE_TASKS[task_id] = {
                "event": completion_event,
                "response": None
            }
            logger.info(f"Triggering Page Refresh on ChatGPT Web UI (Task {task_id})...")
            TASK_QUEUE.put(task_item)

            completion_event.wait(timeout=5.0)
            if task_id in ACTIVE_TASKS:
                del ACTIVE_TASKS[task_id]

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"refresh_triggered"}')
            return

        elif path in ("/v1/bridge/probe", "/bridge/probe"):
            # ทดสอบสถานะว่า ChatGPT พร้อมส่งหรือติด Rate Limit (Watchdog Sentinel Probe)
            task_id = str(uuid.uuid4())
            task_item = {
                "task_id": task_id,
                "action": "probe_status",
                "created_at": time.time()
            }
            completion_event = threading.Event()
            ACTIVE_TASKS[task_id] = {
                "event": completion_event,
                "response": None
            }
            logger.info(f"Probing ChatGPT Web status & rate limit (Task {task_id})...")
            TASK_QUEUE.put(task_item)

            if not completion_event.wait(timeout=8.0):
                logger.warning("Probe task wait timed out!")

            resp_val = ACTIVE_TASKS[task_id].get("response") if task_id in ACTIVE_TASKS else None
            res_data = resp_val if resp_val is not None else {
                "status": "done", "can_send": False, "is_rate_limited": True, "reason": "Userscript probe timed out"
            }
            if task_id in ACTIVE_TASKS:
                del ACTIVE_TASKS[task_id]

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res_data).encode("utf-8"))
            return

        elif path in ("/v1/chat/completions", "/chat/completions"):
            # OpenAI-compatible API Endpoint ที่ ATF เรียกใช้งาน
            # แยก prompt จาก messages
            messages = payload.get("messages", [])
            model = payload.get("model", "chatgpt-web")
            
            system_prompts = []
            user_prompts = []
            
            for m in messages:
                role = m.get("role", "")
                text = m.get("content", "")
                if role == "system":
                    system_prompts.append(text)
                elif role == "user":
                    user_prompts.append(text)
                elif role == "assistant":
                    user_prompts.append(f"[Previous Assistant]: {text}")

            # รวม Prompt ให้เหมาะสมสำหรับส่งเข้า Web UI
            full_prompt_parts = []
            if system_prompts:
                full_prompt_parts.append("### SYSTEM INSTRUCTIONS:\n" + "\n\n".join(system_prompts))
            if user_prompts:
                full_prompt_parts.append("### TASK INPUT:\n" + "\n\n".join(user_prompts))
            
            full_prompt = "\n\n---\n\n".join(full_prompt_parts) if full_prompt_parts else "Hello"

            task_id = str(uuid.uuid4())
            task_item = {
                "task_id": task_id,
                "prompt": full_prompt,
                "model": model,
                "created_at": time.time()
            }

            completion_event = threading.Event()
            ACTIVE_TASKS[task_id] = {
                "event": completion_event,
                "response": None
            }

            logger.info(f"Enqueuing task {task_id} (Prompt size: {len(full_prompt)} chars). Waiting for Userscript...")
            TASK_QUEUE.put(task_item)

            # No Timeout Principle: รอจนกว่า Userscript จะส่งผลลัพธ์กลับมา
            while not completion_event.wait(timeout=5.0):
                # ตรวจสอบว่า Userscript ยังต่ออยู่หรือไม่
                if (time.time() - CLIENT_CONNECTED["last_seen"]) > 30.0:
                    logger.warning("Userscript seems disconnected or inactive on chatgpt.com!")

            res_data = ACTIVE_TASKS[task_id]["response"] if task_id in ACTIVE_TASKS else None
            if task_id in ACTIVE_TASKS:
                del ACTIVE_TASKS[task_id]

            if not res_data or res_data.get("status") in ("error", "rate_limited"):
                is_rate_limited = (res_data.get("status") == "rate_limited") or (res_data.get("is_rate_limited") is True) if res_data else False
                wait_minutes = res_data.get("wait_minutes") if res_data else None
                raw_err = res_data.get("error") if res_data else "Bridge Task was cancelled or lost."
                err_msg = raw_err if (raw_err and str(raw_err).strip()) else "ChatGPT Web UI returned an empty or failed response."
                
                # ตรวจจับคีย์เวิร์ด Rate Limit ในข้อความ Error อีกชั้น
                if any(kw in str(err_msg).lower() for kw in [
                    "try again after", "try again in", "ลองอีกครั้งใน", "เรากำลังตรวจสอบ", "too many requests",
                    "rate limit", "usage cap", "usage limit", "คุณถึงขีดจำกัดแล้ว",
                    "send button blocked", "send button disabled", "blocked", "silent usage limit active", "cooldown"
                ]):
                    is_rate_limited = True

                http_code = 429 if is_rate_limited else 500
                self.send_response(http_code)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err_resp = {
                    "error": {
                        "message": err_msg,
                        "type": "rate_limit_error" if is_rate_limited else "server_error",
                        "wait_minutes": wait_minutes
                    }
                }
                self.wfile.write(json.dumps(err_resp).encode("utf-8"))
                return

            # ตอบกลับในรูปแบบ OpenAI Chat Completion มาตรฐาน
            result_content = res_data.get("content", "")
            chat_limit_reached = res_data.get("chat_limit_reached", False)
            openai_format = {
                "id": f"chatcmpl-{task_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "chat_limit_reached": chat_limit_reached,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": result_content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(full_prompt) // 4,
                    "completion_tokens": len(result_content) // 4,
                    "total_tokens": (len(full_prompt) + len(result_content)) // 4
                }
            }

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(openai_format, ensure_ascii=False).encode("utf-8"))
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()


def run_server(host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), BridgeHTTPRequestHandler)
    server.daemon_threads = True
    print("=" * 60)
    print(f"🚀 ATF ChatGPT Web Bridge Server running at http://{host}:{port}")
    print(f"👉 API Endpoint: http://{host}:{port}/v1/chat/completions")
    print(f"👉 Bridge Status: http://{host}:{port}/bridge/status")
    print("=" * 60)
    print("Waiting for Tampermonkey Userscript on chatgpt.com to connect...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Bridge Server...")
        server.server_close()


if __name__ == "__main__":
    run_server()
