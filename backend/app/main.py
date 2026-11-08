"""FastAPI entry point.

Run from the project root:
    uvicorn app.main:app --app-dir backend --reload --port 8000
"""
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .documents import add_documents, delete_document, list_documents
from .generator import ApiGenerator, GeneratorNotConfigured, NO_KEY_MESSAGE, describe_generator
from .schemas import (
    AskRequest,
    CompareOut,
    ConnectionTestIn,
    ConnectionTestOut,
    DocumentListOut,
    HealthOut,
    SearchOut,
    SearchRequest,
    UploadIn,
)
from .service import RagService
from .store import ArtifactsMissing


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag = None
    app.state.init_error = None
    app.state.rebuild_lock = threading.Lock()
    try:
        app.state.rag = RagService.from_settings(settings)
    except (ArtifactsMissing, FileNotFoundError, RuntimeError) as exc:
        # Keep the process up so /health explains what to do instead of
        # crashing on startup with an opaque traceback.
        app.state.init_error = str(exc)
    yield


app = FastAPI(title="Course RAG API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _rag(request: Request) -> RagService:
    rag = getattr(request.app.state, "rag", None)
    if rag is None:
        detail = getattr(request.app.state, "init_error", None) or "RAG service not initialized."
        raise HTTPException(status_code=503, detail=f"{detail} Run: python scripts/build_index.py")
    return rag


@app.get("/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    rag = _rag(request)
    manifest = rag.store.manifest
    return HealthOut(
        status="ok" if rag.store.corpus_ok else "stale",
        index_ready=True,
        corpus_ok=rag.store.corpus_ok,
        chunks=len(rag.store.chunks),
        dim=rag.store.index.d,
        embedding_model=manifest.get("embedding_model", ""),
        corpus_sha256=rag.store.corpus_sha256[:16],
        **describe_generator(rag.generator),
        default_k=rag.settings.default_k,
        default_min_score=rag.settings.default_min_score,
    )


@app.post("/search", response_model=SearchOut)
def search(req: SearchRequest, request: Request) -> SearchOut:
    rag = _rag(request)
    from .service import to_source

    hits = rag.search(req.question, req.k, req.mode)
    return SearchOut(question=req.question, mode=req.mode,
                     hits=[to_source(h) for h in hits])


@app.post("/ask")
def ask(req: AskRequest, request: Request) -> StreamingResponse:
    rag = _rag(request)
    return StreamingResponse(
        rag.ask_events(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


@app.post("/compare", response_model=CompareOut)
def compare(req: AskRequest, request: Request) -> CompareOut:
    """Notebook Step 6, side by side: answer with retrieval and without it."""
    try:
        return _rag(request).compare(req)
    except GeneratorNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/documents", response_model=DocumentListOut)
def documents_list(request: Request) -> DocumentListOut:
    """Real corpus files + their actual chunk counts from the live index."""
    return list_documents(_rag(request), settings)


@app.post("/documents", response_model=DocumentListOut)
def documents_add(payload: UploadIn, request: Request) -> DocumentListOut:
    """Save real .txt files and rebuild the FAISS index before returning."""
    return add_documents(request.app, _rag(request), settings, payload)


@app.delete("/documents/{name}", response_model=DocumentListOut)
def documents_delete(name: str, request: Request) -> DocumentListOut:
    """Remove a real corpus file and rebuild the FAISS index."""
    return delete_document(request.app, _rag(request), settings, name)


@app.post("/test-connection", response_model=ConnectionTestOut)
def test_connection(req: ConnectionTestIn) -> ConnectionTestOut:
    """Verify a real API key with one tiny chat-completion call.

    Credentials come from the request body or fall back to backend/.env.
    They are never stored, logged or returned.
    """
    gen = ApiGenerator(
        api_key=settings.api_key,
        api_base=settings.api_base,
        model=settings.api_model,
        max_new_tokens=settings.llm_max_new_tokens,
        temperature=settings.api_temperature,
        timeout=settings.api_timeout,
    ).override(api_key=req.api_key, api_base=req.api_base, api_model=req.api_model)

    if not gen.loaded:
        raise HTTPException(status_code=400, detail=NO_KEY_MESSAGE)

    started = time.perf_counter()
    try:
        # Reasoning models (e.g. gpt-oss) consume part of the budget internally,
        # so leave enough headroom for an actual content token.
        preview = gen.generate("Reply with exactly: OK", max_tokens=96).strip()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ConnectionTestOut(
        ok=True,
        model=gen.model,
        api_base=gen.api_base,
        preview=preview[:200] or "(connected; no text returned)",
        latency_s=round(time.perf_counter() - started, 3),
    )
