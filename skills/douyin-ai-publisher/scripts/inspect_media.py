#!/usr/bin/env python3
"""Pre-publish media QA for Douyin: parameters, loudness, black/silent spans,
keyframe sheet, phone feed preview with UI-overlay zones, and cover candidates.

Measures only. It never uploads, re-encodes the source, or decides for the user.
Requires ffmpeg and ffprobe on PATH. See references/media-qa.md for thresholds.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}
IMAGE_OK_EXT = {".jpg", ".jpeg", ".png", ".webp"}
GOOD_VCODEC = {"h264", "hevc"}
# Feed overlay zones on a 1080x1920 phone frame (editorial estimates, see media-qa.md).
FEED_W, FEED_H = 1080, 1920
ZONES = [  # x, y, w, h
    (0, 0, FEED_W, round(FEED_H * 0.07)),
    (0, round(FEED_H * 0.76), FEED_W, FEED_H - round(FEED_H * 0.76)),
    (round(FEED_W * 0.86), round(FEED_H * 0.40), FEED_W - round(FEED_W * 0.86), round(FEED_H * 0.36)),
]


class QAError(Exception):
    pass


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise QAError(f"{args[0]} failed ({proc.returncode}): {tail}")
    return proc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(out.stdout or "{}")


def fps_of(stream: dict) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        value = stream.get(key) or "0/0"
        num, _, den = value.partition("/")
        try:
            if float(den or 1):
                rate = float(num) / float(den or 1)
                if rate > 0:
                    return round(rate, 3)
        except ValueError:
            continue
    return None


def rotation_of(stream: dict) -> int:
    rot = stream.get("tags", {}).get("rotate")
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            rot = side["rotation"]
    try:
        return int(float(rot or 0)) % 360
    except ValueError:
        return 0


def aspect_label(w: int, h: int) -> str:
    ratio = w / h
    for name, value in (("9:16", 9 / 16), ("3:4", 3 / 4), ("1:1", 1.0), ("4:3", 4 / 3), ("16:9", 16 / 9)):
        if abs(ratio - value) / value < 0.02:
            return name
    return f"{w}:{h}"


def loudness_and_silence(path: Path, duration: float) -> dict:
    proc = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
        "-af", "ebur128=peak=true:framelog=verbose,silencedetect=noise=-50dB:d=1",
        "-f", "null", "-",
    ], check=False)
    err = proc.stderr
    if proc.returncode != 0:
        return {"error": "\n".join(err.strip().splitlines()[-3:])}

    def last(pattern: str) -> float | None:
        hits = re.findall(pattern, err)
        if not hits:
            return None
        value = hits[-1]
        return None if "inf" in value else float(value)

    summary = err[err.rfind("Summary:"):] if "Summary:" in err else err
    silences, start = [], None
    for kind, value in re.findall(r"silence_(start|end): (-?[\d.]+)", err):
        if kind == "start":
            start = max(0.0, float(value))
        elif start is not None:
            silences.append([round(start, 2), round(float(value), 2)])
            start = None
    if start is not None:
        silences.append([round(start, 2), round(duration, 2)])
    return {
        "integrated_lufs": last(r"I:\s+(-?[\d.]+|-inf) LUFS") if summary else None,
        "loudness_range_lu": last(r"LRA:\s+(-?[\d.]+) LU"),
        "true_peak_dbtp": last(r"Peak:\s+(-?[\d.]+|-inf) dBFS"),
        "silences": silences,
        "silence_total_seconds": round(sum(b - a for a, b in silences), 2),
    }


def opening_black(path: Path) -> list[list[float]]:
    proc = run([
        "ffmpeg", "-hide_banner", "-nostats", "-t", "3", "-i", str(path), "-an",
        "-vf", "blackdetect=d=0.1:pix_th=0.10", "-f", "null", "-",
    ], check=False)
    return [[float(a), float(b)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", proc.stderr)]


def frame_cmd(path: Path, t: float) -> list[str]:
    return ["-ss", f"{t:.3f}", "-i", str(path)]


def keyframe_sheet(path: Path, duration: float, dest: Path) -> list[float]:
    end = max(0.0, duration - 0.5)
    times = [t for t in (0.0, 0.5, 1.0, 2.0) if t < duration] + [round(duration / 2, 2), round(end, 2)]
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for t in times:
        args += frame_cmd(path, t)
    chains = [f"[{i}:v]scale=-2:360,setsar=1[f{i}]" for i in range(len(times))]
    chains.append("".join(f"[f{i}]" for i in range(len(times))) + f"hstack=inputs={len(times)}[out]")
    args += ["-filter_complex", ";".join(chains), "-map", "[out]", "-frames:v", "1", str(dest)]
    run(args)
    return times


def feed_preview(path: Path, t: float, dest: Path) -> None:
    boxes = ",".join(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red@0.35:t=fill" for x, y, w, h in ZONES)
    vf = (f"scale={FEED_W}:{FEED_H}:force_original_aspect_ratio=decrease,setsar=1,"
          f"pad={FEED_W}:{FEED_H}:(ow-iw)/2:(oh-ih)/2:black,{boxes}")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *frame_cmd(path, t), "-vf", vf, "-frames:v", "1", str(dest)])


def covers(path: Path, times: list[float], out_dir: Path, stem: str) -> list[dict]:
    result = []
    for t in times:
        tag = f"{t:.1f}".replace(".", "_")
        portrait = out_dir / f"{stem}_cover_{tag}_3x4.png"
        landscape = out_dir / f"{stem}_cover_{tag}_4x3.png"
        graph = ("[0:v]split=2[a][b];"
                 "[a]crop='min(iw,ih*3/4)':'min(ih,iw*4/3)'[p];"
                 "[b]crop='min(iw,ih*4/3)':'min(ih,iw*3/4)'[l]")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *frame_cmd(path, t), "-filter_complex", graph,
             "-map", "[p]", "-frames:v", "1", str(portrait), "-map", "[l]", "-frames:v", "1", str(landscape)])
        result.append({"time": t, "portrait_3x4": str(portrait), "landscape_4x3": str(landscape)})
    return result


def check(level: str, cid: str, message: str) -> dict:
    return {"level": level, "id": cid, "message": message}


def inspect_video(path: Path, info: dict, out_dir: Path, stem: str, cover_times: list[float] | None) -> dict:
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    checks: list[dict] = []
    if video is None:
        return {"video": None, "checks": [check("block", "no_video_stream", "没有可读的视频流")]}

    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    w, h = int(video.get("width") or 0), int(video.get("height") or 0)
    if rotation_of(video) in (90, 270):
        w, h = h, w
    fps = fps_of(video)
    vcodec = video.get("codec_name")
    report = {
        "duration_seconds": round(duration, 3),
        "container": info.get("format", {}).get("format_name"),
        "video": {"codec": vcodec, "width": w, "height": h, "aspect": aspect_label(w, h), "fps": fps,
                  "pix_fmt": video.get("pix_fmt"), "orientation": "vertical" if h > w else "horizontal" if w > h else "square"},
        "audio": None if audio is None else {"codec": audio.get("codec_name"), "channels": audio.get("channels"),
                                             "sample_rate": int(audio.get("sample_rate") or 0) or None},
    }
    if duration <= 0:
        checks.append(check("block", "no_duration", "读不到时长"))

    # format & resolution
    if h > w:
        if report["video"]["aspect"] != "9:16":
            checks.append(check("info", "aspect", f"竖屏 {report['video']['aspect']}，非标准 9:16，看推荐流预览确认裁切"))
    elif w > h:
        share = round((FEED_W * h / w) / FEED_H * 100)
        checks.append(check("warn", "landscape", f"横屏 {report['video']['aspect']}：推荐流中只占屏幕高度约 {share}%，主体和文字会明显变小"))
    else:
        checks.append(check("warn", "square", "方形画面：推荐流上下留黑较多"))
    short = min(w, h)
    if short < 720:
        checks.append(check("warn", "resolution_low", f"短边 {short}px，低于 720"))
    elif short < 1080:
        checks.append(check("warn", "resolution_720", f"短边 {short}px，低于 1080；不要放大冒充高清"))
    if fps is not None and fps < 24:
        checks.append(check("warn", "fps_low", f"帧率 {fps}，低于 24"))
    if vcodec not in GOOD_VCODEC:
        checks.append(check("warn", "video_codec", f"视频编码 {vcodec}，建议 H.264/HEVC"))

    # opening
    black = opening_black(path)
    report["opening_black"] = black
    lead = next((b for b in black if b[0] <= 0.05), None)
    if lead and lead[1] - lead[0] > 0.5:
        checks.append(check("warn", "opening_black", f"开头黑场 {lead[1] - lead[0]:.1f} 秒，可能导致快速划走"))
    checks.append(check("info", "opening_review", "人工看联系表前 4 帧：主体是否在 1 秒内出现且足够大"))

    # audio
    if audio is None:
        checks.append(check("warn", "no_audio", "没有音轨，确认是否有意"))
        report["loudness"] = None
    else:
        if audio.get("codec_name") != "aac":
            checks.append(check("info", "audio_codec", f"音频编码 {audio.get('codec_name')}，常见为 AAC"))
        loud = loudness_and_silence(path, duration)
        report["loudness"] = loud
        lufs, peak = loud.get("integrated_lufs"), loud.get("true_peak_dbtp")
        if lufs is None:
            checks.append(check("warn", "loudness_unknown", "无法测得响度"))
        elif lufs < -20:
            checks.append(check("warn", "too_quiet", f"整体响度 {lufs} LUFS，偏小（参考约 -14）"))
        elif lufs > -9:
            checks.append(check("warn", "too_loud", f"整体响度 {lufs} LUFS，偏吵（参考约 -14）"))
        if peak is not None and peak > -1.0:
            checks.append(check("warn", "true_peak", f"真峰值 {peak} dBTP，超过 -1，转码后可能失真"))
        long_sil = [s for s in loud.get("silences", []) if s[1] - s[0] >= 3]
        if long_sil:
            checks.append(check("info", "silence_spans", f"≥3 秒静音段：{long_sil}"))
        if duration and loud.get("silence_total_seconds", 0) > duration * 0.3:
            checks.append(check("warn", "silence_ratio", f"静音合计 {loud['silence_total_seconds']} 秒，超过时长 30%"))
    checks.append(check("info", "listening", "客观响度不能代替人工听审；承诺声音体验时必须有人听过"))

    # visuals
    sheet = out_dir / f"{stem}_sheet.png"
    report["keyframe_times"] = keyframe_sheet(path, duration, sheet)
    report["keyframe_sheet"] = str(sheet)
    feed = out_dir / f"{stem}_feed.png"
    feed_preview(path, round(duration * 0.3, 2), feed)
    report["feed_preview"] = str(feed)
    times = cover_times or [round(duration * p, 1) for p in (0.15, 0.35, 0.55, 0.75)]
    report["cover_candidates"] = covers(path, [t for t in times if 0 <= t < duration], out_dir, stem)
    report["checks"] = checks
    return report


def inspect_image(path: Path, info: dict, out_dir: Path, stem: str) -> dict:
    stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    checks: list[dict] = []
    if stream is None:
        return {"checks": [check("block", "unreadable_image", "图片无法读取")]}
    w, h = int(stream.get("width") or 0), int(stream.get("height") or 0)
    size_mb = round(path.stat().st_size / 1024 / 1024, 2)
    if path.suffix.lower() not in IMAGE_OK_EXT:
        checks.append(check("warn", "image_format", f"格式 {path.suffix}，图文上传页曾只支持 jpg/jpeg/png/webp（见 ui-notes.md）"))
    if size_mb > 50:
        checks.append(check("warn", "image_size", f"{size_mb}MB，超过曾观察到的单张 50MB 上限（见 ui-notes.md）"))
    ratio = max(w, h) / max(1, min(w, h))
    if ratio > 2:
        checks.append(check("warn", "image_ratio", f"长宽比 {w}:{h} 超过 1:2，可能被裁切"))
    checks.append(check("info", "image_review", "人工查看：主体、文字乱码、重复、裁切"))
    return {"image": {"codec": stream.get("codec_name"), "width": w, "height": h, "aspect": aspect_label(w, h), "size_mb": size_mb},
            "checks": checks}


def safe_stem(index: int, path: Path) -> str:
    stem = re.sub(r"[^\w.-]+", "_", path.stem, flags=re.UNICODE)[:40] or "media"
    return f"{index:02d}_{stem}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("media", nargs="+", help="视频或图片，按发布顺序")
    parser.add_argument("--out-dir", required=True, help="输出目录（报告、关键帧、封面候选）")
    parser.add_argument("--cover-times", help="封面候选时间点（秒，逗号分隔），默认取时长的 15/35/55/75%%")
    args = parser.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(json.dumps({"ok": False, "error": f"{tool} not found on PATH"}, ensure_ascii=False), file=sys.stderr)
            return 2
    out_dir = Path(args.out_dir).expanduser().resolve()
    skill_dir = Path(__file__).resolve().parent.parent
    if out_dir == skill_dir or skill_dir in out_dir.parents:
        print(json.dumps({"ok": False, "error": "out-dir must not be inside the Skill directory"}), file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    cover_times = [float(x) for x in args.cover_times.split(",")] if args.cover_times else None

    items, worst = [], "info"
    rank = {"info": 0, "warn": 1, "block": 2}
    for index, value in enumerate(args.media, 1):
        path = Path(value).expanduser().resolve()
        entry: dict = {"index": index, "path": str(path)}
        try:
            if not path.is_file():
                raise QAError("文件不存在")
            entry["sha256"] = sha256(path)
            entry["size_bytes"] = path.stat().st_size
            info = probe(path)
            stem = safe_stem(index, path)
            if path.suffix.lower() in IMAGE_EXT:
                entry["kind"] = "image"
                entry.update(inspect_image(path, info, out_dir, stem))
            else:
                entry["kind"] = "video"
                entry.update(inspect_video(path, info, out_dir, stem, cover_times))
        except (QAError, OSError, ValueError) as exc:
            entry.setdefault("kind", None)
            entry["checks"] = [check("block", "inspect_failed", str(exc))]
        for item in entry.get("checks", []):
            if rank[item["level"]] > rank[worst]:
                worst = item["level"]
        items.append(entry)

    kinds = {i.get("kind") for i in items if i.get("kind")}
    report = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tool": "douyin-ai-publisher/scripts/inspect_media.py",
        "kind": kinds.pop() if len(kinds) == 1 else ("mixed" if kinds else None),
        "overall": worst,
        "media": items,
        "note": "客观测量结果；画面和声音质量仍需人工判断。warn 由用户决定修改或照发。",
    }
    report_path = out_dir / "media_report.json"
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=out_dir, suffix=".tmp")
    with tmp:
        json.dump(report, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    os.replace(tmp.name, report_path)

    for entry in items:
        print(f"[{entry['index']}] {entry['path']}")
        for item in entry.get("checks", []):
            if item["level"] != "info":
                print(f"    {item['level'].upper():5} {item['message']}")
    print(f"overall: {worst}  report: {report_path}")
    return 1 if worst == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
