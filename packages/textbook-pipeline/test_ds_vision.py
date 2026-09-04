import os
from openai import OpenAI

api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

try:
    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash-vision-exp",
        messages=[{"role": "user", "content": "Describe what you can do."}]
    )
    print("DeepSeek Vision Success:", response.choices[0].message.content)
except Exception as e:
    print("DeepSeek Vision Failed:", e)
