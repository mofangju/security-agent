"""ChromaDB vector store wrapper for the RAG pipeline."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings


class VectorStore:
    """ChromaDB-based vector store for document retrieval."""

    def __init__(
        self,
        persist_dir: str = "./data/chroma",
        collection_name: str = "security_docs",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self._embedding_fn = None

        # Initialize ChromaDB
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

    @property
    def embedding_function(self):
        """Lazy-load sentence-transformers embedding function."""
        if self._embedding_fn is None:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            self._embedding_fn = SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model_name,
            )
        return self._embedding_fn

    def get_or_create_collection(self) -> chromadb.Collection:
        """Get or create the document collection."""
        return self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Add documents to the vector store."""
        collection = self.get_or_create_collection()
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Query the vector store for similar documents."""
        collection = self.get_or_create_collection()
        kwargs = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return collection.query(**kwargs)

    def count(self) -> int:
        """Get the number of documents in the collection."""
        collection = self.get_or_create_collection()
        return collection.count()

    def reset(self) -> None:
        """Delete the collection and recreate it."""
        try:
            self.client.delete_collection(self.collection_name)
        except (ValueError, Exception):
            # Collection may not exist on first run
            pass
