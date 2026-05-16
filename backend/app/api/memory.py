"""Memory API for the enhanced MySQL long-term memory layer."""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from flask import jsonify, request

from ..db import DatabaseUnavailableError, create_all_tables, database_health
from ..repositories.memory_repository import MemoryRepository
from ..services.memory_retriever import MemoryRetriever
from ..services.memory_store import ChromaUnavailableError, MemoryStore
from . import memory_bp


memory_repository = MemoryRepository()


def _database_error_response(exc, status_code: int = 503):
    """Return a clear JSON response when MySQL is missing or unreachable."""
    return (
        jsonify(
            {
                "success": False,
                "error": "mysql memory database is unavailable",
                "detail": str(exc),
            }
        ),
        status_code,
    )


def _chroma_error_response(exc, status_code: int = 503):
    """Return a clear JSON response when Chroma or embedding is unavailable."""
    return (
        jsonify(
            {
                "success": False,
                "error": "chroma memory store is unavailable",
                "detail": str(exc),
            }
        ),
        status_code,
    )


@memory_bp.route("/health", methods=["GET"])
def memory_health():
    """Check whether the MySQL memory database is reachable."""
    health = database_health()
    status_code = 200 if health.get("connected") else 503
    return (
        jsonify(
            {
                "success": health.get("connected", False),
                "service": "memory_mysql",
                "status": "ok" if health.get("connected") else "unavailable",
                **health,
            }
        ),
        status_code,
    )


@memory_bp.route("/items", methods=["POST"])
def create_memory_item():
    """Insert one test memory item into MySQL."""
    payload = request.get_json(silent=True) or {}
    if not any(payload.get(key) for key in ("raw_text", "clean_text", "summary", "title", "url")):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "at least one of raw_text, clean_text, summary, title, or url is required",
                }
            ),
            400,
        )

    try:
        create_all_tables()
        item = memory_repository.create_item(payload)
        return jsonify({"success": True, "item": item}), 201
    except IntegrityError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "memory item already exists or violates a database constraint",
                    "detail": str(exc.orig) if getattr(exc, "orig", None) else str(exc),
                }
            ),
            409,
        )
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@memory_bp.route("/embed/<int:memory_id>", methods=["POST"])
def embed_memory_item(memory_id: int):
    """Embed one MySQL memory item and write it into Chroma."""
    try:
        create_all_tables()
        result = MemoryStore(repository=memory_repository).save_memory_id_to_chroma(memory_id)
        return jsonify({"success": True, "result": result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
    except ChromaUnavailableError as exc:
        return _chroma_error_response(exc)
    except Exception as exc:
        return _chroma_error_response(exc, status_code=502)


@memory_bp.route("/recall", methods=["POST"])
def recall_memory_items():
    """Recall historical memory items for a user question."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    top_k = payload.get("top_k", 5)

    if not question:
        return jsonify({"success": False, "error": "question is required"}), 400

    try:
        memories = MemoryRetriever(repository=memory_repository).recall_memory(
            question,
            top_k=top_k,
        )
        return jsonify({"success": True, "question": question, "items": memories, "count": len(memories)})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
    except ChromaUnavailableError as exc:
        return _chroma_error_response(exc)
    except Exception as exc:
        return _chroma_error_response(exc, status_code=502)


@memory_bp.route("/items", methods=["GET"])
def list_memory_items():
    """List memory items from MySQL."""
    try:
        create_all_tables()
        items = memory_repository.list_items(
            limit=request.args.get("limit", 50),
            offset=request.args.get("offset", 0),
            memory_type=request.args.get("memory_type"),
            source_type=request.args.get("source_type"),
        )
        return jsonify({"success": True, "items": items, "count": len(items)})
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)


@memory_bp.route("/items/<int:item_id>", methods=["GET"])
def get_memory_item(item_id: int):
    """Get one memory item by id from MySQL."""
    try:
        create_all_tables()
        item = memory_repository.get_item(item_id)
        if item is None:
            return jsonify({"success": False, "error": "memory item not found"}), 404
        return jsonify({"success": True, "item": item})
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
