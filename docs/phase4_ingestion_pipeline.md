# phase 4: apscheduler + celery + rabbitmq ingestion pipeline

本阶段新增主动采集异步任务链路。

当前重点是链路跑通，不追求真实搜索质量，也不改原有 graph、simulation、report 主流程。


## 1. 修改范围

新增文件：

- `backend/app/tasks/__init__.py`
- `backend/app/tasks/celery_app.py`
- `backend/app/tasks/ingestion_tasks.py`
- `backend/app/tasks/scheduler.py`
- `backend/app/services/active_search_service.py`
- `backend/app/services/content_cleaner.py`
- `backend/app/services/dedup_service.py`
- `backend/app/services/summary_service.py`
- `backend/app/services/importance_scorer.py`
- `backend/app/api/ingestion.py`
- `docs/phase4_ingestion_pipeline.md`

修改文件：

- `backend/app/config.py`
- `.env.example`
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/repositories/ingestion_repository.py`


## 2. 三个核心组件分别负责什么

### apscheduler

负责定时触发。

它只做轻量动作：

1. 读取 `INGESTION_KEYWORDS`。
2. 按固定间隔触发每个关键词。
3. 创建 `ingestion_task`。
4. 把任务投递给 Celery。

它不执行搜索、清洗、摘要、入库这些耗时逻辑。


### celery

负责异步任务执行。

worker 收到任务后执行：

```text
active_search
-> clean_documents
-> dedup_documents
-> summarize_document
-> calculate_importance
-> save_to_mysql
-> save_to_chroma
-> reserved zep write
```


### rabbitmq

负责消息队列。

API 或 APScheduler 不直接调用耗时任务，而是把任务消息发到 RabbitMQ。

Celery worker 从 RabbitMQ 拉取任务并执行。

本项目阶段 4 不使用 Redis。


## 3. 新增配置

```env
CELERY_BROKER_URL=amqp://mirofish:mirofish_password@localhost:5672//
CELERY_RESULT_BACKEND=rpc://
CELERY_TASK_ALWAYS_EAGER=false
CELERY_TASK_TIME_LIMIT=600
CELERY_BROKER_CONNECTION_TIMEOUT=3

ACTIVE_SEARCH_PROVIDER=provider
INGESTION_KEYWORDS=示例事件,能源市场
INGESTION_INTERVAL_SECONDS=3600
INGESTION_CONTENT_MIN_LENGTH=20
INGESTION_DEDUP_SIMILARITY_THRESHOLD=0.88
SUMMARY_MAX_INPUT_CHARS=4000
```

说明：

- `CELERY_BROKER_URL` 指向 RabbitMQ。
- `CELERY_RESULT_BACKEND=rpc://` 是最小可行方案，避免 Celery 结果后端强依赖 MySQL。
- `ACTIVE_SEARCH_PROVIDER` 需要接入真实搜索 provider。
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 缺失时摘要服务会明确报错。


## 4. 主动采集完整流程

### 1. 创建任务

来源可以是 API，也可以是 APScheduler。

创建 MySQL 表：

```text
ingestion_task
```

初始状态：

```text
pending
```


### 2. 投递 Celery

调用：

```python
run_ingestion_task.delay(task_id, keyword)
```

任务会进入 RabbitMQ。


### 3. worker 执行

Celery worker 执行：

```text
run_ingestion_task(task_id, keyword)
```

执行开始后把任务状态改成：

```text
running
```


### 4. 真实搜索 provider

文件：

```text
backend/app/services/active_search_service.py
```

真实搜索 provider 返回结构：

```json
[
  {
    "title": "...",
    "url": "...",
    "source": "...",
    "publish_time": "...",
    "raw_text": "..."
  }
]
```

provider 模式已经预留，但阶段 4 不接真实搜索 API。


### 5. 文本清洗

文件：

```text
backend/app/services/content_cleaner.py
```

处理：

- 去 html 标签
- html entity 反转义
- 合并多余空格
- 过滤过短文本
- 写入 `clean_text`


### 6. 三层去重

文件：

```text
backend/app/services/dedup_service.py
```

去重顺序：

1. `url` 去重。
2. `content_hash` 去重。
3. `difflib.SequenceMatcher` 简单相似度去重。

相似度阈值：

```env
INGESTION_DEDUP_SIMILARITY_THRESHOLD=0.88
```


