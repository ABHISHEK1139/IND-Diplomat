import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    import litellm
except ImportError:
    print("litellm not installed locally, installing it temporarily...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "litellm"])
    import litellm

# Explicitly test openrouter key
litellm.api_key = os.getenv('OPENROUTER_API_KEY')

print('Testing OpenRouter connection to tencent/hy3:free...')
try:
    response = litellm.completion(
        model='openrouter/tencent/hy3:free',
        messages=[{'role': 'user', 'content': 'Hello, are you alive? Reply in one sentence.'}]
    )
    print('\nSuccess! Model reply:')
    print(response.choices[0].message.content)
except Exception as e:
    print(f'\nError calling OpenRouter: {e}')
