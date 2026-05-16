# phase 7 react report agent

## goal

阶段 7 在原有 `ReportAgent` 基础上新增一个增强版入口：

`POST /api/report/traceable`

它不会替换原来的 `/api/report/generate`、`/api/report/chat`，而是作为整合层复用前面阶段已经完成的能力：

- active search
- memory recall
- graph retrieve
- agent interview
- confidence review
- evidence trace


## files

新增文件：

- `backend/app/services/report_tools.py`
- `backend/app/services/traceable_report_agent.py`
- `backend/app/services/evidence_trace.py`
- `docs/phase7_react_report_agent.md`

修改文件：

- `backend/app/api/report.py`
- `backend/app/config.py`
- `.env.example`


## tools

`memory_recall_tool(question)`

输入：用户问题。

输出：从 Chroma + MySQL 召回的长期记忆列表。失败时返回空列表和错误信息，不阻断报告生成。


`graph_retrieve_tool(question)`

输入：用户问题。

输出：从 Zep GraphRAG 召回的人物、组织、事件、观点等关系。Zep 未配置时返回错误信息，不阻断报告生成。


`active_search_tool(question)`

输入：用户问题。

输出：主动搜索结果。当前会复用阶段 4 的真实 provider 机制。


`interview_agents_tool(question, context)`

输入：用户问题和上下文。

输出优先级：

1. 如果 OASIS 仿真环境存活，尝试调用真实 agent interview。
2. 如果环境不可用，读取历史 interview 记录。
3. 如果没有 interview，读取 simulation action 日志。
4. 如果都没有，返回空结果和清晰错误信息。

注意：agent 采访只作为观点来源，不作为事实证据。


`confidence_review_tool(report_text)`

输入：初步报告文本。

输出：阶段 6 的 claim 拆分、多角色评审、置信度、风险等级。


`evidence_trace_tool(context)`

输入：已经收集好的 memory、graph、search、interview 上下文。

输出：统一的 evidence trace，每条证据包含：

- `evidence_id`
- `evidence_text`
- `source_type`
- `source`
- `url`
- `publish_time`
- `related_claim`
- `used_in_section`


## workflow

`traceable_report_agent.py` 的流程：

1. 创建上下文 `context`。
2. 调用 `memory_recall_tool`。
3. 调用 `graph_retrieve_tool`。
4. 如果 `use_active_search=true`，调用 `active_search_tool`。
5. 调用 `interview_agents_tool`。
6. 统一生成 `evidence_trace`。
7. 生成初步报告。
8. 如果 `use_review=true`，调用 `confidence_review_tool`。
9. 根据评审结果补充保守表述和不确定性。
10. 返回报告、证据链、记忆、图谱关系、agent 采访和评审结果。


## api

请求：

```bash
curl -X POST http://localhost:5001/api/report/traceable \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"分析方案 X 后续可能怎么发展\",\"project_id\":\"demo_project\",\"use_active_search\":true,\"use_review\":true}"
```

响应核心字段：

```json
{
  "success": true,
  "report": "...",
  "evidence_trace": [],
  "memory_used": [],
  "graph_relations_used": [],
  "active_search_used": [],
  "agent_interviews": [],
  "review_result": {},
  "tool_errors": []
}
```


## local test tips

本地没有 MySQL、Chroma、Zep、真实搜索或正在运行的 OASIS 环境时，接口仍然应该返回报告。

此时常见表现是：

- `memory_used` 为空。
- `graph_relations_used` 为空。
- `tool_errors` 中记录 MySQL、Chroma 或 Zep 不可用原因。

这说明阶段 7 的整合层可以明确暴露缺失依赖，但完整演示前仍需要接通真实基础设施。


## config

新增配置：

```env
TRACEABLE_REPORT_MEMORY_TOP_K=5
TRACEABLE_REPORT_GRAPH_LIMIT=5
TRACEABLE_REPORT_MAX_SEARCH_RESULTS=5
TRACEABLE_REPORT_MAX_INTERVIEWS=5
TRACEABLE_REPORT_INTERVIEW_TIMEOUT_SECONDS=15
```

报告生成和可信评审都依赖真实 LLM 配置；缺少配置时接口会返回清晰错误。
