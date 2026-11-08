"""Tests for the real streaming API generator.

A tiny local HTTP server emulates an OpenAI-compatible /chat/completions
endpoint, so SSE parsing, token streaming, credential overrides and HTTP
error mapping are all exercised without spending a real API key.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.generator import ApiGenerator, GenerationError, GeneratorNotConfigured


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")

        if "bad-key" in self.path:
            body = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for token in ["Real ", "answer ", "from ", payload.get("model", "?")]:
            frame = json.dumps({"choices": [{"delta": {"content": token}}]})
            self.wfile.write(f"data: {frame}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="module")
def provider():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_streams_real_tokens(provider):
    gen = ApiGenerator(api_key="test-key", api_base=provider,
                       model="test-model", timeout=10)
    assert gen.loaded
    assert "".join(gen.stream("hi")) == "Real answer from test-model"
    assert gen.generate("hi") == "Real answer from test-model"


def test_runtime_credentials_override_server_defaults(provider):
    gen = ApiGenerator(api_key="", api_base="https://example.invalid/v1",
                       model="server-model")
    assert not gen.loaded
    overridden = gen.override(api_key="test-key", api_base=provider,
                              api_model="ui-model")
    assert overridden.loaded
    assert overridden.model == "ui-model"
    assert "ui-model" in overridden.generate("hi")
    assert not gen.loaded, "overrides must not mutate the shared generator"


def test_missing_key_never_produces_an_answer():
    gen = ApiGenerator(api_key="", model="some-model")
    with pytest.raises(GeneratorNotConfigured, match="No API key configured"):
        list(gen.stream("hi"))


def test_provider_401_is_mapped_to_a_clean_message(provider):
    gen = ApiGenerator(api_key="wrong", api_base=provider + "/bad-key",
                       model="x", timeout=10)
    with pytest.raises(GenerationError) as exc:
        gen.generate("hi")
    assert "401" in str(exc.value)
    assert "Incorrect API key provided" in str(exc.value)
    assert "wrong" not in str(exc.value)


def test_endpoint_normalisation():
    a = ApiGenerator(api_key="k", api_base="https://x.test/v1", model="m")
    b = ApiGenerator(api_key="k", api_base="https://x.test/v1/chat/completions", model="m")
    assert a.endpoint == "https://x.test/v1/chat/completions"
    assert b.endpoint == "https://x.test/v1/chat/completions"


def test_test_connection_accepts_runtime_credentials(provider, monkeypatch):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app import main as main_module
    from app.config import settings
    from app.main import app

    # Simulate a server with no key: the UI-supplied key must still work.
    monkeypatch.setattr(main_module, "settings", replace(settings, api_key=""))
    res = TestClient(app).post("/test-connection", json={
        "api_key": "runtime-key", "api_base": provider, "api_model": "ui-model",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["model"] == "ui-model"
    assert body["preview"]


def test_full_ask_path_uses_runtime_credentials(provider):
    """End-to-end: UI-supplied key overrides an unconfigured server and the
    answer is streamed from a real HTTP provider, not fabricated locally."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.retriever import Hit
    from app.service import RagService

    class _Retriever:
        def retrieve(self, question, k, mode="semantic"):
            return [Hit(id=0, source="12_evaluation_metrics.txt", score=0.662,
                        semantic_score=0.662, text="Precision = TP / (TP + FP)")]

    class _Store:
        manifest = {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"}
        chunks = [None]
        index = SimpleNamespace(d=384, ntotal=1)
        corpus_ok = True
        corpus_sha256 = "abc"

    app.state.rag = RagService(
        settings=settings,
        store=_Store(),
        retriever=_Retriever(),
        generator=ApiGenerator(api_key="", api_base="https://example.invalid/v1",
                               model="server-model", timeout=10),
    )
    app.state.init_error = None

    res = TestClient(app).post("/ask", json={
        "question": "What is precision?", "k": 1, "min_score": 0.4,
        "api_key": "runtime-key", "api_base": provider, "api_model": "ui-model",
    })
    text = res.text
    assert res.status_code == 200
    assert "event: meta" in text and "event: token" in text and "event: done" in text
    assert "Real answer from ui-model" in text
    assert "No API key configured" not in text
    assert "event: error" not in text
