"""
benchmark.py - Lightweight benchmark harness for query latency and payload size.

Usage:
  python -m sf_code_intelligence.benchmark ./fixtures
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Callable

from sf_code_intelligence import query
from sf_code_intelligence.db import get_connection, init_db
from sf_code_intelligence.indexer import (
    build_dependency_edges,
    index_apex_class,
    index_object,
)


def _estimate_tokens(payload: str) -> int:
    # Fast approximation for planning budgets during local benchmarking.
    return max(1, len(payload) // 4)


def _benchmark_case(
    label: str,
    fn: Callable[[], object],
    iterations: int,
    warmup: int,
) -> dict:
    for _ in range(warmup):
        fn()

    latencies_ms: list[float] = []
    payload_sizes: list[int] = []
    token_estimates: list[int] = []
    last_result = None

    for _ in range(iterations):
        started = time.perf_counter()
        result = fn()
        elapsed = (time.perf_counter() - started) * 1000.0
        payload = json.dumps(result, separators=(",", ":"), sort_keys=True)
        latencies_ms.append(elapsed)
        payload_sizes.append(len(payload))
        token_estimates.append(_estimate_tokens(payload))
        last_result = result

    p95 = statistics.quantiles(latencies_ms, n=20)[18] if iterations > 1 else latencies_ms[0]
    return {
        "case": label,
        "iterations": iterations,
        "latency_ms": {
            "min": round(min(latencies_ms), 3),
            "p50": round(statistics.median(latencies_ms), 3),
            "p95": round(p95, 3),
            "max": round(max(latencies_ms), 3),
            "mean": round(statistics.mean(latencies_ms), 3),
        },
        "payload_bytes": {
            "min": min(payload_sizes),
            "max": max(payload_sizes),
            "mean": round(statistics.mean(payload_sizes), 2),
        },
        "estimated_tokens": {
            "min": min(token_estimates),
            "max": max(token_estimates),
            "mean": round(statistics.mean(token_estimates), 2),
        },
        "sample_result_type": type(last_result).__name__,
        "sample_result_items": len(last_result) if isinstance(last_result, list) else 1,
    }


def _build_index(fixtures_path: Path) -> None:
    init_db()
    conn = get_connection()
    for cls_file in fixtures_path.glob("classes/*.cls"):
        if "Test" in cls_file.name:
            continue
        index_apex_class(str(cls_file), conn)
    for obj_file in fixtures_path.glob("objects/**/*.object-meta.xml"):
        index_object(str(obj_file), conn)
    build_dependency_edges(conn)
    conn.commit()
    conn.close()


def run(fixtures: str, iterations: int, warmup: int) -> dict:
    fixtures_path = Path(fixtures)
    _build_index(fixtures_path)
    conn = get_connection()

    try:
        results = [
            _benchmark_case(
                "search_symbol:class_exact",
                lambda: query.search_symbol("PropertyController", conn),
                iterations,
                warmup,
            ),
            _benchmark_case(
                "search_symbol:method_partial",
                lambda: query.search_symbol("get", conn),
                iterations,
                warmup,
            ),
            _benchmark_case(
                "get_object_schema:property",
                lambda: query.get_object_schema("Property__c", conn),
                iterations,
                warmup,
            ),
            _benchmark_case(
                "find_apex_touching_object:property",
                lambda: query.find_apex_touching_object("Property__c", conn),
                iterations,
                warmup,
            ),
            _benchmark_case(
                "get_class_summary:property_controller",
                lambda: query.get_class_summary("PropertyController", conn),
                iterations,
                warmup,
            ),
        ]
        return {
            "fixtures": str(fixtures_path),
            "iterations": iterations,
            "warmup": warmup,
            "results": results,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark query latency and response token footprint."
    )
    parser.add_argument(
        "fixtures",
        nargs="?",
        default="./fixtures",
        help="Path to fixtures root (default: ./fixtures)",
    )
    parser.add_argument(
        "--iterations", type=int, default=50, help="Measured iterations per case"
    )
    parser.add_argument(
        "--warmup", type=int, default=5, help="Warmup iterations per case"
    )
    args = parser.parse_args()

    report = run(args.fixtures, args.iterations, args.warmup)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
