"""Tests for the subject config loader.

Verifies that all Phase 1 subjects have valid config.json files
and that the SubjectConfig round-trip works through Pydantic.
"""

from __future__ import annotations

import pytest

from data.subjects.loader import (
    available_subjects,
    is_subject_available,
    load_subject_config,
    reset_cache,
)
from schemas import Subject


# Ensure cache is fresh for each test
@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


class TestAvailableSubjects:
    def test_all_phase1_subjects_available(self):
        """All 4 Phase 1 subjects must have a config.json on disk."""
        available = available_subjects()
        assert "english" in available
        assert "math" in available
        assert "science" in available
        assert "social" in available

    def test_gk_not_available_yet(self):
        """GK config.json must NOT exist yet (Phase 2 deferred)."""
        available = available_subjects()
        assert "gk" not in available

    def test_phase1_count(self):
        """Exactly 4 subjects available at this stage."""
        assert len(available_subjects()) == 4


class TestSubjectConfigLoading:
    @pytest.mark.parametrize("subject", [
        Subject.ENGLISH,
        Subject.MATH,
        Subject.SCIENCE,
        Subject.SOCIAL,
    ])
    def test_subject_config_loads(self, subject: Subject):
        """Each Phase 1 subject's config.json validates against SubjectConfig."""
        cfg = load_subject_config(subject)
        assert cfg.subject == subject
        assert cfg.display_name
        assert cfg.default_voice
        assert cfg.primary_color.startswith("#")
        assert cfg.scene_types is not None
        assert len(cfg.scene_types) > 0

    def test_math_has_equation_patterns(self):
        """Math config must include equation detection patterns."""
        cfg = load_subject_config(Subject.MATH)
        assert cfg.equation_detection_patterns is not None
        assert len(cfg.equation_detection_patterns) > 0

    def test_english_has_reading_pace(self):
        """English config must include grade-specific reading pace."""
        cfg = load_subject_config(Subject.ENGLISH)
        assert cfg.reading_pace_wpm is not None
        # All 4 grade bands present
        assert "grade_1_2" in cfg.reading_pace_wpm
        assert "grade_3_5" in cfg.reading_pace_wpm
        assert "grade_6_8" in cfg.reading_pace_wpm
        assert "grade_9_10" in cfg.reading_pace_wpm

    def test_social_has_sub_themes(self):
        """Social config distinguishes social_studies vs evs sub_themes."""
        cfg = load_subject_config(Subject.SOCIAL)
        assert cfg.sub_themes is not None
        assert "social_studies" in cfg.sub_themes
        assert "evs" in cfg.sub_themes

    def test_subject_not_available_raises(self, tmp_path, monkeypatch):
        """Loading a missing config should raise FileNotFoundError."""
        # Use a temp dir that has no configs
        import data.subjects.loader as loader_mod
        monkeypatch.setattr(loader_mod, "_DATA_DIR", tmp_path)
        loader_mod.load_subject_config.cache_clear()
        with pytest.raises(FileNotFoundError):
            load_subject_config(Subject.ENGLISH)
        # restore
        loader_mod.load_subject_config.cache_clear()


class TestIsSubjectAvailable:
    def test_phase1_subjects_available(self):
        assert is_subject_available(Subject.ENGLISH) is True
        assert is_subject_available(Subject.MATH) is True
        assert is_subject_available(Subject.SCIENCE) is True
        assert is_subject_available(Subject.SOCIAL) is True