from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Sample:
    elapsed_ms: float
    ok: bool
    error: str = ""


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percent))
    return ordered[index]


def run_load(
    url: str,
    duration_seconds: int,
    concurrency: int,
    token: str = "",
) -> dict[str, float | int | dict[str, int]]:
    deadline = time.monotonic() + duration_seconds
    samples: list[Sample] = []
    lock = threading.Lock()

    def worker() -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        while time.monotonic() < deadline:
            started = time.perf_counter()
            ok = False
            error = ""
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=10) as response:
                    response.read()
                    ok = 200 <= response.status < 300
            except urllib.error.HTTPError as exc:
                error = f"HTTP {exc.code}"
            except OSError as exc:
                error = type(exc.reason if isinstance(exc, urllib.error.URLError) else exc).__name__
            sample = Sample((time.perf_counter() - started) * 1000, ok, error)
            with lock:
                samples.append(sample)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for future in futures:
            future.result()
    latencies = [item.elapsed_ms for item in samples if item.ok]
    failures = sum(not item.ok for item in samples)
    error_types = collections.Counter(item.error or "Unbekannt" for item in samples if not item.ok)
    return {
        "requests": len(samples),
        "failures": failures,
        "error_types": dict(error_types.most_common()),
        "error_rate": round(failures / len(samples), 6) if samples else 1.0,
        "requests_per_second": round(len(samples) / duration_seconds, 2),
        "latency_mean_ms": round(statistics.fmean(latencies), 2) if latencies else 0.0,
        "latency_p50_ms": round(percentile(latencies, 0.50), 2),
        "latency_p95_ms": round(percentile(latencies, 0.95), 2),
        "latency_p99_ms": round(percentile(latencies, 0.99), 2),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP load and soak test for EventMonitorAI")
    parser.add_argument("--url", default="http://127.0.0.1:8015/health")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--token", default="")
    parser.add_argument("--max-error-rate", type=float, default=0.001)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    arguments = parser.parse_args()
    if arguments.duration < 1 or not 1 <= arguments.concurrency <= 200:
        parser.error("duration >= 1 und concurrency zwischen 1 und 200 erforderlich")
    result = run_load(
        arguments.url,
        arguments.duration,
        arguments.concurrency,
        arguments.token,
    )
    print(json.dumps(result, indent=2))
    if result["error_rate"] > arguments.max_error_rate:
        raise SystemExit(2)
    if result["latency_p95_ms"] > arguments.max_p95_ms:
        raise SystemExit(3)
