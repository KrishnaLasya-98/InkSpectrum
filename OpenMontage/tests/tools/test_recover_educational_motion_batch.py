import json
from pathlib import Path

from tools.video.modelslab_motion_budget import MotionBudget
from tools.video.recover_educational_motion_batch import recover


class _FailedResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "failed"}


def test_provider_failure_becomes_terminal_and_releases_budget(tmp_path, monkeypatch):
    project = tmp_path / "project"
    output = project / "assets" / "video" / "motion-batch-01" / "shot.mp4"
    output.parent.mkdir(parents=True)
    batch = project / "assets" / "video" / "motion-batch-01.json"
    batch.write_text(
        json.dumps({"shots": [{"shot_id": "shot"}]}), encoding="utf-8"
    )
    sidecar = Path(str(output) + ".modelslab-job.json")
    sidecar.write_text(
        json.dumps(
            {
                "provider": "modelslab",
                "status": "submitted",
                "request_id": "123",
                "poll_endpoint": "video",
                "model_id": "wan2.2",
                "operation": "text_to_video",
                "output_path": str(output),
                "submitted_at_unix": 9000,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MODELSLAB_API_KEY", "test-only")
    monkeypatch.setattr(
        "tools.video.recover_educational_motion_batch.requests.post",
        lambda *args, **kwargs: _FailedResponse(),
    )

    report = recover(project, batch)

    assert report["jobs"][0]["status"] == "terminal_failed"
    assert json.loads(sidecar.read_text(encoding="utf-8"))["status"] == "terminal_failed"
    budget = MotionBudget(tmp_path / "budget", tmp_path, clock=lambda: 10000)
    assert budget.snapshot()["active"] == 0
