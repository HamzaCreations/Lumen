"""Configuration. All values can be overridden with RAG_* environment variables
or a `backend/.env` file. No third-party settings dependency is required.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_file = ROOT / "backend" / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _get(key: str, default: str) -> str:
    return os.environ.get("RAG_" + key, default)


def _bool(key: str, default: bool) -> bool:
    return _get(key, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    corpus_dir: Path = field(default_factory=lambda: Path(_get("CORPUS_DIR", str(ROOT / "data" / "corpus"))))
    artifacts_dir: Path = field(default_factory=lambda: Path(_get("ARTIFACTS_DIR", str(ROOT / "artifacts"))))

    # Must match the notebook exactly, otherwise saved vectors are not compatible.
    embedding_model: str = field(default_factory=lambda: _get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    embedding_max_length: int = field(default_factory=lambda: int(_get("EMBEDDING_MAX_LENGTH", "256")))
    embedding_batch_size: int = field(default_factory=lambda: int(_get("EMBEDDING_BATCH_SIZE", "32")))
    chunk_size: int = field(default_factory=lambda: int(_get("CHUNK_SIZE", "300")))
    chunk_overlap: int = field(default_factory=lambda: int(_get("CHUNK_OVERLAP", "50")))

    default_k: int = field(default_factory=lambda: int(_get("DEFAULT_K", "3")))
    # Calibrated on the notebook's honest test: in-domain 0.62-0.76,
    # out-of-domain ("What is LangChain?") 0.248-0.319.
    default_min_score: float = field(default_factory=lambda: float(_get("DEFAULT_MIN_SCORE", "0.40")))
    hybrid_candidates: int = field(default_factory=lambda: int(_get("HYBRID_CANDIDATES", "20")))

    # api    = any OpenAI-compatible chat-completions endpoint (DEFAULT, real answers)
    # local  = notebook's Qwen2.5-1.5B-Instruct (faithful, slow on CPU)
    # ollama = same model quantized via Ollama (recommended on CPU)
    # hf     = Hugging Face Inference API (needs RAG_HF_TOKEN)
    llm_backend: str = field(default_factory=lambda: _get("LLM_BACKEND", "api"))
    llm_model: str = field(default_factory=lambda: _get("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"))
    llm_max_new_tokens: int = field(default_factory=lambda: int(_get("LLM_MAX_NEW_TOKENS", "300")))
    llm_device: str = field(default_factory=lambda: _get("LLM_DEVICE", "auto"))
    llm_load_on_startup: bool = field(default_factory=lambda: _bool("LLM_LOAD_ON_STARTUP", False))

    # --- Real hosted generation -------------------------------------------
    # RAG_API_KEY also falls back to a plain OPENAI_API_KEY in the environment.
    # A key supplied by the UI is never written to disk and never logged.
    api_key: str = field(default_factory=lambda: os.environ.get("RAG_API_KEY")
                         or os.environ.get("OPENAI_API_KEY") or "")
    api_base: str = field(default_factory=lambda: _get("API_BASE", "https://api.openai.com/v1"))
    api_model: str = field(default_factory=lambda: _get("API_MODEL", "gpt-4o-mini"))
    api_temperature: float = field(default_factory=lambda: float(_get("API_TEMPERATURE", "0")))
    api_timeout: float = field(default_factory=lambda: float(_get("API_TIMEOUT", "120")))

    hf_token: str = field(default_factory=lambda: _get("HF_TOKEN", ""))
    hf_model: str = field(default_factory=lambda: _get("HF_MODEL", "deepseek-ai/DeepSeek-V3-0324"))
    ollama_url: str = field(default_factory=lambda: _get("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _get("OLLAMA_MODEL", "qwen2.5:1.5b"))

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in _get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
        )
    )


settings = Settings()
