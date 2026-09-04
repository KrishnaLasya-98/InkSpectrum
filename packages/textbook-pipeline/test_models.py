from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

models_to_test = [
    "deepseek/deepseek-chat",           # Router
    "deepseek/deepseek-v4-flash-vision-exp",  # Vision
    "anthropic/claude-sonnet-5",        # Analyzer
    "anthropic/claude-sonnet-4.6",      # Scriptwriter
    "anthropic/claude-sonnet-4.5",      # Engineer
]

for model in models_to_test:
    chat = ChatOpenAI(
        model=model,
        base_url="https://api.anyapi.ai/v1",
        api_key="sk-QW3kaf3i_ywuquWbnQaDYw",
    )
    try:
        response = chat.invoke([HumanMessage(content="OK")])
        print(f"✅ {model}: {response.content[:30]}")
    except Exception as e:
        print(f"❌ {model}: {e}")