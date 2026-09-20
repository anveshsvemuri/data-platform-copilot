from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Document:
    source: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    source: str
    text: str
    score: float


def _tokens(text: str) -> set[str]:
    stopwords = {
        "and",
        "are",
        "for",
        "from",
        "has",
        "how",
        "the",
        "this",
        "what",
        "when",
        "where",
        "which",
        "who",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", text.lower())
        if len(token) > 2 and token not in stopwords
    }


def load_documents(directory: Path) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(Document(source=path.name, text=text))
    if not documents:
        raise ValueError(f"no Markdown knowledge documents found in {directory}")
    return documents


class Retriever:
    def __init__(self, documents: list[Document]):
        self.documents = documents

    def search(self, query: str, limit: int = 3) -> list[SearchResult]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        results = []
        for document in self.documents:
            doc_tokens = _tokens(document.text)
            overlap = len(query_tokens & doc_tokens)
            score = overlap / math.sqrt(len(query_tokens) * max(len(doc_tokens), 1))
            if score > 0:
                results.append(SearchResult(document.source, document.text, round(score, 4)))
        return sorted(results, key=lambda item: (-item.score, item.source))[:limit]
