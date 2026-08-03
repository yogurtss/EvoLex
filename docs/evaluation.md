# EvoLex 0.3 评测方法与结果

## 1. 结论

仓库提供了一套可重复、无网络的工程回归，用来证明联合端点引用、双层规范化、证据补丁和演化安全门确实在代码中可执行。

2026-07-31 的当前运行结果：

| 指标 | Legacy separate | Joint + Agent |
|---|---:|---:|
| Entity F1 | 0.0426 | 1.0000 |
| Relation F1 | 0.0000 | 1.0000 |
| 关系端点对 recall | 0.0000 | 1.0000 |
| Endpoint ID validity | 1.0000 | 1.0000 |
| Relation evidence-contract coverage | 0.0000 | 1.0000 |
| Joint materialization rate | 0.0000 | 1.0000 |
| Publish rate | 0.0000 | 1.0000 |

联合路径还在声明的别名组上把2个表面身份合并为1个canonical identity；影子门、确定性重放、因果验证凭证、提交清单及历史补偿探针在该次运行中均通过。

这些数字只能解释为 **本仓库固定样例的回归结果**。它们不能表示开放域泛化性能、公开 benchmark 排名、SOTA、专利新颖性或自由实施结论。

原始交付：

- [Markdown 报告](../outputs/demo/benchmark/patent_benchmark_report.md)
- [完整 JSON 报告](../outputs/demo/benchmark/patent_benchmark_report.json)
- [交互式演化控制台](../outputs/demo/evolex_dashboard.html)
- [Gold corpus](../benchmarks/patent_joint_kg_corpus.json)

## 2. 评测对象

固定 corpus 含 8 条技术句子，覆盖：

- 直接关系端点；
- `API Gateway` / `API GW` 声明别名；
- `requires → depends_on` 谓词规范化；
- 多种普通关系谓词；
- 关系 Evidence；
- canonical 多版本提交；
- 补偿回滚。

全部运行使用 deterministic heuristic，不访问 LLM 或外部网络。

## 3. 对照协议

### 3.1 Legacy separate

```text
HeuristicExtractor
  → legacy semantic atoms
  → fixed system pipeline
  → post-resolution relation fallback
```

### 3.2 Joint + Agent

```text
HeuristicTypedExtractor
  → one-batch mention/relation/evidence
  → mention-ID endpoint resolution
  → entity/relation canonicalization
  → Agent governance
  → evidence contract
  → frozen impact-domain shadow gate
  → dependency-closed counterfactual attribution
  → causal validation certificate
  → commit manifest
  → canonical commit
```

两个 variant 同时改变了 **extractor** 和 **pipeline**。因此当前对比没有识别“联合抽取架构”本身的独立因果效应。8 条文本也刻意匹配 heuristic 的实体和谓词规则，结果会高估对类似模板的适配程度。

正确表述是：

> 在项目自有的固定回归样例上，联合 + Agent 完整路径能端到端保留提及级关系端点和证据，并完成声明的 canonical/演化治理动作；历史兼容路径不能完成同一任务。

不正确表述包括：

- “联合抽取在所有领域把 Relation F1 提升 100%”；
- “EvoLex 达到 100% 准确率”；
- “Agent 一定优于 pipeline”；
- “结果证明专利具有新颖性或创造性”。

## 4. 指标定义

### 4.1 实体与关系

Gold 与预测均在文档范围内比较：

```text
Precision = TP / Predicted
Recall    = TP / Gold
F1        = 2PR / (P + R)
```

实体使用归一化文本；关系使用 `(subject, canonical_predicate, object)`。

### 4.2 端点

- `relation_endpoint_pair_accuracy`：Gold 主宾端点对被正确恢复的 recall；
- `endpoint_id_validity`：预测关系两端均能解析到局部实体的比例；
- `joint_materialization_rate`：最终关系来自联合候选物化的比例。

Legacy 的 endpoint validity 为 1.0 但 Relation F1 为 0，是因为该 variant 没有产生错误 ID 的关系，而不是成功提取了关系。端点有效率必须与关系数量和 recall 联合解释。

### 4.3 证据

`relation_evidence_contract_coverage` 要求关系同时具有：

- Evidence 文本；
- Evidence ID；
- segment ID。

该指标检查字段闭合，不验证来源之间的事实独立性，也不验证 Evidence 是否足以支持任意外部语义主张。

### 4.4 Identity

