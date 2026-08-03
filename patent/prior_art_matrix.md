# EvoLex 第二轮现有技术与创造性攻击矩阵

检索基准日：2026-07-31  
目标：为中国发明专利申请前技术检索、创造性论证和代理师claim chart提供初稿  

> 本矩阵是申请前初筛，不是正式查新、法律状态意见、新颖性/创造性结论或自由实施意见。是否构成现有技术取决于本案有效申请日、优先权、公开日、抵触申请规则及具体权利要求解释。发明人的最早公开日尚待确认。

## 1. 严格结论

尚未发现一份单一文献明确公开第二轮权利要求1的全部连续限制，因此字面新颖性仍可能争取。但创造性风险为“中高”：联合抽取、实体/关系canonicalization、局部影响域、影子图、查询原因、最小数据库repair、依赖补偿、版本事务和幂等分别已有强现有技术。

最可能形成区别的不是任何单个名词，而是以下强制耦合：

1. 候选更新操作带有机器消费的来源锚、声明影响对象和关系端点依赖；
2. 上述数据与固定父版本基线邻接共同生成原始影响域，并在所有局部排除重放中冻结；
3. 对查询关联操作逐个执行端点依赖闭包排除和同基线重放，仅在目标失败消失时形成反事实原因记录；
4. 在反事实候选空间内求待排除集合，并在冻结域下重验剩余子补丁；
5. 内容寻址凭证绑定基线、域、查询原因、求解器、排除/接受操作和最终影子；
6. 判定、评估和凭证的接受操作必须一致，提交清单再把实际接受操作摘要和凭证ID绑定到幂等图版本事务。

## 2. 主要专利文献

