import json
import asyncio
import logging
from pathlib import Path
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from dip.unified_pipeline import execute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("replay_runner")

async def run_benchmark():
    """
    Runs the unified_pipeline against the golden benchmark dataset and evaluates
    the responses using DeepEval.
    """
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    
    with open(dataset_path, "r") as f:
        benchmarks = json.load(f)

    # Note: Requires OPENAI_API_KEY for DeepEval
    answer_relevancy = AnswerRelevancyMetric(threshold=0.7)
    faithfulness = FaithfulnessMetric(threshold=0.7)

    for i, test_case in enumerate(benchmarks):
        logger.info(f"Running Scenario {i+1}: {test_case['query']}")
        
        # 1. Execute the pipeline
        try:
            result = await execute(test_case["query"], test_case["country_code"])
            actual_output = result.get("briefing", "")
            
            # 2. Check strict conditions
            if test_case["expected_threat_level"] != result.get("threat_level"):
                logger.warning(
                    f"Threat level mismatch: Expected {test_case['expected_threat_level']}, "
                    f"Got {result.get('threat_level')}"
                )
            
            # 3. Evaluate with DeepEval (Semantic evaluation)
            eval_case = LLMTestCase(
                input=test_case["query"],
                actual_output=actual_output if actual_output else "No briefing generated.",
                retrieval_context=result.get("evidence_log", []),
                expected_output=f"Key entities: {', '.join(test_case['expected_entities'])}. "
                                f"Keywords: {', '.join(test_case['expected_narrative_keywords'])}."
            )

            answer_relevancy.measure(eval_case)
            faithfulness.measure(eval_case)
            
            logger.info(f"Score - Relevancy: {answer_relevancy.score}, Faithfulness: {faithfulness.score}")
            
        except Exception as e:
            logger.error(f"Failed benchmark {test_case['id']}: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
