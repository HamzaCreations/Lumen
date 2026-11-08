"""Retrieval, faithful to notebook Steps 4a and 8.

- semantic: cosine over the L2-normalized IndexFlatIP index.
- hybrid: the notebook's additive blend of cosine + min-max-normalized TF-IDF.
  (`Retriever` also exposes the raw cosine for every hybrid hit so the
  abstention threshold stays meaningful when the ranking score is > 1.)
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

import faiss
import numpy as np

from .embedder import Embedder
from .store import ArtifactStore


@dataclass(frozen=True)
class Hit:
    id: int
    source: str
    score: float
    semantic_score: float
    text: str

    @property
    def snippet(self) -> str:
        return " ".join(self.text.split())[:240]


class Retriever:
    def __init__(self, store: ArtifactStore, embedder: Embedder, hybrid_candidates: int = 20):
        self.store = store
        self.embedder = embedder
        self.hybrid_candidates = hybrid_candidates
        self._tfidf = None
        self._matrix = None
        self._lock = threading.Lock()

    def _ensure_tfidf(self) -> None:
        if self._tfidf is not None:
            return
        with self._lock:
            if self._tfidf is not None:
                return
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._tfidf = TfidfVectorizer().fit(self.store.texts)
            self._matrix = self._tfidf.transform(self.store.texts)

    def _query_vector(self, question: str) -> np.ndarray:
        q = self.embedder.embed_one(question)
        faiss.normalize_L2(q)
        return q

    def _cosine(self, idx: int, q: np.ndarray) -> float:
        return float(np.dot(self.store.index.reconstruct(idx), q[0]))

    def semantic(self, question: str, k: int) -> list[Hit]:
        q = self._query_vector(question)
        scores, ids = self.store.search(q, k)
        hits = []
        for i in range(len(ids[0])):
            idx = int(ids[0][i])
            if idx < 0:
                continue
            rec = self.store.get(idx)
            s = float(scores[0][i])
            hits.append(Hit(id=idx, source=rec.source, score=s, semantic_score=s, text=rec.text))
        return hits

    def hybrid(self, question: str, k: int) -> list[Hit]:
        self._ensure_tfidf()
        candidates = min(self.hybrid_candidates, self.store.index.ntotal)
        q = self._query_vector(question)
        scores, ids = self.store.search(q, candidates)
        sem = {int(ids[0][i]): float(scores[0][i]) for i in range(candidates) if ids[0][i] >= 0}

        key_scores = (self._tfidf.transform([question]) @ self._matrix.T).toarray()[0]
        key_top = key_scores.argsort()[::-1][:candidates]
        key = {int(i): float(key_scores[i]) for i in key_top}

        combined: dict[int, float] = {}
        for i, s in sem.items():
            combined[i] = combined.get(i, 0) + s
        max_key = max(key.values()) if key else 1.0
        for i, s in key.items():
            combined[i] = combined.get(i, 0) + (s / max_key if max_key else 0.0)

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:k]
        hits = []
        for idx, score in ranked:
            rec = self.store.get(idx)
            cos = sem.get(idx, self._cosine(idx, q))
            hits.append(Hit(id=idx, source=rec.source, score=float(score),
                            semantic_score=cos, text=rec.text))
        return hits

    def retrieve(self, question: str, k: int, mode: str = "semantic") -> list[Hit]:
        if mode == "hybrid":
            return self.hybrid(question, k)
        return self.semantic(question, k)
