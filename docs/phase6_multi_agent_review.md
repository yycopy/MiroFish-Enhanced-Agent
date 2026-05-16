# phase 6 multi-agent review

## goal

阶段 6 新增多 agent 可信评审机制，用来评估 ReportAgent 或 SimulationAgent 生成的初步结论。

这一阶段保持独立运行，不强行接入原有 report 主流程。原有 graph、simulation、report API 继续保持兼容。


## what is pseudo consensus

伪共识指的是多个结论看起来都在支持同一个判断，但这些结论可能来自同一批弱证据、同一种提示词偏向，或者同一个模型的重复表达。

在世界推演场景里，如果只让一个 agent 直接给结论，很容易把“可能发生”说成“很可能发生”，也容易忽略反例和证据来源。因此本阶段把报告先拆成 claim，再分别找证据和多角色评审。


## why split claims

一整段报告通常混合了事实、预测、因果判断和风险判断。直接评审整段文本会让模型跳过细节。

`claim_splitter.py` 的作用是把报告拆成多个可验证的小判断：

- 每个 claim 尽量只表达一个判断。
- 每个 claim 可以单独召回证据。
- 每个 claim 可以单独计算置信度。

如果 LLM 未配置，系统会使用简单规则按标点拆分，并过滤过短句子，保证本地开发可跑。


## evidence slicing

`evidence_slicer.py` 会围绕单个 claim 收集证据，并分成三类：

- `supporting_evidence`: 支持该 claim 的证据。
- `opposing_evidence`: 反对或削弱该 claim 的证据。
- `neutral_evidence`: 相关但立场不明确的证据。

证据来源采用 best-effort 模式：

- `memory_recall`: 从 Chroma + MySQL 长期记忆召回历史信息。
- `graph_retrieve`: 从 Zep GraphRAG 召回实体关系。
- `active_search`: 可选调用主动搜索，默认不强制开启。

如果 MySQL、Chroma、Zep 或外部搜索没有配置，证据切片不会让评审接口直接崩溃，而是返回清晰的不可用信息。


## review roles

`review_agent.py` 设计了五个相互独立的评审角色：

- `fact_checker`: 重点检查事实是否被证据支撑。
- `supporter`: 只从支持角度寻找 claim 成立的理由。
- `opponent`: 主动寻找反证和削弱理由。
- `risk_reviewer`: 检查幻觉、过度推断、证据不足和不确定性。
- `evidence_organizer`: 整理证据质量和可追溯证据。

每个角色独立评审 claim，不读取其他角色的结果，避免角色之间互相影响。

如果 LLM 可用，会使用不同 prompt 和较低 temperature 调用模型。如果 LLM 不可用，会使用规则模式返回稳定结构。


## confidence scoring

`confidence_scorer.py` 会把多角色评审结果聚合成：

- `confidence_score`: 0 到 1 的置信度。
- `risk_level`: low / medium / high。
- `final_judgement`: reliable / needs more evidence / not reliable。

评分考虑以下因素：

- 角色平均置信度。
- 支持证据数量。
- 反对证据数量。
- 风险备注数量。
- 多角色判断一致性。

当前是可解释的规则评分，后续可以替换为更细的证据质量评分或评审模型。


## persistence

新增 MySQL 表：

`review`

字段包括：

- `id`
- `claim`
- `supporting_evidence_json`
- `opposing_evidence_json`
- `neutral_evidence_json`
- `role_reviews_json`
- `confidence_score`
- `risk_notes_json`
- `created_at`

repository 层在 `backend/app/repositories/review_repository.py`，业务代码不直接写 SQL。

如果 MySQL 不可用，API 会返回 `persistence.persisted = false` 和原因，不影响评审结果返回。


## api

拆分报告 claim：

```bash
curl -X POST http://localhost:5001/api/review/claims \
  -H "Content-Type: application/json" \
  -d "{\"report_text\":\"事件 X 可能继续发酵。相关组织的态度会影响后续走势。\"}"
```

评审单个 claim：

```bash
curl -X POST http://localhost:5001/api/review/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"claim\":\"事件 X 后续可能继续发酵\",\"persist\":false}"
```

评审整篇报告：

```bash
curl -X POST http://localhost:5001/api/review/report \
  -H "Content-Type: application/json" \
  -d "{\"report_text\":\"事件 X 可能继续发酵。相关组织的态度会影响后续走势。\",\"persist\":false}"
```


## files

新增文件：

- `backend/app/models/review.py`
- `backend/app/repositories/review_repository.py`
- `backend/app/services/claim_splitter.py`
- `backend/app/services/evidence_slicer.py`
- `backend/app/services/review_agent.py`
- `backend/app/services/confidence_scorer.py`
- `backend/app/api/review.py`
- `docs/phase6_multi_agent_review.md`

修改文件：

- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/config.py`
- `backend/app/db.py`
- `backend/app/models/__init__.py`
- `backend/app/repositories/__init__.py`
- `.env.example`


## how to run

启动 Flask：

```bash
cd backend
uv run python run.py
```

如果没有使用 `uv`，也可以在安装依赖后运行：

```bash
cd backend
python run.py
```


## how to test

健康检查：

```bash
curl http://localhost:5001/health
```

查看 review 路由是否注册：

```bash
cd backend
uv run python -c "from app import create_app; app=create_app(); print([str(r) for r in app.url_map.iter_rules() if '/api/review' in str(r)])"
```

本地没有配置 MySQL、Zep、Chroma 或 LLM 时，建议先使用 `persist:false` 测试评审链路。这样可以验证 claim 拆分、证据切片、角色评审和置信度聚合。

