"""Document ingestion pipeline — chunk and embed markdown docs into ChromaDB."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from security_agent.rag.store import VectorStore


def chunk_markdown(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> list[dict]:
    """Split markdown text into overlapping chunks, preserving section headers.

    Each chunk includes metadata about the originating section.
    """
    chunks = []

    # Split by headers
    sections = re.split(r"(^#{1,3}\s+.+$)", text, flags=re.MULTILINE)

    current_header = ""
    current_text = ""

    for part in sections:
        if re.match(r"^#{1,3}\s+", part):
            # This is a header — process accumulated text first
            if current_text.strip():
                for chunk in _split_text(current_text.strip(), chunk_size, chunk_overlap):
                    chunks.append({
                        "text": f"{current_header}\n\n{chunk}" if current_header else chunk,
                        "header": current_header,
                    })
            current_header = part.strip()
            current_text = ""
        else:
            current_text += part

    # Process remaining text
    if current_text.strip():
        for chunk in _split_text(current_text.strip(), chunk_size, chunk_overlap):
            chunks.append({
                "text": f"{current_header}\n\n{chunk}" if current_header else chunk,
                "header": current_header,
            })

    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            break_point = text.rfind("\n\n", start, end)
            if break_point > start:
                end = break_point + 2
            else:
                # Look for sentence break
                break_point = text.rfind(". ", start, end)
                if break_point > start:
                    end = break_point + 2

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks


def ingest_documents(
    docs_dir: str = "./data/docs",
    persist_dir: str = "./data/chroma",
    embedding_model: str = "all-MiniLM-L6-v2",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> int:
    """Ingest all markdown documents from docs_dir into ChromaDB.

    Returns:
        Number of chunks ingested.
    """
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"❌ Docs directory not found: {docs_dir}")
        return 0

    md_files = list(docs_path.glob("*.md"))
    if not md_files:
        print(f"❌ No markdown files found in {docs_dir}")
        return 0

    print(f"📚 Found {len(md_files)} documents in {docs_dir}")

    store = VectorStore(
        persist_dir=persist_dir,
        embedding_model=embedding_model,
    )

    # Reset existing collection
    store.reset()

    total_chunks = 0

    for md_file in md_files:
        print(f"  📄 Processing {md_file.name}...")
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, chunk_size, chunk_overlap)

        if not chunks:
            continue

        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(
                f"{md_file.name}:{i}:{chunk['text'][:50]}".encode()
            ).hexdigest()

            documents.append(chunk["text"])
            metadatas.append({
                "source": md_file.name,
                "section": chunk["header"],
                "chunk_index": i,
            })
            ids.append(doc_id)

        store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
        total_chunks += len(chunks)
        print(f"    → {len(chunks)} chunks indexed")

    print(f"\n✅ Ingested {total_chunks} chunks from {len(md_files)} documents")
    print(f"   ChromaDB path: {persist_dir}")

    return total_chunks


if __name__ == "__main__":
    from security_agent.config import config

    ingest_documents(
        docs_dir=config.rag.docs_dir,
        persist_dir=config.rag.chroma_persist_dir,
        embedding_model=config.rag.embedding_model,
        chunk_size=config.rag.chunk_size,
        chunk_overlap=config.rag.chunk_overlap,
    )
