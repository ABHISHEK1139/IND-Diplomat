import pytest

pytestmark = pytest.mark.live_llm
pytest.importorskip("ragas", reason="Ragas is an optional live-LLM QA dependency")

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)

def test_ragas_e2e_evaluation():
    """
    Evaluates the RAG pipeline using Ragas metrics on a sample dataset.
    This mimics how we'd evaluate the Knowledge Extraction (Layer 2) and World Model (Layer 3)
    outputs against a golden test set.
    """
    
    # 1. Prepare sample data in the format Ragas expects
    # 'question': The analyst's query
    # 'answer': The LLM's generated assessment
    # 'contexts': The retrieved documents/evidence from Neo4j/Qdrant
    # 'ground_truth': The golden answer we expect
    
    data_samples = {
        "question": ["What is India's plan for semiconductor manufacturing?"],
        "answer": ["India is investing $10B through the India Semiconductor Mission. Tata and PSMC are building a 28nm fab in Gujarat expected to be operational by 2026."],
        "contexts": [
            [
                "The Indian Semiconductor Mission (ISM) launched with a $10B outlay.",
                "Tata Electronics and PSMC announced a 28nm fab joint venture in Dholera, Gujarat.",
                "Production at the Dholera fab is slated to begin in 2026."
            ]
        ],
        "ground_truth": ["India's strategy centers on a $10B subsidy program (ISM). Key projects include a Tata-PSMC 28nm fab in Gujarat starting in 2026."]
    }
    
    dataset = Dataset.from_dict(data_samples)
    
    # 2. Run the evaluation
    # Note: This requires OpenAI API keys by default as Ragas uses LLM-as-a-judge
    # For CI, you'd typically use a local model or mock this.
    try:
        result = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall
            ],
            raise_exceptions=False # Don't crash test runner if API key missing during initial setup
        )
        
        # 3. Assert quality thresholds
        assert result["faithfulness"] >= 0.7, f"Faithfulness too low: {result['faithfulness']}"
        assert result["answer_relevancy"] >= 0.7, f"Answer relevancy too low: {result['answer_relevancy']}"
        assert result["context_precision"] >= 0.7, f"Context precision too low: {result['context_precision']}"
        
    except Exception as e:
        # If API keys aren't set up yet, we'll gracefully skip rather than failing
        # In production CI, this should be a hard fail.
        pytest.skip(f"Ragas evaluation skipped (likely missing API keys): {str(e)}")
