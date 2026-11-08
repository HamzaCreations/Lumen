"""Generation providers.

The default backend `api` produces REAL answers from any OpenAI-compatible
``/chat/completions`` endpoint: OpenAI, OpenRouter, Groq, DeepSeek, Together,
Google Gemini (OpenAI-compat), Hugging Face router, SiliconFlow, or a local
vLLM / LM Studio server. Tokens are streamed straight through to the browser.

Other backends:
  - `local`  : notebook Step 6 verbatim, Qwen/Qwen2.5-1.5B-Instruct via
               transformers.pipeline, greedy, max_new_tokens=300
  - `ollama` : the same Qwen model quantized, fast on CPU
  - `hf`     : Hugging Face Inference API

There is deliberately NO mock generator in the shipped product. The test
suite supplies its own stub. Missing or invalid credentials produce an
explicit error, never a made-up answer.
"""
from __future__ import annotations

import json
import threading
from typing import Iterator, Protocol

import httpx

from .config import Settings


class Generator(Protocol):
    name: str

    @property
    def loaded(self) -> bool: ...

    def stream(self, prompt: str) -> Iterator[str]: ...

    def generate(self, prompt: str) -> str: ...


class GenerationError(RuntimeError):
    """Sanitised provider error, safe to display (never contains the API key)."""


class GeneratorNotConfigured(RuntimeError):
    """No usable credentials/model configured yet."""


NO_KEY_MESSAGE = (
    "No API key configured. Add your key in the Connection panel, or set "
    "RAG_API_KEY together with RAG_API_BASE / RAG_API_MODEL in backend/.env "
    "and restart the server. No answer was generated."
)

DEFAULT_API_BASE = "https://api.openai.com/v1"


def _chat_messages(prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prompt}]


