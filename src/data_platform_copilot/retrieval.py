from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

INDEX_VERSION = 1
VECTOR_DIMENSIONS = 256


@dataclass(frozen=True)
class Document:
    source: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    section: str
    text: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    source: str
    section: str
    text: str
    score: float


def _tokens(text: str) -> list[str]:
    stopwords = {
        "and", "are", "for", "from", "has", "how", "the", "this", "what", "when",
        "where", "which", "who", "with",
    }
    return [
        token for token in re.findall(r"[a-z0-9_]+", text.lower())
        if len(token) > 2 and token not in stopwords
    ]


def vectorize_text(text: str) -> tuple[float, ...]:
    """Create a stable, dependency-free feature-hashing vector."""
    vector = [0.0] * VECTOR_DIMENSIONS
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode()).digest()
        position = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[position] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        vector = [value / magnitude for value in vector]
    return tuple(vector)


def load_documents(directory: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(Document(source=path.name, text=text))
    if not documents:
        raise ValueError(f"no Markdown knowledge documents found in {directory}")
    return documents


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "document"


def chunk_documents(
    documents: list[Document], max_words: int = 120, overlap_words: int = 20
) -> list[Chunk]:
    if overlap_words >= max_words:
        raise ValueError("overlap_words must be smaller than max_words")
    chunks: list[Chunk] = []
    for document in documents:
        sections: list[tuple[str, list[str]]] = []
        heading = "Overview"
        lines: list[str] = []
        for line in document.text.splitlines():
            if line.startswith("#"):
                if lines:
                    sections.append((heading, lines))
                heading = line.lstrip("# ").strip() or "Overview"
                lines = []
            elif line.strip():
                lines.append(line.strip())
        if lines:
            sections.append((heading, lines))

        for section, section_lines in sections:
            words = " ".join(section_lines).split()
            step = max_words - overlap_words
            for position, start in enumerate(range(0, len(words), step)):
                text = " ".join(words[start : start + max_words])
                if not text:
                    continue
                chunk_id = f"{document.source}#{_slug(section)}-{position}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        source=document.source,
                        section=section,
                        text=text,
                        vector=vectorize_text(f"{section} {text}"),
                    )
                )
                if start + max_words >= len(words):
                    break
    return chunks


def _fingerprint(documents: list[Document]) -> str:
    payload = "\n".join(f"{document.source}\0{document.text}" for document in documents)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_index(documents: list[Document], destination: Path) -> list[Chunk]:
    chunks = chunk_documents(documents)
    payload = {
        "version": INDEX_VERSION,
        "fingerprint": _fingerprint(documents),
        "chunks": [asdict(chunk) for chunk in chunks],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return chunks


def load_index(documents: list[Document], source: Path) -> list[Chunk]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("version") != INDEX_VERSION:
        raise ValueError("retrieval index version is unsupported; rebuild the index")
    if payload.get("fingerprint") != _fingerprint(documents):
        raise ValueError("retrieval index is stale; rebuild it from the approved documents")
    return [
        Chunk(
            chunk_id=item["chunk_id"], source=item["source"], section=item["section"],
            text=item["text"], vector=tuple(item["vector"]),
        )
        for item in payload["chunks"]
    ]


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        query_vector = vectorize_text(query)
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []
        results = []
        for chunk in self.chunks:
            cosine = sum(left * right for left, right in zip(query_vector, chunk.vector))
            heading_overlap = len(query_tokens & set(_tokens(chunk.section))) / len(query_tokens)
            score = max(0.0, cosine) + 0.15 * heading_overlap
            if score > 0:
                results.append(
                    SearchResult(
                        chunk_id=chunk.chunk_id, source=chunk.source, section=chunk.section,
                        text=chunk.text, score=round(min(score, 1.0), 4),
                    )
                )
        return sorted(results, key=lambda item: (-item.score, item.chunk_id))[:limit]


def extract_grounded_answer(
    query: str, results: list[SearchResult], max_sentences: int = 2
) -> str:
    """Select the most query-relevant sentences without calling an LLM."""
    query_tokens = set(_tokens(query))
    candidates: list[tuple[float, int, str]] = []
    seen: set[str] = set()
    for result in results:
        for sentence in re.split(r"(?<=[.!?])\s+", result.text):
            sentence = sentence.strip()
            if not sentence or sentence in seen:
                continue
            seen.add(sentence)
            overlap = len(query_tokens & set(_tokens(sentence)))
            if overlap:
                candidates.append((result.score, overlap, sentence))
    selected = sorted(candidates, key=lambda item: (-item[0], -item[1], item[2]))[:max_sentences]
    return " ".join(sentence for _, _, sentence in selected)
