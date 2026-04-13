"""Phase 6: Full end-to-end pipeline test."""
import sys, os, traceback, asyncio
proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, proj)

from test._support import script_log_path

out = open(script_log_path("e2e_results.log"), "w", encoding="utf-8")

async def full_test():
    try:
        from Config.pipeline import initialize, run_query
        
        out.write("=== 1. Pipeline Initialize ===\n")
        initialize()
        out.write("OK: Pipeline initialized\n\n")
        
        out.write("=== 2. Full Pipeline Query ===\n")
        result = await run_query(
            "What is the current state of India-China trade relations?",
            country_code="IND",
        )
        out.write(f"OK: Pipeline completed\n")
        out.write(f"  result type: {type(result).__name__}\n")
        if isinstance(result, dict):
            out.write(f"  keys: {list(result.keys())[:10]}\n")
            out.write(f"  answer: {str(result.get('answer', ''))[:200]}\n")
        else:
            out.write(f"  value: {str(result)[:200]}\n")
            
    except Exception:
        out.write("FAIL:\n")
        traceback.print_exc(file=out)

asyncio.run(full_test())
out.close()
print("Done")