class ApiGenerator:
    """Real, streaming generation via an OpenAI-compatible chat-completions API."""

    name = "api"

    def __init__(
        self,
        api_key: str = "",
        api_base: str = DEFAULT_API_BASE,
        model: str = "gpt-4o-mini",
        max_new_tokens: int = 300,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ):
        self.api_key = (api_key or "").strip()
        self.api_base = (api_base or DEFAULT_API_BASE).strip().rstrip("/")
        self.model = (model or "").strip()
        self.max_new_tokens = int(max_new_tokens)
        self.temperature = float(temperature)
        self.timeout = float(timeout)

    @property
    def loaded(self) -> bool:
        return bool(
            self.api_key
            and self.model
            and self.api_base.startswith(("http://", "https://"))
        )

    def override(self, *, api_key=None, api_base=None, api_model=None) -> "ApiGenerator":
        """Per-request copy using UI-supplied credentials. Nothing is persisted."""
        return ApiGenerator(
            api_key=api_key or self.api_key,
            api_base=api_base or self.api_base,
            model=api_model or self.model,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
        )

    @property
    def endpoint(self) -> str:
        base = self.api_base.rstrip("/")
        return base if base.endswith("/chat/completions") else base + "/chat/completions"

    def _payload(self, prompt: str, max_tokens: int | None) -> dict:
        return {
            "model": self.model,
            "messages": _chat_messages(prompt),
            "max_tokens": max_tokens or self.max_new_tokens,
            "temperature": self.temperature,
            "stream": True,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    @staticmethod
    def _http_error(status: int, body: str) -> GenerationError:
        hints = {
            400: "Bad request (400) - check the model name and request parameters.",
            401: "Invalid or missing API key (401).",
            403: "Access denied (403) - check key permissions or model access.",
            404: "Endpoint or model not found (404) - check Base URL and Model.",
            408: "Provider request timed out (408).",
            429: "Rate limited or quota exceeded (429).",
            500: "Provider server error (500).",
            502: "Provider gateway error (502).",
            503: "Provider temporarily unavailable (503).",
        }
        hint = hints.get(status, f"Provider returned HTTP {status}.")
        detail = ""
        try:
            parsed = json.loads(body)
            err = parsed.get("error", parsed)
            detail = str(err.get("message") or err.get("detail") or "") if isinstance(err, dict) else str(err)
        except (ValueError, TypeError):
            detail = body[:300]
        return GenerationError(f"{hint} {detail[:300]}".strip())

    def stream(self, prompt: str, max_tokens: int | None = None) -> Iterator[str]:
        if not self.loaded:
            raise GeneratorNotConfigured(NO_KEY_MESSAGE)

        timeout = httpx.Timeout(connect=10.0, read=self.timeout, write=10.0, pool=10.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream(
                    "POST", self.endpoint, json=self._payload(prompt, max_tokens),
                    headers=self._headers(),
                ) as response:
                    if response.status_code != 200:
                        body = response.read().decode("utf-8", "replace")
                        raise self._http_error(response.status_code, body)

                    for line in response.iter_lines():
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(chunk, dict) and chunk.get("error"):
                            raise GenerationError(f"Provider error: {str(chunk['error'])[:300]}")
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if isinstance(content, list):  # some providers return content parts
                            content = "".join(
                                part.get("text", "") for part in content
                                if isinstance(part, dict)
                            )
                        if content:
                            yield content
        except (GenerationError, GeneratorNotConfigured):
            raise
        except httpx.TimeoutException as exc:
            raise GenerationError(
                f"Provider timed out after {self.timeout:.0f}s. Increase RAG_API_TIMEOUT "
                "or try a faster model."
            ) from exc
        except httpx.RequestError as exc:
            raise GenerationError(
                f"Could not reach {self.api_base}: {type(exc).__name__}: {exc}"
            ) from exc

    def generate(self, prompt: str, max_tokens: int | None = None) -> str:
        return "".join(self.stream(prompt, max_tokens))


class LocalQwenGenerator:
    """Faithful port of notebook Step 6."""

    name = "local"

    def __init__(self, model_name: str, max_new_tokens: int = 300, device: str = "auto"):
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.device = device
        self._pipe = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._pipe is not None

    def load(self) -> None:
        if self._pipe is not None:
            return
        with self._lock:
            if self._pipe is not None:
                return
            from transformers import pipeline

            self._pipe = pipeline(
                "text-generation",
                model=self.model_name,
                device_map=self.device,
                torch_dtype="auto",
            )

    def generate(self, prompt: str) -> str:
        self.load()
        out = self._pipe(_chat_messages(prompt), max_new_tokens=self.max_new_tokens,
                         do_sample=False)
        return out[0]["generated_text"][-1]["content"]

    def stream(self, prompt: str) -> Iterator[str]:
        from transformers import TextIteratorStreamer

        self.load()
        streamer = TextIteratorStreamer(self._pipe.tokenizer, skip_prompt=True,
                                        skip_special_tokens=True)
        messages = _chat_messages(prompt)
        kwargs = {"max_new_tokens": self.max_new_tokens, "do_sample": False,
                  "streamer": streamer}

        def _run() -> None:
            try:
                self._pipe(messages, **kwargs)
            except Exception as exc:  # surfaced by the stream consumer
                _run.error = exc  # type: ignore[attr-defined]
            finally:
                end = getattr(streamer, "end", None)
                if callable(end):
                    end()

        _run.error = None  # type: ignore[attr-defined]
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        for token in streamer:
            yield token
        thread.join(timeout=30)
        if _run.error is not None:  # type: ignore[attr-defined]
            raise _run.error  # type: ignore[attr-defined]


class OllamaGenerator:
    """Same Qwen model, served quantized by a local Ollama daemon."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, max_new_tokens: int = 300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_new_tokens = max_new_tokens

    @property
    def loaded(self) -> bool:
        try:
            return httpx.get(f"{self.base_url}/api/tags", timeout=1.0).status_code == 200
        except Exception:
            return False

    def stream(self, prompt: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": _chat_messages(prompt),
            "stream": True,
            "options": {"temperature": 0, "num_predict": self.max_new_tokens},
        }
        with httpx.stream("POST", f"{self.base_url}/api/chat", json=payload,
                          timeout=None) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                delta = data.get("message", {}).get("content", "")
                if delta:
                    yield delta

    def generate(self, prompt: str) -> str:
        return "".join(self.stream(prompt))


class HFGenerator:
    """Hosted generation through the Hugging Face Inference API."""

    name = "hf"

    def __init__(self, token: str, model: str, max_new_tokens: int = 300):
        self.token = token
        self.model = model
        self.max_new_tokens = max_new_tokens

    @property
    def loaded(self) -> bool:
        return bool(self.token)

    def stream(self, prompt: str) -> Iterator[str]:
        from huggingface_hub import InferenceClient

        client = InferenceClient(provider="auto", api_key=self.token)
        for chunk in client.chat.completions.create(
            model=self.model,
            messages=_chat_messages(prompt),
            max_tokens=self.max_new_tokens,
            temperature=0.2,
            stream=True,
        ):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    def generate(self, prompt: str) -> str:
        return "".join(self.stream(prompt))


def build_generator(settings: Settings) -> Generator:
    backend = settings.llm_backend.lower()
    if backend in ("api", "openai", "openai-compatible"):
        # Do not raise here when the key is missing: /health, /search and the
        # frontend must stay usable so the user can paste a key at runtime.
        return ApiGenerator(
            api_key=settings.api_key,
            api_base=settings.api_base,
            model=settings.api_model,
            max_new_tokens=settings.llm_max_new_tokens,
            temperature=settings.api_temperature,
            timeout=settings.api_timeout,
        )
    if backend == "local":
        g = LocalQwenGenerator(settings.llm_model, settings.llm_max_new_tokens,
                               settings.llm_device)
        if settings.llm_load_on_startup:
            g.load()
        return g
    if backend == "ollama":
        return OllamaGenerator(settings.ollama_url, settings.ollama_model,
                               settings.llm_max_new_tokens)
    if backend == "hf":
        if not settings.hf_token:
            raise RuntimeError("RAG_LLM_BACKEND=hf requires RAG_HF_TOKEN in backend/.env")
        return HFGenerator(settings.hf_token, settings.hf_model,
                           settings.llm_max_new_tokens)
    raise RuntimeError(
        f"Unknown RAG_LLM_BACKEND={backend!r}. Use api / local / ollama / hf. "
        "This project ships no mock provider."
    )


def describe_generator(g: Generator) -> dict:
    """Non-secret generator details for /health."""
    model = getattr(g, "model", None) or getattr(g, "model_name", "")
    return {
        "llm_backend": g.name,
        "llm_model": model,
        "llm_loaded": bool(g.loaded),
        "llm_ready": g.name == "local" or bool(g.loaded),
        "api_base": getattr(g, "api_base", ""),
        "api_key_configured": bool(getattr(g, "api_key", "")),
    }
