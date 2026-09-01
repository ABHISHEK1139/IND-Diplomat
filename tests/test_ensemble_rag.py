import pytest
from dip.pipeline.knowledge.ensemble_rag import legal_rag

def test_ensemble_legal_rag_retrieval():
    passages = legal_rag.retrieve("sovereignty violation and self defense un charter", top_k=2)
    assert len(passages) == 2
    assert "UN_CHARTER" in [p.treaty for p in passages]
    assert passages[0].relevance_score > 0.0
    assert passages[0].citation != ""
