# SQLite 只读取证

用户明确提供一个稳定离线 SQLite 文件，需要查看结构或原生查询计划时使用。辅助不执行原查询，不自动优化、评分、修复或备份，不部署 MCP，也不发现/遍历其它数据库。没有指定文件时先确认输入，不接触用户其它数据库。

```sh
python3 scripts/inspect_sqlite.py --database /path/to/offline.db --schema
python3 scripts/inspect_sqlite.py --database /path/to/offline.db --plan 'SELECT source_row, repository FROM candidates WHERE repository = ?' --params-json '["ofershap/mcp-server-sqlite"]'
```

依赖 Python 3.9+ 标准库和 SQLite 3.37+。`--schema` 与 `--plan SQL` 二选一；只有计划模式接 `--params-json` 数组标量，用原生绑定，不把值拼进 SQL。参数错误可写 stderr 并退出 `2`；`--help` 是普通帮助文本。

## 输入和只读边界

只接受既存普通文件，拒绝叶符号链接、特殊对象、缺失文件，以及任何同名 `-wal`、`-shm`、`-journal`。需要数据库一致离线副本时，由调用者先按原工程权限取得；辅助不自动复制、checkpoint 或移除旁路文件。项目原用 JSON 时，把其内容转换为临时 SQLite 验证输入不等于项目原已有数据库。

连接采用只读不可变模式、`query_only` 与内存临时存储，检查前后文件身份、大小、修改时间、全文件 SHA256 及旁路；检测到变化丢弃结果并报错。它不提供多文件原子快照、不保证抵抗恶意并发替换，也不是全宿主 SQLite 沙箱。只接明确授权的可信离线文件。

结构模式仅返回 main 的 `sqlite_master` 原列 `type/name/tbl_name/sql`，排序并保留空结构的列，不对各表执行 COUNT。计划模式交给 SQLite 原生解析，授权阶段与固定元数据初始化分开，必须出现 SELECT；只允许普通 main 表/视图的只读 SELECT/CTE。所有函数（本轮也不支持普通内置函数）、虚拟/影子/未知表、PRAGMA、事务、附加库和写入等均拒绝。`EXPLAIN` 名称本身不代表安全；结果只是本次引擎计划事实，不是性能或正确性结论。

SQL 最多 16 KiB，输入文件最多 128 MiB，锁等待 250 ms；不宣称 native 函数硬超时或硬进程内存限制。默认最多 128 行、64 KiB 行 payload，可用 `--max-rows`（1–512）和 `--max-output-bytes`（1–256 KiB）调小/调大。按行读取并至多多看一行确认剩余；不先 fetchall 再假称有界。

## 结果

完整有效调用向 stdout 输出一个 JSON 对象，保留 `status/operation/database/sqlite_version/columns/rows/returned_rows/row_payload_bytes/truncated/reason/error`。行 payload 是每行规范 JSON（UTF-8、非 ASCII 不转义、紧凑分隔、拒非标准数字）的字节数之和，不含外层 JSON 或行间逗号；不是整个输出大小。零行 payload 为 0，空结构可正常成功。

| 状态 / 退出码 | 含义 |
|---|---|
| `ok` / `0` | 本次结果完整。 |
| `partial` / `3` | 确有结果因 `max_rows` 或 `max_output_bytes` 未返回；首行超预算也可返回零行部分结果。 |
| `error` / `2` | 输入、运行时、文件、读取变化、SQL/授权或参数等障碍；成功行丢弃。 |

`returned_rows` 不是全结果总数。恰好达到预算且没有剩余时仍为 `ok`，不能仅因达到上限就标截断。调用者需一起消费状态、列、行、截断与原因；SQLite 版本可能影响计划细节，不能跨版本拿字符串变化直接判性能退步。

## 来源与适配

成熟源的核心是显式单库、引擎只读、结构/计划和关闭链。绑定、稳定文件与旁路检查、授权范围、预算、机器协议都是本地适配，详见 [上游取舍](lineage.md) 和 [NOTICE](../NOTICE.txt)。旧 Python 临时组合也能正确完成一次；新入口只提供可重复工程接口，不证明模型通用能力或原源全部行为更好。
