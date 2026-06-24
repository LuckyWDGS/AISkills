from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from .bridge import BridgeClient
from .core import resolve_root_context, save_json, slugify, utc_now_iso, write_text


RECIPE_ALIASES = {
    "fire": "fire_flipbook",
    "flame": "fire_flipbook",
    "fire-flipbook": "fire_flipbook",
    "fire_ribbon": "fire_ribbon_additive",
    "flame_ribbon": "fire_ribbon_additive",
    "ribbon_fire": "fire_ribbon_additive",
    "ribbon_flame": "fire_ribbon_additive",
    "fire_ribbon_additive": "fire_ribbon_additive",
    "flame_trail": "fire_ribbon_additive",
    "fire_ribbon_android": "fire_ribbon_additive_android",
    "fire_ribbon_mobile": "fire_ribbon_additive_android",
    "fire_ribbon_additive_android": "fire_ribbon_additive_android",
    "flame_trail_android": "fire_ribbon_additive_android",
    "android_fire_ribbon": "fire_ribbon_additive_android",
    "mobile_fire_ribbon": "fire_ribbon_additive_android",
    "decal": "decal_stain",
    "stain": "decal_stain",
    "decal-stain": "decal_stain",
    "foliage": "two_sided_foliage",
    "two-sided-foliage": "two_sided_foliage",
    "water": "basic_water",
    "basic-water": "basic_water",
    "ribbon": "energy_ribbon",
    "energy-ribbon": "energy_ribbon",
    "dissolve": "dissolve_edge",
    "dissolve-edge": "dissolve_edge",
}


MATERIAL_USAGE_FLAG_ENUMS = {
    "beamtrails": "MATUSAGE_BEAM_TRAILS",
    "clothing": "MATUSAGE_CLOTHING",
    "editorcompositing": "MATUSAGE_EDITOR_COMPOSITING",
    "geometrycache": "MATUSAGE_GEOMETRY_CACHE",
    "geometrycollections": "MATUSAGE_GEOMETRY_COLLECTIONS",
    "hairstrands": "MATUSAGE_HAIR_STRANDS",
    "heterogeneousvolumes": "MATUSAGE_HETEROGENEOUS_VOLUMES",
    "instancedskinnedmesh": "MATUSAGE_INSTANCED_SKINNED_MESH",
    "instancedstaticmesh": "MATUSAGE_INSTANCED_STATIC_MESHES",
    "instancedstaticmeshes": "MATUSAGE_INSTANCED_STATIC_MESHES",
    "lidarpointcloud": "MATUSAGE_LIDAR_POINT_CLOUD",
    "meshdeformer": "MATUSAGE_MESH_DEFORMER",
    "meshparticles": "MATUSAGE_MESH_PARTICLES",
    "morphtargets": "MATUSAGE_MORPH_TARGETS",
    "nanite": "MATUSAGE_NANITE",
    "neuralnetworks": "MATUSAGE_NEURAL_NETWORKS",
    "niagarameshparticles": "MATUSAGE_NIAGARA_MESH_PARTICLES",
    "niagararibbons": "MATUSAGE_NIAGARA_RIBBONS",
    "niagarasprites": "MATUSAGE_NIAGARA_SPRITES",
    "particlesprites": "MATUSAGE_PARTICLE_SPRITES",
    "skeletalmesh": "MATUSAGE_SKELETAL_MESH",
    "splinemesh": "MATUSAGE_SPLINE_MESH",
    "splinemeshes": "MATUSAGE_SPLINE_MESH",
    "staticlighting": "MATUSAGE_STATIC_LIGHTING",
    "staticmesh": "MATUSAGE_STATIC_MESH",
    "virtualheightfieldmesh": "MATUSAGE_VIRTUAL_HEIGHTFIELD_MESH",
    "volumetriccloud": "MATUSAGE_VOLUMETRIC_CLOUD",
    "voxels": "MATUSAGE_VOXELS",
    "water": "MATUSAGE_WATER",
}


