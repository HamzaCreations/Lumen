"""Offline ingestion: corpus -> chunks -> embeddings -> FAISS index.

Run once (and again whenever the corpus or chunking parameters change):

    python scripts/build_index.py
    python scripts/build_index.py --verify   # also runs the golden retrieval check

This is the piece the notebook never did: it persists the chunk text and
source filenames alongside rag.index, so a separate server process can serve
answers. FAISS row i is chunk i in chunks.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import faiss  # noqa: E402
from app.chunker import recursive_chunk  # noqa: E402
from app.config import settings  # noqa: E402
from app.corpus import ensure_corpus, fingerprint  # noqa: E402
from app.embedder import Embedder  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="run the notebook golden retrieval check")
    args = ap.parse_args()

    docs = ensure_corpus(settings.corpus_dir, ROOT / "rag_course_docs.zip")
    total_chars = sum(len(t) for t in docs.values())
    print(f"Corpus: {len(docs)} files, {total_chars:,} characters")
    if total_chars != 276_888:
        print("WARNING: corpus size differs from the notebook's 276,888 characters.")

    chunks: list[str] = []
    sources: list[str] = []
    for name in sorted(docs):
        for c in recursive_chunk(docs[name], settings.chunk_size, settings.chunk_overlap):
            chunks.append(c)
            sources.append(name)
    print(f"Chunks: {len(chunks)} | avg {sum(map(len, chunks)) / len(chunks):.1f} chars "
          f"| min {min(map(len, chunks))} | max {max(map(len, chunks))}")

    embedder = Embedder(settings.embedding_model, settings.embedding_max_length,
                        settings.embedding_batch_size)
    print(f"Embedding with {settings.embedding_model} ...")
    vectors = embedder.embed(chunks)
    print(f"Embeddings shape: {vectors.shape}")

    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    print(f"Index: IndexFlatIP | dim {index.d} | vectors {index.ntotal}")

    out = settings.artifacts_dir
    out.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out / "rag.index"))

    with (out / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for i, (src, text) in enumerate(zip(sources, chunks)):
            f.write(json.dumps({"id": i, "source": src, "text": text}, ensure_ascii=False) + "\n")

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
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_notebook": "build-a-full-rag-system.ipynb",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out / 'rag.index'}, chunks.jsonl, manifest.json")

    if args.verify:
        q = embedder.embed_one("What is precision?")
        faiss.normalize_L2(q)
        scores, ids = index.search(q, 3)
        top = float(scores[0][0])
        print(f"\nGolden check: 'What is precision?' top-1 score = {top:.3f} "
              f"from {sources[int(ids[0][0])]} (notebook: 0.662 from 12_evaluation_metrics.txt)")
        if abs(top - 0.662) > 0.01:
            raise SystemExit("Golden check FAILED - embeddings differ from the notebook.")
        print("Golden check PASSED - local pipeline matches Kaggle.")


if __name__ == "__main__":
    main()
