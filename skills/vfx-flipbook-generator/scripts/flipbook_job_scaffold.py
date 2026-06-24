from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from flipbook_route_advisor import Advice, build_advice, parse_grid


EFFECT_ALIASES: dict[str, tuple[str, ...]] = {
    "smoke": ("smoke", "smokes", "smoke plume", "smoke column", "soft smoke", "烟", "烟雾", "烟柱"),
    "dust": ("dust", "falling dust", "dustfall", "dust plume", "ceiling dust", "roof dust", "rooftop dust", "collapse dust", "dust smoke", "smoke dust", "烟尘", "尘烟", "灰尘", "落尘"),
    "powder": ("powder", "powder plume", "fenmo", "powder dust", "粉末"),
    "mist": ("mist", "fog", "mist plume", "misty", "薄雾", "雾气", "雾"),
    "cloud": ("cloud", "cloud puff", "云", "yun"),
    "fire": ("fire", "hero fire", "fire plume", "火", "火焰", "huo"),
    "flame": ("flame", "flames", "torch flame", "flame tongue", "yanhuo", "flametongue"),
    "embers": ("embers", "ember", "embers burst", "余烬", "火星"),
    "sparks": ("sparks", "spark", "spark shower", "火花"),
    "energy": ("energy", "plasma", "magic flame", "energy plume", "能量", "等离子"),
    "portal": ("portal", "energy portal", "magic portal", "传送门", "法阵"),
    "hologram": ("hologram", "holographic", "scanline", "全息", "投影"),
    "lightning": ("lightning", "electric arc", "electricity", "bolt", "闪电", "电弧"),
    "water": ("water", "splash", "foam", "whitewater", "水花", "飞溅", "泡沫"),
    "blood": ("blood", "blood impact", "blood splatter", "血", "血雾", "血溅"),
    "toxic": ("toxic", "poison", "acid", "gas cloud", "毒", "毒雾", "酸液"),
    "muzzle": ("muzzle", "muzzle flash", "gun smoke", "枪口", "枪火"),
    "slash": ("slash", "weapon slash", "impact slash", "刀光", "斩击"),
}


EFFECT_CONTEXT_HINTS: dict[str, tuple[str, ...]] = {
    "dust": ("roof", "rooftop", "ceiling", "collapse", "falling", "fall", "debris", "overhead", "屋顶", "天花板", "掉落", "坠落"),
    "smoke": ("rise", "rising", "curl", "billow", "plume", "volumetric"),
    "fire": ("ignite", "ignition", "burn", "burning"),
    "flame": ("ignite", "ignition", "torch", "tongue"),
    "portal": ("ring", "core", "vortex", "rune"),
    "water": ("splash", "foam", "droplet", "impact"),
    "blood": ("impact", "splatter", "burst", "cloud"),
    "muzzle": ("flash", "barrel", "gun"),
    "slash": ("trail", "weapon", "impact"),
}


EFFECT_PRIORITY: dict[str, int] = {
    "dust": 100,
    "powder": 95,
    "mist": 90,
    "smoke": 85,
    "cloud": 80,
    "fire": 75,
    "flame": 70,
    "embers": 65,
    "sparks": 60,
    "energy": 55,
    "portal": 54,
    "hologram": 53,
    "lightning": 52,
    "water": 51,
    "blood": 50,
    "toxic": 49,
    "muzzle": 48,
    "slash": 47,
    "generic": 0,
}


STATE_LADDERS: dict[str, list[str]] = {
    "smoke": ["seed puff", "narrow rise", "curl body", "full plume", "diffuse fade"],
    "dust": ["thin seed", "falling streak", "denser body", "soft bloom", "faint tail"],
    "powder": ["thin seed", "narrow column", "wider breakup", "soft residue", "fade"],
    "mist": ["soft seed", "light spread", "mist body", "diffuse edge", "fade"],
    "cloud": ["small puff", "wider body", "soft expansion", "diffuse body", "fade"],
    "fire": ["ignition", "tight tongue", "split tongues", "bright core", "collapse"],
    "flame": ["ignition", "tight tongue", "split tongues", "bright core", "collapse"],
    "embers": ["tight cluster", "scatter", "wider scatter", "dim residue"],
    "sparks": ["tight burst", "wider scatter", "residual streaks", "fade"],
    "energy": ["seed core", "rising wisp", "full body", "torn edges", "fade"],
    "portal": ["seed ring", "opening vortex", "bright core", "unstable edge", "soft close"],
    "hologram": ["faint scan seed", "forming silhouette", "stable projection", "glitch shimmer", "fade scanout"],
    "lightning": ["small fork seed", "branching arc", "peak bolt", "fragmenting tendrils", "residual sparks"],
    "water": ["first impact", "rising splash", "peak crown", "breaking foam", "droplet fade"],
    "blood": ["tight impact", "expanding burst", "peak mist and droplets", "falling breakup", "thin residue"],
    "toxic": ["seed puff", "rolling body", "peak toxic cloud", "diffuse edges", "thin fade"],
    "muzzle": ["ignition flash", "peak flash", "smoke seed", "expanding smoke", "fade"],
    "slash": ["thin slash seed", "bright full stroke", "impact flare", "fragmented tail", "fade"],
    "generic": ["early", "mid", "peak", "late", "fade"],
}


