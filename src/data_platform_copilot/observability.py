from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class TraceRecord:
    event_id: str
    timestamp: str
    question_hash: str
    prompt_version: str
    mode: str
    model: str
    grounded: bool
    citation_count: int
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None


def estimate_tokens(text: str) -> int:
    """Provide a deterministic no-key approximation for local telemetry."""
    return max(1, (len(text) + 3) // 4)


def calculate_cost(input_tokens: int, output_tokens: int) -> float | None:
    input_rate = os.getenv("OPENAI_INPUT_COST_PER_MILLION")
    output_rate = os.getenv("OPENAI_OUTPUT_COST_PER_MILLION")
    if not input_rate or not output_rate:
        return None
    try:
        input_price, output_price = float(input_rate), float(output_rate)
    except ValueError as exc:
        raise ValueError("OpenAI cost rates must be numeric") from exc
    if input_price < 0 or output_price < 0:
        raise ValueError("OpenAI cost rates cannot be negative")
    cost = input_tokens * input_price + output_tokens * output_price
    return round(cost / 1_000_000, 8)


def create_trace(
    *,
    question: str,
    prompt_version: str,
    mode: str,
    model: str,
    grounded: bool,
    citation_count: int,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
) -> TraceRecord:
    return TraceRecord(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        question_hash=hashlib.sha256(question.encode()).hexdigest(),
        prompt_version=prompt_version,
        mode=mode,
        model=model,
        grounded=grounded,
        citation_count=citation_count,
        latency_ms=round(latency_ms, 3),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=calculate_cost(input_tokens, output_tokens),
    )


def append_trace(trace: TraceRecord, destination: Path) -> None:
    """Append one compact JSON event without persisting prompts or responses."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(asdict(trace), separators=(",", ":")) + "\n").encode()
    descriptor = os.open(destination, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
