"""Pipeline logging system with TQDM progress visualization.

Provides structured logging for the video generation pipeline with:
- Precise ISO 8601 timestamps
- JSONL event stream + human-readable log
- TQDM progress bars with tqdm.write() compatibility
- Asset tracking with duration/size metadata
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TextIO

from tqdm import tqdm


# ───────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────

@dataclass
class LoggingConfig:
    """Logging system configuration."""
    output_dir: Path = Path("logs")
    log_filename: str = "execution.log"
    events_filename: str = "events.jsonl"
    console_level: int = logging.INFO
    file_level: int = logging.DEBUG
    tqdm_enabled: bool = True
    tqdm_mininterval: float = 0.1
    tqdm_miniters: int = 1


# ───────────────────────────────────────────────────────────────────
# Structured Event Schema
# ───────────────────────────────────────────────────────────────────

@dataclass
class GenerationEvent:
    """Single generation event with precise metadata."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = "info"
    stage: str = ""
    component: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    success: bool = True
    error: Optional[str] = None

    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_human(self) -> str:
        ts = self.timestamp.split("T")[1].split(".")[0]
        status = "✓" if self.success else "✗"
        parts = [f"[{ts}]", status, f"[{self.stage or 'system'}]"]
        if self.component:
            parts.append(f"({self.component})")
        parts.append(self.message)
        if self.duration_ms is not None:
            parts.append(f"({self.duration_ms:.0f}ms)")
        if self.error:
            parts.append(f"ERROR: {self.error}")
        return " ".join(parts)


# ───────────────────────────────────────────────────────────────────
# Custom TQDM-Aware Handler
# ───────────────────────────────────────────────────────────────────

class TqdmLoggingHandler(logging.Handler):
    """Logging handler that preserves TQDM progress bar integrity."""

    def __init__(self, tqdm_file: TextIO = sys.stderr):
        super().__init__()
        self.tqdm_file = tqdm_file

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            tqdm.write(msg, file=self.tqdm_file)
        except Exception:
            self.handleError(record)


# ───────────────────────────────────────────────────────────────────
# Main Logging System
# ───────────────────────────────────────────────────────────────────

