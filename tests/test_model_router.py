import os
import pytest
from unittest.mock import MagicMock, patch

def test_model_router_raises_if_no_providers():
    """Router must raise RuntimeError when no API keys are set."""
    with patch.dict(os.environ, {}, clear=True):
        for key in ["GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OLLAMA_BASE_URL"]:
            os.environ.pop(key, None)
        with pytest.raises(RuntimeError, match="No LLM providers configured"):
            from model_router import ModelRouter
            ModelRouter()

def test_model_router_selects_preferred_provider():
    """Router returns the preferred provider when explicitly set."""
    mock_groq = MagicMock()
    mock_gemini = MagicMock()
    with patch.dict(os.environ, {"GROQ_API_KEY": "test", "GEMINI_API_KEY": "test", "MODEL_BACKEND": "gemini"}):
        with patch("model_router.ModelRouter._build_clients") as mock_build:
            from model_router import ModelRouter
            router = ModelRouter.__new__(ModelRouter)
            router.preferred = "gemini"
            router._clients = {"groq": mock_groq, "gemini": mock_gemini}
            router._current_provider = None
            result = router.get_llm()
            assert result is mock_gemini

def test_model_router_skips_rate_limited_provider():
    """invoke_with_fallback skips a provider that raises a 429 error."""
    from model_router import ModelRouter
    router = ModelRouter.__new__(ModelRouter)
    router.preferred = "auto"
    router._current_provider = None

    mock_groq = MagicMock()
    mock_groq.invoke.side_effect = Exception("429 rate limit exceeded")
    mock_gemini = MagicMock()
    mock_gemini.invoke.return_value = "ok"

    router._clients = {"groq": mock_groq, "gemini": mock_gemini}

    with patch("model_router.PROVIDERS", ["groq", "gemini"]):
        response, provider = router.invoke_with_fallback([{"role": "user", "content": "hi"}])
        assert provider == "gemini"
        assert response == "ok"
