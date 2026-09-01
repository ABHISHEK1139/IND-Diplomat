import asyncio
import json
import logging
import pytest
from dip.unified_pipeline import execute
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

@pytest.mark.asyncio
async def test_pipeline_smoke():
    result = await execute("Massive cyber attack on Taiwanese grid detected. Chinese naval vessels moving into strait.", "TWN")
    assert result is not None
    assert result["status"] in ("COMPLETE", "WITHHELD", "HUMAN_REVIEW", "REFUSED", "HUMAN_OVERRIDE_REQUIRED")
    assert "threat_level" in result
    assert "verification_score" in result

async def main():
    print("==========================================")
    print("INPUT: Query = 'Massive cyber attack on Taiwanese grid detected. Chinese naval vessels moving into strait.'")
    print("INPUT: Country = 'TWN'")
    print("==========================================\n")
    
    print("--- PIPELINE STARTING ---")
    try:
        result = await execute("Massive cyber attack on Taiwanese grid detected. Chinese naval vessels moving into strait.", "TWN")
        
        print("\n==========================================")
        print("FINAL OUTPUT CATCHED:")
        print("==========================================")
        
        print(json.dumps(result, indent=2))
        
        print("\n--- BUG CHECK ---")
        if "nash_equilibrium" not in result:
            print("[BUG] Nash Equilibrium missing from output!")
        else:
            print("[OK] Nash Equilibrium successfully populated.")
            
        if "ripple_effects" not in result:
            print("[BUG] Ripple Effects missing from output!")
        else:
            print("[OK] Ripple Effects successfully populated.")
            
        if "self_model_dashboard" not in result:
            print("[BUG] Self-Model Dashboard missing from output!")
        else:
            print("[OK] Self-Model Dashboard successfully populated.")
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