BASE_PROMPTS: dict[str, str] = {
    "smoke": "isolated smoke plume, soft volumetric breakup, layered curl motion, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "dust": "isolated falling dust plume, soft particulate breakup, subtle turbulence, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "powder": "isolated powder plume, soft particulate breakup, narrow to wider column motion, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "mist": "isolated mist plume, soft low-density breakup, airy silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "cloud": "isolated cloud puff, soft volumetric body, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "fire": "isolated flame tongue, bright core with torn outer edges, strong upward flow, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "flame": "isolated flame tongue, bright core with torn outer edges, strong upward flow, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "embers": "isolated ember burst, small bright particles with controlled scatter, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "sparks": "isolated spark shower, small bright particles with controlled scatter, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "energy": "isolated energy plume, emissive core with soft torn edges, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "portal": "isolated magic energy portal core, circular ring and swirling inner motion, emissive edges, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "hologram": "isolated hologram scan effect, layered scanline shimmer and translucent projection breakup, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "lightning": "isolated electric lightning arc, branching jagged bolt motion, bright emissive core with fading edge glow, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "water": "isolated water splash and foam burst, translucent droplets with readable splash silhouette, centered, fixed camera, consistent scale, transparent or black background, VFX flipbook frame",
    "blood": "isolated stylized blood impact mist and droplets, readable burst silhouette, centered, fixed camera, consistent scale, transparent background, VFX flipbook frame",
    "toxic": "isolated toxic gas puff, soft rolling poison cloud with readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "muzzle": "isolated muzzle flash and gun smoke burst, bright flash core with short smoke expansion, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "slash": "isolated weapon slash impact, bright crescent stroke with fragmenting energy tail, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
    "generic": "isolated VFX plume, readable silhouette, centered, fixed camera, consistent scale, black background, VFX flipbook frame",
}


@dataclass(slots=True)
class JobSpec:
    request_text: str
    effect: str
    grid: str
    target_cells: int
    duration_seconds: float
    source_fps: float | None
    route: str
    route_reason: str
    duplicate_pressure: str
    source_to_target_ratio: float | None
    search_queries: list[str]
    base_prompt: str
    anchor_prompts: list[dict[str, str]]
    generation_canvas: dict[str, int]
    packing_cell_size: dict[str, int]
    output_paths: dict[str, str]
    batch_plan_command: str
    packing_command: str


