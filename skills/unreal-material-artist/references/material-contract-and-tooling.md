# Material Contract And Tooling

## Use This When

- A Niagara effect layer needs a material and the carrier contract must be clear before graph work.
- A material task risks becoming vague: "make it glow", "make it smoky", "use a grid", "make it cheaper".
- The material specialist needs to return concrete material-input requirements, texture requirements, and performance risks to the VFX lead.
- You need to decide which tool or script should support the work.

## Capability Gaps To Keep Covered

`unreal-material-artist` should not only generate graph ideas. It should cover these production capabilities:

- Intake contract: renderer, UVs, Particle Color, Dynamic Parameters, blend mode, domain, platform, and budget.
- Graph authoring: material outputs, functions, parameters, instances, Custom HLSL, switches, and fallbacks.
- Texture strategy: generated textures, baked textures, procedural math, flipbooks, atlases, packed masks, ramps, flow maps, and import settings.
- Performance review: instruction count, sampler count, texture bandwidth, overdraw, material domain, blend mode, feature level, and screen coverage.
- Asset hygiene: naming, MI override cleanup, dead graph branches, stale parameters, duplicate samples, wrong sRGB, and oversized textures.
- Delivery: a material contract, texture manifest, import settings, parameter table, audit report, known risks, and acceptance checks.

## Material Contract

Before building or reviewing a material for a Niagara layer, write down:

- Effect and layer name.
- Carrier: sprite, ribbon, mesh, decal, surface, UI, post process, landscape, or unknown.
- UV expectations: mesh UV, ribbon UV along length, sprite SubUV, screen UV, world projection, or custom.
- Expected material inputs from Niagara or another caller: `ParticleColor`, `DynamicParameter`, user parameters, custom attributes, SubImageIndex, or vertex color.
- Material route: domain, blend mode, shading model, two-sided flag, expected output pins.
- Texture requirements: role, channels, resolution, grid, sRGB, compression, alpha, and source.
- Budgets: platform, instruction budget, sampler budget, overdraw risk, texture memory limit.
- Acceptance: how it should look, what must be controllable, and what cost must stay under budget.

Use:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_contract.py new --effect WingEcho --layer RibbonTrail --renderer ribbon --blend-mode Additive --platform PC --dynamic-parameters EdgeBreakup,OpacityScale --markdown
```

Validate an edited contract:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_contract.py validate path/to/material-contract.json --markdown
```

## Texture Asset Report

Use this after `cm-imagegen`, baking, or receiving external texture files:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_asset_report.py D:/textures/WingEcho --role flipbook --grid 8x8 --effect WingEcho --markdown
```

It checks first-pass readiness:

- dimensions and power-of-two status
- alpha availability
- atlas/flipbook grid divisibility
- oversized textures
- role-specific warnings for masks, packed data, flow maps, normals, flipbooks, and atlases

This script is not a replacement for UE import review. It is a fast gate before wasting time wiring a bad generated texture into a material.

## Tooling Roadmap

Current useful tools:

- `material_audit.py`: live UE graph, parameters, stale overrides, instruction and sampler findings.
- `material_contract.py`: handoff contract between VFX lead and material specialist.
- `material_asset_library.py`: reusable asset search, registration, promotion, and library status.
- `texture_asset_report.py`: generated or external texture sanity report.
- `texture_import_audit.py`: Unreal texture import settings, compression, LOD group, mip, sRGB, and resource-size audit.
- `texture_import_fix.py`: safe role-based import repairs for one texture or a batch spec.
- `material_preview.py`: controlled material preview, shader-complexity capture, MI parameter sweeps, Niagara-based sprite/ribbon previews, legacy card previews, and VFX-carrier previews for decal/post-process.
- `material_instance_batch.py`: create many MIs from one JSON spec, apply params, and optionally preview them.
- `runtime_param_trace.py`: trace material parameter sources through MI chain, graph hints, MPC references, and other material-side ownership clues.
- `channel_packer.py`: pack external grayscale masks into RGBA runtime textures with a manifest.
- `flipbook_normalizer.py`: center, crop, optionally rescale, and repack generated flipbook frames.

High-value future tools:

- UE texture import-settings fixer for masks, normals, packed data, flipbooks, and sprite atlases.
- Material contract expander that turns one contract into MI batch specs and preview plans automatically.
- Preview harness refinements beyond the current temporary carrier harnesses, while keeping real Niagara hookup ownership outside this skill.
- Channel unpack / repack validation against expected channel semantics.
- Flipbook QA that detects frame jitter, silhouette drift, and loop discontinuity numerically.

## Material Instance Batch Spec

`material_instance_batch.py` uses a JSON spec like:

```json
{
  "parent_path": "/Game/Materials/M_WingEcho_Master",
  "effect": "WingEcho",
  "reuse_existing": true,
  "preview": {
    "enabled": true,
    "mesh": "shaderball",
    "lighting": "hdri",
    "resolution": 512,
    "yaw": 30.0,
    "pitch": 15.0,
    "distance": 0.0
  },
  "instances": [
    {
      "path": "/Game/Materials/MI_WingEcho_A",
      "params": [
        {"name": "Roughness", "type": "Scalar", "value": "0.35"},
        {"name": "TrailColor", "type": "Vector", "value": "(R=1,G=0.6,B=0.2,A=1)"}
      ]
    }
  ]
}
```

Use this when the material specialist must produce multiple variants fast and still hand back previewable assets to the VFX lead.

## Output Back To Niagara

When returning to `niagara-vfx-artist`, summarize:

- material path or proposed asset name
- required renderer-facing material assumptions
- required Dynamic Parameter or Particle Attribute names from the material side
- required texture imports and channel meanings
- known performance cost
- any carrier change recommendation
- audit or texture report path

Do not just say "material is done". Return the material contract that tells Niagara what the material expects. Do not claim that live Niagara bindings were verified here unless `niagara-vfx-artist` separately confirmed them.
