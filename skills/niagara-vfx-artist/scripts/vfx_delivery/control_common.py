from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json
from .effect_state import control_presets_default, control_schema_default, load_effect_record, save_effect_record


NUMERIC_NIAGARA_TYPES = {
    "float",
    "double",
    "int32",
    "int",
    "bool",
}


def schema_path(ctx, effect: str) -> Path:
    return default_report_path(ctx, "control-schemas", effect, "effect-control-schema", ".json")


def control_report_path(ctx, category: str, effect: str, stem: str) -> Path:
    return default_report_path(ctx, category, effect, stem, ".json")


def load_control_schema(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Control schema must be a JSON object: {path}")
    return payload


def save_control_schema(ctx, effect: str, payload: dict[str, Any], out: str | Path | None = None) -> Path:
    path = Path(out) if out else schema_path(ctx, effect)
    save_json(path, payload)
    if path == schema_path(ctx, effect):
        save_effect_record(ctx, "control-schemas", effect, payload)
    return path


def load_effect_control_schema(ctx, effect: str) -> dict[str, Any]:
    return load_effect_record(ctx, "control-schemas", effect, control_schema_default(effect))


def load_control_presets(ctx, effect: str) -> dict[str, Any]:
    return load_effect_record(ctx, "control-presets", effect, control_presets_default(effect))


def save_control_presets(ctx, effect: str, payload: dict[str, Any]) -> Path:
    return save_effect_record(ctx, "control-presets", effect, payload)


def split_range(text: str) -> tuple[float | None, float | None]:
    raw = str(text or "").strip()
    if not raw:
        return None, None
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*\.\.\s*(-?\d+(?:\.\d+)?)\s*$", raw)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def surface_key(surface: str, target_name: str) -> str:
    return f"{surface}:{target_name}"


def infer_group(name: str) -> str:
    lowered = str(name or "").lower()
    if any(token in lowered for token in ("color", "tint", "hue")):
        return "Color"
    if any(token in lowered for token in ("intensity", "emissive", "brightness", "density", "opacity")):
        return "Intensity"
    if any(token in lowered for token in ("lifetime", "duration", "age", "delay")):
        return "Timing"
    if any(token in lowered for token in ("width", "size", "scale", "radius")):
        return "Scale"
    if any(token in lowered for token in ("speed", "velocity", "flow", "drag")):
        return "Motion"
    if any(token in lowered for token in ("spawn", "burst", "rate", "count")):
        return "Spawn"
    if any(token in lowered for token in ("enable", "disable", "toggle", "switch", "state")):
        return "State"
    return "General"


def infer_unit(name: str, range_text: str = "") -> str:
    lowered = str(name or "").lower()
    if any(token in lowered for token in ("lifetime", "duration", "delay", "age")):
        return "seconds"
    if any(token in lowered for token in ("width", "size", "radius")):
        return "uu"
    if any(token in lowered for token in ("speed", "velocity", "flow")):
        return "rate"
    if range_text and "0..1" in range_text.replace(" ", ""):
        return "normalized"
    return "scalar"


def infer_runtime_tunable(owner: str, target_name: str) -> bool:
    owner_blob = str(owner or "").lower()
    name_blob = str(target_name or "").lower()
    return any(token in owner_blob for token in ("runtime", "game", "blueprint", "gas", "sequencer")) or name_blob.startswith("user.")


def infer_probe_support(surface: str, type_name: str, type_object_path: str) -> str:
    normalized = str(surface or "").lower()
    type_blob = " ".join([str(type_name or ""), str(type_object_path or "")]).lower()
    if normalized in {"niagara_user_variable", "niagara_component_variable"}:
        if any(token in type_blob for token in NUMERIC_NIAGARA_TYPES):
            return "runtime_component_numeric"
        if "linearcolor" in type_blob or "vector" in type_blob:
            return "runtime_component_struct"
        return "runtime_component_unknown"
    if normalized == "material_instance_parameter":
        if "scalar" in type_blob or "vector" in type_blob:
            return "material_parameter_preview_only"
        return "material_parameter_unknown"
    return "unsupported"


def infer_sweep_support(surface: str, type_name: str, type_object_path: str) -> str:
    normalized = str(surface or "").lower()
    type_blob = " ".join([str(type_name or ""), str(type_object_path or "")]).lower()
    if normalized in {"niagara_user_variable", "niagara_component_variable"} and any(token in type_blob for token in ("float", "double", "int32", "int")):
        return "niagara_numeric_preview_sweep"
    if normalized == "material_instance_parameter" and "scalar" in type_blob:
        return "material_scalar_preview_sweep"
    return "unsupported"


def normalize_default_json(value: str | dict[str, Any] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except Exception:
        return text
    return json.dumps(payload, ensure_ascii=False)


def normalize_default_text(value_json: str, fallback: str = "") -> str:
    text = str(value_json or "").strip()
    if not text:
        return str(fallback or "")
    try:
        payload = json.loads(text)
    except Exception:
        return text
    if isinstance(payload, dict) and set(payload.keys()) == {"value"}:
        return str(payload["value"])
    return json.dumps(payload, ensure_ascii=False)


def control_matches(control: dict[str, Any], selector: str) -> bool:
    wanted = str(selector or "").strip().lower()
    return wanted in {
        str(control.get("id") or "").lower(),
        str(control.get("logical_name") or "").lower(),
        str(control.get("target_name") or "").lower(),
    }


def find_control(schema: dict[str, Any], selector: str) -> dict[str, Any]:
    matches = [item for item in schema.get("controls") or [] if control_matches(item, selector)]
    if not matches:
        raise SystemExit(f"No control matched selector `{selector}`.")
    if len(matches) > 1:
        raise SystemExit(f"Selector `{selector}` matched multiple controls; use the full control id.")
    return matches[0]


def numeric_probe_values(control: dict[str, Any]) -> list[str]:
    default_text = str(control.get("default_value_text") or "").strip()
    range_min = control.get("range_min")
    range_max = control.get("range_max")
    try:
        default_value = float(default_text)
    except Exception:
        default_value = 0.0
    values: list[float] = []
    if range_min is not None:
        values.append(float(range_min))
    values.append(default_value)
    if range_max is not None:
        values.append(float(range_max))
    if len(values) < 3:
        values.extend([default_value * 0.5 if default_value else 0.5, default_value * 1.5 if default_value else 1.5])
    deduped = []
    for item in values:
        if item not in deduped:
            deduped.append(item)
    return [json.dumps({"value": item}, ensure_ascii=False) for item in deduped[:5]]


def make_control_row(
    *,
    logical_name: str,
    target_name: str,
    surface: str,
    runtime_surface: str,
    type_name: str,
    type_object_path: str,
    value_struct_path: str,
    default_value_json: str,
    range_text: str,
    unit: str,
    group: str,
    runtime_tunable: bool,
    driven_by: str,
    owner: str,
    purpose: str,
    source_kind: str,
    source_path: str,
) -> dict[str, Any]:
    range_min, range_max = split_range(range_text)
    row = {
        "id": surface_key(surface, target_name),
        "logical_name": logical_name,
        "target_name": target_name,
        "surface": surface,
        "runtime_surface": runtime_surface,
        "type_name": type_name,
        "type_object_path": type_object_path,
        "value_struct_path": value_struct_path,
        "default_value_json": normalize_default_json(default_value_json),
        "default_value_text": normalize_default_text(default_value_json),
        "range_text": range_text,
        "range_min": range_min,
        "range_max": range_max,
        "unit": unit,
        "group": group,
        "runtime_tunable": runtime_tunable,
        "driven_by": driven_by,
        "owner": owner,
        "purpose": purpose,
        "source_kind": source_kind,
        "source_path": source_path,
    }
    row["probe_support"] = infer_probe_support(surface, type_name, type_object_path)
    row["sweep_support"] = infer_sweep_support(surface, type_name, type_object_path)
    if row["sweep_support"] == "niagara_numeric_preview_sweep":
        row["suggested_sweep_values"] = numeric_probe_values(row)
    else:
        row["suggested_sweep_values"] = []
    return row


def sorted_groups(controls: list[dict[str, Any]]) -> list[str]:
    return sorted(dict.fromkeys(str(item.get("group") or "General") for item in controls))


def resolve_root(root: str | Path | None):
    return resolve_root_context(root)
