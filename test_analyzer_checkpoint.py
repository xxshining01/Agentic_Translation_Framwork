import asyncio
import os
import sys

# Ensure the src path is available
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from atf.tools.tlas_analyzer import run_analyzer

async def main():
    print("=== STARTING TLAS ANALYZER DRY RUN TEST ===")
    tlas_dir = r"d:\Agentic Translation Framework (ATF) Project\data\tlas"
    
    # Run the analyzer (this will use the actual analyzer logic but we only care about the init printout for this test to verify the fix)
    try:
        # We wrap in a timeout so it doesn't process all 1226 files but just shows the initial print
        task = asyncio.create_task(run_analyzer(tlas_dir))
        await asyncio.wait_for(task, timeout=5)
    except asyncio.TimeoutError:
        print("\n=== TEST TIMED OUT (AS EXPECTED, WE ONLY NEED THE PRE-FLIGHT LOGS) ===")
    except Exception as e:
        print(f"\n=== TEST FAILED: {e} ===")

if __name__ == "__main__":
    asyncio.run(main())
