# phase 1: config and docker skeleton

本阶段只做增强版基础设施骨架，不接入原有 graph、simulation、report 主流程。

目标是让后续的长期记忆、异步任务、主动采集、语义召回可以逐步落地，同时不破坏原项目已有启动方式。


## 1. 修改范围

本阶段修改了这些文件：

- `.env.example`
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `backend/app/config.py`
- `docker-compose.yml`

本阶段新增了这个文件：

- `docs/phase1_config_and_docker.md`


## 2. 新增依赖

后端新增了增强版项目后续会用到的基础依赖：

- `SQLAlchemy`: 后续用于 MySQL 数据访问层。
- `PyMySQL`: 后续用于 Python 连接 MySQL。
- `alembic`: 后续用于数据库迁移。
- `celery`: 后续用于异步任务队列。
- `APScheduler`: 后续用于周期性任务调度。
- `chromadb`: 后续用于 Chroma 语义向量记忆。

这些依赖目前只是准备骨架，尚未接入原有业务流程。


## 3. 新增环境变量

`.env.example` 中新增了以下配置组。

### mysql

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mirofish
MYSQL_PASSWORD=mirofish_password
MYSQL_DATABASE=mirofish
MYSQL_ROOT_PASSWORD=mirofish_root_password
```

这些配置后续用于长期记忆、任务结果、结构化数据持久化。


### rabbitmq and celery

```env
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
RABBITMQ_USER=mirofish
RABBITMQ_PASSWORD=mirofish_password
RABBITMQ_VHOST=/

CELERY_BROKER_URL=amqp://mirofish:mirofish_password@localhost:5672//
CELERY_RESULT_BACKEND=db+mysql+pymysql://mirofish:mirofish_password@localhost:3306/mirofish
```

这些配置后续用于主动采集、文本清洗、摘要压缩、入库写入等异步任务。


### chroma

```env
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_PERSIST_DIR=./backend/uploads/chroma
```

这些配置后续用于语义向量记忆和历史信息召回。


### openai-compatible llm

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-3-small
```

原项目仍保留 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME`。

新增的 `OPENAI_*` 是为了让后续增强模块更明确地表达“openai-compatible llm”调用方式。


### zep

```env
ZEP_API_KEY=your_zep_api_key_here
ZEP_API_URL=
```

`ZEP_API_KEY` 是原项目已有配置。

`ZEP_API_URL` 是后续兼容自建 zep 或代理地址的预留配置。


### ingestion

```env
ACTIVE_SEARCH_PROVIDER=provider
```

后续主动采集模块必须接入真实外部搜索 api；如果 provider 尚未实现，主动采集会明确报错，避免生成替代数据。


## 4. 统一配置模块

`backend/app/config.py` 已扩展为统一配置入口。

主要原则：

- 所有配置都从环境变量读取。
- 没有配置时提供安全默认值。
- 不在代码中写死真实密钥。
- 保留原项目的 `LLM_*`、`ZEP_API_KEY`、`OASIS_*`、`REPORT_AGENT_*` 配置名。
- 新增 `OPENAI_*`、`MYSQL_*`、`RABBITMQ_*`、`CELERY_*`、`CHROMA_*`、`INGESTION_*` 配置名。

当前 `validate()` 仍只检查原主流程所需的 llm 和 zep 密钥，不强制要求 mysql、rabbitmq、chroma 必须可用。


## 5. docker compose 服务

`docker-compose.yml` 新增了三个可选基础设施服务：

- `mysql`
- `rabbitmq`
- `chroma`

原有 `mirofish` 服务仍然保留，并且没有强制依赖这三个服务。

也就是说，阶段 1 不会因为 mysql、rabbitmq、chroma 没启动就破坏原项目。


## 6. 启动基础设施

只启动增强版基础设施：

```powershell
docker compose up -d mysql rabbitmq chroma
```

启动原项目加基础设施：

```powershell
docker compose up -d
```

查看服务状态：

```powershell
docker compose ps
```


## 7. 检查 rabbitmq

rabbitmq 管理页面：

```text
http://localhost:15672
```

默认账号密码来自 `.env.example`：

```text
username: mirofish
password: mirofish_password
```

也可以用命令检查：

```powershell
curl -u mirofish:mirofish_password http://localhost:15672/api/overview
```


## 8. 检查 mysql

容器内检查：

```powershell
docker compose exec mysql mysql -u mirofish -pmirofish_password -e "select 1;" mirofish
```

如果本机安装了 mysql 客户端，也可以检查：

```powershell
mysql -h 127.0.0.1 -P 3306 -u mirofish -pmirofish_password mirofish -e "select 1;"
```


## 9. 检查 chroma

优先检查 heartbeat：

```powershell
curl http://localhost:8000/api/v1/heartbeat
```

如果使用的 chroma 镜像版本暴露 v2 api，可以改查：

```powershell
curl http://localhost:8000/api/v2/heartbeat
```


## 10. 检查后端配置是否可加载

进入后端目录：

```powershell
cd backend
```

加载配置并打印关键值：

```powershell
uv run python -c "from app.config import Config; print(Config.MYSQL_HOST, Config.CELERY_BROKER_URL, Config.CHROMA_HTTP_URL)"
```

如果能正常输出 mysql host、celery broker url、chroma url，说明阶段 1 的配置骨架已经可以被后端读取。


## 11. 当前已完成和预留

已完成：

- 增强版依赖骨架。
- 增强版 `.env.example`。
- 统一配置读取。
- docker compose 中的 mysql、rabbitmq、chroma 服务定义。
- 不强制新基础设施影响原主流程。

预留接口：

- 尚未创建 SQLAlchemy model。
- 尚未创建 Alembic migration。
- 尚未创建 Celery app 和 task。
- 尚未创建 APScheduler 周期任务。
- 尚未创建 Chroma collection。
- 尚未把主动采集、长期记忆、语义召回接入 graph / simulation / report。
