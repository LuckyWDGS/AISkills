from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text


BACKGROUND_PRESETS = {
    "black": {"background_preset": "black", "light_rig": "dark"},
    "neutral": {"background_preset": "neutral", "light_rig": "studio"},
    "gray": {"background_preset": "neutral", "light_rig": "studio"},
    "bright": {"background_preset": "bright", "light_rig": "bright"},
    "busy": {"background_preset": "busy", "light_rig": "contrast"},
}

LIGHT_RIGS = {"studio", "contrast", "bright", "dark"}


def material_preview_tool() -> Path:
    return Path(__file__).resolve().parents[2] / "tools" / "material_preview.py"


def parse_exposure_bias(value: str) -> float:
    token = str(value or "0").strip().lower()
    aliases = {
        "black": -1.0,
        "dark": -1.0,
        "low": -0.75,
        "neutral": 0.0,
        "mid": 0.0,
        "0": 0.0,
        "high": 0.75,
        "bright": 1.0,
    }
    if token in aliases:
        return aliases[token]
    return float(token)


def resolved_environment(args: argparse.Namespace) -> dict[str, Any]:
    preset = BACKGROUND_PRESETS.get(str(args.background).strip().lower(), {"background_preset": str(args.background).strip().lower() or "neutral", "light_rig": "studio"})
    light_rig = args.light_rig or preset.get("light_rig") or "studio"
    if light_rig not in LIGHT_RIGS:
        raise SystemExit(f"Unsupported light rig `{light_rig}`.")
    return {
        "background": args.background,
        "background_preset": preset.get("background_preset") or "neutral",
        "exposure": args.exposure,
        "exposure_bias": parse_exposure_bias(args.exposure),
        "light_rig": light_rig,
    }


def build_preview_command(args: argparse.Namespace, environment: dict[str, Any], out: Path | None = None) -> list[str]:
    """The capture to run once the environment is staged; MCP cannot apply background/exposure/light rig itself."""
    del environment  # Recorded in the report; the user stages it in the level.
    command = [
        sys.executable,
        str(material_preview_tool()),
        "capture",
        args.material_path,
        "--root",
        str(args.root),
        "--route",
        "thumbnail" if args.carrier == "mesh" else "viewport",
        "--carrier",
        args.carrier,
    ]
    if args.effect:
        command.extend(["--effect", args.effect])
    if args.pose:
        command.extend(["--pose", args.pose])
    if out:
        command.extend(["--out", str(out)])
    if args.project:
        command.extend(["--project", args.project])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    if args.markdown_previews:
        command.append("--markdown")
    return command


def command_text(command: list[str]) -> str:
    return " ".join(json.dumps(part) if (" " in part or "\t" in part) else part for part in command)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    environment = resolved_environment(args)
    effect = slugify(args.effect or args.material_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "preview-environments", effect, f"{slugify(args.material_path)}-{args.carrier}-{environment['background']}-{environment['exposure']}", ".json")
    preview_command = build_preview_command(args, environment)
    preview_payload: dict[str, Any] | None = None
    preview_report_path = ""
    status = "planned"
    detail = "Stage the background, exposure and light rig in the level, then rerun with --execute --staged."
    completed_stdout = ""
    completed_stderr = ""
    exit_code: int | None = None
    if args.execute:
        completed = subprocess.run(preview_command, capture_output=True, text=True, check=False)
        exit_code = completed.returncode
        completed_stdout = completed.stdout.strip()
        completed_stderr = completed.stderr.strip()
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        preview_report_path = lines[-1] if lines else ""
        if preview_report_path and Path(preview_report_path).exists():
            try:
                preview_payload = json.loads(Path(preview_report_path).read_text(encoding="utf-8"))
            except Exception:
                preview_payload = None
        shaded_ok = bool(((preview_payload or {}).get("outputs") or {}).get("shaded_ok"))
        if completed.returncode != 0 or not shaded_ok:
            status = "fail"
        else:
            # The capture only proves this environment when the user staged it first.
            status = "pass" if args.staged else "captured_unstaged"
        detail = f"preview_report={preview_report_path or 'missing'} shaded_ok={shaded_ok} staged={args.staged}."
    report = {
        "tool": "preview_environment_executor",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": args.effect or "",
        "material_path": args.material_path,
        "carrier": args.carrier,
        "environment": {**environment, "applied_by": "user staging" if args.staged else "not staged"},
        "preview_command": preview_command,
        "preview_command_text": command_text(preview_command),
        "preview_report_path": preview_report_path,
        "preview_tool": (preview_payload or {}).get("tool") if preview_payload else "",
        "outputs": ((preview_payload or {}).get("outputs") or {}),
        "status": status,
        "detail": detail,
        "stdout": completed_stdout,
        "stderr": completed_stderr,
        "exit_code": exit_code,
        "gate": {
            "executed": bool(args.execute),
            "passed": status == "pass",
            "preview_report_available": bool(preview_report_path),
        },
        "next_actions": [next_action(status, preview_report_path)],
    }
    return report, out


