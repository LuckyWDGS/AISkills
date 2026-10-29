from __future__ import annotations

import argparse
import hashlib
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from .core import default_report_path, resolve_root_context, save_json, slugify, write_text
from .mcp import DEFAULT_MCP_URL, call_tool, run_tool_script


SYSTEM_PROPS = [
    "EmitterHandles",
    "EffectType",
    "FixedBounds",
    "WarmupTickCount",
    "WarmupTickDelta",
    "SystemScalabilityOverrides",
]
EMITTER_PROPS = [
    "SimTarget",
    "FixedBounds",
    "RendererProperties",
    "RendererBindings",
    "SpawnScriptProps",
    "UpdateScriptProps",
    "EmitterSpawnScriptProps",
    "EmitterUpdateScriptProps",
    "EventHandlerScriptProps",
    "SimulationStages",
    "GraphSource",
    "GPUComputeScript",
]


COVERAGE_GAPS = [
    "Data-interface values (e.g. ParticleRead EmitterBinding) are StackInputData_Unsupported in GetEmitterInputValues; "
    "attribute-reader roles come from module names only, and data_interface_bindings stays empty.",
    "Per-emitter data-interface classes are not exposed; system-wide classes are in system_dependencies.",
]
STANDARD_STACKS = ("emitterSpawnScript", "emitterUpdateScript", "particleSpawnScript", "particleUpdateScript")
STACK_PROPS = {
    "particleSpawnScript": "SpawnScriptProps",
    "particleUpdateScript": "UpdateScriptProps",
    "emitterSpawnScript": "EmitterSpawnScriptProps",
    "emitterUpdateScript": "EmitterUpdateScriptProps",
}


def object_path(asset_path: str) -> str:
    """'/Game/FX/NS_X' -> '/Game/FX/NS_X.NS_X'; full object paths pass through."""
    if re.match(r"^[A-Za-z]:[/\\]", asset_path):
        raise SystemExit(f"{asset_path!r} is a filesystem path; Git Bash rewrote '/Game/...'. Re-run with MSYS_NO_PATHCONV=1.")
    if "." in asset_path.rsplit("/", 1)[-1]:
        return asset_path
    return f"{asset_path}.{asset_path.rsplit('/', 1)[-1]}"


def build_collect_script(system_path: str) -> str:
    """ProgrammaticToolset script; every call in it must succeed or the whole script fails."""
    return textwrap.dedent(
        """
        import json

        SYSTEM = {"refPath": __SYSTEM__}
        N = "NiagaraToolsets.NiagaraToolset_System."
        O = "editor_toolset.toolsets.object.ObjectTools."

        def call(tool, **args):
            # Tool results are strict dicts (no .get default); round-trip to plain JSON types.
            return json.loads(json.dumps(execute_tool(N + tool, json.dumps(args))["returnValue"]))

        def ref(emitter, renderer=-1):
            return {"system": SYSTEM, "emitterName": emitter, "scriptName": "", "moduleName": "",
                    "rendererIndex": renderer, "inputNameStack": []}

        def mesh_materials(data):
            # Mesh renderers without override materials render with each mesh's own slots.
            values = json.loads(data) if isinstance(data, str) and data else {}
            if values.get("bOverrideMaterials") or not values.get("Meshes"):
                return {}
            found = {}
            for entry in values["Meshes"]:
                mesh = entry.get("mesh")
                path = mesh.get("refPath") if isinstance(mesh, dict) else mesh
                if path and path != "None" and path not in found:
                    slots = execute_tool(O + "get_properties", json.dumps({"instance": {"refPath": path}, "properties": ["staticMaterials"]}))["returnValue"]
                    slots = json.loads(slots) if isinstance(slots, str) else json.loads(json.dumps(slots))
                    found[path] = [slot.get("materialInterface") for slot in slots.get("staticMaterials", [])]
            return found

        def run():
            summary = call("GetSystemSummary", system=SYSTEM)
            emitters = []
            for item in summary.get("emitters", []):
                name = item["emitterName"]
                topology = call("GetEmitterTopology", emitterRef=ref(name))
                renderers = []
                for renderer in topology.get("renderers", []):
                    index = renderer["rendererIndex"]
                    data = call("GetRendererData", rendererRef=ref(name, index)).get("propertyValues", "")
                    renderers.append({"index": index, "class": renderer.get("rendererClass"), "data": data,
                                      "mesh_materials": mesh_materials(data)})
                emitters.append({
                    "summary": item,
                    "data": call("GetEmitterData", emitterRef=ref(name)).get("propertyValues", ""),
                    "topology": topology,
                    "renderers": renderers,
                })
            return {
                "summary": summary,
                "system_data": call("GetSystemData", system=SYSTEM).get("propertyValues", ""),
                "dependencies": call("GetSystemDependencies", system=SYSTEM),
                "emitters": emitters,
            }
        """
    ).strip().replace("__SYSTEM__", json.dumps(system_path))


