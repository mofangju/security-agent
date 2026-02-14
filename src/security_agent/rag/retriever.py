"""Hybrid retriever combining semantic search with BM25 + RRF fusion."""

from __future__ import annotations

import re
from collections import defaultdict

from rank_bm25 import BM25Okapi

from security_agent.rag.store import VectorStore


class HybridRetriever:
    """Combines ChromaDB semantic search with BM25 keyword search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
    """

    def __init__(
        self,
        store: VectorStore,
        rrf_k: int = 60,
        semantic_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ):
        self.store = store
        self.rrf_k = rrf_k
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight

        # BM25 index (built lazily)
        self._bm25_index: BM25Okapi | None = None
        self._bm25_docs: list[dict] | None = None

    def _build_bm25_index(self) -> None:
        """Build BM25 index from all documents in the collection."""
        collection = self.store.get_or_create_collection()
        result = collection.get(include=["documents", "metadatas"])

        if not result["documents"]:
            self._bm25_docs = []
            self._bm25_index = BM25Okapi([[""]])
            return

        self._bm25_docs = [
            {
                "id": result["ids"][i],
                "document": result["documents"][i],
                "metadata": result["metadatas"][i] if result["metadatas"] else {},
            }
            for i in range(len(result["ids"]))
        ]

        # Tokenize documents for BM25
        tokenized = [self._tokenize(doc["document"]) for doc in self._bm25_docs]
        self._bm25_index = BM25Okapi(tokenized)

    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        # Remove markdown formatting, lowercase, split
        clean = re.sub(r"[#*`\[\]()]", "", text.lower())
        return clean.split()

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """Retrieve documents using hybrid search with RRF fusion.

        Args:
            query: The search query.
            n_results: Number of results to return.
            where: Optional metadata filter.

        Returns:
            List of document dicts with text, metadata, and score.
        """
        # Semantic search via ChromaDB
        semantic_results = self._semantic_search(query, n_results * 2, where)

        # BM25 keyword search
        bm25_results = self._bm25_search(query, n_results * 2)

        # RRF fusion
        fused = self._rrf_fuse(semantic_results, bm25_results)

        # Return top n results
        return fused[:n_results]

    def _semantic_search(
        self, query: str, n_results: int, where: dict | None = None
    ) -> list[dict]:
        """Perform semantic search via ChromaDB embeddings."""
        result = self.store.query(query_text=query, n_results=n_results, where=where)

        docs = []
        if result["documents"] and result["documents"][0]:
            for i, doc in enumerate(result["documents"][0]):
                docs.append({
                    "id": result["ids"][0][i],
                    "document": doc,
                    "metadata": result["metadatas"][0][i] if result["metadatas"] else {},
                    "distance": result["distances"][0][i] if result["distances"] else 0,
                })
        return docs

    def _bm25_search(self, query: str, n_results: int) -> list[dict]:
        """Perform BM25 keyword search."""
        if self._bm25_index is None:
            self._build_bm25_index()

        if not self._bm25_docs:
            return []

        query_tokens = self._tokenize(query)
        scores = self._bm25_index.get_scores(query_tokens)

        # Get top-n by score
        scored_docs = [
            (i, score) for i, score in enumerate(scores) if score > 0
        ]
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scored_docs[:n_results]:
            doc = self._bm25_docs[idx].copy()
            doc["bm25_score"] = score
            results.append(doc)

        return results

    def _rrf_fuse(
        self, semantic: list[dict], bm25: list[dict]
    ) -> list[dict]:
        """Reciprocal Rank Fusion to combine two ranked lists."""
        scores: dict[str, float] = defaultdict(float)
        doc_map: dict[str, dict] = {}

        # Score semantic results
        for rank, doc in enumerate(semantic):
            doc_id = doc["id"]
            scores[doc_id] += self.semantic_weight / (self.rrf_k + rank + 1)
            doc_map[doc_id] = doc

        # Score BM25 results
        for rank, doc in enumerate(bm25):
            doc_id = doc["id"]
            scores[doc_id] += self.bm25_weight / (self.rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids:
            doc = doc_map[doc_id]
            doc["rrf_score"] = scores[doc_id]
            results.append(doc)

        return results
