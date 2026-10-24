import asyncio
import json
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)

class PixelBroadcaster:
    """
    Broadcaster for sending real-time agent status to Pixel Agent Desk.
    """
    def __init__(self, port=47821):
        self.port = port
        self.url = f"http://127.0.0.1:{self.port}/hook"
        self.pid = os.getpid()
        self.session_started = set()
        
    def _send_payload(self, payload):
        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=1.0) as response:
                pass
        except Exception as e:
            # ไม่ต้องแจ้งเตือนพร่ำเพรื่อถ้าแอปไม่ได้เปิดอยู่
            pass

    def _broadcast_async(self, payload):
        # Fire and forget in the current asyncio event loop
        try:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self._send_payload, payload)
        except RuntimeError:
            # ถ้าไม่มี loop ให้รันแบบซิงโครนัส
            self._send_payload(payload)

    def _build_base_payload(self, event_name, session_id, agent_name):
        return {
            "hook_event_name": event_name,
            "session_id": session_id,
            "_pid": self.pid,
            "_timestamp": int(time.time() * 1000),
            "cwd": agent_name, # Pixel Desk ใช้ cwd เป็นชื่อ Display Name ของ Agent
            "agent_type": "Claude Code"
        }

    def start_session(self, session_id: str, agent_name: str):
        if session_id in self.session_started:
            return
        self.session_started.add(session_id)
        
        # ส่ง SessionStart เพื่อสร้างตัวละคร
        payload = self._build_base_payload("SessionStart", session_id, agent_name)
        self._send_payload(payload)
        
        # Pixel Desk จะข้าม PreToolUse ครั้งแรก (มองเป็นการ Init) เราจึงต้องยิงดัมมี่ไป 1 ที
        dummy_payload = self._build_base_payload("PreToolUse", session_id, agent_name)
        dummy_payload["tool_name"] = "init"
        self._send_payload(dummy_payload)

    def end_session(self, session_id: str, agent_name: str):
        if session_id in self.session_started:
            self.session_started.remove(session_id)
        payload = self._build_base_payload("SessionEnd", session_id, agent_name)
        self._broadcast_async(payload)

    def start_typing(self, session_id: str, agent_name: str, tool_name: str = "working", tool_input: dict = None):
        payload = self._build_base_payload("PreToolUse", session_id, agent_name)
        if tool_input and "batch_id" in tool_input and "size" in tool_input:
            tool_name = f"Processing {tool_input['batch_id']} ({tool_input['size']} tokens)"
        payload["tool_name"] = tool_name
        if tool_input:
            payload["tool_input"] = tool_input
        self._broadcast_async(payload)

    def stop_typing(self, session_id: str, agent_name: str):
        payload = self._build_base_payload("TeammateIdle", session_id, agent_name)
        payload["teammate_name"] = agent_name
        self._broadcast_async(payload)
