# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [handoff](handoff.md) | [mattpocock/skills / skills/productivity/handoff/SKILL.md](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/handoff/SKILL.md) | [MIT](../licenses/handoff.txt) |
| [update-docs](update-docs.md) | [affaan-m/everything-claude-code / commands/update-docs.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/commands/update-docs.md) | [MIT](../licenses/update-docs.txt) |
| [verification](verification.md) | [obra/superpowers / skills/verification-before-completion/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/verification-before-completion/SKILL.md) | [MIT](../licenses/verification.txt) |
| [记录的完成条件、资料入口与单一事实来源](update-docs.md) | [mattpocock/skills / skills/productivity/writing-for-agents/SKILL.md](https://github.com/mattpocock/skills/blob/959a8e9f1edc3adbe2f7e3054bb6fbefa6696260/skills/productivity/writing-for-agents/SKILL.md) | [MIT](../licenses/handoff.txt) |
| [分层验证报告](verification.md) | [affaan-m/everything-claude-code / skills/verification-loop/SKILL.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/skills/verification-loop/SKILL.md) | [MIT](../licenses/update-docs.txt) |
| [清理分类与动态引用核验](cleanup.md) | [affaan-m/everything-claude-code / commands/refactor-clean.md](https://github.com/affaan-m/everything-claude-code/blob/8321021c54d670126ce3b2969d5deb880b4b0c2a/commands/refactor-clean.md) | [MIT](../licenses/update-docs.txt) |
| [分支交付检查](branch-handoff.md) | [obra/superpowers / skills/finishing-a-development-branch/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/finishing-a-development-branch/SKILL.md) | [MIT](../licenses/verification.txt) |
| [PR 审查输入采集](github-review-comments.md) | [openai/skills / skills/.curated/gh-address-comments/SKILL.md](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-address-comments/SKILL.md) 及同目录 [scripts/fetch_comments.py](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-address-comments/scripts/fetch_comments.py) | [Apache-2.0](../licenses/gh-address-comments.txt) |

同一上游相同许可证共用一份全文。保留原有交接主干；记录方法与分层验证合入对应法器。清理仅取分级和引用核验；分支法器仅在交付分支、PR 或工作树任务中加载。各文件的“西游适配”说明未继承的流程。

PR 采集以沙僧的输入整理及交接职责承接。2026-10-24 依据固定退休官方源改写，保留三类输入及原字段；新增显式 base 仓库、独立分页、身份核对和有限采集。不继承认证提权或评论处理授权，不称当前官方维护版；来源资格不代替本地适配的独立验收。
