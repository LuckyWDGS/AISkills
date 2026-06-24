from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .core import ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso


COMMON_GRIDS: tuple[tuple[int, int], ...] = (
    (2, 2),
    (4, 2),
    (4, 4),
    (8, 4),
    (8, 8),
    (16, 8),
    (16, 16),
)


@dataclass(slots=True)
class VideoMetadata:
    path: str
    width: int
    height: int
    duration_seconds: float
    fps: float
    frame_count: int
    source: str


@dataclass(slots=True)
class ClipRange:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    uses_full_video: bool


def parse_rational(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        try:
            return float(value)
        except ValueError:
            return 0.0


def parse_size(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must look like 512x512")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("size must contain integer width and height") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size width and height must be positive")
    return width, height


def parse_grid(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("*", "x").replace("×", "x")
    parts = normalized.split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("grid must look like 8x8")
    try:
        columns = int(parts[0])
        rows = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("grid must contain integer columns and rows") from exc
    if columns <= 0 or rows <= 0:
        raise argparse.ArgumentTypeError("grid columns and rows must be positive")
    return columns, rows


def parse_time(value: str) -> float:
    text = str(value).strip()
    if not text:
        raise argparse.ArgumentTypeError("time value cannot be empty")
    try:
        if ":" not in text:
            seconds = float(text)
        else:
            parts = text.split(":")
            if len(parts) > 3:
                raise ValueError
            values = [float(part) for part in parts]
            seconds = 0.0
            for part in values:
                seconds = seconds * 60.0 + part
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time must be seconds, MM:SS, or HH:MM:SS") from exc
    if seconds < 0:
        raise argparse.ArgumentTypeError("time must be >= 0")
    return round(seconds, 6)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def nearest_power_of_two(value: int) -> int:
    if value <= 0:
        raise ValueError("value must be greater than 0")
    lower = 1 << (value.bit_length() - 1)
    if lower == value:
        return value
    upper = lower << 1
    if value - lower <= upper - value:
        return lower
    return upper


def atlas_size_for_mode(raw_size: tuple[int, int], mode: str) -> tuple[int, int]:
    if mode == "raw":
        return raw_size
    if mode == "nearest-power-of-two":
        return nearest_power_of_two(raw_size[0]), nearest_power_of_two(raw_size[1])
    raise ValueError(f"Unknown atlas size mode: {mode}")


def executable_names(name: str) -> tuple[str, ...]:
    if sys.platform.startswith("win"):
        return (f"{name}.exe", name)
    return (name, f"{name}.exe")


def local_ffmpeg_roots() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    candidates = (
        root / "Tools" / "FFmpeg",
        root / "tools" / "ffmpeg",
        root / "Tools" / "ffmpeg",
        root / "tools" / "FFmpeg",
    )
    seen: set[str] = set()
    roots: list[Path] = []
    for candidate in candidates:
        key = str(candidate.resolve())
        if key not in seen:
            roots.append(candidate)
            seen.add(key)
    return roots


def find_executable_under(directory: Path, name: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    for filename in executable_names(name):
        for candidate in (directory / filename, directory / "bin" / filename):
            if candidate.is_file():
                return candidate
    for filename in executable_names(name):
        matches = sorted(path for path in directory.rglob(filename) if path.is_file())
        if matches:
            return matches[0]
    return None


def archive_candidates(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    patterns = ("*.zip", "*.7z", "*.tar", "*.tar.gz", "*.tgz", "*.tar.xz", "*.xz")
    seen: set[str] = set()
    archives: list[Path] = []
    for pattern in patterns:
        for path in directory.rglob(pattern):
            if path.is_file():
                key = str(path.resolve())
                if key not in seen:
                    archives.append(path)
                    seen.add(key)
    return sorted(archives)


def is_archive_file(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith((".zip", ".7z", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".xz"))


def local_ffmpeg_state(name: str, roots: list[Path] | None = None) -> str:
    roots = roots or local_ffmpeg_roots()
    existing_roots = [root for root in roots if root.exists()]
    if not existing_roots:
        looked = ", ".join(str(root) for root in roots)
        return f"Looked in local FFmpeg folders but none exist: {looked}."
    archives: list[Path] = []
    for root in existing_roots:
        archives.extend(archive_candidates(root))
    root_text = ", ".join(str(root) for root in existing_roots)
    if archives:
        shown = ", ".join(str(path) for path in archives[:5])
        extra = f" (and {len(archives) - 5} more)" if len(archives) > 5 else ""
        return (
            f"Looked in local FFmpeg folders: {root_text}. "
            f"Found archive(s) but no {name} executable: {shown}{extra}. "
            "Extract or download a Windows binary build that contains bin/ffmpeg.exe and bin/ffprobe.exe."
        )
    return f"Looked in local FFmpeg folders but found no {name} executable: {root_text}."


def resolve_path_or_directory(name: str, value: str) -> Path | None:
    path = Path(value).expanduser()
    if path.exists():
        if path.is_file():
            if is_archive_file(path):
                return None
            return path.resolve()
        if path.is_dir():
            return find_executable_under(path, name)
    found = shutil.which(value)
    if found:
        return Path(found).resolve()
    return None


def find_local_executable(name: str) -> Path | None:
    for root in local_ffmpeg_roots():
        found = find_executable_under(root, name)
        if found:
            return found.resolve()
    return None


def sibling_executable(peer: Path, name: str) -> Path | None:
    for filename in executable_names(name):
        sibling = peer.with_name(filename)
        if sibling.is_file():
            return sibling.resolve()
        bin_sibling = peer.parent / "bin" / filename
        if bin_sibling.is_file():
            return bin_sibling.resolve()
    return None


def resolve_executable(name: str, override: str | None, *, peer_override: str | None = None) -> str:
    if override:
        resolved_override = resolve_path_or_directory(name, override)
        if resolved_override:
            return str(resolved_override)
        path = Path(override).expanduser()
        if path.exists() and path.is_dir():
            raise RuntimeError(f"{name} was not found under {path}. {local_ffmpeg_state(name, [path])}")
        if path.exists() and path.is_file() and is_archive_file(path):
            raise RuntimeError(
                f"{name} was given an archive, not an executable: {path}. "
                "Extract or download a Windows binary build that contains bin/ffmpeg.exe and bin/ffprobe.exe."
            )
        raise RuntimeError(f"{name} was not found at {override}")
    if name == "ffprobe":
        peer_candidates: list[Path] = []
        if peer_override:
            resolved_peer = resolve_path_or_directory("ffmpeg", peer_override)
            if resolved_peer:
                peer_candidates.append(resolved_peer)
        local_peer = find_local_executable("ffmpeg")
        if local_peer:
            peer_candidates.append(local_peer)
        found_ffmpeg = shutil.which("ffmpeg")
        if found_ffmpeg:
            peer_candidates.append(Path(found_ffmpeg))
        for peer in peer_candidates:
            sibling = sibling_executable(peer, "ffprobe")
            if sibling:
                return str(sibling)
    local = find_local_executable(name)
    if local:
        return str(local)
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    local_state = local_ffmpeg_state(name)
    raise RuntimeError(f"{name} was not found on PATH. {local_state}")


def format_subprocess_error(tool_name: str, command: list[str], error: subprocess.CalledProcessError) -> str:
    stderr = (error.stderr or "").strip()
    stdout = (error.stdout or "").strip()
    details: list[str] = [
        f"{tool_name} failed with exit code {error.returncode}.",
        f"Executable: {command[0]}",
        f"Command: {subprocess.list2cmdline(command)}",
    ]
    if stderr:
        details.append(f"stderr: {stderr[-4000:]}")
    if stdout:
        details.append(f"stdout: {stdout[-2000:]}")
    return " ".join(details)


def run_checked(command: list[str], *, tool_name: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(format_subprocess_error(tool_name, command, exc)) from exc
    except OSError as exc:
        raise RuntimeError(
            f"{tool_name} could not be started. Executable: {command[0]}. "
            f"Command: {subprocess.list2cmdline(command)}. Reason: {exc}"
        ) from exc


def probe_video(video_path: Path, ffprobe: str | None = None, ffmpeg: str | None = None) -> VideoMetadata:
    exe = resolve_executable("ffprobe", ffprobe, peer_override=ffmpeg)
    command = [
        exe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    completed = run_checked(command, tool_name="ffprobe")
    payload = json.loads(completed.stdout or "{}")
    streams = payload.get("streams") or []
    if not streams:
        raise RuntimeError(f"No video stream found in {video_path}")
    stream = streams[0]
    duration = float(stream.get("duration") or payload.get("format", {}).get("duration") or 0.0)
    fps = parse_rational(stream.get("avg_frame_rate")) or parse_rational(stream.get("r_frame_rate"))
    frame_count_text = stream.get("nb_frames")
    try:
        frame_count = int(frame_count_text)
    except (TypeError, ValueError):
        frame_count = int(round(duration * fps)) if duration > 0 and fps > 0 else 0
    return VideoMetadata(
        path=str(video_path.resolve()),
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        duration_seconds=round(duration, 4),
        fps=round(fps, 4),
        frame_count=frame_count,
        source="ffprobe",
    )


def metadata_from_args(args: argparse.Namespace, *, require_video: bool) -> VideoMetadata:
    video_path = Path(args.video).expanduser().resolve() if args.video else None
    metadata: VideoMetadata | None = None
    if video_path and not video_path.exists():
        raise RuntimeError(f"Source video does not exist: {video_path}")
    if video_path and not getattr(args, "no_probe", False):
        metadata = probe_video(video_path, getattr(args, "ffprobe", None), getattr(args, "ffmpeg", None))
    elif require_video and not video_path:
        raise RuntimeError("A video path is required.")

    width = metadata.width if metadata else 0
    height = metadata.height if metadata else 0
    duration = metadata.duration_seconds if metadata else 0.0
    fps = metadata.fps if metadata else 0.0
    frame_count = metadata.frame_count if metadata else 0
    source = metadata.source if metadata else "manual"

    if getattr(args, "source_size", None):
        width, height = args.source_size
        source = f"{source}+manual-size" if metadata else "manual"
    if getattr(args, "duration", None):
        duration = float(args.duration)
        source = f"{source}+manual-duration" if metadata else "manual"
    if getattr(args, "source_fps", None):
        fps = float(args.source_fps)
        source = f"{source}+manual-fps" if metadata else "manual"
    if not frame_count and duration > 0 and fps > 0:
        frame_count = int(round(duration * fps))

    missing: list[str] = []
    if width <= 0 or height <= 0:
        missing.append("--source-size")
    if duration <= 0:
        missing.append("--duration")
    if fps <= 0:
        missing.append("--source-fps")
    if missing:
        raise RuntimeError(
            "Could not determine video metadata. Install/pass ffprobe or provide "
            + ", ".join(missing)
            + "."
        )

    return VideoMetadata(
        path=str(video_path) if video_path else "",
        width=width,
        height=height,
        duration_seconds=round(duration, 4),
        fps=round(fps, 4),
        frame_count=frame_count,
        source=source,
    )


def clip_range_from_args(metadata: VideoMetadata, args: argparse.Namespace) -> ClipRange:
    start = float(getattr(args, "start", 0.0) or 0.0)
    end_arg = getattr(args, "end", None)
    end = float(end_arg) if end_arg is not None else metadata.duration_seconds
    if start < 0:
        raise RuntimeError("--start must be >= 0")
    if end <= start:
        raise RuntimeError("--end must be greater than --start")
    if start >= metadata.duration_seconds:
        raise RuntimeError(f"--start ({start}s) must be before video duration ({metadata.duration_seconds}s)")
    if end > metadata.duration_seconds + 0.001:
        raise RuntimeError(f"--end ({end}s) exceeds video duration ({metadata.duration_seconds}s)")
    end = min(end, metadata.duration_seconds)
    return ClipRange(
        start_seconds=round(start, 6),
        end_seconds=round(end, 6),
        duration_seconds=round(end - start, 6),
        uses_full_video=abs(start) < 0.000001 and abs(end - metadata.duration_seconds) < 0.001,
    )


def metadata_for_clip(metadata: VideoMetadata, clip: ClipRange) -> VideoMetadata:
    source = metadata.source if clip.uses_full_video else f"{metadata.source}+clip"
    return VideoMetadata(
        path=metadata.path,
        width=metadata.width,
        height=metadata.height,
        duration_seconds=clip.duration_seconds,
        fps=metadata.fps,
        frame_count=int(round(clip.duration_seconds * metadata.fps)),
        source=source,
    )


def choose_grid(desired_frames: int, max_cells: int) -> tuple[int, int]:
    viable = [grid for grid in COMMON_GRIDS if grid[0] * grid[1] >= desired_frames and grid[0] * grid[1] <= max_cells]
    if viable:
        return viable[0]
    side = max(1, int(math.ceil(math.sqrt(desired_frames))))
    columns = 1
    while columns < side:
        columns *= 2
    rows = int(math.ceil(desired_frames / columns))
    return columns, rows


def lower_grid(desired_frames: int) -> tuple[int, int] | None:
    smaller = [grid for grid in COMMON_GRIDS if grid[0] * grid[1] < desired_frames]
    return smaller[-1] if smaller else None


def higher_grid(columns: int, rows: int, max_cells: int) -> tuple[int, int] | None:
    current_cells = columns * rows
    larger = [grid for grid in COMMON_GRIDS if current_cells < grid[0] * grid[1] <= max_cells]
    return larger[0] if larger else None


def choose_cell_size(
    metadata: VideoMetadata,
    columns: int,
    rows: int,
    *,
    max_texture_size: int,
    allow_upscale: bool,
) -> tuple[int, int]:
    max_cell_width = max(1, max_texture_size // columns)
    max_cell_height = max(1, max_texture_size // rows)
    scale = min(max_cell_width / metadata.width, max_cell_height / metadata.height)
    if not allow_upscale:
        scale = min(scale, 1.0)
    width = max(1, int(round(metadata.width * scale)))
    height = max(1, int(round(metadata.height * scale)))
    return width, height


def build_recommendation(
    metadata: VideoMetadata,
    *,
    target_fps: float,
    min_frames: int,
    max_frames: int,
    max_texture_size: int,
    allow_upscale: bool,
    atlas_size_mode: str = "nearest-power-of-two",
) -> dict[str, Any]:
    if target_fps <= 0:
        raise RuntimeError("--target-fps must be greater than 0")
    if min_frames <= 0 or max_frames <= 0:
        raise RuntimeError("--min-frames and --max-frames must be greater than 0")
    if min_frames > max_frames:
        raise RuntimeError("--min-frames cannot be greater than --max-frames")
    if max_texture_size <= 0:
        raise RuntimeError("--max-texture-size must be greater than 0")
    raw_desired = int(round(metadata.duration_seconds * target_fps))
    desired_frames = clamp(raw_desired, min_frames, max_frames)
    columns, rows = choose_grid(desired_frames, max_frames)
    cells = columns * rows
    cell_width, cell_height = choose_cell_size(
        metadata,
        columns,
        rows,
        max_texture_size=max_texture_size,
        allow_upscale=allow_upscale,
    )
    raw_atlas_size = (cell_width * columns, cell_height * rows)
    estimated_atlas_size = atlas_size_for_mode(raw_atlas_size, atlas_size_mode)
    alternatives: list[dict[str, Any]] = []
    compact = lower_grid(desired_frames)
    if compact:
        alternatives.append(
            {
                "label": "compact",
                "grid": f"{compact[0]}x{compact[1]}",
                "cells": compact[0] * compact[1],
                "tradeoff": "smaller texture, may skip motion detail",
            }
        )
    quality = higher_grid(columns, rows, max_frames)
    if quality:
        alternatives.append(
            {
                "label": "quality",
                "grid": f"{quality[0]}x{quality[1]}",
                "cells": quality[0] * quality[1],
                "tradeoff": "more temporal detail, larger texture",
            }
        )
    if metadata.duration_seconds <= 1.25:
        reason = "short VFX clip; a compact SubUV grid usually preserves the read without overspending texture memory"
    elif cells <= 32:
        reason = "medium-short clip; 8x4 keeps timing readable while staying cheap"
    elif cells <= 64:
        reason = "longer or detailed clip; 8x8 is the usual UE-friendly balance"
    else:
        reason = "high frame budget; verify texture memory and import limits before using in runtime"
    return {
        "target_fps": target_fps,
        "raw_desired_frames": raw_desired,
        "desired_frames_clamped": desired_frames,
        "recommended_grid": {
            "columns": columns,
            "rows": rows,
            "cells": cells,
            "label": f"{columns}x{rows}",
        },
        "recommended_sampling_frames": cells,
        "recommended_cell_size": {"width": cell_width, "height": cell_height},
        "raw_estimated_atlas_size": {"width": raw_atlas_size[0], "height": raw_atlas_size[1]},
        "estimated_atlas_size": {"width": estimated_atlas_size[0], "height": estimated_atlas_size[1]},
        "atlas_size_mode": atlas_size_mode,
        "estimated_atlas_power_of_two": is_power_of_two(estimated_atlas_size[0])
        and is_power_of_two(estimated_atlas_size[1]),
        "max_texture_size": max_texture_size,
        "alternatives": alternatives,
        "reason": reason,
        "ue_notes": {
            "sub_uv_columns": columns,
            "sub_uv_rows": rows,
            "suggested_play_rate_fps": round(cells / metadata.duration_seconds, 3),
            "unused_cells_if_sampling_desired_only": max(0, cells - desired_frames),
        },
    }


def frame_times(start: float, end: float, count: int, *, mode: str, fps: float) -> list[float]:
    if count <= 0:
        return []
    duration = end - start
    if duration <= 0:
        raise RuntimeError("--end must be greater than --start")
    if mode == "fps":
        if fps <= 0:
            raise RuntimeError("--target-fps must be greater than 0 for --sample-mode fps")
        return [round(start + (index / fps), 6) for index in range(count) if start + (index / fps) < end]
    step = duration / count
    return [round(start + ((index + 0.5) * step), 6) for index in range(count)]


def run_ffmpeg_extract(
    video_path: Path,
    output_dir: Path,
    times: list[float],
    *,
    ffmpeg: str | None,
    source_fps: float = 0.0,
) -> list[Path]:
    exe = resolve_executable("ffmpeg", ffmpeg)
    ensure_dir(output_dir)
    paths: list[Path] = []
    for index, timestamp in enumerate(times):
        output_path = output_dir / f"raw_{index:04d}.png"
        step = 1.0 / source_fps if source_fps > 0 else 0.05
        attempts = [
            timestamp,
            max(0.0, timestamp - step * 0.5),
            max(0.0, timestamp - step),
            max(0.0, timestamp - step * 2),
        ]
        errors: list[str] = []
        for attempt_time in attempts:
            if output_path.exists():
                output_path.unlink()
            command = [
                exe,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{attempt_time:.6f}",
                "-i",
                str(video_path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                str(output_path),
            ]
            try:
                run_checked(command, tool_name="ffmpeg")
                if output_path.exists() and output_path.stat().st_size > 0:
                    break
                errors.append(f"timestamp {attempt_time:.6f}: no output frame")
            except RuntimeError as exc:
                errors.append(f"timestamp {attempt_time:.6f}: {exc}")
        if not output_path.exists() or output_path.stat().st_size <= 0:
            detail = " | ".join(errors[-4:])
            raise RuntimeError(f"ffmpeg did not create {output_path}. {detail}")
        paths.append(output_path)
    return paths


def parse_background(value: str) -> tuple[int, int, int, int]:
    if value.lower() == "transparent":
        return (0, 0, 0, 0)
    if value.startswith("#"):
        text = value[1:]
        if len(text) == 6:
            text += "ff"
        if len(text) != 8:
            raise argparse.ArgumentTypeError("background hex must be #RRGGBB or #RRGGBBAA")
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4, 6))  # type: ignore[return-value]
    parts = [part.strip() for part in value.split(",")]
    if len(parts) not in {3, 4}:
        raise argparse.ArgumentTypeError("background must be transparent, #RRGGBB, #RRGGBBAA, or r,g,b[,a]")
    channels = [int(part) for part in parts]
    if len(channels) == 3:
        channels.append(255)
    if any(channel < 0 or channel > 255 for channel in channels):
        raise argparse.ArgumentTypeError("background channels must be 0-255")
    return tuple(channels)  # type: ignore[return-value]


def normalize_frame(
    source: Path,
    target: Path,
    *,
    cell_size: tuple[int, int],
    fit: str,
    background: tuple[int, int, int, int],
) -> None:
    ensure_dir(target.parent)
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        if fit == "stretch":
            normalized = image.resize(cell_size, Image.Resampling.LANCZOS)
        elif fit == "cover":
            normalized = ImageOps.fit(image, cell_size, method=Image.Resampling.LANCZOS)
        else:
            contained = ImageOps.contain(image, cell_size, method=Image.Resampling.LANCZOS)
            normalized = Image.new("RGBA", cell_size, background)
            x = (cell_size[0] - contained.width) // 2
            y = (cell_size[1] - contained.height) // 2
            normalized.alpha_composite(contained, (x, y))
        normalized.save(target)


def compose_atlas(
    frame_paths: list[Path],
    atlas_path: Path,
    *,
    columns: int,
    rows: int,
    cell_size: tuple[int, int],
    background: tuple[int, int, int, int],
    atlas_size: tuple[int, int] | None = None,
) -> tuple[int, int]:
    ensure_dir(atlas_path.parent)
    atlas_width = columns * cell_size[0]
    atlas_height = rows * cell_size[1]
    atlas = Image.new("RGBA", (atlas_width, atlas_height), background)
    for index, frame_path in enumerate(frame_paths[: columns * rows]):
        with Image.open(frame_path) as opened:
            image = opened.convert("RGBA")
            column = index % columns
            row = index // columns
            atlas.alpha_composite(image, (column * cell_size[0], row * cell_size[1]))
    if atlas_size and atlas_size != (atlas_width, atlas_height):
        atlas = atlas.resize(atlas_size, Image.Resampling.LANCZOS)
        atlas_width, atlas_height = atlas_size
    atlas.save(atlas_path)
    return atlas_width, atlas_height


def summary_text(payload: dict[str, Any]) -> str:
    grid = payload["grid"]
    atlas = payload["atlas"]
    sampling = payload["sampling"]
    ue = payload["ue_notes"]
    clip = payload["clip"]
    atlas_line = f"- Atlas: `{atlas['path']}` (`{atlas['width']}x{atlas['height']}`)"
    if atlas.get("snapped_from"):
        raw = atlas["snapped_from"]
        atlas_line += f" snapped from `{raw['width']}x{raw['height']}` via `{atlas['size_mode']}`"
    return "\n".join(
        [
            f"# Flipbook Build: {payload['effect_name']}",
            "",
            f"- Source: `{payload['source_video']}`",
            f"- Clip: `{clip['start_seconds']}s -> {clip['end_seconds']}s` (`{clip['duration_seconds']}s`)",
            f"- Grid: `{grid['columns']}x{grid['rows']}` ({grid['cells']} cells)",
            f"- Frames: `{sampling['frame_count']}`",
            f"- Cell: `{grid['cell_width']}x{grid['cell_height']}`",
            atlas_line,
            f"- UE SubUV: columns `{ue['sub_uv_columns']}`, rows `{ue['sub_uv_rows']}`",
            f"- Suggested play rate: `{ue['suggested_play_rate_fps']}` fps",
            "",
        ]
    )


def print_recommendation(payload: dict[str, Any]) -> None:
    metadata = payload["video"]
    clip = payload["clip"]
    recommendation = payload["recommendation"]
    grid = recommendation["recommended_grid"]
    atlas = recommendation["estimated_atlas_size"]
    cell = recommendation["recommended_cell_size"]
    print(f"Video: {metadata['width']}x{metadata['height']}, {metadata['duration_seconds']}s, {metadata['fps']}fps")
    print(f"Clip: {clip['start_seconds']}s -> {clip['end_seconds']}s ({clip['duration_seconds']}s)")
    print(f"Recommended: {grid['label']} ({grid['cells']} frames/cells)")
    raw_atlas = recommendation.get("raw_estimated_atlas_size", atlas)
    if raw_atlas != atlas:
        print(
            f"Cell: {cell['width']}x{cell['height']} -> raw atlas "
            f"{raw_atlas['width']}x{raw_atlas['height']} -> atlas {atlas['width']}x{atlas['height']}"
        )
    else:
        print(f"Cell: {cell['width']}x{cell['height']} -> atlas {atlas['width']}x{atlas['height']}")
    print(f"Reason: {recommendation['reason']}")
    for alternative in recommendation["alternatives"]:
        print(f"Alternative {alternative['label']}: {alternative['grid']} - {alternative['tradeoff']}")


def recommend_command(args: argparse.Namespace) -> int:
    metadata = metadata_from_args(args, require_video=False)
    clip = clip_range_from_args(metadata, args)
    clip_metadata = metadata_for_clip(metadata, clip)
    recommendation = build_recommendation(
        clip_metadata,
        target_fps=args.target_fps,
        min_frames=args.min_frames,
        max_frames=args.max_frames,
        max_texture_size=args.max_texture_size,
        allow_upscale=args.allow_upscale,
        atlas_size_mode=args.atlas_size_mode,
    )
    payload = {
        "tool": "flipbook_builder",
        "command": "recommend",
        "generated_utc": utc_now_iso(),
        "video": asdict(metadata),
        "clip": asdict(clip),
        "recommendation": recommendation,
    }
    if args.out:
        save_json(Path(args.out), payload)
    if args.json:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_recommendation(payload)
        if args.out:
            print(Path(args.out))
    return 0


def build_command(args: argparse.Namespace) -> int:
    metadata = metadata_from_args(args, require_video=True)
    clip = clip_range_from_args(metadata, args)
    clip_metadata = metadata_for_clip(metadata, clip)
    video_path = Path(metadata.path)
    if args.grid.lower() == "auto":
        recommendation = build_recommendation(
            clip_metadata,
            target_fps=args.target_fps,
            min_frames=args.min_frames,
            max_frames=args.max_frames,
            max_texture_size=args.max_texture_size,
            allow_upscale=args.allow_upscale,
            atlas_size_mode=args.atlas_size_mode,
        )
        columns = recommendation["recommended_grid"]["columns"]
        rows = recommendation["recommended_grid"]["rows"]
    else:
        columns, rows = parse_grid(args.grid)
        recommendation = build_recommendation(
            clip_metadata,
            target_fps=args.target_fps,
            min_frames=args.min_frames,
            max_frames=max(args.max_frames, columns * rows),
            max_texture_size=args.max_texture_size,
            allow_upscale=args.allow_upscale,
            atlas_size_mode=args.atlas_size_mode,
        )
    cells = columns * rows
    frame_count = args.frames or cells
    if frame_count > cells:
        raise RuntimeError(f"--frames ({frame_count}) cannot exceed grid cells ({cells})")

    start = clip.start_seconds
    end = clip.end_seconds
    times = frame_times(start, end, frame_count, mode=args.sample_mode, fps=args.target_fps)
    if len(times) > cells:
        times = times[:cells]
    if not times:
        raise RuntimeError("No frame times selected. Check --start, --end, --frames, and --target-fps.")

    cell_size = args.cell_size or choose_cell_size(
        metadata,
        columns,
        rows,
        max_texture_size=args.max_texture_size,
        allow_upscale=args.allow_upscale,
    )
    raw_atlas_size = (columns * cell_size[0], rows * cell_size[1])
    atlas_size = atlas_size_for_mode(raw_atlas_size, args.atlas_size_mode)
    background = parse_background(args.background)
    effect = args.effect or video_path.stem
    ctx = resolve_root_context(args.root)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else ctx.vfx_root / "flipbooks" / slugify(effect) / run_id
    frames_dir = ensure_dir(output_dir / "frames")
    atlas_path = output_dir / args.atlas_name

    with tempfile.TemporaryDirectory(prefix="flipbook-raw-") as temp_name:
        raw_dir = Path(temp_name)
        raw_paths = run_ffmpeg_extract(video_path, raw_dir, times, ffmpeg=args.ffmpeg, source_fps=metadata.fps)
        normalized_paths: list[Path] = []
        for index, raw_path in enumerate(raw_paths):
            target = frames_dir / f"frame_{index:04d}.png"
            normalize_frame(raw_path, target, cell_size=cell_size, fit=args.fit, background=background)
            normalized_paths.append(target)

    atlas_width, atlas_height = compose_atlas(
        normalized_paths,
        atlas_path,
        columns=columns,
        rows=rows,
        cell_size=cell_size,
        background=background,
        atlas_size=atlas_size,
    )
    snapped_from = None
    if raw_atlas_size != (atlas_width, atlas_height):
        snapped_from = {"width": raw_atlas_size[0], "height": raw_atlas_size[1]}
    manifest_path = output_dir / "flipbook-manifest.json"
    summary_path = output_dir / "summary.md"
    payload = {
        "tool": "flipbook_builder",
        "command": "build",
        "generated_utc": utc_now_iso(),
        "effect_name": effect,
        "source_video": str(video_path),
        "video": asdict(metadata),
        "clip": asdict(clip),
        "recommendation": recommendation,
        "grid": {
            "columns": columns,
            "rows": rows,
            "cells": cells,
            "cell_width": cell_size[0],
            "cell_height": cell_size[1],
            "fit": args.fit,
            "background": args.background,
        },
        "sampling": {
            "mode": args.sample_mode,
            "start_seconds": start,
            "end_seconds": end,
            "frame_count": len(normalized_paths),
            "requested_frame_count": frame_count,
            "target_fps": args.target_fps,
            "times_seconds": times,
        },
        "atlas": {
            "path": str(atlas_path),
            "width": atlas_width,
            "height": atlas_height,
            "raw_width": raw_atlas_size[0],
            "raw_height": raw_atlas_size[1],
            "size_mode": args.atlas_size_mode,
            "power_of_two": is_power_of_two(atlas_width) and is_power_of_two(atlas_height),
            "snapped_from": snapped_from,
        },
        "outputs": {
            "output_dir": str(output_dir),
            "frames_dir": str(frames_dir),
            "atlas_png": str(atlas_path),
            "manifest": str(manifest_path),
            "summary_md": str(summary_path),
        },
        "ue_notes": {
            "sub_uv_columns": columns,
            "sub_uv_rows": rows,
            "first_frame": 0,
            "last_frame": max(0, len(normalized_paths) - 1),
            "suggested_play_rate_fps": round(len(normalized_paths) / max(0.001, end - start), 3),
            "blank_cells": max(0, cells - len(normalized_paths)),
        },
    }
    save_json(manifest_path, payload)
    summary_path.write_text(summary_text(payload), encoding="utf-8")
    print(manifest_path)
    return 0


def add_metadata_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("video", nargs="?", help="Source video path. Optional for recommend when manual metadata is provided.")
    parser.add_argument("--ffprobe", help="Path to ffprobe if it is not on PATH.")
    parser.add_argument("--ffmpeg", help="Path to ffmpeg. For recommend it is only used to find sibling ffprobe.")
    parser.add_argument("--no-probe", action="store_true", help="Do not call ffprobe; require manual metadata.")
    parser.add_argument("--source-size", type=parse_size, help="Manual source size, e.g. 1920x1080.")
    parser.add_argument("--duration", type=float, help="Manual duration in seconds.")
    parser.add_argument("--source-fps", type=float, help="Manual source FPS.")


def add_recommendation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-fps", type=float, default=12.0, help="Temporal sampling target used for auto recommendation.")
    parser.add_argument("--min-frames", type=int, default=16, help="Minimum auto frame budget.")
    parser.add_argument("--max-frames", type=int, default=64, help="Maximum auto frame budget.")
    parser.add_argument("--max-texture-size", type=int, default=4096, help="Maximum atlas width or height used for cell-size recommendation.")
    parser.add_argument("--allow-upscale", action="store_true", help="Allow recommended cell size to upscale above source resolution.")
    parser.add_argument(
        "--atlas-size-mode",
        choices=("nearest-power-of-two", "raw"),
        default="nearest-power-of-two",
        help="Atlas output size policy. Default snaps each atlas axis to the nearest power of two.",
    )


def add_clip_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", type=parse_time, default=0.0, help="Clip start time. Accepts seconds, MM:SS, or HH:MM:SS. Defaults to 0.")
    parser.add_argument("--end", type=parse_time, help="Clip end time. Defaults to the full video duration.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recommend and build UE/Niagara-friendly flipbook atlases from video.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    recommend = subparsers.add_parser("recommend", help="Inspect a video and recommend a flipbook grid.")
    add_metadata_args(recommend)
    add_recommendation_args(recommend)
    add_clip_args(recommend)
    recommend.add_argument("--out", help="Optional JSON report path.")
    recommend.add_argument("--json", action="store_true", help="Print the full JSON recommendation.")
    recommend.set_defaults(func=recommend_command)

    build = subparsers.add_parser("build", help="Extract frames and build a PNG atlas plus manifest.")
    add_metadata_args(build)
    add_recommendation_args(build)
    add_clip_args(build)
    build.add_argument("--root", default="auto")
    build.add_argument("--effect", default="", help="Effect name for the default output folder.")
    build.add_argument("--grid", default="auto", help="auto or explicit grid such as 8x8 / 8*8.")
    build.add_argument("--frames", type=int, help="Frame count to extract. Defaults to filling the grid.")
    build.add_argument("--sample-mode", choices=("evenly", "fps"), default="evenly")
    build.add_argument("--cell-size", type=parse_size, help="Output cell size, e.g. 256x256. Defaults to a max-texture-safe source fit.")
    build.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    build.add_argument("--background", default="transparent", help="transparent, #RRGGBB, #RRGGBBAA, or r,g,b[,a].")
    build.add_argument("--out-dir", help="Output directory. Defaults to .codex/session/vfx-delivery/flipbooks/<effect>/<run-id>.")
    build.add_argument("--run-id", help="Stable run id for default output directory.")
    build.add_argument("--atlas-name", default="flipbook_atlas.png")
    build.set_defaults(func=build_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, subprocess.CalledProcessError, argparse.ArgumentTypeError, ValueError) as exc:
        parser.exit(2, f"flipbook_builder: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