别名指标只针对 corpus 中显式声明的 alias group，比较表面形式数量与 canonical identity 数量。它不是通用实体消歧 benchmark。

### 4.5 演化安全

- Shadow gate pass：当前补丁的自动结构不变量通过；
- Deterministic replay：同一内存 baseline 上，同一纯函数补丁执行两次哈希一致；
- Counterfactual attribution：排除操作及其端点依赖闭包后，目标失败在同基线重放中消失；
- Certificate verified：基线、冻结原始影响域、查询原因、求解器、排除/接受操作、最终影子及门结果重算一致；
- Consensus accept：Evidence、replay、non-interference、invariant、utility 和 certificate 六项布尔条件全部为真；`required_quorum=5`仅是审计统计，不能覆盖任一硬条件失败；
- Commit manifest match：提交前再次重算凭证，并要求 decision/evaluation/certificate 的接受操作一致；随后核对 patch、parent、接受操作摘要和凭证ID与持久化提交清单一致；
- Rollback probe：新增版本的实体、关系和 Evidence 可由追加式补偿恢复到 probe 前计数，历史增加一个补偿版本。

上述测试不等同于：

- 随机 LLM 完全复现；
- 真实分布式数据库故障恢复；
- 形式化程序验证；
- 任意操作顺序都满足交换律。

## 5. 可重复运行

```bash
PYTHONPATH=src python -m evolex.cli eval patent \
  --output-dir outputs/demo/benchmark
```

也可以指定另一个同结构 corpus：

```bash
PYTHONPATH=src python -m evolex.cli eval patent \
  --corpus path/to/gold.json \
  --output-dir outputs/custom-benchmark
```

生成可视化：

```bash
PYTHONPATH=src python -m evolex.cli visualize \
  --canonical-dir outputs/demo/benchmark/joint_agent/canonical \
  --registry-dir outputs/demo/benchmark/joint_agent/registry \
  --schema-dir outputs/demo/benchmark/joint_agent/schema_candidates \
  --output outputs/demo/evolex_dashboard.html
```

上述`visualize`命令继续生成一个跨文档单页。生成静态总图、索引和逐文档页面的完整bundle：

```bash
PYTHONPATH=src python -m evolex.cli visualize-bundle \
  --canonical-dir outputs/demo/benchmark/joint_agent/canonical \
  --registry-dir outputs/demo/benchmark/joint_agent/registry \
  --schema-dir outputs/demo/benchmark/joint_agent/schema_candidates \
  --output-dir outputs/demo/evolex-visualization
```

预期生成`index.html`、`evolex-global-kg.html`和`documents/evolex-doc-*.html`。这些页面完全自包含，不需要网络或运行中的EvoLex服务，采用白底严肃风格。总图应包含全部活动关系及证据；单文档页按`entity_mentions`和`relation_evidence`的`document_id`隔离，只补齐本页关系端点，共享实体不得把其他文档关系带入当前页。

## 6. 回归与单元验证覆盖

除 corpus 评测外，测试套件覆盖：

- 联合响应 ID 命名空间和 Claim 唯一 ID；
- 无效关系端点与 canonical endpoint collapse；
- Evidence 先过滤、Claim 后验证；
- Evidence先过滤后同时校验Claim和RelationCandidate，记录无效关系证据引用；
- Unicode 实体和 complete-link 防过合并；
- 多值谓词与功能型冲突的一致定义；
- 谓词别名与 Schema gap 一致；
- 多未知 schema symbol 分别提案；
- schema 固定、并发 promotion 无丢更新、晋升/阻止终态竞争互斥、proposal replay 幂等；
- Agent 上游重跑导致下游失效；
- 异常 Agent 直接提议发布时的代码级依赖门与发布节点复核；
- 负效用共识拒绝；
- 由证据、端点依赖和基线邻接派生原始影响域，以及不超过 16 个反事实原因候选时在定义搜索空间内精确求解待排除集合；
- 原始影响域在局部排除后保持冻结，并另记接受操作声明域；
- 逐关联操作的依赖闭包反事实原因验证；
- 基线、查询关联、求解器、排除集合、最终影子和decision选择篡改均使凭证失败；
- 17原因候选进入带`single_deletion_local_minimum_not_global`标记的固定点回退；
- stale canonical patch 拒绝及 patch 幂等；
- 同patch不同接受集合或凭证的提交清单重试拒绝；
- 同一三元组不同限定信息保持不同关系并保存源断言快照；
- canonical commit 先于本地发布；
- 策略授权不提前标记 `published`、运行级发布失败整体回滚及同运行重试不重复；
- 候选注册快照失败重试的替换语义，并保留早期 typed candidates；
- 贡献级旧版本回滚、后续删除保护和交错恢复；
- checkpoint 最近 run 选择、Agent step 单调、低收益计数和 runtime/pipeline 继承；
- 固定 `phase3` 从 policy 或隔离 quality-review 检查点恢复时正确消费分支出边；
- 完成态自定义 extractor 直接恢复，以及进行中未知 extractor 的 fail-closed。
- `visualize`单页向后兼容，以及`visualize-bundle`生成固定索引、总图和安全命名的逐文档HTML；
- 静态页面无外部资源和网络依赖，总图包含全部对象，逐文档页不会混入其他文档关系或证据；
- 空存储、已补偿为空的文档和同一内容快照的多run不会使批量导出失败或覆盖其他文档页面。

