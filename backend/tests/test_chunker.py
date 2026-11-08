"""Parity tests against build-a-full-rag-system.ipynb.

These need no model download: they prove the port of recursive_chunk and the
corpus produce exactly the numbers printed in the notebook (Step 0b / Step 1b).
"""
from __future__ import annotations

from pathlib import Path

from app.chunker import recursive_chunk
from app.corpus import read_corpus

ROOT = Path(__file__).resolve().parents[2]


def test_notebook_toy_example_matches_verbatim() -> None:
    test = ("First sentence here. Second sentence here.\n\nNew paragraph "
            "starts here. It keeps going for a while.")
    assert recursive_chunk(test, chunk_size=60, chunk_overlap=10) == [
        "First sentence here. Second sentence here.\n\nNew paragr",
        "New paragraph starts here. It keeps going for a while.",
    ]


def test_corpus_and_chunk_stats_match_kaggle() -> None:
    docs = read_corpus(ROOT / "data" / "corpus")
    assert len(docs) == 13
    assert sum(len(t) for t in docs.values()) == 276_888

    chunks: list[str] = []
    for name in sorted(docs):
        chunks.extend(recursive_chunk(docs[name]))

    assert len(chunks) == 1342
    assert round(sum(map(len, chunks)) / len(chunks), 1) == 254.7
    assert max(map(len, chunks)) == 350
    assert min(map(len, chunks)) == 8


def test_first_two_chunks_match_notebook_output() -> None:
    docs = read_corpus(ROOT / "data" / "corpus")
    chunks = recursive_chunk(docs["01_ai_fundamentals.txt"])
    assert chunks[0].startswith("AI Fundamentals")
    assert "Before you write a line of code" in chunks[1]
