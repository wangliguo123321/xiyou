# 离线 Playwright 网络记录观察

在调查前，读取用户已有、已解包的 `.network` JSONL 文件，将每条资源快照中声明的方法、URL 有限投影和 HTTP 状态整理成可复核的输入。已有工具能提供同一内容身份、逐行来源、值排除及未知协议时优先复用。

从本技能目录运行：

```bash
python3 scripts/inspect_playwright_network.py --input /path/to/trace.network
```

仅用 Python 3.9+ 标准库，不需要安装或运行 Playwright。输入必须是既存普通 UTF-8 文件，拒绝符号链接和特殊文件；按同一有界字节计算 SHA256/bytes，不改原文件。不解包 ZIP、不运行浏览器或 trace-viewer、不访问 URL、DNS、资源 sha1/_file 路径或云服务，不写回或重放请求。

## 有限记录与字段

仅支持已核字段形态：每个非空 LF 行是一个 `type=resource-snapshot` 对象，其 `snapshot.request` 为对象，`response` 可未提供或为 null。按原物理行顺序返回，不按 URL、request_id 或状态去重。`line` 从 1 起算；`snapshot_count` 是文件中的声明快照条目数，不是唯一请求、完成请求或真实网络总数。

输出每条 `method`、`url`、`response_status` 及固定问题码：

- 方法按非空、有界、无控制字符字符串保原文，不猜 GET、不做完整 HTTP 方法合法性校验。
- URL 仅用标准库拆成 `scheme/hostname/port/path`，只展示可解析的 HTTP(S)；不输出原 URL、userinfo、query、fragment 或 netloc，不百分号解码路径。host/path 仍可能含业务命名，这不是通用脱敏。
- 状态只有整数语义的 100..599 才作为声明值返回；缺失、null、0、-1 或其它整数均保 null/未知。不据状态码判断请求成功、失败、根因或安全。错误类型与非整数不强制转换。

原生 recorder 可在停止或切块时写出 pending 条目，status 初始为 -1；不能把每条记录当成已完成请求。网络文件可能跨 chunk 保留，单独文件也没有可核版本头，不能确认任意输入来自某一 Playwright 版本、真实录制或完整会话。本法器不是完整 HAR、`.trace`、ZIP 或所有 Playwright 版本的验证器。

整体 JSON 解析仍会把字段读入内存，但不采用、输出或上传 headers、cookies、postData、body、content、timings、时钟或资源引用。只输出白名单和常量问题码，错误不带源行或 URL 异常片段。不做时间、阶段、性能或因果分析。

## 完整性与错误

`verification` 始终为 `not_performed`。`complete/partial/error` 对应退出码 0/2/1：

- complete 仅表示全部已声明快照的有限字段可读，无不可用字段。
- method/url/status 缺失或不可安全解释时，partial 仍保全部声明条目与已知数量，问题码顺序为 method_unavailable、url_unavailable、status_unavailable。response 省略/null 只表示状态未知。
- 空文件或仅 ASCII 空白行返回 partial/count0；这只说明输入没有声明条目，不能据此说真实无请求。
- 未支持/缺失记录 type、坏 JSON、重复键、非标准 NaN/Infinity、非法 UTF-8、错误容器或已提供字段非法类型/控制字符、硬界错误均 error/count null/空列表，不交一份貌似完整的半库存。陌生 type 仅是不受本接口支持，不断言其它 trace 记录无效。

文件最大 5 MiB、非空记录最多 2000、每原始行最多 1 MiB（不含 LF，包含 CR）、method 最多 128 UTF-8 字节、URL 最多 8192 字节。只按 LF 切行，字面 U+2028 不当行界；CRLF 尾 CR 可作 JSON 空白，ASCII space/tab/CR 空白行可忽略但仍受行界。超界拒绝，不截断。

## 来源与验证边界

基于 [Microsoft Playwright CLI Skill](https://github.com/microsoft/playwright-cli/blob/b1a5903c5b633b8c9f843ad7b629c2a78437040c/skills/playwright-cli/SKILL.md)及必要 [tracing 引用](https://github.com/microsoft/playwright-cli/blob/b1a5903c5b633b8c9f843ad7b629c2a78437040c/skills/playwright-cli/references/tracing.md)的录制产物调查方法。Copyright (c) Microsoft Corporation.，完整原 [Apache-2.0](../licenses/playwright-cli.txt)随附。

CLI 声明的 exact core 包版本通过 registry 元数据关联到 `microsoft/playwright@e8149b8257d32dcf8f72573ecc43e72439da7080`。必要 writer 只读核到 `.network` 写入资源快照及 pending/status=-1 边界；trace context version10 不是单文件格式版本证明。未复制 core 实现、资源或原测试，不引入其运行依赖或权限。

2026-10-28 本地新写文件读取、有限投影、位置/身份、值排除及未知/错误协议，原 Skill 没有此 helper。不继承 open/attach、profile、依赖安装、录制/查看器或自动旧文件删除。适配实际验证使用按已核源码原义构造的数据，**未取得真实录制 fixture、未运行上游程序**；这只能限定证明本接口行为，不能证明全部 trace 兼容或网络事实。完整归属与取舍见 [上游致谢](lineage.md)。
