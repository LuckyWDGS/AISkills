from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


PHASE_WEIGHTS: dict[str, tuple[float, ...]] = {
    "dust": (0.12, 0.2, 0.28, 0.24, 0.16),
    "powder": (0.12, 0.2, 0.28, 0.24, 0.16),
    "smoke": (0.14, 0.18, 0.26, 0.24, 0.18),
    "mist": (0.16, 0.2, 0.24, 0.22, 0.18),
    "cloud": (0.16, 0.2, 0.24, 0.22, 0.18),
    "fire": (0.12, 0.2, 0.3, 0.24, 0.14),
    "flame": (0.12, 0.2, 0.3, 0.24, 0.14),
    "embers": (0.24, 0.28, 0.26, 0.22),
    "sparks": (0.24, 0.28, 0.26, 0.22),
    "energy": (0.16, 0.22, 0.28, 0.2, 0.14),
}


STATE_DETAIL_HINTS: dict[str, tuple[tuple[str, str], ...]] = {
    "dust": (
        ("thin overhead release, sparse particles breaking free from the roof edge", "slightly longer downward streak, still sparse and narrow"),
        ("clear gravity-driven falling column, denser particulate body", "wider breakup and stronger interior density"),
        ("peak falling dust body, broad particulate breakup, readable central mass", "slightly fuller body with a soft outward bloom"),
        ("widening residue, softer edges, density starting to thin", "falloff tail with more diffuse haze than solid mass"),
        ("faint lingering tail, only light particulate residue remains", "nearly dissipated haze with minimal remaining density"),
    ),
    "powder": (
        ("thin powder release, sparse falling grains", "narrow powder streak with a slightly denser core"),
        ("clear falling powder column, soft breakup", "wider powder body with stronger granular breakup"),
        ("peak powder body, broad particulate breakup", "softer bloom around the peak powder body"),
        ("lighter powder residue, thinning edges", "diffuse powder tail with weakening core"),
        ("faint powder residue, almost gone", "very soft remaining powder haze"),
    ),
    "smoke": (
        ("small smoke seed, narrow early rise", "slightly fuller rise with the first curl hints"),
        ("clear curl body, stronger internal breakup", "fuller curl with a wider readable silhouette"),
        ("peak plume body, layered curl motion, richest density", "slightly broader plume body with soft torn edges"),
        ("wider diffuse body, density easing off", "soft fade body with less central density"),
        ("thin fading smoke, only a faint tail remains", "very light residual smoke haze"),
    ),
    "fire": (
        ("small ignition tongue, tight bright core", "slightly taller rising flame tongue"),
        ("clear upward flame tongue, stronger core", "split tongues begin with torn edges"),
        ("peak flame body, brightest core, torn outer edges", "full upward flame with energetic split tongues"),
        ("collapsing tip, thinner outer tongues", "less dense flame body with visible falloff"),
        ("late flame residue, weaker tip and fading core", "near-fade flame tongue with very light residual glow"),
    ),
    "flame": (
        ("small ignition tongue, tight bright core", "slightly taller rising flame tongue"),
        ("clear upward flame tongue, stronger core", "split tongues begin with torn edges"),
        ("peak flame body, brightest core, torn outer edges", "full upward flame with energetic split tongues"),
        ("collapsing tip, thinner outer tongues", "less dense flame body with visible falloff"),
        ("late flame residue, weaker tip and fading core", "near-fade flame tongue with very light residual glow"),
    ),
}


CM_GENERATION_SCRIPT = r"$HOME\.codex\skills\cm-imagegen\scripts\cm_image_gen.py"


@dataclass(slots=True)
class PlannedPhase:
    phase_index: int
    phase_number: int
    phase_name: str
    start_frame_index: int
    end_frame_index: int
    frame_count: int
    anchor_frame_index: int
    anchor_filename: str


