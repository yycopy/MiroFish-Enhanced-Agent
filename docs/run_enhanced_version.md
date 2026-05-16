# 增强版 docker 运行说明

本文档说明如何用 `docker compose` 启动增强版 MiroFish 的核心依赖和后端任务链路。

原有启动方式仍然保留：

```bash
npm run dev
```

增强版启动方式是新增的，不会替换原项目的本地开发方式。


## 1. 准备 .env

复制环境变量模板：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```


## 2. 填写 LLM 配置

项目使用 OpenAI-Compatible LLM，也就是只要服务兼容 OpenAI 的 `/v1/chat/completions` 格式，就可以接入。

至少填写：

```env
LLM_API_KEY=你的模型服务 key
LLM_BASE_URL=https://你的模型服务地址/v1
LLM_MODEL_NAME=你的模型名

OPENAI_API_KEY=你的模型服务 key
OPENAI_BASE_URL=https://你的模型服务地址/v1
OPENAI_MODEL=你的模型名
```

增强版运行文档默认只描述真实配置路径。请确保 LLM、Embedding、MySQL、RabbitMQ、Chroma、Zep 都已经配置可用。主动采集需要先在 `backend/app/services/active_search_service.py` 接入真实搜索 provider。


## 3. 填写 Zep 配置

原项目和阶段 5 的图谱记忆都依赖 Zep。

```env
ZEP_API_KEY=你的 zep key
ZEP_API_URL=
ZEP_ENHANCED_GRAPH_ID=mirofish_enhanced_memory
```

如果 Zep 未配置，增强版接口不会直接崩溃，但 `graph_retrieve` 会返回清晰的不可用信息，图谱召回结果会为空。


## 4. 启动基础服务

只启动 MySQL、RabbitMQ、Chroma：

```bash
docker compose up -d mysql rabbitmq chroma
```

查看状态：

```bash
docker compose ps
```

RabbitMQ 管理页面：

```text
http://localhost:15672
```

默认账号密码来自 `.env`：

```env
RABBITMQ_USER=mirofish
RABBITMQ_PASSWORD=mirofish_password
```

检查 MySQL：

```bash
docker compose exec mysql mysql -umirofish -pmirofish_password -e "select 1;"
```

检查 Chroma：

```bash
docker compose ps chroma
```

也可以尝试访问：

```bash
curl http://localhost:8000/api/v1/heartbeat
```

如果你的 Chroma 镜像使用 v2 API，可以尝试：

```bash
curl http://localhost:8000/api/v2/heartbeat
```


## 5. 启动完整增强版服务

启动后端、Celery worker、APScheduler：

```bash
docker compose up -d --build backend-app celery-worker scheduler
```

或者一次性启动全部默认增强服务：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f backend-app
docker compose logs -f celery-worker
docker compose logs -f scheduler
```

后端健康检查：

```bash
curl http://localhost:5001/health
```


## 6. 服务说明

`mysql`

用于长期记忆、主动采集任务、可信评审结果等结构化数据。

`rabbitmq`

作为 Celery broker，负责把采集任务从 Flask API 投递给 worker。

`chroma`

用于长期记忆的向量存储和语义召回。

`backend-app`

运行 Flask 后端：

```bash
uv run python run.py
```

`celery-worker`

运行异步任务消费者：

```bash
uv run celery -A app.tasks.celery_app worker -l info
```

`scheduler`

运行 APScheduler 定时器：

```bash
uv run python -m app.tasks.scheduler
```


## 7. 手动触发 ingestion

触发主动采集任务：

```bash
curl -X POST http://localhost:5001/api/ingestion/tasks \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"方案 X\"}"
```

返回里会有 `task_id`。

查询任务：

```bash
curl http://localhost:5001/api/ingestion/tasks/你的_task_id
```

失败任务重试：

```bash
curl -X POST http://localhost:5001/api/ingestion/tasks/你的_task_id/retry
```


## 8. 测试 memory recall

先插入一条测试记忆：

```bash
curl -X POST http://localhost:5001/api/memory/items \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"manual\",\"source_type\":\"test\",\"title\":\"方案 X 讨论\",\"clean_text\":\"方案 X 后续可能继续发酵，相关组织态度会影响结果。\",\"summary\":\"方案 X 存在继续发酵可能。\",\"importance_score\":0.8,\"memory_type\":\"event\"}"
```

假设返回的 `id` 是 `1`，写入 Chroma：

```bash
curl -X POST http://localhost:5001/api/memory/embed/1
```

召回：

```bash
curl -X POST http://localhost:5001/api/memory/recall \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"方案 X 后续会怎么发展？\",\"top_k\":5}"
```


## 9. 测试 graph retrieve

把某条 MySQL 记忆写入增强版 Zep 图谱：

```bash
curl -X POST http://localhost:5001/api/graph-memory/write/1
```

查询图谱关系：

```bash
curl -X POST http://localhost:5001/api/graph-memory/retrieve \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"方案 X 后续会怎么发展？\"}"
```

如果没有配置 Zep，接口会返回清晰错误，不代表 Flask 服务失败。


## 10. 测试 review

拆分 claim：

```bash
curl -X POST http://localhost:5001/api/review/claims \
  -H "Content-Type: application/json" \
  -d "{\"report_text\":\"方案 X 可能继续发酵。相关组织的态度会影响后续走势。\"}"
```

评审单条 claim：

```bash
curl -X POST http://localhost:5001/api/review/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"claim\":\"方案 X 后续可能继续发酵\",\"persist\":false}"
```

评审整篇报告：

```bash
curl -X POST http://localhost:5001/api/review/report \
  -H "Content-Type: application/json" \
  -d "{\"report_text\":\"方案 X 可能继续发酵。相关组织的态度会影响后续走势。\",\"persist\":false}"
```


## 11. 测试 traceable report

生成可追溯预测报告：

```bash
curl -X POST http://localhost:5001/api/report/traceable \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"分析方案 X 后续可能怎么发展\",\"project_id\":\"demo_project\",\"use_active_search\":true,\"use_review\":true}"
```

重点看返回中的字段：

```json
{
  "report": "...",
  "evidence_trace": [],
  "memory_used": [],
  "graph_relations_used": [],
  "agent_interviews": [],
  "review_result": {}
}
```

`evidence_trace` 是证据链。每条证据都会标注来源类型、来源、url、发布时间、关联 claim 和用于报告的哪个部分。


## 12. 原有 docker 镜像启动方式

旧的 `mirofish` 服务仍然保留，但放到了 `legacy` profile 中。

启动旧镜像：

```bash
docker compose --profile legacy up -d mirofish
```

这条路径适合只想使用原项目镜像的情况。增强版开发推荐使用：

```bash
docker compose up -d --build backend-app celery-worker scheduler
```
