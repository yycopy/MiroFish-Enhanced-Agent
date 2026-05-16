"""API endpoints for the active ingestion pipeline."""

from sqlalchemy.exc import SQLAlchemyError

from flask import jsonify, request

from ..config import Config
from ..db import DatabaseUnavailableError, create_all_tables
from ..models.ingestion import INGESTION_STATUS_FAILED
from ..models.project import ProjectManager
from ..repositories.ingestion_repository import IngestionRepository
from ..services.keyword_extractor import extract_keywords
from ..services.project_ingestion_manager import ProjectIngestionManager
from ..services.text_processor import TextProcessor
from ..tasks.ingestion_tasks import run_ingestion_task
from ..utils.logger import get_logger
from . import ingestion_bp


logger = get_logger("mirofish.api.ingestion")
ingestion_repository = IngestionRepository()


def _database_error_response(exc, status_code: int = 503):
    """Return a clear JSON response when MySQL is unavailable."""
    return (
        jsonify(
            {
                "success": False,
                "error": "mysql ingestion database is unavailable",
                "detail": str(exc),
            }
        ),
        status_code,
    )


def _send_to_celery(task_id: str, keyword: str):
    """Send one ingestion task to Celery/RabbitMQ."""
    return run_ingestion_task.delay(task_id, keyword)


def _enrich_task_for_frontend(task: dict) -> dict:
    """Add display-only fields expected by the enhanced ingestion console."""
    status = task.get("status")
    if status == "finished":
        current_stage = "writing_zep"
    elif status == "failed":
        current_stage = "failed"
    elif status == "running":
        current_stage = "summarizing"
    else:
        current_stage = "searching"

    return {
        "event_id": task.get("event_id") or "",
        "current_stage": task.get("current_stage") or current_stage,
        "retry_count": task.get("retry_count") or 0,
        **task,
    }


@ingestion_bp.route("/tasks", methods=["GET"])
def list_ingestion_tasks():
    """List ingestion tasks for the enhanced frontend console."""
    try:
        create_all_tables()
        tasks = ingestion_repository.list_tasks(
            limit=request.args.get("limit", 50),
            offset=request.args.get("offset", 0),
            status=request.args.get("status") or None,
        )
        return jsonify({"success": True, "tasks": [_enrich_task_for_frontend(task) for task in tasks]})
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)


@ingestion_bp.route("/tasks", methods=["POST"])
def create_ingestion_task():
    """Create an ingestion_task row and send it to Celery."""
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"success": False, "error": "keyword is required"}), 400

    try:
        create_all_tables()
        task = ingestion_repository.create_task(keyword=keyword, task_type="active_search")
        try:
            async_result = _send_to_celery(task["task_id"], keyword)
            return jsonify({"success": True, "task": _enrich_task_for_frontend(task), "celery_id": async_result.id}), 202
        except Exception as exc:
            failed_task = ingestion_repository.update_status(
                task["task_id"],
                status=INGESTION_STATUS_FAILED,
                error_message=f"failed to send celery task: {exc}",
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "failed to send celery task to RabbitMQ",
                        "detail": str(exc),
                        "task": _enrich_task_for_frontend(failed_task or task),
                    }
                ),
                503,
            )
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)


@ingestion_bp.route("/tasks/<task_id>", methods=["GET"])
def get_ingestion_task(task_id: str):
    """Return current ingestion task status."""
    try:
        create_all_tables()
        task = ingestion_repository.get_task(task_id)
        if task is None:
            return jsonify({"success": False, "error": "ingestion task not found"}), 404
        return jsonify({"success": True, "task": _enrich_task_for_frontend(task)})
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)


@ingestion_bp.route("/tasks/<task_id>/retry", methods=["POST"])
def retry_ingestion_task(task_id: str):
    """Retry a failed ingestion task by sending it to Celery again."""
    try:
        create_all_tables()
        task = ingestion_repository.get_task(task_id)
        if task is None:
            return jsonify({"success": False, "error": "ingestion task not found"}), 404
        if task.get("status") != INGESTION_STATUS_FAILED:
            return jsonify({"success": False, "error": "only failed tasks can be retried"}), 400

        reset_task = ingestion_repository.reset_for_retry(task_id)
        try:
            async_result = _send_to_celery(task_id, reset_task.get("keyword") or "")
            return jsonify({"success": True, "task": _enrich_task_for_frontend(reset_task), "celery_id": async_result.id}), 202
        except Exception as exc:
            failed_task = ingestion_repository.update_status(
                task_id,
                status=INGESTION_STATUS_FAILED,
                error_message=f"failed to send celery task: {exc}",
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "failed to send celery task to RabbitMQ",
                        "detail": str(exc),
                        "task": _enrich_task_for_frontend(failed_task or reset_task),
                    }
                ),
                503,
            )
    except (DatabaseUnavailableError, SQLAlchemyError) as exc:
        return _database_error_response(exc)


# ============== 项目级动态采集接口 ==============


@ingestion_bp.route("/project/<project_id>/extract-keywords", methods=["POST"])
def extract_project_keywords(project_id: str):
    """从项目种子材料中动态提取搜索关键词。

    请求体 (JSON):
        simulation_requirement: 仿真需求描述（可选）

    返回:
        {keywords: [...], search_queries: [...], domain_tags: [...]}
    """
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({"success": False, "error": "project not found"}), 404

    payload = request.get_json(silent=True) or {}
    sim_req = payload.get("simulation_requirement") or project.simulation_requirement

    try:
        file_paths = ProjectManager.get_project_files(project_id)
        if not file_paths:
            return jsonify({
                "success": False,
                "error": "项目没有上传种子文件，请先上传"
            }), 400

        all_text = TextProcessor.extract_from_files(file_paths)
        if not all_text or len(all_text.strip()) < 50:
            return jsonify({
                "success": False,
                "error": "种子材料文本内容不足"
            }), 400

        result = extract_keywords(
            all_text,
            simulation_requirement=sim_req,
            max_keywords=8,
        )
        return jsonify({"success": True, **result})

    except Exception as e:
        logger.error(f"提取关键词失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@ingestion_bp.route("/project/<project_id>/start", methods=["POST"])
def start_project_ingestion(project_id: str):
    """启动项目的定时主动信息采集。

    请求体 (JSON):
        keywords: 关键词列表（通常从 extract-keywords 获取）
        interval_seconds: 采集间隔秒数（可选，默认30分钟）

    采集的生命周期：项目启动时开始，模拟结束时自动停止。
    """
    payload = request.get_json(silent=True) or {}
    keywords = payload.get("keywords") or []
    interval_seconds = payload.get("interval_seconds")

    if not keywords:
        return jsonify({
            "success": False,
            "error": "keywords 不能为空，请先调用 extract-keywords"
        }), 400

    try:
        result = ProjectIngestionManager.instance().start_ingestion(
            project_id=project_id,
            keywords=keywords,
            interval_seconds=interval_seconds,
        )
        return jsonify(result)

    except Exception as e:
        logger.error(f"启动项目采集失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ingestion_bp.route("/project/<project_id>/stop", methods=["POST"])
def stop_project_ingestion(project_id: str):
    """停止项目的定时信息采集."""
    try:
        result = ProjectIngestionManager.instance().stop_ingestion(project_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"停止项目采集失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@ingestion_bp.route("/project/<project_id>/status", methods=["GET"])
def get_project_ingestion_status(project_id: str):
    """查询项目的采集状态."""
    try:
        result = ProjectIngestionManager.instance().get_status(project_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"查询项目采集状态失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
