# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [retrieval](retrieval.md) | [affaan-m/everything-claude-code / skills/iterative-retrieval/SKILL.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/skills/iterative-retrieval/SKILL.md) | [MIT](../licenses/retrieval.txt) |
| [explorer](explorer.md) | [affaan-m/everything-claude-code / agents/code-explorer.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/agents/code-explorer.md) | [MIT](../licenses/explorer.txt) |
| [action-first](action-first.md) | [ayghri/i-have-adhd / skills/i-have-adhd/SKILL.md](https://github.com/ayghri/i-have-adhd/blob/b15d0be58f55b33972ba3e39709e0e5208ef30cb/skills/i-have-adhd/SKILL.md) | [MIT](../licenses/action-first.txt) |
| [project-entry](project-entry.md) | [github/awesome-copilot / skills/acquire-codebase-knowledge/scripts/scan.py](https://github.com/github/awesome-copilot/blob/7629185ca7644389b37b16aad9e592c277533200/skills/acquire-codebase-knowledge/scripts/scan.py)，所属 [Skill](https://github.com/github/awesome-copilot/blob/7629185ca7644389b37b16aad9e592c277533200/skills/acquire-codebase-knowledge/SKILL.md) | [MIT](../licenses/project-entry.txt) |

`project-entry` 保留“清单优先，再查声明入口”的方法，增加根 `package.json` 与 `pyproject.toml` 的标准库结构化提取和有界只读接口。上游是清单预览/入口候选扫描，不声称其已有本实现的字段提取器；不复制全树、TODO、Git 热点或强制七篇仓内文档流程。

## 本轮取舍

`i-have-adhd` 与哪吒共同强调快速抵达重点，因此将结论/动作前置、步骤化、任务状态外显、支线收束和不丢项的展示规则炼成“混天绫”。不采用跨会话持续模式、宿主 Hook、固定耗时估算或医学解释，也不创建新人物。

上游公开评测的主要收益集中在多步进度与失败报告，但其首轮 release gate 仍失败；`partial-success` 场景出现无证据断言根因的回退。哪吒适配明确要求原因按证据分级，并保留现有渐进检索和最小缺口规则。结构、安装与作者评测均不能单独证明适配版有效，仍需使用同题隔离任务比较。
