#!/usr/bin/env python3
"""将显式布局的有限流程图 JSON 制作为离线 SVG；不自动布局或导入 SVG。"""

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET


NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
FONT = "Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC, sans-serif"
MAX_BYTES = 1024 * 1024
FONT_SIZE = 16
LINE_HEIGHT = 22


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, required, optional, where):
    require(isinstance(value, dict), where + " 必须是对象")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    require(not missing, where + " 缺少字段：" + ", ".join(sorted(missing)))
    require(not extra, where + " 含未知字段：" + ", ".join(sorted(extra)))


def number(value, where):
    require(type(value) in (int, float) and math.isfinite(value), where + " 必须是有限数值")
    return value


def text(value, where, limit=2048):
    require(isinstance(value, str) and value.strip(), where + " 必须是非空字符串")
    require(len(value) <= limit, where + " 过长")
    require(all(c in "\n\t\r" or 0x20 <= ord(c) <= 0xD7FF or
                0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF
                for c in value), where + " 含 XML 不允许的字符")
    return value


def label(value, where):
    text(value, where, 512)
    lines = value.split("\n")
    require(len(lines) <= 6 and all(line.strip() for line in lines), where + " 需为 1–6 个非空行")
    require(not any(c in value for c in "\t\r"), where + " 仅用换行符分行，不用制表符或回车")
    return lines


def text_width(lines):
    # 仅作保守排版预算，真实字体宽度与重叠仍须查看渲染结果。
    return max(sum(0 if unicodedata.combining(c) else
                   1 if unicodedata.east_asian_width(c) in "WF" else 0.7
                   for c in line) for line in lines) * FONT_SIZE


def port(node, point):
    x, y, w, h = (node[k] for k in ("x", "y", "w", "h"))
    px, py = point
    if node["shape"] == "decision":
        return math.isclose(abs(px - x - w / 2) / (w / 2) +
                            abs(py - y - h / 2) / (h / 2), 1, abs_tol=1e-7)
    radius = min(h / 2, w / 2) if node["shape"] in ("start", "end") else 8
    return ((math.isclose(px, x, abs_tol=1e-7) or math.isclose(px, x + w, abs_tol=1e-7))
            and y + radius <= py <= y + h - radius or
            (math.isclose(py, y, abs_tol=1e-7) or math.isclose(py, y + h, abs_tol=1e-7))
            and x + radius <= px <= x + w - radius)