RECIPE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "fire_flipbook": {
        "title": "Fire flipbook material route",
        "intent": "Unlit additive fire or flame sprite/ribbon layer with SubUV flipbook identity.",
        "default_asset_prefix": "M_FireFlipbook",
        "route": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraSprites"],
        },
        "carrier": "sprite",
        "texture_requirements": [
            {
                "slot": "fire_flipbook",
                "name": "T_FireFlipbook_VFX",
                "channels": "RGBA; RGB emissive shape, A opacity when available",
                "recommended_size": "1024 or 2048 atlas, power-of-two cells",
                "sRGB": True,
                "compression": "Default or HDR if very bright source is baked",
                "required": True,
            },
            {
                "slot": "edge_noise",
                "name": "T_EdgeNoise_VFX",
                "channels": "R breakup mask",
                "recommended_size": "512 tileable grayscale",
                "sRGB": False,
                "compression": "Masks",
                "required": False,
            },
        ],
        "parameters": [
            {"name": "V_FireColor", "type": "Vector", "default": "(R=1.0,G=0.38,B=0.08,A=1.0)", "purpose": "Main tint for emissive fire body."},
            {"name": "S_EmissiveIntensity", "type": "Scalar", "default": "8.0", "purpose": "Fire brightness multiplier."},
            {"name": "S_Opacity", "type": "Scalar", "default": "1.0", "purpose": "Global alpha trim."},
            {"name": "S_DynamicEmissiveBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param1 emissive scale contribution."},
            {"name": "S_DynamicOpacityBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param2 opacity scale contribution."},
            {"name": "S_EdgeBreakup", "type": "Scalar", "default": "0.25", "purpose": "Optional edge-noise strength."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "fire_color", "parameter_name": "V_FireColor", "default_value": "(R=1.0,G=0.38,B=0.08,A=1.0)", "x": -760, "y": -120},
            {"template": "particle_color", "alias": "particle_color", "x": -760, "y": 60},
            {"template": "scalar_parameter", "alias": "emissive_intensity", "parameter_name": "S_EmissiveIntensity", "default_value": "8.0", "x": -760, "y": 40},
            {"template": "dynamic_parameter", "alias": "dynamic_parameter", "x": -760, "y": 240},
            {"template": "scalar_parameter", "alias": "dynamic_emissive_boost", "parameter_name": "S_DynamicEmissiveBoost", "default_value": "0.0", "x": -760, "y": 390},
            {"template": "constant_scalar", "alias": "emissive_scale_one", "value": "1.0", "x": -760, "y": 520},
            {"template": "scalar_parameter", "alias": "dynamic_opacity_boost", "parameter_name": "S_DynamicOpacityBoost", "default_value": "0.0", "x": -760, "y": 650},
            {"template": "constant_scalar", "alias": "opacity_scale_one", "value": "1.0", "x": -760, "y": 780},
            {"template": "multiply_pair", "alias": "tinted_particle_color", "left_expression": "fire_color", "right_expression": "particle_color", "x": -500, "y": -100},
            {"template": "multiply_pair", "alias": "emissive_color", "left_expression": "tinted_particle_color", "right_expression": "emissive_intensity", "x": -220, "y": -80},
            {"template": "multiply_pair", "alias": "dynamic_emissive_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param1", "right_expression": "dynamic_emissive_boost", "x": -500, "y": 360},
            {"template": "add_pair", "alias": "dynamic_emissive_scale", "left_expression": "emissive_scale_one", "right_expression": "dynamic_emissive_delta", "x": -220, "y": 360},
            {"template": "multiply_pair", "alias": "emissive_with_dynamic", "left_expression": "emissive_color", "right_expression": "dynamic_emissive_scale", "x": 60, "y": -80, "output_property": "MP_EmissiveColor"},
            {"template": "scalar_parameter", "alias": "opacity", "parameter_name": "S_Opacity", "default_value": "1.0", "x": -460, "y": 220},
            {"template": "multiply_pair", "alias": "dynamic_opacity_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param2", "right_expression": "dynamic_opacity_boost", "x": -500, "y": 620},
            {"template": "add_pair", "alias": "dynamic_opacity_scale", "left_expression": "opacity_scale_one", "right_expression": "dynamic_opacity_delta", "x": -220, "y": 620},
            {"template": "multiply_pair", "alias": "opacity_with_dynamic", "left_expression": "opacity", "right_expression": "dynamic_opacity_scale", "x": 60, "y": 220, "output_property": "MP_Opacity"},
        ],
        "preview": {"carrier": "sprite", "with_complexity": True},
        "audit_focus": ["SubUV/flipbook identity", "camera-facing one-sided sprite contract", "overdraw", "alpha edge", "emissive readability"],
    },
    "fire_ribbon_additive": {
        "title": "Additive Niagara ribbon fire trail route",
        "intent": "Unlit additive Niagara Ribbon flame/energy trail with one packed R/G/B mask, ParticleColor lifetime fade, and PC/Android fallback controls.",
        "default_asset_prefix": "M_FireRibbonAdditive",
        "route": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": True,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "carrier": "ribbon",
        "texture_requirements": [
            {
                "slot": "fire_ribbon_mask",
                "name": "T_FireRibbonMask_VFX",
                "channels": "R core/tongue filament, G main flame body, B distortion/breakup noise, A optional opacity/detail",
                "recommended_size": "512x256 or 1024x256; power-of-two where practical; Android fallback 256-512",
                "sRGB": False,
                "compression": "Masks",
                "required": True,
            }
        ],
        "parameters": [
            {"name": "Texture_Mask", "type": "Texture2D", "default": "T_FireRibbonMask_VFX", "purpose": "Packed mask: R=core/tongues, G=main flame body, B=distortion/breakup."},
            {"name": "Color_Main", "type": "Vector", "default": "(R=1.0,G=0.35,B=0.05,A=1.0)", "purpose": "Main flame color."},
            {"name": "Color_Core", "type": "Vector", "default": "(R=1.0,G=0.82,B=0.28,A=1.0)", "purpose": "Hot core/filament color."},
            {"name": "Intensity", "type": "Scalar", "default": "4.0", "purpose": "Overall emissive intensity. Android fallback starts around 1.5."},
            {"name": "Core_Boost", "type": "Scalar", "default": "3.0", "purpose": "R-channel core/filament boost. Android fallback starts around 1.5."},
            {"name": "OpacityScale", "type": "Scalar", "default": "1.0", "purpose": "Global opacity multiplier before ParticleColor alpha and DynamicParameter scale."},
            {"name": "Width_Power", "type": "Scalar", "default": "1.4", "purpose": "Controls generated centered raw-V width falloff after clamp."},
            {"name": "Distortion_Intensity", "type": "Scalar", "default": "0.06", "purpose": "B-channel UV distortion strength; keep near 0.02 for Android fallback."},
            {"name": "Speed_Main", "type": "Scalar", "default": "1.5", "purpose": "Main mask panner speed along raw ribbon U or Flow_UV.y art-space remap."},
            {"name": "Speed_Noise", "type": "Scalar", "default": "0.15", "purpose": "Slow B-channel noise panner speed."},
            {"name": "Tiling_Length", "type": "Scalar", "default": "3.0", "purpose": "Generated length-axis mask tiling before panner and optional Flow_UV remap."},
            {"name": "Use_Flow_UV_Remap", "type": "Scalar", "default": "0.0", "purpose": "0 uses raw ribbon U=length/V=width; 1 samples art textures as Flow_UV=float2(V,U)."},
            {"name": "S_DynamicEmissiveBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param1 emissive scale contribution."},
            {"name": "S_DynamicOpacityBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param2 opacity scale contribution."},
        ],
        "builder_templates": [
            {"template": "texture_coordinate", "alias": "raw_uv", "x": -1500, "y": -900},
            {"template": "component_mask", "alias": "raw_u", "source_expression": "raw_uv", "mask": "R", "x": -1240, "y": -940},
            {"template": "component_mask", "alias": "raw_v", "source_expression": "raw_uv", "mask": "G", "x": -1240, "y": -800},
            {"template": "scalar_parameter", "alias": "tiling_length", "parameter_name": "Tiling_Length", "default_value": "3.0", "x": -1500, "y": -640},
            {"template": "multiply_pair", "alias": "uv_u_tiled", "left_expression": "raw_u", "right_expression": "tiling_length", "x": -1240, "y": -660},
            {"template": "append_vector", "alias": "flow_uv_raw", "left_expression": "uv_u_tiled", "right_expression": "raw_v", "x": -980, "y": -900},
            {"template": "append_vector", "alias": "flow_uv_remap", "left_expression": "raw_v", "right_expression": "uv_u_tiled", "x": -980, "y": -720},
            {"template": "scalar_parameter", "alias": "use_flow_uv_remap", "parameter_name": "Use_Flow_UV_Remap", "default_value": "0.0", "x": -980, "y": -560},
            {"template": "time", "alias": "time", "x": -1500, "y": -420},
            {"template": "scalar_parameter", "alias": "speed_main", "parameter_name": "Speed_Main", "default_value": "1.5", "x": -1500, "y": -280},
            {"template": "scalar_parameter", "alias": "speed_noise", "parameter_name": "Speed_Noise", "default_value": "0.15", "x": -1500, "y": -120},
            {"template": "multiply_pair", "alias": "time_main", "left_expression": "time", "right_expression": "speed_main", "x": -1240, "y": -300},
            {"template": "multiply_pair", "alias": "time_noise", "left_expression": "time", "right_expression": "speed_noise", "x": -1240, "y": -120},
            {"template": "panner", "alias": "main_panner_raw", "coordinate_expression": "flow_uv_raw", "time_expression": "time_main", "speed_x": "1.0", "speed_y": "0.0", "x": -720, "y": -900},
            {"template": "panner", "alias": "main_panner_remap", "coordinate_expression": "flow_uv_remap", "time_expression": "time_main", "speed_x": "0.0", "speed_y": "1.0", "x": -720, "y": -720},
            {"template": "lerp", "alias": "main_panned_uv", "left_expression": "main_panner_raw", "right_expression": "main_panner_remap", "alpha_expression": "use_flow_uv_remap", "x": -460, "y": -820},
            {"template": "panner", "alias": "noise_panner_raw", "coordinate_expression": "flow_uv_raw", "time_expression": "time_noise", "speed_x": "1.0", "speed_y": "0.0", "x": -720, "y": -520},
            {"template": "panner", "alias": "noise_panner_remap", "coordinate_expression": "flow_uv_remap", "time_expression": "time_noise", "speed_x": "0.0", "speed_y": "1.0", "x": -720, "y": -340},
            {"template": "lerp", "alias": "noise_uv", "left_expression": "noise_panner_raw", "right_expression": "noise_panner_remap", "alpha_expression": "use_flow_uv_remap", "x": -460, "y": -440},
            {"template": "texture_parameter_2d", "alias": "mask_texture_noise", "parameter_name": "Texture_Mask", "default_texture_name": "T_FireRibbonMask_VFX", "coordinates_expression": "noise_uv", "x": -180, "y": -420},
            {"template": "component_mask", "alias": "mask_b_breakup", "source_expression": "mask_texture_noise", "mask": "B", "x": 80, "y": -420},
            {"template": "constant_scalar", "alias": "half_for_distortion", "value": "0.5", "x": -180, "y": -220},
            {"template": "scalar_parameter", "alias": "distortion_intensity", "parameter_name": "Distortion_Intensity", "default_value": "0.06", "x": -180, "y": -60},
            {"template": "subtract_pair", "alias": "mask_b_centered", "left_expression": "mask_b_breakup", "right_expression": "half_for_distortion", "x": 80, "y": -240},
            {"template": "multiply_pair", "alias": "distortion_amount", "left_expression": "mask_b_centered", "right_expression": "distortion_intensity", "x": 340, "y": -220},
            {"template": "constant_scalar", "alias": "zero_offset", "value": "0.0", "x": 80, "y": -40},
            {"template": "append_vector", "alias": "distortion_offset_raw", "left_expression": "zero_offset", "right_expression": "distortion_amount", "x": 600, "y": -260},
            {"template": "append_vector", "alias": "distortion_offset_remap", "left_expression": "distortion_amount", "right_expression": "zero_offset", "x": 600, "y": -80},
            {"template": "lerp", "alias": "distortion_offset", "left_expression": "distortion_offset_raw", "right_expression": "distortion_offset_remap", "alpha_expression": "use_flow_uv_remap", "x": 860, "y": -160},
            {"template": "add_pair", "alias": "main_uv", "left_expression": "main_panned_uv", "right_expression": "distortion_offset", "x": 1120, "y": -520},
            {"template": "texture_parameter_2d", "alias": "mask_texture", "parameter_name": "Texture_Mask", "default_texture_name": "T_FireRibbonMask_VFX", "coordinates_expression": "main_uv", "x": 1400, "y": -520},
            {"template": "component_mask", "alias": "mask_r_core", "source_expression": "mask_texture", "mask": "R", "x": 1660, "y": -560},
            {"template": "component_mask", "alias": "mask_g_body", "source_expression": "mask_texture", "mask": "G", "x": 1660, "y": -410},
            {"template": "constant_scalar", "alias": "half_width", "value": "0.5", "x": -980, "y": -210},
            {"template": "constant_scalar", "alias": "width_double", "value": "2.0", "x": -980, "y": -60},
            {"template": "scalar_parameter", "alias": "width_power", "parameter_name": "Width_Power", "default_value": "1.4", "x": -980, "y": 100},
            {"template": "subtract_pair", "alias": "width_centered", "left_expression": "raw_v", "right_expression": "half_width", "x": -720, "y": -180},
            {"template": "abs", "alias": "width_abs", "source_expression": "width_centered", "x": -460, "y": -160},
            {"template": "multiply_pair", "alias": "width_edge_distance", "left_expression": "width_abs", "right_expression": "width_double", "x": -200, "y": -140},
            {"template": "one_minus", "alias": "width_center_fade", "source_expression": "width_edge_distance", "x": 60, "y": -120},
            {"template": "clamp", "alias": "width_clamped", "source_expression": "width_center_fade", "min": "0.0", "max": "1.0", "x": 320, "y": -100},
            {"template": "power_pair", "alias": "width_falloff", "base_expression": "width_clamped", "exponent_expression": "width_power", "x": 580, "y": -100},
            {"template": "vector_parameter", "alias": "main_color", "parameter_name": "Color_Main", "default_value": "(R=1.0,G=0.35,B=0.05,A=1.0)", "x": -980, "y": 260},
            {"template": "vector_parameter", "alias": "core_color", "parameter_name": "Color_Core", "default_value": "(R=1.0,G=0.82,B=0.28,A=1.0)", "x": -980, "y": 420},
            {"template": "particle_color", "alias": "particle_color", "x": -980, "y": 580},
            {"template": "component_mask", "alias": "particle_alpha", "source_expression": "particle_color", "mask": "A", "x": -720, "y": 640},
            {"template": "dynamic_parameter", "alias": "dynamic_parameter", "x": -980, "y": 820},
            {"template": "scalar_parameter", "alias": "intensity", "parameter_name": "Intensity", "default_value": "4.0", "x": -720, "y": 260},
            {"template": "scalar_parameter", "alias": "core_boost", "parameter_name": "Core_Boost", "default_value": "3.0", "x": -720, "y": 420},
            {"template": "scalar_parameter", "alias": "opacity_scale", "parameter_name": "OpacityScale", "default_value": "1.0", "x": -720, "y": 720},
            {"template": "scalar_parameter", "alias": "dynamic_emissive_boost", "parameter_name": "S_DynamicEmissiveBoost", "default_value": "0.0", "x": -720, "y": 980},
            {"template": "scalar_parameter", "alias": "dynamic_opacity_boost", "parameter_name": "S_DynamicOpacityBoost", "default_value": "0.0", "x": -720, "y": 1140},
            {"template": "constant_scalar", "alias": "emissive_scale_one", "value": "1.0", "x": -980, "y": 980},
            {"template": "constant_scalar", "alias": "opacity_scale_one", "value": "1.0", "x": -980, "y": 1140},
            {"template": "multiply_pair", "alias": "main_color_particle", "left_expression": "main_color", "right_expression": "particle_color", "x": -460, "y": 240},
            {"template": "multiply_pair", "alias": "body_colored", "left_expression": "main_color_particle", "right_expression": "mask_g_body", "x": -200, "y": 240},
            {"template": "multiply_pair", "alias": "body_with_width", "left_expression": "body_colored", "right_expression": "width_falloff", "x": 60, "y": 240},
            {"template": "multiply_pair", "alias": "body_emissive", "left_expression": "body_with_width", "right_expression": "intensity", "x": 320, "y": 240},
            {"template": "multiply_pair", "alias": "core_colored", "left_expression": "core_color", "right_expression": "mask_r_core", "x": -200, "y": 420},
            {"template": "multiply_pair", "alias": "core_with_width", "left_expression": "core_colored", "right_expression": "width_falloff", "x": 60, "y": 420},
            {"template": "multiply_pair", "alias": "core_emissive", "left_expression": "core_with_width", "right_expression": "core_boost", "x": 320, "y": 420},
            {"template": "add_pair", "alias": "flame_emissive_base", "left_expression": "body_emissive", "right_expression": "core_emissive", "x": 580, "y": 320},
            {"template": "multiply_pair", "alias": "dynamic_emissive_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param1", "right_expression": "dynamic_emissive_boost", "x": -460, "y": 960},
            {"template": "add_pair", "alias": "dynamic_emissive_scale", "left_expression": "emissive_scale_one", "right_expression": "dynamic_emissive_delta", "x": -200, "y": 960},
            {"template": "multiply_pair", "alias": "flame_emissive", "left_expression": "flame_emissive_base", "right_expression": "dynamic_emissive_scale", "x": 860, "y": 330, "output_property": "MP_EmissiveColor"},
            {"template": "multiply_pair", "alias": "opacity_body_alpha", "left_expression": "mask_g_body", "right_expression": "particle_alpha", "x": -460, "y": 660},
            {"template": "multiply_pair", "alias": "opacity_with_width", "left_expression": "opacity_body_alpha", "right_expression": "width_falloff", "x": -200, "y": 660},
            {"template": "multiply_pair", "alias": "opacity_with_scale", "left_expression": "opacity_with_width", "right_expression": "opacity_scale", "x": 60, "y": 660},
            {"template": "multiply_pair", "alias": "dynamic_opacity_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param2", "right_expression": "dynamic_opacity_boost", "x": -460, "y": 1120},
            {"template": "add_pair", "alias": "dynamic_opacity_scale", "left_expression": "opacity_scale_one", "right_expression": "dynamic_opacity_delta", "x": -200, "y": 1120},
            {"template": "multiply_pair", "alias": "flame_opacity", "left_expression": "opacity_with_scale", "right_expression": "dynamic_opacity_scale", "x": 320, "y": 660, "output_property": "MP_Opacity"},
        ],
        "preview": {"carrier": "ribbon", "with_complexity": True},
        "audit_focus": [
            "ribbon raw U length / raw V width convention",
            "packed mask import: TC_Masks and sRGB=false",
            "ParticleColor.A lifetime fade",
            "DynamicParameter Param1/Param2 sockets",
            "two-sided additive brightness multiplier",
            "Android one-sample fallback",
        ],
    },
    "fire_ribbon_additive_android": {
        "title": "Android one-sample additive Niagara ribbon fire trail route",
        "intent": "Low-tier/Android Niagara Ribbon flame trail fallback with one packed-mask sample, no secondary distortion sample, and conservative emissive defaults.",
        "default_asset_prefix": "M_FireRibbonAdditive_Android",
        "route": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": True,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "carrier": "ribbon",
        "texture_requirements": [
            {
                "slot": "fire_ribbon_mask",
                "name": "T_FireRibbonMask_VFX",
                "channels": "R core/tongue filament, G main flame body and opacity, B optional baked breakup/detail, A optional opacity/detail",
                "recommended_size": "256x128 or 512x256; power-of-two; prefer one packed data texture",
                "sRGB": False,
                "compression": "Masks",
                "required": True,
            }
        ],
        "parameters": [
            {"name": "Texture_Mask", "type": "Texture2D", "default": "T_FireRibbonMask_VFX", "purpose": "Single packed mask sample: R=core/tongues, G=main body/opacity, B/A optional baked detail."},
            {"name": "Color_Main", "type": "Vector", "default": "(R=1.0,G=0.32,B=0.06,A=1.0)", "purpose": "Main flame color tuned for lower HDR intensity."},
            {"name": "Color_Core", "type": "Vector", "default": "(R=1.0,G=0.72,B=0.22,A=1.0)", "purpose": "Hot core/filament color tuned for mobile readability."},
            {"name": "Intensity", "type": "Scalar", "default": "1.5", "purpose": "Conservative emissive intensity for Android/low-tier fallback."},
            {"name": "Core_Boost", "type": "Scalar", "default": "1.5", "purpose": "Conservative R-channel core boost."},
            {"name": "OpacityScale", "type": "Scalar", "default": "0.85", "purpose": "Global opacity multiplier before ParticleColor alpha and DynamicParameter scale."},
            {"name": "Width_Power", "type": "Scalar", "default": "1.2", "purpose": "Controls generated centered raw-V width falloff after clamp."},
            {"name": "Speed_Main", "type": "Scalar", "default": "1.0", "purpose": "Single-sample panner speed along raw ribbon U or Flow_UV.y art-space remap."},
            {"name": "Tiling_Length", "type": "Scalar", "default": "2.0", "purpose": "Generated length-axis mask tiling before panner and optional Flow_UV remap."},
            {"name": "Use_Flow_UV_Remap", "type": "Scalar", "default": "0.0", "purpose": "0 uses raw ribbon U=length/V=width; 1 samples art textures as Flow_UV=float2(V,U)."},
            {"name": "S_DynamicEmissiveBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param1 emissive scale contribution."},
            {"name": "S_DynamicOpacityBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param2 opacity scale contribution."},
        ],
        "builder_templates": [
            {"template": "texture_coordinate", "alias": "raw_uv", "x": -1300, "y": -760},
            {"template": "component_mask", "alias": "raw_u", "source_expression": "raw_uv", "mask": "R", "x": -1040, "y": -800},
            {"template": "component_mask", "alias": "raw_v", "source_expression": "raw_uv", "mask": "G", "x": -1040, "y": -660},
            {"template": "scalar_parameter", "alias": "tiling_length", "parameter_name": "Tiling_Length", "default_value": "2.0", "x": -1300, "y": -520},
            {"template": "multiply_pair", "alias": "uv_u_tiled", "left_expression": "raw_u", "right_expression": "tiling_length", "x": -1040, "y": -540},
            {"template": "append_vector", "alias": "flow_uv_raw", "left_expression": "uv_u_tiled", "right_expression": "raw_v", "x": -820, "y": -760},
            {"template": "append_vector", "alias": "flow_uv_remap", "left_expression": "raw_v", "right_expression": "uv_u_tiled", "x": -820, "y": -600},
            {"template": "scalar_parameter", "alias": "use_flow_uv_remap", "parameter_name": "Use_Flow_UV_Remap", "default_value": "0.0", "x": -820, "y": -420},
            {"template": "time", "alias": "time", "x": -1300, "y": -340},
            {"template": "scalar_parameter", "alias": "speed_main", "parameter_name": "Speed_Main", "default_value": "1.0", "x": -1300, "y": -200},
            {"template": "multiply_pair", "alias": "time_main", "left_expression": "time", "right_expression": "speed_main", "x": -1040, "y": -220},
            {"template": "panner", "alias": "main_panner_raw", "coordinate_expression": "flow_uv_raw", "time_expression": "time_main", "speed_x": "1.0", "speed_y": "0.0", "x": -500, "y": -760},
            {"template": "panner", "alias": "main_panner_remap", "coordinate_expression": "flow_uv_remap", "time_expression": "time_main", "speed_x": "0.0", "speed_y": "1.0", "x": -500, "y": -580},
            {"template": "lerp", "alias": "main_uv", "left_expression": "main_panner_raw", "right_expression": "main_panner_remap", "alpha_expression": "use_flow_uv_remap", "x": -240, "y": -680},
            {"template": "texture_parameter_2d", "alias": "mask_texture", "parameter_name": "Texture_Mask", "default_texture_name": "T_FireRibbonMask_VFX", "coordinates_expression": "main_uv", "x": 260, "y": -620},
            {"template": "component_mask", "alias": "mask_r_core", "source_expression": "mask_texture", "mask": "R", "x": 520, "y": -660},
            {"template": "component_mask", "alias": "mask_g_body", "source_expression": "mask_texture", "mask": "G", "x": 520, "y": -510},
            {"template": "constant_scalar", "alias": "half_width", "value": "0.5", "x": -820, "y": -160},
            {"template": "constant_scalar", "alias": "width_double", "value": "2.0", "x": -820, "y": 0},
            {"template": "scalar_parameter", "alias": "width_power", "parameter_name": "Width_Power", "default_value": "1.2", "x": -820, "y": 160},
            {"template": "subtract_pair", "alias": "width_centered", "left_expression": "raw_v", "right_expression": "half_width", "x": -560, "y": -140},
            {"template": "abs", "alias": "width_abs", "source_expression": "width_centered", "x": -40, "y": -120},
            {"template": "multiply_pair", "alias": "width_edge_distance", "left_expression": "width_abs", "right_expression": "width_double", "x": 180, "y": -100},
            {"template": "one_minus", "alias": "width_center_fade", "source_expression": "width_edge_distance", "x": 700, "y": -80},
            {"template": "clamp", "alias": "width_clamped", "source_expression": "width_center_fade", "min": "0.0", "max": "1.0", "x": 960, "y": -60},
            {"template": "power_pair", "alias": "width_falloff", "base_expression": "width_clamped", "exponent_expression": "width_power", "x": 1220, "y": -60},
            {"template": "vector_parameter", "alias": "main_color", "parameter_name": "Color_Main", "default_value": "(R=1.0,G=0.32,B=0.06,A=1.0)", "x": -560, "y": 260},
            {"template": "vector_parameter", "alias": "core_color", "parameter_name": "Color_Core", "default_value": "(R=1.0,G=0.72,B=0.22,A=1.0)", "x": -560, "y": 420},
            {"template": "particle_color", "alias": "particle_color", "x": -560, "y": 580},
            {"template": "component_mask", "alias": "particle_alpha", "source_expression": "particle_color", "mask": "A", "x": -300, "y": 640},
            {"template": "dynamic_parameter", "alias": "dynamic_parameter", "x": -560, "y": 820},
            {"template": "scalar_parameter", "alias": "intensity", "parameter_name": "Intensity", "default_value": "1.5", "x": -300, "y": 260},
            {"template": "scalar_parameter", "alias": "core_boost", "parameter_name": "Core_Boost", "default_value": "1.5", "x": -300, "y": 420},
            {"template": "scalar_parameter", "alias": "opacity_scale", "parameter_name": "OpacityScale", "default_value": "0.85", "x": -300, "y": 720},
            {"template": "scalar_parameter", "alias": "dynamic_emissive_boost", "parameter_name": "S_DynamicEmissiveBoost", "default_value": "0.0", "x": -300, "y": 980},
            {"template": "scalar_parameter", "alias": "dynamic_opacity_boost", "parameter_name": "S_DynamicOpacityBoost", "default_value": "0.0", "x": -300, "y": 1140},
            {"template": "constant_scalar", "alias": "emissive_scale_one", "value": "1.0", "x": -560, "y": 980},
            {"template": "constant_scalar", "alias": "opacity_scale_one", "value": "1.0", "x": -560, "y": 1140},
            {"template": "multiply_pair", "alias": "main_color_particle", "left_expression": "main_color", "right_expression": "particle_color", "x": -40, "y": 240},
            {"template": "multiply_pair", "alias": "body_colored", "left_expression": "main_color_particle", "right_expression": "mask_g_body", "x": 220, "y": 240},
            {"template": "multiply_pair", "alias": "body_with_width", "left_expression": "body_colored", "right_expression": "width_falloff", "x": 480, "y": 240},
            {"template": "multiply_pair", "alias": "body_emissive", "left_expression": "body_with_width", "right_expression": "intensity", "x": 740, "y": 240},
            {"template": "multiply_pair", "alias": "core_colored", "left_expression": "core_color", "right_expression": "mask_r_core", "x": 220, "y": 420},
            {"template": "multiply_pair", "alias": "core_with_width", "left_expression": "core_colored", "right_expression": "width_falloff", "x": 480, "y": 420},
            {"template": "multiply_pair", "alias": "core_emissive", "left_expression": "core_with_width", "right_expression": "core_boost", "x": 740, "y": 420},
            {"template": "add_pair", "alias": "flame_emissive_base", "left_expression": "body_emissive", "right_expression": "core_emissive", "x": 1000, "y": 320},
            {"template": "multiply_pair", "alias": "dynamic_emissive_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param1", "right_expression": "dynamic_emissive_boost", "x": -40, "y": 960},
            {"template": "add_pair", "alias": "dynamic_emissive_scale", "left_expression": "emissive_scale_one", "right_expression": "dynamic_emissive_delta", "x": 220, "y": 960},
            {"template": "multiply_pair", "alias": "flame_emissive", "left_expression": "flame_emissive_base", "right_expression": "dynamic_emissive_scale", "x": 1260, "y": 330, "output_property": "MP_EmissiveColor"},
            {"template": "multiply_pair", "alias": "opacity_body_alpha", "left_expression": "mask_g_body", "right_expression": "particle_alpha", "x": -40, "y": 660},
            {"template": "multiply_pair", "alias": "opacity_with_width", "left_expression": "opacity_body_alpha", "right_expression": "width_falloff", "x": 220, "y": 660},
            {"template": "multiply_pair", "alias": "opacity_with_scale", "left_expression": "opacity_with_width", "right_expression": "opacity_scale", "x": 480, "y": 660},
            {"template": "multiply_pair", "alias": "dynamic_opacity_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param2", "right_expression": "dynamic_opacity_boost", "x": -40, "y": 1120},
            {"template": "add_pair", "alias": "dynamic_opacity_scale", "left_expression": "opacity_scale_one", "right_expression": "dynamic_opacity_delta", "x": 220, "y": 1120},
            {"template": "multiply_pair", "alias": "flame_opacity", "left_expression": "opacity_with_scale", "right_expression": "dynamic_opacity_scale", "x": 740, "y": 660, "output_property": "MP_Opacity"},
        ],
        "preview": {"carrier": "ribbon", "with_complexity": True},
        "audit_focus": [
            "Android/low-tier one-sample packed-mask route",
            "ribbon raw U length / raw V width convention",
            "packed mask import: TC_Masks and sRGB=false",
            "ParticleColor.A lifetime fade",
            "DynamicParameter Param1/Param2 sockets",
            "two-sided additive brightness multiplier",
        ],
    },
    "decal_stain": {
        "title": "Deferred decal stain material route",
        "intent": "Low-motion dirt, scorch, blood, slime, or impact stain decal with opacity control.",
        "default_asset_prefix": "M_DecalStain",
        "route": {
            "domain": "DeferredDecal",
            "blend_mode": "Translucent",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Opacity", "Roughness"],
            "usage_flags": [],
        },
        "carrier": "decal",
        "texture_requirements": [
            {
                "slot": "decal_mask",
                "name": "T_DecalMask",
                "channels": "RGBA; RGB color or dirt value, A opacity mask",
                "recommended_size": "1024 for hero decals, 512 for common grime",
                "sRGB": True,
                "compression": "Default",
                "required": True,
            }
        ],
        "parameters": [
            {"name": "V_StainColor", "type": "Vector", "default": "(R=0.22,G=0.18,B=0.12,A=1.0)", "purpose": "Main decal stain color."},
            {"name": "S_Opacity", "type": "Scalar", "default": "0.65", "purpose": "Decal opacity."},
            {"name": "S_Roughness", "type": "Scalar", "default": "0.8", "purpose": "Surface roughness contribution."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "stain_color", "parameter_name": "V_StainColor", "default_value": "(R=0.22,G=0.18,B=0.12,A=1.0)", "x": -620, "y": -160, "output_property": "MP_BaseColor"},
            {"template": "scalar_parameter", "alias": "opacity", "parameter_name": "S_Opacity", "default_value": "0.65", "x": -620, "y": 20, "output_property": "MP_Opacity"},
            {"template": "scalar_parameter", "alias": "roughness", "parameter_name": "S_Roughness", "default_value": "0.8", "x": -620, "y": 180, "output_property": "MP_Roughness"},
        ],
        "preview": {"carrier": "decal", "with_complexity": True},
        "audit_focus": ["domain legality", "opacity coverage", "decal sort/fade behavior", "texture alpha"],
    },
    "two_sided_foliage": {
        "title": "Two-sided foliage material route",
        "intent": "Leaf card or thin vegetation surface with alpha mask and subsurface color.",
        "default_asset_prefix": "M_TwoSidedFoliage",
        "route": {
            "domain": "Surface",
            "blend_mode": "Masked",
            "shading_model": "TwoSidedFoliage",
            "two_sided": True,
            "expected_outputs": ["BaseColor", "OpacityMask", "Roughness", "SubsurfaceColor", "Normal"],
            "usage_flags": ["StaticMesh", "Foliage"],
        },
        "carrier": "mesh",
        "texture_requirements": [
            {
                "slot": "base_color_alpha",
                "name": "T_Leaf_BaseColorAlpha",
                "channels": "RGB leaf color, A opacity mask",
                "recommended_size": "1024 or 2048 for hero cards",
                "sRGB": True,
                "compression": "Default",
                "required": True,
            },
            {
                "slot": "normal",
                "name": "T_Leaf_Normal",
                "channels": "Normal XYZ",
                "recommended_size": "match base color or half-size",
                "sRGB": False,
                "compression": "Normalmap",
                "required": False,
            },
        ],
        "parameters": [
            {"name": "V_LeafTint", "type": "Vector", "default": "(R=0.34,G=0.52,B=0.18,A=1.0)", "purpose": "Leaf color tint."},
            {"name": "V_SubsurfaceColor", "type": "Vector", "default": "(R=0.42,G=0.68,B=0.22,A=1.0)", "purpose": "Backlit leaf transmission color."},
            {"name": "S_Roughness", "type": "Scalar", "default": "0.65", "purpose": "Leaf roughness."},
            {"name": "S_OpacityClip", "type": "Scalar", "default": "0.333", "purpose": "Masked clip threshold."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "leaf_tint", "parameter_name": "V_LeafTint", "default_value": "(R=0.34,G=0.52,B=0.18,A=1.0)", "x": -700, "y": -180, "output_property": "MP_BaseColor"},
            {"template": "vector_parameter", "alias": "subsurface", "parameter_name": "V_SubsurfaceColor", "default_value": "(R=0.42,G=0.68,B=0.22,A=1.0)", "x": -700, "y": 0, "output_property": "MP_SubsurfaceColor"},
            {"template": "scalar_parameter", "alias": "roughness", "parameter_name": "S_Roughness", "default_value": "0.65", "x": -700, "y": 180, "output_property": "MP_Roughness"},
            {"template": "scalar_parameter", "alias": "opacity_mask", "parameter_name": "S_OpacityClip", "default_value": "1.0", "x": -700, "y": 340, "output_property": "MP_OpacityMask"},
        ],
        "preview": {"carrier": "mesh", "with_complexity": True},
        "audit_focus": ["masked opacity", "two-sided shading", "subsurface output", "foliage texture alpha"],
    },
    "basic_water": {
        "title": "Basic Single Layer Water route",
        "intent": "Starter water material route with water-specific audit and normal/foam texture slots.",
        "default_asset_prefix": "M_BasicWater",
        "route": {
            "domain": "Surface",
            "blend_mode": "Opaque",
            "shading_model": "SingleLayerWater",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "Roughness", "Normal", "Opacity", "SingleLayerWaterMaterialOutput"],
            "usage_flags": ["StaticMesh"],
        },
        "carrier": "mesh",
        "texture_requirements": [
            {
                "slot": "water_normal",
                "name": "T_WaterNormal",
                "channels": "Normal XYZ",
                "recommended_size": "1024 tileable normal",
                "sRGB": False,
                "compression": "Normalmap",
                "required": True,
            },
            {
                "slot": "foam_mask",
                "name": "T_FoamMask",
                "channels": "R foam/mask",
                "recommended_size": "512 or 1024 grayscale",
                "sRGB": False,
                "compression": "Masks",
                "required": False,
            },
        ],
        "parameters": [
            {"name": "V_ShallowColor", "type": "Vector", "default": "(R=0.08,G=0.42,B=0.52,A=1.0)", "purpose": "Near/shallow water color."},
            {"name": "V_DeepColor", "type": "Vector", "default": "(R=0.01,G=0.08,B=0.16,A=1.0)", "purpose": "Deep water color."},
            {"name": "S_Roughness", "type": "Scalar", "default": "0.04", "purpose": "Water surface roughness."},
            {"name": "S_NormalStrength", "type": "Scalar", "default": "0.7", "purpose": "Normal intensity."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "water_color", "parameter_name": "V_ShallowColor", "default_value": "(R=0.08,G=0.42,B=0.52,A=1.0)", "x": -650, "y": -120, "output_property": "MP_BaseColor"},
            {"template": "scalar_parameter", "alias": "roughness", "parameter_name": "S_Roughness", "default_value": "0.04", "x": -650, "y": 60, "output_property": "MP_Roughness"},
            {"template": "scalar_parameter", "alias": "opacity", "parameter_name": "S_WaterOpacity", "default_value": "0.5", "x": -650, "y": 220, "output_property": "MP_Opacity"},
        ],
        "preview": {"carrier": "mesh", "with_complexity": True},
        "audit_focus": ["Single Layer Water route", "normal strength", "water preview context", "shading-model budget"],
    },
    "energy_ribbon": {
        "title": "Energy ribbon trail route",
        "intent": "Unlit additive ribbon trail with bright head, tail falloff, and optional breakup texture.",
        "default_asset_prefix": "M_EnergyRibbon",
        "route": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": True,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "carrier": "ribbon",
        "texture_requirements": [
            {
                "slot": "ribbon_mask",
                "name": "T_RibbonMask_VFX",
                "channels": "R head/tail gradient or breakup mask",
                "recommended_size": "512x256 or 1024x256",
                "sRGB": False,
                "compression": "Masks",
                "required": False,
            }
        ],
        "parameters": [
            {"name": "V_TrailColor", "type": "Vector", "default": "(R=0.08,G=0.7,B=1.0,A=1.0)", "purpose": "Ribbon tint."},
            {"name": "S_TrailHeadBrightness", "type": "Scalar", "default": "6.0", "purpose": "Head emissive multiplier."},
            {"name": "S_TrailTailOpacity", "type": "Scalar", "default": "0.15", "purpose": "Tail alpha floor."},
            {"name": "S_DynamicEmissiveBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param1 emissive scale contribution."},
            {"name": "S_DynamicOpacityBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in Niagara DynamicParameter Param2 opacity scale contribution."},
            {"name": "S_RibbonUEmissiveBoost", "type": "Scalar", "default": "0.0", "purpose": "Opt-in ribbon U-axis emissive shaping contribution."},
            {"name": "S_FlowSpeed", "type": "Scalar", "default": "0.45", "purpose": "Optional UV flow speed."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "trail_color", "parameter_name": "V_TrailColor", "default_value": "(R=0.08,G=0.7,B=1.0,A=1.0)", "x": -760, "y": -100},
            {"template": "particle_color", "alias": "particle_color", "x": -760, "y": 60},
            {"template": "scalar_parameter", "alias": "trail_brightness", "parameter_name": "S_TrailHeadBrightness", "default_value": "6.0", "x": -760, "y": 60},
            {"template": "dynamic_parameter", "alias": "dynamic_parameter", "x": -760, "y": 240},
            {"template": "scalar_parameter", "alias": "dynamic_emissive_boost", "parameter_name": "S_DynamicEmissiveBoost", "default_value": "0.0", "x": -760, "y": 390},
            {"template": "constant_scalar", "alias": "emissive_scale_one", "value": "1.0", "x": -760, "y": 520},
            {"template": "scalar_parameter", "alias": "dynamic_opacity_boost", "parameter_name": "S_DynamicOpacityBoost", "default_value": "0.0", "x": -760, "y": 650},
            {"template": "constant_scalar", "alias": "opacity_scale_one", "value": "1.0", "x": -760, "y": 780},
            {"template": "texture_coordinate", "alias": "ribbon_uv", "x": -760, "y": 930},
            {"template": "component_mask", "alias": "ribbon_u", "source_expression": "ribbon_uv", "mask": "R", "x": -500, "y": 930},
            {"template": "scalar_parameter", "alias": "ribbon_u_emissive_boost", "parameter_name": "S_RibbonUEmissiveBoost", "default_value": "0.0", "x": -500, "y": 1080},
            {"template": "multiply_pair", "alias": "tinted_particle_color", "left_expression": "trail_color", "right_expression": "particle_color", "x": -500, "y": -80},
            {"template": "multiply_pair", "alias": "trail_emissive", "left_expression": "tinted_particle_color", "right_expression": "trail_brightness", "x": -220, "y": -60},
            {"template": "multiply_pair", "alias": "dynamic_emissive_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param1", "right_expression": "dynamic_emissive_boost", "x": -500, "y": 360},
            {"template": "multiply_pair", "alias": "ribbon_u_emissive_delta", "left_expression": "ribbon_u", "right_expression": "ribbon_u_emissive_boost", "x": -220, "y": 920},
            {"template": "add_pair", "alias": "dynamic_emissive_scale", "left_expression": "emissive_scale_one", "right_expression": "dynamic_emissive_delta", "x": -220, "y": 360},
            {"template": "add_pair", "alias": "ribbon_emissive_scale", "left_expression": "dynamic_emissive_scale", "right_expression": "ribbon_u_emissive_delta", "x": 60, "y": 360},
            {"template": "multiply_pair", "alias": "trail_emissive_with_dynamic", "left_expression": "trail_emissive", "right_expression": "ribbon_emissive_scale", "x": 320, "y": -60, "output_property": "MP_EmissiveColor"},
            {"template": "scalar_parameter", "alias": "tail_opacity", "parameter_name": "S_TrailTailOpacity", "default_value": "0.15", "x": -480, "y": 220},
            {"template": "multiply_pair", "alias": "dynamic_opacity_delta", "left_expression": "dynamic_parameter", "left_output_name": "Param2", "right_expression": "dynamic_opacity_boost", "x": -500, "y": 620},
            {"template": "add_pair", "alias": "dynamic_opacity_scale", "left_expression": "opacity_scale_one", "right_expression": "dynamic_opacity_delta", "x": -220, "y": 620},
            {"template": "multiply_pair", "alias": "tail_opacity_with_dynamic", "left_expression": "tail_opacity", "right_expression": "dynamic_opacity_scale", "x": 60, "y": 220, "output_property": "MP_Opacity"},
        ],
        "preview": {"carrier": "ribbon", "with_complexity": True},
        "audit_focus": ["ribbon UV direction", "alpha coverage", "ParticleColor compatibility", "overdraw"],
    },
    "dissolve_edge": {
        "title": "Masked dissolve edge route",
        "intent": "Masked dissolve material with emissive edge band and reusable threshold controls.",
        "default_asset_prefix": "M_DissolveEdge",
        "route": {
            "domain": "Surface",
            "blend_mode": "Masked",
            "shading_model": "DefaultLit",
            "two_sided": False,
            "expected_outputs": ["BaseColor", "OpacityMask", "EmissiveColor", "Roughness"],
            "usage_flags": ["StaticMesh"],
        },
        "carrier": "mesh",
        "texture_requirements": [
            {
                "slot": "dissolve_noise",
                "name": "T_DissolveNoise",
                "channels": "R dissolve threshold noise",
                "recommended_size": "512 or 1024 tileable grayscale",
                "sRGB": False,
                "compression": "Masks",
                "required": True,
            }
        ],
        "parameters": [
            {"name": "V_BaseColor", "type": "Vector", "default": "(R=0.25,G=0.25,B=0.25,A=1.0)", "purpose": "Base surface color."},
            {"name": "V_EdgeColor", "type": "Vector", "default": "(R=0.1,G=0.65,B=1.0,A=1.0)", "purpose": "Dissolve edge glow."},
            {"name": "S_DissolveThreshold", "type": "Scalar", "default": "0.5", "purpose": "Dissolve progress."},
            {"name": "S_EdgeWidth", "type": "Scalar", "default": "0.08", "purpose": "Glow band width."},
            {"name": "S_EmissiveIntensity", "type": "Scalar", "default": "5.0", "purpose": "Glow intensity."},
        ],
        "builder_templates": [
            {"template": "vector_parameter", "alias": "base_color", "parameter_name": "V_BaseColor", "default_value": "(R=0.25,G=0.25,B=0.25,A=1.0)", "x": -720, "y": -180, "output_property": "MP_BaseColor"},
            {"template": "vector_parameter", "alias": "edge_color", "parameter_name": "V_EdgeColor", "default_value": "(R=0.1,G=0.65,B=1.0,A=1.0)", "x": -720, "y": 0},
            {"template": "scalar_parameter", "alias": "emissive_intensity", "parameter_name": "S_EmissiveIntensity", "default_value": "5.0", "x": -720, "y": 160},
            {"template": "multiply_pair", "alias": "edge_emissive", "left_expression": "edge_color", "right_expression": "emissive_intensity", "x": -450, "y": 40, "output_property": "MP_EmissiveColor"},
            {"template": "scalar_parameter", "alias": "opacity_mask", "parameter_name": "S_DissolveThreshold", "default_value": "1.0", "x": -450, "y": 260, "output_property": "MP_OpacityMask"},
        ],
        "preview": {"carrier": "mesh", "with_complexity": True},
        "audit_focus": ["opacity mask threshold", "edge band readability", "mask texture import settings", "masked overdraw"],
    },
}


