#!/usr/bin/env bash
cd /mnt/d/new_video_pip
source .venv/bin/activate
python3 packages/model-evaluator/run.py "$@"
