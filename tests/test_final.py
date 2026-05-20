import sys
import os
import asyncio
from pathlib import Path

# Provide pure correct scope
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.Layer4_Analysis.core.llm_client import AsyncLLMClient
from dotenv import load_dotenv

load_dotenv()

async def functional_test():
    client = AsyncLLMClient()
    client.local.provider = "openrouter"
    
    print("--- TESTING OPENROUTER VALIDATED CONTEXT LIMITS ---\n")
    
    # 1. Test massive prompt against Qwen (which supports 262k context according to the backend)
    # We will give it a 100k character prompt string which easily fits in its 700k char limit.
    client.local.model = "qwen/qwen3-coder:free"
    huge_load = "apple " * 15000  # ~105,000 characters
    
    print(f"[TEST 1] Sending {len(huge_load)} characters to {client.local.model} (Limit: 700k chars)...")
    resp_qwen = client.local._generate_openrouter(
        system_prompt="Test.", user_prompt=f"Summarize:\n{huge_load}",
        temperature=0.1, timeout=60, json_mode=False, max_tokens=10
    )
    if "LLM_ERROR" in resp_qwen:
        print(f"❌ QWEN FAILED: {resp_qwen[:100]}\n")
    else:
        print(f"✅ QWEN SUCCEEDED via raw API! Response: {resp_qwen[:100]}\n")

    # 2. Test auto-compactor fallback logic by purposely exceeding the 350k limit of Hermes
    client.local.model = "nousresearch/hermes-3-llama-3.1-405b:free"
    overloaded_load = "orange " * 60000  # ~420,000 characters, exceeds 350k compactor limit
    
    print(f"[TEST 2] Sending {len(overloaded_load)} characters to {client.local.model} (Limit: 350k chars)...")
    resp_hermes = client.local._generate_openrouter(
        system_prompt="Test.", user_prompt=f"Summarize overload:\n{overloaded_load}",
        temperature=0.1, timeout=60, json_mode=False, max_tokens=10
    )
    
    if "LLM_ERROR" in resp_hermes:
        print(f"❌ HERMES FAILED: {resp_hermes[:100]}\n")
    else:
        print(f"✅ HERMES COMPACTED & SUCCEEDED! Response: {resp_hermes[:100]}\n")

if __name__ == "__main__":
    asyncio.run(functional_test())
