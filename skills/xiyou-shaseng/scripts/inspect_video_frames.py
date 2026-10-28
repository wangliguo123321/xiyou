#!/usr/bin/env python3
"""为本地 MP4/MOV 生成有界的首路视频 PNG/解码时间证据；不代替视觉验收。"""

import argparse
import hashlib
import json
import math
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
from decimal import Decimal, InvalidOperation, MAX_EMAX, MIN_EMIN, localcontext
from fractions import Fraction

INPUT_LIMIT = 64 * 1024 * 1024
PNG_LIMIT = 32 * 1024 * 1024
PIXEL_LIMIT = 8294400
LOG_LIMIT = 4 * 1024 * 1024
TOOL_TIMEOUT = 20
TOTAL_TIMEOUT = 120


class InspectionError(Exception):
    pass


def number(value, name):
    if len(value) > 128:
        raise InspectionError(name + " 数值过长")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise InspectionError(name + " 必须是有限数值")
    if not result.is_finite():
        raise InspectionError(name + " 必须是有限数值")
    return result


def ratio(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,9}/[1-9][0-9]{0,9}", value):
        raise InspectionError(name + " 未知或不是正分数")
    numerator, denominator = map(int, value.split("/"))
    if max(numerator, denominator) > 2147483647:
        raise InspectionError(name + " 超出工具时间基范围")
    return Fraction(numerator, denominator)


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not re.fullmatch(r"-?[0-9]{1,20}", str(value)):
        raise InspectionError(name + " 未知或不是整数")
    result = int(value)
    if result < minimum:
        raise InspectionError(name + " 越界")
    return result


def fraction_text(value):
    return str(value.numerator) + "/" + str(value.denominator)


def seconds_text(value):
    # 秒数仅便于阅读；PTS 与 time_base 的分数才是精确证据。
    return format(Decimal(value.numerator) / Decimal(value.denominator), ".12f")


def compare_decimal(exact, decimal):
    # 比较 n/d 与十进制时只乘小整数，避免极小指数展开为无界分母。
    with localcontext() as context:
        context.prec = len(decimal.as_tuple().digits) + len(str(exact.denominator)) + 2
        context.Emax, context.Emin = MAX_EMAX, MIN_EMIN
        scaled = decimal * exact.denominator
        return (Decimal(exact.numerator) > scaled) - (Decimal(exact.numerator) < scaled)


def duration_matches(observed, expected, tolerance):
    if compare_decimal(observed, expected) < 0:
        return compare_decimal(Fraction(expected) - observed, tolerance) <= 0
    largest, smallest = max(expected, tolerance), min(expected, tolerance)
    # 支持的 time_base 分母至多 INT32_MAX，所以正时长必然大于 1e-20。
    if largest == 0 or largest.adjusted() < -20:
        return False
    residual = observed - Fraction(largest)
    return residual <= 0 or compare_decimal(residual, smallest) <= 0


def run_tool(argv, deadline, output=None):
    """日志写私有临时文件，轮询限制时间、日志量和 PNG 体积。"""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InspectionError("超过总计 120 秒边界")
    timeout = min(TOOL_TIMEOUT, remaining)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        reason = None
        started = time.monotonic()
        try:
            while child.poll() is None:
                if time.monotonic() - started > timeout:
                    reason = "工具超时（每条至多 20 秒，总计至多 120 秒）"
                    break
                if os.fstat(stdout.fileno()).st_size > LOG_LIMIT or os.fstat(stderr.fileno()).st_size > LOG_LIMIT:
                    reason = "工具诊断超出 4 MiB 边界"
                    break
                if output is not None and output.exists() and output.stat().st_size > PNG_LIMIT:
                    reason = "PNG 超出 32 MiB 边界"
                    break
                time.sleep(0.02)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
        stdout.seek(0)
        stderr.seek(0)
        out = stdout.read(LOG_LIMIT + 1).decode("utf-8", errors="replace")
        err = stderr.read(LOG_LIMIT + 1).decode("utf-8", errors="replace")
    if reason or child.returncode != 0:
        raise InspectionError(json.dumps({"reason": reason or "工具执行失败", "argv": argv,
                                         "returncode": child.returncode, "stdout": out,
                                         "stderr": err}, ensure_ascii=False))
    if len(out.encode("utf-8")) > LOG_LIMIT or len(err.encode("utf-8")) > LOG_LIMIT:
        raise InspectionError("工具诊断超出 4 MiB 边界")
    return out, err


