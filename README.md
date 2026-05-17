<div align="center">

# MiroFish-Pro 多智能体世界推演系统增强版

基于 MiroFish 开源多智能体仿真框架的工程化增强项目，面向主动信息采集、长期记忆、图谱关系记忆、多 Agent 可信评审和可追溯报告生成。

[English](./README-EN.md) | [中文文档](./README-ZH.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-RabbitMQ-37814A?style=flat-square)
![Chroma](https://img.shields.io/badge/VectorDB-Chroma-5B5BD6?style=flat-square)
![Zep](https://img.shields.io/badge/GraphRAG-Zep-6B46C1?style=flat-square)

</div>

## 项目概述

MiroFish-Pro 是一个"多智能体世界推演系统增强版"。项目在原 MiroFish 的上传资料、生成 ontology、写入 Zep、生成 OASIS agent profile、启动 camel-oasis 仿真、生成报告这条主链路上，扩展了真实可运行的工程化能力：

- 通过 APScheduler、Celery 和 RabbitMQ 构建主动信息采集任务链路。
- 使用 MySQL 保存采集任务、长期记忆、证据和可信评审结果。
- 使用 Chroma 保存文本向量，支持历史信息语义召回和动态上下文注入。
- 使用 Zep GraphRAG 维护人物、组织、事件、观点、证据和立场的实体关系记忆。
- 使用多角色 Agent 对报告 claim 进行独立评审，输出置信度和风险等级。
- 增强 ReportAgent，使其可以调用搜索、记忆召回、图谱检索、Agent 采访和可信评审工具，生成可追溯预测报告。

这个仓库更偏向 AI Agent 后端工程实践，不是简单的 demo 包装。重点在于把"仿真推演"从一次性生成，扩展为可采集、可沉淀、可召回、可评审、可追溯的完整链路。

## 核心能力

| 能力 | 说明 |
|------|------|
| 主动信息采集 | 定时触发关键词采集任务，经 Celery 异步执行搜索、清洗、去重、摘要和入库。 |
| 长期记忆 | MySQL 保存原文、清洗文本、摘要、证据、重要性评分、可信度评分等结构化数据。 |
| 语义召回 | Chroma 存储 embedding，按语义相似度、重要性、时间衰减综合排序召回历史记忆。 |
| 图谱关系记忆 | Zep GraphRAG 存储实体和关系，用于增强 Agent 推演过程中的上下文一致性。 |
| 多 Agent 可信评审 | fact checker、supporter、opponent、risk reviewer 等角色独立评审 claim，降低伪共识和幻觉风险。 |
| 可追溯报告 | ReportAgent 汇总 memory、graph、search、simulation、review 结果，并输出 evidence trace。 |

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端 API | Flask |
| LLM 接入 | OpenAI-Compatible LLM |
| 图谱记忆 | Zep GraphRAG |
| 向量记忆 | Chroma |
| 结构化存储 | MySQL、SQLAlchemy、PyMySQL |
| 异步任务 | RabbitMQ、Celery |
| 定时调度 | APScheduler |
| 多智能体仿真 | camel-ai、camel-oasis |
| 容器编排 | Docker Compose |
| 前端 | Vue / Vite |

## 系统链路

```text
用户上传资料或触发主动采集
-> 文本清洗、去重、摘要压缩
-> 写入 MySQL 长期记忆
-> 写入 Chroma 向量记忆
-> 写入 Zep GraphRAG 实体关系记忆
-> 从 Zep 读取实体并生成 OASIS agent profile
-> 启动 camel-oasis 社交仿真
-> 记录 agent 发帖、评论、点赞、采访等行为
-> ReportAgent 调用 memory / graph / search / interview / review 工具
-> 输出带 evidence trace 的可追溯预测报告
```

## 和原项目相比的增强点

| 原始链路 | 增强后 |
|----------|--------|
| 主要依赖用户上传资料 | 增加主动信息采集和定时任务链路 |
| 图谱记忆偏一次性写入 | 增加长期图谱关系记忆和按需查询 |
| 缺少结构化长期记忆层 | 增加 MySQL 记忆表、证据表、任务表、评审表 |
| 缺少语义召回能力 | 增加 Chroma 向量存储和综合排序召回 |
| 报告生成缺少可信评审 | 增加多角色、多证据切片的可信评审机制 |
| 报告依据不够可追溯 | 增加 evidence trace，标注来源、时间、url 和关联 claim |

## 快速开始

本项目支持两种运行方式：

- **本机源码运行**：适合开发、调试、逐步理解前后端和增强模块。
- **Docker Compose 运行**：适合快速启动 MySQL、RabbitMQ、Chroma、Flask、Celery Worker 和 Scheduler。

> 注意：不要把包含真实密钥的 `.env` 提交到 GitHub。仓库只应提交 `.env.example`。

### 一、本机源码运行

#### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|---------|------|---------|
| **Node.js** | 18+ | 前端运行环境，包含 npm | `node -v` |
| **Python** | >=3.11, <=3.12 | 后端运行环境 | `python --version` |
| **uv** | 最新版 | Python 包管理器 | `uv --version` |
| **MySQL** | 8.0 推荐 | 长期记忆、采集任务、评审结果持久化 | `mysql --version` |
| **RabbitMQ** | 3.x 推荐 | Celery 异步任务 broker，可选 | `rabbitmqctl status` |

本机运行时，Chroma 默认使用本地持久化目录，不强制单独启动 Chroma Server。

#### 1. 配置环境变量

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

至少填写：

```env
LLM_API_KEY=your_chat_model_key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL_NAME=your_chat_model

OPENAI_API_KEY=your_chat_model_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
OPENAI_MODEL=your_chat_model

EMBEDDING_MODEL=your_embedding_model

ZEP_API_KEY=your_zep_api_key
ZEP_ENHANCED_GRAPH_ID=mirofish_enhanced_memory

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=mirofish
MYSQL_PASSWORD=mirofish_password
MYSQL_DATABASE=mirofish

CHROMA_USE_HTTP=false
CHROMA_PERSIST_DIR=./backend/uploads/chroma
```

增强版启动要求使用完整真实配置。请确保 LLM、Embedding、MySQL、Zep、Chroma 均已配置可用。主动采集默认支持 `ACTIVE_SEARCH_PROVIDER=rss`，会通过真实 RSS / 新闻搜索源拉取外部信息；如果你的网络无法访问默认 RSS，可以替换 `ACTIVE_SEARCH_RSS_URLS`。

#### 2. 准备 MySQL

如果使用默认配置，可以在 MySQL 中创建数据库和用户：

```sql
CREATE DATABASE IF NOT EXISTS mirofish CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'mirofish'@'localhost' IDENTIFIED BY 'mirofish_password';
GRANT ALL PRIVILEGES ON mirofish.* TO 'mirofish'@'localhost';
FLUSH PRIVILEGES;
```

增强版表结构由 SQLAlchemy ORM 自动创建，入口在 `backend/app/db.py` 的 `create_all_tables()`。

#### 3. 安装依赖

```bash
npm run setup:all
```

或者分步安装：

```bash
npm run setup
npm run setup:backend
```

#### 4. 启动本机服务

启动前后端：

```bash
npm run dev
```

单独启动：

```bash
npm run backend
npm run frontend
```

如果需要异步采集链路，另开终端启动：

```bash
cd backend
uv run celery -A app.tasks.celery_app worker -l info
uv run python -m app.tasks.scheduler
```

服务地址：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`
- 健康检查：`http://localhost:5001/health`

#### 5. 本机端到端验证

```bash
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict
```

该脚本会使用真实 MySQL、真实 Embedding、真实 LLM、真实 Chroma 和真实 Zep 配置；任一关键依赖不可用时会直接失败，避免演示结果来自模拟数据。

### 二、Docker Compose 运行

#### 前置要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| **Docker Desktop** | 最新稳定版 | 提供 Docker Engine |
| **Docker Compose** | v2 推荐 | 启动多服务编排 |

#### 1. 配置环境变量

```bash
cp .env.example .env
```

需要重点填写：

```env
LLM_API_KEY=your_chat_model_key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL_NAME=your_chat_model

OPENAI_API_KEY=your_chat_model_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
OPENAI_MODEL=your_chat_model
EMBEDDING_MODEL=your_embedding_model

ZEP_API_KEY=your_zep_api_key

MYSQL_USER=mirofish
MYSQL_PASSWORD=mirofish_password
MYSQL_DATABASE=mirofish
MYSQL_ROOT_PASSWORD=mirofish_root_password

RABBITMQ_USER=mirofish
RABBITMQ_PASSWORD=mirofish_password
RABBITMQ_VHOST=/
```

Docker Compose 会在容器内部自动把 `MYSQL_HOST`、`RABBITMQ_HOST`、`CHROMA_HOST` 指向对应服务名，因此 `.env` 中可以保留本机默认值。

#### 2. 只启动基础依赖

```bash
docker compose up -d mysql rabbitmq chroma
docker compose ps
```

RabbitMQ 管理页面：

```text
http://localhost:15672
```

#### 3. 启动完整增强版服务

```bash
docker compose up -d --build backend-app celery-worker scheduler
```

或启动所有默认增强服务：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f backend-app
docker compose logs -f celery-worker
docker compose logs -f scheduler
```

#### 4. Docker 验证命令

```bash
curl http://localhost:5001/health

curl -X POST http://localhost:5001/api/ingestion/tasks \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"方案 X\"}"

curl -X POST http://localhost:5001/api/review/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"claim\":\"方案 X 后续可能继续发酵\",\"persist\":false}"

curl -X POST http://localhost:5001/api/report/traceable \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"分析方案 X 后续可能怎么发展\",\"use_active_search\":true,\"use_review\":true}"
```

#### 5. 上游兼容模式启动

如果只想启动上游兼容服务：

```bash
docker compose --profile legacy up -d mirofish
```

### 三、增强版文档

更详细的增强版说明见：

- `docs/run_enhanced_version.md`
- `docs/phase9_e2e_test.md`

## 开源说明

本仓库是基于 MiroFish 开源项目进行二次开发的增强版工程实践，重点展示多 Agent 仿真系统在主动采集、长期记忆、GraphRAG、可信评审和可追溯报告方面的工程化改造。

原项目及相关商标、素材、演示内容归原作者所有。本仓库保留兼容原始主流程的代码和启动方式，并在此基础上新增增强模块。若用于正式发布，请根据上游项目许可证要求保留必要的版权和许可声明。

## 致谢

- 感谢 MiroFish 开源项目提供的多智能体推演基础框架。
- 感谢 CAMEL-AI 和 OASIS 提供多智能体社交仿真能力。
- 感谢 Zep、Chroma、Celery、Flask、SQLAlchemy 等开源生态提供基础能力。
