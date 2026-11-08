"""Real document management over the existing corpus + FAISS pipeline.

Nothing here is simulated: uploaded text is written to `data/corpus/`, the
index is rebuilt with the SAME chunker / embedder / IndexFlatIP used by
`scripts/build_index.py`, and the live retrieval service is hot-reloaded.

Only UTF-8 .txt files are accepted because `app.corpus.read_corpus` and the
notebook pipeline are plain-text based. PDF/DOCX would need a different
parser and are therefore not offered as a fake option.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import faiss
from fastapi import HTTPException

from .chunker import recursive_chunk
from .config import Settings
from .corpus import fingerprint, read_corpus
from .embedder import Embedder
from .retriever import Retriever
from .schemas import DocumentListOut, DocumentOut, UploadIn
from .store import ArtifactStore

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\- ]{0,150}\.txt$", re.IGNORECASE)
MAX_CONTENT_CHARS = 2_000_000


def safe_name(raw: str) -> str:
    """Reject path traversal and unsupported extensions."""
    name = Path(raw).name
    if name != raw or not SAFE_NAME.fullmatch(name):
        raise HTTPException(
            status_code=400,
            detail="Use a plain .txt filename (letters, numbers, spaces, . _ -).",
        )
    return name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_artifacts(
    corpus_dir: Path,
    artifacts_dir: Path,
    settings: Settings,
    embedder,
) -> dict:
    """Rebuild rag.index / chunks.jsonl / manifest.json from the current corpus.

    Mirrors scripts/build_index.py exactly (same chunker, same embedder, L2
    normalisation, IndexFlatIP). Files are written to .tmp then atomically
    replaced so a failed rebuild cannot leave a half-written index.
    """
    docs = read_corpus(corpus_dir)
    if not docs:
        raise ValueError("At least one .txt document is required in the corpus.")

    chunks: list[str] = []
    sources: list[str] = []
    for name in sorted(docs):
        for chunk in recursive_chunk(docs[name], settings.chunk_size, settings.chunk_overlap):
            chunks.append(chunk)
            sources.append(name)
    if not chunks:
        raise ValueError("The documents contain no text to index.")

    vectors = embedder.embed(chunks)
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    total_chars = sum(len(t) for t in docs.values())
    manifest = {
        "corpus_sha256": fingerprint(docs),
        "documents": len(docs),
        "total_characters": total_chars,
        "chunks": len(chunks),
        "embedding_model": settings.embedding_model,
        "embedding_max_length": settings.embedding_max_length,
        "dim": int(vectors.shape[1]),
        "index_type": "IndexFlatIP",
        "metric": "cosine (L2-normalized inner product)",
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "avg_chunk_chars": round(sum(map(len, chunks)) / len(chunks), 1),
        "built_at": _now(),
        "source_notebook": "build-a-full-rag-system.ipynb",
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    tmp_index = artifacts_dir / "rag.index.tmp"
    tmp_chunks = artifacts_dir / "chunks.jsonl.tmp"
    tmp_manifest = artifacts_dir / "manifest.json.tmp"

    faiss.write_index(index, str(tmp_index))
    with tmp_chunks.open("w", encoding="utf-8", newline="\n") as f:
        for i, (src, text) in enumerate(zip(sources, chunks)):
            f.write(json.dumps({"id": i, "source": src, "text": text}, ensure_ascii=False) + "\n")
    tmp_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    os.replace(tmp_index, artifacts_dir / "rag.index")
    os.replace(tmp_chunks, artifacts_dir / "chunks.jsonl")
    os.replace(tmp_manifest, artifacts_dir / "manifest.json")
    return manifest


def reload_service(app, rag, settings: Settings) -> None:
    """Point the running service at the freshly built artifacts."""
    store = ArtifactStore(settings.artifacts_dir, settings.corpus_dir)
    embedder = rag.embedder or Embedder(
        settings.embedding_model, settings.embedding_max_length, settings.embedding_batch_size
    )
    rag.embedder = embedder
    rag.store = store
    rag.retriever = Retriever(store, embedder, settings.hybrid_candidates)


def _lock(app) -> threading.Lock:
    lock = getattr(app.state, "rebuild_lock", None)
    if lock is None:
        lock = threading.Lock()
        app.state.rebuild_lock = lock
    return lock


def list_documents(rag, settings: Settings) -> DocumentListOut:
    store = rag.store
    counts: dict[str, int] = {}
    for record in store.chunks:
        counts[record.source] = counts.get(record.source, 0) + 1

    docs = read_corpus(settings.corpus_dir)
    rows: list[DocumentOut] = []
    for path in sorted(settings.corpus_dir.glob("*.txt")):
        text = docs.get(path.name, "")
        stat = path.stat()
        n_chunks = counts.get(path.name, 0)
        if not store.corpus_ok:
            status = "Needs indexing"
        elif n_chunks == 0:
            status = "No indexable text"
        else:
            status = "Indexed"
        rows.append(DocumentOut(
            name=path.name,
            type="TXT",
            size_bytes=stat.st_size,
            characters=len(text),
            chunks=n_chunks,
            modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            status=status,
        ))

    return DocumentListOut(
        documents=rows,
        total_documents=len(rows),
        total_chunks=len(store.chunks),
        corpus_ok=store.corpus_ok,
        embedding_model=store.manifest.get("embedding_model", ""),
        dim=store.index.d,
        built_at=store.manifest.get("built_at", ""),
    )


def _rebuild_with_rollback(app, rag, settings: Settings, backups: dict[str, bytes | None]) -> dict:
    try:
        embedder = rag.embedder or Embedder(
            settings.embedding_model, settings.embedding_max_length, settings.embedding_batch_size
        )
        manifest = build_artifacts(settings.corpus_dir, settings.artifacts_dir, settings,
                                   embedder)
        rag.embedder = embedder
        reload_service(app, rag, settings)
        return manifest
    except Exception as exc:
        for name, previous in backups.items():
            path = settings.corpus_dir / name
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        raise HTTPException(status_code=500, detail=f"Index rebuild failed, changes rolled back: {exc}") from exc


def add_documents(app, rag, settings: Settings, payload: UploadIn) -> DocumentListOut:
    corpus_dir = settings.corpus_dir
    corpus_dir.mkdir(parents=True, exist_ok=True)
    validated: list[tuple[str, str]] = []
    for item in payload.files:
        name = safe_name(item.name)
        if len(item.content) > MAX_CONTENT_CHARS:
            raise HTTPException(status_code=400, detail=f"{name} is too large (max 2 MB of text).")
        if not item.content.strip():
            raise HTTPException(status_code=400, detail=f"{name} is empty. Add some text before uploading.")
        validated.append((name, item.content))

    with _lock(app):
        backups: dict[str, bytes | None] = {}
        for name, _ in validated:
            path = corpus_dir / name
            backups[name] = path.read_bytes() if path.exists() else None
        try:
            for name, content in validated:
                (corpus_dir / name).write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not save documents: {exc}") from exc

        _rebuild_with_rollback(app, rag, settings, backups)

    result = list_documents(rag, settings)
    result.message = f"Indexed {len(validated)} document(s). The search index is up to date."
    return result


def delete_document(app, rag, settings: Settings, raw_name: str) -> DocumentListOut:
    name = safe_name(raw_name)
    path = settings.corpus_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} was not found.")
    if len(list(settings.corpus_dir.glob("*.txt"))) <= 1:
        raise HTTPException(
            status_code=400,
            detail="At least one document must stay in the library so the index can be built. "
                   "Add another document first.",
        )

    with _lock(app):
        backup = path.read_bytes()
        path.unlink()
        _rebuild_with_rollback(app, rag, settings, {name: backup})

    result = list_documents(rag, settings)
    result.message = f"Removed {name}. The search index is up to date."
    return result