REFACTOR_OPERATIONS: dict[str, dict[str, Any]] = {
    "add_fresnel_layer": {
        "title": "Add Fresnel rim layer",
        "intent": "Insert a rim-light layer without changing the base material route.",
        "risk": "medium",
        "candidate_nodes": ["Fresnel", "VectorParameter V_FresnelColor", "ScalarParameter S_FresnelIntensity", "Multiply/Add into EmissiveColor"],
        "guardrails": [
            "Do not replace the existing EmissiveColor chain without saving before/after audits.",
            "Prefer additive blending into the existing emissive result.",
            "Run preview regression before accepting the new rim layer.",
        ],
        "validation": ["material_audit", "material_preview", "material_regression"],
    },
    "add_depth_fade": {
        "title": "Add DepthFade opacity softening",
        "intent": "Reduce hard intersections for translucent sprite, ribbon, mesh, or decal-like materials.",
        "risk": "medium",
        "candidate_nodes": ["DepthFade", "ScalarParameter S_DepthFadeDistance", "Multiply into Opacity"],
        "guardrails": [
            "Only apply to translucent/additive routes where soft intersection is desired.",
            "Keep a scalar distance parameter so Niagara or MI tuning can recover edge readability.",
            "Check sorting and overdraw after the change.",
        ],
        "validation": ["material_domain_audit", "material_preview", "material_regression"],
    },
    "add_detail_normal": {
        "title": "Add detail normal layer",
        "intent": "Layer a small-scale normal detail without replacing the primary normal route.",
        "risk": "medium",
        "candidate_nodes": ["TextureSampleParameter2D T_DetailNormal", "ScalarParameter S_DetailNormalStrength", "BlendAngleCorrectedNormals"],
        "guardrails": [
            "Only apply to lit surface routes that already use or can safely use Normal.",
            "Use Normalmap compression and sRGB=false.",
            "Preview at target distance; detail normals can shimmer or alias.",
        ],
        "validation": ["texture_import_audit", "material_audit", "material_preview"],
    },
    "restore_route_contract": {
        "title": "Restore render route contract",
        "intent": "Revert accidental domain, blend, shading model, two-sided, or usage-flag drift.",
        "risk": "high",
        "candidate_nodes": [],
        "guardrails": [
            "Treat route changes as top-priority regression causes.",
            "Restore route first before tuning parameters.",
            "Re-run domain audit immediately after the route change.",
        ],
        "validation": ["material_domain_audit", "material_preview", "material_regression"],
    },
    "repair_output_chain": {
        "title": "Repair output chain wiring",
        "intent": "Review and reconnect changed BaseColor, Emissive, Opacity, OpacityMask, Normal, WPO, PDO, or Refraction chains.",
        "risk": "high",
        "candidate_nodes": [],
        "guardrails": [
            "Use GUID-level audits when available before rewiring nodes.",
            "Patch one output at a time and rerun preview/regression after each output-level repair.",
            "Do not tune unrelated parameters until the changed output chain is accounted for.",
        ],
        "validation": ["material_audit --include-raw-graph", "material_preview", "material_regression"],
    },
    "normalize_parameters": {
        "title": "Normalize material parameter names and defaults",
        "intent": "Resolve confusing or colliding parameter controls after master-material migration or graph rebuild.",
        "risk": "low",
        "candidate_nodes": ["ScalarParameter", "VectorParameter", "TextureSampleParameter2D", "StaticSwitchParameter"],
        "guardrails": [
            "Prefer adding aliases or migration notes over silently renaming live runtime parameters.",
            "Check runtime_param_trace when Niagara, MPC, or gameplay may drive the parameter.",
            "Keep old/new parameter mapping in delivery notes.",
        ],
        "validation": ["runtime_param_trace", "material_audit", "material_instance_batch dry run"],
    },
}


