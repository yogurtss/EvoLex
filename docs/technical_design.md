# EvoLex 0.3 技术设计

## 1. 设计结论

EvoLex 0.3 的默认系统不是“实体 Agent + 关系 Agent + 写库”的线性脚本，而是由四条闭环组成：

1. **联合抽取闭环**：同一片段的一次主要模型响应同时给出提及、关系端点和证据；
2. **身份规范化闭环**：分别处理实体身份与关系身份，并保留所有来源贡献；
3. **演化验证闭环**：候选对象先成为来源绑定补丁，冻结原始影响域后执行结构查询、依赖闭包反事实归因和局部排除；
4. **版本治理闭环**：因果验证凭证在判定和提交阶段重算，提交清单把实际接受操作绑定到canonical版本，失败进入候选或隔离，并支持追加式历史补偿版本。

`agent` 是默认运行模式。`system` 是固定节点顺序的对照基线，不包含完整的 canonical 自进化控制链。

## 2. 总体架构

```text
Document
  │
  ▼
Ingest ─ Profile ─ Segment
  │
  ▼
Joint Extractor
  ├─ Mention(mention_id)
  ├─ RelationCandidate(subject_mention_id, object_mention_id)
  ├─ Claim(claim_id, evidence_ids)
  └─ Evidence(evidence_id, segment_id)
  │
  ▼
Validate Evidence First
  │
  ▼
Entity Resolve ─ Entity Canonicalize
  │                    │
  └─ mention→entity ───┘
             │
             ▼
Relation Materialize ─ Relation Canonicalize / Conflict Detect
             │
             ▼
Schema Gap / Proposal  ──────────────┐
             │                       │ candidate only
             ▼                       ▼
Evolution Patch ─ Frozen Impact Domain ─ Shadow Graph
                                 ├─ provenance invariants
                                 ├─ endpoint/key invariants
                                 ├─ deterministic replay
                                 └─ outside-domain projection
                                           │
                          failed query → associated operations
                                           │
                           dependency-closed counterfactual replay
                                           │
                             verified cause candidates
                                           │
                        excluded-set solver + residual revalidation
                                           │
                           content-addressed validation certificate
                                           │
                                           ▼
                         Base gates + certificate consistency gate
                                           │
                       ┌───────────────────┴──────────────────┐
                       ▼                                      ▼
             Commit-manifest-bound                    Candidate /
             canonical transaction                    Quarantine
             version + events + certificate
                       │
                       ▼
                Local publish view
```

## 3. 联合抽取

### 3.1 输出契约

`TypedExtractor.extract_typed(segment_text)` 的联合响应至少包括：

```json
{
  "mentions": [
    {
      "mention_id": "m1",
      "text": "API Gateway",
      "mention_type": "tool",
      "evidence": "API Gateway retries HTTP errors.",
      "confidence": 0.91
    }
  ],
  "relations": [
    {
      "subject_mention_id": "m1",
      "predicate": "retries",
      "object_mention_id": "m2",
      "evidence": "API Gateway retries HTTP errors.",
      "confidence": 0.88
    }
  ],
  "measurements": [],
  "conditions": []
}
```

关系端点只能引用同一响应内声明的 `mention_id`。解析器不会把未知端点猜成相似实体；它保留候选并标记 `endpoint_validation_status=invalid` 及具体错误。

### 3.2 运行内标识

模型只负责片段内局部标识。`extract` 节点加入片段命名空间：

```text
m1       → seg-0001:m1
ev-0001  → seg-0001:ev-0001
clm-0001 → seg-0001:clm-0001
rc-0001  → seg-0001:rc-0001
```

这些标识保证同一次运行的多片段对象不碰撞，但不宣称跨文档版本永久稳定。跨运行稳定性由 canonical identity 提供。

### 3.3 为什么改善关系失败

分离抽取的典型失配是：

```text
第一次：模型抽到 “API Gateway”
第二次：关系模型输出 “gateway” 或不存在的 entity_id
结果：端点无法映射，关系被丢弃
```

联合路径把端点引用固定在同一响应的提及标识上：

```text
subject_mention_id
  → namespaced mention_id
  → mention_entity_map
  → canonical entity ID
```

只有没有任何可成功物化的有效联合关系时，`relation_extract` 才走兼容性回退。若端点只有一部分失败，系统保留有效关系，并把失败候选写入 `relation_endpoint_failures`；若两个端点规范化为同一实体，则记录 `canonical_endpoint_collapse`，而不是悄悄生成自环。

