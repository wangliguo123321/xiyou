# xiyou

**以西游人物组织 AI 编程能力，让问题讲得明白、方案选得有据、改动保持克制、工作收得完整。**

xiyou 是一组中文 Agent Skills。它以成熟开源技能为基础，把日常研发中不同的工作方式交给六个各有所长的人物，也提供可以单独取用的法器。你可以点名使用，也可以把任务交给 `/xiyou`，让它按需要分工。

## 为什么做 xiyou

用 AI 编程久了，会遇到一些反复出现的困扰。

代码改好了，但你仍不知道这段业务为什么这样运行。下一次换一个触发条件，又得从头排查。

一个局部问题，本来可以沿用现有机制解决，AI 却增加了管理器、策略层、配置开关，还顺手重构了旁边的代码。改动变大，验证和维护也跟着变重。

有时你只想确认一个字段或条件，却收到一份长篇报告；有时你需要认真比较路线，得到的却只是几个缺少依据的选项。

到了收尾，“已修改”“编译通过”“真实场景已验证”又容易混在一起。临时文件留下了，修改理由没有留下，接手的人还得翻完整段对话。

这些问题需要不同的处理方式。xiyou 用熟悉的人物帮助你表达意图：**这一次，是想学会、想破局、想快答、想收敛改动，还是想把事情收好尾。**

## 先用起来

把下面这句话交给你正在使用的 AI 编程工具：

```text
请从 https://github.com/wangliguo123321/xiyou 安装全部 Skills，使用当前工具的用户级技能目录。
```

<details>
<summary>也可以使用现成的 Skills 安装器</summary>

以下示例安装到 Codex；需要 Node.js 和 npx。

```bash
npx skills add wangliguo123321/xiyou --agent codex --skill '*' --global
```

