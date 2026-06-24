from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, sha256_file, slugify, utc_now_iso, write_text
from .material_contract import validate_contract
from .texture_asset_report import image_info


PROFILE_KEYWORDS = {
    "post_process": ("post process", "postprocess", "screen", "full screen", "lut", "vignette", "bloom", "color grade"),
    "decal": ("decal", "stain", "graffiti", "bullet", "splat", "mark", "sticker", "projected"),
    "foliage": ("foliage", "leaf", "leaves", "grass", "bush", "plant", "vegetation", "two sided foliage"),
    "water": ("water", "river", "lake", "ocean", "foam", "shore", "caustic", "ripple", "wave"),
    "heat_haze": ("heat haze", "refraction", "distortion", "mirage", "shockwave distortion"),
    "fire": ("fire", "flame", "burning", "torch", "ember", "lava", "magma", "explosion flame"),
    "smoke": ("smoke", "fog", "mist", "dust", "steam", "ash"),
    "energy": ("energy", "plasma", "magic", "arcane", "electric", "lightning", "laser", "glow"),
    "dissolve": ("dissolve", "burn edge", "erosion", "disintegrate", "reveal mask"),
    "glass": ("glass", "crystal", "transparent", "ice", "gem", "clear coat"),
    "ui": ("ui", "hud", "widget", "interface", "reticle", "button"),
    "landscape": ("landscape", "terrain", "slope", "rvt", "ground blend"),
    "character": ("skin", "hair", "cloth", "armor", "character", "eye"),
    "environment": ("rock", "wall", "metal", "wood", "concrete", "prop", "environment"),
}

VALID_PROFILES = (
    "auto",
    "surface",
    "fire",
    "smoke",
    "energy",
    "heat_haze",
    "water",
    "foliage",
    "decal",
    "post_process",
    "ui",
    "glass",
    "dissolve",
    "landscape",
    "character",
    "environment",
    "custom",
)

VALID_CARRIERS = (
    "auto",
    "sprite",
    "ribbon",
    "mesh",
    "decal",
    "surface",
    "landscape",
    "ui",
    "post_process",
    "unknown",
)


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def bool_from_string(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def infer_profile(text: str, requested: str) -> str:
    requested = requested.strip().lower()
    if requested and requested != "auto":
        return requested
    lowered = text.lower()
    for profile, keywords in PROFILE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return profile
    return "surface"


def infer_carrier(profile: str, requested: str) -> str:
    requested = requested.strip().lower()
    if requested and requested != "auto":
        return requested
    if profile == "decal":
        return "decal"
    if profile == "post_process":
        return "post_process"
    if profile == "ui":
        return "ui"
    if profile == "landscape":
        return "landscape"
    if profile in {"fire", "smoke", "energy", "heat_haze"}:
        return "sprite"
    return "surface"


def route_for(profile: str, carrier: str) -> dict[str, Any]:
    routes: dict[str, dict[str, Any]] = {
        "fire": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["UsedWithNiagaraSprites"] if carrier == "sprite" else [],
            "dynamic_inputs": ["ParticleColor", "DynamicParameter"],
            "sort_or_depth_notes": "High overdraw risk; preview on the intended VFX carrier before optimization.",
        },
        "smoke": {
            "domain": "Surface",
            "blend_mode": "Translucent",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["UsedWithNiagaraSprites"] if carrier == "sprite" else [],
            "dynamic_inputs": ["ParticleColor", "DynamicParameter"],
            "sort_or_depth_notes": "Soft translucent coverage; validate sorting and screen coverage early.",
        },
        "energy": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["UsedWithNiagaraSprites"] if carrier == "sprite" else [],
            "dynamic_inputs": ["ParticleColor", "DynamicParameter"],
            "sort_or_depth_notes": "Additive intensity can hide alpha mistakes; sweep opacity and emissive separately.",
        },
        "heat_haze": {
            "domain": "Surface",
            "blend_mode": "Translucent",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity", "Refraction"],
            "usage_flags": ["UsedWithNiagaraSprites"] if carrier == "sprite" else [],
            "dynamic_inputs": ["ParticleColor", "DynamicParameter"],
            "sort_or_depth_notes": "Distortion must be tested against high-contrast and neutral backgrounds.",
        },
        "water": {
            "domain": "Surface",
            "blend_mode": "Opaque",
            "shading_model": "SingleLayerWater",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Roughness", "Normal", "Opacity"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "Route assumes Single Layer Water; verify project water rendering support.",
        },
        "foliage": {
            "domain": "Surface",
            "blend_mode": "Masked",
            "shading_model": "TwoSidedFoliage",
            "two_sided": True,
            "expected_outputs": ["BaseColor", "OpacityMask", "SubsurfaceColor", "Roughness", "Normal"],
            "usage_flags": [],
            "dynamic_inputs": ["VertexColor"],
            "sort_or_depth_notes": "Masked two-sided coverage; validate alpha mips and foliage card carrier.",
        },
        "decal": {
            "domain": "DeferredDecal",
            "blend_mode": "Translucent",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Opacity", "Roughness", "Normal"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "DeferredDecal is a material domain; do not model it as a usage flag.",
        },
        "post_process": {
            "domain": "PostProcess",
            "blend_mode": "Opaque",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "Preview in a neutral scene and record blendable location.",
        },
        "ui": {
            "domain": "UserInterface",
            "blend_mode": "Translucent",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["FinalColor", "Opacity"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "UI materials need widget-size preview and readable alpha edges.",
        },
        "glass": {
            "domain": "Surface",
            "blend_mode": "Translucent",
            "shading_model": "ThinTranslucent",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Opacity", "Roughness", "Normal", "Refraction"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "Translucent glass needs sorting, refraction, and background readability checks.",
        },
        "dissolve": {
            "domain": "Surface",
            "blend_mode": "Masked",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "OpacityMask", "EmissiveColor", "Roughness", "Normal"],
            "usage_flags": [],
            "dynamic_inputs": ["DynamicParameter"],
            "sort_or_depth_notes": "Dissolve threshold and edge width must be swept before acceptance.",
        },
        "landscape": {
            "domain": "Surface",
            "blend_mode": "Opaque",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Roughness", "Normal"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "Large screen coverage; validate texture memory, RVT use, and layer count.",
        },
    }
    return routes.get(
        profile,
        {
            "domain": "Surface",
            "blend_mode": "Opaque",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Roughness", "Normal"],
            "usage_flags": [],
            "dynamic_inputs": [],
            "sort_or_depth_notes": "Confirm carrier, screen coverage, and platform budget from the reference.",
        },
    )


