#!/usr/bin/env python3
"""只读观察已解包 Playwright .network 的有限声明字段。

Apache-2.0；方法来源 Microsoft Corporation / playwright-cli，固定版本
b1a5903c5b633b8c9f843ad7b629c2a78437040c 的
skills/playwright-cli/SKILL.md 及 references/tracing.md。
2026-10-28 本地新写：内容身份、逐行投影、字段排除及未知/错误协议。
原 Skill 没有此 helper；未复制 core 实现或运行录制链。
完整来源与许可见 ../NOTICE.txt、../licenses/playwright-cli.txt。
"""

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import unicodedata
from urllib.parse import urlsplit


MAX_INPUT = 5 * 1024 * 1024
MAX_RECORDS = 2000
MAX_LINE = 1024 * 1024
MAX_METHOD = 128
MAX_URL = 8192


class NetworkError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise NetworkError("invalid_arguments", "参数无效；需要 --input 指定本地文件。")


def read_source(name):
    try:
        path = Path(name).expanduser()
        if not stat.S_ISREG(path.lstat().st_mode):
            raise NetworkError("invalid_input", "输入必须是普通文件，不能是符号链接或特殊文件。")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(str(path), flags), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise NetworkError("invalid_input", "输入必须是普通文件。")
            data = stream.read(MAX_INPUT + 1)
    except (OSError, ValueError, RuntimeError, UnicodeError):
        raise NetworkError("input_read_failed", "无法读取指定普通文件。")
    if len(data) > MAX_INPUT:
        raise NetworkError("input_limit", "输入超过 5 MiB。")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NetworkError("duplicate_json_key", "JSON 记录含重复键。")
        result[key] = value
    return result


def reject_constant(value):
    raise NetworkError("non_finite_json", "JSON 记录含非标准非有限数值。")


def parse_record(raw):
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant,
            parse_int=Decimal, parse_float=Decimal,
        )
    except (ValueError, UnicodeError, InvalidOperation, RecursionError):
        raise NetworkError("invalid_json", "输入行不是可解析的 JSON 记录。")


def object_field(value):
    if not isinstance(value, dict):
        raise NetworkError("invalid_structure", "采用的记录或容器字段类型不符。")
    return value


def optional_text(value, limit):
    if value is None:
        return None
    if not isinstance(value, str):
        raise NetworkError("invalid_metadata", "采用的文本字段类型不符。")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise NetworkError("invalid_metadata", "采用的文本不能编码为 UTF-8。")
    if len(encoded) > limit:
        raise NetworkError("metadata_limit", "采用的文本超过本接口字节上限。")
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise NetworkError("invalid_metadata", "采用的文本含控制字符。")
    return value or None


def projected_url(value):
    value = optional_text(value, MAX_URL)
    if value is None:
        return None
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
        if parts.scheme not in ("http", "https") or not hostname:
            return None
        return {"scheme": parts.scheme, "hostname": hostname, "port": port, "path": parts.path}
    except ValueError:
        # 标准库异常可能包含原 URL；只返回常量未知，不传播原文。
        return None


def declared_status(response):
    if response is None:
        return None
    value = object_field(response).get("status")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise NetworkError("invalid_status", "已提供的状态须为整数数值。")
    if not value.is_finite() or value != value.to_integral_value():
        raise NetworkError("invalid_status", "已提供的状态须为有限整数数值。")
    # 先比较再转 int，避免把不采用的巨大指数展开成巨型整数。
    return int(value) if 100 <= value <= 599 else None


def inspect_records(data):
    try:
        data.decode("utf-8")
    except UnicodeError:
        raise NetworkError("invalid_encoding", "输入必须是有效 UTF-8。")
    snapshots = []
    for line_number, raw in enumerate(data.split(b"\n"), 1):
        if len(raw) > MAX_LINE:
            raise NetworkError("line_limit", "原始行超过 1 MiB。")
        if not raw.strip(b" \t\r"):
            continue
        if len(snapshots) >= MAX_RECORDS:
            raise NetworkError("record_limit", "非空资源快照记录超过 2000。")
        record = object_field(parse_record(raw))
        if record.get("type") != "resource-snapshot":
            raise NetworkError("unsupported_record_type", "本接口仅支持 resource-snapshot 声明记录。")
        snapshot = object_field(record.get("snapshot"))
        request = object_field(snapshot.get("request"))
        method = optional_text(request.get("method"), MAX_METHOD)
        url = projected_url(request.get("url"))
        status = declared_status(snapshot.get("response"))
        issues = []
        for unavailable, code in (
            (method is None, "method_unavailable"),
            (url is None, "url_unavailable"),
            (status is None, "status_unavailable"),
        ):
            if unavailable:
                issues.append(code)
        snapshots.append({
            "line": line_number, "method": method, "url": url,
            "response_status": status, "issues": issues,
        })
    return snapshots


def main(argv=None):
    result = {
        "status": "error", "source": None, "snapshot_count": None, "snapshots": [],
        "reason": None, "error": None, "verification": "not_performed",
    }
    try:
        parser = Parser(description="只读投影 Playwright .network 的有限声明字段。", allow_abbrev=False)
        parser.add_argument("--input", required=True, help="已解包的普通本地 UTF-8 .network 文件")
        args = parser.parse_args(argv)
        data = read_source(args.input)
        result["source"] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        snapshots = inspect_records(data)
        unknown = any(row["issues"] for row in snapshots)
        result.update(
            status="partial" if not snapshots or unknown else "complete",
            snapshot_count=len(snapshots), snapshots=snapshots,
            reason="no_resource_snapshots" if not snapshots else (
                "snapshot_fields_unavailable" if unknown else None
            ),
        )
    except NetworkError as exc:
        result["error"] = {"code": exc.code, "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return {"complete": 0, "partial": 2, "error": 1}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
