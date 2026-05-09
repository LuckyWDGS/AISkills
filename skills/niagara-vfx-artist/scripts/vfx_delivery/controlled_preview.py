from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from .bridge import BridgeClient
from .core import default_report_path, ensure_dir, load_json, resolve_root_context, save_json, slugify, utc_now_iso, write_text


PRESET_NAMES = ("studio-plane", "studio-actor", "niagara-sandbox")


def preset_dir(ctx) -> Path:
    return ensure_dir(ctx.vfx_root / "preview-presets")


def preset_path(ctx, name: str) -> Path:
    return preset_dir(ctx) / f"{slugify(name)}.json"


def default_preset(name: str) -> dict:
    base = {
        "name": name,
        "description": "",
        "capture_mode": "material",
        "view_mode": "Lit",
        "resolution": 1024,
        "yaw": 35.0,
        "pitch": -15.0,
        "fov": 40.0,
        "distance": 0.0,
        "distance_scale": 2.6,
        "cleanup_after": True,
        "show_flags": {"Grid": False, "SelectionOutline": False, "ModeWidgets": False},
    }
    if name == "studio-actor":
        base["capture_mode"] = "actor"
    elif name == "niagara-sandbox":
        base["capture_mode"] = "niagara"
        base["cleanup_after"] = True
        base["distance_scale"] = 3.0
    return base


def load_preset(ctx, name: str) -> dict:
    return load_json(
        preset_path(ctx, name),
        {
            "version": 1,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            **default_preset(name),
        },
    )


def save_preset(ctx, payload: dict) -> Path:
    payload["updated_at"] = utc_now_iso()
    path = preset_path(ctx, payload["name"])
    save_json(path, payload)
    return path


def material_script(material_path: str, out_png: str, mesh: str, lighting: str, resolution: int, yaw: float, pitch: float, distance: float) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal
        ok = unreal.UnrealBridgeMaterialLibrary.preview_material(
            {material_path!r},
            {mesh!r},
            {lighting!r},
            {resolution},
            {yaw},
            {pitch},
            {distance},
            {out_png!r},
        )
        print(json.dumps({{"success": bool(ok), "out_png": {out_png!r}}}, ensure_ascii=False))
        """
    ).strip()


def actor_script(actor_name: str, out_png: str, yaw: float, pitch: float, distance_scale: float, fov: float, mode: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import math
        import unreal

        ED = unreal.UnrealBridgeEditorLibrary
        LV = unreal.UnrealBridgeLevelLibrary

        old_camera = ED.get_editor_viewport_camera()
        old_mode = ED.get_viewport_view_mode()
        old_realtime = ED.is_viewport_realtime()
        flags = ["Grid", "SelectionOutline", "ModeWidgets"]
        old_flags = {{}}
        for flag in flags:
            old_flags[flag] = ED.get_viewport_show_flag(flag)

        bounds = LV.get_actor_bounds({actor_name!r})
        center = bounds.bounds_origin
        radius = max(bounds.bounds_sphere_radius, 50.0)
        distance = max(radius * {distance_scale}, 150.0)

        yaw_rad = math.radians({yaw})
        pitch_rad = math.radians({pitch})
        camera = unreal.Vector(
            center.x + math.cos(pitch_rad) * math.cos(yaw_rad) * distance,
            center.y + math.cos(pitch_rad) * math.sin(yaw_rad) * distance,
            center.z + math.sin(pitch_rad) * distance,
        )
        rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)

        LV.deselect_all_actors()
        ED.set_viewport_realtime(True)
        ED.set_viewport_view_mode({mode!r})
        for flag in flags:
            ED.set_viewport_show_flag(flag, False)
        ED.set_editor_viewport_camera(camera, rotation, {fov})
        ED.capture_active_viewport({out_png!r}, False)

        ED.set_editor_viewport_camera(old_camera.location, old_camera.rotation, old_camera.fov)
        ED.set_viewport_view_mode(old_mode)
        ED.set_viewport_realtime(old_realtime)
        for flag, value in old_flags.items():
            ED.set_viewport_show_flag(flag, value)

        print(json.dumps({{
            "success": True,
            "out_png": {out_png!r},
            "camera_location": [camera.x, camera.y, camera.z],
            "camera_rotation": [rotation.pitch, rotation.yaw, rotation.roll],
            "bounds_radius": radius,
        }}, ensure_ascii=False))
        """
    ).strip()


