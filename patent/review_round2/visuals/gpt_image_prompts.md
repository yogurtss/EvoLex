# EvoLex GPT Image 辅助视觉记录

> 本目录中的 GPT Image 图仅用于技术交底、路演和商业沟通，不作为正式专利申请附图。正式申请附图由 `patent/render_figures.py` 确定性生成黑白 SVG/PNG。

## 当前交付版本：白底严肃技术图

用户在第二轮视觉复核中明确要求“严肃、不要太过花哨、使用白底”。当前仓库中的两张 PNG 已按该要求覆盖为白底修订版：纯白背景、平面二维、黑灰正文、克制深蓝主路径，仅用红/绿/橙区分失败、通过和回退；不使用深色背景、渐变、霓虹、等距科幻、阴影、人物或机器人。

### 图A当前修订 Prompt

```text
Restyle this existing EvoLex technical comparison infographic into a serious, restrained, white-background engineering diagram suitable for a patent technical disclosure and executive architecture review. Preserve the same core information and left-versus-right comparison, but fully replace the visual language.

Mandatory style: pure white background; flat 2D vector diagram; square or very lightly rounded rectangles; thin dark-gray rules; black/charcoal typography; one muted navy-blue accent for the verified path; muted red used only for failures; muted green used only for passed checks. No dark background, gradients, neon, glow, isometric depth, glass effects, shadows, decorative sci-fi, oversized icons, people, robots, logos, shields, locks, badges, or ornamental illustrations. Generous whitespace, strict grid, consistent line weight, academic/enterprise seriousness.

LEFT column: title “Direct Write”. Show Documents feeding separate Extracted Entities and Extracted Relations, two wrong or dangling endpoints, then an Unchecked Update writing into a corrupted knowledge graph with limited muted-red error propagation. Use simple circles and lines, not pictorial warning art.

RIGHT main area: title “EvoLex Verified Evolution”. Keep six numbered stages in a precise horizontal-to-vertical engineering flow: 1 Candidate Patch, 2 Frozen Scope, 3 Shadow Replay, 4 Counterfactual Replay, 5 Validation Certificate, 6 Commit Manifest. The same dashed navy boundary must visibly reappear in Frozen Scope, Shadow Replay, and Counterfactual Replay. The failed constraint disappears only after a suspect operation is toggled off. The Validation Certificate must visibly bind a baseline hash, frozen-scope hash, excluded operations, and retained-subpatch hash. Mismatch branches to a plain red-outlined “Quarantine” box; match proceeds through Commit Manifest to “Version N+1” and an Audit Trail.

Use only short English labels already present in the source image: “Direct Write”, “Documents”, “Extracted Entities”, “Extracted Relations”, “Unchecked Update”, “Error Propagation”, “EvoLex Verified Evolution”, “Candidate Patch”, “Frozen Scope”, “Shadow Replay”, “Counterfactual Replay”, “Validation Certificate”, “Commit Manifest”, “Quarantine”, “Version N+1”, “Audit Trail”. No explanatory paragraphs, tiny pseudo-code, fake security claims, decorative hashes, seals or signature imagery. 16:9, high resolution, rigorous alignment and readable at document width.
```

### 图B当前修订 Prompt

