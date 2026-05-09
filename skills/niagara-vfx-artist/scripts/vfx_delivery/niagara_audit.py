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

        system_path = {system_path!r}
        system_props = {{name: read_export(system_path, name) for name in {SYSTEM_PROPS!r}}}
        handle_text = system_props["EmitterHandles"]["text"]

        names = re.findall(r'(?<!Id)Name="([^"]+)"', handle_text)
        id_names = re.findall(r'IdName="([^"]*)"', handle_text)
        enabled = re.findall(r'bIsEnabled=(True|False)', handle_text)
        emitter_paths = re.findall(r'Emitter="([^"]+)"', handle_text)

        emitters = []
        for index, emitter_path in enumerate(emitter_paths):
            props = {{name: read_export(emitter_path, name) for name in {EMITTER_PROPS!r}}}
            emitters.append({{
                "index": index,
                "name": names[index] if index < len(names) else "",
                "id_name": id_names[index] if index < len(id_names) else "",
                "enabled": enabled[index] if index < len(enabled) else "",
                "emitter_path": emitter_path,
                "properties": props,
            }})

        payload = {{
            "system_path": system_path,
            "system_properties": system_props,
            "emitters": emitters,
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


def renderer_classes(text: str) -> list[str]:
    classes = re.findall(r"Niagara([A-Za-z0-9_]+RendererProperties)", text)
    return sorted(dict.fromkeys(classes))


def material_paths(text: str) -> list[str]:
    return sorted(dict.fromkeys(re.findall(r"/(?:Game|Engine)[^'\",)]+", text)))


def text_digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def classify_role(emitter: dict[str, Any]) -> str:
    name = emitter["name"].lower()
    renderers = emitter["parsed"]["renderer_classes"]
    has_events = emitter["parsed"]["event_handler_summary"] != "none"
    renderer_text = emitter["properties"]["RendererProperties"]["text"]
    event_text = emitter["properties"]["EventHandlerScriptProps"]["text"]
    module_blob = " ".join(
        emitter["properties"][key]["text"]
        for key in ("SpawnScriptProps", "UpdateScriptProps", "EmitterSpawnScriptProps", "EmitterUpdateScriptProps")
    )

    if any("Ribbon" in item for item in renderers):
        return "trail-receiver"
    if "ribbon" in renderer_text.lower() or "trail" in renderer_text.lower():
        return "trail-receiver"
    if "attribute" in module_blob.lower() or "reader" in module_blob.lower() or "source" in module_blob.lower():
        return "source"
    if "event" in event_text.lower() or has_events:
        return "receiver"
    if any(token in name for token in ("source", "leader", "seed", "driver", "upstream")):
        return "source"
    if any(token in name for token in ("receiver", "trail", "follow", "secondary", "downstream")):
        return "receiver"
    return "generic"


def parse_event_handlers(text: str) -> str:
    if not text:
        return "none"
    hits = re.findall(r"SourceEmitter(?:Name|ID)?=([^,\)]+)", text)
    if hits:
        return ", ".join(hit.strip('"') for hit in hits)
    return "present"


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    emitters: list[dict[str, Any]] = []
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = []
    system_bounds = payload["system_properties"]["FixedBounds"]["text"]
    for emitter in payload["emitters"]:
        renderer_text = emitter["properties"]["RendererProperties"]["text"]
        event_text = emitter["properties"]["EventHandlerScriptProps"]["text"]
        module_text = " ".join(
            emitter["properties"][key]["text"]
            for key in ("SpawnScriptProps", "UpdateScriptProps", "EmitterSpawnScriptProps", "EmitterUpdateScriptProps", "SimulationStages", "GraphSource", "GPUComputeScript")
        )
        parsed = {
            "renderer_classes": renderer_classes(renderer_text),
            "renderer_materials": material_paths(renderer_text),
            "event_handler_summary": parse_event_handlers(event_text),
            "sim_target": emitter["properties"]["SimTarget"]["text"],
            "fixed_bounds": emitter["properties"]["FixedBounds"]["text"],
            "renderer_digest": text_digest(renderer_text),
            "module_digest": text_digest(module_text),
            "event_digest": text_digest(event_text),
        }
        emitter["parsed"] = parsed
        emitter["role"] = classify_role(emitter)
        emitters.append(emitter)
        evidence.append(
            {
                "name": emitter["name"],
                "role": emitter["role"],
                "renderer_digest": parsed["renderer_digest"],
                "module_digest": parsed["module_digest"],
                "event_digest": parsed["event_digest"],
                "has_renderer_text": bool(renderer_text.strip()),
                "has_module_text": bool(module_text.strip()),
                "has_event_text": bool(event_text.strip()),
            }
        )
        if emitter["enabled"] == "False":
            warnings.append(f"Emitter `{emitter['name']}` is disabled.")
        if emitter["role"] in {"trail-receiver", "receiver"} and not parsed["renderer_classes"]:
            warnings.append(f"Emitter `{emitter['name']}` looks like a receiver but has no renderer.")
        if emitter["role"] == "trail-receiver" and not parsed["renderer_materials"]:
            warnings.append(f"Ribbon/trail emitter `{emitter['name']}` has no bound material in RendererProperties export text.")
    if not system_bounds and any(entry["role"] == "trail-receiver" for entry in emitters):
        warnings.append("System has ribbon/trail emitters but no FixedBounds export text.")
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
        lines.extend(
            [
                f"- `{emitter['name']}` role=`{emitter['role']}` sim=`{emitter['parsed']['sim_target'] or 'unknown'}` renderers=`{', '.join(emitter['parsed']['renderer_classes']) or 'none'}` materials=`{', '.join(emitter['parsed']['renderer_materials']) or 'none'}` events=`{emitter['parsed']['event_handler_summary']}`",
            ]
        )
    lines.extend(["", "## Evidence", ""])
    for item in report["evidence"]:
        lines.append(
            f"- `{item['name']}` renderer={item['renderer_digest']} module={item['module_digest']} event={item['event_digest']} role={item['role']}"
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
    client = BridgeClient(ctx.skill_root, project=args.project, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.system_path))
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
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")
    parser.set_defaults(func=command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
