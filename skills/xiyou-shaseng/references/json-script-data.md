# HTML 非执行 JSON 数据块

用于把已有 JSON 文件交付为正常 HTML 中的一个非执行数据块。只处理明确的 `script[type="application/json"]` 原始文本上下文；不用于 HTML 属性、可执行 JavaScript 字符串、URL 或任意 HTML 清洗。宿主已有同等安全序列化路径时优先复用。

## 编码与消费

1. 确认实际 JSON 输入、数据块 ID 与宿主消费方式；不从数据字段推定 HTML 属性，也不补造业务、作者或日期字段。
2. 先用真实 JSON parser 解码，再由标准 JSON encoder 编码，转义数据正文**所有 literal `<`** 为 `\u003c`。不能用 HTML 实体转义正文，也不能只替换 `</`；数据里的混合大小写关闭标签、注释和 `<script` 同样要保持为数据。
3. 输出一个固定 `type="application/json"` 的片段。它不包含可执行 JavaScript，不执行/读取 JSON 字符串中的程序、路径或 URL。原输入保留，已有输出不覆盖。
4. 在真实浏览器的受控宿主消费：检查预期 ID/type、只有一个数据 script、宿主前后节点仍存在、没有数据突破形成的新节点或执行；然后读取 `textContent` 并 `JSON.parse`，按实际预期核每个键、类型和字段值。只用普通 JSON parser 往返不足以证明 HTML tokenizer 行为。
5. 分别记录“片段已生成”“浏览器消费已核”“业务字段/整页未覆盖”。没有浏览器链就说明仅生成、尚未消费验收，不自动安装。收据固定 `browser_review=not_performed`，不能凭退出成功改成全页面合格。

## 接口

Python 3.9+ 标准库，无产品运行时浏览器依赖。路径相对本技能目录：

```bash
python3 scripts/embed_json_data.py --input /path/to/data.json --output /path/to/new-data-block.html --id xiyou-data
```

`--id` 默认 `xiyou-data`，只接受 ASCII 字母开头、其余字母/数字/`_`/`-`，总长 1–64。type 固定，无任意 HTML 属性或可执行类型选项。多数据块的宿主 ID 约定及其他页面代码需另核。

输入为无 BOM 的 UTF-8 JSON 普通文件；对象、数组、字符串、布尔、null 和常规有限数字可用。拒绝符号链接/特殊文件、重复键、无效 UTF-8/Unicode 标量及非 JSON 常量。整数限 JavaScript 安全范围 ±`(2**53-1)`，超限会拒绝，不自动改类型。浮点按标准 JSON 常规数值语义处理，不承诺任意精度、原数字字面、空白或序列化格式不变；跨语言解释由消费者核对。

单输入至多 1MiB、根深度 0 且成员/数组元素边加 1（含叶）至多 32、值节点含根至多 50000（不含键），输出至多 8MiB。资源限额不是业务字段或安全评分。

输出父目录需存在，目标是新文件路径。完整临时写入后独占发布，已有文件/目录/符号链接不覆盖，写入/验证失败不发布部分正文；清理本次临时文件。成功 stdout 给 input/output 的实际 SHA256 与 bytes、固定 type、id 和浏览器未审标记；失败为 stderr 中文结构化 error、非零退出，不吐完整数据值。

消费者的基本读法：

```javascript
const value = JSON.parse(document.getElementById('xiyou-data').textContent);
```

这不是翻译、Schema.org/JSON-LD 语义或 SEO 通过结论；也不证明宿主其他脚本、样式、策略或整页安全。只把本工具的受限片段作为明确的数据节点集成，仍要核真实消费环境。

## 来源与取舍

[AgriciDaniel/claude-blog 正式 blog-schema Skill](https://github.com/AgriciDaniel/claude-blog/blob/354442348815a7f0327077ad89af2c43cf4b4ab4/skills/blog-schema/SKILL.md) Step 9 及同版 `scripts/blog_render.py:_build_json_ld`、`tests/test_blog_delivery_contract.py:test_xss_via_jsonld_is_escaped` 支持 JSON 编码后脚本上下文转义与值往返方法。Copyright (c) 2025-2026 AgriciDaniel，完整 [MIT](../licenses/blog-schema.txt) 随附。

原函数只转义 `</`，正式 Skill 要求全部 literal `<`；本适配遵从后者，不能把原实现等同完整保证。源用途是 JSON-LD，本地新写工具扩为固定普通 JSON 数据块，并增加 ID/类型/数值/资源边界、实读身份及独占输出；不是源渲染器移植。原源及其测试未执行，未采用其他编辑、研究、FLOW、博客/PDF 或 Google 当前事实流程。
