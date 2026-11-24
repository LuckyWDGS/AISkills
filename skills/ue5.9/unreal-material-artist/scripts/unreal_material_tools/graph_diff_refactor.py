from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .core import ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso, write_text


PARAMETER_GROUPS = (
    ("scalar_parameters", "scalar"),
    ("vector_parameters", "vector"),
    ("texture_parameters", "texture"),
    ("static_switch_parameters", "static_switch"),
)

ROUTE_FIELDS = (
    "material_domain",
    "blend_mode",
    "shading_models",
    "two_sided",
    "use_material_attributes",
    "usage_flags",
)

BUDGET_FIELDS = (
    "max_instructions",
    "sampler_count",
    "expression_count",
    "instruction_budget",
    "sampler_budget",
)

NODE_EVIDENCE_FIELDS = (
    "texture_sample_nodes",
    "scene_texture_nodes",
    "depth_nodes",
    "world_space_nodes",
    "rvt_nodes",
    "custom_nodes",
    "quality_switch_nodes",
    "material_attribute_nodes",
    "substrate_nodes",
    "vertex_color_nodes",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _value_key(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(_stable(value), ensure_ascii=False, sort_keys=True)
    return _text(value)


def _maybe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _counter_delta(before: Counter[str], after: Counter[str], limit: int = 40) -> dict[str, Any]:
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        old = int(before.get(key, 0))
        new = int(after.get(key, 0))
        if old == new:
            continue
        row = {"key": key, "before": old, "after": new, "delta": new - old}
        if old == 0:
            added.append(row)
        elif new == 0:
            removed.append(row)
        else:
            changed.append(row)
    rows = sorted(added + removed + changed, key=lambda item: (abs(item["delta"]), item["key"]), reverse=True)
    return {
        "added": added[:limit],
        "removed": removed[:limit],
        "changed": changed[:limit],
        "top": rows[:limit],
        "total_changed_keys": len(added) + len(removed) + len(changed),
    }


def _changed_value(field: str, before: Any, after: Any) -> dict[str, Any] | None:
    if _stable(before) == _stable(after):
        return None
    delta: float | None = None
    if not isinstance(before, bool) and not isinstance(after, bool):
        old_num = _maybe_number(before)
        new_num = _maybe_number(after)
        if old_num is not None and new_num is not None:
            delta = round(new_num - old_num, 4)
    result: dict[str, Any] = {"field": field, "before": before, "after": after}
    if delta is not None:
        result["delta"] = delta
    return result


def _set_diff(before: list[Any], after: list[Any]) -> dict[str, Any]:
    before_set = {_value_key(item) for item in before if _value_key(item)}
    after_set = {_value_key(item) for item in after if _value_key(item)}
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "unchanged_count": len(before_set & after_set),
    }


def _material_info(audit: dict[str, Any]) -> dict[str, Any]:
    return audit.get("material_info") if isinstance(audit.get("material_info"), dict) else {}


def _analysis(audit: dict[str, Any]) -> dict[str, Any]:
    return audit.get("analysis") if isinstance(audit.get("analysis"), dict) else {}


def _graph_summary(audit: dict[str, Any]) -> dict[str, Any]:
    return audit.get("graph_summary") if isinstance(audit.get("graph_summary"), dict) else {}


def _raw_graph(audit: dict[str, Any]) -> dict[str, Any]:
    raw = audit.get("raw_graph")
    return raw if isinstance(raw, dict) else {}


def _domain_contract(domain_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not domain_audit:
        return {}
    contract = domain_audit.get("domain_contract")
    return contract if isinstance(contract, dict) else {}


def _node_evidence(domain_audit: dict[str, Any] | None) -> dict[str, Any]:
    if not domain_audit:
        return {}
    evidence = domain_audit.get("node_evidence")
    return evidence if isinstance(evidence, dict) else {}


def report_identity(audit: dict[str, Any], path: Path) -> dict[str, Any]:
    info = _material_info(audit)
    return {
        "path": str(path),
        "tool": audit.get("tool", ""),
        "material_path": audit.get("material_path") or info.get("path") or "",
        "asset_name": info.get("name") or "",
        "is_material_instance": bool(info.get("is_material_instance")),
        "parent_path": info.get("parent_path") or "",
        "base_path": info.get("base_path") or "",
    }


def route_summary(audit: dict[str, Any]) -> dict[str, Any]:
    info = _material_info(audit)
    return {
        "material_domain": info.get("material_domain"),
        "blend_mode": info.get("blend_mode"),
        "shading_models": sorted(_as_list(info.get("shading_models"))),
        "two_sided": info.get("two_sided"),
        "use_material_attributes": info.get("use_material_attributes"),
        "usage_flags": sorted(_as_list(info.get("usage_flags"))),
    }


def compare_route(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_route = route_summary(before)
    after_route = route_summary(after)
    changes = []
    for field in ROUTE_FIELDS:
        change = _changed_value(field, before_route.get(field), after_route.get(field))
        if change:
            changes.append(change)
    return {
        "before": before_route,
        "after": after_route,
        "changes": changes,
        "changed": bool(changes),
    }


def _param_map(info: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in info.get(key) or []:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        result[name.lower()] = {
            "name": name,
            "param_type": item.get("param_type"),
            "value": item.get("value"),
            "guid": item.get("guid"),
        }
    return result


def compare_parameter_group(before_info: dict[str, Any], after_info: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    before = _param_map(before_info, key)
    after = _param_map(after_info, key)
    added = [after[name] for name in sorted(set(after) - set(before))]
    removed = [before[name] for name in sorted(set(before) - set(after))]
    changed: list[dict[str, Any]] = []
    for name in sorted(set(before) & set(after)):
        before_item = before[name]
        after_item = after[name]
        field_changes = []
        for field in ("param_type", "value", "guid"):
            change = _changed_value(field, before_item.get(field), after_item.get(field))
            if change:
                field_changes.append(change)
        if field_changes:
            changed.append(
                {
                    "name": after_item.get("name") or before_item.get("name"),
                    "group": label,
                    "changes": field_changes,
                }
            )
    return {
        "group": label,
        "before_count": len(before),
        "after_count": len(after),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def collect_instance_overrides(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    chain = audit.get("instance_chain") if isinstance(audit.get("instance_chain"), dict) else {}
    result: dict[str, dict[str, Any]] = {}
    for layer in chain.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        layer_path = _text(layer.get("path") or layer.get("name"))
        for param in layer.get("override_parameters") or []:
            if not isinstance(param, dict):
                continue
            name = _text(param.get("name"))
            if not name:
                continue
            key = f"{layer_path.lower()}::{name.lower()}"
            result[key] = {
                "layer_path": layer_path,
                "name": name,
                "param_type": param.get("param_type"),
                "value": param.get("value"),
            }
    return result


def compare_overrides(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_overrides = collect_instance_overrides(before)
    after_overrides = collect_instance_overrides(after)
    added = [after_overrides[key] for key in sorted(set(after_overrides) - set(before_overrides))]
    removed = [before_overrides[key] for key in sorted(set(before_overrides) - set(after_overrides))]
    changed: list[dict[str, Any]] = []
    for key in sorted(set(before_overrides) & set(after_overrides)):
        old = before_overrides[key]
        new = after_overrides[key]
        field_changes = []
        for field in ("param_type", "value"):
            change = _changed_value(field, old.get(field), new.get(field))
            if change:
                field_changes.append(change)
        if field_changes:
            changed.append(
                {
                    "layer_path": new.get("layer_path") or old.get("layer_path"),
                    "name": new.get("name") or old.get("name"),
                    "changes": field_changes,
                }
            )
    stale = {
        "before_count": len(before.get("stale_overrides") or []),
        "after_count": len(after.get("stale_overrides") or []),
    }
    stale["delta"] = stale["after_count"] - stale["before_count"]
    return {
        "before_count": len(before_overrides),
        "after_count": len(after_overrides),
        "added": added,
        "removed": removed,
        "changed": changed,
        "stale_overrides": stale,
    }


def compare_parameters(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_info = _material_info(before)
    after_info = _material_info(after)
    groups = [
        compare_parameter_group(before_info, after_info, key, label)
        for key, label in PARAMETER_GROUPS
    ]
    total = {
        "added": sum(len(group["added"]) for group in groups),
        "removed": sum(len(group["removed"]) for group in groups),
        "changed": sum(len(group["changed"]) for group in groups),
    }
    overrides = compare_overrides(before, after)
    total["override_added"] = len(overrides["added"])
    total["override_removed"] = len(overrides["removed"])
    total["override_changed"] = len(overrides["changed"])
    return {
        "groups": groups,
        "instance_overrides": overrides,
        "total": total,
    }


def budget_summary(audit: dict[str, Any]) -> dict[str, Any]:
    info = _material_info(audit)
    analysis = _analysis(audit)
    summary: dict[str, Any] = {
        "num_expressions": info.get("num_expressions"),
        "num_function_calls": info.get("num_function_calls"),
        "compile_errors": list(analysis.get("compile_errors") or []),
        "shader_stats_ready": analysis.get("shader_stats_ready"),
    }
    for field in BUDGET_FIELDS:
        summary[field] = analysis.get(field)
    return summary


def compare_budget(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_budget = budget_summary(before)
    after_budget = budget_summary(after)
    changes = []
    for field in ("num_expressions", "num_function_calls", *BUDGET_FIELDS, "shader_stats_ready"):
        change = _changed_value(field, before_budget.get(field), after_budget.get(field))
        if change:
            changes.append(change)
    compile_diff = _set_diff(before_budget.get("compile_errors") or [], after_budget.get("compile_errors") or [])
    return {
        "before": before_budget,
        "after": after_budget,
        "changes": changes,
        "compile_errors": compile_diff,
    }


def _node_label(node: dict[str, Any]) -> str:
    caption = _text(node.get("caption"))
    desc = _text(node.get("desc"))
    class_name = _text(node.get("class_name"))
    if caption:
        return f"{class_name}:{caption}"
    if desc:
        return f"{class_name}:{desc}"
    return class_name or "UnknownNode"


def _node_signature(node: dict[str, Any]) -> str:
    key_props = node.get("key_properties")
    return "|".join(
        [
            _text(node.get("class_name")),
            _text(node.get("caption")),
            _text(node.get("desc")),
            _value_key(key_props),
        ]
    )


def _connection_signature(edge: dict[str, Any]) -> str:
    return "|".join(
        [
            _text(edge.get("src_guid")),
            _text(edge.get("src_output_name")),
            _text(edge.get("dst_guid")),
            _text(edge.get("dst_input_name")),
            _text(edge.get("dst_property_name")),
        ]
    )


def _output_chain_map(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    chains: dict[str, dict[str, Any]] = {}
    for item in _graph_summary(audit).get("output_chains") or []:
        if not isinstance(item, dict):
            continue
        prop = _text(item.get("property") or item.get("dst_property_name"))
        if prop:
            chains[prop] = {
                "property": prop,
                "src_guid": item.get("src_guid"),
                "reachable_count": len(item.get("reachable_nodes") or []),
                "reachable_nodes": item.get("reachable_nodes") or [],
            }
    return chains


def _class_counts_from_audit(audit: dict[str, Any], domain_audit: dict[str, Any] | None) -> Counter[str]:
    raw = _raw_graph(audit)
    if raw.get("nodes"):
        return Counter(_text(node.get("class_name")) for node in raw.get("nodes") or [] if isinstance(node, dict))
    evidence = _node_evidence(domain_audit)
    class_counts = evidence.get("class_counts")
    if isinstance(class_counts, dict):
        return Counter({_text(key): int(value or 0) for key, value in class_counts.items()})
    dead_nodes = _graph_summary(audit).get("dead_nodes") or []
    return Counter(_text(node.get("class_name")) for node in dead_nodes if isinstance(node, dict))


def graph_summary(audit: dict[str, Any], domain_audit: dict[str, Any] | None) -> dict[str, Any]:
    raw = _raw_graph(audit)
    graph = _graph_summary(audit)
    output_map = _output_chain_map(audit)
    class_counts = _class_counts_from_audit(audit, domain_audit)
    return {
        "has_raw_graph": bool(raw),
        "node_count": len(raw.get("nodes") or []) if raw else None,
        "connection_count": len(raw.get("connections") or []) if raw else None,
        "output_connection_count": len(raw.get("output_connections") or []) if raw else len(output_map),
        "live_node_count": len(graph.get("live_node_guids") or []),
        "dead_node_count": len(graph.get("dead_nodes") or []),
        "output_properties": sorted(output_map),
        "class_counts": dict(sorted(class_counts.items())),
    }


def compare_output_chains(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_outputs = _output_chain_map(before)
    after_outputs = _output_chain_map(after)
    added = [after_outputs[key] for key in sorted(set(after_outputs) - set(before_outputs))]
    removed = [before_outputs[key] for key in sorted(set(before_outputs) - set(after_outputs))]
    changed: list[dict[str, Any]] = []
    for prop in sorted(set(before_outputs) & set(after_outputs)):
        old = before_outputs[prop]
        new = after_outputs[prop]
        field_changes = []
        for field in ("src_guid", "reachable_count"):
            change = _changed_value(field, old.get(field), new.get(field))
            if change:
                field_changes.append(change)
        if field_changes:
            changed.append({"property": prop, "changes": field_changes})
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def compare_raw_graph(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_raw = _raw_graph(before)
    after_raw = _raw_graph(after)
    if not before_raw or not after_raw:
        return {
            "available": False,
            "reason": "Run material_audit.py with --include-raw-graph on both revisions for GUID-level node and connection diffs.",
        }

    before_nodes = {node.get("guid"): node for node in before_raw.get("nodes") or [] if isinstance(node, dict) and node.get("guid")}
    after_nodes = {node.get("guid"): node for node in after_raw.get("nodes") or [] if isinstance(node, dict) and node.get("guid")}
    added_nodes = [
        {
            "guid": guid,
            "label": _node_label(after_nodes[guid]),
            "class_name": after_nodes[guid].get("class_name"),
        }
        for guid in sorted(set(after_nodes) - set(before_nodes))
    ]
    removed_nodes = [
        {
            "guid": guid,
            "label": _node_label(before_nodes[guid]),
            "class_name": before_nodes[guid].get("class_name"),
        }
        for guid in sorted(set(before_nodes) - set(after_nodes))
    ]
    changed_nodes: list[dict[str, Any]] = []
    for guid in sorted(set(before_nodes) & set(after_nodes)):
        old = before_nodes[guid]
        new = after_nodes[guid]
        field_changes = []
        for field in ("class_name", "caption", "desc", "x", "y", "input_names", "output_names", "key_properties"):
            change = _changed_value(field, old.get(field), new.get(field))
            if change:
                field_changes.append(change)
        if field_changes:
            changed_nodes.append(
                {
                    "guid": guid,
                    "before_label": _node_label(old),
                    "after_label": _node_label(new),
                    "changes": field_changes,
                }
            )

    before_signature_counts = Counter(_node_signature(node) for node in before_nodes.values())
    after_signature_counts = Counter(_node_signature(node) for node in after_nodes.values())
    before_connections = Counter(
        _connection_signature(edge)
        for edge in before_raw.get("connections") or []
        if isinstance(edge, dict)
    )
    after_connections = Counter(
        _connection_signature(edge)
        for edge in after_raw.get("connections") or []
        if isinstance(edge, dict)
    )
    before_output_connections = Counter(
        _connection_signature(edge)
        for edge in before_raw.get("output_connections") or []
        if isinstance(edge, dict)
    )
    after_output_connections = Counter(
        _connection_signature(edge)
        for edge in after_raw.get("output_connections") or []
        if isinstance(edge, dict)
    )

    return {
        "available": True,
        "guid_nodes": {
            "added": added_nodes[:80],
            "removed": removed_nodes[:80],
            "changed": changed_nodes[:80],
            "added_count": len(added_nodes),
            "removed_count": len(removed_nodes),
            "changed_count": len(changed_nodes),
        },
        "node_signature_counts": _counter_delta(before_signature_counts, after_signature_counts),
        "connection_counts": _counter_delta(before_connections, after_connections),
        "output_connection_counts": _counter_delta(before_output_connections, after_output_connections),
    }


def compare_dead_nodes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_dead = _graph_summary(before).get("dead_nodes") or []
    after_dead = _graph_summary(after).get("dead_nodes") or []
    before_counter = Counter(_node_label(node) for node in before_dead if isinstance(node, dict))
    after_counter = Counter(_node_label(node) for node in after_dead if isinstance(node, dict))
    return {
        "before_count": len(before_dead),
        "after_count": len(after_dead),
        "delta": len(after_dead) - len(before_dead),
        "signature_counts": _counter_delta(before_counter, after_counter),
    }


def compare_graph(
    before: dict[str, Any],
    after: dict[str, Any],
    before_domain: dict[str, Any] | None,
    after_domain: dict[str, Any] | None,
) -> dict[str, Any]:
    before_summary = graph_summary(before, before_domain)
    after_summary = graph_summary(after, after_domain)
    class_diff = _counter_delta(
        Counter(before_summary.get("class_counts") or {}),
        Counter(after_summary.get("class_counts") or {}),
    )
    scalar_changes = []
    for field in ("node_count", "connection_count", "output_connection_count", "live_node_count", "dead_node_count"):
        change = _changed_value(field, before_summary.get(field), after_summary.get(field))
        if change:
            scalar_changes.append(change)
    return {
        "before": before_summary,
        "after": after_summary,
        "scalar_changes": scalar_changes,
        "class_count_changes": class_diff,
        "output_chains": compare_output_chains(before, after),
        "dead_nodes": compare_dead_nodes(before, after),
        "raw_graph": compare_raw_graph(before, after),
    }


def _finding_key(item: dict[str, Any]) -> str:
    return "|".join(
        [
            _text(item.get("severity")).lower(),
            _text(item.get("rule_id") or item.get("rule") or item.get("id")),
            _text(item.get("message")),
        ]
    )


def _finding_summary(item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "severity": item.get("severity"),
        "rule": item.get("rule_id") or item.get("rule") or item.get("id"),
        "message": item.get("message"),
        "evidence": item.get("evidence") or item.get("detail") or "",
        "recommendation": item.get("recommendation") or "",
    }


def _collect_findings(audit: dict[str, Any] | None, source: str) -> dict[str, dict[str, Any]]:
    if not audit:
        return {}
    findings: dict[str, dict[str, Any]] = {}
    analysis_findings = (_analysis(audit).get("findings") or []) if audit.get("tool") == "material_audit" else []
    for item in analysis_findings:
        if isinstance(item, dict):
            findings[f"{source}:analysis:{_finding_key(item)}"] = _finding_summary(item, f"{source}:analysis")
    for item in audit.get("findings") or []:
        if isinstance(item, dict):
            findings[f"{source}:domain:{_finding_key(item)}"] = _finding_summary(item, f"{source}:domain")
    return findings


def compare_findings(
    before: dict[str, Any],
    after: dict[str, Any],
    before_domain: dict[str, Any] | None,
    after_domain: dict[str, Any] | None,
) -> dict[str, Any]:
    before_findings = {}
    after_findings = {}
    before_findings.update(_collect_findings(before, "material"))
    after_findings.update(_collect_findings(after, "material"))
    before_findings.update(_collect_findings(before_domain, "domain"))
    after_findings.update(_collect_findings(after_domain, "domain"))
    added = [after_findings[key] for key in sorted(set(after_findings) - set(before_findings))]
    resolved = [before_findings[key] for key in sorted(set(before_findings) - set(after_findings))]
    persisted = [after_findings[key] for key in sorted(set(after_findings) & set(before_findings))]
    return {
        "added": added,
        "resolved": resolved,
        "persisted_count": len(persisted),
        "added_errors": sum(1 for item in added if _text(item.get("severity")).lower() == "error"),
        "added_warnings": sum(1 for item in added if _text(item.get("severity")).lower() == "warning"),
    }


def compare_domain_audits(before_domain: dict[str, Any] | None, after_domain: dict[str, Any] | None) -> dict[str, Any]:
    if not before_domain and not after_domain:
        return {
            "available": False,
            "reason": "Provide --before-domain-audit and --after-domain-audit to compare render-contract evidence.",
        }
    before_contract = _domain_contract(before_domain)
    after_contract = _domain_contract(after_domain)
    fields = (
        "domain",
        "blend_mode",
        "shading_models",
        "two_sided",
        "use_material_attributes",
        "usage_flags",
    )
    contract_changes = []
    for field in fields:
        change = _changed_value(field, before_contract.get(field), after_contract.get(field))
        if change:
            contract_changes.append(change)
    wired_outputs = _set_diff(before_contract.get("wired_outputs") or [], after_contract.get("wired_outputs") or [])

    before_evidence = _node_evidence(before_domain)
    after_evidence = _node_evidence(after_domain)
    evidence_changes = []
    for field in NODE_EVIDENCE_FIELDS:
        change = _changed_value(field, before_evidence.get(field), after_evidence.get(field))
        if change:
            evidence_changes.append(change)
    class_counts_before = before_evidence.get("class_counts") if isinstance(before_evidence.get("class_counts"), dict) else {}
    class_counts_after = after_evidence.get("class_counts") if isinstance(after_evidence.get("class_counts"), dict) else {}

    return {
        "available": True,
        "before": {
            "contract": before_contract,
            "summary": (before_domain or {}).get("summary") or {},
        },
        "after": {
            "contract": after_contract,
            "summary": (after_domain or {}).get("summary") or {},
        },
        "contract_changes": contract_changes,
        "wired_outputs": wired_outputs,
        "node_evidence_changes": evidence_changes,
        "class_count_changes": _counter_delta(Counter(class_counts_before), Counter(class_counts_after)),
    }


def summarize_regression(regression: dict[str, Any] | None, path: Path | None) -> dict[str, Any]:
    if not regression:
        return {
            "available": False,
            "path": "",
            "passed": None,
            "findings": [],
            "metrics": [],
        }
    gate = regression.get("gate") if isinstance(regression.get("gate"), dict) else {}
    metrics: list[dict[str, Any]] = []
    for comparison in regression.get("comparisons") or []:
        if not isinstance(comparison, dict):
            continue
        row = {
            "role": comparison.get("role"),
            "error": comparison.get("error") or "",
            "metrics": comparison.get("metrics") or {},
            "outputs": comparison.get("outputs") or {},
        }
        metrics.append(row)
    return {
        "available": True,
        "path": str(path or ""),
        "effect": regression.get("effect"),
        "layer": regression.get("layer"),
        "label": regression.get("label"),
        "passed": gate.get("passed"),
        "errors": gate.get("errors", 0),
        "warnings": gate.get("warnings", 0),
        "findings": gate.get("findings") or [],
        "metrics": metrics,
    }


def _param_names_with_tokens(parameters: dict[str, Any], tokens: tuple[str, ...]) -> list[str]:
    names: list[str] = []
    for group in parameters.get("groups") or []:
        for bucket in ("added", "removed"):
            for item in group.get(bucket) or []:
                name = _text(item.get("name"))
                blob = " ".join([name, _text(item.get("param_type")), _text(item.get("value"))]).lower()
                if any(token in blob for token in tokens):
                    names.append(name)
        for item in group.get("changed") or []:
            name = _text(item.get("name"))
            blob = json.dumps(item, ensure_ascii=False).lower()
            if any(token in blob for token in tokens):
                names.append(name)
    overrides = parameters.get("instance_overrides") or {}
    for bucket in ("added", "removed", "changed"):
        for item in overrides.get(bucket) or []:
            name = _text(item.get("name"))
            blob = json.dumps(item, ensure_ascii=False).lower()
            if any(token in blob for token in tokens):
                names.append(name)
    return sorted(set(name for name in names if name))


def _changed_fields(changes: list[dict[str, Any]]) -> set[str]:
    return {_text(change.get("field")) for change in changes}


def _top_metric(regression_summary: dict[str, Any], metric: str) -> float:
    values = []
    for row in regression_summary.get("metrics") or []:
        metrics = row.get("metrics") or {}
        value = _maybe_number(metrics.get(metric))
        if value is not None:
            values.append(abs(value))
    return max(values) if values else 0.0


def infer_likely_causes(diff: dict[str, Any]) -> list[dict[str, Any]]:
    causes: list[dict[str, Any]] = []

    def add(severity: str, category: str, reason: str, evidence: str, recommendation: str) -> None:
        causes.append(
            {
                "severity": severity,
                "category": category,
                "reason": reason,
                "evidence": evidence,
                "recommendation": recommendation,
            }
        )

    route = diff["diffs"]["route"]
    budget = diff["diffs"]["budget"]
    params = diff["diffs"]["parameters"]
    graph = diff["diffs"]["graph"]
    domain = diff["diffs"]["domain"]
    findings = diff["diffs"]["findings"]
    regression = diff["regression"]
    route_fields = _changed_fields(route.get("changes") or [])
    domain_fields = _changed_fields(domain.get("contract_changes") or [])
    output_added = (graph.get("output_chains") or {}).get("added") or []
    output_removed = (graph.get("output_chains") or {}).get("removed") or []
    output_changed = (graph.get("output_chains") or {}).get("changed") or []
    output_count = len(output_added) + len(output_removed) + len(output_changed)

    if route_fields & {"material_domain", "blend_mode", "shading_models", "two_sided", "use_material_attributes"}:
        add(
            "high",
            "route",
            "Render route changed between audits.",
            ", ".join(sorted(route_fields)),
            "Restore the old domain/blend/shading route first, or intentionally accept a new baseline after art review.",
        )
    if domain_fields & {"domain", "blend_mode", "shading_models", "two_sided", "use_material_attributes"}:
        add(
            "high",
            "domain_contract",
            "Domain audit contract changed.",
            ", ".join(sorted(domain_fields)),
            "Treat this as a render-path change; rerun preview and domain audit before judging node-level changes.",
        )
    if output_count:
        add(
            "high",
            "output_chain",
            "Material output wiring changed.",
            f"added={len(output_added)} removed={len(output_removed)} changed={len(output_changed)}",
            "Inspect changed output properties first; BaseColor, Emissive, Opacity, OpacityMask, Normal, WPO, PDO, and Refraction are common drift sources.",
        )

    brightness_delta = _top_metric(regression, "brightness_delta")
    alpha_delta = _top_metric(regression, "alpha_coverage_delta")
    visual_delta = _top_metric(regression, "visual_coverage_delta")
    centroid_shift = _top_metric(regression, "centroid_shift_px")
    mean_diff = _top_metric(regression, "mean_abs_rgb")
    brightness_params = _param_names_with_tokens(
        params,
        ("color", "base", "emissive", "brightness", "intensity", "tint", "roughness", "metallic", "specular", "coat"),
    )
    alpha_params = _param_names_with_tokens(params, ("opacity", "alpha", "mask", "cutoff", "dither", "fade"))
    texture_params = _param_names_with_tokens(params, ("texture", "tex", "_t_", "mask", "normal", "rma", "orm", "basecolor"))

    if brightness_delta and (brightness_params or route_fields & {"blend_mode", "shading_models"}):
        add(
            "medium",
            "brightness",
            "Regression brightness drift lines up with color, emissive, roughness, or shading-route changes.",
            f"brightness_delta={brightness_delta}; params={', '.join(brightness_params[:10]) or 'none'}",
            "Check color/emissive defaults and lit/unlit/shading model changes before tuning unrelated math.",
        )
    if alpha_delta and (alpha_params or "blend_mode" in route_fields or output_count):
        add(
            "medium",
            "alpha_coverage",
            "Alpha or coverage drift lines up with opacity/mask/blend/output changes.",
            f"alpha_delta={alpha_delta}; params={', '.join(alpha_params[:10]) or 'none'}",
            "Review Opacity/OpacityMask chains, mask texture import settings, cutoff thresholds, and blend mode.",
        )
    if visual_delta or centroid_shift:
        class_top = (graph.get("class_count_changes") or {}).get("top") or []
        add(
            "medium",
            "composition",
            "Visual coverage or centroid changed, which often means mask, UV, WPO/PDO, or output-chain drift.",
            f"visual_delta={visual_delta}; centroid_shift={centroid_shift}; class_changes={class_top[:5]}",
            "Compare UV/mask/WPO/PDO nodes and confirm the same preview carrier was used.",
        )
    if mean_diff and texture_params:
        add(
            "medium",
            "texture_inputs",
            "Large visual diff may be driven by changed texture or mask parameters.",
            f"mean_abs_rgb={mean_diff}; texture-like params={', '.join(texture_params[:10])}",
            "Pair this graph diff with texture reports or import audits for the changed texture set.",
        )

    budget_changes = {change["field"]: change for change in budget.get("changes") or []}
    if any(field in budget_changes for field in ("max_instructions", "sampler_count", "expression_count", "num_expressions")):
        evidence_bits = []
        for field in ("max_instructions", "sampler_count", "expression_count", "num_expressions"):
            if field in budget_changes:
                evidence_bits.append(f"{field} delta={budget_changes[field].get('delta')}")
        add(
            "medium",
            "budget",
            "Shader budget changed between audits.",
            "; ".join(evidence_bits),
            "If the visual change is unintended, isolate recent graph additions before optimizing. If intended, refresh complexity preview evidence.",
        )
    if findings.get("added_errors") or findings.get("added_warnings"):
        add(
            "medium",
            "audit_findings",
            "New audit findings appeared after the change.",
            f"errors={findings.get('added_errors')} warnings={findings.get('added_warnings')}",
            "Resolve new errors first, then warnings tied to domain, compile, stale overrides, or expensive render features.",
        )
    if graph.get("dead_nodes", {}).get("delta", 0) > 0:
        add(
            "low",
            "cleanup",
            "Dead graph node count increased.",
            f"dead_nodes_delta={graph.get('dead_nodes', {}).get('delta')}",
            "Remove or reconnect dead branches after the visual route is confirmed.",
        )
    raw_graph = graph.get("raw_graph") or {}
    if not raw_graph.get("available"):
        add(
            "info",
            "evidence_gap",
            "GUID-level graph diff is unavailable.",
            raw_graph.get("reason", ""),
            "Rerun both material audits with --include-raw-graph when exact node/connection provenance matters.",
        )
    if regression.get("available") and regression.get("passed") is False and not causes:
        add(
            "info",
            "unexplained_regression",
            "Regression failed but this audit pair did not expose an obvious material-side cause.",
            "No route, output, parameter, budget, or finding changes crossed the first-pass heuristics.",
            "Check texture import reports, preview carrier/options, camera framing, lighting, or runtime parameter sources.",
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    return sorted(causes, key=lambda item: (severity_rank.get(item["severity"], 9), item["category"]))


def build_recommendations(diff: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    causes = diff.get("likely_causes") or []
    regression = diff.get("regression") or {}
    graph = diff.get("diffs", {}).get("graph") or {}
    domain = diff.get("diffs", {}).get("domain") or {}
    budget = diff.get("diffs", {}).get("budget") or {}

    if regression.get("available") and regression.get("passed") is False:
        recommendations.append("Treat the current preview as not accepted until the listed high/medium causes are either fixed or explicitly approved as a new look.")
    if any(item.get("category") in {"route", "domain_contract", "output_chain"} for item in causes):
        recommendations.append("Review route and output-chain changes before tuning parameters; render-path changes can dominate every visual metric.")
    if any(item.get("category") == "brightness" for item in causes):
        recommendations.append("Diff color/emissive/roughness defaults and rerender after reverting only those values to confirm brightness causality.")
    if any(item.get("category") == "alpha_coverage" for item in causes):
        recommendations.append("Check opacity and mask sources, then rerender against the same regression baseline with alpha/coverage thresholds unchanged.")
    if any(item.get("category") == "texture_inputs" for item in causes):
        recommendations.append("Run texture_set_pipeline or texture/import audits for the changed texture inputs before blaming shader math.")
    if budget.get("compile_errors", {}).get("added"):
        recommendations.append("Fix newly added compile errors before interpreting visual regression metrics.")
    if not graph.get("raw_graph", {}).get("available"):
        recommendations.append("For a precise refactor plan, rerun material_audit.py with --include-raw-graph on both revisions.")
    if not domain.get("available"):
        recommendations.append("Add material_domain_audit.py reports to catch domain, output-pin, and render-contract drift.")
    if not recommendations:
        recommendations.append("No high-risk graph diff was detected; if regression failed, compare preview options, texture reports, and runtime parameter traces next.")
    return recommendations


def build_diff(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    before_audit_path = Path(args.before_audit)
    after_audit_path = Path(args.after_audit)
    before_audit = load_json(before_audit_path)
    after_audit = load_json(after_audit_path)
    if before_audit.get("tool") != "material_audit":
        raise SystemExit(f"Expected material_audit for --before-audit, got `{before_audit.get('tool')}`")
    if after_audit.get("tool") != "material_audit":
        raise SystemExit(f"Expected material_audit for --after-audit, got `{after_audit.get('tool')}`")

    before_domain_path = Path(args.before_domain_audit) if args.before_domain_audit else None
    after_domain_path = Path(args.after_domain_audit) if args.after_domain_audit else None
    before_domain = load_json(before_domain_path) if before_domain_path else None
    after_domain = load_json(after_domain_path) if after_domain_path else None
    if before_domain and before_domain.get("tool") != "material_domain_audit":
        raise SystemExit(f"Expected material_domain_audit for --before-domain-audit, got `{before_domain.get('tool')}`")
    if after_domain and after_domain.get("tool") != "material_domain_audit":
        raise SystemExit(f"Expected material_domain_audit for --after-domain-audit, got `{after_domain.get('tool')}`")

    regression_path = Path(args.regression_report) if args.regression_report else None
    regression_report = load_json(regression_path) if regression_path else None
    if regression_report and regression_report.get("tool") != "material_regression_compare":
        raise SystemExit(f"Expected material_regression_compare for --regression-report, got `{regression_report.get('tool')}`")
    regression_summary = summarize_regression(regression_report, regression_path)

    effect = args.effect or _text(regression_summary.get("effect")) or "Material"
    layer = args.layer or _text(regression_summary.get("layer")) or "GraphDiff"
    before_material = _text(report_identity(before_audit, before_audit_path).get("material_path"))
    after_material = _text(report_identity(after_audit, after_audit_path).get("material_path"))
    label = args.label or slugify(f"{before_material or 'before'}-to-{after_material or 'after'}")[:96]

    report: dict[str, Any] = {
        "tool": "graph_diff_refactor",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": label,
        "inputs": {
            "before_audit": str(before_audit_path),
            "after_audit": str(after_audit_path),
            "before_domain_audit": str(before_domain_path or ""),
            "after_domain_audit": str(after_domain_path or ""),
            "regression_report": str(regression_path or ""),
        },
        "identity": {
            "before": report_identity(before_audit, before_audit_path),
            "after": report_identity(after_audit, after_audit_path),
        },
        "regression": regression_summary,
        "diffs": {
            "route": compare_route(before_audit, after_audit),
            "parameters": compare_parameters(before_audit, after_audit),
            "budget": compare_budget(before_audit, after_audit),
            "graph": compare_graph(before_audit, after_audit, before_domain, after_domain),
            "domain": compare_domain_audits(before_domain, after_domain),
            "findings": compare_findings(before_audit, after_audit, before_domain, after_domain),
        },
        "likely_causes": [],
        "refactor_recommendations": [],
        "gate": {},
    }
    report["likely_causes"] = infer_likely_causes(report)
    report["refactor_recommendations"] = build_recommendations(report)
    high = sum(1 for item in report["likely_causes"] if item.get("severity") == "high")
    medium = sum(1 for item in report["likely_causes"] if item.get("severity") == "medium")
    regression_failed = regression_summary.get("available") and regression_summary.get("passed") is False
    report["gate"] = {
        "requires_review": bool(high or medium or regression_failed),
        "regression_failed": bool(regression_failed),
        "explains_regression": bool(regression_failed and (high or medium)),
        "high_causes": high,
        "medium_causes": medium,
        "raw_graph_available": bool((report["diffs"]["graph"].get("raw_graph") or {}).get("available")),
        "domain_audit_available": bool(report["diffs"]["domain"].get("available")),
    }

    out = Path(args.out) if args.out else ctx.material_root / "graph-diffs" / slugify(f"{effect}-{layer}-{label}") / "graph-diff-refactor.json"
    return report, out


def _format_change(change: dict[str, Any]) -> str:
    field = change.get("field")
    before = change.get("before")
    after = change.get("after")
    if "delta" in change:
        return f"`{field}` `{before}` -> `{after}` delta=`{change.get('delta')}`"
    return f"`{field}` `{before}` -> `{after}`"


def _limit(items: list[Any], count: int = 12) -> list[Any]:
    return items[:count]


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    regression = report.get("regression") or {}
    identity = report.get("identity") or {}
    before_id = identity.get("before") or {}
    after_id = identity.get("after") or {}
    diffs = report.get("diffs") or {}
    route = diffs.get("route") or {}
    budget = diffs.get("budget") or {}
    params = diffs.get("parameters") or {}
    graph = diffs.get("graph") or {}
    domain = diffs.get("domain") or {}
    findings = diffs.get("findings") or {}

    lines = [
        f"# Graph Diff Refactor: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Requires review: `{gate.get('requires_review')}`",
        f"- Regression failed: `{gate.get('regression_failed')}`",
        f"- Explains regression: `{gate.get('explains_regression')}`",
        f"- Before: `{before_id.get('material_path')}`",
        f"- After: `{after_id.get('material_path')}`",
        f"- Regression report: `{regression.get('path') or 'none'}`",
        "",
        "## Likely Causes",
        "",
    ]
    if report.get("likely_causes"):
        for cause in _limit(report["likely_causes"], 12):
            lines.append(
                f"- [{cause.get('severity')}] `{cause.get('category')}` {cause.get('reason')} "
                f"Evidence: {cause.get('evidence')}"
            )
    else:
        lines.append("- No likely causes inferred from the supplied audits.")

    lines.extend(["", "## Route And Budget", ""])
    if route.get("changes"):
        for change in route["changes"]:
            lines.append(f"- Route {_format_change(change)}")
    else:
        lines.append("- Route unchanged.")
    if domain.get("available") and domain.get("wired_outputs"):
        wired = domain["wired_outputs"]
        if wired.get("added") or wired.get("removed"):
            lines.append(f"- Wired outputs added=`{', '.join(wired.get('added') or []) or 'none'}` removed=`{', '.join(wired.get('removed') or []) or 'none'}`")
    if budget.get("changes"):
        for change in budget["changes"]:
            lines.append(f"- Budget {_format_change(change)}")
    else:
        lines.append("- Budget fields unchanged.")
    if budget.get("compile_errors", {}).get("added") or budget.get("compile_errors", {}).get("removed"):
        lines.append(
            f"- Compile errors added=`{len(budget['compile_errors'].get('added') or [])}` "
            f"removed=`{len(budget['compile_errors'].get('removed') or [])}`"
        )

    lines.extend(["", "## Parameters", ""])
    totals = params.get("total") or {}
    lines.append(
        f"- Defaults added=`{totals.get('added', 0)}` removed=`{totals.get('removed', 0)}` changed=`{totals.get('changed', 0)}`"
    )
    lines.append(
        f"- MI overrides added=`{totals.get('override_added', 0)}` removed=`{totals.get('override_removed', 0)}` changed=`{totals.get('override_changed', 0)}`"
    )
    for group in params.get("groups") or []:
        changed = group.get("changed") or []
        added = group.get("added") or []
        removed = group.get("removed") or []
        if not (changed or added or removed):
            continue
        lines.append(
            f"- `{group.get('group')}` added=`{len(added)}` removed=`{len(removed)}` changed=`{len(changed)}`"
        )
        for item in _limit(changed, 6):
            lines.append(f"- `{group.get('group')}` changed param `{item.get('name')}`")

    lines.extend(["", "## Graph", ""])
    raw = graph.get("raw_graph") or {}
    lines.append(f"- Raw graph diff available: `{raw.get('available')}`")
    if not raw.get("available") and raw.get("reason"):
        lines.append(f"- Raw graph note: {raw.get('reason')}")
    output = graph.get("output_chains") or {}
    lines.append(
        f"- Output chains added=`{len(output.get('added') or [])}` removed=`{len(output.get('removed') or [])}` changed=`{len(output.get('changed') or [])}`"
    )
    dead = graph.get("dead_nodes") or {}
    lines.append(f"- Dead nodes `{dead.get('before_count')}` -> `{dead.get('after_count')}` delta=`{dead.get('delta')}`")
    class_top = (graph.get("class_count_changes") or {}).get("top") or []
    for row in _limit(class_top, 8):
        lines.append(f"- Node class `{row.get('key')}` `{row.get('before')}` -> `{row.get('after')}` delta=`{row.get('delta')}`")
    if raw.get("available"):
        guid_nodes = raw.get("guid_nodes") or {}
        lines.append(
            f"- GUID nodes added=`{guid_nodes.get('added_count')}` removed=`{guid_nodes.get('removed_count')}` changed=`{guid_nodes.get('changed_count')}`"
        )

    lines.extend(["", "## Findings", ""])
    lines.append(
        f"- Added findings errors=`{findings.get('added_errors', 0)}` warnings=`{findings.get('added_warnings', 0)}` resolved=`{len(findings.get('resolved') or [])}`"
    )
    for item in _limit(findings.get("added") or [], 8):
        lines.append(f"- [{item.get('severity')}] `{item.get('rule')}` {item.get('message')}")

    lines.extend(["", "## Recommendations", ""])
    for item in report.get("refactor_recommendations") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command_diff(args: argparse.Namespace) -> int:
    report, out = build_diff(args)
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 1 if args.strict and report["gate"]["requires_review"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare material audit reports and explain graph, parameter, route, and budget changes behind regression drift."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    diff = sub.add_parser("diff", help="Diff two material_audit reports, optionally with domain audits and regression evidence.")
    diff.add_argument("--root", default="auto")
    diff.add_argument("--before-audit", required=True)
    diff.add_argument("--after-audit", required=True)
    diff.add_argument("--before-domain-audit")
    diff.add_argument("--after-domain-audit")
    diff.add_argument("--regression-report")
    diff.add_argument("--effect")
    diff.add_argument("--layer")
    diff.add_argument("--label", default="")
    diff.add_argument("--out")
    diff.add_argument("--markdown", action="store_true")
    diff.add_argument("--strict", action="store_true", help="Return non-zero when review is required.")
    diff.set_defaults(func=command_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