GRAPH_DIFF_CATEGORY_TO_OPERATION = {
    "route": "restore_route_contract",
    "domain_contract": "restore_route_contract",
    "output_chain": "repair_output_chain",
    "brightness": "normalize_parameters",
    "alpha": "repair_output_chain",
    "coverage": "repair_output_chain",
    "composition": "repair_output_chain",
    "texture": "normalize_parameters",
    "budget": "normalize_parameters",
}


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _append_expr(spec: dict[str, Any], alias: str, expression_class: str, x: int, y: int) -> None:
    spec.setdefault("expressions", []).append(
        {
            "alias": alias,
            "expression_class": expression_class,
            "x": int(x),
            "y": int(y),
        }
    )


def _append_expr_props(spec: dict[str, Any], expression: str, properties: list[dict[str, Any]]) -> None:
    spec.setdefault("expression_properties", []).append(
        {
            "expression": expression,
            "properties": properties,
        }
    )


def _append_conn(spec: dict[str, Any], from_expression: str, to_expression: str, to_input_name: str, from_output_name: str = "") -> None:
    spec.setdefault("connections", []).append(
        {
            "from_expression": from_expression,
            "from_output_name": from_output_name,
            "to_expression": to_expression,
            "to_input_name": to_input_name,
        }
    )


