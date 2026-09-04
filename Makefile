.PHONY: help install install-dev test lint format clean run-edugen run-video-explainer run-textbook-pipeline

help:
	@echo "Available targets:"
	@echo "  install          - Install dependencies"
	@echo "  install-dev      - Install dev dependencies"
	@echo "  test             - Run tests"
	@echo "  lint             - Run linters"
	@echo "  format           - Format code"
	@echo "  clean            - Clean temp files"
	@echo "  run-edugen       - Run EduGen module"
	@echo "  run-video-explainer - Run video explainer"
	@echo "  run-textbook-pipeline - Run textbook pipeline"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install black ruff pytest pytest-cov

test:
	python -m pytest tests/ -v

lint:
	ruff check src/ tests/ EduGen/ video_explainer/ textbook-pipeline/
	black --check src/ tests/ EduGen/ video_explainer/ textbook-pipeline/

format:
	black src/ tests/ EduGen/ video_explainer/ textbook-pipeline/
	ruff check --fix src/ tests/ EduGen/ video_explainer/ textbook-pipeline/

clean:
	del /s /q temp\* 2>nul
	del /s /q output\* 2>nul
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	for /d /r . %%d in (.pytest_cache) do @if exist "%%d" rd /s /q "%%d"
	for /d /r . %%d in (.ruff_cache) do @if exist "%%d" rd /s /q "%%d"

run-edugen:
	python src/run.py edugen

run-video-explainer:
	python src/run.py video_explainer

run-textbook-pipeline:
	python src/run.py textbook_pipeline
