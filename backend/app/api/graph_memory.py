"""API for enhanced Zep GraphRAG memory."""

from sqlalchemy.exc import SQLAlchemyError

from flask import jsonify, request

from ..db import DatabaseUnavailableError, create_all_tables
from ..repositories.memory_repository import MemoryRepository
from ..services.graph_retriever import GraphRetriever
from ..services.zep_memory_writer import ZepGraphMemoryUnavailable, ZepMemoryWriter
from ..utils.logger import get_logger
from . import graph_memory_bp


logger = get_logger("mirofish.api.graph_memory")
memory_repository = MemoryRepository()


def _database_error_response(exc, status_code: int = 503):
    """Return a clear JSON response when MySQL is unavailable."""
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


def _zep_error_response(exc, status_code: int = 503):
    """Return a clear JSON response when Zep is unavailable."""
    return (
        jsonify(
            {
                "success": False,
                "error": "zep graph memory is unavailable",
                "detail": str(exc),
            }
        ),
        status_code,
    )


@graph_memory_bp.route("/write/<int:memory_id>", methods=["POST"])
def write_memory_to_zep(memory_id: int):
    """Write one MySQL memory item into the enhanced Zep graph."""
    payload = request.get_json(silent=True) or {}
    graph_id = payload.get("graph_id")

    try:
        create_all_tables()
        memory_item = memory_repository.get_item(memory_id)
        if memory_item is None:
            return jsonify({"success": False, "error": "memory item not found"}), 404

        enhanced_payload = _memory_item_to_graph_payload(memory_item)
        result = ZepMemoryWriter(graph_id=graph_id).write_graph_memory(enhanced_payload)
        return jsonify({"success": True, "result": result})
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
    except ZepGraphMemoryUnavailable as exc:
        return _zep_error_response(exc)
    except Exception as exc:
        return _zep_error_response(exc, status_code=502)


@graph_memory_bp.route("/retrieve", methods=["POST"])
def retrieve_graph_memory():
    """Retrieve enhanced entity-relation context from Zep."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    limit = int(payload.get("limit") or 10)
    graph_id = payload.get("graph_id")

    if not question:
        return jsonify({"success": False, "error": "question is required"}), 400

    try:
        rows = GraphRetriever(graph_id=graph_id).graph_retrieve(question, limit=limit)
        return jsonify({"success": True, "question": question, "items": rows, "count": len(rows)})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except ZepGraphMemoryUnavailable as exc:
        return _zep_error_response(exc)
    except Exception as exc:
        return _zep_error_response(exc, status_code=502)


@graph_memory_bp.route("/import-to-graph/<graph_id>", methods=["POST"])
def batch_import_to_graph(graph_id: str):
    """将记忆库中的记忆条目批量导入到指定Zep图谱中。

    用于增强流程Step2：将主动采集到MySQL/Chroma的记忆导入到项目的Zep知识图谱，
    作为仿真的知识基础。

    请求体 (JSON):
        keyword: 按关键词筛选记忆条目（可选，默认全部未写入Zep的条目）
        limit: 最大导入数量（可选，默认50）
        min_importance: 最低重要性阈值（可选，默认0.3）
    """
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword") or "").strip()
    limit = int(payload.get("limit") or 50)
    min_importance = float(payload.get("min_importance") or 0.3)

    try:
        create_all_tables()
        # 获取未写入Zep的记忆条目
        items = memory_repository.list_items(
            keyword=keyword if keyword else None,
            limit=limit,
            min_importance=min_importance,
            only_not_in_zep=True,
        )

        if not items:
            return jsonify({
                "success": True,
                "message": "没有找到符合条件的记忆条目",
                "imported_count": 0,
                "items": [],
            })

        writer = ZepMemoryWriter(graph_id=graph_id)
        results = []
        for item in items:
            try:
                enhanced_payload = _memory_item_to_graph_payload(item)
                result = writer.write_graph_memory(enhanced_payload)
                memory_repository.mark_written_to_zep(item["id"], True)
                results.append({
                    "memory_id": item["id"],
                    "title": item.get("title"),
                    "status": "imported",
                    "episode_uuid": result.get("episode_uuid"),
                })
            except Exception as exc:
                logger.warning(f"导入记忆条目 {item['id']} 到图谱失败: {exc}")
                results.append({
                    "memory_id": item["id"],
                    "title": item.get("title"),
                    "status": "failed",
                    "error": str(exc),
                })

        imported = [r for r in results if r["status"] == "imported"]
        return jsonify({
            "success": True,
            "graph_id": graph_id,
            "imported_count": len(imported),
            "failed_count": len(results) - len(imported),
            "items": results,
        })
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)
    except ZepGraphMemoryUnavailable as exc:
        return _zep_error_response(exc)
    except Exception as exc:
        return _zep_error_response(exc, status_code=502)


def _memory_item_to_graph_payload(memory_item: dict) -> dict:
    """Convert a stored memory item into the writer's expected payload."""
    evidence_rows = memory_item.get("evidence") or []
    evidence = []
    opinions = []
    for row in evidence_rows:
        if row.get("evidence_text"):
            evidence.append(row.get("evidence_text"))
        if row.get("claim"):
            opinions.append(row.get("claim"))

    return {
        "id": memory_item.get("id"),
        "mysql_id": memory_item.get("id"),
        "source": memory_item.get("source"),
        "source_url": memory_item.get("url"),
        "url": memory_item.get("url"),
        "summary": memory_item.get("summary") or memory_item.get("clean_text"),
        "clean_text": memory_item.get("clean_text"),
        "publish_time": memory_item.get("publish_time"),
        "entities": [],
        "events": [memory_item.get("title")] if memory_item.get("title") else [],
        "opinions": opinions or [memory_item.get("summary") or memory_item.get("clean_text")],
        "evidence": evidence or evidence_rows,
        "uncertainty": "",
    }
