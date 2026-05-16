# phase 5: enhanced zep graphrag memory

本阶段增强原项目已有的 Zep 能力。

原项目已经具备：

- 通过 `GraphBuilderService` 创建 Zep standalone graph。
- 通过 `ZepToolsService` 做图谱检索。
- 通过 `ZepGraphMemoryUpdater` 把 simulation 中的 agent 行为追加到 Zep。
- ReportAgent 已经可以调用 Zep 检索工具。

所以阶段 5 不是从零接入 Zep，而是在已有 Zep 调用基础上，新增一套面向长期记忆和主动采集的实体关系写入策略。


## 1. 修改范围

新增文件：

- `backend/app/services/zep_schema_service.py`
- `backend/app/services/zep_memory_writer.py`
- `backend/app/services/graph_retriever.py`
- `backend/app/api/graph_memory.py`
- `docs/phase5_zep_graphrag.md`

修改文件：

- `backend/app/config.py`
- `.env.example`
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/tasks/ingestion_tasks.py`


## 2. zep 和 chroma 的区别

### chroma

Chroma 保存文本向量。

它适合回答：

```text
哪些历史记忆和这个问题语义相似？
```

例如用户问：

```text
方案 x 后续会怎么发展？
```

Chroma 会找出和这句话语义相近的 memory_item。


### zep graphrag

Zep 保存实体、关系和事实。

它适合回答：

```text
谁支持谁？
谁反对谁？
哪个事件影响了哪个观点？
这个观点基于什么证据？
某组织的立场有没有变化？
```

也就是说：

```text
chroma = 相似文本召回
zep = 实体关系记忆
```

两者配合后，Agent 不只是拿到相似材料，还能看到人物、组织、事件、观点、证据之间的关系。


## 3. 增强图谱配置

新增配置：

```env
ZEP_ENHANCED_GRAPH_ID=mirofish_enhanced_memory
```

说明：

- 原项目每个用户项目仍然可以创建自己的 Zep graph。
- 阶段 5 的主动采集记忆默认写入 `ZEP_ENHANCED_GRAPH_ID`。
- API 也支持传入 `graph_id` 覆盖默认目标图谱。


## 4. 图谱实体设计

文件：

```text
backend/app/services/zep_schema_service.py
```

实体类型：

| 类型 | 含义 |
| --- | --- |
| person | 人物、专家、公众人物、agent |
| organization | 公司、机构、政府部门、媒体、组织 |
| event | 事件、政策动作、市场变化、冲突 |
| opinion | 观点、判断、预测、解释 |
| evidence | 证据片段、引用、来源文本 |
| stance | 立场，支持、反对、中立或变化 |


## 5. 图谱关系设计

关系类型：

| 关系 | 含义 |
| --- | --- |
| supports | 支持 |
| opposes | 反对 |
| publishes | 发布 |
| mentions | 提及 |
| causes | 导致 |
| influences | 影响 |
| based_on | 基于证据 |
| expresses | 表达观点或立场 |
| responds_to | 回应某事件或观点 |
| changes_stance | 改变立场 |

这些关系会尽量保留 metadata：

```text
source_url
publish_time
mysql_id
evidence_text
```

由于当前 Zep `graph.add` 接口没有独立 metadata 参数，本阶段把 metadata 放进 JSON / text episode 内容里，让 Zep 抽取事实时能保留来源线索。


## 6. 写入图谱

文件：

```text
backend/app/services/zep_memory_writer.py
```

核心函数：

```python
write_graph_memory(memory_item)
```

输入结构来自阶段 4 的 `summary_service`：

```json
{
  "summary": "...",
  "entities": [],
  "events": [],
  "opinions": [],
  "evidence": [],
  "uncertainty": "...",
  "source_url": "...",
  "publish_time": "...",
  "mysql_id": 1
}
```

写入流程：

1. 确认 `ZEP_API_KEY` 和 `ZEP_ENHANCED_GRAPH_ID`。
2. 尝试创建增强图谱。
3. 尝试应用增强 schema。
4. 组装结构化 episode。
5. 优先用 `type=json` 写入 Zep。
6. 如果 JSON 写入失败，fallback 为 `type=text`。


## 7. 查询图谱

文件：

```text
backend/app/services/graph_retriever.py
```

核心函数：

```python
graph_retrieve(question)
```

查询流程：

1. 从问题中抽取轻量关键实体。
2. 调用原有 `ZepToolsService.search_graph()`。
3. 查询相关 edges。
4. 把 Zep 结果整理成结构化 graph_context。

返回格式：

```json
[
  {
    "source": "组织A",
    "relation": "supports",
    "target": "方案X",
    "evidence": "...",
    "source_url": "...",
    "publish_time": "...",
    "mysql_id": "1"
  }
]
```


## 8. 新增 api

### post /api/graph-memory/write/<memory_id>

把某条 MySQL memory_item 写入 Zep。

示例：

```powershell
curl -X POST http://localhost:5001/api/graph-memory/write/1
```

可选传入 graph_id：

```powershell
curl -X POST http://localhost:5001/api/graph-memory/write/1 `
  -H "Content-Type: application/json" `
  -d "{\"graph_id\":\"mirofish_enhanced_memory\"}"
```


### post /api/graph-memory/retrieve

查询增强图谱关系。

示例：

```powershell
curl -X POST http://localhost:5001/api/graph-memory/retrieve `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"方案 X 后续会怎么发展？\"}"
```


## 9. ingestion 轻量接入

文件：

```text
backend/app/tasks/ingestion_tasks.py
```

阶段 4 的主动采集任务现在会在：

```text
summarize_document
-> save_to_mysql
-> save_to_chroma
```

之后尝试：

```text
write_graph_memory
```

要求：

- 如果 Zep 未配置，不影响任务成功。
- 如果 Zep 写入失败，只记录 warning。
- MySQL 和 Chroma 仍然是采集链路的主落点。


## 10. 如何用于 agent 上下文一致性

增强图谱能让 Agent 在推演时拿到更稳定的关系上下文。

例如：

```text
组织 A expresses 观点 B
观点 B based_on 证据 C
事件 D influences 观点 B
组织 A changes_stance 立场 E
```

这样 Agent 不只是看到一段摘要，而是能知道：

- 谁说的
- 说了什么
- 支持还是反对
- 基于什么证据
- 和哪个事件有关
- 来源在哪里
- 发布时间是什么

这能降低上下文漂移，也能减少 ReportAgent 生成报告时的不可追溯判断。


## 11. 当前已完成和预留

已完成：

- 增强 schema 定义。
- Zep 写入服务。
- 图谱检索服务。
- graph-memory API。
- ingestion best-effort 写入 Zep。

预留：

- 暂未改 ReportAgent 工具列表。
- 暂未做前端图谱关系展示。
- 暂未做更强的实体抽取模型。
- 暂未做 stance change 的时间序列专门判断。
- 暂未做 Zep 写入批处理。
