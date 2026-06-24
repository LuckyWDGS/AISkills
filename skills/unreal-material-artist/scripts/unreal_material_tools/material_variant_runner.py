from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import _text, load_json, resolve_path


DEFAULT_TIERS = ("default", "low", "high", "extreme", "gameplay-safe")
SUPPORTED_PARAM_TYPES = {"scalar", "vector", "texture"}


def normalize_type(value: Any) -> str:
    token = "".join(ch for ch in _text(value).lower() if ch.isalnum())
    aliases = {
        "float": "scalar",
        "scalarparameter": "scalar",
        "linearcolor": "vector",
        "color": "vector",
        "vectorparameter": "vector",
        "texture2d": "texture",
        "textureparameter": "texture",
        "staticswitch": "static_switch",
        "staticswitchparameter": "static_switch",
        "bool": "static_switch",
    }
    return aliases.get(token, _text(value).lower())


def split_tiers(value: str) -> list[str]:
    tiers = [item.strip() for item in value.split(",") if item.strip()]
    return tiers or list(DEFAULT_TIERS)


def schema_parameters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    schema = payload.get("schema") if isinstance(payload.get("schema"), dict) else {}
    rows = schema.get("parameters") if isinstance(schema.get("parameters"), list) else payload.get("parameters")
    return [item for item in rows or [] if isinstance(item, dict)]


