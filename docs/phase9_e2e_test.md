# phase 9 e2e enhanced demo

## goal

阶段 9 提供一个端到端验证脚本，用最小闭环验证增强版链路：

外部信息
-> 主动采集
-> 清洗去重摘要
-> MySQL 长期记忆
-> Chroma 语义召回
-> Zep 图谱关系
-> 多 Agent 可信评审
-> ReAct ReportAgent 可追溯报告

脚本路径：

```text
backend/scripts/e2e_enhanced_demo.py
```

## required configuration

运行真实验证前，请先完成 `.env` 配置：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_NAME`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `EMBEDDING_MODEL`
- `ZEP_API_KEY`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `CHROMA_USE_HTTP`
- `CHROMA_HOST`
- `CHROMA_PORT`
- `ACTIVE_SEARCH_PROVIDER`

同时保持以下开关为 `false`：

主动采集依赖真实搜索 provider。当前项目保留了 provider 扩展点，接入位置在：

```text
backend/app/services/active_search_service.py
```

## run with local services

先确认 MySQL 可连接，并确认 Chroma 使用本地持久化模式：

```env
CHROMA_USE_HTTP=false
CHROMA_PERSIST_DIR=./backend/uploads/chroma
```

执行：

```bash
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict
```

可以自定义关键词、问题和评审 claim：

```bash
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict \
  --keyword "方案 X" \
  --question "方案 X 后续可能怎么发展？" \
  --claim "方案 X 后续可能继续发酵"
```

Windows PowerShell 可以写成一行：

```powershell
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict --keyword "方案 X" --question "方案 X 后续可能怎么发展？" --claim "方案 X 后续可能继续发酵"
```

## run with docker services

如果已经用 Docker Compose 启动基础设施：

```bash
docker compose up -d mysql rabbitmq chroma
```

请把 `.env` 中的 Chroma 改为 http 模式，或使用脚本参数临时覆盖：

```bash
cd backend
uv run python scripts/e2e_enhanced_demo.py --strict --use-http-chroma
```

## expected output

成功跑通后，最后会看到类似结果：

```text
demo summary
task_id: e2e_xxx
raw_docs: 3
clean_docs: 3
unique_docs: 3
memory_items: 3
chroma_written: 3
zep_written: 3
recall_results: 3
graph_results: 1
review_confidence: 0.72
report_chars: 1200
evidence_trace_count: 7
```

如果某个关键依赖不可用，`--strict` 会让脚本直接失败并打印错误原因。这样可以确保演示结果来自真实配置，而不是本地替代数据。
