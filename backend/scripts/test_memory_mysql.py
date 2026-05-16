"""Minimal MySQL memory-layer smoke test.

Run from the backend directory:

    uv run python scripts/test_memory_mysql.py

The script creates the stage-2 tables, inserts one memory_item row, queries it
back, and prints the result. If MySQL is missing, it exits with a clear message.
"""

import json
import os
import sys


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db import DatabaseUnavailableError, create_all_tables, database_health, dispose_database
from app.repositories.memory_repository import MemoryRepository


def main() -> int:
    """Run the smallest possible insert-and-read test against MySQL."""
    health = database_health()
    print("mysql health:")
    print(json.dumps(health, ensure_ascii=False, indent=2))

    if not health.get("connected"):
        print("mysql is not connected; start mysql or update .env before running this test.")
        return 1

    try:
        create_all_tables()
        repository = MemoryRepository()

        item = repository.create_item(
            {
                "source": "phase2 smoke test",
                "source_type": "manual",
                "url": "local://phase2/test-memory-mysql",
                "title": "stage 2 mysql memory test",
                "raw_text": "raw text before cleaning",
                "clean_text": "clean text after cleaning",
                "summary": "a minimal memory row inserted by the smoke test",
                "importance_score": 0.5,
                "credibility_score": 0.8,
                "memory_type": "smoke_test",
            }
        )
        fetched = repository.get_item(item["id"])

        print("inserted memory item:")
        print(json.dumps(fetched, ensure_ascii=False, indent=2))
        return 0
    except DatabaseUnavailableError as exc:
        print(f"mysql memory database is unavailable: {exc}")
        return 1
    finally:
        dispose_database()


if __name__ == "__main__":
    raise SystemExit(main())