def snapshot(source, target, deadline):
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    descriptor = os.open(str(source), flags)
    with os.fdopen(descriptor, "rb") as original:
        before = os.fstat(original.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= INPUT_LIMIT:
            raise InspectionError("输入必须是非空普通文件，且至多 64 MiB；拒绝符号链接")
        digest = hashlib.sha256()
        size = 0
        with target.open("xb") as copied:
            while True:
                if time.monotonic() >= deadline:
                    raise InspectionError("输入快照超过总计 120 秒边界")
                block = original.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > INPUT_LIMIT:
                    raise InspectionError("输入复制中超过 64 MiB 边界")
                copied.write(block)
                digest.update(block)
        after = os.fstat(original.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if size != before.st_size or any(getattr(before, key) != getattr(after, key) for key in fields):
        raise InspectionError("输入在复制期间发生变化，无法绑定一致快照")
    target.chmod(0o400)
    return {"path": str(source), "size_bytes": size, "sha256": digest.hexdigest(),
            "binding": "all_media_commands_read_same_private_byte_snapshot",
            "source_stat": {key: getattr(before, key) for key in fields}}


def inspect_stream(probe):
    streams = probe.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "video":
        raise InspectionError("首路视频不存在或无法唯一观测")
    stream = streams[0]
    time_base = ratio(stream.get("time_base"), "视频 time_base")
    start_pts = integer(stream.get("start_pts"), "视频 start_pts")
    start_time = number(str(stream.get("start_time", "N/A")), "视频 start_time")
    if start_pts != 0 or start_time != 0:
        raise InspectionError("仅支持声明 start_pts=0 且 start_time=0 的首路视频")
    ticks = integer(stream.get("duration_ts"), "视频 duration_ts", 1)
    duration = ticks * time_base
    declared = number(str(stream.get("duration", "N/A")), "视频 duration")
    if not 0 < duration <= 120 or not 0 < declared <= 120:
        raise InspectionError("视频必须声明有限正时长，且至多 120 秒")
    # ffprobe 的十进制 duration 通常保留六位小数。
    if abs(Fraction(declared) - duration) > Fraction(1, 1000000):
        raise InspectionError("视频 duration 与 duration_ts/time_base 声明不一致")
    width = integer(stream.get("width"), "视频 width", 1)
    height = integer(stream.get("height"), "视频 height", 1)
    if width * height > PIXEL_LIMIT:
        raise InspectionError("视频单帧超过 8,294,400 像素")
    return stream, time_base, duration


def png_info(path):
    if not path.is_file() or not 0 < path.stat().st_size <= PNG_LIMIT:
        raise InspectionError("PNG 缺失、为空或超出 32 MiB")
    with path.open("rb") as image:
        header = image.read(33)
        if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[8:16] != b"\x00\x00\x00\rIHDR":
            raise InspectionError("输出不是完整 PNG 文件头")
        width, height = struct.unpack(">II", header[16:24])
        if not width or not height or width * height > PIXEL_LIMIT or header[24:29] != b"\x08\x02\x00\x00\x00":
            raise InspectionError("PNG 尺寸、RGB24 格式或像素量不符")
        image.seek(8)
        found_data = False
        while True:
            chunk_header = image.read(8)
            if len(chunk_header) != 8:
                raise InspectionError("PNG 缺少完整结束块")
            length, kind = struct.unpack(">I4s", chunk_header)
            if length > PNG_LIMIT:
                raise InspectionError("PNG 块越界")
            data, checksum = image.read(length), image.read(4)
            if len(data) != length or len(checksum) != 4 or zlib.crc32(kind + data) != struct.unpack(">I", checksum)[0]:
                raise InspectionError("PNG 块不完整或校验失败")
            found_data = found_data or (kind == b"IDAT" and length > 0)
            if kind == b"IEND":
                if length or not found_data or image.read(1):
                    raise InspectionError("PNG 结束块或图像数据无效")
                break
        image.seek(0)
        digest = hashlib.sha256()
        while True:
            block = image.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return width, height, digest.hexdigest(), path.stat().st_size


def decode_evidence(stderr, stdout, time_base, minimum_pts, duration, dimensions):
    lines = [line for line in stderr.splitlines() if "[showinfo@evidence @" in line]
    configs = [line for line in lines if "config in time_base:" in line]
    frames = [line for line in lines if re.search(r"\bn:\s*\d+\s+pts:", line)]
    if len(configs) != 1 or len(frames) != 1:
        raise InspectionError("必须有且仅有一条 showinfo 时间基和一帧解码证据；原始诊断：\n" + stderr)
    config = re.search(r"config in time_base:\s*([0-9]+/[0-9]+)", configs[0])
    frame = re.search(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:(\S+).*?\bfmt:(\S+).*?\bs:(\d+)x(\d+)\b", frames[0])
    if not config or not frame or ratio(config.group(1), "解码时间基") != time_base:
        raise InspectionError("解码 PTS/时间基未知或与声明不同；原始诊断：\n" + stderr)
    index, pts = int(frame.group(1)), int(frame.group(2))
    width, height = int(frame.group(5)), int(frame.group(6))
    actual = pts * time_base
    progress = re.findall(r"^frame=(\d+)\s*$", stdout, re.MULTILINE)
    if index != 0 or frame.group(4) != "rgb24" or not progress or progress[-1] != "1" or "progress=end" not in stdout:
        raise InspectionError("无法证明唯一 PNG 对应唯一解码帧；原始诊断：\n" + stderr + "\n" + stdout)
    if pts < minimum_pts or not 0 <= actual < duration or (width, height) != dimensions:
        raise InspectionError("实际帧 PTS/时间/尺寸不满足采样约定；原始诊断：\n" + stderr)
    return {"pts": pts, "time_base": config.group(1), "seconds_fraction": fraction_text(actual),
            "seconds": seconds_text(actual), "logged_pts_time": frame.group(3),
            "showinfo_config": configs[0], "showinfo_frame": frames[0],
            "association": "select_then_trim_one_then_rgb24_showinfo;one_logged_frame_and_one_png"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="本地普通 MP4/MOV 文件")
    parser.add_argument("--times", required=True, help="逗号分隔秒数，保持次序，至多十点")
    parser.add_argument("--output-dir", required=True, help="尚不存在的输出目录")
    parser.add_argument("--expected-duration", help="可选的明确约定秒数")
    parser.add_argument("--duration-tolerance", default="0.05", help="时长比较容差秒数，默认 0.05")
    args = parser.parse_args()
    deadline = time.monotonic() + TOTAL_TIMEOUT
    output = Path(os.path.abspath(args.output_dir))
    created_stat = None
    try:
        parts = args.times.split(",")
        if not 1 <= len(parts) <= 10 or any(not part.strip() for part in parts):
            raise InspectionError("--times 必须含一至十个非空时点")
        times = [number(part.strip(), "请求时点") for part in parts]
        if any(value < 0 or value >= 120 for value in times):
            raise InspectionError("请求时点须满足 0<=秒数<120，并且小于视频时长")
        tolerance = number(args.duration_tolerance, "时长容差")
        if not 0 <= tolerance <= 120:
            raise InspectionError("时长容差须在 0 至 120 秒内")
        expected = number(args.expected_duration, "预期时长") if args.expected_duration is not None else None
        if expected is not None and not 0 < expected <= 120:
            raise InspectionError("预期时长须在 0 至 120 秒内，且不能为零")
        source = Path(os.path.abspath(args.input))
        if source.suffix.lower() not in (".mp4", ".mov"):
            raise InspectionError("仅支持 .mp4/.mov 本地文件")
        binaries = {name: shutil.which(name) for name in ("ffprobe", "ffmpeg")}
        if not all(binaries.values()):
            raise InspectionError("需要已有 ffprobe 和 ffmpeg；不会安装工具")
        os.mkdir(str(output), 0o700)
        created_stat = output.stat()
        with tempfile.TemporaryDirectory(prefix="inspect-video-") as temporary:
            frozen = Path(temporary) / ("input" + source.suffix.lower())
            identity = snapshot(source, frozen, deadline)
            versions = {name: run_tool([binary, "-version"], deadline)[0].splitlines()[0]
                        for name, binary in binaries.items()}
            input_options = ["-protocol_whitelist", "file", "-format_whitelist", "mov", "-f", "mov",
                             "-enable_drefs", "0", "-use_absolute_path", "0", "-max_pixels", str(PIXEL_LIMIT)]
            probe_command = [binaries["ffprobe"], "-v", "error"] + input_options + [
                "-select_streams", "v:0", "-show_entries",
                "stream=index,codec_type,codec_name,width,height,start_pts,start_time,duration_ts,duration,time_base:format=format_name,start_time,duration",
                "-of", "json", str(frozen)]
            raw_probe, probe_stderr = run_tool(probe_command, deadline)
            if probe_stderr.strip():
                raise InspectionError("ffprobe 报告错误：\n" + probe_stderr)
            probe = json.loads(raw_probe)
            stream, time_base, duration = inspect_stream(probe)
            # 避免把任意极小十进制指数展开成无界大整数；它的首个正 PTS 阈值仍精确为 1。
            thresholds = []
            for requested in times:
                if compare_decimal(duration, requested) <= 0:
                    raise InspectionError("请求时点必须小于视频流时长")
                if requested == 0:
                    thresholds.append(0)
                elif compare_decimal(time_base, requested) > 0:
                    thresholds.append(1)
                else:
                    thresholds.append(math.ceil(Fraction(requested) / time_base))
                if thresholds[-1] > 2 ** 53:
                    raise InspectionError("PTS 阈值超过滤镜可精确表达的整数范围")
            comparison = {"status": "not_requested", "expected_seconds": None, "tolerance_seconds": None,
                          "observed_seconds_fraction": fraction_text(duration)}
            if expected is not None:
                matched = duration_matches(duration, expected, tolerance)
                difference = abs(Decimal(duration.numerator) / Decimal(duration.denominator) - expected)
                comparison.update(status="matched" if matched else "mismatched",
                                  expected_seconds=str(expected), tolerance_seconds=str(tolerance),
                                  absolute_difference_seconds_approx=str(difference))
                if not matched:
                    raise InspectionError("声明视频流时长不符合明确预期：" + json.dumps(comparison, ensure_ascii=False))
            frames = []
            for index, (requested, threshold) in enumerate(zip(times, thresholds), 1):
                image = output / ("frame_%02d.png" % index)
                graph = "select=gte(pts\\,%d),trim=end_frame=1,format=rgb24,showinfo@evidence" % threshold
                command = [binaries["ffmpeg"], "-nostdin", "-hide_banner", "-loglevel", "info", "-nostats", "-n",
                           "-xerror", "-copyts", "-filter_threads", "1", "-threads", "1", "-noautorotate"] + input_options + [
                    "-i", str(frozen), "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", graph,
                    "-frames:v", "1", "-fps_mode", "passthrough", "-c:v", "png", "-threads:v", "1",
                    "-fs", str(PNG_LIMIT), "-progress", "pipe:1", "-f", "image2", "-update", "1", str(image)]
                progress, diagnostic = run_tool(command, deadline, image)
                try:
                    width, height, digest, size = png_info(image)
                    actual = decode_evidence(diagnostic, progress, time_base, threshold, duration, (width, height))
                except InspectionError as failure:
                    raise InspectionError(str(failure) + "\n原始解码诊断：\n" + diagnostic + "\n" + progress)
                if (width, height) != (stream["width"], stream["height"]):
                    raise InspectionError("解码尺寸与首路视频声明不同")
                frames.append({"file": image.name, "requested_seconds": str(requested), "minimum_pts": threshold,
                               "actual": actual, "sha256": digest, "size_bytes": size, "width": width, "height": height,
                               "ffmpeg_argv": command, "ffmpeg_stderr": diagnostic, "ffmpeg_progress": progress})
            manifest = {"schema_version": 1, "status": "evidence_complete", "visual_review": "not_performed",
                        "scope": "local_mp4_mov_first_video_stream_zero_start",
                        "selection": "first_decoded_pts_at_or_after_request;no_seek;preserve_request_order",
                        "rotation": "noautorotate;coded_video_dimensions", "input": identity, "tools": versions,
                        "video_stream": stream, "duration_comparison": comparison, "frames": frames,
                        "probe": {"argv": probe_command, "observation": probe, "stderr": probe_stderr},
                        "limits": {"input_bytes": INPUT_LIMIT, "video_seconds": 120, "frame_pixels": PIXEL_LIMIT,
                                   "png_bytes": PNG_LIMIT, "points": 10, "tool_seconds": TOOL_TIMEOUT,
                                   "total_seconds": TOTAL_TIMEOUT}}
            if time.monotonic() >= deadline:
                raise InspectionError("超过总计 120 秒边界")
            with (output / "manifest.json").open("x", encoding="utf-8") as result:
                json.dump(manifest, result, ensure_ascii=False, indent=2, allow_nan=False)
                result.write("\n")
        print(json.dumps({"status": "evidence_complete", "manifest": str(output / "manifest.json"),
                          "visual_review": "not_performed"}, ensure_ascii=False))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        cleanup_error = None
        if created_stat is not None:
            try:
                current = output.lstat()
                if (current.st_dev, current.st_ino) != (created_stat.st_dev, created_stat.st_ino) or not stat.S_ISDIR(current.st_mode):
                    raise OSError("输出目录身份已变化，不删除他人目录")
                shutil.rmtree(output)
            except OSError as failure:
                cleanup_error = str(failure)
        print(json.dumps({"status": "failed", "error": str(error), "cleanup_error": cleanup_error,
                          "visual_review": "not_performed"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
