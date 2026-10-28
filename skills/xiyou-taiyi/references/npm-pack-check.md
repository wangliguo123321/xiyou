# npm 打包计划清单核对

已有单包 `npm pack` JSON 清单，需要重复核对必需路径和缓存名模式时使用。项目已有等价检查则复用；普通技能发现和自产 ZIP 打包不强制使用本法器。来源、修改及完整 MIT/品牌 NOTICE 见 [上游致谢](lineage.md#npm-打包计划清单核对)；本法器与 YottaMeta 官方无关联。

```sh
python3 scripts/inspect_npm_pack.py --input /明确已有/npm-pack.json --require SKILL.md --require NOTICE.txt
```

需要 Python 3.9+ 标准库及支持 `O_NOFOLLOW` 的系统（macOS/Linux）。只读显式普通文件，不运行 npm、不探目录、不回退生成名单，不跟清单中的路径/URL、不读取最终 tgz/ZIP、不安装或发布。结果输出 stdout JSON；保存时由调用方选择项目外位置。清单来源及其采集命令由调用方另核。

## 输入与检查

输入必须是只有一个对象的数组，对象的 `files` 为数组，每项均有字符串 `path`。其它 metadata 不解释或投影，不声称核验完整 npm schema。空 `files` 可读取但指定必需项将缺失；空根数组、多包、对象根、缺字段、坏类型和重复文件路径均明确失败，不合并多包或默认为零。

文件名和 `--require` 均按包根的原字面相对 POSIX 路径比较，大小写和 Unicode 不归一化。不接受前导 `/`、反斜杠、空段、`.`/`..` 段、ASCII 控制字符；每路径 1–4096 字符。至少一个 `--require`，最多 256 个原参数；重复请求去重。不要自动去掉 `package/` 或 `./` 前缀来制造匹配。

- `file_paths` 排序保留全部已声明路径，先不排除任何条目。
- `missing_required_paths` 是明确请求路径与文件名表的字面差集。
- `cache_path_matches` 保每个匹配路径及模式：文件末名以 `.pyc` 结尾为 `pyc_suffix`，任一完整路径段等于 `__pycache__` 为 `pycache_component`。例如 `__pycache__-guide.md` 不因子串被当作缓存目录。只看名称，不检测内容、其它字节码、秘密或可执行风险。

结果包含实际输入原字节 SHA256/字节数、单包范围、完整声明与请求/缺失/匹配清单和计数。保留原文件/请求名称，可能含调用方自己的敏感命名；不读取文件内容，不自动上报，也不宣称全结果脱敏。

## 状态与边界

- 退出 0：`declared_checks_satisfied`，仅表示本清单满足所选名称条件。
- 退出 1：`issues_found`，已完成检查但有缺件或缓存名匹配；结构化结果仍在 stdout。
- 退出 2：输入、参数、文件、编码、结构或资源不支持；stderr 中文 JSON，stdout 不输出部分结果。

输入上限 2 MiB、深度 32（根为0，含叶值）、节点 100000（含值不含键）、数值字面量128字符、文件项10000、输出2 MiB。拒绝 BOM、非法 UTF-8/Unicode、重复键、非有限数，以及链接/特殊文件和超限。`--help` 为普通用法、退出0。

`artifact_validation` 固定为 `not_performed`，`producer_authenticity` 固定为 `not_verified`。输入可以是计划或调用方提供的声明；条件满足不证明最终归档与它相同、文件有效、许可证齐备、无秘密或可安全发布。工作区存在的 NOTICE/CHANGELOG 是否漏入包不能由本清单单独推断；当前任务要求它们时显式加入 `--require`。

交付时实际消费结果、核对原输入身份和每项观察；沙僧可整理为检查证据。需要生成新技能 ZIP 时仍使用[本地技能打包](skill-package.md)，两种操作和格式分别处理。
