from __future__ import annotations

import argparse
import hashlib
import re
import textwrap
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


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


def build_ue_script(system_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import re
        import unreal

        PROP = unreal.UnrealBridgePropertyLibrary

        def read_export(path, prop_name):
            text, ok = PROP.get_u_property_as_export_text(path, prop_name)
            return {{"success": bool(ok), "text": text}}

        def parse_renderer_objects(renderer_text):
            objects = []
            for class_path, object_path in re.findall(r"(/Script/[^']+)'([^']+)'", renderer_text or ""):
                material = read_export(object_path, "Material")
                objects.append({{
                    "class_path": class_path,
                    "class_name": class_path.rsplit(".", 1)[-1],
                    "object_path": object_path,
                    "material": material,
                }})
            return objects

        def versioned_renderers(system_path):
            if not hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                return []
            rows = []
            for item in unreal.UnrealBridgeNiagaraLibrary.list_system_renderers(system_path):
                rows.append({{
                    "emitter_name": item.emitter_name,
                    "emitter_path": item.emitter_path,
                    "emitter_version": item.emitter_version,
                    "class_path": item.renderer_class,
                    "class_name": item.renderer_class.rsplit(".", 1)[-1],
                    "object_path": item.renderer_path,
                    "material_path": item.material_path,
                    "source": "versioned-emitter-data",
                }})
            return rows

        def as_list(value):
            try:
                return [item for item in value]
            except Exception:
                return []

        def object_path_from_export(text):
            match = re.search(r"(/Script/[^']+)'([^']+)'", text or "")
            return match.group(2) if match else ""

        def graph_node(item, graph_path):
            node = {{
                "node_class": str(item.node_class),
                "node_name": str(item.node_name),
                "node_path": (str(graph_path) + "." + str(item.node_name)) if graph_path and item.node_name else "",
                "node_title": str(item.node_title),
                "function_name": str(item.function_name),
                "function_script_path": str(item.function_script_path),
                "signature_name": str(item.signature_name),
                "usage": str(item.usage),
                "usage_id": str(item.usage_id),
                "input_pins": [str(pin) for pin in as_list(item.input_pins)],
                "output_pins": [str(pin) for pin in as_list(item.output_pins)],
            }}
            if "DataInterface" in node["signature_name"] and node["node_path"]:
                data_interface = read_export(node["node_path"], "DataInterface")
                node["data_interface"] = data_interface
                data_interface_path = object_path_from_export(data_interface.get("text", ""))
                node["data_interface_path"] = data_interface_path
                if data_interface_path:
                    node["data_interface_emitter_binding"] = read_export(data_interface_path, "EmitterBinding")
            return node

        def graph_event(item):
            return {{
                "emitter_name": str(item.emitter_name),
                "emitter_path": str(item.emitter_path),
                "emitter_version": str(item.emitter_version),
                "script_path": str(item.script_path),
                "usage_id": str(item.usage_id),
                "execution_mode": str(item.execution_mode),
                "spawn_number": int(item.spawn_number),
                "max_events_per_frame": int(item.max_events_per_frame),
                "source_emitter_id": str(item.source_emitter_id),
                "source_event_name": str(item.source_event_name),
                "update_attribute_initial_values": bool(item.update_attribute_initial_values),
                "has_latest_source": bool(item.has_latest_source),
                "latest_source_path": str(item.latest_source_path),
                "event_receiver_count": int(item.event_receiver_count),
                "event_generator_count": int(item.event_generator_count),
            }}

        def versioned_graphs(system_path):
            if not hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                return []
            rows = []
            for item in unreal.UnrealBridgeNiagaraLibrary.list_system_emitter_graphs(system_path):
                graph_path = str(item.graph_path)
                rows.append({{
                    "emitter_name": str(item.emitter_name),
                    "emitter_path": str(item.emitter_path),
                    "emitter_version": str(item.emitter_version),
                    "has_graph_source": bool(item.has_graph_source),
                    "graph_source_path": str(item.graph_source_path),
                    "graph_path": graph_path,
                    "graph_node_count": int(item.graph_node_count),
                    "data_interface_classes": [str(cls) for cls in as_list(item.data_interface_classes)],
                    "function_nodes": [graph_node(node, graph_path) for node in as_list(item.function_nodes)],
                    "output_nodes": [graph_node(node, graph_path) for node in as_list(item.output_nodes)],
                    "input_nodes": [graph_node(node, graph_path) for node in as_list(item.input_nodes)],
                    "event_handlers": [graph_event(event) for event in as_list(item.event_handlers)],
                }})
            return rows

        system_path = {system_path!r}
        system_props = {{name: read_export(system_path, name) for name in {SYSTEM_PROPS!r}}}
        handle_text = system_props["EmitterHandles"]["text"]

        names = re.findall(r'(?<!Id)Name="([^"]+)"', handle_text)
        id_names = re.findall(r'IdName="([^"]*)"', handle_text)
        enabled = re.findall(r'bIsEnabled=(True|False)', handle_text)
        emitter_paths = re.findall(r'Emitter="([^"]+)"', handle_text)
        live_renderers = versioned_renderers(system_path)
        live_graphs = versioned_graphs(system_path)

        emitters = []
        for index, emitter_path in enumerate(emitter_paths):
            props = {{name: read_export(emitter_path, name) for name in {EMITTER_PROPS!r}}}
            renderer_objects = parse_renderer_objects(props["RendererProperties"]["text"])
            name = names[index] if index < len(names) else ""
            normalized_emitter_path = emitter_path
            match = re.search(r"'([^']+)'", normalized_emitter_path)
            if match:
                normalized_emitter_path = match.group(1)
            versioned_for_emitter = [
                item for item in live_renderers
                if item.get("emitter_name") == name or item.get("emitter_path") == normalized_emitter_path
            ]
            graph_for_emitter = next(
                (
                    item for item in live_graphs
                    if item.get("emitter_name") == name or item.get("emitter_path") == normalized_emitter_path
                ),
                None,
            )
            emitters.append({{
                "index": index,
                "name": name,
                "id_name": id_names[index] if index < len(id_names) else "",
                "enabled": enabled[index] if index < len(enabled) else "",
                "emitter_path": emitter_path,
                "properties": props,
                "renderer_objects": renderer_objects,
                "versioned_renderer_objects": versioned_for_emitter,
                "versioned_graph": graph_for_emitter,
            }})

        payload = {{
            "system_path": system_path,
            "system_properties": system_props,
            "versioned_renderers": live_renderers,
            "versioned_graphs": live_graphs,
            "emitters": emitters,
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


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
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.system_path), no_preflight=True)
    report = summarize(raw)
    out_path = Path(args.out) if args.out else default_report_path(ctx, "audits/niagara", slugify(args.system_path), "niagara-audit", ".json")
    save_json(out_path, report)
    if args.markdown:
        write_text(out_path.with_suffix(".md"), render_markdown(report))
    print(out_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Niagara system structure via unreal-bridge property exports.")
    parser.add_argument("system_path")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
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
