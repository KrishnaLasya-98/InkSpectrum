"""Generate valid placeholder JPEGs for each scene using PIL."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os

VISUALS_DIR = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/visuals")
PUBLIC_DIR = Path("D:/new_video_pip/textbook-pipeline/remotion_renderer/public/visuals")

# Scene color themes matching the Remotion layout
SCENES = {
    "sec1_intro": ("#0c4a6e", "Welcome to Lesson 1", "🌊"),
    "sec2_question": ("#1e293b", "Question", "❓"),
    "sec3_worked_step_a": ("#1e293b", "Step 1", "🪜"),
    "sec4_worked_step_b": ("#1e293b", "Step 2", "🪜"),
    "sec5_worked_step_c": ("#1e293b", "Step 3", "🪜"),
    "sec6_worked_step_d": ("#1e293b", "Step 4", "🪜"),
    "sec7_answer_reveal": ("#14532d", "Answer Reveal", "✅"),
    "sec8_mcq": ("#1e293b", "Multiple Choice", "❓"),
    "secB_exercise1": ("#1e293b", "True or False", "✔️"),
    "sec2_question_a": ("#1e293b", "Question A", "❓"),
    "sec3_answer_a": ("#14532d", "Answer A", "✅"),
    "sec4_question_b": ("#1e293b", "Question B", "❓"),
    "sec5_answer_b": ("#14532d", "Answer B", "✅"),
    "sec6_question_c": ("#1e293b", "Question C", "❓"),
    "sec7_answer_c": ("#14532d", "Answer C", "✅"),
    "sec8_discussion": ("#1e293b", "Let's Discuss", "💭"),
    "sec9_greeting_mcq": ("#1e293b", "Greeting Practice", "👋"),
    "sec10_greeting_answer": ("#14532d", "Correct Greeting", "✅"),
}

WIDTH, HEIGHT = 1920, 1080

def generate_image(scene_id, bg_color, label, emoji):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to use a default font
    try:
        font_large = ImageFont.truetype("arial.ttf", 120)
        font_small = ImageFont.truetype("arial.ttf", 60)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Center the emoji
    draw.text((WIDTH // 2 - 60, 200), emoji, fill="white", font=font_large)
    # Center the label
    bbox = draw.textbbox((0, 0), label, font=font_small)
    text_w = bbox[2] - bbox[0]
    draw.text(((WIDTH - text_w) // 2, 600), label, fill="white", font=font_small)

    return img

print("Generating placeholder JPEGs...")
for scene_id, (bg, label, emoji) in SCENES.items():
    img = generate_image(scene_id, bg, label, emoji)
    img.save(VISUALS_DIR / f"{scene_id}.jpg", quality=85)
    img.save(PUBLIC_DIR / f"{scene_id}.jpg", quality=85)
    print(f"  ✓ {scene_id}.jpg")

print(f"\n✅ Generated {len(SCENES)} JPEGs")
