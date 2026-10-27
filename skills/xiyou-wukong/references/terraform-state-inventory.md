# 离线 Terraform 状态库存

<!-- SPDX-License-Identifier: MPL-2.0 -->

在迁移或重构调查前，读取用户已导出的 Terraform `show -json` 状态文件，盘点其中声明的资源对象与模块。已有工具能提供相同身份、层次和属性值排除要求时优先复用。本法器不访问云端、不运行 Terraform、provider、init、state mv、plan 或 apply，也不读取 JSON 中的路径或 URL。

从本技能目录显式给文件：

```bash
python3 scripts/inspect_terraform_state.py --input /path/to/exported-state.json
```

依赖 Python 3.9+ 标准库，不安装其它工具。输入须为既存普通本地 JSON 文件，拒绝符号链接或特殊文件，不改写原文件；输入字节数与 SHA256 对应实际读取内容。

## 库存含义

只读 `values.root_module`，先保当前模块的资源数组顺序，再深度优先遍历 `child_modules`。资源和模块地址均当作不透明字符串保留，不能按点号拆分、重建或按地址去重。每个条目只输出 `address`、`mode`（managed/data）、`type`、所属 `module_address` 和 `object_kind`；根模块地址为空串。

当前官方渲染实现可能将 Current 和 Deposed 对象逐项输出，同一地址可出现多次。没有 `deposed_key` 时标 `current`，有非空字符串时标 `deposed`，不输出该 key 原值。`resource_count` 是文档中遍历到的对象条目数，`module_count` 包括根和所有声明子节点；它们不是唯一地址或真实云资源数量。非法类型或空 key 不猜。

不输出 `values`、`outputs`、`sensitive_values`、索引、provider 或未知属性的内容。这里只排除这些值字段，不承诺任意元数据已脱敏；声明地址本身可能含业务命名。该输入仍是本地导出副本，库存不证明它新鲜、完整或与云端一致，不替代 HCL 地址校验、状态迁移方案或执行授权。

## 格式、未知与错误

只支持数字 minor 的 `format_version` 1.x，忽略未采用的新属性；未知 major、计划文件和原始 version-4 tfstate 均不当成状态库存。

- 缺 `values` 的合法最小输出可能表示空 state 或没有 state；`values` 有而没有 `root_module` 也不证明资源已展开。返回 `partial`，两个 count 都为 `null`，不假称零资源。
- 显式 `root_module: {}` 返回完整的零条目、一模块；模块省略 `resources` 或 `child_modules` 代表对应列表空。无资源中间模块仍继续遍历孩子。`null` 与省略不同。
- 坏 JSON、重复键、非法字段类型或模式、输入门与限额错误返回 `error`，count 为 `null`、资源数组为空；不输出一份看似完整的半库存，不把源值放进错误片段。

标准输出为单个 JSON：`complete/partial/error` 对应退出码 `0/2/1`。完整仅表示本工具支持范围内的声明字段读取完成，不能据此允许迁移或断言云上没有资源。

输入最大 5 MiB、模块最多 512、对象条目最多 2000、模块深度最多 32（根为 0）、所用元数据字符串最多 1024 字符且无控制字符。超界拒绝，不自动截断、升级权限或改解析规则。

## 来源与改动

Copyright IBM Corp. 2026（原 Skill 声明）。基于 HashiCorp [refactor-module](https://github.com/hashicorp/agent-skills/blob/f706481af9b8fedb66de909f6243ad29601afa0c/plugins/terraform/skills/refactor-module/SKILL.md) 的迁移前地址盘点、稳定状态接口及敏感值不回显方法。2026-10-28 本地新写只读文件、层次遍历、对象分类、限额及结构化结果；原 Skill 没有此 helper，不宣称移植原程序或证明完整模块重构能力。

本引用与独立脚本按 [MPL-2.0](../licenses/terraform-refactor.txt)分发，其他独立文件许可不变。官方 [JSON 格式](https://developer.hashicorp.com/terraform/internals/json-format)及固定 Terraform 实现行为用于核字段：网站 current-only 说明与已核当前实现的 Deposed 行为存在差异，故显式保对象分类。未复制 Terraform 的 BUSL 实现、原 HCL 样例或测试数据；完整归属及固定版本见 [上游致谢](lineage.md)。
