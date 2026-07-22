import os
import sys
from dotenv import load_dotenv

load_dotenv()
import litellm

litellm.api_key = os.getenv('DEEPSEEK_API_KEY')

print('Testing DeepSeek connection to deepseek-chat...')
try:
    response = litellm.completion(
        model='deepseek/deepseek-chat',
        messages=[{'role': 'user', 'content': 'Hello, are you alive? Reply in one sentence.'}]
    )
    print('\nSuccess! Model reply:')
    print(response.choices[0].message.content)
except Exception as e:
    print(f'\nError calling DeepSeek: {e}')
