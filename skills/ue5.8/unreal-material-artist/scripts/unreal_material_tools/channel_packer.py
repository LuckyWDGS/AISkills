from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


CHANNEL_TOKENS = {"R", "G", "B", "A", "L"}


def require_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("channel_packer.py requires Pillow (PIL).") from exc
    return Image


def parse_source(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    path_text, _, token = value.rpartition("@")
    if token and token.upper() in CHANNEL_TOKENS:
        return {"path": path_text, "channel": token.upper()}
    return {"path": value, "channel": "L"}


def load_channel(image_module: Any, spec: dict[str, Any], target_size: tuple[int, int]) -> Any:
    image = image_module.open(spec["path"]).convert("RGBA")
    if image.size != target_size:
        image = image.resize(target_size, image_module.Resampling.LANCZOS)
    bands = image.split()
    token = spec["channel"]
    if token == "R":
        return bands[0]
    if token == "G":
        return bands[1]
    if token == "B":
        return bands[2]
    if token == "A":
        return bands[3]
    return image.convert("L")


def invert_if_needed(channel: Any, invert: bool, image_module: Any) -> Any:
    if not invert:
        return channel
    return image_module.eval(channel, lambda px: 255 - px)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Channel Packer",
        "",
        f"- Output: `{report['output_png']}`",
        f"- Size: `{report['width']}x{report['height']}`",
        "",
        "Channels:",
    ]
    for key in ("r", "g", "b", "a"):
        source = report["sources"].get(key)
        if source:
            lines.append(f"- {key.upper()}: `{source['path']}` from `{source['channel']}`")
        else:
            lines.append(f"- {key.upper()}: constant `{report['constants'][key]}`")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    image_module = require_pillow()
    ctx = resolve_root_context(args.root)

    sources = {
        "r": parse_source(args.r),
        "g": parse_source(args.g),
        "b": parse_source(args.b),
        "a": parse_source(args.a),
    }

    existing_sources = [spec for spec in sources.values() if spec]
    if not existing_sources:
        raise SystemExit("Provide at least one channel source such as --r path/to/file.png@R.")

    base_image = image_module.open(existing_sources[0]["path"]).convert("RGBA")
    target_size = base_image.size

    channels = []
    constants = {"r": args.fill_r, "g": args.fill_g, "b": args.fill_b, "a": args.fill_a}
    invert_flags = {"r": args.invert_r, "g": args.invert_g, "b": args.invert_b, "a": args.invert_a}
    for key in ("r", "g", "b", "a"):
        spec = sources[key]
        if spec:
            channel = load_channel(image_module, spec, target_size)
            channel = invert_if_needed(channel, invert_flags[key], image_module)
        else:
            channel = image_module.new("L", target_size, color=constants[key])
        channels.append(channel)

    packed = image_module.merge("RGBA", channels)
    effect = slugify(args.effect or "packed-texture")
    out = Path(args.out) if args.out else default_report_path(ctx, "packed", effect, "channel-packed", ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    packed.save(out)

    report = {
        "tool": "channel_packer",
        "output_png": str(out),
        "width": target_size[0],
        "height": target_size[1],
        "sources": sources,
        "constants": constants,
    }
    json_out = out.with_suffix(".json")
    save_json(json_out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(json_out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pack grayscale channels from source images into one RGBA texture.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect")
    parser.add_argument("--r")
    parser.add_argument("--g")
    parser.add_argument("--b")
    parser.add_argument("--a")
    parser.add_argument("--fill-r", type=int, default=0)
    parser.add_argument("--fill-g", type=int, default=0)
    parser.add_argument("--fill-b", type=int, default=0)
    parser.add_argument("--fill-a", type=int, default=255)
    parser.add_argument("--invert-r", action="store_true")
    parser.add_argument("--invert-g", action="store_true")
    parser.add_argument("--invert-b", action="store_true")
    parser.add_argument("--invert-a", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
