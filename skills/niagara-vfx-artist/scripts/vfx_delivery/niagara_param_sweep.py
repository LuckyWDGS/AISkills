from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .bridge import BridgeClient
from .control_common import find_control, load_control_schema, numeric_probe_values, resolve_root
from .core import default_report_path, normalize_cli_global_args, save_json, slugify, utc_now_iso, write_text


def build_sweep_capture_script(
    *,
    system_path: str,
    variable_name: str,
    type_object_path: str,
    value_struct_path: str,
    value_json: str,
    out_png: str,
    sim_time: float,
) -> str:
    return textwrap.dedent(
        f"""
        import json
        import math
        import unreal

        LV = unreal.UnrealBridgeLevelLibrary
        NIA = unreal.UnrealBridgeNiagaraLibrary
        system_path = {system_path!r}
        variable_name = {variable_name!r}
        type_object_path = {type_object_path!r}
        value_struct_path = {value_struct_path!r}
        value_json = {value_json!r}
        out_png = {out_png!r}
        sim_time = {sim_time}

        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        center = unreal.Vector(500000.0, 500000.0, 500000.0)
        actor_name = LV.spawn_actor("/Script/Niagara.NiagaraActor", center, unreal.Rotator(0, 0, 0))
        result = {{
            "success": False,
            "out_png": out_png,
            "component_path": "",
            "summary": {{}},
        }}

        def resolve_actor(name):
            for actor in actor_sub.get_all_level_actors():
                if actor.get_name() == name or actor.get_actor_label() == name:
                    return actor
            return None

        try:
            system_asset = unreal.EditorAssetLibrary.load_asset(system_path)
            if not system_asset:
                raise RuntimeError(f"Could not load Niagara system: {{system_path}}")
            actor = resolve_actor(actor_name)
            if actor is None:
                raise RuntimeError(f"Could not resolve spawned preview actor: {{actor_name}}")
            comps = list(actor.get_components_by_class(unreal.NiagaraComponent))
            comp = comps[-1] if comps else None
            if comp is None:
                raise RuntimeError("Could not find NiagaraComponent on preview actor.")
            comp.set_asset(system_asset)
            comp.set_world_location(center, False, False)
            comp.set_bounds_scale(12.0)
            comp.set_can_render_while_seeking(True)
            comp.set_rendering_enabled(True)
            comp.set_age_update_mode(unreal.NiagaraAgeUpdateMode.DESIRED_AGE)
            comp.set_seek_delta(1.0 / 60.0)
            comp.set_desired_age(sim_time)
            comp.activate(True)
            comp.seek_to_desired_age(sim_time)
            component_path = comp.get_path_name()
            result["component_path"] = component_path
            summary = NIA.set_official_component_variable(component_path, variable_name, type_object_path, value_struct_path, value_json)
            result["summary"] = {{
                "success": bool(summary.success),
                "error": str(summary.error),
                "component_path": str(summary.component_path),
                "name": str(summary.name),
                "type_name": str(summary.type_name),
                "type_object_path": str(summary.type_path),
                "value_struct_path": str(summary.value_struct_path),
                "value_json": str(summary.value_json),
            }}
            comp.reset_system()
            yaw = math.radians(35.0)
            pitch = math.radians(10.0)
            distance = 420.0
            camera = unreal.Vector(
                center.x + math.cos(pitch) * math.cos(yaw) * distance,
                center.y + math.cos(pitch) * math.sin(yaw) * distance,
                center.z + math.sin(pitch) * distance,
            )
            rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
            result["capture_ok"] = bool(LV.capture_from_pose(camera, rotation, 35.0, 768, 768, out_png))
            result["success"] = True
        finally:
            actor = resolve_actor(actor_name)
            if actor is not None:
                actor_sub.destroy_actor(actor)

        print(json.dumps(result, ensure_ascii=False))
        """
    ).strip()


def build_contact_sheet(images: list[Path], labels: list[str], out_path: Path) -> None:
    frames = [Image.open(path).convert("RGBA") for path in images]
    try:
        cell_w = max(image.width for image in frames)
        cell_h = max(image.height for image in frames) + 34
        sheet = Image.new("RGBA", (cell_w * len(frames), cell_h), (24, 24, 24, 255))
        draw = ImageDraw.Draw(sheet)
        for index, frame in enumerate(frames):
            x = index * cell_w
            sheet.paste(frame, (x, 0))
            draw.text((x + 8, frame.height + 8), labels[index], fill=(255, 255, 255, 255))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out_path)
    finally:
        for frame in frames:
            frame.close()


def command_sweep(args: argparse.Namespace) -> int:
    ctx = resolve_root(args.root)
    schema = load_control_schema(args.schema)
    control = find_control(schema, args.control)
    sweep_support = str(control.get("sweep_support") or "")
    if sweep_support != "niagara_numeric_preview_sweep":
        raise SystemExit(f"Control `{control.get('id')}` does not support Niagara numeric sweep yet; sweep_support={sweep_support}.")
    if not args.system_path:
        raise SystemExit("--system-path is required for niagara_param_sweep.")

    values = list(args.value_json or [])
    if not values:
        values = list(control.get("suggested_sweep_values") or [])
    if not values:
        values = numeric_probe_values(control)
    effect = str(schema.get("effect_name") or "Effect")
    stem = slugify(control["id"])
    out_dir = Path(args.out_dir) if args.out_dir else default_report_path(ctx, "niagara-param-sweeps", effect, stem, "").parent
    out_dir.mkdir(parents=True, exist_ok=True)

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    captures = []
    png_paths: list[Path] = []
    labels: list[str] = []
    for index, value_json in enumerate(values):
        png_path = out_dir / f"{stem}-value-{index:02d}.png"
        raw = client.exec_json(
            build_sweep_capture_script(
                system_path=args.system_path,
                variable_name=str(control.get("target_name") or ""),
                type_object_path=str(control.get("type_object_path") or ""),
                value_struct_path=str(control.get("value_struct_path") or ""),
                value_json=value_json,
                out_png=str(png_path),
                sim_time=args.sim_time,
            ),
            no_preflight=True,
        )
        captures.append(
            {
                "index": index,
                "value_json": value_json,
                "png": str(png_path),
                "raw": raw,
            }
        )
        png_paths.append(png_path)
        labels.append(value_json)

    contact_sheet = out_dir / f"{stem}-contact-sheet.png"
    build_contact_sheet(png_paths, labels, contact_sheet)
    report = {
        "tool": "niagara_param_sweep",
        "generated_utc": utc_now_iso(),
        "effect_name": effect,
        "control_id": control.get("id", ""),
        "system_path": args.system_path,
        "captures": captures,
        "contact_sheet_png": str(contact_sheet),
        "value_count": len(values),
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "niagara-param-sweeps", effect, stem, ".json")
    save_json(out, report)
    if args.markdown:
        lines = [f"# Niagara Param Sweep: {control.get('id', '')}", "", f"- System: `{args.system_path}`", f"- Contact sheet: `{contact_sheet}`", ""]
        for item in captures:
            lines.append(f"- `{item['value_json']}` -> `{item['png']}` success=`{(item.get('raw') or {}).get('success')}`")
        write_text(out.with_suffix(".md"), "\n".join(lines).rstrip() + "\n")
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sweep a Niagara runtime control across multiple values and capture a comparison sheet.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--system-path", required=True)
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--value-json", action="append", default=[])
    parser.add_argument("--sim-time", type=float, default=1.0)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command_sweep)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands=set())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
