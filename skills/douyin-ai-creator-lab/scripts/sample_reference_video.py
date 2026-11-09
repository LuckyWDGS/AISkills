"""Create timestamped research contact sheets; never marks them as reviewed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def number(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if result < 0 or not result < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Actual local reference video, not a page URL")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; existing directories are not overwritten")
    parser.add_argument("--fps", type=int, choices=(3, 4, 5), default=4)
    parser.add_argument("--native", action="store_true", help="Keep all decoded source frames within an explicit interval")
    parser.add_argument("--start", type=number, default=0, help="Seconds from the video stream start")
    parser.add_argument("--end", type=number, help="Exclusive end in seconds from the video stream start")
    parser.add_argument("--width", type=int, default=176)
    parser.add_argument("--columns", type=int, default=8)
    parser.add_argument("--rows", type=int, default=6)
    parser.add_argument("--font", type=Path, help="Optional TrueType font for timestamps")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error("source must be an existing local video")
    if args.out.exists():
        parser.error("output directory exists; choose a new directory")
    if args.native and args.end is None:
        parser.error("--native requires --end to define the interval")
    if args.end is not None and args.end <= args.start:
        parser.error("--end must be greater than --start")
    if min(args.width, args.columns, args.rows) < 1:
        parser.error("width, columns and rows must be positive")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe must be available on PATH")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        parser.error("Pillow is required to compose contact sheets")
    probe_run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(args.source.resolve())],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    probe = json.loads(probe_run.stdout)
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    source_start = float(stream.get("start_time") or 0)
    stream_duration = stream.get("duration")
    duration = float(stream_duration) if stream_duration not in (None, "N/A") else float(probe["format"]["duration"]) - max(0, source_start)
    duration_basis = "video_stream_duration" if stream_duration not in (None, "N/A") else "format_duration_minus_positive_video_start"
    end = min(args.end if args.end is not None else duration, duration)
    if args.start >= end:
        parser.error("requested interval is outside the video")
    out = args.out.resolve()
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True)
    # select preserves source PTS and does not manufacture frames by interpolation.
    interval_start = source_start + args.start
    interval_end = source_start + end
    filters = [f"trim=start={interval_start}:end={interval_end}"]
    if not args.native:
        # Tiny tolerance avoids delaying an exact rational timestamp such as
        # 5/3 by a source frame due to floating-point subtraction.
        filters.append(f"select='gte(t-{interval_start}+1e-9,selected_n/{args.fps})'")
    filters.extend(["showinfo", f"scale={args.width}:-2"])
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-copyts", "-i", str(args.source.resolve()),
        "-an", "-vf", ",".join(filters), "-fps_mode", "vfr", "-q:v", "4",
        "-threads", "1", str(frames_dir / "frame-%06d.jpg"),
    ]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out / "ffmpeg.log").write_text(run.stderr, encoding="utf-8")
    if run.returncode:
        parser.exit(1, f"ffmpeg failed; inspect {out / 'ffmpeg.log'}\n")
    times = [float(t) for t in re.findall(r"\bpts_time:([-\d.eE+]+)", run.stderr)]
    playback_times = [t - source_start for t in times]
    frames = sorted(frames_dir.glob("frame-*.jpg"))
    if not frames or len(times) != len(frames):
        parser.exit(1, f"Frame/timestamp mismatch ({len(frames)} images, {len(times)} timestamps); inspect {out}\n")
    if any(b <= a for a, b in zip(times, times[1:])):
        parser.exit(1, "Source frame timestamps are not strictly increasing\n")
    font_candidates = [args.font] if args.font else [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next((p for p in font_candidates if p and p.is_file()), None)
    font = ImageFont.truetype(str(font_path), 14) if font_path else ImageFont.load_default()
    with Image.open(frames[0]) as first:
        thumb_height = first.height
    per_sheet = args.columns * args.rows
    sheet_records = []
    for offset in range(0, len(frames), per_sheet):
        group = frames[offset:offset + per_sheet]
        row_count = (len(group) + args.columns - 1) // args.columns
        cell_width, cell_height = args.width + 8, thumb_height + 27
        sheet = Image.new("RGB", (cell_width * args.columns, cell_height * row_count + 30), "#eee9df")
        draw = ImageDraw.Draw(sheet)
        draw.text((5, 5), f"{args.source.stem} | {'native' if args.native else str(args.fps) + 'fps target'} | playback {playback_times[offset]:.3f}-{playback_times[offset+len(group)-1]:.3f}s", font=font, fill="#222222")
        for index, path in enumerate(group):
            x, y = index % args.columns * cell_width + 4, index // args.columns * cell_height + 30
            with Image.open(path) as thumb:
                sheet.paste(thumb, (x, y))
            draw.text((x, y + thumb_height + 3), f"{playback_times[offset+index]:.3f}s", font=font, fill="#222222")
        sheet_path = out / f"sheet-{offset // per_sheet + 1:03d}.jpg"
        sheet.save(sheet_path, quality=88)
        sheet_records.append({"path": str(sheet_path), "start_index": offset, "frame_count": len(group), "first_time": times[offset], "last_time": times[offset+len(group)-1], "first_playback_time": playback_times[offset], "last_playback_time": playback_times[offset+len(group)-1]})
    digest = hashlib.sha256()
    with args.source.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    record = {
        "source": str(args.source.resolve()), "source_sha256": digest.hexdigest(),
        "source_duration_seconds": duration, "source_width": stream["width"], "source_height": stream["height"],
        "source_duration_basis": duration_basis, "source_start_time_seconds": source_start,
        "source_frame_rate_raw": stream.get("avg_frame_rate"),
        "requested_start": args.start, "requested_end": end,
        "sampling_mode": "native_interval" if args.native else "source_pts_selection",
        "target_frames_per_second": None if args.native else args.fps,
        "sample_times": times, "sample_playback_times": playback_times,
        "time_semantics": "sample_times retain source PTS; sample_playback_times and --start/--end are relative to the video stream start. Sheet labels use playback seconds.",
        "sample_count": len(frames), "sheets": sheet_records,
        "audio_review": "not_listened", "visual_review_status": "pending",
        "note": "Sheets and files exist; only a separate human/agent inspection record can mark which pages were actually examined. No audio analysis or shot-count inference is performed.",
    }
    (out / "sampling.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "frames": len(frames), "sheets": len(sheet_records), "time_range": [times[0], times[-1]], "visual_review_status": "pending"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
