from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import fcntl

DefaultFactory = Callable[[], Any]
Mutator = Callable[[Any], Any]

_LOCK_RETRY_SLEEP_SECONDS = 0.05
_DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0


def _lock_file_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.lock")


@contextmanager
def file_lock(path: Path, timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Acquire an exclusive advisory lock for a JSON file path."""
    lock_path = _lock_file_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    lock_handle = lock_path.open("a+", encoding="utf-8")
    try:
        while True:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for file lock: {path}") from exc
                time.sleep(_LOCK_RETRY_SLEEP_SECONDS)
        yield
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


@contextmanager
def file_locks(paths: Iterable[Path], timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Acquire multiple file locks in deterministic order to avoid deadlocks."""
    unique_paths = sorted({Path(path).resolve() for path in paths}, key=lambda p: str(p))
    with ExitStack() as stack:
        for path in unique_paths:
            stack.enter_context(file_lock(path, timeout_seconds=timeout_seconds))
        yield


def _atomic_write_json_unlocked(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(serialized)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json_unlocked(path: Path, default_factory: DefaultFactory, initialize_if_missing: bool) -> Any:
    if not path.exists():
        default_value = default_factory()
        if initialize_if_missing:
            _atomic_write_json_unlocked(path, default_value)
        return default_value
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_file(
    path: Path,
    default_factory: DefaultFactory,
    initialize_if_missing: bool = True,
    timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> Any:
    with file_lock(path, timeout_seconds=timeout_seconds):
        return _read_json_unlocked(path, default_factory=default_factory, initialize_if_missing=initialize_if_missing)


def write_json_file(
    path: Path,
    payload: Any,
    timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> None:
    with file_lock(path, timeout_seconds=timeout_seconds):
        _atomic_write_json_unlocked(path, payload)


def mutate_json_file(
    path: Path,
    default_factory: DefaultFactory,
    mutator: Mutator,
    timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> Any:
    with file_lock(path, timeout_seconds=timeout_seconds):
        current = _read_json_unlocked(path, default_factory=default_factory, initialize_if_missing=True)
        updated = mutator(current)
        _atomic_write_json_unlocked(path, updated)
        return updated


def load_json_unlocked(path: Path, default_factory: DefaultFactory, initialize_if_missing: bool = True) -> Any:
    return _read_json_unlocked(path, default_factory=default_factory, initialize_if_missing=initialize_if_missing)


def save_json_unlocked(path: Path, payload: Any) -> None:
    _atomic_write_json_unlocked(path, payload)
