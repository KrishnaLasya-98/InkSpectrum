import os, json
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

client = ChatOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-120b",
    temperature=0.3,
)

system_prompt = """You are an expert teacher creating educational video scripts.

SCENE STEP VOCABULARY (constrained primitives - ONLY these types allowed):
- TITLE, SUBTITLE, TEXT, CLEAR

OUTPUT FORMAT: Valid JSON array of ScriptScene objects matching this schema:
{"id": "sec1_intro", "title": "Introduction", "voiceover_lines": [{"text": "Welcome", "duration_seconds": 5.0, "pause_after": 0.5}], "scene_steps": [{"at": 0, "type": "TITLE", "text": "Lesson 1", "size": "xl", "color": "saffron"}], "duration_seconds": 10.0, "section_ref": "sec_1", "notes": "test"}

CRITICAL: Use ONLY SceneStepType enum values. NO arbitrary fields. Timing 'at' in seconds."""

user_prompt = """Generate theory script for this section:

SECTION: Lesson 1 - At the Beach
TYPE: THEORETICAL
CONTENT: Varun and Vidya are at a beach with their parents. They build a sandcastle together.
GRADE: 1
SUBJECT: english

Use TITLE for lesson name, TEXT for explanations. Output JSON array."""

response = client.invoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=user_prompt)
])

print("=== RAW RESPONSE ===")
print(repr(response.content))
print()
print("=== LENGTH ===")
print(len(response.content))
print()
print("=== TRY JSON PARSE ===")
try:
    parsed = json.loads(response.content)
    print("SUCCESS:", type(parsed), len(parsed) if isinstance(parsed, list) else "")
except Exception as e:
    print("FAIL:", e)