def slugify(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "flipbook-job"


def parse_duration(text: str) -> float | None:
    patterns = (
        r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|sec|s)\b",
        r"(\d+(?:\.\d+)?)\s*秒",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def detect_effect(text: str) -> str:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for effect, aliases in EFFECT_ALIASES.items():
        score = 0
        for alias in aliases:
            alias_text = alias.lower()
            if re.fullmatch(r"[a-z0-9][a-z0-9\s-]*", alias_text):
                pattern = rf"(?<![a-z0-9]){re.escape(alias_text)}(?![a-z0-9])"
                if re.search(pattern, lowered):
                    score += 3 if (" " in alias_text or "-" in alias_text) else 1
            elif alias_text in lowered:
                score += 3
        for hint in EFFECT_CONTEXT_HINTS.get(effect, ()):
            if hint.lower() in lowered:
                score += 1
        if score:
            scores[effect] = score
    if scores:
        return max(scores, key=lambda effect: (scores[effect], EFFECT_PRIORITY.get(effect, 0)))
    return "generic"


def infer_generation_canvas(effect: str) -> tuple[int, int]:
    if effect in {"fire", "flame"}:
        return (1024, 1536)
    if effect in {"dust"}:
        return (1024, 1536)
    return (1024, 1024)


def choose_pack_cell(grid: tuple[int, int], generation_canvas: tuple[int, int], max_texture: int = 4096) -> tuple[int, int]:
    columns, rows = grid
    max_cell_width = max(1, max_texture // columns)
    max_cell_height = max(1, max_texture // rows)
    scale = min(max_cell_width / generation_canvas[0], max_cell_height / generation_canvas[1], 1.0)
    return max(1, round(generation_canvas[0] * scale)), max(1, round(generation_canvas[1] * scale))


def create_route(effect: str, grid: tuple[int, int], duration: float, source_fps: float | None) -> Advice:
    if source_fps is None:
        search_queries = build_advice(effect, grid, duration, 1.0).search_queries
        return Advice(
            effect=effect,
            grid=f"{grid[0]}x{grid[1]}",
            target_cells=grid[0] * grid[1],
            clip_duration=round(duration, 4),
            source_fps=0.0,
            estimated_source_samples=0.0,
            source_to_target_ratio=0.0,
            duplicate_pressure="unknown",
            route="full-generated",
            route_reason="no source fps or source clip was provided, so the job should start in generated planning mode",
            generated_anchor_states=max(4, len(STATE_LADDERS.get(effect, STATE_LADDERS["generic"]))),
            notes=[
                "No source footage metadata was provided, so the scaffold assumes generated planning first.",
                "Search references first if the motion language or silhouette family is not already obvious.",
                "Generate anchor states, reject drift, then fill the sequence before packing.",
            ],
            search_queries=search_queries,
        )
    return build_advice(effect, grid, duration, source_fps)


def anchor_prompts_for_effect(effect: str, count: int) -> list[dict[str, str]]:
    ladder = STATE_LADDERS.get(effect, STATE_LADDERS["generic"])
    base = BASE_PROMPTS.get(effect, BASE_PROMPTS["generic"])
    prompts: list[dict[str, str]] = []
    for index in range(min(count, len(ladder))):
        state = ladder[index]
        prompts.append(
            {
                "name": f"anchor_{index + 1:02d}",
                "state": state,
                "prompt": f"{base}, {state}, preserve the same framing and effect family as the accepted previous anchor",
            }
        )
    return prompts


def build_job_spec(request_text: str, grid: tuple[int, int], duration: float, source_fps: float | None, out_root: Path) -> JobSpec:
    effect = detect_effect(request_text)
    route = create_route(effect, grid, duration, source_fps)
    generation_canvas = infer_generation_canvas(effect)
    packing_cell = choose_pack_cell(grid, generation_canvas)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = slugify(f"{effect}-{grid[0]}x{grid[1]}-{duration:g}s")
    job_root = out_root / slug / stamp
    output_paths = {
        "job_root": str(job_root),
        "references": str(job_root / "references"),
        "generated_frames": str(job_root / "generated-frames"),
        "curated_frames": str(job_root / "curated-frames"),
        "atlas": str(job_root / "atlas"),
    }
    atlas_name = f"{slug}.png".replace("--", "-")
    batch_plan_command = (
        f'python D:/Skills/skills/vfx-flipbook-generator/scripts/flipbook_batch_plan.py "{job_root / "job-spec.json"}" '
        f'--effect "{effect}"'
    )
    packing_command = (
        f'python D:/Skills/skills/vfx-flipbook-generator/scripts/frame_atlas_packer.py "{output_paths["curated_frames"]}" '
        f'--grid {grid[0]}x{grid[1]} --cell-size {packing_cell[0]}x{packing_cell[1]} --fit contain '
        f'--background transparent --atlas-size-mode pad-to-power-of-two --out-dir "{output_paths["atlas"]}" '
        f'--atlas-name "{atlas_name}" --effect "{slug}"'
    )
    return JobSpec(
        request_text=request_text,
        effect=effect,
        grid=f"{grid[0]}x{grid[1]}",
        target_cells=grid[0] * grid[1],
        duration_seconds=round(duration, 4),
        source_fps=None if source_fps is None else round(source_fps, 4),
        route=route.route,
        route_reason=route.route_reason,
        duplicate_pressure=route.duplicate_pressure,
        source_to_target_ratio=None if source_fps is None else round(route.source_to_target_ratio, 3),
        search_queries=route.search_queries,
        base_prompt=BASE_PROMPTS.get(effect, BASE_PROMPTS["generic"]),
        anchor_prompts=anchor_prompts_for_effect(effect, route.generated_anchor_states),
        generation_canvas={"width": generation_canvas[0], "height": generation_canvas[1]},
        packing_cell_size={"width": packing_cell[0], "height": packing_cell[1]},
        output_paths=output_paths,
        batch_plan_command=batch_plan_command,
        packing_command=packing_command,
    )


def write_job_files(spec: JobSpec) -> Path:
    job_root = Path(spec.output_paths["job_root"])
    for path in spec.output_paths.values():
        Path(path).mkdir(parents=True, exist_ok=True)

    spec_path = job_root / "job-spec.json"
    spec_path.write_text(json.dumps(asdict(spec), ensure_ascii=False, indent=2), encoding="utf-8")

    prompts_lines = [
        f"# Flipbook Job Prompts: {spec.effect}",
        "",
        f"- Request: `{spec.request_text}`",
        f"- Base prompt: `{spec.base_prompt}`",
        "",
        "## Anchors",
    ]
    for prompt in spec.anchor_prompts:
        prompts_lines.append(f"- `{prompt['name']}` / `{prompt['state']}`")
        prompts_lines.append(f"  - `{prompt['prompt']}`")
    (job_root / "prompts.md").write_text("\n".join(prompts_lines) + "\n", encoding="utf-8")

    search_lines = [
        f"# Flipbook Search Queries: {spec.effect}",
        "",
        "## Queries",
    ]
    for query in spec.search_queries:
        search_lines.append(f"- `{query}`")
    (job_root / "search-queries.md").write_text("\n".join(search_lines) + "\n", encoding="utf-8")

    summary_lines = [
        f"# Flipbook Job: {spec.effect}",
        "",
        f"- Request: `{spec.request_text}`",
        f"- Route: `{spec.route}`",
        f"- Reason: {spec.route_reason}",
        f"- Grid: `{spec.grid}` ({spec.target_cells} cells)",
        f"- Duration: `{spec.duration_seconds}s`",
        f"- Generation canvas: `{spec.generation_canvas['width']}x{spec.generation_canvas['height']}`",
        f"- Packing cell size: `{spec.packing_cell_size['width']}x{spec.packing_cell_size['height']}`",
        f"- Job root: `{spec.output_paths['job_root']}`",
        "",
        "## Batch-Plan Command",
        "",
        "```powershell",
        spec.batch_plan_command,
        "```",
        "",
        "## Packing Command",
        "",
        "```powershell",
        spec.packing_command,
        "```",
    ]
    (job_root / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return spec_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a flipbook generation job from a short request like 'smoke 12x12 6s'.")
    parser.add_argument("request_text", help="Short request text, preferably quoted.")
    parser.add_argument("--grid", help="Optional grid override such as 12x12.")
    parser.add_argument("--duration", type=float, help="Optional duration override in seconds.")
    parser.add_argument("--source-fps", type=float, help="Optional source fps for route advice.")
    parser.add_argument("--out-root", default="", help="Root output folder. Defaults to ./flipbook-jobs")
    parser.add_argument("--json", action="store_true", help="Print JSON after writing the job pack.")
    args = parser.parse_args()

    grid = parse_grid(args.grid) if args.grid else parse_grid(re.search(r"(\d+\s*(?:x|\*|×)\s*\d+)", args.request_text, flags=re.IGNORECASE).group(1)) if re.search(r"(\d+\s*(?:x|\*|×)\s*\d+)", args.request_text, flags=re.IGNORECASE) else None
    if grid is None:
        raise SystemExit("Could not find a grid in the request. Pass --grid or include text like 12x12.")

    duration = args.duration if args.duration is not None else parse_duration(args.request_text)
    if duration is None:
        raise SystemExit("Could not find a duration in the request. Pass --duration or include text like 6s / 6 sec / 6秒.")
    if duration <= 0:
        raise SystemExit("Duration must be > 0.")

    out_root = Path(args.out_root).expanduser().resolve() if args.out_root else (Path.cwd() / "flipbook-jobs").resolve()
    spec = build_job_spec(args.request_text, grid, duration, args.source_fps, out_root)
    spec_path = write_job_files(spec)
    if args.json:
        print(json.dumps(asdict(spec), ensure_ascii=False, indent=2))
    else:
        print(spec_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
