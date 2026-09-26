from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .models import CopilotAnswer
from .retrieval import Chunk, vectorize_text

CACHE_VERSION = 1


def knowledge_fingerprint(chunks: list[Chunk]) -> str:
    payload = "\n".join(f"{chunk.chunk_id}\0{chunk.text}" for chunk in chunks)
    return hashlib.sha256(payload.encode()).hexdigest()


class ResponseCache:
    """Persistent semantic cache that never stores raw operator questions."""

    def __init__(
        self,
        path: Path,
        *,
        similarity_threshold: float = 0.88,
        ttl_seconds: int = 86_400,
        max_entries: int = 500,
    ):
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("cache similarity threshold must be between 0 and 1")
        if ttl_seconds < 1 or max_entries < 1:
            raise ValueError("cache TTL and maximum entries must be positive")
        self.path = path
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries

    def _read(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("version") != CACHE_VERSION:
            return []
        return list(payload.get("entries", []))

    def get(
        self, question: str, *, knowledge_hash: str, prompt_version: str, provider: str
    ) -> CopilotAnswer | None:
        query_vector = vectorize_text(question)
        now = time.time()
        best: tuple[float, dict[str, object]] | None = None
        for entry in self._read():
            if (
                entry.get("knowledge_hash") != knowledge_hash
                or entry.get("prompt_version") != prompt_version
                or entry.get("provider") != provider
                or now - float(entry["created_at"]) > self.ttl_seconds
            ):
                continue
            score = sum(
                left * right for left, right in zip(query_vector, entry["query_vector"])
            )
            if score >= self.similarity_threshold and (best is None or score > best[0]):
                best = (score, entry)
        return CopilotAnswer.model_validate(best[1]["answer"]) if best else None

    def put(
        self,
        question: str,
        answer: CopilotAnswer,
        *,
        knowledge_hash: str,
        prompt_version: str,
        provider: str,
    ) -> None:
        now = time.time()
        entries = [
            entry
            for entry in self._read()
            if now - float(entry["created_at"]) <= self.ttl_seconds
        ]
        entries.append(
            {
                "question_hash": hashlib.sha256(question.encode()).hexdigest(),
                "query_vector": vectorize_text(question),
                "knowledge_hash": knowledge_hash,
                "prompt_version": prompt_version,
                "provider": provider,
                "created_at": now,
                "answer": answer.model_dump(),
            }
        )
        payload = {"version": CACHE_VERSION, "entries": entries[-self.max_entries :]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, (json.dumps(payload, separators=(",", ":")) + "\n").encode())
        finally:
            os.close(descriptor)
        os.replace(temporary, self.path)
