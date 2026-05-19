import os
import time
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("synapse.model_router")

PROVIDERS = [
    "groq", "groq_2",
    "gemini", "gemini_2", "gemini_3",
    "cerebras",
    "ollama_1", "ollama_2",
]


def _get_provider_keys(prefix: str) -> list[tuple[str, str]]:
    """Return [(slot_name, key), ...] for a provider's numbered env keys.

    Slot 1 is read from PREFIX_API_KEY_1 OR the bare PREFIX_API_KEY (legacy);
    slot 1's name is the lowercase prefix. Slots 2..9 are named
    `<prefix>_2`, `<prefix>_3`, ... and read from PREFIX_API_KEY_2, _3, etc.
    Missing slots are skipped.
    """
    keys: list[tuple[str, str]] = []
    slot_1 = os.getenv(f"{prefix}_API_KEY_1") or os.getenv(f"{prefix}_API_KEY")
    if slot_1:
        keys.append((prefix.lower(), slot_1))
    for i in range(2, 10):
        k = os.getenv(f"{prefix}_API_KEY_{i}")
        if k:
            keys.append((f"{prefix.lower()}_{i}", k))
    return keys


_RATE_LIMIT_MARKERS = (
    "429", "rate limit", "ratelimit", "rate_limit",
    "quota", "too many requests", "tokens per minute", "tpm",
    # Transient provider unavailability — treat like a rate-limit for fallover.
    # Gemini's free tier 503s under load with "model is overloaded"; Groq and
    # Cerebras occasionally 5xx during regional incidents.
    "503", "service unavailable", "overloaded", "model is overloaded",
    "server is overloaded", "temporarily unavailable",
)


def is_rate_limit_error(exc: BaseException) -> bool:
    """True if an exception looks like a transient provider error (rate-limit,
    quota, or service-unavailable / overloaded).

    Used by the streaming agent path to fail over to the next provider when the
    primary 429s or 503s. Matches on string content because providers' SDK
    exceptions don't share a common base class.
    """
    msg = str(exc).lower()
    return any(marker in msg for marker in _RATE_LIMIT_MARKERS)


