
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer2_Knowledge.retriever import DiplomaticRetriever

def test_rag():
    print("Testing DiplomaticRetriever (RAG)...")
    retriever = DiplomaticRetriever()
    
    # Query for something we know is in legal_memory (Refugees chapter)
    query = "What are the rights of refugees under the 1951 convention?"
    print(f"Query: {query}")
    
    results = retriever.hybrid_search(query, top_k=3)
    
    print(f"Found {len(results)} results.")
    for i, res in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  ID: {res.get('id')}")
        print(f"  Score: {res.get('score')}")
        print(f"  Space: {res.get('space')}")
        print(f"  Source: {res.get('metadata', {}).get('source')}")
        print(f"  Content Snippet: {res.get('content', '')[:200]}...")

if __name__ == "__main__":
    test_rag()