def budget_for(profile: str, platform: str) -> dict[str, Any]:
    low_end = platform.strip().lower() in {"android", "mobile", "ios", "quest", "low"}
    defaults = {
        "fire": (90, 4, 16),
        "smoke": (80, 3, 16),
        "energy": (100, 4, 16),
        "heat_haze": (80, 3, 8),
        "water": (140, 6, 64),
        "foliage": (90, 4, 32),
        "decal": (70, 3, 16),
        "post_process": (100, 2, 8),
        "ui": (60, 2, 8),
        "glass": (130, 5, 32),
        "dissolve": (110, 5, 32),
        "landscape": (160, 8, 128),
        "surface": (120, 5, 32),
    }
    instruction_budget, sampler_budget, texture_mb = defaults.get(profile, defaults["surface"])
    if low_end:
        instruction_budget = max(45, int(instruction_budget * 0.6))
        sampler_budget = max(2, min(sampler_budget, 4))
        texture_mb = max(4, int(texture_mb * 0.5))
    return {
        "platform": platform,
        "instruction_budget": instruction_budget,
        "sampler_budget": sampler_budget,
        "texture_memory_budget_mb": texture_mb,
        "overdraw_risk": "high" if profile in {"fire", "smoke", "energy", "heat_haze", "glass"} else "medium",
    }


def tex(name: str, role: str, channels: str, resolution: str, srgb: bool, source_action: str, grid: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "role": role,
        "channels": channels,
        "resolution": resolution,
        "grid": grid,
        "srgb": srgb,
        "source_action": source_action,
        "qa": "texture_asset_report.py",
        "import_review": "texture_import_audit.py / texture_import_fix.py",
    }


