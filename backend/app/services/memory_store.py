"""Chroma write path for MySQL memory items."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import chromadb

from ..config import Config
from ..repositories.memory_repository import MemoryRepository
from .embedding_service import EmbeddingService


class ChromaUnavailableError(RuntimeError):
    """Raised when Chroma cannot be initialized or written."""


class MemoryStore:
    """Save long-term memory rows from MySQL into Chroma."""

    def __init__(
        self,
        *,
        config=Config,
        embedding_service: Optional[EmbeddingService] = None,
        repository: Optional[MemoryRepository] = None,
    ):
        self.config = config
        self.embedding_service = embedding_service or EmbeddingService(config)
        self.repository = repository or MemoryRepository()
        self._client = None
        self._collection = None

    def _get_client(self):
        """Create a Chroma client using http or local persistent mode."""
        if self._client is not None:
            return self._client

        try:
            if self.config.CHROMA_USE_HTTP:
                self._client = chromadb.HttpClient(
                    host=self.config.CHROMA_HOST,
                    port=int(self.config.CHROMA_PORT),
                )
            else:
                persist_dir = self._resolve_persist_dir(self.config.CHROMA_PERSIST_DIR)
                os.makedirs(persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(path=str(persist_dir))
            return self._client
        except Exception as exc:
            raise ChromaUnavailableError(f"failed to initialize chroma client: {exc}") from exc

    def get_collection(self):
        """Return the Chroma collection used for long-term memory."""
        if self._collection is None:
            try:
                self._collection = self._get_client().get_or_create_collection(
                    name=self.config.CHROMA_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:
                raise ChromaUnavailableError(f"failed to open chroma collection: {exc}") from exc
        return self._collection

    def save_memory_to_chroma(self, memory_item: Dict[str, Any]) -> Dict[str, Any]:
        """Embed and upsert one MySQL memory item into Chroma."""
        text = (memory_item.get("summary") or memory_item.get("clean_text") or "").strip()
        if not text:
            raise ValueError("memory item has no summary or clean_text to embed")

        mysql_id = memory_item.get("id")
        if mysql_id is None:
            raise ValueError("memory item id is required")

        embedding = self.embedding_service.embed_text(text)
        metadata = {
            "mysql_id": int(mysql_id),
            "source": memory_item.get("source") or "",
            "url": memory_item.get("url") or "",
            "publish_time": memory_item.get("publish_time") or "",
            "importance_score": float(memory_item.get("importance_score") or 0.0),
            "memory_type": memory_item.get("memory_type") or "general",
        }

        document_id = self._document_id(mysql_id)
        try:
            self.get_collection().upsert(
                ids=[document_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
            )
        except Exception as exc:
            raise ChromaUnavailableError(f"failed to write memory to chroma: {exc}") from exc

        self.repository.mark_embedded(int(mysql_id), True)
        return {
            "id": document_id,
            "mysql_id": int(mysql_id),
            "metadata": metadata,
            "document": text,
            "embedding_mode": "openai-compatible",
        }

    def save_memory_id_to_chroma(self, memory_id: int) -> Dict[str, Any]:
        """Load one memory item from MySQL and save it into Chroma."""
        memory_item = self.repository.get_item(int(memory_id))
        if memory_item is None:
            raise ValueError(f"memory item {memory_id} not found")
        return self.save_memory_to_chroma(memory_item)

    def query(self, question: str, n_results: int) -> Dict[str, Any]:
        """Query Chroma with an embedded question."""
        embedding = self.embedding_service.embed_text(question)
        try:
            return self.get_collection().query(
                query_embeddings=[embedding],
                n_results=max(1, int(n_results)),
                include=["metadatas", "documents", "distances"],
            )
        except Exception as exc:
            raise ChromaUnavailableError(f"failed to query chroma: {exc}") from exc

    @staticmethod
    def _document_id(mysql_id: Any) -> str:
        """Build a stable Chroma document id from the MySQL id."""
        return f"memory_item:{mysql_id}"

    @staticmethod
    def _resolve_persist_dir(value: str) -> Path:
        """Resolve Chroma paths consistently from backend or repository root."""
        path = Path(value)
        if path.is_absolute():
            return path

        backend_dir = Path(__file__).resolve().parents[2]
        project_root = backend_dir.parent
        if path.parts and path.parts[0] == "backend":
            return project_root / path
        return backend_dir / path


def save_memory_to_chroma(memory_item: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function required by the phase 3 interface."""
    return MemoryStore().save_memory_to_chroma(memory_item)
