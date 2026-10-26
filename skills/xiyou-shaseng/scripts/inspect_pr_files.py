#!/usr/bin/env python3
"""只读采集显式 GitHub.com PR 的文件清单和 API 提供的差异片段。

2026-10-26：扩展已适配的 gh-address-comments 输入整理方法；复用同目录
评论工具的有界 gh 捕获，不解析或应用 patch。来源与 Apache-2.0 见 ../NOTICE.txt。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

# 导入同技能 helper 也不在安装目录生成缓存文件。
sys.dont_write_bytecode = True
from inspect_pr_comments import (SHA, bounded_gh, integer, nonempty, now,
                                 positive_int, reject_constant, repository_arg,
                                 timeout_arg)

API_VERSION = "2026-03-10"
REQUEST_BUDGET = 64
FILE_LIMIT = 3000
DATA_LIMIT = 8 * 1024 * 1024
PAGE_SIZE = 100
URL_FIELDS = ("blob_url", "raw_url", "contents_url")


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("不允许溢出为非有限值的 JSON 数字。")
    return parsed


def max_pages_arg(value):
    parsed = positive_int(value)
    if parsed > 30:
        raise argparse.ArgumentTypeError("max-pages 必须在 1..30 之间。")
    return parsed


def canonical_repo(value):
    try:
        return isinstance(value, str) and repository_arg(value) == value
    except argparse.ArgumentTypeError:
        return False


class Inspector:
    def __init__(self, args):
        self.args = args
        self.before = None
        self.stale = False
        self.seen = set()
        self.retained_bytes = 2  # ensure_ascii=True 的 files JSON 数组含括号与分隔符。
        self.endpoint = f"repos/{args.repo}/pulls/{args.pr}"
        self.data = {
            "schema_version": 1,
            "request": {"host": "github.com", "repo": args.repo, "pr": args.pr,
                        "api_version": API_VERSION, "timeout": args.timeout,
                        "max_pages": args.max_pages, "request_budget": REQUEST_BUDGET},
            "pull_request": {"before": None, "after": None, "observations": []},
            "files": [],
            "collection": {"status": "error", "started_at": now(), "finished_at": None,
                           "expected_count": None, "count": 0, "pages": [],
                           "file_list_complete": False, "patch_fields_complete": False,
                           "patch_text_completeness": "not_proven", "truncated": False,
                           "request_count": 0, "retained_fields_bytes": 2,
                           "retained_fields_limit": DATA_LIMIT,
                           "observation": "sequential_non_atomic"},
            "commands": [], "errors": [], "exit_code": 2,
        }

    def issue(self, code, scope, detail, truncated=False):
        self.data["errors"].append({"code": code, "scope": scope, "detail": detail})
        self.data["collection"]["truncated"] |= truncated

    def get(self, endpoint, scope, identity=False):
        # 文件页必须给随后的身份回读保留一个请求名额。
        if len(self.data["commands"]) >= REQUEST_BUDGET - (0 if identity else 1):
            self.issue("request_budget_exhausted", scope, "请求预算不足，保留已核数据。", True)
            return None
        argv = ["api", "--hostname", "github.com", "--method", "GET", endpoint,
                "-H", "Accept: application/vnd.github+json",
                "-H", "X-GitHub-Api-Version: " + API_VERSION]
        command, payload = bounded_gh(argv, self.args.timeout)
        command["scope"] = scope
        self.data["commands"].append(command)
        self.data["collection"]["request_count"] = len(self.data["commands"])
        if command["capture_status"] != "ok":
            code = command["capture_status"]
            self.issue(code, scope, "gh 输出捕获未完成。", code.endswith("_limit"))
            return None
        if command["returncode"] != 0:
            self.issue("gh_error", scope, "gh 返回非零状态，响应不作为完整数据。")
            return None
        try:
            return json.loads(payload, parse_constant=reject_constant, parse_float=finite_float)
        except (ValueError, UnicodeDecodeError, RecursionError):
            self.issue("invalid_json", scope, "gh 响应不是合法有限值 JSON。")
            return None

    def identity(self, scope):
        errors_before = len(self.data["errors"])
        value = self.get(self.endpoint, scope, identity=True)
        if value is None:
            if len(self.data["errors"]) == errors_before:
                self.issue("invalid_identity", scope, "PR 身份不能为 null。")
            return None
        if not isinstance(value, dict):
            self.issue("invalid_identity", scope, "PR 身份必须为对象。")
            return None
        base, head = value.get("base"), value.get("head")
        repo = base.get("repo") if isinstance(base, dict) else None
        if not isinstance(repo, dict) or not isinstance(head, dict):
            self.issue("invalid_identity", scope, "缺少 base 仓库或 head 身份。")
            return None
        name, number, url = repo.get("full_name"), value.get("number"), value.get("html_url")
        # 规范 URL 若明确指向别的目标，即使其余字段不一致也不能继续采集。
        match = (re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/([1-9][0-9]*)", url)
                 if isinstance(url, str) else None)
        other_url = (match is not None and canonical_repo(match[1])
                     and (match[1].casefold() != self.args.repo.casefold()
                          or match[2] != str(self.args.pr)))
        if (other_url or (canonical_repo(name) and name.casefold() != self.args.repo.casefold())
                or (integer(number, 1) and number != self.args.pr)):
            self.stale = True
            self.issue("target_mismatch", scope, "响应明确指向其他仓库或 PR。")
            return None
        valid = (canonical_repo(name) and integer(number, 1)
                 and url == f"https://github.com/{name}/pull/{number}"
                 and repo.get("html_url") == f"https://github.com/{name}"
                 and all(integer(item.get("id"), 1) and nonempty(item.get("node_id"))
                         for item in (repo, value))
                 and all(isinstance(item.get("sha"), str) and SHA.fullmatch(item["sha"])
                         for item in (base, head)))
        if not valid:
            self.issue("invalid_identity", scope, "PR/repo ID、URL、编号或提交身份缺失或不合法。")
            return None
        count = value.get("changed_files")
        if not integer(count):
            self.issue("invalid_changed_files", scope, "changed_files 缺失或不是非负整数。")
            count = None
        snapshot = {"id": value["id"], "node_id": value["node_id"], "number": number,
                    "html_url": url, "base": {"sha": base["sha"], "repo": {
                        key: repo[key] for key in ("id", "node_id", "full_name", "html_url")}},
                    "head": {"sha": head["sha"]}, "changed_files": count}
        self.data["pull_request"]["observations"].append(
            {"scope": scope, "observed_at": now(), "identity": snapshot})
        if self.before is not None:
            # 数量类型错误是未知；有效数字发生变化才是明确漂移。
            prior = dict(self.before, changed_files=None)
            current = dict(snapshot, changed_files=None)
            if (current != prior or (count is not None and count != self.before["changed_files"])):
                self.stale = True
                self.issue("identity_changed", scope, "PR/repo 身份、head/base 或 changed_files 已变化。")
        return snapshot

    def file(self, value, scope):
        if not isinstance(value, dict):
            self.issue("invalid_file", scope, "文件条目必须为对象。")
            return None
        name = value.get("filename")
        valid = (isinstance(name, str) and bool(name) and nonempty(value.get("status"))
                 and isinstance(value.get("sha"), str) and SHA.fullmatch(value["sha"])
                 and all(integer(value.get(key)) for key in ("additions", "deletions", "changes"))
                 and ("previous_filename" not in value or
                      isinstance(value["previous_filename"], str) and bool(value["previous_filename"]))
                 and all(key not in value or value[key] is None or isinstance(value[key], str)
                         for key in URL_FIELDS))
        if not valid:
            self.issue("invalid_file", scope, "文件路径、SHA、状态、计数或可选字段类型不合法。")
            return None
        if name in self.seen:
            self.issue("duplicate_filename", scope, "出现重复 filename，未重复保留。")
            return None
        keys = ("filename", "status", "sha", "additions", "deletions", "changes",
                "previous_filename", "patch", *URL_FIELDS)
        row = {key: value[key] for key in keys if key in value}
        provided = isinstance(row.get("patch"), str)
        row["patch_availability"] = "provided" if provided else "unavailable"
        if not provided:
            row["patch_unavailable_reason"] = "unknown"
            code = "invalid_patch" if row.get("patch") is not None else "patch_unavailable"
            self.issue(code, scope, "API patch 未提供字符串；原因未知，不推断二进制或零差异。")
        size = len(json.dumps(row, ensure_ascii=True).encode("ascii")) + (2 if self.seen else 0)
        if self.retained_bytes + size > DATA_LIMIT:
            self.issue("retained_data_limit", scope, "保留文件字段超过 8 MiB，未保留越界条目。", True)
            return None
        self.retained_bytes += size
        self.seen.add(name)
        return row

    def collect(self):
        count = self.before["changed_files"]
        if count is None:
            return
        collection = self.data["collection"]
        collection["expected_count"] = count
        required_pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
        if count > FILE_LIMIT:
            self.issue("api_file_limit", "files", "PR 超出 API 的 3000 文件范围。", True)
        if required_pages > self.args.max_pages:
            self.issue("page_limit", "files", "所需页数超过 max-pages。", True)
        list_ok = True
        for page in range(1, min(required_pages, self.args.max_pages, 30) + 1):
            scope = f"files_page_{page}"
            errors_before = len(self.data["errors"])
            payload = self.get(self.endpoint + f"/files?per_page=100&page={page}", scope)
            # 页内容先暂存，只有随后的身份回读稳定才能保留。
            after = self.identity(f"identity_after_page_{page}")
            self.data["pull_request"]["after"] = after
            if after is None or self.stale or after["changed_files"] is None:
                list_ok = False
                break
            expected = min(PAGE_SIZE, max(0, count - (page - 1) * PAGE_SIZE))
            received = len(payload) if isinstance(payload, list) else None
            collection["pages"].append({"page": page, "expected": expected, "received": received})
            if not isinstance(payload, list):
                if len(self.data["errors"]) == errors_before:
                    self.issue("invalid_files_page", scope, "文件页必须为数组。")
                list_ok = False
                break
            if received != expected:
                self.issue("page_count_mismatch", scope, "文件页数量与初始 changed_files 的预期范围不符。")
                list_ok = False
            for item in payload[:PAGE_SIZE]:
                row = self.file(item, scope)
                if row is None:
                    list_ok = False
                    break
                self.data["files"].append(row)
            if not list_ok:
                break
        collection["count"] = len(self.data["files"])
        collection["retained_fields_bytes"] = self.retained_bytes
        collection["file_list_complete"] = (list_ok and not self.stale and count <= FILE_LIMIT
                                            and required_pages <= self.args.max_pages
                                            and collection["count"] == count)
        collection["patch_fields_complete"] = (collection["file_list_complete"] and
            all(row["patch_availability"] == "provided" for row in self.data["files"]))

    def run(self):
        self.before = self.identity("identity_before")
        self.data["pull_request"]["before"] = self.before
        if self.before is not None and not self.stale:
            self.collect()
        collection = self.data["collection"]
        complete = (collection["file_list_complete"] and collection["patch_fields_complete"]
                    and not self.data["errors"])
        collection["status"] = ("stale" if self.stale else "complete" if complete
                                else "partial" if self.before else "error")
        collection["finished_at"] = now()
        self.data["exit_code"] = 0 if complete else 2
        return self.data


def main():
    parser = argparse.ArgumentParser(description="只读收集 GitHub.com PR 文件清单和 API patch 字段。")
    parser.add_argument("--repo", required=True, type=repository_arg, help="显式 base 仓库 OWNER/REPO")
    parser.add_argument("--pr", required=True, type=positive_int, help="显式 PR 正整数编号")
    parser.add_argument("--timeout", type=timeout_arg, default=30, help="每次 gh 超时秒数，默认 30")
    parser.add_argument("--max-pages", type=max_pages_arg, default=10, help="页数上限 1..30，默认 10")
    result = Inspector(parser.parse_args()).run()
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
