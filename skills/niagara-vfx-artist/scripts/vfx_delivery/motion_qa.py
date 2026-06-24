from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .core import default_report_path, normalize_cli_global_args, resolve_root_context, save_json, slugify, utc_now_iso, write_text


def collect_frames(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"})


def frame_diff(a: Path, b: Path) -> dict[str, object]:
    with Image.open(a) as left, Image.open(b) as right:
        left_rgba = left.convert("RGBA")
        right_rgba = right.convert("RGBA")
        diff = ImageChops.difference(left_rgba, right_rgba)
        stat = ImageStat.Stat(diff)
        mean_abs_diff = sum(float(item) for item in stat.mean) / len(stat.mean)
        bbox = diff.getbbox()
        return {
            "baseline": str(a),
            "candidate": str(b),
            "mean_abs_diff": mean_abs_diff,
            "bbox": list(bbox) if bbox else [],
        }


def command_compare(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    baseline = collect_frames(Path(args.baseline_dir))
    candidate = collect_frames(Path(args.candidate_dir))
    if not baseline or not candidate:
        raise SystemExit("Both baseline and candidate directories must contain at least one image frame.")
    pairs = list(zip(baseline, candidate))
    diffs = [frame_diff(a, b) for a, b in pairs]
    worst = max((item["mean_abs_diff"] for item in diffs), default=0.0)
    average = sum(item["mean_abs_diff"] for item in diffs) / len(diffs)
    report = {
        "tool": "motion_qa",
        "generated_utc": utc_now_iso(),
        "baseline_dir": str(Path(args.baseline_dir).resolve()),
        "candidate_dir": str(Path(args.candidate_dir).resolve()),
        "frame_count": len(pairs),
        "average_mean_abs_diff": average,
        "worst_mean_abs_diff": worst,
        "within_threshold": worst <= args.max_mean_diff,
        "frames": diffs,
    }
    effect = args.effect or f"{slugify(Path(args.baseline_dir).name)}-vs-{slugify(Path(args.candidate_dir).name)}"
    out = Path(args.out) if args.out else default_report_path(ctx, "motion-qa", effect, "motion-qa", ".json")
    save_json(out, report)
    if args.markdown:
        lines = [
            f"# Motion QA: {effect}",
            "",
            f"- Frame count: `{report['frame_count']}`",
            f"- Average mean abs diff: `{report['average_mean_abs_diff']}`",
            f"- Worst mean abs diff: `{report['worst_mean_abs_diff']}`",
            f"- Within threshold: `{report['within_threshold']}`",
            "",
        ]
        for item in diffs[:10]:
            lines.append(f"- `{Path(item['baseline']).name}` vs `{Path(item['candidate']).name}` diff=`{item['mean_abs_diff']}` bbox=`{item['bbox']}`")
        write_text(out.with_suffix(".md"), "\n".join(lines).rstrip() + "\n")
    print(out)
    return 0 if report["within_threshold"] or not args.strict else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare frame sequences for first-pass motion QA.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--effect", default="")
    parser.add_argument("--max-mean-diff", type=float, default=24.0)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands=set())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
