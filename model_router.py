import os
import time
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger("synapse.model_router")

PROVIDERS = ["groq", "gemini", "cerebras", "ollama"]


class ModelRouter:
    """Fallback chain: Groq (primary) -> Gemini -> Cerebras -> Ollama."""

    def __init__(self, preferred: Optional[str] = None):
        self.preferred = preferred or os.getenv("MODEL_BACKEND", "auto")
        self._current_provider: Optional[str] = None
        self._clients: dict = {}
        self._build_clients()

    def _build_clients(self):
        if os.getenv("GROQ_API_KEY"):
            try:
                from langchain_groq import ChatGroq
                self._clients["groq"] = ChatGroq(
                    model="llama-3.3-70b-versatile",
                    temperature=0,
                    api_key=os.getenv("GROQ_API_KEY"),
                    max_retries=0,
                )
                logger.info("ModelRouter: Groq ready")
            except ImportError:
                logger.warning("ModelRouter: langchain-groq not installed")

        if os.getenv("GEMINI_API_KEY"):
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._clients["gemini"] = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    temperature=0,
                    google_api_key=os.getenv("GEMINI_API_KEY"),
                    max_retries=0,
                )
                logger.info("ModelRouter: Gemini ready")
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
                self._clients["ollama"] = ChatOllama(
                    model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                    temperature=0,
                )
                logger.info("ModelRouter: Ollama ready")
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

    def get_llm(self) -> BaseChatModel:
        if self.preferred != "auto" and self.preferred in self._clients:
            self._current_provider = self.preferred
            return self._clients[self.preferred]
        for provider in PROVIDERS:
            if provider in self._clients:
                self._current_provider = provider
                logger.info(f"ModelRouter: primary = {provider}")
                return self._clients[provider]
        raise RuntimeError("ModelRouter: No LLM clients available")

    def invoke_with_fallback(self, messages: list, on_switch=None) -> tuple:
        """Try each provider in order; skip on 429/rate-limit. Returns (response, provider)."""
        order = [self.preferred] if self.preferred != "auto" else PROVIDERS
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
