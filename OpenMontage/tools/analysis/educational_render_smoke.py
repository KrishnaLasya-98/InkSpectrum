"""Build a no-provider 24s shared-composer fixture with audible timing markers.

This tests rendering, not narration quality or speech alignment. Its subtitles
are synthetic test cues; never publish this fixture as educational content.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--exercise", action="store_true", help="Include a timed question/pause/answer UI test")
    parser.add_argument("--matching", action="store_true", help="Test source-style matching columns and timed connections")
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    if destination.exists():
        raise ValueError("Use a fresh smoke workspace; existing files are not overwritten")
    destination.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("fixture", root / "tests/tools/test_educational_hyperframes_composer.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    data = fixture._inputs(destination)
    data["educational_plan"].update(grade=1, chapter_number=8)
    data["educational_plan"]["sections"][1].update(
        source_block_type="we_learn", title="We Learn",
        source_questions=["Do you have any pet animals?", "How do you look after your pet animal?"])
    data["educational_plan"]["sections"][2].update(
        source_block_type="concept", title="Animals are living beings",
        current_source_idea="Animals are living beings like us which are found in nature.")
    for i, (clip, audio, section, span) in enumerate(zip(data["clip_manifest"],
            data["narration_manifest"]["segments"], data["educational_plan"]["sections"],
            data["multimedia_sync_plan"]["timeline"])):
        # Replace intentionally invalid unit-test media with real diagnostic media.
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=size=960x540:rate=30", "-t", "8", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", clip["output_path"]], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency={440+i*110}:duration=8:sample_rate=48000",
                        "-af", "volume=0.06,volume=0:enable='between(t,1,5)'",
                        audio["audio_path"]], check=True)
        clip["duration_seconds"] = audio["duration_seconds"] = 8
        audio.update(heading_duration_seconds=1, body_start_seconds=5,
                     heading_holds=[{"title": section["title"], "start_seconds": 1, "end_seconds": 5}])
        span.update(start_seconds=i*8, end_seconds=(i+1)*8,
                    audio_duration_seconds=8, clip_duration_seconds=8)
    for word in data["word_captions"]:
        word["startMs"] *= 4
        word["endMs"] *= 4
    data["multimedia_sync_plan"]["total_duration_seconds"] = 24
    if args.exercise or args.matching:
        data["educational_plan"]["sections"][2].update(
            source_block_type="assessment", title="Choose the colour",
            teaching_contract={"questions": [{"question": "Which colour?", "answer": "Blue.",
                "qa_format": "mcq", "choices": ["Red", "Blue"], "correct_index": 1,
                "thinking_pause_seconds": .8}]})
        data["word_captions"] = [w for w in data["word_captions"] if w["startMs"] < 16000]
        data["word_captions"].extend([
            {"word": "Choose", "startMs":16000,"endMs":16300},
            {"word": "the", "startMs":16300,"endMs":16500},
            {"word": "colour.", "startMs":16500,"endMs":16900},
            {"word": "Which", "startMs":21000,"endMs":21300},
            {"word": "colour?", "startMs":21300,"endMs":21600},
            {"word": "Blue.", "startMs":22400,"endMs":22900},
        ])
        data["narration_manifest"]["segments"][2]["heading_holds"][0]["title"] = "Choose the colour"
        if args.matching:
            question = data["educational_plan"]["sections"][2]["teaching_contract"]["questions"][0]
            question.update(question="Match the sounds.", answer="Cat meows. Dog barks.", qa_format="matching",
                exercise_visual={"kind": "matching",
                    "left": [{"id":"cat", "text":"Cat"}, {"id":"dog", "text":"Dog"}],
                    "right": [{"id":"bark", "text":"Barks"}, {"id":"meow", "text":"Meows"}],
                    "matches": [{"left_id":"cat", "right_id":"meow", "cue_text":"Cat meows."},
                                {"left_id":"dog", "right_id":"bark", "cue_text":"Dog barks."}]})
            question.pop("choices", None)
            data["educational_plan"]["sections"][2]["title"] = "Match the sounds"
            data["narration_manifest"]["segments"][2]["heading_holds"][0]["title"] = "Match the sounds"
            data["word_captions"] = [w for w in data["word_captions"] if w["startMs"] < 16000]
            for text, at in [("Match",16000),("the",16300),("sounds.",16600),
                             ("Match",21000),("the",21200),("sounds.",21400),
                             ("Cat",22400),("meows.",22600),("Dog",23000),("barks.",23200)]:
                data["word_captions"].append({"word":text,"startMs":at,"endMs":at+200})
    result = fixture.EducationalHyperFramesComposer().execute(data)
    if not result.success:
        raise RuntimeError(result.error)
    (destination / "smoke-inputs.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"workspace": result.data["workspace_path"],
                      "boundary": "Synthetic tone/caption test; no speech or textbook QA"}))


if __name__ == "__main__":
    main()
