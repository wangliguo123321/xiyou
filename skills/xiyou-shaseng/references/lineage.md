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

2026-10-26 的 [PR 文件输入采集](github-pr-files.md)沿用同一固定源及 Apache-2.0 归因，扩展为只读 REST 文件清单与 API patch 字段，复用本技能既有的有界 gh 捕获；原源本身没有该文件接口。新增逐页身份复核、文件数量/数据预算及文件列表与 patch 的分层完整性。字段语义依据该法器链接的 GitHub 官方文档；不宣称 patch 文本完整或代码已审，不修改既有评论接口。

2026-10-26 对既有 [PR 审查输入采集](github-review-comments.md)补齐有限浮点与递归解码错误处理，原字段、分页、身份及输出接口不变。此为上述固定源的宿主适配修正，沿用 Apache-2.0 与作者归因；不声称上游原实现已有修复或生产故障已发生。

2026-10-26 参考 [wshobson/agents 的 Python 性能方法](https://github.com/wshobson/agents/blob/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-performance-optimization/SKILL.md)（固定提交 `0874a27b17a22e2b7c2e2bcd725768e0803cad06`，作者 Seth Hobson，[MIT 全文](../licenses/python-performance.txt)），采用标准库 profile 归因来选择评论输入的紧凑 JSON 输出。具体格式为宿主实现选择，不引入通用调优流程、源程序或新运行依赖。

## SARIF 等级观察独立法器

- 2026-10-28 基于 Trail of Bits [sarif-parsing](https://github.com/trailofbits/skills/blob/196a9073ab10d35bacf111f945e02c00b2c6883a/plugins/static-analysis/skills/sarif-parsing/SKILL.md) 与 [sarif_helpers.py](https://github.com/trailofbits/skills/blob/196a9073ab10d35bacf111f945e02c00b2c6883a/plugins/static-analysis/skills/sarif-parsing/resources/sarif_helpers.py) 改编等级观察法器。固定完整提交 `196a9073ab10d35bacf111f945e02c00b2c6883a`；helper blob `a817f0386b5ebabd81d571da95b801d68025b535`，SHA256 `06d8e63849bd2b93baf31b23a33550447eed2ac457c2687f173933039e5ad247`。
- 归属 Trail of Bits；插件声明作者 Axel Mierczuk、Paweł Płatek，具体等级继承维护者 Dan Guido。其公开 Issue #262 与合并 PR #271 针对缺少 result.level 时误漏继承等级的修复、fixtures 和回归支持方法资格，不替代本地验收，不称上游私有生产事故或全库效果。
- 新增独立 `scripts/inspect_sarif_levels.py` 与 [使用引用](sarif-levels.md) 采用 [CC-BY-SA-4.0](../licenses/sarif-parsing.txt)，保留完整原许可、归属、固定来源和修改说明；其他独立文件按其原有声明。这是独立法器聚合，不把改编材料改标 Apache/MIT，也不宣称原作者背书。
- 保留每个 run 的 driver 上下文、有效 kind 及显式/规则默认/缺省等级顺序；不采用会跨 run 覆盖规则的全局映射、去重、路径归一、合并/重写或 CI 门禁。null兼容缺失、非法/冲突与未支持继承的保守未知、配额和机器结果是本地明确定义，不宣称完整 SARIF 验证。
- 不运行扫描器或来源程序，不读取 URI/artifact 指向文件，不按报告确认漏洞。原始显式等级计数、driver 规则定义计数与归一后的结果计数含义不同；解析完成/零退出不是无 error 结果或安全结论。

## PDF 逐页渲染证据

- 固定历史公开源：[OpenAI / skills PDF](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/pdf/SKILL.md)，完整提交 `49f948faa9258a0c61caceaf225e179651397431`，正文 blob `fd5d56058f10202e4f50a30bc2906f39696024a1`；[Apache-2.0 全文](../licenses/pdf.txt)来自该 PDF 目录。来源归属与同步维护者见本技能 `NOTICE.txt`。
- 2026-10-28 吸收“PDF 用 Poppler 逐页转 PNG 后实际看图；文本抽取不能替代版式核验”。原目录仅指令/界面元数据及图片，没有脚本、测试或可核实例；本地 [使用引用](pdf-render-evidence.md)及脚本是窄适配，不宣称移植了上游程序或证明模型能力提升。
- 原例库已明确弃用并迁往 `openai/plugins`；本法器固定旧版可分发方法，不称当前官方推荐。当前专有 PDF 条目及本机插件内容未被复制。宿主已有完整 PDF 工具时复用；本法器只补可分发的输入内容身份、范围与逐页产物对账接口。
- 保留真实视觉检查，不继承生成/编辑 PDF、OCR、依赖安装和源仓输出路径约定。快照、配额、选页/PNG 身份、拒覆盖和错误协议为本地适配，不是视觉合格或恶意 PDF 安全结论。

## 视频采样帧验收窄方法

2026-10-28：参考 HeyGen 的 [HyperFrames CLI Skill](https://github.com/heygen-com/hyperframes/blob/3d1c0764a018c5c0412c6273a54c87b6ce532ef7/skills/hyperframes-cli/SKILL.md) 及同版 `references/preview-render.md`、`references/lint-validate-inspect.md` 的独立最终验收步骤：核输出、用 ffprobe 对照时长、检查解码帧，按场景采样且实际看像素。Copyright 2026 HeyGen, Inc.，完整 [Apache-2.0](../licenses/hyperframes-cli.txt) 随附。

[视频采样帧证据](video-frame-evidence.md)与本地新写 `inspect_video_frames.py` 将该下游方法收敛为本地有限 MP4/MOV 的显式时点采样、输入内容快照及请求点/实际解码 PTS/PNG 身份绑定。不是上游脚本或完整渲染器移植，不执行原源程序；不采用原 CLI、GSAP、时间线编辑、云制作、自动安装、预览服务器或遥测反馈。帧/时长就绪仍不能代替内容验收或证明整段无缺陷。

## 独立 JSON 语言回退目录

2026-10-28：参考 [marmelab/react-admin 的 i18n Skill](https://github.com/marmelab/react-admin/blob/0c33d9c3c27cc4bf97e11f56080c5bfe182f2f2a/.agents/skills/i18n/SKILL.md)，及同版 [TranslationUtils.ts](https://github.com/marmelab/react-admin/blob/0c33d9c3c27cc4bf97e11f56080c5bfe182f2f2a/packages/ra-core/src/i18n/TranslationUtils.ts) 的 `mergeTranslations` 与 [真实测试](https://github.com/marmelab/react-admin/blob/0c33d9c3c27cc4bf97e11f56080c5bfe182f2f2a/packages/ra-core/src/i18n/TranslationUtils.spec.ts)，采用默认语言作底层、后层递归覆盖且保留缺键和额外消息的方法。Copyright (c) 2016-present, Francois Zaninotto, Marmelab，完整 [MIT](../licenses/react-admin-i18n.txt) 随附。

[回退目录引用](locale-fallback.md)及本地新写 `merge_locale_catalogs.py` 收窄为两份兼容对象/字符串 JSON 消息树。输出为可消费的独立 JSON；输入类型/形状与资源限制、内容身份和独占发布是宿主约束，不声称原 Lodash 会拒绝形状冲突或提供此 Python 接口。键与字符串按 JSON 数据字面处理，不采用 JavaScript 原型/属性访问，不模拟 TS `satisfies`、语言选择、插值、Polyglot 复数或完整 Lodash 语义。未执行原源程序，不携 React/Polyglot/Lodash 依赖。

## HTML 非执行 JSON 数据块

2026-10-28：采用 [AgriciDaniel/claude-blog 正式 blog-schema Skill](https://github.com/AgriciDaniel/claude-blog/blob/354442348815a7f0327077ad89af2c43cf4b4ab4/skills/blog-schema/SKILL.md) Step 9 的真实 JSON 编码与 HTML script 上下文转义方法，必要实现依据为同版 `scripts/blog_render.py:_build_json_ld`（488–509）及 `tests/test_blog_delivery_contract.py:test_xss_via_jsonld_is_escaped`（235–255）。Copyright (c) 2025-2026 AgriciDaniel，完整 [MIT](../licenses/blog-schema.txt) 随附。

[数据块引用](json-script-data.md)与本地新写 `embed_json_data.py` 选择正式 Skill 要求的全部 literal `<` 转义；原函数只转义 `</`，并非同等完整保证。输入改为已有 JSON，输出固定为普通 `application/json` 数据块，ID、类型/数值、资源、内容身份及独占发布为宿主约束，不声称原源已提供此工具或全浏览器/全页面安全。未运行上游程序，不采用博客制作、SEO、富结果或 Schema.org 验证。

原根 [NOTICE](https://github.com/AgriciDaniel/claude-blog/blob/354442348815a7f0327077ad89af2c43cf4b4ab4/NOTICE) 已完整核读，列出的 impeccable 编辑启发式、last30days 研究及 FLOW 提示内容未在本窄方法中采用。本次不取 Tessl 链接到的 `brain/.raw/sources/...` 快照作为原源；其父与更近许可须分层判断，不能仅据父声明推断无许可。
