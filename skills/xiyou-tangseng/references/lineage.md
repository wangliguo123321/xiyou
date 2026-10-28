# 上游致谢

本人物基于以下公开版本翻译并适配。保留其核心工作方法，按 xiyou 的职责、触发范围和用户意图调整。每件法器中的“西游适配”说明具体取舍。

| 法器 | 固定上游 | 许可证 |
|---|---|---|
| [teach](teach.md) | [mattpocock/skills / skills/productivity/teach/SKILL.md](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/teach/SKILL.md) | [MIT](../licenses/teach.txt) |
| [explanatory](explanatory.md) | [anthropics/claude-plugins-official / plugins/explanatory-output-style/hooks-handlers/session-start.sh](https://github.com/anthropics/claude-plugins-official/blob/da823e86c8feef13b73b6712af11eadd38c992f6/plugins/explanatory-output-style/hooks-handlers/session-start.sh) | [Apache-2.0](../licenses/explanatory.txt) |
| [离线流程图制作](flowchart.md) | [cathrynlavery/diagram-design / skills/diagram-design/SKILL.md](https://github.com/cathrynlavery/diagram-design/blob/0cf73c3fcc56667ad91a9a04c439ac6ccfabc9d1/skills/diagram-design/SKILL.md)，及同版 `references/type-flowchart.md`、`primitives-core.md`、`style-guide.md`、`output-spec.md` | [MIT](../licenses/diagram-design.txt) |

2026-10-28：吸收第一方流程语义形状、正交连接、分支标签净空、系统字体及可访问性方法。宿主新增 `make_flowchart.py` 实现有限显式场景到原生 SVG 的制作接口；不是上游 HTML 导出器移植。不带第三方图标、logo、字体字节，不执行上游脚本。原源版本固定到上述完整提交；仓库 release 版本不当作该 Skill 的独立版本。
