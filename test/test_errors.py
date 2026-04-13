import sys
import os
import asyncio
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.Layer4_Analysis.core.llm_client import AsyncLLMClient
from dotenv import load_dotenv
from test._support import script_log_path

load_dotenv()

models_to_test = [
    ("nousresearch/hermes-3-llama-3.1-405b:free", 110000),
    ("qwen/qwen3-coder-480b-a35b:free", 90000),
    ("z-ai/glm-4.5-air:free", 30000),
    ("stepfun/step-3.5-flash:free", 30000),
    ("nvidia/nemotron-3-super:free", 15000)
]

async def check_errors():
    client = AsyncLLMClient()
    with open(script_log_path("error_log.txt"), "w", encoding="utf-8") as f:
        for model_id, char_load in models_to_test:
            client.local.model = model_id
            client.local.provider = "openrouter"
            
            huge_prompt = "apple " * (char_load // 6)
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"Summarize:\n{huge_prompt}"}],
                "max_tokens": 10
            }
            
            headers = {
                "Authorization": f"Bearer {client.local.openrouter_api_key}",
                "Content-Type": "application/json",
            }
            
            f.write(f"\n--- Testing {model_id} ({char_load} chars) ---\n")
            try:
                # We bypass the auto-compactor cleanly to see the RAW OpenRouter API rejection
                response = requests.post(
                    client.local.url if client.local.url else "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                f.write("SUCCESS (No error)\n")
            except requests.exceptions.RequestException as e:
                f.write(f"ERROR: {response.status_code}\n")
                f.write(f"DETAILS: {response.text}\n")

if __name__ == "__main__":
    asyncio.run(check_errors())
