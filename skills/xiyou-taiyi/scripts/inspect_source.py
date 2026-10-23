#!/usr/bin/env python3
"""只读获取同一提交的 GitHub 源文件；不安装、执行或隐式保存文件。

2026-10-23 适配 OpenAI skill-installer 的显式仓库/路径及 GitHub 请求方法。
新增提交固定、字节核验与纯 JSON 输出；来源和 Apache-2.0 许可见
../references/lineage.md、../NOTICE.txt 和 ../licenses/skill-installer.txt。
"""

import argparse
import base64
import binascii
import hashlib
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
MAX_FILE_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PATHS = 16
TIMEOUT = 10


class SourceError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("不跟随 GitHub API 重定向，请核对原仓库名称")


def _request_json(endpoint):
    headers = {"User-Agent": "xiyou-source-inspector", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        if any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise SourceError("认证环境变量格式无效")
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + endpoint, headers=headers, method="GET")
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise SourceError(f"GitHub 请求失败：HTTP {exc.code}；请核对来源、权限或限额") from None
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
        raise SourceError("GitHub 连接失败或超时；未取得可用来源") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SourceError("GitHub 响应超过 2 MiB，未使用截断数据")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise SourceError("GitHub 响应不是有效 UTF-8 JSON") from None
    if type(data) is not dict:
        raise SourceError("GitHub 响应不是文件或元数据对象")
    return data


def _ref(value):
    if type(value) is not str or not value or len(value) > 1024:
        raise SourceError("ref 必须是非空分支、标签或提交")
    if (value == "@" or value.startswith(("/", "-")) or value.endswith(("/", "."))
            or ".." in value or "@{" in value
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in "~^:?*[\\" for c in value)
            or any(not part or part.startswith(".") or part.endswith(".lock") for part in value.split("/"))):
        raise SourceError("ref 不是有效的分支、标签或完整提交名称")
    return value


def _sha(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise SourceError("GitHub 未返回完整的 40 位提交或 blob SHA")
    return value


def inspect_source(repo, paths, ref=None):
    """返回完整来源对象；任一输入/响应无效即失败，不输出部分文件。"""
    if type(repo) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", repo) is None or repo.split("/")[-1] in (".", ".."):
        raise SourceError("repo 必须是 GitHub 的 owner/repo，不接受 URL")
    if type(paths) is not list or not 1 <= len(paths) <= MAX_PATHS:
        raise SourceError("请明确指定 1 至 16 个文件路径")
    for path in paths:
        if type(path) is not str or "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path) or any(part in ("", ".", "..") for part in path.split("/")):
            raise SourceError("path 必须是仓库内相对文件路径，不含穿越、空段或控制字符")
    if len(set(paths)) != len(paths):
        raise SourceError("文件路径重复")
    if ref is not None:
        _ref(ref)

    prefix = "/repos/" + repo
    metadata = _request_json(prefix)
    canonical = metadata.get("full_name")
    if type(canonical) is not str or canonical.lower() != repo.lower() or type(metadata.get("id")) is not int or metadata["id"] <= 0:
        raise SourceError("仓库身份与请求不一致或缺失")
    resolved_ref = _ref(metadata.get("default_branch") if ref is None else ref)
    commit = _sha(_request_json(prefix + "/commits/" + urllib.parse.quote(resolved_ref, safe="")).get("sha"))
    if re.fullmatch(r"[0-9a-fA-F]{40}", resolved_ref) and resolved_ref.lower() != commit:
        raise SourceError("请求的完整提交与 GitHub 响应不一致")

    files = []
    for path in paths:
        encoded_path = urllib.parse.quote(path, safe="/")
        entry = _request_json(prefix + "/contents/" + encoded_path + "?ref=" + commit)
        if entry.get("type") != "file" or "target" in entry or "submodule_git_url" in entry or entry.get("path") != path:
            raise SourceError("路径未返回对应文件；不接受目录、符号链接或子模块对象")
        if entry.get("encoding") != "base64" or type(entry.get("content")) is not str:
            raise SourceError("文件正文缺失或不是完整 base64 内容")
        size = entry.get("size")
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise SourceError("文件大小无效或超过 512 KiB")
        blob = _sha(entry.get("sha"))
        try:
            raw = base64.b64decode("".join(entry["content"].splitlines()), validate=True)
            content = raw.decode("utf-8")
        except (ValueError, binascii.Error, UnicodeError):
            raise SourceError("文件不是有效 base64/UTF-8 文本") from None
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if len(raw) != size or actual_blob != blob:
            raise SourceError("文件字节大小或 Git blob SHA 与响应不一致")
        files.append({"path": path, "blob_sha": blob, "sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": size, "content": content,
                      "source_url": f"https://github.com/{canonical}/blob/{commit}/{encoded_path}"})
    return {"repository": canonical, "repository_id": metadata["id"], "requested_ref": ref,
            "resolved_ref": resolved_ref, "commit": commit, "files": files}


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读获取同一 GitHub 提交的指定源文件及内容身份")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--path", required=True, action="append", help="相对文件路径；多个文件重复此参数")
    parser.add_argument("--ref", help="分支、标签或完整提交；省略时解析仓库默认分支")
    args = parser.parse_args(argv)
    try:
        result = inspect_source(args.repo, args.path, args.ref)
        output = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
        print(output)
    except (SourceError, UnicodeError, RecursionError):
        exc = sys.exc_info()[1]
        print(f"取源失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
