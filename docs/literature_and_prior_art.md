# EvoLex 论文与相邻技术综述（第二轮）

整理截止日：2026-07-31

本文说明学术方法对EvoLex创新定位的影响。专利逐限制矩阵见[第二轮现有技术与创造性攻击矩阵](../patent/prior_art_matrix.md)，逐权项判决见[严格审查报告](../patent/review_round2/reports/strict_reviewer_report.md)。本文不构成法律意见或正式查新。

## 1. 核心结论

“Agent + 联合实体关系抽取 + KG自进化”已经不是有说服力的创新表述：相关单点在联合抽取、LLM构图、schema归纳、实体/关系canonicalization、图约束修复和Agent工作流中均有大量公开。

第二轮的研究问题应改写为：

> 如何使一个来源绑定的候选KG补丁，在固定验证边界内被反事实定位、局部保留，并使验证结果与实际提交的剩余操作在并发和幂等重试下保持可重算一致？

## 2. 联合实体—关系抽取

| 工作 | 主要思想 | 对EvoLex的含义 |
|---|---|---|
| [PURE](https://aclanthology.org/2021.naacl-main.5/) | 强实体模型与关系模型流水线 | 不能声称“分开抽取必然失败”；只能针对端点身份重新生成导致的具体故障 |
| [REBEL](https://aclanthology.org/2021.findings-emnlp.204/) | 端到端生成关系三元组 | 联合/端到端三元组生成已知 |
| [TDEER](https://aclanthology.org/2021.emnlp-main.635/) | 面向重叠三元组的联合抽取 | 联合抽取不应作为主创新 |
| [E2GRE](https://aclanthology.org/2021.repl4nlp-1.30/) | 实体和关系端到端框架 | 同上 |

EvoLex的工程差异是同一批次的关系端点引用提及标识，后续直接消费提及到规范实体的映射，并先过滤关系证据引用。该差异适合做从属保护和消融实验，不足以单独承担创造性。

## 3. LLM、schema与Agent KG构建

| 工作 | 主要思想 | 对EvoLex的含义 |
|---|---|---|
| [EDC](https://aclanthology.org/2024.emnlp-main.548/) | Extract、Define、Canonicalize开放KG schema | 普通谓词规范化和schema归纳已拥挤 |
| [SAC-KG](https://aclanthology.org/2024.acl-long.238/) | schema-aware KG construction | schema约束构图不是新点 |
| [iText2KG](https://arxiv.org/abs/2409.03284) | LLM增量构图与实体对齐 | “LLM+增量KG+对齐”高度邻近 |
| [GraphJudge](https://aclanthology.org/2025.emnlp-main.554/) | 对自动构建KG进行判断 | 用模型审查图本身不足 |
| [ATOM](https://aclanthology.org/2026.findings-eacl.49/) | 原子事实、双时间和动态KG | 时间化和合并已有公开 |
| [AutoSchemaKG](https://aclanthology.org/2026.acl-long.942/) | 自动schema发现 | 动态schema不作为本案核心 |
| [AutoPKG](https://aclanthology.org/2026.findings-acl.766/) | 自动化/个性化KG构建 | 产品竞争点应落在变更控制面 |

Agent在第二轮中只是实施主体和调度机制。正式技术贡献必须落在可复现的数据结构、哈希、图依赖、查询、优化约束和事务边界上。

## 4. 查询因果与数据库repair：最危险的相邻领域

第一轮检索过度集中于“知识图谱构建”，漏掉了可能直接摧毁创造性的数据库理论。

| 工作 | 公开内容 | 对EvoLex的攻击 |
|---|---|---|
| [Meliou et al., PVLDB](https://www.vldb.org/pvldb/vol4/p34-meliou.pdf) | query lineage、actual cause、contingency、responsibility | 失败查询到原因及最小排除已有理论基础 |
| [Salimi & Bertossi, ICDT 2015](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ICDT.2015.342) | 查询原因、database repair、诊断、hitting set/vertex cover的联系 | 从约束失败到最小修复的组合动机非常强 |
| [Set repairs for data-graphs, 2022](https://arxiv.org/abs/2206.07504) | data-graph约束下subset/superset repairs | 图数据库修复并非空白 |
| [Preferred data-graph repairs, 2023](https://arxiv.org/abs/2304.00931) | 基于权重和多重集偏好的repair | 攻击带权证据损失目标 |
| [Property graph repair, 2026](https://arxiv.org/abs/2602.05503) | PG-Constraints、ILP、naive、LP-guided greedy和节点/边/标签删除 | 精确/启发式图修复已有直接邻近方法 |
| [Delta Debugging](https://arxiv.org/abs/cs/0012009) | 重复执行隔离最小失败诱因 | 攻击枚举子集和重放定位 |

因此，EvoLex不能把“失败查询→因果集合→最小删除→重放”本身包装成首次创新。可争取差异必须是：来源锚派生并冻结验证域、KG端点依赖闭包、尚未提交候选补丁的部分保留、内容寻址验证凭证及实际接受操作清单的连续耦合。

## 5. 图约束、来源和版本

- [W3C SHACL](https://www.w3.org/TR/shacl/)已经提供shape、target和验证结果；实体存在、端点完整性和唯一键属于基本约束。
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)表明provenance字段本身常规；EvoLex只有在来源锚被算法实际消费以生成冻结域和提交门时才产生差异。
- event sourcing、补偿事务、MVCC/CAS和不可变版本历史均是成熟工程思想；版本ID、日志、undo或hash不能单独建立创新。

## 6. 第二轮技术贡献的学术表述

推荐方法表述：

1. 从具有来源锚和端点依赖的KG候选操作派生原始影响域；
2. 对原始域计算摘要并在全部candidate repair replay中冻结；
3. 对失败约束的关联操作执行dependency-closed counterfactual exclusion；
4. 只把使目标失败消失的操作加入repair candidate space；
5. 在冻结域非干扰和图依赖约束下保留feasible residual subpatch；
6. 以content-addressed validation certificate绑定验证链；
7. 以commit manifest把certificate和实际accepted operation events绑定到幂等版本提交。

这不是“新repair理论”的主张，而是面向持续KG写入控制面的特定组合与系统实现。

## 7. 建议实验

### 7.1 联合抽取消融

- 相同基础模型、相同token预算下比较分步抽取与同批次提及端点；
- relation materialization recall；
- unresolved endpoint rate；
- invalid evidence reference rate；
- 每文档模型调用数和成本。

### 7.2 冻结影响域与局部保留

- 全图验证与冻结局部域的读取对象数、延迟和内存；
- 局部排除相对整补丁拒绝的有效操作保留率；
- 非冻结域相对冻结域漏检的边界对象数量；
- 不同候选规模下精确与固定点回退的质量/时间曲线。

### 7.3 反事实归因

- 人工注入端点缺失、来源缺失、重复关系键和依赖错误；
- 原因precision/recall；
- 每个失败查询的replay次数；
- 静态关联集合相对反事实原因集合的缩减比例。

### 7.4 凭证和提交清单

- 基线、域、查询关联、求解器、排除集合、接受集合、最终影子和decision篡改检出率；
- 同patch不同selection重试拒绝率；
- 证书生成/重算和清单核对开销；
- 并发stale-parent和idempotent replay测试。

## 8. 论文和专利叙事边界

可以说：

> EvoLex实现了一个来源约束的KG候选补丁控制面，在冻结影响域内验证反事实失败操作、局部保留剩余子补丁，并用可重算凭证和提交清单防止验证—提交错配。

不应说：

- 首次联合抽取实体和关系；
- 首次用Agent让KG自进化；
- 首次进行知识图谱修复；
- 证明现实世界因果或知识真实性；
- 任意规模求得全局最小修复；
- 当前项目回归语料达到开放域SOTA。
