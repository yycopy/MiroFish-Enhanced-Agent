# phase 2: mysql long-term memory

本阶段新增 MySQL 长期记忆基础结构，但不接入原有 graph、simulation、report 主流程。

目标是先把主动采集和长期记忆需要的结构化存储层搭起来，后续阶段再接 Celery、APScheduler、Chroma、Zep GraphRAG 和 ReportAgent 工具调用。


## 1. 修改范围

新增文件：

- `backend/app/db.py`
- `backend/app/models/memory.py`
- `backend/app/models/ingestion.py`
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/memory_repository.py`
- `backend/app/repositories/ingestion_repository.py`
- `backend/app/api/memory.py`
- `backend/scripts/test_memory_mysql.py`
- `docs/phase2_mysql_memory.md`

修改文件：

- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/models/__init__.py`
- `backend/app/config.py`
- `.env.example`


## 2. 新增配置

阶段 2 在 phase 1 的 MySQL 配置基础上新增：

```env
MYSQL_CONNECT_TIMEOUT=3
MYSQL_AUTO_CREATE_TABLES=false
```

说明：

- `MYSQL_CONNECT_TIMEOUT` 控制 MySQL 连接超时时间，避免 MySQL 没启动时接口卡太久。
- `MYSQL_AUTO_CREATE_TABLES=false` 表示默认不在 Flask 启动时强制建表，避免破坏原项目启动体验。
- 如果要在 Flask 启动时自动建表，可以改成 `MYSQL_AUTO_CREATE_TABLES=true`。


## 3. db 层

`backend/app/db.py` 提供统一数据库入口：

- `Base`: SQLAlchemy ORM 基类。
- `configure_database()`: 创建 SQLAlchemy engine 和 session factory。
- `init_app(app)`: Flask 启动时初始化可选 MySQL 层。
- `create_all_tables()`: 创建阶段 2 的 MySQL 表。
- `get_session()`: 获取数据库 session。
- `session_scope()`: repository 使用的事务上下文。
- `database_health()`: 检查 MySQL 是否可连接。
- `DatabaseUnavailableError`: MySQL 未配置或不可用时抛出的清晰异常。

注意：

`init_app(app)` 不会让 MySQL 变成原项目硬依赖。

如果 MySQL 未启动，原来的 `/health`、graph、simulation、report 仍然可以启动；只有 `/api/memory/*` 会返回明确的 MySQL 不可用提示。


## 4. 表结构

### ingestion_task

模型文件：

```text
backend/app/models/ingestion.py
```

用途：

记录后续主动采集、清洗、摘要、写入等异步任务。

字段：

| 字段 | 说明 |
| --- | --- |
| id | 自增主键 |
| task_id | 对外任务 id |
| keyword | 搜索关键词 |
| task_type | 任务类型 |
| status | 任务状态 |
| error_message | 失败原因 |
| created_at | 创建时间 |
| updated_at | 更新时间 |
| started_at | 开始时间 |
| finished_at | 完成时间 |

状态值：

- `pending`
- `running`
- `finished`
- `failed`


### memory_item

模型文件：

```text
backend/app/models/memory.py
```

用途：

保存主动采集或人工写入的长期记忆文本。

字段：

| 字段 | 说明 |
| --- | --- |
| id | 自增主键 |
| source | 来源名称 |
| source_type | 来源类型 |
| url | 原文地址 |
| title | 标题 |
| raw_text | 原始文本 |
| clean_text | 清洗后的文本 |
| summary | 摘要 |
| publish_time | 发布时间 |
| content_hash | 内容哈希，用于去重 |
| importance_score | 重要性评分 |
| credibility_score | 可信度评分 |
| memory_type | 记忆类型 |
| is_embedded | 是否已写入向量库 |
| is_written_to_zep | 是否已写入 Zep |
| created_at | 创建时间 |
| updated_at | 更新时间 |


### memory_evidence

模型文件：

```text
backend/app/models/memory.py
```

用途：

保存某条记忆下的观点、证据、引用片段，后续可用于可信评审和可追溯报告。

字段：

| 字段 | 说明 |
| --- | --- |
| id | 自增主键 |
| memory_id | 关联 memory_item.id |
| claim | 主张或判断 |
| evidence_text | 证据文本 |
| evidence_type | 证据类型 |
| source_url | 证据来源 |
| created_at | 创建时间 |


## 5. repository 层

阶段 2 新增两个 repository：

```text
backend/app/repositories/memory_repository.py
backend/app/repositories/ingestion_repository.py
```

设计原则：

- API 或未来 service 不直接写 SQL。
- 增删查改都通过 repository。
- repository 内部使用 `session_scope()` 统一提交、回滚和关闭 session。

当前能力：

- `MemoryRepository.create_item()`
- `MemoryRepository.list_items()`
- `MemoryRepository.get_item()`
- `MemoryRepository.delete_item()`
- `MemoryRepository.create_evidence()`
- `IngestionRepository.create_task()`
- `IngestionRepository.get_task()`
- `IngestionRepository.list_tasks()`
- `IngestionRepository.update_status()`


## 6. memory api

新增蓝图：

```text
backend/app/api/memory.py
```

注册前缀：

```text
/api/memory
```

### GET /api/memory/health

检查 MySQL 是否可用。

示例：

```powershell
curl http://localhost:5001/api/memory/health
```

MySQL 可用时返回 `200`。

MySQL 不可用时返回 `503`，但不会影响原项目其他接口。


### POST /api/memory/items

插入一条测试记忆。

示例：

```powershell
curl -X POST http://localhost:5001/api/memory/items `
  -H "Content-Type: application/json" `
  -d "{\"source\":\"manual\",\"source_type\":\"test\",\"title\":\"phase2 test\",\"raw_text\":\"before\",\"clean_text\":\"after\",\"summary\":\"test memory\",\"memory_type\":\"smoke_test\"}"
```


### GET /api/memory/items

查询记忆列表。

示例：

```powershell
curl "http://localhost:5001/api/memory/items?limit=20&offset=0"
```

支持参数：

- `limit`
- `offset`
- `memory_type`
- `source_type`


### GET /api/memory/items/<id>

查询单条记忆。

示例：

```powershell
curl http://localhost:5001/api/memory/items/1
```


## 7. 启动 mysql

如果本机有 docker，可以启动阶段 1 中定义的 MySQL：

```powershell
docker compose up -d mysql
```

检查 MySQL：

```powershell
docker compose exec mysql mysql -u mirofish -pmirofish_password -e "select 1;" mirofish
```


## 8. 运行最小测试脚本

进入后端目录：

```powershell
cd backend
```

运行：

```powershell
uv run python scripts/test_memory_mysql.py
```

脚本会做四件事：

1. 检查 MySQL 连接。
2. 创建 `ingestion_task`、`memory_item`、`memory_evidence` 表。
3. 插入一条 `memory_item`。
4. 查询并打印插入结果。

如果 MySQL 没启动，脚本会打印明确错误并退出，不会假装测试成功。


## 9. 当前已完成和预留

已完成：

- SQLAlchemy db 层。
- MySQL ORM 模型。
- ingestion task 表结构。
- memory item 表结构。
- memory evidence 表结构。
- repository 封装。
- memory API。
- 最小 MySQL 测试脚本。

预留：

- 尚未接入 Celery。
- 尚未接入 APScheduler。
- 尚未接入 Chroma。
- 尚未把 memory_item 写入 Zep。
- 尚未把长期记忆注入 simulation 或 ReportAgent。
- 尚未创建 Alembic migration，本阶段使用 `create_all_tables()` 做最小建表。
