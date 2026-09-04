"""Analyze rendered MP4 video using Gemini Flash / AnyAPI Vision model.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in environment.")
    sys.exit(1)

genai.configure(api_key=api_key)

video_path = Path("D:/new_video_pip/textbook-pipeline/remotion_renderer/out.mp4")
if not video_path.exists():
    print(f"ERROR: Video not found at {video_path}")
    sys.exit(1)

print(f"Uploading video {video_path.name} to Gemini for visual verification...")
video_file = genai.upload_file(path=str(video_path))
print(f"Uploaded as: {video_file.uri}")

# Wait for video processing
import time
while video_file.state.name == "PROCESSING":
    print("Waiting for video processing...")
    time.sleep(5)
    video_file = genai.get_file(video_file.name)

if video_file.state.name == "FAILED":
    raise ValueError("Video processing failed on Gemini server.")

print("Video processed successfully. Asking Gemini to inspect contents...")

model = genai.GenerativeModel(model_name="gemini-2.5-flash")

prompt = """
Please analyze this rendered educational lecture video.
1. What text or title is displayed on the screen?
2. Is this the full chapter 1 or just a placeholder title card?
3. Evaluate the visual styling, layout, and readability.
"""

response = model.generate_content([video_file, prompt])
print("\n=== GEMINI VISION ANALYSIS ===")
print(response.text)
