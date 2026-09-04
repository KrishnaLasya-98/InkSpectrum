import os
from openai import OpenAI

api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

try:
    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash-0731",
        messages=[{"role": "user", "content": "Say hello!"}]
    )
    print("DeepSeek Flash Success:", response.choices[0].message.content)
except Exception as e:
    print("DeepSeek Flash Failed:", e)
