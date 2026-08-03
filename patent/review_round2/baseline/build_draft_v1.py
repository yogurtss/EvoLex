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
        "summary": "先过滤证据对象，再使用过滤后的证据标识校验主张和关系候选，避免无效证据继续传播。",
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
        "summary": "规范谓词、排序对称关系端点、聚合同一规范关系的证据，并保留可逆关系身份假设。",
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
        "summary": "从操作声明域、证据契约、关系端点和基线一跳依赖派生影响域，并生成与操作标识关联的结构查询。",
        "confidence": "high",
    },
    {
        "id": "C009",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_apply_shadow、_unaffected_projection",
        "summary": "在内存影子图中应用补丁，执行端点完整性、规范关系唯一性、确定性重放和域外投影一致性检查。",
        "confidence": "high",
    },
    {
        "id": "C010",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，_minimum_cost_compensation、_dependency_closed_exclusions",
        "summary": "把失败查询归因到补丁操作，对因果候选做依赖闭包；候选不超过十六个时精确枚举，超过时使用明确标记的包含极小回退。",
        "confidence": "high",
    },
    {
        "id": "C011",
        "type": "code",
        "locator": "src/evolex/nodes/evolution.py，evolution_consensus_node；src/evolex/agentic/metrics.py，publish_gate",
        "summary": "证据契约、确定性重放、非干扰、不变量、非负效用和发布置信度形成提交硬门。",
        "confidence": "high",
    },
    {
        "id": "C012",
        "type": "code",
        "locator": "src/evolex/repositories/canonical.py，commit_patch",
        "summary": "在 canonical 单库事务中进行补丁幂等检查、父版本校验、图对象写入、版本事件记录和活动版本切换。",
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
        "locator": "src/evolex/visualization/dashboard.py，build_dashboard",
        "summary": "生成自包含交互式控制台，关联展示图对象、证据、版本、Agent 轨迹、影子查询、补偿、合并和 schema 信息。",
        "confidence": "high",
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
        "id": "F001",
        "type": "source-figure",
        "locator": "docs/patent_strategy.md，第4节核心保护链",
        "summary": "S1至S8受控自进化方法链。",
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
        "concept": "causal operation",
        "canonical_zh": "因果操作",
        "source_terms": ["caused_by_operation_ids", "causal operation"],
        "forbidden_aliases": [],
    },
    {
        "concept": "compensation subset",
        "canonical_zh": "补偿操作子集",
        "source_terms": ["compensation", "excluded operations"],
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
        "technical_role": "度量补偿操作子集的编辑数、影响半径和证据损失。",
        "disposition": "specification-equation-3",
    },
    {
        "source_id": "E004",
        "source_number": "源码公式D",
        "technical_role": "在 Agent 动作选择中平衡信息增益、执行成本和风险。",
        "disposition": "specification-equation-4",
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
        "disposition": "redraw-as-figure-4",
    },
]