```text
Restyle this existing EvoLex agent-assisted knowledge-graph mechanism diagram into a serious white-background technical disclosure figure. Preserve all substantive architecture and examples, but remove the presentation-deck/playful visual style.

Mandatory visual system: pure white background; flat 2D engineering schematic; black and dark-gray typography; thin neutral-gray borders and connectors; muted navy-blue for primary data flow; muted green only for valid/pass; muted red only for rejected/mismatch; muted amber only for the zero-success fallback. Use a strict four-column grid, square or minimally rounded boxes, consistent line weights, no gradients, shadows, glossy icons, large colored circles, shields, locks, databases-as-decorations, people, robots, logos, sci-fi motifs, or ornamental illustrations. Keep the composition readable at A4 document width with generous whitespace.

Top orchestration row: represent “Extraction Agent”, “Canonicalization Agent”, “Validation Agent”, and “Commit Agent” as plain labeled rectangular modules connected by a thin arrow, without pictograms.

Column 1 “Joint Extraction”: one Document Segment enters one Single Extraction Batch that contains Entity Mentions M1/M2/M3, Evidence Anchors E1/E2, and Relation Candidates M1→M2 and M2→M3. Show endpoints and evidence references with thin lines. Keep a compact dashed amber “Fallback” box below, labelled to indicate it activates only when zero joint relations survive.

Column 2 “Evidence Gate”: a small formal table checks relation candidates, endpoints and Evidence IDs; one M1→M3 / E9 row is rejected in muted red; surviving relations remain in a green-outlined box.

Column 3 “Canonicalization”: upper “Entity Merge” panel compares same-type Cluster A and Cluster B and shows that every cross-cluster pair passes before merge, preserving source assertions. Lower “Relation Merge” panel shows normalized predicate/endpoints and qualifier fingerprints (2020|NY, 2021|NY, 2020|SF), keeping same triples with different qualifiers separate and preserving per-source assertions. Use tables and simple lines, not illustrative icons.

Column 4 “Verified Evolution”: Candidate Patch → Frozen Scope → Counterfactual Replay → Validation Certificate. A plain branch labelled Match proceeds to Commit Manifest and Version N+1; Mismatch goes to a simple red-outlined Quarantine box. A thin Audit Feedback line returns to the orchestration row, but do not imply online model retraining.

Retain short English labels and example IDs from the source. Do not add paragraphs, promotional slogans, fake hashes, security claims, badges, seals, or decorative symbols. 16:9, high resolution, rigorous and restrained.
```

### 当前版本人工检查

- 两图均为白底；主色收敛为黑灰和深蓝，红/绿/橙只表达状态语义。
- 图A保留传统错误扩散与六阶段验证提交闭环；图B保留联合抽取、证据先行、双层规范化和验证式演进。
- 两图无人物、机器人、霓虹、渐变或等距科幻装饰，适合技术交底及正式汇报。
- 图中示例对象、关系和哈希仅为说明，不作为运行证据；正式申请仍以确定性黑白附图为准。

## 生成历史：图A首次版本（已被白底修订替代）

- 文件：`EvoLex-innovation-graphical-abstract.png`
- 比例：16:9
- 生成日期：2026-07-31
- 生成工具：OpenAI GPT Image
- 设计目的：把核心技术效果可视化为“错误扩散”与“冻结影响域—影子重放—反事实归因—因果验证凭证—提交清单”两条路径的对照。

### Prompt

```text
Create a premium 16:9 landscape technical innovation infographic for an enterprise AI knowledge-graph system named EvoLex. This is a supplementary graphical abstract, NOT a formal patent drawing. Use a clean dark navy background with cyan/teal data paths and restrained amber/red risk accents, crisp vector-like isometric elements, high legibility, no logos, no people, no decorative clutter.

Composition: a clear left-versus-right comparison separated by a subtle vertical divider.
LEFT, titled only with the short English label “Direct Write”: document fragments flow into separately extracted entity nodes and relation edges; several relation endpoints become dangling or wrong; an unchecked update enters a knowledge graph and creates visible red error propagation across multiple nodes. Include a small broken-link icon and a red warning triangle.
RIGHT, titled “EvoLex Verified Evolution”: show one coherent pipeline with six numbered visual stages arranged left-to-right and then into a versioned graph: 1 Candidate Patch (entity + relation extracted together with evidence anchors), 2 Frozen Scope (a bounded graph subregion inside a cyan boundary), 3 Shadow Replay (a translucent duplicate graph), 4 Counterfactual Replay (toggle one suspect operation off and show the failed constraint disappearing), 5 Validation Certificate (a content-addressed certificate card binding hashes, excluded operations and retained operations), 6 Commit Manifest (a manifest gate writing only retained operations into Version N+1). Place a small quarantine branch below the certificate gate for mismatch. Finish with a clean versioned knowledge graph and an audit trail.

Emphasize the core novelty visually: the SAME frozen boundary is reused for every replay; the certificate is linked to the exact retained subpatch and commit manifest. Use only these short English labels, spell them exactly: “Direct Write”, “Candidate Patch”, “Frozen Scope”, “Shadow Replay”, “Counterfactual Replay”, “Validation Certificate”, “Commit Manifest”, “Quarantine”, “Version N+1”. Avoid paragraphs, tiny text, pseudo-code, formulas, legal badges, seals, locks, signatures, blockchain imagery, or claims of security. Accurate data engineering schematic, patent-tech commercialization aesthetic, publication-quality, balanced whitespace, 2560×1440.
```

