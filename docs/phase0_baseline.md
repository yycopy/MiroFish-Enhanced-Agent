# phase 0 baseline

本文档记录当前 MiroFish 项目的基线状态。本阶段只做结构确认和文档补充，不修改核心业务逻辑。

## 1. 当前项目目录结构说明

顶层结构：

```text
.
├── README.md
├── README-ZH.md
├── .env.example
├── docker-compose.yml
├── package.json
├── backend/
├── frontend/
├── static/
└── locales/
```

后端核心结构：

```text
backend/
├── run.py
├── pyproject.toml
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── api/
│   │   ├── graph.py
│   │   ├── simulation.py
│   │   └── report.py
│   ├── models/
│   │   ├── project.py
│   │   └── task.py
│   ├── services/
│   │   ├── graph_builder.py
│   │   ├── ontology_generator.py
│   │   ├── text_processor.py
│   │   ├── zep_entity_reader.py
│   │   ├── zep_graph_memory_updater.py
│   │   ├── zep_tools.py
│   │   ├── oasis_profile_generator.py
│   │   ├── simulation_config_generator.py
│   │   ├── simulation_manager.py
│   │   ├── simulation_runner.py
│   │   ├── simulation_ipc.py
│   │   └── report_agent.py
│   └── utils/
│       ├── file_parser.py
│       ├── llm_client.py
│       ├── logger.py
│       ├── retry.py
│       ├── locale.py
│       └── zep_paging.py
├── scripts/
│   ├── run_parallel_simulation.py
│   ├── run_reddit_simulation.py
│   ├── run_twitter_simulation.py
│   ├── action_logger.py
│   └── test_profile_format.py
└── uploads/
```

前端核心结构：

```text
frontend/src/
├── api/
│   ├── graph.js
│   ├── simulation.js
│   └── report.js
├── components/
│   ├── Step1GraphBuild.vue
│   ├── Step2EnvSetup.vue
│   ├── Step3Simulation.vue
│   ├── Step4Report.vue
│   └── Step5Interaction.vue
└── views/
```

Flask 入口：

- 启动入口：`backend/run.py`
- Flask app 工厂：`backend/app/__init__.py`
- 健康检查：`GET /health`

现有蓝图注册：

```text
/api/graph       -> backend/app/api/graph.py
/api/simulation  -> backend/app/api/simulation.py
/api/report      -> backend/app/api/report.py
/health          -> backend/app/__init__.py
```

## 2. 原项目已有能力

### Flask API

已有 Flask 应用工厂和三组主要业务 API：

- `graph`：项目、ontology 生成、图谱构建、图谱数据读取。
- `simulation`：从图谱读取实体、创建仿真、准备 profile/config、启动/停止仿真、读取行为日志、采访 agent。
- `report`：生成报告、查询报告、下载报告、ReportAgent chat、报告工具查询。
- `health`：返回后端服务健康状态。

### LLM 调用

项目使用 OpenAI SDK 兼容格式调用模型：

- 配置位置：`backend/app/config.py`
- 工具封装：`backend/app/utils/llm_client.py`
- 使用位置：ontology 生成、agent profile 生成、simulation config 生成、report 生成。

### Zep GraphRAG

原项目已经接入 Zep：

- `backend/app/services/graph_builder.py`
  - 创建 zep graph。
  - 设置 ontology。
  - 将文本 chunk 批量写入 zep。
- `backend/app/services/zep_entity_reader.py`
  - 从 zep 读取 nodes / edges。
  - 过滤有效实体。
  - 补充 related_edges / related_nodes。
- `backend/app/services/zep_tools.py`
  - 给 ReportAgent 提供图谱检索、统计、实体摘要、仿真上下文等工具。
- `backend/app/services/zep_graph_memory_updater.py`
  - 监听仿真 actions 日志。
  - 将有意义的 agent 行为增量写回 zep graph。
- `backend/app/services/oasis_profile_generator.py`
  - 生成 agent profile 时会用 zep search 补充实体上下文。

### ReportAgent

ReportAgent 位于：

```text
backend/app/services/report_agent.py
```

已有能力：

- 规划报告大纲。
- 按章节生成 markdown 报告。
- 使用 ReAct 风格工具调用。
- 当前工具主要包括：
  - `insight_forge`
  - `panorama_search`
  - `quick_search`
  - `interview_agents`
- 报告产物保存在 `backend/uploads/reports/{report_id}/`。

### simulation / camel-oasis 调用链路

核心链路：

```text
backend/app/api/simulation.py
-> SimulationManager.prepare_simulation
-> ZepEntityReader.filter_defined_entities
-> OasisProfileGenerator.generate_profiles_from_entities
-> SimulationConfigGenerator.generate_config
-> SimulationRunner.start_simulation
-> backend/scripts/run_parallel_simulation.py
-> camel-oasis
```