## 4. 证据优先校验

校验顺序是：

1. 删除缺少 `evidence_id`、`document_id` 或非空 `text` 的 Evidence；
2. 以过滤后的 Evidence ID 集合验证 Claim；
3. 只有所有引用均指向有效 Evidence 的 Claim 才进入候选链；
4. 无有效 Claim/legacy atom 的运行进入隔离。

校验器始终回写过滤后的 Claim 和 Evidence 列表，避免原状态中的无效对象继续流向 `candidate_store`。

## 5. 实体身份规范化

### 5.1 两阶段设计

`entity_resolve` 先把 Mention 解析为局部实体并形成 `mention_entity_map`；`entity_merge` 再提出同类实体合并。

自动合并硬条件：

- 实体类型相同；
- 双方具有来源提及；
- 规范文本、别名、缩写或词项重叠达到阈值；
- 新成员与簇中每个成员都满足阈值（complete-link）。

complete-link 防止相似度链式扩散：

```text
A≈B 且 B≈C，但 A≉C  →  不把 A、B、C 全部合并
```

Unicode 文本只做兼容性归一化、大小写和空白处理，不删除中文等非 ASCII 字符。

### 5.2 可逆证据

合并后的实体保留：

- `source_entity_ids`
- `source_mention_ids`
- `segment_ids`
- `aliases`
- `merge_decisions`
- 自动合并或 hold 的原因

当前支持按版本贡献的补偿回滚，不支持用户界面中的任意单实体“自动拆分”操作。

## 6. 关系身份规范化

关系首先通过共享的谓词规范化器：

```text
requires / relies_on / rely_on → depends_on
associated_with                → related_to
```

`schema_gap` 复用同一规范化器，因此不会把已经映射到 `depends_on` 的 `requires` 再提议成冗余新谓词。

关系身份键：

```text
K(r) = (canonical_subject, canonical_predicate,
        canonical_object, qualifiers_hash)
```

限定信息先按键排序规范序列化并计算摘要；因此同一三元组在不同时间、条件或范围下保持不同身份。对称谓词统一端点顺序；同键关系聚合时保存逐条`source_assertions`，每条包含源关系/候选、原谓词、端点、限定信息、证据、片段和源置信度，可重建原断言。置信度可使用带折扣、带上限的noisy-OR：

```text
c_combined = 1 - ∏(1 - d_i c_i)
c_relation = min(c_combined, max(c_i) + 0.08(n_segment - 1), 0.99)
```

其中 `n_segment` 是不同证据片段数，不表述为已经验证的“独立信息源”数。

只有配置为功能型的谓词（如 `has_owner`、`has_version`）才把同一主语对应多个宾语视为冲突；`uses` 等多值谓词不会被误判。冲突定义在合并节点、图指标和策略层保持一致。

## 7. 多 Agent 控制

### 7.1 Agent 角色

| 角色 | 技术职责 |
|---|---|
| Orchestrator | 执行准备动作、汇总提案、按效用选工具 |
| Extraction | 发起联合抽取或必要的重抽取 |
| Entity Resolution | 建立 mention 到局部实体的映射 |
| Entity/Relation Canonicalization | 提出并执行同类身份合并 |
| Evidence | 检查 Claim/Evidence 覆盖并触发校验 |
| Graph Critic | 检查稀疏、证据和功能关系冲突 |
| Schema | 发现并分别累积未知类型、关系、属性 |
| Evolution | 规划补丁、影子验证、共识和提交 |
| Policy | 风险路由、本地发布或隔离 |

这些角色是可解释的 proposal/controller 角色；当前并不要求每个角色都是独立 LLM，也不执行在线模型训练。

### 7.2 动作效用

控制器计算：

```text
U(a) = EIG(a) - λ · Cost(a) - μ · Risk(a)
```

动作选择、候选动作、EIG、风险、成本和结果都写入 `agent_trace`。最大轮数为 40；低效用持续达到门槛时停止并进入 candidate/quarantine。

### 7.3 依赖失效

工具之间有显式依赖图。若重新执行 `extract_tool`，已完成的 validate、resolver、merge、relation、schema、evolution、policy 和 publish 产物会失效并删除，下游必须基于新输出重算。每个工具有 revision 号，trace 记录被失效的后继工具。

