from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class Advice:
    effect: str
    grid: str
    target_cells: int
    clip_duration: float
    source_fps: float
    estimated_source_samples: float
    source_to_target_ratio: float
    duplicate_pressure: str
    route: str
    route_reason: str
    generated_anchor_states: int
    notes: list[str]
    search_queries: list[str]


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


def thresholds_for_effect(effect: str) -> tuple[float, float, int]:
    if effect in {"fire", "flame", "energy", "portal", "hologram", "lightning", "slash"}:
        return (1.15, 0.72, 5)
    if effect in {"dust", "powder", "smoke", "mist", "cloud", "water", "blood", "toxic"}:
        return (1.00, 0.68, 5)
    if effect in {"embers", "sparks", "muzzle"}:
        return (1.10, 0.80, 4)
    return (1.05, 0.75, 5)


def search_queries_for_effect(effect: str) -> list[str]:
    table = {
        "dust": ["falling dust alpha reference", "ceiling dust collapse reference", "dust plume side view"],
        "powder": ["powder plume alpha reference", "falling powder side view", "powder burst vfx reference"],
        "smoke": ["smoke plume side reference", "soft smoke alpha reference", "smoke curl vfx reference"],
        "mist": ["mist plume side reference", "soft mist alpha reference", "mist breakup vfx reference"],
        "cloud": ["cloud plume alpha reference", "soft cloud side view", "volumetric cloud puff reference"],
        "fire": ["torch flame side reference", "flame plume alpha reference", "stylized flame vfx side view"],
        "flame": ["torch flame side reference", "flame tongue alpha reference", "flame breakup side view"],
        "embers": ["ember burst reference", "embers side view vfx", "ember shower alpha reference"],
        "sparks": ["spark shower alpha reference", "metal sparks side view", "spark burst vfx reference"],
        "energy": ["energy flame vfx reference", "plasma plume side view", "magic energy wisp reference"],
        "portal": ["magic portal flipbook reference", "energy portal sprite sheet", "portal core vfx reference"],
        "hologram": ["animated hologram flipbook reference", "scanline hologram material reference", "hologram sprite sheet"],
        "lightning": ["lightning arc flipbook reference", "electric arc sprite sheet", "energy bolt vfx reference"],
        "water": ["water splash flipbook reference", "foam burst sprite sheet", "whitewater splash alpha reference"],
        "blood": ["blood impact cloud flipbook reference", "blood splatter sprite sheet", "stylized blood burst vfx reference"],
        "toxic": ["poison cloud flipbook reference", "toxic gas sprite sheet", "acid splash vfx reference"],
        "muzzle": ["muzzle flash sprite sheet reference", "gun smoke flipbook reference", "muzzle flash atlas vfx"],
        "slash": ["slash impact flipbook reference", "anime slash sprite sheet", "weapon trail impact vfx reference"],
    }
    return table.get(effect, [f"{effect} vfx reference", f"{effect} alpha reference", f"{effect} side view"])


def build_advice(effect: str, grid: tuple[int, int], clip_duration: float, source_fps: float) -> Advice:
    cells = grid[0] * grid[1]
    samples = clip_duration * source_fps
    ratio = samples / cells if cells else 0.0
    direct_threshold, hybrid_threshold, anchor_states = thresholds_for_effect(effect)
    if ratio >= direct_threshold:
        route = "direct-extract"
        reason = "source sample pressure is healthy enough for the requested atlas"
    elif ratio >= hybrid_threshold:
        route = "hybrid"
        reason = "the source has useful motion, but the atlas is dense enough that generation should bridge or extend states"
    else:
        route = "full-generated"
        reason = "the source is too sparse for the requested atlas and should not be stretched blindly"

    if ratio >= 1.10:
        pressure = "low"
    elif ratio >= 0.90:
        pressure = "medium"
    else:
        pressure = "high"

    notes = [
        "Do not rely on Niagara slow playback alone when duplicate pressure is medium or high.",
        "Keep one canvas, one framing rule, and one background policy across the sequence.",
    ]
    if route == "hybrid":
        notes.append("Keep the best real source motion and generate missing phases or bridge states with image generation.")
    if route == "full-generated":
        notes.append("Generate anchor states first, reject drift, then fill the full family before packing.")
    if effect in {"fire", "flame", "energy", "portal", "hologram", "lightning", "slash"}:
        notes.append("Hero fire and energetic effects expose stepping earlier than dust or mist.")
    if effect in {"dust", "powder", "smoke", "mist", "cloud", "water", "blood", "toxic"}:
        notes.append("Soft effects can often run near source speed while Niagara extends life through size and alpha.")

    return Advice(
        effect=effect,
        grid=f"{grid[0]}x{grid[1]}",
        target_cells=cells,
        clip_duration=round(clip_duration, 4),
        source_fps=round(source_fps, 4),
        estimated_source_samples=round(samples, 3),
        source_to_target_ratio=round(ratio, 3),
        duplicate_pressure=pressure,
        route=route,
        route_reason=reason,
        generated_anchor_states=anchor_states,
        notes=notes,
        search_queries=search_queries_for_effect(effect),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Advise whether a flipbook job should use source extraction, hybrid generation, or full generation.")
    parser.add_argument("--grid", required=True, type=parse_grid, help="Target atlas grid such as 12x12.")
    parser.add_argument(
        "--effect",
        default="generic",
        choices=(
            "generic",
            "dust",
            "powder",
            "smoke",
            "mist",
            "cloud",
            "fire",
            "flame",
            "embers",
            "sparks",
            "energy",
            "portal",
            "hologram",
            "lightning",
            "water",
            "blood",
            "toxic",
            "muzzle",
            "slash",
        ),
        help="Effect family.",
    )
    parser.add_argument("--clip-duration", required=True, type=float, help="Usable clip duration in seconds.")
    parser.add_argument("--source-fps", required=True, type=float, help="Source fps for the usable clip.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown.")
    args = parser.parse_args()

    if args.clip_duration <= 0:
        raise SystemExit("--clip-duration must be > 0")
    if args.source_fps <= 0:
        raise SystemExit("--source-fps must be > 0")

    advice = build_advice(args.effect, args.grid, args.clip_duration, args.source_fps)
    payload = asdict(advice)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.markdown or not args.json:
        print(f"# Flipbook Route Advice: {advice.effect}")
        print()
        print(f"- Grid: `{advice.grid}` ({advice.target_cells} cells)")
        print(f"- Clip duration: `{advice.clip_duration}s`")
        print(f"- Source fps: `{advice.source_fps}`")
        print(f"- Estimated source samples: `{advice.estimated_source_samples}`")
        print(f"- Source/target ratio: `{advice.source_to_target_ratio}`")
        print(f"- Duplicate pressure: `{advice.duplicate_pressure}`")
        print(f"- Recommended route: `{advice.route}`")
        print(f"- Reason: {advice.route_reason}")
        print(f"- Suggested generated anchor states: `{advice.generated_anchor_states}`")
        print()
        print("## Notes")
        for note in advice.notes:
            print(f"- {note}")
        print()
        print("## Search Queries")
        for query in advice.search_queries:
            print(f"- `{query}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
