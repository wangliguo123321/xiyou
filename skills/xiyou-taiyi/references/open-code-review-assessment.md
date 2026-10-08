# OpenCodeReview 融入 xiyou Skills 的可行性评估

> 调研日期：2026-10-08
>
> 上游快照：[`alibaba/open-code-review@fabbdb2`](https://github.com/alibaba/open-code-review/tree/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4)
>
> 当日最新发布版：[`v1.12.13`](https://github.com/alibaba/open-code-review/releases/tag/v1.12.13)
>
> 资料范围：仅使用上游仓库的 README、Skill、源码、路线图、清单和发布记录；上游自报的规模与基准结果均按“项目方声称”处理，未做独立复现。

## 结论

**后续决策：新增独立法器 `zhaoyingjing`（照影镜·代码巡检），以 `/zhaoyingjing` 一个入口承接 OpenCodeReview 的完整能力；不把整套 OCR 流程直接塞进八戒，也暂不新增人物。**

理由如下：

1. OpenCodeReview 最值得吸收的不是又一份审查提示词，而是“确定性工程负责范围与规则，Agent 负责语义判断”的混合架构。上游把精确选文件、文件分组、按文件匹配规则、评论重定位与复核留给工程流程，把动态检索和语义审查交给 Agent；这正好补上纯 Skill 容易漏文件、定位漂移、结果随提示词波动的问题。[README：核心设计](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#core-design-deterministic-engineering--agent-hybrid)
2. 上游已经提供适合宿主 Agent 的 delegation mode：`ocr delegate preview` 负责选出待审文件并说明排除原因，`ocr delegate rule` 负责为文件解析规则，OCR 本身不调用 LLM，实际审查仍由当前 Agent 完成。因此它可以作为 xiyou 法器增强审查，而不必再配置第二套模型端点。[delegation Skill](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md)
3. 八戒当前的稳定职责是“需求/规范双轴 + 最小正确改动”，它能判断改动是否越界，却不等同于覆盖整个变更集的缺陷、安全、性能和测试审查。直接把 OCR 的安装、选文件、规则、并发、会话和输出协议全塞进八戒，会让人物职责变深变杂；独立法器更符合 xiyou 已有“人物负责稳定职责、法器负责具体工作方法”的组织约定（见本仓库 `README.md` 与 `skills/xiyou-taiyi/SKILL.md`）。
4. 这项能力有明确且长期存在的输入、输出和验收方式，但本质仍是“借助专用 CLI 做代码审查”的方法，不需要为了工具名再造一个人物。只有后续证实代码审查本身需要独立的长期编排、教学和治理职责，才值得考虑人物化。

## 上游能力与架构

### 1. 两种执行方式

- **OCR 管理审查**：`ocr review` 读取工作区、提交或分支范围的 Git diff，由 OCR 调用已配置的 LLM，输出带文件、行号、严重度、类别和修复建议的结构化评论；支持文本、JSON、SARIF、结果文件、预算、并发和恢复会话。[主 Skill 的工作流与输出协议](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md)
- **宿主 Agent 委托审查**：`ocr delegate preview` 只计算审查范围，`ocr delegate rule` 只解析规则；宿主 Agent 再读取 diff、逐文件审查并统计覆盖率。该模式在 OCR 侧不需要 LLM 端点。[delegation Skill 的七步流程](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md#workflow)

对 xiyou 而言，委托模式应是默认路线：它保留当前宿主的模型、权限和工具链，只让 OCR 承担最适合确定性实现的选文件与规则解析。OCR 管理模式可作为用户明确配置模型、希望独立复核或需要 SARIF/CI 输出时的可选后端。

### 2. 确定性范围与覆盖

预览代码复用真实运行的 diff 选择逻辑，逐项返回文件状态、增删行、是否审查和排除原因，并区分用户规则、扩展名、默认目录、秘密文件、供应商目录、删除、二进制和超大文件等排除类别。[`internal/agent/preview.go`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/agent/preview.go)

上游 delegation Skill 进一步要求：为每个预览到的文件建立清单；每项必须标成 `reviewed` 或带具体原因的 `skipped`；结束前报告 `total_files`、`reviewed_files`、`skipped_files` 和 `coverage_rate`，不能发现第一个高危问题后就提前结束。[delegation Skill：逐文件审查与覆盖](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md#step-4-review-each-file)

这套“范围先冻结、每项有终态、跳过必须解释”的约束，适合直接成为 `zhaoyingjing` 的核心验收标准。

### 3. 按文件解析规则

OCR 的规则解析器支持项目、全局、命令行自定义和系统规则；路径模式按声明顺序匹配，首个命中项生效，未命中时回退默认规则。项目规则可为某类文件替换系统规则，也可通过 `merge_system_rule` 合并。[`internal/config/rules/system_rules.go`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/config/rules/system_rules.go)

委托模式会按“规则来源 + 命中模式 + 规则正文”分组文件；即使规则文字相同但来源不同，也不会错误合并，便于审计每组规则的来由。[`internal/delegate/rulegroup.go`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/delegate/rulegroup.go)

适合 xiyou 吸收的不是整份内置规则文本，而是三个原则：规则按文件适用、规则来源可追溯、同规则文件成组审查。若未来真正引入上游规则正文，应固定版本并按 Apache-2.0 要求补齐 NOTICE 与许可证，而不是把远端 `main` 当作动态提示词源。[上游许可证](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/LICENSE)

### 4. 审查专用 Agent 流程

主审查提示明确要求逐个覆盖 `<review_files>`，只评论变更中的代码，需要时再读全文件或检索相关代码，且不能把实现文件已审视当成头文件、接口或配置文件也已审视。[主审查系统提示](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/config/template/prompts/main_task_system.md)

默认任务模板还把规划、主审查、记忆压缩、评论事实过滤、评论重定位和文件分组拆成独立阶段，并设置规划阈值、分组阈值、轮数及 token 上限。[`task_template.json`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/config/template/task_template.json)

其中两个设计尤其值得借鉴：

- 评论过滤器只删除“当前 diff 足以证明为错误”的评论；证据不足时保留，避免过滤器无声吞掉真实问题。[事实过滤提示](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/config/template/prompts/review_filter_task_system.md)
- 评论无法用文本匹配定位时，独立重定位阶段根据 diff 和评论生成精确代码片段，再次解析行号；失败时恢复原评论而不是伪造位置。[`internal/diff/relocation.go`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/diff/relocation.go)

`zhaoyingjing` 可在不复制整套实现的前提下采用相同输出纪律：发现必须落在实际变更行或明确标注“无法精确定位”；报告前对高严重度发现做一次事实复核；复核只能在证据证明其错误时删除。

### 5. 会话、失败与恢复

OCR 的运行清单把每个文件归入完成、失败或豁免集合，并用固定枚举区分 provider、timeout、cancelled、configuration、input、budget、panic 等失败；最终状态由覆盖集合计算为 complete、partial、failed 或 skipped，而不是由“有没有评论”推断。[`internal/session/manifest.go`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/internal/session/manifest.go)

范围/提交审查支持通过 session id 恢复；上游 Skill 同时明确 workspace 模式不能恢复。[主 Skill：恢复与限制](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md#gotchas)

这适合与沙僧的收尾记录对接；照影镜先把覆盖状态、失败分类和恢复命令作为标准输出，不必把 OCR 的实现复制进沙僧本体。

## 建议的 Skills 设计

### P0：新增 `zhaoyingjing`

**定位**：法器·照影镜——以一个入口调用 OCR 的差异审查、全量扫描、委托模式、自管模型、规则、会话、结构化输出和集成能力。

**触发场景**：

- 审查当前改动、某个提交、某个分支相对基线的变化；
- 审查 PR 对应的本地差异；
- 用户要求查找 bug、安全、性能、错误处理、测试或维护性问题；
- 用户明确要求“审查并修复”时，在完成审查后处理已确认问题。

**不负责**：需求值不值得做、设计路线比较、业务原理教学、提交/发布、CI 平台配置。范围收敛继续由八戒承担；疑难根因与方案比较继续由悟空承担；交付记录继续由沙僧承担。

**默认工作流**：

1. 明确审查目标和基线；从需求、PR 描述或提交信息提取简短业务背景。
2. 运行 `ocr delegate preview --format json`，在调用 LLM 或产生模型费用前冻结审查清单和排除原因；命令不存在时停止并给出可选安装方式，不静默安装全局软件。[架构文档：预览不消耗 token](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/architecture.md#the-five-gate-file-filter)
3. 运行 `ocr delegate rule --format json <paths...>`，记录每组规则的来源与匹配模式。
4. 按规则组与 diff 大小分批；每个 `(path, status)` 都必须 `reviewed` 或带理由 `skipped`。工作区里同一路径可能因“暂存删除后又未跟踪重建”出现两项，上游要求用 `(path, status)` 作为身份。[delegation Skill：清单身份](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md#step-4-review-each-file)
5. 仅报告能够由变更和必要上下文支持的问题；每条包含路径、实际新文件行号、严重度、类别、事实链和建议。
6. 对 critical/high 发现做独立事实复核；不能精确定位时明确标注，不虚构行号。
7. 输出发现 + 覆盖摘要 + 排除/失败项 + 当前验证边界。只有用户明确要求修复时才改代码；修复后重新审查受影响差异并运行相应测试。

**可选后端**：用户已经配置 OCR 模型并明确希望 OCR 独立运行时，可使用 `ocr review --audience agent --format json --output <file>`；用户要外部代码扫描集成时可选 SARIF。主 Skill 说明这些输出和预算参数，也要求大结果写文件防止 stdout 截断。[主 Skill：高级选项与输出](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md#advanced-review-options)

**验收输出**：

- 每个审查项都有终态；
- `coverage_rate` 与跳过原因可见；
- 每条发现可定位、可复述触发条件、可说明影响；
- 无 critical/high/medium 时只说该严重度范围未发现问题，不声称“代码完全安全”；
- 审查与修复授权分开。

### P1：让八戒和沙僧“会调用”，不要复制实现

- 八戒在用户要求审查实际差异、且变更达到多文件或高风险范围时，可建议或调用照影镜；八戒仍负责需求符合性、规范符合性与过度设计判断，不复制 OCR 参数表和故障排查。
- 沙僧在收尾时可消费照影镜的覆盖摘要、失败分类、session id 和验证时间；不必修改沙僧来复制 OCR 能力。
- `xiyou` 总入口在“审查/PR review/扫描变更”任务中选照影镜；在“缩小方案/去掉无关改动”任务中仍选八戒；只有任务同时需要两者时才串联。

### P2：项目规则与 CI 后端，验证后再做

当真实项目出现稳定、重复的规则时，再提供 `.opencodereview/rule.json` 示例或规则生成向导；不要第一版就复制上游全部语言规则。CI、GitHub Actions、GitLab、Gerrit、MCP 和会话查看器是 OCR 产品集成能力，上游确实提供这些方向，但它们不是本轮 xiyou Skill 的必要组成。[README：文档与集成清单](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#documentation)

## 依赖与版本边界

| 项目 | 建议 |
|---|---|
| Git | 上游要求 Git 2.41 或更高。[README：Prerequisites](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#prerequisites) |
| OCR CLI | 作为可选外部依赖，由用户安装；不要由 Skill 在未确认时做全局安装。上游提供 npm 包、安装脚本、Release 二进制和源码构建。[README：安装](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#install) |
| Node.js | 仅 npm 启动器路径需要 Node；上游 `package.json` 声明 Node `>=14`，npm 包再下载平台二进制。[`package.json`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/package.json) |
| LLM | delegation mode 在 OCR 侧不需要模型端点；`ocr review` 需要受支持的提供商配置。[两个上游 Skill 的 compatibility](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md) |
| 最低 OCR 版本 | 建议首版固定并测试 `v1.12.13`，而不是只写“latest”。delegation JSON `--format` 需要 `v1.9.0+`，`--output` 需要 `v1.10.0+`；版本漂移会直接改变工作流。[delegate Skill 的版本兼容说明](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md#troubleshooting-cli-version-compatibility)；[主 Skill 的 `--output` 兼容说明](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md#troubleshooting) |
| 自动更新 | npm 启动器默认后台检查并自动升级，默认冷却时间为 18 分钟；可复现评测与 CI 应固定包版本并设置 `OCR_NO_UPDATE=1`，静态二进制不走此机制。[安装文档：Updating](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/installation.md#updating) |
| 许可 | 仓库和两个 Skill 均为 Apache-2.0；复制或改写上游内容时需要在对应技能目录保留固定来源、NOTICE 与许可证文本。[`LICENSE`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/LICENSE) |

## 主要风险与控制

### 1. 精度优先不等于安全兜底

项目方报告其专用流程相对通用 Agent 有更高 Precision/F1、更少 token 和更快速度，但同时明确 Recall 更低，这是减少噪声的主动取舍。[README：Benchmark](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#benchmark)

因此照影镜不能宣称“通过即安全”，也不应替代测试、静态分析、依赖审计或人工安全评审。高风险任务可提供“更彻底但更慢”的审查策略，不过上游 Ultra Mode 在当前路线图中仍是计划项，不能当成已经可用的稳定能力。[`ROADMAP.md`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/ROADMAP.md#ultra-mode)

### 2. 代码与凭据外发

`ocr review` 会把 diff 及检索到的上下文交给外部模型提供商；上游 FAQ 明确表示 OCR 没有内置秘密脱敏，敏感路径需要用户排除。使用前必须沿用用户与项目的数据边界。delegation mode 只表示 OCR 本身不调用 LLM，并不保证宿主 Agent 不联网。照影镜应在执行前说明所选模式与数据路径，并禁止把密钥写入规则、背景参数或报告。[README：工作原理](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#what-is-open-code-review)；[FAQ：Privacy & Security](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/faq.md#privacy--security)

上游威胁模型把 Git 仓库与 LLM 提供商都视作“半可信”：diff 可以包含对抗性内容，LLM 响应也必须校验。xiyou 的权限、写入和命令执行边界必须保留在 OCR 提示词之外，仓库内规则不能扩大 Agent 权限。[`ASSURANCE_CASE.md`：Threat Model](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/ASSURANCE_CASE.md#threat-model)

### 3. 外部二进制与版本漂移

全局 npm 安装会引入外部二进制和供应链更新；上游包通过 release URL 与 checksum 清单分发平台二进制。[`package.json` 的 `ocrConfig`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/package.json)

控制办法：Skill 不自动安装；文档给出 npm 与 Release 两条路径；评测与上游致谢固定版本；运行时对不兼容参数给出明确降级或升级建议，不对普通失败盲目重试。

### 4. 大变更可能只有部分覆盖

上游允许 token 总预算停止后续分组，并把未执行文件标成 `failed(budget)`；单文件 diff 超过 token 上限的 80% 会跳过。默认过滤还会排除多种测试文件、依赖/构建目录和已删除文件；仓库根目录下的 `vendor`、`node_modules` 等 provider directory 即使写 include 也不能恢复。范围/提交模式可恢复，但 workspace 模式不可恢复。[架构文档：五道过滤门](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/architecture.md#the-five-gate-file-filter)；[主 Skill：Budget 与 Gotchas](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md#gotchas)

控制办法：最终结论以覆盖清单为准；partial 不能写成 complete；默认排除、预算、超大文件和超时必须出现在结果摘要中。上游还明确说明，只要任一审查分组成功，其他分组失败时进程仍可能退出 0，因此不能只检查退出码，必须读取 warning、manifest 与失败/跳过列表。[FAQ：部分子 Agent 失败仍退出 0](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/faq.md#some-sub-agents-fail-the-run-still-exits-0)

### 5. 自定义规则可能覆盖安全检查

用户规则默认替换系统规则；如果生成项目规则时忘记 `merge_system_rule: true`，可能无意中丢掉内置语言或安全检查。[Review Rules：Priority Chain](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs/en/review-rules.md#priority-chain)

控制办法：xiyou 提供的规则模板默认合并系统规则，只有用户明确要完全替换时才关闭；报告同时展示规则来源和命中模式。

### 6. 自动修复的授权边界

上游 Skill 支持用户明确提出“review and fix”后修改代码，但上游路线图也明确把“未经人工审查的自动修复”排除在产品目标之外。[主 Skill：Fix](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md#step-4-fix)；[`ROADMAP.md`：Not Planned](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/ROADMAP.md#not-planned)

xiyou 应采用更清楚的边界：普通“审查”只报告；明确“审查并修复”才修改；提交、推送和发布仍需各自授权；修复后重新验证，不把建议代码直接视为正确补丁。

## 建议的验证方案

在正式炼化前，用同一模型、同一仓库快照做隔离对照：现有八戒/无照影镜基线 vs. `zhaoyingjing` 候选。至少覆盖以下六类任务：

1. 单文件小修复，验证不会制造低价值噪声；
2. 跨文件接口变更，验证每个文件都被独立审视；
3. 工作区含未跟踪文件，验证它被纳入清单；
4. 生成文件、二进制、供应商目录和超大文件，验证排除原因可见；
5. 项目自定义规则覆盖系统规则，验证来源与匹配模式正确；
6. 人为植入已知 bug、安全问题与误导性“看似问题”，验证召回、误报和事实复核。

记录以下指标：范围准确率、文件覆盖率、已知缺陷召回率、可行动发现的 precision、行号定位成功率、高严重度误报数、耗时、token（能取得时）、失败/恢复行为。上游公开基准包含 50 个开源仓库、200 个真实 PR、10 种语言和 1,505 个标注问题，但这些是项目方提供的基准描述；xiyou 仍需用自己的任务验证融合收益。[README：基准数据说明](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/README.md#benchmark)

## 优先级与决策门槛

| 优先级 | 动作 | 进入条件 | 暂停条件 |
|---|---|---|---|
| P0 | 实现 `zhaoyingjing`，用 `/zhaoyingjing` 覆盖 delegation、自管审查、scan、规则、会话与集成能力 | OCR CLI 可固定版本；六类评测中覆盖可审计，且比基线显著减少漏文件/定位漂移 | 安装负担超过收益；规则解析与实际 diff 不一致；高严重度误报不可接受 |
| P1 | 接入 `xiyou` 路由；让八戒/沙僧按需串联 | P0 真实任务稳定；职责边界没有让八戒或沙僧输出膨胀 | 大量简单任务被强制走重型流程 |
| P2 | 可选 `ocr review` 后端、项目规则模板、SARIF/CI | 用户确有独立模型、CI 或机器可读输出需求；数据边界明确 | 需要默认收集/外发代码；版本维护成本过高 |
| 不采用 | 直接复制上游全部内置规则、默认自动修复、新增审查人物 | 无 | 与现有角色重复、引入未经验证的规则噪声或扩大权限 |

最终建议是：**先炼“流程骨架”，后评估“规则内容”和“完整产品集成”**。这样能获得 OpenCodeReview 最强的确定性覆盖能力，同时保持 xiyou 的轻量、显式调用和职责清楚。
