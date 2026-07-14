"""
infra/metrics.py — Upgrade 7: Request Metrics Collector
Tracks p50/p95/p99 latency, error rate, and throughput in real time.
FastAPI middleware records every request; /metrics endpoint exposes results.
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class RequestRecord:
    path:       str
    method:     str
    status:     int
    elapsed_ms: float
    timestamp:  float = field(default_factory=time.time)


class MetricsCollector:
    """
    Rolling window metrics collector.
    Keeps the last 10,000 requests in memory and computes:
      - throughput (req/s over last 60s)
      - latency percentiles (p50, p95, p99)
      - error rate
      - per-endpoint breakdown
    """

    def __init__(self, window: int = 10_000):
        self._records: Deque[RequestRecord] = deque(maxlen=window)
        self._lock     = threading.Lock()
        self._start    = time.time()

    def record(self, path: str, method: str,
               status: int, elapsed_ms: float):
        with self._lock:
            self._records.append(RequestRecord(
                path=path, method=method,
                status=status, elapsed_ms=elapsed_ms,
            ))

    def _recent(self, seconds: int = 60) -> list[RequestRecord]:
        cutoff = time.time() - seconds
        return [r for r in self._records if r.timestamp >= cutoff]

    def percentile(self, values: list[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        idx = max(0, int(len(sorted_v) * p / 100) - 1)
        return round(sorted_v[idx], 2)

    def summary(self) -> dict:
        with self._lock:
            recent  = self._recent(60)
            all_rec = list(self._records)

        if not recent:
            return {
                "requests_total":   len(all_rec),
                "requests_60s":     0,
                "throughput_rps":   0,
                "error_rate_pct":   0,
                "latency_ms":       {"p50": 0, "p95": 0, "p99": 0, "avg": 0},
                "uptime_s":         round(time.time() - self._start, 0),
            }

        latencies  = [r.elapsed_ms for r in recent]
        errors     = [r for r in recent if r.status >= 500]
        throughput = len(recent) / 60

        # Per-endpoint breakdown
        by_path: dict[str, list] = {}
        for r in recent:
            key = f"{r.method} {r.path}"
            by_path.setdefault(key, []).append(r.elapsed_ms)

        endpoints = {
            path: {
                "count": len(times),
                "avg_ms": round(sum(times)/len(times), 1),
                "p99_ms": self.percentile(times, 99),
            }
            for path, times in sorted(
                by_path.items(),
                key=lambda x: -len(x[1])
            )[:8]
        }

        return {
            "requests_total":   len(all_rec),
            "requests_60s":     len(recent),
            "throughput_rps":   round(throughput, 1),
            "error_rate_pct":   round(len(errors)/len(recent)*100, 2),
            "latency_ms": {
                "avg": round(sum(latencies)/len(latencies), 1),
                "p50": self.percentile(latencies, 50),
                "p95": self.percentile(latencies, 95),
                "p99": self.percentile(latencies, 99),
            },
            "uptime_s":       round(time.time() - self._start, 0),
            "top_endpoints":  endpoints,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
metrics = MetricsCollector()
