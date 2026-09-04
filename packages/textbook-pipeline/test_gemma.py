import os
from openai import OpenAI

api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

try:
    response = client.chat.completions.create(
        model="google/gemma-4-26b-a4b-it:free",
        messages=[{"role": "user", "content": "Say hello!"}]
    )
    print("Gemma Free Model Success:", response.choices[0].message.content)
except Exception as e:
    print("Gemma Free Model Failed:", e)
