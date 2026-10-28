# 独立 JSON 语言回退目录

用于已有纯 JSON 消息树的离线交付准备：默认目录作底层，部分目标目录覆盖，产出可直接读取的 `effective.json`。项目已具备 `mergeTranslations`、编译检查或等价合成流程时直接复用，不额外添加工具。

## 合成与核验

1. 确认两份资源的实际版本和用途：`base` 是默认底层，`override` 是目标覆盖。检查项目已有消费路径，不能把缺键回填的英文当成已完成目标语言翻译。
2. 只接受 JSON 根对象，内部为对象或字符串。两对象递归组合；同路径两字符串取目标值，**空字符串也是目标值**；仅底层存在的键保留，仅目标存在的额外消息也保留。两侧同路径对象/字符串冲突会拒绝，这是本接口的宿主收窄，不能说原 Lodash 也会拒绝。
3. 键按 JSON 字面处理，含点键不展开成路径；字符串原值保留，包括 Unicode、URL、插值和复数写法。它不作 JavaScript 原型/继承属性访问，不执行内容，不解析/比较占位符，不模拟 TS `satisfies`、Polyglot 或完整 Lodash 语义。
4. 用下列接口写入一个全新文件；再用普通 JSON 消费者读回，逐项核对关键覆盖值、缺键回退、额外消息、空字符串及必要数量/结构，并复核输入摘要未变。退出成功只证明有限合成完成，不证明译文语义、语言切换、插值或应用渲染正确。
5. 用户指定的正式结果保留；临时试验的程序、输入与产物在核验后按归属清理，只留必要事实/摘要。源文件与用户已有结果不覆盖。

## 接口

Python 3.9+ 标准库，无第三方依赖；路径相对本技能目录：

```bash
python3 scripts/merge_locale_catalogs.py --base /path/to/en.json --override /path/to/partial-fr.json --output /path/to/new-effective-fr.json
```

输入为不带 BOM 的 UTF-8 JSON 普通文件，不接受输入符号链接或特殊文件。重复 JSON 键（包括转义后相同的键）、非法 Unicode、数字/数组/布尔/null 或非对象根值会明确拒绝。不会按消息中的路径、URL 或字段执行别的读取/操作。

每份原始输入至多 2MiB、50000 节点，根深度 0、每条成员边加 1（含字符串叶），最大深度 32。节点含根/对象/字符串值，不含键。最终 UTF-8 输出至多 8MiB；这些是接口资源边界，不是翻译质量指标。

输出父目录需已存在，目标必须是新文件路径。完整临时写入后独占发布；已有文件、目录或符号链接均不覆盖，写入/校验失败不发布部分文件。本次临时文件会清理。成功退出码 0，stdout 收据为 `schema_version:1`，`base`、`override`、`output` 各有实际字节的 `sha256/bytes` 及 `nodes/strings` 计数；不打印完整消息内容。已支持的错误以 stderr 中的中文结构化 `error` 返回、退出码 2，带错误种类和有限位置/作用域。

结果稳定排序、两空格缩进、UTF-8 编码并有末尾换行；同输入重复生成字节一致。收据用于来源复核，不能单凭计数判断目录或翻译完整。

最小数据示例：

```text
base:     {"action":{"save":"Save","edit":"Edit"}}
override: {"action":{"edit":"Modifier","hint":""}}
结果:     {"action":{"save":"Save","edit":"Modifier","hint":""}}
```

## 来源与取舍

参考 [Marmelab React-admin i18n Skill](https://github.com/marmelab/react-admin/blob/0c33d9c3c27cc4bf97e11f56080c5bfe182f2f2a/.agents/skills/i18n/SKILL.md) 及同版 `packages/ra-core/src/i18n/TranslationUtils.ts` 的 `mergeTranslations` 和相应测试：默认语言在前、覆盖在后，递归保留未覆盖消息与额外消息。Copyright (c) 2016-present, Francois Zaninotto, Marmelab，完整 [MIT](../licenses/react-admin-i18n.txt) 随附。

原接口是 TS/JavaScript 中的 `merge({}, ...translationsModules)`。本脚本为本地新写的两份 JSON 兼容对象/字符串子集；资源限制、形状冲突拒绝、内容身份及独占输出是宿主实现，不声称原库提供此 Python 工具。原程序/测试未执行，不携 React、Lodash 或 Polyglot，不构建翻译、语言解析或格式化系统。
