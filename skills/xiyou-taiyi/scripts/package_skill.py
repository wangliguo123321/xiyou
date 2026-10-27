#!/usr/bin/env python3
"""校验并导出显式本地技能目录，不安装或执行待打包代码。

整目录打包方法适配自 Anthropic skill-creator@dbd4588f9e1033efb41dad4bef2f7947c8993d44
的 scripts/package_skill.py（Copyright 2026 Anthropic, PBC.，Apache-2.0）。
复用本包 Ruby 校验器；有界读取、安全失败与 JSON 接口为本地改动。
来源及完整许可见 ../NOTICE.txt、../references/lineage.md、../licenses/skill-creator.txt。
跨文件读取为 sequential_non_atomic，不承诺多文件原子快照或恶意并发目录替换防护。
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

MAX_METADATA = 262_144
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 2048
MAX_ENTRIES = 4096
MAX_DEPTH = 64


class PackageError(Exception):
    def __init__(self, code, message, exit_code=1):
        self.code, self.message, self.exit_code = code, message, exit_code


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def safe_name(name, top_level=False):
    try:
        name.encode("utf-8")
    except UnicodeError:
        raise PackageError("unsafe_name", "文件名必须能表示为 UTF-8。") from None
    if (name in ("", ".", "..") or any(c in name for c in "/\\")
            or (top_level and len(name) > 1 and name[1] == ":")
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise PackageError("unsafe_name", "文件名含不安全的相对路径字符。")


def inside_source(directory, source):
    resolved = directory.resolve(strict=True)
    root = source.resolve(strict=True)
    return (resolved == root or root in resolved.parents
            or any(os.path.samefile(source, ancestor)
                   for ancestor in (resolved, *resolved.parents)))


def read_regular(path, limit, expected=None):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise PackageError("not_regular_file", "分发范围只接受普通文件，不接受符号链接或特殊文件。")
    if expected is not None and signature(before) != signature(expected):
        raise PackageError("source_changed", "源文件在读取期间发生变化。", 2)
    if before.st_size > limit:
        raise PackageError("byte_limit", "源文件超过元数据或总读取字节上限。")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        if signature(os.fstat(handle.fileno())) != signature(before):
            raise PackageError("source_changed", "源文件在读取期间发生变化。", 2)
        data = handle.read(before.st_size + 1)
        if (len(data) != before.st_size
                or signature(os.fstat(handle.fileno())) != signature(before)
                or signature(path.lstat()) != signature(before)):
            raise PackageError("source_changed", "源文件在读取期间发生变化。", 2)
    return data, before


def validate_metadata(content, temporary_parent):
    validator = Path(__file__).resolve().with_name("validate_skill.rb")
    if not validator.is_file():
        raise PackageError("validator_unavailable", "缺少本工具同目录的 Ruby 校验器。", 2)
    with tempfile.TemporaryDirectory(prefix="xiyou-package-", dir=temporary_parent) as shadow:
        (Path(shadow) / "SKILL.md").write_bytes(content)
        try:
            result = subprocess.run(["ruby", str(validator), "--", shadow],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=10, check=False)
        except subprocess.TimeoutExpired:
            raise PackageError("validator_timeout", "Ruby 元数据校验超时。", 2) from None
    if result.returncode:
        raise PackageError("metadata_invalid" if result.returncode == 1 else "validator_error",
                           "Ruby 元数据校验未通过；未回显输入正文。",
                           1 if result.returncode == 1 else 2)


def collect_files(source, metadata, metadata_stat, excluded):
    files, entry_count, total = [], 0, len(metadata)

    def walk(directory, parts):
        nonlocal entry_count, total
        before = directory.lstat()
        if not stat.S_ISDIR(before.st_mode):
            raise PackageError("not_directory", "源目录或分发子目录必须是普通目录。")
        with os.scandir(directory) as entries:
            ordered = []
            for entry in entries:
                entry_count += 1
                if entry_count > MAX_ENTRIES:
                    raise PackageError("entry_limit", "源目录条目超过 4096。")
                ordered.append(entry.name)
        for name in sorted(ordered):
            relative = (*parts, name)
            member = "/".join((source.name, *relative))
            if (name in (".git", "__pycache__", "node_modules", ".DS_Store")
                    or name.endswith(".pyc") or (not parts and name == "evals")):
                excluded.append({"path": member, "reason": "distribution_exclusion"})
                continue
            safe_name(name)
            if len(relative) > MAX_DEPTH:
                raise PackageError("depth_limit", "分发路径深度超过 64。")
            path = directory / name
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                walk(path, relative)
                continue
            if not stat.S_ISREG(info.st_mode):
                raise PackageError("not_regular_file", "分发范围含符号链接或特殊文件。")
            if len(files) >= MAX_FILES:
                raise PackageError("file_limit", "可分发文件超过 2048。")
            if relative == ("SKILL.md",):
                if signature(info) != signature(metadata_stat):
                    raise PackageError("source_changed", "SKILL.md 在校验后发生变化。", 2)
                data = metadata
            else:
                data, info = read_regular(path, MAX_BYTES - total, info)
                total += len(data)
            files.append((member, data, info.st_mode))
        if signature(directory.lstat()) != signature(before):
            raise PackageError("source_changed", "源目录在读取期间发生变化。", 2)

    walk(source, ())
    if not any(name == source.name + "/SKILL.md" for name, _data, _mode in files):
        raise PackageError("source_changed", "SKILL.md 在校验后消失。", 2)
    return files


def write_archive(output, files):
    with tempfile.TemporaryDirectory(prefix="xiyou-archive-", dir=output.parent) as private:
        staged = Path(private) / "archive.skill"
        with staged.open("x+b") as handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, content, mode in files:
                    member = zipfile.ZipInfo(name)
                    member.create_system = 3
                    member.external_attr = mode << 16
                    member.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(member, content)
            handle.flush()
            completed = os.fstat(handle.fileno())
            handle.seek(0)
            with zipfile.ZipFile(handle) as archive:
                if archive.namelist() != [item[0] for item in files]:
                    raise PackageError("archive_mismatch", "ZIP 成员与本次读取清单不一致。", 2)
                for name, content, mode in files:
                    member = archive.getinfo(name)
                    with archive.open(member) as entry:
                        observed = entry.read(len(content) + 1)
                    if observed != content or member.external_attr != mode << 16:
                        raise PackageError("archive_mismatch", "ZIP 字节或权限与本次读取不一致。", 2)
            handle.seek(0)
            digest, size = hashlib.sha256(), 0
            while size < completed.st_size:
                chunk = handle.read(min(64 * 1024, completed.st_size - size))
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            current = staged.lstat()
            if (size != completed.st_size or signature(current) != signature(completed)
                    or signature(os.fstat(handle.fileno())) != signature(completed)):
                raise PackageError("output_changed", "输出文件在回读期间发生变化。", 2)
        # 同一文件系统内原子独占发布；失败不回退，也从不删除最终路径。
        os.link(staged, output)
        return {"format": "zip", "path": str(output), "bytes": size, "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description="只读校验并导出一个本地技能目录为 ZIP 格式分发包。")
    parser.add_argument("--skill-dir", required=True, help="显式普通技能目录")
    parser.add_argument("--output", required=True, help="全新输出文件，父目录须已存在，通常使用 .skill 后缀")
    args = parser.parse_args()
    source, output = (Path(value).absolute() for value in (args.skill_dir, args.output))
    result = {"schema_version": 1, "status": "error", "exit_code": 2,
              "source": str(source), "output": str(output), "archive": None,
              "files": [], "excluded": [], "errors": []}
    try:
        if not stat.S_ISDIR(source.lstat().st_mode):
            raise PackageError("not_directory", "源根必须是普通目录，不接受符号链接。")
        source = source.resolve(strict=True)
        result["source"] = str(source)
        safe_name(source.name, top_level=True)
        if os.path.lexists(output):
            raise PackageError("output_exists", "输出路径已存在，未覆盖。", 2)
        if not output.parent.is_dir():
            raise PackageError("output_parent", "输出父目录须已存在且可访问。", 2)
        if inside_source(output.parent, source):
            raise PackageError("output_inside_source", "输出不得位于源目录或其子目录内。", 2)
        try:
            metadata, metadata_stat = read_regular(source / "SKILL.md", MAX_METADATA)
        except FileNotFoundError:
            raise PackageError("skill_missing", "源目录缺少普通 SKILL.md。") from None
        validate_metadata(metadata, output.parent)
        files = collect_files(source, metadata, metadata_stat, result["excluded"])
        result["files"] = [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                           for name, content, _mode in files]
        result["archive"] = write_archive(output, files)
        result.update(status="success", exit_code=0)
    except PackageError as exc:
        result.update(status="invalid" if exc.exit_code == 1 else "error", exit_code=exc.exit_code)
        result["errors"].append({"code": exc.code, "message": exc.message})
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        result["errors"].append({"code": "io_or_dependency", "message": "文件、ZIP 或 Ruby 依赖发生障碍，未完成打包。"})
    print(json.dumps(result, ensure_ascii=True))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
