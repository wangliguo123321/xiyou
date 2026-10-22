#!/usr/bin/env python3
"""校验并汇总太乙配对评测数据；不执行评测或判断技能优劣。

2026-10-22 独立适配 Anthropic skill-creator 数据契约与统计思想。
固定来源和 Apache-2.0 许可见 ../references/lineage.md 与 ../NOTICE.txt。
"""

import json
import math
import statistics
import sys

VARIANTS = ("baseline", "candidate")
METRICS = ("duration_ms", "total_tokens")


def _object(value, required, optional, path):
    if type(value) is not dict:
        raise ValueError(f"{path} 必须是对象")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f"{path} 字段不符：缺少 {sorted(missing)}，多余 {sorted(extra)}")
    return value


def _text(value, path):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{path} 必须是非空字符串")
    return value


def _number(value, path):
    if value is None:
        return None
    try:
        valid = type(value) in (int, float) and value >= 0 and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{path} 必须是非负有限数字或 null，不能使用布尔值")
    return value


def _stats(values, unknown=None):
    try:
        mean = statistics.mean(values) if values else None
        stddev = statistics.stdev(values) if len(values) > 1 else None
        if any(v is not None and not math.isfinite(v) for v in (mean, stddev)):
            raise ValueError("统计结果超出有限数值范围")
    except OverflowError as exc:
        raise ValueError("统计结果超出有限数值范围") from exc
    result = {"n": len(values), "mean": mean, "stddev": stddev}
    if unknown is not None:
        result["unknown"] = unknown
    return result


def summarize(payload):
    """返回 JSON 可序列化报告；非法输入抛出 ValueError，不修改输入。"""
    _object(payload, ("versions", "runs"), (), "输入")
    versions = _object(payload["versions"], VARIANTS, (), "versions")
    for variant in VARIANTS:
        _text(versions[variant], f"versions.{variant}")
    if versions["baseline"] == versions["candidate"]:
        raise ValueError("baseline 与 candidate 的版本标识必须不同")
    if type(payload["runs"]) is not list or not payload["runs"]:
        raise ValueError("runs 必须是非空数组")

    groups = {}
    for index, raw in enumerate(payload["runs"]):
        path = f"runs[{index}]"
        _object(raw, ("case_id", "run_id", "variant", "expectations"), ("timing",), path)
        case_id = _text(raw["case_id"], f"{path}.case_id")
        run_id = _text(raw["run_id"], f"{path}.run_id")
        variant = _text(raw["variant"], f"{path}.variant")
        if variant not in VARIANTS:
            raise ValueError(f"{path}.variant 必须是 baseline 或 candidate")
        pair = groups.setdefault((case_id, run_id), {})
        if variant in pair:
            raise ValueError(f"{path} 重复身份：{case_id!r}/{run_id!r}/{variant}")
        expectations = raw["expectations"]
        if type(expectations) is not list or not expectations:
            raise ValueError(f"{path}.expectations 必须是非空数组")
        by_text = {}
        for position, item in enumerate(expectations):
            location = f"{path}.expectations[{position}]"
            _object(item, ("text", "passed", "evidence"), (), location)
            text = _text(item["text"], f"{location}.text")
            _text(item["evidence"], f"{location}.evidence")
            if type(item["passed"]) is not bool:
                raise ValueError(f"{location}.passed 必须是布尔值")
            if text in by_text:
                raise ValueError(f"{location}.text 重复：{text!r}")
            by_text[text] = dict(item)
        raw_timing = raw.get("timing")
        timing = _object({} if raw_timing is None else raw_timing, (), METRICS, f"{path}.timing")
        timing = {key: _number(timing.get(key), f"{path}.timing.{key}") for key in METRICS}
        passed = sum(item["passed"] for item in expectations)
        pair[variant] = {
            "case_id": case_id, "run_id": run_id, "variant": variant,
            "version": versions[variant],
            "expectations": [by_text[text] for text in sorted(by_text)],
            "passed": passed, "total": len(expectations),
            "pass_rate": passed / len(expectations), "timing": timing,
        }

    runs, pairs = [], []
    for (case_id, run_id), pair in sorted(groups.items()):
        if set(pair) != set(VARIANTS):
            raise ValueError(f"{case_id!r}/{run_id!r} 缺少 baseline 或 candidate 配对")
        baseline, candidate = (pair[key] for key in VARIANTS)
        if [e["text"] for e in baseline["expectations"]] != [e["text"] for e in candidate["expectations"]]:
            raise ValueError(f"{case_id!r}/{run_id!r} 的双版本断言 text 集合不一致")
        delta = {"pass_rate": candidate["pass_rate"] - baseline["pass_rate"]}
        for key in METRICS:
            before, after = baseline["timing"][key], candidate["timing"][key]
            delta[key] = after - before if before is not None and after is not None else None
        pairs.append({"case_id": case_id, "run_id": run_id, "delta": delta})
        runs.extend((baseline, candidate))

    summary = {}
    for variant in VARIANTS:
        selected = [run for run in runs if run["variant"] == variant]
        summary[variant] = {"pass_rate": _stats([run["pass_rate"] for run in selected])}
        for key in METRICS:
            known = [run["timing"][key] for run in selected if run["timing"][key] is not None]
            summary[variant][key] = _stats(known, len(selected) - len(known))
    delta = {"direction": "candidate-baseline"}
    delta["pass_rate"] = _stats([pair["delta"]["pass_rate"] for pair in pairs])
    for key in METRICS:
        known = [pair["delta"][key] for pair in pairs if pair["delta"][key] is not None]
        delta[key] = _stats(known, len(pairs) - len(known))
    return {"versions": dict(versions), "pair_count": len(pairs), "runs": runs,
            "pairs": pairs, "summary": summary, "delta": delta}


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"JSON 字段重复：{key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"JSON 不允许非标准数字：{value}")


def main():
    try:
        if len(sys.argv) != 1:
            raise ValueError("不接受命令行参数；请从 stdin 输入一个 JSON 对象")
        payload = json.load(sys.stdin, object_pairs_hook=_unique_object,
                            parse_constant=_reject_constant)
        output = json.dumps(summarize(payload), ensure_ascii=False, allow_nan=False, indent=2)
        print(output)
    except (ValueError, TypeError, OSError, UnicodeError, RecursionError) as exc:
        print(f"评测结果无效：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