主要文件：

- `backend/app/services/simulation_manager.py`
  - 创建仿真状态。
  - 从 zep 读取实体。
  - 生成 reddit/twitter agent profile。
  - 生成 `simulation_config.json`。
- `backend/app/services/oasis_profile_generator.py`
  - 将 zep entity 转成 OASIS agent profile。
  - reddit 输出 json，twitter 输出 csv。
- `backend/app/services/simulation_config_generator.py`
  - 生成仿真时间、事件、agent 活跃度、平台配置。
- `backend/app/services/simulation_runner.py`
  - 使用 `subprocess.Popen` 启动仿真脚本。
  - 读取 `actions.jsonl` 更新运行状态。
  - 可选将行为写回 zep。
- `backend/scripts/run_parallel_simulation.py`
  - 读取 profile/config。
  - 调用 `generate_twitter_agent_graph` / `generate_reddit_agent_graph`。
  - 调用 `oasis.make(...)` 创建模拟环境。
  - 调用 `env.step(...)` 推进每轮仿真。
- `backend/scripts/action_logger.py`
  - 写入 `twitter/actions.jsonl` 和 `reddit/actions.jsonl`。

### 当前数据持久化方式

项目当前主要使用文件系统和 sqlite：

```text
backend/uploads/projects/
  project.json
  extracted_text.txt
  files/*

backend/uploads/simulations/{simulation_id}/
  state.json
  run_state.json
  reddit_profiles.json
  twitter_profiles.csv
  simulation_config.json
  simulation.log
  twitter/actions.jsonl
  reddit/actions.jsonl
  twitter_simulation.db
  reddit_simulation.db
  env_status.json

backend/uploads/reports/{report_id}/
  meta.json
  outline.json
  progress.json
  section_*.md
  full_report.md
  agent_log.jsonl
  console_log.txt
```

当前没有统一的 MySQL/SQLAlchemy 数据层。`backend/app/models/project.py` 和 `backend/app/models/task.py` 是文件/内存式管理，不是 ORM。

### docker-compose 当前服务

当前 `docker-compose.yml` 只有一个服务：

```text
mirofish
```

该服务：

- 使用镜像 `ghcr.io/666ghj/mirofish:latest`
- 读取 `.env`
- 暴露端口：
  - `3000:3000`
  - `5001:5001`
- 挂载：
  - `./backend/uploads:/app/backend/uploads`

当前 docker compose 中还没有：

- mysql
- rabbitmq
- celery worker
- apscheduler / scheduler
- chroma

## 3. 原项目缺少的能力

当前原项目缺少或尚未工程化的能力：

1. 主动信息采集链路
   - 没有周期性搜索。
   - 没有外部信息源 connector。
   - 没有搜索、清洗、去重、摘要、入库的异步流水线。

2. 长期记忆数据库
   - 没有 MySQL。
   - 没有 SQLAlchemy。
   - 没有 Alembic migration。
   - 历史资料主要分散在 json/csv/markdown/sqlite 文件中。

3. 语义召回
   - 没有 Chroma。
   - 没有统一 vector store 抽象。
   - 没有按相似度召回历史记忆并注入上下文的模块。

4. 生产级异步任务系统
   - 当前 prepare/report 等耗时任务主要依赖 `threading.Thread`。
   - 当前 task 状态主要是内存任务管理。
   - 没有 RabbitMQ/Celery 的可靠队列、重试和 worker 模式。

5. 调度系统
   - 没有 APScheduler。
   - 暂无周期性主动采集任务。

6. 多 Agent 可信评审
   - 当前 ReportAgent 已能调用工具生成报告。
   - 但还没有独立的多角色、多立场、多证据切片评审服务。
   - 缺少 claim 级置信度评分和证据追踪结构。

7. 可追溯报告增强
   - 当前报告已有 agent log 和 console log。
   - 但还没有统一的 evidence trace、长期记忆引用、主动搜索引用和可信评审结果落库。

## 4. 后续增强点落点建议

### 配置和扩展初始化

建议落点：

```text
backend/app/config.py
backend/app/extensions.py
backend/app/db.py
.env.example
docker-compose.yml
```

用途：

- 增加 MySQL、RabbitMQ、Celery、Chroma、Scheduler 配置。
- 建立可选初始化和 fallback 状态。

### MySQL / SQLAlchemy / Alembic

建议新增：

```text
backend/app/models/memory.py
backend/app/models/ingestion.py
backend/app/models/review.py
backend/app/repositories/
backend/migrations/
```