def niagara_script(system_path: str, out_png: str, yaw: float, pitch: float, distance_scale: float, fov: float, mode: str, cleanup_after: bool) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        LV = unreal.UnrealBridgeLevelLibrary

        actor_name = LV.spawn_actor("/Script/Engine.Actor", unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        LV.add_actor_tag(actor_name, "CodexVFXPreviewTemp")
        component_name = LV.add_component_of_class(actor_name, "/Script/Niagara.NiagaraComponent")

        editor_actor = None
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for actor in subsystem.get_all_level_actors():
            if actor.get_name() == actor_name or actor.get_actor_label() == actor_name:
                editor_actor = actor
                break

        if editor_actor is None:
            raise RuntimeError(f"Unable to resolve spawned preview actor: {{actor_name}}")

        niagara_component = None
        for component in editor_actor.get_components_by_class(unreal.NiagaraComponent):
            if component.get_name() == component_name:
                niagara_component = component
                break
        if niagara_component is None:
            raise RuntimeError(f"Unable to resolve Niagara component: {{component_name}}")

        system_asset = unreal.load_asset({system_path!r})
        niagara_component.set_asset(system_asset)
        niagara_component.activate(True)

        exec({actor_script("__PREVIEW_ACTOR__", out_png, yaw, pitch, distance_scale, fov, mode)!r}.replace("__PREVIEW_ACTOR__", actor_name))

        if {cleanup_after!r}:
            LV.destroy_actor(actor_name)
        """
    ).strip()


def material_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    out_png = Path(args.out) if args.out else default_report_path(ctx, "previews/material", slugify(args.material_path), "material-preview", ".png")
    result = client.exec_json(
        material_script(args.material_path, str(out_png), args.mesh, args.lighting, args.resolution, args.yaw, args.pitch, args.distance)
    )
    save_json(out_png.with_suffix(".json"), result)
    print(out_png)
    return 0


def actor_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    out_png = Path(args.out) if args.out else default_report_path(ctx, "previews/actor", slugify(args.actor_name), "actor-preview", ".png")
    result = client.exec_json(actor_script(args.actor_name, str(out_png), args.yaw, args.pitch, args.distance_scale, args.fov, args.view_mode))
    save_json(out_png.with_suffix(".json"), result)
    print(out_png)
    return 0


def preset_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    preset = load_preset(ctx, args.name)
    if args.description:
        preset["description"] = args.description
    if args.capture_mode:
        preset["capture_mode"] = args.capture_mode
    if args.view_mode:
        preset["view_mode"] = args.view_mode
    if args.resolution:
        preset["resolution"] = args.resolution
    if args.yaw is not None:
        preset["yaw"] = args.yaw
    if args.pitch is not None:
        preset["pitch"] = args.pitch
    if args.fov is not None:
        preset["fov"] = args.fov
    if args.distance is not None:
        preset["distance"] = args.distance
    if args.distance_scale is not None:
        preset["distance_scale"] = args.distance_scale
    preset["cleanup_after"] = not args.no_cleanup_after
    if args.show_flag:
        for item in args.show_flag:
            if "=" not in item:
                raise SystemExit(f"Expected flag=true/false, got: {item}")
            key, value = item.split("=", 1)
            preset.setdefault("show_flags", {})[key] = value.lower() in {"1", "true", "yes", "on"}
    path = save_preset(ctx, preset)
    print(path)
    return 0


def render_preset_markdown(preset: dict) -> str:
    lines = [
        f"# Preview Preset: {preset['name']}",
        "",
        f"- Capture mode: `{preset['capture_mode']}`",
        f"- View mode: `{preset['view_mode']}`",
        f"- Resolution: `{preset['resolution']}`",
        f"- FOV: `{preset['fov']}`",
        f"- Distance scale: `{preset['distance_scale']}`",
        f"- Cleanup after capture: `{preset['cleanup_after']}`",
        "",
        "## Show Flags",
        "",
    ]
    for key, value in preset.get("show_flags", {}).items():
        lines.append(f"- `{key}` = `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def preset_show_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    preset = load_preset(ctx, args.name)
    print(json.dumps(preset, ensure_ascii=False, indent=2))
    return 0


def preset_export_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    preset = load_preset(ctx, args.name)
    out_path = Path(args.out) if args.out else preset_path(ctx, args.name).with_suffix(".md")
    write_text(out_path, render_preset_markdown(preset))
    print(out_path)
    return 0


def niagara_command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    preset = load_preset(ctx, args.preset or "niagara-sandbox")
    out_png = Path(args.out) if args.out else default_report_path(ctx, "previews/niagara", slugify(args.system_path), "niagara-preview", ".png")
    result = client.exec_json(
        niagara_script(
            args.system_path,
            str(out_png),
            args.yaw if args.yaw is not None else preset["yaw"],
            args.pitch if args.pitch is not None else preset["pitch"],
            args.distance_scale if args.distance_scale is not None else preset["distance_scale"],
            args.fov if args.fov is not None else preset["fov"],
            args.view_mode or preset["view_mode"],
            args.cleanup_after if args.cleanup_after else preset["cleanup_after"],
        )
    )
    save_json(out_png.with_suffix(".json"), result)
    print(out_png)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create controlled VFX previews without relying on editor UI screenshots.")
    parser.add_argument("--root", default="auto")
    subparsers = parser.add_subparsers(dest="command", required=True)

    material = subparsers.add_parser("material")
    material.add_argument("material_path")
    material.add_argument("--project")
    material.add_argument("--timeout", type=int, default=180)
    material.add_argument("--out")
    material.add_argument("--mesh", default="plane")
    material.add_argument("--lighting", default="studio")
    material.add_argument("--resolution", type=int, default=1024)
    material.add_argument("--yaw", type=float, default=35.0)
    material.add_argument("--pitch", type=float, default=-15.0)
    material.add_argument("--distance", type=float, default=0.0)
    material.set_defaults(func=material_command)

    actor = subparsers.add_parser("actor")
    actor.add_argument("actor_name")
    actor.add_argument("--project")
    actor.add_argument("--timeout", type=int, default=180)
    actor.add_argument("--out")
    actor.add_argument("--yaw", type=float, default=45.0)
    actor.add_argument("--pitch", type=float, default=15.0)
    actor.add_argument("--distance-scale", type=float, default=2.6)
    actor.add_argument("--fov", type=float, default=40.0)
    actor.add_argument("--view-mode", default="Lit")
    actor.set_defaults(func=actor_command)

    niagara = subparsers.add_parser("niagara")
    niagara.add_argument("system_path")
    niagara.add_argument("--project")
    niagara.add_argument("--timeout", type=int, default=240)
    niagara.add_argument("--out")
    niagara.add_argument("--yaw", type=float, default=45.0)
    niagara.add_argument("--pitch", type=float, default=15.0)
    niagara.add_argument("--distance-scale", type=float, default=2.6)
    niagara.add_argument("--fov", type=float, default=40.0)
    niagara.add_argument("--view-mode", default="Lit")
    niagara.add_argument("--preset")
    niagara.add_argument("--cleanup-after", action="store_true")
    niagara.set_defaults(func=niagara_command)

    preset = subparsers.add_parser("preset")
    preset_sub = preset.add_subparsers(dest="preset_command", required=True)

    preset_set = preset_sub.add_parser("set")
    preset_set.add_argument("name")
    preset_set.add_argument("--description", default="")
    preset_set.add_argument("--capture-mode", choices=list(PRESET_NAMES) + ["material", "actor", "niagara"])
    preset_set.add_argument("--view-mode")
    preset_set.add_argument("--resolution", type=int)
    preset_set.add_argument("--yaw", type=float)
    preset_set.add_argument("--pitch", type=float)
    preset_set.add_argument("--fov", type=float)
    preset_set.add_argument("--distance", type=float)
    preset_set.add_argument("--distance-scale", type=float)
    preset_set.add_argument("--no-cleanup-after", action="store_true")
    preset_set.add_argument("--show-flag", action="append", default=[])
    preset_set.set_defaults(func=preset_command)

    preset_show = preset_sub.add_parser("show")
    preset_show.add_argument("name")
    preset_show.set_defaults(func=preset_show_command)

    preset_export = preset_sub.add_parser("export-md")
    preset_export.add_argument("name")
    preset_export.add_argument("--out")
    preset_export.set_defaults(func=preset_export_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