def texture_requirements_for(effect: str, profile: str) -> list[dict[str, Any]]:
    prefix = f"T_{slugify(effect).replace('-', '_')}"
    by_profile: dict[str, list[dict[str, Any]]] = {
        "fire": [
            tex(f"{prefix}_FlameFlipbook_VFX", "flipbook", "RGBA color+alpha", "1024x1024 or 2048x2048", True, "library search, then cm-imagegen if no approved match", "8x8"),
            tex(f"{prefix}_BreakupNoise_VFX", "mask", "R opacity breakup", "512x512 or 1024x1024", False, "reuse approved noise/mask library asset"),
            tex(f"{prefix}_ColorRamp_VFX", "ramp", "RGB heat color ramp", "256x16", True, "author or generate after color approval"),
        ],
        "smoke": [
            tex(f"{prefix}_SmokeFlipbook_VFX", "flipbook", "RGBA density+alpha", "1024x1024 or 2048x2048", True, "library search, then cm-imagegen if no approved match", "8x8"),
            tex(f"{prefix}_SoftNoise_VFX", "mask", "R density breakup", "512x512", False, "reuse approved noise/mask library asset"),
        ],
        "energy": [
            tex(f"{prefix}_EnergyMask_VFX", "mask", "R shape, optional G secondary break", "1024x1024", False, "generate from reference if shape language is custom"),
            tex(f"{prefix}_EnergyRamp_VFX", "ramp", "RGB color over intensity", "256x16", True, "author from reference color bands"),
            tex(f"{prefix}_Distortion_VFX", "flow", "RG flow or distortion vector", "512x512", False, "draft only until channel validated"),
        ],
        "heat_haze": [
            tex(f"{prefix}_DistortionNormal_VFX", "normal", "RGB tangent normal", "512x512 or 1024x1024", False, "use validated normal/distortion library asset"),
            tex(f"{prefix}_OpacityMask_VFX", "mask", "R distortion falloff", "512x512", False, "generate from reference silhouette if needed"),
        ],
        "water": [
            tex(f"{prefix}_NormalA", "normal", "RGB small wave normal", "1024x1024", False, "reuse approved water normal or bake"),
            tex(f"{prefix}_NormalB", "normal", "RGB large wave normal", "1024x1024", False, "reuse approved water normal or bake"),
            tex(f"{prefix}_FoamMask", "mask", "R foam breakup", "1024x1024", False, "library search, generate only for custom foam identity"),
            tex(f"{prefix}_FlowMap", "flow", "RG direction, B/A optional masks", "512x512 or 1024x1024", False, "technical validation required before final use"),
        ],
        "foliage": [
            tex(f"{prefix}_Leaf_DiffuseAlpha", "foliage", "RGB leaf color, A cutout", "1024x1024 or 2048x2048", True, "library search, then cm-imagegen from reference species"),
            tex(f"{prefix}_Leaf_Normal", "normal", "RGB leaf/card normal", "1024x1024", False, "generate/bake only if silhouette reference supports it"),
            tex(f"{prefix}_Leaf_ORM", "packed", "R AO, G Roughness, B Metallic", "1024x1024", False, "pack after channel validation"),
        ],
        "decal": [
            tex(f"{prefix}_DecalColorAlpha", "decal", "RGB decal color, A opacity", "1024x1024", True, "generate from exact reference marks if custom"),
            tex(f"{prefix}_DecalNormal", "normal", "RGB projected normal detail", "1024x1024", False, "optional; validate decal normal cost"),
            tex(f"{prefix}_DecalRoughness", "mask", "R roughness/wetness", "512x512", False, "derive from decal intent"),
        ],
        "post_process": [
            tex(f"{prefix}_LUT", "ramp", "RGB color transform or palette ramp", "256x16 or LUT asset", True, "author from graded reference"),
            tex(f"{prefix}_ScreenMask", "mask", "R spatial mask", "512x512", False, "only if effect has stable screen-space shape"),
        ],
        "ui": [
            tex(f"{prefix}_UI_ColorAlpha", "sprite", "RGBA interface graphic", "power-of-two or UI-native size", True, "use source art or generate crisp alpha asset"),
        ],
        "glass": [
            tex(f"{prefix}_GlassNormal", "normal", "RGB surface distortion normal", "1024x1024", False, "reuse/bake validated normal"),
            tex(f"{prefix}_DirtMask", "mask", "R dirt/frost opacity", "1024x1024", False, "generate from reference if dirty/frosted identity matters"),
            tex(f"{prefix}_RoughnessMask", "mask", "R roughness variation", "512x512", False, "derive from surface condition"),
        ],
        "dissolve": [
            tex(f"{prefix}_DissolveMask", "mask", "R dissolve threshold", "1024x1024", False, "generate or reuse mask matching edge language"),
            tex(f"{prefix}_EdgeRamp", "ramp", "RGB burning/energy edge color", "256x16", True, "author from approved edge colors"),
        ],
        "landscape": [
            tex(f"{prefix}_Layer_BaseColor", "albedo", "RGB surface color", "2048x2048", True, "use scanned/authored surface set"),
            tex(f"{prefix}_Layer_Normal", "normal", "RGB surface normal", "2048x2048", False, "use scanned/authored surface set"),
            tex(f"{prefix}_Layer_ORM", "packed", "R AO, G Roughness, B Height/Metallic", "2048x2048", False, "pack and validate channel semantics"),
        ],
    }
    return by_profile.get(
        profile,
        [
            tex(f"{prefix}_BaseColor", "albedo", "RGB color", "1024x1024 or 2048x2048", True, "use source texture or generate after reference analysis"),
            tex(f"{prefix}_Normal", "normal", "RGB normal", "1024x1024 or 2048x2048", False, "bake/source preferred; generated normals need validation"),
            tex(f"{prefix}_ORM", "packed", "R AO, G Roughness, B Metallic", "1024x1024 or 2048x2048", False, "pack after semantic validation"),
        ],
    )


