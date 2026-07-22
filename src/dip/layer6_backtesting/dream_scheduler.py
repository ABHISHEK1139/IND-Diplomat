from dip.Config.config import config
"""
Dream Scheduler (Layer 6 Consolidation)
=======================================
Runs a background loop that samples the ChromaDB Memory Vault when the system
is idle. It finds hidden cross-temporal patterns and "dreams" up new insights.
"""

import os
import logging
import asyncio
from typing import List

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None

try:
    import litellm
except ImportError:
    litellm = None

logger = logging.getLogger("Layer6.dream")
LLM_MODEL = config.LLM_MODEL

async def run_consolidation_dream():
    """
    Randomly samples 2 historic events from ChromaDB and uses the LLM
    to find structural similarities or insights that analysts might have missed.
    """
    if not chromadb or not litellm:
        logger.warning("Dependencies missing for dreaming.")
        return "Dependencies missing."
        
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chromadb")
    os.makedirs(db_path, exist_ok=True)
    
    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_or_create_collection(name="crisis_memory")
        
        # In a real scenario we sample randomly. For now, just peek.
        peek = collection.peek(2)
        if not peek or not peek.get("documents") or len(peek["documents"]) < 2:
            return "Not enough memories to dream."
            
        doc1 = peek["documents"][0]
        doc2 = peek["documents"][1]
        
        prompt = (
            f"You are the consolidation engine of a geopolitical AI. You are 'dreaming'.\n"
            f"Look at these two disparate historical crisis memories:\n"
            f"Memory 1: {doc1}\n"
            f"Memory 2: {doc2}\n\n"
            f"What structural, hidden similarity do these two events share? "
            f"Write a 1-paragraph 'Morning Discovery' insight."
        )
        
        response = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,  # Higher temp for creative dreaming
            max_tokens=1000
        )
        
        insight = response.choices[0].message.content.strip()
        logger.info(f"DREAM INSIGHT GENERATED: {insight}")
        return insight
        
    except Exception as e:
        logger.error(f"Dream error: {e}")
        return "Dream failed."

if __name__ == "__main__":
    print(asyncio.run(run_consolidation_dream()))
