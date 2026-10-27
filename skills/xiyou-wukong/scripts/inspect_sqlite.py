#!/usr/bin/env python3
"""提取稳定离线 SQLite 的 schema 或原生查询计划，不执行用户查询本体。

方法来源：ofershap/mcp-server-sqlite 的 sqlite-query Skill 与 src/sqlite.ts，
固定版本 a3b0323ce23521190572460dff944722b0036b3c。
MIT License，Copyright (c) 2026 Ofer Shapira；完整许可见
../licenses/sqlite-query.txt，适配归属见 ../references/lineage.md。
参数绑定、预算、窄授权、文件检查及 JSON 协议均为本地新增。
仅适用于受控普通本地文件；不承诺恶意并发下原子快照、硬超时或内存沙箱。
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import sys


MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_SQL_BYTES = 16 * 1024
SCHEMA_SQL = (
    "SELECT type, name, tbl_name, sql FROM main.sqlite_master ORDER BY type, name"
)
SIDECARS = ("-wal", "-shm", "-journal")


class InspectionError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", required=True, metavar="FILE")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--schema", action="store_true")
    mode.add_argument("--plan", metavar="SQL")
    parser.add_argument("--params-json", metavar="JSON_ARRAY")
    parser.add_argument("--max-rows", type=int, default=128)
    parser.add_argument("--max-output-bytes", type=int, default=65536)
    args = parser.parse_args()
    if args.schema and args.params_json is not None:
        parser.error("--params-json 仅适用于 --plan")
    if not 1 <= args.max_rows <= 512:
        parser.error("--max-rows 必须在 1..512 范围内")
    if not 1 <= args.max_output_bytes <= 262144:
        parser.error("--max-output-bytes 必须在 1..262144 范围内")
    return args


def parameters(raw):
    try:
        values = json.loads(raw if raw is not None else "[]")
    except (ValueError, RecursionError) as exc:
        raise InspectionError("PARAMETERS", "参数必须是合法 JSON 数组") from exc
    if not isinstance(values, list):
        raise InspectionError("PARAMETERS", "参数必须是 JSON 数组")
    for value in values:
        if value is None or isinstance(value, (str, bool)):
            continue
        if isinstance(value, int) and -(2 ** 63) <= value < 2 ** 63:
            continue
        if isinstance(value, float) and math.isfinite(value):
            continue
        raise InspectionError("PARAMETERS", "只接受 null、布尔、字符串、有限浮点或有符号64位整数")
    return values


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


def check_sidecars(path):
    if any(os.path.lexists(path + suffix) for suffix in SIDECARS):
        raise InspectionError("INPUT_FILE", "数据库旁存在 -wal、-shm 或 -journal")


def snapshot(path):
    """先检查大小，再流式哈希；哈希期间的可见变化也拒绝。"""
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise InspectionError("INPUT_FILE", "数据库必须是叶非符号链接的普通既存文件")
        if not 0 < before.st_size <= MAX_DATABASE_BYTES:
            raise InspectionError("INPUT_FILE", "数据库必须非空且不大于128MiB")
        check_sidecars(path)
        digest = hashlib.sha256()
        read_bytes = 0
        with open(path, "rb") as source:
            if identity(os.fstat(source.fileno())) != identity(before):
                raise InspectionError("FILE_CHANGED", "打开文件时数据库身份发生变化")
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                read_bytes += len(chunk)
                if read_bytes > MAX_DATABASE_BYTES:
                    raise InspectionError("FILE_CHANGED", "读取期间数据库超过大小限制")
                digest.update(chunk)
        after = os.lstat(path)
        check_sidecars(path)
        if identity(before) != identity(after) or read_bytes != before.st_size:
            raise InspectionError("FILE_CHANGED", "读取期间数据库发生变化")
        return identity(after), digest.hexdigest()
    except OSError as exc:
        raise InspectionError("INPUT_FILE", str(exc)) from exc


def readonly_authorizer(objects):
    state = {"selected": False, "denied": None}

    def authorize(action, first, second, database, source):
        if action == sqlite3.SQLITE_SELECT:
            state["selected"] = True
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_RECURSIVE:
            return sqlite3.SQLITE_OK
        # SQLite 对不读取列的表访问可报告空列及无数据库名；新建单库连接
        # 没有用户 temp 对象且拒绝 ATTACH，仅兼容名单内 main 对象的此事件。
        if (action == sqlite3.SQLITE_READ and first in objects
                and (database == "main" or (database is None and second == ""))):
            return sqlite3.SQLITE_OK
        state["denied"] = "拒绝授权动作 {}（{}）".format(action, first or "")
        return sqlite3.SQLITE_DENY

    return authorize, state


def collect(cursor, max_rows, max_bytes):
    columns = [column[0] for column in cursor.description]
    rows = []
    payload = 0
    while True:
        row = cursor.fetchone()
        if row is None:
            return columns, rows, payload, None
        if len(rows) == max_rows:
            return columns, rows, payload, "max_rows"
        row = list(row)
        size = len(json.dumps(row, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False).encode("utf-8"))
        if payload + size > max_bytes:
            return columns, rows, payload, "max_output_bytes"
        rows.append(row)
        payload += size


def inspect(args, result):
    connection = None
    initial = None
    failure = None
    authorization = None
    try:
        if sys.version_info < (3, 9) or sqlite3.sqlite_version_info < (3, 37):
            raise InspectionError("RUNTIME", "需要 Python3.9+ 与 SQLite3.37+；本工具不安装升级")
        values = parameters(args.params_json)
        if args.plan is not None and len(args.plan.encode("utf-8")) > MAX_SQL_BYTES:
            raise InspectionError("SQL_INPUT", "SQL 的 UTF-8 长度超过16KiB")
        initial = snapshot(result["database"])
        uri = Path(result["database"]).as_uri() + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True, timeout=0.25)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        if args.schema:
            objects = {"sqlite_master", "sqlite_schema"}
            sql = SCHEMA_SQL
        else:
            # 固定 metadata 查询独立于用户 SQL；不借它的授权事件判 SELECT。
            objects = {row[1] for row in connection.execute("PRAGMA main.table_list")
                       if row[0] == "main" and row[2] in ("table", "view")}
            objects.update(("sqlite_master", "sqlite_schema"))
            sql = "EXPLAIN QUERY PLAN " + args.plan
        authorize, authorization = readonly_authorizer(objects)
        connection.set_authorizer(authorize)
        cursor = connection.execute(sql, values)
        if not authorization["selected"]:
            raise InspectionError("SQL_REJECTED", "用户计划必须包含原生 SELECT 授权事件")
        columns, rows, payload, reason = collect(
            cursor, args.max_rows, args.max_output_bytes
        )
        result.update(columns=columns, rows=rows, returned_rows=len(rows),
                      row_payload_bytes=payload, reason=reason,
                      truncated=reason is not None,
                      status="partial" if reason else "ok")
    except InspectionError as exc:
        failure = exc
    except (sqlite3.Error, sqlite3.Warning) as exc:
        # Python3.9 的驱动以 Warning 拒绝多语句，也须保持 error JSON 协议。
        if authorization is not None and authorization["denied"]:
            failure = InspectionError("SQL_REJECTED", authorization["denied"])
        else:
            failure = InspectionError("SQLITE", str(exc))
    except (OSError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        failure = InspectionError("INPUT", str(exc))
    finally:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error as exc:
                failure = InspectionError("SQLITE", str(exc))
        if initial is not None:
            try:
                if snapshot(result["database"]) != initial:
                    raise InspectionError("FILE_CHANGED", "检查前后数据库身份或内容发生变化")
            except InspectionError as exc:
                failure = InspectionError("FILE_CHANGED", str(exc))
    if failure is not None:
        result.update(status="error", columns=[], rows=[], returned_rows=0,
                      row_payload_bytes=0, truncated=False, reason=None,
                      error={"code": failure.code, "message": str(failure)})
    return {"ok": 0, "partial": 3, "error": 2}[result["status"]]


def main():
    args = arguments()
    result = {
        "status": "error",
        "operation": "schema" if args.schema else "plan",
        "database": os.path.abspath(args.database),
        "sqlite_version": sqlite3.sqlite_version,
        "columns": [], "rows": [], "returned_rows": 0,
        "row_payload_bytes": 0, "truncated": False, "reason": None, "error": None,
    }
    exit_code = inspect(args, result)
    # 外层使用 ASCII 转义保持 stdout 始终是合法 UTF-8；行预算单独按原值计算。
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":"), allow_nan=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