用途：

- 保存结构化长期记忆。
- 保存采集任务、来源、摘要、证据、评审结果。

### RabbitMQ / Celery / APScheduler

建议新增：

```text
backend/app/tasks/celery_app.py
backend/app/tasks/ingestion_tasks.py
backend/app/tasks/scheduler.py
backend/app/api/tasks.py
```

用途：

- 主动采集、清洗、摘要、入库。
- 后续可逐步承接原有耗时任务，但阶段初期不替换原有线程逻辑。

### 主动采集和文本清洗

建议新增：

```text
backend/app/api/ingestion.py
backend/app/services/active_search_service.py
backend/app/services/content_cleaner.py
backend/app/services/dedup_service.py
backend/app/services/summary_service.py
```

用途：

- 搜索、清洗、去重、摘要压缩。
- 未配置外部搜索服务时主动采集不可用，需要接入真实 provider。

### Chroma 语义记忆

建议新增：

```text
backend/app/services/vector_store.py
backend/app/services/memory_store.py
backend/app/services/memory_retriever.py
backend/app/services/context_injector.py
backend/app/api/memory.py
```

用途：

- 保存文本 embedding。
- 按语义召回历史记忆。
- 给 simulation config 和 ReportAgent 注入上下文。

### Zep 图谱关系增强

建议复用并增强：

```text
backend/app/services/zep_graph_memory_updater.py
backend/app/services/zep_tools.py
backend/app/services/graph_builder.py
```

建议新增：

```text
backend/app/services/zep_schema_service.py
backend/app/services/zep_memory_writer.py
```

用途：

- 规范人物、组织、事件、观点、证据的关系写入。
- 将仿真行为转成更稳定的图谱记忆。

### 多 Agent 可信评审

建议新增：

```text
backend/app/api/review.py
backend/app/services/review_agent.py
backend/app/services/evidence_slicer.py
backend/app/services/confidence_scorer.py
```

用途：

- claim 拆分。
- 支持/反对证据召回。
- 多角色独立评审。
- 输出置信度。

### ReAct ReportAgent 工具增强

建议修改：

```text
backend/app/services/report_agent.py
backend/app/api/report.py
```

新增工具建议：

```text
active_search
memory_recall
graph_retrieve
confidence_review
evidence_trace
```

原则：

- 保留现有工具和 API。
- 新工具作为增量注册。
- 未配置外部依赖时返回清晰错误或 fallback，而不是中断整个报告生成。

## 5. 当前项目如何启动

### 源码方式

安装依赖：

```bash
npm run setup:all
```

复制并配置环境变量：

```bash
cp .env.example .env
```

当前必要配置：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

同时启动前后端：

```bash
npm run dev
```

单独启动后端：

```bash
npm run backend
```

等价于：

```bash
cd backend
uv run python run.py
```

单独启动前端：

```bash
npm run frontend
```

服务地址：

```text
frontend: http://localhost:3000
backend:  http://localhost:5001
```

注意：

- `backend/run.py` 当前会调用 `Config.validate()`。
- 如果缺少 `LLM_API_KEY` 或 `ZEP_API_KEY`，后端会在启动时退出。

### Docker 方式

```bash
cp .env.example .env
docker compose up -d
```

当前 docker compose 只启动 `mirofish` 一个服务，不会启动 MySQL、RabbitMQ、Chroma 或 Celery worker。

## 6. 当前项目健康检查接口如何测试

后端启动后：

```bash
curl http://localhost:5001/health
```

预期返回：

```json
{
  "status": "ok",
  "service": "MiroFish Backend"
}
```

本阶段已用 Flask test client 做过轻量检查：

```bash
cd backend
uv run python -c "from app import create_app; app=create_app(); client=app.test_client(); resp=client.get('/health'); print(resp.status_code); print(resp.get_json())"
```

实际结果：

```text
200
{'service': 'MiroFish Backend', 'status': 'ok'}
```

这次检查没有启动长时间服务，也没有调用外部 LLM 或 Zep API。

## 7. 本阶段结论

阶段 0 已确认：

- Flask 入口存在且可创建 app。
- `/health` 可用。
- `graph / simulation / report` 三组 API 已注册。
- 原项目已经使用 Zep GraphRAG。
- 原项目已经有 ReportAgent。
- 原项目已经有 camel-oasis 仿真链路。
- 当前持久化以文件系统、json、csv、markdown、sqlite 为主。
- 当前 docker compose 只有单个 `mirofish` 服务。

阶段 0 未做：

- 未修改核心业务逻辑。
- 未新增数据库。
- 未新增任务系统。
- 未新增主动采集、长期记忆、语义召回或可信评审功能。