最终全量测试结果以交付时的 `pytest -q` 输出为准。

## 7. 申请前/商用前应补的实验

### 7.1 架构消融

至少形成四组同模型、同 prompt、同语料的对照：

1. Separate entity/relation；
2. Joint extraction only；
3. Joint + entity canonicalization；
4. Joint + dual canonicalization + evolution governance。

这才能分别估计联合抽取、实体合并、关系合并和治理链的增量。

### 7.2 公开数据集

根据目标领域选择公开 joint entity-relation extraction 数据集，并冻结：

- train/dev/test 划分；
- 模型版本与温度；
- prompt；
- schema；
- 随机种子；
- 失败样例。

公开 benchmark 结果应与 REBEL、PURE、TDEER、E2GRE 等论文按相同评价口径比较，不能把项目自有 heuristic 结果直接放在同一排名表中。

### 7.3 Identity benchmark

构造 hard negative：

- 同名不同实体；
- 类型相同但上下文不同；
- A≈B、B≈C、A≉C；
- 中英文/缩写/产品版本；
- 功能型关系真冲突与多值关系非冲突。

至少报告 pairwise precision/recall、cluster B³ 或 CEAF 类指标及过合并率。

### 7.4 演化故障注入

增加：

- canonical 事务每个写入点故障；
- stale parent 并发；
- 17+ 因果操作 fallback；
- 多轮交错 upsert/delete/rollback；
- registry 或本地发布失败；
- LLM 超时、截断 JSON、重复 ID、未知端点。

### 7.5 治理链篡改与边界评测

申请前应把当前单元验证扩展为可归档的故障注入矩阵，并至少报告以下项目：

| 项目 | 注入或对照 | 通过标准 |
|---|---|---|
| 冻结影响域 | 在完整补丁、逐操作反事实重放、求解器重放和最终剩余子补丁重放中记录域摘要 | 各阶段使用同一原始影响域摘要；接受操作声明域可另记，但不能替换验证边界 |
| 六项 AND 门 | 分别翻转 Evidence、replay、non-interference、invariant、utility、certificate 结果 | 任一项为假均 `hold` 或隔离；quorum 统计不得覆盖失败项 |
| 凭证篡改阻断 | 分别修改基线、查询归因、求解模式、排除/接受集合、最终影子或门结果 | 判定或提交阶段重算不一致，canonical 版本不得前移 |
| 提交清单绑定 | 对同一 patch 分别重放“同选择同凭证”和“不同选择或不同凭证” | 前者幂等返回同一版本；后者拒绝，不得返回与本次选择不对应的旧版本 |
| 求解边界 | `k<=16` 与穷举真值比对；`k>16` 重复运行固定点单删除回退 | 小空间在定义搜索空间内与精确结果一致；大空间结果确定、可行且无单项可继续删除，并标记 `single_deletion_local_minimum_not_global`，不报告全局最优或一般集合包含极小 |

报告应保存候选操作、冻结域摘要、反事实检查记录、凭证ID、提交清单摘要、预期结果和实际结果；不能只报告最终 `pass/fail`。

### 7.6 商业指标

在客户历史数据上测量：

- 每千文档的人工修正分钟数；
- 关系端点 orphan rate；
- duplicate identity rate；
- 错误发布率与回滚时间；
- 每次变更的审计取证时间；
- 单文档模型调用成本和 P95 延迟。

只有经过客户基线和对照试点后，才能把这些指标换算为 ROI。
