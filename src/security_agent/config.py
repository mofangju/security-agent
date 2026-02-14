"""Centralized configuration for the Security Agent PoC.

All settings are loaded from environment variables (or .env file).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Google Gemini
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    google_model: str = field(
        default_factory=lambda: os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")
    )

    # vLLM (OpenAI-compatible)
    vllm_base_url: str = field(
        default_factory=lambda: os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    )
    vllm_model: str = field(
        default_factory=lambda: os.getenv("VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    )


@dataclass
class SafeLineConfig:
    """SafeLine WAF configuration."""

    url: str = field(default_factory=lambda: os.getenv("SAFELINE_URL", "https://localhost:9443"))
    api_token: str = field(default_factory=lambda: os.getenv("SAFELINE_API_TOKEN", ""))

    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers for SafeLine API requests."""
        return {
            "X-SLCE-API-TOKEN": self.api_token,
            "Content-Type": "application/json",
        }


@dataclass
class PetShopConfig:
    """Pet Shop web app configuration."""

    host: str = field(default_factory=lambda: os.getenv("PETSHOP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PETSHOP_PORT", "8080")))
    db_path: str = field(default_factory=lambda: os.getenv("PETSHOP_DB", "petshop.db"))


@dataclass
class RAGConfig:
    """RAG pipeline configuration."""

    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )
    chunk_size: int = 512
    chunk_overlap: int = 50
    docs_dir: str = field(
        default_factory=lambda: str(_PROJECT_ROOT / "data" / "docs")
    )


@dataclass
class AppConfig:
    """Top-level application configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    safeline: SafeLineConfig = field(default_factory=SafeLineConfig)
    petshop: PetShopConfig = field(default_factory=PetShopConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Singleton config instance
config = AppConfig()