def validate(scene):
    fields(scene, {"title", "description", "width", "height", "nodes", "edges"}, set(), "图")
    text(scene["title"], "title")
    text(scene["description"], "description")
    width, height = (number(scene[k], k) for k in ("width", "height"))
    require(160 <= width <= 4096 and 160 <= height <= 4096, "画布宽高需在 160–4096 像素")
    require(isinstance(scene["nodes"], list) and 1 <= len(scene["nodes"]) <= 30,
            "nodes 需为 1–30 个节点的数组")
    require(isinstance(scene["edges"], list) and len(scene["edges"]) <= 60,
            "edges 需为至多 60 条连接的数组")
    nodes = {}
    for index, node in enumerate(scene["nodes"]):
        where = "nodes[{}]".format(index)
        fields(node, {"id", "shape", "x", "y", "w", "h", "label"}, set(), where)
        ident = node["id"]
        require(isinstance(ident, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", ident),
                where + ".id 需为字母开头的 1–48 位字母、数字、下划线或连字符")
        require(ident not in nodes, "重复节点 id：" + ident)
        require(node["shape"] in ("start", "process", "decision", "end"), where + ".shape 不支持")
        x, y, w, h = (number(node[k], where + "." + k) for k in ("x", "y", "w", "h"))
        require(w >= 48 and h >= 32, where + " 宽至少 48、高至少 32")
        require(x >= 8 and y >= 8 and x + w <= width - 8 and y + h <= height - 8,
                where + " 超出画布或不足 8 像素边距")
        lines = label(node["label"], where + ".label")
        usable_w, usable_h = (w / 2, h / 2) if node["shape"] == "decision" else (w, h)
        require(text_width(lines) <= usable_w - 16 and len(lines) * LINE_HEIGHT <= usable_h - 8,
                where + " 文字超出保守空间预算；请分行、放大节点或精简文字后再看图")
        nodes[ident] = node
    outgoing = {ident: 0 for ident in nodes}
    for index, edge in enumerate(scene["edges"]):
        where = "edges[{}]".format(index)
        fields(edge, {"from", "to", "points"}, {"label", "label_x", "label_y"}, where)
        require(isinstance(edge["from"], str) and edge["from"] in nodes and
                isinstance(edge["to"], str) and edge["to"] in nodes, where + " 引用了不存在的节点")
        points = edge["points"]
        require(isinstance(points, list) and 2 <= len(points) <= 32, where + ".points 需为 2–32 个坐标点")
        for point in points:
            require(isinstance(point, list) and len(point) == 2, where + " 每个点需为 [x,y]")
            px, py = (number(point[k], where + ".points") for k in (0, 1))
            require(8 <= px <= width - 8 and 8 <= py <= height - 8, where + " 路由超出 8 像素画布边距")
        for a, b in zip(points, points[1:]):
            require(a != b and (a[0] == b[0] or a[1] == b[1]), where + " 相邻点必须构成非零水平或竖直线段")
        require(port(nodes[edge["from"]], points[0]) and port(nodes[edge["to"]], points[-1]),
                where + " 首尾点需落在对应节点的直边或菱形轮廓上，避开圆角")
        outgoing[edge["from"]] += 1
        has_label = "label" in edge
        require(has_label == ("label_x" in edge) == ("label_y" in edge),
                where + " label、label_x、label_y 必须一起提供或一起省略")
        if nodes[edge["from"]]["shape"] == "decision":
            require(has_label, where + " 判断节点的每条出口都需要文字标签")
        if has_label:
            lines = label(edge["label"], where + ".label")
            lx, ly = (number(edge[k], where + "." + k) for k in ("label_x", "label_y"))
            half_w, half_h = text_width(lines) / 2 + 6, len(lines) * LINE_HEIGHT / 2 + 4
            require(8 <= lx - half_w and lx + half_w <= width - 8 and
                    8 <= ly - half_h and ly + half_h <= height - 8,
                    where + " 标签超出画布或不足 8 像素边距")
    for ident, count in outgoing.items():
        require(nodes[ident]["shape"] != "decision" or count >= 2,
                "判断节点 " + ident + " 需至少两条带文字标签的出口")


def element(parent, tag, **attributes):
    return ET.SubElement(parent, "{" + NS + "}" + tag,
                         {key.replace("_", "-"): str(value) for key, value in attributes.items()})


def draw_text(parent, value, x, y, **attributes):
    lines = value.split("\n")
    node = element(parent, "text", x=x, y=y, text_anchor="middle",
                   dominant_baseline="central", **attributes)
    for index, line in enumerate(lines):
        span = element(node, "tspan", x=x, dy=-(len(lines) - 1) * LINE_HEIGHT / 2 if index == 0 else LINE_HEIGHT)
        span.text = line


def render(scene):
    root = ET.Element("{" + NS + "}svg", {
        "width": str(scene["width"]), "height": str(scene["height"]),
        "viewBox": "0 0 {} {}".format(scene["width"], scene["height"]),
        "role": "img", "aria-labelledby": "graph-title graph-description",
        "font-family": FONT, "font-size": str(FONT_SIZE), "fill": "#17212b",
    })
    element(root, "title", id="graph-title").text = scene["title"]
    element(root, "desc", id="graph-description").text = scene["description"]
    defs = element(root, "defs")
    marker = element(defs, "marker", id="arrow", markerWidth=10, markerHeight=8,
                     refX=9, refY=4, orient="auto", markerUnits="userSpaceOnUse")
    element(marker, "path", d="M0 0 L10 4 L0 8 Z", fill="#425466")
    element(root, "rect", width=scene["width"], height=scene["height"], fill="#ffffff")
    connections = element(root, "g", id="connections", fill="none", stroke="#425466", stroke_width=2,
                          stroke_linejoin="round", stroke_linecap="round")
    for index, edge in enumerate(scene["edges"], 1):
        path = "M" + " L".join("{} {}".format(*point) for point in edge["points"])
        element(connections, "path", id="edge-{:03d}".format(index), d=path, marker_end="url(#arrow)")
    shapes = element(root, "g", id="nodes")
    for node in scene["nodes"]:
        group = element(shapes, "g", id="node-" + node["id"])
        x, y, w, h = (node[k] for k in ("x", "y", "w", "h"))
        if node["shape"] == "decision":
            points = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            element(group, "polygon", points=" ".join("{},{}".format(*p) for p in points),
                    fill="#fff6dc", stroke="#75551a", stroke_width=2)
        else:
            radius = min(w / 2, h / 2) if node["shape"] in ("start", "end") else 8
            element(group, "rect", x=x, y=y, width=w, height=h, rx=radius,
                    fill="#f0f5fa", stroke="#425466", stroke_width=2)
        draw_text(group, node["label"], x + w / 2, y + h / 2)
    # 标签最后绘制并带留白底板；是否遮住其他对象仍由制作者实际看图核查。
    captions = element(root, "g", id="connection-labels")
    for index, edge in enumerate(scene["edges"], 1):
        if "label" not in edge:
            continue
        lines, x, y = edge["label"].split("\n"), edge["label_x"], edge["label_y"]
        w, h = text_width(lines) + 12, len(lines) * LINE_HEIGHT + 8
        group = element(captions, "g", id="edge-label-{:03d}".format(index))
        element(group, "rect", x=x - w / 2, y=y - h / 2, width=w, height=h, rx=3, fill="#ffffff")
        draw_text(group, edge["label"], x, y)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "JSON 字段重复：" + key)
        value[key] = item
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="显式布局的 JSON 文件")
    parser.add_argument("--output", required=True, type=Path, help="新 SVG 文件；不覆盖已有路径")
    args = parser.parse_args()
    temporary = None
    try:
        with args.input.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, "输入 JSON 超过 1 MiB，请缩小图示")
        scene = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
        validate(scene)
        data = render(scene)
        # 同目录完整写入后独占发布，已有文件或符号链接不会被替换。
        fd, temporary = tempfile.mkstemp(prefix=".xiyou-flowchart-", dir=args.output.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.link(temporary, args.output)
        print("已生成 SVG：" + str(args.output))
        return 0
    except (ValueError, TypeError, OverflowError, RecursionError, OSError) as exc:
        print("制图失败：" + str(exc), file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            os.unlink(temporary)


if __name__ == "__main__":
    sys.exit(main())
