# phase 3: chroma semantic memory recall

本阶段在 phase 2 的 MySQL 长期记忆基础上，接入 Chroma 做语义向量召回。

当前仍然不改 ReportAgent，不改 graph、simulation、report 原主流程。


## 1. 修改范围

新增文件：

- `backend/app/services/embedding_service.py`
- `backend/app/services/memory_store.py`
- `backend/app/services/memory_retriever.py`
- `backend/app/services/context_injector.py`
- `backend/scripts/test_memory_chroma.py`
- `docs/phase3_chroma_memory.md`

修改文件：

- `backend/app/config.py`
- `.env.example`
- `backend/app/repositories/memory_repository.py`
- `backend/app/api/memory.py`


## 2. MySQL 和 Chroma 如何配合

MySQL 保存完整长期记忆。

它负责保存：

- 原始文本 `raw_text`
- 清洗文本 `clean_text`
- 摘要 `summary`
- 来源 `source`
- 链接 `url`
- 发布时间 `publish_time`
- 重要性评分 `importance_score`
- 可信度评分 `credibility_score`
- 是否已写入 Chroma `is_embedded`
- 是否已写入 Zep `is_written_to_zep`

Chroma 保存用于相似度搜索的向量。

它负责保存：

- 文本向量 embedding
- 用于快速展示和回查的 metadata
- 对应 MySQL 主键 `mysql_id`

也就是说：

```text
mysql = 完整记忆正文和结构化字段
chroma = 语义检索索引
```

召回时不是只相信 Chroma 返回的片段，而是先用 Chroma 找候选，再根据 `mysql_id` 回 MySQL 查完整 `memory_item`。


## 3. embedding_service

文件：

```text
backend/app/services/embedding_service.py
```

作用：

把文本转换成向量。

真实 embedding 模式：

- 使用 OpenAI-Compatible embeddings api。
- 读取 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`EMBEDDING_MODEL`。
- 适合真实语义召回。

增强版当前只保留真实 embedding 路径。`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`EMBEDDING_MODEL` 缺失时会直接报错，避免语义召回结果来自替代向量。


## 4. memory_store

文件：

```text
backend/app/services/memory_store.py
```

核心函数：

```python
save_memory_to_chroma(memory_item)
```

写入逻辑：

1. 从 MySQL 的 `memory_item` 中优先取 `summary`。
2. 如果没有 `summary`，再取 `clean_text`。
3. 调用 `EmbeddingService` 生成 embedding。
4. 写入 Chroma collection。
5. metadata 中写入：

```text
mysql_id
source
url
publish_time
importance_score
memory_type
```

写入成功后，会把 MySQL 中的 `is_embedded` 更新为 `true`。


## 5. memory_retriever

文件：

```text
backend/app/services/memory_retriever.py
```

核心函数：

```python
recall_memory(question, top_k=5)
```

召回逻辑：

1. 把用户问题转成 embedding。
2. 从 Chroma 召回 top 20 候选。
3. 从候选 metadata 里取 `mysql_id`。
4. 回 MySQL 查询完整 `memory_item`。
5. 计算综合分数。
6. 按综合分数排序后返回 top_k。


## 6. 综合排序分数

默认公式：

```text
final_score =
semantic_score * 0.5
+ importance_score * 0.3
+ time_decay_score * 0.2
```

配置项：

```env
MEMORY_RECALL_SEMANTIC_WEIGHT=0.5
MEMORY_RECALL_IMPORTANCE_WEIGHT=0.3
MEMORY_RECALL_TIME_DECAY_WEIGHT=0.2
MEMORY_RECALL_CANDIDATES=20
MEMORY_TIME_DECAY_HALF_LIFE_DAYS=30
```


## 7. semantic_score

`semantic_score` 来自 Chroma 的向量距离。

当前 Chroma collection 使用 cosine space。

转换方式：

```text
semantic_score = 1 - chroma_distance
```

然后限制在 `0 到 1` 之间。

含义：

- 越接近 1，问题和记忆越相似。
- 越接近 0，问题和记忆越不相关。


## 8. importance_score

`importance_score` 来自 MySQL 的 `memory_item.importance_score`。

它表示这条记忆本身的重要程度。

例如：

- 普通闲聊新闻：`0.2`
- 明确事件节点：`0.6`
- 对推演影响很大的核心事实：`0.9`

召回时，即使两条内容语义相似，也会优先考虑更重要的记忆。


## 9. time_decay_score

`time_decay_score` 用来让更新的记忆更容易被召回。

默认半衰期：

```env
MEMORY_TIME_DECAY_HALF_LIFE_DAYS=30
```

计算方式：

```text
age_days = 当前时间 - publish_time
time_decay_score = exp(-age_days / half_life_days)
```

如果没有 `publish_time`，会退回使用 `created_at`。

如果两个时间都没有，默认给 `0.5`，表示这条记忆不是完全无效，但也不当成最新信息。


## 10. context_injector

文件：

```text
backend/app/services/context_injector.py
```

核心函数：

```python
build_agent_context(question)
```

作用：

1. 调用 `recall_memory(question)`。
2. 把召回结果拼成 Agent 可读上下文。
3. 保留可追溯字段。

上下文格式类似：

```text
[memory 1]
summary: ...
source: ...
time: ...
importance_score: ...
url: ...
final_score: ...
```

后续阶段接 ReportAgent 时，可以把这段 context 放进工具调用结果或提示词上下文里。


## 11. 新增 API

### POST /api/memory/embed/<memory_id>

把某条 MySQL 记忆写入 Chroma。

示例：

```powershell
curl -X POST http://localhost:5001/api/memory/embed/1
```

成功返回：

```json
{
  "success": true,
  "result": {
    "id": "memory_item:1",
    "mysql_id": 1,
    "embedding_mode": "openai-compatible"
  }
}
```


### POST /api/memory/recall

根据问题召回历史记忆。

示例：

```powershell
curl -X POST http://localhost:5001/api/memory/recall `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"某事件未来会怎么发展？\",\"top_k\":5}"
```

返回字段包括：

- `summary`
- `source`
- `url`
- `publish_time`
- `importance_score`
- `semantic_score`
- `time_decay_score`
- `final_score`


## 12. 测试脚本

文件：

```text
backend/scripts/test_memory_chroma.py
```

运行：

```powershell
cd backend
uv run python scripts/test_memory_chroma.py
```

脚本流程：

1. 检查 MySQL。
2. 创建表。
3. 插入三条测试 `memory_item`。
4. 使用真实 embedding。
5. 写入本地 Chroma。
6. 用一个问题召回。
7. 打印排序结果。

注意：

脚本不需要真实 embedding api，也不需要 Chroma server。

但它需要 MySQL 可连接，因为完整记忆仍然保存在 MySQL。


## 13. 当前已完成和预留

已完成：

- OpenAI-Compatible embedding 封装。
- 真实 embedding 调用。
- MySQL memory_item 写入 Chroma。
- Chroma metadata 绑定 MySQL id。
- 问题语义召回。
- 基于 semantic / importance / time decay 的重排。
- Agent 上下文拼接。
- memory API 增强。
- 最小测试脚本。

预留：

- 尚未把召回结果接入 ReportAgent。
- 尚未把召回结果注入 simulation agent profile。
- 尚未做 Chroma 删除和重建索引 API。
- 尚未做批量 embedding。
- 尚未接入 Celery 异步 embedding。
