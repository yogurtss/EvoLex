# EvoLex 第二轮源码—权利要求证据矩阵

本矩阵将正式权利要求的每个实质限制映射到源码、测试和说明书。状态含义：`explicit`为直接实现，`inherent`为计算机实现固有支持。没有把文档愿望当作实现证据。

## 权利要求1逐限制映射

| 限制 | 实现证据 | 测试/反例 | 状态 |
|---|---|---|---|
| S1 固定父版本基线和来源绑定候选图补丁 | `evolution.py::_build_patch`；`canonical.py::snapshot/latest_version_id` | pipeline canonical commit测试 | explicit |
| S1 关系操作端点依赖 | `depends_on_entity_ids`生成及消费 | 实体排除带关系闭包测试 | explicit |
| S2 来源锚+声明对象+端点+基线一跳邻接派生域 | `evolution.py::_derive_impact_domain` | evidence impact-domain测试 | explicit |
| S2 原始影响域冻结 | `_evaluate_patch`把同一`frozen_impact_domain`传入反事实、求解和最终重放 | 原域包含ce-1/ce-2而接受域仅ce-2测试 | explicit |
| S3 影子结构查询 | `_apply_shadow`中的entity existence/provenance、relation endpoints/provenance、relation key uniqueness | shadow gate测试 | explicit |
| S3 固定域外投影摘要 | `_unaffected_projection`及冻结域参数 | non-interference测试 | explicit |
| S4 逐关联操作反事实闭包重放 | `_verify_failed_query_attributions` | `target_failure_resolved`及篡改测试 | explicit |
| S4 待排除集合及剩余子补丁重验 | `_minimum_cost_compensation`、`_replay_without` | exact compensation及17候选fallback测试 | explicit |
| S5 内容寻址因果验证凭证 | `_build_validation_certificate`、`_snapshot_hash` | baseline/query/solver/exclusion/final-hash篡改测试 | explicit |
| S6 判定与提交两次重算 | `evolution_consensus_node`、`make_evolution_commit_node` | attribution tampering测试 | explicit |
| S6 decision/evaluation/certificate接受ID一致 | `_decision_matches_certificate` | forged decision selection测试 | explicit |
| S6 提交清单绑定的版本事务 | `canonical.py::commit_patch`、`_content_hash` | same patch/different selection rejection测试 | explicit |

## 从属及其他类别

| 权项 | 特征 | 证据 | 状态 |
|---:|---|---|---|
| 2 | 按实体/关系类型适配的来源锚 | `_build_patch`实体与关系证据契约分支 | explicit |
| 3 | 三类结构查询、两次重放、冻结域外投影 | `_apply_shadow`、`_evaluate_patch` | explicit |
| 4 | 每关联操作的排除闭包、目标失败状态和原因候选 | `_verify_failed_query_attributions` | explicit |
| 5 | 加权排除目标、≤16精确、>16固定点局部回退 | `_compensation_objective`、`_minimum_cost_compensation` | explicit |
| 6 | 凭证绑定字段及非真实性判断边界 | `_build_validation_certificate`；源码docstring | explicit |
| 7 | patch、parent、接受ID/hash、certificate构成提交清单 | `CanonicalGraphStore.commit_patch` | explicit |
| 8 | 同批次mention/relation/evidence、命名空间和直接端点映射 | `deepseek_client.py`、`extract.py`、`relation_extract.py` | explicit |
| 9 | evidence先过滤、relation reference失败、零成功回退 | `validate.py`、`relation_extract.py` | explicit |
| 10 | same-type、provenance、跨簇任意成员对合并 | `entity_merge.py` | explicit |
| 11 | qualifier hash关系身份及逐条source assertions | `relation_merge.py::_qualifier_hash/relation_merge_node` | explicit |
| 12 | contribution、tombstone、新生命周期和安全跳过历史补偿 | `canonical.py::rollback_version/_safe_to_compensate` | explicit |
| 13 | 镜像权1的系统数据流 | graph builder、Agent工具依赖、evolution及canonical模块 | explicit |
| 14 | 联合抽取、证据校验和双层规范化前端 | extract/validate/entity_merge/relation_merge | explicit |
| 15 | 处理器/存储器执行方法 | Python程序、CLI和自动测试 | inherent |
| 16 | 存储程序并由处理器执行 | Python包、构建配置和自动测试 | inherent |

## 核心摘要字段

`causal_validation_certificate`当前绑定：

```text
schema
patch_id
parent_version_id
baseline_snapshot_hash
candidate_operations_hash
original_impact_domain_hash
frozen_impact_domain_hash
retained_declared_impact_domain_hash
query_causality_hash + query_causality
excluded_operation_ids
solver_mode / solver_optimality / solver_result_hash
accepted_operation_ids
retained_operations_hash
final_shadow_snapshot_hash
gate_results
certificate_id
```

`graph_versions`当前额外持久化：

```text
accepted_operation_ids_json
accepted_operations_hash
certificate_id
commit_manifest_hash
```

## 未进入正式权利要求的实现

- noisy-OR和置信度上限：保留说明书公式（1）（2）；
- Agent EIG-cost-risk：仅调度公式（4）；
- schema提议与晋升：说明书/分案储备；
- 双层静态HTML控制台：`build_dashboard_bundle`生成当前活动规范总图和逐`document_id`来源投影，`snapshot_for_document`按实体提及和关系证据隔离且只补关系端点，`tests/test_visualization_bundle.py`验证共享实体不带入其他文档关系/证据；该能力保留为说明书中的可选审计实施方式及软件产品入口，未进入当前正式权利要求；
- 普通发布置信度和图稀疏评分：实现策略，不作为核心保护；
- 任意delete自动影子规划、跨库原子、任意业务语义等价、任意规模全局最优：明确排除。
