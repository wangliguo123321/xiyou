# 离线 npm 锁定树声明盘点

改编自 Trail of Bits / Eric Quintero 的 supply-chain-risk-auditor；本引用及对应脚本按 [CC-BY-SA-4.0](../licenses/npm-lock-inventory.txt) 分发。固定来源、修改和取舍见 [上游致谢](lineage.md#离线-npm-锁定树声明盘点)。

用户已有明确的 `package-lock.json` 或 `npm-shrinkwrap.json`，需要核对锁定树中的包声明时使用。项目已有等价工具则直接复用；普通依赖选型不强制生成清单。

```sh
python3 scripts/inspect_npm_lock.py --input /明确已有文件/package-lock.json
```

需要 Python 3.9+ 标准库及支持 `O_NOFOLLOW` 的系统（macOS/Linux）。只读显式普通文件，JSON 输出到 stdout；不会自动查找目录、读取 `package.json`、联网、执行 npm/安装脚本或跟随数据中的 URL、link、路径。调用方需要保存时选择项目外位置。

## 读取范围

只支持整数 `lockfileVersion` 为 2 或 3 且有对象 `packages` 的文件。按原 `packages` 位置排序，每个位置分别保留，不按同名同版本去重：

- 键含字面 `node_modules/` 且非 link、版本非空的项进入 `packages`。名称优先取 entry.name，否则取最后一个 `node_modules/` 后的字面字符串；版本原样保留，dev 缺失为 false。
- 根项、其它非 node_modules 位置、link 与缺版本项保留在 `excluded_entries`，说明未被纳入包清单的原因。link 指向的真实目标不解析，未被纳入不代表不存在或不需要审查。
- resolved 以 `https://registry.npmjs.org/` 开头且 integrity 是非空字符串，记 `registry_integrity_declared`；其余记 `not_established`，保留 `non_public_registry_declaration`、`missing_integrity` 中适用的原因。两项原文均不输出，避免将 URL 中的凭据带进报告。 position/name/version 仍按声明保留，若其中自身包含 URL 或敏感内容，不保证整体清洗；分享结果前应核对这些原声明。

上述匹配只是字符串声明，空白或假哈希同样可能非空。`registry_integrity_declared` **不是**来源真实性、SRI/哈希、包已安装或安全结论；`not_established` 也不是已发现风险。输出固定 `assessment` 和 `integrity_verification` 为 `not_performed`。

## 输出与失败

结果包含实际所读字节的 `input.sha256`/`bytes`、锁格式版本、逐位置包声明、排除清单及计数。`summary.package_entries = included + excluded`，字面模式匹配数与未建立数合计为 included。成功退出码 0 只表示完成了这一声明盘点；空表不能当项目没有依赖或安全。

输入上限 16 MiB、深度 64（根为 0，含叶值）、节点 200000（含根及值，不含键），数值字面量最多 128 字符；输出上限 16 MiB。拒绝 BOM、非法 UTF-8/Unicode、重复键、非有限数、相关字段类型错误、非对象 entry、不支持格式、链接/特殊文件和超限输入。版本缺失/null/空串按排除处理；其它非字符串版本拒绝。相关 name 缺失/null/空串才推名；其它非字符串 name 拒绝。dev/link 存在须布尔，resolved/integrity 缺失/null视空，否则须字符串；不解释未知元数据。

失败时 stdout 不输出部分清单，stderr 返回中文结构化 JSON 并退出 2。格式不支持或未读不被压成成功的零计数。输入的声明没有被 npm 引擎解析、安装或联网核验；输入身份也不保证文件随后未发生变化。

## 交付核对

核对原文件与收据身份，检查传递包、开发依赖、同名多位置及排除项是否满足当前调查目的。实际读取 JSON 结果逐项消费后，才能记录清单已生成；需要比较两个版本时可分别盘点后按位置核对，不将此称为上游提供的 diff 算法。

本法器不构建完整依赖解析图、解析真实链接或验证包名注册，不检查漏洞、维护者、许可证或安装时行为，不替代照影镜的安全审查或项目实际安装/构建验证。