def parameters_for(profile: str) -> list[dict[str, Any]]:
    common_color = {"name": "Tint", "type": "Vector", "default": "(R=1,G=1,B=1,A=1)", "range": "", "owner": "artist", "purpose": "Global color bias from the reference."}
    common_opacity = {"name": "OpacityScale", "type": "Scalar", "default": "1.0", "range": "0..2", "owner": "artist/runtime", "purpose": "Overall alpha strength."}
    profile_params: dict[str, list[dict[str, Any]]] = {
        "fire": [
            {"name": "HotColor", "type": "Vector", "default": "(R=1,G=0.75,B=0.25,A=1)", "range": "", "owner": "artist", "purpose": "Bright inner flame color."},
            {"name": "CoolColor", "type": "Vector", "default": "(R=1,G=0.12,B=0.02,A=1)", "range": "", "owner": "artist", "purpose": "Outer flame/ember color."},
            {"name": "EmissiveIntensity", "type": "Scalar", "default": "8.0", "range": "0..50", "owner": "artist/runtime", "purpose": "Visible heat and bloom strength."},
            {"name": "BreakupScale", "type": "Scalar", "default": "1.0", "range": "0.1..8", "owner": "artist", "purpose": "Mask/noise spatial frequency."},
            common_opacity,
        ],
        "smoke": [
            common_color,
            common_opacity,
            {"name": "Density", "type": "Scalar", "default": "0.65", "range": "0..2", "owner": "artist/runtime", "purpose": "Smoke body opacity before particle fading."},
            {"name": "EdgeSoftness", "type": "Scalar", "default": "0.35", "range": "0..1", "owner": "artist", "purpose": "Controls how quickly alpha dissolves at the plume edge."},
            {"name": "NoiseContrast", "type": "Scalar", "default": "0.5", "range": "0..2", "owner": "artist", "purpose": "Breakup strength inside the smoke body."},
        ],
        "energy": [
            common_color,
            common_opacity,
            {"name": "EmissiveIntensity", "type": "Scalar", "default": "12.0", "range": "0..80", "owner": "artist/runtime", "purpose": "Core glow and bloom strength."},
            {"name": "CoreWidth", "type": "Scalar", "default": "0.45", "range": "0..1", "owner": "artist", "purpose": "Width of the brightest internal band."},
            {"name": "DistortionStrength", "type": "Scalar", "default": "0.1", "range": "0..1", "owner": "artist/runtime", "purpose": "Optional UV or refraction-style shimmer."},
        ],
        "heat_haze": [
            common_opacity,
            {"name": "DistortionStrength", "type": "Scalar", "default": "0.08", "range": "0..0.5", "owner": "artist/runtime", "purpose": "Screen/background offset amount."},
            {"name": "FalloffPower", "type": "Scalar", "default": "2.0", "range": "0.25..8", "owner": "artist", "purpose": "Shape falloff from center to edge."},
            {"name": "NoiseSpeed", "type": "Scalar", "default": "0.2", "range": "0..2", "owner": "artist/runtime", "purpose": "Animated distortion drift speed."},
        ],
        "water": [
            {"name": "ShallowColor", "type": "Vector", "default": "(R=0.18,G=0.55,B=0.62,A=1)", "range": "", "owner": "artist", "purpose": "Near-surface water color."},
            {"name": "DeepColor", "type": "Vector", "default": "(R=0.02,G=0.12,B=0.25,A=1)", "range": "", "owner": "artist", "purpose": "Depth-tinted water color."},
            {"name": "NormalStrength", "type": "Scalar", "default": "0.6", "range": "0..2", "owner": "artist", "purpose": "Combined wave normal strength."},
            {"name": "FlowSpeed", "type": "Scalar", "default": "0.05", "range": "0..1", "owner": "artist/runtime", "purpose": "Panning/flow speed."},
            {"name": "FoamAmount", "type": "Scalar", "default": "0.35", "range": "0..1", "owner": "artist/runtime", "purpose": "Foam visibility."},
        ],
        "foliage": [
            common_color,
            {"name": "OpacityClip", "type": "Scalar", "default": "0.35", "range": "0..1", "owner": "artist", "purpose": "Masked alpha cutoff."},
            {"name": "SubsurfaceTint", "type": "Vector", "default": "(R=0.35,G=0.8,B=0.2,A=1)", "range": "", "owner": "artist", "purpose": "Backlit leaf color."},
            {"name": "WindStrength", "type": "Scalar", "default": "0.25", "range": "0..2", "owner": "artist/runtime", "purpose": "WPO wind amount if enabled."},
        ],
        "decal": [
            common_color,
            common_opacity,
            {"name": "EdgeFeather", "type": "Scalar", "default": "0.1", "range": "0..1", "owner": "artist", "purpose": "Softens projected decal edges."},
            {"name": "RoughnessOverride", "type": "Scalar", "default": "0.7", "range": "0..1", "owner": "artist", "purpose": "Controls decal roughness/wetness read."},
        ],
        "post_process": [
            {"name": "BlendWeight", "type": "Scalar", "default": "1.0", "range": "0..1", "owner": "runtime", "purpose": "Global post-process contribution."},
            common_color,
            {"name": "DistortionStrength", "type": "Scalar", "default": "0.0", "range": "0..1", "owner": "artist/runtime", "purpose": "Optional screen-space distortion."},
        ],
        "glass": [
            common_color,
            {"name": "Opacity", "type": "Scalar", "default": "0.35", "range": "0..1", "owner": "artist", "purpose": "Visible transparency amount."},
            {"name": "Roughness", "type": "Scalar", "default": "0.05", "range": "0..1", "owner": "artist", "purpose": "Sharpness of transmitted/reflected highlight."},
            {"name": "RefractionStrength", "type": "Scalar", "default": "0.04", "range": "0..0.5", "owner": "artist", "purpose": "Background distortion/refraction amount."},
            {"name": "NormalStrength", "type": "Scalar", "default": "0.35", "range": "0..2", "owner": "artist", "purpose": "Surface ripple, bevel, frost, or chipped detail strength."},
        ],
        "dissolve": [
            common_color,
            {"name": "DissolveAmount", "type": "Scalar", "default": "0.0", "range": "0..1", "owner": "runtime", "purpose": "Threshold position for reveal/removal."},
            {"name": "EdgeWidth", "type": "Scalar", "default": "0.05", "range": "0..0.5", "owner": "artist", "purpose": "Width of glowing transition edge."},
            {"name": "EdgeIntensity", "type": "Scalar", "default": "5.0", "range": "0..50", "owner": "artist/runtime", "purpose": "Glow strength on dissolve edge."},
        ],
    }
    return profile_params.get(profile, [common_color, common_opacity, {"name": "Roughness", "type": "Scalar", "default": "0.55", "range": "0..1", "owner": "artist", "purpose": "Base surface roughness."}])


