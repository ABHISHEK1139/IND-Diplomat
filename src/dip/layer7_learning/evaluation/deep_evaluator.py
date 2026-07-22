import logging
from typing import Dict, Any, List

try:
    from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase
except ImportError:
    HallucinationMetric, AnswerRelevancyMetric, LLMTestCase = None, None, None

logger = logging.getLogger("DIP3.Layer7.DeepEvaluator")

class DeepEvaluator:
    """
    Uses DeepEval to score every run (Hallucination rate, Answer quality).
    """
    def __init__(self):
        # We define a threshold where scores below this are considered "failed"
        self.threshold = 0.7

    def evaluate_dossier(self, query: str, context: List[str], generated_output: str) -> Dict[str, Any]:
        """
        Evaluates the generated intelligence dossier against the provided context and query.
        """
        logger.info("Evaluating dossier for hallucinations and answer relevancy.")
        
        if not all([HallucinationMetric, AnswerRelevancyMetric, LLMTestCase]):
            logger.warning("deepeval not found. Returning mocked evaluation metrics.")
            return {
                "hallucination_score": 0.0,
                "hallucination_reason": "Mocked",
                "answer_relevancy_score": 1.0,
                "answer_relevancy_reason": "Mocked"
            }

        # Format inputs for DeepEval
        actual_output = generated_output
        if isinstance(actual_output, dict):
            actual_output = str(actual_output.get("final_report", actual_output))

        # We must provide some context to check hallucination against
        if not context:
            context = ["No evidence collected."]

        test_case = LLMTestCase(
            input=query,
            actual_output=actual_output,
            context=context
        )

        metrics_results = {}
        
        try:
            # Evaluate Hallucination
            hallucination_metric = HallucinationMetric(threshold=self.threshold)
            hallucination_metric.measure(test_case)
            metrics_results["hallucination_score"] = hallucination_metric.score
            metrics_results["hallucination_reason"] = hallucination_metric.reason
            
            # Evaluate Answer Relevancy
            relevancy_metric = AnswerRelevancyMetric(threshold=self.threshold)
            relevancy_metric.measure(test_case)
            metrics_results["answer_relevancy_score"] = relevancy_metric.score
            metrics_results["answer_relevancy_reason"] = relevancy_metric.reason
            
        except Exception as e:
            logger.error(f"DeepEval metric execution failed: {e}")
            metrics_results["error"] = str(e)
            metrics_results["hallucination_score"] = 0.0
            metrics_results["answer_relevancy_score"] = 0.0

        return metrics_results