依赖图同时是执行许可，而不只是调度提示。控制器在调用每个工具前重新核对必需前驱；即使自定义或异常 Agent 直接提议 `publish_tool`，也不能越过校验、候选注册、解析、双层合并、schema 检查、已接受演化、canonical 提交和发布置信度门。发布节点还会独立重复授权检查，形成纵深防御。

`policy.action=publish` 只授予进入提交/发布阶段的许可，策略节点本身不会把运行标成 `published`。实际运行级发布在独立 SQLite 事务内写入；任一实体或关系写入失败会整体回滚，同一状态的 `run_id` 重试以快照替换而非累加。该派生快照没有 revision CAS，不同新旧载荷对同一 `run_id` 并发写入时仍是 last-writer-wins。

## 8. 补丁与证据契约

实体补丁和关系补丁共有：

```text
operation_id
action / object_type / object_id
after
evidence_contract
affected_domain
caused_by
```

关系补丁额外具有`depends_on_entity_ids`。实体证据契约包含来源文档、片段、Mention、类型一致性和来源完整性；关系证据契约包含Evidence、候选关系、端点映射完整性和来源完整性。不同对象类型不被错误要求具有完全相同的来源字段。

证据契约不是说明性备注。影子不变量、影响域 grounded 判定和 EvidenceContractAgent 直接读取它。

## 9. 影响域与影子图

### 9.1 影响域

影响域由补丁声明域、证据契约、端点依赖和当前 canonical 基线共同推导：

- 被修改的实体和关系；
- 关系的主语、宾语与谓词；
- 来源文档、片段和 Evidence；
- 基线中与端点/谓词相关的一跳对象。

该域限定要检查的对象，也定义域外投影边界。系统在完整候选补丁上计算`domain_hash`并冻结；之后排除部分操作时可以另记接受操作声明域，但所有反事实和求解重放仍使用原始冻结域。

### 9.2 自动不变量

当前自动生成的结构不变量包括：

- 实体存在且 canonical key 可解析；
- 实体与关系来源契约完整；
- 关系两个端点均存在；
- canonical relation key 唯一；
- 同一补丁重复应用得到相同内存快照哈希；
- 应用前后影响域外投影哈希相同。

这里的 deterministic replay 是同一补丁、同一基线、同一纯函数影子执行的一致性检查；不是随机 LLM 输出复现证明。non-interference 是影子投影一致性检查；不是形式化验证，也不是物理隔离数据库证明。

每个查询结果初始包含`query_id`、pass/fail和`associated_operation_ids`。系统逐个排除关联操作及其端点依赖闭包，从同一基线重放；只有目标`query_id`不再失败时，才写入`counterfactual_cause_operation_ids`并进入排除求解候选空间。

## 10. 反事实原因与待排除集合

目标函数为：

```text
R* = argmin_R [
  1.00 · |R|
  + 0.05 · BlastRadius(R)
  + 0.02 · EvidenceLoss(R)
]
```

约束：

- 排除后全部强制不变量通过；
- 排除集合满足操作依赖闭包；
- 保留操作可重放；
- 域外投影保持一致。

当反事实原因候选不超过16个时，系统枚举候选子集，输出`solver_mode=exact_enumeration`、目标分量、约束和`global_over_causal_candidate_space`标记。全局性只针对该候选空间。

大于阈值时，从完整原因闭包开始重复单项删除和重放直至固定点，输出`deterministic_fixed_point_deletion_fallback`和`single_deletion_local_minimum_not_global`。它既不保证全局最优，也不无条件保证一般非单调约束下的集合包含极小。

### 10.1 因果验证凭证

`_build_validation_certificate`把基线、完整候选操作、冻结/接受域、查询关联和反事实检查、求解器结果、排除/接受操作、最终影子摘要及门结果规范序列化并计算内容摘要。该凭证是可重算一致性清单，不是数字签名或知识真实性证明。

## 11. 基础门与凭证一致性门

接受补丁必须同时满足：

1. EvidenceContractAgent：来源契约完整且影响域有证据依据；
2. DeterministicReplayAgent：影子重复执行一致；
3. NonInterferenceAgent：域外投影一致；
4. InvariantAgent：补偿后强制不变量全部通过；
5. UtilityAgent：演化效用非负；
6. CausalCertificateAgent：重算凭证与全部绑定字段一致；
7. 至少5票同意；
8. 至少保留一个可提交操作。

