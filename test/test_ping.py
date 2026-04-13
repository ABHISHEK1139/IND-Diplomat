import sys
import os
import asyncio
from pathlib import Path

# Provide pure correct scope for DIP_6 root
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.Layer4_Analysis.core.llm_client import AsyncLLMClient
from dotenv import load_dotenv
from test._support import script_log_path

load_dotenv()

openrouter_models = [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-coder:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "stepfun/step-3.5-flash:free",
    "z-ai/glm-4.5-air:free"
]

async def ping_models():
    client = AsyncLLMClient()
    client.local.provider = "openrouter"
    
    with open(script_log_path("ping_results.txt"), "w", encoding="utf-8") as f:
        f.write("--- PINGING ALL OPENROUTER MODELS ---\n\n")
        
        for model_id in openrouter_models:
            f.write(f"Pinging [ {model_id} ] ... ")
            f.flush()
            
            client.local.model = model_id
            resp = client.local._generate_openrouter(
                system_prompt="You are a ping testing bot.",
                user_prompt="Respond strictly with the single word: PONG",
                temperature=0.0,
                timeout=30,
                json_mode=False,
                max_tokens=10
            )
            
            if "LLM_ERROR" in resp:
                f.write(f"[FAILED] Error: {resp}\n")
            else:
                f.write(f"[SUCCESS] Response: {resp.strip()}\n")

if __name__ == "__main__":
    asyncio.run(ping_models())
