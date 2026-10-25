#!/usr/bin/env python3
"""离线核对指定文档中的有限 CLI 片段与显式 TSV 快照。

2026-10-25 适配 wayglass-skill scripts/check.sh 的第 1 项命令检查。
固定来源与 MIT 许可见 ../references/lineage.md、../NOTICE.txt
及 ../licenses/cli-doc-check.txt；不执行文档命令或上游脚本。
"""

import argparse
import json
from pathlib import Path
import re
import sys


class InputError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def format_help(self):
        return super().format_help().replace("usage:", "用法：", 1)

    def error(self, message):
        self.exit(2, "参数无效：请使用 --help 查看必填参数与调用方式\n")


def read_text(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        raise InputError(f"无法读取 UTF-8 文件：{path}") from exc
    if "\0" in text:
        raise InputError(f"文件含无效的空字符：{path}")
    return text


def read_surface(path, command):
    known, groups = {}, set()
    for number, line in enumerate(read_text(path).splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 2:
            raise InputError(f"命令表第 {number} 行须为两列 TSV：{path}")
        words, flags = columns[0].split(" "), columns[1].split()
        if (words[0] != command
                or any(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", word) is None for word in words)
                or any(re.fullmatch(r"--?[^\s=]+", flag) is None for flag in flags)):
            raise InputError(f"命令表第 {number} 行路径或 flag 格式无效：{path}")
        entry = " ".join(words)
        known.setdefault(entry, set()).update(flags)
        for length in range(1, len(words)):
            groups.add(" ".join(words[:length]))
    if not known:
        raise InputError(f"命令表没有可用命令：{path}")
    if command not in known:
        raise InputError(f"命令表缺少根命令独立行：{command}；{path}")
    for entry in known:
        words = entry.split(" ")
        for length in range(1, len(words)):
            parent = " ".join(words[:length])
            if parent not in known:
                raise InputError(f"命令表缺少父路径独立行：{parent}；{path}")
    return known, groups


def extract_commands(text, command):
    """只抽取源检查器约定的 shell 围栏行和围栏外单反引号片段。"""
    start = re.compile(r"^" + re.escape(command) + r"[ \t]+[^\s`]")
    inline = re.compile(r"`(" + re.escape(command) + r"[ \t]+[^\s`][^`]*)`")
    fence, shell, pending = False, False, ""
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r"^[ \t]*```", line):
            shell = not fence and re.fullmatch(r"[ \t]*```(?:sh|bash|shell)[ \t]*", line) is not None
            fence = not fence
            pending = ""
            continue
        if fence and shell:
            line = pending + line
            pending = ""
            if re.search(r"\\[ \t]*$", line):
                pending = re.sub(r"\\[ \t]*$", "", line) + " "
                continue
            line = re.sub(r"^[ \t]*(?:\$ )?", "", line)
            if start.match(line):
                yield number, line
        elif not fence:
            for match in inline.finditer(line):
                yield number, match[1]


def check_command(raw, known, groups):
    # 保留源的有限词法；引号内容只作参数，未实现完整 shell 解析。
    text = re.sub(r'''"[^"]*"|'[^']*' ''', "ARG", raw, flags=re.VERBOSE)
    text = re.sub(r"[ \t]#.*$", "", text)
    words = re.split(r"[|;&>]", text, maxsplit=1)[0].split()
    path, index = words[0], 1
    while index < len(words) and path + " " + words[index] in known:
        path += " " + words[index]
        index += 1
    if path in groups and index < len(words) and re.match(r"[a-z]", words[index]):
        return [("unknown-command", path, words[index])]
    return [("unknown-flag", path, token.split("=", 1)[0])
            for token in words[index:]
            if token.startswith("-") and token.split("=", 1)[0] not in known.get(path, set())]


def check_docs(surface, command, docs):
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", command) is None:
        raise InputError("根命令须为不含空白或 shell 符号的单个名称")
    known, groups = read_surface(surface, command)
    result = {"checked_commands": 0, "diagnostics": []}
    for path in docs:
        for number, raw in extract_commands(read_text(path), command):
            result["checked_commands"] += 1
            for kind, recognized, token in check_command(raw, known, groups):
                result["diagnostics"].append({"file": path, "line": number, "kind": kind,
                                              "command": recognized, "token": token})
    return result


def main(argv=None):
    parser = Parser(description="只读核对指定文档的 CLI 片段与给定 TSV 快照；不联网或执行命令",
                    usage="%(prog)s --surface 路径 --command 名称 文档 [文档 ...]", add_help=False)
    parser._positionals.title = "文档"
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助并退出")
    parser.add_argument("--surface", required=True, metavar="路径", help="显式 TSV 命令/flag 快照")
    parser.add_argument("--command", required=True, metavar="名称", help="目标根命令名称")
    parser.add_argument("docs", nargs="+", metavar="文档", help="按输入顺序检查的 UTF-8 文档路径")
    args = parser.parse_args(argv)
    try:
        result = check_docs(args.surface, args.command, args.docs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except InputError as exc:
        print(f"输入无效：{exc}", file=sys.stderr)
        return 2
    return 1 if result["diagnostics"] else 0


if __name__ == "__main__":
    sys.exit(main())
