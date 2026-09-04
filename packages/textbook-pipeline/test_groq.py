import os, json
from dotenv import load_dotenv
load_dotenv()

import openai

# Use Groq directly with raw openai client
client = openai.OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

print("Groq API key present:", bool(os.getenv("GROQ_API_KEY")))
print("Groq API key (first 10):", os.getenv("GROQ_API_KEY", "")[:10])

# Simple test first
try:
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "Say OK"}],
    )
    print("Simple test:", repr(resp.choices[0].message.content))
except Exception as e:
    print("Simple test error:", e)

# JSON test
try:
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a teacher. Output only valid JSON array."},
            {"role": "user", "content": 'Return JSON array: [{"id":"x","title":"test"}]'}
        ],
        response_format={"type": "json_object"},
    )
    print("JSON test:", repr(resp.choices[0].message.content))
except Exception as e:
    print("JSON test error:", e)