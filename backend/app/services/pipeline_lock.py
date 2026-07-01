"""Cross-platform lock for the real data pipeline (one runner at a time)."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

STALE_LOCK_SECONDS = 2 * 60 * 60


def _lock_path() -> Path:
    backend_dir = Path(__file__).resolve().parents[2]
    lock_dir = backend_dir / "runtime" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "real_pipeline.lock"


@dataclass
class LockResult:
    acquired: bool
    reason: str | None = None


def _is_stale(lock_file: Path) -> bool:
    if not lock_file.exists():
        return False
    age = time.time() - lock_file.stat().st_mtime
    return age > STALE_LOCK_SECONDS


def try_acquire_lock(owner: str = "pipeline") -> LockResult:
    lock_file = _lock_path()
    if lock_file.exists():
        if _is_stale(lock_file):
            try:
                lock_file.unlink(missing_ok=True)
            except OSError:
                return LockResult(acquired=False, reason="stale_lock_cleanup_failed")
        else:
            return LockResult(acquired=False, reason="skipped_locked")

    payload = json.dumps(
        {
            "pid": os.getpid(),
            "source": owner,
            "started_at": int(time.time()),
        },
        ensure_ascii=False,
    )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_file), flags)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        return LockResult(acquired=True)
    except FileExistsError:
        return LockResult(acquired=False, reason="skipped_locked")
    except OSError as exc:
        return LockResult(acquired=False, reason=f"lock_write_failed:{exc}")


def release_lock() -> None:
    lock_file = _lock_path()
    try:
        lock_file.unlink(missing_ok=True)
    except OSError:
        pass


@contextmanager
def pipeline_lock(owner: str = "pipeline"):
    result = try_acquire_lock(owner=owner)
    if not result.acquired:
        yield result
        return
    try:
        yield result
    finally:
        release_lock()
