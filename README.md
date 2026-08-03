# EvoLex 0.3

EvoLex 是一个面向技术文档的、证据治理型多 Agent 知识图谱系统。当前默认路径不再把实体与关系拆成两次彼此独立的模型抽取，而是在同一片段、同一次联合响应中输出实体提及、关系端点和证据；随后由 Agent 完成实体与关系的双层规范化，并在影子图中验证补丁后才允许知识图谱自进化。

项目的产品定位是 **Knowledge Graph Change Control Plane（知识图谱变更控制面）**：它不仅回答“抽出了什么”，还记录“为什么能合并、原始验证边界是什么、哪个失败经反事实重放归因到哪个操作、哪些操作被排除、凭证绑定了哪个实际提交版本”。

> 当前仓库是可运行的工程与中国发明专利申请前技术底稿，不是已授权专利，也不构成法律意见或自由实施（FTO）结论。“A1”通常是专利申请公开文本的种类代码，并非专利质量等级。

## 核心改进

### 1. 实体与关系联合抽取

每个源片段的主要抽取路径一次返回：

- `mentions`：带片段内提及标识、类型和证据的实体提及；
- `relations`：主语端、宾语端直接引用同一响应中的提及标识；
- `evidence`、`measurements`、`conditions` 和 `claims`。

片段汇总时，本地标识会被加上片段命名空间。关系物化直接消费 `mention_id -> entity_id` 映射，因此避免了“先抽实体、后让第二个模型凭文本重新寻找端点”造成的端点缺失和错配。只有没有任何可成功物化的有效联合关系时，才启用兼容性关系回退路径；失败候选仍会留在审计记录中。

### 2. Agent 驱动的同类实体与关系合并

- 实体只在类型一致、来源可追溯且匹配阈值满足时自动合并；
- 采用 complete-link 簇约束，避免 A≈B、B≈C 导致 A 与 C 被传递性误合并；
- 保留别名、源实体、源提及、片段和合并决策，可审计而非静默覆盖；
- 关系先规范化谓词和对称端点，再以规范化主语、谓词、宾语和限定信息摘要形成关系身份键；
- 聚合关系证据、片段和置信度，并保存逐条源断言快照，使不同时间/条件事实不会被误合并。

### 3. 受控知识图谱自进化

默认 `agent` 管线把候选图转换为具有证据契约、操作依赖和受影响域的图补丁：

```text
联合抽取
  → 实体解析与同类实体规范化
  → 关系物化与同类关系规范化
  → 证据契约化图补丁
  → 从来源锚、端点和基线邻接推导并冻结原始影响域
  → 自动生成不变量
  → 固定基线影子重放、确定性与冻结域外投影验证
  → 逐关联操作依赖闭包排除及同基线反事实原因验证
  → 待排除集合求解并重验剩余子补丁
  → 内容寻址因果验证凭证及提交判定重算
  → Evidence/replay/non-interference/invariant/utility/certificate 六项 AND 硬门
  → decision/evaluation/certificate 接受操作三方一致
  → commit 再次重算凭证并核对提交清单
  → canonical 版本事务提交实际接受操作
  → 本地发布视图或候选/隔离存储
```

当反事实原因候选操作不超过16个时，求解器在已验证原因及其依赖闭包所定义的搜索空间内执行精确枚举；更大空间使用明确标记为`single_deletion_local_minimum_not_global`的固定点回退，只保证单删除局部最小，不宣称全局最优或一般集合包含极小。共识记录中的`required_quorum=5`仅是审计统计，六项硬条件必须全部为真。canonical图在一个SQLite事务中提交实际接受操作、事件、版本、凭证ID和提交清单摘要；相同patch但不同接受集合或凭证的重试被拒绝。运行级本地KG是派生发布视图，不宣称两个存储跨库原子。

## 快速开始

要求 Python 3.11+。

```bash
conda env create -f environment.yml
conda activate evolex
```