六项均以AND方式作为硬条件，因此quorum只是审计统计而非替代任一硬门。提交执行节点还要求decision、evaluation和certificate三方接受操作ID相等，并再次重算凭证。

## 12. Canonical 版本与补偿

### 12.1 提交边界

在 `canonical_registry.sqlite` 的一个 `BEGIN IMMEDIATE` 事务中：

- 检查补丁 parent 等于当前 active version；
- 对同一 patch 做幂等重放识别；
- 计算并核对`commit_manifest_hash = H(patch_id,parent,accepted IDs,accepted operations hash,certificate ID)`；
- 写 `graph_versions`；
- 应用实体/关系操作；
- 写逐操作 `graph_events`、before/after/inverse 和证据契约；
- 更新 `active_version` 指针。

`graph_versions`额外持久化`accepted_operation_ids_json`、`accepted_operations_hash`、`certificate_id`和`commit_manifest_hash`。相同patch ID只有提交清单摘要一致才作为幂等重放；不同接受集合或凭证会被拒绝。

任一步骤异常时整个 canonical 事务回滚。只有 canonical commit 成功后，Agent 才运行本地 `publish_tool`。运行级 KG 与 canonical store 是两个存储，本项目不声称跨库分布式原子性；canonical store 是版本事实源，本地 KG 是派生视图。

### 12.2 按版本贡献

实体、实体别名和关系分别保存 `version_id` 级贡献；Mention 和关系 Evidence 自带贡献版本。对旧版本做选择性回滚时：

- 只删除目标版本贡献；
- 从仍存在的贡献重算 canonical label、类型、置信度和 created version；
- 保留后来版本的别名、Mention 和 Evidence；
- 若后来活动关系仍依赖且实体没有其他贡献，则跳过实体补偿；
- 后来的 delete 状态不会被旧版本回滚重新激活；
- 回滚 later delete 时使用专用 status restore，从现存贡献重算，不伪造一条旧内容贡献。

回滚不删除历史版本，而是追加一个新的补偿版本。自动演化 planner 和影子验证链当前只生成、执行证据化 upsert 补丁；canonical repository 另行支持 upsert/delete/tombstone/compensate 的版本生命周期与选择性回滚。两者不能混为一谈，也不能外推成任意图变换的交换律或通用事务补偿理论。

## 13. Schema 演化

运行开始时固定活动 schema，整个运行不读取中途变化的热版本。未知 symbol 按 `(category, normalized_symbol)` 分别形成 proposal，避免同一文档的两个未知谓词被合成一个候选。

提升门默认要求：

- `occurrence_count >= 3`
- `independent_document_count >= 2`
- 治理报告无 high-risk 决策
- 无 rollback recommendation

并发 promotion 在 `BEGIN IMMEDIATE` 后重新读取活动 schema，第二个提升从第一个版本继续，避免丢更新。同一提议的 `candidate → promoted | blocked` 也是单事务条件状态转换；晋升与阻止并发竞争时只能有一个终态及一条相应账本记录，避免活动 schema 已含符号而提议又显示 blocked。schema promotion 当前由 CLI/外部流程发起并受自动门控制；不是 ontology 无人值守自主修改。

## 14. Checkpoint、回放与恢复

每个节点或 Agent 工具完成后持久化 GraphState。checkpoint 包含：

- `pipeline_mode`
- extractor class、是否 LLM、联合抽取能力
- 非敏感模型路由（base URL、model、profile、timeout、concurrency）
- schema/policy/graph 版本
- Agent trace 和工具 revision

`resume_thread` 默认继承 checkpoint 中的 pipeline 和 heuristic/LLM 路由；显式传入不匹配 pipeline 会拒绝。已经完成的 checkpoint 可直接返回，不需要重建抽取器。进行中的未知自定义 extractor 不会静默降级为内置启发式实现，只有调用方显式提供同一类实例时才恢复，否则 fail-closed。LLM 恢复仍要求运行环境提供 API key，并不能保证服务端随机采样得到 bit-for-bit 相同输出。

同一 thread 的恢复目标按最近写入 checkpoint 选择，而不是被旧长 run 的较大 step index 遮蔽。

