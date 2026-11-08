"""API contract tests.

Retrieval and generation are replaced with local test doubles so the suite
runs offline with no FAISS index, no embedding model and no API key. The
shipped product itself contains no mock generator.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.generator import ApiGenerator
from app.main import app
from app.retriever import Hit
from app.service import RagService

GOOD_HITS = [
    Hit(id=0, source="12_evaluation_metrics.txt", score=0.662,
        semantic_score=0.662, text="Precision = TP / (TP + FP)"),
    Hit(id=1, source="12_evaluation_metrics.txt", score=0.593,
        semantic_score=0.593, text="Precision looks at the model's alerts."),
]
WEAK_HITS = [
    Hit(id=2, source="09_ml_scikit_learn.txt", score=0.319,
        semantic_score=0.319, text="K-Nearest Neighbors is a classifier."),
]


class StubGenerator:
    """Deterministic test double - not part of the product."""

    name = "stub"
    loaded = True

    def stream(self, prompt: str):
        yield ("Grounded answer from the retrieved course material."
               if "Context:" in prompt else "Answer without retrieval.")

    def generate(self, prompt: str) -> str:
        return "".join(self.stream(prompt))


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def retrieve(self, question, k, mode="semantic"):
        return self.hits[:k]


class FakeStore:
    manifest = {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"}
    chunks = [None] * 1342
    index = SimpleNamespace(d=384, ntotal=1342)
    corpus_ok = True
    corpus_sha256 = "0123456789abcdef"


@pytest.fixture
def client():
    app.state.rag = RagService(settings=settings, store=FakeStore(),
                               retriever=FakeRetriever(GOOD_HITS),
                               generator=StubGenerator())
    app.state.init_error = None
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["chunks"] == 1342 and body["dim"] == 384
    assert body["llm_backend"] == "stub"
    assert body["llm_ready"] is True
    assert body["api_key_configured"] is False
    assert "llm_model" in body and "api_base" in body


def test_search_returns_structured_sources(client):
    res = client.post("/search", json={"question": "What is precision?", "k": 2})
    assert res.status_code == 200
    hits = res.json()["hits"]
    assert len(hits) == 2
    assert hits[0]["source"] == "12_evaluation_metrics.txt"
    assert hits[0]["semantic_score"] == 0.662
    assert "snippet" in hits[0]


def test_ask_streams_meta_tokens_and_done(client):
    res = client.post("/ask", json={"question": "What is precision?", "k": 2, "min_score": 0.4})
    assert res.status_code == 200
    text = res.text
    assert "event: meta" in text
    assert "event: token" in text
    assert "event: done" in text
    assert "Grounded answer" in text
    assert '"abstained": false' in text


def test_low_score_abstains_without_calling_the_model(client):
    app.state.rag.retriever = FakeRetriever(WEAK_HITS)
    res = client.post("/ask", json={"question": "What is LangChain?", "k": 3, "min_score": 0.4})
    text = res.text
    assert "I do not know" in text
    assert '"abstained": true' in text
    assert "Grounded answer" not in text, "abstention must skip generation entirely"


def test_baseline_event_is_emitted_when_requested(client):
    res = client.post("/ask", json={"question": "What is precision?", "k": 2,
                                    "min_score": 0.4, "include_baseline": True})
    assert "event: baseline" in res.text


def test_compare_returns_both_answers(client):
    res = client.post("/compare", json={"question": "What is precision?", "k": 2})
    assert res.status_code == 200
    body = res.json()
    assert "Grounded answer" in body["with_rag"]
    assert "without retrieval" in body["without_rag"]
    assert len(body["sources"]) == 2


def test_ask_without_api_key_returns_an_error_not_a_fake_answer(client):
    app.state.rag.generator = ApiGenerator(api_key="", model="gpt-4o-mini")
    res = client.post("/ask", json={"question": "What is precision?", "k": 2, "min_score": 0.4})
    text = res.text
    assert "event: meta" in text
    assert "event: error" in text
    assert "No API key configured" in text
    assert "event: token" not in text
    assert "event: done" not in text


def test_compare_without_api_key_returns_503(client):
    app.state.rag.generator = ApiGenerator(api_key="", model="gpt-4o-mini")
    res = client.post("/compare", json={"question": "What is precision?", "k": 2})
    assert res.status_code == 503
    assert "No API key configured" in res.json()["detail"]


def test_test_connection_rejects_missing_key(client, monkeypatch):
    # Force an unconfigured server so this stays deterministic even when
    # backend/.env contains a real key (and never makes a network call).
    from dataclasses import replace

    from app import main as main_module

    monkeypatch.setattr(main_module, "settings", replace(settings, api_key=""))
    res = client.post("/test-connection", json={})
    assert res.status_code == 400
    assert "No API key configured" in res.json()["detail"]


def test_validation_rejects_empty_question(client):
    res = client.post("/ask", json={"question": ""})
    assert res.status_code == 422
