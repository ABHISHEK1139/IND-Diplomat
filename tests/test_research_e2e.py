import asyncio
import logging
import sys
import os

# Ensure the src directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from dip.pipeline.collection.research.planner import ResearchPlanner

logging.basicConfig(level=logging.INFO)

from duckduckgo_search import DDGS

import pytest

@pytest.mark.asyncio
async def test_research_planner_execution():
    planner = ResearchPlanner()
    result = await planner.execute_from_gaps(
        missing_signals=["latest news on space exploration"],
        country="USA",
        query_context="Determine current state of US space capabilities"
    )
    assert result is not None
    assert hasattr(result, "documents")
    assert hasattr(result, "evidence")
    assert hasattr(result, "execution_time")

async def main():
    print("Testing DDGS native...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text("space exploration", max_results=2))
            print("Native DDGS:", results)
    except Exception as e:
        print("Native DDGS Error:", e)

    planner = ResearchPlanner()
    
    print("Executing Research Planner...")
    result = await planner.execute_from_gaps(
        missing_signals=["latest news on space exploration"],
        country="USA",
        query_context="Determine current state of US space capabilities"
    )
    
    print("\n" + "="*50)
    print("RESEARCH COMPLETE")
    print("="*50)
    print(f"Time: {result.execution_time:.2f}s")
    print(f"Documents retrieved: {len(result.documents)}")
    print(f"Evidence extracted: {len(result.evidence)}")
    
    for i, ev in enumerate(result.evidence):
        print(f"\n[Evidence {i+1}] {ev.publisher} (Confidence: {ev.confidence})")
        print(f"URL: {ev.url}")
        print(f"Text: {ev.text}")

if __name__ == "__main__":
    asyncio.run(main())

