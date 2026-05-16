"""Smoke test for the real active-search provider.

This script only exercises the search provider. It does not write MySQL,
Chroma, or Zep, so it is a quick way to check whether ingestion can reach an
external information source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    """Run active search and print normalized documents."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", default="energy market")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    from app.config import Config
    from app.services.active_search_service import active_search

    Config.ACTIVE_SEARCH_MAX_RESULTS = args.limit
    docs = active_search(args.keyword)
    print(json.dumps(docs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
