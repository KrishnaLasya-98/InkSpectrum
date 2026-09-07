.PHONY: help install install-dev setup test contracts qa eval lint format clean pipeline list-tools check-deps

help:
	@echo "InkSpectrum Makefile"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install runtime dependencies"
	@echo "  install-dev      Install dev dependencies (ruff, black, pytest)"
	@echo "  setup            Create venv and install everything"
	@echo ""
	@echo "Tests:"
	@echo "  test             Run all tests"
	@echo "  contracts        Run contract tests (BaseTool, registry, schemas)"
	@echo "  qa               Run QA integration tests (real APIs)"
	@echo "  eval             Run eval harness (golden scenarios)"
	@echo ""
	@echo "Quality:"
	@echo "  lint             Run ruff + black"
	@echo "  format           Auto-format code"
	@echo "  check-deps       Check tool dependencies (FFmpeg, env vars, packages)"
	@echo "  list-tools       List all registered tools"
	@echo ""
	@echo "Pipeline:"
	@echo "  pipeline PIPELINE=<name>   Run a pipeline (smoke test if no input given)"
	@echo "  smoke            Run framework_smoke pipeline"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Remove temp files, caches"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install black ruff pytest pytest-cov jsonschema pyyaml pydantic

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -e packages/textbook-pipeline/ -e packages/model-evaluator/ && pip install -r requirements.txt

test:
	python -m pytest tests/ packages/textbook-pipeline/tests/ -v

contracts:
	python -m pytest tests/contracts/ -v

qa:
	python -m pytest tests/qa/ -v

eval:
	python -m pytest tests/eval/ -v

lint:
	ruff check lib/ tools/ tests/ packages/textbook-pipeline/src/ packages/textbook-pipeline/tests/
	black --check lib/ tools/ tests/ packages/textbook-pipeline/src/ packages/textbook-pipeline/tests/

format:
	black lib/ tools/ tests/ packages/textbook-pipeline/src/ packages/textbook-pipeline/tests/
	ruff check --fix lib/ tools/ tests/ packages/textbook-pipeline/src/ packages/textbook-pipeline/tests/

clean:
	python -c "import shutil, glob; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True)]; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/.pytest_cache', recursive=True)]; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/.ruff_cache', recursive=True)]"

list-tools:
	python -c "from lib.tool_registry import all_tools; [print(f'{t.metadata.name:30s} {t.metadata.capability:20s} {t.metadata.runtime.value:10s} cost=${t.metadata.estimated_cost_usd}') for t in all_tools()]"

check-deps:
	python -c "from lib.tool_registry import all_tools; [print(t.metadata.name, '->', t.describe()['missing_dependencies'] or 'OK') for t in all_tools()]"

smoke:
	python -c "from lib.pipeline_loader import load_manifest; m = load_manifest('pipeline_defs/framework_smoke.yaml'); print(f'Pipeline: {m.name} ({len(m.stages)} stages)'); [print(f'  - {s.name}: {s.skill}') for s in m.stages]"

pipeline:
	@if [ -z "$(PIPELINE)" ]; then echo "Usage: make pipeline PIPELINE=<name>"; exit 1; fi
	@echo "Running pipeline: $(PIPELINE)"
	python -m ink_orchestrator --pipeline pipeline_defs/$(PIPELINE).yaml
