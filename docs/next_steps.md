# EvoLex 后续路线

适用基线：0.3.0

## 已完成

- 同一片段一次主要响应联合输出 Mention、RelationCandidate、Claim 和 Evidence；
- Relation 端点引用同响应 Mention ID，并在片段汇总时命名空间化；
- Evidence 先过滤、Claim 后验证；
- Mention 到实体的可审计解析；
- 同类型、provenance-gated、complete-link 实体规范化；
- 谓词和 relation identity 规范化、Evidence 聚合及功能型冲突；
- Agent 工具调度、效用记录、依赖失效和 revision；
- EvidenceContract 化 upsert 补丁；
- 由 Evidence、端点依赖和基线邻接派生并冻结原始 ImpactDomain，接受操作声明域仅作记录；
- 影子不变量、query-to-operation 静态关联、同基线反事实原因验证和冻结域外投影检查；
- 反事实原因候选不超过 16 时在定义搜索空间内精确枚举；超过 16 时采用确定性固定点单删除回退，仅保证单删除局部最小，并明确标记不保证全局最优或一般集合包含极小；
- Evidence/replay/non-interference/invariant/utility/certificate 六项布尔条件全部 AND 通过；`required_quorum=5`仅作为审计统计，不能覆盖任一硬门失败；
- 判定和提交阶段重算因果验证凭证并核对 decision/evaluation/certificate 接受操作一致，存储层再核对提交清单；
- pre-commit publish-confidence gate；
- canonical stale-parent 检查、patch 幂等、版本/事件/活动指针同事务；
- commit-before-local-publish；
- entity/alias/relation contribution 和 delete tombstone；
- later-change-aware、交错顺序可重算的追加式补偿；
- run-start schema 固定、独立 symbol proposal、并发 observation/promotion 无丢更新；
- checkpoint runtime/pipeline 继承与错模式拒绝；
- 全局活动图及逐`document_id`来源投影的自包含静态HTML，并提供离线索引、筛选、证据和治理审计；
- 8 文档无网络工程回归；
- 专利初筛、保护策略和完整申请前文档包。

## P0：正式申请前

### 1. 专业 claim chart

由代理师逐项核对至少：

- CN120179832A
- CN121787546A
- US12423523B2
- US12135740B1
- US20260004204A1
- US20230087667A1
- US10915577B2
- US11531705B2
- US7873605B2

输出 family、priority、法律状态、独权要素映射及组合显而易见性风险。

### 2. 同模型消融

固定模型、prompt、schema、语料和温度，只改变：

1. entity/relation separate；
2. joint only；
3. joint + entity canonicalization；
4. joint + dual canonicalization；
5. full evidence-governed evolution。

当前 8 条回归同时改变 extractor 与 pipeline，只能作工程验证。

### 3. 公开数据集

选择公开 joint entity-relation extraction benchmark，报告：

- Entity/Relation P-R-F1；
- overlapping relation；
- orphan endpoints；
- Evidence precision；
- 调用次数、延迟和成本。

### 4. 治理链故障注入

将现有单元测试扩展为可随申请材料归档的独立报告，至少覆盖：

- 原始影响域摘要在完整补丁、反事实重放、排除集合求解和最终重放间保持冻结；
- 分别篡改基线、查询归因、求解结果、排除/接受集合、最终影子或门结果时，凭证重算失败且补丁不得提交；
- 逐一翻转六项硬门中的任一条件，验证即使 quorum 统计达标也必须拒绝；
- 同 patch、同接受操作和同凭证的提交清单可幂等返回；同 patch 但接受操作或凭证变化时必须拒绝；
- `k<=16` 与穷举真值核对，`k>16` 只验证确定性、可行性和单删除局部最小，不报告全局最优。

### 5. 发明事实确认

- 发明人、申请人；
- 首次完成与首次公开日期；
- GitHub、论文、答辩、客户演示；
- 第三方代码/数据许可证；
- 是否需要保密审查、PCT 或海外布局。

## P1：生产试点

### 1. 人工审批

为以下动作增加 review queue：

- schema promotion；
- functional relation conflict；
- high-risk policy；
- 大空间待排除集合固定点单删除 fallback；
- contribution/tombstone 异常；
- canonical 已提交但派生发布失败。

### 2. 跨存储投递可靠性

canonical 是事实源；增加：

- transactional outbox；
- 派生发布幂等键；
- 重试与死信；
- canonical—run KG 对账；
- dashboard 告警。

当前不宣称跨存储原子。

### 3. 权限与隐私

- OIDC/RBAC；
- tenant isolation；
- Evidence 字段级加密；
- 密钥管理；
- 审计日志签名；
- retention/deletion policy；
- 外部模型数据驻留控制。

### 4. 领域不变量

把当前结构不变量扩展为客户配置：

- domain/range；
- cardinality；
- temporal consistency；
- unit compatibility；
- 产品/法规特定 query；
- 受控人工豁免。

## P2：算法增强

### 1. Identity split

新增人工批准的 cluster split/unmerge：

- 原贡献分区；
- 关系重定向；
- Evidence 保留；
- 影响域验证；
- 补偿版本。

在完成前，不对外声称自动拆分。

### 2. 大空间优化器

将 `>16` fallback 替换或补充为：

- ILP/MaxSAT；
- branch-and-bound；
- 图分解；
- 可验证上下界；
- time budget 与最优性 gap。

### 3. Action-aware delete planning

当前 Agent 自动 planner 生成 Evidence 化 upsert；repository 支持 delete/tombstone 与版本补偿，但 shadow planner 不覆盖任意普通 delete patch。

若要扩大保护和产品能力，应增加：

- action-aware shadow apply；
- 删除端点/孤儿/级联不变量；
- delete ImpactDomain；
- delete 的因果排除与剩余子补丁求解；
- mixed upsert/delete property tests。

### 4. 跨文档 temporal identity

研究稳定 identity，而不是复用运行内 Mention ID：

- document revision mapping；
- temporal entity state；
- same-as / split-from / supersedes；
- Evidence validity interval。

## P3：平台化

- Web/API 控制面；
- Neo4j/RDF/Property Graph adapters；
- Kafka/Pulsar ingestion；
- model routing and cost budgets；
- tenant-specific rules；
- CI checks for schema/graph pull requests；
- governance analytics；
- plugin SDK。

## 验收原则

每项新能力必须同时具备：

1. 数据契约；
2. 失败语义；
3. 审计记录；
4. 可重复测试；
5. 回滚/补偿方案；
6. 文档中的非保证边界；
7. 若进入权利要求，则具有源码、测试和附图证据。
