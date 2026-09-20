from __future__ import annotations

import re

BLOCKED_PATTERNS = (
    r"ignore (all|the|previous) instructions",
    r"reveal (the )?(system prompt|secret|api key)",
    r"drop\s+(table|database)",
    r"delete\s+from",
    r"customer[_ ]?(email|phone|ssn)",
)


def validate_question(question: str) -> str:
    normalized = " ".join(question.strip().split())
    if not normalized:
        raise ValueError("question cannot be empty")
    if len(normalized) > 500:
        raise ValueError("question exceeds 500 characters")
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in BLOCKED_PATTERNS):
        raise ValueError("question violates the copilot safety policy")
    return normalized