### 7. 摘要压缩

文件：

```text
backend/app/services/summary_service.py
```

输出结构：

```json
{
  "summary": "...",
  "entities": [],
  "events": [],
  "opinions": [],
  "evidence": [],
  "uncertainty": "..."
}
```

如果 LLM 没配置，摘要压缩会明确失败，需要先补全 OpenAI-Compatible LLM 配置。


### 8. 重要性评分

文件：

```text
backend/app/services/importance_scorer.py
```

规则来源：

- 来源权威性
- 是否包含实体
- 是否包含事件动作
- 是否有证据
- 来源数量

返回：

```text
0 到 1 的 importance_score
```


### 9. 写入 MySQL

写入：

```text
memory_item
memory_evidence
```

`memory_item` 保存完整文本、摘要、来源、时间、重要性评分等。

`memory_evidence` 保存摘要中抽取出的证据片段。


### 10. 写入 Chroma

调用阶段 3 的：

```text
MemoryStore.save_memory_to_chroma()
```

把 MySQL memory item 写入 Chroma，用于后续语义召回。


### 11. 预留 Zep 写入

当前任务结果里会标记：

```text
zep_write: reserved
```

阶段 4 不写 Zep，后续可以把实体、事件、观点关系写入 Zep GraphRAG。


### 12. 完成或失败

成功：

```text
finished
```

异常：

```text
failed
```

失败原因写入：

```text
error_message
```


## 5. 启动方式

先启动基础设施：

```powershell
docker compose up -d mysql rabbitmq
```

如果要使用 Chroma http 服务：

```powershell
docker compose up -d chroma
```

如果使用默认 `CHROMA_USE_HTTP=false`，则 Chroma 会使用本地持久化目录，不需要启动 Chroma 容器。


## 6. 启动 Flask API

```powershell
cd backend
python run.py
```

或：

```powershell
cd backend
uv run python run.py
```


## 7. 启动 Celery worker

Linux / macOS：

```powershell
cd backend
celery -A app.tasks.celery_app worker -l info
```

Windows 建议使用 solo pool：

```powershell
cd backend
celery -A app.tasks.celery_app worker -l info --pool=solo
```

如果使用 uv：

```powershell
uv run celery -A app.tasks.celery_app worker -l info --pool=solo
```


## 8. 启动 APScheduler

```powershell
cd backend
python -m app.tasks.scheduler
```

或：

```powershell
cd backend
uv run python -m app.tasks.scheduler
```

它会读取：

```env
INGESTION_KEYWORDS=示例事件,能源市场
INGESTION_INTERVAL_SECONDS=3600
```

然后按间隔创建任务并投递 Celery。


## 9. 手动触发任务

```powershell
curl -X POST http://localhost:5001/api/ingestion/tasks `
  -H "Content-Type: application/json" `
  -d "{\"keyword\":\"某事件\"}"
```

成功返回：

```json
{
  "success": true,
  "task": {
    "task_id": "ing_xxx",
    "status": "pending",
    "keyword": "某事件"
  },
  "celery_id": "..."
}
```


## 10. 查看任务状态

```powershell
curl http://localhost:5001/api/ingestion/tasks/ing_xxx
```


## 11. 重试失败任务

```powershell
curl -X POST http://localhost:5001/api/ingestion/tasks/ing_xxx/retry
```

只有 `failed` 状态的任务可以重试。


## 12. 本地开发建议

如果只是想不启动 RabbitMQ，直接在 API 进程里跑 Celery 任务，可以临时设置：

```env
CELERY_TASK_ALWAYS_EAGER=true
```

注意：

这不是生产模式。

生产或完整链路演示时应使用：

```text
Flask API -> RabbitMQ -> Celery worker
```


## 13. 当前已完成和预留

已完成：

- Celery app。
- RabbitMQ broker 配置。
- ingestion Celery task。
- APScheduler 定时触发。
- 真实 provider 主动搜索接口。
- 文本清洗。
- 三层去重。
- LLM 摘要压缩。
- 规则重要性评分。
- 写入 MySQL。
- 写入 Chroma。
- ingestion API。

预留：

- 真实搜索 provider 未接入。
- Zep GraphRAG 写入未接入。
- Celery 任务结果详情未落单独结果表。
- 批量任务管理页面未接入前端。