EVIDENCE_LEDGER = [
    {
        "id": "L001",
        "feature": "同一源片段的一次抽取结果同时包含实体提及、引用该提及标识的关系候选和证据片段",
        "source_ids": ["C001", "C002"],
        "source_location": "联合抽取接口和片段命名空间函数",
        "technical_role": "保持关系端点与提及身份位于同一上下文和可校验标识空间",
        "effect": "减少分步关系抽取中端点身份丢失并使端点失败可定位",
        "support_status": "explicit",
    },
    {
        "id": "L002",
        "feature": "先验证证据对象，再用有效证据标识验证主张和关系",
        "source_ids": ["C003"],
        "source_location": "validate_node",
        "technical_role": "阻止悬空或越界证据引用传播到后续图操作",
        "effect": "提高证据链结构完整性",
        "support_status": "explicit",
    },
    {
        "id": "L003",
        "feature": "在类型、来源完整性和 complete-link 条件下合并同类实体",
        "source_ids": ["C004"],
        "source_location": "entity_resolve_node、entity_merge_node",
        "technical_role": "形成可追溯的规范实体身份假设",
        "effect": "压缩别名重复并限制传递性过度合并",
        "support_status": "explicit",
    },
    {
        "id": "L004",
        "feature": "对谓词和关系端点进行规范化并聚合关系证据",
        "source_ids": ["C005", "C006", "E001", "E002"],
        "source_location": "relation_extract、relation_merge",
        "technical_role": "在实体身份稳定后建立规范关系身份",
        "effect": "减少同义谓词和重复断言，同时保留来源证据",
        "support_status": "explicit",
    },
    {
        "id": "L005",
        "feature": "将候选图对象转换为携带证据契约、端点依赖和声明影响域的操作级 upsert 补丁",
        "source_ids": ["C007"],
        "source_location": "_build_patch",
        "technical_role": "把抽取对象转换为可验证、可归因和可补偿的变更单元",
        "effect": "为提交前治理提供机器可执行输入",
        "support_status": "explicit",
    },
    {
        "id": "L006",
        "feature": "由证据契约、端点及基线一跳依赖派生影响域",
        "source_ids": ["C008"],
        "source_location": "_derive_impact_domain",
        "technical_role": "确定补丁验证和域外一致性检查的边界",
        "effect": "把影响分析绑定到具体来源和图依赖",
        "support_status": "explicit",
    },
    {
        "id": "L007",
        "feature": "在影子图中执行补丁并输出可归因查询、确定性重放和域外投影检查结果",
        "source_ids": ["C008", "C009"],
        "source_location": "_evaluate_patch、_apply_shadow",
        "technical_role": "在规范图提交前检测结构破坏并定位失败操作",
        "effect": "降低不合格补丁直接污染规范图的风险",
        "support_status": "explicit",
    },
    {
        "id": "L008",
        "feature": "在依赖闭合约束下按编辑数、影响半径和证据损失选择补偿操作子集",
        "source_ids": ["C010", "E003"],
        "source_location": "_minimum_cost_compensation",
        "technical_role": "针对失败查询排除因果相关操作并重新验证剩余补丁",
        "effect": "在满足约束时尽量保留未受影响的候选知识",
        "support_status": "explicit",
    },
    {
        "id": "L009",
        "feature": "候选操作不超过十六个时进行精确枚举，超过时标记包含极小回退",
        "source_ids": ["C010"],
        "source_location": "_minimum_cost_compensation",
        "technical_role": "给出与候选规模相匹配且可审计的求解声明",
        "effect": "避免把大空间启发式结果错误标记为全局解",
        "support_status": "explicit",
    },
    {
        "id": "L010",
        "feature": "证据、重放、非干扰、不变量、非负效用和发布置信度形成提交门控",
        "source_ids": ["C011", "E004"],
        "source_location": "evolution_consensus_node、publish_gate",
        "technical_role": "把多个技术检查结果合成为可执行提交判定",
        "effect": "阻止任一硬条件失败的补丁进入规范图",
        "support_status": "explicit",
    },
    {
        "id": "L011",
        "feature": "规范图存储在单一事务中校验补丁与父版本并写入对象、事件和活动版本",
        "source_ids": ["C012"],
        "source_location": "CanonicalGraphStore.commit_patch",
        "technical_role": "建立具有并发拒绝和幂等语义的规范提交边界",
        "effect": "避免陈旧补丁静默覆盖并保持版本事件一致",
        "support_status": "explicit",
    },
    {
        "id": "L012",
        "feature": "通过版本贡献和删除墓碑生成追加式选择性补偿版本",
        "source_ids": ["C013"],
        "source_location": "CanonicalGraphStore.rollback_version",
        "technical_role": "只移除目标版本可归因贡献并重算当前对象状态",
        "effect": "保留后续贡献和后续删除，避免整图快照覆盖",
        "support_status": "explicit",
    },
    {
        "id": "L013",
        "feature": "运行开始时固定 schema 版本并在事务锁内累积和晋升 schema 提议",
        "source_ids": ["C014"],
        "source_location": "SchemaStore.put_proposal、promote_proposal",
        "technical_role": "分离观察与正式结构变更并避免并发丢更新",
        "effect": "提高同一运行的 schema 可复现性",
        "support_status": "explicit",
    },
    {
        "id": "L014",
        "feature": "技术判定模块按依赖图执行且上游修订使下游结果失效",
        "source_ids": ["C015"],
        "source_location": "AgenticKGRunner、工具依赖表",
        "technical_role": "防止陈旧下游判定被用于提交",
        "effect": "保持 Agent 控制链的阶段一致性",
        "support_status": "explicit",
    },
    {
        "id": "L015",
        "feature": "将图、证据、版本、Agent、影子、补偿、合并和 schema 记录关联可视化",
        "source_ids": ["C016"],
        "source_location": "build_dashboard",
        "technical_role": "提供同一变更链的审计和人工复核界面",
        "effect": "缩短变更定位和复核路径",
        "support_status": "explicit",
    },
    {
        "id": "L016",
        "feature": "由处理器执行存储在存储器中的程序以实现受控自进化方法",
        "source_ids": ["C001", "C007", "C010", "C012", "C015", "C017"],
        "source_location": "可执行 Python 源码、命令行入口和自动化测试",
        "technical_role": "支持系统、电子设备和存储介质类别",
        "effect": "使所述方法能够在通用计算设备上执行",
        "support_status": "inherent",
    },
]


