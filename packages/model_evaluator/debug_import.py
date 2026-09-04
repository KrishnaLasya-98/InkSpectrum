#!/usr/bin/env python3
"""Standalone runner for model-evaluator CLI using absolute path import."""
import sys
import importlib.util
from pathlib import Path

BASE = Path("/mnt/d/new_video_pip/packages")
sys.path.insert(0, str(BASE))

spec = importlib.util.find_spec("model_evaluator")
print("DEBUG:", spec)
