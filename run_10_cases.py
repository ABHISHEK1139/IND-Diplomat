import asyncio
import logging
from dip.pipeline.deliberation.reasoning.ablation import AblationConfig
from dip.pipeline.deliberation.reasoning.backtesting import HISTORICAL_CASES
import run_backtest

logging.basicConfig(level=logging.INFO)

async def test_all_10_cases():
    print(f"=======================================================")
    print(f"  RUNNING 10 WORLD SCENARIOS (FULL MULTI-AGENT CONFIG)  ")
    print(f"=======================================================\n")
    
    study = run_backtest.AblationStudy()
    
    for case in HISTORICAL_CASES:
        print(f">> Evaluating: {case.name}")
        try:
            res = await run_backtest.run_case_evaluation(case, AblationConfig.FULL, use_mocks=False)
            print(f"   [SUCCESS] Predicted: {res.predicted_probability:.2f} (Actual: {case.actual_probability:.2f})\n")
        except Exception as e:
            print(f"   [ERROR / BUG CAUGHT] {case.name} failed: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_all_10_cases())
