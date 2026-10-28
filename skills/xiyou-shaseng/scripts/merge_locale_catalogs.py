#!/usr/bin/env python3
"""将两份有界 JSON 消息树递归合成为新的 UTF-8 资源文件。

仅支持对象和字符串，键按 JSON 字面处理；对象/字符串冲突拒绝是本工具的
窄约束，不代表 Lodash、Polyglot 或其他国际化框架的完整行为。
"""

import argparse
import hashlib
import itertools
import json
import os
import stat
import sys
import tempfile


INPUT_BYTES = 2 * 1024 * 1024
OUTPUT_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32  # 根对象深度为 0，每条成员边加 1，含字符串叶。
MAX_NODES = 50000  # 含根、对象和字符串值，不含键。


class CatalogError(Exception):
    def __init__(self, code, message, scope="command", **details):
        self.error = dict(code=code, message=message, scope=scope, **details)
        super().__init__(message)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CatalogError("arguments", "参数缺失或不受支持，请使用 --help 查看用法。")


def check_nesting(text, scope):
    # 在标准解码器之前限制容器嵌套，避免超深输入耗尽 Python 调用栈。
    quoted = escaped = False
    depth = 0
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
            if depth > MAX_DEPTH + 1:
                raise CatalogError("depth_limit", "消息树深度超过 32。", scope)
        elif char in "}]":
            depth -= 1


def inspect_tree(tree, scope, node_limit=None):
    nodes = strings = 0
    stack = [(tree, 0)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if node_limit is not None and nodes > node_limit:
            raise CatalogError("node_limit", "单份输入的节点超过 50000。", scope)
        if depth > MAX_DEPTH:
            raise CatalogError("depth_limit", "消息树深度超过 32。", scope)
        if isinstance(value, dict):
            for key, child in value.items():
                check_unicode(key, scope)
                stack.append((child, depth + 1))
        elif isinstance(value, str):
            check_unicode(value, scope)
            strings += 1
        else:
            raise CatalogError("unsupported_type", "消息树仅支持对象和字符串值。", scope)
    return dict(nodes=nodes, strings=strings)


def check_unicode(value, scope):
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise CatalogError("invalid_unicode", "键或字符串含无效 Unicode 代理码点。", scope)


def read_catalog(path, scope):
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise CatalogError("input_file", "输入必须是普通文件，不接受符号链接或特殊文件。", scope)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (not stat.S_ISREG(opened.st_mode)
                    or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
                raise CatalogError("input_changed", "输入文件在打开时已变化，请重新执行。", scope)
            raw = source.read(INPUT_BYTES + 1)
    except (OSError, ValueError) as error:
        raise CatalogError("input_file", "无法读取输入普通文件。", scope,
                           errno=getattr(error, "errno", None)) from None
    if len(raw) > INPUT_BYTES:
        raise CatalogError("input_bytes_limit", "单份输入超过 2 MiB。", scope)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise CatalogError("invalid_utf8", "输入不是有效 UTF-8。", scope) from None
    check_nesting(text, scope)

    def pairs_to_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CatalogError("duplicate_key", "JSON 对象含重复键。", scope)
            result[key] = value
        return result

    def reject_number(value):
        raise CatalogError("unsupported_type", "消息树仅支持对象和字符串值，不接受数字。", scope)

    try:
        tree = json.loads(text, object_pairs_hook=pairs_to_object,
                          parse_int=reject_number, parse_float=reject_number,
                          parse_constant=reject_number)
    except json.JSONDecodeError as error:
        raise CatalogError("invalid_json", "输入不是有效 JSON。", scope,
                           line=error.lineno, column=error.colno) from None
    except RecursionError:
        raise CatalogError("depth_limit", "消息树深度超过 32。", scope) from None
    if not isinstance(tree, dict):
        raise CatalogError("root_type", "JSON 根值必须是对象。", scope)
    counts = inspect_tree(tree, scope, MAX_NODES)
    return tree, dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), **counts)


def merge_catalogs(base, override):
    merged = dict(base)
    for key, value in override.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_catalogs(merged[key], value)
        elif isinstance(merged[key], str) and isinstance(value, str):
            merged[key] = value
        else:
            raise CatalogError("shape_conflict", "相同键路径出现对象与字符串的形状冲突。", "merge")
    return merged


def publish_catalog(tree, output):
    parent, name = os.path.split(output)
    if name in ("", ".", ".."):
        raise CatalogError("output_path", "输出必须是新文件路径。", "output")
    temporary = None
    total = 0
    digest = hashlib.sha256()
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".merge-locale-", dir=parent or ".")
        with os.fdopen(descriptor, "wb") as destination:
            encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, indent=2)
            for chunk in itertools.chain(encoder.iterencode(tree), ("\n",)):
                encoded = chunk.encode("utf-8")
                total += len(encoded)
                if total > OUTPUT_BYTES:
                    raise CatalogError("output_bytes_limit", "合成输出超过 8 MiB。", "output")
                destination.write(encoded)
                digest.update(encoded)
            destination.flush()
            os.fsync(destination.fileno())
        # 同目录硬链接发布已经完整关闭的临时文件；目标存在时原子拒绝覆盖。
        os.link(temporary, output, follow_symlinks=False)
    except FileExistsError:
        raise CatalogError("output_exists", "输出路径已存在，不覆盖文件、目录或符号链接。", "output") from None
    except (OSError, ValueError) as error:
        raise CatalogError("output_file", "无法完整写入并独占发布输出文件。", "output",
                           errno=getattr(error, "errno", None)) from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                raise CatalogError("temporary_cleanup", "无法清理本次创建的临时文件。", "output") from None
    return dict(sha256=digest.hexdigest(), bytes=total, **inspect_tree(tree, "output"))


def main():
    try:
        parser = Parser(description=__doc__, allow_abbrev=False, add_help=False)
        parser.add_argument("-h", "--help", action="help", help="显示帮助并退出。")
        parser.add_argument("--base", required=True, help="默认消息 JSON 普通文件。")
        parser.add_argument("--override", required=True, help="目标消息 JSON 普通文件。")
        parser.add_argument("--output", required=True, help="独占创建的合成 JSON 文件。")
        args = parser.parse_args()
        base, base_receipt = read_catalog(args.base, "base")
        override, override_receipt = read_catalog(args.override, "override")
        output_receipt = publish_catalog(merge_catalogs(base, override), args.output)
        print(json.dumps(dict(schema_version=1, base=base_receipt,
                              override=override_receipt, output=output_receipt),
                         sort_keys=True, separators=(",", ":")))
        return 0
    except CatalogError as error:
        print(json.dumps(dict(error=error.error), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
