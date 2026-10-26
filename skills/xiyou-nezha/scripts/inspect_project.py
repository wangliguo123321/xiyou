#!/usr/bin/env python3
"""只读提取显式项目根清单中的命令与声明入口；不执行项目代码。"""

from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import stat
import sys

try:
    import tomllib
except ImportError:
    tomllib = None

MAX_BYTES = 262144
SCOPE = "仅根目录 package.json 与 pyproject.toml；非递归、非项目完整性验证"


def result(root=None):
    return {"schema_version": 1, "root": root, "status": "complete",
            "manifests": [], "diagnostics": [], "scope": SCOPE}


def emit(output):
    print(json.dumps(output, ensure_ascii=True, indent=2))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        output = result()
        output["status"] = "error"
        output["diagnostics"].append({"path": None, "code": "usage-error",
                                      "message": message})
        emit(output)
        self.exit(2)


def mapping(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} 需要对象或表，不能当作空值忽略")
    return value


def string(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} 需要字符串，不能当作空值忽略")
    return value


def reject_json_constant(value):
    raise ValueError(f"JSON 不允许常量 {value}")


def extract(name, document):
    document = mapping(document, "清单根")
    item = {"path": name, "format": "package.json" if name == "package.json"
            else "pyproject.toml", "commands": [], "entry_points": []}
    if name == "package.json":
        scripts = mapping(document.get("scripts", {}), "scripts")
        for key, value in sorted(scripts.items()):
            item["commands"].append({"kind": "package_script", "name": key,
                                     "value": string(value, f"scripts.{key}"),
                                     "field": ["scripts", key]})
        for key in ("main", "module"):
            if key in document:
                item["entry_points"].append({"kind": "node_declared_path",
                                             "name": key,
                                             "value": string(document[key], key),
                                             "field": [key]})
        if "bin" in document:
            bins = document["bin"]
            if isinstance(bins, str):
                item["entry_points"].append({"kind": "node_declared_path",
                                             "name": "bin", "value": bins,
                                             "field": ["bin"]})
            else:
                for key, value in sorted(mapping(bins, "bin").items()):
                    item["entry_points"].append({"kind": "node_declared_path",
                                                 "name": key,
                                                 "value": string(value, f"bin.{key}"),
                                                 "field": ["bin", key]})
    else:
        project = mapping(document.get("project", {}), "project")
        scripts = mapping(project.get("scripts", {}), "project.scripts")
        for key, value in sorted(scripts.items()):
            item["entry_points"].append({"kind": "python_entrypoint", "name": key,
                                         "value": string(value, f"project.scripts.{key}"),
                                         "field": ["project", "scripts", key]})
    return item


def inspect_manifest(directory_fd, name, output):
    descriptor = None

    def diagnose(code, message):
        output["diagnostics"].append({"path": name, "code": code,
                                      "message": message})
        output["status"] = "partial"

    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            descriptor = os.open(name, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return
        except OSError as error:
            code = "symlink-skipped" if error.errno == errno.ELOOP else "read-error"
            diagnose(code, error.strerror or str(error))
            return
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            diagnose("non-regular-file", "只读取普通清单文件")
            return
        if info.st_size > MAX_BYTES:
            diagnose("size-limit", f"清单超过 {MAX_BYTES} 字节")
            return
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            diagnose("size-limit", f"读取时清单超过 {MAX_BYTES} 字节")
            return
        try:
            text = raw.decode("utf-8")
            document = (json.loads(text, parse_constant=reject_json_constant)
                        if name == "package.json" else tomllib.loads(text))
        except (UnicodeError, ValueError, RecursionError) as error:
            diagnose("parse-error", str(error))
            return
        try:
            output["manifests"].append(extract(name, document))
        except (ValueError, RecursionError) as error:
            diagnose("unsupported-field", str(error))
    except OSError as error:
        diagnose("read-error", error.strerror or str(error))
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main():
    parser = Parser(description="只读提取根清单中的开发命令和声明入口，不执行命令。")
    parser.add_argument("root", help="显式项目目录；不递归")
    args = parser.parse_args()
    output = result()
    if (sys.version_info < (3, 11) or tomllib is None or os.name != "posix"
            or not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
            or os.open not in os.supports_dir_fd):
        output["status"] = "error"
        output["diagnostics"].append({"path": None, "code": "platform-error",
                                      "message": "需要 Python 3.11+ 与支持目录 fd 的 POSIX 系统"})
        emit(output)
        return 2
    directory_fd = None
    try:
        root = Path(args.root).expanduser().resolve(strict=True)
        output["root"] = str(root)
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except (OSError, RuntimeError, ValueError) as error:
        output["status"] = "error"
        output["diagnostics"].append({"path": args.root, "code": "root-error",
                                      "message": str(error)})
    else:
        for name in ("package.json", "pyproject.toml"):
            inspect_manifest(directory_fd, name, output)
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    emit(output)
    return {"complete": 0, "partial": 1, "error": 2}[output["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
