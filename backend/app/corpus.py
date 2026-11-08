"""Corpus loading and fingerprinting, shared by the offline builder and the
server. read_text() applies universal newline translation, which is why the
13 files total 276,888 characters here (their raw byte sizes are larger).
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


def read_corpus(corpus_dir: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(corpus_dir.glob("*.txt"))}


def fingerprint(docs: dict[str, str]) -> str:
    h = hashlib.sha256()
    for name in sorted(docs):
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(docs[name].encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def ensure_corpus(corpus_dir: Path, zip_path: Path) -> dict[str, str]:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    docs = read_corpus(corpus_dir)
    if docs:
        return docs
    if not zip_path.exists():
        raise FileNotFoundError(f"No corpus in {corpus_dir} and no zip at {zip_path}")
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if n.endswith(".txt"))
        for n in names:
            (corpus_dir / Path(n).name).write_bytes(z.read(n))
    return read_corpus(corpus_dir)
