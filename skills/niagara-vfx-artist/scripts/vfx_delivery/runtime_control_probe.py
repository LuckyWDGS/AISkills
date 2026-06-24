from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .bridge import BridgeClient
from .control_common import find_control, load_control_schema, numeric_probe_values, resolve_root
from .core import default_report_path, normalize_cli_global_args, save_json, slugify, utc_now_iso, write_text


def jsonish_equal(left: str, right: str) -> bool:
    try:
        return json.loads(left) == json.loads(right)
    except Exception:
        return str(left).strip() == str(right).strip()


def choose_probe_value(control: dict[str, Any], explicit_value_json: str) -> str:
    if explicit_value_json:
        return explicit_value_json
    type_blob = " ".join([str(control.get("type_name") or ""), str(control.get("type_object_path") or "")]).lower()
    default_value_json = str(control.get("default_value_json") or "").strip()
    if "bool" in type_blob:
        if default_value_json:
            try:
                payload = json.loads(default_value_json)
                value = bool(payload.get("value"))
            except Exception:
                value = False
        else:
            value = False
        return json.dumps({"value": not value}, ensure_ascii=False)
    suggested = control.get("suggested_sweep_values") or []
    if suggested:
        for item in reversed(suggested):
            if not jsonish_equal(item, default_value_json):
                return item
    return default_value_json


