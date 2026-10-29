# 载荷字段一致性核对

用户已有 JSON 对象，明确只需核对其中 `canonical_bytes` 与 `output_hash` 两字段时使用。源为固定版本 Zambo AER-1 verifier 的部分规则；原文自己也不把字段关系当执行、正确性或授权证明。固定来源与完整 MIT 见[上游致谢](lineage.md#载荷字段一致性核对)。

```sh
python3 scripts/inspect_payload_commitment.py --input /明确已有/payload-object.json
```

需要 Python 3.9+ 标准库及 `O_NOFOLLOW` 支持（macOS/Linux）。只读显式普通文件，不联网、执行命令、跟随载荷内路径或生成/修改回执。结果不回显原 base64、解码文本或其它 metadata，不保存解码载荷；摘要和长度不是来源或匿名化保证。

## 检查范围

根为对象，顶层须有上述两个字符串字段；缺字段或类型不支持，表示本部分尚不能检查，**不是**对完整收据有效性的判定。其它 metadata 不解释，只受 JSON 编码和资源支持界限约束；不自动解包对象、猜字段或相信输入中的 `verification_status` 等自报状态。

1. base64 必须为 ASCII 标准字母表、合法尾部 padding，无任何空白；按 Python 标准库严格解码后再次标准编码，必须逐字等原字符串。非零 pad bits 等不同拼写即使解出相同字节、摘要也相同，仍不匹配。空字符串允许为空载荷。
2. 解码原字节须是严格 UTF-8。字段名不授权把载荷当 JSON 解析或 JCS 重序列化；不 trim、改换行、替换字符或做 Unicode 归一化。
3. `output_hash` 格式为精确 `sha256:` 加64个小写 ASCII hex，不去空白或转小写。摘要比较针对原解码字节。

若 base64 无法解码，解码大小、UTF8及摘要观察为未测 null。若可解但拼写非规范，仍可观察字节大小、UTF8和摘要，整体不匹配。UTF8失败后不计算观察摘要或继续摘要比较，保 null；hash格式错误时不做摘要相等比较。未测不当作 false 或通过。

## 输出与退出

stdout JSON 包含实际所读文件 SHA256/字节数、固定 scope、分项 bool/null、解码字节数和可取得的观察摘要、问题标签及 `payload_status`。原输入与载荷摘要是不同层次，分别保留。

- 退出0：`matched`，仅四项载荷字段检查均成立。
- 退出1：`mismatched`，已检查的内容、编码或摘要条件不满足，结构化结果仍可消费。
- 退出2：参数、文件、外层 JSON、字段材料或资源不支持，stderr 中文 JSON，stdout 不输出部分结果。`--help` 为普通用法、退出0。

输入最多2 MiB、深度32（根0，含叶）、节点100000（含值不含键）、数值字面量128字符；base64字段最多1398104字符、解码最多1 MiB。拒绝外层 BOM、非法 UTF8/Unicode标量、重复键、非有限数、链接/特殊文件与超限。载荷本身的合法 UTF8 BOM、NUL或换行不被擅自删除；其摘要仍按原字节。

`full_receipt_validation` 与 `execution_verification` 固定 `not_performed`。本法器没有检查其它核心/schema版本、时间、id、provenance、chain/Merkle/anchor、签名、来源信任、权限或输出含义，不能叫完整 CONFORMANT、已签名、命令真实执行或结果正确。用户需要这些结论时，继续核对应原物与适用授权，不能用本次字段匹配代替。

交付前实际消费结果，保留不匹配与未测事实；不要修写输入以让它通过，也不要把源规范向量、自评计数或草案名称当作真实任务通过证据。
