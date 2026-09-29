"""Vector store for RAG: document chunks embedded and indexed in ChromaDB.

Document metadata (including the owning user) lives in SQLite (see Store); the chunk text
and vectors live in Chroma.
Embeddings are computed here and passed to Chroma explicitly, so the embedder is swappable.
"""

from pathlib import Path
from typing import Any, Callable

import chromadb

from app.rag.chunking import chunk_text, extract_text
from app.store import Store

Embedder = Callable[[list[str]], list[list[float]]]
COLLECTION = "knowledge"
EMBED_BATCH = 64


def default_embedder() -> Embedder:
    """Chroma's bundled all-MiniLM-L6-v2 (ONNX, runs locally). Downloads ~80 MB on first use."""
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    fn = DefaultEmbeddingFunction()
    return lambda texts: [list(map(float, v)) for v in fn(texts)]


class KnowledgeBase:
    def __init__(self, path: Path | str, store: Store, embedder: Embedder | None = None):
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            COLLECTION,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )
        self._store = store
        self._embed_fn: Embedder | None = embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embed_fn is None:
            self._embed_fn = default_embedder()  # lazy: model loads on first use, not at startup
        vectors: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            vectors.extend(self._embed_fn(texts[i : i + EMBED_BATCH]))
        return vectors

    def add_document(self, user_id: str, filename: str, data: bytes) -> dict[str, Any]:
        text = extract_text(filename, data)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError(f"No text could be extracted from '{filename}'")

        doc = self._store.add_document(user_id, filename, size=len(data), chunks=len(chunks))
        try:
            self._collection.add(
                ids=[f"{doc['id']}:{i}" for i in range(len(chunks))],
                documents=chunks,
                embeddings=self._embed(chunks),
                metadatas=[{"doc_id": doc["id"], "source": filename, "chunk": i} for i in range(len(chunks))],
            )
        except Exception:
            self._store.delete_document(user_id, doc["id"])
            raise
        return doc

    def delete_document(self, user_id: str, doc_id: str) -> bool:
        if not self._store.delete_document(user_id, doc_id):
            return False
        self._collection.delete(where={"doc_id": doc_id})
        return True

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        return self._store.list_documents(user_id)

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        # Ownership lives in SQLite, so restrict the vector search to this user's documents.
        docs = self._store.list_documents(user_id)
        n = sum(d["chunks"] for d in docs)
        if not n:
            return []
        res = self._collection.query(
            query_embeddings=self._embed([query]),
            n_results=min(top_k, n),
            where={"doc_id": {"$in": [d["id"] for d in docs]}},
            include=["documents", "metadatas", "distances"],
        )
        return [
            {
                "source": meta["source"],
                "chunk": meta["chunk"],
                "score": round(1 - dist, 3),  # cosine similarity
                "text": text,
            }
            for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]