安装器来自 [vercel-labs/skills](https://github.com/vercel-labs/skills)。其他客户端可以使用各自支持的技能安装方式。

</details>

在支持 Skill 斜杠菜单的客户端中，输入 `/xiyou` 筛选总入口、人物和常规法器；代码巡检可直接记 `/zhaoyingjing`。Codex 终端／IDE 也可以用 `$xiyou`、`$xiyou-wukong`、`$xiyou-xiulian`、`$zhaoyingjing` 等方式引用。具体菜单形式由客户端决定。

| 入口 | 人物与法器 | 什么时候用 |
|---|---|---|
| `/xiyou` | 全队入口 | 交给它一个任务，按需要安排人物协作 |
| `/xiyou-tangseng` | 唐僧·明理 | 想把业务、代码来由和排查方法真正弄懂 |
| `/xiyou-wukong` | 悟空·破局 | 卡在问题原因或方案选择，需要找到突破口 |
| `/xiyou-nezha` | 哪吒·速断 | 只想快速确认一个事实、条件或代码位置 |
| `/xiyou-bajie` | 八戒·省力 | 防止过度设计，检查本次改动能否更小、更直接 |
| `/xiyou-shaseng` | 沙僧·善后 | 清理本次临时产物，记录修改思路和接续事项 |
| `/xiyou-taiyi` | 太乙·炼技 | 发现了一个好 Skill，想吸收进现有人物或新增人物 |
| `/xiyou-xiulian` | 法器·修炼 | 把粗略需求或已有提示词改写清楚，保留原意和约束 |
| `/zhaoyingjing` | 法器·照影镜 | 用一个入口审查差异、扫描代码、管理规则或接入 OpenCodeReview |

## 六个人物，六种做事方式

### 唐僧·明理：这次讲透，下次能判断

取其耐心、重视来由、坚持目标的一面。唐僧先回答当前问题，再从熟悉的业务行为讲到代码：谁提供输入，谁拥有状态，数据经过哪些环节，最后为什么得到这个结果。

它重点解释关键规则的必要性：解决过什么问题，当前实现怎样工作，改变一个条件后会怎样。历史动机需要源码、提交或文档支持；资料没有说明的地方会明确留下疑问。

讲解结束时，留下的是可以复用的判断方法，例如“先区分数据没到，还是数据到了但没有被消费”。需要跨次学习时，按模块保留轻量摘要，并在下次使用前核对代码变化。

“已经讲过”和“已经掌握”分别对待。练习与完整课程按需进行。

需要把分支或操作顺序讲清时，唐僧可制作[可编辑的离线 SVG 流程图](skills/xiyou-tangseng/references/flowchart.md)，使用起止、操作、判断等语义图元与显式正交连线。交付前实际渲染核对内容和版面；重复调整标签可沿用同一制作接口，普通问答不强制成图。

```text
/xiyou-tangseng 解释这个状态为什么一直没有结束，并讲清下次该从哪里排查。
```

### 悟空·破局：看清前提，找到出路

“火眼金睛”用来检查最影响结论的假设，“七十二变”用来根据约束调整路线。

悟空会先理解现场，找出能够区分不同解释的最小检查。证据有变化，判断也随之变化。有真实选择空间时，它比较不同方案的收益、改动范围、维护负担、失败行为和验证方式，并明确推荐。

每条推荐都应能说明：什么条件下成立，什么证据出现后应该改选。已经批准的方案，不会被反复拉回起点。

```text
/xiyou-wukong 比较这两种修复路线，说明各自的影响，给出推荐和验证办法。
```

已有 Terraform 状态导出需要盘点时，悟空可读取[离线资源地址库存](skills/xiyou-wukong/references/terraform-state-inventory.md)，保留模块与对象分类，不输出资源属性值，不运行 Terraform 或云操作。

已有 GitHub Actions 工作流需要调查依赖声明时，悟空可做[离线 uses 引用观察](skills/xiyou-wukong/references/workflow-refs.md)，返回 job/step 位置与字面形式；不执行工作流，也不把完整 SHA 形态当安全结论。

已有解包的 Playwright `.network` 需要调查时，悟空可做[离线网络记录观察](skills/xiyou-wukong/references/playwright-network.md)，保留声明行、URL有限投影与未知状态；不运行浏览器或做耗时、根因判断。

已有明确的 npm v2/v3 锁文件需要核对时，悟空可做[离线锁定树声明盘点](skills/xiyou-wukong/references/npm-lock-inventory.md)，保留传递包的安装位置、精确版本、开发依赖与排除项。公开仓库 URL 前缀及完整性字段只作声明观察，不代表包已验证或项目安全。

### 哪吒·速断：圈定问题，尽快答完

风火轮负责快速抵达入口，乾坤圈负责限制调查范围。

哪吒适合确认字段含义、状态条件、提交是否包含某项变化，以及一条日志究竟能证明什么。它沿最相关的线索检索，证据足够就给出结论。

快答仍然保留必要条件。证据不足时，说明已经确定的部分和最小缺口，不把猜测压缩成一个肯定答案。

“混天绫”把结论或下一动作放到第一行，多步任务说明当前状态，失败原因按证据强度表达。长列表可以分组和排序，但不会为了显得简短漏掉审计、检索或完整清单中的相关发现。

```text
/xiyou-nezha 这个空值分支会清空旧数据吗？给结论和代码依据。
```

### 八戒·省力：每一处改动，都要有必要

把八戒务实、关心负担、寻找省劲办法的一面，用来约束 AI 的过度设计。

八戒在方案前、实施中和收尾时检查同一件事：这组改动解决哪个已确认要求？去掉它，问题是否仍能正确解决？现有机制能否承担？为什么要影响公共组件或其他模块？

它特别关注单次用途的通用框架、没有需求的扩展接口、假设性配置，以及顺手发生的重构、重命名和格式调整。准备添加新能力时，先检查仓库和成熟工具中是否已经存在。

审查时把需求符合性与代码规范分开：既看有没有漏做、做错和额外增加行为，也看是否遵循项目约定。面对“再通用一点”“加个管理器”等评审建议，先核对实际场景和技术依据，再决定采纳、缩小实现或暂缓。

最小改动需要保持修复完整、行为正确和必要验证。学习价值、可靠性和未来反复返工的成本，也要一起考虑。

```text
/xiyou-bajie 审视当前方案和差异，去掉无关设计，保留解决问题所必需的改动。
```

### 沙僧·善后：把修改理由和现场一起收好

取其沉稳、耐心、承担琐碎工作的一面。沙僧负责让结果真实、现场干净、后续能够接续。

它先对照任务目标，确认实际完成了什么，再保留必要证据、清理本次临时产物。只处理归属明确的内容，保留正式交付物、项目需要的测试和文档，以及用户已有工作。

修改记录回答几个关键问题：为什么这样改，为什么选择这个范围，哪些替代路线被放弃，验证到了哪一步，还有什么没有完成。

每份验证证据都对应实际代码状态；同一提交上后来又改过代码，先前的通过结果也可能已经过期。清理会核对产物归属和动态引用，文档保留事实来源与下一步完成条件，分支和工作树的处理只在相应交付任务中进行。

完成、暂停、失败和受阻都可以有清楚的收尾。文档保存到用户指定的位置；默认使用项目外的个人文档目录。

```text
/xiyou-shaseng 清理本次临时验证文件，记录修改理由、验证边界和下一步。
```

已有 PDF 需要交付验收时，可让沙僧生成[逐页渲染证据](skills/xiyou-shaseng/references/pdf-render-evidence.md)：把明确内容和页范围对应到 PNG 与清单，再实际看图核版面；不把渲染成功当作视觉合格。

已有本地 MP4/MOV 需要核对指定时点时，可让沙僧生成[视频采样帧证据](skills/xiyou-shaseng/references/video-frame-evidence.md)：绑定视频内容、声明时长、请求采样点和实际解码帧，按需对照明确的时长约定，再实际看图检查内容。采样不代表整段视频已经验收。

已有两份独立 JSON 语言资源、需要把默认语言与目标覆盖收成一个文件时，可让沙僧[合成语言回退目录](skills/xiyou-shaseng/references/locale-fallback.md)：目标已有字符串优先，缺键保留默认语言，额外消息与空字符串保值，交付前用普通 JSON 消费者读回核对。项目已有等价工具时直接复用。

已有 JSON 需要交付为 HTML 中的非执行数据块时，可让沙僧[生成 JSON script 片段](skills/xiyou-shaseng/references/json-script-data.md)：使用标准 JSON 编码，转义数据中的所有 `<`，避免数据提前结束节点；交付前在真实浏览器读取并解析，核对原值与宿主节点。

### 太乙·炼技：把社区经验炼成可用的法器

借太乙真人传授能力、重塑既有结构的意象，负责持续吸收开源社区的经验。

给太乙一个 Skill 链接，或描述一个反复出现的工作短板，它会回到原始项目核对内容、版本、依赖和许可证，再决定如何吸收：

| 发现的能力 | 处理方式 |
|---|---|
| 已有能力完整覆盖 | 保留现状，避免重复加入 |
| 能改善某件已有法器 | 在原有基础上做定向改进 |
| 有明确场景，适合现有人物 | 给这个人物增加按需使用的法器 |
| 有独立、长期有用的职责 | 选择贴合的人物，新增一个 Skill |
| 缺乏价值或无法核验 | 说明原因，暂不采用 |

已有单包 npm 打包 JSON 清单时，太乙可按明确的必需路径做[清单核对](skills/xiyou-taiyi/references/npm-pack-check.md)，保留完整声明路径、缺件与缓存名匹配；不运行 npm，不将计划清单当最终归档或发布证明。

例如，一套更好的假设验证方法适合给悟空，一套更清楚的修改决策记录方法适合给沙僧。只有出现现有人物难以自然承接的独立职责，才考虑新增人物。

炼化需要实际任务验证。太乙会先固定旧版与验收标准，再对匿名成果做成对比较；每个目标默认最多两轮，持平、证据不足或关键回归失败就保留稳定版。角色更多、文件更长，都不能单独证明能力变好了。

```text
/xiyou-taiyi 评估这个 Skill；合适就炼化给现有人物，必要时新增职责清楚的人物。
```

## 法器：按需取用的能力

法器解决具体问题，可以单独调用，也可以配合人物使用。通常沿用 `/xiyou-*` 命名；用户需要特别好记的独立入口时可以保留短名，例如 `/zhaoyingjing`。后续有适合独立使用的方法，也会继续收录在这里。

### 修炼·提示词增强：先把想做的事说清楚

取“修炼”反复打磨、去粗存精的意思，把一时说不清的需求，整理成目标明确、约束清楚、结果可以判断的提示词。

修炼先理清你真正想完成什么，再利用相关上下文补清表达。技术名称、命令、数值和原有要求会保留；缺少的事实会明确留下空位，不擅自添加功能或替你决定方案。

可以从一句粗略需求开始，也可以拿已有提示词继续打磨。觉得太长、重点不对，或上一次回答偏离了预期，都可以带着反馈再炼一次。

默认交付可复制的增强稿。明确要求“增强后直接执行”时，才接着完成原任务。

```text
/xiyou-xiulian 帮我增强这段提示词：排查登录失败的原因，先不要改代码。
```

### 照影镜·代码巡检：把完整审查能力收进一个入口

照影镜封装 [Alibaba OpenCodeReview](https://github.com/alibaba/open-code-review) 的完整能力。你只需要说明审查对象和目的，不必记住 CLI 参数：它会在工作区、提交、分支差异、完整文件扫描、委托模式、自管模型、规则检查、会话恢复、JSON/SARIF 与 CI 集成之间选择合适入口。

审查结果会说明实际覆盖了哪些文件、跳过或失败了哪些部分，并把发现定位到代码行。普通审查只报告；明确要求修复时才修改代码，提交和推送仍分别处理。

```text
/zhaoyingjing 审查当前分支相对 main 的改动，并修复已确认的高风险问题，不要提交。
```

## 为什么采用“人物 + 法器”

人物提供稳定的职责，法器提供具体的工作方法。

你可以记住“八戒帮我收敛改动”，不用记住所有反过度设计技巧；新方法出现后，也可以成为八戒的一件法器，继续从同一个入口使用。

角色之间共享相同的事实标准，区别在于这次希望交付什么。总入口会按任务选择和接续，复用已经取得的证据，最后整合成一个结果。

例如，调查一个偶发问题时，可以由悟空寻找原因和比较路线，八戒检查修复范围，沙僧整理验证与收尾；你想理解这次修改时，再让唐僧讲透。一个简单事实问题，则由哪吒回答即可。

**默认按需协作，不要求所有角色逐一发言。** 用户的明确要求和项目约定始终优先，角色名称不会扩大操作权限。

## 站在成熟项目的基础上

xiyou 从已有的优秀方法出发，保留有用的流程，再针对角色分工、中文表达和日常使用作适配。

| 技能与来源记录 | 主要基础 |
|---|---|
| [唐僧](skills/xiyou-tangseng/references/lineage.md) | Anthropic 解释式教学、Matt Pocock `teach`；Cathryn Lavery `diagram-design` 的静态流程图制作方法 |
| [悟空](skills/xiyou-wukong/references/lineage.md) | Superpowers `brainstorming`、`systematic-debugging`；HashiCorp Terraform 状态地址盘点（独立 MPL-2.0 法器）；GitHub 社区 workflow 引用观察（保原 MIT 通知）；Microsoft Playwright 网络声明观察；Trail of Bits npm 锁定树声明盘点（独立 CC-BY-SA-4.0 法器） |
| [哪吒](skills/xiyou-nezha/references/lineage.md) | ECC `iterative-retrieval`、`code-explorer`；`i-have-adhd` 的行动优先表达 |
| [八戒](skills/xiyou-bajie/references/lineage.md) | Anthropic 代码简化、ECC 复用优先、Matt Pocock 双轴审查、Superpowers 评审建议核验、gstack 范围保持与缩减 |
| [沙僧](skills/xiyou-shaseng/references/lineage.md) | Matt Pocock 交接与文档组织、Superpowers 完成验证与分支状态检查、ECC 文档同步、清理分级与分层验证；OpenAI 历史公开 PDF 逐页渲染验收；HeyGen HyperFrames 的成品视频抽帧验收；Marmelab React-admin 的语言目录回退合成；AgriciDaniel claude-blog 的 JSON/HTML 数据块编码；Trail of Bits SARIF 等级观察（独立 CC-BY-SA-4.0 法器） |
| [太乙](skills/xiyou-taiyi/references/lineage.md) | Vercel `find-skills`、Anthropic `skill-creator`、ECC 技能盘点、Darwin 匿名成对比较与有界优化；YottaMeta 的 npm 打包名单检查子法 |
| [修炼（法器）](skills/xiyou-xiulian/references/lineage.md) | talki `prompt-optimizer` 的保真改写、Max Simchowitz `prompt-improving` 的上下文澄清（均为 MIT 许可） |
| [照影镜（法器）](skills/zhaoyingjing/references/lineage.md) | Alibaba OpenCodeReview 的差异审查、全量扫描、委托模式、规则、会话与集成能力（Apache-2.0） |

感谢 [Superpowers](https://github.com/obra/superpowers)、[Matt Pocock Skills](https://github.com/mattpocock/skills)、[ECC](https://github.com/affaan-m/everything-claude-code)、[Anthropic Skills](https://github.com/anthropics/skills)、[Anthropic 官方插件库](https://github.com/anthropics/claude-plugins-official)、[Vercel Skills](https://github.com/vercel-labs/skills)、[gstack](https://github.com/garrytan/gstack)、[i-have-adhd](https://github.com/ayghri/i-have-adhd)、[talki Prompt Optimizer](https://github.com/talki-io/prompt-optimizer)、[Max Simchowitz Prompt Improving](https://github.com/msimchowitz/writing-skills/tree/main/for-agents/prompt-improving) 和 [Alibaba OpenCodeReview](https://github.com/alibaba/open-code-review)。各技能目录中的上游致谢提供具体文件、固定版本、适配说明与许可证。

## 一起完善 xiyou

欢迎通过 [Issue](https://github.com/wangliguo123321/xiyou/issues) 分享使用反馈、反复出现的痛点或值得吸收的 Skill，也欢迎提交 PR。

一次好的改进，最好能说清：遇到了什么问题，基于哪个上游，改了什么，以及用什么真实场景确认它有帮助。优先完善已有能力；新增人物或法器时说明它的用途与边界。

采用开源方法时，同步维护 README 和技能目录中的来源、适配说明与许可证，让后续改进有据可循。

GitHub 中的改进经合并后成为共享版本。已经安装到电脑里的副本需要再更新一次，你可以直接告诉 AI：

```text
请从 https://github.com/wangliguo123321/xiyou 更新我已安装的 xiyou，先保留并检查本地改动。
```

日常使用只需要记住人物和法器的入口。源码、差异和社区协作交给 GitHub 与现成工具，不需要额外的维护命令。

## 许可

本项目新增组织与适配内容采用 [Apache-2.0](LICENSE)。各上游内容保留其原有许可，版权声明及许可证随对应技能提供，详见 [NOTICE](NOTICE)。

独立的 [SARIF 等级观察引用](skills/xiyou-shaseng/references/sarif-levels.md) 与 [对应实现](skills/xiyou-shaseng/scripts/inspect_sarif_levels.py) 是 Trail of Bits 方法的改编，按 [CC-BY-SA-4.0](skills/xiyou-shaseng/licenses/sarif-parsing.txt) 分发；此为上述默认声明的明确文件例外。归属与修改说明随法器提供，其余独立组件的许可不变。

独立的 [Terraform 状态库存引用](skills/xiyou-wukong/references/terraform-state-inventory.md)与[对应实现](skills/xiyou-wukong/scripts/inspect_terraform_state.py)按 [MPL-2.0](skills/xiyou-wukong/licenses/terraform-refactor.txt)分发，来源 HashiCorp / Copyright IBM Corp. 2026；这是默认 Apache 声明的明确文件例外，其余独立组件许可不变。

独立的 [npm 锁定树盘点引用](skills/xiyou-wukong/references/npm-lock-inventory.md)与[对应实现](skills/xiyou-wukong/scripts/inspect_npm_lock.py)改编自 Trail of Bits / Eric Quintero 的 supply-chain-risk-auditor，按 [CC-BY-SA-4.0](skills/xiyou-wukong/licenses/npm-lock-inventory.txt)分发，归属和修改说明随附；这是默认 Apache 声明的明确文件例外，其余组件许可不变。
