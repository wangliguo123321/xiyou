# SARIF 等级观察

> 独立改编材料采用 CC-BY-SA-4.0。归属 Trail of Bits（插件声明作者 Axel Mierczuk、Paweł Płatek，等级继承维护者 Dan Guido）；固定来源与 2026-10-28 本地改动见 [lineage](lineage.md)，完整许可见 [sarif-parsing.txt](../licenses/sarif-parsing.txt)。其他独立组件保留原许可，不声明官方背书。

用户已有 SARIF 2.1.0 文件，需要读取结果等级与规则继承时使用：

```sh
python3 scripts/inspect_sarif_levels.py --input /path/to/report.sarif
```

仅依赖 Python 3.9+ 标准库。工具只读显式文件，不扫描代码、不运行 CodeQL/Semgrep 或来源程序，不读取报告里的 URI/artifact、联网校验 schema、过滤/去重/改写或发布报告。

## 有限等级语义

逐 run 使用自己的 `tool.driver.rules`，不同 run 的同名规则不互相覆盖。kind 缺失/null 兼容为 fail；合法非 fail 且 level 缺失/null/none 归 none，非 fail 与显式非 none 冲突则未知。fail 按显式合法 result.level、当前 run 规则默认等级、支持范围内真正缺省 warning 的次序；null 兼容缺失有注记，未知字符串、空字符串、false 或其他类型不静默缺省。

合法显式等级不会被坏规则覆盖。合法索引或唯一精确 id 可选规则；-1 表示无索引，越界索引只有唯一 id 可回退且保 partial；重复 id、选择器冲突、非法索引类型、未支持 result.rule 不静默降级。坏配置不把已确认 error 改成 warning；需要查找却无法确认唯一元数据时保 unknown。

只处理 driver 规则，extensions/overrides 不解释，依赖它们的缺等级保未知。suppression、baseline 和运行状态不解释并标 partial，但保留已知原始等级。它不是全 SARIF schema 验证器，也不计算“未抑制的新漏洞”或 CI 放行结论。

## 输出与限额

stdout 一个 JSON，`complete/partial/error` 对应退出码 `0/2/1`。**三种退出码都不是安全判定；退出 0 也可能含 error 等级结果。** 调用者要消费归一等级、unknown、未解释上下文与明细，而不是只看退出码。

`resolved_level_counts` 含 error/warning/note/none/unknown 五类，总和对应全输入结果数。`raw_result_level_counts` 只统计显式合法等级，包括冲突中的合法原始 error；`raw_driver_rule_level_counts` 统计规则定义中的显式合法等级，包括未被结果引用的规则，它不是发现数量。不要把三种统计相加或互相替代。

每个结果保 run/result 索引、所选原始字段、规则选择、归一等级及来源/未知原因与上下文。默认只展示前 200 条明细；截断时 partial，统计仍覆盖全输入，不能只统计展示条数。合法空 runs/results 只说明文件未声明结果，不证明扫描执行成功或没有漏洞。

输入上限为 5 MiB、64 runs、共 1 万 driver 规则、5 万 results、直接消费的标识 1024 字符、每个选定原始字段紧凑 UTF-8 JSON 值 4096 字节、嵌套 64。超过配额、根/version/runs/results 结构异常、读取或 JSON 障碍均 error，计数为 null，不伪报零发现。参数错误可写 stderr 并退出非零；输入始终不改。

## 来源与适配

成熟源的具体等级继承修复、公开受控 fixtures 和测试支持这个窄方法。资源/结构边界、未知协议、原始与归一计数及机器退出是本地适配，不冒称来源完整支持所有 SARIF 语义。公开工具教学样例也不等于本机运行过扫描器。旧人工/jq/Python可正确读取一次；新入口的价值须以重复接口及未知保真验证，不以新命令名或一般模型能力判优。