def next_action(status: str, preview_report_path: str) -> str:
    if status == "pass":
        return "Feed the preview report into preview_matrix.py --cell-report, preview_readability_score.py, or material_regression.py."
    if status == "captured_unstaged":
        return "The capture shows whatever the level holds; stage this environment and rerun with --execute --staged."
    if status == "fail":
        return f"The capture failed ({preview_report_path or 'no report'}); check the editor connection and the staged carrier."
    return "Stage the background, exposure and light rig in the level, then rerun with --execute --staged."


def render_markdown(report: dict[str, Any]) -> str:
    env = report.get("environment") or {}
    lines = [
        f"# Preview Environment Executor: {report.get('material_path')}",
        "",
        f"- Carrier: `{report.get('carrier')}`",
        f"- Background: `{env.get('background')}` -> `{env.get('background_preset')}`",
        f"- Exposure: `{env.get('exposure')}` -> `{env.get('exposure_bias')}`",
        f"- Light rig: `{env.get('light_rig')}`",
        f"- Executed: `{(report.get('gate') or {}).get('executed')}`",
        f"- Passed: `{(report.get('gate') or {}).get('passed')}`",
        f"- Preview report: `{report.get('preview_report_path') or 'none'}`",
        "",
        "## Next Actions",
        "",
    ]
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.strict and args.execute and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and capture a material preview in a staged background/exposure/light-rig environment.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--material-path", required=True)
    parser.add_argument("--effect", default="")
    parser.add_argument("--carrier", default="mesh", choices=["mesh", "sprite", "ribbon", "sprite_card", "ribbon_card", "decal", "post_process"])
    parser.add_argument("--mesh", default="shaderball")
    parser.add_argument("--template-system", default="")
    parser.add_argument(
        "--verify-system-path",
        default="",
        help=(
            "Forward an optional provided Niagara System path to material_preview.py for external "
            "material-side contract comparison; this is not full live Niagara integration validation."
        ),
    )
    parser.add_argument("--lighting", default="hdri")
    parser.add_argument("--background", default="neutral")
    parser.add_argument("--exposure", default="0")
    parser.add_argument("--light-rig", default="")
    parser.add_argument("--resolution", type=int, default=512)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--yaw", type=float, default=30.0)
    parser.add_argument("--pitch", type=float, default=15.0)
    parser.add_argument("--distance", type=float, default=0.0)
    parser.add_argument("--fov", type=float, default=35.0)
    parser.add_argument("--sim-time", type=float, default=1.0)
    parser.add_argument("--with-complexity", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--pose", default="", help="Viewport camera pose x,y,z,pitch,yaw,roll for the capture.")
    parser.add_argument("--execute", action="store_true", help="Capture the current level through Epic MCP.")
    parser.add_argument("--staged", action="store_true", help="Confirm the background, exposure and light rig are staged in the level.")
    parser.add_argument("--markdown-previews", action="store_true", help="Also ask material_preview.py to emit Markdown.")
    parser.add_argument("--complexity-out", default="")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
