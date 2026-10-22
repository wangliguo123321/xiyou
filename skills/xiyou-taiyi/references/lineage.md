# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [skill-creator](skill-creator.md) | [anthropics/skills / skills/skill-creator/SKILL.md](https://github.com/anthropics/skills/blob/34040c9c568585f6929bedeaad110ad08f079624/skills/skill-creator/SKILL.md) | [Apache-2.0](../licenses/skill-creator.txt) |
| [stocktake](stocktake.md) | [affaan-m/everything-claude-code / skills/skill-stocktake/SKILL.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/skills/skill-stocktake/SKILL.md) | [MIT](../licenses/stocktake.txt) |
| [find-skills](find-skills.md) | [vercel-labs/skills / skills/find-skills/SKILL.md](https://github.com/vercel-labs/skills/blob/d6b37f62ae23c3825b0ed16c73e123eee0a41fdc/skills/find-skills/SKILL.md) | [MIT](../licenses/find-skills.txt) |
| [创建与评测中的有界优化](skill-creator.md) | [alchaincyf/darwin-skill / SKILL.md](https://github.com/alchaincyf/darwin-skill/blob/8a8b66258e3c45d6ae4aea39719468c6428fcb0a/SKILL.md) | [MIT](../licenses/darwin.txt) |
| [评测结果契约与汇总](evaluation-results.md) | [anthropics/skills / references/schemas.md](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/references/schemas.md)、[scripts/aggregate_benchmark.py](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator/scripts/aggregate_benchmark.py) | [Apache-2.0](../licenses/skill-creator.txt) |

## 评测结果适配取舍

- 2026-10-22 独立编写 `scripts/summarize_evaluation.py`，吸收固定上游的断言证据、运行身份、timing 与多次统计思想；采用 xiyou 显式双版本配对输入，非原 viewer 兼容实现。
- 明确拒绝缺对、重复身份、断言不一致及非法指标；未知保留 `null`，成本差仅计算两侧已知的配对，所有差值固定 candidate 减 baseline，不继承缺值补零、字符数充当 tokens、缺 grading 跳过及顺序决定差值方向。
- 不执行上游脚本，不采用 Claude 执行器或自动触发优化。只核数据结构和统计，不能证明证据真实、源内容不同、技能一般效果或自动采用资格；独立匿名成对裁决不变。

## 达尔文适配取舍

- 吸收独立成对比较、真实任务验证、仅保留有证据收益和有界优化；将匿名成果比较并入已有创建与评测法器。
- 不吸收固定评分权重、逐轮强制确认、自动全量扫描、第三方脚本或自动更新。沿用用户原授权，平票与未知不采用，每目标默认最多两轮。
- 原文对论文、评测准确率及收益的描述未经本项目独立核验，不作为已确认事实或本技能效果依据；来源固定仅证明材料可追溯。
