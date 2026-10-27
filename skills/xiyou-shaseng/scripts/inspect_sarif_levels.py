#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-SA-4.0
# 改编自 Trail of Bits skills 的 SARIF parser：
# https://github.com/trailofbits/skills/tree/196a9073ab10d35bacf111f945e02c00b2c6883a/plugins/static-analysis/skills/sarif-parsing
# 插件声明作者：Axel Mierczuk、Paweł Płatek；等级方法维护：Dan Guido。
# 2026-10-28 本地修改：仅保留逐 run 的等级解析方法，增加未知保真、
# 有界本地 JSON 输入及原始/归一计数；不采用扫描、去重、改写或门禁功能。
# 完整许可见 ../licenses/sarif-parsing.txt；归属见 ../NOTICE.txt、../references/lineage.md。
"""只读观察显式本地 SARIF 2.1.0 文件，不跟随其中任何引用。

遵循 S93-sarif-level-observer-v1 有限消费合同；不是完整 schema 验证器。
退出 0/2/1 仅表示 complete/partial/error，不表示无漏洞或允许放行。
"""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys

LEVELS = ("error", "warning", "note", "none")
KINDS = ("fail", "pass", "open", "review", "notApplicable", "informational")
RAW_FIELDS = ("kind", "level", "ruleId", "ruleIndex", "rule")
MAX_BYTES = 5 * 1024 * 1024
MAX_RUNS = 64
MAX_RULES = 10000
MAX_RESULTS = 50000
MAX_IDENTIFIER = 1024
MAX_RAW_BYTES = 4096
MAX_DEPTH = 64
MAX_DETAILS = 200


class ObservationError(Exception):
    def __init__(self, code, detail, **location):
        super().__init__(detail)
        self.issue = {"code": code, "detail": detail, **location}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ObservationError("invalid_cli", "仅接受 --input FILE 指定本地普通文件。")


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ObservationError("duplicate_json_key", "JSON 含重复对象键。")
        value[key] = item
    return value


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ObservationError("nonfinite_number", "JSON 数字必须为有限值。")
    return number


def reject_constant(value):
    raise ObservationError("nonfinite_number", "JSON 不接受非有限数常量。")


def check_depth(value):
    pending = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if not isinstance(item, (dict, list)):
            continue
        if depth > MAX_DEPTH:
            raise ObservationError("json_depth_limit", "JSON 容器嵌套超过 64 层。")
        children = item.values() if isinstance(item, dict) else item
        pending.extend((child, depth + 1) for child in children)


def check_identifier(value):
    if isinstance(value, str) and len(value) > MAX_IDENTIFIER:
        raise ObservationError("identifier_limit", "被消费的标识超过 1024 字符。")


def check_raw(value):
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_RAW_BYTES:
        raise ObservationError("raw_field_limit", "选定原始字段的 JSON 超过 4096 字节。")


def is_level(value):
    return isinstance(value, str) and value in LEVELS


