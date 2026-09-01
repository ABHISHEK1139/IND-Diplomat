import pytest
import os
import sys
from pathlib import Path
import numpy as np

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from dip.pipeline.knowledge import vector_store
from dip.pipeline.memory.backtesting.crisis_registry import registry, CrisisTimelineEvent, CrisisScenario
from dip.engines.legal.signal_legal_mapper import map_signal_to_treaties


def test_tfidf_fallback_vector_store():
    # Force store to use fallback by skipping chroma initialization in test
    vector_store.CHROMADB_AVAILABLE = False
    
    # Create a fresh store
    store = vector_store.VectorStore()
    
    # Store some documents
    store.store_document("test_col", "doc1", "The cat sits on the mat")
    store.store_document("test_col", "doc2", "The dog barks at the mailman")
    store.store_document("test_col", "doc3", "A cat and a dog")
    
    # Search
    results = store.search("test_col", "cat", k=2)
    assert len(results) > 0
    assert "cat" in results[0]["text"].lower()

def test_crisis_registry_schema():
    # Registry should have loaded defaults
    scenarios = registry.list_scenarios()
    assert "UKRAINE_2022" in scenarios
    
    scenario = registry.get_scenario("UKRAINE_2022")
    assert scenario is not None
    assert scenario["name"] == "Russian Invasion of Ukraine"
    assert len(scenario["timeline"]) > 0

def test_dynamic_treaty_association():
    # Test that vector store fallback or hardcoded works
    # Using a known signal that has a hardcoded mapping
    results = map_signal_to_treaties("troop_movement", intensity=0.8, country="IND", target="BTN")
    
    assert len(results) > 0
    # Should trigger India-Bhutan Friendship Treaty (from bilateral fallback or hardcoded map)
    found_bhutan = any("Bhutan" in r["treaty"] for r in results)
    assert found_bhutan is True
    
@pytest.mark.skip(reason="Function _scipy_minimax_solve was removed")
def test_scipy_minimax_solve():
    pass
