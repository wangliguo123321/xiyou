#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""只读核对单包 npm 文件清单的声明，不验证最终归档或发布安全。

方法参考 YottaMeta/yotta-publish-guard 的清单、必需件和缓存名检查：
https://github.com/YottaMeta/yotta-publish-guard/blob/
d36044d4d7fc48c1f8cfec3f9827639ddcc49e35/scripts/yotta_publish_guard.py
上游版权：Copyright (c) 2026 YottaMeta；完整 MIT 与 NOTICE 见
../licenses/npm-pack-check.txt 和 ../licenses/npm-pack-check-NOTICE.txt。
本地适配为显式 JSON 单包输入、必需路径、目录段模式、有界读取与身份；
不执行原程序、npm、目录回退或发布。本法器与 YottaMeta 官方无关联。
"""

import argparse
from collections import deque
import hashlib
import json
import math
import os
import stat
import sys


MAX_INPUT = 2 * 1024 * 1024
MAX_OUTPUT = 2 * 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 100000
MAX_NUMBER = 128
MAX_FILES = 10000
MAX_REQUIRED = 256
MAX_PATH = 4096


class ManifestError(ValueError):
    """只包含固定说明，不回显输入值。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ManifestError("参数不合法；请使用 --help 查看用法。")


def read_bytes(filename):
    if not all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK")):
        raise ManifestError("当前系统不支持所需的普通文件读取保护。")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(filename, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ManifestError("输入必须是普通文件，不能是链接、目录或特殊文件。")
        if info.st_size > MAX_INPUT:
            raise ManifestError("输入超过 2 MiB 字节上限。")
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ManifestError("输入超过 2 MiB 字节上限。")
    if raw[:3] == b"\xef\xbb\xbf":
        raise ManifestError("输入须为不带 BOM 的 UTF-8 JSON。")
    return raw


def object_without_duplicates(pairs):
    item = dict(pairs)
    if len(item) != len(pairs):
        raise ManifestError("JSON 对象含重复键，未完成核对。")
    return item


def parse_number(text, convert):
    if len(text) > MAX_NUMBER:
        raise ManifestError("JSON 数值字面量超过 128 字符上限。")
    number = convert(text)
    if isinstance(number, float) and not math.isfinite(number):
        raise ManifestError("JSON 不接受非有限数。")
    return number


def reject_constant(text):
    raise ManifestError("JSON 不接受非有限数。")


def decode(raw):
    document = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=object_without_duplicates,
        parse_int=lambda text: parse_number(text, int),
        parse_float=lambda text: parse_number(text, float),
        parse_constant=reject_constant,
    )
    queue = deque([(document, 0)])
    visited = 0
    while queue:
        item, depth = queue.popleft()
        visited += 1
        if visited > MAX_NODES or depth > MAX_DEPTH:
            raise ManifestError("JSON 超过深度 32 或节点数 100000 上限。")
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, dict):
            for key in item:
                key.encode("utf-8")
            queue.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            queue.extend((child, depth + 1) for child in item)
    return document


def checked_path(value):
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_PATH:
        raise ManifestError("路径声明须为 1–4096 字符的相对 POSIX 路径。")
    value.encode("utf-8")
    if value.startswith("/") or "\\" in value:
        raise ManifestError("路径声明不能是绝对路径或含反斜杠。")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ManifestError("路径声明不能含空目录段、点或双点目录段。")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ManifestError("路径声明不能含 ASCII 控制字符。")
    return value


def inspect(document, required, raw):
    if not isinstance(document, list) or len(document) != 1:
        raise ManifestError("仅支持恰好一项的单包 JSON 数组清单。")
    package = document[0]
    if not isinstance(package, dict) or not isinstance(package.get("files"), list):
        raise ManifestError("单包对象须包含数组形式的 files。")
    entries = package["files"]
    if len(entries) > MAX_FILES:
        raise ManifestError("files 超过 10000 项上限。")
    paths = set()
    for entry in entries:
        if not isinstance(entry, dict) or "path" not in entry:
            raise ManifestError("files 每项须为含 path 的对象。")
        path = checked_path(entry["path"])
        if path in paths:
            raise ManifestError("files 含重复路径，未完成核对。")
        paths.add(path)
    files = sorted(paths)
    missing = sorted(set(required) - paths)
    matches = []
    for path in files:
        parts = path.split("/")
        patterns = []
        if parts[-1].endswith(".pyc"):
            patterns.append("pyc_suffix")
        if "__pycache__" in parts:
            patterns.append("pycache_component")
        if patterns:
            matches.append({"path": path, "patterns": patterns})
    has_issues = bool(missing or matches)
    return {
        "input": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        "package_count": 1,
        "file_paths": files,
        "required_paths": required,
        "missing_required_paths": missing,
        "cache_path_matches": matches,
        "summary": {
            "files": len(files),
            "required": len(required),
            "present_required": len(required) - len(missing),
            "missing_required": len(missing),
            "cache_paths": len(matches),
        },
        "status": "issues_found" if has_issues else "declared_checks_satisfied",
        "artifact_validation": "not_performed",
        "producer_authenticity": "not_verified",
    }


def fail(message):
    diagnostic = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        sys.stderr.buffer.write(diagnostic)
        sys.stderr.buffer.flush()
    except OSError:
        pass
    return 2


def main():
    parser = Parser(description="只读单包 npm JSON 名单，核对明确必需路径与缓存名模式。")
    parser.add_argument("--input", required=True, help="明确已有的 npm pack JSON 文件")
    parser.add_argument("--require", dest="required", action="append", required=True,
                        help="相对包根的必需路径，可重复指定；同路径去重")
    try:
        args = parser.parse_args()
        if len(args.required) > MAX_REQUIRED:
            raise ManifestError("--require 原参数数超过 256 项上限。")
        required = sorted({checked_path(path) for path in args.required})
        raw = read_bytes(args.input)
        result = inspect(decode(raw), required, raw)
        output = json.dumps(result, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8") + b"\n"
        if len(output) > MAX_OUTPUT:
            raise ManifestError("结果超过 2 MiB 字节上限，未输出部分清单。")
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 1 if result["status"] == "issues_found" else 0
    except ManifestError as error:
        return fail(str(error))
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError):
        return fail("输入不是 Unicode 标量有效、资源有界的标准 UTF-8 JSON。")
    except OSError:
        return fail("无法读取指定普通文件或写入输出。")


if __name__ == "__main__":
    sys.exit(main())
