from __future__ import annotations

import argparse
import textwrap
from collections import Counter
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import default_report_path, resolve_root_context, save_json, slugify, write_text


def build_ue_script(material_path: str) -> str:
    return textwrap.dedent(
        f"""
        import json
        import unreal

        MAT = unreal.UnrealBridgeMaterialLibrary

        def guid_text(value):
            try:
                return value.to_string()
            except Exception:
                return str(value)

        def serialize_param_default(param):
            return {{
                "name": param.name,
                "param_type": param.param_type,
                "value": param.value,
                "guid": guid_text(param.guid),
            }}

        def serialize_node(node):
            return {{
                "guid": guid_text(node.guid),
                "class_name": node.class_name,
                "caption": node.caption,
                "desc": node.desc,
                "x": node.x,
                "y": node.y,
                "input_names": list(node.input_names),
                "output_names": list(node.output_names),
                "key_properties": node.key_properties,
            }}

        def serialize_connection(connection):
            return {{
                "src_guid": guid_text(connection.src_guid),
                "src_output_name": connection.src_output_name,
                "src_output_index": connection.src_output_index,
                "dst_guid": guid_text(connection.dst_guid),
                "dst_input_name": connection.dst_input_name,
                "dst_input_index": connection.dst_input_index,
                "dst_property_name": connection.dst_property_name,
            }}

        def enum_token(value):
            text = str(value)
            if "." in text and ":" in text:
                return text.split(".")[-1].split(":")[0]
            return text

        def map_domain(value):
            return {{
                "MD_SURFACE": "Surface",
                "MD_DEFERRED_DECAL": "DeferredDecal",
                "MD_LIGHT_FUNCTION": "LightFunction",
                "MD_VOLUME": "Volume",
                "MD_POST_PROCESS": "PostProcess",
                "MD_UI": "UI",
                "MD_RUNTIME_VIRTUAL_TEXTURE": "RuntimeVirtualTexture",
            }}.get(enum_token(value), enum_token(value))

        def map_blend(value):
            return {{
                "BLEND_OPAQUE": "Opaque",
                "BLEND_MASKED": "Masked",
                "BLEND_TRANSLUCENT": "Translucent",
                "BLEND_ADDITIVE": "Additive",
                "BLEND_MODULATE": "Modulate",
                "BLEND_ALPHA_COMPOSITE": "AlphaComposite",
                "BLEND_ALPHA_HOLDOUT": "AlphaHoldout",
            }}.get(enum_token(value), enum_token(value))

        def read_raw_editor_info(path, bridge_info):
            raw = {{}}
            try:
                asset_path = path.split(".")[0]
                asset = unreal.EditorAssetLibrary.load_asset(asset_path)
                base = asset
                try:
                    if bridge_info.is_material_instance and bridge_info.base_path:
                        base = unreal.EditorAssetLibrary.load_asset(bridge_info.base_path.split(".")[0])
                    elif hasattr(asset, "get_base_material"):
                        base = asset.get_base_material() or asset
                except Exception:
                    base = asset
                if base:
                    raw["material_domain"] = map_domain(base.get_editor_property("material_domain"))
                    raw["blend_mode"] = map_blend(base.get_editor_property("blend_mode"))
                    raw["two_sided"] = bool(base.get_editor_property("two_sided"))
                    raw["use_material_attributes"] = bool(base.get_editor_property("use_material_attributes"))
            except Exception as exc:
                raw["error"] = str(exc)
            return raw

        info = MAT.get_material_info({material_path!r})
        graph = MAT.get_material_graph({material_path!r})
        analysis = MAT.analyze_material({material_path!r}, 0, 0)
        raw_editor_info = read_raw_editor_info({material_path!r}, info)

        payload = {{
            "material_info": {{
                "found": info.found,
                "name": info.name,
                "path": info.path,
                "is_material_instance": info.is_material_instance,
                "parent_path": info.parent_path,
                "base_path": info.base_path,
                "material_domain": info.material_domain,
                "blend_mode": info.blend_mode,
                "shading_models": list(info.shading_models),
                "two_sided": info.two_sided,
                "use_material_attributes": info.use_material_attributes,
                "usage_flags": list(info.usage_flags),
                "scalar_parameters": [serialize_param_default(item) for item in info.scalar_parameters],
                "vector_parameters": [serialize_param_default(item) for item in info.vector_parameters],
                "texture_parameters": [serialize_param_default(item) for item in info.texture_parameters],
                "static_switch_parameters": [serialize_param_default(item) for item in info.static_switch_parameters],
                "num_expressions": info.num_expressions,
                "num_function_calls": info.num_function_calls,
            }},
            "graph": {{
                "found": graph.found,
                "path": graph.path,
                "is_material_function": graph.is_material_function,
                "nodes": [serialize_node(node) for node in graph.nodes],
                "connections": [serialize_connection(item) for item in graph.connections],
                "output_connections": [serialize_connection(item) for item in graph.output_connections],
            }},
            "analysis": {{
                "found": analysis.found,
                "path": analysis.path,
                "material_domain": analysis.material_domain,
                "shading_models": list(analysis.shading_models),
                "max_instructions": analysis.max_instructions,
                "sampler_count": analysis.sampler_count,
                "expression_count": analysis.expression_count,
                "compile_errors": list(analysis.compile_errors),
                "shader_stats_ready": analysis.shader_stats_ready,
            }},
            "raw_editor_info": raw_editor_info,
        }}
        print(json.dumps(payload, ensure_ascii=False))
        """
    ).strip()


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _lower_blob(*values: Any) -> str:
    return " ".join(str(value or "") for value in values).lower()