@dataclass(slots=True)
class PlannedFrame:
    frame_index: int
    filename: str
    phase_index: int
    phase_name: str
    phase_frame_index: int
    phase_frame_count: int
    phase_progress: float
    global_progress: float
    is_anchor: bool
    prompt: str
    edit_prompt: str
    preferred_operation: str
    reference_strategy: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Turn a flipbook job spec into a per-frame prompt plan plus provider-specific execution guidance.")
    parser.add_argument("spec_path", help="Path to job-spec.json produced by flipbook_job_scaffold.py")
    parser.add_argument("--effect", default="", help="Optional effect override when the scaffolded effect needs correction.")
    parser.add_argument("--prompt-prefix", default="", help="Optional text inserted before the base prompt.")
    parser.add_argument("--prompt-suffix", default="", help="Optional text appended to every frame prompt.")
    parser.add_argument("--background", default="transparent", help="Default background policy for generated frames.")
    parser.add_argument("--quality", default="high", help="Default output quality hint for image generation.")
    parser.add_argument("--output-format", default="png", choices=("png", "jpeg", "webp"))
    parser.add_argument("--provider-mode", default="system-imagegen", choices=("system-imagegen", "cm-imagegen"))
    parser.add_argument("--frame-plan-name", default="frame-plan.json")
    parser.add_argument("--script-name", default="generate-frames-cm.ps1")
    parser.add_argument("--runner-script-name", default="run-phases.ps1")
    parser.add_argument("--manual-guide-name", default="system-imagegen-guide.md")
    parser.add_argument("--summary-name", default="batch-plan-summary.md")
    return parser.parse_args()


def ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def load_spec(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def weights_for_effect(effect: str, state_count: int) -> list[float]:
    base = PHASE_WEIGHTS.get(effect)
    if base is None or len(base) != state_count:
        return [1.0 / state_count] * state_count
    total = sum(base)
    return [value / total for value in base]


def distribute_counts(total_frames: int, weights: list[float]) -> list[int]:
    raw = [total_frames * weight for weight in weights]
    counts = [int(value) for value in raw]
    remainder = total_frames - sum(counts)
    fractional = sorted(((value - int(value), index) for index, value in enumerate(raw)), reverse=True)
    for _, index in fractional[:remainder]:
        counts[index] += 1
    return counts


def detail_hint(effect: str, phase_index: int, phase_progress: float, phase_name: str) -> str:
    hints = STATE_DETAIL_HINTS.get(effect)
    if hints and phase_index < len(hints):
        early_hint, late_hint = hints[phase_index]
        return early_hint if phase_progress < 0.5 else late_hint
    if phase_progress < 0.5:
        return f"earlier {phase_name} state, tighter and less diffuse than the later phase"
    return f"later {phase_name} state, slightly broader and softer than the earlier phase"


def normalize_background_prompt(base_prompt: str, background: str) -> str:
    if background == "transparent":
        return base_prompt.replace("black background", "transparent background")
    if background in {"black", "#000000", "#000000ff", "0,0,0", "0,0,0,255"}:
        return base_prompt.replace("transparent background", "black background")
    return base_prompt


def build_prompt(base_prompt: str, phase_name: str, detail: str, prompt_prefix: str, prompt_suffix: str) -> str:
    parts = [
        prompt_prefix.strip(),
        base_prompt.strip(),
        phase_name.strip(),
        detail.strip(),
        "isolated VFX element only",
        "no environment",
        "no characters",
        "no props",
        "no text",
        "no UI",
        "preserve the same framing, camera, and effect family as the accepted previous frame",
        prompt_suffix.strip(),
    ]
    return ", ".join(part for part in parts if part)


def build_edit_prompt(generate_prompt: str, phase_name: str) -> str:
    parts = [
        generate_prompt,
        "use the supplied reference image as the accepted previous frame in the same phase",
        "preserve the same framing, subject scale, background policy, and effect family",
        f"advance by one small temporal step later within the {phase_name} phase",
        "evolve the motion instead of inventing a fresh composition",
    ]
    return ", ".join(part for part in parts if part)


def build_frames(spec: dict, effect: str, prompt_prefix: str, prompt_suffix: str, background: str) -> tuple[list[PlannedPhase], list[PlannedFrame]]:
    anchor_prompts = spec["anchor_prompts"]
    phase_names = [anchor["state"] for anchor in anchor_prompts]
    weights = weights_for_effect(effect, len(phase_names))
    counts = distribute_counts(spec["target_cells"], weights)
    base_prompt = normalize_background_prompt(spec["base_prompt"], background)

    phases: list[PlannedPhase] = []
    frames: list[PlannedFrame] = []
    frame_index = 1
    for phase_index, phase_name in enumerate(phase_names):
        phase_count = counts[phase_index]
        start_frame_index = frame_index
        for local_index in range(phase_count):
            phase_progress = 0.0 if phase_count == 1 else local_index / (phase_count - 1)
            global_progress = 0.0 if spec["target_cells"] == 1 else (frame_index - 1) / (spec["target_cells"] - 1)
            generate_prompt = build_prompt(
                base_prompt,
                phase_name,
                detail_hint(effect, phase_index, phase_progress, phase_name),
                prompt_prefix,
                prompt_suffix,
            )
            is_anchor = local_index == 0
            frames.append(
                PlannedFrame(
                    frame_index=frame_index,
                    filename=f"frame_{frame_index:03d}.png",
                    phase_index=phase_index,
                    phase_name=phase_name,
                    phase_frame_index=local_index + 1,
                    phase_frame_count=phase_count,
                    phase_progress=round(phase_progress, 4),
                    global_progress=round(global_progress, 4),
                    is_anchor=is_anchor,
                    prompt=generate_prompt,
                    edit_prompt=build_edit_prompt(generate_prompt, phase_name),
                    preferred_operation="generate" if is_anchor else "edit",
                    reference_strategy=(
                        "text-only anchor candidate; accept or replace before filling the rest of this phase"
                        if is_anchor
                        else "prefer image-reference edit using the accepted anchor or previous accepted frame in the same phase"
                    ),
                )
            )
            frame_index += 1
        phases.append(
            PlannedPhase(
                phase_index=phase_index,
                phase_number=phase_index + 1,
                phase_name=phase_name,
                start_frame_index=start_frame_index,
                end_frame_index=frame_index - 1,
                frame_count=phase_count,
                anchor_frame_index=start_frame_index,
                anchor_filename=f"frame_{start_frame_index:03d}.png",
            )
        )
    return phases, frames


def write_plan_files(
    spec: dict,
    spec_path: Path,
    effect: str,
    phases: list[PlannedPhase],
    frames: list[PlannedFrame],
    background: str,
    quality: str,
    output_format: str,
    provider_mode: str,
    frame_plan_name: str,
    script_name: str,
    runner_script_name: str,
    manual_guide_name: str,
    summary_name: str,
) -> Path:
    job_root = spec_path.parent
    generated_frames_dir = Path(spec["output_paths"]["generated_frames"])
    generated_frames_dir.mkdir(parents=True, exist_ok=True)
    size = f'{spec["generation_canvas"]["width"]}x{spec["generation_canvas"]["height"]}'
    runner_script_path = Path(__file__).resolve().with_name("flipbook_batch_runner.py")
    frame_plan_path = job_root / frame_plan_name

    plan_payload = {
        "tool": "flipbook_batch_plan",
        "spec_path": str(spec_path),
        "effect": effect,
        "default_provider_mode": provider_mode,
        "size": size,
        "background": background,
        "quality": quality,
        "output_format": output_format,
        "generated_frames_dir": str(generated_frames_dir),
        "phases": [asdict(phase) for phase in phases],
        "runner": {
            "script_path": str(runner_script_path),
            "state_path": str(job_root / "batch-run-state.json"),
            "status_command": f'python "{runner_script_path}" status "{frame_plan_path}"',
            "run_command": f'python "{runner_script_path}" run "{frame_plan_path}" --provider {provider_mode}',
            "approve_anchor_example": f'python "{runner_script_path}" approve-anchor "{frame_plan_path}" --phase 1',
            "reject_anchor_example": f'python "{runner_script_path}" reject-anchor "{frame_plan_path}" --phase 1 --reason "anchor drifted"',
            "import_frame_example": f'python "{runner_script_path}" import-frame "{frame_plan_path}" --frame 1 --path "D:/path/to/generated/frame_001.png" --approve-anchor',
        },
        "frames": [asdict(frame) for frame in frames],
    }
    frame_plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    script_lines = [
        '$ErrorActionPreference = "Stop"',
        f"$cmImageGen = {ps_quote(CM_GENERATION_SCRIPT)}",
        f"$outDir = {ps_quote(str(generated_frames_dir))}",
        "",
    ]
    for frame in frames:
        script_lines.append(
            "python $cmImageGen generate "
            f"--prompt {ps_quote(frame.prompt)} "
            f"--size {size} "
            f"--quality {quality} "
            f"--background {background} "
            f"--output-format {output_format} "
            "--out-dir $outDir "
            f"--filename {ps_quote(frame.filename)}"
        )
    (job_root / script_name).write_text("\n".join(script_lines) + "\n", encoding="utf-8")

    runner_lines = [
        '$ErrorActionPreference = "Stop"',
        f"$runner = {ps_quote(str(runner_script_path))}",
        f"$plan = {ps_quote(str(frame_plan_path))}",
        "",
        "python $runner status $plan",
        f"python $runner run $plan --provider {provider_mode}",
        "# After reviewing the generated anchor, approve it with:",
        "# python $runner approve-anchor $plan --phase 1",
    ]
    (job_root / runner_script_name).write_text("\n".join(runner_lines) + "\n", encoding="utf-8")

    manual_lines = [
        f"# System Imagegen Guide: {effect}",
        "",
        f"- Default provider mode: `{provider_mode}`",
        f"- Frame plan: `{frame_plan_path}`",
        f"- Generated frames dir: `{generated_frames_dir}`",
        "",
        "## Manual Loop",
        "",
        f'- Inspect next step: `{plan_payload["runner"]["run_command"]}`',
        "- Use the assistant-side built-in `imagegen` to generate the requested anchor or fill frame(s).",
        "- Save or copy accepted results into the expected output path under `generated-frames/`.",
        f'- Register a saved file: `{plan_payload["runner"]["import_frame_example"]}`',
        "- Approve or reject anchors after review before filling the rest of a phase.",
        "",
        "## Notes",
        "",
        "- `system-imagegen` is the default route for this skill now.",
        "- The optional cm-imagegen PowerShell script is still emitted as a fallback automation path.",
        "- When the runner emits a phase fill packet, later frames may reference the expected output path of the previous frame in the same phase.",
    ]
    (job_root / manual_guide_name).write_text("\n".join(manual_lines) + "\n", encoding="utf-8")

    summary_lines = [
        f"# Flipbook Batch Plan: {effect}",
        "",
        f"- Job spec: `{spec_path}`",
        f"- Default provider mode: `{provider_mode}`",
        f"- Frames: `{len(frames)}`",
        f"- Output size: `{size}`",
        f"- Generated frames dir: `{generated_frames_dir}`",
        f"- Frame plan: `{frame_plan_path}`",
        f"- System imagegen guide: `{job_root / manual_guide_name}`",
        f"- Optional cm-imagegen script: `{job_root / script_name}`",
        f"- Phase runner script: `{job_root / runner_script_name}`",
        "",
        "## Phase Counts",
    ]
    for phase in phases:
        summary_lines.append(
            f"- `Phase {phase.phase_number}: {phase.phase_name}`: `{phase.frame_count}` frames "
            f"(anchor `frame_{phase.anchor_frame_index:03d}.png`)"
        )
    summary_lines.extend(
        [
            "",
            "## Runner Commands",
            f'- Status: `{plan_payload["runner"]["status_command"]}`',
            f'- Run next step: `{plan_payload["runner"]["run_command"]}`',
            f'- Import a generated frame: `{plan_payload["runner"]["import_frame_example"]}`',
            f'- Approve first anchor example: `{plan_payload["runner"]["approve_anchor_example"]}`',
            f'- Reject anchor example: `{plan_payload["runner"]["reject_anchor_example"]}`',
            "",
            "## Notes",
            "- `system-imagegen` is now the default provider mode for this skill.",
            "- The runner is the preferred path when temporal consistency matters.",
            "- The runner can emit manual system-imagegen steps by default, and cm-imagegen automation only when explicitly requested.",
            "- After an anchor is approved, later frames in that phase can prefer image-reference edit rather than fresh text generation.",
        ]
    )
    (job_root / summary_name).write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return frame_plan_path


def main() -> int:
    args = parse_args()
    spec_path = Path(args.spec_path).expanduser().resolve()
    spec = load_spec(spec_path)
    effect = args.effect or spec["effect"]
    phases, frames = build_frames(spec, effect, args.prompt_prefix, args.prompt_suffix, args.background)
    frame_plan_path = write_plan_files(
        spec,
        spec_path,
        effect,
        phases,
        frames,
        args.background,
        args.quality,
        args.output_format,
        args.provider_mode,
        args.frame_plan_name,
        args.script_name,
        args.runner_script_name,
        args.manual_guide_name,
        args.summary_name,
    )
    print(frame_plan_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
