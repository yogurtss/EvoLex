# EvoLex 下一步实现清单

当前代码已经完成了 `Phase 1` 完整链路，以及 `Phase 2` 的简化链路。仓库已经具备从文档输入、语义原子抽取、结构校验，到实体解析、关系抽取、质量复核和 SQLite 发布的基本能力。

当前代码已经进入目标架构里的最小治理闭环：`Claim` / `Evidence` 对象槽位、`Policy` 路由、`Schema proposal` 候选、Candidate / Quarantine Registry、运行审计和多模型 OpenAI-compatible 接入已经落地。下一阶段的基础能力也已经补上：`Frozen Corpus` 回归基线、`Shadow` 评估、可恢复 checkpointer、运行回放，以及面向 canary / rollback 判断的跨运行治理摘要。

本文只做一件事：把仓库当前已实现能力与 `langgraph_semiconductor_system_report_v2.html` 的目标能力对齐，整理出一份按执行顺序排列的下一步实现 backlog，便于直接进入工程实现。

## 当前进度

### 已完成的主链路

- `ingest -> profile -> segment -> extract -> validate -> candidate_store`
- `entity_resolve -> relation_extract -> quality_review -> publish`

### 已完成的运行方式

- 已有 CLI 入口，可直接处理文本输入和本地文件路径。
- 已支持 `Phase 1` / `Phase 2` 管线切换。
- 已支持 `DeepSeek`、通用本地 OpenAI-compatible 模型和本地 heuristic extractor 运行。
- 已支持 `JSONL` candidate 输出。
- 已支持 `SQLite` knowledge graph 输出。

### 已完成的测试覆盖

- `Phase 1 graph`
- `Phase 2 graph`
- `chat controller / CLI`
- `intent / DeepSeek client`

### 当前能力边界

- `semantic_atoms` 仍保留为兼容层，`Claim` / `Condition` / `Evidence` 已有最小对象化输出。
- 实体解析已有决策记录，但仍以启发式规则为主。
- 已有独立 `critic` / `policy` / `quarantine` / `registry_finalize` 闭环。
- 已有 `Schema proposal` 候选存储；`shadow`、`frozen corpus`、治理摘要报告已经落地。
- 已有版本治理字段、审计存储、可恢复 `checkpointer` 和运行回放。

## 目标进度

下一阶段的目标能力只保留会影响实现顺序的部分：

- `Claim` 中心知识模型
- 强证据绑定与 `provenance`
- 显式 `Policy / quarantine / publish` 路由
- `Schema proposal` 与 `registry`
- `Shadow schema / canary / 回滚`
- 可重放、可追踪、带版本的运行状态

## 关键接口变化

### GraphState 需要补充的字段

- 版本字段：`document_version`、`schema_version`、`policy_version`
- 抽取对象字段：`mentions`、`measurements`、`conditions`、`claim_candidates`、`evidence_spans`
- 决策对象字段：`entity_decisions`、`policy_decisions`、`schema_proposals`

### 需要新增的节点

- `critic`
- `policy`
- `schema_gap`
- `schema_proposer`
- `quarantine`

### 需要新增的存储职责

- `Candidate Registry`
- `Quarantine Store`
- `Run Audit Store`
- `Schema Candidate Registry`

## 实现清单状态

## 1. [已完成] Claim / Evidence 数据契约落地

**目标**

把当前由 `semantic_atoms` 主导的输出，升级为能承载目标系统的最小结构化对象模型。

**功能点**

- 在状态层新增独立对象槽位：`mentions`、`measurements`、`conditions`、`claim_candidates`、`evidence_spans`。
- 抽取节点输出从“原子列表”升级为“对象包”，至少支持 `Mention`、`Measurement`、`Condition`、`Claim`、`Evidence` 五类对象。
- 每个 `Claim` 必须关联至少一个 `Evidence`。
- `Evidence` 至少包含：`document_id`、`segment_id`、`text/span`、`run_id`。
- `candidate_store` 持久化时不再只写 `atom`，而是能写多对象类型。
- `validate` 节点改为校验对象级必填字段，而不是只校验 atom。

**验收清单**

- 输入一段带条件和测量值的技术文本，输出中能区分 `Claim`、`Condition`、`Measurement`。
- 每个 `Claim` 都能追到明确 `Evidence`。
- 缺少 `evidence` 的 `Claim` 不能通过结构化校验。
- candidate 输出中能看出对象类型，而不是只有混合 atom。

## 2. [已完成] 实体解析升级为决策型 Resolver

**目标**

把当前“按文本归并”的启发式 entity merge，升级为可解释的解析决策流程。

**功能点**

- `Resolver` 输出决策类型：`LINK` / `CREATE_CANDIDATE` / `AMBIGUOUS` / `REJECT`。
- 增加别名归一化和单位归一化前处理。
- 把“实体结果”与“实体决策记录”分开保存。
- 对无法稳定链接的对象保留 `AMBIGUOUS`，不强行落正式实体。
- `relation` / `claim` 后续只消费已解析或明确保留的对象。

**验收清单**

- 同名不同上下文对象不会被盲目合并。
- 别名形式能归到同一 `canonical entity`。
- 单位表达差异不会导致重复实体。
- 歧义样本进入 `AMBIGUOUS`，不会直接发布。

## 3. [已完成] 独立 Critic + Policy 路由

**目标**

把当前简单质量打分改成“验证 -> 语义复核 -> 策略决策”的三段式门禁。

**功能点**

