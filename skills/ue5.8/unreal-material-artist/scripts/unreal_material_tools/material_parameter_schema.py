from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .material_acceptance_gate import (
    _as_list,
    _text,
    evidence_rows,
    load_json,
    package_report_paths,
    resolve_path,
    rows_by_tool,
    severity_counts,
)


CONTRACT_TOOLS = {"material_contract", "delivery_packager", "reference_to_material_plan", "material_parameter_schema"}
LIVE_TOOLS = {"material_audit", "runtime_param_trace"}
REQUIRED_FIELDS = (
    "type",
    "default",
    "unit",
    "range",
    "runtime_owner",
    "writable_by",
    "artist_tunable",
    "regression_participation",
)
TYPE_ALIASES = {
    "scalarparameter": "scalar",
    "scalar": "scalar",
    "float": "scalar",
    "vectorparameter": "vector",
    "vector": "vector",
    "linearcolor": "vector",
    "color": "vector",
    "textureparameter": "texture",
    "texture": "texture",
    "texture2d": "texture",
    "staticswitchparameter": "static_switch",
    "staticswitch": "static_switch",
    "switch": "static_switch",
    "bool": "static_switch",
}


def normalize_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).lower() if ch.isalnum() or ch == "_")


def normalize_type(value: Any) -> str:
    token = "".join(ch for ch in _text(value).lower() if ch.isalnum())
    return TYPE_ALIASES.get(token, _text(value).lower())


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def contract_path_from_package(package: dict[str, Any], package_path: Path, explicit: str = "") -> Path | None:
    if explicit:
        return resolve_path(explicit, base=Path.cwd())
    source = package.get("source") if isinstance(package.get("source"), dict) else {}
    if source.get("contract_path"):
        return resolve_path(str(source["contract_path"]), base=package_path.parent)
    return None


def collect_rows(args: argparse.Namespace, package: dict[str, Any], package_path: Path | None, contract_path: Path | None) -> list[dict[str, Any]]:
    paths = package_report_paths(package, package_path=package_path) if package and package_path else []
    if package_path:
        paths.append(package_path)
    if contract_path:
        paths.append(contract_path)
    for values in (
        args.audit_report,
        args.runtime_trace_report,
        args.parameter_report,
    ):
        for value in values:
            paths.append(resolve_path(value, base=Path.cwd()))
    return evidence_rows(paths)


def source_priority(tool: str) -> int:
    return {
        "material_parameter_schema": 0,
        "material_contract": 1,
        "delivery_packager": 2,
        "reference_to_material_plan": 3,
        "runtime_param_trace": 4,
        "material_audit": 5,
    }.get(tool, 9)


def parameter_name(row: dict[str, Any]) -> str:
    return _text(first_present(row, "name", "parameter", "id", "material_param", "parameter_name"))


def parameter_default(row: dict[str, Any]) -> Any:
    return first_present(row, "default", "default_value", "value", "initial_value")


def parameter_type(row: dict[str, Any]) -> str:
    return normalize_type(first_present(row, "type", "param_type", "kind", "parameter_type"))


def range_value(row: dict[str, Any]) -> Any:
    value = first_present(row, "range", "allowed_range", "limits")
    if value not in (None, ""):
        return value
    min_value = first_present(row, "min", "minimum", "min_value")
    max_value = first_present(row, "max", "maximum", "max_value")
    if min_value is not None or max_value is not None:
        result: dict[str, Any] = {}
        if min_value is not None:
            result["min"] = min_value
        if max_value is not None:
            result["max"] = max_value
        step = first_present(row, "step", "increment")
        if step is not None:
            result["step"] = step
        return result
    return None


def boolean_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"true", "yes", "1", "artist", "tunable"}:
        return True
    if text in {"false", "no", "0", "locked", "internal"}:
        return False
    return None


def writable_by_value(row: dict[str, Any]) -> list[str]:
    explicit = first_present(row, "writable_by", "write_owners", "writers")
    values = [_text(item) for item in as_list(explicit) if _text(item)]
    for key, label in (
        ("writable_by_niagara", "Niagara"),
        ("writable_by_mid", "MID"),
        ("writable_by_blueprint", "Blueprint"),
        ("niagara_writable", "Niagara"),
        ("mid_writable", "MID"),
        ("blueprint_writable", "Blueprint"),
    ):
        if boolean_value(row.get(key)) is True and label not in values:
            values.append(label)
    return values


