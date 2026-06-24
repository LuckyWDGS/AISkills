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
    command = [
        sys.executable,
        str(material_preview_tool()),
        "render",
        args.material_path,
        "--root",
        str(args.root),
        "--carrier",
        args.carrier,
        "--mesh",
        args.mesh,
        "--lighting",
        args.lighting,
        "--resolution",
        str(args.resolution),
        "--yaw",
        str(args.yaw),
        "--pitch",
        str(args.pitch),
        "--distance",
        str(args.distance),
        "--fov",
        str(args.fov),
        "--sim-time",
        str(args.sim_time),
        "--background-preset",
        str(environment["background_preset"]),
        "--exposure-bias",
        str(environment["exposure_bias"]),
        "--light-rig",
        str(environment["light_rig"]),
    ]
    if args.width:
        command.extend(["--width", str(args.width)])
    if args.height:
        command.extend(["--height", str(args.height)])
    if args.effect:
        command.extend(["--effect", args.effect])
    if args.template_system:
        command.extend(["--template-system", args.template_system])
    if args.verify_system_path:
        command.extend(["--verify-system-path", args.verify_system_path])
    if args.with_complexity:
        command.append("--with-complexity")
    if out:
        command.extend(["--out", str(out)])
    if args.complexity_out:
        command.extend(["--complexity-out", args.complexity_out])
    if args.project:
        command.extend(["--project", args.project])
    if args.endpoint:
        command.extend(["--endpoint", args.endpoint])
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
    preview_out = None if args.execute else None
    preview_command = build_preview_command(args, environment, out=preview_out)
    preview_payload: dict[str, Any] | None = None
    preview_report_path = ""
    status = "planned"
    detail = "Run with --execute to capture a real environment-adjusted preview."
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
        status = "pass" if completed.returncode == 0 and shaded_ok else "fail"
        detail = f"preview_report={preview_report_path or 'missing'} shaded_ok={shaded_ok}."
    report = {
        "tool": "preview_environment_executor",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": args.effect or "",
        "material_path": args.material_path,
        "carrier": args.carrier,
        "environment": environment,
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
        "next_actions": [
            "Feed the preview report into preview_matrix.py, preview_readability_score.py, or material_regression.py."
            if args.execute and preview_report_path
            else "Rerun with --execute when live UnrealBridge/UE is available."
        ],
    }
    return report, out


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
    parser = argparse.ArgumentParser(description="Execute material previews against concrete background/exposure/light-rig presets instead of intent-only preview-matrix axes.")
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
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--execute", action="store_true")
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
