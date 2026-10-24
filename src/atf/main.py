import asyncio
import logging
import os
from typing import List, Dict

# นำเข้าโมดูลทั้งหมดที่เราสร้างไว้ (ปรับชื่อไฟล์ตามที่คุณอัปโหลดไว้)
from .core.models import TranslationToken, TokenState, TranslationBatch
from .core.state_machine import StateMachine
from .core.event_bus import EventBus
from .core.orchestrator import PipelineOrchestrator

from .memory.context_engine import ContextEngine
from .parsers.csv_excel_spreadsheet_parser import CSVParser
from .parsers.validator import SyntaxValidator

from .agents.translator import TranslatorAgent
from .agents.editor import EditorAgent
from .agents.qa import QAAgent
from .agents.timing import TimingAgent
from .agents.summarizer import SummarizerAgent
from .agents.linguistic_analyzer import LinguisticAnalyzerAgent
from .core.mapping_engine import MappingEngine

from .ui.pixel_broadcaster import PixelBroadcaster

# ตั้งค่า Logging ให้เห็นการทำงานลงไฟล์ (เพื่อไม่ให้กวน UI ของ rich)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [%(name)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("atf.log", encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger(__name__)

class ATFApplication:
    """
    คลาสหลักสำหรับรัน Agentic Translation Framework
    ทำหน้าที่ผูก Event Listeners และควบคุมวงจรชีวิตของโปรแกรม
    """
    def __init__(self):
        # 1. สร้าง Core Components
        self.state_machine = StateMachine()
        self.event_bus = EventBus()
        self.orchestrator = PipelineOrchestrator(self.event_bus, self.state_machine)
        self.context_engine = ContextEngine()
        
        # Inject orchestrator to all agents for queue status checks
        from .agents.base import BaseAgent
        BaseAgent.orchestrator = self.orchestrator
        
        # 2. สร้าง AI Agents และ Validator
        # แบ่งโหลดงาน: โมเดลเดียววิ่งทุกงานทีละขั้นตอน
        self.translator = TranslatorAgent(model_name="gemma-4-12b-it-qat")
        self.editor = EditorAgent(model_name="gemma-4-12b-it-qat")
        self.qa = QAAgent(model_name="gemma-4-12b-it-qat")
        self.timing = TimingAgent(model_name="gemma-4-12b-it-qat")
        self.summarizer = SummarizerAgent(model_name="gemma-4-12b-it-qat")
        self.analyzer = LinguisticAnalyzerAgent(model_name="gemma-4-12b-it-qat")
        self.mapping_engine = MappingEngine()
        self.validator = SyntaxValidator()
        self.parser = CSVParser()
        self.broadcaster = PixelBroadcaster()
        
        from .agents.logger import LoggerAgent
        self.logger_agent = LoggerAgent()
        
        # สถิติสำหรับ Summary
        self.stats = {
            "summarizer": {"scopes_analyzed": 0, "errors": 0},
            "translator": {"batches_received": 0, "batches_completed": 0, "batches_failed": 0},
            "editor": {"batches_received": 0, "batches_completed": 0, "batches_failed": 0, "repair_loops": 0},
            "qa": {"batches_received": 0, "batches_completed": 0, "batches_failed": 0},
            "timing": {"batches_received": 0, "batches_completed": 0, "batches_failed": 0},
            "validator": {"batches_received": 0, "batches_completed": 0, "batches_failed": 0, "repair_loops": 0}
        }
        
        # Link Broadcaster to agents for real-time status reporting
        self.translator.set_broadcaster(self.broadcaster, "translator_1", "Alice")
        self.editor.set_broadcaster(self.broadcaster, "editor_1", "Bob")
        self.qa.set_broadcaster(self.broadcaster, "qa_1", "Charlie")
        self.timing.set_broadcaster(self.broadcaster, "timing_1", "Diana")
        self.summarizer.set_broadcaster(self.broadcaster, "summarizer_1", "Frank")
        self.analyzer.set_broadcaster(self.broadcaster, "analyzer_1", "Grace")
        
        self.export_lock = asyncio.Lock()
        self.output_file = "" # เก็บไว้เพื่อให้ handler เรียกใช้ได้
        
        # ตัวแปรสำหรับเก็บ Token และ Batch ที่ผ่านเข้าระบบทั้งหมด
        self.already_translated_tokens: List[TranslationToken] = []
        self.processed_batches: List[TranslationBatch] = []
        
        # ตัวแปรสำหรับจัดการ Context Scopes
        self.scope_locks: Dict[str, asyncio.Lock] = {}
        self.context_chunks: Dict[str, List[TranslationToken]] = {}
        
        # ผูก Event (Wiring)
        self._subscribe_events()

    def _subscribe_events(self):
        """
        ลงทะเบียนว่า Agent ตัวไหน ต้องรอรับฟัง State อะไร
        """
        
        # 1. PENDING -> เตรียม Context -> ส่งให้ TRANSLATING หรือ EDITING
        async def handle_pending(batch: TranslationBatch):
            # ตรวจสอบและสร้าง Context Scope ถ้าจำเป็น
            if batch.batch_type == "HEAVY":
                group_id = batch.tokens[0].metadata.get("context_group_id")
                if group_id:
                    if group_id not in self.scope_locks:
                        self.scope_locks[group_id] = asyncio.Lock()
                    
                    async with self.scope_locks[group_id]:
                        if not self.context_engine.has_scope(group_id):
                            chunk = self.context_chunks.get(group_id, [])
                            if chunk:
                                self.broadcaster.start_typing("summarizer_1", "Frank")
                                try:
                                    scope_data = await self.summarizer.analyze_scope(chunk)
                                    scope_text = scope_data.get("summary", "")
                                    scope_situation = scope_data.get("situation", [])
                                    self.context_engine.set_scope(group_id, scope_text)
                                    for t in chunk:
                                        t.metadata["situation"] = scope_situation
                                    self.stats["summarizer"]["scopes_analyzed"] += 1
                                except Exception:
                                    self.stats["summarizer"]["errors"] += 1
                                    raise
                                finally:
                                    self.broadcaster.stop_typing("summarizer_1", "Frank")

            # สร้าง Context สำหรับประโยค
            for t in batch.tokens:
                self.context_engine.build_context(t)
            
            if batch.batch_type == "LIGHT":
                # สำหรับ LIGHT ส่งตรงให้ EditorAgent แปลและเกลาในตัว
                await self.orchestrator.advance_and_route(batch, TokenState.EDITING)
            else:
                # ---------------- TLAS INTEGRATION ----------------
                # 1. Linguistic Analyzer Agent extracts Dialogue Metadata
                self.broadcaster.start_typing("analyzer_1", "Grace", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
                try:
                    await self.analyzer.process(batch)
                finally:
                    self.broadcaster.stop_typing("analyzer_1", "Grace")
                
                # 2. Mapping Engine resolves pronouns and updates Context Style Rules
                for t in batch.tokens:
                    if t.speaker:
                        current_phase = t.metadata.get("timeline_phase", -1)
                        speaker_profile = self.context_engine.get_resolved_profile(t.speaker, current_phase)
                        listener_profile = self.context_engine.get_resolved_profile(t.metadata.get("target_character", ""), current_phase) if t.metadata.get("target_character", "") else {}
                        
                        guidance = self.mapping_engine.resolve_pronouns(
                            speaker_profile=speaker_profile, 
                            listener_profile=listener_profile, 
                            metadata=t.metadata
                        )
                        t.context.pronoun_guidance = guidance
                        t.context.style_rules += f"\n\n{guidance}"
                # ----------------------------------------------------
                
                await self.orchestrator.advance_and_route(batch, TokenState.TRANSLATING)
            
        # 2. TRANSLATING -> แปลความหมาย -> ส่งให้ EDITING
        async def handle_translating(batch: TranslationBatch):
            self.stats["translator"]["batches_received"] += 1
            self.broadcaster.start_typing("translator_1", "Alice", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
            try:
                success = await self.translator.process(batch)
            finally:
                self.broadcaster.stop_typing("translator_1", "Alice")
            if success:
                self.stats["translator"]["batches_completed"] += 1
                await self.orchestrator.advance_and_route(batch, TokenState.EDITING)
            else:
                self.stats["translator"]["batches_failed"] += 1
                await self.orchestrator.advance_and_route(batch, TokenState.ERROR_CRITICAL)

        # 3. EDITING -> เกลาภาษา -> ส่งให้ QA_VERIFYING (หรือ VALIDATING สำหรับ LIGHT)
        async def handle_editing(batch: TranslationBatch):
            self.stats["editor"]["batches_received"] += 1
            self.broadcaster.start_typing("editor_1", "Bob", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
            try:
                success = await self.editor.process(batch)
            finally:
                self.broadcaster.stop_typing("editor_1", "Bob")
            if success:
                self.stats["editor"]["batches_completed"] += 1
                if batch.batch_type == "LIGHT":
                    await self.orchestrator.advance_and_route(batch, TokenState.VALIDATING)
                else:
                    await self.orchestrator.advance_and_route(batch, TokenState.QA_VERIFYING)
            else:
                self.stats["editor"]["batches_failed"] += 1
                await self.orchestrator.advance_and_route(batch, TokenState.ERROR_CRITICAL)

        # 4. QA_VERIFYING -> ตรวจงาน -> ผ่านไป TIMING / ไม่ผ่านตีกลับไป EDITING
        async def handle_qa(batch: TranslationBatch):
            self.stats["qa"]["batches_received"] += 1
            self.broadcaster.start_typing("qa_1", "Charlie", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
            try:
                success = await self.qa.process(batch)
            finally:
                self.broadcaster.stop_typing("qa_1", "Charlie")
            if success:
                self.stats["qa"]["batches_completed"] += 1
                await self.orchestrator.advance_and_route(batch, TokenState.TIMING)
            else:
                # QA Agent sets token.outputs.qa_feedback for failed tokens
                self.stats["qa"]["batches_completed"] += 1 # completed QA process, but found flaws
                self.stats["editor"]["repair_loops"] += 1
                await self.orchestrator.trigger_repair_loop(
                    batch, 
                    target_agent_state=TokenState.EDITING
                )

        # 5. TIMING -> ใส่จังหวะ -> ส่งให้ VALIDATING
        async def handle_timing(batch: TranslationBatch):
            self.broadcaster.start_typing("timing_1", "Diana", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
            try:
                success = await self.timing.process(batch)
            finally:
                self.broadcaster.stop_typing("timing_1", "Diana")
            if success:
                await self.orchestrator.advance_and_route(batch, TokenState.VALIDATING)
            else:
                await self.orchestrator.advance_and_route(batch, TokenState.ERROR_CRITICAL)

        # 6. VALIDATING -> ตรวจโค้ดด่านสุดท้าย -> ผ่านไป READY_TO_EXPORT
        async def handle_validating(batch: TranslationBatch):
            self.broadcaster.start_typing("validator_1", "Eve", tool_input={"batch_id": batch.batch_id, "size": len(batch.tokens)})
            try:
                all_valid = True
                for t in batch.tokens:
                    if not self.validator.validate(t):
                        t.outputs.qa_feedback = "Validation Failed: Syntax error detected."
                        all_valid = False
            finally:
                self.broadcaster.stop_typing("validator_1", "Eve")
            if all_valid:
                await self.orchestrator.advance_and_route(batch, TokenState.READY_TO_EXPORT)
            else:
                target_state = TokenState.EDITING if batch.batch_type == "LIGHT" else TokenState.TIMING
                await self.orchestrator.trigger_repair_loop(
                    batch,
                    target_agent_state=target_state
                )
                
        # 7. READY_TO_EXPORT -> บันทึกลงไฟล์ทันที (Continuous Saving)
        async def handle_export(batch: TranslationBatch):
            if self.output_file:
                self.broadcaster.start_typing("python_1", "Orion", tool_name="Continuous Saving", tool_input={"batch_id": batch.batch_id})
                try:
                    async with self.export_lock:
                        for t in batch.tokens:
                            self.parser.update_token_in_memory(t)
                        
                        # บันทึกลงไฟล์ .progress เพื่อไม่ให้รบกวนไฟล์หลักที่ผู้ใช้อาจจะเปิดดูอยู่
                        temp_save_path = self.output_file + ".progress"
                        self.parser.write_to_disk(temp_save_path)
                finally:
                    self.broadcaster.stop_typing("python_1", "Orion")
                logger.info(f"[Continuous Save] Batch {batch.batch_id} saved to {temp_save_path}.")
                
                # Update Translation Memory (TM)
                recent_heavy = [t for t in batch.tokens if t.token_type.startswith("HEAVY")]
                if recent_heavy:
                    self.context_engine.populate_tm(recent_heavy)

        # 8. ERROR_CRITICAL -> จัดการ Error ขั้นสุดท้าย
        async def handle_error(batch: TranslationBatch):
            logger.error(f"[App] Batch {batch.batch_id} entered ERROR_CRITICAL state. Halting processing for this batch.")

        # ลงทะเบียนกับ Event Bus
        self.event_bus.subscribe(TokenState.PENDING, handle_pending)
        self.event_bus.subscribe(TokenState.TRANSLATING, handle_translating)
        self.event_bus.subscribe(TokenState.EDITING, handle_editing)
        self.event_bus.subscribe(TokenState.QA_VERIFYING, handle_qa)
        self.event_bus.subscribe(TokenState.TIMING, handle_timing)
        self.event_bus.subscribe(TokenState.VALIDATING, handle_validating)
        self.event_bus.subscribe(TokenState.READY_TO_EXPORT, handle_export)
        self.event_bus.subscribe(TokenState.ERROR_CRITICAL, handle_error)
        
        logger.info("[App] All event handlers subscribed successfully.")

    async def run(self, input_file: str, output_file: str, master_prompt_file: str, max_batches: int = 0):
        """ฟังก์ชันหลักสำหรับเริ่มกระบวนการแปลทั้งไฟล์"""
        from datetime import datetime
        self.pipeline_start_time = datetime.now()
        logger.info(f"--- Starting ATF Pipeline ---")
        
        # 1. โหลดข้อมูลแบบ Dynamic จากไฟล์ Master Prompt .md
        if os.path.exists(master_prompt_file):
            self.context_engine.load_master_prompt_md(master_prompt_file)
        else:
            logger.warning(f"Master prompt file {master_prompt_file} not found. Running without dynamic context.")
            
        # โหลดข้อมูล TLAS RAG
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        tlas_dir = os.path.join(project_root, "data", "tlas")
        self.context_engine.load_tlas_data(tlas_dir)
        
        # 2. แกะไฟล์ CSV
        if os.path.exists(input_file):
            tokens = self.parser.parse(input_file)
        else:
            logger.error(f"Input file {input_file} not found.")
            return
            
        # ถ้าอยากเทสแค่ไม่กี่บรรทัด จะตัดอาเรย์ (กรณี max_tokens > 0)
        # สังเกตว่าเราจะจำกัดเฉพาะ Token ที่ต้องแปล
        translated_tokens = [t for t in tokens if t.current_state == TokenState.ALREADY_TRANSLATED]
        pending_tokens = [t for t in tokens if t.current_state != TokenState.ALREADY_TRANSLATED]
            
        self.already_translated_tokens = translated_tokens
        
        # สร้าง Full TM และ Auto-Glossary จากคำแปลเก่าทั้งหมด
        if translated_tokens:
            self.context_engine.populate_full_tm(translated_tokens)
            
        self.output_file = output_file
        
        # 3. จัดเตรียม Context Scopes (แบ่งกลุ่มละ 30 เซลล์สำหรับ HEAVY)
        heavy_tokens = [t for t in pending_tokens if t.token_type.startswith("HEAVY")]
        light_tokens = [t for t in pending_tokens if t.token_type.startswith("LIGHT")]
        
        chunk_size = 30
        for i in range(0, len(heavy_tokens), chunk_size):
            chunk = heavy_tokens[i:i + chunk_size]
            group_id = f"SCOPE_{i // chunk_size + 1}"
            self.context_chunks[group_id] = chunk
            for t in chunk:
                t.metadata["context_group_id"] = group_id
                
        logger.info(f"[App] Created {len(self.context_chunks)} Context Scopes for HEAVY tokens.")
        
        # 4. จัดกลุ่มเป็น Batch ตาม Token และ Token Type
        batches = []
        
        def group_tokens(tokens_list, b_type, max_tokens=150):
            grouped_batches = []
            current_chunk = []
            current_count = 0
            for t in tokens_list:
                if current_count + t.estimated_tokens > max_tokens and current_chunk:
                    b = TranslationBatch(batch_id=f"B_{b_type}_{len(grouped_batches)+1}", batch_type=b_type, tokens=current_chunk)
                    grouped_batches.append(b)
                    current_chunk = []
                    current_count = 0
                
                current_chunk.append(t)
                current_count += t.estimated_tokens
                
            if current_chunk:
                b = TranslationBatch(batch_id=f"B_{b_type}_{len(grouped_batches)+1}", batch_type=b_type, tokens=current_chunk)
                grouped_batches.append(b)
            return grouped_batches

        batches.extend(group_tokens(heavy_tokens, "HEAVY", max_tokens=80))
        batches.extend(group_tokens(light_tokens, "LIGHT", max_tokens=120))
            
        if max_batches > 0:
            batches = batches[:max_batches]
            
        self.processed_batches = batches
        
        # ปลุกตัวละครใน Pixel Desk
        self.broadcaster.start_session("python_1", "Orion")
        self.broadcaster.start_session("translator_1", "Alice")
        self.broadcaster.start_session("editor_1", "Bob")
        self.broadcaster.start_session("qa_1", "Charlie")
        self.broadcaster.start_session("timing_1", "Diana")
        self.broadcaster.start_session("validator_1", "Eve")
        self.broadcaster.start_session("summarizer_1", "Frank")
        self.broadcaster.start_session("analyzer_1", "Grace")
        
        self.broadcaster.start_typing("python_1", "Orion", tool_name="Orchestrating Pipeline")
        
        # Populate TM for context
        recent_translated = translated_tokens[-100:]
        if recent_translated:
            self.context_engine.populate_tm(recent_translated)

        # 4. เริ่มต้นระบบ Event Bus และ Queue Worker
        await self.event_bus.start()
        self.orchestrator.start_queue_worker()
        
        # 5. โยนเฉพาะ Batch ที่รอการแปลเข้าคิว
        import time
        import sys
        start_time = time.time()
        loop_count = 1
        
        while True:
            logger.info(f"--- Starting Pipeline Pass {loop_count} ---")
            
            batches_to_run = [b for b in self.processed_batches if b.current_state not in (TokenState.READY_TO_EXPORT,)]
            for batch in batches_to_run:
                if batch.current_state == TokenState.ERROR_CRITICAL:
                    # Reset state for retry
                    for t in batch.tokens:
                        t.current_state = TokenState.PENDING
                    batch.current_state = TokenState.PENDING
                self.orchestrator.enqueue_batch(batch)
                
            # 6. รอจนกว่า Batch ทั้งหมดจะแปลเสร็จ (พร้อมแสดง Progress Bar และ ETA)
            while any(b.current_state not in (TokenState.READY_TO_EXPORT, TokenState.ERROR_CRITICAL) for b in self.processed_batches):
                await asyncio.sleep(1.0)
                
                total_batches = len(self.processed_batches)
                success_batches = sum(1 for b in self.processed_batches if b.current_state == TokenState.READY_TO_EXPORT)
                failed_batches = sum(1 for b in self.processed_batches if b.current_state == TokenState.ERROR_CRITICAL)
                remaining_batches = total_batches - success_batches - failed_batches
                completed = success_batches + failed_batches
                
                progress_pct = (completed / total_batches) * 100 if total_batches > 0 else 100
                
                elapsed = time.time() - start_time
                if completed > 0:
                    avg_time_per_batch = elapsed / completed
                    eta_seconds = remaining_batches * avg_time_per_batch
                else:
                    eta_seconds = 0
                    
                eta_str = time.strftime('%H:%M:%S', time.gmtime(eta_seconds))
                
                bar_length = 20
                filled_len = int(bar_length * completed // total_batches) if total_batches > 0 else bar_length
                bar = '#' * filled_len + '-' * (bar_length - filled_len)
                
                # แสดงผลที่บรรทัดเดิม
                sys.stdout.write(f"\rProgress: [{bar}] {progress_pct:.1f}% | Total: {total_batches} | Success: {success_batches} | Failed: {failed_batches} | Rem: {remaining_batches} | ETA: {eta_str}   ")
                sys.stdout.flush()
                
            print() # ขึ้นบรรทัดใหม่หลังจบรอบ
            
            # เช็คว่ามี failed หรือไม่
            final_failed = sum(1 for b in self.processed_batches if b.current_state == TokenState.ERROR_CRITICAL)
            if final_failed == 0:
                logger.info("All batches completed successfully 100%!")
                break
            else:
                logger.warning(f"Found {final_failed} failed batches. Re-queueing for self-healing repair loop...")
                loop_count += 1
                await asyncio.sleep(2.0)

            
        # 7. เมื่อเสร็จหมดแล้ว สั่ง Export
        if os.path.exists(input_file):
            self.broadcaster.start_typing("python_1", "Orion", tool_name="Exporting Final CSV")
            try:
                all_tokens = self.already_translated_tokens + [t for b in self.processed_batches for t in b.tokens]
                
                # เขียนลงไฟล์หลัก
                success = self.parser.export(input_file, all_tokens, output_file)
                
                # หากเขียนไฟล์หลักสำเร็จ ให้ลบไฟล์ .progress ทิ้ง
                if success:
                    progress_file = output_file + ".progress"
                    if os.path.exists(progress_file):
                        try:
                            os.remove(progress_file)
                        except Exception as e:
                            logger.warning(f"Could not remove progress file {progress_file}: {e}")
                            
            finally:
                self.broadcaster.stop_typing("python_1", "Orion")
            
        # 8. ปิดระบบ
        await self.orchestrator.shutdown()
        
        self.broadcaster.end_session("translator_1", "Alice")
        self.broadcaster.end_session("editor_1", "Bob")
        self.broadcaster.end_session("qa_1", "Charlie")
        self.broadcaster.end_session("timing_1", "Diana")
        self.broadcaster.end_session("validator_1", "Eve")
        self.broadcaster.end_session("summarizer_1", "Frank")
        self.broadcaster.end_session("analyzer_1", "Grace")
        self.broadcaster.end_session("python_1", "Orion")
        
        logger.info(f"--- ATF Pipeline Finished ---")
        
        # พิมพ์สรุปผลรวมของการทำงาน (Terminal Summary)
        logger.info("\n" + "="*60)
        logger.info("   ATF Pipeline Execution Summary")
        logger.info("="*60)
        
        total_batches = len(self.processed_batches)
        completed = sum(1 for b in self.processed_batches if b.current_state == TokenState.READY_TO_EXPORT)
        failed = sum(1 for b in self.processed_batches if b.current_state == TokenState.ERROR_CRITICAL)
        
        logger.info(f"Total Batches Submitted: {total_batches}")
        logger.info(f" - Completed: {completed}")
        logger.info(f" - Failed:    {failed}")
        logger.info("-" * 60)
        
        logger.info(f"[Summarizer] Scopes Analyzed: {self.stats['summarizer']['scopes_analyzed']} | Errors: {self.stats['summarizer']['errors']}")
        logger.info(f"[Translator] Batches Received: {self.stats['translator']['batches_received']} | Completed: {self.stats['translator']['batches_completed']} | Failed: {self.stats['translator']['batches_failed']}")
        logger.info(f"[Editor]     Batches Received: {self.stats['editor']['batches_received']} | Completed: {self.stats['editor']['batches_completed']} | Returned/Fixed: {self.stats['editor']['repair_loops']} | Failed: {self.stats['editor']['batches_failed']}")
        logger.info(f"[QA]         Batches Received: {self.stats['qa']['batches_received']} | Checked: {self.stats['qa']['batches_completed']} | Errors/Failures: {self.stats['qa']['batches_failed']}")
        
        # Capture End Time and Extract Logs
        from datetime import datetime
        self.pipeline_end_time = datetime.now()
        self.logger_agent.extract_run_logs(self.pipeline_start_time, self.pipeline_end_time, total_batches)
        
        logger.info("="*60 + "\n")

if __name__ == "__main__":
    app = ATFApplication()
    
    # รันทดสอบกับไฟล์จริง (ทดสอบแค่ 5 บรรทัดแรกก่อนเพื่อความเร็ว หากต้องการรันทั้งหมดให้ลบ max_tokens=5 ออก)
    asyncio.run(app.run(
        input_file="testing files/SSPV034v1.35 - Trans - Processed_v3.csv", 
        output_file="testing files/SSPV034v1.35 - Trans - Processed_v3_out.csv",
        master_prompt_file="testing files/Master_Prompt_Hybrid.md"
    ))