def normalize_contract_param(row: dict[str, Any], *, tool: str, path: str, section: str) -> dict[str, Any]:
    return {
        "source_tool": tool,
        "source_path": path,
        "source_section": section,
        "name": parameter_name(row),
        "type": parameter_type(row),
        "default": parameter_default(row),
        "unit": first_present(row, "unit", "units"),
        "range": range_value(row),
        "runtime_owner": first_present(row, "runtime_owner", "owner", "owner_model", "source_owner"),
        "writable_by": writable_by_value(row),
        "artist_tunable": first_present(row, "artist_tunable", "artist_editable", "exposed_to_artist"),
        "regression_participation": first_present(row, "regression_participation", "participates_in_regression", "regression"),
        "raw": row,
    }


def iter_payload_parameters(payload: dict[str, Any], *, tool: str, path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add_from(value: Any, section: str) -> None:
        for item in _as_list(value):
            if isinstance(item, dict):
                rows.append(normalize_contract_param(item, tool=tool, path=path, section=section))

    if tool in CONTRACT_TOOLS:
        add_from(payload.get("parameters"), "parameters")
        add_from(payload.get("parameter_table"), "parameter_table")
        add_from(payload.get("runtime_parameters"), "runtime_parameters")
        if isinstance(payload.get("schema"), dict):
            add_from(payload["schema"].get("parameters"), "schema.parameters")

    if tool == "material_audit":
        info = payload.get("material_info") if isinstance(payload.get("material_info"), dict) else {}
        for key, param_type in (
            ("scalar_parameters", "scalar"),
            ("vector_parameters", "vector"),
            ("texture_parameters", "texture"),
            ("static_switch_parameters", "static_switch"),
        ):
            for item in info.get(key) or []:
                if isinstance(item, dict):
                    row = dict(item)
                    row.setdefault("type", param_type)
                    rows.append(normalize_contract_param(row, tool=tool, path=path, section=f"material_info.{key}"))

    if tool == "runtime_param_trace":
        info = payload.get("material_info") if isinstance(payload.get("material_info"), dict) else {}
        for key, param_type in (
            ("scalar_parameters", "scalar"),
            ("vector_parameters", "vector"),
            ("texture_parameters", "texture"),
            ("static_switch_parameters", "static_switch"),
        ):
            for item in info.get(key) or []:
                if isinstance(item, dict):
                    row = dict(item)
                    row.setdefault("type", param_type)
                    rows.append(normalize_contract_param(row, tool=tool, path=path, section=f"material_info.{key}"))
        mi = payload.get("mi_parameters") if isinstance(payload.get("mi_parameters"), dict) else {}
        for item in mi.get("parameters") or []:
            if isinstance(item, dict):
                rows.append(normalize_contract_param(item, tool=tool, path=path, section="mi_parameters.parameters"))
        chain = payload.get("chain") if isinstance(payload.get("chain"), dict) else {}
        for layer in chain.get("layers") or []:
            if not isinstance(layer, dict):
                continue
            for item in layer.get("override_parameters") or []:
                if isinstance(item, dict):
                    row = normalize_contract_param(item, tool=tool, path=path, section="chain.override_parameters")
                    row["runtime_owner"] = row.get("runtime_owner") or ("MID" if not layer.get("is_base_material") else "BaseMaterial")
                    if "MID" not in row["writable_by"]:
                        row["writable_by"].append("MID")
                    rows.append(row)
        for link in payload.get("runtime_links") or []:
            if isinstance(link, dict):
                row = normalize_contract_param(link, tool=tool, path=path, section="runtime_links")
                if row["name"]:
                    row["runtime_owner"] = row.get("runtime_owner") or "NiagaraRapidIteration"
                    if "Niagara" not in row["writable_by"]:
                        row["writable_by"].append("Niagara")
                    rows.append(row)
    return rows


def has_explicit(source: dict[str, Any], field: str) -> bool:
    raw = source.get("raw") if isinstance(source.get("raw"), dict) else {}
    if field == "type":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("type", "param_type", "kind", "parameter_type"))
    if field == "default":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("default", "default_value", "value", "initial_value"))
    if field == "unit":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("unit", "units"))
    if field == "range":
        return range_value(raw) is not None
    if field == "runtime_owner":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("runtime_owner", "owner", "owner_model", "source_owner"))
    if field == "writable_by":
        return bool(writable_by_value(raw))
    if field == "artist_tunable":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("artist_tunable", "artist_editable", "exposed_to_artist"))
    if field == "regression_participation":
        return any(key in raw and raw.get(key) not in (None, "") for key in ("regression_participation", "participates_in_regression", "regression"))
    return False


