#!/usr/bin/env python3
"""只读观察已导出的 Terraform show -json 状态资源对象库存。

SPDX-License-Identifier: MPL-2.0
方法来源：Copyright IBM Corp. 2026 / HashiCorp agent-skills，固定版本
f706481af9b8fedb66de909f6243ad29601afa0c，
plugins/terraform/skills/refactor-module/SKILL.md。
2026-10-28 本地新写：有界内容读取、声明对象库存、未知及错误协议。
原 Skill 没有此脚本；未复制或执行 Terraform 实现。见 ../licenses/terraform-refactor.txt。
"""

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata


MAX_INPUT = 5 * 1024 * 1024
MAX_MODULES = 512
MAX_RESOURCES = 2000
MAX_DEPTH = 32
MAX_METADATA = 1024


class InventoryError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InventoryError("invalid_arguments", "参数无效；需要 --input 指定本地 JSON 文件。")


def read_source(name):
    try:
        path = Path(name).expanduser()
        if not stat.S_ISREG(path.lstat().st_mode):
            raise InventoryError("invalid_input", "输入必须是普通文件，不能是符号链接或特殊文件。")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(str(path), flags), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InventoryError("invalid_input", "输入必须是普通文件。")
            data = stream.read(MAX_INPUT + 1)
    except (OSError, ValueError, RuntimeError):
        raise InventoryError("input_read_failed", "无法读取指定普通文件。")
    if len(data) > MAX_INPUT:
        raise InventoryError("input_limit", "输入超过 5 MiB。")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("duplicate_json_key", "JSON 含重复键，不能确认文档结构。")
        result[key] = value
    return result


def reject_constant(value):
    raise InventoryError("non_finite_json", "JSON 含非有限数值。")


def parse_document(data):
    try:
        # 不对资源属性做运算；Decimal 避免未采用的大整数或指数先溢出为浮点值。
        return json.loads(
            data, object_pairs_hook=unique_object, parse_constant=reject_constant,
            parse_int=Decimal, parse_float=Decimal,
        )
    except (ValueError, UnicodeError, InvalidOperation, RecursionError):
        raise InventoryError("invalid_json", "输入不是可解析的有限 JSON 文档。")


def metadata(value):
    if (
        not isinstance(value, str) or not value or len(value) > MAX_METADATA
        or any(unicodedata.category(char) in ("Cc", "Cs") for char in value)
    ):
        raise InventoryError("invalid_metadata", "采用的元数据须为有界、非空且不含控制字符的字符串。")
    return value


def object_field(value):
    if not isinstance(value, dict):
        raise InventoryError("invalid_structure", "采用的对象字段类型不符。")
    return value


def list_field(module, name):
    value = module.get(name, [])
    if not isinstance(value, list):
        raise InventoryError("invalid_structure", "采用的资源或子模块列表类型不符。")
    return value


def inspect_modules(root):
    resources = []
    module_count = 0
    stack = [(root, "", 0)]
    while stack:
        module, address, depth = stack.pop()
        object_field(module)
        module_count += 1
        if module_count > MAX_MODULES or depth > MAX_DEPTH:
            raise InventoryError("module_limit", "模块数量或深度超过本接口上限。")
        entries = list_field(module, "resources")
        if len(resources) + len(entries) > MAX_RESOURCES:
            raise InventoryError("resource_limit", "资源对象条目超过 2000。")
        for entry in entries:
            object_field(entry)
            resource_address = metadata(entry.get("address"))
            mode = metadata(entry.get("mode"))
            resource_type = metadata(entry.get("type"))
            if mode not in ("managed", "data"):
                raise InventoryError("unsupported_mode", "资源 mode 超出本接口支持范围。")
            kind = "current"
            if "deposed_key" in entry:
                metadata(entry["deposed_key"])
                kind = "deposed"
            resources.append({
                "address": resource_address, "mode": mode, "type": resource_type,
                "module_address": address, "object_kind": kind,
            })
        children = list_field(module, "child_modules")
        if module_count + len(stack) + len(children) > MAX_MODULES:
            raise InventoryError("module_limit", "模块数量超过 512。")
        for child in reversed(children):
            object_field(child)
            stack.append((child, metadata(child.get("address")), depth + 1))
    return resources, module_count


def main(argv=None):
    result = {
        "status": "error", "source": None, "format_version": None,
        "resource_count": None, "module_count": None, "resources": [],
        "reason": None, "error": None,
    }
    try:
        parser = Parser(description="只读列出已导出 Terraform 状态的声明资源对象；不输出属性值。")
        parser.add_argument("--input", required=True, help="terraform show -json 已导出的普通本地文件")
        args = parser.parse_args(argv)
        data = read_source(args.input)
        result["source"] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        document = object_field(parse_document(data))
        if any(key in document for key in ("planned_values", "resource_changes", "prior_state")):
            raise InventoryError("unsupported_input", "本接口不接受 Terraform plan 文档。")
        if "format_version" not in document and "version" in document:
            raise InventoryError("unsupported_input", "本接口不接受原始 tfstate 文档。")
        version = metadata(document.get("format_version"))
        if not re.fullmatch(r"1\.[0-9]+", version):
            raise InventoryError("unsupported_format", "仅支持 format_version 为 1.x 的状态 JSON。")
        result["format_version"] = version
        if "values" not in document:
            result.update(status="partial", reason="state_values_not_provided")
        else:
            values = object_field(document["values"])
            if "root_module" not in values:
                result.update(status="partial", reason="root_module_not_provided")
            else:
                resources, modules = inspect_modules(object_field(values["root_module"]))
                result.update(
                    status="complete", resource_count=len(resources), module_count=modules,
                    resources=resources,
                )
    except InventoryError as exc:
        result["error"] = {"code": exc.code, "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return {"complete": 0, "partial": 2, "error": 1}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
