import json
import stat

import pytest

from data_platform_copilot.cloud_metrics import create_emf_event, export_report_metrics


def report() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "alert",
        "events": 10,
        "grounded_rate": 0.9,
        "cache_hit_rate": 0.4,
        "latency_ms": {"p50": 100, "p95": 800, "max": 1200},
        "tokens": {"input": 1000, "output": 300, "total": 1300},
        "cost": {"estimated_usd": 0.015, "coverage_rate": 1.0},
        "alerts": ["grounded_rate_below_minimum"],
        "model_counts": {"provider-model": 10},
    }


def test_creates_allowlisted_cloudwatch_event() -> None:
    event = create_emf_event(report(), "production")

    assert event["Environment"] == "production"
    assert event["Alert"] == 1
    assert event["GroundedRate"] == 0.9
    assert event["P95Latency"] == 800
    assert event["TotalTokens"] == 1300
    assert "alerts" not in event
    assert "model_counts" not in event
    assert event["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "DataPlatformCopilot"


def test_exports_atomic_owner_only_json_line(tmp_path) -> None:
    source = tmp_path / "report.json"
    destination = tmp_path / "metrics.jsonl"
    source.write_text(json.dumps(report()), encoding="utf-8")

    payload = export_report_metrics(source, destination=destination)

    assert destination.read_text(encoding="utf-8") == payload
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert json.loads(payload)["EstimatedCost"] == 0.015


@pytest.mark.parametrize(
    "mutation",
    [
        {"schema_version": "2.0"},
        {"status": "unknown"},
        {"grounded_rate": "high"},
        {"latency_ms": None},
    ],
)
def test_rejects_invalid_report_contract(mutation) -> None:
    candidate = report()
    candidate.update(mutation)
    with pytest.raises((TypeError, ValueError)):
        create_emf_event(candidate)
