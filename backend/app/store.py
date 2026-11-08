"""Loads the three persisted artifacts produced by scripts/build_index.py.

FAISS row i corresponds to line i+1 of chunks.jsonl. This is the mapping the
notebook kept only in memory; persisting it is what makes a separate server
process possible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from .corpus import fingerprint, read_corpus


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    source: str
    text: str


class ArtifactsMissing(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, artifacts_dir: Path, corpus_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.manifest = self._load_manifest()
        self.chunks = self._load_chunks()
        self.index = faiss.read_index(str(artifacts_dir / "rag.index"))

        if self.index.ntotal != len(self.chunks):
            raise ArtifactsMissing(
                f"Index has {self.index.ntotal} vectors but chunks.jsonl has {len(self.chunks)} rows. "
                "Re-run: python scripts/build_index.py"
            )
        if self.index.d != self.manifest.get("dim"):
            raise ArtifactsMissing("Index dimension does not match manifest.json.")
        if len(self.chunks) != self.manifest.get("chunks"):
            raise ArtifactsMissing("Chunk count does not match manifest.json.")

        self.corpus_sha256 = self.manifest.get("corpus_sha256", "")
        try:
            self.corpus_ok = fingerprint(read_corpus(corpus_dir)) == self.corpus_sha256
        except OSError:
            self.corpus_ok = False

    def _load_manifest(self) -> dict:
        path = self.artifacts_dir / "manifest.json"
        if not path.exists():
            raise ArtifactsMissing(f"Missing {path}. Re-run: python scripts/build_index.py")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_chunks(self) -> list[ChunkRecord]:
        path = self.artifacts_dir / "chunks.jsonl"
        if not path.exists():
            raise ArtifactsMissing(f"Missing {path}. Re-run: python scripts/build_index.py")
        records = []
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["id"] != i:
                    raise ArtifactsMissing(f"chunks.jsonl row {i} has id {row['id']}; ids must be sequential.")
                records.append(ChunkRecord(id=i, source=row["source"], text=row["text"]))
        return records

    @property
    def texts(self) -> list[str]:
        return [c.text for c in self.chunks]

    def search(self, query_vector: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """query_vector must already be L2-normalized (cosine via IndexFlatIP)."""
        k = min(k, self.index.ntotal)
        return self.index.search(query_vector, k)

    def get(self, idx: int) -> ChunkRecord:
        return self.chunks[idx]