或者：

```bash
python -m pip install -e ".[dev,rich]"
```

离线演示不需要 API：

```bash
export EVOLEX_OFFLINE=1
evolex chat --pipeline agent --output-dir data/demo
```

在交互界面中粘贴技术文本，或输入本地文件：

```text
API Gateway retries HTTP 503 responses before failing over.
examples/technical_note.txt
entities
relations
policy
audit
```

使用 OpenAI-compatible 服务时：

```bash
export DEEPSEEK_API_KEY="your-api-key"
evolex chat \
  --pipeline agent \
  --llm-base-url https://api.deepseek.com \
  --llm-model deepseek-v4-flash \
  --llm-concurrency 4
```

密钥只应通过环境变量或会话配置传入，不要提交到仓库。

## 运行模式

| 模式 | 用途 |
|---|---|
| `agent`（默认） | 联合抽取、双层规范化、证据补丁、影子验证、共识、canonical 提交和治理记录 |
| `system` / `full` / `phase3` | 固定顺序的确定性基线，用于对照和兼容性测试 |
| `phase2`、`phase1` | 早期阶段兼容入口，仅建议调试使用 |

重新执行上游工具时，Agent 控制器会依据依赖图使下游产物失效，避免“新抽取结果配旧关系或旧补丁”的状态污染。Agent 的工具提议不是授权本身：控制器和发布节点分别执行代码级依赖检查，`policy.action=publish` 只表示允许继续，运行状态仍保持 `candidate`；只有演化补丁已被接受、canonical 提交成功、发布置信度达标且运行级发布事务完成后，状态才变为 `published`。

## 评测与可视化

运行仓库自带的 8 文档、无网络工程回归：

```bash
evolex eval patent --output-dir outputs/demo/benchmark
```

该命令对比：

- `legacy_separate`：历史分离式启发抽取 + 固定系统管线；
- `joint_agent`：联合提及/关系候选 + Agent 规范化与演化治理。

报告包含实体/关系 P-R-F1、关系端点对准确率、端点标识有效率、证据契约覆盖率、联合物化率、别名归并及影子/回滚探针。它是项目自有小型回归集，不是公开学术 SOTA 基准，也不能单独证明专利新颖性。

保留原有 `visualize` 命令，用于从一次或多次 Agent 运行的存储生成一个跨文档交互式控制台：

```bash
evolex visualize \
  --canonical-dir data/demo/canonical \
  --registry-dir data/demo/registry \
  --schema-dir data/demo/schema_candidates \
  --output data/demo/evolex_dashboard.html
```

控制台同时展示 canonical 图、关系证据、图版本、Agent 决策轨迹、影子不变量、待排除集合与剩余子补丁、因果验证凭证、提交清单、合并与 schema 审计；registry和canonical history来源保持独立，不额外推断缺少关联证据的`run_id–version_id`关系。

需要同时交付总知识图和逐文档知识图时，使用新增的 `visualize-bundle`：

```bash
evolex visualize-bundle \
  --canonical-dir data/demo/canonical \
  --registry-dir data/demo/registry \
  --schema-dir data/demo/schema_candidates \
  --output-dir data/demo/evolex-visualization
```

输出目录固定包含：

```text
data/demo/evolex-visualization/
├── index.html
├── evolex-global-kg.html
└── documents/
    └── evolex-doc-*.html
```

`index.html`是静态入口，`evolex-global-kg.html`展示全部活动 canonical 对象，`documents/evolex-doc-*.html`分别展示单个来源文档的投影。每个图页面都把数据、样式和交互脚本内嵌在自身 HTML 中，不需要前端工程、后端服务、CDN 或网络连接；视觉采用白底、克制配色的严肃审计风格。