def numeric(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def scalar_range(row: dict[str, Any]) -> tuple[float | None, float | None]:
    data = row.get("range")
    if isinstance(data, dict):
        return numeric(data.get("min")), numeric(data.get("max"))
    return None, None


def clamp(value: float, low: float | None, high: float | None) -> float:
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return round(value, 6)


def scalar_value(row: dict[str, Any], tier: str) -> float | None:
    default = numeric(row.get("default"))
    if default is None:
        return None
    low, high = scalar_range(row)
    span = (high - low) if low is not None and high is not None else None
    lowered = str(row.get("name") or "").lower()
    if tier == "default":
        value = default
    elif tier == "low":
        value = low + span * 0.25 if span is not None else default * 0.5
    elif tier == "high":
        value = low + span * 0.75 if span is not None else default * 1.5
    elif tier == "extreme":
        value = high if high is not None else default * 2.0
    elif tier == "gameplay-safe":
        if any(token in lowered for token in ("opacity", "alpha")):
            value = clamp(default, low if low is not None else 0.2, high if high is not None else 1.0)
        elif any(token in lowered for token in ("intensity", "boost", "emissive", "brightness")):
            value = min(default, high if high is not None else default)
            value = clamp(value, low, high)
        else:
            value = default
    else:
        value = default
    return clamp(value, low, high)


def vector_channels(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        result = {}
        for key, fallback in (("r", 0.0), ("g", 0.0), ("b", 0.0), ("a", 1.0)):
            result[key] = float(value.get(key, value.get(key.upper(), fallback)))
        return result
    if isinstance(value, (list, tuple)):
        values = list(value)[:4]
        while len(values) < 4:
            values.append(1.0 if len(values) == 3 else 0.0)
        return {"r": float(values[0]), "g": float(values[1]), "b": float(values[2]), "a": float(values[3])}
    return None


def vector_value(row: dict[str, Any], tier: str) -> dict[str, float] | None:
    base = vector_channels(row.get("default"))
    if base is None:
        return None
    factor = {
        "default": 1.0,
        "low": 0.65,
        "high": 1.25,
        "extreme": 1.75,
        "gameplay-safe": 1.0,
    }.get(tier, 1.0)
    return {
        "r": round(max(0.0, min(10.0, base["r"] * factor)), 6),
        "g": round(max(0.0, min(10.0, base["g"] * factor)), 6),
        "b": round(max(0.0, min(10.0, base["b"] * factor)), 6),
        "a": round(max(0.0, min(10.0, base["a"])), 6),
    }


def parameter_value(row: dict[str, Any], tier: str) -> Any:
    ptype = normalize_type(row.get("type"))
    if ptype == "scalar":
        return scalar_value(row, tier)
    if ptype == "vector":
        return vector_value(row, tier)
    if ptype == "texture":
        return row.get("default")
    return None


def should_participate(row: dict[str, Any], include_non_regression: bool) -> bool:
    if include_non_regression:
        return True
    value = row.get("regression_participation")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"false", "0", "no", "none"}


def material_leaf(path_text: str) -> str:
    leaf = str(path_text).rsplit("/", 1)[-1].split(".", 1)[0]
    if leaf.startswith("M_"):
        leaf = "MI_" + leaf[2:]
    elif not leaf.startswith("MI_"):
        leaf = "MI_" + leaf
    return leaf


def default_instance_path(parent_path: str, output_folder: str, tier: str) -> str:
    folder = output_folder.strip("/") if output_folder else str(parent_path).rsplit("/", 1)[0].strip("/")
    return f"/{folder}/{material_leaf(parent_path)}_{slugify(tier)}"


def build_variants(args: argparse.Namespace, parameters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tiers = split_tiers(args.tiers)
    variants: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active_params = [row for row in parameters if should_participate(row, args.include_non_regression)]
    for tier in tiers:
        params = []
        skipped_for_tier = []
        for row in active_params:
            ptype = normalize_type(row.get("type"))
            name = _text(row.get("name"))
            if not name:
                skipped_for_tier.append({"name": "", "reason": "missing_name", "type": ptype})
                continue
            if ptype not in SUPPORTED_PARAM_TYPES:
                skipped_for_tier.append({"name": name, "reason": "unsupported_for_material_instance_batch", "type": ptype})
                continue
            value = parameter_value(row, tier)
            if value in (None, ""):
                skipped_for_tier.append({"name": name, "reason": "no_default_or_uncomputable_value", "type": ptype})
                continue
            params.append({"name": name, "type": ptype, "value": value})
        instance_path = default_instance_path(args.parent_path, args.output_folder, tier)
        variants.append(
            {
                "tier": tier,
                "path": instance_path,
                "parent_path": args.parent_path,
                "params": params,
                "preview": {"enabled": False},
                "skipped_parameters": skipped_for_tier,
            }
        )
        for item in skipped_for_tier:
            skipped.append({"tier": tier, **item})
    return variants, skipped


def build_preview_matrix_commands(args: argparse.Namespace, variants: list[dict[str, Any]], spec_path: Path) -> list[dict[str, Any]]:
    tool_path = Path(__file__).resolve().parents[2] / "tools" / "preview_matrix.py"
    rows: list[dict[str, Any]] = []
    for variant in variants:
        command = [
            sys.executable,
            str(tool_path),
            "--material-path",
            variant["path"],
            "--effect",
            args.effect or slugify(args.parent_path),
            "--parameter-tier",
            variant["tier"],
            "--quality",
            args.preview_quality,
        ]
        rows.append({"tier": variant["tier"], "material_instance_path": variant["path"], "command": command, "source_variant_spec": str(spec_path)})
    return rows


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    schema_path = resolve_path(args.parameter_schema, base=Path.cwd())
    schema = load_json(schema_path)
    parameters = schema_parameters(schema)
    if not args.parent_path:
        args.parent_path = args.material_path or schema.get("material_path") or ""
    if not args.parent_path:
        raise SystemExit("Provide --parent-path/--material-path or a parameter schema with material_path.")
    variants, skipped = build_variants(args, parameters)
    effect = args.effect or schema.get("effect") or slugify(args.parent_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "variant-runs", effect, "material-variant-runner", ".json")
    spec_path = Path(args.spec_out) if args.spec_out else out.with_name("material-instance-variant-spec.json")
    batch_spec = {
        "effect": effect,
        "parent_path": args.parent_path,
        "reuse_existing": bool(args.reuse_existing),
        "use_official_toolsets": True,
        "preview": {"enabled": False},
        "instances": [
            {key: value for key, value in variant.items() if key in {"path", "parent_path", "params", "preview"}}
            for variant in variants
        ],
    }
    save_json(spec_path, batch_spec)
    report = {
        "tool": "material_variant_runner",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "material_path": args.parent_path,
        "source_parameter_schema": str(schema_path),
        "tiers": split_tiers(args.tiers),
        "variants": variants,
        "skipped_parameters": skipped,
        "material_instance_batch_spec": str(spec_path),
        "preview_matrix_commands": build_preview_matrix_commands(args, variants, spec_path),
        "summary": {
            "parameter_count": len(parameters),
            "variant_count": len(variants),
            "skipped_parameter_count": len(skipped),
        },
        "gate": {
            "passed": bool(variants),
            "variants_generated": bool(variants),
            "has_batch_spec": True,
            "requires_triage": bool(skipped and args.fail_on_skipped),
        },
        "next_actions": next_actions(skipped, args),
    }
    return report, out


def next_actions(skipped: list[dict[str, Any]], args: argparse.Namespace) -> list[str]:
    actions: list[str] = []
    if skipped:
        actions.append("Review skipped parameters; static switches should now flow through static_switch_variant_expander.py before MI batch execution.")
    actions.append("Run material_instance_batch.py with the emitted spec when UnrealBridge is available, then feed the created MIs into preview_matrix.py and material_regression.py.")
    if not args.include_non_regression:
        actions.append("Only regression-participating parameters were varied; rerun with --include-non-regression if art-review tiers need every exposed control.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Material Variant Runner: {report.get('effect')}",
        "",
        f"- Variants: `{summary.get('variant_count')}`",
        f"- Parameters: `{summary.get('parameter_count')}`",
        f"- Skipped parameter writes: `{summary.get('skipped_parameter_count')}`",
        f"- Batch spec: `{report.get('material_instance_batch_spec')}`",
        "",
        "## Variants",
        "",
        "| Tier | MI Path | Params | Skipped |",
        "| --- | --- | ---: | ---: |",
    ]
    for variant in report.get("variants") or []:
        lines.append(f"| `{variant.get('tier')}` | `{variant.get('path')}` | {len(variant.get('params') or [])} | {len(variant.get('skipped_parameters') or [])} |")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    report, out = build_report(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    if args.fail_on_skipped and report["skipped_parameters"]:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate material instance variants from material_parameter_schema.py and emit a material_instance_batch.py spec.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--parameter-schema", required=True, help="material_parameter_schema.py JSON report.")
    parser.add_argument("--parent-path", default="", help="Parent material path for generated MIs.")
    parser.add_argument("--material-path", default="", help="Alias for --parent-path.")
    parser.add_argument("--effect", default="")
    parser.add_argument("--output-folder", default="", help="UE folder for generated MI paths; defaults to parent material folder.")
    parser.add_argument("--tiers", default=",".join(DEFAULT_TIERS))
    parser.add_argument("--include-non-regression", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--preview-quality", default="low")
    parser.add_argument("--fail-on-skipped", action="store_true")
    parser.add_argument("--spec-out")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.material_path and not args.parent_path:
        args.parent_path = args.material_path
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
