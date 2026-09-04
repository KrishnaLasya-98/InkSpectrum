"""Transition generator for scene changes."""

from __future__ import annotations

from typing import Dict, Optional


class TransitionGenerator:
    """Generates transition configurations."""

    TRANSITIONS = {
        "cut": {"duration": 0.0},
        "fade": {"duration": 0.5},
        "cross_dissolve": {"duration": 0.3},
    }

    def get_transition(self, name: str, override_duration: Optional[float] = None) -> Dict[str, float]:
        if name not in self.TRANSITIONS:
            name = "cut"
        config = dict(self.TRANSITIONS[name])
        if override_duration is not None:
            config["duration"] = override_duration
        return config
