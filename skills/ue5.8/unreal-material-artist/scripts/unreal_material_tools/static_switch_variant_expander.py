from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import _text, load_json, resolve_path
from .material_variant_runner import (
    build_preview_matrix_commands,
    build_variants,
    default_instance_path,
    normalize_type,
    schema_parameters,
    should_participate,
    split_tiers,
)


def bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def parse_switch_overrides(values: list[str]) -> dict[str, list[bool]]:
    result: dict[str, list[bool]] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Expected switch override like Name=true,false, got: {value}")
        name, raw = value.split("=", 1)
        bools: list[bool] = []
        for item in raw.split(","):
            parsed = bool_value(item)
            if parsed is None:
                raise SystemExit(f"Unsupported static-switch value `{item}` in override `{value}`.")
            if parsed not in bools:
                bools.append(parsed)
        if not bools:
            raise SystemExit(f"Override `{value}` did not provide any boolean values.")
        result[name.strip()] = bools
    return result


def switch_allowed_values(row: dict[str, Any], overrides: dict[str, list[bool]]) -> tuple[list[bool], str]:
    name = _text(row.get("name"))
    if name in overrides:
        return overrides[name], "override"
    range_data = row.get("range")
    if isinstance(range_data, dict):
        allowed = range_data.get("allowed")
        if isinstance(allowed, list):
            values: list[bool] = []
            for item in allowed:
                parsed = bool_value(item)
                if parsed is not None and parsed not in values:
                    values.append(parsed)
            if values:
                return values, "schema_range"
    default = bool_value(row.get("default"))
    if default is None:
        return [False, True], "implicit_bool"
    opposite = not default
    return [default, opposite] if default != opposite else [default], "default_and_inverse"


