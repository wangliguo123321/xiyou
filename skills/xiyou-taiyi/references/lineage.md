# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [skill-creator](skill-creator.md) | [anthropics/skills / skills/skill-creator/SKILL.md](https://github.com/anthropics/skills/blob/34040c9c568585f6929bedeaad110ad08f079624/skills/skill-creator/SKILL.md) | [Apache-2.0](../licenses/skill-creator.txt) |
| [stocktake](stocktake.md) | [affaan-m/everything-claude-code / skills/skill-stocktake/SKILL.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/skills/skill-stocktake/SKILL.md) | [MIT](../licenses/stocktake.txt) |
| [find-skills](find-skills.md) | [vercel-labs/skills / skills/find-skills/SKILL.md](https://github.com/vercel-labs/skills/blob/d6b37f62ae23c3825b0ed16c73e123eee0a41fdc/skills/find-skills/SKILL.md) | [MIT](../licenses/find-skills.txt) |
| [创建与评测中的有界优化](skill-creator.md) | [alchaincyf/darwin-skill / SKILL.md](https://github.com/alchaincyf/darwin-skill/blob/8a8b66258e3c45d6ae4aea39719468c6428fcb0a/SKILL.md) | [MIT](../licenses/darwin.txt) |

## 达尔文适配取舍

- 吸收独立成对比较、真实任务验证、仅保留有证据收益和有界优化；将匿名成果比较并入已有创建与评测法器。
- 不吸收固定评分权重、逐轮强制确认、自动全量扫描、第三方脚本或自动更新。沿用用户原授权，平票与未知不采用，每目标默认最多两轮。
- 原文对论文、评测准确率及收益的描述未经本项目独立核验，不作为已确认事实或本技能效果依据；来源固定仅证明材料可追溯。
