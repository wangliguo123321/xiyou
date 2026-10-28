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

## 离线 Terraform 状态库存

- 2026-10-28 基于 HashiCorp [refactor-module](https://github.com/hashicorp/agent-skills/blob/f706481af9b8fedb66de909f6243ad29601afa0c/plugins/terraform/skills/refactor-module/SKILL.md) 的 State Migration / Inspecting Current State 方法适配；固定完整提交 `f706481af9b8fedb66de909f6243ad29601afa0c`、正文 blob `d6339a30f9be58d58d4d4a1a98d6ef29e0e01753`。Copyright IBM Corp. 2026，发布者 HashiCorp；[完整 MPL-2.0](../licenses/terraform-refactor.txt)随附。
- 原维护 [PR #90 对应提交](https://github.com/hashicorp/agent-skills/commit/4451ceca5456e79cc776efee96a744f7ac96e5bf)新增稳定 state list / show-json 优先与明文敏感值提醒，维护署名见 NOTICE。保留地址盘点及属性值排除，不继承整个模块重构、HCL 范例、state mv 或 provider/云执行。
- [使用引用](terraform-state-inventory.md)与独立 `scripts/inspect_terraform_state.py` 按 MPL-2.0 分发，默认 Apache 声明不覆盖这两文件，其余独立组件许可保持。原 Skill 没有 helper；文件输入/身份、完整递归、对象分类、未知/限额和 JSON 协议为本地新写，不称上游程序移植或一般模型收益。
- 格式依据 [官方 JSON 输出](https://developer.hashicorp.com/terraform/internals/json-format)及 [show 命令](https://developer.hashicorp.com/terraform/cli/commands/show)；另只读核固定 `hashicorp/terraform@ae75cbe434a7dbcca310b11f6b5d9bc5dfdb3380` 的 `internal/command/jsonstate/state.go`：合法最小输出与 Current/Deposed 逐项列举，处理网站 current-only 说法的演进差异。该 BUSL 实现及官方测试 JSON 仅临时验证/事实参考，未写入产品或复制实现。
- 只观察已导出文档声明，地址不按点拆/去重，保留对象分类但不输出属性或 deposed_key。完整解析不证明云端真实性/迁移安全；许可与方法资格不替代本地实际验收。

## 离线工作流 uses 引用观察

- 2026-10-28 参考 [github/awesome-copilot / github-actions-hardening](https://github.com/github/awesome-copilot/blob/98b45a78d3ed316e78f005b60594d5c4a50588e3/skills/github-actions-hardening/SKILL.md) Step 5 与同版 [supply-chain.md](https://github.com/github/awesome-copilot/blob/98b45a78d3ed316e78f005b60594d5c4a50588e3/skills/github-actions-hardening/references/supply-chain.md)；固定提交 `98b45a78d3ed316e78f005b60594d5c4a50588e3`，正文 blob `61fa956e0ca6a0958ff6713b7b94ed22ecdc2e7e`，供给链引用 blob `6cb05474467ab11925d31a4d1ba9e74297ca1596`。Copyright GitHub, Inc.，原[完整 MIT](../licenses/github-actions-hardening.txt)字节保留，不编版权年份。
- 社区贡献者 Amir / AmirhosseinHonardoust 的已合并 [PR #2002](https://github.com/github/awesome-copilot/pull/2002)引入 Skill 与方法示例，原仓结构检查不当成本 helper 的行为或安全收益测试。该目录没有原 helper/专用行为测试。
- 原生 AST 的显式文件输入、job/steps 声明位置与字面分类、相关别名/merge 未知、限额与结构化结果均为本地新写，[使用引用](workflow-refs.md)及脚本按系列默认 Apache-2.0 保留原 MIT 通知；其它独立 MPL2/CC 等材料许可不变。
- 只观察已声明 uses，不在 run/env/with 里做正则全文找词，不执行/改写/联网解 pin。40hex/digest 不证明存在、来源可信或安全；动态/新语法/相关结构无法解释时保未知，不套原源严重等级，不冒全量安全审查或 CI 放行。后续判断依实际权限、来源和执行上下文另审。

## 离线 Playwright 网络记录观察

- 固定源 [microsoft/playwright-cli / playwright-cli](https://github.com/microsoft/playwright-cli/blob/b1a5903c5b633b8c9f843ad7b629c2a78437040c/skills/playwright-cli/SKILL.md)，完整提交 `b1a5903c5b633b8c9f843ad7b629c2a78437040c`，必要 [tracing.md](https://github.com/microsoft/playwright-cli/blob/b1a5903c5b633b8c9f843ad7b629c2a78437040c/skills/playwright-cli/references/tracing.md)。Copyright (c) Microsoft Corporation.，完整原 [Apache-2.0](../licenses/playwright-cli.txt)保字节与通知，不补年份或唯一作者。
- CLI0.1.22声明 exact core1.64.0-alpha-1790635538000，registry gitHead关联 `microsoft/playwright@e8149b8257d32dcf8f72573ecc43e72439da7080`；只读必要 `packages/playwright-core/src/server/trace/recorder/tracing.ts` 与 `server/har/harTracer.ts` 行为，确认资源快照JSONL、pending flush和status初始-1。版本关联不是运行或供应链证明，context version10不当单文件版本头。
- 2026-10-28 新写 [使用引用](playwright-network.md)与 Python 标准库 helper，沿原Apache2保归属，取离线声明调查而非原捕获链；原源没有此分析脚本。输入身份、逐行投影、URL有限显示、未知/硬界与结构化输出为本地适配。
- 未复制core实现/原测试/资源、不引Node或浏览器；不采用时间/性能、回放、profile、旧trace删除、安装或上传。真实fixture未取得，实际适配试验仅受控原义数据；不能冒真实录制、上游测试或完整网络/根因/安全保证。其它独立MPL2等单元不变。
