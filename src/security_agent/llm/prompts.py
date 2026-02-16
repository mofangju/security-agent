"""Prompt templates for Security agent nodes.

Security agent is the AI-powered security assistant for SafeLine WAF, built with
LangGraph. Prompts are loaded from text files in the prompts/ directory
so they can be edited without touching Python code.
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load(name: str) -> str:
    """Load a prompt from a text file in the prompts/ directory."""
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()


SUPERVISOR_SYSTEM = _load("supervisor")
MONITOR_SYSTEM = _load("monitor")
LOG_ANALYST_SYSTEM = _load("log_analyst")
CONFIG_MANAGER_SYSTEM = _load("config_manager")
THREAT_INTEL_SYSTEM = _load("threat_intel")
TUNER_SYSTEM = _load("tuner")
REPORTER_SYSTEM = _load("reporter")
RAG_SYSTEM = _load("rag")
SELF_RAG_CRITIC_SYSTEM = _load("selfrag_critic")
