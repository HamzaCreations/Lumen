"""Document management tests using a real (temporary) corpus and FAISS index.

A stub embedder avoids model downloads while still exercising the actual
chunker -> embed -> normalize -> IndexFlatIP -> ArtifactStore pipeline.
"""
from __future__ import annotations

import threading
from dataclasses import replace

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings
from app.documents import build_artifacts, safe_name
from app.main import app
from app.retriever import Retriever
from app.service import RagService
from app.store import ArtifactStore


class StubEmbedder:
    def embed(self, texts):
        return np.ones((len(texts), 384), dtype="float32")

    def embed_one(self, text):
        return self.embed([text])


class StubGenerator:
    name = "stub"
    loaded = True

    def stream(self, prompt):
        yield "ok"

    def generate(self, prompt):
        return "ok"


@pytest.mark.parametrize("bad", [
    "../evil.txt", "/etc/passwd.txt", "folder/a.txt", "a\\b.txt",
    "notes.pdf", ".hidden.txt", "a" * 200 + ".txt",
])
def test_safe_name_rejects_unsupported_or_unsafe_names(bad):
    with pytest.raises(HTTPException):
        safe_name(bad)


def test_safe_name_accepts_plain_txt():
    assert safe_name("My Notes 01.txt") == "My Notes 01.txt"


def test_build_artifacts_produces_a_consistent_index(tmp_path):
    corpus = tmp_path / "corpus"
    artifacts = tmp_path / "artifacts"
    corpus.mkdir()
    (corpus / "a.txt").write_text("Precision is TP over TP plus FP. " * 20, encoding="utf-8")
    (corpus / "b.txt").write_text("Recall looks at reality. " * 20, encoding="utf-8")
    cfg = replace(settings, corpus_dir=corpus, artifacts_dir=artifacts)

    manifest = build_artifacts(corpus, artifacts, cfg, StubEmbedder())

    store = ArtifactStore(artifacts, corpus)
    assert store.corpus_ok is True
    assert manifest["documents"] == 2
    assert store.index.ntotal == len(store.chunks) == manifest["chunks"]
    assert {c.source for c in store.chunks} == {"a.txt", "b.txt"}


@pytest.fixture
def doc_client(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    artifacts = tmp_path / "artifacts"
    corpus.mkdir()
    (corpus / "base.txt").write_text("Precision equals TP divided by TP plus FP. " * 20,
                                     encoding="utf-8")
    cfg = replace(settings, corpus_dir=corpus, artifacts_dir=artifacts)
    build_artifacts(corpus, artifacts, cfg, StubEmbedder())

    store = ArtifactStore(artifacts, corpus)
    embedder = StubEmbedder()
    rag = RagService(settings=cfg, store=store, embedder=embedder,
                     retriever=Retriever(store, embedder, cfg.hybrid_candidates),
                     generator=StubGenerator())
    monkeypatch.setattr(main_module, "settings", cfg)
    app.state.rag = rag
    app.state.init_error = None
    app.state.rebuild_lock = threading.Lock()
    return TestClient(app), corpus, rag


def test_get_documents_reports_real_files(doc_client):
    client, _, _ = doc_client
    res = client.get("/documents")
    assert res.status_code == 200
    body = res.json()
    assert body["total_documents"] == 1
    assert body["documents"][0]["name"] == "base.txt"
    assert body["documents"][0]["status"] == "Indexed"
    assert body["documents"][0]["chunks"] > 0
    assert body["corpus_ok"] is True


def test_upload_writes_file_and_rebuilds_index(doc_client):
    client, corpus, rag = doc_client
    before = rag.store.index.ntotal
    res = client.post("/documents", json={
        "files": [{"name": "extra.txt", "content": "Hybrid search adds keyword scores. " * 25}],
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_documents"] == 2
    assert body["corpus_ok"] is True
    assert body["total_chunks"] > before
    assert (corpus / "extra.txt").is_file()
    assert rag.store.corpus_ok is True
    assert any(d["name"] == "extra.txt" and d["status"] == "Indexed" for d in body["documents"])


def test_upload_rejects_non_txt_and_empty_content(doc_client):
    client, _, _ = doc_client
    assert client.post("/documents", json={"files": [{"name": "x.pdf", "content": "hi"}]}).status_code == 400
    assert client.post("/documents", json={"files": [{"name": "x.txt", "content": "   "}]}).status_code == 400
    assert client.post("/documents", json={"files": [{"name": "../x.txt", "content": "hi"}]}).status_code == 400


def test_delete_rebuilds_index_and_removes_file(doc_client):
    client, corpus, rag = doc_client
    assert client.post("/documents", json={
        "files": [{"name": "second.txt", "content": "Another real document. " * 20}],
    }).status_code == 200
    res = client.delete("/documents/second.txt")
    assert res.status_code == 200, res.text
    assert not (corpus / "second.txt").exists()
    assert res.json()["total_documents"] == 1
    assert res.json()["corpus_ok"] is True
    assert rag.store.corpus_ok is True


def test_deleting_the_last_document_is_rejected(doc_client):
    client, corpus, _ = doc_client
    res = client.delete("/documents/base.txt")
    assert res.status_code == 400
    assert (corpus / "base.txt").is_file()
