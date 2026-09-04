"""Example test setup."""

import pytest


def test_imports():
    import cv2
    import numpy
    import torch
    import transformers
    import moviepy

    assert all([cv2, numpy, torch, transformers, moviepy])


def test_venv_active():
    import sys
    assert ".venv" in sys.prefix or ".venv" in sys.executable