class ModelRouter:
    """Provider fallback chain with optional preferred backend."""

    def __init__(self, preferred: Optional[str] = None):
        self.preferred = preferred or os.getenv("MODEL_BACKEND", "auto")
        self._current_provider: Optional[str] = None
        self._clients: dict = {}
        self._build_clients()

    def _build_clients(self):
        groq_keys = _get_provider_keys("GROQ")
        if groq_keys:
            try:
                from langchain_groq import ChatGroq
                for slot, key in groq_keys:
                    self._clients[slot] = ChatGroq(
                        model="llama-3.3-70b-versatile",
                        temperature=0,
                        api_key=key,
                        max_retries=0,
                    )
                    logger.info("ModelRouter: %s ready", slot)
            except ImportError:
                logger.warning("ModelRouter: langchain-groq not installed")

        gemini_keys = _get_provider_keys("GEMINI")
        if gemini_keys:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                for slot, key in gemini_keys:
                    self._clients[slot] = ChatGoogleGenerativeAI(
                        model=gemini_model,
                        temperature=0,
                        google_api_key=key,
                        max_retries=0,
                    )
                    logger.info("ModelRouter: %s ready (%s)", slot, gemini_model)
            except ImportError:
                logger.warning("ModelRouter: langchain-google-genai not installed")

        if os.getenv("CEREBRAS_API_KEY"):
            try:
                from langchain_cerebras import ChatCerebras
                self._clients["cerebras"] = ChatCerebras(
                    model="llama3.1-70b",
                    temperature=0,
                    api_key=os.getenv("CEREBRAS_API_KEY"),
                    max_retries=0,
                )
                logger.info("ModelRouter: Cerebras ready")
            except ImportError:
                logger.warning("ModelRouter: langchain-cerebras not installed")

        if os.getenv("OLLAMA_BASE_URL") or self._is_ollama_running():
            try:
                from langchain_ollama import ChatOllama
                base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                # Two slots so we can chain (e.g.) a strong coder model and a
                # smaller fast model as last-resort fallbacks. Legacy OLLAMA_MODEL
                # is honored as ollama_1 when the numbered vars are absent.
                model_1 = os.getenv("OLLAMA_MODEL_1") or os.getenv("OLLAMA_MODEL")
                model_2 = os.getenv("OLLAMA_MODEL_2")
                if model_1:
                    self._clients["ollama_1"] = ChatOllama(
                        model=model_1, base_url=base_url, temperature=0,
                    )
                    logger.info("ModelRouter: Ollama slot 1 ready (%s)", model_1)
                if model_2:
                    self._clients["ollama_2"] = ChatOllama(
                        model=model_2, base_url=base_url, temperature=0,
                    )
                    logger.info("ModelRouter: Ollama slot 2 ready (%s)", model_2)
                if not (model_1 or model_2):
                    logger.warning(
                        "ModelRouter: Ollama running but no OLLAMA_MODEL_1 / OLLAMA_MODEL_2 / OLLAMA_MODEL set"
                    )
            except ImportError:
                logger.warning("ModelRouter: langchain-ollama not installed")

        if not self._clients:
            raise RuntimeError(
                "ModelRouter: No LLM providers configured. "
                "Set at least one of: GROQ_API_KEY, GEMINI_API_KEY, CEREBRAS_API_KEY, or run Ollama."
            )

    def _is_ollama_running(self) -> bool:
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
            return r.status_code == 200
        except Exception:
            return False

    def _provider_order(self) -> list[str]:
        if self.preferred == "auto":
            return list(PROVIDERS)
        if self.preferred == "ollama":
            head = ["ollama_1", "ollama_2"]
        elif self.preferred in ("groq", "gemini"):
            # Bring ALL slots of this provider to the front (slot 1, then _2, _3, ...).
            head = [
                p for p in PROVIDERS
                if p == self.preferred or p.startswith(f"{self.preferred}_")
            ]
        else:
            head = [self.preferred]
        return head + [p for p in PROVIDERS if p not in head]

    def mark_current(self, provider: str):
        if provider in self._clients:
            self._current_provider = provider

    def get_clients_ordered(self) -> list[tuple[str, BaseChatModel]]:
        """Return [(provider_name, client), ...] in fallback order.

        Streaming + tool-binding paths (executor, single-ReAct) iterate this list
        directly because RunnableWithFallbacks does not reliably propagate
        `bind_tools` through to fallback clients in langgraph.
        """
        order = self._provider_order()
        return [(p, self._clients[p]) for p in order if p in self._clients]

    def get_llm(self) -> BaseChatModel:
        """Return the primary client wrapped with fallbacks across remaining providers.

        Fallbacks fire on ANY exception from the primary (langchain default), so
        rate-limit / 429 errors transparently switch to the next provider for the
        in-flight call — including streaming paths used by create_react_agent.
        """
        order = self._provider_order()
        chain = [self._clients[p] for p in order if p in self._clients]
        if not chain:
            raise RuntimeError("ModelRouter: No LLM clients available")
        primary, *rest = chain
        self._current_provider = next(p for p in order if p in self._clients)
        logger.info(
            f"ModelRouter: primary = {self._current_provider}, "
            f"fallbacks = {[p for p in order if p in self._clients][1:]}"
        )
        return primary.with_fallbacks(rest) if rest else primary

    def invoke_with_fallback(self, messages: list, on_switch=None) -> tuple:
        """Try each provider in order; skip on 429/rate-limit. Returns (response, provider)."""
        order = self._provider_order()
        available = [p for p in order if p in self._clients]
        last_error = None
        for provider in available:
            try:
                if on_switch:
                    on_switch(provider)
                response = self._clients[provider].invoke(messages)
                self._current_provider = provider
                return response, provider
            except Exception as e:
                if any(w in str(e).lower() for w in ["429", "rate limit", "quota", "ratelimit", "too many requests", "exceeded"]):
                    logger.warning(f"ModelRouter: {provider} rate limited, trying next")
                    last_error = e
                    time.sleep(0.5)
                    continue
                raise
        raise RuntimeError(f"ModelRouter: all providers exhausted. Last: {last_error}")

    @property
    def current_provider(self) -> Optional[str]:
        return self._current_provider
