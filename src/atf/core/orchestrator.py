import logging
import asyncio
from typing import Optional

from .models import TokenState, TranslationBatch
from .event_bus import EventBus
from .state_machine import StateMachine

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """
    ผู้จัดการสายพานการแปล (Orchestrator)
    ทำหน้าที่ผสาน State Machine และ Event Bus เข้าด้วยกัน 
    และเป็นจุดศูนย์กลางให้ Agent เรียกใช้เมื่อทำงานของตัวเองเสร็จสิ้น
    """
    def __init__(self, event_bus: EventBus, state_machine: StateMachine):
        self.bus = event_bus
        self.sm = state_machine
        self.batch_queue = asyncio.Queue()
        self.active_pipeline_batch_ids = set()
        self._queue_worker_task = None
        self.max_concurrent_translations = 1

    def enqueue_batch(self, batch: TranslationBatch):
        """เพิ่ม Batch ลงคิวเพื่อรอคิวการแปล"""
        self.batch_queue.put_nowait(batch)
        
    def start_queue_worker(self):
        """เริ่ม Background Task สำหรับทยอยส่ง Batch ให้ Translator"""
        if not self._queue_worker_task:
            self._queue_worker_task = asyncio.create_task(self._queue_worker())

    async def _queue_worker(self):
        """Loop ดึง Batch จากคิวและส่งให้ EventBus เมื่อ Translator ว่าง"""
        logger.info("[Orchestrator] Queue worker started.")
        while True:
            try:
                # ถ้าจำนวน Batch ที่แปลอยู่เต็มแล้ว ให้รอจนกว่าจะมีที่ว่าง
                while len(self.active_pipeline_batch_ids) >= self.max_concurrent_translations:
                    await asyncio.sleep(1.0)
                    
                batch = await self.batch_queue.get()
                self.active_pipeline_batch_ids.add(batch.batch_id)
                await self.submit_token(batch)
                self.batch_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Orchestrator] Error in queue worker: {e}")
                await asyncio.sleep(1.0)
                
    def is_translator_idle(self) -> bool:
        """ส่งค่า True เมื่อไม่มี Batch ค้างอยู่ในคิวและไม่มี Batch ที่กำลังแปลอยู่"""
        return self.batch_queue.empty() and len(self.active_pipeline_batch_ids) == 0

    async def submit_token(self, batch: TranslationBatch):
        """
        จุดเริ่มต้น: นำ Batch ใหม่เข้าสู่สายพาน
        เปลี่ยนสถานะจาก UNPROCESSED เป็น PENDING และดันเข้า Event Bus
        """
        if batch.current_state == TokenState.UNPROCESSED:
            if self.sm.advance_state(batch, TokenState.PENDING):
                logger.info(f"[Orchestrator] Submitted Batch {batch.batch_id} to PENDING queue.")
                await self.bus.publish(batch)
            else:
                logger.error(f"[Orchestrator] Failed to start Batch {batch.batch_id}. Invalid initial state.")
                self.active_pipeline_batch_ids.discard(batch.batch_id)
        else:
            # ถ้าเข้ามาเป็น PENDING อยู่แล้ว ก็ดันเข้า Bus ได้เลย
            await self.bus.publish(batch)

    async def advance_and_route(self, batch: TranslationBatch, next_state: TokenState):
        """
        ฟังก์ชันหลักที่ Agent จะเรียกใช้เมื่อ "ทำงานของตัวเองเสร็จแล้ว"
        Orchestrator จะเช็คกฎกับ State Machine แล้วประกาศ (Publish) สู่สถานะถัดไป
        """
        current = batch.current_state
        if self.sm.advance_state(batch, next_state):
            logger.info(f"[Orchestrator] Batch {batch.batch_id} advanced: {current.value} -> {next_state.value}")
            
            # เมื่อ Batch จบการทำงานในลูปหรือมี Error ค่อยคืนคิวให้ Pipeline
            if next_state in (TokenState.READY_TO_EXPORT, TokenState.ERROR_CRITICAL):
                self.active_pipeline_batch_ids.discard(batch.batch_id)
                
            await self.bus.publish(batch)
        else:
            logger.error(
                f"[Orchestrator] ILLEGAL TRANSITION for Batch {batch.batch_id}: "
                f"Cannot move from {current.value} to {next_state.value}"
            )

    async def trigger_repair_loop(self, batch: TranslationBatch, target_agent_state: TokenState):
        """
        ฟังก์ชันฉุกเฉินสำหรับ QA Agent หรือ Validator เมื่อตรวจพบข้อผิดพลาด
        เพื่อตีกลับประโยคไปยัง Agent ก่อนหน้า (Repair Loop)
        """
        logger.warning(
            f"[Orchestrator] REPAIR LOOP triggered for Batch {batch.batch_id}. "
            f"Routing back to {target_agent_state.value}."
        )
        
        current = batch.current_state
        
        # ใช้ State Machine เช็คว่าวนลูปเกินขีดจำกัด (Max Retries) หรือยัง
        if self.sm.trigger_repair_loop(batch, target_agent_state):
            if batch.current_state == TokenState.ERROR_CRITICAL:
                logger.error(f"[Orchestrator] Batch {batch.batch_id} hit MAX RETRIES and is now ERROR_CRITICAL.")
                self.active_pipeline_batch_ids.discard(batch.batch_id)
            
            # ไม่ว่าจะกลับไปสถานะซ่อมแซม หรือไปจบที่ ERROR_CRITICAL ก็ต้องดันเข้า Bus
            await self.bus.publish(batch)
        else:
            logger.error(f"[Orchestrator] Failed to trigger repair loop for Batch {batch.batch_id}.")

    async def shutdown(self):
        """ปิดระบบสายพาน"""
        logger.info("[Orchestrator] Shutting down pipeline...")
        if self._queue_worker_task:
            self._queue_worker_task.cancel()
        await self.bus.stop()