def resolve_roi_box(
    *,
    width: int,
    height: int,
    roi_mode: str,
    roi_scale: float,
    roi_left: int,
    roi_top: int,
    roi_right: int,
    roi_bottom: int,
) -> tuple[int, int, int, int]:
    if roi_mode == "manual-box":
        left = max(0, min(width, int(roi_left)))
        top = max(0, min(height, int(roi_top)))
        right = max(left + 1, min(width, int(roi_right)))
        bottom = max(top + 1, min(height, int(roi_bottom)))
        return left, top, right, bottom
    if roi_mode == "center-crop":
        scale = min(max(float(roi_scale), 0.05), 1.0)
        roi_width = max(1, int(round(width * scale)))
        roi_height = max(1, int(round(height * scale)))
        left = max(0, (width - roi_width) // 2)
        top = max(0, (height - roi_height) // 2)
        return left, top, min(width, left + roi_width), min(height, top + roi_height)
    return 0, 0, width, height


def estimate_brightness_roi_box(
    before_path: Path,
    after_path: Path,
    *,
    threshold: int,
    padding: int,
) -> tuple[int, int, int, int] | None:
    with Image.open(before_path) as before_img, Image.open(after_path) as after_img:
        before = before_img.convert("RGBA")
        after = after_img.convert("RGBA")
        composite = ImageChops.lighter(before, after).convert("RGB")
        brightness = composite.convert("L")
        mask = brightness.point(lambda value: 255 if value >= threshold else 0)
        bbox = mask.getbbox()
        if bbox is None:
            return None
        left = max(0, bbox[0] - padding)
        top = max(0, bbox[1] - padding)
        right = min(before.width, bbox[2] + padding)
        bottom = min(before.height, bbox[3] + padding)
        return left, top, right, bottom


def image_diff_summary(
    before_path: Path,
    after_path: Path,
    *,
    roi_box: tuple[int, int, int, int] | None = None,
    pixel_threshold: int = 1,
) -> dict[str, Any]:
    with Image.open(before_path) as before_img, Image.open(after_path) as after_img:
        before = before_img.convert("RGBA")
        after = after_img.convert("RGBA")
        if roi_box is not None:
            before = before.crop(roi_box)
            after = after.crop(roi_box)
        diff = ImageChops.difference(before, after)
        stat = ImageStat.Stat(diff)
        channel_means = [float(value) for value in stat.mean]
        mean_abs_diff = sum(channel_means) / len(channel_means)
        gray = diff.convert("L")
        bbox = gray.getbbox()
        changed_pixels = 0
        if bbox:
            binary = gray.point(lambda value: 255 if value >= pixel_threshold else 0)
            histogram = binary.histogram()
            changed_pixels = int(sum(histogram[1:]))
        return {
            "mean_abs_diff": mean_abs_diff,
            "channel_means": channel_means,
            "bbox": list(bbox) if bbox else [],
            "changed_pixels": changed_pixels,
            "roi_box": list(roi_box) if roi_box else [],
            "width": before.width,
            "height": before.height,
        }


def build_probe_script(
    *,
    system_path: str,
    component_path: str,
    type_object_path: str,
    variable_name: str,
    baseline_value_json: str,
    probe_value_json: str,
    value_struct_path: str,
    capture: bool,
    before_png: str,
    after_png: str,
    sim_time: float,
    camera_yaw: float,
    camera_pitch: float,
    camera_distance: float,
    camera_fov: float,
) -> str:
    return textwrap.dedent(
        f"""
        import json
        import math
        import unreal

        LV = unreal.UnrealBridgeLevelLibrary
        NIA = unreal.UnrealBridgeNiagaraLibrary
        SYSTEM_PATH = {system_path!r}
        COMPONENT_PATH = {component_path!r}
        VARIABLE_NAME = {variable_name!r}
        TYPE_OBJECT_PATH = {type_object_path!r}
        VALUE_STRUCT_PATH = {value_struct_path!r}
        BASELINE_VALUE_JSON = {baseline_value_json!r}
        PROBE_VALUE_JSON = {probe_value_json!r}
        CAPTURE = {capture!r}
        BEFORE_PNG = {before_png!r}
        AFTER_PNG = {after_png!r}
        SIM_TIME = {sim_time}
        CAMERA_YAW = {camera_yaw}
        CAMERA_PITCH = {camera_pitch}
        CAMERA_DISTANCE = {camera_distance}
        CAMERA_FOV = {camera_fov}

        actor_name = ""
        spawned_component_path = ""
        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        center = unreal.Vector(500000.0, 500000.0, 500000.0)
        system_asset = unreal.EditorAssetLibrary.load_asset(SYSTEM_PATH) if SYSTEM_PATH else None
        before_summary = {{}}
        after_summary = {{}}
        result = {{
            "success": False,
            "spawned_preview_actor": False,
            "actor_name": "",
            "component_path": COMPONENT_PATH,
            "before_png": BEFORE_PNG if CAPTURE else "",
            "after_png": AFTER_PNG if CAPTURE else "",
        }}

        def resolve_actor(name):
            for actor in actor_sub.get_all_level_actors():
                if actor.get_name() == name or actor.get_actor_label() == name:
                    return actor
            return None

        def capture_component(component, out_png):
            yaw = math.radians(CAMERA_YAW)
            pitch = math.radians(CAMERA_PITCH)
            distance = CAMERA_DISTANCE
            camera = unreal.Vector(
                center.x + math.cos(pitch) * math.cos(yaw) * distance,
                center.y + math.cos(pitch) * math.sin(yaw) * distance,
                center.z + math.sin(pitch) * distance,
            )
            rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
            component.reset_system()
            return bool(LV.capture_from_pose(camera, rotation, CAMERA_FOV, 768, 768, out_png))

        def summary_to_dict(summary):
            return {{
                "success": bool(summary.success),
                "error": str(summary.error),
                "component_path": str(summary.component_path),
                "name": str(summary.name),
                "type_name": str(summary.type_name),
                "type_object_path": str(summary.type_path),
                "value_struct_path": str(summary.value_struct_path),
                "value_json": str(summary.value_json),
            }}

        def spawn_preview_component():
            if system_asset is None:
                raise RuntimeError(f"Could not load Niagara system: {{SYSTEM_PATH}}")
            local_actor_name = LV.spawn_actor("/Script/Niagara.NiagaraActor", center, unreal.Rotator(0, 0, 0))
            editor_actor = resolve_actor(local_actor_name)
            if editor_actor is None:
                raise RuntimeError(f"Could not resolve spawned Niagara preview actor: {{local_actor_name}}")
            comps = list(editor_actor.get_components_by_class(unreal.NiagaraComponent))
            component = comps[-1] if comps else None
            if component is None:
                raise RuntimeError("Could not find NiagaraComponent on preview actor.")
            component.set_asset(system_asset)
            component.set_world_location(center, False, False)
            component.set_bounds_scale(12.0)
            component.set_can_render_while_seeking(True)
            component.set_rendering_enabled(True)
            component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.DESIRED_AGE)
            component.set_seek_delta(1.0 / 60.0)
            component.set_desired_age(SIM_TIME)
            component.activate(True)
            component.seek_to_desired_age(SIM_TIME)
            return local_actor_name, component

        def destroy_preview_actor(local_actor_name):
            if not local_actor_name:
                return
            actor = resolve_actor(local_actor_name)
            if actor is not None:
                actor_sub.destroy_actor(actor)

        def capture_value(value_json, out_png):
            local_actor_name = ""
            try:
                local_actor_name, component = spawn_preview_component()
                local_component_path = component.get_path_name()
                if value_json:
                    summary = NIA.set_official_component_variable(local_component_path, VARIABLE_NAME, TYPE_OBJECT_PATH, VALUE_STRUCT_PATH, value_json)
                else:
                    summary = NIA.get_official_component_variable_summary(local_component_path, VARIABLE_NAME, TYPE_OBJECT_PATH)
                capture_ok = capture_component(component, out_png)
                return local_component_path, summary_to_dict(summary), bool(capture_ok)
            finally:
                destroy_preview_actor(local_actor_name)

        component_path = COMPONENT_PATH
        preview_component = None
        try:
            if CAPTURE:
                before_component_path, before_summary, before_capture_ok = capture_value(BASELINE_VALUE_JSON, BEFORE_PNG)
                after_component_path, after_summary, after_capture_ok = capture_value(PROBE_VALUE_JSON, AFTER_PNG)
                spawned_component_path = after_component_path or before_component_path
                result["spawned_preview_actor"] = True
                result["component_path"] = spawned_component_path
                result["spawned_component_path"] = spawned_component_path
                result["before_capture_ok"] = before_capture_ok
                result["after_capture_ok"] = after_capture_ok
            else:
                if not component_path:
                    actor_name, preview_component = spawn_preview_component()
                    component_path = preview_component.get_path_name()
                    spawned_component_path = component_path
                    result["spawned_preview_actor"] = True
                    result["actor_name"] = actor_name
                    result["component_path"] = component_path
                if BASELINE_VALUE_JSON:
                    before = NIA.set_official_component_variable(component_path, VARIABLE_NAME, TYPE_OBJECT_PATH, VALUE_STRUCT_PATH, BASELINE_VALUE_JSON)
                else:
                    before = NIA.get_official_component_variable_summary(component_path, VARIABLE_NAME, TYPE_OBJECT_PATH)
                before_summary = summary_to_dict(before)
                after = NIA.set_official_component_variable(component_path, VARIABLE_NAME, TYPE_OBJECT_PATH, VALUE_STRUCT_PATH, PROBE_VALUE_JSON)
                after_summary = summary_to_dict(after)
            result["success"] = True
        finally:
            destroy_preview_actor(actor_name)

        result["before_summary"] = before_summary
        result["after_summary"] = after_summary
        result["spawned_component_path"] = spawned_component_path
        print(json.dumps(result, ensure_ascii=False))
        """
    ).strip()


def build_capture_value_script(
    *,
    system_path: str,
    variable_name: str,
    type_object_path: str,
    value_struct_path: str,
    value_json: str,
    out_png: str,
    sim_time: float,
    camera_yaw: float,
    camera_pitch: float,
    camera_distance: float,
    camera_fov: float,
) -> str:
    return textwrap.dedent(
        f"""
        import json
        import math
        import unreal

        LV = unreal.UnrealBridgeLevelLibrary
        NIA = unreal.UnrealBridgeNiagaraLibrary
        SYSTEM_PATH = {system_path!r}
        VARIABLE_NAME = {variable_name!r}
        TYPE_OBJECT_PATH = {type_object_path!r}
        VALUE_STRUCT_PATH = {value_struct_path!r}
        VALUE_JSON = {value_json!r}
        OUT_PNG = {out_png!r}
        SIM_TIME = {sim_time}
        CAMERA_YAW = {camera_yaw}
        CAMERA_PITCH = {camera_pitch}
        CAMERA_DISTANCE = {camera_distance}
        CAMERA_FOV = {camera_fov}

        actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        center = unreal.Vector(500000.0, 500000.0, 500000.0)
        system_asset = unreal.EditorAssetLibrary.load_asset(SYSTEM_PATH)
        if system_asset is None:
            raise RuntimeError(f"Could not load Niagara system: {{SYSTEM_PATH}}")

        def resolve_actor(name):
            for actor in actor_sub.get_all_level_actors():
                if actor.get_name() == name or actor.get_actor_label() == name:
                    return actor
            return None

        actor_name = LV.spawn_actor("/Script/Niagara.NiagaraActor", center, unreal.Rotator(0, 0, 0))
        result = {{
            "success": False,
            "out_png": OUT_PNG,
            "component_path": "",
            "summary": {{}},
            "capture_ok": False,
        }}

        try:
            actor = resolve_actor(actor_name)
            if actor is None:
                raise RuntimeError(f"Could not resolve spawned Niagara preview actor: {{actor_name}}")
            comps = list(actor.get_components_by_class(unreal.NiagaraComponent))
            component = comps[-1] if comps else None
            if component is None:
                raise RuntimeError("Could not find NiagaraComponent on preview actor.")
            component.set_asset(system_asset)
            component.set_world_location(center, False, False)
            component.set_bounds_scale(12.0)
            component.set_can_render_while_seeking(True)
            component.set_rendering_enabled(True)
            component.set_age_update_mode(unreal.NiagaraAgeUpdateMode.DESIRED_AGE)
            component.set_seek_delta(1.0 / 60.0)
            component.set_desired_age(SIM_TIME)
            component.activate(True)
            component.seek_to_desired_age(SIM_TIME)
            component_path = component.get_path_name()
            result["component_path"] = component_path
            if VALUE_JSON:
                summary = NIA.set_official_component_variable(component_path, VARIABLE_NAME, TYPE_OBJECT_PATH, VALUE_STRUCT_PATH, VALUE_JSON)
            else:
                summary = NIA.get_official_component_variable_summary(component_path, VARIABLE_NAME, TYPE_OBJECT_PATH)
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
            yaw = math.radians(CAMERA_YAW)
            pitch = math.radians(CAMERA_PITCH)
            distance = CAMERA_DISTANCE
            camera = unreal.Vector(
                center.x + math.cos(pitch) * math.cos(yaw) * distance,
                center.y + math.cos(pitch) * math.sin(yaw) * distance,
                center.z + math.sin(pitch) * distance,
            )
            rotation = unreal.MathLibrary.find_look_at_rotation(camera, center)
            component.reset_system()
            result["capture_ok"] = bool(LV.capture_from_pose(camera, rotation, CAMERA_FOV, 768, 768, OUT_PNG))
            result["success"] = True
        finally:
            actor = resolve_actor(actor_name)
            if actor is not None:
                actor_sub.destroy_actor(actor)

        print(json.dumps(result, ensure_ascii=False))
        """
    ).strip()


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Runtime Control Probe: {report.get('control_id', '')}", ""]
    lines.extend(
        [
            f"- Surface: `{report.get('surface', '')}`",
            f"- Runtime surface: `{report.get('runtime_surface', '')}`",
            f"- Probe passed: `{(report.get('gate') or {}).get('probe_passed')}`",
            f"- Value roundtrip passed: `{(report.get('gate') or {}).get('value_roundtrip_passed')}`",
            f"- Visual change detected: `{(report.get('gate') or {}).get('visual_change_detected')}`",
            f"- Component path: `{report.get('component_path', '') or 'unset'}`",
            "",
            "## Values",
            "",
            f"- Baseline: `{report.get('baseline_value_json', '') or 'unset'}`",
            f"- Probe: `{report.get('probe_value_json', '') or 'unset'}`",
            "",
        ]
    )
    if report.get("image_diff"):
        diff = report["image_diff"]
        lines.extend(
            [
                "## Image Diff",
                "",
                f"- Diff ROI mode: `{diff.get('selected_mode', '')}`",
                f"- Diff threshold: `{diff.get('min_mean_diff')}`",
                f"- Selected mean abs diff: `{(diff.get('selected_region') or {}).get('mean_abs_diff')}`",
                f"- Selected changed pixels: `{(diff.get('selected_region') or {}).get('changed_pixels')}`",
                f"- Selected bounding box: `{(diff.get('selected_region') or {}).get('bbox')}`",
                f"- Selected ROI box: `{(diff.get('selected_region') or {}).get('roi_box')}`",
                f"- Full-frame mean abs diff: `{(diff.get('full_frame') or {}).get('mean_abs_diff')}`",
                "",
            ]
        )
    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        for item in report["warnings"]:
            lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command_probe(args: argparse.Namespace) -> int:
    ctx = resolve_root(args.root)
    schema = load_control_schema(args.schema)
    control = find_control(schema, args.control)
    effect = str(schema.get("effect_name") or "Effect")
    probe_support = str(control.get("probe_support") or "")
    if not probe_support.startswith("runtime_component"):
        raise SystemExit(f"Control `{control.get('id')}` does not support runtime Niagara probing yet; probe_support={probe_support}.")
    if not (args.system_path or args.component_path):
        raise SystemExit("Provide --system-path or --component-path.")

    baseline_value_json = args.baseline_value_json or str(control.get("default_value_json") or "")
    probe_value_json = choose_probe_value(control, args.probe_value_json)
    before_base_png = str(Path(args.before_png) if args.before_png else default_report_path(ctx, "runtime-control-probe", effect, f"{slugify(control['id'])}-before", ".png"))
    after_base_png = str(Path(args.after_png) if args.after_png else default_report_path(ctx, "runtime-control-probe", effect, f"{slugify(control['id'])}-after", ".png"))
    sim_times = [float(args.sim_time), *[float(item) for item in args.extra_sim_time]]

    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    run_rows = []
    raw = {}
    for index, sim_time in enumerate(sim_times):
        if len(sim_times) == 1:
            before_png = before_base_png
            after_png = after_base_png
        else:
            before_png = str(Path(before_base_png).with_name(Path(before_base_png).stem + f"-t{index:02d}" + Path(before_base_png).suffix))
            after_png = str(Path(after_base_png).with_name(Path(after_base_png).stem + f"-t{index:02d}" + Path(after_base_png).suffix))
        if args.capture and args.system_path:
            before_raw = client.exec_json(
                build_capture_value_script(
                    system_path=args.system_path,
                    variable_name=str(control.get("target_name") or ""),
                    type_object_path=str(control.get("type_object_path") or ""),
                    value_struct_path=str(control.get("value_struct_path") or ""),
                    value_json=baseline_value_json,
                    out_png=before_png,
                    sim_time=sim_time,
                    camera_yaw=args.camera_yaw,
                    camera_pitch=args.camera_pitch,
                    camera_distance=args.camera_distance,
                    camera_fov=args.camera_fov,
                ),
                no_preflight=True,
            )
            after_raw = client.exec_json(
                build_capture_value_script(
                    system_path=args.system_path,
                    variable_name=str(control.get("target_name") or ""),
                    type_object_path=str(control.get("type_object_path") or ""),
                    value_struct_path=str(control.get("value_struct_path") or ""),
                    value_json=probe_value_json,
                    out_png=after_png,
                    sim_time=sim_time,
                    camera_yaw=args.camera_yaw,
                    camera_pitch=args.camera_pitch,
                    camera_distance=args.camera_distance,
                    camera_fov=args.camera_fov,
                ),
                no_preflight=True,
            )
            current_raw = {
                "success": bool(before_raw.get("success")) and bool(after_raw.get("success")),
                "spawned_preview_actor": True,
                "actor_name": "",
                "component_path": str(after_raw.get("component_path") or before_raw.get("component_path") or ""),
                "before_png": before_png,
                "after_png": after_png,
                "before_capture_ok": bool(before_raw.get("capture_ok")),
                "after_capture_ok": bool(after_raw.get("capture_ok")),
                "before_summary": before_raw.get("summary") or {},
                "after_summary": after_raw.get("summary") or {},
                "spawned_component_path": str(after_raw.get("component_path") or before_raw.get("component_path") or ""),
            }
        else:
            current_raw = client.exec_json(
                build_probe_script(
                    system_path=args.system_path,
                    component_path=args.component_path,
                    type_object_path=str(control.get("type_object_path") or ""),
                    variable_name=str(control.get("target_name") or ""),
                    baseline_value_json=baseline_value_json,
                    probe_value_json=probe_value_json,
                    value_struct_path=str(control.get("value_struct_path") or ""),
                    capture=False,
                    before_png=before_png,
                    after_png=after_png,
                    sim_time=sim_time,
                    camera_yaw=args.camera_yaw,
                    camera_pitch=args.camera_pitch,
                    camera_distance=args.camera_distance,
                    camera_fov=args.camera_fov,
                ),
                no_preflight=True,
            )
        if not raw:
            raw = current_raw
        run_rows.append(
            {
                "sim_time": sim_time,
                "before_png": before_png if args.capture and args.system_path else "",
                "after_png": after_png if args.capture and args.system_path else "",
                "raw": current_raw,
            }
        )

    warnings: list[str] = []
    value_roundtrip_passed = jsonish_equal(
        str((raw.get("after_summary") or {}).get("value_json") or ""),
        probe_value_json,
    )
    visual_change_detected = None
    image_diff = {}
    primary_before_png = run_rows[0]["before_png"] if run_rows else before_base_png
    primary_after_png = run_rows[0]["after_png"] if run_rows else after_base_png
    if args.capture and args.system_path:
        comparisons = []
        for row in run_rows:
            before_png = str(row.get("before_png") or "")
            after_png = str(row.get("after_png") or "")
            before_exists = Path(before_png).exists()
            after_exists = Path(after_png).exists()
            if not before_exists or not after_exists:
                comparisons.append(
                    {
                        "sim_time": row.get("sim_time"),
                        "before_png": before_png,
                        "after_png": after_png,
                        "missing_capture": True,
                    }
                )
                continue
            with Image.open(before_png) as before_img:
                default_roi = resolve_roi_box(
                    width=before_img.width,
                    height=before_img.height,
                    roi_mode="center-crop",
                    roi_scale=args.roi_scale,
                    roi_left=args.roi_left,
                    roi_top=args.roi_top,
                    roi_right=args.roi_right,
                    roi_bottom=args.roi_bottom,
                )
                if args.diff_roi_mode == "auto-brightness":
                    roi_box = estimate_brightness_roi_box(
                        Path(before_png),
                        Path(after_png),
                        threshold=args.brightness_roi_threshold,
                        padding=args.brightness_roi_padding,
                    ) or default_roi
                else:
                    roi_box = resolve_roi_box(
                        width=before_img.width,
                        height=before_img.height,
                        roi_mode=args.diff_roi_mode,
                        roi_scale=args.roi_scale,
                        roi_left=args.roi_left,
                        roi_top=args.roi_top,
                        roi_right=args.roi_right,
                        roi_bottom=args.roi_bottom,
                    )
            full_frame = image_diff_summary(Path(before_png), Path(after_png))
            selected_region = image_diff_summary(
                Path(before_png),
                Path(after_png),
                roi_box=roi_box if args.diff_roi_mode != "full-frame" else None,
                pixel_threshold=args.pixel_diff_threshold,
            )
            comparisons.append(
                {
                    "sim_time": row.get("sim_time"),
                    "before_png": before_png,
                    "after_png": after_png,
                    "full_frame": full_frame,
                    "selected_region": selected_region,
                }
            )
        valid = [item for item in comparisons if not item.get("missing_capture")]
        if valid:
            selected = max(valid, key=lambda item: float((item.get("selected_region") or {}).get("mean_abs_diff", 0.0)))
            image_diff = {
                "selected_mode": args.diff_roi_mode,
                "min_mean_diff": args.min_mean_diff,
                "pixel_diff_threshold": args.pixel_diff_threshold,
                "comparisons": comparisons,
                "selected_sim_time": selected.get("sim_time"),
                "full_frame": selected.get("full_frame"),
                "selected_region": selected.get("selected_region"),
            }
            visual_change_detected = bool((selected.get("selected_region") or {}).get("mean_abs_diff", 0.0) > args.min_mean_diff)
            if not visual_change_detected:
                warnings.append(
                    "Runtime value roundtrip succeeded, but ROI-based preview image difference stayed below the visual-change threshold."
                )
        else:
            warnings.append("Capture was requested but before/after PNG outputs were not both created.")
    gate = {
        "value_roundtrip_passed": value_roundtrip_passed,
        "visual_change_detected": visual_change_detected,
        "probe_passed": value_roundtrip_passed and (visual_change_detected in {True, None}),
    }
    report = {
        "tool": "runtime_control_probe",
        "generated_utc": utc_now_iso(),
        "effect_name": effect,
        "control_id": control.get("id", ""),
        "logical_name": control.get("logical_name", ""),
        "surface": control.get("surface", ""),
        "runtime_surface": control.get("runtime_surface", ""),
        "system_path": args.system_path or schema.get("system_path") or "",
        "component_path": str(raw.get("component_path") or args.component_path or schema.get("component_path") or ""),
        "baseline_value_json": baseline_value_json,
        "probe_value_json": probe_value_json,
        "before_summary": raw.get("before_summary") or {},
        "after_summary": raw.get("after_summary") or {},
        "before_png": primary_before_png if args.capture and args.system_path else "",
        "after_png": primary_after_png if args.capture and args.system_path else "",
        "sim_times": sim_times,
        "image_diff": image_diff,
        "warnings": warnings,
        "gate": gate,
        "raw": raw,
    }
    out = Path(args.out) if args.out else default_report_path(ctx, "runtime-control-probe", effect, slugify(control["id"]), ".json")
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 0 if report["gate"]["probe_passed"] or not args.strict else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe whether a runtime Niagara control can be set and read back, with optional before/after capture.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--schema", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--system-path", default="")
    parser.add_argument("--component-path", default="")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--baseline-value-json", default="")
    parser.add_argument("--probe-value-json", default="")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--sim-time", type=float, default=1.0)
    parser.add_argument("--extra-sim-time", action="append", default=[])
    parser.add_argument("--camera-yaw", type=float, default=35.0)
    parser.add_argument("--camera-pitch", type=float, default=10.0)
    parser.add_argument("--camera-distance", type=float, default=420.0)
    parser.add_argument("--camera-fov", type=float, default=35.0)
    parser.add_argument("--before-png", default="")
    parser.add_argument("--after-png", default="")
    parser.add_argument("--min-mean-diff", type=float, default=0.02)
    parser.add_argument("--diff-roi-mode", choices=["full-frame", "center-crop", "manual-box", "auto-brightness"], default="center-crop")
    parser.add_argument("--roi-scale", type=float, default=0.35)
    parser.add_argument("--roi-left", type=int, default=0)
    parser.add_argument("--roi-top", type=int, default=0)
    parser.add_argument("--roi-right", type=int, default=0)
    parser.add_argument("--roi-bottom", type=int, default=0)
    parser.add_argument("--pixel-diff-threshold", type=int, default=1)
    parser.add_argument("--brightness-roi-threshold", type=int, default=12)
    parser.add_argument("--brightness-roi-padding", type=int, default=24)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command_probe)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = normalize_cli_global_args(argv, known_subcommands=set())
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
