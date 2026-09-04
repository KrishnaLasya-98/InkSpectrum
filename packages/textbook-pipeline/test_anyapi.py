from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

chat = ChatOpenAI(
    model="deepseek/deepseek-chat",
    base_url="https://api.anyapi.ai/v1",
    api_key="sk-QW3kaf3i_ywuquWbnQaDYw",
)

messages = [HumanMessage(content="Hello! Respond with just 'OK'")]

try:
    response = chat.invoke(messages)
    print(f"✅ SUCCESS: {response.content}")
except Exception as e:
    print(f"❌ ERROR: {e}")