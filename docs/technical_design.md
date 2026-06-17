# EvoLex 技术设计文档

## 1. 项目概述

EvoLex 是一个面向技术文档的受控知识抽取系统。它通过命令行对话入口接收技术文本或本地文件，运行一条带治理能力的文档处理管线，将非结构化技术内容转化为可审计、可回放、可发布或隔离的结构化知识对象。

当前版本已经从早期的 Phase 1/Phase 2 原型，演进为默认运行完整 Phase 3 系统管线。历史上的 `phase1`、`phase2`、`phase3` 仍保留为内部测试和调试概念；对普通用户来说，`evolex chat` 默认就是完整系统。

EvoLex 的核心目标不是直接“无条件把 LLM 输出写进知识图谱”，而是建立一个受控闭环：

- 从文档中抽取 Claim、Evidence、Mention、Measurement、Condition 等 typed objects。
- 对 Claim 做证据绑定和结构校验。
- 对 Mention 做实体解析，并记录 LINK / CREATE_CANDIDATE / AMBIGUOUS / REJECT 决策。
- 对实体间关系做抽取和质量复核。
- 对未知类型、关系和属性生成 schema proposal。
- 通过 critic 和 policy 节点决定 publish / candidate / quarantine / reject。
- 将候选、隔离、审计、schema proposal、checkpoint、评估报告分别落到独立存储。

## 2. 设计目标与非目标

### 设计目标

- **可追溯**：每个输出对象都应能追溯到 run、document、segment 和 evidence。
- **可治理**：高风险或证据不足的内容不能直接进入 production KG。
- **可回放**：每个节点后的 GraphState 都可以 checkpoint，支持 replay 和 resume。
- **可评估**：通过 frozen corpus 和 shadow evaluation 观察模型、prompt、schema 变化造成的影响。
- **可扩展**：保留 schema proposal 和 promotion 机制，为后续 schema 演化做准备。
- **可本地运行**：支持真实 OpenAI-compatible LLM API，也支持 `EVOLEX_OFFLINE=1` heuristic 模式。

### 当前非目标

- 不提供 Web UI。
- 不做人工审批 UI；当前 schema promotion 是自动门禁。
- 不对历史 production KG 做自动迁移。
- 不提供完整多租户权限系统。
- 不把 shadow evaluation 结果写入 production KG。

## 3. 系统架构

### 3.1 顶层运行入口

主要入口是 Typer CLI：

```bash
evolex chat
evolex eval frozen
evolex eval shadow
evolex run replay --run-id RUN-...
evolex run resume --thread-id document:...
evolex schema candidates
evolex schema promote-ready
evolex schema promote --proposal-id ...
evolex schema promotions
```

核心代码分层：

| 模块 | 职责 |
|---|---|
| `evolex.cli` | 顶层命令行入口 |
| `evolex.chat` | 交互式 CLI、意图识别、结果展示 |
| `evolex.graph` | 管线构建、运行、checkpoint、evaluation runner |
| `evolex.nodes` | 图节点：ingest/extract/validate/policy/publish 等 |
| `evolex.agents` | OpenAI-compatible LLM client 和 heuristic extractor |
| `evolex.contracts` | Claim、SchemaProposal 等数据契约 |
| `evolex.repositories` | SQLite/JSONL/JSON 存储层 |
| `evolex.policy` | policy 决策规则 |

### 3.2 图拓扑

当前默认系统管线：

```text
START
  -> ingest
  -> profile
  -> segment
  -> extract
  -> validate
  -> candidate_store
  -> entity_resolve
  -> relation_extract
  -> schema_gap
  -> schema_proposer
  -> quality_review
  -> critic
  -> policy
       ├─ publish
       ├─ quarantine
       └─ candidate / reject
  -> registry_finalize
  -> END
```

当安装了 `langgraph` 时，系统使用 `StateGraph` 构建图；否则使用本地 deterministic runner。两条路径保持同样的节点语义，以保证测试和本地 smoke run 稳定。

### 3.3 节点职责

| 节点 | 说明 |
|---|---|
| `ingest` | 清理和校验输入文本 |
| `profile` | 根据关键词识别技术领域和文档类型 |
| `segment` | 将文档切为句子级或段落级 segment |
| `extract` | 抽取 typed objects 或 legacy semantic atoms |
| `validate` | 校验 Claim / Evidence 等必填字段 |
| `candidate_store` | 写 JSONL candidate 和 Candidate Registry |
| `entity_resolve` | 解析 Mention 到实体，并记录决策 |
| `relation_extract` | 抽取实体关系，LLM 或 heuristic fallback |
| `schema_gap` | 发现无法映射到当前 schema 的概念 |
| `schema_proposer` | 生成 new_type / new_relation / new_attribute proposal |
| `quality_review` | 对 atoms 和 relations 打分并记录 issues |
| `critic` | 检查证据充分性和语义风险 |
| `policy` | 基于风险和证据做 publish/candidate/quarantine/reject 决策 |
| `publish` | 将通过门禁的实体、关系、审计写入 production KG |
| `quarantine` | 保留失败原因和建议动作 |
| `registry_finalize` | 写入 policy、quarantine、audit、schema proposal 等 registry |