def reference_record(path: Path, cache_dir: Path | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "cached_path": "",
        "sha256": "",
        "image_info": None,
    }
    if path.exists() and path.is_file():
        record["sha256"] = sha256_file(path)
        try:
            record["image_info"] = image_info(path)
        except Exception as exc:
            record["image_info"] = {"path": str(path), "warning": f"image info unavailable: {exc}"}
        if cache_dir is not None:
            ensure_dir(cache_dir)
            dest = cache_dir / f"{slugify(path.stem)}{path.suffix.lower()}"
            if dest.resolve() != path.resolve():
                if dest.exists():
                    dest = cache_dir / f"{slugify(path.stem)}-{record['sha256'][:8]}{path.suffix.lower()}"
                shutil.copy2(path, dest)
            record["cached_path"] = str(dest)
    return record


def parse_texture_override(value: str) -> dict[str, Any]:
    parts = [part.strip() for part in value.split("|")]
    if len(parts) < 3:
        raise argparse.ArgumentTypeError("Texture overrides must look like name|role|channels|resolution|srgb|source_action|grid.")
    while len(parts) < 7:
        parts.append("")
    return {
        "name": parts[0],
        "role": parts[1],
        "channels": parts[2],
        "resolution": parts[3],
        "srgb": bool_from_string(parts[4]) if parts[4] else None,
        "source_action": parts[5],
        "grid": parts[6],
        "qa": "texture_asset_report.py",
        "import_review": "texture_import_audit.py / texture_import_fix.py",
    }


def parse_parameter_override(value: str) -> dict[str, Any]:
    parts = [part.strip() for part in value.split("|")]
    if len(parts) < 3:
        raise argparse.ArgumentTypeError("Parameter overrides must look like name|type|default|range|owner|purpose.")
    while len(parts) < 6:
        parts.append("")
    return {
        "name": parts[0],
        "type": parts[1],
        "default": parts[2],
        "range": parts[3],
        "owner": parts[4],
        "purpose": parts[5],
    }


def preview_plan_for(effect: str, layer: str, carrier: str, profile: str, parameters: list[dict[str, Any]]) -> dict[str, Any]:
    material_placeholder = f"/Game/Materials/M_{slugify(effect).replace('-', '_')}_{slugify(layer).replace('-', '_')}"
    carrier_arg = carrier if carrier in {"sprite", "ribbon", "decal", "post_process"} else "shaderball"
    render_command = (
        f"python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render {material_placeholder} "
        f"--project <UE_PROJECT> --markdown"
    )
    if carrier_arg != "shaderball":
        render_command = (
            f"python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render {material_placeholder} "
            f"--carrier {carrier_arg} --project <UE_PROJECT> --markdown"
        )
    sweep_names = [item["name"] for item in parameters if item.get("type") == "Scalar"][:3]
    sweep_commands = [
        f"python D:/Skills/skills/unreal-material-artist/tools/material_preview.py sweep {material_placeholder} --param-name {name} --value 0.25 --value 0.5 --value 1.0 --project <UE_PROJECT> --markdown"
        for name in sweep_names
    ]
    notes = [
        "Use the closest real carrier before approving the look.",
        "Record preview paths so later material_regression can compare against the accepted baseline.",
    ]
    if profile in {"fire", "smoke", "energy", "heat_haze"}:
        notes.append("Preview against both dark and mid-gray backgrounds to catch overbright or invisible alpha edges.")
    return {
        "material_path_placeholder": material_placeholder,
        "carrier": carrier,
        "primary_render_command": render_command,
        "sweep_commands": sweep_commands,
        "notes": notes,
    }