CLAIMS = [
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


CLAIM_FEATURE_MAP = [
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


FIGURES = [
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


SPECIFICATION = {
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
                "可视化模块读取规范图存储、候选注册、schema存储和运行状态的只读快照，生成自包含HTML。页面使用运行标识和图版本标识关联规范实体、关系、证据、版本、补丁、补偿、技术判定轨迹、合并决定和schema记录。",
                "可视化页面用于审计和人工复核，不替代提交硬门。若部署到多用户生产环境，应增加身份认证、访问控制、敏感证据脱敏、日志完整性保护和外部图存储连接器。",
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


ABSTRACT = (
    "本发明公开一种知识图谱受控自进化方法、系统、设备及介质。"
    "对技术文档片段一次联合生成实体提及、引用提及标识的关系候选及证据；"
    "经证据先行校验和实体、关系双层规范化后，形成携带证据契约、端点依赖和声明影响域的更新补丁。"
    "系统由证据契约及图依赖派生影响域，在影子图执行结构不变量、确定性重放和域外投影检查，"
    "把失败查询归因到具体操作并在依赖闭合约束下选择补偿子集。"
    "仅当证据、重放、非干扰、不变量、效用及策略门通过时，才在规范图事务中提交剩余操作并记录图版本；否则隔离。"
    "本发明能够降低关系端点失配，使知识更新具有可追溯、提交前验证和选择性补偿能力。"
)


def build_draft() -> dict:
    return {
        "schema_version": "2.0",
        "title": "一种基于证据契约、影响域验证及补偿求解的多技术判定模块知识图谱受控自进化方法、系统、设备及介质",
        "metadata": {
            "source": "EvoLex 0.3.0 source tree, tests, design and evaluation documents",
            "target": "中国发明专利",
            "draft_status": "供发明人及专利代理师复核",
            "prepared_on": "2026-07-31",
            "a1_note": "A1为专利文献种类代码，不是质量等级或授权保证。",
        },
        "source_analysis": {
            "contains_core_formulas": True,
            "formula_count_in_source": 4,
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
            "自动演化规划和影子验证的正式方法链限定为证据化upsert补丁。",
            "规范图事务仅覆盖单一规范图存储，不覆盖候选库、schema库、检查点库和运行级发布库。",
            "专利检索结果属于申请前初筛，不构成新颖性、创造性或自由实施意见。",
        ],
        "invention_concept": {
            "technical_problem": "分步实体—关系抽取造成端点身份丢失，规范化后证据断裂，且自动写图缺少可归因、可补偿的提交前验证。",
            "technical_means": "把同响应提及端点与证据连续转换为双层规范对象和操作级证据契约，由契约派生影响域和可归因影子查询，并在依赖闭合约束下选择补偿子集，经技术硬门后进行规范版本事务。",
            "technical_effect": "降低关系端点失配和重复身份传播，使候选图更新在提交前能够定位结构失败、保留未受影响操作并形成可审计的规范图版本。",
        },
        "evidence_ledger": EVIDENCE_LEDGER,
        "claims": CLAIMS,
        "claim_feature_map": CLAIM_FEATURE_MAP,
        "figures": FIGURES,
        "specification": SPECIFICATION,
        "abstract": ABSTRACT,
        "audit": {
            "support_findings": [
                "全部正式权利要求至少映射到一个源码或测试证据条目。",
                "独立方法权利要求的S1至S8形成输入、处理、门控和版本化输出闭环。",
                "自动影子规划限定为证据化upsert；delete/tombstone仅在版本生命周期从属特征中主张。",
                "候选数超过十六个时明确限定为非全局的包含极小回退。",
            ],
            "consistency_findings": [
                "权利要求、说明书和附图统一使用实体提及、关系候选、证据契约、影响域、影子图、补偿操作子集和规范图存储。",
                "未把A1表述为专利质量、授权或可专利性等级。",
                "未声称跨存储原子、任意业务语义等价、在线模型学习、任意自动拆分或开放域SOTA。",
            ],
        },
        "quality_assessment": {
            "status": "review-draft",
            "scores": {
                "evidence_support": {
                    "score": 5,
                    "evidence": "每项权利要求均映射到稳定源码、测试或文档证据ID，且主权项完整链有逐步支持。",
                },
                "claim_architecture": {
                    "score": 4,
                    "evidence": "方法独立权利要求形成S1至S8闭环，设置联合抽取、规范化、影响域、补偿、版本和系统类别回退层。",
                },
                "terminology_consistency": {
                    "score": 5,
                    "evidence": "术语台账、权利要求、说明书和四幅附图使用一致的规范中文术语。",
                },
                "enablement_detail": {
                    "score": 4,
                    "evidence": "七个实施例说明数据字段、阈值边界、公式、失败路径、事务和部署替代方式。",
                },
                "technical_effect_reasoning": {
                    "score": 4,
                    "evidence": "每个主要技术效果均关联到提及端点、证据契约、影子查询、补偿或版本贡献机制。",
                },
                "formula_coverage": {
                    "score": 5,
                    "evidence": "四个源码核心公式均收录LaTeX、符号定义、实施参数和技术作用。",
                },
                "figure_alignment": {
                    "score": 5,
                    "evidence": "图1逐项覆盖权利要求1的S1至S8，图2至图4分别支撑系统、补偿和版本机制。",
                },
            },
        },
        "inventor_questions": [
            "[TO CONFIRM: 发明人姓名、各发明人的实质贡献及顺序是什么？]",
            "[TO CONFIRM: 申请人名称、权属依据以及是否存在雇佣或合作开发协议？]",
            "[TO CONFIRM: 最早的论文、演示、代码仓库、客户交付或其他公开日期是什么？]",
            "[TO CONFIRM: 是否已经向境外主体披露，是否需要保密审查、优先权或PCT布局？]",
            "[TO CONFIRM: 正式提交前是否取得公开语料上的同模型分步/联合消融结果？]",
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
                "input": "技术文档源片段",
                "operation": "同结果联合抽取并添加片段命名空间",
                "output": "实体提及、关系候选和证据片段",
                "source_ids": ["C001", "C002"],
            },
            {
                "input": "带来源的提及、关系候选和证据",
                "operation": "证据先行校验和双层规范化",
                "output": "规范实体、规范关系及身份谱系",
                "source_ids": ["C003", "C004", "C005", "C006"],
            },
            {
                "input": "规范实体和规范关系",
                "operation": "证据契约化补丁和影响域派生",
                "output": "更新操作、影响域和结构不变量",
                "source_ids": ["C007", "C008"],
            },
            {
                "input": "候选补丁、影响域和规范图基线",
                "operation": "影子回放、失败归因和依赖闭合补偿",
                "output": "通过约束的剩余补丁或隔离决定",
                "source_ids": ["C009", "C010", "C011"],
            },
            {
                "input": "门控允许的剩余补丁",
                "operation": "规范图单库版本事务",
                "output": "具有版本标识的受控知识图谱更新结果",
                "source_ids": ["C012", "C013"],
            },
        ],
        "formula_inventory": FORMULA_INVENTORY,
        "figure_inventory": FIGURE_INVENTORY,
        "implementation_gaps": [
            "自动planner和影子执行器当前只覆盖证据化upsert，不覆盖任意普通delete补丁。",
            "候选数超过十六个时只保证包含极小回退，不保证全局代价最小。",
            "规范图与运行级发布库之间不存在分布式原子事务。",
            "当前结构投影检查不证明任意业务查询语义等价。",
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
            "任意规模补偿求解全局最小",
            "规范图和运行发布库跨库原子",
            "任意业务查询语义等价",
            "自动在线更新模型权重",
            "所有误合并对象自动拆分",
        ],
        "inventor_questions": draft["inventor_questions"],
        "gate": {"essential_features_unsupported": 0, "status": "passed"},
    }
    strategy_stage = {
        "stage": 4,
        "one_sentence_concept": (
            "针对分步抽取导致端点身份丢失和自动写图缺少可归因补偿的问题，"
            "把同响应提及端点与证据连续转换为操作级证据契约，"
            "由该契约派生影响域和带因果操作标识的影子查询，"
            "在依赖闭合约束下选择补偿子集并仅事务提交通过硬门的剩余补丁，"
            "从而形成版本化、可追溯且可选择性恢复的规范知识图谱更新结果。"
        ),
        "principal_protected_object": "证据化upsert知识图谱补丁的受控自进化方法",
        "essential_feature_chain": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
        "fallback_positions": [
            "同响应提及端点和有条件关系回退",
            "同类型complete-link实体合并",
            "关系身份与有界证据置信度",
            "证据契约及一跳影响域",
            "精确阈值和标记回退的补偿求解",
            "版本贡献与删除墓碑",
            "运行固定schema和治理可视化",
        ],
        "claim_categories": ["方法", "系统", "电子设备", "非暂态计算机可读存储介质"],
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