## 4. 数据模型

### 4.1 GraphState

`GraphState` 是节点之间共享的运行状态。关键字段包括：

| 类型 | 字段 |
|---|---|
| 运行身份 | `run_id`, `thread_id`, `document_id`, `document_version` |
| 版本控制 | `schema_version`, `policy_version`, `graph_version`, `prompt_versions`, `model_routes` |
| 文档信息 | `document_text`, `document_type`, `domains`, `segments` |
| Legacy 输出 | `semantic_atoms`, `validation_results`, `candidate_output_path` |
| Phase 2 输出 | `entities`, `relations`, `quality_scores`, `publish_output_path` |
| Typed objects | `mentions`, `measurements`, `conditions`, `claim_candidates`, `evidence_spans` |
| 决策对象 | `entity_decisions`, `policy_decisions`, `critic_results`, `schema_proposals` |
| 治理/评估 | `unresolved_terms`, `audit_events`, `registry_output_path`, `checkpoint_path`, `shadow_report_path` |
| 运行计数 | `llm_call_count`, `tool_call_count`, `retry_count`, `warnings`, `status` |

### 4.2 Typed Objects

| 对象 | 关键字段 | 说明 |
|---|---|---|
| `Claim` | `subject`, `predicate`, `object`, `evidence_ids`, `measurements`, `conditions` | 核心知识声明 |
| `Evidence` | `evidence_id`, `document_id`, `segment_id`, `text`, `span_start`, `span_end` | Claim 的证据片段 |
| `Mention` | `text`, `normalized_text`, `mention_type`, `evidence` | 实体候选提及 |
| `Measurement` | `parameter`, `value`, `unit`, `text`, `evidence` | 测量值 |
| `Condition` | `text` 或参数化条件字段 | Claim 生效条件 |

系统要求每个 Claim 至少关联一个 Evidence。缺少 evidence 的 Claim 会被 `validate` 节点过滤或导致 quarantine。

### 4.3 决策模型

实体解析输出：

| 决策 | 含义 |
|---|---|
| `LINK` | 匹配已有 canonical entity |
| `CREATE_CANDIDATE` | 创建新的候选实体 |
| `AMBIGUOUS` | 存在歧义，保留但不强行发布 |
| `REJECT` | 文本过短、置信度过低或无效 |

Policy 输出：

| 动作 | 含义 |
|---|---|
| `publish` | 低风险且证据充分，写入 production KG |
| `candidate` | 中等风险或部分证据，保留为候选 |
| `quarantine` | 高风险或 critic 拒绝，隔离 |
| `reject` | 确定性失败，丢弃或终止发布 |

## 5. LLM 与并发设计

EvoLex 使用 OpenAI-compatible chat completion API。默认配置面向 DeepSeek：

- `base_url`: `https://api.deepseek.com`
- `model`: `deepseek-v4-flash`
- `timeout_seconds`: `30`
- `concurrency`: `4`

DeepSeek profile 会携带 provider-specific 参数：

- `reasoning_effort="high"`
- `extra_body={"thinking": {"type": "enabled"}}`

Generic OpenAI-compatible profile 只传通用字段：

- `model`
- `messages`
- `stream=False`

### 并发抽取

`extract` 节点支持 segment-level 并发：

- 每个 segment 的 extraction 可以并发调用 LLM。
- 默认并发数为 4。
- `llm_concurrency=1` 时退回串行行为。
- 并发结果会按原始 segment 顺序合并，保证输出稳定。
- `relation_extract` 暂不并发，因为它需要完整 entities/atoms 上下文做一次聚合抽取。

配置方式：

```bash
evolex chat --llm-concurrency 4
```

交互式配置：

```text
EvoLex> set llm concurrency 4
EvoLex> /config concurrency 4
```

## 6. 存储设计

### 6.1 Candidate JSONL

每次运行都会输出 candidate JSONL，记录 typed object 或 legacy atom：

- `run_id`
- `document_id`
- `object_type`
- `object`
- `created_at`

### 6.2 Candidate Registry

SQLite registry，用于结构化查询 candidate、policy、quarantine 和 audit。

核心表：

- `candidates`
- `entity_decisions`
- `policy_decisions`
- `quarantine_records`
- `audit_events`

### 6.3 Production KG

Production KG 是 SQLite 文件。只有 policy 允许 publish 的对象才会进入。

核心表：

- `runs`
- `entities`
- `entity_segments`
- `entity_decisions`
- `relations`
- `quality_scores`
- `run_audit`

### 6.4 Schema Candidate Store

