from __future__ import annotations

import re
import textwrap
from typing import Any


SYSTEM_PROPS = [
    "EmitterHandles",
    "FixedBounds",
    "WarmupTickCount",
    "WarmupTickDelta",
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
                renderer_props = None
                try:
                    renderer_props = unreal.load_object(None, item.renderer_path)
                except Exception:
                    renderer_props = None
                probe = {{}}
                probe_names = [
                    "color_binding",
                    "dynamic_material_binding",
                    "sub_image_index_binding",
                    "sub_image_size",
                    "position_binding",
                    "velocity_binding",
                    "normalized_age_binding",
                ]
                export_names = [
                    "ColorBinding",
                    "DynamicMaterialBinding",
                    "SubImageIndexBinding",
                    "SubImageSize",
                    "PositionBinding",
                    "VelocityBinding",
                    "NormalizedAgeBinding",
                    "RibbonIDBinding",
                    "RibbonWidthBinding",
                    "Material",
                    "MaterialParameters",
                ]
                if renderer_props is not None:
                    for name in probe_names:
                        try:
                            probe[name] = str(renderer_props.get_editor_property(name))
                        except Exception:
                            pass
                binding_exports = {{}}
                for name in export_names:
                    text, ok = read_export(item.renderer_path, name)
                    if ok:
                        binding_exports[name] = text
                rows.append({{
                    "emitter_name": item.emitter_name,
                    "emitter_path": item.emitter_path,
                    "emitter_version": item.emitter_version,
                    "class_path": item.renderer_class,
                    "class_name": item.renderer_class.rsplit(".", 1)[-1],
                    "object_path": item.renderer_path,
                    "material_path": item.material_path,
                    "probe_bindings": probe,
                    "binding_exports": binding_exports,
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
                "node_name": str(item.node_name),
                "node_title": str(item.node_title),
                "function_name": str(item.function_name),
                "signature_name": str(item.signature_name),
            }}
            if "DataInterface" in node["signature_name"]:
                node["data_interface_path"] = ""
            return node

        def graph_event(item):
            return {{
                "source_event_name": str(item.source_event_name),
                "execution_mode": str(item.execution_mode),
            }}

        def versioned_graphs(system_path):
            if not hasattr(unreal, "UnrealBridgeNiagaraLibrary"):
                return []
            rows = []
            for item in unreal.UnrealBridgeNiagaraLibrary.list_system_emitter_graphs(system_path):
                rows.append({{
                    "emitter_name": str(item.emitter_name),
                    "emitter_path": str(item.emitter_path),
                    "graph_node_count": int(item.graph_node_count),
                    "data_interface_classes": [str(cls) for cls in as_list(item.data_interface_classes)],
                    "function_nodes": [graph_node(node, str(item.graph_path)) for node in as_list(item.function_nodes)],
                    "input_nodes": [graph_node(node, str(item.graph_path)) for node in as_list(item.input_nodes)],
                    "event_handlers": [graph_event(event) for event in as_list(item.event_handlers)],
                }})
            return rows

        system_path = {system_path!r}
        system_props = {{name: read_export(system_path, name) for name in {SYSTEM_PROPS!r}}}
        handle_text = system_props["EmitterHandles"]["text"]
        names = re.findall(r'(?<!Id)Name="([^"]+)"', handle_text)
        emitter_paths = re.findall(r'Emitter="([^"]+)"', handle_text)
        live_renderers = versioned_renderers(system_path)
        live_graphs = versioned_graphs(system_path)
        emitters = []
        for index, emitter_path in enumerate(emitter_paths):
            props = {{name: read_export(emitter_path, name) for name in {EMITTER_PROPS!r}}}
            renderer_objects = parse_renderer_objects(props["RendererProperties"]["text"])
            name = names[index] if index < len(names) else ""
            normalized = emitter_path
            match = re.search(r"'([^']+)'", normalized)
            if match:
                normalized = match.group(1)
            versioned_for_emitter = [
                item for item in live_renderers
                if item.get("emitter_name") == name or item.get("emitter_path") == normalized
            ]
            graph_for_emitter = next(
                (
                    item for item in live_graphs
                    if item.get("emitter_name") == name or item.get("emitter_path") == normalized
                ),
                None,
            )
            emitters.append({{
                "name": name,
                "emitter_path": emitter_path,
                "renderer_objects": renderer_objects,
                "versioned_renderer_objects": versioned_for_emitter,
                "versioned_graph": graph_for_emitter,
                "properties": props,
            }})
        print(json.dumps({{
            "system_path": system_path,
            "system_properties": system_props,
            "emitters": emitters,
        }}, ensure_ascii=False))
        """
    ).strip()


def renderer_classes(emitter: dict[str, Any]) -> list[str]:
    classes = []
    for item in emitter.get("versioned_renderer_objects") or []:
        class_name = item.get("class_name", "")
        if class_name.startswith("Niagara"):
            class_name = class_name[len("Niagara") :]
        classes.append(class_name)
    return sorted(dict.fromkeys(classes))


def renderer_materials(emitter: dict[str, Any]) -> list[str]:
    paths = []
    for item in emitter.get("versioned_renderer_objects") or []:
        if item.get("material_path"):
            paths.append(str(item["material_path"]))
    return sorted(dict.fromkeys(paths))


def renderer_binding_probe(emitter: dict[str, Any]) -> list[dict[str, str]]:
    return [item.get("probe_bindings", {}) for item in emitter.get("versioned_renderer_objects") or []]


def renderer_binding_exports(emitter: dict[str, Any]) -> list[dict[str, str]]:
    return [item.get("binding_exports", {}) for item in emitter.get("versioned_renderer_objects") or []]


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    emitters = []
    for emitter in payload.get("emitters") or []:
        graph = emitter.get("versioned_graph") or {}
        emitters.append(
            {
                "name": emitter.get("name"),
                "emitter_path": emitter.get("emitter_path"),
                "renderer_classes": renderer_classes(emitter),
                "renderer_materials": renderer_materials(emitter),
                "renderer_binding_probe": renderer_binding_probe(emitter),
                "renderer_binding_exports": renderer_binding_exports(emitter),
                "function_names": [str(node.get("function_name") or "") for node in graph.get("function_nodes") or [] if node.get("function_name")],
                "input_titles": [str(node.get("node_title") or "") for node in graph.get("input_nodes") or [] if node.get("node_title")],
                "input_signatures": [str(node.get("signature_name") or "") for node in graph.get("input_nodes") or [] if node.get("signature_name")],
                "data_interface_classes": [str(item) for item in graph.get("data_interface_classes") or []],
                "event_handlers": graph.get("event_handlers") or [],
                "graph_node_count": graph.get("graph_node_count", 0),
            }
        )
    return {
        "tool": "niagara_contract_audit",
        "system_path": payload.get("system_path"),
        "emitters": emitters,
    }
