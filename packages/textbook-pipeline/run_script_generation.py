import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/new_video_pip/textbook-pipeline").absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.environment import initialize_environment
initialize_environment()

from lib.script_writer.generator import generate_chapter_script
from schemas import ChapterNode

# Load the blueprint
blueprint_path = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/pymupdf_blueprint.json")
with open(blueprint_path) as f:
    data = json.load(f)

chapter = ChapterNode(**data)
print(f"Loaded chapter: {chapter.title} ({chapter.subject.value} Grade {chapter.grade})")
print(f"Sections: {len(chapter.sections)}")

# Generate script
print("\nGenerating script...")
scenes = generate_chapter_script(chapter)

print(f"\nGenerated {len(scenes)} scenes")
for i, scene in enumerate(scenes[:5]):
    print(f"\n  Scene {i+1}: {scene.scene_id}")
    print(f"    Type: {scene.section_type}")
    print(f"    Narration: {scene.narration[:100]}...")
    print(f"    Visual: {scene.visual_plan.get('type', 'N/A')}")

# Save output
output_path = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/chapter_script.json")
with open(output_path, "w") as f:
    json.dump([s.model_dump() for s in scenes], f, indent=2)
print(f"\nSaved to: {output_path}")