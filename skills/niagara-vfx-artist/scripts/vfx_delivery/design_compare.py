from __future__ import annotations

import argparse
from pathlib import Path

from .core import load_json, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .visual_layer_map import load_map


DEFAULT_CRITERIA = [
    ("silhouette", "轮廓 / 外轮廓是否贴近设计图"),
    ("brightness", "亮度重心是否一致"),
    ("density", "密度是否过空或过厚"),
    ("width", "宽度与宽度衰减是否接近"),
    ("trail_direction", "拖尾方向是否跟随设计中的运动向量"),
    ("echo_spacing", "残影 / 波纹间距是否接近"),
    ("dynamic_rhythm", "动态节奏与消隐时长是否接近"),
]


def checklist_path(ctx, effect: str, layer: str) -> Path:
    return ctx.vfx_root / "design-compare" / slugify(effect) / f"{slugify(layer)}.json"


def generate_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    layer_map = load_map(ctx, args.effect)
    layer = next((item for item in layer_map["layers"] if item["name"] == args.layer), None)
    if layer is None:
        raise SystemExit(f"Unknown layer in map: {args.layer}")
    checklist = {
        "version": 1,
        "effect_name": args.effect,
        "layer_name": args.layer,
        "generated_at": utc_now_iso(),
        "anchor_reference_id": layer_map["anchor_reference_id"],
        "criteria": [
            {
                "name": name,
                "prompt": prompt,
                "status": "pending",
                "observation": "",
                "weight": 3 if name in {"silhouette", "trail_direction", "dynamic_rhythm"} else 2,
            }
            for name, prompt in DEFAULT_CRITERIA
        ],
        "layer_self_test": [item["check"] for item in layer.get("self_test", [])],
        "layer_evidence": layer.get("evidence", {}),
    }
    out_path = Path(args.out) if args.out else checklist_path(ctx, args.effect, args.layer)
    save_json(out_path, checklist)
    if args.markdown:
        md_lines = [
            f"# Design Compare Checklist: {args.effect} / {args.layer}",
            "",
            f"- Anchor reference: `{checklist['anchor_reference_id']}`",
            f"- Layer self-test: {', '.join(checklist['layer_self_test']) or 'none'}",
            "",
        ]
        for item in checklist["criteria"]:
            md_lines.append(f"- `{item['name']}`: {item['prompt']} [status={item['status']}]")
        write_text(out_path.with_suffix(".md"), "\n".join(md_lines).rstrip() + "\n")
    print(out_path)
    return 0


def update_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    path = checklist_path(ctx, args.effect, args.layer)
    checklist = load_json(path, None)
    if checklist is None:
        raise SystemExit(f"Checklist not found: {path}")
    item = next((entry for entry in checklist["criteria"] if entry["name"] == args.criterion), None)
    if item is None:
        raise SystemExit(f"Unknown criterion: {args.criterion}")
    item["status"] = args.status
    item["observation"] = args.observation
    item["updated_at"] = utc_now_iso()
    save_json(path, checklist)
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and annotate a design-comparison checklist for a VFX layer.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--effect", required=True)
    generate.add_argument("--layer", required=True)
    generate.add_argument("--out")
    generate.add_argument("--markdown", action="store_true")
    generate.set_defaults(func=generate_command)

    update = subparsers.add_parser("update")
    update.add_argument("--effect", required=True)
    update.add_argument("--layer", required=True)
    update.add_argument("--criterion", required=True)
    update.add_argument("--status", required=True, choices=["pass", "fail", "needs-tuning", "pending"])
    update.add_argument("--observation", default="")
    update.set_defaults(func=update_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
