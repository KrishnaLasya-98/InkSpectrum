import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# Test AnyAPI with user's new key
api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

try:
    response = client.chat.completions.create(
        model="auto:free",
        messages=[{"role": "user", "content": "Say hello and confirm API key works."}]
    )
    print("AnyAPI Test Success:", response.choices[0].message.content)
except Exception as e:
    print("AnyAPI Test Failed:", e)
