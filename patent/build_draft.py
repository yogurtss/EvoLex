#!/usr/bin/env python3
"""Build the evidence-grounded EvoLex Chinese patent drafting artifacts.

The generated application is a review draft for the inventors and a qualified
patent professional.  It is not a patentability, freedom-to-operate, or filing
opinion.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


SOURCE_MAP = [
    {
        "id": "C001",
        "type": "code",
        "locator": "src/evolex/agents/deepseek_client.py，TypedExtractor.extract_typed、OpenAICompatibleExtractor.extract_typed",
        "summary": "同一源片段的一次结构化响应同时生成提及、关系候选、测量和条件，关系端点引用同响应提及标识。",
        "confidence": "high",
    },
    {
        "id": "C002",
        "type": "code",
        "locator": "src/evolex/nodes/extract.py，make_extract_node、_namespace_typed_batch",
        "summary": "对每个片段的提及、证据、主张和关系候选标识加入片段命名空间，并保留来源文档与运行上下文。",
        "confidence": "high",
    },
    {
        "id": "C003",
        "type": "code",
        "locator": "src/evolex/nodes/validate.py，validate_node",
        "summary": "先按证据标识、来源文档标识和证据文本过滤证据对象，再以有效证据标识集合分别校验主张和关系候选，并输出无效关系证据引用失败记录。",
        "confidence": "high",
    },
    {
        "id": "C004",
        "type": "code",
        "locator": "src/evolex/nodes/entity_resolve.py，entity_resolve_node；src/evolex/nodes/entity_merge.py，entity_merge_node",
        "summary": "执行类型约束的提及解析、别名与单位归一化，并通过来源完整性门和 complete-link 簇约束合并同类实体。",
        "confidence": "high",
    },
    {
        "id": "C005",
        "type": "code",
        "locator": "src/evolex/nodes/relation_extract.py，make_relation_extract_node、_materialize_joint_relations",
        "summary": "根据提及到实体映射物化联合关系，对悬空端点和规范端点坍缩形成审计失败，仅在无有效联合关系可物化时回退。",
        "confidence": "high",
    },
    {
        "id": "C006",
        "type": "code",
        "locator": "src/evolex/nodes/relation_merge.py，canonicalize_predicate、relation_merge_node",
        "summary": "规范谓词、排序对称关系端点，以端点、谓词及限定信息摘要区分关系身份，聚合重复证据并保留逐条源断言快照。",
        "confidence": "high",
    },
    {
        "id": "C007",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_build_patch",
        "summary": "把规范实体和关系转换为操作级证据化 upsert 补丁；每个操作携带证据契约、端点依赖和声明影响域。",
        "confidence": "high",
    },
    {
        "id": "C008",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_derive_impact_domain、_evaluate_patch",
        "summary": "从操作声明域、证据契约、关系端点和基线一跳依赖派生原始影响域并冻结其摘要，后续反事实重放和排除集合求解均使用同一验证边界。",
        "confidence": "high",
    },
    {
        "id": "C009",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_apply_shadow、_unaffected_projection",
        "summary": "在内存影子图中应用补丁，执行端点完整性、规范关系唯一性、确定性重放和冻结影响域外投影一致性检查。",
        "confidence": "high",
    },
    {
        "id": "C010",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_minimum_cost_compensation、_dependency_closed_exclusions",
        "summary": "以逐操作依赖闭包排除和同基线反事实重放验证失败关联，对验证后的候选做依赖闭包求解；候选不超过十六个时精确枚举，超过时使用明确标记的固定点局部回退。",
        "confidence": "high",
    },
    {
        "id": "C011",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，evolution_consensus_node；src/evolex/agentic/metrics.py，publish_gate",
        "summary": "证据契约、确定性重放、非干扰、不变量和更新效用形成基础验证门，内容寻址因果验证凭证一致性形成附加提交门。",
        "confidence": "high",
    },
    {
        "id": "C012",
        "type": "code",
        "locator": "src/evolex/repositories/canonical.py，commit_patch",
        "summary": "在 canonical 单库事务中核对由候选补丁、父版本、接受操作摘要和凭证标识形成的提交清单，进行幂等与父版本校验，并写入图对象、版本事件和活动版本。",
        "confidence": "high",
    },
    {
        "id": "C013",
        "type": "code",
        "locator": "src/evolex/repositories/canonical.py，rollback_version、贡献重算及 tombstone 辅助方法",
        "summary": "以追加补偿版本移除目标版本贡献，结合实体与关系墓碑重算存活状态，保留后续贡献或后续删除。",
        "confidence": "high",
    },
    {
        "id": "C014",
        "type": "code",
        "locator": "src/evolex/repositories/schema_store.py，put_proposal、promote_proposal；src/evolex/nodes/schema_proposer.py",
        "summary": "以内容稳定标识累积 schema 证据，并在即时事务锁内重新读取活动版本后晋升，运行开始时固定使用版本。",
        "confidence": "high",
    },
    {
        "id": "C015",
        "type": "code",
        "locator": "src/evolex/agentic/controller.py，AgenticKGRunner；src/evolex/graph/builder.py",
        "summary": "多个技术判定模块按依赖图执行，上游修订使下游结果失效，并保留运行检查点和审计轨迹。",
        "confidence": "high",
    },
    {
        "id": "C016",
        "type": "code",
        "locator": "src/evolex/visualization/dashboard.py，build_dashboard、build_dashboard_bundle；src/evolex/repositories/canonical.py，snapshot_for_document；tests/test_visualization_bundle.py",
        "summary": "生成一份当前活动规范图的自包含交互页面及按来源文档内容快照分别投影的自包含页面；文档投影以实体提及和关系证据的document_id为直接边界，只补齐已选关系端点，并由测试验证共享实体不扩张其他文档关系。该展示能力属于可选治理和软件产品特征，不作为当前正式权利要求创新点。",
        "confidence": "medium",
    },
    {
        "id": "C017",
        "type": "test",
        "locator": "tests/test_joint_evolution.py、tests/test_governance_hardening.py、tests/test_patent_benchmark.py",
        "summary": "对联合端点物化、合并边界、补偿硬门、事务版本和项目自有回归语料提供可执行验证。",
        "confidence": "high",
    },
    {
        "id": "C018",
        "type": "documentation",
        "locator": "docs/technical_design.md、docs/evaluation.md、docs/security_and_governance.md",
        "summary": "记录实现边界、评估限制、信任边界和非保证事项。",
        "confidence": "high",
    },
    {
        "id": "C019",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_verify_failed_query_attributions、_build_validation_certificate、_validation_certificate_matches、_decision_matches_certificate",
        "summary": "通过依赖闭包反事实重放验证查询—操作原因，生成绑定基线、冻结影响域、查询原因、排除集合、保留操作、求解结果和门结果的内容寻址凭证，并在共识和提交前两次重算核对。",
        "confidence": "high",
    },
    {
        "id": "C020",
        "type": "test",
        "locator": "tests/test_governance_hardening.py，test_causal_validation_certificate_blocks_attribution_tampering、test_idempotent_patch_rejects_different_certificate_bound_selection、test_large_causal_candidate_space_uses_labelled_fixed_point_fallback",
        "summary": "覆盖基线、查询关联、求解结果、排除集合、最终影子摘要和提交选择篡改，以及同补丁不同提交清单重试拒绝和大候选空间标记回退。",
        "confidence": "high",
    },
    {
        "id": "E001",
        "type": "equation",
        "locator": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
        "summary": "带后续证据折扣的 noisy-OR 关系置信度聚合。",
        "confidence": "high",
    },
    {
        "id": "E002",
        "type": "equation",
        "locator": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
        "summary": "根据最高单项置信度和片段数设置关系置信度上限。",
        "confidence": "high",
    },
    {
        "id": "E003",
        "type": "equation",
        "locator": "src/evolex/nodes/evolution.py，_compensation_objective",
        "summary": "以排除操作数量、影响半径和证据损失构造补偿代价。",
        "confidence": "high",
    },
    {
        "id": "E004",
        "type": "equation",
        "locator": "src/evolex/agentic/agents.py，AgentProposal.utility",
        "summary": "以预期信息增益减去成本和风险形成 Agent 动作效用。",
        "confidence": "high",
    },
    {
        "id": "E005",
        "type": "equation",
        "locator": "src/evolex/nodes/evolution.py，_build_validation_certificate、_snapshot_hash",
        "summary": "对规范序列化的验证清单计算SHA-256内容摘要以形成因果验证凭证标识。",
        "confidence": "high",
    },
    {
        "id": "E006",
        "type": "equation",
        "locator": "src/evolex/repositories/canonical.py，commit_patch、_content_hash",
        "summary": "对补丁标识、父版本、接受操作标识、接受操作摘要和凭证标识计算提交清单摘要。",
        "confidence": "high",
    },
    {
        "id": "F001",
        "type": "source-figure",
        "locator": "docs/patent_strategy.md，第4节核心保护链",
        "summary": "S1至S6候选图补丁验证、反事实局部排除、凭证绑定和版本提交方法链。",
        "confidence": "high",
    },
    {
        "id": "F002",
        "type": "source-figure",
        "locator": "docs/technical_design.md，总体架构与演进验证闭环",
        "summary": "联合抽取、双层规范化、补丁、影子、门控和 canonical 存储的系统数据流。",
        "confidence": "high",
    },
    {
        "id": "F003",
        "type": "source-figure",
        "locator": "src/evolex/nodes/evolution.py，失败查询归因与补偿函数调用关系",
        "summary": "影响域、失败查询、依赖闭包和补偿重放的方法结构。",
        "confidence": "high",
    },
    {
        "id": "F004",
        "type": "source-figure",
        "locator": "src/evolex/repositories/canonical.py，graph_versions、version_events、contribution、tombstone 数据表及方法",
        "summary": "canonical 图版本提交与追加补偿生命周期。",
        "confidence": "high",
    },
    {
        "id": "F005",
        "type": "source-figure",
        "locator": "src/evolex/nodes/evolution.py，反事实归因与因果验证凭证数据流",
        "summary": "冻结影响域、反事实查询归因、排除集合、剩余子补丁和验证凭证之间的机制。",
        "confidence": "high",
    },
    {
        "id": "F006",
        "type": "source-figure",
        "locator": "src/evolex/nodes/extract.py、validate.py、entity_merge.py、relation_merge.py",
        "summary": "联合实体关系证据抽取、证据先行校验以及实体和关系规范化数据流。",
        "confidence": "high",
    },
]


TERMINOLOGY = [
    {
        "concept": "mention",
        "canonical_zh": "实体提及",
        "source_terms": ["mention", "entity mention"],
        "forbidden_aliases": [],
    },
    {
        "concept": "relation candidate",
        "canonical_zh": "关系候选",
        "source_terms": ["relation candidate"],
        "forbidden_aliases": [],
    },
    {
        "concept": "evidence span",
        "canonical_zh": "证据片段",
        "source_terms": ["evidence", "evidence span"],
        "forbidden_aliases": [],
    },
    {
        "concept": "canonical entity",
        "canonical_zh": "规范实体",
        "source_terms": ["canonical entity"],
        "forbidden_aliases": [],
    },
    {
        "concept": "canonical relation",
        "canonical_zh": "规范关系",
        "source_terms": ["canonical relation"],
        "forbidden_aliases": [],
    },
    {
        "concept": "evidence contract",
        "canonical_zh": "证据契约",
        "source_terms": ["EvidenceContract", "evidence contract"],
        "forbidden_aliases": [],
    },
    {
        "concept": "impact domain",
        "canonical_zh": "影响域",
        "source_terms": ["ImpactDomain", "affected domain"],
        "forbidden_aliases": [],
    },
    {
        "concept": "shadow graph",
        "canonical_zh": "影子图",
        "source_terms": ["shadow graph", "shadow snapshot"],
        "forbidden_aliases": [],
    },
    {
        "concept": "counterfactual cause operation",
        "canonical_zh": "反事实原因操作",
        "source_terms": ["counterfactual_cause_operation_ids"],
        "forbidden_aliases": [],
    },
    {
        "concept": "excluded update set",
        "canonical_zh": "待排除更新操作集合",
        "source_terms": ["compensation_operation_ids", "excluded operations"],
        "forbidden_aliases": ["补偿操作子集"],
    },
    {
        "concept": "retained subpatch",
        "canonical_zh": "剩余子补丁",
        "source_terms": ["retained operations", "accepted operations"],
        "forbidden_aliases": [],
    },
    {
        "concept": "causal validation certificate",
        "canonical_zh": "因果验证凭证",
        "source_terms": ["causal_validation_certificate"],
        "forbidden_aliases": [],
    },
    {
        "concept": "commit manifest",
        "canonical_zh": "提交清单",
        "source_terms": ["commit_manifest"],
        "forbidden_aliases": [],
    },
    {
        "concept": "canonical graph store",
        "canonical_zh": "规范图存储",
        "source_terms": ["canonical store", "canonical graph"],
        "forbidden_aliases": [],
    },
    {
        "concept": "version contribution",
        "canonical_zh": "版本贡献",
        "source_terms": ["version contribution"],
        "forbidden_aliases": [],
    },
    {
        "concept": "tombstone",
        "canonical_zh": "删除墓碑",
        "source_terms": ["tombstone"],
        "forbidden_aliases": [],
    },
]


FORMULA_INVENTORY = [
    {
        "source_id": "E001",
        "source_number": "源码公式A",
        "technical_role": "聚合同一规范关系的多项证据置信度，并对后续证据施加折扣。",
        "disposition": "specification-equation-1",
    },
    {
        "source_id": "E002",
        "source_number": "源码公式B",
        "technical_role": "限制关系聚合置信度随片段数量增长的幅度。",
        "disposition": "specification-equation-2",
    },
    {
        "source_id": "E003",
        "source_number": "源码公式C",
        "technical_role": "度量待排除更新操作集合的编辑数、影响对象数量和证据损失。",
        "disposition": "specification-equation-3",
    },
    {
        "source_id": "E004",
        "source_number": "源码公式D",
        "technical_role": "在 Agent 动作选择中平衡信息增益、执行成本和风险。",
        "disposition": "specification-only-noncore-equation-4",
    },
    {
        "source_id": "E005",
        "source_number": "源码公式E",
        "technical_role": "把基线、影响域、查询原因、排除集合、剩余操作及验证结果绑定为内容寻址因果验证凭证。",
        "disposition": "specification-equation-5-and-claim-1",
    },
    {
        "source_id": "E006",
        "source_number": "源码公式F",
        "technical_role": "把实际提交选择及验证凭证绑定到幂等提交清单。",
        "disposition": "specification-equation-6-and-claim-7",
    },
]


FIGURE_INVENTORY = [
    {
        "source_id": "F001",
        "source_number": "保护链",
        "type": "methodology",
        "disposition": "redraw-as-figure-1",
    },
    {
        "source_id": "F002",
        "source_number": "系统架构",
        "type": "methodology",
        "disposition": "redraw-as-figure-2",
    },
    {
        "source_id": "F003",
        "source_number": "补偿闭环",
        "type": "methodology",
        "disposition": "redraw-as-figure-3",
    },
    {
        "source_id": "F004",
        "source_number": "版本生命周期",
        "type": "methodology",
        "disposition": "redraw-as-figure-6",
    },
    {
        "source_id": "F005",
        "source_number": "因果验证凭证机制",
        "type": "methodology",
        "disposition": "redraw-as-figure-3-and-figure-4",
    },
    {
        "source_id": "F006",
        "source_number": "联合抽取与双层规范化",
        "type": "methodology",
        "disposition": "redraw-as-figure-5",
    },
]


EVIDENCE_LEDGER = [
    {
        "id": "L001",
        "feature": "同一抽取批次同时产生实体提及、以批次内提及标识作为端点的关系候选和证据片段，并对跨片段标识命名空间化",
        "source_ids": ["C001", "C002", "C005"],
        "source_location": "联合抽取接口、_namespace_typed_batch、_materialize_joint_relations",
        "technical_role": "使关系端点与提及身份共享可校验标识空间",
        "effect": "减少分步抽取导致的端点身份丢失并记录端点失败",
        "support_status": "explicit",
    },
    {
        "id": "L002",
        "feature": "先过滤缺少证据标识、来源文档标识或证据文本的证据，再校验主张与关系候选的证据引用并输出失败记录",
        "source_ids": ["C003", "C020"],
        "source_location": "validate_node及无效关系证据引用测试",
        "technical_role": "阻断悬空证据引用进入端点物化和图补丁",
        "effect": "提高证据引用完整性",
        "support_status": "explicit",
    },
    {
        "id": "L003",
        "feature": "仅在同类型、来源提及完整且两个待合并簇的任意跨簇成员对均达到等价阈值时自动合并实体",
        "source_ids": ["C004", "C017"],
        "source_location": "entity_merge_node及complete-link攻击测试",
        "technical_role": "形成受类型和来源约束的规范实体身份假设",
        "effect": "减少别名重复并限制传递性过度合并",
        "support_status": "explicit",
    },
    {
        "id": "L004",
        "feature": "以规范端点、规范谓词和限定信息摘要形成关系身份，聚合重复关系并保留逐条源断言快照",
        "source_ids": ["C006", "C017", "E001", "E002"],
        "source_location": "relation_merge_node、_qualifier_hash及限定信息隔离测试",
        "technical_role": "区分同一三元组在不同限定条件下的断言并支持源断言重建",
        "effect": "降低限定关系误合并并保留关系谱系",
        "support_status": "explicit",
    },
    {
        "id": "L005",
        "feature": "把规范图对象转换为具有操作标识、对象后态、与对象类型相适配的来源锚、声明影响对象及关系端点依赖的候选图补丁",
        "source_ids": ["C007"],
        "source_location": "_build_patch",
        "technical_role": "把知识候选转换为可独立验证和排除的操作单元",
        "effect": "为提交前影响分析提供机器输入",
        "support_status": "explicit",
    },
    {
        "id": "L006",
        "feature": "由来源锚、声明影响对象、关系端点依赖及基线一跳邻接派生并冻结原始影响域摘要",
        "source_ids": ["C008", "C020"],
        "source_location": "_derive_impact_domain、_evaluate_patch及冻结域测试",
        "technical_role": "为全部反事实重放和排除集合求解固定验证边界",
        "effect": "避免候选删减过程中验证边界随之缩小",
        "support_status": "explicit",
    },
    {
        "id": "L007",
        "feature": "在固定基线影子图执行候选补丁，输出带操作关联和影响域摘要的结构查询、重放摘要及域外投影摘要",
        "source_ids": ["C009"],
        "source_location": "_apply_shadow、_unaffected_projection、_query",
        "technical_role": "在正式图提交前形成可重放的失败记录和边界检查结果",
        "effect": "降低不合格补丁直接污染规范图的风险",
        "support_status": "explicit",
    },
    {
        "id": "L008",
        "feature": "对失败查询的每个关联操作执行依赖闭包排除和同基线反事实重放，仅将使目标失败消失的操作确定为反事实原因操作",
        "source_ids": ["C010", "C019", "C020"],
        "source_location": "_verify_failed_query_attributions及篡改测试",
        "technical_role": "把静态操作关联收紧为可执行的反事实原因验证",
        "effect": "缩小排除候选空间并提供原因检查记录",
        "support_status": "explicit",
    },
    {
        "id": "L009",
        "feature": "在关系端点依赖闭合和冻结影响域约束下选择待排除更新操作集合；小候选空间精确枚举，大候选空间输出固定点单删除局部最小且非全局的标记结果",
        "source_ids": ["C010", "C020", "E003"],
        "source_location": "_minimum_cost_compensation及十七候选回归测试",
        "technical_role": "在满足结构约束时保留剩余子补丁并如实标记求解性质",
        "effect": "减少整补丁回退造成的有效知识损失",
        "support_status": "explicit",
    },
    {
        "id": "L010",
        "feature": "生成内容寻址因果验证凭证，绑定基线、候选操作、冻结影响域、查询原因、求解结果、排除与接受操作、最终影子摘要及门结果",
        "source_ids": ["C019", "C020", "E005"],
        "source_location": "_build_validation_certificate及多字段篡改测试",
        "technical_role": "使验证依据与剩余子补丁形成可重算的一致性清单",
        "effect": "检测验证结果、选择结果或基线被替换",
        "support_status": "explicit",
    },
    {
        "id": "L011",
        "feature": "共识和提交节点重算凭证，并要求判定、评估和凭证中的接受操作标识一致；存储层再核对提交清单摘要",
        "source_ids": ["C011", "C012", "C019", "C020", "E006"],
        "source_location": "_decision_matches_certificate、commit_patch及同补丁不同选择测试",
        "technical_role": "把实际写入事件集合绑定到验证凭证和幂等重试",
        "effect": "阻止选择篡改或旧版本误作为本次提交返回",
        "support_status": "explicit",
    },
    {
        "id": "L012",
        "feature": "规范图存储在单库事务中校验父版本和提交清单，写入剩余操作、图事件、图版本及活动版本指针",
        "source_ids": ["C012"],
        "source_location": "CanonicalGraphStore.commit_patch",
        "technical_role": "建立具有父版本拒绝和清单幂等语义的提交边界",
        "effect": "避免陈旧或错配子补丁静默写入",
        "support_status": "explicit",
    },
    {
        "id": "L013",
        "feature": "通过版本贡献和删除墓碑创建追加式历史补偿版本，在后续依赖不允许安全移除时记录跳过操作",
        "source_ids": ["C013", "C017"],
        "source_location": "rollback_version、_safe_to_compensate及交错生命周期测试",
        "technical_role": "按贡献重算当前对象而不删除历史版本",
        "effect": "保留后续贡献、后续删除和新生命周期",
        "support_status": "explicit",
    },
    {
        "id": "L014",
        "feature": "一次运行固定schema版本，schema提议使用内容稳定标识累积，并在事务锁内重读活动版本后晋升",
        "source_ids": ["C014", "C017"],
        "source_location": "schema_store及并发晋升测试",
        "technical_role": "分离当前运行配置与后续schema变更",
        "effect": "提高运行可复现性并避免并发丢更新",
        "support_status": "explicit",
    },
    {
        "id": "L015",
        "feature": "技术判定模块按依赖图执行且上游修订使下游结果失效",
        "source_ids": ["C015", "C017"],
        "source_location": "AgenticKGRunner及工具依赖失效测试",
        "technical_role": "防止陈旧下游结果用于提交",
        "effect": "保持控制链阶段一致性",
        "support_status": "explicit",
    },
    {
        "id": "L016",
        "feature": "生成展示当前活动规范图的全局页面，以及按来源文档内容快照投影且不扩张其他文档关系证据的逐文档页面",
        "source_ids": ["C016"],
        "source_location": "build_dashboard、build_dashboard_bundle、snapshot_for_document及可视化隔离测试",
        "technical_role": "提供实施例中的人工审计入口；不承担正式权利要求创造性",
        "effect": "在不部署前后端服务的条件下缩短全局审计和逐来源诊断路径",
        "support_status": "explicit",
    },
    {
        "id": "L017",
        "feature": "由处理器执行程序以实现候选图补丁验证、局部排除、凭证核对和版本提交",
        "source_ids": ["C007", "C008", "C009", "C010", "C012", "C019", "C020"],
        "source_location": "可执行源码、命令行入口和自动化测试",
        "technical_role": "支持系统、设备和存储介质类别",
        "effect": "在通用计算设备上实现所述数据完整性控制链",
        "support_status": "inherent",
    },
]


LEGACY_CLAIMS_REVIEW_BASELINE = [
    {
        "number": 1,
        "text": (
            "一种基于多技术判定模块的知识图谱受控自进化方法，其特征在于，包括："
            "S1，获取待处理技术文档并划分源片段，使联合抽取器针对每一源片段在一次抽取结果中生成实体提及、关系候选和证据片段，其中，所述关系候选的主端点和客端点分别引用所述一次抽取结果内的实体提及标识；"
            "S2，为不同源片段的实体提及标识、关系候选标识和证据标识加入片段命名空间，先过滤不满足来源字段约束的证据片段，再根据过滤后保留的证据标识校验所述关系候选；"
            "S3，根据实体类型、规范化文本和来源提及对实体提及进行解析，在同类型和来源完整性约束下合并实体身份，并在经解析的实体端点上对关系谓词和重复关系进行规范化，得到保留来源谱系的规范实体和规范关系；"
            "S4，将所述规范实体和规范关系转换为证据化的新增操作或修改操作，将所述新增操作或修改操作记为更新操作，每一更新操作携带证据契约、对象标识、来源文档标识、来源片段标识、证据标识、声明影响域以及关系端点依赖，由所述更新操作组成候选图补丁；"
            "S5，消费所述证据契约、所述声明影响域、所述关系端点依赖及规范图基线的一跳关联，生成所述候选图补丁的影响域和与更新操作标识关联的结构不变量；"
            "S6，在影子图中执行所述候选图补丁，重复执行相同补丁以进行确定性重放检查，并比较影响域外的基线投影与影子投影，对未通过的结构不变量输出包含因果操作标识的失败查询；"
            "S7，在存在所述失败查询时，根据所述因果操作标识和实体操作与关系操作之间的依赖形成依赖闭合的候选集合，从所述候选集合中选择补偿操作子集，使排除该补偿操作子集后的补丁通过结构不变量和影响域外投影检查，并由证据契约检查、确定性重放检查、非干扰检查、结构不变量检查以及效用检查生成提交判定；"
            "S8，仅当所述提交判定和发布策略均允许提交时，在规范图存储的事务中校验父版本和补丁幂等性，提交排除所述补偿操作子集后的更新操作并记录图版本和版本事件，输出具有图版本标识的受控知识图谱更新结果；否则将所述候选图补丁隔离。"
        ),
    },
    {
        "number": 2,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述联合抽取器在同一模型响应或同一确定性抽取函数返回值中声明全部被关系候选引用的实体提及标识；关系物化直接使用实体提及标识到规范实体标识的映射，且仅在不存在可成功物化的有效联合关系时启动独立关系抽取回退，并保存未物化关系候选的端点失败原因。"
        ),
    },
    {
        "number": 3,
        "text": (
            "根据权利要求1所述的方法，其特征在于，对所述证据片段的过滤至少包括校验证据标识、源片段标识、证据文本和置信度，并在证据过滤完成后删除主张或关系候选对无效证据标识的引用，使证据完整性校验先于候选图补丁构造。"
        ),
    },
    {
        "number": 4,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述合并实体身份包括：仅针对实体类型相同的实体生成合并提议；根据规范文本、别名、缩写或单位同义形式计算等价分值；在合并簇内任意两个实体均达到自动合并阈值且均具有来源提及时接受合并；并保留原实体标识、实体提及标识、别名、源片段标识和合并决定。"
        ),
    },
    {
        "number": 5,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述关系规范化包括：把谓词别名映射为规范谓词；对于对称谓词按规范实体标识排序主客端点；以主端点、规范谓词、客端点和限定信息形成关系身份键；聚合具有相同关系身份键的证据，并记录源关系标识、源关系候选标识、谓词别名和可逆关系身份假设。"
        ),
    },
    {
        "number": 6,
        "text": (
            "根据权利要求5所述的方法，其特征在于，对于同一规范关系的证据置信度，按照带折扣的 noisy-OR 方式合并，并根据最高单项置信度和不同源片段数量设置聚合上限；仅对预先配置为功能性谓词的同一主端点和不同客端点组合标记关系冲突。"
        ),
    },
    {
        "number": 7,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述证据契约至少包括来源完整性状态、来源文档标识集合、来源片段标识集合、证据标识集合、实体提及标识集合或源关系候选标识集合；所述影响域至少包括受影响实体、关系、谓词、来源文档、来源片段、证据和更新操作，并沿规范图基线中与受影响端点或谓词相连的一跳关系扩展。"
        ),
    },
    {
        "number": 8,
        "text": (
            "根据权利要求7所述的方法，其特征在于，所述结构不变量至少包括规范实体存在、关系端点可解析和规范关系键唯一；所述确定性重放检查比较相同基线和相同更新操作两次执行所得规范化影子快照的结构摘要；所述非干扰检查从基线和影子快照中排除影响域对象后比较剩余投影的结构摘要。"
        ),
    },
    {
        "number": 9,
        "text": (
            "根据权利要求1所述的方法，其特征在于，选择所述补偿操作子集时，以被排除更新操作数量、补偿影响半径和随补偿丢失的证据数量的加权和为目标函数，并以补偿操作子集依赖闭合、补偿后全部结构不变量通过以及影响域外投影检查通过为约束；当因果候选更新操作不超过预设阈值时枚举依赖闭合子集并选择目标函数值最小的子集，当超过所述预设阈值时输出被明确标记为非全局解的包含极小子集。"
        ),
    },
    {
        "number": 10,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述效用检查根据预期信息增益减去执行成本和风险代价计算更新效用；仅当证据契约完整、确定性重放一致、影响域外投影一致、补偿后结构不变量通过、更新效用非负、发布置信度达到阈值且图稀疏惩罚不超过阈值时允许规范图提交。"
        ),
    },
    {
        "number": 11,
        "text": (
            "根据权利要求1所述的方法，其特征在于，在一次文档处理运行开始时固定活动 schema 版本；对未识别的实体类型、关系谓词或属性按其类别和规范符号分别形成内容稳定的 schema 提议标识；在晋升 schema 提议的事务锁内重新读取活动 schema 版本，创建以后读取的活动版本为父版本的新 schema 版本。"
        ),
    },
    {
        "number": 12,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述规范图存储分别记录规范实体、实体别名、实体提及、规范关系和关系证据的版本贡献以及实体和关系的删除墓碑；响应于回滚指定图版本，追加补偿图版本，移除可归因于指定图版本的贡献，并依据剩余贡献和时间上较后的删除墓碑重算对象状态，以保留指定图版本之后的更新或删除。"
        ),
    },
    {
        "number": 13,
        "text": (
            "一种知识图谱受控自进化系统，其特征在于，包括：联合抽取模块，用于从同一源片段的一次抽取结果获得实体提及、引用实体提及标识的关系候选和证据片段；双层规范化模块，用于在类型和来源约束下形成规范实体，并在规范实体端点上形成规范关系；补丁规划模块，用于把规范实体和规范关系转换为携带证据契约、关系端点依赖和声明影响域的新增操作或修改操作，并将所述新增操作或修改操作记为更新操作；影响域模块，用于消费证据契约、声明影响域、端点依赖和规范图基线一跳关联以形成影响域及结构不变量；影子验证模块，用于在影子图中执行更新操作，进行确定性重放和影响域外投影检查，并把失败查询关联到因果操作标识；补偿模块，用于在依赖闭合约束下选择补偿操作子集并重新验证剩余更新操作；门控模块，用于根据证据、重放、非干扰、不变量、效用和策略产生提交判定；以及规范图存储模块，用于在提交判定允许时在事务中记录剩余更新操作、图版本和版本事件，并输出具有图版本标识的受控知识图谱更新结果。"
        ),
    },
    {
        "number": 14,
        "text": (
            "根据权利要求13所述的系统，其特征在于，还包括可视化模块，所述可视化模块根据同一运行标识和图版本标识关联展示规范实体、规范关系、关系证据、图版本、技术判定模块轨迹、影子结构不变量、失败查询、补偿操作子集、实体与关系合并决定以及 schema 提议。"
        ),
    },
    {
        "number": 15,
        "text": (
            "一种电子设备，其特征在于，包括处理器和存储器，所述存储器中存储有计算机程序，所述计算机程序被所述处理器执行时，使所述处理器执行权利要求1至12任一项所述的方法。"
        ),
    },
    {
        "number": 16,
        "text": (
            "一种非暂态计算机可读存储介质，其特征在于，所述非暂态计算机可读存储介质上存储有计算机程序，所述计算机程序被处理器执行时，使所述处理器执行权利要求1至12任一项所述的方法。"
        ),
    },
]


LEGACY_CLAIM_FEATURE_MAP_REVIEW_BASELINE = [
    {
        "claim_number": 1,
        "feature": "联合提及端点、证据化补丁、证据派生影响域、可归因影子查询、依赖闭合补偿、硬门和规范版本事务组成连续技术链",
        "evidence_ids": [
            "L001",
            "L002",
            "L003",
            "L004",
            "L005",
            "L006",
            "L007",
            "L008",
            "L010",
            "L011",
        ],
        "specification_locations": ["发明内容，技术方案S1至S8", "具体实施方式，实施例1至实施例4"],
    },
    {
        "claim_number": 2,
        "feature": "同响应提及标识端点、直接物化和有条件回退",
        "evidence_ids": ["L001", "L004"],
        "specification_locations": ["具体实施方式，实施例1"],
    },
    {
        "claim_number": 3,
        "feature": "证据先过滤、候选后校验",
        "evidence_ids": ["L002"],
        "specification_locations": ["具体实施方式，实施例1"],
    },
    {
        "claim_number": 4,
        "feature": "同类型、来源门和 complete-link 实体合并",
        "evidence_ids": ["L003"],
        "specification_locations": ["具体实施方式，实施例2"],
    },
    {
        "claim_number": 5,
        "feature": "谓词规范、对称端点排序、关系身份和可逆谱系",
        "evidence_ids": ["L004"],
        "specification_locations": ["具体实施方式，实施例2"],
    },
    {
        "claim_number": 6,
        "feature": "带折扣和上限的关系置信度以及功能性谓词冲突",
        "evidence_ids": ["L004"],
        "specification_locations": ["具体实施方式，实施例2", "说明书公式（1）和公式（2）"],
    },
    {
        "claim_number": 7,
        "feature": "证据契约字段和证据派生一跳影响域",
        "evidence_ids": ["L005", "L006"],
        "specification_locations": ["具体实施方式，实施例3"],
    },
    {
        "claim_number": 8,
        "feature": "结构不变量、确定性重放和域外投影",
        "evidence_ids": ["L007"],
        "specification_locations": ["具体实施方式，实施例3"],
    },
    {
        "claim_number": 9,
        "feature": "依赖闭合补偿目标、十六操作精确阈值及标记回退",
        "evidence_ids": ["L008", "L009"],
        "specification_locations": ["具体实施方式，实施例4", "说明书公式（3）"],
    },
    {
        "claim_number": 10,
        "feature": "非负效用、证据、重放、非干扰、不变量和发布置信度门控",
        "evidence_ids": ["L010"],
        "specification_locations": ["具体实施方式，实施例4", "说明书公式（4）"],
    },
    {
        "claim_number": 11,
        "feature": "运行时 schema 固定和并发安全晋升",
        "evidence_ids": ["L013"],
        "specification_locations": ["具体实施方式，实施例6"],
    },
    {
        "claim_number": 12,
        "feature": "版本贡献、删除墓碑和追加式选择性补偿",
        "evidence_ids": ["L012"],
        "specification_locations": ["具体实施方式，实施例5"],
    },
    {
        "claim_number": 13,
        "feature": "实现方法连续链的系统模块和强制数据流",
        "evidence_ids": ["L001", "L003", "L005", "L006", "L007", "L008", "L010", "L011", "L014", "L016"],
        "specification_locations": ["发明内容，系统方案", "具体实施方式，实施例7"],
    },
    {
        "claim_number": 14,
        "feature": "按运行和图版本关联的治理可视化",
        "evidence_ids": ["L015"],
        "specification_locations": ["具体实施方式，实施例6"],
    },
    {
        "claim_number": 15,
        "feature": "由处理器和存储器执行受控自进化方法",
        "evidence_ids": ["L016"],
        "specification_locations": ["具体实施方式，实施例7"],
    },
    {
        "claim_number": 16,
        "feature": "存储使处理器执行受控自进化方法的程序",
        "evidence_ids": ["L016"],
        "specification_locations": ["具体实施方式，实施例7"],
    },
]


CLAIMS = [
    {
        "number": 1,
        "text": (
            "一种知识图谱候选图补丁的验证和版本提交方法，其特征在于，包括："
            "S1，获取固定于父图版本的规范图基线和候选图补丁，所述候选图补丁包括多个具有操作标识的更新操作，每一更新操作包括对象标识、对象后态、与对象类型相适配的来源锚集合及声明影响对象，关系更新操作还包括对端点实体的依赖；"
            "S2，消费所述来源锚集合、所述声明影响对象、所述端点实体的依赖以及所述规范图基线中的一跳邻接，生成包括受影响实体、受影响关系、受影响谓词和来源范围的原始影响域，并冻结所述原始影响域的内容摘要；"
            "S3，在固定于所述父图版本的影子图中执行所述候选图补丁，获得分别具有查询标识、通过状态、关联操作标识集合和原始影响域摘要的结构查询结果，并比较从所述规范图基线和影子图中排除原始影响域对象后所得域外投影摘要；"
            "S4，对于未通过的结构查询，分别以其关联更新操作作为排除种子，将依赖被排除实体的关系更新操作加入排除闭包，从所述规范图基线重放排除该排除闭包后的更新操作，仅当目标结构查询不再失败时把所述排除种子确定为反事实原因操作；在所述反事实原因操作及其依赖闭包内确定待排除更新操作集合，使由其余更新操作形成的剩余子补丁在所述原始影响域保持冻结的条件下重放后通过结构查询和域外投影摘要比较；不存在未通过的结构查询时，所述待排除更新操作集合为空集；"
            "S5，对验证清单进行规范序列化并计算内容摘要以生成因果验证凭证，所述验证清单至少绑定规范图基线摘要、候选更新操作摘要、原始影响域摘要、结构查询与反事实原因操作的对应关系、待排除更新操作集合、剩余子补丁摘要及重放结果；"
            "S6，在提交判定阶段和提交执行阶段重新计算并核对所述因果验证凭证，且校验提交判定、结构查询评估和因果验证凭证中的接受操作标识相同；仅在核对一致且所述结构查询和域外投影摘要比较通过时，于规范图存储的事务中校验父图版本及由候选图补丁、接受操作和因果验证凭证形成的提交清单，写入所述剩余子补丁、图事件、图版本和活动版本指针，并把因果验证凭证标识与所述图版本关联；否则隔离所述候选图补丁。"
        ),
    },
    {
        "number": 2,
        "text": (
            "根据权利要求1所述的方法，其特征在于，实体更新操作的来源锚集合包括来源文档标识、来源片段标识和实体提及标识中的至少两项，关系更新操作的来源锚集合包括来源文档标识、证据标识、源关系候选标识和证据文本中的至少两项；仅在与更新操作类型对应的来源完整性条件满足时把所述更新操作纳入剩余子补丁。"
        ),
    },
    {
        "number": 3,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述结构查询至少包括规范实体存在查询、关系端点可解析查询和规范关系身份唯一查询；对相同规范图基线和相同候选图补丁执行两次影子重放并比较规范化影子快照摘要，且所述域外投影摘要比较始终使用步骤S2冻结的原始影响域，而不随待排除更新操作集合变化。"
        ),
    },
    {
        "number": 4,
        "text": (
            "根据权利要求1所述的方法，其特征在于，对每一未通过的结构查询记录关联操作标识集合，并为其中每一操作标识记录由该操作标识触发的排除闭包、目标失败是否消失及反事实验证状态；只有目标失败消失的操作标识进入用于确定所述待排除更新操作集合的候选空间。"
        ),
    },
    {
        "number": 5,
        "text": (
            "根据权利要求1所述的方法，其特征在于，以被排除更新操作数量、被排除更新操作覆盖的实体、关系和谓词数量以及随排除丢失的证据数量的加权和评价待排除更新操作集合，并以依赖闭合、结构查询通过和域外投影摘要比较通过为约束；当候选空间不超过预设阈值时枚举依赖闭合子集并选择目标函数值最小的可行子集，当超过所述预设阈值时重复执行单项删除和重放直至达到固定点，并把所得结果标记为单删除局部最小且非全局最小。"
        ),
    },
    {
        "number": 6,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述因果验证凭证还绑定候选更新操作内容摘要、反事实检查记录摘要、排除集合求解模式及解性质标记、接受操作标识集合、冻结影响域摘要、接受操作自身声明影响域摘要、最终影子快照摘要以及证据完整性、确定性重放、域外投影、结构查询和更新效用的门结果；所述因果验证凭证为可重算的内容寻址一致性清单，而不作为知识内容真实性判断。"
        ),
    },
    {
        "number": 7,
        "text": (
            "根据权利要求1所述的方法，其特征在于，所述提交清单包括候选图补丁标识、父图版本标识、排序后的接受操作标识集合、接受操作内容摘要和因果验证凭证标识；规范图存储将所述提交清单摘要随图版本持久化，同一候选图补丁标识再次提交时，仅在本次提交清单摘要与已持久化提交清单摘要一致时返回原图版本，否则拒绝所述再次提交。"
        ),
    },
    {
        "number": 8,
        "text": (
            "根据权利要求1所述的方法，其特征在于，在步骤S1之前，对同一源片段执行一次联合抽取以获得实体提及、关系候选和证据片段，所述关系候选的主端点和客端点引用该次联合抽取中声明的实体提及标识；跨源片段汇总前对实体提及标识、关系候选标识和证据标识加入片段命名空间，并利用实体提及标识到规范实体标识的映射物化关系。"
        ),
    },
    {
        "number": 9,
        "text": (
            "根据权利要求8所述的方法，其特征在于，先过滤缺少证据标识、来源文档标识或证据文本的证据片段，再依据过滤后保留的证据标识集合分别校验主张和关系候选；不满足证据引用条件的关系候选不进入关系物化，并记录关系候选标识、缺失字段和无效证据标识；仅在不存在能够成功物化的有效联合关系时启动独立关系抽取回退。"
        ),
    },
    {
        "number": 10,
        "text": (
            "根据权利要求8所述的方法，其特征在于，仅针对实体类型相同的实体生成合并提议，并在来源提及完整且两个拟合并实体簇中的任意跨簇实体对均达到自动合并阈值时接受合并；合并结果保留源实体标识、实体提及标识、别名、来源片段标识和合并决定。"
        ),
    },
    {
        "number": 11,
        "text": (
            "根据权利要求8所述的方法，其特征在于，在实体端点稳定后把谓词别名映射为规范谓词，对对称谓词按规范实体标识排序端点，并以主端点、规范谓词、客端点和限定信息的规范序列化摘要形成关系身份；仅聚合关系身份相同的关系，并为每一源关系保留源关系标识、源关系候选标识、原谓词、限定信息、证据标识、证据文本、来源片段标识和源置信度组成的源断言快照。"
        ),
    },
    {
        "number": 12,
        "text": (
            "根据权利要求1所述的方法，其特征在于，规范图存储分别记录规范实体、实体别名、实体提及、规范关系和关系证据的版本贡献以及实体和关系的删除墓碑；响应于补偿指定历史图版本，创建追加式历史补偿版本，按安全补偿条件移除可归因于指定历史图版本的贡献，并依据剩余贡献、时间上较后的删除墓碑和新对象生命周期重算对象状态；因后续依赖不满足安全补偿条件的操作被记录为跳过操作。"
        ),
    },
    {
        "number": 13,
        "text": (
            "一种知识图谱候选图补丁的验证和版本提交系统，其特征在于，包括：补丁接收模块，用于获得固定父图版本的规范图基线以及携带来源锚、声明影响对象和端点实体依赖的候选图补丁；影响域模块，用于消费所述来源锚、声明影响对象、端点实体依赖及规范图基线邻接以生成并冻结原始影响域摘要；影子验证模块，用于在固定基线的影子图执行候选图补丁并输出带关联操作标识的结构查询结果和域外投影摘要比较结果；反事实归因及排除模块，用于通过依赖闭包排除和同基线重放确定反事实原因操作，并确定通过重新验证的待排除更新操作集合和剩余子补丁；凭证模块，用于生成并重算绑定基线、候选操作、原始影响域、查询原因、排除集合、剩余子补丁和重放结果的因果验证凭证；以及规范图存储模块，用于在提交选择与因果验证凭证一致时核对父图版本和提交清单，在事务中写入剩余子补丁、图事件、图版本及活动版本指针，并将因果验证凭证标识与图版本关联。"
        ),
    },
    {
        "number": 14,
        "text": (
            "根据权利要求13所述的系统，其特征在于，还包括联合抽取模块、证据校验模块、实体规范化模块和关系规范化模块；所述联合抽取模块输出批次内共享提及标识空间的实体提及、关系候选和证据片段，所述证据校验模块先形成有效证据标识集合，所述实体规范化模块在同类型和跨簇成员对约束下产生规范实体，所述关系规范化模块在规范实体端点上按限定信息区分规范关系并保留源断言快照，所述规范实体和规范关系被转换为供所述补丁接收模块接收的候选图补丁。"
        ),
    },
    {
        "number": 15,
        "text": (
            "一种电子设备，其特征在于，包括处理器和存储器，所述存储器中存储有计算机程序，所述计算机程序被所述处理器执行时，使所述处理器执行权利要求1至12任一项所述的方法。"
        ),
    },
    {
        "number": 16,
        "text": (
            "一种计算机可读存储介质，其特征在于，所述计算机可读存储介质上存储有计算机程序，所述计算机程序被处理器执行时，使所述处理器执行权利要求1至12任一项所述的方法。"
        ),
    },
]


CLAIM_FEATURE_MAP = [
    {"claim_number": 1, "feature": "S1：固定父版本基线及携带来源锚、声明影响对象和端点依赖的操作级候选图补丁", "evidence_ids": ["L005"], "specification_locations": ["发明内容，核心方案S1", "具体实施方式，实施例1"]},
    {"claim_number": 1, "feature": "S2：消费来源锚和图依赖生成并冻结原始影响域摘要", "evidence_ids": ["L006"], "specification_locations": ["发明内容，核心方案S2", "具体实施方式，实施例2"]},
    {"claim_number": 1, "feature": "S3：固定基线影子执行、结构查询及冻结域外投影摘要比较", "evidence_ids": ["L007"], "specification_locations": ["发明内容，核心方案S3", "具体实施方式，实施例2"]},
    {"claim_number": 1, "feature": "S4：依赖闭包反事实原因验证、待排除集合及剩余子补丁重放", "evidence_ids": ["L008", "L009"], "specification_locations": ["发明内容，核心方案S4", "具体实施方式，实施例3"]},
    {"claim_number": 1, "feature": "S5：规范序列化验证清单及内容寻址因果验证凭证", "evidence_ids": ["L010"], "specification_locations": ["发明内容，核心方案S5", "具体实施方式，实施例4", "说明书公式（5）"]},
    {"claim_number": 1, "feature": "S6：两阶段凭证重算、三方接受操作一致和提交清单绑定的剩余子补丁事务提交", "evidence_ids": ["L011", "L012"], "specification_locations": ["发明内容，核心方案S6", "具体实施方式，实施例4", "说明书公式（6）"]},
    {"claim_number": 2, "feature": "按实体或关系操作类型适配的来源锚集合及来源完整性门", "evidence_ids": ["L005"], "specification_locations": ["具体实施方式，实施例1"]},
    {"claim_number": 3, "feature": "三类结构查询、确定性重放及全程冻结的域外投影边界", "evidence_ids": ["L006", "L007"], "specification_locations": ["具体实施方式，实施例2"]},
    {"claim_number": 4, "feature": "逐关联操作记录依赖闭包与目标失败消失状态的反事实检查", "evidence_ids": ["L008"], "specification_locations": ["具体实施方式，实施例3"]},
    {"claim_number": 5, "feature": "依赖闭合排除目标、精确枚举阈值和带性质标记的固定点回退", "evidence_ids": ["L009"], "specification_locations": ["具体实施方式，实施例3", "说明书公式（3）"]},
    {"claim_number": 6, "feature": "因果验证凭证字段、门结果和非真实性判断边界", "evidence_ids": ["L010"], "specification_locations": ["具体实施方式，实施例4", "说明书公式（5）"]},
    {"claim_number": 7, "feature": "提交清单字段、持久化摘要及同补丁不同选择重试拒绝", "evidence_ids": ["L011", "L012"], "specification_locations": ["具体实施方式，实施例4", "说明书公式（6）"]},
    {"claim_number": 8, "feature": "同批次实体—关系—证据联合抽取、片段命名空间和提及端点直接物化", "evidence_ids": ["L001"], "specification_locations": ["具体实施方式，实施例5"]},
    {"claim_number": 9, "feature": "证据先过滤、关系证据引用失败记录及零有效联合关系回退", "evidence_ids": ["L002", "L001"], "specification_locations": ["具体实施方式，实施例5"]},
    {"claim_number": 10, "feature": "同类型、来源完整和跨簇任意成员对约束的实体合并", "evidence_ids": ["L003"], "specification_locations": ["具体实施方式，实施例6"]},
    {"claim_number": 11, "feature": "限定信息参与关系身份及逐条源断言快照", "evidence_ids": ["L004"], "specification_locations": ["具体实施方式，实施例6"]},
    {"claim_number": 12, "feature": "版本贡献、删除墓碑、新生命周期和跳过条件下的追加式历史补偿", "evidence_ids": ["L013"], "specification_locations": ["具体实施方式，实施例7"]},
    {"claim_number": 13, "feature": "镜像权利要求1连续数据依赖的补丁验证和版本提交系统", "evidence_ids": ["L005", "L006", "L007", "L008", "L009", "L010", "L011", "L012", "L017"], "specification_locations": ["发明内容，系统方案", "具体实施方式，实施例8"]},
    {"claim_number": 14, "feature": "联合抽取、证据校验和双层规范化前端向补丁系统提供操作级候选图补丁", "evidence_ids": ["L001", "L002", "L003", "L004", "L005"], "specification_locations": ["具体实施方式，实施例5和实施例6", "具体实施方式，实施例8"]},
    {"claim_number": 15, "feature": "处理器和存储器执行权利要求1至12的方法", "evidence_ids": ["L017"], "specification_locations": ["具体实施方式，实施例8"]},
    {"claim_number": 16, "feature": "存储使处理器执行权利要求1至12方法的程序", "evidence_ids": ["L017"], "specification_locations": ["具体实施方式，实施例8"]},
]


LEGACY_FIGURES_REVIEW_BASELINE = [
    {
        "number": 1,
        "title": "知识图谱受控自进化方法流程图",
        "type": "flowchart",
        "orientation": "vertical",
        "claim_number": 1,
        "complete_claim_flow": True,
        "source_ids": ["F001", "C001", "C007", "C008", "C009", "C010", "C011", "C012"],
        "nodes": [
            {"id": "S1", "label": "S1：同片段联合生成提及、关系候选和证据", "claim_step": "S1"},
            {"id": "S2", "label": "S2：标识命名空间化并先行过滤证据", "claim_step": "S2"},
            {"id": "S3", "label": "S3：实体与关系双层证据化规范", "claim_step": "S3"},
            {"id": "S4", "label": "S4：构造携带证据契约的更新补丁", "claim_step": "S4"},
            {"id": "S5", "label": "S5：派生影响域并生成结构不变量", "claim_step": "S5"},
            {"id": "S6", "label": "S6：影子执行、重放及域外投影检查", "claim_step": "S6"},
            {"id": "S7", "label": "S7：因果归因、依赖闭合补偿及硬门", "claim_step": "S7"},
            {"id": "S8", "label": "S8：事务提交或隔离，输出版本化知识图谱", "claim_step": "S8"},
        ],
        "edges": [
            {"from": "S1", "to": "S2", "label": ""},
            {"from": "S2", "to": "S3", "label": ""},
            {"from": "S3", "to": "S4", "label": ""},
            {"from": "S4", "to": "S5", "label": ""},
            {"from": "S5", "to": "S6", "label": ""},
            {"from": "S6", "to": "S7", "label": "失败查询携带因果操作标识"},
            {"from": "S7", "to": "S8", "label": "剩余补丁通过全部硬门"},
        ],
    },
    {
        "number": 2,
        "title": "知识图谱受控自进化系统结构示意图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F002", "C015"],
        "nodes": [
            {"id": "input", "label": "技术文档及固定Schema"},
            {"id": "joint", "label": "联合抽取模块"},
            {"id": "canon", "label": "双层规范化模块"},
            {"id": "patch", "label": "证据补丁与影响域模块"},
            {"id": "shadow", "label": "影子验证与补偿模块"},
            {"id": "gate", "label": "多技术判定门控模块"},
            {"id": "store", "label": "规范图版本存储"},
            {"id": "view", "label": "版本化知识图谱及审计视图"},
        ],
        "edges": [
            {"from": "input", "to": "joint", "label": ""},
            {"from": "joint", "to": "canon", "label": "提及、关系候选、证据"},
            {"from": "canon", "to": "patch", "label": "规范实体与关系"},
            {"from": "patch", "to": "shadow", "label": "证据契约和影响域"},
            {"from": "shadow", "to": "gate", "label": "重放、查询和补偿结果"},
            {"from": "gate", "to": "store", "label": "提交判定"},
            {"from": "store", "to": "view", "label": "图版本和事件"},
        ],
    },
    {
        "number": 3,
        "title": "失败查询归因与补偿求解示意图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F003", "C008", "C009", "C010"],
        "nodes": [
            {"id": "domain", "label": "证据契约派生影响域"},
            {"id": "queries", "label": "影子结构查询"},
            {"id": "failure", "label": "失败查询及因果操作标识"},
            {"id": "closure", "label": "实体—关系依赖闭包"},
            {"id": "solver", "label": "补偿操作子集求解"},
            {"id": "replay", "label": "排除后重放与域外投影检查"},
            {"id": "patchout", "label": "通过约束的剩余更新补丁"},
        ],
        "edges": [
            {"from": "domain", "to": "queries", "label": "限定验证边界"},
            {"from": "queries", "to": "failure", "label": "未通过"},
            {"from": "failure", "to": "closure", "label": "归因"},
            {"from": "closure", "to": "solver", "label": "候选集合"},
            {"from": "solver", "to": "replay", "label": "排除子集"},
            {"from": "replay", "to": "patchout", "label": "全部约束通过"},
        ],
    },
    {
        "number": 4,
        "title": "规范图版本提交与选择性补偿示意图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F004", "C012", "C013"],
        "nodes": [
            {"id": "base", "label": "父图版本"},
            {"id": "commit", "label": "补丁事务提交"},
            {"id": "version", "label": "新图版本、事件及版本贡献"},
            {"id": "delete", "label": "后续贡献或删除墓碑"},
            {"id": "rollback", "label": "目标版本选择性补偿"},
            {"id": "current", "label": "保留后续状态的当前规范图版本"},
        ],
        "edges": [
            {"from": "base", "to": "commit", "label": "父版本校验"},
            {"from": "commit", "to": "version", "label": "单库事务"},
            {"from": "version", "to": "delete", "label": "后续事件"},
            {"from": "delete", "to": "rollback", "label": "指定历史版本"},
            {"from": "rollback", "to": "current", "label": "追加补偿版本"},
        ],
    },
]


FIGURES = [
    {
        "number": 1,
        "title": "知识图谱候选图补丁验证和版本提交方法流程图",
        "type": "flowchart",
        "orientation": "vertical",
        "claim_number": 1,
        "complete_claim_flow": True,
        "source_ids": ["F001", "F005", "C007", "C008", "C009", "C010", "C012", "C019"],
        "nodes": [
            {"id": "S1", "label": "S1：获取固定父版本基线与来源绑定候选图补丁", "claim_step": "S1"},
            {"id": "S2", "label": "S2：派生并冻结原始影响域摘要", "claim_step": "S2"},
            {"id": "S3", "label": "S3：影子执行、结构查询与冻结域外投影比较", "claim_step": "S3"},
            {"id": "S4", "label": "S4：反事实原因验证、依赖闭合排除与剩余子补丁重放", "claim_step": "S4"},
            {"id": "S5", "label": "S5：生成内容寻址因果验证凭证", "claim_step": "S5"},
            {"id": "S6", "label": "S6：两阶段核验后事务提交或隔离", "claim_step": "S6"},
        ],
        "edges": [
            {"from": "S1", "to": "S2", "label": "来源锚、对象写集和端点依赖"},
            {"from": "S2", "to": "S3", "label": "冻结影响域哈希"},
            {"from": "S3", "to": "S4", "label": "失败查询及关联操作"},
            {"from": "S4", "to": "S5", "label": "排除集合、剩余子补丁和重放结果"},
            {"from": "S5", "to": "S6", "label": "凭证与接受操作标识"},
        ],
    },
    {
        "number": 2,
        "title": "候选图补丁受控更新系统结构示意图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F002", "C015", "C019", "C012"],
        "nodes": [
            {"id": "input", "label": "父图版本、规范图基线及候选图补丁"},
            {"id": "domain", "label": "来源约束影响域模块"},
            {"id": "shadow", "label": "固定基线影子验证模块"},
            {"id": "cause", "label": "反事实归因与依赖闭合排除模块"},
            {"id": "certificate", "label": "因果验证凭证模块"},
            {"id": "decision", "label": "提交选择一致性门"},
            {"id": "store", "label": "提交清单绑定的规范图版本存储"},
            {"id": "output", "label": "图版本、事件及凭证关联结果"},
        ],
        "edges": [
            {"from": "input", "to": "domain", "label": "来源锚与端点依赖"},
            {"from": "domain", "to": "shadow", "label": "冻结影响域"},
            {"from": "shadow", "to": "cause", "label": "查询结果"},
            {"from": "cause", "to": "certificate", "label": "反事实检查及剩余子补丁"},
            {"from": "certificate", "to": "decision", "label": "内容摘要"},
            {"from": "decision", "to": "store", "label": "一致时"},
            {"from": "store", "to": "output", "label": "单库事务"},
        ],
    },
    {
        "number": 3,
        "title": "反事实原因验证与依赖闭合排除机制图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F003", "F005", "C008", "C009", "C010", "C020"],
        "nodes": [
            {"id": "frozen", "label": "冻结：基线版本与原始影响域哈希"},
            {"id": "failure", "label": "失败结构查询及关联操作标识"},
            {"id": "seed", "label": "逐个操作作为排除种子"},
            {"id": "closure", "label": "加入依赖被排除实体的关系操作"},
            {"id": "counterfactual", "label": "从同一基线重放并检查目标失败是否消失"},
            {"id": "verified", "label": "反事实原因候选空间"},
            {"id": "solver", "label": "精确枚举或带性质标记的固定点回退"},
            {"id": "revalidate", "label": "剩余子补丁在冻结影响域下重新验证"},
        ],
        "edges": [
            {"from": "frozen", "to": "failure", "label": "统一验证边界"},
            {"from": "failure", "to": "seed", "label": "操作关联"},
            {"from": "seed", "to": "closure", "label": "端点依赖"},
            {"from": "closure", "to": "counterfactual", "label": "排除闭包"},
            {"from": "counterfactual", "to": "verified", "label": "目标失败消失"},
            {"from": "verified", "to": "solver", "label": "候选集合"},
            {"from": "solver", "to": "revalidate", "label": "待排除集合"},
        ],
    },
    {
        "number": 4,
        "title": "因果验证凭证与提交清单绑定机制图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F005", "C019", "C012", "E005", "E006"],
        "nodes": [
            {"id": "inputs", "label": "基线、候选操作、冻结域、查询原因、排除/接受操作及重放结果"},
            {"id": "canonical", "label": "规范序列化验证清单"},
            {"id": "cert", "label": "内容摘要形成因果验证凭证标识"},
            {"id": "consensus", "label": "提交判定阶段重算凭证"},
            {"id": "selection", "label": "判定=评估=凭证的接受操作标识"},
            {"id": "commitcheck", "label": "提交执行阶段再次重算凭证"},
            {"id": "manifest", "label": "生成并持久化提交清单摘要"},
            {"id": "result", "label": "一致则写入图版本；不一致则隔离或拒绝重试"},
        ],
        "edges": [
            {"from": "inputs", "to": "canonical", "label": "字段绑定"},
            {"from": "canonical", "to": "cert", "label": "SHA-256"},
            {"from": "cert", "to": "consensus", "label": "首次核验"},
            {"from": "consensus", "to": "selection", "label": "凭证一致"},
            {"from": "selection", "to": "commitcheck", "label": "提交选择"},
            {"from": "commitcheck", "to": "manifest", "label": "二次核验"},
            {"from": "manifest", "to": "result", "label": "幂等清单"},
        ],
    },
    {
        "number": 5,
        "title": "联合抽取与实体关系双层规范化机制图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F006", "C001", "C002", "C003", "C004", "C005", "C006"],
        "nodes": [
            {"id": "segment", "label": "技术文档源片段"},
            {"id": "joint", "label": "同批次实体提及、关系候选及证据片段"},
            {"id": "namespace", "label": "片段命名空间与证据先行校验"},
            {"id": "endpoint", "label": "提及标识到规范实体标识的端点映射"},
            {"id": "entity", "label": "同类型、来源完整、跨簇成员对实体合并"},
            {"id": "relation", "label": "谓词、对称端点及限定信息关系身份"},
            {"id": "lineage", "label": "规范实体、规范关系及逐条源断言快照"},
            {"id": "patch", "label": "来源绑定的操作级候选图补丁"},
        ],
        "edges": [
            {"from": "segment", "to": "joint", "label": "一次联合结果"},
            {"from": "joint", "to": "namespace", "label": "共享局部标识"},
            {"from": "namespace", "to": "endpoint", "label": "有效证据引用"},
            {"from": "endpoint", "to": "entity", "label": "稳定实体端点"},
            {"from": "entity", "to": "relation", "label": "规范实体标识"},
            {"from": "relation", "to": "lineage", "label": "身份及谱系"},
            {"from": "lineage", "to": "patch", "label": "操作化"},
        ],
    },
    {
        "number": 6,
        "title": "版本贡献、删除墓碑与追加式历史补偿机制图",
        "type": "methodology",
        "orientation": "vertical",
        "source_ids": ["F004", "C013"],
        "nodes": [
            {"id": "v1", "label": "历史图版本及对象贡献"},
            {"id": "later", "label": "后续贡献、后续删除墓碑或重新创建生命周期"},
            {"id": "request", "label": "指定历史版本补偿请求"},
            {"id": "safe", "label": "逐事件安全补偿条件检查"},
            {"id": "remove", "label": "移除允许移除的目标版本贡献"},
            {"id": "skip", "label": "记录后续依赖导致的跳过操作"},
            {"id": "recompute", "label": "按剩余贡献、墓碑和新生命周期重算"},
            {"id": "new", "label": "追加新的历史补偿图版本"},
        ],
        "edges": [
            {"from": "v1", "to": "later", "label": "时间推进"},
            {"from": "later", "to": "request", "label": "选择目标版本"},
            {"from": "request", "to": "safe", "label": "逆序事件"},
            {"from": "safe", "to": "remove", "label": "允许"},
            {"from": "safe", "to": "skip", "label": "不允许"},
            {"from": "remove", "to": "recompute", "label": "贡献变化"},
            {"from": "skip", "to": "recompute", "label": "保留并记录"},
            {"from": "recompute", "to": "new", "label": "当前状态"},
        ],
    },
]


LEGACY_SPECIFICATION_REVIEW_BASELINE = {
    "technical_field": [
        "本发明涉及知识图谱构建、自然语言处理、图数据质量控制及计算机软件版本治理技术领域，具体涉及一种基于证据契约、影响域验证及补偿求解的多技术判定模块知识图谱受控自进化方法、系统、电子设备及存储介质。",
        "本发明尤其适用于由技术文档持续提取实体和关系并向规范知识图谱增量写入的计算机系统。",
    ],
    "background": [
        "知识图谱构建系统通常从论文、专利、规格书、运维记录或业务规则中提取实体和关系。现有流水线常先执行实体识别，再将实体文本或实体列表交给另一个关系抽取步骤。由于两个步骤所使用的上下文、标识空间和实体名称可能不一致，第二步骤可能无法恢复第一步骤中的实体身份，从而出现关系端点悬空、端点漂移或已明确陈述的关系未被物化。",
        "即使关系能够抽取，企业文档中仍普遍存在大小写、缩写、别名、单位形式和谓词同义形式。同一对象若以多个身份进入图中，会使查询结果分散；不同对象因传递性相似而被误合并，则会把错误传播到相关关系。仅对实体进行去重也无法解决谓词别名、对称端点次序和重复关系证据的问题。",
        "现有自动写图方案还可能把模型输出直接写入生产知识图谱。此类方案难以在写入前说明每个变化来自何处、影响哪些图对象、违反哪项约束，以及某项约束失败时应排除哪些具体操作。采用全量快照回退会覆盖后续正确更新，单纯保存操作日志又不能自动形成满足图依赖的补偿集合。",
        "此外，schema 在长时间运行中可能发生变化。若一次处理任务在不同阶段读取不同的活动 schema，则同一输入难以复现；若多个 schema 提议并发累积或晋升而缺少事务校验，则可能丢失观察证据或以陈旧父版本创建新版本。",
        "因此，需要一种计算机实现的连续控制链，使联合抽取产生的提及身份和证据能够一直传递到规范化、影响域、影子检查、失败归因、补偿求解和版本事务，而不是把多个彼此独立的常规模块简单并列。",
        "本背景技术仅用于说明本发明所面对的技术问题，不构成对任一现有技术范围或法律状态的确认。",
    ],
    "invention_content": {
        "problem": [
            "本发明要解决的第一技术问题是，减少实体与关系分步抽取造成的关系端点身份丢失，并使未能物化的端点具有可审计原因。",
            "本发明要解决的第二技术问题是，在合并同类实体和同义关系的同时保持证据谱系，并限制类型不相容或传递性相似导致的错误合并。",
            "本发明要解决的第三技术问题是，把候选知识变化转换为能够在提交前计算影响、检测结构破坏、归因失败并选择性补偿的版本化图补丁。",
        ],
        "solution": [
            "为解决上述问题，本发明提供如下方法。S1，获取待处理技术文档并划分源片段；联合抽取器对每一片段只需产生一个可共同解析的抽取结果，该结果同时声明实体提及、关系候选和证据片段，关系候选的两个端点引用同一结果中的实体提及标识。联合抽取器可以是生成式模型、判别式模型、规则程序或其组合，关键在于端点与提及共享可校验标识空间。",
            "S2，在汇总不同片段前，把片段标识加入实体提及标识、关系候选标识、主张标识和证据标识，形成运行内唯一标识。先校验证据的来源文档、源片段、文本和置信度字段，再根据保留的证据标识校验主张和关系候选。无效端点、未知提及和规范端点坍缩均形成审计记录。",
            "S3，根据类型与规范文本解析实体提及。合并提议仅在类型相同且来源提及完整时自动接受，并通过 complete-link 条件要求拟合并两个簇中每一对成员均达到阈值。实体合并保留别名、原实体标识、提及和片段。关系在实体端点稳定后进行谓词规范化、对称端点排序和关系身份聚合，并保留源关系候选、证据和可逆身份假设。",
            "S4，把规范实体和规范关系转换为更新操作。实体操作和关系操作均具有操作标识、对象标识、更新后内容、来源、证据契约和声明影响域；关系操作还声明其依赖的两个规范实体。当前自动规划实施例生成证据化 upsert 操作，普通 delete 操作不属于该自动影子规划实施例。",
            "S5，合并各更新操作的声明影响域，从证据契约取得文档、片段和证据边界，加入关系端点、谓词和规范图基线中的一跳相关关系，从而形成可计算影响域。基于更新操作生成规范实体存在、关系端点可解析和规范关系键唯一等结构不变量，每个查询记录可能导致其失败的更新操作标识。",
            "S6，把候选补丁应用到内存影子图或其他隔离图环境；在相同基线执行两次并比较规范化快照摘要；从基线和影子快照中移除影响域对象并比较剩余投影摘要。该域外投影检查是所定义结构投影的一致性检查，不表示任意业务查询的语义等价证明。",
            "S7，若结构查询失败，从失败查询取得直接因果操作，加入因实体操作被排除而必须排除的依赖关系操作，得到依赖闭合候选集合。对候选子集进行排除后重放，以结构不变量通过和域外投影一致为约束，选择代价较小的补偿操作子集。随后由证据、重放、非干扰、不变量和效用技术判定模块产生硬门结果。",
            "S8，仅在全部硬门和策略允许时，规范图存储才在单库事务内检查补丁幂等性和父版本新鲜性，写入剩余操作、对象、证据、图版本、版本事件和活动指针。未通过时补丁保持候选或隔离。运行级发布视图是规范提交后的派生结果，不把两个独立存储描述为跨库原子事务。",
            "本发明还提供与上述方法相对应的系统。系统各模块之间传递实体提及标识映射、证据契约、影响域、带因果操作标识的查询结果、补偿操作子集和图版本标识，使各模块形成强制数据依赖而非彼此独立的功能列表。",
            "本发明还提供电子设备及非暂态计算机可读存储介质，用于执行上述方法。",
        ],
        "beneficial_effects": [
            "关系端点使用同一抽取结果中的实体提及标识，避免后续关系步骤仅凭名称重新寻找端点，并使端点缺失能够被记录和复核。",
            "实体与关系分别进行类型受限规范化，既减少别名和谓词重复，又保留每次合并的原标识和证据谱系。",
            "证据契约把来源字段转化为影响域和结构查询的机器输入，使证据不仅用于展示，还直接参与提交控制。",
            "影子图、确定性重放和域外投影检查在规范图写入前发现当前定义范围内的结构破坏。",
            "失败查询带有因果操作标识，补偿器在依赖闭合约束下排除相关操作，能够在满足约束的情况下保留其他候选知识。",
            "父版本校验和补丁幂等检查降低陈旧补丁覆盖以及重复提交的风险，版本事件为后续审计提供依据。",
            "版本贡献和删除墓碑支持追加式选择性补偿，避免简单恢复旧快照时覆盖后续贡献或复活后续已删除对象。",
            "图、证据、版本和技术判定记录的关联可视化使审核人员能够沿同一运行和图版本定位变化来源及门控原因。",
        ],
    },
    "figure_descriptions": [
        "图1为本发明知识图谱受控自进化方法的总体流程图。",
        "图2为本发明知识图谱受控自进化系统的结构示意图。",
        "图3为本发明失败查询归因与补偿求解的示意图。",
        "图4为本发明规范图版本提交与选择性补偿的示意图。",
    ],
    "equations": [
        {
            "number": 1,
            "source_location": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
            "source_ids": ["E001"],
            "expression": "c_combined = 1 - ∏_(i=1)^m (1 - d_i c_i)",
            "latex": "c_{combined}=1-\\prod_{i=1}^{m}(1-d_i c_i)",
            "symbols": [
                {"symbol": "c_combined", "meaning": "同一规范关系的合并置信度"},
                {"symbol": "m", "meaning": "待聚合证据项数量"},
                {"symbol": "c_i", "meaning": "第i项证据对应的置信度"},
                {"symbol": "d_i", "meaning": "第i项证据的折扣系数"},
            ],
            "technical_role": "采用有界 noisy-OR 聚合同一规范关系的多项证据。",
            "description": "其中，首项证据的折扣系数可取1，后续项可取小于1的值，以降低把相关证据误当作完全独立证据造成的过度增益。",
        },
        {
            "number": 2,
            "source_location": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
            "source_ids": ["E002"],
            "expression": "c_relation = min(c_combined, c_max + α(n_seg - 1), c_cap)",
            "latex": "c_{relation}=\\min(c_{combined},c_{max}+\\alpha(n_{seg}-1),c_{cap})",
            "symbols": [
                {"symbol": "c_relation", "meaning": "输出的规范关系置信度"},
                {"symbol": "c_max", "meaning": "各项证据置信度中的最大值"},
                {"symbol": "α", "meaning": "每增加一个来源片段所允许的置信度增量系数"},
                {"symbol": "n_seg", "meaning": "包含关系证据的不同源片段数量"},
                {"symbol": "c_cap", "meaning": "预设全局置信度上限"},
            ],
            "technical_role": "限制聚合置信度随证据数量无界上升。",
            "description": "一个实施例取α为0.08、c_cap为0.99；所述数值可根据领域验证集配置，而不限定本发明范围。",
        },
        {
            "number": 3,
            "source_location": "src/evolex/nodes/evolution.py，_compensation_objective",
            "source_ids": ["E003"],
            "expression": "J(R) = λ_1 |R| + λ_2 B(R) + λ_3 L_e(R)",
            "latex": "J(R)=\\lambda_1|R|+\\lambda_2 B(R)+\\lambda_3 L_e(R)",
            "symbols": [
                {"symbol": "R", "meaning": "从候选图补丁中排除的补偿操作子集"},
                {"symbol": "|R|", "meaning": "补偿操作子集所含更新操作数量"},
                {"symbol": "B(R)", "meaning": "补偿操作子集覆盖的实体、关系和谓词范围"},
                {"symbol": "L_e(R)", "meaning": "随补偿操作子集排除的证据、提及和证据标识数量"},
                {"symbol": "λ_1、λ_2、λ_3", "meaning": "三个非负代价权重"},
            ],
            "technical_role": "在满足依赖闭合、不变量和非干扰约束时评价补偿操作子集。",
            "description": "一个实施例依次取λ_1为1.00、λ_2为0.05、λ_3为0.02；同一代价下还可优先保留置信度和较高的剩余操作。",
        },
        {
            "number": 4,
            "source_location": "src/evolex/agentic/agents.py，AgentProposal.utility",
            "source_ids": ["E004"],
            "expression": "U(a) = EIG(a) - λ C(a) - μ R(a)",
            "latex": "U(a)=EIG(a)-\\lambda C(a)-\\mu R(a)",
            "symbols": [
                {"symbol": "a", "meaning": "待选择的技术判定或工具动作"},
                {"symbol": "U(a)", "meaning": "动作效用"},
                {"symbol": "EIG(a)", "meaning": "动作的预期信息增益"},
                {"symbol": "C(a)", "meaning": "动作执行成本"},
                {"symbol": "R(a)", "meaning": "动作风险量"},
                {"symbol": "λ、μ", "meaning": "成本与风险权重"},
            ],
            "technical_role": "对执行动作进行质量、成本与风险平衡，并为非负效用硬门提供输入。",
            "description": "当动作效用低于零时，可拒绝该动作或保持候选状态；该调度公式不是对知识内容真实性的判断。",
        },
    ],
    "embodiments": [
        {
            "heading": "实施例1：联合抽取与证据先行校验",
            "paragraphs": [
                "在本实施例中，计算机读取一份技术文档，生成文档标识并按标题、段落或字符上限划分为多个源片段，每个源片段具有片段标识。运行开始时读取并固定活动 schema 版本，后续节点均使用该固定版本。",
                "联合抽取器为每个源片段输出一个结构化对象。结构化对象至少具有mentions、relations和evidence_spans字段。每个实体提及包含片段局部mention_id、文本、类型和置信度；每个关系候选包含subject_mention_id、predicate、object_mention_id、证据文本和置信度，两个端点必须等于同一结构化对象中已经声明的mention_id。",
                "例如，源句“Aquila Processor depends on Nova Cache.”可生成提及m1=Aquila Processor、m2=Nova Cache，以及关系候选(m1, depends_on, m2)。汇总时分别形成seg-0001:m1、seg-0001:m2和seg-0001:rc-0001，从而避免另一片段复用m1时发生碰撞。",
                "校验器先过滤缺少文档标识、片段标识、证据文本或合理置信度的证据对象，再根据保留下来的证据标识过滤主张和关系引用。随后实体解析器生成mention_id到entity_id映射，关系物化器使用该映射取得两个规范端点。若端点未解析或两个端点合并后成为同一实体，则关系候选进入失败清单。",
                "只要至少有一条有效联合关系成功物化，本实施例不进行第二次独立关系模型调用；只有没有任何有效联合关系可以物化时，才执行兼容回退。回退结果标记为relation_fallback或heuristic_fallback，以便评估时与联合关系区分。",
            ],
        },
        {
            "heading": "实施例2：实体与关系双层规范化",
            "paragraphs": [
                "实体解析先对文本进行Unicode安全的大小写折叠、空白和分隔符归一化，并可应用领域别名表及单位同义表。实体类型不同的两个对象不进入自动合并候选。",
                "对同类型对象计算规范文本精确相等、别名等价、缩写等价或词元重合分值。自动合并还要求两个对象均具有来源提及。为避免A接近B、B接近C但A不接近C造成传递性误合并，拟合并两个簇之间的所有成员对均需达到自动合并阈值。未满足该条件的提议保持held状态。",
                "合并后的规范实体保留canonical_text、entity_type、aliases、source_entity_ids、source_mention_ids、segment_ids和confidence。实体身份决定以LINK、CREATE_CANDIDATE或HOLD等状态记录，使关系端点映射可以重建。",
                "关系规范化在上述实体端点稳定后执行。谓词先进行大小写和下划线规范，再根据谓词别名表映射。对于related_to等对称谓词，按照规范实体标识排序端点。具有相同主端点、规范谓词、客端点和限定信息的关系被聚合。",
                "关系聚合保留source_relation_ids、source_relation_candidate_ids、evidence_ids、evidence_texts、segment_ids和predicate_aliases，并形成identity_hypothesis_id。对于has_status、has_version、located_in或has_owner等预先声明的功能性谓词，同一主端点出现不同客端点时产生冲突；普通多值谓词不因此被误判为冲突。",
                "关系置信度可按公式（1）和公式（2）计算。该实现对后续证据使用折扣并设置片段增益上限，记录片段数只表示结构来源边界，不把各片段无条件认定为科学或法律意义上的独立证据。",
            ],
        },
        {
            "heading": "实施例3：证据补丁、影响域与影子图",
            "paragraphs": [
                "补丁规划器读取规范实体、规范关系、提及映射和证据对象。每个实体操作携带规范实体标识、文本、类型、置信度、别名、提及记录、affected_domain和evidence_contract。每个关系操作携带规范关系标识、两个端点、规范谓词、置信度、证据记录、depends_on_entity_ids、affected_domain和evidence_contract。",
                "实体证据契约可包含source_mention_ids、source_segment_ids、source_document_ids、same_type和provenance_complete；关系证据契约可包含evidence_ids、source_candidate_ids、source_document_ids、endpoint_mapping_complete和provenance_complete。补丁标识根据规范化操作内容计算，以用于幂等检查。",
                "影响域生成器先合并各操作声明的实体、关系、谓词、文档、片段和证据标识，再从关系更新后内容加入两个端点和谓词。随后扫描规范图基线，把与受影响端点相连或具有受影响谓词的一跳关系及其端点加入影响域，并保存每一扩展的依据。",
                "影子执行器复制规范图基线并应用当前实施例支持的upsert_entity和upsert_relation操作。执行时统计证据增量，并生成实体存在、关系端点存在、关系身份唯一等查询。每个查询具有query_id、passed、caused_by_operation_ids、description和impact_domain字段。",
                "确定性检查在同一基线重复执行同一有序操作集，比较规范化实体和关系快照的摘要。域外投影检查从基线和影子图分别去除影响域内的实体和关系，排序后比较摘要。该检查仅覆盖所定义的数据结构和一跳影响边界，客户可以补充多跳或领域业务查询。",
            ],
        },
        {
            "heading": "实施例4：失败归因、补偿与提交硬门",
            "paragraphs": [
                "当影子查询失败时，补偿器读取failed_queries中的caused_by_operation_ids形成直接因果操作集合。若被排除的是实体操作，则依赖该实体的关系操作也必须加入排除集合，直至集合不再变化，以形成依赖闭包。",
                "因果候选数量不超过十六个时，补偿器枚举候选子集，对每个子集再次做依赖闭包并排除重复集合。把排除后的剩余操作重新应用到同一基线；只有不存在失败查询且域外投影一致的集合才是可行集合。对可行集合按公式（3）排序，并以排除操作数、证据损失和保留置信度作为顺序判据。",
                "因果候选数量超过十六个时，可以从全部因果闭包开始逐项尝试移除排除项，得到删除意义下的包含极小集合。输出必须把solver_mode记为deterministic_deletion_minimal_fallback，并把optimality记为inclusion_minimal_not_global，从而不把该结果描述成大空间全局最小代价。",
                "补偿后的剩余补丁再次进行影子回放。EvidenceContract检查验证接受操作具有完整来源且影响域由证据派生；DeterministicReplay检查验证重复快照；NonInterference检查验证域外投影；Invariant检查验证全部结构查询；Utility检查根据公式（4）要求更新效用非负。",
                "此外，发布置信度可以由证据覆盖、关系证据覆盖、关系一致性、schema匹配和质量分数组合，并扣除图稀疏惩罚。只有硬门和策略均允许时进入规范图提交；否则保持candidate或quarantined并记录原因。",
            ],
        },
        {
            "heading": "实施例5：规范图提交与版本补偿",
            "paragraphs": [
                "规范图存储维护graph_versions、version_events和活动版本元数据，并为实体、别名、提及、关系和关系证据记录其版本贡献。提交开始时执行即时写事务，先根据patch_id查询是否已经提交；若已提交则返回同一版本。随后比较补丁parent_version_id与当前活动图版本，不一致时拒绝陈旧补丁。",
                "在同一规范图事务内，系统创建图版本、应用实体和关系操作、记录每个操作的前态、后态、逆操作、证据契约和触发模块，并更新活动版本。任一步骤异常均回滚该规范图事务。规范图事务不跨越候选库、schema库、检查点库或运行级发布库。",
                "删除实体或关系时写入与版本关联的删除墓碑。对已删除对象的后续新建贡献形成新的对象生命周期，不继承已经完全移除的旧贡献置信度和创建版本。",
                "回滚指定历史版本时，不删除该历史版本，而是创建新的compensation图版本。系统逆序处理目标版本事件，移除目标版本对应的贡献，并根据仍存活的贡献和时间较后的删除墓碑重算当前实体或关系。如果较后版本已经删除对象，则回滚较早版本不会使对象复活；如果较后版本重新新增对象，则回滚较早版本不会删除该新生命周期。",
                "该版本补偿用于实现代码所支持的实体、关系、别名、提及和证据贡献，不声称任意图变换均可交换回滚，也不声称能够自动拆分任意历史误合并实体簇。",
            ],
        },
        {
            "heading": "实施例6：schema治理与审计可视化",
            "paragraphs": [
                "运行启动时从schema存储读取活动schema版本并写入运行状态。运行中的候选对象均记录该schema_version。未知类型、谓词和属性按proposal_type及规范symbol分组，内容稳定散列产生proposal_id，使同一提议重放时累积证据而不是重复创建。",
                "schema提议可以统计来源运行和文档数量、关系模式一致性及证据覆盖。正式晋升由受控命令或审批流程触发，在BEGIN IMMEDIATE事务内重新读取活动版本，并以该版本作为新schema版本的父版本。观察提议不等于自动晋升。",
                "可视化模块读取规范图存储、候选注册、schema存储和运行状态的只读快照，分别生成当前活动规范图的全局自包含HTML和按来源文档内容快照投影的逐文档自包含HTML。逐文档投影以实体提及和关系证据中的document_id选择直接来源对象，只补入所选关系的主客端点；共享规范实体不使仅由其他文档支持的关系或证据进入当前页面。",
                "每个图页面把图数据、样式和交互脚本嵌入单一文件，可在无前端服务和后端服务时离线复核。document_id表示内容快照而非权限主体；展示投影是数据最小化，不是访问控制或密码学隔离。页面用于审计和人工复核，不替代提交硬门；多用户生产环境仍需身份认证、访问控制、敏感证据脱敏和日志完整性保护。",
            ],
        },
        {
            "heading": "实施例7：系统、电子设备及存储介质",
            "paragraphs": [
                "图2所示系统可以由一个或多个计算进程实现。联合抽取模块输出的提及标识和证据由双层规范化模块消费；双层规范化模块的规范对象由补丁规划模块消费；影响域模块的输出限定影子验证模块的查询范围；影子验证模块的失败查询向补偿模块提供因果操作标识；门控模块只消费补偿后重放结果；规范图存储模块只接收门控允许的剩余补丁。",
                "电子设备包括至少一个处理器、存储器、输入输出接口和通信接口。存储器保存实现上述模块的程序指令、固定schema、候选状态和图版本元数据；处理器执行程序指令时完成权利要求所述步骤。",
                "非暂态计算机可读存储介质可以是磁盘、固态存储器、只读存储器、随机存取存储器或其他能够保存程序指令的介质。程序在处理器上执行时，使处理器实现上述受控自进化方法。",
                "具体实现可采用关系数据库、原生图数据库或对象存储保存不同边界的数据，但规范图的一次版本提交应由一个明确的事务边界或具有等效原子提交语义的存储机制完成。模型供应商、编程语言、工作流框架和数据库品牌均不构成必要限定。",
            ],
        },
    ],
}


LEGACY_ABSTRACT_REVIEW_BASELINE = (
    "本发明公开一种知识图谱受控自进化方法、系统、设备及介质。"
    "对技术文档片段一次联合生成实体提及、引用提及标识的关系候选及证据；"
    "经证据先行校验和实体、关系双层规范化后，形成携带证据契约、端点依赖和声明影响域的更新补丁。"
    "系统由证据契约及图依赖派生影响域，在影子图执行结构不变量、确定性重放和域外投影检查，"
    "把失败查询归因到具体操作并在依赖闭合约束下选择补偿子集。"
    "仅当证据、重放、非干扰、不变量、效用及策略门通过时，才在规范图事务中提交剩余操作并记录图版本；否则隔离。"
    "本发明能够降低关系端点失配，使知识更新具有可追溯、提交前验证和选择性补偿能力。"
)


SPECIFICATION = {
    "technical_field": [
        "本发明涉及知识图谱、图数据库完整性控制、数据来源追踪及软件版本治理技术领域，具体涉及一种基于来源约束影响域、反事实操作归因和内容寻址验证凭证的知识图谱候选图补丁验证和版本提交方法、系统、电子设备及计算机可读存储介质。",
        "本发明可用于从论文、专利、规格书、运维记录或业务文档持续形成候选知识，并在写入规范知识图谱之前进行有界验证、局部排除和版本化提交。",
    ],
    "background": [
        "持续构建知识图谱时，抽取模型、规则程序或外部数据连接器会产生包含实体和关系的增量知识。直接把增量知识写入正式图，可能造成关系端点悬空、重复关系身份、来源缺失或图约束破坏。全量拒绝一个候选批次虽然能够阻止错误写入，却会同时丢失同一批次中未受影响的有效知识。",
        "已有方案分别涉及联合实体关系抽取、实体或关系规范化、局部子图更新、影子环境验证、数据库约束修复、事务补偿以及图版本管理。上述单项技术并不能当然保证：验证所使用的基线、影响范围和操作集合与最终写入的操作集合完全相同，也不能当然保证在局部排除部分候选操作后仍然沿用原始验证边界。",
        "一种常见错配发生在验证与提交之间。验证节点可能针对候选操作集合A生成通过结果，而提交节点实际收到集合B；或者同一候选补丁在重试时采用不同的接受操作集合，却因候选补丁标识相同而错误返回先前版本。普通日志能够记录结果，但若日志没有把基线摘要、影响域摘要、查询—操作对应关系、排除集合和实际接受操作共同绑定，则无法以确定性重算方式发现该错配。",
        "另一问题在于所谓查询原因可能只是生成查询时静态附加的操作标识。若没有在固定基线上排除该操作及其依赖并重新执行，就不能判断目标失败是否随之消失。对知识图谱而言，排除实体操作还可能使依赖该实体作为端点的关系操作失效，因此原因验证和排除求解需要消费图操作之间的端点依赖。",
        "实体和关系的上游生成同样会影响补丁质量。若实体与关系分开抽取，关系步骤可能无法恢复实体步骤中的身份；若同类实体或同义关系被无条件传递合并，错误身份会沿图边传播；若同一三元组在不同时间或条件下的限定信息被忽略，也会把不同事实合并为一条关系。",
        "因此，需要一种计算机实现的连续数据完整性控制链：把来源锚转换为固定验证边界，通过同基线反事实重放验证失败操作，在端点依赖闭包内保留可行的剩余子补丁，并用可重算内容寻址凭证及提交清单把验证结果绑定到实际版本事件。上述背景仅用于说明本发明面对的技术问题，不构成对任一文献范围、公开日或法律状态的确认。",
    ],
    "invention_content": {
        "problem": [
            "本发明要解决的第一技术问题是，在候选知识图谱更新提交前建立不会随局部排除而收缩的来源约束验证边界。",
            "本发明要解决的第二技术问题是，把结构查询与候选操作之间的静态关联转化为通过同基线重放验证的反事实原因记录，并在实体—关系端点依赖下局部排除失败相关操作。",
            "本发明要解决的第三技术问题是，检测验证结果、提交选择、幂等重试和实际版本事件之间的错配，使通过验证的剩余子补丁与正式写入事件可重算地绑定。",
            "本发明还要改善实体与关系分步抽取造成的端点丢失，以及实体或关系合并中来源断裂和限定事实误合并的问题。",
        ],
        "solution": [
            "S1，获取固定于父图版本的规范图基线和候选图补丁。候选图补丁由具有稳定操作标识的实体更新操作和关系更新操作组成。每个操作具有对象标识、对象后态、声明影响对象及与对象类型相适配的来源锚；关系更新操作还声明其依赖的端点实体。当前自动规划实施例针对来源完整的upsert_entity和upsert_relation操作，普通删除操作不属于该自动规划实施例。",
            "S2，合并全部操作声明的实体、关系、谓词、来源文档、来源片段和证据范围，再加入关系操作端点及规范图基线中与受影响端点或谓词相连的一跳关系，形成原始影响域。对规范序列化后的原始影响域计算摘要，并在后续反事实检查、排除求解和剩余子补丁重放中保持该原始影响域不变。接受操作自身声明的影响域可以另行计算并记录，但不替换冻结的验证边界。",
            "S3，把候选图补丁应用到固定于父图版本的影子图，执行规范实体存在、关系端点可解析和规范关系身份唯一等结构查询。每项查询包含查询标识、通过状态、关联操作标识和冻结影响域摘要。系统在相同基线重复执行候选补丁以获得确定性重放摘要，并从基线与影子快照中移除冻结影响域对象后比较域外投影摘要。该比较限定于所定义结构投影，不声称证明任意业务查询的语义等价。",
            "S4，对每一失败查询的每一关联操作标识执行反事实检查：以该操作作为排除种子；若其对象为实体，则递归加入依赖该实体端点的关系操作；把剩余操作从同一规范图基线重放；若目标查询不再失败，则把排除种子列入反事实原因操作。求解器只在反事实原因操作及其端点依赖闭包内搜索待排除更新操作集合，并要求剩余子补丁通过全部结构查询及冻结影响域外投影比较。不存在失败查询时，待排除更新操作集合为空。",
            "S5，将规范图基线摘要、候选操作摘要、冻结影响域摘要、查询与反事实原因对应记录、求解器结果、待排除更新操作集合、接受操作集合、剩余子补丁摘要、最终影子快照摘要和门结果组成验证清单。验证清单经键排序、确定性列表排序和无歧义字段编码后进行规范序列化，再计算内容摘要以形成因果验证凭证标识。所述凭证是内容寻址一致性清单，不是数字签名，不提供密钥身份认证，也不判断抽取知识在现实世界中的真实性。",
            "S6，提交判定节点根据候选补丁、基线和评估结果重算因果验证凭证，并要求判定、评估和凭证中的接受操作标识一致。提交执行节点在写图前再次重算。规范图存储进一步形成提交清单，其包含候选补丁标识、父图版本、排序后的接受操作标识、接受操作内容摘要和凭证标识。仅在父图版本、凭证和提交清单均一致时，在单一规范图事务中写入剩余操作、图事件、图版本和活动版本指针；不一致时隔离候选图补丁或拒绝幂等重试。",
            "在可选上游实施例中，同一源片段的一次联合抽取结果同时声明实体提及、关系候选和证据片段，关系端点引用该结果内的提及标识。系统先形成有效证据标识集合，再校验主张和关系候选；关系物化直接使用提及标识到规范实体标识的映射，只有零条有效联合关系能够物化时才启动独立关系回退。",
            "在另一可选上游实施例中，实体合并仅针对同类型且来源完整的对象，并要求两个候选簇的任意跨簇成员对均达到阈值。关系在实体端点稳定后规范谓词和对称端点，以端点、谓词及限定信息摘要形成身份，并为每条源关系保留可重建字段组成的源断言快照。",
            "本发明还提供镜像上述连续数据依赖的系统、执行所述方法的电子设备和保存相应程序的计算机可读存储介质。",
        ],
        "beneficial_effects": [
            "原始影响域在候选操作局部排除后仍保持冻结，避免通过缩小验证范围掩盖原候选补丁可能影响的对象。",
            "逐操作依赖闭包排除和同基线反事实重放把静态查询关联转化为可复核的原因记录，降低无关操作进入求解候选空间的概率。",
            "依赖闭合局部排除使满足约束的剩余子补丁能够继续提交，相比整候选补丁拒绝可保留更多未受失败影响的候选知识。",
            "因果验证凭证绑定验证全过程，判定与提交两次重算能够发现基线、查询原因、求解结果、排除集合、接受操作或最终影子摘要被替换。",
            "提交清单把候选补丁标识与实际接受操作和凭证标识共同持久化，同补丁不同选择的重试被拒绝，避免返回与本次凭证不对应的历史图版本。",
            "同批次提及端点和证据先行引用校验降低关系端点身份丢失及悬空证据传播。",
            "同类型跨簇成员对约束和限定信息关系身份减少实体过度合并及不同限定事实误合并，并通过源断言快照保留可审计谱系。",
            "版本贡献、删除墓碑和安全跳过记录支持追加式历史补偿，避免简单恢复旧快照覆盖后续贡献或错误复活后续删除对象。",
        ],
    },
    "figure_descriptions": [
        "图1为本发明知识图谱候选图补丁验证和版本提交方法的总体流程图，并作为摘要附图。",
        "图2为本发明候选图补丁受控更新系统的结构示意图。",
        "图3为本发明反事实原因验证与依赖闭合排除机制图。",
        "图4为本发明因果验证凭证与提交清单绑定机制图。",
        "图5为本发明联合抽取与实体关系双层规范化机制图。",
        "图6为本发明版本贡献、删除墓碑与追加式历史补偿机制图。",
    ],
    "equations": [
        {
            "number": 1,
            "source_location": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
            "source_ids": ["E001"],
            "expression": "c_combined = 1 - ∏_(i=1)^m (1 - d_i c_i)",
            "latex": "c_{combined}=1-\\prod_{i=1}^{m}(1-d_i c_i)",
            "symbols": [
                {"symbol": "c_combined", "meaning": "同一规范关系的组合置信度"},
                {"symbol": "m", "meaning": "证据项数量"},
                {"symbol": "c_i", "meaning": "第i项源断言置信度"},
                {"symbol": "d_i", "meaning": "第i项证据折扣系数"},
            ],
            "technical_role": "可选地聚合同一限定关系身份下的多项证据。",
            "description": "该公式属于关系评分实施方式，不构成主权项必要特征。首项折扣可取1，后续项可取0.85。",
        },
        {
            "number": 2,
            "source_location": "src/evolex/nodes/relation_merge.py，_aggregate_confidence",
            "source_ids": ["E002"],
            "expression": "c_relation = min(c_combined, c_max + α(n_seg - 1), c_cap)",
            "latex": "c_{relation}=\\min(c_{combined},c_{max}+\\alpha(n_{seg}-1),c_{cap})",
            "symbols": [
                {"symbol": "c_relation", "meaning": "规范关系输出置信度"},
                {"symbol": "c_max", "meaning": "最高单项置信度"},
                {"symbol": "α", "meaning": "独立片段增益系数"},
                {"symbol": "n_seg", "meaning": "不同来源片段数量"},
                {"symbol": "c_cap", "meaning": "全局上限"},
            ],
            "technical_role": "限制重复证据造成的置信度无界增长。",
            "description": "一个实施例取α为0.08、c_cap为0.99；数值应由领域验证集校准。",
        },
        {
            "number": 3,
            "source_location": "src/evolex/nodes/evolution.py，_compensation_objective",
            "source_ids": ["E003"],
            "expression": "J(R) = λ_1 |R| + λ_2 B(R) + λ_3 L_e(R)",
            "latex": "J(R)=\\lambda_1|R|+\\lambda_2 B(R)+\\lambda_3 L_e(R)",
            "symbols": [
                {"symbol": "R", "meaning": "待排除更新操作集合"},
                {"symbol": "|R|", "meaning": "被排除操作数量"},
                {"symbol": "B(R)", "meaning": "被排除操作覆盖的实体、关系和谓词数量"},
                {"symbol": "L_e(R)", "meaning": "随排除丢失的证据、提及和证据标识数量"},
                {"symbol": "λ_1、λ_2、λ_3", "meaning": "非负权重"},
            ],
            "technical_role": "在依赖闭合、结构查询和域外投影约束下评价待排除集合。",
            "description": "一个实施例取λ_1=1.00、λ_2=0.05、λ_3=0.02；同代价时优先保留置信度和较高的操作。",
        },
        {
            "number": 4,
            "source_location": "src/evolex/agentic/agents.py，AgentProposal.utility",
            "source_ids": ["E004"],
            "expression": "U_agent(a) = EIG(a) - λ C(a) - μ R(a)",
            "latex": "U_{agent}(a)=EIG(a)-\\lambda C(a)-\\mu R(a)",
            "symbols": [
                {"symbol": "a", "meaning": "待调度的Agent工具动作"},
                {"symbol": "EIG(a)", "meaning": "预期信息增益"},
                {"symbol": "C(a)", "meaning": "动作执行成本"},
                {"symbol": "R(a)", "meaning": "动作风险量"},
                {"symbol": "λ、μ", "meaning": "成本与风险权重"},
            ],
            "technical_role": "仅用于Agent动作调度。",
            "description": "本公式不等同于图更新提交效用，不作为权利要求中的提交选择公式。",
        },
        {
            "number": 5,
            "source_location": "src/evolex/nodes/evolution.py，_build_validation_certificate、_snapshot_hash",
            "source_ids": ["E005"],
            "expression": "id_cert = 'cvc-' || SHA-256(CanonicalJSON(M_v))",
            "latex": "id_{cert}=\\operatorname{prefix}_{cvc}\\Vert\\operatorname{SHA256}(\\operatorname{CanonicalJSON}(M_v))",
            "symbols": [
                {"symbol": "id_cert", "meaning": "因果验证凭证标识"},
                {"symbol": "M_v", "meaning": "验证清单"},
                {"symbol": "CanonicalJSON", "meaning": "键排序、确定性列表及无歧义编码的规范序列化"},
                {"symbol": "||", "meaning": "字节连接"},
            ],
            "technical_role": "把基线、影响域、反事实原因、排除与接受操作以及验证结果绑定为可重算标识。",
            "description": "SHA-256可由满足确定性内容寻址要求的其他摘要算法替代；当前实施例不是带密钥数字签名。",
        },
        {
            "number": 6,
            "source_location": "src/evolex/repositories/canonical.py，commit_patch、_content_hash",
            "source_ids": ["E006"],
            "expression": "h_commit = SHA-256(CanonicalJSON(patch_id, parent, sort(A), h_A, id_cert))",
            "latex": "h_{commit}=\\operatorname{SHA256}(\\operatorname{CanonicalJSON}(id_{patch},v_{parent},\\operatorname{sort}(A),h_A,id_{cert}))",
            "symbols": [
                {"symbol": "h_commit", "meaning": "提交清单摘要"},
                {"symbol": "patch_id", "meaning": "候选图补丁标识"},
                {"symbol": "parent", "meaning": "父图版本标识"},
                {"symbol": "A", "meaning": "接受操作标识集合"},
                {"symbol": "h_A", "meaning": "接受操作内容摘要"},
                {"symbol": "id_cert", "meaning": "因果验证凭证标识"},
            ],
            "technical_role": "把幂等键绑定到实际接受操作和验证凭证。",
            "description": "同一patch_id命中既有版本时，若h_commit不同则拒绝，不返回原版本作为本次成功结果。",
        },
    ],
    "embodiments": [
        {
            "heading": "实施例1：来源绑定候选图补丁",
            "paragraphs": [
                "规范图存储提供父图版本标识和按规范对象标识排序的基线快照。补丁规划器把上游规范实体和规范关系转换为操作列表；每个操作具有operation_id、action、object_type、object_id、after、affected_domain和evidence_contract字段。关系操作还具有depends_on_entity_ids字段。",
                "实体证据契约可包含source_document_ids、source_segment_ids、source_mention_ids和provenance_complete；关系证据契约可包含source_document_ids、evidence_ids、source_candidate_ids、endpoint_mapping_complete和provenance_complete。不同对象类型不被错误要求具有完全相同字段，而是按照对象类型检查来源锚是否足以定位原文和端点。",
                "候选补丁标识根据全部候选操作的规范序列化内容生成。该标识只代表完整候选操作集合；实际接受操作另外由因果验证凭证和提交清单绑定。自动规划实施例仅产生来源完整的新增或更新操作。",
            ],
        },
        {
            "heading": "实施例2：冻结影响域与影子结构查询",
            "paragraphs": [
                "影响域派生器首先对全部操作的声明域求并集，再加入实体操作的对象、关系操作的身份、谓词和两个端点。对于基线中与任一受影响端点相连、关系身份被声明或谓词被声明的关系，派生器把该关系及其相对端点加入原始影响域。来源文档、片段和证据标识同时进入域记录。",
                "派生器记录每个操作对应的来源锚、来源完整性状态和扩展依据，计算domain_hash。后续所有候选排除重放均传入该冻结域；即使接受操作自身重新派生的声明域更小，也只将较小域作为记录，而不用于替换冻结域外投影边界。",
                "影子执行器复制固定父版本基线，依次应用实体和关系操作。实体查询检查规范实体是否存在及来源是否完整；关系查询检查两个规范端点是否存在及关系来源是否完整；补丁级查询检查由主端点、谓词、客端点和限定信息摘要组成的关系身份是否唯一。",
                "确定性重放比较两次同输入执行的规范化快照摘要。域外投影比较从基线与影子快照中移除冻结影响域实体和关系后所得结构摘要。实现可用独立进程或隔离数据库替代内存影子图，但必须固定基线版本和序列化规则。",
            ],
        },
        {
            "heading": "实施例3：反事实原因验证与待排除集合求解",
            "paragraphs": [
                "失败查询初始携带与该查询生成相关的操作标识。对每一关联操作op，系统计算Close({op})：若闭包中存在实体操作，则把depends_on_entity_ids包含该实体标识的关系操作加入闭包，重复直至不再增加。系统从同一基线重放P减去Close({op})。若目标query_id不存在于失败集合或其通过状态变为真，则记录op为反事实原因操作，并保存闭包及target_failure_resolved=true。",
                "上述反事实定义限于候选图补丁及其端点依赖闭包，不声称给出现实世界因果、统计因果或所有可能数据库原因。没有通过反事实检查的静态关联不进入求解候选空间；若因此不存在可行排除集合，补丁保持隔离。",
                "设反事实候选数量为k。k不超过十六时，枚举候选子集，对每个子集执行依赖闭包、去重及冻结影响域重放。只有结构查询均通过且域外投影一致的集合为可行集合，再按公式（3）及顺序判据选择。其最坏时间约为O(2^k·Replay)。",
                "k超过十六时，从完整因果闭包开始，按稳定操作标识顺序尝试删除一个排除项并重放；只在剩余排除集合仍可行时接受该删除。重复完整扫描直至固定点。该结果标记为deterministic_fixed_point_deletion_fallback和single_deletion_local_minimum_not_global，不声称全局最优，也不无条件声称一般非单调约束下的集合包含极小。",
            ],
        },
        {
            "heading": "实施例4：因果验证凭证、提交选择与幂等清单",
            "paragraphs": [
                "验证清单包括schema标识、patch_id、parent_version_id、baseline_snapshot_hash、candidate_operations_hash、original及frozen impact-domain hash、query_causality、solver_result_hash、excluded_operation_ids、accepted_operation_ids、retained_operations_hash、final_shadow_snapshot_hash和gate_results。query_causality逐查询保存关联操作、反事实原因操作、反事实检查摘要和归因状态。",
                "按照公式（5）生成certificate_id。提交判定节点重新构造完整清单而不是只比较certificate_id字符串；任何字段变化都会导致对象不等或摘要变化。测试分别改变基线版本、查询操作映射、求解模式、排除操作、最终影子摘要及提交判定接受操作，均使凭证验证失败。",
                "提交执行节点再次重构凭证，并强制decision.accepted_operation_ids、evaluation.accepted_operation_ids和certificate.accepted_operation_ids三者相等，同时核对decision.certificate_id。核对失败时不调用规范图存储，并把运行置于quarantined状态。",
                "规范图存储按照公式（6）生成commit_manifest_hash，并随graph_versions记录accepted_operation_ids_json、accepted_operations_hash、certificate_id和commit_manifest_hash。首次写入在BEGIN IMMEDIATE事务内检查父版本、写入剩余操作及graph_events并更新活动指针。相同patch_id重试时，只有提交清单摘要相同才返回既有版本；若接受集合或凭证不同则抛出清单不匹配错误。",
                "内容摘要能检测非预期内容错配，但没有密钥时不能抵抗能够同时改写数据和重新计算摘要的对手。需要对抗性身份认证的部署可在凭证外增加HMAC、数字签名、不可变日志或硬件密钥；这些安全增强不是本实施例的必要限定。",
            ],
        },
        {
            "heading": "实施例5：联合实体—关系—证据抽取与证据先行校验",
            "paragraphs": [
                "对每个源片段，联合抽取器返回mentions、relation_candidates和evidence_spans。关系候选的subject_mention_id和object_mention_id必须引用同一返回对象中已经声明的mention_id。抽取器可以是生成模型、判别模型、规则程序或其组合，必要限定是共享可校验的批次内端点句柄。",
                "不同片段汇总前，对mention_id、relation_candidate_id、claim_id和evidence_id增加segment_id命名空间。证据对象先检查evidence_id、document_id和text；系统形成valid_evidence_ids，再分别检查claim和relation_candidate的evidence_ids是否非空且为其子集。失败关系记录候选标识、缺失字段和无效证据标识。",
                "实体解析器产生mention_id到entity_id的映射，关系物化器不按名称重新检索端点，而是消费该映射。悬空端点和两个端点规范化后坍缩为同一实体分别形成失败原因。至少一条有效联合关系成功物化时，不执行第二次关系模型调用；零条成功时才使用兼容关系回退。",
            ],
        },
        {
            "heading": "实施例6：同类实体合并与限定关系身份",
            "paragraphs": [
                "实体合并提议仅在实体类型相同时生成。一个实施例中，提议阈值为0.65，自动合并阈值为0.90；规范化完全相等得分1.00，词典别名等价得分0.97，缩写等价得分0.92，词元重叠形成较低候选分。自动合并还要求两个实体均具有来源提及。",
                "当合并两个已有簇时，系统检查任意左簇成员与任意右簇成员的类型一致且等价分达到自动阈值。若任一跨簇成员对不满足，提议保持held并记录blocked_by_complete_link_cluster_constraint。该跨簇成员对条件限制链式相似导致的过度合并。",
                "关系规范化先映射谓词别名，对对称谓词按端点标识排序。限定信息按键排序进行规范序列化并计算qualifiers_hash，关系身份键由subject、predicate、object和qualifiers_hash构成。因此同一三元组的valid_year=2025与valid_year=2026保持为不同关系。",
                "聚合后的每条关系保存source_assertions；每个源断言包括源关系标识、源候选标识、原谓词、端点、限定信息及其摘要、证据标识、证据文本、来源片段和源置信度。该具体字段集合使原断言能够重建，而不只保存抽象的可逆布尔标记。公式（1）和（2）仅是可选置信度聚合方式。",
            ],
        },
        {
            "heading": "实施例7：规范图版本贡献与追加式历史补偿",
            "paragraphs": [
                "规范图存储为实体、别名、提及、关系和关系证据记录版本贡献，并为实体和关系记录删除墓碑。删除后重新创建形成新对象生命周期，不把已经移除的旧贡献置信度带入新生命周期。",
                "对指定历史版本的补偿不删除原版本，而是逆序读取其graph_events并生成新的补偿版本。系统移除允许安全移除的目标版本贡献，再根据剩余贡献及时间较后的墓碑重算当前状态；较后删除不会因补偿较早版本而复活，较后重新创建也不会被错误删除。",
                "若移除实体贡献会破坏由较后版本产生且没有替代实体贡献支撑的活动关系，则安全补偿检查跳过该事件并记录skipped_operation_ids。因而本实施例不无条件声称每个历史贡献均可移除，也不声称能够自动拆分任意历史误合并簇。",
            ],
        },
        {
            "heading": "实施例8：系统、Agent调度、schema、可视化、设备及介质",
            "paragraphs": [
                "图2所示系统的模块之间传递具体数据对象：补丁接收模块向影响域模块传递来源锚和端点依赖；影子验证模块向反事实归因模块传递查询标识及操作关联；排除模块向凭证模块传递反事实检查、求解结果和剩余子补丁；存储模块只接收凭证核对后的接受操作。模块可位于同一进程或不同服务，服务拆分不改变数据依赖。",
                "Agent控制器可以调度抽取、合并、影子、凭证和提交工具，并在上游结果修订后使下游缓存结果失效。公式（4）只决定下一个工具动作，不替代图更新结构查询、凭证核对或提交清单检查。Agent不是本发明主权项的必要主体。",
                "运行开始时可以固定活动schema版本，未知类型或谓词形成内容稳定提议，并在事务锁内重读活动schema后晋升。当前运行继续使用启动时固定版本。该schema机制及交互式控制台属于可选治理实施方式，可作为后续分案或软件产品特征，不承担本案核心创造性。",
                "交互式控制台可以分别生成一份当前活动规范图页面和若干逐来源文档页面。逐文档页面以实体提及和关系证据中的document_id选择直接来源对象，仅为所选关系补齐主客端点；同一规范实体由多个文档共享时，不据此加入仅由其他文档支持的关系或证据。同一document_id的多次运行可以聚合图投影和版本历史，治理详情按明确的run_id读取对应候选注册；缺失时标记未绑定而不借文件时间推断关联。",
                "上述每个图页面把图数据、样式和交互脚本嵌入一个HTML文件，可在不部署前端服务和后端服务时离线复核。document_id表示输入内容快照而非权限主体，逐文档投影属于展示层数据最小化，并不构成访问控制、租户隔离、密码学完整性或不可篡改证明。该控制台属于可选治理实施方式和软件产品特征，不承担本案核心创造性；正式多用户部署仍应增加显式run_id、graph_version_id和operation_id关联、身份认证、证据脱敏及日志完整性保护。",
                "电子设备包括处理器、存储器、输入输出接口和通信接口。存储器保存程序、固定schema、候选补丁、影子结果、因果验证凭证和版本元数据；处理器执行程序时完成权利要求所述步骤。计算机可读存储介质保存使处理器实现上述方法的程序指令。",
                "规范图一次版本提交由单一明确事务边界完成。本实施例不声称候选库、schema库、检查点库、运行发布库和规范图存储之间存在跨库分布式原子事务；也不声称当前项目自有回归语料证明开放域SOTA、任意业务语义等价或在线模型权重自学习。",
            ],
        },
    ],
}


ABSTRACT = (
    "本发明公开一种知识图谱候选图补丁的验证和版本提交方法、系统、设备及介质。"
    "获取固定父图版本的基线及携带来源锚和端点依赖的更新操作，由来源锚、声明影响对象和基线邻接派生并冻结原始影响域。"
    "在影子图执行结构查询；对失败查询逐操作实施依赖闭包排除和同基线反事实重放，在冻结影响域下确定待排除更新操作集合并验证剩余子补丁。"
    "将基线、影响域、查询原因、排除与接受操作及重放结果绑定为内容寻址因果验证凭证。"
    "提交判定和执行阶段重算凭证，并以包含接受操作摘要和凭证标识的提交清单校验幂等性；一致时事务写入剩余子补丁及图版本，否则隔离。"
    "本发明能够检测验证—提交错配并在满足图约束时保留未受失败影响的候选知识。"
)


def build_draft() -> dict:
    return {
        "schema_version": "2.0",
        "title": "一种基于来源约束影响域和因果验证凭证的知识图谱候选图补丁验证和版本提交方法、系统、设备及介质",
        "metadata": {
            "source": "EvoLex 0.3.0 source tree, tests, design and evaluation documents",
            "target": "中国发明专利",
            "draft_status": "严格审查修订稿，供发明人及专利代理师复核",
            "prepared_on": "2026-07-31",
            "a1_note": "A1为专利文献种类代码，不是质量等级或授权保证。",
        },
        "source_analysis": {
            "contains_core_formulas": True,
            "formula_count_in_source": 6,
            "contains_methodology_figures": True,
            "source_format": "mixed project",
            "task_mode": "full draft",
            "invention_type": "algorithm/software system",
        },
        "source_map": SOURCE_MAP,
        "terminology_ledger": TERMINOLOGY,
        "formula_inventory": FORMULA_INVENTORY,
        "figure_inventory": FIGURE_INVENTORY,
        "abstract_figure_number": 1,
        "assumptions": [
            "目标法域暂按中国发明专利准备。",
            "自动补丁规划和影子验证的正式方法链限定为来源完整的upsert补丁。",
            "规范图事务仅覆盖单一规范图存储，不覆盖候选库、schema库、检查点库和运行级发布库。",
            "因果验证凭证是内容寻址一致性清单，不是数字签名、身份认证或知识真实性证明。",
            "专利检索结果属于申请前初筛，不构成新颖性、创造性或自由实施意见。",
        ],
        "invention_concept": {
            "technical_problem": "候选图补丁局部排除时验证边界可能漂移，查询—操作原因未经重放验证，且验证结果、接受操作和实际版本事件可能错配。",
            "technical_means": "由来源锚和图依赖派生并冻结影响域，在固定基线上通过依赖闭包排除重放验证反事实原因，求得可行剩余子补丁，再以内容寻址因果验证凭证和提交清单把验证结果绑定到实际接受操作及版本事务。",
            "technical_effect": "在阻止错配或不合格操作写入规范图的同时保留通过约束的剩余候选知识，并使基线、验证边界、原因记录、提交选择和版本事件可确定性重算。",
        },
        "evidence_ledger": EVIDENCE_LEDGER,
        "claims": CLAIMS,
        "claim_feature_map": CLAIM_FEATURE_MAP,
        "figures": FIGURES,
        "specification": SPECIFICATION,
        "abstract": ABSTRACT,
        "audit": {
            "support_findings": [
                "权利要求1的每一实质步骤分别映射到源码、反例测试和说明书位置，而非以一条汇总映射替代。",
                "主独权从外部可获得的候选图补丁开始，联合抽取与规范化下沉从权。",
                "反事实原因、冻结影响域、凭证重算、三方接受操作一致及提交清单均有可执行测试。",
                "自动影子规划限定为来源完整upsert；历史删除和墓碑仅在权利要求12的受限生命周期中主张。",
                "候选数超过十六个时明确标记为固定点单删除局部最小且非全局最小。",
            ],
            "consistency_findings": [
                "权利要求、说明书和六幅附图统一使用原始影响域、反事实原因操作、待排除更新操作集合、剩余子补丁、因果验证凭证和提交清单。",
                "未把A1表述为专利质量、授权或可专利性等级。",
                "未声称凭证是数字签名或真实性证明，也未声称跨存储原子、任意业务语义等价、任意规模全局最优、在线模型学习、任意自动拆分或开放域SOTA。",
            ],
        },
        "quality_assessment": {
            "status": "review-draft",
            "scores": {
                "evidence_support": {
                    "score": 4,
                    "evidence": "主权项六步逐限制映射到实现及攻击性回归测试；仍需发明人确认公开日和公开数据集效果。",
                },
                "claim_architecture": {
                    "score": 4,
                    "evidence": "方法独权形成补丁输入—冻结域—反事实排除—凭证—清单提交闭环，联合抽取和合并作为从属回退层。",
                },
                "terminology_consistency": {
                    "score": 5,
                    "evidence": "术语台账、权利要求、说明书和六幅附图一致区分静态关联、反事实原因、待排除集合、历史补偿和提交清单。",
                },
                "enablement_detail": {
                    "score": 4,
                    "evidence": "八个实施例说明数据字段、反事实伪代码、复杂度、阈值边界、篡改反例、公式、事务及安全边界。",
                },
                "technical_effect_reasoning": {
                    "score": 4,
                    "evidence": "每项主要效果分别关联冻结验证边界、反事实重放、局部保留、凭证重算或清单幂等机制。",
                },
                "formula_coverage": {
                    "score": 5,
                    "evidence": "六个源码公式均收录LaTeX、符号定义和技术作用，并明确Agent调度公式不属于图提交效用。",
                },
                "figure_alignment": {
                    "score": 5,
                    "evidence": "图1逐项覆盖权利要求1的S1至S6，图2至图6分别支撑系统、反事实排除、凭证清单、联合规范化和历史补偿。",
                },
            },
        },
        "inventor_questions": [
            "[TO CONFIRM: 发明人姓名、各发明人的实质贡献及顺序是什么？]",
            "[TO CONFIRM: 申请人名称、权属依据以及是否存在雇佣或合作开发协议？]",
            "[TO CONFIRM: 最早的论文、演示、代码仓库、客户交付或其他公开日期是什么？]",
            "[TO CONFIRM: 是否已经向境外主体披露，是否需要保密审查、优先权或PCT布局？]",
            "[TO CONFIRM: 正式提交前是否取得公开语料上的同模型分步/联合消融结果？]",
            "[TO CONFIRM: 是否补充影响域相对全图验证的读取量/耗时、局部排除相对整补丁拒绝的知识保留率及凭证篡改检出率实验？]",
            "[TO CONFIRM: 是否把版本存储子方案作为分案，或保留在本案从属权利要求？]",
        ],
    }


def main() -> None:
    draft = build_draft()
    intake = {
        "stage": 0,
        "source_files": [
            "src/evolex/",
            "tests/",
            "docs/",
            "benchmarks/patent_joint_kg_corpus.json",
        ],
        "requested_deliverables": [
            "完整可运行项目",
            "联合实体关系抽取",
            "实体和关系合并Agent",
            "知识图谱受控自进化",
            "可视化",
            "中国发明专利审阅草案及配套文档",
        ],
        "target_jurisdiction": "中国",
        "publication_status": "[TO CONFIRM: 项目是否已经公开及最早公开日期]",
        "known_disclosure_dates": [],
        "inventorship": "[TO CONFIRM: 发明人及贡献]",
        "ownership": "[TO CONFIRM: 申请人及权属依据]",
        "risk_flags": [
            "A1是公开文本种类代码，不是质量或授权等级。",
            "最接近专利和family/claim chart仍需代理师正式检索。",
            "项目自有八条回归语料不证明开放域泛化或学术SOTA。",
            "申请前需冻结源码提交并确认全部公开披露。",
        ],
        "gate": {
            "all_inputs_identified": True,
            "unknown_facts_explicit": True,
            "status": "passed-with-inventor-questions",
        },
    }
    source_stage = {
        "stage": 1,
        "source_map": SOURCE_MAP,
        "inspection": {
            "method": "inspected",
            "implementation": "inspected",
            "tests": "inspected",
            "limitations": "inspected",
            "formulas": "inspected",
            "methodology_figures": "redraw required",
            "public_benchmark": "unavailable; project-owned regression corpus only",
        },
        "gate": {"status": "passed"},
    }
    inventory_stage = {
        "stage": 2,
        "terminology_ledger": TERMINOLOGY,
        "input_operation_output_map": [
            {
                "input": "固定父图版本基线和来源绑定候选图补丁",
                "operation": "消费来源锚、声明对象、端点依赖和基线邻接",
                "output": "冻结的原始影响域及摘要",
                "source_ids": ["C007", "C008"],
            },
            {
                "input": "候选图补丁、固定基线及冻结影响域",
                "operation": "影子执行、结构查询和域外投影比较",
                "output": "带操作关联的查询结果和结构摘要",
                "source_ids": ["C009"],
            },
            {
                "input": "失败查询及关联操作",
                "operation": "依赖闭包排除、同基线反事实重放和待排除集合求解",
                "output": "反事实原因记录、待排除集合和经重验剩余子补丁",
                "source_ids": ["C010", "C019"],
            },
            {
                "input": "基线、影响域、原因、排除/接受操作及重放结果",
                "operation": "规范序列化、内容寻址摘要及两阶段重算",
                "output": "因果验证凭证和一致的提交选择",
                "source_ids": ["C011", "C019", "E005"],
            },
            {
                "input": "凭证核对后的接受操作和提交清单",
                "operation": "提交清单幂等核对及规范图单库事务",
                "output": "关联凭证的图版本和图事件，或隔离/拒绝结果",
                "source_ids": ["C012", "E006"],
            },
            {
                "input": "可选技术文档源片段",
                "operation": "联合抽取、证据先行校验及双层规范化",
                "output": "作为候选图补丁来源的规范实体、规范关系及源断言快照",
                "source_ids": ["C001", "C002", "C003", "C004", "C005", "C006"],
            },
        ],
        "formula_inventory": FORMULA_INVENTORY,
        "figure_inventory": FIGURE_INVENTORY,
        "implementation_gaps": [
            "自动planner和影子执行器当前只覆盖证据化upsert，不覆盖任意普通delete补丁。",
            "候选数超过十六个时只保证固定点单删除局部最小，不保证全局或一般集合包含极小。",
            "规范图与运行级发布库之间不存在分布式原子事务。",
            "当前结构投影检查不证明任意业务查询语义等价。",
            "内容寻址凭证不提供带密钥身份认证，能够同时改写内容和摘要的对手需要额外签名或不可变日志。",
            "当前不提供任意历史误合并实体簇的自动拆分。",
            "八条项目自有回归语料需要公开语料和同模型消融补充。",
        ],
        "gate": {"all_core_operations_have_io": True, "all_formulas_disposed": True, "all_figures_disposed": True, "status": "passed"},
    }
    evidence_stage = {
        "stage": 3,
        "evidence_ledger": EVIDENCE_LEDGER,
        "excluded_unsupported_features": [
            "任意delete补丁通过相同自动影子规划",
            "任意规模待排除集合求解全局最小或一般集合包含极小",
            "规范图和运行发布库跨库原子",
            "任意业务查询语义等价",
            "因果验证凭证提供身份认证、对抗性防篡改或知识真实性证明",
            "自动在线更新模型权重",
            "所有误合并对象自动拆分",
        ],
        "inventor_questions": draft["inventor_questions"],
        "gate": {"essential_features_unsupported": 0, "status": "passed"},
    }
    strategy_stage = {
        "stage": 4,
        "one_sentence_concept": (
            "针对候选图补丁验证边界漂移、原因未验证以及验证选择与实际写入错配的问题，"
            "由来源锚和图依赖派生并冻结原始影响域，"
            "在固定基线上通过依赖闭包排除重放验证反事实原因并保留可行剩余子补丁，"
            "再以内容寻址因果验证凭证和提交清单把基线、验证结果、接受操作与图版本事件绑定，"
            "从而阻止错配写入并减少整补丁拒绝造成的有效知识损失。"
        ),
        "principal_protected_object": "来源约束知识图谱候选图补丁的反事实局部排除、凭证绑定和版本提交方法",
        "essential_feature_chain": ["S1", "S2", "S3", "S4", "S5", "S6"],
        "fallback_positions": [
            "按对象类型适配的来源锚及来源完整性门",
            "冻结影响域下的结构重放和域外投影",
            "逐操作依赖闭包反事实原因记录",
            "精确阈值和带性质标记的固定点排除回退",
            "因果验证凭证的具体绑定字段",
            "接受操作和凭证共同参与的提交清单幂等键",
            "同批次提及端点、证据先行校验和零成功关系回退",
            "同类型跨簇成员对实体合并",
            "限定信息关系身份及逐条源断言快照",
            "版本贡献、删除墓碑和安全跳过历史补偿",
        ],
        "claim_categories": ["方法", "系统", "电子设备", "计算机可读存储介质"],
        "gate": {"closed_input_operation_output_chain": True, "all_essential_features_supported": True, "status": "passed"},
    }

    write_json(WORK / "00-intake.json", intake)
    write_json(WORK / "01-source-map.json", source_stage)
    write_json(WORK / "02-technical-inventory.json", inventory_stage)
    write_json(WORK / "03-evidence-ledger.json", evidence_stage)
    write_json(WORK / "04-claim-strategy.json", strategy_stage)
    write_text(
        WORK / "05-claims.txt",
        "\n\n".join(f"{claim['number']}. {claim['text']}" for claim in CLAIMS),
    )
    write_json(
        WORK / "05-claim-map.json",
        {
            "stage": 5,
            "claims": CLAIMS,
            "claim_feature_map": CLAIM_FEATURE_MAP,
            "gate": {
                "formal_claim_placeholders": 0,
                "all_claims_mapped": True,
                "audit_required": True,
            },
        },
    )
    write_json(WORK / "06-draft.json", draft)
    write_json(ROOT / "draft.json", draft)
    print(ROOT / "draft.json")


if __name__ == "__main__":
    main()
