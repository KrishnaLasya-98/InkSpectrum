import os
from openai import OpenAI

api_key = "sk-mOEOUjQ8Itw2HEcSX-73cw"
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anyapi.ai/v1"
)

try:
    models = client.models.list()
    print("Available models:")
    for m in models:
        print("  -", m.id)
except Exception as e:
    print("Failed to list models:", e)
