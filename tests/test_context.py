import sys
import os
import asyncio
from pathlib import Path

# Fix relative pathing so it executes inside DIP_6
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer4_Analysis.core.llm_client import AsyncLLMClient
from dotenv import load_dotenv

load_dotenv()

models_to_test = [
    ("nousresearch/hermes-3-llama-3.1-405b:free", 110000),  # Test >100k
    ("qwen/qwen3-coder-480b-a35b:free", 90000),             # Test >80k
    ("z-ai/glm-4.5-air:free", 30000),                       # Test >24k
    ("stepfun/step-3.5-flash:free", 30000),                 # Test >24k
    ("nvidia/nemotron-3-super:free", 15000)                 # Test >12k
]

async def stress_test():
    client = AsyncLLMClient()
    print("--- OPENROUTER CONTEXT LIMIT TESTS ---\n")
    
    for model_id, char_load in models_to_test:
        client.local.model = model_id
        client.local.provider = "openrouter"
        
        print(f"Testing {model_id} with {char_load} characters...")
        
        huge_prompt = "apple " * (char_load // 6)
        payload = f"Summarize everything below:\n{huge_prompt}\nAnd the secret word is Omega."
        
        # Bypass Async interface since we're manipulating client.local internally and directly
        resp = client.local._generate_openrouter(
            system_prompt="Extract the secret word accurately.",
            user_prompt=payload,
            temperature=0.0,
            timeout=120,
            json_mode=False,
            max_tokens=64
        )
        
        if "LLM_ERROR:" in resp:
            print(f"  ❌ FAILED: {resp[:100]}\n")
        else:
            print(f"  ✅ SUCCESS! Response: {resp[:100]}\n")

if __name__ == "__main__":
    asyncio.run(stress_test())