def collect_switch_rows(
    parameters: list[dict[str, Any]],
    *,
    include_non_regression: bool,
    overrides: dict[str, list[bool]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    switches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in parameters:
        if normalize_type(row.get("type")) != "static_switch":
            continue
        if not should_participate(row, include_non_regression):
            skipped.append(
                {
                    "name": _text(row.get("name")),
                    "reason": "non_regression_parameter_excluded",
                    "type": "static_switch",
                }
            )
            continue
        name = _text(row.get("name"))
        if not name:
            skipped.append({"name": "", "reason": "missing_name", "type": "static_switch"})
            continue
        default = bool_value(row.get("default"))
        if default is None:
            skipped.append({"name": name, "reason": "unparseable_default", "type": "static_switch"})
            continue
        allowed_values, source = switch_allowed_values(row, overrides)
        switches.append(
            {
                "name": name,
                "type": "static_switch",
                "default": default,
                "allowed_values": allowed_values,
                "allowed_value_source": source,
                "regression_participation": row.get("regression_participation"),
                "runtime_owner": row.get("runtime_owner"),
                "writable_by": row.get("writable_by"),
            }
        )
    switches.sort(key=lambda item: item["name"].lower())
    return switches, skipped


def signature_label(values: dict[str, bool]) -> str:
    if not values:
        return "switchless"
    parts = []
    for name, value in sorted(values.items()):
        parts.append(f"{slugify(name)}-{'on' if value else 'off'}")
    return "-".join(parts)


def permutation_priority(values: dict[str, bool], switches: list[dict[str, Any]]) -> tuple[int, str]:
    distance = 0
    ordered_parts = []
    defaults = {row["name"]: bool(row["default"]) for row in switches}
    for name in sorted(values):
        if bool(values[name]) != defaults[name]:
            distance += 1
        ordered_parts.append(f"{name}={'1' if values[name] else '0'}")
    return distance, "|".join(ordered_parts)


def build_switch_permutations(switches: list[dict[str, Any]], max_permutations: int) -> tuple[list[dict[str, Any]], int, bool]:
    if not switches:
        return [{"id": "switchless", "label": "switchless", "values": {}, "signature": []}], 1, False
    names = [row["name"] for row in switches]
    option_lists = [row["allowed_values"] for row in switches]
    requested = math.prod(max(1, len(options)) for options in option_lists)
    rows: list[dict[str, Any]] = []
    for index, combo in enumerate(itertools.product(*option_lists), start=1):
        values = {name: bool(value) for name, value in zip(names, combo)}
        signature = [f"{name}={'true' if values[name] else 'false'}" for name in sorted(values)]
        rows.append(
            {
                "id": f"perm-{index:03d}",
                "label": signature_label(values),
                "values": values,
                "signature": signature,
            }
        )
    rows.sort(key=lambda item: permutation_priority(item["values"], switches))
    truncated = requested > max_permutations
    if truncated:
        rows = rows[: max_permutations]
    for index, row in enumerate(rows, start=1):
        row["id"] = f"perm-{index:03d}"
        row["deviation_count"] = permutation_priority(row["values"], switches)[0]
    return rows, requested, truncated


def expand_variants(base_variants: list[dict[str, Any]], permutations: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for variant in base_variants:
        tier = str(variant.get("tier") or "default")
        skipped_parameters = list(variant.get("skipped_parameters") or [])
        for permutation in permutations:
            switch_params = [
                {"name": name, "type": "static_switch", "value": value}
                for name, value in sorted((permutation.get("values") or {}).items())
            ]
            label = permutation.get("label") or "switchless"
            tier_label = tier if label == "switchless" else f"{tier}-{label}"
            instance_path = default_instance_path(args.parent_path, args.output_folder, tier_label)
            variants.append(
                {
                    "tier": tier,
                    "variant_id": f"{slugify(tier)}-{slugify(label)}",
                    "switch_permutation": label,
                    "switch_signature": list(permutation.get("signature") or []),
                    "path": instance_path,
                    "parent_path": args.parent_path,
                    "params": list(variant.get("params") or []) + switch_params,
                    "preview": {"enabled": False},
                    "skipped_parameters": skipped_parameters,
                }
            )
    return variants


def next_actions(
    switch_rows: list[dict[str, Any]],
    *,
    truncated: bool,
    skipped: list[dict[str, Any]],
    max_permutations: int,
) -> list[str]:
    actions: list[str] = []
    if switch_rows:
        actions.append("Run material_instance_batch.py with the emitted spec so static-switch permutations become real MIs before preview_matrix.py or material_delivery_smoke.py.")
    if truncated:
        actions.append(f"Permutation space was capped at {max_permutations}; narrow switch scope or raise --max-permutations for deeper coverage.")
    if skipped:
        actions.append("Review skipped static-switch rows; missing names/defaults prevent safe permutation expansion.")
    if not switch_rows:
        actions.append("No static switches were found, so the expander emitted the original tier space only.")
    return actions


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    schema_path = resolve_path(args.parameter_schema, base=Path.cwd())
    schema = load_json(schema_path)
    parameters = schema_parameters(schema)
    if not args.parent_path:
        args.parent_path = args.material_path or schema.get("material_path") or ""
    if not args.parent_path:
        raise SystemExit("Provide --parent-path/--material-path or a parameter schema with material_path.")
    base_variants, base_skipped = build_variants(args, parameters)
    switch_rows, switch_skipped = collect_switch_rows(
        parameters,
        include_non_regression=args.include_non_regression,
        overrides=parse_switch_overrides(args.switch),
    )
    permutations, requested_permutations, truncated = build_switch_permutations(switch_rows, args.max_permutations)
    variants = expand_variants(base_variants, permutations, args)
    effect = args.effect or schema.get("effect") or slugify(args.parent_path)
    out = Path(args.out) if args.out else default_report_path(ctx, "variant-runs", effect, "static-switch-variant-expander", ".json")
    spec_path = Path(args.spec_out) if args.spec_out else out.with_name("material-instance-static-switch-spec.json")
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
    preview_commands = build_preview_matrix_commands(args, variants, spec_path)
    skipped = base_skipped + switch_skipped
    report = {
        "tool": "static_switch_variant_expander",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "material_path": args.parent_path,
        "source_parameter_schema": str(schema_path),
        "tiers": split_tiers(args.tiers),
        "switch_parameters": switch_rows,
        "switch_permutations": permutations,
        "variants": variants,
        "skipped_parameters": skipped,
        "material_instance_batch_spec": str(spec_path),
        "preview_matrix_commands": preview_commands,
        "summary": {
            "parameter_count": len(parameters),
            "base_variant_count": len(base_variants),
            "switch_parameter_count": len(switch_rows),
            "requested_permutation_count": requested_permutations,
            "emitted_permutation_count": len(permutations),
            "variant_count": len(variants),
            "skipped_parameter_count": len(skipped),
        },
        "gate": {
            "passed": bool(variants),
            "variants_generated": bool(variants),
            "switch_space_truncated": truncated,
            "within_permutation_budget": not truncated,
            "requires_triage": bool(skipped and args.fail_on_skipped),
        },
        "next_actions": next_actions(
            switch_rows,
            truncated=truncated,
            skipped=skipped,
            max_permutations=args.max_permutations,
        ),
    }
    return report, out


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Static Switch Variant Expander: {report.get('effect')}",
        "",
        f"- Base tiers: `{summary.get('base_variant_count')}`",
        f"- Static switches: `{summary.get('switch_parameter_count')}`",
        f"- Requested permutations: `{summary.get('requested_permutation_count')}`",
        f"- Emitted permutations: `{summary.get('emitted_permutation_count')}`",
        f"- Expanded variants: `{summary.get('variant_count')}`",
        f"- Batch spec: `{report.get('material_instance_batch_spec')}`",
        "",
        "## Switches",
        "",
        "| Name | Default | Allowed | Source |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.get("switch_parameters") or []:
        allowed = ", ".join("true" if bool(item) else "false" for item in row.get("allowed_values") or [])
        lines.append(f"| `{row.get('name')}` | `{row.get('default')}` | `{allowed}` | `{row.get('allowed_value_source')}` |")
    lines.extend(["", "## Permutations", ""])
    for row in report.get("switch_permutations") or []:
        lines.append(f"- `{row.get('id')}` `{row.get('label')}` deviations=`{row.get('deviation_count', 0)}`")
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
    if args.fail_on_skipped and report.get("skipped_parameters"):
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand material-parameter tiers across static-switch permutations and emit an executable MI batch spec.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--parameter-schema", required=True, help="material_parameter_schema.py JSON report.")
    parser.add_argument("--parent-path", default="", help="Parent material path for generated MIs.")
    parser.add_argument("--material-path", default="", help="Alias for --parent-path.")
    parser.add_argument("--effect", default="")
    parser.add_argument("--output-folder", default="", help="UE folder for generated MI paths; defaults to parent material folder.")
    parser.add_argument("--tiers", default="default,low,high,extreme,gameplay-safe")
    parser.add_argument("--include-non-regression", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--preview-quality", default="low")
    parser.add_argument("--switch", action="append", default=[], help="Override switch domain, e.g. UseNoise=true,false")
    parser.add_argument("--max-permutations", type=int, default=16)
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
