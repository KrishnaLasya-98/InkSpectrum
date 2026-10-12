"""Bounded process execution and atomic artifacts; no provider decisions."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path


def atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def stop_process_tree(process) -> None:
    """Stop only descendants of the process launched by this runner."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=15, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def run_logged(command, *, cwd=None, timeout=43200, log_dir: Path,
               env=None, heartbeat=None, tail_bytes=100_000,
               max_log_bytes=4 * 1024 * 1024):
    """Drain both pipes concurrently with bounded tails and two rotating logs.

    The timeout is a wall-clock deadline, not an inactivity timer. Every child
    owns a process group; cancellation and timeout clean up that group.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, **options)
    tails = {"stdout": bytearray(), "stderr": bytearray()}
    errors = []

    def drain(pipe, name):
        path = log_dir / f"{name}.log"
        try:
            with pipe:
                handle = path.open("wb")
                try:
                    size = 0
                    while chunk := pipe.read(8192):
                        tails[name].extend(chunk)
                        del tails[name][:-tail_bytes]
                        if size + len(chunk) > max_log_bytes:
                            handle.close()
                            path.replace(path.with_suffix(".log.1"))
                            handle = path.open("wb")
                            size = 0
                        handle.write(chunk)
                        handle.flush()
                        size += len(chunk)
                finally:
                    handle.close()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=drain, args=(getattr(process, name), name), daemon=True)
               for name in tails]
    for thread in threads:
        thread.start()
    deadline, next_heartbeat = time.monotonic() + float(timeout), 0.0
    timed_out = False
    old_sigterm = None
    if threading.current_thread() is threading.main_thread():
        old_sigterm = signal.getsignal(signal.SIGTERM)
        def terminate(signum, frame):
            raise InterruptedError("Process runner received SIGTERM")
        signal.signal(signal.SIGTERM, terminate)
    try:
        while process.poll() is None:
            now = time.monotonic()
            if errors:
                raise RuntimeError(f"Process log write failed: {errors[0]}")
            if now >= deadline:
                timed_out = True
                stop_process_tree(process)
                break
            if heartbeat and now >= next_heartbeat:
                heartbeat(process.pid)
                next_heartbeat = now + 5
            time.sleep(min(.1, max(0, deadline - now)))
        process.wait(timeout=15)
    except BaseException:
        stop_process_tree(process)
        process.wait(timeout=15)
        raise
    finally:
        if old_sigterm is not None:
            signal.signal(signal.SIGTERM, old_sigterm)
        for thread in threads:
            thread.join(timeout=5)
    if any(thread.is_alive() for thread in threads):
        stop_process_tree(process)
        raise RuntimeError("Child descendants retained output pipes after process exit")
    if errors:
        raise RuntimeError(f"Process log write failed: {errors[0]}")
    stdout, stderr = (bytes(tails[name]).decode("utf-8", errors="replace") for name in tails)
    if timed_out:
        stderr += f"\n[timeout after {timeout}s]"
    return subprocess.CompletedProcess(command, 124 if timed_out else process.returncode, stdout, stderr)