def read_document(path, input_info):
    if path == "-" or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", path):
        raise ObservationError("invalid_input", "输入须为显式本地普通文件。")
    input_info["path"] = os.path.abspath(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ObservationError("invalid_input", "输入须为本地普通文件。")
        input_info["bytes"] = metadata.st_size
        if metadata.st_size > MAX_BYTES:
            raise ObservationError("input_bytes_limit", "输入超过 5 MiB。")
        content = stream.read(MAX_BYTES + 1)
    input_info["bytes"] = len(content)
    if len(content) > MAX_BYTES:
        raise ObservationError("input_bytes_limit", "输入超过 5 MiB。")
    input_info["sha256"] = hashlib.sha256(content).hexdigest()
    document = json.loads(content.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=reject_constant, parse_float=finite_number)
    check_depth(document)
    return document


def check_structure(document):
    if not isinstance(document, dict) or document.get("version") != "2.1.0":
        raise ObservationError("invalid_structure", "根须为对象且 version 严格等于 2.1.0。")
    runs = document.get("runs")
    if not isinstance(runs, list):
        raise ObservationError("invalid_structure", "runs 须为数组。")
    if len(runs) > MAX_RUNS:
        raise ObservationError("runs_limit", "run 数量超过 64。")
    results_total = rules_total = 0
    for run_index, run in enumerate(runs):
        if not isinstance(run, dict) or not isinstance(run.get("results"), list):
            raise ObservationError("invalid_structure", "每个 run 须为对象并显式包含 results 数组。",
                                   run_index=run_index)
        results_total += len(run["results"])
        if results_total > MAX_RESULTS:
            raise ObservationError("results_limit", "结果总数超过 50000。")
        for result_index, result in enumerate(run["results"]):
            if not isinstance(result, dict):
                raise ObservationError("invalid_structure", "每个 result 须为对象。",
                                       run_index=run_index, result_index=result_index)
            for key in RAW_FIELDS:
                if key in result:
                    check_raw(result[key])
            check_identifier(result.get("ruleId"))
        tool = run.get("tool")
        driver = tool.get("driver") if isinstance(tool, dict) else None
        if isinstance(driver, dict):
            check_identifier(driver.get("name"))
            rules = driver.get("rules")
            if isinstance(rules, list):
                rules_total += len(rules)
                if rules_total > MAX_RULES:
                    raise ObservationError("rules_limit", "driver 规则总数超过 10000。")
                for rule in rules:
                    if isinstance(rule, dict):
                        if "id" in rule:
                            check_identifier(rule["id"])
                            check_raw(rule["id"])
                        if "defaultConfiguration" in rule:
                            configuration = rule["defaultConfiguration"]
                            if isinstance(configuration, dict):
                                if "level" in configuration:
                                    check_raw(configuration["level"])
                            else:
                                check_raw(configuration)
    return runs, results_total


def issue(code, detail, **location):
    return {"code": code, "detail": detail, **location}


REASONS = {
    "invalid_kind": "kind 不是支持的枚举值。",
    "invalid_level": "显式 level 不是支持的枚举值。",
    "kind_level_conflict": "非 fail kind 与显式非 none 等级冲突。",
    "invalid_selector": "规则选择器类型或范围无法解释。",
    "selector_conflict": "ruleIndex 与 ruleId 指向不同规则。",
    "duplicate_rule_id": "所引用的规则 id 不唯一。",
    "invalid_rule_level": "所选规则等级不是支持的枚举值。",
    "unsupported_selector": "result.rule 选择器不在解释范围。",
    "unsupported_extensions": "已声明不支持的 tool.extensions。",
    "unsupported_overrides": "已声明不支持或无法解释的规则覆盖配置。",
    "malformed_rule_metadata": "driver 规则元数据形状异常。",
    "index_out_of_range_fallback": "越界索引已按唯一精确 ruleId 回退。",
    "uninterpreted_context": "存在未解释的 suppression、baseline 或运行上下文。",
}


def run_metadata(run, run_index, output):
    flags = []
    blocking = []
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    rules = driver.get("rules", []) if isinstance(driver, dict) else None
    if not isinstance(rules, list):
        rules = []
        blocking.append("malformed_rule_metadata")
        output["driver_rule_counts_complete"] = False
    if isinstance(tool, dict) and "extensions" in tool:
        extensions = tool["extensions"]
        if not isinstance(extensions, list) or extensions:
            blocking.append("unsupported_extensions")
    if "invocations" in run:
        flags.extend(("uninterpreted_context", "invocations"))
        invocations = run["invocations"]
        if not isinstance(invocations, list):
            blocking.append("unsupported_overrides")
        else:
            for invocation in invocations:
                if not isinstance(invocation, dict):
                    blocking.append("unsupported_overrides")
                    break
                if "ruleConfigurationOverrides" in invocation:
                    overrides = invocation["ruleConfigurationOverrides"]
                    if not isinstance(overrides, list) or overrides:
                        blocking.append("unsupported_overrides")
                        break
    id_indexes = {}
    malformed_ids = False
    rule_problems = {}
    for index, rule in enumerate(rules):
        problems = []
        if not isinstance(rule, dict):
            problems.append("malformed_rule_metadata")
            malformed_ids = True
        else:
            identifier = rule.get("id")
            if not isinstance(identifier, str) or not identifier:
                problems.append("malformed_rule_metadata")
                malformed_ids = True
            else:
                id_indexes.setdefault(identifier, []).append(index)
            if "defaultConfiguration" in rule:
                configuration = rule["defaultConfiguration"]
                if not isinstance(configuration, dict):
                    problems.append("malformed_rule_metadata")
                elif "level" in configuration:
                    level = configuration["level"]
                    if is_level(level):
                        output["raw_driver_rule_level_counts"][level] += 1
                    elif level is not None:
                        problems.append("invalid_rule_level")
        if problems:
            rule_problems[index] = problems
            output["driver_rule_counts_complete"] = False
            for code in problems:
                output["issues"].append(issue(code, REASONS[code], run_index=run_index, rule_index=index))
    for code in dict.fromkeys(flags[:1] + blocking):
        output["issues"].append(issue(code, REASONS[code], run_index=run_index))
    return {"rules": rules, "ids": id_indexes, "malformed_ids": malformed_ids,
            "rule_problems": rule_problems, "blocking": list(dict.fromkeys(blocking)),
            "flags": flags, "tool_name": driver.get("name") if isinstance(driver, dict)
            and isinstance(driver.get("name"), str) else None}


def select_rule(result, metadata):
    problems = []
    flags = []
    selected = None
    if "rule" in result:
        problems.append("unsupported_selector")
    identifier = result.get("ruleId")
    id_present = "ruleId" in result
    if id_present and (not isinstance(identifier, str) or not identifier):
        problems.append("invalid_selector")
    index = result.get("ruleIndex")
    # bool 是 int 子类，必须显式排除，null/-1 仅表示无索引。
    no_index = index is None or (type(index) is int and index == -1)
    valid_index = type(index) is int and index >= 0
    if not no_index and not valid_index:
        problems.append("invalid_selector")
    matches = metadata["ids"].get(identifier, []) if isinstance(identifier, str) else []
    if valid_index:
        if index < len(metadata["rules"]):
            selected = index
        elif len(matches) == 1:
            selected = matches[0]
            flags.append("index_out_of_range_fallback")
            if metadata["malformed_ids"]:
                problems.append("malformed_rule_metadata")
        else:
            problems.append("invalid_selector")
    elif no_index and id_present and isinstance(identifier, str) and identifier:
        if len(matches) == 1:
            selected = matches[0]
        if metadata["malformed_ids"]:
            problems.append("malformed_rule_metadata")
    if len(matches) > 1:
        problems.append("duplicate_rule_id")
    resolved_rule = None
    if selected is not None:
        rule = metadata["rules"][selected]
        resolved_rule = {"index": selected, "id": None, "raw_fields": {}}
        if isinstance(rule, dict):
            resolved_rule["id"] = rule.get("id")
            if "id" in rule:
                resolved_rule["raw_fields"]["id"] = rule["id"]
            selected_id = rule.get("id")
            if isinstance(selected_id, str) and len(metadata["ids"].get(selected_id, [])) > 1:
                problems.append("duplicate_rule_id")
            if id_present and identifier != rule.get("id"):
                problems.append("selector_conflict")
            if "defaultConfiguration" in rule:
                configuration = rule["defaultConfiguration"]
                resolved_rule["raw_fields"]["defaultConfiguration"] = (
                    {"level": configuration["level"]} if isinstance(configuration, dict)
                    and "level" in configuration else {} if isinstance(configuration, dict)
                    else configuration)
            problems.extend(metadata["rule_problems"].get(selected, []))
        else:
            # 保留非法所选条目，不能把它当成未声明 descriptor。
            resolved_rule["raw_rule"] = rule
            check_raw(rule)
            problems.append("malformed_rule_metadata")
    return resolved_rule, list(dict.fromkeys(problems)), flags


def observe_result(result, metadata, run_index, result_index, output):
    raw = {key: result[key] for key in RAW_FIELDS if key in result}
    level = result.get("level")
    if is_level(level):
        output["raw_result_level_counts"][level] += 1
    compatibility = []
    for field in ("kind", "level"):
        if field in result and result[field] is None:
            compatibility.append("result." + field + ":null_as_missing")
    rule, problems, flags = select_rule(result, metadata)
    configuration = rule["raw_fields"].get("defaultConfiguration") if rule else None
    if isinstance(configuration, dict) and "level" in configuration and configuration["level"] is None:
        compatibility.append("rule.defaultConfiguration.level:null_as_missing")
    problems = list(dict.fromkeys(metadata["blocking"] + problems))
    flags = metadata["flags"] + flags
    for field in ("suppressions", "baselineState"):
        if field in result:
            flags.extend(("uninterpreted_context", field))
    kind = result.get("kind")
    kind = "fail" if kind is None else kind
    unknown = []
    effective = None
    source = "unknown"
    if not isinstance(kind, str) or kind not in KINDS:
        unknown.append("invalid_kind")
    if level is not None and not is_level(level):
        unknown.append("invalid_level")
    if not unknown:
        if kind != "fail":
            if level is None or level == "none":
                effective, source = "none", "nonfail_kind"
            else:
                unknown.append("kind_level_conflict")
        elif is_level(level):
            effective, source = level, "result"
        elif problems:
            unknown.extend(problems)
        else:
            configuration = configuration if isinstance(configuration, dict) else {}
            default_level = configuration.get("level")
            if is_level(default_level):
                effective, source = default_level, "rule_default"
            else:
                effective, source = "warning", "sarif_default"
    unknown = list(dict.fromkeys(unknown))
    context = list(dict.fromkeys(flags + problems))
    for code in dict.fromkeys(unknown + problems + [flag for flag in flags if flag in REASONS]):
        output["issues"].append(issue(code, REASONS[code], run_index=run_index, result_index=result_index))
    output["resolved_level_counts"][effective if effective is not None else "unknown"] += 1
    if len(output["details"]) < MAX_DETAILS:
        output["details"].append({"run_index": run_index, "result_index": result_index,
                                  "tool_name": metadata["tool_name"], "raw_fields": raw,
                                  "resolved_rule": rule, "effective_level": effective,
                                  "level_source": source, "unknown_reasons": unknown,
                                  "context_flags": context, "compatibility_notes": compatibility})


def empty_output():
    return {"schema_version": 1, "status": "error",
            "input": {"path": None, "sha256": None, "bytes": None},
            "counts_complete": False, "total_runs": None, "total_results": None,
            "resolved_level_counts": None, "raw_result_level_counts": None,
            "raw_driver_rule_level_counts": None, "driver_rule_counts_complete": False,
            "details": [], "truncated": False, "issues": []}


def main(argv=None):
    output = empty_output()
    try:
        parser = Parser(add_help=False, allow_abbrev=False)
        parser.add_argument("--input", required=True)
        args = parser.parse_args(argv)
        document = read_document(args.input, output["input"])
        runs, result_count = check_structure(document)
        output.update(status="complete", counts_complete=True, total_runs=len(runs),
                      total_results=result_count, driver_rule_counts_complete=True,
                      resolved_level_counts=dict.fromkeys(LEVELS + ("unknown",), 0),
                      raw_result_level_counts=dict.fromkeys(LEVELS, 0),
                      raw_driver_rule_level_counts=dict.fromkeys(LEVELS, 0))
        for run_index, run in enumerate(runs):
            metadata = run_metadata(run, run_index, output)
            for result_index, result in enumerate(run["results"]):
                observe_result(result, metadata, run_index, result_index, output)
        if result_count > MAX_DETAILS:
            output["truncated"] = True
            output["issues"].append(issue("details_truncated", "仅展示输入顺序前 200 条明细，计数包含全部结果。"))
        if output["issues"]:
            output["status"] = "partial"
    except (ObservationError, OSError, ValueError, RecursionError, MemoryError) as error:
        input_info = output["input"]
        output = empty_output()
        output["input"] = input_info
        if isinstance(error, ObservationError):
            output["issues"] = [error.issue]
        elif isinstance(error, OSError):
            output["issues"] = [issue("read_error", "无法读取指定的本地普通文件。")]
        else:
            output["issues"] = [issue("invalid_json", "JSON 解码、数值或资源处理失败。")]
    print(json.dumps(output, ensure_ascii=True, separators=(",", ":"), allow_nan=False))
    return {"complete": 0, "partial": 2, "error": 1}[output["status"]]


if __name__ == "__main__":
    sys.exit(main())