class PipelineLogger:
    """Unified logging system for the video generation pipeline."""

    def __init__(self, config: Optional[LoggingConfig] = None, project_name: str = "default"):
        self.config = config or LoggingConfig()
        self.project_name = project_name
        self.output_dir = self.config.output_dir / project_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = self.output_dir / self.config.log_filename
        self.events_path = self.output_dir / self.config.events_filename

        self.logger = logging.getLogger(f"pipeline.{project_name}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
        file_handler.setLevel(self.config.file_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        ))
        self.logger.addHandler(file_handler)

        console_handler = TqdmLoggingHandler()
        console_handler.setLevel(self.config.console_level)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        ))
        self.logger.addHandler(console_handler)

        self._bars: dict[str, tqdm] = {}
        self._event_count = 0

    def log_event(self, event: GenerationEvent) -> None:
        self._event_count += 1
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(event.to_jsonl() + "\n")
        level_map = {
            "info": logging.INFO,
            "success": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "stage_start": logging.INFO,
            "stage_end": logging.INFO,
            "asset_start": logging.DEBUG,
            "asset_end": logging.DEBUG,
        }
        level = level_map.get(event.event_type, logging.INFO)
        self.logger.log(level, event.to_human())

    def info(self, message: str, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="info", message=message, details=kwargs))

    def success(self, message: str, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="success", message=message, success=True, details=kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="warning", message=message, success=True, details=kwargs))

    def error(self, message: str, error: Optional[str] = None, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="error", message=message, success=False, error=error, details=kwargs))

    def stage_start(self, stage: str, message: str, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="stage_start", stage=stage, message=message, details=kwargs))
        self.info(f"═══ {stage.upper()} START ═══")

    def stage_end(self, stage: str, message: str, duration_ms: Optional[float] = None, **kwargs: Any) -> None:
        self.log_event(GenerationEvent(event_type="stage_end", stage=stage, message=message, duration_ms=duration_ms, details=kwargs))
        self.info(f"═══ {stage.upper()} END ═══")

    def asset_start(self, component: str, asset_id: str, **kwargs: Any) -> GenerationEvent:
        event = GenerationEvent(
            event_type="asset_start",
            component=component,
            message=f"Starting generation: {asset_id}",
            details={**kwargs, "asset_id": asset_id},
        )
        self.log_event(event)
        return event

    def asset_end(self, event: GenerationEvent, success: bool = True,
                  file_path: Optional[str] = None, file_size_bytes: Optional[int] = None,
                  error: Optional[str] = None) -> None:
        event.event_type = "asset_end"
        event.success = success
        event.file_path = file_path
        event.file_size_bytes = file_size_bytes
        event.error = error
        if event.timestamp:
            start_time = datetime.fromisoformat(event.timestamp)
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            event.duration_ms = duration_ms
        self.log_event(event)

    def create_progress_bar(self, bar_id: str, total: int, desc: str,
                           unit: str = "items", **kwargs: Any) -> Optional[tqdm]:
        if not self.config.tqdm_enabled:
            return None
        bar = tqdm(
            total=total,
            desc=desc,
            unit=unit,
            mininterval=self.config.tqdm_mininterval,
            miniters=self.config.tqdm_miniters,
            dynamic_ncols=True,
            file=sys.stderr,
            **kwargs
        )
        self._bars[bar_id] = bar
        return bar

    def update_progress(self, bar_id: str, n: int = 1, **kwargs: Any) -> None:
        if bar_id in self._bars and self._bars[bar_id] is not None:
            self._bars[bar_id].update(n, **kwargs)

    def close_progress(self, bar_id: str) -> None:
        if bar_id in self._bars and self._bars[bar_id] is not None:
            self._bars[bar_id].close()
            del self._bars[bar_id]

    def close_all_progress(self) -> None:
        for bar_id in list(self._bars.keys()):
            self.close_progress(bar_id)

    def set_progress_description(self, bar_id: str, desc: str, **kwargs: Any) -> None:
        if bar_id in self._bars and self._bars[bar_id] is not None:
            self._bars[bar_id].set_description(desc)
            if kwargs:
                self._bars[bar_id].set_postfix(kwargs)

    def get_summary(self) -> dict[str, Any]:
        events = []
        if self.events_path.exists():
            with open(self.events_path, "r", encoding="utf-8") as f:
                for line in f:
                    events.append(json.loads(line))
        stage_starts = [e for e in events if e["event_type"] == "stage_start"]
        stage_ends = [e for e in events if e["event_type"] == "stage_end"]
        errors = [e for e in events if e["event_type"] == "error"]
        assets = [e for e in events if e["event_type"] in ("asset_start", "asset_end")]
        return {
            "project": self.project_name,
            "total_events": len(events),
            "stages_completed": len(stage_ends),
            "errors": len(errors),
            "assets_tracked": len(assets) // 2,
            "log_files": {
                "execution": str(self.log_path),
                "events": str(self.events_path),
            }
        }

    def __enter__(self) -> PipelineLogger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close_all_progress()
        if exc_type is not None:
            self.error(f"Pipeline failed: {exc_val}", error=str(exc_val))
        else:
            self.success("Pipeline completed successfully")


def run_with_logging(stage_name: str, func: Any, logger: PipelineLogger,
                     progress_bar: Optional[tqdm] = None, **kwargs: Any) -> Any:
    """Execute a pipeline stage with full logging coverage."""
    start_time = time.perf_counter()
    logger.stage_start(stage_name, f"Starting {stage_name}")
    try:
        result = func(**kwargs)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.stage_end(stage_name, f"Completed {stage_name}", duration_ms=duration_ms)
        return result
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Stage {stage_name} failed", error=str(e), duration_ms=duration_ms)
        raise
