"""Contract tests for lib.checkpoint.Checkpoint and CheckpointStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.checkpoint import Checkpoint, CheckpointStore, new_run_id


class TestCheckpoint:
    def test_round_trip(self, tmp_path: Path):
        store = CheckpointStore(root=tmp_path)
        cp = Checkpoint(
            pipeline_id="english_classroom",
            run_id="run-1",
            stage="research",
            artifacts=["chapter.json"],
            cost_usd=0.01,
            metadata={"section_count": 20},
        )
        store.write(cp)

        loaded = store.read("english_classroom", "run-1", "research")
        assert loaded is not None
        assert loaded.stage == "research"
        assert loaded.cost_usd == 0.01
        assert loaded.metadata["section_count"] == 20

    def test_has_stage(self, tmp_path: Path):
        store = CheckpointStore(root=tmp_path)
        assert not store.has_stage("p", "r", "s")
        store.write(Checkpoint("p", "r", "s"))
        assert store.has_stage("p", "r", "s")

    def test_completed_stages_ordered(self, tmp_path: Path):
        store = CheckpointStore(root=tmp_path)
        run_id = new_run_id()
        for stage in ["script", "research", "assets", "compose"]:
            store.write(Checkpoint("english_classroom", run_id, stage))
        stages = store.completed_stages("english_classroom", run_id)
        assert stages == ["assets", "compose", "research", "script"]

    def test_read_missing_returns_none(self, tmp_path: Path):
        store = CheckpointStore(root=tmp_path)
        assert store.read("nope", "nope", "nope") is None