def choose_value(sources: list[dict[str, Any]], field: str) -> Any:
    for source in sorted(sources, key=lambda item: source_priority(str(item.get("source_tool") or ""))):
        value = source.get(field)
        if field == "writable_by":
            if value:
                return list(dict.fromkeys(_text(item) for item in value if _text(item)))
        elif value not in (None, "", []):
            return value
    return None


def suggest_unit(name: str, param_type: str) -> str:
    lowered = name.lower()
    if param_type == "texture":
        return "asset"
    if param_type == "static_switch":
        return "bool"
    if any(token in lowered for token in ("color", "tint", "hue")):
        return "linear_color"
    if any(token in lowered for token in ("opacity", "alpha", "mask", "amount", "intensity", "strength", "scale", "boost")):
        return "normalized_or_multiplier"
    if any(token in lowered for token in ("speed", "rate")):
        return "units_per_second_or_multiplier"
    if any(token in lowered for token in ("angle", "rotation")):
        return "degrees"
    return "document_unit"


def suggest_range(param_type: str, name: str) -> Any:
    lowered = name.lower()
    if param_type == "static_switch":
        return {"allowed": [False, True]}
    if param_type == "texture":
        return "asset reference"
    if any(token in lowered for token in ("opacity", "alpha", "mask")):
        return {"min": 0.0, "max": 1.0}
    if any(token in lowered for token in ("color", "tint")):
        return {"min": 0.0, "max": 1.0, "space": "linear"}
    if any(token in lowered for token in ("boost", "intensity", "strength", "scale")):
        return {"min": 0.0, "max": 10.0}
    if any(token in lowered for token in ("speed", "rate")):
        return {"min": -10.0, "max": 10.0}
    return {"min": None, "max": None}


def infer_runtime_owner(sources: list[dict[str, Any]]) -> str:
    explicit = choose_value(sources, "runtime_owner")
    if explicit:
        return _text(explicit)
    tools = {source.get("source_tool") for source in sources}
    sections = " ".join(str(source.get("source_section") or "") for source in sources)
    if "runtime_links" in sections:
        return "NiagaraRapidIteration"
    if "chain.override_parameters" in sections or "runtime_param_trace" in tools:
        return "MID"
    return "Material"


def infer_writable_by(sources: list[dict[str, Any]]) -> list[str]:
    values = choose_value(sources, "writable_by") or []
    result = list(dict.fromkeys(_text(item) for item in values if _text(item)))
    sections = " ".join(str(source.get("source_section") or "") for source in sources)
    if "runtime_links" in sections and "Niagara" not in result:
        result.append("Niagara")
    if "chain.override_parameters" in sections and "MID" not in result:
        result.append("MID")
    return result


