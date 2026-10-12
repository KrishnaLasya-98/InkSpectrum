"""Stream media without exposing partially downloaded final artifacts."""
from pathlib import Path
import os
import uuid
import requests


def download_atomic(url: str, destination: Path, *, timeout=120) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        with requests.get(url, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            size = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
                        size += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            expected = response.headers.get("Content-Length")
            if size == 0 or (expected and not response.headers.get("Content-Encoding") and size != int(expected)):
                raise IOError("Empty or incomplete media download")
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
