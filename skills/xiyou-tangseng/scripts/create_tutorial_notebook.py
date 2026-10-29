#!/usr/bin/env python3
"""按显式路径新建待填写的教学 Notebook，不运行代码。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata


class InputError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError("参数不完整或无效，请查看 --help。")


def load_template():
    path = Path(__file__).resolve().parent.parent / "assets" / "tutorial-template.json"
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise InputError("教学模板超过 64 KiB。")
    notebook = json.loads(raw.decode("utf-8"))
    if not isinstance(notebook, dict) or set(notebook) != {"cells", "metadata", "nbformat", "nbformat_minor"}:
        raise InputError("教学模板根结构无效。")
    if notebook["nbformat"] != 4 or notebook["nbformat_minor"] != 5:
        raise InputError("教学模板必须使用 Notebook 4.5。")
    expected_metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    if notebook["metadata"] != expected_metadata:
        raise InputError("教学模板的 Python 3 元数据无效。")
    cells = notebook["cells"]
    types = ["markdown", "markdown", "code", "markdown", "code", "markdown", "code"]
    if not isinstance(cells, list) or len(cells) != len(types):
        raise InputError("教学模板必须保留七个有序单元格。")
    identifiers = set()
    for cell, kind in zip(cells, types):
        keys = {"id", "cell_type", "metadata", "source"}
        if kind == "code":
            keys |= {"execution_count", "outputs"}
        if not isinstance(cell, dict) or set(cell) != keys or cell["cell_type"] != kind:
            raise InputError("教学模板的单元格结构或顺序无效。")
        identifier = cell["id"]
        if not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier) is None or identifier in identifiers:
            raise InputError("教学模板的单元格 ID 无效或重复。")
        identifiers.add(identifier)
        if not isinstance(cell["metadata"], dict) or not isinstance(cell["source"], list) or not cell["source"] or not all(isinstance(line, str) for line in cell["source"]):
            raise InputError("教学模板的单元格内容无效。")
        if kind == "code" and (cell["execution_count"] is not None or cell["outputs"] != [] or any(line.strip() and not line.lstrip().startswith("#") for line in cell["source"])):
            raise InputError("代码骨架只能包含待填注释，计数须为 null、输出须为空。")
    if cells[0]["source"][0] != "# {{TITLE}}\n":
        raise InputError("教学模板缺少首行标题位置。")
    return notebook


def main():
    temporary = None
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--title", required=True, help="非空单行标题，最多 200 字符")
        parser.add_argument("--output", required=True, help="父目录已存在的绝对全新 .ipynb 路径")
        args = parser.parse_args()
        title = args.title
        if not title.strip() or len(title) > 200 or any(unicodedata.category(c) in {"Cc", "Zl", "Zp"} for c in title):
            raise InputError("标题须为非空单行文本，最多 200 字符，不能包含控制字符。")
        title.encode("utf-8")
        output = Path(args.output)
        if not output.is_absolute() or output.suffix != ".ipynb":
            raise InputError("输出须是绝对 .ipynb 路径。")
        if not output.parent.is_dir():
            raise InputError("输出父目录须已存在。")
        notebook = load_template()
        notebook["cells"][0]["source"][0] = "# " + title + "\n"
        content = (json.dumps(notebook, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        # 同目录临时文件写完后独占链接；目标已存在（含软链接）时绝不替换。
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".xiyou-notebook-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.link(temporary, output)
        temporary.unlink()
        temporary = None
        result = {
            "status": "created",
            "output": {"path": str(output), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()},
            "notebook": {"nbformat": 4, "nbformat_minor": 5, "cell_count": 7, "code_cell_count": 3},
            "execution": "not_performed",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, RecursionError) as error:
        message = str(error) if isinstance(error, InputError) else "参数、教学模板或文件操作失败；请核对路径与读写权限。"
        print(json.dumps({"status": "error", "message": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
