import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Test Groq
print("Testing Groq (gpt-oss-120b)...")
try:
    groq_client = ChatOpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
        temperature=0.3,
    )
    response = groq_client.invoke([HumanMessage(content="Say OK")])
    print(f"Groq response: '{response.content}'")
except Exception as e:
    print(f"Groq error: {e}")

# Test AnyAPI with Gemma
print("\nTesting AnyAPI (Gemma)...")
try:
    anyapi_client = ChatOpenAI(
        api_key=os.getenv("ANYAPI_API_KEY"),
        base_url="https://api.anyapi.ai/v1",
        model="google/gemma-4-26b-a4b-it:free",
        temperature=0.3,
    )
    response = anyapi_client.invoke([HumanMessage(content="Say OK")])
    print(f"Gemma response: '{response.content}'")
except Exception as e:
    print(f"Gemma error: {e}")

# Test AnyAPI with DeepSeek
print("\nTesting AnyAPI (DeepSeek)...")
try:
    anyapi_client = ChatOpenAI(
        api_key=os.getenv("ANYAPI_API_KEY"),
        base_url="https://api.anyapi.ai/v1",
        model="deepseek/deepseek-chat",
        temperature=0.3,
    )
    response = anyapi_client.invoke([HumanMessage(content="Say OK")])
    print(f"DeepSeek response: '{response.content}'")
except Exception as e:
    print(f"DeepSeek error: {e}")