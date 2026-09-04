import os
from openai import OpenAI

api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

# Test with deepseek model
try:
    response = client.chat.completions.create(
        model="deepseek/deepseek-chat",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("DeepSeek model OK:", response.choices[0].message.content)
except Exception as e:
    print("DeepSeek model failed:", e)