def _json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value or {}


def _ref(value: Any) -> str:
    """Object references arrive as {"refPath": ...}, a bare path string, or None/"None"."""
    if isinstance(value, dict):
        return value.get("refPath") or ""
    return value if isinstance(value, str) and value != "None" else ""


def _prop(text: str) -> dict[str, Any]:
    return {"success": bool(text), "text": text}


def _materials(value: Any, key: str = "") -> list[str]:
    """Asset references found under any *Material* key, ignoring parameter bindings."""
    in_material = "material" in key.lower() and "binding" not in key.lower()
    if isinstance(value, dict):
        found = [_ref(value)] if in_material and _ref(value).startswith("/") else []
        for child_key, child in value.items():
            if child_key != "refPath":
                found += _materials(child, key if in_material else child_key)
        return found
    if isinstance(value, list):
        return [path for child in value for path in _materials(child, key)]
    if in_material and isinstance(value, str) and value.startswith("/"):
        return [value]
    return []


def _stack_modules(stack: Any) -> list[dict[str, Any]]:
    stacks = stack if isinstance(stack, list) else [stack]
    return [module for item in stacks if isinstance(item, dict) for module in item.get("modules", [])]


def to_payload(system_path: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Map MCP results onto the raw payload shape that summarize() and downstream reports expect."""
    system = _json(raw["system_data"])
    handles = raw["summary"].get("emitters", [])
    system_props = {
        "EmitterHandles": _prop(json.dumps(handles, ensure_ascii=False)),
        "EffectType": _prop("" if system.get("EffectType") in (None, "None") else str(system["EffectType"])),
        "FixedBounds": _prop(json.dumps(system["FixedBounds"]) if system.get("bFixedBounds") else ""),
        "WarmupTickCount": _prop(str(system.get("WarmupTickCount", ""))),
        "WarmupTickDelta": _prop(str(system.get("WarmupTickDelta", ""))),
        "SystemScalabilityOverrides": _prop(json.dumps(system.get("SystemScalabilityOverrides", {}))),
    }
    emitters = []
    for index, entry in enumerate(raw["emitters"]):
        summary, topology = entry["summary"], entry["topology"]
        data = _json(entry["data"])
        name = summary["emitterName"]
        extra = {key: value for key, value in topology.items() if key not in STANDARD_STACKS and _stack_modules(value)}
        event_stacks = {key: value for key, value in extra.items() if "event" in key.lower()}
        stage_stacks = {key: value for key, value in extra.items() if key not in event_stacks}
        renderer_rows = []
        for renderer in entry["renderers"]:
            class_path = _ref(renderer["class"])
            renderer_data = _json(renderer["data"])
            materials = sorted(dict.fromkeys(_materials(renderer_data)))
            mesh_materials = renderer.get("mesh_materials") or {}
            if not materials:
                materials = sorted(dict.fromkeys(_ref(item) for slots in mesh_materials.values() for item in slots if _ref(item)))
            renderer_rows.append({
                "emitter_name": name,
                "emitter_path": f"{system_path}:{name}",
                "class_path": class_path,
                "class_name": class_path.rsplit(".", 1)[-1],
                "object_path": f"{system_path}:{name}#renderer{renderer['index']}",
                "material_path": materials[0] if materials else "",
                "material_paths": materials,
                "material_source": "mesh-slots" if mesh_materials and not _materials(renderer_data) else "renderer",
                "mesh_paths": sorted(mesh_materials),
                "source": "mcp-renderer-data",
                "renderer_data": renderer_data,
            })
        modules = [module for key in STANDARD_STACKS for module in _stack_modules(topology.get(key))]
        modules += [module for value in extra.values() for module in _stack_modules(value)]
        properties = {
            "SimTarget": _prop(str(data.get("SimTarget") or summary.get("simTarget") or "")),
            "FixedBounds": _prop(json.dumps(data["FixedBounds"]) if data.get("CalculateBoundsMode") == "Fixed" else ""),
            "RendererProperties": _prop(json.dumps([
                {k: v for k, v in row.items() if k not in ("source", "renderer_data")} for row in renderer_rows
            ]) if renderer_rows else ""),
            "RendererBindings": _prop(""),
            "EventHandlerScriptProps": _prop(json.dumps(event_stacks) if event_stacks else ""),
            "SimulationStages": _prop(json.dumps(stage_stacks) if stage_stacks else ""),
            "GraphSource": _prop(""),
            "GPUComputeScript": _prop(""),
        }
        for key, prop in STACK_PROPS.items():
            names = [module.get("moduleName", "") for module in _stack_modules(topology.get(key))]
            properties[prop] = _prop(json.dumps(names) if names else "")
        emitters.append({
            "index": index,
            "name": name,
            "id_name": str(data.get("IdName", "")),
            "enabled": "True" if summary.get("bEnabled", data.get("bIsEnabled")) else "False",
            "emitter_path": f"{system_path}:{name}",
            "properties": properties,
            "renderer_objects": [],
            "versioned_renderer_objects": renderer_rows,
            "versioned_graph": {
                "emitter_name": name,
                "has_graph_source": bool(modules),
                "graph_node_count": len(modules),
                "data_interface_classes": [],
                "function_nodes": [
                    {"function_name": module.get("moduleName", ""), "function_script_path": _ref(module.get("moduleScript")),
                     "enabled": module.get("enabled", True)}
                    for module in modules
                ],
                "input_nodes": [],
                "output_nodes": [],
                "event_handlers": [
                    {"source_event_name": key, "execution_mode": "unknown", "module_count": len(_stack_modules(value))}
                    for key, value in event_stacks.items()
                ],
            },
        })
    return {
        "system_path": system_path,
        "system_properties": system_props,
        "versioned_renderers": [row for emitter in emitters for row in emitter["versioned_renderer_objects"]],
        "versioned_graphs": [emitter["versioned_graph"] for emitter in emitters],
        "emitters": emitters,
    }


def collect_diagnostics(skill_root: Path, system_path: str, url: str, timeout: float) -> dict[str, Any]:
    """Compile state and stack issues wait for in-flight compilation, so run them separately and bounded."""
    rows: dict[str, Any] = {}
    for tool in ("GetSystemCompileState", "GetStackIssues"):
        try:
            rows[tool] = call_tool(skill_root, "NiagaraToolset_System", tool, {"system": {"refPath": system_path}}, url=url, timeout=timeout)
        except Exception as exc:
            rows[tool] = {"error": str(exc)}
    return rows


def audit(skill_root: Path, system_path: str, *, url: str = DEFAULT_MCP_URL, timeout: float = 180,
          diagnostics: bool = False, diagnostics_timeout: float = 30) -> dict[str, Any]:
    path = object_path(system_path)
    raw = run_tool_script(skill_root, build_collect_script(path), url=url, timeout=timeout)
    report = summarize(to_payload(path, raw))
    report["system_path"] = system_path
    report["system_dependencies"] = {key: [_ref(item) for item in value] for key, value in raw["dependencies"].items()}
    report["user_variables"] = raw["summary"].get("userVariables", [])
    report["transport"] = "epic-mcp ProgrammaticToolset"
    report["coverage_gaps"] = COVERAGE_GAPS
    if diagnostics:
        report["diagnostics"] = collect_diagnostics(skill_root, path, url, diagnostics_timeout)
    return report


def renderer_classes(text: str, renderer_objects: list[dict[str, Any]] | None = None) -> list[str]:
    classes = re.findall(r"Niagara([A-Za-z0-9_]+RendererProperties)", text)
    for item in renderer_objects or []:
        class_name = item.get("class_name", "")
        if class_name.startswith("Niagara"):
            class_name = class_name[len("Niagara") :]
        if class_name:
            classes.append(class_name)
    return sorted(dict.fromkeys(classes))


def material_paths(text: str) -> list[str]:
    return sorted(dict.fromkeys(re.findall(r"/(?:Game|Engine)/[^'\",)]+", text or "")))


def renderer_material_paths(renderer_objects: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for item in renderer_objects:
        material = item.get("material", {})
        if material.get("success"):
            paths.extend(material_paths(material.get("text", "")))
        if item.get("material_path"):
            paths.append(str(item["material_path"]))
    return sorted(dict.fromkeys(paths))


def text_digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def classify_role_traits(emitter: dict[str, Any]) -> dict[str, list[str]]:
    name = emitter["name"].lower()
    renderers = emitter["parsed"]["renderer_classes"]
    has_events = emitter["parsed"]["event_handler_summary"] != "none"
    function_names = " ".join(emitter["parsed"].get("function_names", [])).lower()
    data_interface_classes = " ".join(emitter["parsed"].get("data_interface_classes", [])).lower()
    data_interface_bindings = emitter["parsed"].get("data_interface_bindings", [])
    renderer_text = emitter["properties"]["RendererProperties"]["text"]
    event_text = emitter["properties"]["EventHandlerScriptProps"]["text"]
    module_blob = " ".join(
        emitter["properties"][key]["text"]
        for key in ("SpawnScriptProps", "UpdateScriptProps", "EmitterSpawnScriptProps", "EmitterUpdateScriptProps")
    ).lower()

    roles: list[str] = []
    capabilities: list[str] = []
    if any("Ribbon" in item for item in renderers):
        roles.append("trail-receiver")
        capabilities.append("ribbon-renderer")
    if "ribbon" in renderer_text.lower() or "trail" in renderer_text.lower():
        roles.append("trail-receiver")
        capabilities.append("ribbon-renderer")
    if any("Sprite" in item for item in renderers):
        capabilities.append("sprite-renderer")
    if any("Mesh" in item for item in renderers):
        capabilities.append("mesh-renderer")
    if (
        data_interface_bindings
        or "spawnparticlesfromotheremitter" in function_names
        or "sampleparticlesfromotheremitter" in function_names
        or "particleread" in data_interface_classes
    ):
        roles.append("attribute-reader-receiver")
        capabilities.extend(["attribute-reader", "inter-emitter-data-flow"])
    if "event" in event_text.lower() or has_events:
        roles.append("receiver")
        capabilities.append("event-receiver")
    if any(token in name for token in ("source", "leader", "seed", "driver", "upstream")):
        roles.append("source")
    if any(token in name for token in ("receiver", "trail", "follow", "secondary", "downstream")):
        roles.append("receiver")
    if not roles:
        roles.append("generic")
    return {
        "roles": sorted(dict.fromkeys(roles)),
        "capabilities": sorted(dict.fromkeys(capabilities)),
    }


def classify_role(emitter: dict[str, Any]) -> str:
    roles = classify_role_traits(emitter)["roles"]
    return primary_role_from_roles(roles)


def primary_role_from_roles(roles: list[str]) -> str:
    for preferred in ("trail-receiver", "attribute-reader-receiver", "source", "receiver", "generic"):
        if preferred in roles:
            return preferred
    return roles[0] if roles else "generic"


def emitter_has_role(emitter: dict[str, Any], role: str) -> bool:
    return role == emitter.get("role") or role in (emitter.get("roles") or [])


def parse_event_handlers(text: str) -> str:
    if not text:
        return "none"
    hits = re.findall(r"SourceEmitter(?:Name|ID)?=([^,\)]+)", text)
    if hits:
        return ", ".join(hit.strip('"') for hit in hits)
    return "present"


def graph_event_summary(graph: dict[str, Any] | None) -> str:
    if not graph:
        return "none"
    handlers = graph.get("event_handlers") or []
    if not handlers:
        return "none"
    parts = []
    for handler in handlers:
        source = handler.get("source_event_name") or "unnamed"
        mode = handler.get("execution_mode") or "unknown"
        parts.append(f"{source}:{mode}")
    return ", ".join(parts)


def graph_function_names(graph: dict[str, Any] | None) -> list[str]:
    if not graph:
        return []
    return [node.get("function_name", "") for node in graph.get("function_nodes", []) if node.get("function_name")]


def graph_data_interface_classes(graph: dict[str, Any] | None) -> list[str]:
    if not graph:
        return []
    return sorted(dict.fromkeys(graph.get("data_interface_classes", []) or []))


def graph_data_interface_bindings(graph: dict[str, Any] | None) -> list[dict[str, str]]:
    if not graph:
        return []
    bindings: list[dict[str, str]] = []
    for node in graph.get("input_nodes", []) or []:
        binding = node.get("data_interface_emitter_binding") or {}
        if not binding.get("success"):
            continue
        bindings.append(
            {
                "node_name": node.get("node_name", ""),
                "node_title": node.get("node_title", ""),
                "signature_name": node.get("signature_name", ""),
                "data_interface_path": node.get("data_interface_path", ""),
                "emitter_binding": binding.get("text", ""),
            }
        )
    return bindings


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    emitters: list[dict[str, Any]] = []
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = []
    system_bounds = payload["system_properties"]["FixedBounds"]["text"]
    system_path = str(payload.get("system_path", "") or "")
    system_path_lower = system_path.lower()
    emitter_names = {item.get("name", "") for item in payload["emitters"]}
    attribute_reader_sources: set[str] = set()
    for emitter in payload["emitters"]:
        graph = emitter.get("versioned_graph") or {}
        for binding in graph_data_interface_bindings(graph):
            text = binding.get("emitter_binding", "")
            match = re.search(r'EmitterName="([^"]+)"', text)
            if match:
                attribute_reader_sources.add(match.group(1))
    for emitter in payload["emitters"]:
        renderer_text = emitter["properties"]["RendererProperties"]["text"]
        renderer_objects = emitter.get("renderer_objects", [])
        versioned_renderer_objects = emitter.get("versioned_renderer_objects", [])
        all_renderer_objects = [*renderer_objects, *versioned_renderer_objects]
        event_text = emitter["properties"]["EventHandlerScriptProps"]["text"]
        graph = emitter.get("versioned_graph") or {}
        function_names = graph_function_names(graph)
        data_interface_bindings = graph_data_interface_bindings(graph)
        module_text = " ".join(
            emitter["properties"][key]["text"]
            for key in ("SpawnScriptProps", "UpdateScriptProps", "EmitterSpawnScriptProps", "EmitterUpdateScriptProps", "SimulationStages", "GraphSource", "GPUComputeScript")
        )
        parsed = {
            "renderer_classes": renderer_classes(renderer_text, all_renderer_objects),
            "renderer_materials": renderer_material_paths(all_renderer_objects),
            "renderer_objects": renderer_objects,
            "versioned_renderer_objects": versioned_renderer_objects,
            "event_handler_summary": graph_event_summary(graph) if graph else parse_event_handlers(event_text),
            "has_graph_source": bool(graph.get("has_graph_source")),
            "graph_node_count": graph.get("graph_node_count", 0),
            "function_names": function_names,
            "data_interface_classes": graph_data_interface_classes(graph),
            "data_interface_bindings": data_interface_bindings,
            "sim_target": emitter["properties"]["SimTarget"]["text"],
            "fixed_bounds": emitter["properties"]["FixedBounds"]["text"],
            "renderer_digest": text_digest(renderer_text + repr(versioned_renderer_objects)),
            "module_digest": text_digest(module_text + repr(function_names)),
            "event_digest": text_digest(event_text + repr(graph.get("event_handlers", []))),
        }
        emitter["parsed"] = parsed
        traits = classify_role_traits(emitter)
        if emitter["name"] in attribute_reader_sources:
            traits["roles"].append("source")
            traits["capabilities"].append("attribute-reader-source")
            traits["roles"] = sorted(dict.fromkeys(traits["roles"]))
            traits["capabilities"] = sorted(dict.fromkeys(traits["capabilities"]))
        emitter["roles"] = traits["roles"]
        emitter["capabilities"] = traits["capabilities"]
        emitter["role"] = primary_role_from_roles(emitter["roles"])
        emitters.append(emitter)
        evidence.append(
            {
                "name": emitter["name"],
                "role": emitter["role"],
                "roles": emitter["roles"],
                "capabilities": emitter["capabilities"],
                "renderer_digest": parsed["renderer_digest"],
                "module_digest": parsed["module_digest"],
                "event_digest": parsed["event_digest"],
                "has_renderer_text": bool(renderer_text.strip()),
                "has_versioned_renderers": bool(versioned_renderer_objects),
                "has_module_text": bool(module_text.strip()),
                "has_graph_source": parsed["has_graph_source"],
                "graph_node_count": parsed["graph_node_count"],
                "function_names": function_names,
                "data_interface_bindings": data_interface_bindings,
                "has_event_text": bool(event_text.strip()),
            }
        )
        if emitter["enabled"] == "False":
            warnings.append(f"Emitter `{emitter['name']}` is disabled.")
        if (emitter_has_role(emitter, "trail-receiver") or emitter_has_role(emitter, "receiver")) and not parsed["renderer_classes"]:
            warnings.append(f"Emitter `{emitter['name']}` looks like a receiver but has no renderer.")
        if emitter_has_role(emitter, "trail-receiver") and not parsed["renderer_materials"]:
            warnings.append(f"Ribbon/trail emitter `{emitter['name']}` has no bound material in live renderer data.")
        if emitter_has_role(emitter, "attribute-reader-receiver") and parsed["renderer_classes"] == ["SpriteRendererProperties"] and not parsed["renderer_materials"]:
            warnings.append(
                f"Emitter `{emitter['name']}` is an attribute-reader receiver but still only has SpriteRendererProperties with no material; this usually means an intermediate receiver/test route was left incomplete."
            )
        if any(token in system_path_lower for token in ("ribbon", "trail")) and (
            emitter_has_role(emitter, "attribute-reader-receiver") or emitter_has_role(emitter, "receiver")
        ):
            if not any("Ribbon" in item for item in parsed["renderer_classes"]):
                warnings.append(
                    f"System `{system_path}` is named like a ribbon/trail asset, but receiver emitter `{emitter['name']}` has no Ribbon renderer in the live route."
                )
        for binding in data_interface_bindings:
            text = binding.get("emitter_binding", "")
            match = re.search(r'EmitterName="([^"]+)"', text)
            if match and match.group(1) not in emitter_names:
                warnings.append(
                    f"Emitter `{emitter['name']}` has data interface `{binding.get('node_title')}` bound to missing emitter `{match.group(1)}`."
                )
    if not system_bounds and any(emitter_has_role(entry, "trail-receiver") for entry in emitters):
        warnings.append("System has ribbon/trail emitters but no FixedBounds export text.")
    if "/game/vfx/" in system_path_lower and any(token in system_path_lower for token in ("codex", "test", "temp")):
        warnings.append(
            f"System `{system_path}` looks like a temporary/test asset but lives under a production VFX folder; quarantine or remove it after readback instead of leaving it as a candidate implementation asset."
        )
    return {
        "tool": "niagara_audit",
        "system_path": payload["system_path"],
        "system_properties": payload["system_properties"],
        "emitters": emitters,
        "evidence": evidence,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Niagara Audit: {report['system_path']}",
        "",
        f"- EffectType: `{report['system_properties']['EffectType']['text'] or 'unset'}`",
        f"- FixedBounds: `{report['system_properties']['FixedBounds']['text'] or 'unset'}`",
        f"- WarmupTickCount: `{report['system_properties']['WarmupTickCount']['text'] or '0'}`",
        "",
        "## Emitters",
        "",
    ]
    for emitter in report["emitters"]:
        graph_note = "graph=no"
        if emitter["parsed"].get("has_graph_source"):
            graph_note = f"graph={emitter['parsed'].get('graph_node_count', 0)} nodes"
        di_note = ""
        if emitter["parsed"].get("data_interface_bindings"):
            di_bits = [
                f"{item.get('node_title') or item.get('signature_name')} {item.get('emitter_binding')}"
                for item in emitter["parsed"]["data_interface_bindings"]
            ]
            di_note = f" data-flow=`{'; '.join(di_bits)}`"
        lines.extend(
            [
                f"- `{emitter['name']}` role=`{emitter['role']}` roles=`{', '.join(emitter.get('roles', [])) or emitter['role']}` capabilities=`{', '.join(emitter.get('capabilities', [])) or 'none'}` sim=`{emitter['parsed']['sim_target'] or 'unknown'}` {graph_note} renderers=`{', '.join(emitter['parsed']['renderer_classes']) or 'none'}` materials=`{', '.join(emitter['parsed']['renderer_materials']) or 'none'}` events=`{emitter['parsed']['event_handler_summary']}`{di_note}",
            ]
        )
        key_functions = [
            name for name in emitter["parsed"].get("function_names", [])
            if any(token in name.lower() for token in ("spawnparticlesfromotheremitter", "sampleparticlesfromotheremitter", "ribbon", "initialize", "scale"))
        ]
        if key_functions:
            lines.append(f"  Key functions: `{', '.join(key_functions[:12])}`")
    lines.extend(["", "## Evidence", ""])
    for item in report["evidence"]:
        lines.append(
            f"- `{item['name']}` renderer={item['renderer_digest']} module={item['module_digest']} event={item['event_digest']} role={item['role']} roles={', '.join(item.get('roles', [])) or item['role']} capabilities={', '.join(item.get('capabilities', [])) or 'none'} graph_nodes={item.get('graph_node_count', 0)}"
        )
    lines.extend(["", "## Warnings", ""])
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- No structural warnings from the first-pass audit.")
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    report = audit(
        ctx.skill_root, args.system_path,
        url=getattr(args, "mcp_url", None) or DEFAULT_MCP_URL,
        timeout=getattr(args, "timeout", 180),
        diagnostics=getattr(args, "diagnostics", False),
        diagnostics_timeout=getattr(args, "diagnostics_timeout", 30),
    )
    out_path = Path(args.out) if args.out else default_report_path(ctx, "audits/niagara", slugify(args.system_path), "niagara-audit", ".json")
    save_json(out_path, report)
    if args.markdown:
        write_text(out_path.with_suffix(".md"), render_markdown(report))
    print(out_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Niagara system structure through Epic's built-in MCP.")
    parser.add_argument("system_path")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--diagnostics", action="store_true", help="Also read compile state and stack issues (each waits for compilation)")
    parser.add_argument("--diagnostics-timeout", type=float, default=30)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
