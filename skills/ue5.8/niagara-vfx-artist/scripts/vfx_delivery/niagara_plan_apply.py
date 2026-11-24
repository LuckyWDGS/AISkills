"""Apply a niagara_asset_assistant mutation plan through Epic MCP.

The plan decides *what* changes; this module maps each operation onto NiagaraToolset_System,
AssetTools and MaterialInstanceTools calls, runs them in order, reads every write back, and
saves only when every operation succeeded. A dry run (the default) needs no editor: it checks
that every operation has an MCP route and lists the calls it will make.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from .mcp import builtin_mcp


SCHEMA_VERSION = "niagara_plan_apply/1"
N = "NiagaraToolset_System"
RIBBON_CLASS = "/Script/Niagara.NiagaraRibbonRendererProperties"

# Operations with an MCP route; read-only ops return their result as evidence.
APPLY_OPS = {
    "duplicate_asset", "create_material_instance", "set_mi_params", "set_niagara_system_props",
    "add_emitter_to_system_from_asset", "set_emitter_enabled_in_system", "add_ribbon_renderer",
    "patch_renderer_material", "toolset_get_system_compile_state", "toolset_get_stack_issues", "save_assets",
}
REFUSED_OPS = {
    "remove_emitter_from_system": "delete operations are not allowed in mutation plans",
    "toolset_remove_module": "delete operations are not allowed in mutation plans",
    "set_u_property_export": "raw UPROPERTY export-text writes have no MCP route; use the structured set_* operations",
}


# In these operations `enabled` is the value to write, not the plan's skip flag.
SEMANTIC_ENABLED_OPS = {"set_emitter_enabled_in_system", "toolset_set_module_enabled"}


def op_disabled(op: dict[str, Any]) -> bool:
    return op.get("op") not in SEMANTIC_ENABLED_OPS and op.get("enabled") is False


class ApplyError(RuntimeError):
    pass


def object_path(path: str) -> str:
    clean = str(path or "").strip()
    last = clean.rsplit("/", 1)[-1]
    return clean if not clean or "." in last else f"{clean}.{last}"


def package_path(path: str) -> str:
    return object_path(path).split(".", 1)[0]


def same_ref(expected: str, actual: Any) -> bool:
    """UE normalizes casing in returned references (DefaultRibbonMaterial -> DefaultRIbbonMaterial)."""
    value = actual.get("refPath") if isinstance(actual, dict) else actual
    return str(value or "").lower() == object_path(expected).lower()


def parse_bounds(text: str) -> dict[str, Any]:
    values = [float(item) for item in str(text).replace(" ", "").split(",") if item]
    if len(values) != 6:
        raise ApplyError(f"fixed_bounds must be minX,minY,minZ,maxX,maxY,maxZ: {text}")
    return {"min": dict(zip("xyz", values[:3])), "max": dict(zip("xyz", values[3:]))}


def parse_color(text: str) -> dict[str, float]:
    values = [float(item) for item in str(text).split(",")]
    if len(values) not in (3, 4):
        raise ApplyError(f"vector parameter value must be r,g,b[,a]: {text}")
    return dict(zip("rgba", [*values, 1.0][:4]))


def emitter_name_of(op: dict[str, Any]) -> str:
    name = str(op.get("emitter_name") or "")
    if not name and op.get("emitter_path"):
        name = str(op["emitter_path"]).rsplit(":", 1)[-1]
    return name


def plan_problems(plan: dict[str, Any]) -> list[str]:
    problems = []
    for index, op in enumerate(plan.get("operations") or [], start=1):
        kind = str(op.get("op") or "")
        if op_disabled(op):
            continue
        if kind in REFUSED_OPS:
            problems.append(f"operation {index} `{kind}`: {REFUSED_OPS[kind]}")
        elif kind not in APPLY_OPS:
            problems.append(f"operation {index} `{kind}` has no MCP executor route")
    return problems


class PlanRunner:
    def __init__(self, client: Any, system_path: str) -> None:
        self.client = client
        self.ue = builtin_mcp()
        self.system_path = system_path
        self.calls: list[dict[str, Any]] = []

    # -- MCP plumbing ----------------------------------------------------------------------------
    def call(self, toolset: str, tool: str, args: dict[str, Any]) -> Any:
        row: dict[str, Any] = {"tool": f"{toolset}.{tool}", "args": args}
        self.calls.append(row)
        try:
            row["result"] = self.ue.unwrap_result(self.client.call_resolved_tool(toolset, tool, args))
        except self.ue.McpError as exc:
            row["error"] = str(exc)
            raise ApplyError(f"{toolset}.{tool} failed: {exc}") from exc
        return row["result"]

    def system_ref(self, path: str = "") -> dict[str, str]:
        return {"refPath": object_path(path or self.system_path)}

    def stack_ref(self, emitter: str, renderer: int = -1, system: str = "") -> dict[str, Any]:
        return {"system": self.system_ref(system), "emitterName": emitter, "scriptName": "", "moduleName": "",
                "rendererIndex": renderer, "inputNameStack": []}

    def property_values(self, tool: str, ref_key: str, ref: Any) -> dict[str, Any]:
        payload = self.call(N, tool, {ref_key: ref}) or {}
        text = payload.get("propertyValues") if isinstance(payload, dict) else ""
        return json.loads(text) if text else {}

    def emitters(self, system: str = "") -> list[str]:
        summary = self.call(N, "GetSystemSummary", {"system": self.system_ref(system)}) or {}
        return [item["emitterName"] for item in summary.get("emitters", [])]

    def exists(self, path: str) -> bool:
        return bool(self.call("AssetTools", "exists", {"path": package_path(path)}))

    # -- operations ------------------------------------------------------------------------------
    def duplicate_asset(self, op: dict[str, Any]) -> dict[str, Any]:
        source, target = package_path(op["source"]), package_path(op["target"])
        if self.exists(target):
            if not op.get("reuse_if_exists"):
                raise ApplyError(f"{target} already exists; set reuse_if_exists or pick another target")
            return {"status": "reused", "target": target}
        self.call("AssetTools", "create_folder", {"path": target.rsplit("/", 1)[0]})
        if not self.call("AssetTools", "duplicate", {"path": source, "new_path": target}) or not self.exists(target):
            raise ApplyError(f"duplicate {source} -> {target} did not create the asset")
        return {"status": "ok", "target": target}

    def create_material_instance(self, op: dict[str, Any]) -> dict[str, Any]:
        target = package_path(op["target"])
        status = "ok"
        if self.exists(target):
            if not op.get("reuse_if_exists"):
                raise ApplyError(f"{target} already exists")
            status = "reused"
        else:
            folder, name = target.rsplit("/", 1)
            self.call("MaterialInstanceTools", "create", {"folder_path": folder, "asset_name": name,
                                                          "parent": {"refPath": object_path(op["parent"])}})
            if not self.exists(target):
                raise ApplyError(f"MaterialInstanceTools.create did not create {target}")
        params = self.set_mi_params({"material_instance": target, "params": op.get("params") or []})
        return {"status": status, "target": target, "params": params.get("params", [])}

    def set_mi_params(self, op: dict[str, Any]) -> dict[str, Any]:
        instance = {"refPath": object_path(op["material_instance"])}
        written = []
        for param in op.get("params") or []:
            kind, name, value = str(param.get("type", "")).lower(), param["name"], param.get("value")
            if kind == "scalar":
                self.call("MaterialInstanceTools", "set_scalar_parameter", {"instance": instance, "name": name, "value": float(value)})
                actual = self.call("MaterialInstanceTools", "get_scalar_parameter", {"instance": instance, "name": name})
                ok = abs(float(actual) - float(value)) < 1e-4
            elif kind == "vector":
                color = parse_color(value)
                self.call("MaterialInstanceTools", "set_vector_parameter", {"instance": instance, "name": name, "value": color})
                actual = self.call("MaterialInstanceTools", "get_vector_parameter", {"instance": instance, "name": name}) or {}
                ok = all(abs(float(actual.get(key, 0)) - color[key]) < 1e-4 for key in color)
            elif kind == "texture":
                self.call("MaterialInstanceTools", "set_texture_parameter", {"instance": instance, "name": name, "value": {"refPath": object_path(value)}})
                actual = self.call("MaterialInstanceTools", "get_texture_parameter", {"instance": instance, "name": name})
                ok = same_ref(value, actual)
            elif kind in ("switch", "staticswitch", "static_switch", "bool"):
                flag = str(value).lower() in ("1", "true", "yes", "on")
                self.call("MaterialInstanceTools", "set_static_switch_parameter", {"instance": instance, "name": name, "value": flag})
                actual = self.call("MaterialInstanceTools", "get_static_switch_parameter", {"instance": instance, "name": name})
                ok = bool(actual) == flag
            else:
                raise ApplyError(f"unsupported MI parameter type `{param.get('type')}` for {name}")
            if not ok:
                raise ApplyError(f"MI parameter {name} read back {actual!r}, expected {value!r}")
            written.append(name)
        return {"status": "ok", "params": written}

    def set_niagara_system_props(self, op: dict[str, Any]) -> dict[str, Any]:
        system = op.get("system_path") or self.system_path
        values: dict[str, Any] = {}
        if op.get("fixed_bounds"):
            values.update(bFixedBounds=True, FixedBounds=parse_bounds(op["fixed_bounds"]))
        if op.get("warmup_tick_count") is not None:
            values["WarmupTickCount"] = int(op["warmup_tick_count"])
        if op.get("warmup_tick_delta") is not None:
            values["WarmupTickDelta"] = float(op["warmup_tick_delta"])
        if op.get("effect_type_path"):
            values["EffectType"] = object_path(op["effect_type_path"])
        if not values:
            return {"status": "noop"}
        self.call(N, "SetSystemData", {"system": self.system_ref(system), "systemData": {"propertyValues": json.dumps(values)}})
        actual = self.property_values("GetSystemData", "system", self.system_ref(system))
        for key, expected in values.items():
            got = actual.get(key)
            if key == "FixedBounds":
                ok = all(abs(float(got[side][axis]) - expected[side][axis]) < 1e-3 for side in ("min", "max") for axis in "xyz")
            elif key == "EffectType":
                ok = same_ref(expected, got)
            elif isinstance(expected, float):
                ok = abs(float(got) - expected) < 1e-4
            else:
                ok = got == expected
            if not ok:
                raise ApplyError(f"system {key} read back {got!r}, expected {expected!r}")
        return {"status": "ok", "set": sorted(values)}

    def add_emitter_to_system_from_asset(self, op: dict[str, Any]) -> dict[str, Any]:
        system = op.get("system_path") or self.system_path
        name = str(op.get("new_emitter_name") or "")
        before = self.emitters(system)
        if name and name in before:
            if op.get("reuse_if_exists"):
                return {"status": "reused", "emitter": name}
            raise ApplyError(f"emitter {name} already exists in {system}")
        self.call(N, "AddEmitter", {"system": self.system_ref(system), "templateEmitter": {"refPath": object_path(op["emitter_asset_path"])},
                                    "emitterName": name})
        added = [item for item in self.emitters(system) if item not in before]
        if not added:
            raise ApplyError(f"AddEmitter left {system} without a new emitter")
        return {"status": "ok", "emitter": added[0]}

    def set_emitter_enabled_in_system(self, op: dict[str, Any]) -> dict[str, Any]:
        system = op.get("system_path") or self.system_path
        name, enabled = emitter_name_of(op), bool(op.get("enabled", True))
        ref = self.stack_ref(name, system=system)
        self.call(N, "SetEmitterData", {"emitter": ref, "emitterData": {"propertyValues": json.dumps({"bIsEnabled": enabled})}})
        if bool(self.property_values("GetEmitterData", "emitterRef", ref).get("bIsEnabled")) != enabled:
            raise ApplyError(f"emitter {name} did not read back enabled={enabled}")
        return {"status": "ok", "emitter": name, "enabled": enabled}

    def set_renderer_values(self, ref: dict[str, Any], values: dict[str, Any]) -> None:
        self.call(N, "SetRendererData", {"renderer": ref, "rendererData": {"propertyValues": json.dumps(values)}})
        actual = self.property_values("GetRendererData", "rendererRef", ref)
        for key, expected in values.items():
            got = actual.get(key)
            ok = same_ref(expected, got) if key == "Material" else (
                abs(float(got) - expected) < 1e-4 if isinstance(expected, float) else got == expected)
            if not ok:
                raise ApplyError(f"renderer {ref['emitterName']}#{ref['rendererIndex']} {key} read back {got!r}, expected {expected!r}")

    def add_ribbon_renderer(self, op: dict[str, Any]) -> dict[str, Any]:
        system = op.get("system_path") or self.system_path
        name = emitter_name_of(op)
        if name not in self.emitters(system):
            raise ApplyError(f"emitter {name} is not in {system}")
        added = self.call(N, "AddRenderer", {"newRendererLocation": self.stack_ref(name, system=system), "rendererClass": RIBBON_CLASS})
        index = int((added or {}).get("rendererIndex", -1))
        if index < 0:
            raise ApplyError(f"AddRenderer returned no renderer index for {name}")
        values: dict[str, Any] = {"Material": object_path(op["material_path"])}
        if op.get("facing_mode"):
            values["FacingMode"] = str(op["facing_mode"])
        if str(op.get("max_num_ribbons", "")).strip():
            values["MaxNumRibbons"] = int(op["max_num_ribbons"])
        if str(op.get("width_segmentation_count", "")).strip():
            values["WidthSegmentationCount"] = int(op["width_segmentation_count"])
        if str(op.get("curve_tension", "")).strip():
            values["CurveTension"] = float(op["curve_tension"])
        self.set_renderer_values(self.stack_ref(name, index, system), values)
        return {"status": "ok", "emitter": name, "renderer_index": index}

    def matching_renderers(self, op: dict[str, Any], system: str) -> list[tuple[str, int, str]]:
        tokens = [str(item).lower() for item in op.get("emitter_name_contains") or [] if str(item)]
        explicit = emitter_name_of(op)
        classes = [str(item).lower().removeprefix("niagara") for item in op.get("renderer_class_contains") or [] if str(item)]
        matches = []
        for emitter in self.emitters(system):
            if explicit and emitter != explicit:
                continue
            if tokens and not any(token in emitter.lower() for token in tokens):
                continue
            topology = self.call(N, "GetEmitterTopology", {"emitterRef": self.stack_ref(emitter, system=system)}) or {}
            for renderer in topology.get("renderers", []):
                index = int(renderer["rendererIndex"])
                if op.get("renderer_index") is not None and index != int(op["renderer_index"]):
                    continue
                cls = renderer.get("rendererClass")
                cls = str(cls.get("refPath") if isinstance(cls, dict) else cls or "")
                if classes and not any(token in cls.lower() for token in classes):
                    continue
                matches.append((emitter, index, cls))
        return matches

    def patch_renderer_material(self, op: dict[str, Any]) -> dict[str, Any]:
        system = op.get("system_path") or self.system_path
        matches = self.matching_renderers(op, system)
        if not matches:
            if op.get("allow_noop"):
                return {"status": "noop", "reason": "no matching renderer"}
            raise ApplyError("no renderer matches " + json.dumps({key: op.get(key) for key in (
                "emitter_name", "emitter_path", "emitter_name_contains", "renderer_class_contains", "renderer_index")}))
        if len(matches) > 1 and not op.get("replace_all"):
            matches = matches[:1]
        for emitter, index, _ in matches:
            self.set_renderer_values(self.stack_ref(emitter, index, system), {"Material": object_path(op["material_path"])})
        return {"status": "ok", "patched": [f"{emitter}#{index}" for emitter, index, _ in matches]}

    def toolset_get_system_compile_state(self, op: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "result": self.call(N, "GetSystemCompileState", {"system": self.system_ref(op.get("system_path", ""))})}

    def toolset_get_stack_issues(self, op: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "result": self.call(N, "GetStackIssues", {"system": self.system_ref(op.get("system_path", ""))})}

    def save_assets(self, op: dict[str, Any]) -> dict[str, Any]:
        paths = [package_path(item) for item in op.get("asset_paths") or [self.system_path]]
        if not self.call("AssetTools", "save_assets", {"asset_paths": paths}):
            raise ApplyError(f"save_assets reported failure for {paths}")
        return {"status": "ok", "saved": paths}


def dry_run_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    routes = {
        "duplicate_asset": "AssetTools.exists / create_folder / duplicate",
        "create_material_instance": "MaterialInstanceTools.create + set_*_parameter with get_* readback",
        "set_mi_params": "MaterialInstanceTools.set_*_parameter with get_* readback",
        "set_niagara_system_props": "NiagaraToolset_System.SetSystemData + GetSystemData readback",
        "add_emitter_to_system_from_asset": "NiagaraToolset_System.AddEmitter + GetSystemSummary readback",
        "set_emitter_enabled_in_system": "NiagaraToolset_System.SetEmitterData + GetEmitterData readback",
        "add_ribbon_renderer": "NiagaraToolset_System.AddRenderer + SetRendererData + GetRendererData readback",
        "patch_renderer_material": "GetEmitterTopology to match renderers, SetRendererData + GetRendererData readback",
        "toolset_get_system_compile_state": "NiagaraToolset_System.GetSystemCompileState",
        "toolset_get_stack_issues": "NiagaraToolset_System.GetStackIssues",
        "save_assets": "AssetTools.save_assets (only when every earlier operation succeeded)",
    }
    return [{"index": index, "op": op.get("op"), "status": "disabled" if op_disabled(op) else "planned",
             "route": routes.get(str(op.get("op")), "")}
            for index, op in enumerate(plan.get("operations") or [], start=1)]


def apply_plan(plan: dict[str, Any], *, execute: bool, connect: Callable[[], Any] | None = None,
               allow_pie: bool = False) -> dict[str, Any]:
    problems = plan_problems(plan)
    report: dict[str, Any] = {
        "tool": "niagara_plan_apply",
        "schema_version": SCHEMA_VERSION,
        "effect_name": plan.get("effect_name", ""),
        "target_system": plan.get("target_system", ""),
        "execute": execute,
        "problems": problems,
        "operations": dry_run_rows(plan),
        "saved": [],
    }
    if problems or not execute:
        report["status"] = "refused" if problems else "planned"
        return report
    if connect is None:
        raise ValueError("connect is required to execute a plan")
    client = connect()
    try:
        if not allow_pie and client.pie_running():
            report.update(status="refused", problems=["Play-In-Editor is running; stop it before applying a plan."])
            return report
        runner = PlanRunner(client, plan.get("target_system", ""))
        failed = False
        for row, op in zip(report["operations"], plan.get("operations") or []):
            if row["status"] == "disabled":
                continue
            if failed:
                row["status"] = "skipped"
                continue
            if op["op"] == "save_assets" and any(item["status"] in ("error", "skipped") for item in report["operations"]):
                row["status"] = "skipped"
                continue
            start = len(runner.calls)
            try:
                row.update(getattr(runner, op["op"])(op))
            except (ApplyError, KeyError, ValueError, TypeError) as exc:
                row.update(status="error", error=str(exc))
                failed = True
            row["calls"] = runner.calls[start:]
            if op["op"] == "save_assets" and row["status"] == "ok":
                report["saved"] = row.get("saved", [])
        report["status"] = "failed" if failed else "applied"
        if failed:
            report["unsaved_note"] = "Nothing was saved; inspect the edited assets in the editor, then fix the plan or revert."
        return report
    finally:
        client.close()
