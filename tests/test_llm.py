
import sys
import os
import asyncio
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer4_Analysis.core.llm_client import AsyncLLMClient
from Config.config import LLM_MODEL

async def test_llm():
    print(f"Testing connection to Ollama model: {LLM_MODEL}...")
    client = AsyncLLMClient(model=LLM_MODEL)
    
    status = client.health()
    print(f"Health Check: {status}")
    
    print("Sending prompt: 'What is diplomatic immunity? Answer in 1 sentence.'")
    response = await client.generate("What is diplomatic immunity? Answer in 1 sentence.")
    
    print("\n--- Response ---")
    print(response)
    print("----------------")
    
    if "LLM_ERROR" in response:
        print("FAIL: Could not generate text.")
        sys.exit(1)
    else:
        print("SUCCESS: Connected to LLM.")

if __name__ == "__main__":
    asyncio.run(test_llm())
