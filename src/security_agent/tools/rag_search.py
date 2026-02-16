"""RAG search tool — queries the ChromaDB knowledge base."""

from __future__ import annotations

import json

from security_agent.config import config
from security_agent.rag.guardrails import sanitize_retrieved_text
from security_agent.rag.retriever import HybridRetriever
from security_agent.rag.store import VectorStore


def tool_rag_search(query: str, n_results: int = 5) -> str:
    """Search the security knowledge base using hybrid retrieval.

    Searches SafeLine documentation, OWASP guides, and incident response
    playbooks using semantic + keyword search with RRF fusion.

    Args:
        query: The search query (natural language)
        n_results: Number of results to return (default: 5)

    Returns:
        JSON string with relevant document chunks and metadata
    """
    store = VectorStore(
        persist_dir=config.rag.chroma_persist_dir,
        embedding_model=config.rag.embedding_model,
    )

    retriever = HybridRetriever(store=store)

    try:
        results = retriever.retrieve(query=query, n_results=n_results)

        # Format results for LLM consumption
        formatted = []
        for r in results:
            safe_text = sanitize_retrieved_text(r.get("document", ""), max_chars=1500)
            formatted.append({
                "text": safe_text,
                "source": r.get("metadata", {}).get("source", "unknown"),
                "section": r.get("metadata", {}).get("section", ""),
                "score": round(r.get("rrf_score", 0), 4),
            })

        return json.dumps(formatted, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "query": query})
