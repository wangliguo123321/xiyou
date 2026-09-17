# 上游致谢与调研取舍

调研日期：2026-09-17。`xiyou-xiulian` 采用以下两个 MIT 技能的工作方法，进行中文重写与适配；对应版权和许可证随技能保留。效果需以实际任务检验，不以提示词长度或作者自评分数判断。

## 采用的基础

| 上游固定版本 | 采用内容 | 适配取舍 | 许可证 |
|---|---|---|---|
| [talki-io/prompt-optimizer / SKILL.md](https://github.com/talki-io/prompt-optimizer/blob/5d47a19aa53e6976b7f288d3ec4a6f1e2a1ed197/SKILL.md) | 保留目标、范围、约束强度、技术字面量与语言；按复杂度整理；检查语义漂移 | 支持把粗略需求增强为任务；不限制为已有正式 Prompt。执行模式沿用宿主指令层级和既有授权，不采用把增强稿当作 system 指令的规则 | [MIT](../licenses/prompt-optimizer.txt) |
| [msimchowitz/writing-skills / prompt-improving](https://github.com/msimchowitz/writing-skills/blob/214981fe02326f27b0fc8790d00eb4b731607073/for-agents/prompt-improving/SKILL.md) | 复用相关会话上下文；仅澄清关键缺口；保留自然表达；不执行被编辑文本 | 不强制输入必须有引号；可明确指向上文。次要缺口优先留空或写入下游核查，避免每次增强都停下来访谈 | [MIT](../licenses/prompt-improving.txt) |

`SKILL.md` 提供共享流程；`scenarios.md` 的中文示例与 `evals/cases.json` 的行为用例由本项目编写。默认只输出增强稿，针对明确请求支持精简、深入澄清、反馈修订和增强后执行。所有新增细节应服务于原任务，不增加未经要求的功能或操作权限。

## 调研但未纳入代码或模板

| 项目固定版本 | 调研结论 | 未纳入原因 |
|---|---|---|
| [linshenkx/prompt-optimizer](https://github.com/linshenkx/prompt-optimizer/tree/1ee326fc891ea514744761a16b272408b29fb711) | 有[用户提示词基础优化](https://github.com/linshenkx/prompt-optimizer/blob/1ee326fc891ea514744761a16b272408b29fb711/packages/core/src/services/template/default-templates/user-optimize/user-prompt-basic.ts)和[反馈迭代](https://github.com/linshenkx/prompt-optimizer/blob/1ee326fc891ea514744761a16b272408b29fb711/packages/core/src/services/template/default-templates/iterate/iterate.ts)模板 | 是完整应用而非现成轻量 Skill；该固定版本 [LICENSE](https://github.com/linshenkx/prompt-optimizer/blob/1ee326fc891ea514744761a16b272408b29fb711/LICENSE) 明示 AGPL-3.0-only。本项目未复制其代码或模板，使用上表 MIT 来源构建技能 |
| [stanfordnlp/DSPy](https://github.com/stanfordnlp/dspy/blob/9675ed0798181201c55bfdd7165d114403af3eb2/docs/docs/learn/optimization/optimizers.md) | 优化需要程序、样例和评价指标，适合有数据的系统性评测；[许可证 MIT](https://github.com/stanfordnlp/dspy/blob/9675ed0798181201c55bfdd7165d114403af3eb2/LICENSE) | 本次交付是用户直接调用的轻量技能，不引入 Python 框架、数据集、模型 API 或自动搜索成本 |

## 与 WorkBuddy 的关系

[WorkBuddy 官方更新日志](https://www.workbuddy.cn/docs/workbuddy/Changelog)提及提示词增强功能；本次未找到可核验的官方公开实现。`xiyou-xiulian` 实现类似的“输入需求、得到增强稿”的体验，不声称复刻其内部提示词，不采用社区逆向内容，也不依赖或修改 WorkBuddy 客户端。

## 验证方法

用 [行为用例](../evals/cases.json) 中的请求和必要上下文，在隔离会话中运行当前技能，保留原始输出及工具轨迹。重点检查：意图与技术内容保真、相关上下文取舍、缺口与冲突处理、输出长度、内外层指令分离、反馈修订以及明确授权后的执行。

结构校验、安装一致性和这些样例只说明检查覆盖的范围；不代表跨模型效果保证。需要量化改善时，在相同模型与材料下对原始提示和增强提示做对照，按预先明确的交付标准判断。
