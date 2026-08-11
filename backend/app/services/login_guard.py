import hashlib
import threading
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 15 * 60
MAX_FAILURES = 8
_failures: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _key(username: str) -> str:
    return hashlib.sha256(username.strip().casefold().encode()).hexdigest()


def _prune(values: deque[float], now: float) -> None:
    while values and now - values[0] >= WINDOW_SECONDS:
        values.popleft()


def retry_after(username: str, now: float | None = None) -> int:
    current = time.monotonic() if now is None else now
    with _lock:
        values = _failures[_key(username)]
        _prune(values, current)
        if len(values) < MAX_FAILURES:
            return 0
        return max(1, int(WINDOW_SECONDS - (current - values[0])))


def record_failure(username: str, now: float | None = None) -> None:
    current = time.monotonic() if now is None else now
    with _lock:
        values = _failures[_key(username)]
        _prune(values, current)
        values.append(current)


def clear_failures(username: str) -> None:
    with _lock:
        _failures.pop(_key(username), None)


def reset_for_tests() -> None:
    with _lock:
        _failures.clear()
