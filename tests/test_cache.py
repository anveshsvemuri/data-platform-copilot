import json
import stat
from pathlib import Path

from data_platform_copilot.copilot import DataPlatformCopilot

ROOT = Path(__file__).parents[1]


def test_semantic_cache_reuses_grounded_paraphrase(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cache_path = tmp_path / "responses.json"
    trace_path = tmp_path / "traces.jsonl"
    copilot = DataPlatformCopilot(
        ROOT / "knowledge", cache_path=cache_path, trace_path=trace_path
    )

    original = copilot.ask("What is the churn model promotion threshold?")
    cached = copilot.ask("What threshold is required for churn model promotion?")
    traces = [json.loads(line) for line in trace_path.read_text().splitlines()]
    cache_payload = json.loads(cache_path.read_text())

    assert cached == original
    assert traces[0]["cache_hit"] is False
    assert traces[1]["cache_hit"] is True
    assert traces[1]["input_tokens"] == traces[1]["output_tokens"] == 0
    assert cache_payload["entries"][0]["question_hash"]
    assert "What is the churn" not in cache_path.read_text()
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600


def test_cache_is_invalidated_when_knowledge_changes(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cache_path = tmp_path / "responses.json"
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    source = knowledge / "runbook.md"
    source.write_text("# Recovery\nRestart the orchestrator.")
    first = DataPlatformCopilot(knowledge, cache_path=cache_path)
    first.ask("How do I recover the orchestrator?")

    source.write_text("# Recovery\nRecover the orchestrator by escalating to the platform owner.")
    trace_path = tmp_path / "trace.jsonl"
    second = DataPlatformCopilot(
        knowledge, cache_path=cache_path, trace_path=trace_path
    )
    answer = second.ask("How do I recover the orchestrator?")
    trace = json.loads(trace_path.read_text())

    assert "escalating" in answer.answer
    assert trace["cache_hit"] is False
