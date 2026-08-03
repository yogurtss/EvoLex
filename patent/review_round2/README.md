# EvoLex 专利第二轮严格审查交付索引

审查日期：2026-07-31

本目录保存第一轮基线、第二轮攻击性审查和辅助创新视觉。正式权利要求、说明书、摘要及黑白附图由项目根目录下的专利构建脚本生成到 `patent/outputs/`。

## 1. 基线冻结

`baseline/` 保存进入严格审查前的第一轮文本和生成器副本：

- `draft_v1.json`
- `EvoLex-完整审阅稿-v1.docx`
- `EvoLex-权利要求书-v1.txt`
- `prior_art_matrix_v1.md`
- `build_draft_v1.py`

这些文件只用于前后对照，不应作为当前申请文本。

## 2. 严格审查

- `reports/strict_reviewer_report.md`：逐项旧权利要求判决、现有技术组合攻击、创新分级、第二轮重构和剩余风险。
- `reports/final_validation_report.md`：专利结构、DOCX、Office Math、附图、源码测试、离线基准和HTML控制台的最终验证记录。
- `../prior_art_matrix.md`：当前主权项逐限制现有技术对照。
- `../source_claim_evidence_matrix.md`：当前权项—源码—测试—说明书证据矩阵。

## 3. 当前正式草稿输出

运行：

```bash
python patent/build_package.py
```

主要交付：

- `../outputs/EvoLex-完整审阅稿.docx`
- `../outputs/EvoLex-权利要求书.docx`
- `../outputs/EvoLex-说明书.docx`
- `../outputs/EvoLex-说明书摘要.docx`
- `../outputs/EvoLex-摘要附图.docx`
- `../outputs/EvoLex-结构化草稿.json`
- `../outputs/EvoLex-权利要求检查.txt`
- `../outputs/EvoLex-草稿验证报告.txt`
- `../outputs/EvoLex-figures/figure-1.svg` 至 `figure-6.svg`

## 4. 辅助创新视觉

- `visuals/EvoLex-innovation-graphical-abstract.png`：传统直接写图与 EvoLex 验证式演进对照，白底严肃技术风格。
- `visuals/EvoLex-agent-joint-extraction-and-evolution.png`：联合抽取、证据过滤、实体/关系双层规范化与 Agent 验证闭环，白底严肃技术风格。
- `visuals/gpt_image_prompts.md`：完整生成提示词、用途和人工检查边界。

辅助视觉不作为正式申请附图，不替代黑白确定性附图；示例哈希、实体和图标不是真实运行证据。

## 5. 当前发明中心

```text
来源绑定候选图补丁
  → 冻结原始影响域
  → 同基线反事实原因验证
  → 依赖闭合局部排除
  → 内容寻址因果验证凭证
  → 提交清单绑定的剩余子补丁版本提交
```

实体与关系联合抽取、证据先行引用校验、同类实体跨簇全成员对合并、限定信息感知的关系身份及逐条源断言被保留为重要从属保护层。

## 6. 使用边界

本交付属于技术交底与申请前草稿，不是法律意见、正式检索报告、可专利性保证或自由实施意见。A1是专利文献种类代码，不是质量等级。提交前仍需发明人和代理师确认发明人/申请人、首次公开日期、权属、正式检索、单一性、保密审查及海外布局。