跨运行累积 schema proposals。proposal 通过 `(proposal_type, name)` 合并稳定信号。

核心字段：

- `proposal_id`
- `proposal_type`
- `name`
- `supporting_texts`
- `evidence_spans`
- `occurrence_count`
- `independent_document_count`
- `relation_pattern_consistency`
- `evidence_coverage`
- `source_run_ids`
- `schema_version`
- `status`

proposal 状态：

- `candidate`
- `promoted`
- `blocked`

### 6.5 Promotion Ledger

`schema_promotions` 记录自动 promotion 或 block 结果：

- proposal id/name/type
- action
- source schema version
- target schema version
- decision reason
- evaluation report path
- timestamp

Promotion 只更新 schema candidate metadata 和 ledger，不改写 production KG，也不迁移历史数据。

### 6.6 Checkpoint Store

每个 graph node 完成后写入 GraphState checkpoint。用途：

- 按 `run_id` replay 节点序列。
- 按 `thread_id` 从最新 checkpoint resume。
- 为故障定位提供状态快照。

## 7. Schema 治理闭环

Schema governance 的流程：

```text
typed extraction
  -> schema_gap
  -> schema_proposer
  -> Schema Candidate Store
  -> frozen/shadow evaluation
  -> automatic promotion gate
  -> promoted / blocked / hold
```

自动 promotion 默认门槛：

- `occurrence_count >= 3`
- `independent_document_count >= 2`
- 没有 high-risk policy decision
- 没有 rollback recommendation

命令：

```bash
evolex schema candidates
evolex schema promote-ready
evolex schema promote --proposal-id scp-...
evolex schema promotions
```

## 8. Evaluation、Shadow 与回归

### Frozen Corpus

`evolex eval frozen` 使用仓库内固定样本文档运行系统，生成稳定指标：

- claim 数量
- evidence 数量
- evidence coverage
- entity 数量
- relation 数量
- unsupported 数量
- ambiguous 数量
- entity remap 数量

### Shadow Evaluation

`evolex eval shadow` 运行离线对比评估：

- 生成 shadow report。
- 不写 production KG。
- 聚合 governance snapshot。
- 输出 `canary_ready` 和 `rollback_recommended`。

### Replay / Resume

```bash
evolex run replay --run-id RUN-...
evolex run resume --thread-id document:DOC-...:v3
```

Replay 读取 checkpoint 生成节点执行序列。Resume 从最新 checkpoint 恢复并继续运行。

## 9. CLI 使用方式

### 交互处理文档

```bash
evolex chat
```

可输入：

```text
EvoLex> API Gateway retries HTTP 503 responses for 2 seconds.
EvoLex> examples/technical_note.txt
EvoLex> entities
EvoLex> relations
EvoLex> policy
EvoLex> schema
EvoLex> audit
```

### LLM 配置

```text
EvoLex> llm settings
EvoLex> set llm url https://api.deepseek.com
EvoLex> set llm model deepseek-v4-flash
EvoLex> set llm api-key sk-...
EvoLex> set llm timeout 45
EvoLex> set llm concurrency 4
```

配置会写入 `~/.evolex.toml`。

### 离线模式

```bash
export EVOLEX_OFFLINE=1
evolex chat
```

离线模式使用 deterministic heuristic extractor，适合测试、演示和无网络环境。

## 10. 测试策略

测试覆盖范围：

- chat controller / CLI
- intent parser
- DeepSeek / OpenAI-compatible client 参数
- Phase 1 graph
- Phase 2 graph
- Phase 3 governance contracts
- frozen/shadow/checkpoint/replay/resume
- segment-level extraction concurrency
- schema promotion gate

运行：

```bash
pytest
```

当前已验证全量测试通过：

```text
128 passed, 3 skipped
```

## 11. 当前能力边界

虽然系统已经具备本地可运行的治理型 MVP，但仍有一些生产化边界：

- Resolver 仍偏启发式，需要更强的跨运行实体历史、别名库和歧义解释。
- Schema promotion 还没有生成正式 schema artifact 或 changelog。
- Shadow/canary 目前是离线评估，还没有接真实线上流量。
- Rollback 目前是治理信号，不会自动回滚 production 数据。
- Frozen corpus 目前主要比较指标，尚未加入强断言式 expected outputs。
- 人工审批 UI 暂未实现，后续可作为可选增强。

## 12. 后续演进方向

建议后续优先级：

1. 强化 entity resolver：跨运行实体历史、别名 registry、冲突检测。
2. 生成正式 schema artifact：schema version package、changelog、promotion diff。
3. 加强 frozen corpus：加入 expected claim/entity/evidence 断言。
4. 真实 canary 接入：在发布前对真实样本或流量影子运行。
5. 自动 rollback 策略：将 governance signal 转为可执行的回滚动作。
6. 可选人工审批：为 schema promotion、quarantine review 提供 review UI 或更完整 CLI。
