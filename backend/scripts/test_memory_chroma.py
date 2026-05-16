"""Minimal MySQL + Chroma memory recall smoke test.

Run from the backend directory:

    uv run python scripts/test_memory_chroma.py

The script uses the configured real embedding model and local Chroma persistent
storage. It requires both MySQL and a working OpenAI-compatible embedding API,
because phase 3 recalls complete memory rows from MySQL after Chroma retrieval.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import Config
from app.db import DatabaseUnavailableError, create_all_tables, database_health, dispose_database
from app.repositories.memory_repository import MemoryRepository
from app.services.embedding_service import EmbeddingService
from app.services.memory_retriever import MemoryRetriever
from app.services.memory_store import MemoryStore


def _configure_local_smoke_test() -> None:
    """Force local Chroma storage for a repeatable smoke test."""
    Config.CHROMA_USE_HTTP = False
    Config.CHROMA_PERSIST_DIR = os.path.join(BACKEND_DIR, "uploads", "chroma_smoke_test")
    Config.CHROMA_COLLECTION_NAME = "mirofish_memory_smoke_test"


def _insert_test_items(repository: MemoryRepository, run_id: str):
    """Insert several test memories with different importance and timestamps."""
    now = datetime.now(timezone.utc)
    payloads = [
        {
            "source": "phase3 smoke test",
            "source_type": "manual",
            "url": f"local://phase3/{run_id}/energy",
            "title": "energy supply shock",
            "raw_text": "energy prices rise after a supply shock",
            "clean_text": "energy prices rise after a supply shock and policy response",
            "summary": "energy supply shock may push prices higher and trigger policy response",
            "publish_time": (now - timedelta(days=1)).isoformat(),
            "importance_score": 0.9,
            "credibility_score": 0.8,
            "memory_type": f"phase3_smoke_{run_id}",
        },
        {
            "source": "phase3 smoke test",
            "source_type": "manual",
            "url": f"local://phase3/{run_id}/sports",
            "title": "sports event result",
            "raw_text": "a sports team won a friendly match",
            "clean_text": "sports result has little relation to energy policy",
            "summary": "sports result is unrelated to energy supply and policy",
            "publish_time": (now - timedelta(days=10)).isoformat(),
            "importance_score": 0.2,
            "credibility_score": 0.7,
            "memory_type": f"phase3_smoke_{run_id}",
        },
        {
            "source": "phase3 smoke test",
            "source_type": "manual",
            "url": f"local://phase3/{run_id}/policy",
            "title": "government energy policy",
            "raw_text": "government considers subsidies and reserve release",
            "clean_text": "government may use subsidies and strategic reserve release for energy stability",
            "summary": "policy makers may use subsidies and reserves to stabilize energy markets",
            "publish_time": (now - timedelta(days=3)).isoformat(),
            "importance_score": 0.8,
            "credibility_score": 0.85,
            "memory_type": f"phase3_smoke_{run_id}",
        },
    ]
    return [repository.create_item(payload) for payload in payloads]


def main() -> int:
    """Insert memories, embed them into Chroma, recall, and print ranking."""
    _configure_local_smoke_test()
    health = database_health()
    print("mysql health:")
    print(json.dumps(health, ensure_ascii=False, indent=2))

    if not health.get("connected"):
        print("mysql is not connected; start mysql or update .env before running this test.")
        return 1

    try:
        create_all_tables()
        run_id = uuid.uuid4().hex[:8]
        repository = MemoryRepository()
        store = MemoryStore(
            embedding_service=EmbeddingService(Config),
            repository=repository,
        )
        retriever = MemoryRetriever(store=store, repository=repository)

        items = _insert_test_items(repository, run_id)
        for item in items:
            result = store.save_memory_to_chroma(item)
            print(f"embedded mysql_id={result['mysql_id']} with mode={result['embedding_mode']}")

        recalled = retriever.recall_memory("what may happen to energy prices and policy?", top_k=3)
        print("recall ranking:")
        print(json.dumps(recalled, ensure_ascii=False, indent=2))
        return 0
    except DatabaseUnavailableError as exc:
        print(f"mysql memory database is unavailable: {exc}")
        return 1
    finally:
        dispose_database()


if __name__ == "__main__":
    raise SystemExit(main())