### 人工检查

- 左右对照和六阶段闭环清楚；冻结边界复用、隔离分支以及只提交保留操作均已体现。
- 图中哈希值为示意，不作为真实运行证据。
- 图中存在少量解释性英文，正式中文交底以图注为准；正式申请附图不使用本图。

## 生成历史：图B首次版本（已被白底修订替代）

- 文件：`EvoLex-agent-joint-extraction-and-evolution.png`
- 比例：16:9
- 生成日期：2026-07-31
- 生成工具：OpenAI GPT Image
- 设计目的：解释实体与关系同批次抽取如何解决端点丢失，并把证据过滤、同类实体合并、限定信息感知的关系合并接入验证式演进闭环。

### Prompt

```text
Create a second premium 16:9 technical mechanism infographic for EvoLex, focused on agent-assisted knowledge graph construction and self-evolution. This is a supplementary commercialization/technical-disclosure visual, NOT a formal patent drawing. Clean light background with white cards, charcoal text, cyan/indigo system paths, green verified states, and restrained amber exceptions. Crisp vector-style architecture, no people, no robots, no logos, no decorative sci-fi, no paragraphs.

Show a left-to-right closed-loop architecture with four clearly separated zones.
ZONE 1 — “Joint Extraction”: one document segment enters a single extraction batch. Inside the batch show entity mentions M1, M2, M3, evidence anchors E1, E2, and relation candidates whose endpoints reference the local handles M1→M2 and M2→M3. Make it visually obvious that entities and relations are produced together, not by disconnected pipelines. Include a small fallback branch labelled “Fallback” that activates only when zero joint relations survive.
ZONE 2 — “Evidence Gate”: evidence IDs are checked first; one relation with a dangling evidence reference is removed; valid relations keep their endpoint handles. Use a compact green check/red reject visual.
ZONE 3 — two parallel canonicalization lanes. Upper lane titled “Entity Merge”: same-type source mentions are compared across clusters; all cross-cluster pairs must pass before clusters merge; preserve source assertions. Lower lane titled “Relation Merge”: normalize predicate and endpoints, include a qualifier fingerprint such as time/location, keep same triples with different qualifiers separate, preserve per-source assertions. Do not use the words complete-linkage or SHA unless necessary.
ZONE 4 — “Verified Evolution”: canonical candidates become an evidence-bound Candidate Patch, pass through Frozen Scope, Counterfactual Replay, Validation Certificate, Commit Manifest, then update “Version N+1”. A mismatch branches to “Quarantine”. A curved audit-feedback arrow returns from Version N+1 to the agent orchestration layer at the top, signalling controlled self-evolution without suggesting online model retraining.

At the top, use a slim orchestration ribbon with four short labels: “Extraction Agent”, “Canonicalization Agent”, “Validation Agent”, “Commit Agent”. The agents coordinate through explicit artifacts, not free-form chat. Use only the exact short labels named in this prompt plus “M1”, “M2”, “M3”, “E1”, “E2”. No tiny explanatory prose, pseudo-code, formulas, security seals, blockchain imagery, signatures, or legal claims. Publication-quality enterprise data-engineering schematic, balanced whitespace, accurate arrows, 2560×1440.
```

### 人工检查

- 联合提取批次、局部端点句柄、零关系成功时回退均被明确表现。
- 无效证据引用先被删除，实体与关系的两条规范化通路相互独立但共享来源断言。
- 限定信息不同的同三元组被保留为不同关系身份；验证失败进入隔离，成功才形成下一版本。
- 锁形小图标仅是“门控/隔离”的视觉隐喻，不表示数字签名、密码学认证或安全保证；正式申请附图不采用该图标。
