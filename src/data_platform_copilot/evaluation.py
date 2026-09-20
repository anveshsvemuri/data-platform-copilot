from __future__ import annotations

import json
from pathlib import Path

from .copilot import DataPlatformCopilot


def evaluate(copilot: DataPlatformCopilot, dataset: Path) -> dict[str, float | int]:
    cases = json.loads(dataset.read_text())
    passed = 0
    grounded = 0
    for case in cases:
        answer = copilot.ask(case["question"])
        sources = {citation.source for citation in answer.citations}
        source_ok = case.get("expected_source") in sources
        abstention_ok = not case.get("should_abstain", False) or not answer.grounded
        passed += int(source_ok or abstention_ok and case.get("should_abstain", False))
        grounded += int(answer.grounded)
    return {
        "cases": len(cases),
        "pass_rate": round(passed / len(cases), 4),
        "grounded_rate": round(grounded / len(cases), 4),
    }

