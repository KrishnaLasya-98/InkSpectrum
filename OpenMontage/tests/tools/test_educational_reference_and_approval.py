from __future__ import annotations

import hashlib
import json

import pytest
from PIL import Image

from tools.graphics.import_native_codex_reference import import_reference
from tools.video.seal_educational_motion_batch import seal
from tools.video.submit_educational_motion_batch import validate_sealed_batch_approval


def test_native_codex_import_is_local_durable_and_no_wrapper(tmp_path):
    project = tmp_path / "chapter"; (project / "assets/images").mkdir(parents=True)
    prompt = "A source-faithful child-friendly historical scene without text."
    output = (project / "assets/images/reference.png").resolve()
    request = project / "artifacts/reference.native-codex-request.json"
    request.parent.mkdir()
    request.write_text(json.dumps({
        "version":"1.0", "provider":"native_codex", "target":"reference",
        "status":"awaiting_native_codex_generation", "prompt":prompt,
        "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
        "output_path":str(output),
    }))
    source = tmp_path / "download.png"
    Image.new("RGB", (1024, 768), "navy").save(source)
    result = import_reference(project, request, source)
    assert result["status"] == "imported" and result["paid_wrapper_used"] is False
    assert output.is_file() and request.with_suffix(".result.json").is_file()
    with pytest.raises(FileExistsError):
        import_reference(project, request, source)


def test_sealed_batch_detects_post_review_edit(tmp_path):
    project = tmp_path / "chapter"
    (project / "artifacts").mkdir(parents=True)
    (project / "assets/images").mkdir(parents=True)
    reference = project / "assets/images/ref.png"
    Image.new("RGB", (1024, 768), "green").save(reference)
    plan = {"sections":[{"section_id":"s01", "source_block_ids":["b01"]}]}
    (project / "artifacts/educational_plan.json").write_text(json.dumps(plan))
    ref_review = project / "artifacts/reference-review.json"
    ref_review.write_text(json.dumps({"review_rounds":2}))
    batch = project / "motion-batch-1.json"
    payload = {"operation":"image_to_video", "shots":[{
        "shot_id":"shot-1", "section_id":"s01", "reference_image":"assets/images/ref.png",
        "prompt":"A sufficiently detailed source faithful prompt with no text labels logos or modern objects anywhere.",
    }]}
    batch.write_text(json.dumps(payload))
    review = project / "artifacts/motion-batch-01-pre-generation-review.json"
    review.write_text(json.dumps({
        "reference_review":"artifacts/reference-review.json",
        "checks":{"unique_shot_ids":True,"unique_reference_hashes":True,
                  "source_matched_sections":True,"no_generated_text_requested":True,
                  "authored_lesson2_labels_retained":True},
    }))
    seal(project, batch)
    sealed = validate_sealed_batch_approval(project, batch, payload, plan)
    assert sealed["approved_shots"][0]["source_block_ids"] == ["b01"]
    batch.write_text(json.dumps({**payload, "changed":True}))
    with pytest.raises(ValueError, match="changed"):
        validate_sealed_batch_approval(project, batch, json.loads(batch.read_text()), plan)
