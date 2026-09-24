import json
from pathlib import Path

import pytest

from data_platform_copilot.retrieval import build_index, load_documents, load_index

ROOT = Path(__file__).parents[1]


def test_persistent_index_preserves_section_metadata(tmp_path: Path):
    documents = load_documents(ROOT / "knowledge")
    index_path = tmp_path / "knowledge-index.json"

    built = build_index(documents, index_path)
    loaded = load_index(documents, index_path)

    assert loaded == built
    assert all(chunk.chunk_id and chunk.section for chunk in loaded)
    assert json.loads(index_path.read_text())["version"] == 1


def test_stale_index_is_rejected(tmp_path: Path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    document = knowledge / "runbook.md"
    document.write_text("# Recovery\nRestart the scoring pipeline.")
    index_path = tmp_path / "index.json"
    build_index(load_documents(knowledge), index_path)

    document.write_text("# Recovery\nEscalate before restarting the pipeline.")

    with pytest.raises(ValueError, match="stale"):
        load_index(load_documents(knowledge), index_path)
