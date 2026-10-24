import os
import re
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class LoggerAgent:
    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.logs_dir = os.path.join(self.project_root, "logs")
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
    def extract_run_logs(self, start_time: datetime, end_time: datetime, total_batches: int):
        try:
            # Create folder
            run_folder_name = f"run_{start_time.strftime('%Y%m%d_%H%M%S')}"
            run_folder_path = os.path.join(self.logs_dir, run_folder_name)
            if not os.path.exists(run_folder_path):
                os.makedirs(run_folder_path)
                
            atf_log_dest = os.path.join(run_folder_path, "atf_run.log")
            lm_studio_log_dest = os.path.join(run_folder_path, "lm_studio_run.log")
            
            self._extract_atf_log(atf_log_dest, start_time, end_time, total_batches)
            self._extract_lm_studio_log(lm_studio_log_dest, start_time, end_time, total_batches)
            
            logger.info(f"[LoggerAgent] Logs for this run successfully saved to {run_folder_path}")
        except Exception as e:
            logger.error(f"[LoggerAgent] Failed to extract logs: {e}")

    def _extract_atf_log(self, dest_path, start_time, end_time, total_batches):
        source_log = os.path.join(self.project_root, "atf.log")
        if not os.path.exists(source_log):
            logger.warning(f"[LoggerAgent] Could not find ATF log at {source_log}")
            return
            
        with open(source_log, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # Find the latest "Starting ATF Pipeline" before or near start_time
        start_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if "--- Starting ATF Pipeline ---" in lines[i]:
                start_idx = i
                break
                
        if start_idx == -1:
            start_idx = 0
            
        run_lines = lines[start_idx:]
        
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("="*60 + "\n")
            f.write(f" ATF Run Summary\n")
            f.write(f" Start Time: {start_time}\n")
            f.write(f" End Time:   {end_time}\n")
            f.write(f" Total Batches Submitted: {total_batches}\n")
            f.write("="*60 + "\n\n")
            f.writelines(run_lines)

    def _extract_lm_studio_log(self, dest_path, start_time, end_time, total_batches):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            logger.warning("[LoggerAgent] APPDATA environment variable not found. Cannot extract LM Studio logs.")
            return
            
        lm_log_path = os.path.join(appdata, "LM Studio", "logs", "main.log")
        if not os.path.exists(lm_log_path):
            logger.warning(f"[LoggerAgent] LM Studio log not found at {lm_log_path}")
            return
            
        # Regex to parse [YYYY-MM-DD HH:MM:SS.mmm]
        time_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]")
        
        extracted_lines = []
        is_in_range = False
        
        with open(lm_log_path, "r", encoding="utf-8") as f:
            for line in f:
                match = time_pattern.search(line)
                if match:
                    try:
                        log_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")
                        # We give a 1-minute buffer to ensure we catch everything
                        if log_time >= (start_time - timedelta(minutes=1)):
                            is_in_range = True
                        if log_time > (end_time + timedelta(minutes=1)):
                            is_in_range = False
                    except ValueError:
                        pass
                
                if is_in_range:
                    extracted_lines.append(line)
                    
        if extracted_lines:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write("="*60 + "\n")
                f.write(f" LM Studio Run Log\n")
                f.write(f" Run Window: {start_time} to {end_time}\n")
                f.write(f" Total Batches: {total_batches}\n")
                f.write("="*60 + "\n\n")
                f.writelines(extracted_lines)
        else:
            logger.info("[LoggerAgent] No LM Studio logs found within the time range.")
