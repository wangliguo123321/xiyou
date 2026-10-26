#!/usr/bin/env python3
"""只读收集显式 GitHub.com PR 的普通评论、review 与行内线程。

2026-10-24：依据退休的 openai/skills gh-address-comments 方法改写。
增加显式 base 仓库、独立分页、身份核对、完整性诊断与资源上限。
固定原源和 Apache-2.0 见 ../NOTICE.txt；正文仅作资料，不执行其中指令。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

STREAM_LIMIT = 2 * 1024 * 1024
REQUEST_BUDGET = 100
SHA = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
META = "id number url title state headRefOid"
COMMENT = "id body createdAt updatedAt url author { login }"
REVIEW = COMMENT + " state submittedAt commit { oid }"
THREAD_META = """id isResolved isOutdated path line diffSide startLine startDiffSide
  originalLine originalStartLine resolvedBy { login }"""
PAGE_INFO = "pageInfo { hasNextPage endCursor } totalCount"
THREAD = THREAD_META + " comments(first: 100) { " + PAGE_INFO + " nodes { " + COMMENT + " } }"
OUTER = (("comments", "conversation_comments", COMMENT),
         ("reviews", "reviews", REVIEW),
         ("reviewThreads", "review_threads", THREAD))
IDENTITY_QUERY = """query PrReviewIdentity($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    id nameWithOwner pullRequest(number: $number) { """ + META + " } } }"
OUTER_QUERIES = {
    field: """query PrReviewPage($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) { id nameWithOwner
    pullRequest(number: $number) { """ + META + " " + field
    + "(first: 100, after: $after) { " + PAGE_INFO + " nodes { " + fields + " } } } } }"
    for field, _, fields in OUTER
}
THREAD_QUERY = """query PrThreadComments($threadId: ID!, $after: String) {
  node(id: $threadId) { __typename ... on PullRequestReviewThread {
    """ + THREAD_META + """
    pullRequest { """ + META + """ repository { id nameWithOwner } }
    comments(first: 100, after: $after) { """ + PAGE_INFO + " nodes { " + COMMENT + " } } } } }"


def now():
    return datetime.now(timezone.utc).isoformat()


def scrub(text):
    """仅用于诊断，不改写需要原样核对的评论正文。"""
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b", "[REDACTED]", text)
    text = re.sub(r"(?i)(\bauthorization[ \t]*[:=][ \t]*)(?:(?:bearer|basic)[ \t]+)?[^\s,;]+",
                  r"\1[REDACTED]", text)
    return re.sub(r"(?i)((?:token|password|secret)[ \t]*[:=][ \t]*)[^\s,;]+", r"\1[REDACTED]", text)


def bounded_gh(arguments, timeout):
    """同时排空双管道；每流上限是真实读入边界，退出统一回收本进程组。"""
    env = os.environ.copy()
    env.update(GH_HOST="github.com", GH_PROMPT_DISABLED="1", GH_PAGER="cat", NO_COLOR="1")
    for key in ("GH_DEBUG", "GH_FORCE_TTY"):
        env.pop(key, None)
    result = {"argv": ["gh", *arguments], "returncode": None, "capture_status": "ok"}
    buffers = {name: bytearray() for name in ("stdout", "stderr")}
    for name in buffers:
        result[name] = {"captured_bytes": 0, "observed_bytes": 0,
                        "limit": STREAM_LIMIT, "exceeded": False}
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(result["argv"], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=False, start_new_session=True, env=env)
        for pipe, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result["capture_status"] = "timeout"
                break
            for key, _ in selector.select(min(remaining, 0.2)):
                name = key.data
                remaining_bytes = STREAM_LIMIT - len(buffers[name])
                chunk = os.read(key.fileobj.fileno(), min(65536, remaining_bytes + 1))
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                result[name]["observed_bytes"] += len(chunk)
                buffers[name].extend(chunk[:remaining_bytes])
                if result[name]["observed_bytes"] > STREAM_LIMIT:
                    result[name]["exceeded"] = True
                    result["capture_status"] = name + "_limit"
                    break
            if result["capture_status"] != "ok":
                break
        if result["capture_status"] == "ok":
            try:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                result["capture_status"] = "timeout"
    except OSError as exc:
        result["capture_status"] = "spawn_error" if process is None else "io_error"
        result["diagnostic"] = scrub(str(exc))[:2000]
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            result["returncode"] = process.returncode
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        selector.close()
    for name in buffers:
        result[name]["captured_bytes"] = len(buffers[name])
    result["stderr"]["excerpt"] = scrub(bytes(buffers["stderr"]).decode("utf-8", errors="replace"))[:2000]
    return result, bytes(buffers["stdout"])


def reject_constant(value):
    raise ValueError("不允许非有限 JSON 数值：" + value)


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON 数值无法表示为有限浮点数。")
    return parsed


def nonempty(value):
    return isinstance(value, str) and bool(value) and not any(ord(c) < 32 for c in value)


def integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def actor(value):
    return value is None or (isinstance(value, dict) and nonempty(value.get("login")))


def valid_node(node, kind):
    if not isinstance(node, dict) or not nonempty(node.get("id")):
        return False
    if kind == "reviewThreads":
        if (type(node.get("isResolved")) is not bool or type(node.get("isOutdated")) is not bool
                or not isinstance(node.get("path"), str) or not nonempty(node.get("diffSide"))
                or "resolvedBy" not in node or not actor(node["resolvedBy"])):
            return False
        for field in ("line", "startLine", "originalLine", "originalStartLine"):
            if field not in node or (node[field] is not None and not integer(node[field], 1)):
                return False
        return "startDiffSide" in node and (node["startDiffSide"] is None or nonempty(node["startDiffSide"]))
    if (not isinstance(node.get("body"), str) or not nonempty(node.get("url"))
            or not nonempty(node.get("createdAt")) or not nonempty(node.get("updatedAt"))
            or "author" not in node or not actor(node["author"])):
        return False
    if kind == "reviews":
        if not nonempty(node.get("state")) or "submittedAt" not in node or "commit" not in node:
            return False
        if node["submittedAt"] is not None and not nonempty(node["submittedAt"]):
            return False
        commit = node["commit"]
        return commit is None or (isinstance(commit, dict) and isinstance(commit.get("oid"), str)
                                  and SHA.fullmatch(commit["oid"]) is not None)
    return True


def connection():
    return {"total_count": None, "count": 0, "pages": [], "page_info": None,
            "complete": False, "truncated": False, "reasons": []}


class Inspector:
    def __init__(self, args):
        self.args = args
        self.before = None
        self.stale = False
        self.node_scopes = {}
        self.data = {
            "schema_version": 1,
            "request": {"host": "github.com", "repo": args.repo, "pr": args.pr,
                        "timeout": args.timeout, "max_pages": args.max_pages,
                        "request_budget": REQUEST_BUDGET},
            "pull_request": {"before": None, "after": None, "observations": []},
            "conversation_comments": [], "reviews": [], "review_threads": [],
            "collection": {"status": "error", "started_at": now(), "finished_at": None,
                           "connections": {field: connection() for field, _, _ in OUTER},
                           "request_count": 0, "truncated": False,
                           "observation": "sequential_non_atomic",
                           "observation_note": "逐页观察；身份稳定与分页完毕不保证评论在同一历史时点的原子快照。"},
            "commands": [], "errors": [], "exit_code": 2,
        }

    def issue(self, code, scope, detail, conn=None, truncated=False):
        self.data["errors"].append({"code": code, "scope": scope, "detail": detail})
        if conn is not None:
            if code not in conn["reasons"]:
                conn["reasons"].append(code)
            conn["truncated"] = conn["truncated"] or truncated
        self.data["collection"]["truncated"] |= truncated

    def query(self, query, variables, scope, conn=None, final=False):
        # 给末尾身份回读保留一个名额；所有实际 gh 请求共享 100 次硬预算。
        if len(self.data["commands"]) >= REQUEST_BUDGET - (0 if final else 1):
            self.issue("request_budget_exhausted", scope, "已达全局请求预算，保留已有上下文。", conn, True)
            return None
        arguments = ["api", "--hostname", "github.com", "--method", "POST", "graphql", "-f", "query=" + query]
        for key, value in variables.items():
            if value is not None:
                arguments += ["-F" if key == "number" else "-f", key + "=" + str(value)]
        result, payload = bounded_gh(arguments, self.args.timeout)
        result["scope"] = scope
        self.data["commands"].append(result)
        self.data["collection"]["request_count"] = len(self.data["commands"])
        if result["capture_status"] != "ok":
            code = result["capture_status"]
            self.issue(code, scope, "gh 输出采集未完成。", conn, code.endswith("_limit"))
            return None
        if result["returncode"] != 0:
            self.issue("gh_error", scope, "gh 返回非零状态；未将其输出视为完整分页。", conn)
            return None
        try:
            payload = json.loads(payload, parse_float=finite_float, parse_constant=reject_constant)
        except (ValueError, UnicodeDecodeError, RecursionError):
            self.issue("invalid_json", scope, "gh 响应无法作为本工具可采集的 JSON 解码。", conn)
            return None
        if not isinstance(payload, dict):
            self.issue("invalid_shape", scope, "GraphQL 顶层必须为对象。", conn)
            return None
        if "errors" in payload:
            if not isinstance(payload["errors"], list):
                self.issue("invalid_shape", scope, "GraphQL errors 必须为数组。", conn)
                return None
            if payload["errors"]:
                self.issue("graphql_errors", scope, scrub(json.dumps(payload["errors"], ensure_ascii=False))[:2000], conn)
                return None
        if not isinstance(payload.get("data"), dict):
            self.issue("invalid_shape", scope, "GraphQL 缺少 data 对象。", conn)
            return None
        return payload["data"]

    def identity(self, repository, pr, scope, conn=None):
        if (not isinstance(repository, dict) or not nonempty(repository.get("id"))
                or not nonempty(repository.get("nameWithOwner")) or not isinstance(pr, dict)
                or not nonempty(pr.get("id")) or not integer(pr.get("number"), 1)
                or not nonempty(pr.get("url")) or not isinstance(pr.get("title"), str)
                or not nonempty(pr.get("state")) or not isinstance(pr.get("headRefOid"), str)
                or SHA.fullmatch(pr["headRefOid"]) is None):
            self.issue("identity_invalid", scope, "仓库或 PR 身份字段缺失或不合法。", conn)
            return None
        current = {field: pr[field] for field in ("id", "number", "url", "title", "state", "headRefOid")}
        current["repository"] = {"id": repository["id"], "nameWithOwner": repository["nameWithOwner"]}
        current["observed_at"] = now()
        self.data["pull_request"]["observations"].append({"scope": scope, "identity": current})
        try:
            parsed = urlsplit(pr["url"])
        except ValueError:
            self.issue("identity_invalid", scope, "PR URL 不合法。", conn)
            return None
        expected_path = "/" + self.args.repo + "/pull/" + str(self.args.pr)
        if (repository["nameWithOwner"].lower() != self.args.repo.lower() or pr["number"] != self.args.pr
                or parsed.scheme != "https" or parsed.netloc.lower() != "github.com"
                or parsed.path.lower() != expected_path.lower() or parsed.query or parsed.fragment):
            self.stale = True
            self.issue("requested_identity_mismatch", scope, "响应不是请求的 GitHub.com base 仓库及 PR。", conn)
            return None
        if self.before is not None:
            same = (current["id"] == self.before["id"]
                    and current["repository"]["id"] == self.before["repository"]["id"]
                    and current["headRefOid"].lower() == self.before["headRefOid"].lower()
                    and current["url"].lower() == self.before["url"].lower())
            if not same:
                self.stale = True
                self.issue("identity_changed", scope, "PR、仓库标识或 head 已变化，保留此前上下文。", conn)
                return None
            if (current["title"], current["state"]) != (self.before["title"], self.before["state"]):
                self.issue("pull_request_metadata_changed", scope, "观察期间 PR 标题或状态变化。", conn)
        return current

    def root_page(self, query, after, scope, conn=None, final=False):
        owner, name = self.args.repo.split("/")
        variables = {"owner": owner, "name": name, "number": self.args.pr}
        if after is not None:
            variables["after"] = after
        data = self.query(query, variables, scope, conn, final)
        if data is None:
            return None, None
        repository = data.get("repository")
        pr = repository.get("pullRequest") if isinstance(repository, dict) else None
        return pr, self.identity(repository, pr, scope, conn)

    def consume(self, page, kind, scope, conn, output, seen_ids, cursors, after):
        """只接受一页已绑定身份的具体评论连接；不重拉已耗尽的连接。"""
        if (not isinstance(page, dict) or not integer(page.get("totalCount"))
                or not isinstance(page.get("nodes"), list) or len(page["nodes"]) > 100
                or not isinstance(page.get("pageInfo"), dict)):
            self.issue("connection_shape_invalid", scope, "连接缺少 totalCount、nodes 或 pageInfo。", conn)
            return None
        info = page["pageInfo"]
        if (type(info.get("hasNextPage")) is not bool or "endCursor" not in info
                or (info["endCursor"] is not None and not nonempty(info["endCursor"]))
                or (info["hasNextPage"] and not nonempty(info["endCursor"]))):
            self.issue("page_info_invalid", scope, "分页结束标志或游标不合法。", conn)
            return None
        total = page["totalCount"]
        if conn["total_count"] is None:
            conn["total_count"] = total
        elif total != conn["total_count"]:
            self.issue("connection_total_changed", scope, "逐页 totalCount 发生变化。", conn)
        conn["pages"].append({"after": after, "totalCount": total,
                              "pageInfo": dict(info), "received_count": len(page["nodes"])})
        conn["page_info"] = dict(info)
        added = []
        for node in page["nodes"]:
            if not valid_node(node, kind):
                self.issue("node_shape_invalid", scope, "节点缺少必需原字段或类型不合法。", conn)
                continue
            if node["id"] in seen_ids or node["id"] in self.node_scopes:
                self.issue("duplicate_id", scope, "连接出现重复节点 ID，仅保留首个已核实节点。", conn)
                continue
            seen_ids.add(node["id"])
            self.node_scopes[node["id"]] = scope
            item = dict(node)
            output.append(item)
            added.append(item)
        conn["count"] = len(output)
        if len(output) > total:
            self.issue("connection_count_mismatch", scope, "收集数量超过本页 totalCount。", conn)
        end = info["endCursor"]
        if info["hasNextPage"]:
            if end in cursors or end == after or not page["nodes"]:
                self.issue("cursor_no_progress", scope, "游标循环或空页仍声明有后页。", conn)
            cursors.add(end)
        elif len(output) != total:
            self.issue("connection_count_mismatch", scope, "末页收集数量与 totalCount 不符。", conn)
        conn["complete"] = not info["hasNextPage"] and not conn["reasons"]
        return added

    def collect_thread(self, thread):
        scope = "thread:" + thread["id"]
        conn = connection()
        output = []
        original = thread.get("comments")
        thread["comments"] = {"totalCount": None, "pageInfo": None, "nodes": output, "collection": conn}
        seen_ids, cursors = set(), set()
        page, after = original, None
        while True:
            added = self.consume(page, "comments", scope, conn, output, seen_ids, cursors, after)
            thread["comments"]["totalCount"] = conn["total_count"]
            thread["comments"]["pageInfo"] = conn["page_info"]
            if added is None or conn["reasons"] or not conn["page_info"]["hasNextPage"]:
                break
            if len(conn["pages"]) >= self.args.max_pages:
                self.issue("page_limit", scope, "线程回复仍有后页，已达每连接页数上限。", conn, True)
                break
            if self.stale:
                self.issue("collection_stale", scope, "身份已漂移，未继续线程后页。", conn)
                break
            after = conn["page_info"]["endCursor"]
            data = self.query(THREAD_QUERY, {"threadId": thread["id"], "after": after}, scope, conn)
            node = data.get("node") if isinstance(data, dict) else None
            if data is None:
                break
            if (not isinstance(node, dict) or node.get("__typename") != "PullRequestReviewThread"
                    or node.get("id") != thread["id"]):
                self.stale = True
                self.issue("thread_identity_changed", scope, "线程节点缺失、类型或 ID 不符。", conn)
                break
            pr = node.get("pullRequest")
            repository = pr.get("repository") if isinstance(pr, dict) else None
            if self.identity(repository, pr, scope, conn) is None:
                break
            if not valid_node(node, "reviewThreads"):
                self.issue("node_shape_invalid", scope, "线程续页上下文字段缺失。", conn)
                break
            if any(node.get(key) != thread.get(key) for key in THREAD_META.split() if key not in ("{", "}", "login")):
                self.issue("thread_metadata_changed", scope, "线程位置或 resolved/outdated 上下文在续页时变化。", conn)
            page = node.get("comments")
            if conn["reasons"]:
                break

    def collect_outer(self, field, target):
        conn = self.data["collection"]["connections"][field]
        output = self.data[target]
        seen_ids, cursors = set(), set()
        after = None
        while not self.stale:
            pr, identity = self.root_page(OUTER_QUERIES[field], after, field, conn)
            if identity is None:
                break
            added = self.consume(pr.get(field), field, field, conn, output, seen_ids, cursors, after)
            if added is None:
                break
            if field == "reviewThreads":
                for thread in added:
                    # 此首屏与外层页一起取得，身份已核；即使后续漂移也保留它。
                    self.collect_thread(thread)
            if conn["reasons"] or not conn["page_info"]["hasNextPage"]:
                break
            if len(conn["pages"]) >= self.args.max_pages:
                self.issue("page_limit", field, "连接仍有后页，已达每连接页数上限。", conn, True)
                break
            after = conn["page_info"]["endCursor"]

    def run(self):
        _, before = self.root_page(IDENTITY_QUERY, None, "identity_before")
        if before is not None:
            self.before = before
            self.data["pull_request"].update({key: value for key, value in before.items() if key != "observed_at"})
            self.data["pull_request"]["before"] = before
            for field, target, _ in OUTER:
                if self.stale:
                    break
                self.collect_outer(field, target)
            _, after = self.root_page(IDENTITY_QUERY, None, "identity_after", final=True)
            if after is None:
                observations = self.data["pull_request"]["observations"]
                if observations and observations[-1]["scope"] == "identity_after":
                    after = observations[-1]["identity"]
            self.data["pull_request"]["after"] = after
        complete = (self.before is not None and self.data["pull_request"]["after"] is not None
                    and not self.data["errors"]
                    and all(item["complete"] for item in self.data["collection"]["connections"].values())
                    and all(thread["comments"]["collection"]["complete"] for thread in self.data["review_threads"]))
        status = "stale" if self.stale else ("complete" if complete else ("partial" if self.before else "error"))
        self.data["collection"]["status"] = status
        self.data["collection"]["finished_at"] = now()
        self.data["exit_code"] = 0 if complete else 2
        return self.data


def repository_arg(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", value):
        raise argparse.ArgumentTypeError("请使用显式 base 仓库 OWNER/REPO，不接受 URL 或 host。")
    if value.split("/")[1] in (".", ".."):
        raise argparse.ArgumentTypeError("仓库名不合法。")
    return value


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("必须为正整数。") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须为正整数。")
    return parsed


def pr_arg(value):
    parsed = positive_int(value)
    if parsed > 2147483647:
        raise argparse.ArgumentTypeError("PR 编号超出 GraphQL Int 范围。")
    return parsed


def timeout_arg(value):
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout 必须是有限正数秒。") from None
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("timeout 必须是有限正数秒。")
    return parsed


def main():
    parser = argparse.ArgumentParser(description="只读采集 GitHub.com PR 的三类审查输入；不评价或处理评论。")
    parser.add_argument("--repo", required=True, type=repository_arg, help="PR 所属的 base 仓库 OWNER/REPO")
    parser.add_argument("--pr", required=True, type=pr_arg, help="显式 PR 编号")
    parser.add_argument("--timeout", type=timeout_arg, default=30, help="每次 gh 命令的超时秒数，默认 30")
    parser.add_argument("--max-pages", type=positive_int, default=10, help="每个外层或线程内层连接页数上限，默认 10")
    args = parser.parse_args()
    result = Inspector(args).run()
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