def build_parameter_schema(name: str, sources: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    sorted_sources = sorted(sources, key=lambda item: source_priority(str(item.get("source_tool") or "")))
    param_type = normalize_type(choose_value(sorted_sources, "type") or "unknown")
    default = choose_value(sorted_sources, "default")
    unit = choose_value(sorted_sources, "unit")
    range_data = choose_value(sorted_sources, "range")
    runtime_owner = infer_runtime_owner(sorted_sources)
    writable_by = infer_writable_by(sorted_sources)
    artist_tunable = choose_value(sorted_sources, "artist_tunable")
    regression = choose_value(sorted_sources, "regression_participation")
    schema = {
        "name": name,
        "type": param_type,
        "default": default,
        "unit": unit or suggest_unit(name, param_type),
        "range": range_data if range_data is not None else suggest_range(param_type, name),
        "runtime_owner": runtime_owner,
        "writable_by": writable_by,
        "artist_tunable": boolean_value(artist_tunable) if artist_tunable is not None else None,
        "regression_participation": boolean_value(regression) if regression is not None else None,
    }
    explicit = {field: any(has_explicit(source, field) for source in sorted_sources if source.get("source_tool") in CONTRACT_TOOLS) for field in REQUIRED_FIELDS}
    explicit["name"] = any(source.get("source_tool") in CONTRACT_TOOLS for source in sorted_sources)
    contract_sources = [source for source in sorted_sources if source.get("source_tool") in CONTRACT_TOOLS]
    live_sources = [source for source in sorted_sources if source.get("source_tool") in LIVE_TOOLS]
    missing = [field for field, present in explicit.items() if field != "name" and not present]
    if param_type in {"texture", "static_switch"}:
        missing = [field for field in missing if field != "range"]
    if param_type in {"vector", "texture"}:
        missing = [field for field in missing if field != "range" or args.require_vector_range]
    return {
        "schema": schema,
        "explicit_contract_fields": explicit,
        "missing_contract_fields": missing,
        "has_contract_row": bool(contract_sources),
        "has_live_evidence": bool(live_sources),
        "sources": [
            {
                "tool": source.get("source_tool"),
                "path": source.get("source_path"),
                "section": source.get("source_section"),
                "type": source.get("type"),
                "default": source.get("default"),
            }
            for source in sorted_sources
        ],
    }


def collect_parameter_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        result.extend(iter_payload_parameters(payload, tool=str(row.get("tool") or ""), path=str(row.get("path") or "")))
    return result


def build_findings(parameters: list[dict[str, Any]], raw_sources: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str, parameter: str = "") -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "parameter": parameter})

    unnamed = [source for source in raw_sources if not source.get("name")]
    for source in unnamed:
        add("error", "unnamed_parameter", f"Parameter row in {source.get('source_tool')} has no name.", "")

    contract_names: list[str] = []
    for source in raw_sources:
        if source.get("source_tool") in CONTRACT_TOOLS and source.get("name"):
            contract_names.append(normalize_key(source["name"]))
    duplicates = sorted({name for name in contract_names if contract_names.count(name) > 1})
    for duplicate in duplicates:
        add("warning", "duplicate_contract_parameter", "Duplicate contract/package parameter name.", duplicate)

    for parameter in parameters:
        schema = parameter["schema"]
        name = schema["name"]
        if not parameter["has_contract_row"]:
            add("warning", "parameter_missing_from_contract", "Live parameter exists but is not listed in the material contract/package.", name)
        missing = parameter.get("missing_contract_fields") or []
        if missing:
            severity = "error" if args.require_complete else "warning"
            add(severity, "missing_contract_fields", "Parameter contract is missing: " + ", ".join(missing), name)
        source_types = sorted({_text(source.get("type")) for source in parameter.get("sources") or [] if _text(source.get("type"))})
        if len({normalize_type(item) for item in source_types}) > 1:
            add("warning", "type_mismatch", f"Parameter type differs across evidence: {source_types}", name)
        source_defaults = sorted({_text(source.get("default")) for source in parameter.get("sources") or [] if source.get("default") not in (None, "")})
        if len(source_defaults) > 1:
            add("warning", "default_mismatch", f"Parameter default differs across evidence: {source_defaults}", name)
        if not schema.get("writable_by") and schema.get("runtime_owner") not in {"Material", "BaseMaterial"}:
            add("warning", "runtime_owner_without_writer", "Runtime owner is set but writable_by is empty.", name)
    return findings


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    package_path = resolve_path(args.package, base=Path.cwd()) if args.package else None
    package = load_json(package_path) if package_path else {}
    contract_path = contract_path_from_package(package, package_path or Path.cwd(), args.contract)
    rows = collect_rows(args, package, package_path, contract_path)
    raw_sources = collect_parameter_sources(rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source in raw_sources:
        name = parameter_name(source)
        if not name:
            continue
        grouped.setdefault(normalize_key(name), []).append(source)
    parameters = [
        build_parameter_schema(sources[0]["name"], sources, args)
        for _, sources in sorted(grouped.items(), key=lambda item: item[0])
    ]
    findings = build_findings(parameters, raw_sources, args)
    counts = severity_counts(findings)
    passed = counts["errors"] == 0 and not (args.fail_on_warning and counts["warnings"])
    effect = args.effect or package.get("effect") or ""
    layer = args.layer or package.get("layer") or ""
    material_path = args.material_path or package.get("material_path") or ""
    report = {
        "tool": "material_parameter_schema",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "material_path": material_path,
        "schema": {
            "parameters": [parameter["schema"] for parameter in parameters],
            "required_fields": list(REQUIRED_FIELDS),
        },
        "parameter_details": parameters,
        "evidence": {
            "package": str(package_path or ""),
            "contract": str(contract_path or ""),
            "audit_reports": [row["path"] for row in rows_by_tool(rows, "material_audit")],
            "runtime_trace_reports": [row["path"] for row in rows_by_tool(rows, "runtime_param_trace")],
            "all_reports": [row["path"] for row in rows],
        },
        "findings": findings,
        "summary": counts,
        "gate": {
            "passed": passed,
            "schema_complete": counts["errors"] == 0 and counts["warnings"] == 0,
            "requires_triage": bool(counts["errors"] or counts["warnings"]),
            "require_complete": bool(args.require_complete),
        },
        "next_actions": next_actions(findings),
    }
    stem = slugify(effect or layer or material_path or "material-parameters")
    out = Path(args.out) if args.out else default_report_path(ctx, "parameter-schemas", stem, "material-parameter-schema", ".json")
    return report, out


def next_actions(findings: list[dict[str, Any]]) -> list[str]:
    rules = {str(item.get("rule") or "") for item in findings if item.get("severity") in {"error", "warning"}}
    actions: list[str] = []
    if "parameter_missing_from_contract" in rules:
        actions.append("Add every live material parameter to the material contract/package parameter table.")
    if "missing_contract_fields" in rules:
        actions.append("Fill unit, range, runtime owner, write owner, artist tunability, and regression participation for each parameter.")
    if "duplicate_contract_parameter" in rules:
        actions.append("Rename or merge duplicate parameter rows before creating MI or Niagara handoff variants.")
    if "type_mismatch" in rules or "default_mismatch" in rules:
        actions.append("Reconcile contract defaults/types with live audit or runtime trace evidence.")
    if not actions:
        actions.append("Parameter schema is structurally complete for current evidence.")
    return actions


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    summary = report.get("summary") or {}
    lines = [
        f"# Material Parameter Schema: {report.get('effect') or report.get('material_path')}",
        "",
        f"- Passed: `{gate.get('passed')}`",
        f"- Schema complete: `{gate.get('schema_complete')}`",
        f"- Parameters: `{len((report.get('schema') or {}).get('parameters') or [])}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        "",
        "## Parameters",
        "",
        "| Name | Type | Unit | Range | Owner | Writable By | Artist | Regression | Missing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.get("parameter_details") or []:
        schema = item.get("schema") or {}
        range_text = json.dumps(schema.get("range"), ensure_ascii=False, sort_keys=True)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{schema.get('name')}`",
                    f"`{schema.get('type')}`",
                    f"`{schema.get('unit')}`",
                    f"`{range_text}`",
                    f"`{schema.get('runtime_owner')}`",
                    f"`{', '.join(schema.get('writable_by') or []) or 'none'}`",
                    f"`{schema.get('artist_tunable')}`",
                    f"`{schema.get('regression_participation')}`",
                    f"`{', '.join(item.get('missing_contract_fields') or []) or 'none'}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Findings", ""])
    for finding in report.get("findings") or []:
        parameter = finding.get("parameter")
        prefix = f"`{parameter}` " if parameter else ""
        lines.append(f"- [{finding.get('severity')}] `{finding.get('rule')}` {prefix}{finding.get('message')}")
    if not report.get("findings"):
        lines.append("- No parameter-schema findings.")
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
    if args.require_complete and not (report.get("gate") or {}).get("schema_complete"):
        print(f"Material parameter schema is incomplete: {out}", file=sys.stderr)
        return 2
    if args.strict and not (report.get("gate") or {}).get("passed"):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build or validate a contract-grade material parameter schema from package, contract, audit, and runtime trace evidence.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--effect", default="")
    parser.add_argument("--layer", default="")
    parser.add_argument("--material-path", default="")
    parser.add_argument("--package", default="", help="delivery_packager.py JSON report.")
    parser.add_argument("--contract", default="", help="material_contract.py JSON report.")
    parser.add_argument("--audit-report", action="append", default=[], help="material_audit.py evidence.")
    parser.add_argument("--runtime-trace-report", action="append", default=[], help="runtime_param_trace.py evidence.")
    parser.add_argument("--parameter-report", action="append", default=[], help="Existing parameter-schema or compatible JSON evidence.")
    parser.add_argument("--require-vector-range", action="store_true", help="Require explicit range fields for vector parameters too.")
    parser.add_argument("--require-complete", action="store_true", help="Return 2 unless every parameter has an explicit contract schema.")
    parser.add_argument("--fail-on-warning", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.package or args.contract or args.audit_report or args.runtime_trace_report or args.parameter_report):
        parser.error("Provide --package, --contract, --audit-report, --runtime-trace-report, or --parameter-report.")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
