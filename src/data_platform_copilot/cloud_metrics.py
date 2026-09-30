from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPORT_FIELDS = {
    "events": ("Events", "Count"),
    "grounded_rate": ("GroundedRate", "None"),
    "cache_hit_rate": ("CacheHitRate", "None"),
}
NESTED_FIELDS = {
    ("latency_ms", "p50"): ("P50Latency", "Milliseconds"),
    ("latency_ms", "p95"): ("P95Latency", "Milliseconds"),
    ("latency_ms", "max"): ("MaxLatency", "Milliseconds"),
    ("tokens", "input"): ("InputTokens", "Count"),
    ("tokens", "output"): ("OutputTokens", "Count"),
    ("tokens", "total"): ("TotalTokens", "Count"),
    ("cost", "estimated_usd"): ("EstimatedCost", "None"),
    ("cost", "coverage_rate"): ("CostCoverageRate", "None"),
}


def _numeric(value: object, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise TypeError(f"{field} must be a non-negative number")
    return value


def create_emf_event(report: dict[str, Any], environment: str = "demo") -> dict[str, Any]:
    """Convert an aggregate observability report to CloudWatch EMF."""
    if not environment or len(environment) > 64:
        raise ValueError("environment must contain 1-64 characters")
    if report.get("schema_version") != "1.0" or report.get("status") not in {
        "healthy",
        "alert",
    }:
        raise ValueError("report must use schema 1.0 and have healthy or alert status")

    definitions: list[dict[str, str]] = [{"Name": "Alert", "Unit": "Count"}]
    values: dict[str, int | float] = {"Alert": int(report["status"] == "alert")}
    for source, (name, unit) in REPORT_FIELDS.items():
        values[name] = _numeric(report.get(source), source)
        definitions.append({"Name": name, "Unit": unit})
    for (section, source), (name, unit) in NESTED_FIELDS.items():
        container = report.get(section)
        if not isinstance(container, dict):
            raise TypeError(f"{section} must be an object")
        values[name] = _numeric(container.get(source), f"{section}.{source}")
        definitions.append({"Name": name, "Unit": unit})

    return {
        "_aws": {
            "CloudWatchMetrics": [
                {
                    "Namespace": "DataPlatformCopilot",
                    "Dimensions": [["Environment"]],
                    "Metrics": definitions,
                }
            ]
        },
        "Environment": environment,
        **values,
    }


def export_report_metrics(
    source: Path, environment: str = "demo", destination: Path | None = None
) -> str:
    report = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise TypeError("report must be a JSON object")
    payload = json.dumps(create_emf_event(report, environment), separators=(",", ":")) + "\n"
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, payload.encode())
        finally:
            os.close(descriptor)
        os.replace(temporary, destination)
    return payload
