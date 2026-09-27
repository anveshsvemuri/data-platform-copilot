from __future__ import annotations

import json
import re
from pathlib import Path

from .copilot import DataPlatformCopilot


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_.-]+", text.lower())
        if len(token) > 2
    }


def _citation_support(answer_text: str, excerpts: list[str]) -> bool:
    answer_tokens = _tokens(answer_text)
    evidence_tokens = _tokens(" ".join(excerpts))
    return not answer_tokens or len(answer_tokens & evidence_tokens) / len(answer_tokens) >= 0.35


def evaluate(copilot: DataPlatformCopilot, dataset: Path) -> dict[str, object]:
    cases = json.loads(dataset.read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError("evaluation dataset must be a non-empty JSON array")
    case_ids = [case.get("id") for case in cases]
    if any(not case_id for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError("evaluation cases require unique non-empty ids")

    passed = grounded = rejected = 0
    failures: list[dict[str, object]] = []
    for case in cases:
        checks: dict[str, bool] = {}
        try:
            answer = copilot.ask(case["question"])
        except ValueError:
            checks["expected_rejection"] = bool(case.get("should_reject"))
            answer = None
            rejected += int(checks["expected_rejection"])
        else:
            checks["expected_rejection"] = not case.get("should_reject", False)
            expected_grounded = case.get("should_be_grounded")
            if expected_grounded is not None:
                checks["grounded"] = answer.grounded is expected_grounded
            expected_source = case.get("expected_source")
            if expected_source:
                checks["source"] = expected_source in {
                    citation.source for citation in answer.citations
                }
            required_terms = case.get("required_terms", [])
            checks["required_terms"] = all(
                term.lower() in answer.answer.lower() for term in required_terms
            )
            forbidden_terms = case.get("forbidden_terms", [])
            checks["forbidden_terms"] = all(
                term.lower() not in answer.answer.lower() for term in forbidden_terms
            )
            checks["citation_support"] = (
                not answer.grounded
                or _citation_support(
                    answer.answer, [citation.excerpt for citation in answer.citations]
                )
            )
            grounded += int(answer.grounded)

        case_passed = all(checks.values())
        passed += int(case_passed)
        if not case_passed:
            failures.append(
                {
                    "id": case["id"],
                    "failed_checks": sorted(name for name, ok in checks.items() if not ok),
                }
            )

    return {
        "schema_version": "1.0",
        "cases": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": round(passed / len(cases), 4),
        "grounded_rate": round(grounded / len(cases), 4),
        "rejected_attacks": rejected,
        "failures": failures,
    }
