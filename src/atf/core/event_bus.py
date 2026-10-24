import asyncio
from typing import Callable, Dict, List, Awaitable
import logging

from .models import TokenState, TranslationBatch

# ตั้งค่า Logger พื้นฐาน
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# กำหนด Type Alias สำหรับ Callback Function ที่ต้องเป็น Async
EventHandler = Callable[[TranslationBatch], Awaitable[None]]

class EventBus:
    """
    ระบบสายพานส่งข้อมูลแบบ Asynchronous (Pub/Sub)
    รับผิดชอบในการกระจาย TranslationBatch ไปยัง Agent ที่ถูกต้อง
    """
    def __init__(self):
        # เก็บรายชื่อฟังก์ชัน (Subscribers) ที่รอรับฟังแต่ละ State
        self._subscribers: Dict[TokenState, List[EventHandler]] = {
            state: [] for state in TokenState
        }
        # คิวสำหรับเก็บ Event ที่กำลังรอประมวลผล
        self._queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        self._worker_task: asyncio.Task | None = None

    def subscribe(self, state: TokenState, handler: EventHandler):
        """ให้ Agent มาลงทะเบียนรอฟัง State ที่ตัวเองสนใจ"""
        if handler not in self._subscribers[state]:
            self._subscribers[state].append(handler)
            logger.info(f"Subscribed handler {handler.__name__} to state {state.value}")

    async def publish(self, batch: TranslationBatch):
        """ดัน Batch เข้าสู่ระบบสายพาน (Queue)"""
        await self._queue.put(batch)
        logger.debug(f"Published Batch {batch.batch_id} with state {batch.current_state.value}")

    async def _worker(self):
        """คนงาน (Worker) ที่คอยหยิบ Batch ออกจากคิวมาส่งต่อให้ Subscriber"""
        self._is_running = True
        logger.info("EventBus worker started.")
        
        while self._is_running:
            batch: TranslationBatch = await self._queue.get()
            current_state = batch.current_state
            
            handlers = self._subscribers.get(current_state, [])
            
            if not handlers:
                logger.warning(f"No subscribers found for state {current_state.value} (Batch: {batch.batch_id})")
            
            # เรียกใช้งาน Handler ทั้งหมดที่รอฟัง State นี้แบบขนาน (Concurrent) และปล่อยให้ทำงานแบบ Fire-and-forget
            # ไม่ใช้ await asyncio.gather() เพื่อให้ Worker ไปหยิบ Batch ต่อไปจากคิวได้ทันที (Parallel Processing)
            for handler in handlers:
                asyncio.create_task(handler(batch))
                
            self._queue.task_done()

    async def start(self):
        """เปิดสวิตช์เริ่มรันสายพาน"""
        if not self._is_running:
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        """ปิดสวิตช์และรอให้งานในคิวเสร็จสิ้น"""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                logger.info("EventBus worker stopped.")