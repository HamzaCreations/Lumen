"""Request/response contracts for the HTTP API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(3, ge=1, le=10)
    min_score: float = Field(0.40, ge=0.0, le=1.0)
    mode: Literal["semantic", "hybrid"] = "semantic"
    include_baseline: bool = False
    # Runtime credentials. Never written to disk, never logged, never echoed.
    # When omitted the server falls back to backend/.env (RAG_API_*).
    api_key: str | None = Field(None, max_length=512)
    api_base: str | None = Field(None, max_length=300)
    api_model: str | None = Field(None, max_length=200)


class ConnectionTestIn(BaseModel):
    api_key: str | None = Field(None, max_length=512)
    api_base: str | None = Field(None, max_length=300)
    api_model: str | None = Field(None, max_length=200)


class ConnectionTestOut(BaseModel):
    ok: bool
    model: str
    api_base: str
    preview: str
    latency_s: float


class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(5, ge=1, le=20)
    mode: Literal["semantic", "hybrid"] = "semantic"


class SourceOut(BaseModel):
    id: int
    source: str
    score: float
    semantic_score: float
    text: str
    snippet: str


class SearchOut(BaseModel):
    question: str
    mode: str
    hits: list[SourceOut]


class CompareOut(BaseModel):
    with_rag: str
    without_rag: str
    sources: list[SourceOut]
    abstained: bool


class DocumentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., max_length=2_000_000)


class UploadIn(BaseModel):
    files: list[DocumentIn] = Field(..., min_length=1, max_length=20)


class DocumentOut(BaseModel):
    name: str
    type: str
    size_bytes: int
    characters: int
    chunks: int
    modified: str
    status: str


class DocumentListOut(BaseModel):
    documents: list[DocumentOut]
    total_documents: int
    total_chunks: int
    corpus_ok: bool
    embedding_model: str
    dim: int
    built_at: str
    message: str = ""


class HealthOut(BaseModel):
    status: str
    index_ready: bool
    corpus_ok: bool
    chunks: int
    dim: int
    embedding_model: str
    corpus_sha256: str
    llm_backend: str
    llm_model: str = ""
    llm_loaded: bool
    llm_ready: bool = True
    api_base: str = ""
    api_key_configured: bool = False
    default_k: int
    default_min_score: float
