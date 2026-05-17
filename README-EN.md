<div align="center">

# MiroFish-Pro Enhanced Multi-Agent World Simulation System

An engineering-enhanced project based on the MiroFish open-source multi-agent simulation framework, targeting active information collection, long-term memory, graph relationship memory, multi-agent credibility review, and traceable report generation.

[English](./README-EN.md) | [中文文档](./README-ZH.md)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-RabbitMQ-37814A?style=flat-square)
![Chroma](https://img.shields.io/badge/VectorDB-Chroma-5B5BD6?style=flat-square)
![Zep](https://img.shields.io/badge/GraphRAG-Zep-6B46C1?style=flat-square)

</div>

## Project Overview

MiroFish-Pro is an "Enhanced Multi-Agent World Simulation System." The project extends the original MiroFish pipeline — upload materials, generate ontology, write to Zep, generate OASIS agent profiles, launch camel-oasis simulation, and generate reports — with real, production-grade engineering capabilities:

- Build an active information collection task pipeline through APScheduler, Celery, and RabbitMQ.
- Use MySQL to persist collection tasks, long-term memory, evidence, and credibility review results.
- Use Chroma to store text embeddings, enabling semantic recall of historical information and dynamic context injection.
- Use Zep GraphRAG to maintain entity-relationship memory for people, organizations, events, opinions, evidence, and stances.
- Use multi-role agents to independently review report claims, outputting confidence scores and risk levels.
- Enhance the ReportAgent to call search, memory recall, graph retrieval, agent interview, and credibility review tools, generating traceable prediction reports.

This repository focuses on AI Agent backend engineering practice, not simple demo wrapping. The emphasis is on extending "simulation inference" from one-time generation into a complete pipeline that supports collection, persistence, recall, review, and traceability.

## Core Capabilities

| Capability | Description |
|-----------|-------------|
| Active Information Collection | Trigger keyword collection tasks on a schedule, execute search, cleaning, deduplication, summarization, and database writes asynchronously via Celery. |
| Long-Term Memory | MySQL stores original text, cleaned text, summaries, evidence, importance scores, and credibility scores as structured data. |
| Semantic Recall | Chroma stores embeddings and recalls historical memory through composite ranking of semantic similarity, importance, and time decay. |
| Graph Relationship Memory | Zep GraphRAG stores entities and relationships to enhance contextual consistency during agent inference. |
| Multi-Agent Credibility Review | Roles such as fact checker, supporter, opponent, and risk reviewer independently review claims to reduce pseudo-consensus and hallucination risks. |
| Traceable Report | ReportAgent aggregates memory, graph, search, simulation, and review results and outputs an evidence trace. |

## Technology Stack

| Module | Technology |
|--------|-----------|
| Backend API | Flask |
| LLM Integration | OpenAI-Compatible LLM |
| Graph Memory | Zep GraphRAG |
| Vector Memory | Chroma |
| Structured Storage | MySQL, SQLAlchemy, PyMySQL |
| Async Tasks | RabbitMQ, Celery |
| Scheduled Dispatch | APScheduler |
| Multi-Agent Simulation | camel-ai, camel-oasis |
| Container Orchestration | Docker Compose |
| Frontend | Vue / Vite |

## System Pipeline

```text
User uploads materials or triggers active collection
-> Text cleaning, deduplication, summarization
-> Write to MySQL long-term memory
-> Write to Chroma vector memory
-> Write to Zep GraphRAG entity-relationship memory
-> Read entities from Zep and generate OASIS agent profiles
-> Launch camel-oasis social simulation
-> Record agent posts, comments, likes, interviews, etc.
-> ReportAgent calls memory / graph / search / interview / review tools
-> Output traceable prediction report with evidence trace
```

## Enhancements Over the Original Project

| Original Pipeline | After Enhancement |
|------------------|-------------------|
| Primarily relies on user-uploaded materials | Added active information collection and scheduled task pipeline |
| Graph memory is mostly one-time write | Added long-term graph relationship memory and on-demand query |
| Lacks structured long-term memory layer | Added MySQL memory table, evidence table, task table, review table |
| Lacks semantic recall capability | Added Chroma vector storage and composite ranking recall |
| Report generation lacks credibility review | Added multi-role, multi-evidence-slice credibility review mechanism |
| Report evidence is not easily traceable | Added evidence trace with source, time, URL, and claim annotations |

## Quick Start

This project supports two ways to run:

- **Local source code run**: Suitable for development, debugging, and step-by-step understanding of the frontend, backend, and enhanced modules.
- **Docker Compose run**: Suitable for quickly starting MySQL, RabbitMQ, Chroma, Flask, Celery Worker, and Scheduler.

> Note: Do not commit `.env` files containing real secrets to GitHub. The repository should only include `.env.example`.

### Option 1: Local Source Code Run

#### Prerequisites

| Tool | Version Requirement | Description | Install Check |
|------|-------------------|-------------|---------------|
| **Node.js** | 18+ | Frontend runtime, includes npm | `node -v` |
| **Python** | >=3.11, <=3.12 | Backend runtime | `python --version` |
| **uv** | Latest | Python package manager | `uv --version` |
| **MySQL** | 8.0 recommended | Long-term memory, collection tasks, review results persistence | `mysql --version` |
| **RabbitMQ** | 3.x recommended | Celery async task broker, optional | `rabbitmqctl status` |

When running locally, Chroma uses a local persistent directory by default and does not require a separate Chroma Server.

#### 1. Configure Environment Variables

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

At minimum, fill in:

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

The enhanced version requires complete real configurations. Ensure LLM, Embedding, MySQL, Zep, and Chroma are all configured and available. Active collection defaults to `ACTIVE_SEARCH_PROVIDER=rss`, which pulls external information through real RSS/news search sources; if your network cannot access the default RSS feeds, replace `ACTIVE_SEARCH_RSS_URLS`.

#### 2. Prepare MySQL

If using the default configuration, create the database and user in MySQL:

```sql
CREATE DATABASE IF NOT EXISTS mirofish CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'mirofish'@'localhost' IDENTIFIED BY 'mirofish_password';
GRANT ALL PRIVILEGES ON mirofish.* TO 'mirofish'@'localhost';
FLUSH PRIVILEGES;
```

Enhanced table structures are automatically created by SQLAlchemy ORM, with the entry point at `backend/app/db.py`'s `create_all_tables()`.

#### 3. Install Dependencies

```bash
npm run setup:all
```

Or install step by step:

```bash
npm run setup
npm run setup:backend
```

#### 4. Start Local Services

Start frontend and backend:

```bash
npm run dev
```

Start individually:

```bash
npm run backend
npm run frontend
```

If you need the async collection pipeline, open another terminal and start:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker -l info
uv run python -m app.tasks.scheduler
```

Service addresses:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`
- Health check: `http://localhost:5001/health`

#### 5. Local End-to-End Verification

```bash
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict
```

This script uses real MySQL, real Embedding, real LLM, real Chroma, and real Zep configuration; it will fail directly if any critical dependency is unavailable, preventing demo results from relying on mock data.

### Option 2: Docker Compose Run

#### Prerequisites

| Tool | Version Requirement | Description |
|------|-------------------|-------------|
| **Docker Desktop** | Latest stable | Provides Docker Engine |
| **Docker Compose** | v2 recommended | Multi-service orchestration |

#### 1. Configure Environment Variables

```bash
cp .env.example .env
```

Key variables to fill in:

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

Docker Compose automatically points `MYSQL_HOST`, `RABBITMQ_HOST`, and `CHROMA_HOST` to the corresponding service names inside the containers, so you can keep the local default values in `.env`.

#### 2. Start Basic Dependencies Only

```bash
docker compose up -d mysql rabbitmq chroma
docker compose ps
```

RabbitMQ management page:

```text
http://localhost:15672
```

#### 3. Start Full Enhanced Services

```bash
docker compose up -d --build backend-app celery-worker scheduler
```

Or start all default enhanced services:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f backend-app
docker compose logs -f celery-worker
docker compose logs -f scheduler
```

#### 4. Docker Verification Commands

```bash
curl http://localhost:5001/health

curl -X POST http://localhost:5001/api/ingestion/tasks \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"Solution X\"}"

curl -X POST http://localhost:5001/api/review/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"claim\":\"Solution X may continue to escalate\",\"persist\":false}"

curl -X POST http://localhost:5001/api/report/traceable \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Analyze how Solution X might develop going forward\",\"use_active_search\":true,\"use_review\":true}"
```

#### 5. Upstream Compatibility Mode

To start only upstream-compatible services:

```bash
docker compose --profile legacy up -d mirofish
```

### Additional Documentation

For more detailed enhanced version documentation, see:

- `docs/run_enhanced_version.md`
- `docs/phase9_e2e_test.md`

## Open Source Notice

This repository is an enhanced engineering practice based on the MiroFish open-source project, focusing on demonstrating engineering transformations of multi-agent simulation systems in active collection, long-term memory, GraphRAG, credible review, and traceable reporting.

The original project and its related trademarks, materials, and demo content belong to the original authors. This repository retains code and startup methods compatible with the original main pipeline, and adds enhanced modules on top of it. If used for formal release, please retain the necessary copyright and license statements according to the upstream project's license requirements.

## Acknowledgements

- Thanks to the MiroFish open-source project for providing the multi-agent simulation foundation framework.
- Thanks to CAMEL-AI and OASIS for providing multi-agent social simulation capabilities.
- Thanks to Zep, Chroma, Celery, Flask, SQLAlchemy, and other open-source ecosystems for providing foundational capabilities.
