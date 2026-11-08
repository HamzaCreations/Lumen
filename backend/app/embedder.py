"""Verbatim port of `embed` from build-a-full-rag-system.ipynb (Step 2).

The notebook loads `sentence-transformers/all-MiniLM-L6-v2` with AutoTokenizer
+ AutoModel and does MANUAL masked mean pooling over last_hidden_state. It does
NOT use the SentenceTransformer class. Swapping libraries changes the vectors
and silently invalidates any saved index, so this module is the single source
of truth used by both the offline builder and the online query path.
"""
from __future__ import annotations

import threading

import numpy as np


class Embedder:
    def __init__(self, model_name: str, max_length: int = 256, batch_size: int = 32):
        self.model_name = model_name
        self.max_length = max_length
        self.batch_size = batch_size
        self._tokenizer = None
        self._model = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        """Lazy, thread-safe model load (first call downloads ~90 MB from HF)."""
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModel.from_pretrained(self.model_name)
            model.eval()
            self._model = model

    def embed(self, texts: list[str] | tuple[str, ...]) -> np.ndarray:
        """Return float32 (n, 384) vectors, identical to the notebook's embed()."""
        import torch

        self.load()
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            encoded = self._tokenizer(batch, padding=True, truncation=True,
                                      max_length=self.max_length, return_tensors="pt")
            with torch.no_grad():
                output = self._model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            mean = (output * mask).sum(1) / mask.sum(1)
            vectors.append(mean.numpy())
        return np.vstack(vectors).astype("float32")

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])
