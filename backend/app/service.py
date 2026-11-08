"""Application service: orchestrates retrieval, abstention and generation.

Kept independent of FastAPI so it can be exercised directly in tests with a
fake retriever and a stub generator.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Iterator

from .config import Settings
from .embedder import Embedder
from .generator import (
    Generator,
    GeneratorNotConfigured,
    NO_KEY_MESSAGE,
    build_generator,
    describe_generator,
)
from .prompt import build_plain_prompt, build_prompt
from .retriever import Hit, Retriever
from .schemas import AskRequest, CompareOut, SourceOut
from .store import ArtifactStore

ABSTAIN_MESSAGE = (
    "I do not know. The course documents do not contain enough information to "
    "answer that question, so I will not guess."
)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def to_source(hit: Hit) -> SourceOut:
    return SourceOut(
        id=hit.id,
        source=hit.source,
        score=round(hit.score, 4),
        semantic_score=round(hit.semantic_score, 4),
        text=hit.text,
        snippet=hit.snippet,
    )


@dataclass
class RagService:
    settings: Settings
    generator: Generator
    store: ArtifactStore | None = None
    embedder: Embedder | None = None
    retriever: Retriever | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "RagService":
        store = ArtifactStore(settings.artifacts_dir, settings.corpus_dir)
        embedder = Embedder(settings.embedding_model, settings.embedding_max_length,
                            settings.embedding_batch_size)
        retriever = Retriever(store, embedder, settings.hybrid_candidates)
        return cls(settings=settings, store=store, embedder=embedder,
                   retriever=retriever, generator=build_generator(settings))

    def search(self, question: str, k: int, mode: str) -> list[Hit]:
        return self.retriever.retrieve(question, k, mode)

    def _generator_for(self, req: AskRequest) -> Generator:
        """Apply UI-supplied credentials for this request only, if provided."""
        override = getattr(self.generator, "override", None)
        if callable(override) and (req.api_key or req.api_base or req.api_model):
            return override(api_key=req.api_key, api_base=req.api_base,
                            api_model=req.api_model)
        return self.generator

    @staticmethod
    def _check_generator(gen: Generator) -> str | None:
        return None if describe_generator(gen)["llm_ready"] else NO_KEY_MESSAGE

    def _abstains(self, hits: list[Hit], min_score: float) -> bool:
        if not hits:
            return True
        return max(h.semantic_score for h in hits) < min_score

    def ask_events(self, req: AskRequest) -> Iterator[str]:
        started = time.perf_counter()
        hits = self.search(req.question, req.k, req.mode)
        sources = [to_source(h).model_dump() for h in hits]
        top = max((h.semantic_score for h in hits), default=0.0)
        abstained = self._abstains(hits, req.min_score)
        retrieved_at = time.perf_counter()

        yield sse("meta", {
            "sources": sources,
            "abstained": abstained,
            "top_score": round(top, 4),
            "min_score": req.min_score,
            "k": req.k,
            "mode": req.mode,
            "timings": {"retrieval_s": round(retrieved_at - started, 3)},
        })

        if abstained:
            detail = (f"{ABSTAIN_MESSAGE}\n\n"
                      f"(Best retrieval score {top:.3f} is below the {req.min_score:.2f} "
                      "threshold, so no answer was generated.)")
            yield sse("token", {"text": detail})
            yield sse("done", {"answer": detail, "abstained": True,
                               "timings": {"retrieval_s": round(retrieved_at - started, 3),
                                           "generation_s": 0.0}})
            return

        gen = self._generator_for(req)
        problem = self._check_generator(gen)
        if problem:
            yield sse("error", {"message": problem})
            return

        prompt = build_prompt(req.question, hits)
        pieces: list[str] = []
        try:
            for token in gen.stream(prompt):
                pieces.append(token)
                yield sse("token", {"text": token})
        except GeneratorExit:
            return
        except Exception as exc:
            message = str(exc) if isinstance(exc, (RuntimeError, ValueError)) else f"{type(exc).__name__}: {exc}"
            yield sse("error", {"message": message})
            return

        answer = "".join(pieces).strip()
        gen_s = round(time.perf_counter() - retrieved_at, 3)

        if req.include_baseline:
            try:
                baseline = gen.generate(build_plain_prompt(req.question)).strip()
                yield sse("baseline", {"text": baseline})
            except Exception as exc:
                yield sse("baseline", {"text": f"(baseline unavailable: {exc})"})

        yield sse("done", {
            "answer": answer,
            "abstained": False,
            "prompt_chars": len(prompt),
            "timings": {"retrieval_s": round(retrieved_at - started, 3),
                        "generation_s": gen_s},
        })

    def compare(self, req: AskRequest) -> CompareOut:
        hits = self.search(req.question, req.k, req.mode)
        sources = [to_source(h) for h in hits]
        if self._abstains(hits, req.min_score):
            return CompareOut(with_rag=ABSTAIN_MESSAGE, without_rag="", sources=sources,
                              abstained=True)
        gen = self._generator_for(req)
        problem = self._check_generator(gen)
        if problem:
            raise GeneratorNotConfigured(problem)
        with_rag = gen.generate(build_prompt(req.question, hits)).strip()
        without_rag = gen.generate(build_plain_prompt(req.question)).strip()
        return CompareOut(with_rag=with_rag, without_rag=without_rag,
                          sources=sources, abstained=False)
