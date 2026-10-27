#!/usr/bin/env python3
"""将明确 PDF 的选定页面渲染为可复核 PNG；不判断视觉是否合格。

Apache-2.0；方法参考 OpenAI 历史公开 PDF Skill：
openai/skills@49f948faa9258a0c61caceaf225e179651397431/skills/.curated/pdf/SKILL.md
2026-10-28 本地新写适配：内容快照、明确选页、拒覆盖及逐页证据清单。
源目录已弃用；这不是上游脚本移植或当前官方运行保证。见 ../licenses/pdf.txt。
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zlib


MAX_INPUT = 25 * 1024 * 1024
MAX_SELECTED = 20
MAX_PNG = 32 * 1024 * 1024
TOOL_TIMEOUT = 15
TOTAL_TIMEOUT = 120


class RenderError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RenderError("invalid_arguments", message)


def select_pages(text, total):
    if text == "all":
        if total > MAX_SELECTED:
            raise RenderError("selection_limit", "超过20页的PDF需显式选择至多20页。")
        return list(range(1, total + 1))
    if len(text) > 1024:
        raise RenderError("invalid_pages", "选页表达式过长。")
    pages = set()
    for token in text.split(","):
        match = re.fullmatch(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?", token.strip())
        if not match:
            raise RenderError("invalid_pages", "选页应为all或正整数/连续范围，如1,3-5。")
        first = int(match[1])
        last = int(match[2] or match[1])
        if first > last or last > total:
            raise RenderError("invalid_pages", "页范围逆序或超出PDF总页数。")
        if last - first + 1 > MAX_SELECTED:
            raise RenderError("selection_limit", "每次最多选择20页。")
        pages.update(range(first, last + 1))
        if len(pages) > MAX_SELECTED:
            raise RenderError("selection_limit", "每次最多选择20页。")
    return sorted(pages)


def read_source(path):
    """只打开普通文件；读取的同一字节串随后写入私有渲染快照。"""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise RenderError("invalid_input", "输入必须是普通文件，不能是符号链接。")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(str(path), flags), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RenderError("invalid_input", "输入必须是普通文件。")
        data = stream.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise RenderError("input_limit", "输入超过25MiB。")
    return data


def run_tool(command, deadline, warnings):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RenderError("timeout", "本次工具执行总时限为120秒。")
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=min(TOOL_TIMEOUT, remaining),
            env=dict(os.environ, LC_ALL="C"),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RenderError("timeout", "工具执行超时（单次最多15秒，总计最多120秒）。")
    stderr = result.stderr.decode("utf-8", errors="replace")[:1000]
    if result.returncode:
        raise RenderError(
            "tool_failed",
            "{}退出{}：{}".format(Path(command[0]).name, result.returncode, stderr),
        )
    if stderr:
        warnings.append({"tool": Path(command[0]).name, "message": stderr})
    return result.stdout


def png_info(path, max_edge):
    """核当前 Poppler 生成的非交错8位PNG及其完整压缩扫描行。"""
    with path.open("rb") as stream:
        data = stream.read(MAX_PNG + 1)
    if len(data) > MAX_PNG or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RenderError("invalid_png", "输出不是限额内的PNG。")
    offset = 8
    header = None
    compressed = []
    ended = False
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + size
        if end > len(data):
            raise RenderError("invalid_png", "PNG块不完整。")
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise RenderError("invalid_png", "PNG块校验不符。")
        if header is None:
            if kind != b"IHDR" or size != 13:
                raise RenderError("invalid_png", "PNG缺少有效IHDR。")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IHDR":
            raise RenderError("invalid_png", "PNG重复IHDR。")
        if kind == b"IDAT":
            compressed.append(payload)
        if kind == b"IEND":
            if size or end != len(data):
                raise RenderError("invalid_png", "PNG结束块无效。")
            ended = True
            break
        offset = end
    if not header or not compressed or not ended:
        raise RenderError("invalid_png", "PNG缺少图像或结束块。")
    width, height, depth, color, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color)
    if (
        not (0 < width <= max_edge and 0 < height <= max_edge)
        or max(width, height) != max_edge
        or depth != 8 or channels is None
        or compression or filtering or interlace
    ):
        raise RenderError("invalid_png", "PNG尺寸或格式不符合本次Poppler渲染约定。")
    row_size = width * channels + 1
    expected = row_size * height
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(b"".join(compressed), expected + 1)
    if (
        len(pixels) != expected or not decoder.eof
        or decoder.unused_data or decoder.unconsumed_tail
        or any(pixels[row] > 4 for row in range(0, expected, row_size))
    ):
        raise RenderError("invalid_png", "PNG扫描行不完整或无效。")
    return {"width": width, "height": height, "sha256": hashlib.sha256(data).hexdigest()}


def main(argv=None):
    result = {
        "status": "error", "source": None, "total_pages": None,
        "requested_pages": None, "whole_document": False, "max_edge": None,
        "pages": [], "tools": {}, "visual_review": "not_performed",
        "errors": [], "warnings": [],
    }
    output = None
    created_output = False
    current_page = None
    deadline = time.monotonic() + TOTAL_TIMEOUT
    try:
        parser = Parser(description="将明确PDF选页渲染为PNG证据，不判断视觉是否合格。")
        parser.add_argument("--input", required=True, help="本地PDF普通文件")
        parser.add_argument("--output-dir", required=True, help="父目录已存在的全新输出目录")
        parser.add_argument("--pages", default="all", help="all或1,3-5（去重升序，最多20页）")
        parser.add_argument("--max-edge", type=int, default=1600, help="PNG最长边像素，256..2400")
        args = parser.parse_args(argv)
        result["max_edge"] = args.max_edge
        if not 256 <= args.max_edge <= 2400:
            raise RenderError("invalid_max_edge", "最长边必须为256..2400像素。")
        source = Path(args.input).expanduser().absolute()
        target = Path(args.output_dir).expanduser().absolute()
        if os.path.lexists(str(target)):
            raise RenderError("output_exists", "输出目录已存在；不覆盖已有文件或符号链接。")
        parent = target.parent.resolve(strict=True)
        if not parent.is_dir():
            raise RenderError("invalid_output", "输出父目录必须已存在。")
        output = parent / target.name
        data = read_source(source)
        result["source"] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name in ("pdfinfo", "pdftoppm"):
            executable = shutil.which(name)
            if not executable:
                raise RenderError("missing_tool", "缺少已安装工具：{}。".format(name))
            result["tools"][name] = {"path": str(Path(executable).resolve())}
        with tempfile.TemporaryDirectory(prefix="xiyou-pdf-render-") as temporary:
            snapshot = Path(temporary) / "input.pdf"
            snapshot.write_bytes(data)
            del data
            info = run_tool(
                [result["tools"]["pdfinfo"]["path"], str(snapshot)], deadline, result["warnings"]
            ).decode("utf-8", errors="replace")
            # 元数据可含换行及同名字段；歧义时不猜首项或末项。
            page_fields = re.findall(r"^Pages:([^\r\n]*)\r?$", info, re.MULTILINE)
            if len(page_fields) != 1:
                raise RenderError("ambiguous_pdf_info", "PDF页数字段缺失或重复，无法确认总页数。")
            count = re.fullmatch(r"[ \t]*([0-9]{1,10})[ \t]*", page_fields[0])
            if not count or int(count[1]) <= 0:
                raise RenderError("invalid_pdf_info", "未取得有效PDF总页数。")
            total = int(count[1])
            result["total_pages"] = total
            requested = select_pages(args.pages, total)
            result["requested_pages"] = requested
            result["whole_document"] = len(requested) == total
            output.mkdir(mode=0o700)
            created_output = True
            for page in requested:
                current_page = page
                prefix = output / "page-{:04d}".format(page)
                run_tool(
                    [result["tools"]["pdftoppm"]["path"], "-f", str(page), "-l", str(page),
                     "-singlefile", "-scale-to", str(args.max_edge), "-png", str(snapshot), str(prefix)],
                    deadline, result["warnings"],
                )
                image = prefix.with_suffix(".png")
                if image.is_symlink() or not image.is_file():
                    raise RenderError("missing_png", "未取得本次页面PNG。")
                dimensions = png_info(image, args.max_edge)
                result["pages"].append({"page": page, "file": image.name, **dimensions})
                current_page = None
        result["status"] = "complete"
    except RenderError as exc:
        result["errors"].append({"code": exc.code, "message": str(exc), "page": current_page})
    except (OSError, ValueError, struct.error, zlib.error) as exc:
        result["errors"].append({"code": "io_or_format_error", "message": str(exc)[:1000], "page": current_page})
    if result["errors"]:
        requested = result["requested_pages"] or []
        result["status"] = "partial" if 0 < len(result["pages"]) < len(requested) else "error"
    if created_output:
        try:
            with (output / "manifest.json").open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except OSError as exc:
            result["errors"].append({"code": "manifest_write_failed", "message": str(exc)[:1000], "page": None})
            requested = result["requested_pages"] or []
            result["status"] = "partial" if 0 < len(result["pages"]) < len(requested) else "error"
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return {"complete": 0, "partial": 2, "error": 1}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
