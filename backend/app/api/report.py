"""
Report API路由
提供模拟报告生成、获取、对话等接口
"""

import json
import os
import traceback
import threading
from datetime import datetime
from flask import request, jsonify, send_file

from . import report_bp
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.locale import t, get_locale, set_locale

logger = get_logger('mirofish.api.report')


# ============== 报告生成接口 ==============

@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    生成模拟分析报告（异步任务）

    这是一个耗时操作，接口会立即返回task_id，
    使用 GET /api/report/generate/status 查询进度

    请求（JSON）：
        {
            "simulation_id": "sim_xxxx",    // 必填，模拟ID
            "force_regenerate": false,       // 可选，强制重新生成
            "use_enhanced": true             // 可选，默认true，使用增强版溯源报告
        }

    返回：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "报告生成任务已启动"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        force_regenerate = data.get('force_regenerate', False)
        use_enhanced = data.get('use_enhanced', True)  # 默认使用增强版

        # 获取模拟信息
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        # 检查是否已有报告
        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "message": t('api.reportAlreadyExists'),
                        "already_generated": True,
                        "use_enhanced": use_enhanced,
                    }
                })

        # 获取项目信息
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404

        graph_id = state.graph_id or project.graph_id
        simulation_requirement = project.simulation_requirement

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": t('api.missingSimRequirement')
            }), 400

        # 提前生成 report_id，以便立即返回给前端
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"

        # 创建异步任务
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id,
                "use_enhanced": use_enhanced,
            }
        )

        # Capture locale before spawning background thread
        current_locale = get_locale()

        if use_enhanced:
            _start_enhanced_report_thread(
                simulation_id, graph_id, simulation_requirement,
                report_id, task_id, task_manager, current_locale,
                project.project_id, force_regenerate,
            )
        else:
            _start_original_report_thread(
                simulation_id, graph_id, simulation_requirement,
                report_id, task_id, task_manager, current_locale,
            )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": t('api.reportGenerateStarted'),
                "already_generated": False,
                "use_enhanced": use_enhanced,
            }
        })

    except Exception as e:
        logger.error(f"启动报告生成任务失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _write_enhanced_agent_log(report_id: str, log_entry: dict):
    """Write one JSON line to agent_log.jsonl for the enhanced report."""
    report_dir = os.path.join(Config.UPLOAD_FOLDER, "reports", report_id)
    os.makedirs(report_dir, exist_ok=True)
    log_path = os.path.join(report_dir, "agent_log.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def _write_enhanced_console_log(report_id: str, message: str, level: str = "INFO"):
    """Write one console-style line to console_log.txt for the enhanced report."""
    report_dir = os.path.join(Config.UPLOAD_FOLDER, "reports", report_id)
    os.makedirs(report_dir, exist_ok=True)
    log_path = os.path.join(report_dir, "console_log.txt")
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {level}: {message}\n")


def _split_markdown_sections(markdown_text: str) -> list:
    """Split markdown by ## headings into section dicts [{title, content}]."""
    sections = []
    if not markdown_text:
        return sections
    lines = markdown_text.split("\n")
    current_title = None
    current_lines = []
    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            if current_title or current_lines:
                sections.append({
                    "title": current_title or "",
                    "content": "\n".join(current_lines).strip(),
                })
            current_title = line.lstrip("# ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_title or current_lines:
        sections.append({
            "title": current_title or "",
            "content": "\n".join(current_lines).strip(),
        })
    return sections


def _start_enhanced_report_thread(
    simulation_id, graph_id, simulation_requirement,
    report_id, task_id, task_manager, current_locale,
    project_id, force_regenerate,
):
    """启动增强版溯源报告生成后台线程."""
    def run_enhanced():
        set_locale(current_locale)
        start_time = datetime.now()

        def _elapsed():
            return round((datetime.now() - start_time).total_seconds(), 2)

        def _log(action, stage, details, section_title=None, section_index=None):
            _write_enhanced_agent_log(report_id, {
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": _elapsed(),
                "report_id": report_id,
                "action": action,
                "stage": stage,
                "section_title": section_title,
                "section_index": section_index,
                "details": details,
            })

        try:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=0,
                message=t('step4.enhProgressStarting'),
            )

            _log("report_start", "pending", {
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "Enhanced TraceableReportAgent started",
            })
            _write_enhanced_console_log(report_id, "Enhanced TraceableReportAgent started")
            _write_enhanced_console_log(report_id, f"Simulation: {simulation_id}")
            _write_enhanced_console_log(report_id, f"Question: {simulation_requirement[:120]}")

            from ..services.traceable_report_agent import TraceableReportAgent

            # --- tool stage: memory + graph ---
            _log("planning_start", "planning", {"message": "Recalling memory + retrieving graph relations..."})
            _write_enhanced_console_log(report_id, "Planning: recalling memory + retrieving graph relations")

            task_manager.update_task(
                task_id, progress=10,
                message=t('step4.enhProgressRecalling'),
            )

            _log("section_start", "generating", {
                "message": "Memory recall & graph retrieval",
            }, section_title=t('step4.enhSectionMemoryGraph'), section_index=1)
            _write_enhanced_console_log(report_id, "Section 1: Memory recall & graph retrieval")

            question = simulation_requirement
            agent = TraceableReportAgent()
            result = agent.run_traceable_report(
                question=question,
                options={
                    "project_id": project_id,
                    "simulation_id": simulation_id,
                    "graph_id": graph_id,
                    "use_active_search": False,
                    "use_review": True,
                },
            )

            _log("section_complete", "generating", {
                "message": "Memory recall & graph retrieval completed",
                "memory_count": len(result.get("memory_used", [])),
                "graph_count": len(result.get("graph_relations_used", [])),
            }, section_title=t('step4.enhSectionMemoryGraph'), section_index=1)

            task_manager.update_task(
                task_id, progress=50,
                message=t('step4.enhProgressInterviewing'),
            )

            # --- tool stage: interviews ---
            interviews = result.get("agent_interviews", [])
            _log("section_start", "generating", {
                "message": "Agent interviews",
            }, section_title=t('step4.enhSectionInterviews'), section_index=2)
            _log("section_complete", "generating", {
                "message": f"Completed {len(interviews)} interviews",
                "interview_count": len(interviews),
            }, section_title=t('step4.enhSectionInterviews'), section_index=2)
            _write_enhanced_console_log(report_id, f"Section 2: {len(interviews)} agent interviews completed")

            # --- tool stage: review ---
            review_result = result.get("review_result", {})
            _log("section_start", "generating", {
                "message": "Confidence review",
            }, section_title=t('step4.enhSectionReview'), section_index=3)
            avg_conf = review_result.get("summary", {}).get("average_confidence", 0) if review_result else 0
            _log("section_complete", "generating", {
                "message": f"Review completed, avg confidence={avg_conf}",
                "average_confidence": avg_conf,
            }, section_title=t('step4.enhSectionReview'), section_index=3)
            _write_enhanced_console_log(report_id, f"Section 3: Review completed, avg confidence={avg_conf}")

            task_manager.update_task(
                task_id, progress=70,
                message=t('step4.enhProgressGenerating'),
            )

            # --- Build content parts ---
            from ..services.report_agent import Report, ReportStatus as RS, ReportOutline, ReportSection

            trace_report = result.get("report", "")
            evidence_trace = result.get("evidence_trace", [])
            memory_used = result.get("memory_used", [])
            graph_relations = result.get("graph_relations_used", [])
            tool_errors = result.get("tool_errors", [])
            report_warnings = result.get("report_warnings", [])

            enhanced_markdown = _build_enhanced_report_sections(
                evidence_trace, review_result, memory_used,
                graph_relations, interviews, tool_errors,
                report_warnings,
            )

            full_markdown = trace_report + enhanced_markdown

            # Split trace_report into subsections by ## headings
            trace_subsections = _split_markdown_sections(trace_report)

            # Build outline for streaming display
            outline_sections = []
            for sub in trace_subsections:
                outline_sections.append({"title": sub["title"]})
            if enhanced_markdown.strip():
                outline_sections.append({"title": t('step4.enhEnhancedTraceInfo')})

            outline = ReportOutline(
                title=t('step4.enhReportTitle'),
                summary=t('step4.enhReportSummary'),
                sections=[
                    ReportSection(title=sub["title"], content=sub["content"])
                    for sub in trace_subsections
                ]
                + (
                    [ReportSection(title=t('step4.enhEnhancedTraceInfo'), content=enhanced_markdown)]
                    if enhanced_markdown.strip()
                    else []
                ),
            )

            # --- planning_complete: emit outline so left panel shows ---
            _log("planning_complete", "generating", {
                "message": "All sections generated",
                "outline": {
                    "title": outline.title,
                    "summary": outline.summary,
                    "sections": outline_sections,
                },
            })
            _write_enhanced_console_log(report_id, f"Outline ready: {len(outline_sections)} sections planned")

            # --- Stream each section: section_start → section_content → section_complete ---
            import time as _time

            for idx, sub in enumerate(trace_subsections, start=1):
                s_title = sub["title"] or f"Section {idx}"
                s_content = sub["content"]

                _log("section_start", "generating", {
                    "message": f"Generating: {s_title}",
                }, section_title=s_title, section_index=idx)
                _write_enhanced_console_log(report_id, f"Generating section {idx}: {s_title}")

                # Small delay to create streaming effect
                _time.sleep(0.3)

                _log("section_content", "generating", {
                    "content": s_content,
                    "message": f"Content ready for: {s_title}",
                }, section_title=s_title, section_index=idx)

                _log("section_complete", "generating", {
                    "content": s_content,
                    "message": f"Section completed: {s_title}",
                    "word_count": len(s_content),
                }, section_title=s_title, section_index=idx)
                _write_enhanced_console_log(report_id, f"Section {idx} completed: {len(s_content)} chars")

                task_manager.update_task(
                    task_id,
                    progress=70 + int(20 * idx / max(len(trace_subsections), 1)),
                    message=f"已生成章节: {s_title}",
                )

            # Enhanced trace info as final section
            if enhanced_markdown.strip():
                sec_idx = len(trace_subsections) + 1
                s_title = t('step4.enhEnhancedTraceInfo')
                _log("section_start", "generating", {
                    "message": f"Generating: {s_title}",
                }, section_title=s_title, section_index=sec_idx)
                _time.sleep(0.2)

                _log("section_content", "generating", {
                    "content": enhanced_markdown,
                    "message": f"Content ready for: {s_title}",
                }, section_title=s_title, section_index=sec_idx)

                _log("section_complete", "generating", {
                    "content": enhanced_markdown,
                    "message": f"Section completed: {s_title}",
                    "word_count": len(enhanced_markdown),
                }, section_title=s_title, section_index=sec_idx)
                _write_enhanced_console_log(report_id, f"Section {sec_idx} completed: {len(enhanced_markdown)} chars")

            # --- Save report ---
            report = Report(
                report_id=report_id,
                simulation_id=simulation_id,
                graph_id=graph_id or "",
                simulation_requirement=simulation_requirement,
                status=RS.COMPLETED,
                outline=outline,
                markdown_content=full_markdown,
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
            )

            _save_enhanced_trace_data(report_id, result)
            ReportManager.save_report(report)

            # --- report_complete ---
            _log("report_complete", "completed", {
                "message": "Enhanced report generation completed",
                "report_id": report_id,
                "simulation_id": simulation_id,
                "evidence_count": len(evidence_trace),
                "memory_count": len(memory_used),
                "review_confidence": avg_conf,
                "total_words": len(full_markdown),
            })
            _write_enhanced_console_log(
                report_id,
                f"Report completed: {len(full_markdown)} chars, "
                f"{len(evidence_trace)} evidence, {len(memory_used)} memories",
            )

            task_manager.complete_task(
                task_id,
                result={
                    "report_id": report.report_id,
                    "simulation_id": simulation_id,
                    "status": "completed",
                    "use_enhanced": True,
                    "evidence_count": len(evidence_trace),
                    "memory_count": len(memory_used),
                    "review_confidence": avg_conf,
                },
            )

        except Exception as e:
            logger.error(f"增强版报告生成失败: {str(e)}")
            _log("report_error", "failed", {"error": str(e)})
            _write_enhanced_console_log(report_id, f"Report FAILED: {e}", level="ERROR")
            task_manager.fail_task(task_id, str(e))

    thread = threading.Thread(target=run_enhanced, daemon=True)
    thread.start()


def _start_original_report_thread(
    simulation_id, graph_id, simulation_requirement,
    report_id, task_id, task_manager, current_locale,
):
    """启动原始版报告生成后台线程."""
    def run_generate():
        set_locale(current_locale)
        try:
            task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=0,
                message=t('api.initReportAgent')
            )

            # 创建Report Agent
            agent = ReportAgent(
                graph_id=graph_id,
                simulation_id=simulation_id,
                simulation_requirement=simulation_requirement
            )

            # 进度回调
            def progress_callback(stage, progress, message):
                task_manager.update_task(
                    task_id,
                    progress=progress,
                    message=f"[{stage}] {message}"
                )

            # 生成报告（传入预先生成的 report_id）
            report = agent.generate_report(
                progress_callback=progress_callback,
                report_id=report_id
            )

            # 保存报告
            ReportManager.save_report(report)

            if report.status == ReportStatus.COMPLETED:
                task_manager.complete_task(
                    task_id,
                    result={
                        "report_id": report.report_id,
                        "simulation_id": simulation_id,
                        "status": "completed",
                        "use_enhanced": False,
                    }
                )
            else:
                task_manager.fail_task(task_id, report.error or t('api.reportGenerateFailed'))

        except Exception as e:
            logger.error(f"报告生成失败: {str(e)}")
            task_manager.fail_task(task_id, str(e))

    thread = threading.Thread(target=run_generate, daemon=True)
    thread.start()


@report_bp.route('/generate/status', methods=['POST'])
def get_generate_status():
    """
    查询报告生成任务进度
    
    请求（JSON）：
        {
            "task_id": "task_xxxx",         // 可选，generate返回的task_id
            "simulation_id": "sim_xxxx"     // 可选，模拟ID
        }
    
    返回：
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # 如果提供了simulation_id，先检查是否已有完成的报告
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": t('api.reportGenerated'),
                        "already_completed": True
                    }
                })
        
        if not task_id:
            return jsonify({
                "success": False,
                "error": t('api.requireTaskOrSimId')
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "success": False,
                "error": t('api.taskNotFound', id=task_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== 报告获取接口 ==============

@report_bp.route('/traceable', methods=['POST'])
def generate_traceable_report():
    """
    Generate a traceable prediction report with enhanced report tools.

    This route is additive and does not replace the original asynchronous
    /api/report/generate workflow.
    """
    try:
        data = request.get_json() or {}

        question = (data.get('question') or '').strip()
        if not question:
            return jsonify({
                "success": False,
                "error": "question is required"
            }), 400

        from ..services.traceable_report_agent import TraceableReportAgent

        agent = TraceableReportAgent()
        result = agent.run_traceable_report(
            question=question,
            options={
                "project_id": data.get("project_id"),
                "simulation_id": data.get("simulation_id"),
                "graph_id": data.get("graph_id"),
                "use_active_search": bool(data.get("use_active_search", False)),
                "use_review": bool(data.get("use_review", True)),
            }
        )

        return jsonify({
            "success": True,
            **result
        })

    except Exception as e:
        logger.error(f"Traceable report generation failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    获取报告详情

    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "use_enhanced": true,
                "enhanced_trace": {...},
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    try:
        report = ReportManager.get_report(report_id)

        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404

        data = report.to_dict()

        # 尝试加载增强版溯源数据
        enhanced_trace = _load_enhanced_trace_data(report_id)
        if enhanced_trace:
            data["use_enhanced"] = True
            data["enhanced_trace"] = {
                "evidence_trace": enhanced_trace.get("evidence_trace", []),
                "memory_used": enhanced_trace.get("memory_used", []),
                "graph_relations_used": enhanced_trace.get("graph_relations_used", []),
                "agent_interviews": enhanced_trace.get("agent_interviews", []),
                "review_result": enhanced_trace.get("review_result"),
                "tool_errors": enhanced_trace.get("tool_errors", []),
                "report_warnings": enhanced_trace.get("report_warnings", []),
            }
        else:
            data["use_enhanced"] = False
            data["enhanced_trace"] = None

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    根据模拟ID获取报告
    
    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.noReportForSim', id=simulation_id),
                "has_report": False
            }), 404
        
        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })
        
    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    """
    列出所有报告
    
    Query参数：
        simulation_id: 按模拟ID过滤（可选）
        limit: 返回数量限制（默认50）
    
    返回：
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)
        
        reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in reports],
            "count": len(reports)
        })
        
    except Exception as e:
        logger.error(f"列出报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    下载报告（Markdown格式）
    
    返回Markdown文件
    """
    try:
        report = ReportManager.get_report(report_id)
        
        if not report:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        md_path = ReportManager._get_report_markdown_path(report_id)
        
        if not os.path.exists(md_path):
            # 如果MD文件不存在，生成一个临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )
        
        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )
        
    except Exception as e:
        logger.error(f"下载报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """删除报告"""
    try:
        success = ReportManager.delete_report(report_id)
        
        if not success:
            return jsonify({
                "success": False,
                "error": t('api.reportNotFound', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "message": t('api.reportDeleted', id=report_id)
        })
        
    except Exception as e:
        logger.error(f"删除报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Report Agent对话接口 ==============

@report_bp.route('/chat', methods=['POST'])
def chat_with_report_agent():
    """
    与Report Agent对话
    
    Report Agent可以在对话中自主调用检索工具来回答问题
    
    请求（JSON）：
        {
            "simulation_id": "sim_xxxx",        // 必填，模拟ID
            "message": "请解释一下舆情走向",    // 必填，用户消息
            "chat_history": [                   // 可选，对话历史
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    
    返回：
        {
            "success": true,
            "data": {
                "response": "Agent回复...",
                "tool_calls": [调用的工具列表],
                "sources": [信息来源]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": t('api.requireSimulationId')
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "error": t('api.requireMessage')
            }), 400
        
        # 获取模拟和项目信息
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": t('api.simulationNotFound', id=simulation_id)
            }), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": t('api.projectNotFound', id=state.project_id)
            }), 404
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.missingGraphId')
            }), 400
        
        simulation_requirement = project.simulation_requirement or ""
        
        # 创建Agent并进行对话
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement
        )
        
        result = agent.chat(message=message, chat_history=chat_history)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"对话失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 报告进度与分章节接口 ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    """
    获取报告生成进度（实时）
    
    返回：
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "正在生成章节: 关键发现",
                "current_section": "关键发现",
                "completed_sections": ["执行摘要", "模拟背景"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    try:
        progress = ReportManager.get_progress(report_id)
        
        if not progress:
            return jsonify({
                "success": False,
                "error": t('api.reportProgressNotAvail', id=report_id)
            }), 404
        
        return jsonify({
            "success": True,
            "data": progress
        })
        
    except Exception as e:
        logger.error(f"获取报告进度失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    """
    获取已生成的章节列表（分章节输出）
    
    前端可以轮询此接口获取已生成的章节内容，无需等待整个报告完成
    
    返回：
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## 执行摘要\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    try:
        sections = ReportManager.get_generated_sections(report_id)
        
        # 获取报告状态
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })
        
    except Exception as e:
        logger.error(f"获取章节列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    """
    获取单个章节内容
    
    返回：
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## 执行摘要\\n\\n..."
            }
        }
    """
    try:
        section_path = ReportManager._get_section_path(report_id, section_index)
        
        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": t('api.sectionNotFound', index=f"{section_index:02d}")
            }), 404
        
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })
        
    except Exception as e:
        logger.error(f"获取章节内容失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 报告状态检查接口 ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    检查模拟是否有报告，以及报告状态
    
    用于前端判断是否解锁Interview功能
    
    返回：
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    try:
        report = ReportManager.get_report_by_simulation(simulation_id)
        
        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None
        
        # 只有报告完成后才解锁interview
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })
        
    except Exception as e:
        logger.error(f"检查报告状态失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Agent 日志接口 ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    获取 Report Agent 的详细执行日志
    
    实时获取报告生成过程中的每一步动作，包括：
    - 报告开始、规划开始/完成
    - 每个章节的开始、工具调用、LLM响应、完成
    - 报告完成或失败
    
    Query参数：
        from_line: 从第几行开始读取（可选，默认0，用于增量获取）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "执行摘要",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"获取Agent日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    获取完整的 Agent 日志（一次性获取全部）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        logs = ReportManager.get_agent_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"获取Agent日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 控制台日志接口 ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    获取 Report Agent 的控制台输出日志
    
    实时获取报告生成过程中的控制台输出（INFO、WARNING等），
    这与 agent-log 接口返回的结构化 JSON 日志不同，
    是纯文本格式的控制台风格日志。
    
    Query参数：
        from_line: 从第几行开始读取（可选，默认0，用于增量获取）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: 搜索完成: 找到 15 条相关事实",
                    "[19:46:14] INFO: 图谱搜索: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"获取控制台日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    获取完整的控制台日志（一次性获取全部）
    
    返回：
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        logs = ReportManager.get_console_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"获取控制台日志失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 工具调用接口（供调试使用）==============

@report_bp.route('/tools/search', methods=['POST'])
def search_graph_tool():
    """
    图谱搜索工具接口（供调试使用）
    
    请求（JSON）：
        {
            "graph_id": "mirofish_xxxx",
            "query": "搜索查询",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        
        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphIdAndQuery')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"图谱搜索失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
def get_graph_statistics_tool():
    """
    图谱统计工具接口（供调试使用）
    
    请求（JSON）：
        {
            "graph_id": "mirofish_xxxx"
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        
        if not graph_id:
            return jsonify({
                "success": False,
                "error": t('api.requireGraphId')
            }), 400
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.get_graph_statistics(graph_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"获取图谱统计失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== 增强版报告辅助函数 ==============


def _build_enhanced_report_sections(
    evidence_trace, review_result, memory_used,
    graph_relations, agent_interviews, tool_errors,
    report_warnings,
) -> str:
    """构建增强版报告的溯源信息尾部."""
    sections = []

    # 证据溯源
    sections.append(f"\n\n## {t('step4.enhEvidenceTrace')}")
    if evidence_trace:
        for ev in evidence_trace[:10]:
            eid = ev.get("evidence_id", "?")
            text = ev.get("evidence_text", "")
            src = ev.get("source", "")
            url = ev.get("url", "")
            sections.append(f"- [{eid}] {text} ({t('step4.ruleSource')}: {src}, URL: {url})")
    else:
        sections.append(f"- {t('step4.enhNoEvidenceTrace')}")

    # 记忆召回
    sections.append(f"\n## {t('step4.enhMemoryRecall')}")
    if memory_used:
        for m in memory_used[:5]:
            title = m.get("title") or m.get("summary", "")
            score = m.get("importance_score", 0)
            sections.append(f"- [{score:.2f}] {title}")
    else:
        sections.append(f"- {t('step4.enhNoMemory')}")

    # 图谱关系
    sections.append(f"\n## {t('step4.enhGraphRelations')}")
    if graph_relations:
        for r in graph_relations[:5]:
            src_n = r.get("source_node_name") or r.get("source", "")
            tgt_n = r.get("target_node_name") or r.get("target", "")
            rel = r.get("relation", "related_to")
            sections.append(f"- {src_n} -> [{rel}] -> {tgt_n}")
    else:
        sections.append(f"- {t('step4.enhNoGraphRelations')}")

    # Agent 采访
    sections.append(f"\n## {t('step4.enhAgentInterviews')}")
    if agent_interviews:
        for iv in agent_interviews[:5]:
            agent = iv.get("agent_name", "unknown")
            resp = iv.get("response", "")
            sections.append(f"- **{agent}**: {resp[:200]}")
    else:
        sections.append(f"- {t('step4.enhNoInterviews')}")

    # 可信度审查
    sections.append(f"\n## {t('step4.enhConfidenceReview')}")
    if review_result and review_result.get("success"):
        summary = review_result.get("summary", {})
        avg_conf = summary.get("average_confidence", 0)
        risk_levels = summary.get("risk_levels", {})
        sections.append(f"- {t('step4.enhAvgConfidence')}: {avg_conf}")
        sections.append(f"- {t('step4.enhRiskDistribution')}: {risk_levels}")
        for claim in (review_result.get("claims") or [])[:5]:
            sections.append(f"- {t('step4.enhClaim')}: {claim.get('claim', '')[:100]}")
    else:
        sections.append(f"- {t('step4.enhReviewNotRun')}")

    # 工具错误
    if tool_errors:
        sections.append(f"\n## {t('step4.enhToolWarnings')}")
        for err in tool_errors:
            sections.append(f"- [{err.get('tool')}] {err.get('error')}")

    # 报告警告
    if report_warnings:
        sections.append(f"\n## {t('step4.ruleGenerationNotes')}")
        for w in report_warnings:
            sections.append(f"- {w}")

    return "\n".join(sections)


def _save_enhanced_trace_data(report_id: str, result: dict) -> None:
    """保存增强版报告的完整溯源数据到 JSON 文件."""
    report_dir = os.path.join(Config.UPLOAD_FOLDER, "reports", report_id)
    os.makedirs(report_dir, exist_ok=True)
    trace_path = os.path.join(report_dir, "enhanced_trace.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)


def _load_enhanced_trace_data(report_id: str) -> dict | None:
    """从 JSON 文件加载增强版报告的溯源数据."""
    trace_path = os.path.join(
        Config.UPLOAD_FOLDER, "reports", report_id, "enhanced_trace.json"
    )
    if not os.path.exists(trace_path):
        return None
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