- 从 `quality_review` 中拆出独立的 `critic` 语义复核结果。
- 新增 `policy` 节点，输出：`publish` / `candidate` / `quarantine` / `reject`。
- 明确低、中、高风险规则：
  - 低风险：新实例、别名、补证据
  - 中风险：新关系、新属性、新类型候选
  - 高风险：类型合并拆分、历史迁移
- 图拓扑增加条件路由，不再只是一条直线走到 `publish`。
- `quarantine` 路径保留失败原因和处理建议。

**验收清单**

- 证据不足样本不会直接 `publish`。
- 高风险变更不会进入正式发布路径。
- `policy` 决策结果可在 run state 中查看。
- `quarantine` 样本能看到明确原因标签。

## 4. [已完成] 版本化 State 与运行审计

**目标**

让每次运行具备最小可重放性和可追踪性。

**功能点**

- 在状态层补充版本字段：`document_version`、`schema_version`、`policy_version`、`prompt_versions`、`model_routes`。
- 所有输出对象都带：`run_id`、`document_id`、`document_version`、`schema_version`。
- 增加运行审计存储，至少记录：节点执行顺序、状态转移、告警、`policy` 决策。
- 保留稳定 `thread_id` 规则，避免同文档版本重复创建独立运行。

**验收清单**

- 同一文档重跑时能区分不同 `document_version`。
- 任一 `claim` / `entity` / `relation` 都能追溯到 run 和版本。
- 能查看一次运行经过了哪些节点和决策。
- 状态结构包含目标版本字段，不再只有最小运行字段。

## 5. [已完成] Candidate Registry 与 Quarantine 工作流

**目标**

把“候选输出文件”升级成可管理的候选知识池。

**功能点**

- 引入 `Candidate Registry` 存储层，保存：
  - candidate objects
  - entity decisions
  - policy decisions
  - quarantine records
- `Candidate` 与 `Production` 明确隔离。
- `Quarantine` 记录支持：
  - 原因
  - 风险等级
  - 关联证据
  - 建议动作
- CLI 增加最小查询能力，至少能看：
  - 最近 quarantine
  - 最近 candidate
  - 最近 policy 决策

**验收清单**

- 被 `quarantine` 的对象不会写入 production KG。
- 可以查询到 `quarantine` 原因和原文证据。
- `candidate` 与 `production` 的对象能明确区分。
- 不依赖翻 `JSONL` 才能定位候选记录。

## 6. [已完成] Schema Gap / Schema Proposal 最小闭环

**目标**

补上从实例抽取到 schema 候选生成的最小闭环。

**功能点**

- 新增 `schema_gap` / `schema_proposer` 子流程。
- 识别“无法映射到现有类型/关系”的对象。
- 生成 `schema proposal`，至少支持：
  - 新类型提案
  - 新关系提案
  - 属性提案
- 为 proposal 记录支持信号：
  - 出现次数
  - 独立文档数
  - 关系模式一致性
  - 证据覆盖率
- 建立 `Schema Candidate Registry`。

**验收清单**

- 遇到未知但重复出现的概念时，不会被静默丢弃。
- proposal 能看到支持它的样本和证据。
- proposal 不会直接进入 production schema。
- 同类 proposal 可以累积稳定性信号。

## 7. [已完成] Frozen Corpus + Shadow Evaluation 回归基线

**目标**

为后续 schema 演化和模型升级建立最小回归护栏，并支持恢复 / 回放调试。

**功能点**

- 固定仓库内样本文档作为 `frozen corpus`。
- 引入 `shadow` 评估输出，不写 production KG。
- 每次 `schema` / `prompt` / `model` 变化时，比较：
  - claim 数量变化
  - evidence coverage
  - unsupported / ambiguous 比例
  - entity remap 数量
- 形成最小回归报告和 shadow 对比报告。
- 在每个节点完成后写入 `GraphState` checkpoint。
- 支持按 `run_id` 回放节点序列，按 `thread_id` 从最新 checkpoint 恢复。
- 聚合 schema proposal 与 policy decision，给出 canary / rollback 判断信号。

**新增入口**

- `evolex eval frozen`
- `evolex eval shadow`
- `evolex run replay --run-id RUN-...`
- `evolex run resume --thread-id document:...`
- `evolex schema candidates`
- `evolex schema promote-ready`
- `evolex schema promote --proposal-id ...`
- `evolex schema promotions`

**验收清单**

- 新旧版本可在同一批文档上对比结果。
- `shadow` 结果不会覆盖 production。
- 回归报告至少能反映 `claim` / `evidence` / `entity` 三类核心差异。
- 版本升级后可以判断是“更好、持平还是退化”。
- checkpoint 可以重放节点顺序和策略决策。
- resume 可以从最新 checkpoint 继续生成最终状态。
- schema proposal 可以通过自动门禁进入 `promoted` 或 `blocked` 状态。
- 多 segment LLM 抽取支持有界并发，并保持输出顺序稳定。

## 完成定义

这份 backlog 的当前完成定义不是把所有生产化能力一次做完，而是完成以下核心收敛项：

- `Claim / Evidence` 契约
- `Resolver` 决策化
- `Policy` 路由
- `Candidate / Quarantine` 管理
- `Schema proposal` 最小闭环
- `Frozen Corpus` / `Shadow` 回归报告
- `Checkpoint` / `Replay` / `Resume` 最小调试闭环
- 自动 schema promotion 门禁
- API segment-level 并发抽取

后续真正的生产化工作应集中在：更强的 resolver、真实 canary 流量接入、自动回滚策略、稳定 schema 版本发布物，以及可选的人工审批 UI。
