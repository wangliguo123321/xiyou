# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [brainstorming](brainstorming.md) | [obra/superpowers / skills/brainstorming/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/brainstorming/SKILL.md) | [MIT](../licenses/brainstorming.txt) |
| [debugging](debugging.md) | [obra/superpowers / skills/systematic-debugging/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/systematic-debugging/SKILL.md) | [MIT](../licenses/debugging.txt) |
| [GitHub CI 上下文](github-ci.md) | [openai/skills / skills/.curated/gh-fix-ci/SKILL.md](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci/SKILL.md)（retired-source） | [Apache-2.0](../licenses/gh-fix-ci.txt) |
| [已有规范图](spec-graph.md) | [JetBrains/thinkrail / packages/spec-graph/skills/spec-graph/SKILL.md](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/skills/spec-graph/SKILL.md) | [Apache-2.0](../licenses/thinkrail-spec-graph.txt) |

CI 适配另参考同提交的 [inspect_pr_checks.py](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci/scripts/inspect_pr_checks.py)，脚本 blob `06cd03c5fc61c784d082e1c25a533c94e0912b3f`；完整许可 blob `13e25df86ce06eb6488e6a6bc5c5847f5dedc352`。修改说明见 [NOTICE](../NOTICE.txt)。旧库已退休，指向的新插件未核验到同名脚本；本地适配不是当前上游迁移版本，来源资格不等于效果验证。

规范图适配另参考同提交 `packages/spec-graph/core/` 的 [parse.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/parse.ts)、[graph.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/graph.ts)、[query.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/query.ts) 和 [validate.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/validate.ts)。上游 Skill 无独立版本号；固定提交而不采用其 private package 的 `0.0.0` 作为技能版本。完整根许可 blob `9a239244ba179fe6ae7bb21c07d5df894ee6f5b5`，保留 Copyright 2026 JetBrains s.r.o.；独立只读 Ruby 实现的改动与安全边界见规范图引用及 NOTICE。
