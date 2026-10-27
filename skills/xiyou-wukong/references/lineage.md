# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [brainstorming](brainstorming.md) | [obra/superpowers / skills/brainstorming/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/brainstorming/SKILL.md) | [MIT](../licenses/brainstorming.txt) |
| [debugging](debugging.md) | [obra/superpowers / skills/systematic-debugging/SKILL.md](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/systematic-debugging/SKILL.md) | [MIT](../licenses/debugging.txt) |
| [GitHub CI 上下文](github-ci.md) | [openai/skills / skills/.curated/gh-fix-ci/SKILL.md](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci/SKILL.md)（retired-source） | [Apache-2.0](../licenses/gh-fix-ci.txt) |
| [CI 解码错误隔离](github-ci.md) | [wshobson/agents / python-error-handling](https://github.com/wshobson/agents/blob/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-error-handling/SKILL.md) | [MIT](../licenses/python-error-handling.txt) |
| [已有规范图](spec-graph.md) | [JetBrains/thinkrail / packages/spec-graph/skills/spec-graph/SKILL.md](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/skills/spec-graph/SKILL.md) | [Apache-2.0](../licenses/thinkrail-spec-graph.txt) |

CI 适配另参考同提交的 [inspect_pr_checks.py](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci/scripts/inspect_pr_checks.py)，脚本 blob `06cd03c5fc61c784d082e1c25a533c94e0912b3f`；完整许可 blob `13e25df86ce06eb6488e6a6bc5c5847f5dedc352`。修改说明见 [NOTICE](../NOTICE.txt)。旧库已退休，指向的新插件未核验到同名脚本；本地适配不是当前上游迁移版本，来源资格不等于效果验证。

CI 解码错误隔离采用上述 `python-error-handling` 的边界验证、具体异常、部分失败方法，另读同提交 [references/details.md](https://github.com/wshobson/agents/blob/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-error-handling/references/details.md) 的操作边界与部分成功示例。原插件作者 Seth Hobson，技能最初贡献者 M. A.（mohammadaffaneh）；保留 Copyright (c) 2024 Seth Hobson 及原 MIT 全文。本地只在已有 JSON 解码边界处理 `RecursionError` 和无法表示为有限浮点数的数值，不移植其宽泛捕获或新框架，也不宣称原源已实现或验证这些补丁。

规范图适配另参考同提交 `packages/spec-graph/core/` 的 [parse.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/parse.ts)、[graph.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/graph.ts)、[query.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/query.ts) 和 [validate.ts](https://github.com/JetBrains/thinkrail/blob/4dba28897785039a73b70e278e3f632cfe17b1f9/packages/spec-graph/core/validate.ts)。上游 Skill 无独立版本号；固定提交而不采用其 private package 的 `0.0.0` 作为技能版本。完整根许可 blob `9a239244ba179fe6ae7bb21c07d5df894ee6f5b5`，保留 Copyright 2026 JetBrains s.r.o.；独立只读 Ruby 实现的改动与安全边界见规范图引用及 NOTICE。

## 离线 SQLite 取证

- 2026-10-28 采用 [ofershap/mcp-server-sqlite 的 sqlite-query](https://github.com/ofershap/mcp-server-sqlite/blob/a3b0323ce23521190572460dff944722b0036b3c/skills/sqlite-query/SKILL.md) 及同版 [src/sqlite.ts](https://github.com/ofershap/mcp-server-sqlite/blob/a3b0323ce23521190572460dff944722b0036b3c/src/sqlite.ts) 的显式单库、引擎只读、结构/EQP 和确保关闭方法。固定完整提交 `a3b0323ce23521190572460dff944722b0036b3c`；作者 Ofer Shapira，保留 Copyright (c) 2026 Ofer Shapira 及完整 [MIT](../licenses/sqlite-query.txt) 原字节。实现 blob `c833a29bdb804965f4439f1d8736b2f7fe5e3b0b`，SHA256 `8ae332531e08ecab720bb262eeabf078dfcf539af24d300d7713e9910bb30384`。
- 本地 `scripts/inspect_sqlite.py` 用 Python 3.9+ 标准库及 SQLite 3.37+；只观察稳定离线文件的 schema 与原生查询计划，不执行原用户 SQL。原生 SQLite 负责解析，不自写 SQL 解析器，也不承诺优化建议或计划优劣评分。
- 原接口没有实际参数绑定/资源预算/截断保证，且暴露写模式；本地绑定、不可变只读连接、文件及旁路核验、引擎授权、行/行 payload 预算、JSON 与 partial 协议均为宿主新增，不冒称原源自带或已测试。原源 CI/测试只支持方法资格，不替代本地验证；不运行上游程序，不引入 Node 原生模块或配置 MCP。
- 不继承默认表 COUNT、文本表格输出、SQL 前缀正则或可写分支。计划只支持合同内普通 main 表/视图的 SELECT/CTE，所有函数、虚拟/影子/未知对象、写入与其它副作用均拒绝；需要这些能力时保留未知或说明工具不适用，不削弱保护继续执行。
