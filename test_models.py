from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv()

client = Groq(api_key=os.getenv('GROQ_API_KEY'))

for model in ['qwen/qwen3.8-27b', 'openai/gpt-oss-120b', 'groq/compound']:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': 'You control a browser. Return ONLY valid JSON, no explanation, no markdown.'},
                {'role': 'user', 'content': 'Task: Go to google.com. Return the next action as JSON with keys: type, url, reasoning'}
            ],
            temperature=0.2,
            max_tokens=200,
        )
        print(f"\n=== {model} ===")
        print(resp.choices[0].message.content)
    except Exception as e:
        print(f"\n=== {model} === ERROR: {e}")
