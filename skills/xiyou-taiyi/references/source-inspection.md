# 固定提交的只读取源

当太乙需要重复读取 GitHub 原源、将多个明确文件绑定到同一版本时，可使用标准库辅助。普通一次性阅读仍可沿用现有 GitHub 工具，不强制多走一步。

```sh
python3 scripts/inspect_source.py --repo openai/skills \
  --path skills/.system/skill-installer/SKILL.md \
  --path skills/.system/skill-installer/LICENSE.txt
```

在太乙技能目录运行；也可使用脚本绝对路径。`--path` 是实际文件路径，多个文件重复参数；不接受目录或自动补 `SKILL.md`。`--ref` 可指定分支、标签或完整提交；省略时读取仓库默认分支。带 `/` 的分支用 `--ref` 明确指定，避免从 URL 猜分支边界。

辅助先解析完整提交，再读取所有指定文件，避免分支移动造成混版。成功时 stdout 返回一个 JSON：`repository`、`repository_id`、`requested_ref`、`resolved_ref`、`commit` 和 `files`。每个文件包含 `path`、`blob_sha`、`sha256`、`bytes`、`content`、`source_url`，核对 API 字节大小及 Git blob SHA。输入路径顺序保留；不添加采集排名或采用结论。

仅支持 GitHub API 和 UTF-8 文本：最多 16 个文件、每文件 512 KiB、每次 API 响应 2 MiB；连接/读取等待超时设为 10 秒，不是整次采集的墙钟总限时。目录、明确符号链接/子模块对象、内容缺失、非法编码、大小或哈希不符均失败；任一文件失败时不向 stdout 输出部分结果，stderr 报错并非零退出。网络失败或限额不是“没有资料”，不会自动换来源、降级或静默截断。

只进行 GET，不安装、不解压、不调用 shell、不执行返回内容、不跟随 API 重定向，也不访问响应中的 `download_url`。可使用现有 `GITHUB_TOKEN` 或 `GH_TOKEN` 环境变量访问有权限的仓库；不会主动取得凭据、输出错误正文或打印令牌。脚本不隐式写文件，调用方若重定向 stdout，应按用户指定的项目外位置保存；包含原始正文的临时结果按任务规则清理。

明确指定需要的许可文件、引用和脚本后分别阅读；辅助不会猜测许可路径、递归收集依赖或判定许可是否足以采用。固定来源与哈希只便于复核，不证明作者、成熟度、内容可信或技能收益。独立验收与采用判断沿用原流程。来源与适配取舍见 [上游致谢](lineage.md)。
