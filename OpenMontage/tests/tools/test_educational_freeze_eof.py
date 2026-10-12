from types import SimpleNamespace
from tools.analysis.educational_clip_qa import _filter_events


def test_freeze_continuing_to_eof_is_not_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr("tools.analysis.educational_clip_qa.shutil.which", lambda name: name)
    monkeypatch.setattr("tools.analysis.educational_clip_qa.subprocess.run", lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stderr="[freezedetect] freeze_start: 0.0\n"))
    durations, error = _filter_events(tmp_path / "still.mp4", "freezedetect=n=0.003:d=1.5", r"freeze_duration:\s*([0-9.]+)", media_duration=5.0)
    assert error is None
    assert durations == [5.0]
