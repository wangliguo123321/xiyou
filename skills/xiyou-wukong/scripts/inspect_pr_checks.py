#!/usr/bin/env python3
"""只读采集显式 GitHub.com PR 的检查与 Actions 失败上下文。

2026-10-24：依据退休的 openai/skills gh-fix-ci 改写；增加稳定 JSON、
身份核对、状态分离与资源上限。固定原源及 Apache-2.0 见 ../NOTICE.txt。
日志和 CLI 输出仅作资料；本脚本不执行其中的内容。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

METADATA_BYTES = 2 * 1024 * 1024
STDERR_BYTES = 64 * 1024
MAX_FAILURES = 20
MAX_ROLLUP_PAGES = 3
ROLLUP_QUERY = """query CiCheckContext($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    pullRequest(number: $number) {
      number url headRefOid
      commits(last: 1) {
        nodes {
          commit {
            oid
            statusCheckRollup {
              contexts(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  __typename
                  ... on CheckRun { id name status conclusion detailsUrl checkSuite { app { slug } } }
                  ... on StatusContext { id context state targetUrl }
                }
              }
            }
          }
        }
      }
    }
  }
}"""
FIELDS = ("name", "state", "bucket", "link", "workflow", "startedAt", "completedAt")
FALLBACK_FIELDS = FIELDS + ("conclusion", "detailsUrl")
CATEGORIES = {
    "passed": {"success", "pass"},
    "failed": {"failure", "fail", "error", "cancel", "cancelled", "timed_out", "action_required", "startup_failure"},
    "pending": {"pending", "queued", "in_progress", "waiting", "requested", "expected"},
    "skipped": {"skipped", "skipping", "neutral"},
}
MARKERS = ("error", "fail", "traceback", "exception", "assert", "panic", "fatal", "timeout", "segmentation fault")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SHA = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


def scrub(text):
    """去 ANSI 及常见凭据；不承诺覆盖任意业务秘密。"""
    text = ANSI.sub("", text)
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b", "[REDACTED]", text)
    text = re.sub(r"(?i)(\bauthorization[ \t]*[:=][ \t]*)(?:(?:bearer|basic)[ \t]+)?[^\s,;]+", r"\1[REDACTED]", text)
    return re.sub(r"(?i)((?:token|password|secret)[ \t]*[:=][ \t]*)[^\s,;]+", r"\1[REDACTED]", text)


def now():
    return datetime.now(timezone.utc).isoformat()


def positive_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def reject_constant(value):
    raise ValueError("JSON 中不允许非有限数值：" + value)


def bounded_gh(arguments, timeout, stdout_limit):
    """同时排空两根管道，读入即限量；失败时回收本次进程组和管道。"""
    env = os.environ.copy()
    env.update(GH_HOST="github.com", GH_PROMPT_DISABLED="1", GH_PAGER="cat", NO_COLOR="1")
    for key in ("GH_DEBUG", "GH_FORCE_TTY"):
        env.pop(key, None)
    result = {"argv": ["gh", *arguments], "exit_code": None, "status": "ok", "stdout_bytes": 0, "stderr_bytes": 0}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(result["argv"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False, start_new_session=True, env=env)
        for pipe, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result["status"] = "timeout"
                break
            for key, _ in selector.select(min(remaining, 0.2)):
                name = key.data
                limit = stdout_limit if name == "stdout" else STDERR_BYTES
                chunk = os.read(key.fileobj.fileno(), min(65536, limit - len(buffers[name]) + 1))
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                result[name + "_bytes"] += len(chunk)
                buffers[name].extend(chunk[:max(0, limit - len(buffers[name]))])
                if result[name + "_bytes"] > limit:
                    result["status"] = name + "_limit"
                    break
            if result["status"] != "ok":
                break
        if result["status"] == "ok":
            try:
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                result["status"] = "timeout"
    except OSError as exc:
        result["status"] = "spawn_error" if process is None else "io_error"
        result["error"] = scrub(str(exc))[:2000]
    finally:
        if process is not None:
            # gh 可能留下继承管道的子进程；本次独立进程组在退出时统一回收。
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            result["exit_code"] = process.returncode
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        selector.close()
    result["stderr"] = scrub(bytes(buffers["stderr"]).decode("utf-8", errors="replace"))[:2000]
    return result, bytes(buffers["stdout"])


class Inspector:
    def __init__(self, args):
        self.args = args
        self.rollup_loaded = False
        self.rollup_contexts = []
        self.rollup_error = None
        self.snapshot_stale = False
        self.data = {
            "schema_version": 1, "request": {"host": "github.com", "repo": args.repo, "pr": args.pr},
            "pr": {"before": None, "after": None}, "ci_status": "unknown",
            "collection": {"status": "error", "started_at": now(), "finished_at": None},
            "summary": {key: 0 for key in (*CATEGORIES, "unknown")},
            "checks": [], "commands": [], "errors": [], "exit_code": 2,
        }

    def issue(self, code, detail):
        self.data["errors"].append({"code": code, "detail": detail})

    def call(self, arguments, log=False):
        result, payload = bounded_gh(arguments, self.args.timeout, self.args.max_log_bytes if log else METADATA_BYTES)
        self.data["commands"].append(result)
        return result, payload

    def api(self, endpoint):
        result, payload = self.call(["api", "--hostname", "github.com", "--method", "GET", endpoint])
        if result["status"] != "ok" or result["exit_code"] != 0:
            return None, result["status"] if result["status"] != "ok" else "gh_error"
        try:
            data = json.loads(payload, parse_constant=reject_constant)
        except (ValueError, UnicodeDecodeError):
            return None, "invalid_json"
        if not isinstance(data, dict):
            return None, "invalid_shape"
        return data, None

    def read_pr(self):
        data, error = self.api(f"repos/{self.args.repo}/pulls/{self.args.pr}")
        if error:
            return None, error
        base = data.get("base")
        repository = base.get("repo") if isinstance(base, dict) else None
        head = data.get("head")
        if (not isinstance(repository, dict) or not isinstance(repository.get("full_name"), str)
                or repository["full_name"].lower() != self.args.repo.lower()
                or not positive_id(repository.get("id")) or not positive_id(data.get("number"))
                or data["number"] != self.args.pr
                or not valid_pr_url(data.get("html_url"), self.args.repo, self.args.pr)
                or not isinstance(head, dict) or not isinstance(head.get("sha"), str) or not SHA.fullmatch(head["sha"])):
            return None, "pr_identity_invalid"
        merge = data.get("merge_commit_sha")
        if merge is not None and (not isinstance(merge, str) or not SHA.fullmatch(merge)):
            return None, "pr_identity_invalid"
        return {"number": data["number"], "url": data["html_url"], "repo_id": repository["id"],
                "repo": repository["full_name"], "head_sha": head["sha"],
                "merge_commit_sha": merge if isinstance(merge, str) and SHA.fullmatch(merge) else None,
                "observed_at": now()}, None

    def read_checks(self):
        fields = list(FIELDS)
        for attempt in range(2):
            result, payload = self.call(["pr", "checks", str(self.args.pr), "--repo", "github.com/" + self.args.repo,
                                         "--json", ",".join(fields)])
            if result["status"] != "ok":
                return None, result["status"]
            # gh 2.93 的 0/1/8 都可能携带合法检查 JSON；先解析资料再判断退出码。
            try:
                data = json.loads(payload, parse_constant=reject_constant)
            except (ValueError, UnicodeDecodeError):
                data = None
            if isinstance(data, list):
                if result["exit_code"] not in (0, 1, 8):
                    self.issue("checks_exit_unexpected", "保留可解析 JSON，但检查命令退出码超出 0/1/8。")
                return data, None
            message = result["stderr"]
            if not payload.strip() and "no checks reported" in message.lower():
                return [], None
            if attempt == 0 and "Available fields:" in message:
                available = set(re.findall(r"^\s*([A-Za-z][A-Za-z0-9]*)\s*$", message.split("Available fields:", 1)[1], re.M))
                fields = [field for field in FALLBACK_FIELDS if field in available]
                if "name" in fields and any(field in fields for field in ("state", "conclusion", "bucket")):
                    continue
            return None, "invalid_shape" if data is not None else "checks_unavailable_or_invalid_json"
        return None, "checks_unavailable"

    def read_rollup(self):
        """仅补证目标 PR 当前检查身份；不替换 gh checks 的清单与分类。"""
        if self.rollup_loaded:
            return self.rollup_contexts, self.rollup_error
        self.rollup_loaded = True
        owner, name = self.args.repo.split("/")
        cursor = None
        seen_cursors = set()
        for _ in range(MAX_ROLLUP_PAGES):
            arguments = ["api", "--hostname", "github.com", "--method", "POST", "graphql",
                         "-f", "query=" + ROLLUP_QUERY, "-f", "owner=" + owner,
                         "-f", "name=" + name, "-F", "number=" + str(self.args.pr)]
            if cursor is not None:
                arguments.extend(["-f", "after=" + cursor])
            result, payload = self.call(arguments)
            if result["status"] != "ok" or result["exit_code"] != 0:
                self.rollup_error = "rollup_" + (result["status"] if result["status"] != "ok" else "gh_error")
                break
            try:
                body = json.loads(payload, parse_constant=reject_constant)
            except (ValueError, UnicodeDecodeError):
                self.rollup_error = "rollup_invalid_json"
                break
            data = body.get("data") if isinstance(body, dict) else None
            repository = data.get("repository") if isinstance(data, dict) else None
            pull = repository.get("pullRequest") if isinstance(repository, dict) else None
            before = self.data["pr"]["before"]
            if (not isinstance(body, dict) or body.get("errors") or not isinstance(repository, dict)
                    or not isinstance(repository.get("nameWithOwner"), str)
                    or repository["nameWithOwner"].lower() != before["repo"].lower()
                    or not isinstance(pull, dict) or not positive_id(pull.get("number"))
                    or pull["number"] != before["number"] or not valid_pr_url(pull.get("url"), before["repo"], before["number"])):
                self.rollup_error = "rollup_identity_or_graphql_error"
                break
            if pull.get("headRefOid") != before["head_sha"]:
                self.snapshot_stale = isinstance(pull.get("headRefOid"), str) and bool(SHA.fullmatch(pull["headRefOid"]))
                self.rollup_error = "rollup_pr_head_changed" if self.snapshot_stale else "rollup_invalid_head"
                break
            commits = pull.get("commits")
            nodes = commits.get("nodes") if isinstance(commits, dict) else None
            commit = nodes[0].get("commit") if isinstance(nodes, list) and len(nodes) == 1 and isinstance(nodes[0], dict) else None
            rollup = commit.get("statusCheckRollup") if isinstance(commit, dict) else None
            contexts = rollup.get("contexts") if isinstance(rollup, dict) else None
            page = contexts.get("pageInfo") if isinstance(contexts, dict) else None
            entries = contexts.get("nodes") if isinstance(contexts, dict) else None
            if (not isinstance(commit, dict) or commit.get("oid") != before["head_sha"]
                    or not isinstance(entries, list) or not isinstance(page, dict)
                    or not isinstance(page.get("hasNextPage"), bool)
                    or any(not valid_rollup_context(entry) for entry in entries)
                    or len({entry["id"] for entry in self.rollup_contexts + entries}) != len(self.rollup_contexts) + len(entries)):
                self.rollup_error = "rollup_invalid_shape_or_commit"
                break
            self.rollup_contexts.extend(entries)
            if not page["hasNextPage"]:
                return self.rollup_contexts, None
            cursor = page.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                self.rollup_error = "rollup_invalid_cursor"
                break
            seen_cursors.add(cursor)
        else:
            self.rollup_error = "rollup_page_limit"
        return self.rollup_contexts, self.rollup_error

    def analyze_actions(self, check, target):
        run_id, job_id, url_attempt = target
        evidence = {"provider": "github_actions", "run_id": run_id, "job_id": job_id,
                    "url_attempt": url_attempt, "run": None, "job": None, "check_run": None,
                    "identity": {"status": "unverified", "head_relation": "unverified", "notes": []},
                    "log": {"status": "unavailable", "reason": None, "source": None, "snippet": None}}
        check["evidence"] = evidence
        identity = evidence["identity"]

        def unverified(reason):
            identity["notes"].append(reason)
            self.issue("actions_unverified", f"{check['name']}: {reason}")

        # 有 job ID 时先查该 job，不以当前 run 的其他 attempt 代替它。
        job = None
        attempt = url_attempt
        if job_id is None:
            unverified("run_scope_has_no_check_job_binding")
        if job_id is not None:
            job, error = self.api(f"repos/{self.args.repo}/actions/jobs/{job_id}")
            if error:
                unverified("job_metadata_" + error)
                evidence["log"]["reason"] = "job_metadata_unavailable"
                return
            evidence["job"] = select(job, ("id", "run_id", "run_attempt", "head_sha", "name", "status", "conclusion", "html_url", "check_run_url"))
            if (not positive_id(job.get("id")) or not positive_id(job.get("run_id"))
                    or job["id"] != job_id or job["run_id"] != run_id):
                unverified("job_run_identity_mismatch")
                evidence["log"]["reason"] = "identity_mismatch"
                return
            if job.get("run_attempt") is not None:
                if not positive_id(job["run_attempt"]) or (attempt is not None and attempt != job["run_attempt"]):
                    unverified("job_attempt_mismatch")
                    evidence["log"]["reason"] = "identity_mismatch"
                    return
                attempt = job["run_attempt"]
            elif attempt is None:
                unverified("job_attempt_unavailable_current_run_metadata_only")
            if job.get("name") != check["name"] or not check["name"]:
                unverified("check_job_name_mismatch")
                evidence["log"]["reason"] = "check_job_mismatch"
                return
            if job.get("html_url") is not None:
                provider, linked = actions_target(job["html_url"], self.args.repo)
                if provider != "github_actions" or not same_action_target(linked, target):
                    unverified("job_html_url_mismatch")
                    evidence["log"]["reason"] = "check_job_mismatch"
                    return
            if job.get("status") == "completed" and not conclusion_matches(check["raw"], job.get("conclusion")):
                unverified("check_job_conclusion_mismatch_or_unknown")
                evidence["log"]["reason"] = "check_job_mismatch"
                return
            if job.get("status") != "completed":
                unverified("failed_check_job_not_completed")
        endpoint = f"repos/{self.args.repo}/actions/runs/{run_id}"
        if attempt is not None:
            endpoint += f"/attempts/{attempt}"
        run, error = self.api(endpoint)
        if error:
            unverified("run_metadata_" + error)
            evidence["log"]["reason"] = "run_metadata_unavailable"
            return
        evidence["run"] = select(run, ("id", "run_attempt", "head_sha", "head_branch", "event", "status", "conclusion", "html_url", "pull_requests", "repository"))
        repository = run.get("repository")
        if (not positive_id(run.get("id")) or run["id"] != run_id or not isinstance(repository, dict)
                or repository.get("id") != self.data["pr"]["before"]["repo_id"]
                or not isinstance(repository.get("full_name"), str)
                or repository["full_name"].lower() != self.args.repo.lower()
                or not isinstance(run.get("head_sha"), str) or not SHA.fullmatch(run["head_sha"])
                or not positive_id(run.get("run_attempt")) or (attempt is not None and run["run_attempt"] != attempt)):
            unverified("run_repository_or_attempt_mismatch")
            evidence["log"]["reason"] = "identity_mismatch"
            return
        attempt = run["run_attempt"]
        relation = head_relation(run, self.data["pr"]["before"])
        identity["head_relation"] = relation
        if relation == "unverified":
            unverified("run_head_not_confirmed_for_pr")
        if job is not None and job.get("head_sha") is not None and job.get("head_sha") != run.get("head_sha"):
            unverified("job_head_mismatch")
            evidence["log"]["reason"] = "identity_mismatch"
            return
        if job is not None and job.get("status") == "completed":
            check_id = check_run_id(job.get("check_run_url"), self.args.repo)
            if check_id is None:
                unverified("job_check_run_url_unverified")
                evidence["log"]["reason"] = "check_binding_unverified"
                return
            actual, error = self.api(f"repos/{self.args.repo}/check-runs/{check_id}")
            if error:
                unverified("check_run_metadata_" + error)
                evidence["log"]["reason"] = "check_binding_unverified"
                return
            evidence["check_run"] = select(actual, ("id", "node_id", "name", "head_sha", "status", "conclusion", "details_url", "html_url", "app"))
            app = actual.get("app")
            provider, linked = actions_target(actual.get("details_url"), self.args.repo)
            if (not positive_id(actual.get("id")) or actual["id"] != check_id
                    or not isinstance(actual.get("node_id"), str) or not actual["node_id"]
                    or actual.get("name") != job["name"] or actual.get("head_sha") != run["head_sha"]
                    or actual.get("status") != job["status"] or actual.get("conclusion") != job.get("conclusion")
                    or not isinstance(app, dict) or not positive_id(app.get("id")) or app.get("slug") != "github-actions"
                    or (actual.get("url") is not None and check_run_id(actual["url"], self.args.repo) != check_id)
                    or provider != "github_actions" or not same_action_target(linked, target)):
                unverified("check_run_job_metadata_mismatch")
                evidence["log"]["reason"] = "check_binding_unverified"
                return
            contexts, error = self.read_rollup()
            if error:
                unverified(error)
                evidence["log"]["reason"] = "check_binding_unverified"
                return
            matches = [entry for entry in contexts if context_matches(check, entry, self.args.repo)]
            current = matches[0] if len(matches) == 1 else None
            suite = current.get("checkSuite") if isinstance(current, dict) else None
            source_app = suite.get("app") if isinstance(suite, dict) else None
            if (not isinstance(current, dict) or current.get("__typename") != "CheckRun"
                    or current.get("id") != actual["node_id"] or not isinstance(source_app, dict)
                    or source_app.get("slug") != "github-actions"):
                unverified("current_rollup_check_identity_ambiguous_or_mismatch")
                evidence["log"]["reason"] = "check_binding_unverified"
                return
            identity["current_check"] = current
            identity["rollup_head_sha"] = self.data["pr"]["before"]["head_sha"]
        identity["status"] = "verified" if not identity["notes"] else "unverified"
        source = {"scope": "job" if job_id is not None else "run", "run_id": run_id,
                  "job_id": job_id, "run_attempt": job.get("run_attempt") if job is not None else attempt,
                  "url": check["url"]}
        if job is not None:
            arguments = ["api", "--hostname", "github.com", "--method", "GET", f"repos/{self.args.repo}/actions/jobs/{job_id}/logs"]
            status = job.get("status")
        else:
            arguments = ["run", "view", str(run_id), "--repo", "github.com/" + self.args.repo,
                         "--attempt", str(attempt), "--log"]
            status = run.get("status")
        if status != "completed":
            evidence["log"].update(reason="job_or_run_not_completed", source=source, status="pending")
            self.issue("log_pending", f"{check['name']}: 对应 job/run 尚未完成。")
            return
        result, payload = self.call(arguments, log=True)
        log = log_evidence(payload, result, source, self.args.max_lines, self.args.context)
        evidence["log"] = log
        if log["status"] != "available":
            self.issue("log_" + log["status"], f"{check['name']}: {log['reason']}")

    def inspect(self):
        before, error = self.read_pr()
        if error:
            self.issue(error, "无法取得并核对显式仓库/PR/head 身份。")
            return self.finish()
        self.data["pr"]["before"] = before
        checks, error = self.read_checks()
        if error:
            self.issue(error, "检查采集失败；不能据此判断 CI 通过。")
        else:
            failures = 0
            for index, raw in enumerate(checks):
                category, problems = classify(raw)
                raw = raw if isinstance(raw, dict) else {}
                name = raw.get("name") if isinstance(raw.get("name"), str) else ""
                url = raw.get("link") or raw.get("detailsUrl") or ""
                check = {"index": index, "name": name, "state_category": category,
                         "url": url if isinstance(url, str) else "", "raw": raw, "issues": problems,
                         "evidence": None}
                self.data["checks"].append(check)
                self.data["summary"][category] += 1
                for problem in problems:
                    self.issue("check_invalid", f"检查 {index}: {problem}")
                provider, target = actions_target(check["url"], self.args.repo)
                if provider == "unverified":
                    self.issue("check_url_unverified", f"检查 {index}: URL 缺失、无效或 GitHub Actions 仓库不匹配。")
                    check["evidence"] = {"provider": "unverified", "url": check["url"]}
                elif category == "failed":
                    if provider == "external":
                        check["evidence"] = {"provider": "external", "url": check["url"], "note": "外部 CI 仅提供链接。"}
                    elif failures >= MAX_FAILURES:
                        self.issue("failure_limit", f"检查 {index}: 超出 {MAX_FAILURES} 个 Actions 失败项上限。")
                        check["evidence"] = {"provider": "github_actions", "log": {"status": "unavailable", "reason": "failure_limit"}}
                    else:
                        failures += 1
                        self.analyze_actions(check, target)
            counts = self.data["summary"]
            self.data["ci_status"] = ("no_checks" if not checks else "failed" if counts["failed"] else
                                      "unknown" if counts["unknown"] else "pending" if counts["pending"] else
                                      "passed" if counts["passed"] else "skipped")
        after, after_error = self.read_pr()
        self.data["pr"]["after"] = after
        if after_error:
            self.issue("pr_after_" + after_error, "采集后无法再次确认 PR 身份与 head。")
        if self.snapshot_stale or (after and (before["head_sha"] != after["head_sha"] or before["repo_id"] != after["repo_id"])):
            self.data["collection"]["status"] = "stale"
            self.issue("pr_changed", "采集中 PR head 或仓库身份发生变化，结果不可作为当前快照。")
        elif error:
            self.data["collection"]["status"] = "error"
        else:
            self.data["collection"]["status"] = "partial" if self.data["errors"] else "complete"
        return self.finish()

    def finish(self):
        status = self.data["collection"]["status"]
        ci = self.data["ci_status"]
        self.data["exit_code"] = (0 if ci == "passed" else 1) if status == "complete" and ci in ("passed", "failed") else 2
        self.data["collection"]["finished_at"] = now()
        return self.data


def select(data, fields):
    return {key: data[key] for key in fields if key in data}


def valid_pr_url(value, repo, number):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.netloc.lower() == "github.com" and not url.query and not url.fragment
                and url.path.rstrip("/").lower() == f"/{repo}/pull/{number}".lower())
    except ValueError:
        return False


def actions_target(value, repo):
    if not isinstance(value, str) or not value:
        return "unverified", None
    try:
        url = urlsplit(value)
    except ValueError:
        return "unverified", None
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        return "unverified", None
    if url.netloc.lower() != "github.com":
        return "external", None
    pattern = "/" + re.escape(repo) + r"/actions/runs/([1-9][0-9]*)(?:/attempts/([1-9][0-9]*))?(?:/job/([1-9][0-9]*))?/?"
    match = re.fullmatch(pattern, url.path, re.I)
    if not match:
        return "unverified", None
    return "github_actions", (int(match[1]), int(match[3]) if match[3] else None, int(match[2]) if match[2] else None)


def same_action_target(left, right):
    return (left is not None and right is not None and left[:2] == right[:2]
            and (left[2] is None or right[2] is None or left[2] == right[2]))


def check_run_id(value, repo):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        match = re.fullmatch(r"/repos/" + re.escape(repo) + r"/check-runs/([1-9][0-9]*)", url.path, re.I)
        if url.scheme == "https" and url.netloc.lower() == "api.github.com" and not url.query and not url.fragment and match:
            return int(match[1])
    except ValueError:
        pass
    return None


def conclusion_matches(raw, value, actions_only=True):
    """比较最终结论；bucket 只提供类别时不伪造更细的结论。"""
    if not isinstance(value, str):
        return False
    value = value.strip().lower()
    category, problems = classify(raw)
    allowed = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"} if actions_only else CATEGORIES["failed"]
    if problems or category != "failed" or value not in allowed:
        return False
    aliases = {"fail": "failure", "cancel": "cancelled"}
    for key in ("state", "conclusion"):
        expected = raw.get(key)
        if not expected or str(expected).strip().lower() == "completed":
            continue
        expected = expected.strip().lower()
        if aliases.get(expected, expected) != value:
            return False
    bucket = str(raw.get("bucket") or "").strip().lower()
    return not ((bucket == "cancel" and value != "cancelled") or (bucket == "fail" and value == "cancelled"))


def context_matches(check, context, repo):
    if context.get("__typename") == "CheckRun":
        if str(context.get("status") or "").lower() != "completed":
            return False
        name, url, conclusion = context.get("name"), context.get("detailsUrl"), context.get("conclusion")
    else:
        name, url, conclusion = context.get("context"), context.get("targetUrl"), context.get("state")
    left_provider, left = actions_target(url, repo)
    right_provider, right = actions_target(check["url"], repo)
    return (name == check["name"] and left_provider == right_provider == "github_actions"
            and same_action_target(left, right)
            and conclusion_matches(check["raw"], conclusion, actions_only=context.get("__typename") == "CheckRun"))


def valid_rollup_context(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
        return False
    if entry.get("__typename") == "CheckRun":
        if not {"name", "status", "conclusion", "detailsUrl", "checkSuite"}.issubset(entry):
            return False
        name, status, url = entry.get("name"), entry.get("status"), entry.get("detailsUrl")
        conclusion = entry["conclusion"]
        if (not isinstance(status, str) or status.lower() not in CATEGORIES["pending"] | {"completed"}
                or (conclusion is not None and (not isinstance(conclusion, str) or conclusion.lower() not in
                    {"success", "failure", "neutral", "cancelled", "skipped", "timed_out", "action_required", "startup_failure", "stale"}))
                or (status.lower() == "completed" and conclusion is None)):
            return False
    elif entry.get("__typename") == "StatusContext":
        if not {"context", "state", "targetUrl"}.issubset(entry):
            return False
        name, status, url = entry.get("context"), entry.get("state"), entry.get("targetUrl")
        if not isinstance(status, str) or status.lower() not in {"error", "expected", "failure", "pending", "success"}:
            return False
    else:
        return False
    return (isinstance(name, str) and bool(name) and isinstance(status, str) and bool(status)
            and (url is None or isinstance(url, str)))


def classify(raw):
    if not isinstance(raw, dict):
        return "unknown", ["检查不是对象。"]
    problems = []
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        problems.append("缺少有效 name。")
    categories = set()
    for key in ("state", "conclusion", "bucket"):
        value = raw.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            problems.append(f"{key} 不是字符串。")
            continue
        normalized = value.strip().lower()
        if normalized == "completed" and key == "state":
            continue
        found = next((name for name, values in CATEGORIES.items() if normalized in values), None)
        if found:
            categories.add(found)
        else:
            problems.append(f"未知 {key} 值：{value[:100]}")
    if not categories:
        problems.append("缺少可识别状态。")
    elif len(categories) > 1:
        problems.append("状态字段互相冲突。")
    category = "failed" if "failed" in categories else next(iter(categories)) if len(categories) == 1 and not problems else "unknown"
    return category, problems


def head_relation(run, pr):
    if run.get("head_sha") == pr["head_sha"]:
        return "pr_head"
    if pr["merge_commit_sha"] and run.get("head_sha") == pr["merge_commit_sha"]:
        return "pr_merge_commit"
    pulls = run.get("pull_requests")
    if isinstance(pulls, list):
        for pull in pulls:
            if not isinstance(pull, dict):
                continue
            base = pull.get("base")
            repo = base.get("repo") if isinstance(base, dict) else None
            if (positive_id(pull.get("number")) and pull["number"] == pr["number"]
                    and isinstance(repo, dict) and positive_id(repo.get("id")) and repo["id"] == pr["repo_id"]
                    and all(key not in repo or (isinstance(repo[key], str) and repo[key].rstrip("/").lower() == expected.lower())
                            for key, expected in (("full_name", pr["repo"]), ("name", pr["repo"].split("/")[1]),
                                                  ("url", f"https://api.github.com/repos/{pr['repo']}"),
                                                  ("html_url", f"https://github.com/{pr['repo']}")))
                    and all(key not in pull or (isinstance(pull[key], str) and pull[key].rstrip("/").lower() == expected.lower())
                            for key, expected in (("url", f"https://api.github.com/repos/{pr['repo']}/pulls/{pr['number']}"),
                                                  ("html_url", pr["url"])))
                    and isinstance(pull.get("head"), dict) and pull["head"].get("sha") == pr["head_sha"]):
                return "run_pull_request_head"
    return "unverified"


def log_evidence(payload, result, source, max_lines, context):
    log = {"status": "unavailable", "reason": None, "source": source,
           "bytes_observed": result["stdout_bytes"], "capture_status": result["status"],
           "capture_complete": False, "snippet": None}
    if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        log["reason"] = "zip_payload"
        return log
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        log["status"] = "truncated" if result["status"] != "ok" else "unavailable"
        log["reason"] = "non_utf8_or_binary_payload"
        return log
    if any(ord(char) < 32 and char not in "\n\r\t\x1b" for char in text):
        log["reason"] = "binary_payload"
        return log
    text = scrub(text)
    if not text.strip():
        log["reason"] = (result["status"] if result["status"] != "ok" else
                         "gh_error" if result["exit_code"] != 0 else "empty_log")
        return log
    if result["status"] != "ok":
        log.update(status="truncated", reason=result["status"])
    elif result["exit_code"] != 0:
        log.update(status="partial", reason="gh_error_with_partial_output")
    else:
        log.update(status="available", reason=None, capture_complete=True)
    lines = text.splitlines()
    hit = next((index for index in range(len(lines) - 1, -1, -1)
                if any(marker in lines[index].lower() for marker in MARKERS)), None)
    start = max(0, len(lines) - max_lines) if hit is None else max(0, hit - context)
    end = len(lines) if hit is None else min(len(lines), hit + context + 1)
    if end - start > max_lines:
        # 缩减双侧上下文，始终保留命中；极小 max_lines 也不可突破上限。
        start = max(start, hit - (max_lines - 1) // 2)
        end = min(end, start + max_lines)
    log["snippet"] = {"text": "\n".join(lines[start:end]), "start_line": start + 1, "end_line": end,
                      "captured_lines": len(lines), "selection": "tail" if hit is None else "last_marker_context",
                      "marker_line": None if hit is None else hit + 1,
                      "omitted_lines": len(lines) - (end - start), "heuristic_only": True}
    return log


def parse_args():
    parser = argparse.ArgumentParser(description="只读采集 GitHub.com 显式仓库与 PR 的 CI 上下文，输出 JSON。")
    parser.add_argument("--repo", required=True, help="OWNER/REPO；不接受 URL、本地路径或 Enterprise。")
    parser.add_argument("--pr", required=True, type=int, help="正整数 PR 编号。")
    parser.add_argument("--timeout", type=int, default=30, help="每条 gh 命令超时秒数（1—120）。")
    parser.add_argument("--max-log-bytes", type=int, default=2097152, help="每次日志 stdout 字节上限（1024—16777216）。")
    parser.add_argument("--max-lines", type=int, default=160, help="每个片段最多行数（1—500）。")
    parser.add_argument("--context", type=int, default=30, help="关键词前后文行数（0—250）。")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", args.repo) or args.repo.split("/")[1] in (".", ".."):
        parser.error("--repo 必须是显式 OWNER/REPO。")
    if args.pr <= 0 or not 1 <= args.timeout <= 120 or not 1024 <= args.max_log_bytes <= 16777216 or not 1 <= args.max_lines <= 500 or not 0 <= args.context <= 250:
        parser.error("编号或资源上限超出有效范围。")
    return args


def main():
    inspector = Inspector(parse_args())
    try:
        data = inspector.inspect()
    except Exception as exc:
        inspector.issue("internal_error", "采集异常：" + type(exc).__name__)
        inspector.data["collection"]["status"] = "error"
        data = inspector.finish()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
