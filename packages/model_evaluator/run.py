#!/usr/bin/env python3
"""Standalone runner for model-evaluator CLI."""
import sys
from pathlib import Path

PACKAGES_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGES_ROOT))

from model_evaluator.cli import app

if __name__ == "__main__":
    app()
