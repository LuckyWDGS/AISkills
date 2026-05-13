# Material Audit Workflow

## Goal

Read the live material, understand what actually affects the output, verify the visual result, then identify cost and cleanup risks without weakening the approved look.

## Audit Order

1. Resolve the asset.
   Confirm the path loads and whether it is a `Material`, `MaterialInstance`, or `MaterialFunction`.

2. Read material metadata.
   Capture domain, blend mode, shading model, `TwoSided`, usage flags, parent material, parameter lists, static switches, instruction count, sampler count, compile errors, and shader stat readiness.

3. Trace outputs backward.
   Start from `BaseColor`, `EmissiveColor`, `Opacity`, `OpacityMask`, `Normal`, `WorldPositionOffset`, `PixelDepthOffset`, `Refraction`, or `MaterialAttributes`. Classify nodes as:
   - live output chain
   - disconnected experiment branch
   - comment or organization-only
   - stale or unused parameter

4. Inspect Material Instance overrides.
   Compare MI overrides with parent parameters. Flag overrides whose parent parameter no longer exists, static switches that create expensive permutations, and inherited values that hide the real tuning layer.

5. Review texture inputs.
   Check sampler type, sRGB, compression, size, mips, channel packing, sampler source, duplicate samples, and whether the texture is a placeholder.

6. Review HLSL and Custom nodes.
   Prefer graph nodes for simple operations. For Custom nodes, check input names, output type, code body, includes, unsupported intrinsics, manual texture sampling, loops, branches, derivatives, and whether a feature/quality fallback is needed.

7. Review visual context.
   Ask what carrier uses this material: mesh, sprite, ribbon, decal, UI, post-process, landscape, or fullscreen plane. Cost changes dramatically with screen coverage and overdraw.

8. Verify.
   Use compile results, material preview, controlled capture, or in-level capture. Do not accept a material based only on editor UI graph screenshots.

9. Optimize from the verified look.
   Once the effect reads correctly, classify cost issues into no-look-change fixes, acceptable prototype risks, and visual tradeoffs. Apply no-look-change fixes first. Do not replace the target look with a cheaper approximation unless the user or lead accepts that visible change.

## CLI

Run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Path/M_Material --project UnrealAI --markdown --instruction-budget 120 --sampler-budget 4
```

Optional:

```powershell
--include-raw-graph
--out C:/path/material-audit.json
--endpoint 127.0.0.1:12345
```

Outputs:

- JSON audit report.
- Markdown summary when `--markdown` is set.
- Data under `<project>/.codex/session/material-delivery/` by default.

## Review Findings

Treat these as high priority:

- Compile errors.
- Missing or wrong material domain.
- Wrong blend mode for the carrier.
- Missing renderer usage flag when the material must work with Niagara sprites/ribbons/mesh particles.
- Stale MI override that makes tuning confusing.
- Dead branches connected to no output.
- Manual texture sampling inside Custom HLSL without a concrete reason.
- Translucent material with large screen coverage and multiple samples.
- Refraction, Pixel Depth Offset, or expensive depth operations on mobile.
- Static switch permutations created casually in many instances.

Treat these as tuning risks:

- Emissive is technically valid but unbounded or washed out.
- Opacity math ignores particle alpha or instance controls.
- Normal map is sampled as color or mask.
- Mask texture is imported as sRGB.
- Flow map or packed mask is AI-generated but unvalidated.
- Parameter names describe node history instead of user intent.

Treat these as visual-regression risks:

- Replacing a reference-specific mask, foam pattern, leaf cutout, rune shape, water ripple language, or painterly texture with generic noise because it is cheaper.
- Lowering texture size until the important silhouette, brushwork, thin lines, edge breakup, or alpha shape no longer matches the target.
- Removing a layer, motion path, refraction, translucency, subsurface, clear coat, WPO, or special shading model before proving an equivalent lower-cost route.
- Passing shader budget while the preview no longer matches the material contract.

## Acceptance Criteria

A production material should have:

- Clear output chain.
- No compile errors.
- No stale MI overrides.
- No dead branches unless explicitly documented as disabled variants.
- Named parameters grouped by user-facing purpose.
- Known texture requirements and import settings.
- Platform-appropriate instruction and sampler cost.
- Preview or runtime capture checked in the intended visual context.
- Visual target confirmed before final performance optimization, with any visible simplification labeled as a tradeoff variant rather than the default result.
