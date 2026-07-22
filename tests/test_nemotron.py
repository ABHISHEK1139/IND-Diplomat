import os
import sys
from dotenv import load_dotenv
load_dotenv()
import litellm

litellm.api_key = os.getenv('OPENROUTER_API_KEY')

print('Testing OpenRouter connection to nvidia/nemotron-3-ultra-550b-a55b:free...')
try:
    response = litellm.completion(
        model='openrouter/nvidia/nemotron-3-ultra-550b-a55b:free',
        messages=[{'role': 'user', 'content': 'Hello, are you alive? Reply in one sentence.'}]
    )
    print('\nSuccess! Model reply:')
    print(response.choices[0].message.content)
except Exception as e:
    print(f'\nError calling OpenRouter: {e}')