def _node_text(node: dict[str, Any]) -> str:
    return _lower_blob(node.get("class_name"), node.get("caption"), node.get("desc"), node.get("key_properties"))


def _add(
    findings: list[dict[str, Any]],
    severity: str,
    rule_id: str,
    message: str,
    *,
    evidence: str | None = None,
    recommendation: str | None = None,
) -> None:
    findings.append(
        {
            "severity": severity,
            "rule_id": rule_id,
            "message": message,
            "evidence": evidence or "",
            "recommendation": recommendation or "",
        }
    )


def _output_properties(graph: dict[str, Any]) -> set[str]:
    props: set[str] = set()
    for connection in graph.get("output_connections") or []:
        prop = _norm(connection.get("dst_property_name"))
        if prop:
            props.add(prop)
    return props


def _prop_key(prop: str) -> str:
    compact = _norm(prop)
    if compact.startswith("MP_"):
        compact = compact[3:]
    return compact.replace(" ", "").replace("_", "").lower()


def _node_counters(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    class_counter = Counter(_norm(node.get("class_name")) for node in nodes)
    text = "\n".join(_node_text(node) for node in nodes)

    def count_contains(*tokens: str) -> int:
        lowered = [token.lower() for token in tokens]
        return sum(1 for node in nodes if any(token in _node_text(node) for token in lowered))

    return {
        "class_counts": dict(sorted(class_counter.items())),
        "texture_sample_nodes": count_contains("texturesample"),
        "scene_texture_nodes": count_contains("scenetexture"),
        "depth_nodes": count_contains("scenedepth", "depthfade", "pixeldepth"),
        "world_space_nodes": count_contains(
            "worldposition",
            "cameraposition",
            "cameravector",
            "objectposition",
            "actorposition",
            "distancetonearestsurface",
            "distancefield",
        ),
        "rvt_nodes": count_contains("runtimevirtualtexture", "virtualtexturesample"),
        "custom_nodes": count_contains("materialexpressioncustom"),
        "quality_switch_nodes": count_contains("qualityswitch", "featurelevelswitch"),
        "material_attribute_nodes": count_contains(
            "materialattributes",
            "makematerialattributes",
            "breakmaterialattributes",
            "blendmaterialattributes",
            "materialattributelayers",
        ),
        "substrate_nodes": count_contains("substrate", "strata"),
        "vertex_color_nodes": count_contains("vertexcolor"),
        "text_blob": text,
    }


def _is_lit(shading_models: list[str]) -> bool:
    lit_markers = {
        "DefaultLit",
        "Subsurface",
        "PreintegratedSkin",
        "ClearCoat",
        "SubsurfaceProfile",
        "TwoSidedFoliage",
        "Hair",
        "Cloth",
        "Eye",
        "SingleLayerWater",
        "ThinTranslucent",
        "FromMaterialExpression",
        "Strata",
    }
    return any(model in lit_markers for model in shading_models)


def audit_payload(raw: dict[str, Any]) -> dict[str, Any]:
    info = raw["material_info"]
    graph = raw["graph"]
    analysis = raw["analysis"]
    raw_editor_info = raw.get("raw_editor_info") or {}
    nodes = graph.get("nodes") or []
    props = _output_properties(graph)
    counters = _node_counters(nodes)
    findings: list[dict[str, Any]] = []

    domain = _norm(info.get("material_domain"))
    blend = _norm(info.get("blend_mode"))
    bridge_domain = domain
    bridge_blend = blend
    raw_domain = _norm(raw_editor_info.get("material_domain"))
    raw_blend = _norm(raw_editor_info.get("blend_mode"))
    if raw_domain and raw_domain != domain:
        domain = raw_domain
        _add(
            findings,
            "warning",
            "bridge_domain_mismatch",
            "Bridge material info domain differs from raw editor property.",
            evidence=f"bridge={bridge_domain} raw={raw_domain}",
            recommendation="Treat raw editor property as ground truth and verify UnrealBridge get_material_info.",
        )
    if raw_blend and raw_blend != blend:
        blend = raw_blend
        _add(
            findings,
            "warning",
            "bridge_blend_mismatch",
            "Bridge material info blend mode differs from raw editor property.",
            evidence=f"bridge={bridge_blend} raw={raw_blend}",
            recommendation="Treat raw editor property as ground truth and verify UnrealBridge get_material_info.",
        )
    shading_models = [_norm(item) for item in info.get("shading_models") or [] if _norm(item)]
    use_attrs = bool(info.get("use_material_attributes"))
    if isinstance(raw_editor_info.get("use_material_attributes"), bool):
        use_attrs = bool(raw_editor_info["use_material_attributes"])
    usage_flags = set(info.get("usage_flags") or [])
    props_lower = {_prop_key(prop) for prop in props}
    node_blob = counters["text_blob"]

    if not info.get("found"):
        _add(findings, "error", "asset_not_found", "Material asset was not found.")

    if analysis.get("compile_errors"):
        _add(
            findings,
            "error",
            "compile_errors",
            "Material currently has compile errors.",
            evidence="; ".join(analysis.get("compile_errors") or []),
            recommendation="Fix compile errors before making rendering-contract decisions.",
        )

    if use_attrs:
        _add(
            findings,
            "info",
            "material_attributes_route",
            "Material uses Material Attributes, so individual output-pin checks are conservative.",
            evidence=f"Material attribute node count: {counters['material_attribute_nodes']}",
            recommendation="Audit the Make/Break/Blend/MaterialAttributeLayers chain for final attribute ownership.",
        )

    pbr_outputs = {"basecolor", "metallic", "specular", "roughness", "normal", "ambientocclusion"}
    transparency_outputs = {"opacity", "opacitymask"}
    costly_outputs = {"worldpositionoffset", "pixeldepthoffset", "refraction"}

    if domain == "PostProcess":
        bad = sorted(prop for prop in props_lower if prop in pbr_outputs or prop in transparency_outputs or prop in costly_outputs)
        if "emissivecolor" not in props_lower and not use_attrs:
            _add(
                findings,
                "warning",
                "postprocess_missing_emissive",
                "PostProcess material has no EmissiveColor route.",
                evidence=f"Outputs: {sorted(props)}",
                recommendation="Post-process materials usually output the final color through EmissiveColor.",
            )
        if bad:
            _add(
                findings,
                "warning",
                "postprocess_pbr_outputs",
                "PostProcess material wires outputs that are normally surface-only.",
                evidence=", ".join(bad),
                recommendation="Move final screen-space color into EmissiveColor and remove ignored surface pins.",
            )
        if counters["scene_texture_nodes"] == 0:
            _add(
                findings,
                "info",
                "postprocess_no_scene_texture",
                "PostProcess material has no SceneTexture evidence.",
                recommendation="This is fine for pure overlays, but most screen effects need PostProcessInput or depth/normal scene reads.",
            )
    elif domain == "UI":
        if counters["world_space_nodes"] or counters["depth_nodes"] or counters["scene_texture_nodes"]:
            _add(
                findings,
                "warning",
                "ui_scene_or_world_nodes",
                "UI material appears to use scene/depth/world-space nodes.",
                evidence=f"scene={counters['scene_texture_nodes']} depth={counters['depth_nodes']} world={counters['world_space_nodes']}",
                recommendation="Keep UI materials simple, deterministic, and mostly texture/math driven.",
            )
        if blend not in {"Translucent", "Masked", "AlphaComposite", "Opaque"}:
            _add(
                findings,
                "info",
                "ui_unusual_blend",
                "UI material uses an unusual blend mode.",
                evidence=blend,
                recommendation="Confirm the Slate/UMG use case really needs this blend mode.",
            )
    elif domain == "LightFunction":
        if counters["texture_sample_nodes"] + counters["custom_nodes"] + counters["scene_texture_nodes"] >= 4:
            _add(
                findings,
                "warning",
                "lightfunction_heavy_graph",
                "LightFunction material appears expensive for a light mask.",
                evidence=f"textures={counters['texture_sample_nodes']} custom={counters['custom_nodes']} scene={counters['scene_texture_nodes']}",
                recommendation="Prefer a small grayscale mask, simple panner/noise, or baked flipbook for repeated light functions.",
            )
        if _is_lit(shading_models):
            _add(
                findings,
                "info",
                "lightfunction_lit_model",
                "LightFunction material reports a lit shading model.",
                evidence=", ".join(shading_models),
                recommendation="Confirm the domain ignores lit surface outputs and simplify if the graph carries unused PBR work.",
            )
    elif domain == "RuntimeVirtualTexture":
        if not counters["rvt_nodes"] and "runtimevirtualtexture" not in node_blob:
            _add(
                findings,
                "warning",
                "rvt_no_rvt_nodes",
                "RuntimeVirtualTexture domain has no obvious RVT node evidence.",
                recommendation="Verify the material writes/samples the intended RVT asset and material type.",
            )
    elif domain == "DeferredDecal":
        if "opacity" not in props_lower and "opacitymask" not in props_lower and not use_attrs:
            _add(
                findings,
                "warning",
                "decal_missing_opacity",
                "DeferredDecal material has no obvious opacity route.",
                evidence=f"Outputs: {sorted(props)}",
                recommendation="Most decals need an opacity/mask contract to avoid full-rectangle projection.",
            )
        if blend == "Opaque":
            _add(
                findings,
                "info",
                "decal_opaque_blend",
                "DeferredDecal material is opaque.",
                recommendation="Confirm this is intentional; many decal materials use translucent-style opacity control.",
            )
    elif domain == "Surface":
        if "Unlit" in shading_models and not _is_lit([m for m in shading_models if m != "Unlit"]):
            if "emissivecolor" not in props_lower and not use_attrs:
                _add(
                    findings,
                    "warning",
                    "unlit_missing_emissive",
                    "Unlit surface material has no EmissiveColor output.",
                    recommendation="Wire the visible color to EmissiveColor or the material may render black.",
                )
            ignored = sorted(prop for prop in props_lower if prop in {"metallic", "specular", "roughness", "normal"})
            if ignored:
                _add(
                    findings,
                    "info",
                    "unlit_lit_outputs",
                    "Unlit material wires lit-only outputs that are likely ignored.",
                    evidence=", ".join(ignored),
                    recommendation="Remove ignored PBR work unless the material can switch to a lit shading model.",
                )
        elif _is_lit(shading_models) and not use_attrs:
            expected = {"basecolor", "roughness", "normal"}
            missing = sorted(expected - props_lower)
            if missing:
                _add(
                    findings,
                    "warning",
                    "lit_missing_core_outputs",
                    "Lit surface material is missing core PBR outputs.",
                    evidence=", ".join(missing),
                    recommendation="Confirm defaults are intentional; most lit materials should define BaseColor, Roughness, and Normal.",
                )

    if blend == "Opaque" and ("opacity" in props_lower or "opacitymask" in props_lower):
        _add(
            findings,
            "info",
            "opaque_alpha_outputs",
            "Opaque material wires alpha-related outputs.",
            evidence=", ".join(sorted(prop for prop in props_lower if prop in transparency_outputs)),
            recommendation="If transparency is required, switch blend mode; otherwise remove the unused alpha work.",
        )
    if blend == "Masked" and "opacitymask" not in props_lower and not use_attrs:
        _add(
            findings,
            "warning",
            "masked_missing_opacitymask",
            "Masked material has no OpacityMask route.",
            recommendation="Wire a stable mask into OpacityMask or use Opaque/Translucent as appropriate.",
        )
    if blend in {"Translucent", "Additive", "Modulate", "AlphaComposite", "AlphaHoldout"}:
        if "opacity" not in props_lower and not use_attrs and blend not in {"Additive", "Modulate"}:
            _add(
                findings,
                "info",
                "translucent_missing_opacity",
                "Transparent/composited blend mode has no Opacity output.",
                recommendation="Confirm alpha is intentionally constant; otherwise expose texture/parameter-driven opacity.",
            )
        if counters["depth_nodes"] or "refraction" in props_lower or "pixeldepthoffset" in props_lower:
            _add(
                findings,
                "warning",
                "transparent_depth_or_refraction_cost",
                "Transparent material uses depth/refraction/PDO-related work.",
                evidence=f"depth_nodes={counters['depth_nodes']} outputs={sorted(props)}",
                recommendation="Preview overdraw and sorting; add a cheaper fallback for mobile or dense screen coverage.",
            )

    if "worldpositionoffset" in props_lower:
        severity = "warning" if info.get("two_sided") or blend == "Masked" else "info"
        _add(
            findings,
            severity,
            "wpo_contract",
            "Material uses WorldPositionOffset.",
            recommendation="Confirm bounds, shadow behavior, Nanite support, motion cost, and low-quality fallback.",
        )
    if "pixeldepthoffset" in props_lower:
        _add(
            findings,
            "warning",
            "pdo_sorting_cost",
            "Material uses PixelDepthOffset.",
            recommendation="Check sorting, depth prepass behavior, virtual shadow maps, and platform support.",
        )
    if "refraction" in props_lower:
        _add(
            findings,
            "warning",
            "refraction_cost",
            "Material uses Refraction.",
            recommendation="Use only where the visual payoff justifies translucent/refraction cost.",
        )

    if "TwoSidedFoliage" in shading_models:
        if not info.get("two_sided"):
            _add(
                findings,
                "warning",
                "foliage_not_twosided",
                "TwoSidedFoliage shading model is used but material is not Two Sided.",
                recommendation="Most foliage sheets need Two Sided plus a controlled subsurface color.",
            )
        if "subsurfacecolor" not in props_lower and not use_attrs:
            _add(
                findings,
                "info",
                "foliage_missing_subsurface",
                "TwoSidedFoliage material has no SubsurfaceColor route.",
                recommendation="Add a leaf transmission/subsurface tint unless the default is intentional.",
            )
    if any(model in shading_models for model in {"Subsurface", "PreintegratedSkin", "SubsurfaceProfile"}):
        if "subsurfacecolor" not in props_lower and not use_attrs:
            _add(
                findings,
                "info",
                "sss_missing_subsurface",
                "Subsurface shading model has no SubsurfaceColor route.",
                recommendation="Wire scatter tint/mask or document why the default is acceptable.",
            )
    if "ClearCoat" in shading_models:
        custom_data = {"customdata0", "customdata1"} & props_lower
        if not custom_data and not use_attrs:
            _add(
                findings,
                "info",
                "clearcoat_missing_customdata",
                "ClearCoat model has no CustomData output evidence.",
                recommendation="Wire clear coat amount and roughness when the coat is part of the art target.",
            )
    if "SingleLayerWater" in shading_models and blend != "Opaque":
        _add(
            findings,
            "warning",
            "singlelayerwater_nonopaque",
            "SingleLayerWater usually belongs on the opaque path.",
            evidence=f"Blend={blend}",
            recommendation="Confirm the water route is intentional; avoid unnecessary translucent sorting/overdraw.",
        )
    if any(model in shading_models for model in {"ThinTranslucent", "Hair", "Cloth", "Eye"}):
        _add(
            findings,
            "info",
            "specialized_shading_model",
            "Material uses a specialized shading model that needs target-carrier preview.",
            evidence=", ".join(model for model in shading_models if model in {"ThinTranslucent", "Hair", "Cloth", "Eye"}),
            recommendation="Review required geometry, tangent/normal/textures, and preview on the appropriate asset type.",
        )
    if any(model in shading_models for model in {"Strata", "FromMaterialExpression"}) or counters["substrate_nodes"]:
        _add(
            findings,
            "warning",
            "advanced_shading_route",
            "Material appears to use Substrate/Strata or per-pixel shading-model selection.",
            evidence=f"models={shading_models} substrate_nodes={counters['substrate_nodes']}",
            recommendation="Verify engine/project support, quality fallback, and shader cost before approving.",
        )

    if counters["rvt_nodes"] and domain not in {"RuntimeVirtualTexture", "Surface"}:
        _add(
            findings,
            "info",
            "rvt_unusual_domain",
            "RVT node evidence appears in an unusual material domain.",
            evidence=f"Domain={domain}",
            recommendation="Confirm this is a supported project-specific route.",
        )
    if counters["custom_nodes"] and not counters["quality_switch_nodes"]:
        _add(
            findings,
            "info",
            "custom_without_quality_gate",
            "Material uses Custom HLSL nodes without obvious FeatureLevelSwitch or QualitySwitch evidence.",
            recommendation="Add a cheaper fallback when the custom path is expensive or platform-sensitive.",
        )
    if counters["texture_sample_nodes"] >= 6 and not counters["quality_switch_nodes"]:
        _add(
            findings,
            "info",
            "many_textures_without_quality_gate",
            "Material has many texture sample nodes and no obvious quality/feature gate.",
            evidence=f"texture_sample_nodes={counters['texture_sample_nodes']}",
            recommendation="Consider packed channels, sampler sharing, quality switches, or lower-tier material instances.",
        )

    if domain == "Surface":
        if "UsedWithNiagaraSprites" in usage_flags or "UsedWithNiagaraRibbons" in usage_flags:
            _add(
                findings,
                "info",
                "vfx_usage_flag_material_side",
                "Material has Niagara usage flags, but this audit only checks material-side compatibility.",
                evidence=", ".join(sorted(flag for flag in usage_flags if "Niagara" in flag)),
                recommendation="Return material input expectations to niagara-vfx-artist for real system hookup verification.",
            )

    if not findings:
        _add(findings, "ok", "no_first_pass_findings", "No first-pass domain/rendering contract findings.")

    risk_counts = Counter(item["severity"] for item in findings)
    return {
        "tool": "material_domain_audit",
        "material_path": raw.get("material_info", {}).get("path") or "",
        "material_info": info,
        "raw_editor_info": raw_editor_info,
        "analysis": analysis,
        "domain_contract": {
            "domain": domain,
            "blend_mode": blend,
            "bridge_domain": bridge_domain,
            "bridge_blend_mode": bridge_blend,
            "shading_models": shading_models,
            "two_sided": bool(raw_editor_info.get("two_sided", info.get("two_sided"))),
            "use_material_attributes": use_attrs,
            "usage_flags": sorted(usage_flags),
            "wired_outputs": sorted(props),
        },
        "node_evidence": {key: value for key, value in counters.items() if key != "text_blob"},
        "findings": findings,
        "summary": {
            "errors": risk_counts.get("error", 0),
            "warnings": risk_counts.get("warning", 0),
            "info": risk_counts.get("info", 0),
            "ok": risk_counts.get("ok", 0),
            "contract_note": "Material-side audit only; real Niagara renderer/emitter binding truth belongs to niagara-vfx-artist.",
        },
    }


def render_markdown(material_path: str, report: dict[str, Any]) -> str:
    contract = report["domain_contract"]
    summary = report["summary"]
    lines = [
        f"# Material Domain Audit: {material_path}",
        "",
        f"- Domain: `{contract['domain']}`",
        f"- Blend mode: `{contract['blend_mode']}`",
        f"- Shading models: `{', '.join(contract['shading_models']) or 'None'}`",
        f"- Two sided: `{contract['two_sided']}`",
        f"- Use Material Attributes: `{contract['use_material_attributes']}`",
        f"- Wired outputs: `{', '.join(contract['wired_outputs']) or 'None'}`",
        f"- Shader stats ready: `{report['analysis'].get('shader_stats_ready')}`",
        f"- Instructions: `{report['analysis'].get('max_instructions')}`",
        f"- Samplers: `{report['analysis'].get('sampler_count')}`",
        "",
        "## Findings",
        "",
    ]
    for finding in report["findings"]:
        lines.append(f"- [{finding['severity']}] `{finding['rule_id']}` {finding['message']}")
        if finding.get("evidence"):
            lines.append(f"  Evidence: {finding['evidence']}")
        if finding.get("recommendation"):
            lines.append(f"  Recommendation: {finding['recommendation']}")
    lines.extend(
        [
            "",
            "## Node Evidence",
            "",
        ]
    )
    evidence = report["node_evidence"]
    for key in (
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
    ):
        lines.append(f"- {key}: `{evidence.get(key, 0)}`")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Errors: `{summary['errors']}`",
            f"- Warnings: `{summary['warnings']}`",
            f"- Info: `{summary['info']}`",
            f"- Boundary: {summary['contract_note']}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def command(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    raw = client.exec_json(build_ue_script(args.material_path))
    report = audit_payload(raw)
    out = Path(args.out) if args.out else default_report_path(
        ctx,
        "audits/domain",
        slugify(args.material_path),
        "material-domain-audit",
        ".json",
    )
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(args.material_path, report))
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit an Unreal material's domain, blend mode, shading model, output pins, and rendering contract."
    )
    parser.add_argument("material_path")
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
