"""Apply graph_refactor_apply operations to a candidate copy of a material through Epic MCP.

The original material is never edited: AssetTools duplicates it to a backup and a candidate,
every operation edits the candidate with MaterialTools/ObjectTools and reads its wiring back,
and both copies are saved only when every operation succeeded.
"""

from __future__ import annotations

import json
from typing import Any

from .material_audit import node_id, ref_of
from .material_toolset_builder import _enum, resolve_input_name, route_properties
from .mcp import builtin_mcp


TRANSLUCENT_BLENDS = {"BLEND_Translucent", "BLEND_Additive", "BLEND_Modulate", "BLEND_AlphaComposite", "BLEND_AlphaHoldout"}
EXPRESSION_CLASS = "/Script/Engine.MaterialExpression{}"


class RefactorError(RuntimeError):
    pass


def object_path(path: str) -> str:
    clean = str(path or "").strip()
    last = clean.rsplit("/", 1)[-1]
    return clean if not clean or "." in last else f"{clean}.{last}"


def package_path(path: str) -> str:
    return object_path(path).split(".", 1)[0]


class RefactorRunner:
    def __init__(self, client: Any, candidate: str) -> None:
        self.client = client
        self.ue = builtin_mcp()
        self.material = {"refPath": object_path(candidate)}
        self.calls: list[dict[str, Any]] = []

    def call(self, toolset: str, tool: str, args: dict[str, Any]) -> Any:
        row: dict[str, Any] = {"tool": f"{toolset}.{tool}", "args": args}
        self.calls.append(row)
        try:
            row["result"] = self.ue.unwrap_result(self.client.call_resolved_tool(toolset, tool, args))
        except self.ue.McpError as exc:
            row["error"] = str(exc)
            raise RefactorError(f"{toolset}.{tool} failed: {exc}") from exc
        return row["result"]

    # -- graph helpers ---------------------------------------------------------------------------
    def properties(self, names: list[str]) -> dict[str, Any]:
        value = self.call("ObjectTools", "get_properties", {"instance": self.material, "properties": names})
        return json.loads(value) if isinstance(value, str) else (value or {})

    def set_properties(self, ref: dict[str, str], values: dict[str, Any]) -> None:
        self.call("ObjectTools", "set_properties", {"instance": ref, "values": json.dumps(values)})

    def output_source(self, prop: str) -> tuple[str, str]:
        value = self.call("MaterialTools", "get_property_input", {"material": self.material, "material_property": prop}) or {}
        return ref_of(value.get("expression")), str(value.get("output_name") or "")

    def expressions_by_node(self) -> dict[str, str]:
        refs = [ref_of(item) for item in self.call("MaterialTools", "get_expressions", {"material_or_function": self.material}) or []]
        return {node_id(ref): ref for ref in refs if ref}

    def add(self, class_name: str, x: int, y: int, values: dict[str, Any] | None = None) -> dict[str, str]:
        ref = ref_of(self.call("MaterialTools", "add_expression", {"material_or_function": self.material,
                                                                   "expression_class": {"refPath": EXPRESSION_CLASS.format(class_name)},
                                                                   "x": x, "y": y}))
        if not ref:
            raise RefactorError(f"add_expression returned no {class_name}")
        expression = {"refPath": ref}
        if values:
            self.set_properties(expression, values)
        return expression

    def connect(self, source: dict[str, str], output: str, target: dict[str, str], input_name: str) -> None:
        inputs = self.call("MaterialTools", "get_expression_input_names", {"expression": target}) or []
        resolved = resolve_input_name(input_name, inputs)
        if resolved is None:
            raise RefactorError(f"{node_id(target['refPath'])} has no input {input_name!r} (pins: {inputs})")
        self.call("MaterialTools", "connect_expressions", {"from_expression": source, "from_output_name": output,
                                                           "to_expression": target, "to_input_name": resolved})

    def connect_output(self, source: dict[str, str], output: str, prop: str) -> None:
        self.call("MaterialTools", "connect_to_output", {"expression": source, "output_name": output, "material_property": prop})
        actual, _ = self.output_source(prop)
        if actual.lower() != source["refPath"].lower():
            raise RefactorError(f"{prop} reads back {actual or 'nothing'}, expected {source['refPath']}")

    # -- operations ------------------------------------------------------------------------------
    def restore_route_contract(self, operation: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        route = payload.get("route_restore") or {}
        if not route:
            raise RefactorError("no before-route evidence")
        values = route_properties(route)
        values.update({flag: True for flag in route.get("usage_flags") or [] if str(flag).startswith("bUsedWith")})
        self.set_properties(self.material, values)
        actual = self.properties(sorted(values))
        drift = {key: actual.get(key) for key, value in values.items() if actual.get(key) != value}
        if drift:
            raise RefactorError(f"route did not read back: {drift}")
        return {"restored": sorted(values)}

    def repair_output_chain(self, operation: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        by_node = self.expressions_by_node()
        repaired, unchanged = [], []
        for row in payload.get("before_output_connections") or []:
            prop = _enum("MP_", row.get("dst_property_name") or row.get("property") or "")
            source = by_node.get(str(row.get("src_guid") or node_id(row.get("source"))))
            if not source:
                raise RefactorError(f"{prop}: before source {row.get('src_guid')} is not in the candidate graph")
            current, _ = self.output_source(prop)
            if current.lower() == source.lower():
                unchanged.append(prop)
                continue
            self.connect_output({"refPath": source}, str(row.get("src_output_name") or ""), prop)
            repaired.append(prop)
        return {"repaired": repaired, "unchanged": unchanged}

    def add_depth_fade(self, operation: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        blend = str(self.properties(["blendMode"]).get("blendMode") or "")
        if blend not in TRANSLUCENT_BLENDS:
            raise RefactorError(f"DepthFade only applies to translucent routes; candidate blend is {blend or 'unknown'}")
        source, output = self.output_source("MP_Opacity")
        fade = self.add("DepthFade", -400, 300)
        distance = self.add("ScalarParameter", -700, 380, {"parameterName": "S_DepthFadeDistance", "defaultValue": 100.0})
        self.connect(distance, "", fade, "FadeDistance")
        if source:
            self.connect({"refPath": source}, output, fade, "Opacity")
        self.connect_output(fade, "", "MP_Opacity")
        return {"added": ["DepthFade", "S_DepthFadeDistance"], "kept_opacity_source": bool(source)}

    def add_fresnel_layer(self, operation: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        source, output = self.output_source("MP_EmissiveColor")
        fresnel = self.add("Fresnel", -900, -300)
        color = self.add("VectorParameter", -900, -150, {"parameterName": "V_FresnelColor",
                                                         "defaultValue": {"r": 1.0, "g": 0.6, "b": 0.2, "a": 1.0}})
        intensity = self.add("ScalarParameter", -900, -40, {"parameterName": "S_FresnelIntensity", "defaultValue": 1.0})
        tinted = self.add("Multiply", -650, -250)
        self.connect(fresnel, "", tinted, "A")
        self.connect(color, "", tinted, "B")
        rim = self.add("Multiply", -450, -200)
        self.connect(tinted, "", rim, "A")
        self.connect(intensity, "", rim, "B")
        final = rim
        if source:
            final = self.add("Add", -250, -150)
            self.connect({"refPath": source}, output, final, "A")
            self.connect(rim, "", final, "B")
        self.connect_output(final, "", "MP_EmissiveColor")
        return {"added": ["Fresnel", "V_FresnelColor", "S_FresnelIntensity"], "kept_emissive_source": bool(source)}


def execute_refactor(client: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Duplicate, edit the candidate, save both copies on full success; returns the report's ue_apply block."""
    ue = builtin_mcp()
    target = package_path(payload["target_material"])
    candidate, backup = package_path(payload["candidate_path"]), package_path(payload["backup_path"])
    result: dict[str, Any] = {"target": target, "candidate_ref": "", "backup_ref": "", "operations": [], "saved": []}

    def call(toolset: str, tool: str, args: dict[str, Any]) -> Any:
        return ue.unwrap_result(client.call_resolved_tool(toolset, tool, args))

    if client.pie_running():
        result["error"] = "Play-In-Editor is running; stop it before applying a refactor."
        return result
    for path in (candidate, backup):
        if call("AssetTools", "exists", {"path": path}):
            result["error"] = f"{path} already exists; pass another --candidate-path/--backup-path or delete it first."
            return result
    for path, key in ((backup, "backup_ref"), (candidate, "candidate_ref")):
        call("AssetTools", "create_folder", {"path": path.rsplit("/", 1)[0]})
        if not call("AssetTools", "duplicate", {"path": target, "new_path": path}):
            result["error"] = f"duplicate {target} -> {path} failed"
            return result
        result[key] = object_path(path)
    runner = RefactorRunner(client, candidate)
    failed = False
    for operation in payload.get("operations") or []:
        row: dict[str, Any] = {"operation": operation.get("operation"), "success": False, "skipped": False}
        if not operation.get("executable"):
            row.update(skipped=True, reason=operation.get("blocked_reason") or "not executable")
        elif failed:
            row.update(skipped=True, reason="an earlier operation failed")
        else:
            start = len(runner.calls)
            try:
                row.update(getattr(runner, operation["operation"])(operation, payload), success=True)
            except (RefactorError, ue.McpError, KeyError, ValueError) as exc:
                row["error"] = str(exc)
                failed = True
            row["calls"] = runner.calls[start:]
        result["operations"].append(row)
    if not failed:
        try:
            runner.call("MaterialTools", "recompile", {"material_or_function": runner.material})
            if call("AssetTools", "save_assets", {"asset_paths": [backup, candidate]}):
                result["saved"] = [backup, candidate]
        except (RefactorError, ue.McpError) as exc:
            result["error"] = str(exc)
    else:
        result["unsaved_note"] = "The candidate is left unsaved for inspection; the original material was not touched."
    return result