分支节点的 checkpoint 表示该节点已经完成、但其出边可能尚未执行。固定 `phase3` 恢复会先消费已完成 `quality_review` 或 `policy` 的路由结果，再进入隔离、发布或最终注册；不会因从节点之后开始遍历而跳过分支动作。

## 15. 可视化

原有`evolex visualize`继续读取canonical store和活动schema，生成无外部静态资源的单HTML。当canonical history给出运行标识时，治理视图只读取同名per-run registry；精确文件缺失或内容无法核对时显示未绑定，不回退到另一个运行。仅对没有任何版本历史的旧空存储保留按修改时间读取独立最新registry的兼容行为：

- 可筛选 canonical graph；
- 点击关系查看来源 Evidence；
- 版本时间线；
- Agent 决策轨迹；
- 影响域不变量；
- 待排除操作、反事实检查和凭证字段；
- merge、patch、commit 和 schema JSON 审计。

新增`evolex visualize-bundle --output-dir <目录>`生成可直接复制和归档的静态HTML包：

```text
<目录>/
├── index.html
├── evolex-global-kg.html
└── documents/
    └── evolex-doc-<安全标识>-<摘要>.html
```

- `index.html`列出跨文档总图和全部来源文档入口；
- `evolex-global-kg.html`包含当前全部活动canonical实体、关系和关系证据；
- `documents/evolex-doc-*.html`为逐文档投影，文件名由安全化片段和内容摘要组成，原始标识不能形成路径穿越；
- 每个图页面都内嵌数据、CSS和JavaScript，不读取外部字体、脚本、样式或API，离线打开即可使用；
- 页面采用白底、细分隔线和克制强调色，不使用营销式渐变或装饰性背景，以适配审计、专利和企业评审场景。

### 15.1 单文档投影边界

`document_id`表示由输入内容确定的内容快照标识，不是原始文件名、业务标题、永久文档主键或访问控制主体。同一内容快照的多次run可以共享`document_id`，但仍保留各自`run_id`和版本记录。

逐文档投影首先按`entity_mentions.document_id`选择直接来源实体，按`relation_evidence.document_id`选择直接来源关系和证据，再为已选择关系补齐主客体端点。一个canonical实体可由多个文档共同贡献；该共享只允许实体作为当前文档关系的端点出现，不能据此遍历或加入仅由其他文档证据支持的关系。旧导入补丁缺少直接来源行时，可使用与该文档图版本绑定的contribution作为显式兼容回退，并在页面标记provenance mode；回退不得把其他文档证据复制进当前页面。

来源文档列表取自`entity_mentions`、`relation_evidence`和非系统`graph_versions`的并集，因此已补偿为空但仍有历史版本的文档也可保留一个可审计空页面。

可视化是治理解释层，不参与共识和提交判定。页面会记录所选`run_id`及registry绑定状态，但不会凭此推断缺少证据支持的`run_id–graph_version_id–operation_id`关系；同一文档含多次运行时，图和版本历史可聚合，而Agent治理详情只展示最新相关运行。当前也未加载全部schema proposal，因此不把该能力作为正式专利创新点。若产品需要跨运行联合审计，应增加显式的`(run_id, graph_version_id, operation_id)`关联索引，而不是依赖文件时间。

## 16. 存储职责

| 存储 | 事实范围 |
|---|---|
| Candidate JSONL | 兼容性对象流 |
| per-run Registry | 候选、合并、Agent、影子、策略和隔离审计 |
| Canonical Registry | 跨运行身份、证据贡献、版本、事件和活动指针 |
| Run KG | canonical commit 后的本地派生发布视图 |
| Schema Store | proposal、版本和 promotion ledger |
| Checkpoint Store | 运行恢复状态 |

## 17. 能力边界

当前明确不保证：

- 跨文档版本稳定 Mention ID；
- Evidence 之间真实统计独立；
- 影子图与任意生产数据库在业务语义上等价；
- 随机 LLM 或外部服务的完全可重复性；
- canonical store 与本地发布库的跨库原子；
- 大于阈值的全局最优或一般集合包含极小排除；
- 内容寻址凭证提供密钥身份认证、对抗性防篡改或知识真实性证明；
- 任意交错图操作都可交换回滚；
- 在线训练、自主修改模型参数或完全无人审批的 schema 演化；
- 自动拆分任意已合并 identity；
- 通用中文/英文开放域 SOTA 准确率。

这些限制是专利支持性、产品可信度和后续工程验收的共同边界。