def _append_output(spec: dict[str, Any], expression: str, material_property: str, output_name: str = "") -> None:
    spec.setdefault("output_connections", []).append(
        {
            "expression": expression,
            "output_name": output_name,
            "material_property": material_property,
        }
    )


def _append_optional_output(expanded: dict[str, Any], item: dict[str, Any], alias: str) -> None:
    if item.get("output_property"):
        _append_output(expanded, alias, str(item["output_property"]))


def _asset_ref(folder_path: str, asset_name_or_path: str) -> str:
    raw = str(asset_name_or_path or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        return raw if "." in raw.rsplit("/", 1)[-1] else f"{raw}.{raw.rsplit('/', 1)[-1]}"
    folder = str(folder_path or "").rstrip("/")
    name = raw.rsplit(".", 1)[-1] if "." in raw else raw
    return f"{folder}/{name}.{name}" if folder else raw


def expand_templates(spec: dict[str, Any]) -> dict[str, Any]:
    expanded = copy.deepcopy(spec)
    templates = expanded.pop("templates", []) or []
    for item in templates:
        template = str(item.get("template") or "").strip().lower()
        prefix = str(item.get("alias_prefix") or template or "node")
        x = int(item.get("x", -400))
        y = int(item.get("y", 0))

        if template == "constant_scalar":
            alias = item.get("alias") or f"{prefix}_scalar"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionConstant", x, y)
            _append_expr_props(expanded, alias, [{"name": "R", "value": str(item.get("value", "1.0"))}])
            _append_optional_output(expanded, item, alias)
        elif template == "constant3_color":
            alias = item.get("alias") or f"{prefix}_color"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionConstant3Vector", x, y)
            _append_expr_props(
                expanded,
                alias,
                [{"name": "Constant", "value": str(item.get("value", "(R=1.0,G=1.0,B=1.0,A=1.0)"))}],
            )
            _append_optional_output(expanded, item, alias)
        elif template == "scalar_parameter":
            alias = item.get("alias") or f"{prefix}_scalar_param"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionScalarParameter", x, y)
            _append_expr_props(
                expanded,
                alias,
                [
                    {"name": "ParameterName", "value": str(item.get("parameter_name", alias))},
                    {"name": "DefaultValue", "value": str(item.get("default_value", "1.0"))},
                ],
            )
            _append_optional_output(expanded, item, alias)
        elif template == "vector_parameter":
            alias = item.get("alias") or f"{prefix}_vector_param"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionVectorParameter", x, y)
            _append_expr_props(
                expanded,
                alias,
                [
                    {"name": "ParameterName", "value": str(item.get("parameter_name", alias))},
                    {"name": "DefaultValue", "value": str(item.get("default_value", "(R=1.0,G=1.0,B=1.0,A=1.0)"))},
                ],
            )
            _append_optional_output(expanded, item, alias)
        elif template == "texture_parameter_2d":
            alias = item.get("alias") or f"{prefix}_texture"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionTextureSampleParameter2D", x, y)
            props = [{"name": "ParameterName", "value": str(item.get("parameter_name", alias))}]
            default_texture = item.get("default_texture") or item.get("default_texture_name")
            if default_texture:
                props.append({"name": "Texture", "value": _asset_ref(str(expanded.get("folder_path") or ""), str(default_texture))})
            _append_expr_props(expanded, alias, props)
            coordinates = item.get("coordinates_expression")
            if coordinates:
                _append_conn(expanded, str(coordinates), alias, "Coordinates", str(item.get("coordinates_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "particle_color":
            alias = item.get("alias") or f"{prefix}_particle_color"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionParticleColor", x, y)
            _append_optional_output(expanded, item, alias)
        elif template == "dynamic_parameter":
            alias = item.get("alias") or f"{prefix}_dynamic_parameter"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionDynamicParameter", x, y)
            _append_optional_output(expanded, item, alias)
        elif template == "texture_coordinate":
            alias = item.get("alias") or f"{prefix}_texture_coordinate"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionTextureCoordinate", x, y)
            props: list[dict[str, Any]] = []
            if "coordinate_index" in item:
                props.append({"name": "CoordinateIndex", "value": str(item["coordinate_index"])})
            if "u_tiling" in item:
                props.append({"name": "UTiling", "value": str(item["u_tiling"])})
            if "v_tiling" in item:
                props.append({"name": "VTiling", "value": str(item["v_tiling"])})
            if props:
                _append_expr_props(expanded, alias, props)
            _append_optional_output(expanded, item, alias)
        elif template == "time":
            alias = item.get("alias") or f"{prefix}_time"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionTime", x, y)
            _append_optional_output(expanded, item, alias)
        elif template == "append_vector":
            left = item.get("left_expression") or f"{prefix}_left"
            right = item.get("right_expression") or f"{prefix}_right"
            alias = item.get("alias") or f"{prefix}_append"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionAppendVector", x + 260, y + 40)
            _append_conn(expanded, str(left), alias, "A", str(item.get("left_output_name", "")))
            _append_conn(expanded, str(right), alias, "B", str(item.get("right_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "component_mask":
            alias = item.get("alias") or f"{prefix}_component_mask"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionComponentMask", x, y)
            mask = str(item.get("mask") or "R").upper()
            _append_expr_props(
                expanded,
                alias,
                [
                    {"name": "R", "value": "True" if "R" in mask else "False"},
                    {"name": "G", "value": "True" if "G" in mask else "False"},
                    {"name": "B", "value": "True" if "B" in mask else "False"},
                    {"name": "A", "value": "True" if "A" in mask else "False"},
                ],
            )
            source = item.get("source_expression")
            if source:
                _append_conn(expanded, str(source), alias, str(item.get("input_name", "Input")), str(item.get("source_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "fresnel":
            alias = item.get("alias") or f"{prefix}_fresnel"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionFresnel", x, y)
            _append_optional_output(expanded, item, alias)
        elif template == "depth_fade":
            alias = item.get("alias") or f"{prefix}_depth_fade"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionDepthFade", x, y)
            _append_optional_output(expanded, item, alias)
        elif template == "add_pair":
            left = item.get("left_expression") or f"{prefix}_left"
            right = item.get("right_expression") or f"{prefix}_right"
            add = item.get("alias") or f"{prefix}_add"
            _append_expr(expanded, add, "/Script/Engine.MaterialExpressionAdd", x + 260, y + 40)
            _append_conn(expanded, str(left), add, "A", str(item.get("left_output_name", "")))
            _append_conn(expanded, str(right), add, "B", str(item.get("right_output_name", "")))
            _append_optional_output(expanded, item, add)
        elif template == "subtract_pair":
            left = item.get("left_expression") or f"{prefix}_left"
            right = item.get("right_expression") or f"{prefix}_right"
            subtract = item.get("alias") or f"{prefix}_subtract"
            _append_expr(expanded, subtract, "/Script/Engine.MaterialExpressionSubtract", x + 260, y + 40)
            _append_conn(expanded, str(left), subtract, "A", str(item.get("left_output_name", "")))
            _append_conn(expanded, str(right), subtract, "B", str(item.get("right_output_name", "")))
            _append_optional_output(expanded, item, subtract)
        elif template == "multiply_pair":
            left = item.get("left_expression") or f"{prefix}_left"
            right = item.get("right_expression") or f"{prefix}_right"
            multiply = item.get("alias") or f"{prefix}_multiply"
            _append_expr(expanded, multiply, "/Script/Engine.MaterialExpressionMultiply", x + 260, y + 40)
            _append_conn(expanded, str(left), multiply, "A", str(item.get("left_output_name", "")))
            _append_conn(expanded, str(right), multiply, "B", str(item.get("right_output_name", "")))
            _append_optional_output(expanded, item, multiply)
        elif template == "one_minus":
            source = item.get("source_expression") or f"{prefix}_source"
            alias = item.get("alias") or f"{prefix}_one_minus"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionOneMinus", x, y)
            _append_conn(expanded, str(source), alias, "Input", str(item.get("source_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "abs":
            source = item.get("source_expression") or f"{prefix}_source"
            alias = item.get("alias") or f"{prefix}_abs"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionAbs", x, y)
            _append_conn(expanded, str(source), alias, "Input", str(item.get("source_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "power_pair":
            base = item.get("base_expression") or f"{prefix}_base"
            exponent = item.get("exponent_expression") or f"{prefix}_exponent"
            alias = item.get("alias") or f"{prefix}_power"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionPower", x + 260, y + 40)
            _append_conn(expanded, str(base), alias, "Base", str(item.get("base_output_name", "")))
            _append_conn(expanded, str(exponent), alias, "Exponent", str(item.get("exponent_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "clamp":
            source = item.get("source_expression") or f"{prefix}_source"
            alias = item.get("alias") or f"{prefix}_clamp"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionClamp", x, y)
            _append_expr_props(
                expanded,
                alias,
                [
                    {"name": "MinDefault", "value": str(item.get("min", "0.0"))},
                    {"name": "MaxDefault", "value": str(item.get("max", "1.0"))},
                ],
            )
            _append_conn(expanded, str(source), alias, "Input", str(item.get("source_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template in {"lerp", "linear_interpolate"}:
            left = item.get("left_expression") or item.get("a_expression") or f"{prefix}_a"
            right = item.get("right_expression") or item.get("b_expression") or f"{prefix}_b"
            alpha = item.get("alpha_expression") or f"{prefix}_alpha"
            alias = item.get("alias") or f"{prefix}_lerp"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionLinearInterpolate", x + 260, y + 40)
            _append_conn(expanded, str(left), alias, "A", str(item.get("left_output_name", "")))
            _append_conn(expanded, str(right), alias, "B", str(item.get("right_output_name", "")))
            _append_conn(expanded, str(alpha), alias, "Alpha", str(item.get("alpha_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "panner":
            coordinate = item.get("coordinate_expression")
            time = item.get("time_expression")
            alias = item.get("alias") or f"{prefix}_panner"
            _append_expr(expanded, alias, "/Script/Engine.MaterialExpressionPanner", x, y)
            _append_expr_props(
                expanded,
                alias,
                [
                    {"name": "SpeedX", "value": str(item.get("speed_x", "1.0"))},
                    {"name": "SpeedY", "value": str(item.get("speed_y", "0.0"))},
                ],
            )
            if coordinate:
                _append_conn(expanded, str(coordinate), alias, "Coordinate", str(item.get("coordinate_output_name", "")))
            if time:
                _append_conn(expanded, str(time), alias, "Time", str(item.get("time_output_name", "")))
            _append_optional_output(expanded, item, alias)
        elif template == "emissive_color_scalar":
            color_alias = item.get("color_alias") or f"{prefix}_color"
            scale_alias = item.get("scale_alias") or f"{prefix}_scale"
            mul_alias = item.get("alias") or f"{prefix}_multiply"
            _append_expr(expanded, color_alias, "/Script/Engine.MaterialExpressionConstant3Vector", x, y)
            _append_expr(expanded, scale_alias, "/Script/Engine.MaterialExpressionConstant", x, y + 140)
            _append_expr(expanded, mul_alias, "/Script/Engine.MaterialExpressionMultiply", x + 280, y + 40)
            _append_expr_props(expanded, color_alias, [{"name": "Constant", "value": str(item.get("color", "(R=1.0,G=1.0,B=1.0,A=1.0)"))}])
            _append_expr_props(expanded, scale_alias, [{"name": "R", "value": str(item.get("scale", "1.0"))}])
            _append_conn(expanded, color_alias, mul_alias, "A")
            _append_conn(expanded, scale_alias, mul_alias, "B")
            _append_output(expanded, mul_alias, str(item.get("output_property", "MP_EmissiveColor")))
        elif template == "basecolor_roughness_pair":
            color_alias = item.get("color_alias") or f"{prefix}_basecolor"
            rough_alias = item.get("roughness_alias") or f"{prefix}_roughness"
            _append_expr(expanded, color_alias, "/Script/Engine.MaterialExpressionConstant3Vector", x, y)
            _append_expr(expanded, rough_alias, "/Script/Engine.MaterialExpressionConstant", x, y + 140)
            _append_expr_props(expanded, color_alias, [{"name": "Constant", "value": str(item.get("basecolor", "(R=0.5,G=0.5,B=0.5,A=1.0)"))}])
            _append_expr_props(expanded, rough_alias, [{"name": "R", "value": str(item.get("roughness", "0.5"))}])
            _append_output(expanded, color_alias, "MP_BaseColor")
            _append_output(expanded, rough_alias, "MP_Roughness")
        else:
            raise SystemExit(f"Unknown material builder template `{template}`.")
    return expanded


def recipe_key(raw: str) -> str:
    key = str(raw or "").strip().lower().replace("-", "_")
    key = RECIPE_ALIASES.get(key, key)
    if key not in RECIPE_DEFINITIONS:
        raise SystemExit(f"Unknown recipe `{raw}`. Use `list-recipes` to see available recipes.")
    return key


def default_asset_name(recipe: dict[str, Any], effect: str, layer: str) -> str:
    parts = [recipe.get("default_asset_prefix") or "M_Material"]
    if effect:
        parts.append(slugify(effect).replace("-", "_"))
    if layer:
        parts.append(slugify(layer).replace("-", "_"))
    return "_".join(parts)


def make_recipe_builder_spec(args: argparse.Namespace, definition: dict[str, Any]) -> dict[str, Any]:
    effect = args.effect or "MaterialRecipe"
    layer = args.layer or definition.get("carrier") or "Layer"
    asset_name = args.asset_name or default_asset_name(definition, effect, layer)
    folder_path = args.folder_path or "/Game/Materials/CodexRecipes"
    spec = {
        "folder_path": folder_path.rstrip("/"),
        "asset_name": asset_name,
        "recipe": args.recipe_key,
        "effect": effect,
        "layer": layer,
        "route": copy.deepcopy(definition.get("route") or {}),
        "templates": copy.deepcopy(definition.get("builder_templates") or []),
        "recompile": True,
    }
    return expand_templates(spec)


def preview_command(tool_root: Path, material_path: str, effect: str, layer: str, preview: dict[str, Any]) -> str:
    carrier = preview.get("carrier") or "mesh"
    complexity = " --with-complexity" if preview.get("with_complexity") else ""
    return (
        f"python {tool_root.as_posix()}/tools/material_preview.py render {material_path} "
        f"--carrier {carrier}{complexity} --markdown"
    )


def build_recipe_report(args: argparse.Namespace) -> tuple[dict[str, Any], Path, Path | None]:
    ctx = resolve_root_context(args.root)
    key = recipe_key(args.recipe)
    args.recipe_key = key
    definition = RECIPE_DEFINITIONS[key]
    spec = make_recipe_builder_spec(args, definition)
    effect = args.effect or spec.get("effect") or key
    layer = args.layer or spec.get("layer") or definition.get("carrier") or "Layer"
    material_path = f"{spec['folder_path']}/{spec['asset_name']}"
    material_ref = f"{material_path}.{spec['asset_name']}"
    package_slug = slugify(f"{effect}-{layer}-{key}")
    out = Path(args.out) if args.out else ctx.material_root / "toolset-recipes" / package_slug / "material-toolset-recipe.json"
    spec_path = Path(args.build_spec_out) if args.build_spec_out else out.with_name("material-builder-spec.json")
    report = {
        "tool": "material_toolset_builder_recipe",
        "version": 1,
        "created_utc": utc_now_iso(),
        "recipe": key,
        "title": definition.get("title"),
        "intent": args.intent or definition.get("intent"),
        "effect": effect,
        "layer": layer,
        "target_material": {
            "folder_path": spec["folder_path"],
            "asset_name": spec["asset_name"],
            "material_path": material_path,
            "material_ref": material_ref,
        },
        "route": copy.deepcopy(definition.get("route") or {}),
        "carrier": args.carrier or definition.get("carrier"),
        "texture_requirements": copy.deepcopy(definition.get("texture_requirements") or []),
        "parameters": copy.deepcopy(definition.get("parameters") or []),
        "builder_spec_path": str(spec_path),
        "builder_spec": spec if args.inline_build_spec else None,
        "preview_plan": {
            "command": preview_command(ctx.skill_root, material_path, effect, layer, definition.get("preview") or {}),
            "carrier": (definition.get("preview") or {}).get("carrier"),
            "with_complexity": bool((definition.get("preview") or {}).get("with_complexity")),
        },
        "audit_plan": [
            f"python {ctx.skill_root.as_posix()}/tools/material_audit.py {material_path} --markdown",
            f"python {ctx.skill_root.as_posix()}/tools/material_domain_audit.py {material_path} --markdown",
        ],
        "texture_plan": [
            f"python {ctx.skill_root.as_posix()}/tools/texture_set_pipeline.py audit --effect {effect} --layer {layer} --scan <texture-folder> --emit-import-fix-spec --markdown"
        ],
        "delivery_plan": [
            "Run the generated builder spec only after texture placeholders and route choices are reviewed.",
            "Preview the material on the intended carrier before optimizing.",
            "Package final plan, texture, preview, audit, and regression evidence with delivery_packager.py.",
        ],
        "audit_focus": copy.deepcopy(definition.get("audit_focus") or []),
        "warnings": recipe_warnings(key, definition, args),
    }
    return report, out, spec_path


def recipe_warnings(key: str, definition: dict[str, Any], args: argparse.Namespace) -> list[str]:
    warnings: list[str] = []
    if key == "basic_water":
        warnings.append("Basic water recipes still require the complex-water playbook for final art direction and water-specific audit.")
    if key == "fire_flipbook":
        warnings.append("Hero fire usually needs real flipbook/SubUV texture evidence; this builder spec is only the material route scaffold.")
        warnings.append("Niagara SubUV sprites are camera-facing by default, so the route keeps Two Sided off unless a non-camera-facing mesh/card carrier is explicitly required.")
    if key == "fire_ribbon_additive":
        warnings.append("This recipe builds a first-pass packed-mask additive graph with panner/time motion, optional Flow_UV remap, centered width falloff, B-channel distortion, ParticleColor, and DynamicParameter sockets.")
        warnings.append("Live UE pin-name smoke and carrier preview are still required before delivery; keep an Android one-sample fallback MI/spec when mobile is in scope.")
        warnings.append("Texture_Mask defaults to the same folder's T_FireRibbonMask_VFX asset reference in the builder spec; edit that property if the imported mask lives elsewhere.")
        warnings.append("Validate Texture_Mask as packed mask data with sRGB=false and mask compression before delivery.")
        warnings.append("Two Sided + Additive can multiply brightness on ribbons; preview on neutral, bright, and busy backgrounds.")
        warnings.append("Real Niagara System/Emitter/Renderer binding proof remains Niagara-owned; hand the material contract to niagara-vfx-artist.")
    if key == "fire_ribbon_additive_android":
        warnings.append("This Android fallback intentionally uses one Texture_Mask sample and omits the secondary noise/distortion sample; treat it as a low-tier variant, not a visual-equivalent replacement for the deep fire_ribbon_additive route.")
        warnings.append("Live UE pin-name smoke and carrier preview are still required before delivery.")
        warnings.append("Texture_Mask defaults to the same folder's T_FireRibbonMask_VFX asset reference in the builder spec; edit that property if the imported mask lives elsewhere.")
        warnings.append("Validate Texture_Mask as packed mask data with sRGB=false, mask compression, and 256-512 fallback size before delivery.")
        warnings.append("Two Sided + Additive can multiply brightness on ribbons; preview on neutral, bright, and busy backgrounds.")
        warnings.append("Real Niagara System/Emitter/Renderer binding proof remains Niagara-owned; hand the material contract to niagara-vfx-artist.")
    if not args.execute:
        warnings.append("Recipe generation is offline by default; no UE asset was created unless --execute is used.")
    if definition.get("texture_requirements"):
        warnings.append("Texture slots must be validated separately with texture_set_pipeline.py or texture_import_audit.py.")
    return warnings


def build_refactor_plan(args: argparse.Namespace) -> tuple[dict[str, Any], Path]:
    ctx = resolve_root_context(args.root)
    graph_diff = load_spec(args.graph_diff_report) if args.graph_diff_report else {}
    effect = args.effect or graph_diff.get("effect") or "MaterialRefactor"
    layer = args.layer or graph_diff.get("layer") or "Layer"
    label = args.label or graph_diff.get("label") or "plan"
    operations = select_refactor_operations(args, graph_diff)
    target = args.material_path or (((graph_diff.get("identity") or {}).get("after") or {}).get("material_path")) or ""
    out = Path(args.out) if args.out else ctx.material_root / "toolset-refactors" / slugify(f"{effect}-{layer}-{label}") / "material-toolset-refactor-plan.json"
    patch_spec_path = Path(args.patch_spec_out) if args.patch_spec_out else out.with_name("material-refactor-patch-spec.json")
    report = {
        "tool": "material_toolset_builder_refactor_plan",
        "version": 1,
        "created_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "label": label,
        "target_material": target,
        "source_graph_diff_report": str(args.graph_diff_report or ""),
        "source_gate": graph_diff.get("gate") or {},
        "source_likely_causes": graph_diff.get("likely_causes") or [],
        "operations": operations,
        "patch_spec_path": str(patch_spec_path),
        "patch_spec": make_patch_spec(target, operations, graph_diff),
        "validation_plan": refactor_validation_plan(ctx.skill_root, target, effect, layer),
        "apply_policy": {
            "default": "plan_only",
            "reason": "Narrow graph refactors should be applied only after before/after audits and preview baselines exist.",
            "safe_to_apply_automatically": False,
        },
        "next_actions": [
            "Capture or confirm a before material_audit.py report, preferably with --include-raw-graph.",
            "Apply one operation at a time through UE tools or a future apply helper.",
            "Rerun material_preview.py and material_regression.py compare after each patch.",
            "Use graph_diff_refactor.py again if the regression still fails.",
        ],
    }
    return report, out


def select_refactor_operations(args: argparse.Namespace, graph_diff: dict[str, Any]) -> list[dict[str, Any]]:
    requested = [normal_operation_name(item) for item in (args.operation or [])]
    if not requested and graph_diff:
        for cause in graph_diff.get("likely_causes") or []:
            if not isinstance(cause, dict):
                continue
            category = str(cause.get("category") or "").lower()
            op_name = GRAPH_DIFF_CATEGORY_TO_OPERATION.get(category)
            if op_name and op_name not in requested:
                requested.append(op_name)
    if not requested:
        requested.append("normalize_parameters")

    operations: list[dict[str, Any]] = []
    seen: set[str] = set()
    cause_map = graph_diff.get("likely_causes") or []
    for op_name in requested:
        if op_name in seen:
            continue
        seen.add(op_name)
        definition = REFACTOR_OPERATIONS[op_name]
        evidence = [
            {
                "severity": cause.get("severity"),
                "category": cause.get("category"),
                "reason": cause.get("reason"),
                "recommendation": cause.get("recommendation"),
            }
            for cause in cause_map
            if isinstance(cause, dict) and GRAPH_DIFF_CATEGORY_TO_OPERATION.get(str(cause.get("category") or "").lower()) == op_name
        ]
        operations.append(
            {
                "operation": op_name,
                "title": definition["title"],
                "intent": definition["intent"],
                "risk": definition["risk"],
                "candidate_nodes": copy.deepcopy(definition["candidate_nodes"]),
                "guardrails": copy.deepcopy(definition["guardrails"]),
                "validation": copy.deepcopy(definition["validation"]),
                "evidence": evidence,
            }
        )
    return operations


def normal_operation_name(raw: str) -> str:
    name = str(raw or "").strip().lower().replace("-", "_")
    aliases = {
        "fresnel": "add_fresnel_layer",
        "add_fresnel": "add_fresnel_layer",
        "depthfade": "add_depth_fade",
        "depth_fade": "add_depth_fade",
        "detail_normal": "add_detail_normal",
        "restore_route": "restore_route_contract",
        "repair_outputs": "repair_output_chain",
        "output_chain": "repair_output_chain",
        "params": "normalize_parameters",
        "parameters": "normalize_parameters",
    }
    name = aliases.get(name, name)
    if name not in REFACTOR_OPERATIONS:
        raise SystemExit(f"Unknown refactor operation `{raw}`.")
    return name


def make_patch_spec(target: str, operations: list[dict[str, Any]], graph_diff: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_material": target,
        "mode": "plan_only",
        "requires_before_audit": True,
        "requires_preview_baseline": True,
        "operations": [
            {
                "operation": item["operation"],
                "risk": item["risk"],
                "candidate_nodes": item["candidate_nodes"],
                "guardrails": item["guardrails"],
            }
            for item in operations
        ],
        "graph_diff_gate": graph_diff.get("gate") or {},
    }


def refactor_validation_plan(tool_root: Path, target: str, effect: str, layer: str) -> list[str]:
    material = target or "<material-path>"
    return [
        f"python {tool_root.as_posix()}/tools/material_audit.py {material} --include-raw-graph --markdown",
        f"python {tool_root.as_posix()}/tools/material_domain_audit.py {material} --markdown",
        f"python {tool_root.as_posix()}/tools/material_preview.py render {material} --with-complexity --markdown",
        f"python {tool_root.as_posix()}/tools/material_regression.py compare --effect {effect} --layer {layer} --preview-report <new-preview.json> --strict --markdown",
    ]


def build_ue_script(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, ensure_ascii=False)
    usage_payload = json.dumps(MATERIAL_USAGE_FLAG_ENUMS, ensure_ascii=False)
    return (
        "import json\n"
        "import unreal\n"
        "MAT = unreal.UnrealBridgeMaterialLibrary\n"
        "TR = unreal.UnrealBridgeToolsetRegistryLibrary\n"
        f"spec = json.loads({payload!r})\n"
        f"USAGE_FLAG_ENUMS = json.loads({usage_payload!r})\n"
        "report = {'material': None, 'usage_flags': [], 'expressions': [], 'connections': [], 'recompile': None, 'save': None}\n"
        "\n"
        "def run_tool(name, payload):\n"
        "    r = TR.execute_qualified_tool(name, json.dumps(payload, ensure_ascii=False), True)\n"
        "    out = None\n"
        "    if r.json_output:\n"
        "        try:\n"
        "            out = json.loads(r.json_output)\n"
        "        except Exception:\n"
        "            out = r.json_output\n"
        "    return {'success': r.success, 'error': r.error, 'output': out}\n"
        "\n"
        "def normalize_usage_flag(value):\n"
        "    text = str(value or '').strip()\n"
        "    compact = ''.join(ch for ch in text if ch.isalnum()).lower()\n"
        "    for prefix in ('busedwith', 'usedwith', 'matusage'):\n"
        "        if compact.startswith(prefix):\n"
        "            compact = compact[len(prefix):]\n"
        "            break\n"
        "    return compact\n"
        "\n"
        "class NullTransaction:\n"
        "    def __enter__(self):\n"
        "        return self\n"
        "    def __exit__(self, exc_type, exc, tb):\n"
        "        return False\n"
        "\n"
        "def apply_usage_flags(material_path, requested_flags):\n"
        "    flags = []\n"
        "    for raw in requested_flags or []:\n"
        "        if raw not in flags:\n"
        "            flags.append(raw)\n"
        "    if not flags:\n"
        "        return []\n"
        "    material = unreal.load_asset(material_path)\n"
        "    if material is None:\n"
        "        return [{'requested': raw, 'success': False, 'changed': False, 'error': f'Could not load material: {material_path}'} for raw in flags]\n"
        "    if not isinstance(material, unreal.Material):\n"
        "        return [{'requested': raw, 'success': False, 'changed': False, 'error': 'Usage flags can only be applied to a base UMaterial.'} for raw in flags]\n"
        "    setter = getattr(unreal.MaterialEditingLibrary, 'set_base_material_usage', None)\n"
        "    legacy_setter = getattr(unreal.MaterialEditingLibrary, 'set_material_usage', None)\n"
        "    transaction = NullTransaction()\n"
        "    try:\n"
        "        transaction = unreal.ScopedEditorTransaction('Codex set material usage flags')\n"
        "    except Exception:\n"
        "        pass\n"
        "    rows = []\n"
        "    with transaction:\n"
        "        for raw in flags:\n"
        "            key = normalize_usage_flag(raw)\n"
        "            enum_name = USAGE_FLAG_ENUMS.get(key)\n"
        "            row = {'requested': raw, 'normalized': key, 'enum': enum_name, 'success': False, 'changed': False, 'before': None, 'after': None, 'error': ''}\n"
        "            if not enum_name:\n"
        "                row['error'] = 'Unsupported material usage flag for safe setter whitelist.'\n"
        "                rows.append(row)\n"
        "                continue\n"
        "            usage = getattr(unreal.MaterialUsage, enum_name, None)\n"
        "            if usage is None:\n"
        "                row['error'] = f'Unreal MaterialUsage enum is not available: {enum_name}'\n"
        "                rows.append(row)\n"
        "                continue\n"
        "            try:\n"
        "                before = bool(unreal.MaterialEditingLibrary.has_material_usage(material, usage))\n"
        "                if not before:\n"
        "                    if setter is not None:\n"
        "                        setter(material, usage, True)\n"
        "                    elif legacy_setter is not None:\n"
        "                        legacy_setter(material, usage)\n"
        "                    else:\n"
        "                        raise RuntimeError('MaterialEditingLibrary has no safe material usage setter.')\n"
        "                after = bool(unreal.MaterialEditingLibrary.has_material_usage(material, usage))\n"
        "                row['before'] = before\n"
        "                row['after'] = after\n"
        "                row['changed'] = before != after\n"
        "                row['success'] = after\n"
        "            except Exception as exc:\n"
        "                row['error'] = repr(exc)\n"
        "            rows.append(row)\n"
        "    try:\n"
        "        material.post_edit_change()\n"
        "        material.mark_package_dirty()\n"
        "    except Exception:\n"
        "        pass\n"
        "    return rows\n"
        "\n"
        "folder_path = spec['folder_path']\n"
        "asset_name = spec['asset_name']\n"
        "target_path = f\"{folder_path}/{asset_name}\"\n"
        "route = spec.get('route') or {}\n"
        "mat_ref = None\n"
        "if route:\n"
        "    created = MAT.create_material(\n"
        "        target_path,\n"
        "        str(route.get('domain') or 'Surface'),\n"
        "        str(route.get('shading_model') or 'DefaultLit'),\n"
        "        str(route.get('blend_mode') or 'Opaque'),\n"
        "        bool(route.get('two_sided')),\n"
        "        bool(route.get('use_material_attributes')),\n"
        "    )\n"
        "    create_row = {\n"
        "        'success': bool(created.success),\n"
        "        'error': created.error,\n"
        "        'output': {'returnValue': {'refPath': created.path}},\n"
        "        'route': 'local-create-material-with-route',\n"
        "        'requested_route': route,\n"
        "    }\n"
        "    if created.success:\n"
        "        mat_ref = created.path\n"
        "else:\n"
        "    create_row = run_tool('toolset_registry.toolsets.core.material.MaterialTools.create', {\n"
        "        'folder_path': folder_path,\n"
        "        'asset_name': asset_name,\n"
        "    })\n"
        "    if create_row['success'] and isinstance(create_row['output'], dict):\n"
        "        mat_ref = (create_row['output'].get('returnValue') or {}).get('refPath')\n"
        "report['material'] = create_row\n"
        "if not mat_ref:\n"
        "    mat_ref = f\"{target_path}.{asset_name}\"\n"
        "requested_usage_flags = route.get('usage_flags') or spec.get('usage_flags') or []\n"
        "report['usage_flags'] = apply_usage_flags(mat_ref, requested_usage_flags)\n"
        "\n"
        "expr_refs = {}\n"
        "expr_guids = {}\n"
        "for item in spec.get('expressions') or []:\n"
        "    add_result = MAT.add_material_expression(\n"
        "        mat_ref,\n"
        "        item['expression_class'],\n"
        "        int(item.get('x', 0)),\n"
        "        int(item.get('y', 0)),\n"
        "    )\n"
        "    alias = item.get('alias') or item['expression_class'].rsplit('.', 1)[-1]\n"
        "    row = {'success': bool(add_result.success), 'error': add_result.error, 'resolved_class': add_result.resolved_class}\n"
        "    if add_result.success:\n"
        "        graph = MAT.get_material_graph(mat_ref)\n"
        "        matches = []\n"
        "        for node in list(graph.nodes):\n"
        "            if node.class_name == add_result.resolved_class.replace('MaterialExpression', '') and int(node.x) == int(item.get('x', 0)) and int(node.y) == int(item.get('y', 0)):\n"
        "                matches.append(node)\n"
        "        if matches:\n"
        "            target = matches[-1]\n"
        "            expr_guids[alias] = target.guid\n"
        "            expr_refs[alias] = target.class_name\n"
        "            row['key_properties'] = target.key_properties\n"
        "            row['caption'] = target.caption\n"
        "        else:\n"
        "            row['success'] = False\n"
        "            row['error'] = 'Could not map new expression to graph node after creation.'\n"
        "    report['expressions'].append({'alias': alias, 'result': row})\n"
        "for item in spec.get('expression_properties') or []:\n"
        "    alias = item['expression']\n"
        "    expr_guid = expr_guids.get(alias)\n"
        "    if expr_guid is None:\n"
        "        report.setdefault('expression_properties', []).append({'target': item, 'success': False, 'error': f\"Unknown expression alias: {alias}\"})\n"
        "        continue\n"
        "    prop_results = []\n"
        "    for prop in item.get('properties') or []:\n"
        "        ok = MAT.set_material_expression_property(\n"
        "            mat_ref,\n"
        "            expr_guid,\n"
        "            prop['name'],\n"
        "            str(prop['value']),\n"
        "        )\n"
        "        prop_results.append({'name': prop['name'], 'value': prop['value'], 'success': bool(ok)})\n"
        "    report.setdefault('expression_properties', []).append({'expression': alias, 'results': prop_results})\n"
        "\n"
        "for item in spec.get('connections') or []:\n"
        "    from_guid = expr_guids.get(item['from_expression'])\n"
        "    to_guid = expr_guids.get(item['to_expression'])\n"
        "    if from_guid is None or to_guid is None:\n"
        "        report['connections'].append({'target': item, 'success': False, 'error': 'Unknown expression alias in connection'})\n"
        "        continue\n"
        "    ok = MAT.connect_material_expressions(\n"
        "        mat_ref,\n"
        "        from_guid,\n"
        "        str(item.get('from_output_name', '')),\n"
        "        to_guid,\n"
        "        item['to_input_name'],\n"
        "    )\n"
        "    row = {'success': bool(ok), 'error': '' if ok else 'connect_material_expressions returned false'}\n"
        "    report['connections'].append({'target': item, 'result': row})\n"
        "\n"
        "for item in spec.get('output_connections') or []:\n"
        "    expr_guid = expr_guids.get(item['expression'])\n"
        "    if expr_guid is None:\n"
        "        report['connections'].append({'target': item, 'success': False, 'error': f\"Unknown expression alias: {item['expression']}\"})\n"
        "        continue\n"
        "    property_name = str(item['material_property'])\n"
        "    if property_name.startswith('MP_'):\n"
        "        property_name = property_name[3:]\n"
        "    ok = MAT.connect_material_output(\n"
        "        mat_ref,\n"
        "        expr_guid,\n"
        "        str(item.get('output_name', '')),\n"
        "        property_name,\n"
        "    )\n"
        "    row = {'success': bool(ok), 'error': '' if ok else 'connect_material_output returned false'}\n"
        "    report['connections'].append({'target': item, 'result': row})\n"
        "\n"
        "if spec.get('recompile', True):\n"
        "    ok = MAT.compile_material(mat_ref, False)\n"
        "    report['recompile'] = {'success': bool(ok), 'error': '' if ok else 'compile_material returned false'}\n"
        "report['save'] = run_tool('toolset_registry.toolsets.core.asset.AssetTools.save_assets', {'asset_paths': [mat_ref]})\n"
        "report['material_ref'] = mat_ref\n"
        "report['expression_aliases'] = list(expr_guids.keys())\n"
        "final_info = MAT.get_material_info(mat_ref)\n"
        "report['final_usage_flags'] = list(final_info.usage_flags) if final_info.found else []\n"
        "print(json.dumps(report, ensure_ascii=False))\n"
    )


def render_build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Material Toolset Builder",
        "",
        f"- Material: `{report.get('material_ref')}`",
        f"- Material create success: `{(report.get('material') or {}).get('success')}`",
        "",
        "## Expressions",
        "",
    ]
    for item in report.get("expressions") or []:
        result = item.get("result") or {}
        lines.append(f"- `{item.get('alias')}` success=`{result.get('success')}` error=`{result.get('error')}`")
    if report.get("usage_flags"):
        lines.extend(["", "## Usage Flags", ""])
        for item in report.get("usage_flags") or []:
            lines.append(
                f"- `{item.get('requested')}` enum=`{item.get('enum')}` "
                f"success=`{item.get('success')}` changed=`{item.get('changed')}` error=`{item.get('error')}`"
            )
        lines.append(f"- Final usage flags: `{', '.join(report.get('final_usage_flags') or []) or 'none'}`")
    if report.get("expression_properties"):
        lines.extend(["", "## Expression Properties", ""])
        for item in report.get("expression_properties") or []:
            lines.append(f"- `{item.get('expression')}`")
            for result in item.get("results") or []:
                lines.append(f"  - `{result.get('name')}`=`{result.get('value')}` success=`{result.get('success')}`")
    lines.extend(["", "## Output Connections", ""])
    for item in report.get("connections") or []:
        if "result" in item:
            result = item["result"]
            lines.append(f"- `{item['target']}` success=`{result.get('success')}` error=`{result.get('error')}`")
        else:
            lines.append(f"- `{item.get('target')}` success=`False` error=`{item.get('error')}`")
    lines.extend(
        [
            "",
            f"- Recompile success: `{(report.get('recompile') or {}).get('success')}`",
            f"- Save success: `{(report.get('save') or {}).get('success')}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_recipe_markdown(report: dict[str, Any]) -> str:
    route = report.get("route") or {}
    target = report.get("target_material") or {}
    lines = [
        "# Material Toolset Recipe",
        "",
        f"- Recipe: `{report.get('recipe')}`",
        f"- Effect / layer: `{report.get('effect')}/{report.get('layer')}`",
        f"- Target material: `{target.get('material_ref')}`",
        f"- Route: domain=`{route.get('domain')}` blend=`{route.get('blend_mode')}` shading=`{route.get('shading_model')}` two_sided=`{route.get('two_sided')}`",
        f"- Builder spec: `{report.get('builder_spec_path')}`",
        "",
        "## Parameters",
        "",
    ]
    for item in report.get("parameters") or []:
        lines.append(f"- `{item.get('name')}` {item.get('type')} default=`{item.get('default')}` - {item.get('purpose')}")
    lines.extend(["", "## Texture Requirements", ""])
    for item in report.get("texture_requirements") or []:
        lines.append(f"- `{item.get('slot')}` `{item.get('name')}` required=`{item.get('required')}` channels=`{item.get('channels')}`")
    lines.extend(["", "## Preview And Audit", ""])
    lines.append(f"- Preview: `{(report.get('preview_plan') or {}).get('command')}`")
    for command in report.get("audit_plan") or []:
        lines.append(f"- Audit: `{command}`")
    lines.extend(["", "## Warnings", ""])
    for warning in report.get("warnings") or []:
        lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def render_refactor_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Material Toolset Refactor Plan",
        "",
        f"- Effect / layer / label: `{report.get('effect')}/{report.get('layer')}/{report.get('label')}`",
        f"- Target material: `{report.get('target_material')}`",
        f"- Source graph diff: `{report.get('source_graph_diff_report')}`",
        f"- Patch spec: `{report.get('patch_spec_path')}`",
        "",
        "## Operations",
        "",
    ]
    for item in report.get("operations") or []:
        lines.append(f"- `{item.get('operation')}` risk=`{item.get('risk')}` - {item.get('intent')}")
        for guardrail in item.get("guardrails") or []:
            lines.append(f"  Guardrail: {guardrail}")
    lines.extend(["", "## Validation Plan", ""])
    for command in report.get("validation_plan") or []:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Next Actions", ""])
    for item in report.get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command_build(args: argparse.Namespace) -> int:
    ctx = resolve_root_context(args.root)
    spec = expand_templates(load_spec(args.spec))
    effect = slugify(args.effect or spec.get("asset_name") or "material-toolset-builder")
    client = BridgeClient(ctx.skill_root, project=args.project, endpoint=args.endpoint, timeout_seconds=args.timeout)
    client.ping()
    report = client.exec_json(build_ue_script(spec))
    out = Path(args.out) if args.out else ctx.material_root / "toolset-material-build" / effect / "material-toolset-builder.json"
    save_json(out, report)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_build_markdown(report))
    print(out)
    return 0


def command_recipe(args: argparse.Namespace) -> int:
    report, out, spec_path = build_recipe_report(args)
    save_json(out, report)
    if spec_path:
        save_json(spec_path, report["builder_spec"] or make_recipe_builder_spec(args, RECIPE_DEFINITIONS[args.recipe_key]))
    if args.markdown:
        write_text(out.with_suffix(".md"), render_recipe_markdown(report))
    if args.execute:
        build_args = argparse.Namespace(
            root=args.root,
            spec=str(spec_path),
            project=args.project,
            endpoint=args.endpoint,
            timeout=args.timeout,
            effect=f"{report.get('effect')}-{report.get('layer')}",
            out=args.build_report_out,
            markdown=args.markdown,
        )
        command_build(build_args)
    print(out)
    return 0


def command_refactor_plan(args: argparse.Namespace) -> int:
    report, out = build_refactor_plan(args)
    save_json(out, report)
    save_json(Path(report["patch_spec_path"]), report["patch_spec"])
    if args.markdown:
        write_text(out.with_suffix(".md"), render_refactor_markdown(report))
    print(out)
    return 0


def command_list_recipes(args: argparse.Namespace) -> int:
    rows = {
        key: {
            "title": value.get("title"),
            "intent": value.get("intent"),
            "carrier": value.get("carrier"),
            "route": value.get("route"),
        }
        for key, value in sorted(RECIPE_DEFINITIONS.items())
    }
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for key, value in rows.items():
            print(f"{key}: {value['title']} ({value['carrier']})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build UE material recipes and safe graph refactor plans.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Execute a low-level builder spec through UnrealBridge and MaterialTools.")
    add_build_args(build)
    build.set_defaults(func=command_build)

    recipe = sub.add_parser("recipe", help="Generate a high-level material recipe plan and executable builder spec.")
    recipe.add_argument("recipe", help="Recipe key, for example fire_flipbook, fire_ribbon_additive, fire_ribbon_additive_android, decal_stain, two_sided_foliage, basic_water, energy_ribbon, dissolve_edge.")
    recipe.add_argument("--root", default="auto")
    recipe.add_argument("--effect")
    recipe.add_argument("--layer")
    recipe.add_argument("--intent")
    recipe.add_argument("--carrier")
    recipe.add_argument("--folder-path")
    recipe.add_argument("--asset-name")
    recipe.add_argument("--out")
    recipe.add_argument("--build-spec-out")
    recipe.add_argument("--build-report-out")
    recipe.add_argument("--inline-build-spec", action="store_true")
    recipe.add_argument("--execute", action="store_true", help="Also create the material in UE using the generated builder spec.")
    recipe.add_argument("--project")
    recipe.add_argument("--endpoint")
    recipe.add_argument("--timeout", type=int, default=180)
    recipe.add_argument("--markdown", action="store_true")
    recipe.set_defaults(func=command_recipe)

    refactor = sub.add_parser("refactor-plan", help="Generate a narrow graph refactor plan from graph diff evidence or explicit operations.")
    refactor.add_argument("--root", default="auto")
    refactor.add_argument("--graph-diff-report")
    refactor.add_argument("--material-path")
    refactor.add_argument("--operation", action="append", default=[], help="Operation to include, such as add-fresnel-layer, add-depth-fade, add-detail-normal, restore-route, repair-outputs, normalize-parameters.")
    refactor.add_argument("--effect")
    refactor.add_argument("--layer")
    refactor.add_argument("--label")
    refactor.add_argument("--out")
    refactor.add_argument("--patch-spec-out")
    refactor.add_argument("--markdown", action="store_true")
    refactor.set_defaults(func=command_refactor_plan)

    recipes = sub.add_parser("list-recipes", help="List built-in high-level material recipes.")
    recipes.add_argument("--json", action="store_true")
    recipes.set_defaults(func=command_list_recipes)
    return parser


def add_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("spec", help="Path to the builder spec JSON.")
    parser.add_argument("--root", default="auto")
    parser.add_argument("--project")
    parser.add_argument("--endpoint")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--effect")
    parser.add_argument("--out")
    parser.add_argument("--markdown", action="store_true")


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build simple material graphs through confirmed editor material toolsets.")
    add_build_args(parser)
    parser.set_defaults(func=command_build)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"build", "recipe", "refactor-plan", "list-recipes"}
    if argv and argv[0] not in commands and not argv[0].startswith("-"):
        parser = build_legacy_parser()
    else:
        parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
