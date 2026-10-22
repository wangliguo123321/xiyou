# 配对评测结果与确定性汇总

本地候选适配 Anthropic skill-creator 的 `expectations`、运行身份和多次统计思路，固定来源及许可见 [上游致谢](lineage.md)。仅在任务已有客观可核查断言、需要可复算数字汇总时使用；主观匿名成对评审无须制造断言或改用本契约。汇总不能替代 [独立成对裁决](skill-creator.md)。

## 输入契约

输入一个 JSON 对象，仅允许以下字段：

```json
{
  "versions": {"baseline": "内容快照甲", "candidate": "内容快照乙"},
  "runs": [
    {
      "case_id": "case-1", "run_id": "run-1", "variant": "baseline",
      "expectations": [{"text": "产物包含可核查来源", "passed": false, "evidence": "检查产物未发现来源"}],
      "timing": {"duration_ms": 1000, "total_tokens": null}
    },
    {
      "case_id": "case-1", "run_id": "run-1", "variant": "candidate",
      "expectations": [{"text": "产物包含可核查来源", "passed": true, "evidence": "产物第 3 段列出固定来源"}],
      "timing": {"duration_ms": 1200}
    }
  ]
}
```

- `versions` 两项必须是不同的非空字符串；提交、哈希或快照身份应由调用方绑定真实源内容。脚本只能检查格式及字符串不同，不能证明内容相异。
- `runs`、每次 `expectations` 都是非空数组；`case_id`、`run_id` 是非空字符串。身份由 `(case_id, run_id, variant)` 唯一确定。每个 `(case_id, run_id)` 必须有且仅有 baseline、candidate 各一次；不能靠输入顺序配对。
- 每次断言的 `text` 唯一且非空；同一配对的两侧 `text` 集合必须完全相同，顺序可不同。`passed` 严格使用 JSON 布尔值；`evidence` 为非空字符串，可写证据文本或已有定位信息。脚本不读取其中的路径、不执行内容，也不验证证据真伪或判定是否正确。
- `timing` 可省略或整体为 `null`，均代表两项成本未知；对象内的 `duration_ms`、`total_tokens` 也可省略或为 `null`。其余字段必填。数值须非负且有限，拒绝布尔值、NaN、Infinity、负数及无法以有限浮点数表示的数值。统计结果无法以有限数值表示时明确失败。
- 对象不接受额外字段；CLI 拒绝任意层级 JSON 重复字段、非标准数值及多个 JSON 文档。非法数据整批失败，不跳过记录。

版本身份、案例和断言应在执行前冻结；分别保存原始产物供独立评审核查。报告保留输入的版本、运行身份、断言与证据，按案例、运行、版本及断言排序，便于复核。不同案例断言数量不同，也逐次计算通过率，不把全部断言混成一个总分。

## 调用与输出

在技能目录调用，显式输入通过 stdin 提供；是否保存结果、保存到哪里由调用方决定，业务项目的临时结果按项目约定清理：

```sh
python3 scripts/summarize_evaluation.py < /显式输入位置/results.json
```

也可导入公开纯函数 `summarize(payload)`；不修改输入，返回可 JSON 序列化的对象，非法输入抛出 `ValueError`。CLI 只从 stdin 读取一个 JSON，成功时将报告写 stdout；错误写 stderr 并非零退出。脚本仅使用 Python 标准库，无网络、子进程、模型调用、隐式文件写入或证据路径读取。

输出字段：

| 字段 | 含义 |
|---|---|
| `versions`、`pair_count` | 两侧标识与完整配对总数 |
| `runs` | 每次输入身份、版本、断言证据、通过数/总数、`pass_rate` 及可空成本 |
| `pairs` | 每个 case/run 的对应关系及逐项 delta；某侧成本未知则该 delta 为 `null` |
| `summary.baseline/candidate` | 每次 `pass_rate` 的 `n`、均值与样本标准差；每种成本另有 `unknown` |
| `delta` | 固定 `direction=candidate-baseline`；通过率按完整配对、成本仅按两侧均已知的配对汇总 |

`n` 是实际参与统计的样本数，成本 `unknown` 是该侧未知记录数，delta 的 `unknown` 是不能计算该成本差的配对数；因此成本 delta 的 `n` 就是有效配对数量。无已知值时均值和标准差均为 `null`，只有一个样本时标准差为 `null`。至少两次时使用样本标准差，分母为 `n-1`，不预先四舍五入。未知不补零，不根据字符数推断 tokens；均值差与已知配对差可能不同，不混用。

上例两侧通过率分别为 0、1，耗时差为 200 ms，有效耗时配对数为 1；tokens 两侧未知，有效配对数为 0。该例所有有值指标均只有一个样本，样本标准差为 `null`。

## 使用边界与取舍

只校验结构与算术一致性，数据校验通过不能表述为技能通过、一般效果提升或可自动合并。更高通过率和成本差只供复核，硬失败、回归、主观质量及采用决定仍按原有独立匿名成对流程判断；不自动触发改写或优化。

这是 xiyou 的独立小型数据适配，不声明兼容 Anthropic 原 viewer/benchmark 格式。不采用上游目录扫描、缺 grading 跳过、缺指标补零、字符数充当 tokens、按发现顺序决定差值方向、Claude 执行器或自动优化。固定来源证明可追溯性，不能证明本候选有效；候选需另做独立验收。
