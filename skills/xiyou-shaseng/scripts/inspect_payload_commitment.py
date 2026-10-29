#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""只读核对载荷字段的一致性，不认证完整收据或执行事实。

载荷规则改编自 Brennan Zambo / zambo.dev 的 aer1-verify：
https://gitlab.com/rambozambodotdev/zambo/-/blob/7d5947d647919705fff3d8223e30594f5918a660/aer-1/conformance.py
原方法位于442–475行，Copyright (c) 2026 Brennan Zambo，原许可为MIT。
完整原MIT见 ../licenses/aer1-payload.txt。本地适配为显式文件、部分结果、
资源与JSON边界及固定证明范围，不执行原程序、载荷、网络或回执生成流程。
"""

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import re
import stat
import sys


MAX_INPUT = 2 * 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 100000
MAX_NUMBER = 128
MAX_ENCODED = 1398104
MAX_DECODED = 1024 * 1024
BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]*={0,2}")
HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


class PayloadError(ValueError):
    """固定诊断说明，不携带输入值。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PayloadError("参数不合法；请使用 --help 查看用法。")


def read_input(filename):
    if not all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_NONBLOCK")):
        raise PayloadError("当前系统不支持所需的普通文件读取保护。")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(filename, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise PayloadError("输入必须是普通文件，不能是链接、目录或特殊文件。")
        if info.st_size > MAX_INPUT:
            raise PayloadError("输入超过 2 MiB 字节上限。")
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise PayloadError("输入超过 2 MiB 字节上限。")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PayloadError("输入须为不带 BOM 的 UTF-8 JSON。")
    return raw


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PayloadError("JSON 对象含重复键，本部分未完成核对。")
        result[key] = value
    return result


def bounded_number(text, convert):
    if len(text) > MAX_NUMBER:
        raise PayloadError("JSON 数值字面量超过 128 字符上限。")
    value = convert(text)
    if isinstance(value, float) and not math.isfinite(value):
        raise PayloadError("JSON 不接受非有限数。")
    return value


def reject_constant(text):
    raise PayloadError("JSON 不接受非有限数。")


def load_object(raw):
    data = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_int=lambda text: bounded_number(text, int),
        parse_float=lambda text: bounded_number(text, float),
        parse_constant=reject_constant,
    )
    pending = [(data, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise PayloadError("JSON 超过深度 32 或节点数 100000 上限。")
        if isinstance(item, str):
            item.encode("utf-8")
        elif isinstance(item, dict):
            for key, value in item.items():
                key.encode("utf-8")
                pending.append((value, depth + 1))
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
    if not isinstance(data, dict):
        raise PayloadError("本部分只读取顶层 JSON 对象，不判断完整收据。")
    if not all(isinstance(data.get(key), str)
               for key in ("canonical_bytes", "output_hash")):
        raise PayloadError("本部分需要 canonical_bytes 和 output_hash 两个顶层字符串字段。")
    return data


def inspect_payload(data, input_bytes):
    encoded = data["canonical_bytes"]
    declared_hash = data["output_hash"]
    if len(encoded) > MAX_ENCODED:
        raise PayloadError("canonical_bytes 超过 1398104 字符上限。")
    issues = []
    decoded = None
    canonical = False
    utf8_valid = None
    observed_hash = None
    hash_matches = None
    if BASE64_PATTERN.fullmatch(encoded) is None:
        issues.append("base64_invalid")
    else:
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            issues.append("base64_invalid")
        else:
            if len(decoded) > MAX_DECODED:
                raise PayloadError("解码载荷超过 1 MiB 字节上限。")
            canonical = base64.b64encode(decoded).decode("ascii") == encoded
            if not canonical:
                issues.append("base64_noncanonical")
            try:
                decoded.decode("utf-8")
            except UnicodeDecodeError:
                utf8_valid = False
                issues.append("utf8_invalid")
            else:
                utf8_valid = True
                observed_hash = "sha256:" + hashlib.sha256(decoded).hexdigest()
    hash_format = HASH_PATTERN.fullmatch(declared_hash) is not None
    if not hash_format:
        issues.append("output_hash_invalid")
    elif observed_hash is not None:
        hash_matches = observed_hash == declared_hash
        if not hash_matches:
            issues.append("sha256_mismatch")
    checks = {
        "base64_canonical": canonical,
        "utf8_valid": utf8_valid,
        "output_hash_format": hash_format,
        "sha256_matches": hash_matches,
    }
    return {
        "input": {"sha256": hashlib.sha256(input_bytes).hexdigest(),
                  "bytes": len(input_bytes)},
        "scope": "canonical_bytes/output_hash_only",
        "checks": checks,
        "payload": {"decoded_bytes": len(decoded) if decoded is not None else None,
                    "observed_output_hash": observed_hash},
        "issues": issues,
        "payload_status": "matched" if all(value is True for value in checks.values())
                          else "mismatched",
        "full_receipt_validation": "not_performed",
        "execution_verification": "not_performed",
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
    parser = Parser(description="只读检查已有 JSON 的载荷编码与摘要，不验证完整收据或执行。")
    parser.add_argument("--input", required=True, help="明确已有、含两个所需字符串字段的 JSON 文件")
    try:
        args = parser.parse_args()
        raw = read_input(args.input)
        result = inspect_payload(load_object(raw), raw)
        output = json.dumps(result, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8") + b"\n"
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0 if result["payload_status"] == "matched" else 1
    except PayloadError as error:
        return fail(str(error))
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError, ValueError):
        return fail("输入不是 Unicode 标量有效、资源有界的标准 UTF-8 JSON。")
    except OSError:
        return fail("无法读取指定普通文件或写入输出。")


if __name__ == "__main__":
    sys.exit(main())
