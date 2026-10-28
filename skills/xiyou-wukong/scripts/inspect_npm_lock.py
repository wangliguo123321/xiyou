#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-SA-4.0
"""离线盘点 npm 锁定树声明，不作供应链安全或完整性验证。

改编自 Trail of Bits / Eric Quintero 的 supply-chain-risk-auditor，
collect.py::_npm_all_locked，固定版本 bf23bfb21f10a2a4b0406086d690dc8cb1b3ccf3：
https://github.com/trailofbits/skills/blob/bf23bfb21f10a2a4b0406086d690dc8cb1b3ccf3/
plugins/supply-chain-risk-auditor/skills/supply-chain-risk-auditor/scripts/collect.py
本地改动：显式单文件、版本门、原位置与排除项、有界读取、身份和有限声明输出。
完整 CC-BY-SA-4.0 见 ../licenses/npm-lock-inventory.txt；未执行原采集程序。
"""

import argparse
import hashlib
import json
import math
import os
import stat
import sys


MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 200000
MAX_NUMBER_CHARS = 128
REGISTRY_PREFIX = "https://registry.npmjs.org/"


class InventoryError(ValueError):
    """只携带可公开的固定错误说明，不包含输入内容。"""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise InventoryError("命令参数不合法；请使用 --help 查看用法。")


def read_input(path):
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
        raise InventoryError("当前系统不支持所需的普通文件读取保护。")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise InventoryError("输入必须是普通文件，不能是目录、链接或特殊文件。")
        if info.st_size > MAX_INPUT_BYTES:
            raise InventoryError("输入超过 16 MiB 字节上限。")
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise InventoryError("输入超过 16 MiB 字节上限。")
    if data.startswith(b"\xef\xbb\xbf"):
        raise InventoryError("输入必须是不带 BOM 的 UTF-8 JSON。")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("JSON 含重复对象键，无法盘点。")
        result[key] = value
    return result


def number(token, converter):
    if len(token) > MAX_NUMBER_CHARS:
        raise InventoryError("JSON 数字字面量超过 128 字符上限。")
    value = converter(token)
    if isinstance(value, float) and not math.isfinite(value):
        raise InventoryError("JSON 含非有限数值。")
    return value


def reject_constant(token):
    raise InventoryError("JSON 含非有限数值。")


def decode_input(data):
    value = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_int=lambda token: number(token, int),
        parse_float=lambda token: number(token, float),
        parse_constant=reject_constant,
    )
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            raise InventoryError("JSON 超过深度 64 或节点数 200000 上限。")
        if isinstance(item, dict):
            for key in item:
                key.encode("utf-8")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            item.encode("utf-8")
    return value


def optional_text(entry, field):
    value = entry.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InventoryError("相关包的文本声明字段类型不合法。")
    return value


def inspect_lock(value, data):
    if not isinstance(value, dict):
        raise InventoryError("锁文件根值必须是 JSON 对象。")
    version = value.get("lockfileVersion")
    if type(version) is not int or version not in (2, 3):
        raise InventoryError("仅支持 lockfileVersion 为整数 2 或 3 的锁文件；未读取完整锁定树。")
    entries = value.get("packages")
    if not isinstance(entries, dict):
        raise InventoryError("锁文件缺少对象形式的 packages；未读取完整锁定树。")

    packages = []
    excluded = []
    declared_count = 0
    for position, entry in sorted(entries.items()):
        if not isinstance(entry, dict):
            raise InventoryError("packages 的每个成员都必须是 JSON 对象。")
        if "node_modules/" not in position:
            reason = "project_entry" if position == "" else "outside_node_modules"
            excluded.append({"position": position, "reason": reason})
            continue
        if "link" in entry and type(entry["link"]) is not bool:
            raise InventoryError("相关包的 link 声明必须是布尔值。")
        if entry.get("link", False):
            excluded.append({"position": position, "reason": "link_entry"})
            continue
        package_version = entry.get("version")
        if package_version is None or package_version == "":
            excluded.append({"position": position, "reason": "missing_version"})
            continue
        if not isinstance(package_version, str):
            raise InventoryError("相关包的 version 声明必须是字符串。")
        name = optional_text(entry, "name") or position.rsplit("node_modules/", 1)[1]
        if not name:
            raise InventoryError("无法从相关包的声明或位置取得非空名称。")
        dev = entry.get("dev", False)
        if type(dev) is not bool:
            raise InventoryError("相关包的 dev 声明必须是布尔值。")
        resolved = optional_text(entry, "resolved")
        integrity = optional_text(entry, "integrity")
        reasons = []
        if not resolved.startswith(REGISTRY_PREFIX):
            reasons.append("non_public_registry_declaration")
        if not integrity:
            reasons.append("missing_integrity")
        declaration = "not_established" if reasons else "registry_integrity_declared"
        declared_count += not reasons
        packages.append(
            {
                "position": position,
                "ecosystem": "npm",
                "name": name,
                "version": package_version,
                "dev": dev,
                "source_declaration": declaration,
                "reasons": reasons,
            }
        )
    return {
        "input": {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
        "lockfile_version": version,
        "packages": packages,
        "excluded_entries": excluded,
        "summary": {
            "package_entries": len(entries),
            "included": len(packages),
            "excluded": len(excluded),
            "registry_integrity_declared": declared_count,
            "not_established": len(packages) - declared_count,
        },
        "assessment": "not_performed",
        "integrity_verification": "not_performed",
    }


def report_error(message):
    payload = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        sys.stderr.buffer.write(payload)
        sys.stderr.buffer.flush()
    except OSError:
        pass
    return 2


def main():
    parser = ArgumentParser(description="只读 npm v2/v3 锁定树声明；不作安全或完整性验证。")
    parser.add_argument("--input", required=True, help="明确已有的 package-lock.json 或 npm-shrinkwrap.json 文件")
    try:
        args = parser.parse_args()
        data = read_input(args.input)
        result = inspect_lock(decode_input(data), data)
        output = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(output) > MAX_OUTPUT_BYTES:
            raise InventoryError("结果超过 16 MiB 字节上限，未输出部分清单。")
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except InventoryError as error:
        return report_error(str(error))
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError):
        return report_error("输入不是可读取的 UTF-8、Unicode 标量有效且资源有界的标准 JSON。")
    except OSError:
        return report_error("无法读取指定普通文件或写入输出。")


if __name__ == "__main__":
    sys.exit(main())