| 文献 | 时间信息 | 最接近公开 | 对本案攻击 | 建议区别 |
|---|---|---|---|---|
| [US20120197862A1](https://patents.google.com/patent/US20120197862A1/en) | 优先权2011-01-31；公开2012-08-02 | 关系对象以MentionId引用端点 | 削弱“提及ID作为关系端点”单点新颖性/创造性 | 联合抽取仅放从权；强调证据引用失败和后续补丁闭环 |
| [US7873605B2](https://patents.google.com/patent/US7873605B2/en) | 优先权2007-01-29；A1公开2008-07-31 | 读写依赖、causal transaction set、选择性补偿事务 | 直接攻击依赖闭合和选择性补偿 | 区分尚未提交候选图操作的反事实排除、冻结证据域和凭证绑定的部分提交 |
| [US8849874B2](https://patents.google.com/patent/US8849874B2/en) | 优先权2009-04-30；A1公开2012-05-10 | ontology change operator和版本演进 | 攻击schema/ontology演进和版本日志 | schema移出核心；只保留说明书/分案 |
| [US20230087667A1](https://patents.google.com/patent/US20230087667A1/en) | 优先权2021-09-21；公开2023-03-23 | 实体和关系提及canonicalization；complete linkage | 直接削弱旧权4及双层规范化 | complete-link仅作窄从权；以跨簇成员对和来源门表述 |
| [US11531705B2](https://patents.google.com/patent/US11531705B2/en) | 公开/授权早于基准日 | 新文档作为实体关联证据更新self-evolving KG | 攻击宽泛“证据支持自进化KG” | 避免以Agent、自进化或证据展示为创新中心 |
| [CN120179832A](https://patents.google.com/patent/CN120179832A/en) | 优先权/申请2025-05-19；公开2025-06-20 | LLM实体关系抽取、对齐、差异、create/modify/delete、sandbox、JSON diff、事务组、快照和回滚 | 覆盖旧权1大部分宏观流程，是最强KG聚合攻击 | 强调冻结域、反事实验证、凭证和实际接受操作清单 |
| [CN121787546A](https://patents.google.com/patent/CN121787546A/en) | 申请2025-12-30；公开2026-04-03 | 增量实体关系单元、临时ID校验、实体中心影响域、局部子图、去重、融合和版本 | 攻击影响域、实体合并、局部更新和证据融合 | 仅主张来源锚被机器消费并贯穿冻结验证边界；先核本案有效申请日 |
| [US20230169059A1](https://patents.google.com/patent/US20230169059A1/en) | 优先权2021-12-01；公开2023-06-01 | KG子区域、局部性、相互依赖、snapshot和change layer | 攻击局部影响范围及change layer | 区分反事实原因和凭证绑定的剩余子补丁提交 |
| [US20260004204A1](https://patents.google.com/patent/US20260004204A1/en) | 优先权2023-12-11；公开2026-01-01 | original/test ontology map、生成输出比较、loss/cost阈值、通过后更新 | 强攻影子图、基线/测试执行和阈值门 | 冻结来源影响域、查询—操作反事实和提交清单是必要区别 |
| [US12135740B1](https://patents.google.com/patent/US12135740B1/en) | 优先权2023-12-20；公开/授权2024-11-05 | 同一查询跨图版本执行、性能/精度比较、定位差异节点边并回退 | 攻击跨版本比较与差异回退 | 强调未提交候选操作、端点依赖闭包和内容寻址凭证 |
| [US20250342369A1](https://patents.google.com/patent/US20250342369A1/en) | 优先权2024-05-03；公开2025-11-06 | KG变化历史及undo信息 | 攻击宽泛版本历史与undo | 权12聚焦贡献、墓碑、新生命周期及安全跳过；考虑分案 |

## 3. 主要论文与标准

| 文献 | 已公开思想 | 对本案影响 |
|---|---|---|
| [REBEL, Findings of EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.204/) | 端到端关系抽取 | 联合抽取不能单独承担核心创造性 |
| [TDEER, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.635/) | 实体与关系联合建模 | 同上 |
| [EDC, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.548/) | 开放KG构建中的实体/关系schema归纳与canonicalization | 动态schema和双层规范化空间拥挤 |
| [Meliou et al., PVLDB](https://www.vldb.org/pvldb/vol4/p34-meliou.pdf) | query lineage、actual cause、contingency和responsibility | 强攻“失败查询→原因→最小排除” |
| [Salimi & Bertossi, ICDT 2015](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ICDT.2015.342) | 查询原因、数据库repair、诊断、hitting set/vertex cover之间的转换 | 是从约束失败到repair的最强理论桥梁 |
| [On the complexity of finding set repairs for data-graphs, 2022](https://arxiv.org/abs/2206.07504) | data-graph约束下subset/superset repair | 证明图修复不是空白领域 |
| [Data-graph repairs: the preferred approach, 2023](https://arxiv.org/abs/2304.00931) | 权重和多重集偏好的图repair | 攻击带权排除目标 |
| [Repairing Property Graphs under PG-Constraints, 2026](https://arxiv.org/abs/2602.05503) | property graph约束repair；ILP、naive和LP-guided greedy；节点/边/标签删除 | 强攻图约束修复和启发式/精确求解组合 |
| [Delta Debugging](https://arxiv.org/abs/cs/0012009) | 通过重复执行隔离最小失败诱因 | 攻击子集枚举和重放隔离 |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) | 来源与活动/实体关系模型 | provenance字段本身常规 |
| [W3C SHACL](https://www.w3.org/TR/shacl/) | RDF图的shape、target和验证结果 | 结构查询/不变量本身常规 |

## 4. 第二轮权利要求1逐限制claim chart

| 新权1限制 | 可组合现有技术 | 风险 | 当前最窄抗辩点 |
|---|---|---:|---|
| 固定父版本基线及来源绑定操作级候选补丁 | CN120179832A、PROV-O、US20230169059A1 | 中高 | 来源锚、声明对象和端点依赖被同一后续算法消费，而非仅记录 |
| 从来源锚、声明对象、端点依赖和基线一跳邻接派生原始影响域并冻结摘要 | CN121787546A、US20230169059A1 | 高 | 局部排除重放不允许缩小原始域；同时记录较小接受操作域但不替换验证边界 |
| 影子结构查询及冻结域外投影摘要 | CN120179832A、US20260004204A1、US12135740B1、SHACL | 高 | 查询结果携带候选操作关联并进入后续反事实与凭证链 |
| 逐关联操作依赖闭包排除、同基线重放、目标失败消失才认定反事实原因 | Meliou、Salimi-Bertossi、US7873605B2、Delta Debugging | 高 | KG端点依赖闭包、冻结来源域和未提交候选操作的具体结合 |
| 反事实候选空间内确定待排除集合并重验剩余子补丁 | database/data-graph/property-graph repair文献 | 高 | 目标是只提交未提交候选补丁的剩余操作，而非修复已写数据库或生成事后补偿事务 |
| 内容寻址凭证绑定基线、域、查询原因、求解器、排除/接受操作和最终影子 | 普通hash manifest、审计日志可作为常识组合 | 中 | 一份可重算清单贯穿判定与提交，且字段变化已有攻击性测试 |
| 三方接受ID一致及提交清单绑定的版本事务 | 常规CAS/幂等/event sourcing | 中 | 同一完整patch但不同接受集合/凭证不得命中旧版本；绑定实际graph_events |

## 5. 三组显而易见性组合

### 组合A

`CN120179832A + CN121787546A + US7873605B2`

可覆盖联合抽取、对齐、影响域、sandbox、事务、版本和依赖补偿。抗辩必须依赖冻结验证边界、同基线反事实验证、内容寻址凭证和提交清单四者的相互制约。

### 组合B

`US20260004204A1 + US12135740B1 + Salimi/Bertossi + Delta Debugging + SHACL`

可形成“测试图→查询差异/约束失败→原因→最小repair→重放→通过后采用”的完整动机。KG或Agent标签不足以建立创造性。

### 组合C

`US20120197862A1 + US20230087667A1 + US20230169059A1 + PROV-O`

可覆盖mention端点、双层canonicalization、complete-link、来源和局部change layer。联合抽取与规范化必须保持从属地位。

## 6. 不宜宣传为核心创新的内容

- “Agent自动完成KG自进化”；
- “实体和关系一起抽取”；
- “complete-link合并同类实体”；
- “noisy-OR融合置信度”；
- “影子图验证后达到阈值即发布”；
- “动态schema”；
- “知识图谱可视化”；
- “记录版本、日志和undo”。

这些内容可以说明产品能力、作为窄从权或形成分案，但不应单独支撑主权项创造性。

## 7. 正式申请前检索任务

1. 以新权1七组限制逐项检索CNIPA、WIPO、EPO、USPTO及非专利文献，而非只检索“Agent KG”。
2. 对CN120179832A、CN121787546A、US20260004204A1、US12135740B1、US7873605B2做family、优先权和全文权项核对。
3. 扩展关键词：`content-addressed validation manifest`、`partial patch commit`、`subset commit`、`counterfactual operation attribution`、`frozen impact scope`、`causal repair certificate`、`idempotency accepted subset`。
4. 确认本项目最早公开日期；只有在有效申请日前公开的文献通常才可按相应规则评价现有技术，另需考虑抵触申请。
5. 由中国专利代理师根据正式检索决定：权12是否保留本案、作为并列独权，或拆分为版本补偿分案。
