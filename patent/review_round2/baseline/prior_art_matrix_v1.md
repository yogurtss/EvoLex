# EvoLex 论文与专利现有技术初步矩阵

状态：供发明人及专利代理师复核  
检索截止：2026-07-31

本文是工程阶段的公开资料初筛，不是正式查新、无效检索、FTO 或可专利性意见。申请前应由专利代理师核对专利族、优先权、法律状态、说明书全文和独立权利要求，并形成逐项 claim chart。

## 一、论文对比

| 文献 | 已公开的主要方向 | 与本项目重合 | 本案不应依赖的单点 | 本案连续链中的差异位置 |
|---|---|---|---|---|
| [PURE, NAACL 2021](https://aclanthology.org/2021.naacl-main.5/) | 实体与关系抽取的流水式方法 | 实体、关系及端点识别 | “先抽实体后抽关系”本身 | 同响应提及端点继续进入证据契约、影响域和补偿 |
| [REBEL, EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.204/) | 端到端关系抽取与三元组生成 | 联合或端到端抽取 | “一次生成实体关系”本身 | 提及标识命名空间、端点失败审计和提交控制链 |
| [TDEER, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.635/) | 三元组抽取及实体—关系交互 | 联合建模和重叠三元组 | “提高联合抽取准确率” | 规范对象被转换为操作级证据契约而非直接三元组输出 |
| [E2GRE, RepL4NLP 2021](https://aclanthology.org/2021.repl4nlp-1.30/) | 全局—局部实体图关系抽取 | 图结构辅助关系抽取 | “图增强关系抽取” | 影响域用于写图前结构验证和补偿，不是抽取表示层 |
| [EDC, EMNLP 2024](https://aclanthology.org/2024.emnlp-main.548/) | 开放 KG 构建中的抽取、定义与规范化 | 实体和关系规范化 | “LLM 自动 canonicalization” | complete-link 来源门、关系身份谱系及版本贡献 |
| [SAC-KG, ACL 2024](https://aclanthology.org/2024.acl-long.238/) | schema-aware KG 构建 | schema 约束和抽取 | “使用 schema 改善 KG” | 运行时 schema 固定、提议累积与事务晋升 |
| [iText2KG, arXiv 2024](https://arxiv.org/abs/2409.03284) | 大模型驱动的增量文本到 KG | 增量构建、实体和关系对齐 | “增量构建 KG” | 证据派生影响域、因果查询和依赖闭合补偿 |
| [GraphJudge, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.554/) | 对图构建或图事实进行判定 | 判定器/Agent 检查 | “用评审模型判断 KG” | 五类技术硬门的机器输入来自同一补丁回放结果 |
| [ATOM, Findings of EACL 2026](https://aclanthology.org/2026.findings-eacl.49/) | 文本原子事实、双时间建模和并行合并的动态时态 KG | 原子化更新与动态 KG | 不能把该文概括为 Agent/ontology 方法 | 本案是证据补丁的影响域、失败归因和补偿提交 |
| [AutoSchemaKG, ACL 2026](https://aclanthology.org/2026.acl-long.942/) | 自动 schema 发现/构建 | schema 自动化 | “自动发现 schema” | observation 与 promotion 分离、运行固定和并发父版本校验 |
| [AutoPKG, Findings of ACL 2026](https://aclanthology.org/2026.findings-acl.766/) | 自动化专业知识图谱构建 | 自动 KG 工作流 | “多阶段自动 KG” | 可执行证据契约到 canonical 版本事务的连续数据依赖 |
| [DIAL-KG, arXiv 2026](https://arxiv.org/abs/2603.20059) | 交互式或迭代式 KG 构建 | Agent/迭代改进 | “Agent 迭代 KG” | query-to-operation 归因与受约束补偿，而非仅重新生成 |

结论：联合抽取、规范化、Agent、动态 schema 和增量 KG 均已拥挤。本案不宜主张任何一个孤立单点的新颖性。

## 二、专利对比

| 公开文本 | 经核对的主要公开内容 | 风险 | 本案建议区分限定 |
|---|---|---|---|
| [CN120179832A](https://patents.google.com/patent/CN120179832A/zh) | 动态 KG、联合三元组抽取、实体对齐、沙箱、JSON diff、两阶段提交、快照及回滚 | 很高 | 证据契约直接生成影响域与查询；失败查询带因果操作标识；只提交补偿后剩余操作；不主张跨库两阶段提交 |
| [CN121787546A](https://patents.google.com/patent/CN121787546A/zh) | 影响域增量更新、同类型去重、关系转移、证据/信任冲突和原子/WAL | 很高 | 影响域由操作契约、端点和基线一跳依赖生成，并连续用于域外投影、归因和补偿 |
| [CN121835863A](https://patents.google.com/patent/CN121835863A/zh) | Agent 三元组抽取及写回 | 高 | 不以 Agent 抽取或写回为中心，限定补丁控制链和硬门 |
| [US12423523B2](https://patents.google.com/patent/US12423523B2/en) | 基于命名实体生成语义三元组，并用文档查询与分类器验证关系目标 | 高 | 不把其宽泛写成一般联合抽取；本案端点引用同响应提及标识并进入补丁治理 |
| [US10839021B2](https://patents.google.com/patent/US10839021B2/en) | 实体提及或关系端点识别 | 中高 | 片段命名空间化标识与后续证据契约、影响域的强制连接 |
| [US12314666B2](https://patents.google.com/patent/US12314666B2/en) | 提及、实体对或关系候选处理 | 中高 | 端点失败审计、双身份规范和图变更控制链 |
| [US20230087667A1](https://patents.google.com/patent/US20230087667A1/en) | 实体/关系归一化 | 高 | same-type complete-link 来源门、关系证据谱系与版本贡献组合 |
| [US10915577B2](https://patents.google.com/patent/US10915577B2/en) | 谓词映射或关系聚类 | 中高 | 规范关系键、证据有界聚合、功能性冲突和可逆身份假设 |
| [US11531705B2](https://patents.google.com/patent/US11531705B2/en) | 自演进知识图谱 | 高 | 避免宽泛“self-evolving KG”；限定证据影响域、因果查询、补偿及事务链 |
| [US12135740B1](https://patents.google.com/patent/US12135740B1/en) | 图版本和版本间查询/比较 | 高 | 版本贡献、later-delete 墓碑及按目标版本追加补偿 |
| [US20260004204A1](https://patents.google.com/patent/US20260004204A1/en) / [US12614124B2](https://patents.google.com/patent/US12614124B2/en) | 图扰动、测试图、损失和晋升 | 高 | 影子查询由证据契约及影响域生成，并输出因果操作用于补偿 |
| [US20250342369A1](https://patents.google.com/patent/US20250342369A1/en) | 使用第二 KG/RDF-star 保存第一 KG 的变更历史，并可返回 undo 信息 | 高 | 不称其为“补偿更新”；本案限定贡献重算、后续墓碑和新生命周期 |
| [US7873605B2](https://patents.google.com/patent/US7873605B2/en) | 通用补偿事务 | 中高 | 补偿目标特定于图操作、证据损失、影响域和实体—关系依赖闭包 |

## 三、建议的新颖性/创造性论证单元

不建议逐一争论以下单点：

- 联合实体—关系抽取；
- 使用 Agent；
- 实体消歧或谓词归一；
- 沙箱或影子图；
- 图版本或回滚；
- schema 自动扩展。

建议把最小可论证单元写成：

```text
同响应证据锚定提及端点
→ 操作级证据契约
→ 由契约和端点依赖派生影响域
→ 由影响域生成带因果操作标识的查询
→ 对因果候选形成实体—关系依赖闭包
→ 在不变量和域外投影约束下选择补偿子集
→ 只把补偿后剩余操作提交为规范图版本
```

技术效果链应对应为：减少端点身份丢失；保持规范化证据谱系；在提交前限定验证边界；定位失败操作；保留未受影响更新；避免不合格补丁进入规范图。

## 四、正式检索任务

代理师应至少完成：

1. 上述中国和美国专利的 family、priority 和法律状态核对；
2. 对 CN120179832A、CN121787546A、US12423523B2、US12135740B1 和 US20260004204A1 做独立权利要求拆解；
3. 按“evidence contract / provenance-bound patch / impact domain / causal operation / compensation subpatch / graph version contribution / tombstone”等概念扩展 CPC/IPC 和引证检索；
4. 检索申请日前公开的图数据库 migration、Graph CI/CD、data contract、change impact analysis 和 compensating transaction 工程文献；
5. 对权利要求1的每一个必要特征制作一对一 claim chart；
6. 根据最接近组合修改必要技术特征、从属回退和分案策略。

任何“未发现相同公开”的结论都必须以代理师正式检索为准。
