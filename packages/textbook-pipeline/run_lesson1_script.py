import json
import sys
from pathlib import Path

PROJECT_ROOT = Path("D:/new_video_pip/textbook-pipeline").absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.environment import initialize_environment
initialize_environment()

from lib.script_writer.generator import ScriptWriter
from schemas import ChapterNode, SectionType, SectionNode

# Load the blueprint
blueprint_path = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/pymupdf_blueprint.json")
with open(blueprint_path) as f:
    data = json.load(f)

chapter = ChapterNode(**data)
print(f"Loaded chapter: {chapter.title} ({chapter.subject.value} Grade {chapter.grade})")

# Lesson 1 real content is in sec_19 (At the Beach story) + sec_20 (True/False) + sec_21 (Comprehension)
# These contain the actual story and exercises
target_ids = ["sec_19", "sec_20", "sec_21"]
target_sections = [s for s in chapter.sections if s.id in target_ids]

# Fallback: if not found, use first 3 sections
if not target_sections:
    target_sections = chapter.sections[:3]

print(f"\n=== Processing Lesson 1 content ({len(target_sections)} sections) ===")
for s in target_sections:
    print(f"  - {s.id}: {s.title} (type={s.type})")

# Build mini-chapter with just Lesson 1 sections
from schemas import ChapterNode as CN
mini_chapter = CN(
    id=chapter.id,
    number=1,
    title="Lesson 1 - At the Beach",
    subject=chapter.subject,
    grade=chapter.grade,
    textbook_id=chapter.textbook_id,
    sections=target_sections,
    page_range=chapter.page_range,
    source_pdf=Path(chapter.source_pdf),
)

# Initialize ScriptWriter (Groq)
writer = ScriptWriter()
print("\nGenerating scripts for Lesson 1...")

scenes = writer.generate_chapter_script(mini_chapter)

print(f"\n=== GENERATED {len(scenes)} SCENES ===")
for i, scene in enumerate(scenes):
    print(f"\nScene {i+1}: {scene.id}")
    print(f"  Title: {scene.title}")
    print(f"  Section: {scene.section_ref}")
    total_vol = sum(vl.duration_seconds for vl in scene.voiceover_lines)
    print(f"  Voiceover length: {len(scene.voiceover_lines)} lines ({total_vol:.1f}s)")
    print(f"  Voiceover: {scene.voiceover_lines[0].text[:80]}...")
    print(f"  Steps: {len(scene.scene_steps)}")
    for step in scene.scene_steps[:3]:
        print(f"    [{step.at}s] {step.type.value} {step.text[:40] if step.text else ''}")

# Save output
output_path = Path("D:/new_video_pip/textbook-pipeline/projects/english_class1_pymupdf/lesson1_script.json")
with open(output_path, "w") as f:
    json.dump([s.model_dump() for s in scenes], f, indent=2)
print(f"\n✅ Saved to: {output_path}")