def audit_plan_for(effect: str, layer: str, profile: str, textures: list[dict[str, Any]]) -> dict[str, Any]:
    material_placeholder = f"/Game/Materials/M_{slugify(effect).replace('-', '_')}_{slugify(layer).replace('-', '_')}"
    texture_commands = []
    for texture in textures:
        role = texture.get("role") or "sprite"
        grid = f" --grid {texture['grid']}" if texture.get("grid") else ""
        texture_commands.append(
            f"python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py <path-to-{texture['name']}> --role {role}{grid} --effect {effect} --markdown"
        )
    references = ["references/material-audit-workflow.md", "references/texture-vs-compute.md"]
    if profile in {"fire", "energy", "smoke", "heat_haze"}:
        references.append("references/fire-energy-material-playbook.md")
    if profile == "water":
        references.append("references/complex-water-material-playbook.md")
    if profile in {"decal", "post_process", "ui", "foliage", "glass", "landscape"}:
        references.append("references/material-domain-and-rendering-contracts.md")
    return {
        "references_to_read": list(dict.fromkeys(references)),
        "commands": [
            f"python D:/Skills/skills/unreal-material-artist/tools/material_audit.py {material_placeholder} --project <UE_PROJECT> --markdown",
            f"python D:/Skills/skills/unreal-material-artist/tools/material_domain_audit.py {material_placeholder} --project <UE_PROJECT> --markdown",
        ],
        "texture_commands": texture_commands,
        "acceptance_checks": [
            "Material route matches the selected domain, blend mode, shading model, and expected outputs.",
            "Reference-critical color, silhouette, roughness, alpha, and motion traits are represented by graph logic or texture assets.",
            "Every required texture has a source, QA report, and role-correct UE import setting.",
            "Preview was captured on the intended carrier before cost optimization.",
            "Optimization notes separate no-look-change fixes from visible tradeoff variants.",
        ],
    }


def material_contract_seed(plan: dict[str, Any]) -> dict[str, Any]:
    route = plan["material_route"]
    carrier = plan["carrier_contract"]
    budgets = plan["budgets"]
    return {
        "tool": "material_contract",
        "version": 1,
        "created_utc": utc_now_iso(),
        "effect": plan["effect"],
        "layer": plan["layer"],
        "owner_model": {
            "vfx_lead": "niagara-vfx-artist",
            "material_specialist": "unreal-material-artist",
        },
        "carrier": {
            "renderer": carrier["carrier"],
            "uv_expectations": carrier["uv_expectations"],
            "particle_inputs": carrier["particle_inputs"],
            "dynamic_parameters": carrier["dynamic_parameters"],
            "sort_or_depth_notes": route["sort_or_depth_notes"],
        },
        "material": {
            "domain": route["domain"],
            "blend_mode": route["blend_mode"],
            "shading_model": route["shading_model"],
            "two_sided": route["two_sided"],
            "expected_outputs": route["expected_outputs"],
            "usage_flags": route["usage_flags"],
        },
        "textures": [
            {
                "name": item["name"],
                "role": item["role"],
                "channels": item["channels"],
                "resolution": item["resolution"],
                "grid": item.get("grid", ""),
                "srgb": item.get("srgb"),
                "source": item.get("source_action", ""),
            }
            for item in plan["texture_requirements"]
        ],
        "parameters": plan["parameters"],
        "budgets": budgets,
        "acceptance": plan["audit_plan"]["acceptance_checks"],
        "notes": f"Generated from reference_to_material_plan. Plan path: {plan.get('plan_path', '')}",
    }


