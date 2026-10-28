#!/usr/bin/env python3
"""把有界 UTF-8 JSON 文档编码为一个非执行的 HTML script 数据块。

仅适用于作为普通 HTML 节点插入的数据片段；不处理 HTML 属性、可执行
JavaScript 字符串、完整网页或业务语义，也不代表已完成浏览器验收。
"""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile


INPUT_BYTES = 1024 * 1024
OUTPUT_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 32  # 根值深度为 0，每条成员或数组元素边加 1，包含叶值。
MAX_NODES = 50000  # 每个值计一个节点，含根，不含对象键。
MAX_INTEGER = 2 ** 53 - 1
DATA_TYPE = "application/json"


class DataError(Exception):
    def __init__(self, code, message):
        self.error = dict(code=code, message=message)
        super().__init__(message)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise DataError("arguments", "参数缺失或不受支持，请使用 --help 查看用法。")


def check_nesting(text):
    # 标准解析前只限制容器嵌套，防止超深输入耗尽解析器调用栈。
    quoted = escaped = False
    nesting = 0
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
            nesting += 1
            if nesting > MAX_DEPTH + 1:
                raise DataError("depth_limit", "JSON 值的深度超过 32。")
        elif char in "}]":
            nesting -= 1


def parse_integer(token):
    if token == "-0":
        return -0.0
    # 先限制位数，避免把超长数字交给大整数转换器。
    if len(token.lstrip("-")) > 16:
        raise DataError("integer_range", "整数超出 JavaScript 安全整数范围。")
    value = int(token)
    if not -MAX_INTEGER <= value <= MAX_INTEGER:
        raise DataError("integer_range", "整数超出 JavaScript 安全整数范围。")
    return value


def reject_constant(token):
    raise DataError("invalid_number", "JSON 不接受 NaN 或 Infinity 常量。")


def object_from_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataError("duplicate_key", "JSON 对象含重复键。")
        result[key] = value
    return result


def check_unicode(value):
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise DataError("invalid_unicode", "键或字符串含无效 Unicode 代理码点。")


def inspect_values(tree):
    nodes = 0
    stack = [(tree, 0)]
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise DataError("node_limit", "JSON 值节点超过 50000。")
        if depth > MAX_DEPTH:
            raise DataError("depth_limit", "JSON 值的深度超过 32。")
        if isinstance(value, dict):
            for key, child in value.items():
                check_unicode(key)
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            check_unicode(value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise DataError("non_finite_number", "浮点数必须为有限值。")


def read_json(path):
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise DataError("input_file", "输入必须是普通文件，不接受链接或特殊文件。")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (not stat.S_ISREG(opened.st_mode)
                    or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
                raise DataError("input_changed", "输入文件在打开时已变化，请重新执行。")
            raw = source.read(INPUT_BYTES + 1)
    except (OSError, ValueError):
        raise DataError("input_file", "无法读取输入普通文件。") from None
    if len(raw) > INPUT_BYTES:
        raise DataError("input_bytes_limit", "单份输入超过 1 MiB。")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise DataError("invalid_utf8", "输入必须是无 BOM 的 UTF-8 文档。")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise DataError("invalid_utf8", "输入不是有效 UTF-8。") from None
    check_nesting(text)
    try:
        tree = json.loads(text, object_pairs_hook=object_from_pairs,
                          parse_int=parse_integer, parse_constant=reject_constant)
    except json.JSONDecodeError:
        raise DataError("invalid_json", "输入不是有效 JSON。") from None
    except RecursionError:
        raise DataError("depth_limit", "JSON 值的深度超过 32。") from None
    inspect_values(tree)
    return tree, dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def publish_fragment(tree, output, element_id):
    parent, name = os.path.split(output)
    if name in ("", ".", ".."):
        raise DataError("output_path", "输出必须是新文件路径。")
    # 必须先用标准 JSON encoder 编码，再转义所有正文中的 literal <。
    data = json.dumps(tree, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    data = data.replace("<", "\\u003c")
    fragment = ('<script type="application/json" id="' + element_id + '">'
                + data + '</script>\n').encode("utf-8")
    if len(fragment) > OUTPUT_BYTES:
        raise DataError("output_bytes_limit", "输出片段超过 8 MiB。")
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".embed-json-data-", dir=parent or ".")
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(fragment)
            destination.flush()
            os.fsync(destination.fileno())
        # 同目录硬链接原子发布完整文件；已有文件、目录或链接均不会被覆盖。
        os.link(temporary, output, follow_symlinks=False)
    except FileExistsError:
        raise DataError("output_exists", "输出路径已存在，不覆盖文件、目录或链接。") from None
    except (OSError, ValueError):
        raise DataError("output_file", "无法完整写入并独占发布输出文件。") from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                raise DataError("temporary_cleanup", "无法清理本次创建的临时文件。") from None
    return dict(sha256=hashlib.sha256(fragment).hexdigest(), bytes=len(fragment))


def main():
    try:
        parser = Parser(description=__doc__, allow_abbrev=False, add_help=False)
        parser.add_argument("-h", "--help", action="help", help="显示帮助并退出。")
        parser.add_argument("--input", required=True, help="无 BOM UTF-8 JSON 普通文件。")
        parser.add_argument("--output", required=True, help="独占创建的 HTML 片段文件。")
        parser.add_argument("--id", default="xiyou-data", help="数据节点标识，默认 xiyou-data。")
        args = parser.parse_args()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", args.id) is None:
            raise DataError("invalid_id", "ID 须为 1 至 64 位 ASCII 字母开头的字母、数字、下划线或短横线。")
        tree, input_receipt = read_json(args.input)
        output_receipt = publish_fragment(tree, args.output, args.id)
        print(json.dumps(dict(input=input_receipt, output=output_receipt,
                              type=DATA_TYPE, id=args.id, browser_review="not_performed"),
                         sort_keys=True, separators=(",", ":")))
        return 0
    except DataError as error:
        print(json.dumps(dict(error=error.error), ensure_ascii=False), file=sys.stderr)
        return 2
    except MemoryError:
        print(json.dumps(dict(error=dict(code="resource_limit", message="处理所需内存超过可用范围。")),
                         ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps(dict(error=dict(code="interrupted", message="处理已中断。")),
                         ensure_ascii=False), file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
