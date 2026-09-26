import json
from pathlib import Path

from data_platform_copilot.copilot import DataPlatformCopilot
from data_platform_copilot.observability import calculate_cost

ROOT = Path(__file__).parents[1]


def test_privacy_safe_trace_records_local_usage(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    trace_path = tmp_path / "traces.jsonl"
    question = "What is the churn model promotion threshold?"

    answer = DataPlatformCopilot(ROOT / "knowledge", trace_path=trace_path).ask(question)
    trace = json.loads(trace_path.read_text())

    assert answer.grounded
    assert trace["mode"] == "deterministic"
    assert trace["model"] == "deterministic-local"
    assert trace["prompt_version"] == "grounded-platform-v1"
    assert trace["citation_count"] >= 1
    assert trace["input_tokens"] > 0
    assert trace["output_tokens"] > 0
    assert trace["latency_ms"] >= 0
    assert trace["question_hash"]
    assert trace["cache_hit"] is False
    assert question not in trace_path.read_text()
    assert answer.answer not in trace_path.read_text()


def test_cost_uses_explicit_configured_rates(monkeypatch):
    monkeypatch.setenv("OPENAI_INPUT_COST_PER_MILLION", "2")
    monkeypatch.setenv("OPENAI_OUTPUT_COST_PER_MILLION", "8")
    assert calculate_cost(1000, 500) == 0.006
