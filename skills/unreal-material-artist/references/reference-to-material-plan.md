# Reference To Material Plan

## Use This When

- A material task starts from a reference image, case-study screenshot, tutorial screenshot, online example, or short visual target.
- You need a front-door artifact before building graph nodes, generating textures, or creating material instances.
- The next steps should be reusable by preview, audit, delivery, and regression tooling.

## Purpose

`reference_to_material_plan.py` turns an early material target into a structured work order. It does not replace a real visual readback of the reference. Its job is to capture the target, infer a likely UE route, list texture and parameter needs, and produce preview/audit commands that downstream tools can consume.

The first version is intentionally heuristic. It uses the target text, filenames, optional source URLs, selected profile/carrier, and user-supplied observations. When a reference image is available, pass observations from the visual read before treating the plan as implementation-ready.

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/reference_to_material_plan.py new --effect WingEcho --layer RibbonTrail --reference D:/Refs/wing_echo.png --cache-reference --target "blue energy ribbon trail with sharp bright core and smoky edge falloff" --profile energy --carrier ribbon --observation "center line is cyan-white, edge fades into soft blue smoke" --must-match "bright core,blue falloff,broken edge alpha" --emit-contract --markdown
```

Validate an existing plan:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/reference_to_material_plan.py validate D:/path/to/reference-to-material-plan.json --markdown
```

## Output Contract

The JSON report includes:

- `source`: reference paths, source URLs, target description, cached copies when `--cache-reference` is used, and image metadata when readable.
- `visual_contract`: observations, style tags, must-match traits, acceptable tradeoffs, and open questions.
- `carrier_contract`: carrier, UV expectation, runtime owner, Particle Color, and Dynamic Parameter assumptions.
- `material_route`: domain, blend mode, shading model, output pins, usage flags, and sorting/depth notes.
- `texture_requirements`: role, channels, resolution, grid, sRGB expectation, source action, QA tool, and UE import review tool.
- `parameters`: artist/runtime controls with type, default, range, owner, and purpose.
- `budgets`: platform, instruction budget, sampler budget, texture memory budget, and overdraw risk.
- `preview_plan`: material path placeholder plus render/sweep command templates.
- `audit_plan`: references to read, audit commands, texture QA commands, and acceptance checks.
- `findings`: warnings or info about missing reference assets, missing visual observations, or heuristic assumptions.

When `--emit-contract` is passed, the tool also writes a compatible `material_contract.py` JSON/Markdown seed under `material-delivery/contracts/`.

## Profiles

Supported profiles:

- `surface`
- `fire`
- `smoke`
- `energy`
- `heat_haze`
- `water`
- `foliage`
- `decal`
- `post_process`
- `ui`
- `glass`
- `dissolve`
- `landscape`
- `character`
- `environment`
- `custom`

Use `--profile auto` for quick scaffolding, but lock the profile explicitly when the reference is important. Auto mode is based on keywords and filenames, not full image understanding.

## Recommended Workflow

1. Register or pass the reference path and use `--cache-reference` when the file should remain durable.
2. Add at least one `--observation` from direct visual inspection.
3. Add `--must-match` for traits that should survive optimization.
4. Generate the plan with `--emit-contract --markdown`.
5. Search the approved material asset library before creating any generic texture.
6. Use the generated texture QA commands before import.
7. Build the first material route and render the generated preview command on the intended carrier.
8. Run the generated audit commands before accepting the material.

## Important Limits

- A plan created with no observations is a route scaffold, not a visual approval.
- A reference file that cannot be read or cached should be treated as an open evidence gap.
- The generated material path is a placeholder. Replace it with the real UE asset path after authoring.
- Generated texture requirements are candidate requirements. If the reference proves a texture is unnecessary or needs a different channel layout, edit the plan before building.
