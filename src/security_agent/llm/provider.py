"""LLM provider factory — supports OpenAI, Google Gemini, and vLLM."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from security_agent.config import config


def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Create an LLM instance based on the configured provider.

    Returns a LangChain-compatible chat model.
    """
    provider = config.llm.provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm.openai_model,
            api_key=config.llm.openai_api_key,
            temperature=temperature,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.llm.google_model,
            google_api_key=config.llm.google_api_key,
            temperature=temperature,
        )

    elif provider == "vllm":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.llm.vllm_model,
            openai_api_base=config.llm.vllm_base_url,
            openai_api_key="not-needed",
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported: openai, google, vllm"
        )
