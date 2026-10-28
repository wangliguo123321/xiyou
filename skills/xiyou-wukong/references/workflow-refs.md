# 离线工作流引用观察

读取用户明确给定的 GitHub Actions workflow YAML，定位 job 级复用工作流和 steps 级 action 的 `uses`，为 CI 调查或后续审查提供原值、位置及有限字面分类。已有工具提供同样的完整性、位置与未知协议时优先复用。

从本技能目录运行：

```bash
ruby scripts/inspect_workflow_refs.rb --input /path/to/workflow.yml
```

仅依赖 Ruby 2.6+ 标准库 Psych，使用原生 AST，不用 `load`、`safe_load` 或对象反序列化，不展开 alias/merge。不执行或修改 workflow，不读 action 路径、访问网络、解析表达式、自动改 pin 或安装依赖；不输出 run/env/with 内容。输入为普通本地 UTF-8 文件，拒绝符号链接与特殊文件，SHA256/bytes 绑定实际读取内容，原文件不改写。

## 声明与位置

只接受一个非空 YAML 文档，根及显式 `jobs` 为映射；空 jobs 可读为零条声明，但不表示工作流有效或安全。按原 job 顺序先取 job 级 uses，再按 steps 原数组顺序取 step 级 uses，不在任意字段中搜索文字 `uses:`。注释、run 字符串及 env/with 中的同名文字不作为引用。

结果包含 `scope`（job/step）、`job_id`、从 1 起算的 `step_index`（job 级为 null）、uses 原标量和 `form`。`line`/`column` 是原生 AST 值节点的从 1 起算位置，指引号或块标量指示符起点，不是内容字符的偏移。job_id `on` 保留为原文，不经过 YAML 1.1 布尔类型转换。

## 有限字面分类

| form | 本接口观察的文本 |
|---|---|
| remote_sha40 | owner/repo[/path]@ref，ref 恰为 40 位 hex |
| remote_named | 同一有限远端结构、非空无空白 ref，但不是 40hex；不能离线区分 tag、branch 或其它 ref |
| local | ./ 开头的非空无空白路径；job/step scope 分开，不读取目标 |
| docker_digest64 | docker://镜像@sha256: 后为 64hex 的字面形态 |
| docker_named | 无 @、非空无空白的 docker:// 镜像标识，可含 tag 或默认名称 |
| dynamic | 含 ${{ 的表达式文本，不求值 |
| unknown | 当前 $/ 同仓新语法或其它未支持形态，不断言其无效 |

这里是有限语法观察，不能证明 GitHub 接受完整工作流。40hex、digest64 均未远端验证其存在、归属、内容或可信度，不给安全等级或 CI 放行结论。step 的 ./ 取决于实际 workspace，不保证 caller commit；不能把所有本地引用当成外部可变依赖。$/ 的平台语义和企业版本支持有差异，本工具先保 unknown，不猜。

## 完整性与错误

`verification` 始终为 `not_performed`。`status=complete/partial/error` 对应退出码 0/2/1：

- 全部声明位置可定位且形态已支持时 complete；零引用只表示文档声明中没找到 uses，不表示没有执行代码。
- dynamic/unknown 导致 partial，但仍保全部已定位引用与已知 `reference_count`。
- 相关 root/jobs/job/step 映射、jobs/steps 容器或 uses 值上的 alias、merge、复杂键或不支持的显式 tag 可能隐藏引用，返回 partial、count 为 null、refs 清空，不拼成半份库存；不展开它们。未采用字段内部的 alias/tag 不影响此有限库存。
- 坏 YAML、多文档、错误结构、相关重复键、非法采用标量、输入门或配额错误为 error，count 为 null、无半库存，错误不回显源语法片段。

采用标量按 AST 原文观察，不做隐式类型求值。空标量（uses: 或空引号）是错误；plain null、~、数字或布尔文字非空时按有限形态归 unknown，不声称它们是合法 GitHub uses。显式 null 等非 str tag 在相关标量上保未知；jobs/steps 的 null 标量不等于所需容器。

输入最大 2 MiB、AST 最多 50000 节点及深度 64（Stream 为 0）、引用最多 2000、采用标量最多 4096 UTF-8 字节且无控制字符。超限拒绝，不截断。uses/job_id 元数据本身仍可能含业务命名，这不是通用脱敏工具；只排除未采用的执行/环境字段。

## 来源与适配

来源 [github/awesome-copilot 的 github-actions-hardening](https://github.com/github/awesome-copilot/blob/98b45a78d3ed316e78f005b60594d5c4a50588e3/skills/github-actions-hardening/SKILL.md) Step 5，及同版 [supply-chain](https://github.com/github/awesome-copilot/blob/98b45a78d3ed316e78f005b60594d5c4a50588e3/skills/github-actions-hardening/references/supply-chain.md)。Copyright GitHub, Inc.，原 [MIT 全文](../licenses/github-actions-hardening.txt)保留；这是 GitHub 组织中的社区贡献，不暗示背书。

2026-10-28 本地新写原生 AST 的离线库存、有限分类、位置、未知与限额协议；原 Skill 没有此 helper。新增适配沿系列默认 Apache-2.0，保留原 MIT 通知，不采用原源的全流程、固定严重等级、自动写 pin、权限/runner/注入审查或安全保证。语法参考 [GitHub 官方工作流语法](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)的 job/steps uses 部分，具体归属见 [上游致谢](lineage.md)。
