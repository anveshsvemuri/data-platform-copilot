from __future__ import annotations

import json
import math
import os
from collections import Counter
from pathlib import Path

REQUIRED_FIELDS = {
    "timestamp",
    "prompt_version",
    "mode",
    "model",
    "grounded",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "cache_hit",
}
SENSITIVE_FIELDS = {
    "question",
    "answer",
    "prompt",
    "context",
    "citations",
    "retrieved_passages",
    "api_key",
}


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def _read_traces(source: Path) -> list[dict[str, object]]:
    if not source.exists():
        raise ValueError(f"trace file does not exist: {source}")
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on trace line {line_number}") from exc
        if not isinstance(record, dict):
            raise TypeError(f"trace line {line_number} must be a JSON object")
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            raise ValueError(
                f"trace line {line_number} is missing fields: {', '.join(sorted(missing))}"
            )
        sensitive = SENSITIVE_FIELDS & record.keys()
        if sensitive:
            raise ValueError(
                f"trace line {line_number} contains forbidden fields: "
                f"{', '.join(sorted(sensitive))}"
            )
        for field in ("latency_ms", "input_tokens", "output_tokens"):
            value = record[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"trace line {line_number} has invalid {field}")
        if not isinstance(record["grounded"], bool) or not isinstance(record["cache_hit"], bool):
            raise TypeError(f"trace line {line_number} has invalid boolean metrics")
        cost = record["estimated_cost_usd"]
        if cost is not None and (
            isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0
        ):
            raise ValueError(f"trace line {line_number} has invalid estimated_cost_usd")
        records.append(record)
    if not records:
        raise ValueError("trace file contains no events")
    return records


def summarize_traces(
    source: Path,
    *,
    minimum_grounded_rate: float | None = None,
    maximum_p95_latency_ms: float | None = None,
) -> dict[str, object]:
    if minimum_grounded_rate is not None and not 0 <= minimum_grounded_rate <= 1:
        raise ValueError("minimum grounded rate must be between 0 and 1")
    if maximum_p95_latency_ms is not None and maximum_p95_latency_ms < 0:
        raise ValueError("maximum p95 latency must be non-negative")

    records = _read_traces(source)
    total = len(records)
    latencies = [float(record["latency_ms"]) for record in records]
    grounded_rate = round(sum(bool(record["grounded"]) for record in records) / total, 4)
    cache_hit_rate = round(sum(bool(record["cache_hit"]) for record in records) / total, 4)
    p95_latency = _percentile(latencies, 0.95)
    reported_costs = [
        float(record["estimated_cost_usd"])
        for record in records
        if record["estimated_cost_usd"] is not None
    ]
    alerts: list[str] = []
    if minimum_grounded_rate is not None and grounded_rate < minimum_grounded_rate:
        alerts.append("grounded_rate_below_minimum")
    if maximum_p95_latency_ms is not None and p95_latency > maximum_p95_latency_ms:
        alerts.append("p95_latency_above_maximum")

    return {
        "schema_version": "1.0",
        "events": total,
        "window": {
            "started_at": min(str(record["timestamp"]) for record in records),
            "ended_at": max(str(record["timestamp"]) for record in records),
        },
        "mode_counts": dict(sorted(Counter(str(record["mode"]) for record in records).items())),
        "model_counts": dict(
            sorted(Counter(str(record["model"]) for record in records).items())
        ),
        "prompt_version_counts": dict(
            sorted(Counter(str(record["prompt_version"]) for record in records).items())
        ),
        "grounded_rate": grounded_rate,
        "cache_hit_rate": cache_hit_rate,
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": p95_latency,
            "max": round(max(latencies), 3),
        },
        "tokens": {
            "input": sum(int(record["input_tokens"]) for record in records),
            "output": sum(int(record["output_tokens"]) for record in records),
            "total": sum(
                int(record["input_tokens"]) + int(record["output_tokens"])
                for record in records
            ),
        },
        "cost": {
            "estimated_usd": round(sum(reported_costs), 8),
            "coverage_rate": round(len(reported_costs) / total, 4),
        },
        "gates": {
            "minimum_grounded_rate": minimum_grounded_rate,
            "maximum_p95_latency_ms": maximum_p95_latency_ms,
        },
        "status": "alert" if alerts else "healthy",
        "alerts": alerts,
    }


def write_report(report: dict[str, object], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
    finally:
        os.close(descriptor)
    os.replace(temporary, destination)
