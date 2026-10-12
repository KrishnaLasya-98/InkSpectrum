import json

import pytest

from tools.analysis.prepare_motion_batch_review import run


def project(tmp_path):
    p = tmp_path / "chapter"
    (p / "assets/video").mkdir(parents=True)
    (p / "artifacts").mkdir()
    (p / "assets/video/motion-batch-01.json").write_text(json.dumps({"shots": [
        {"shot_id": "shot-a", "section_id": "section-a"}]}), encoding="utf-8")
    return p


def test_missing_recovered_clip_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        run(project(tmp_path), 1)


def test_reviewed_decision_is_never_overwritten(tmp_path):
    p = project(tmp_path)
    review = p / "artifacts/motion-batch-01-review.json"
    review.write_text('{"status":"reviewed","clips":[]}', encoding="utf-8")
    with pytest.raises(FileExistsError):
        run(p, 1)
    assert json.loads(review.read_text(encoding="utf-8"))["status"] == "reviewed"
