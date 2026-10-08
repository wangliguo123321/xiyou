# 上游致谢与更新基线

`zhaoyingjing` 是 [Alibaba OpenCodeReview](https://github.com/alibaba/open-code-review) 的中文调用入口与西游体系适配层。它不重写 OCR 引擎，而是让用户通过一个 Skill 使用上游 CLI 的完整能力。

## 当前基线

| 项目 | 固定版本 |
|---|---|
| 上游仓库 | [`fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4`](https://github.com/alibaba/open-code-review/tree/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4) |
| 调研时发布版 | [`v1.12.13`](https://github.com/alibaba/open-code-review/releases/tag/v1.12.13) |
| 主调用 Skill | [`skills/open-code-review/SKILL.md`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review/SKILL.md) |
| 委托模式 Skill | [`skills/open-code-review-delegate/SKILL.md`](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/skills/open-code-review-delegate/SKILL.md) |
| 官方文档 | [`pages/src/content/docs`](https://github.com/alibaba/open-code-review/tree/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/pages/src/content/docs) |
| 许可证 | [Apache-2.0](https://github.com/alibaba/open-code-review/blob/fabbdb296b0d97e2140ada8d54ca7d6d6d1d7ad4/LICENSE) |

调研与融合判断见 [太乙评估记录](../../xiyou-taiyi/references/open-code-review-assessment.md)。

## 采用内容

- `ocr review`：工作区、提交、分支差异审查，业务背景、预算、并发、结构化输出和恢复。
- `ocr scan`：无 Git diff 时对文件、目录或代码库做全量扫描。
- `ocr delegate preview/rule`：由 OCR 确定文件范围与规则，当前宿主 Agent 完成语义审查。
- 项目/全局/命令行规则、排除项、系统规则合并与规则命中检查。
- 会话查看/评论/比较/导出/删除、恢复与 Viewer；JSON、SARIF 与多平台 CI/CD 集成入口。
- 提供商配置、自定义工具、作为 MCP client 接入外部工具，以及 OpenTelemetry 可观测性。
- 文件覆盖清单、严重度与类别、行级定位、失败/跳过透明化等输出纪律。

## 更新方法

更新时先读取上游最新 Release 和以下固定入口的最新版本：README、两个官方 Skill、安装/配置/CLI/规则/Delegation/CI/Session 文档。然后：

1. 比较命令、最低版本、参数与默认行为；特别核对 `--format`、`--output`、自动更新、预算、恢复和退出状态。
2. 更新 `references/ocr-operations.md` 的稳定映射与陷阱，不缓存可由 `ocr --help` 可靠取得的完整参数表。
3. 更新本文件的 commit、发布版、链接和 NOTICE 日期。
4. 运行结构校验与 `evals/cases.json` 行为用例；可用 OCR 时，至少实测 preview、delegate rule、workspace review/scan 的安全样例。
5. 在 README 和总入口仍能发现该法器，并确认直接调用名保持 `zhaoyingjing`。

上游与本项目均采用 Apache-2.0。本适配保留上游版权与固定来源；上游产品能力、商标和运行结果不由 xiyou 背书。
