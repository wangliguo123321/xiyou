# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [simplifier](simplifier.md) | [anthropics/claude-plugins-official / plugins/code-simplifier/agents/code-simplifier.md](https://github.com/anthropics/claude-plugins-official/blob/da823e86c8feef13b73b6712af11eadd38c992f6/plugins/code-simplifier/agents/code-simplifier.md) | [Apache-2.0](../licenses/simplifier.txt) |
| [search-first](search-first.md) | [affaan-m/everything-claude-code / skills/search-first/SKILL.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/skills/search-first/SKILL.md) | [MIT](../licenses/search-first.txt) |
| [需求与规范两轴](scope-review.md) | [mattpocock/skills / skills/engineering/code-review/SKILL.md](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/engineering/code-review/SKILL.md) | [MIT](../licenses/code-review.txt) |
| [范围保持与缩减](scope-review.md#范围保持与缩减) | [garrytan/gstack / plan-ceo-review/SKILL.md.tmpl](https://github.com/garrytan/gstack/blob/a6b3a57512ca6d5c6aa5b68f74f736195021f96e/plan-ceo-review/SKILL.md.tmpl) | [MIT](../licenses/scope-review.txt) |
| [核验评审建议](receiving-review.md) | [obra/superpowers / skills/receiving-code-review/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/receiving-code-review/SKILL.md) | [MIT](../licenses/receiving-review.txt) |

## 本轮取舍

`code-review` 的双轴进入主干，按需展开范围审查；`receiving-code-review` 成为独立法器。gstack 仅提取保持、缩减范围的部分。ECC 简化器与现有官方简化器重合，不新增第二件简化法器；架构改善任务继续独立处理。

社区 [karpathy-guidelines](https://github.com/multica-ai/andrej-karpathy-skills/blob/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines/SKILL.md) 用于原则对照，并非 Karpathy 官方发布。其简单优先、精准改动等原则已由既有八戒覆盖，本轮不复制该技能或新增法器。该版本 README 标注 MIT，仓库未提供独立许可证文件。
