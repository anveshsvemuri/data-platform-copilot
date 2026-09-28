import json
import stat
import sys
from pathlib import Path

import pytest

from data_platform_copilot.cli import main
from data_platform_copilot.reporting import summarize_traces, write_report


def _record(**overrides):
    record = {
        "event_id": "event",
        "timestamp": "2026-09-27T12:00:00+00:00",
        "question_hash": "hash",
        "prompt_version": "grounded-platform-v1",
        "mode": "deterministic",
        "model": "deterministic-local",
        "grounded": True,
        "citation_count": 1,
        "latency_ms": 100.0,
        "input_tokens": 20,
        "output_tokens": 10,
        "estimated_cost_usd": None,
        "cache_hit": False,
    }
    record.update(overrides)
    return record


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def test_summarizes_privacy_safe_operational_metrics(tmp_path):
    traces = tmp_path / "traces.jsonl"
    _write_jsonl(
        traces,
        [
            _record(latency_ms=100, estimated_cost_usd=0.001),
            _record(
                timestamp="2026-09-27T12:05:00+00:00",
                latency_ms=300,
                grounded=False,
                cache_hit=True,
                input_tokens=0,
                output_tokens=0,
            ),
        ],
    )

    report = summarize_traces(
        traces, minimum_grounded_rate=0.5, maximum_p95_latency_ms=500
    )

    assert report["events"] == 2
    assert report["grounded_rate"] == 0.5
    assert report["cache_hit_rate"] == 0.5
    assert report["latency_ms"] == {"p50": 100.0, "p95": 300.0, "max": 300.0}
    assert report["tokens"] == {"input": 20, "output": 10, "total": 30}
    assert report["cost"] == {"estimated_usd": 0.001, "coverage_rate": 0.5}
    assert report["status"] == "healthy"
    serialized = json.dumps(report)
    assert "question_hash" not in serialized
    assert "event_id" not in serialized


def test_alerts_and_cli_failure_gate(tmp_path, monkeypatch, capsys):
    traces = tmp_path / "traces.jsonl"
    _write_jsonl(traces, [_record(grounded=False, latency_ms=900)])
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "data-copilot",
            "--summarize-traces",
            str(traces),
            "--report-output",
            str(output),
            "--minimum-grounded-rate",
            "0.8",
            "--maximum-p95-latency-ms",
            "500",
            "--fail-on-alert",
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    report = json.loads(output.read_text())
    assert report["status"] == "alert"
    assert report["alerts"] == [
        "grounded_rate_below_minimum",
        "p95_latency_above_maximum",
    ]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert '"status": "alert"' in capsys.readouterr().out


def test_rejects_sensitive_or_malformed_trace_records(tmp_path):
    traces = tmp_path / "traces.jsonl"
    _write_jsonl(traces, [_record(question="raw operator question")])

    with pytest.raises(ValueError, match="forbidden fields: question"):
        summarize_traces(traces)

    traces.write_text("not-json\n")
    with pytest.raises(ValueError, match="invalid JSON on trace line 1"):
        summarize_traces(traces)


def test_writes_report_atomically_with_restricted_permissions(tmp_path):
    destination = tmp_path / "nested" / "report.json"
    write_report({"status": "healthy"}, destination)

    assert json.loads(destination.read_text()) == {"status": "healthy"}
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