def build_findings(plan: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    if not plan["source"]["references"] and not plan["source"]["source_urls"]:
        add("warning", "no_reference_asset", "No reference image/path or source URL was recorded.")
    for ref in plan["source"]["references"]:
        if not ref.get("exists"):
            add("warning", "missing_reference_file", f"Reference path does not exist: {ref.get('path')}")
    if not plan["visual_contract"]["observations"]:
        add(
            "warning",
            "no_visual_observations",
            "No explicit visual observations were supplied; this is a route scaffold, not a full visual readback.",
        )
    if plan["source"]["analysis_mode"] == "heuristic_from_metadata_and_text":
        add("info", "heuristic_plan", "Profile and route were inferred from text, filenames, and CLI options.")
    if plan["profile"] in {"fire", "smoke", "energy"} and not any(texture.get("role") == "flipbook" for texture in plan["texture_requirements"]):
        add("warning", "missing_flipbook", "This profile often needs a flipbook or richer animated mask plan.")
    return findings


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    text_blob = " ".join(
        [
            args.effect,
            args.layer,
            args.target or "",
            args.notes or "",
            " ".join(args.reference or []),
            " ".join(args.source_url or []),
            " ".join(args.style_tag or []),
            " ".join(args.observation or []),
        ]
    )
    profile = infer_profile(text_blob, args.profile)
    carrier = infer_carrier(profile, args.carrier)
    route = route_for(profile, carrier)
    budgets = budget_for(profile, args.platform)
    if args.instruction_budget is not None:
        budgets["instruction_budget"] = args.instruction_budget
    if args.sampler_budget is not None:
        budgets["sampler_budget"] = args.sampler_budget
    if args.texture_memory_budget_mb is not None:
        budgets["texture_memory_budget_mb"] = args.texture_memory_budget_mb

    ctx = resolve_root_context(args.root)
    cache_dir = ctx.material_root / "reference-cache" / slugify(args.effect) if args.cache_reference else None
    references = [reference_record(Path(raw).expanduser(), cache_dir) for raw in args.reference]
    textures = texture_requirements_for(args.effect, profile)
    textures.extend(parse_texture_override(item) for item in args.texture)
    parameters = parameters_for(profile)
    parameters.extend(parse_parameter_override(item) for item in args.parameter)
    preview_plan = preview_plan_for(args.effect, args.layer, carrier, profile, parameters)
    audit_plan = audit_plan_for(args.effect, args.layer, profile, textures)
    uv_defaults = {
        "sprite": "Sprite UV0; SubUV if flipbook texture is used.",
        "ribbon": "Ribbon UV along length; verify tiling and trail direction.",
        "mesh": "Mesh UV0 unless the reference needs world projection.",
        "decal": "Projected decal UV; edge falloff driven by opacity.",
        "surface": "Mesh UV0 plus optional world/detail coordinates.",
        "landscape": "Landscape layer coordinates or RVT route.",
        "ui": "Widget UV space.",
        "post_process": "Screen UV.",
    }
    plan: dict[str, Any] = {
        "tool": "reference_to_material_plan",
        "version": 1,
        "created_utc": utc_now_iso(),
        "effect": args.effect,
        "layer": args.layer,
        "profile": profile,
        "source": {
            "reference_kind": args.reference_kind,
            "analysis_mode": "heuristic_from_metadata_and_text",
            "target_description": args.target,
            "source_urls": args.source_url,
            "references": references,
            "notes": args.notes,
        },
        "visual_contract": {
            "style_tags": args.style_tag,
            "observations": args.observation,
            "must_match": split_csv(args.must_match),
            "acceptable_tradeoffs": split_csv(args.acceptable_tradeoff),
            "open_questions": split_csv(args.open_question),
        },
        "carrier_contract": {
            "carrier": carrier,
            "uv_expectations": args.uv or uv_defaults.get(carrier, "Confirm UV contract from the reference."),
            "particle_inputs": ["ParticleColor"] if carrier in {"sprite", "ribbon", "mesh"} else [],
            "dynamic_parameters": [item for item in route["dynamic_inputs"] if item != "ParticleColor"],
            "runtime_owner": "Niagara/runtime" if carrier in {"sprite", "ribbon", "mesh"} else "Material/actor instance",
        },
        "material_route": route,
        "texture_requirements": textures,
        "parameters": parameters,
        "budgets": budgets,
        "preview_plan": preview_plan,
        "audit_plan": audit_plan,
        "next_actions": [
            "Review the plan against the actual reference and add missing observations.",
            "Search approved material asset library entries before generating any generic texture.",
            "Generate or source missing custom textures, then run texture_asset_report.py.",
            "Build the first material route and preview on the planned carrier.",
            "Run material_audit.py and material_domain_audit.py before accepting the material.",
        ],
    }
    plan["findings"] = build_findings(plan)
    return plan


def render_markdown(plan: dict[str, Any]) -> str:
    route = plan["material_route"]
    carrier = plan["carrier_contract"]
    budgets = plan["budgets"]
    lines = [
        f"# Reference To Material Plan: {plan['effect']} / {plan['layer']}",
        "",
        f"- Profile: `{plan['profile']}`",
        f"- Reference kind: `{plan['source']['reference_kind']}`",
        f"- Analysis mode: `{plan['source']['analysis_mode']}`",
        f"- Target: {plan['source']['target_description'] or 'not specified'}",
        "",
        "## Material Route",
        "",
        f"- Carrier: `{carrier['carrier']}`",
        f"- UV expectations: {carrier['uv_expectations']}",
        f"- Domain: `{route['domain']}`",
        f"- Blend mode: `{route['blend_mode']}`",
        f"- Shading model: `{route['shading_model']}`",
        f"- Two sided: `{route['two_sided']}`",
        f"- Outputs: {', '.join(route['expected_outputs'])}",
        f"- Usage flags: {', '.join(route['usage_flags']) or 'none'}",
        "",
        "## Texture Requirements",
        "",
    ]
    for texture in plan["texture_requirements"]:
        lines.append(
            f"- `{texture['name']}` role=`{texture['role']}` channels=`{texture['channels']}` "
            f"size=`{texture['resolution']}` sRGB=`{texture.get('srgb')}` source=`{texture.get('source_action', '')}`"
        )
    lines.extend(["", "## Parameters", ""])
    for param in plan["parameters"]:
        lines.append(
            f"- `{param['name']}` {param['type']} default=`{param.get('default', '')}` "
            f"range=`{param.get('range', '') or 'n/a'}` owner=`{param.get('owner', '') or 'n/a'}`: {param.get('purpose', '')}"
        )
    lines.extend(
        [
            "",
            "## Preview Plan",
            "",
            f"- Primary render: `{plan['preview_plan']['primary_render_command']}`",
        ]
    )
    for command in plan["preview_plan"]["sweep_commands"]:
        lines.append(f"- Sweep: `{command}`")
    lines.extend(
        [
            "",
            "## Audit Plan",
            "",
            f"- References: {', '.join(plan['audit_plan']['references_to_read'])}",
        ]
    )
    for command in plan["audit_plan"]["commands"]:
        lines.append(f"- Command: `{command}`")
    for command in plan["audit_plan"]["texture_commands"]:
        lines.append(f"- Texture: `{command}`")
    lines.extend(
        [
            "",
            "## Budgets",
            "",
            f"- Platform: `{budgets['platform']}`",
            f"- Instruction budget: `{budgets['instruction_budget']}`",
            f"- Sampler budget: `{budgets['sampler_budget']}`",
            f"- Texture memory budget MB: `{budgets['texture_memory_budget_mb']}`",
            f"- Overdraw risk: `{budgets['overdraw_risk']}`",
            "",
            "## Findings",
            "",
        ]
    )
    if plan["findings"]:
        for finding in plan["findings"]:
            lines.append(f"- [{finding['severity']}] `{finding['rule']}` {finding['message']}")
    else:
        lines.append("- No first-pass findings.")
    lines.extend(["", "## Acceptance Checks", ""])
    lines.extend(f"- {item}" for item in plan["audit_plan"]["acceptance_checks"])
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {item}" for item in plan["next_actions"])
    return "\n".join(lines).rstrip() + "\n"


def command_new(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    plan = build_plan(args)
    stem = slugify(f"{args.effect}-{args.layer}")
    out = Path(args.out) if args.out else default_report_path(ctx, "plans", stem, "reference-to-material-plan", ".json")
    plan["plan_path"] = str(out)
    save_json(out, plan)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(plan))
    if args.emit_contract:
        contract = material_contract_seed(plan)
        contract["findings"] = validate_contract(contract)
        contract_out = default_report_path(ctx, "contracts", stem, "material-contract", ".json")
        save_json(contract_out, contract)
        if args.markdown:
            from .material_contract import render_markdown as render_contract_markdown

            write_text(contract_out.with_suffix(".md"), render_contract_markdown(contract, contract["findings"]))
        plan["material_contract_path"] = str(contract_out)
        save_json(out, plan)
    print(out)
    return 1 if any(item["severity"] == "error" for item in plan["findings"]) else 0


def validate_plan(plan: dict[str, Any]) -> list[dict[str, str]]:
    findings = build_findings(plan)

    def add(severity: str, rule: str, message: str) -> None:
        findings.append({"severity": severity, "rule": rule, "message": message})

    for key in ("effect", "layer", "profile", "material_route", "texture_requirements", "parameters", "preview_plan", "audit_plan"):
        if key not in plan:
            add("error", "missing_key", f"Plan is missing `{key}`.")
    route = plan.get("material_route") or {}
    for key in ("domain", "blend_mode", "shading_model", "expected_outputs"):
        if not route.get(key):
            add("error", "missing_material_route", f"Material route is missing `{key}`.")
    if not plan.get("texture_requirements"):
        add("warning", "missing_texture_plan", "Plan has no texture requirements.")
    if not plan.get("preview_plan", {}).get("primary_render_command"):
        add("warning", "missing_preview_command", "Plan has no primary preview command.")
    return findings


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.plan)
    plan = json.loads(path.read_text(encoding="utf-8"))
    findings = validate_plan(plan)
    plan["findings"] = findings
    if args.markdown:
        out = Path(args.out) if args.out else path.with_suffix(".md")
        write_text(out, render_markdown(plan))
        print(out)
    else:
        print(json.dumps({"findings": findings}, ensure_ascii=False, indent=2))
    return 1 if any(item["severity"] == "error" for item in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turn a material reference target into a structured Unreal material work plan.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create a reference-driven material plan.")
    new.add_argument("--root", default="auto")
    new.add_argument("--effect", required=True)
    new.add_argument("--layer", default="MainMaterial")
    new.add_argument("--reference", action="append", default=[], help="Local reference image, case-study screenshot, or tutorial screenshot path.")
    new.add_argument("--cache-reference", action="store_true", help="Copy existing local reference files into material-delivery/reference-cache.")
    new.add_argument("--reference-kind", default="image", choices=["image", "case-study", "tutorial", "video-frame", "online-reference", "description"])
    new.add_argument("--source-url", action="append", default=[])
    new.add_argument("--target", default="", help="Short visual target description.")
    new.add_argument("--profile", default="auto", choices=VALID_PROFILES)
    new.add_argument("--carrier", default="auto", choices=VALID_CARRIERS)
    new.add_argument("--platform", default="PC")
    new.add_argument("--uv", default="")
    new.add_argument("--style-tag", action="append", default=[])
    new.add_argument("--observation", action="append", default=[], help="Observed visual evidence from the reference.")
    new.add_argument("--must-match", default="", help="Comma-separated visual traits that must survive implementation.")
    new.add_argument("--acceptable-tradeoff", default="", help="Comma-separated visible tradeoffs that are acceptable.")
    new.add_argument("--open-question", default="", help="Comma-separated questions that block full visual certainty.")
    new.add_argument("--texture", action="append", default=[], help="Override/add texture as name|role|channels|resolution|srgb|source_action|grid.")
    new.add_argument("--parameter", action="append", default=[], help="Override/add parameter as name|type|default|range|owner|purpose.")
    new.add_argument("--instruction-budget", type=int)
    new.add_argument("--sampler-budget", type=int)
    new.add_argument("--texture-memory-budget-mb", type=float)
    new.add_argument("--notes", default="")
    new.add_argument("--emit-contract", action="store_true")
    new.add_argument("--out")
    new.add_argument("--markdown", action="store_true")
    new.set_defaults(func=command_new)

    validate = sub.add_parser("validate", help="Validate an existing reference-to-material plan.")
    validate.add_argument("plan")
    validate.add_argument("--out")
    validate.add_argument("--markdown", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
