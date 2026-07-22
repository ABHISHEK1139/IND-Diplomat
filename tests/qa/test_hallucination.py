import pytest

pytestmark = pytest.mark.live_llm
pytest.importorskip("deepeval", reason="DeepEval is an optional live-LLM QA dependency")

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import HallucinationMetric, FaithfulnessMetric

def test_hallucination():
    """
    Evaluates whether the LLM's forecast output contradicts or hallucinates 
    beyond the retrieved context (evidence_log).
    """
    
    # Mock result from the pipeline
    actual_output = "India will aggressively build 10 trailing-edge fabs by 2026, investing $50B."
    
    # The factual context returned from our OSINT retrieval/Neo4j graph
    retrieval_context = [
        "The Indian Semiconductor Mission has pledged $10B for semiconductor manufacturing.",
        "Tata and PSMC are partnering to build a 28nm fab in Gujarat.",
        "The timeline for the first fab to be operational is late 2026."
    ]

    # Initialize the Hallucination metric (threshold 0.5 means any hallucination score >= 0.5 fails)
    hallucination_metric = HallucinationMetric(threshold=0.5)

    test_case = LLMTestCase(
        input="What is India's semiconductor manufacturing strategy?",
        actual_output=actual_output,
        context=retrieval_context
    )

    # assert_test evaluates the test case using the selected metric
    # In this case, it should detect a hallucination ($50B vs $10B, 10 fabs vs 1 fab)
    assert_test(test_case, [hallucination_metric])

def test_faithfulness():
    """
    Evaluates whether the LLM's output can be directly inferred from the retrieved context.
    """
    actual_output = "India is building a 28nm fab in Gujarat in partnership with Tata and PSMC, supported by a $10B government mission."
    
    retrieval_context = [
        "The Indian Semiconductor Mission has pledged $10B for semiconductor manufacturing.",
        "Tata and PSMC are partnering to build a 28nm fab in Gujarat.",
        "The timeline for the first fab to be operational is late 2026."
    ]
    
    faithfulness_metric = FaithfulnessMetric(threshold=0.7)
    
    test_case = LLMTestCase(
        input="What is India's semiconductor manufacturing strategy?",
        actual_output=actual_output,
        retrieval_context=retrieval_context
    )
    
    assert_test(test_case, [faithfulness_metric])