单文档投影以`entity_mentions.document_id`和`relation_evidence.document_id`作为直接来源边界，只补入已选关系的端点实体。共享 canonical 实体可以在多个文档页出现，但不会把仅由其他文档支持的关系或证据扩张到当前页面。这里的`document_id`是由文档内容确定的内容快照标识，不等同于原始文件名、业务标题或权限主体。所有 HTML 都可能内嵌原文证据和治理记录，应按敏感导出物管理。

本轮离线验收已生成[基准报告](outputs/final/benchmark/patent_benchmark_report.md)、[静态可视化索引](outputs/final/kg_visualizations/index.html)、[跨文档总图](outputs/final/kg_visualizations/evolex-global-kg.html)和8个单文档图；旧版[单页控制台](outputs/final/evolex_dashboard.html)继续保留用于兼容验收。

## 治理命令

```bash
# 检查、提升或切换行为生效的 schema
evolex schema candidates
evolex schema promote-ready
evolex schema promote --proposal-id scp-...
evolex schema current
evolex schema activate --version-id evolex-base-0.1.0
evolex schema promotions

# 查看 canonical 版本或追加选择性补偿版本
evolex evolve history
evolex evolve rollback --version-id gv-... --reason "confirmed regression"

# 回放或恢复
evolex run replay --run-id RUN-...
evolex run resume --thread-id document:DOC-...:agent
```

运行开始时固定活动 schema 版本；并发提升在写锁事务内重新读取活动版本，避免并行 proposal 形成丢更新分支。

## 主要输出

在自定义 `--output-dir` 下：

| 目录/文件 | 内容 |
|---|---|
| `canonical/canonical_registry.sqlite` | 跨运行 canonical 实体、别名、关系、证据、版本与事件 |
| `registry/*_registry.sqlite` | 候选对象、合并决策、Agent trace、补丁、影子结果、共识和隔离记录 |
| `kg/*.sqlite` | canonical 提交成功后、在单库事务内替换的运行级发布视图 |
| `schema_candidates/schema_candidates.db` | schema proposal、版本、活动指针和提升账本 |
| `checkpoints/checkpoints.db` | 节点/工具状态快照，用于回放和恢复 |
| `*.jsonl` | 兼容性的候选对象流 |

失败、拒绝、负效用或提交异常不会提升 canonical 活动版本；对应证据、补丁和失败原因仍进入候选/隔离记录。

运行级发布若在关系外键等任一步骤失败，会回滚该 SQLite 事务，不留下半份运行快照；同一状态的 `run_id` 重试采用替换语义，避免重复追加。当前没有 revision CAS，针对同一 `run_id` 的不同新旧载荷仍应由调用方串行化。该保证仍不扩展为 canonical 与运行级发布库之间的跨库原子性。

## 文档

- [技术架构](docs/technical_design.md)
- [评测方法与结果](docs/evaluation.md)
- [论文与专利现有技术对比](docs/literature_and_prior_art.md)
- [创新点与商业价值](docs/innovation_and_business_value.md)
- [专利保护策略](docs/patent_strategy.md)
- [安全与治理边界](docs/security_and_governance.md)
- [后续路线](docs/next_steps.md)
- [专利交付目录](patent/README.md)

## 测试

```bash
pytest -q
```

真实模型端到端测试需要显式提供 API key；默认测试和专利工程回归不访问网络。

## 明确能力边界

当前版本没有宣称或实现：

- 跨文档版本永久稳定的 mention ID；
- 对证据来源“相互独立”的事实认定；
- 任意业务查询的语义等价证明；
- 物理写时复制图数据库或跨两个 SQLite 文件的分布式原子事务；
- 每个 Agent 都是独立 LLM、在线训练或无人监督修改模型权重；
- 已合并对象的自动拆分；
- 超过精确求解阈值的待排除集合具备全局最优或一般集合包含极小保证；
- 内容寻址因果验证凭证提供数字签名、身份认证或知识真实性证明。

这些边界同时写入专利和产品文档，以确保工程证据、权利要求和商业承诺一致。
