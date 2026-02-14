"""CLI entry point: python -m security_agent.rag.ingest"""
from security_agent.rag.ingest import ingest_documents
from security_agent.config import config

if __name__ == "__main__":
    ingest_documents(
        docs_dir=config.rag.docs_dir,
        persist_dir=config.rag.chroma_persist_dir,
        embedding_model=config.rag.embedding_model,
        chunk_size=config.rag.chunk_size,
        chunk_overlap=config.rag.chunk_overlap,
    )
