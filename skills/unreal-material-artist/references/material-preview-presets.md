# Material Preview Presets

## Goal

Make `material_preview.py` behave like a real material specialist preview tool, not just a generic screenshot generator.

Presets define:

- which carrier the preview represents
- which temporary carrier harness to use
- what renderer/material binding assumptions are being made
- whether SubUV is part of the preview contract
- which Dynamic Parameters or particle-side controls should be assumed
- how ribbon UVs are expected to read

The preview tool now scans part of this contract before capture:

- required material `usage_flags`
- whether a SubUV-oriented preset declares a grid
- whether the graph shows evidence of `ParticleColor`
- whether the graph shows evidence of `DynamicParameter`
- whether a ribbon preset at least declares a ribbon UV expectation

Implementation note: `scripts/unreal_material_tools/niagara_contract_audit.py` is an internal helper used by preview/system scan paths. It is not a public `tools/` CLI in this skill; full live Niagara integration probes belong to `niagara-vfx-artist`.

For Niagara-oriented preview presets it now also scans preview-harness facts:

- actual renderer class used by the temporary preview harness
- whether the preview harness really bound the requested material
- whether a sprite preview with SubUV actually set the expected `SubImageSize`

## Table Of Contents

- [Preset File](#preset-file)
- [Current Niagara-Oriented Presets](#current-niagara-oriented-presets)
- [Default Behavior](#default-behavior)
- [Current Meaning Of The Preview](#current-meaning-of-the-preview)
- [Important Limitation](#important-limitation)
- [Contract Scan Meaning](#contract-scan-meaning)
- [Contract Meaning](#contract-meaning)

## Preset File

Stored at:

```text
D:/Skills/skills/unreal-material-artist/assets/material-preview-presets.json
```

## Current Niagara-Oriented Presets

- `niagara_sprite_basic`
  General Niagara sprite material preview.

- `niagara_sprite_subuv_4x4`
  Sprite preview with renderer `SubImageSize = 4x4`.

- `niagara_sprite_subuv_8x8`
  Sprite preview with renderer `SubImageSize = 8x8`.

- `niagara_ribbon_trail`
  Ribbon preview using `AttributeReaderTrails` and the `Followers` emitter as the ribbon material target.

## Default Behavior

When the user asks for:

- `--carrier sprite`
  Default preset is `niagara_sprite_basic`

- `--carrier ribbon`
  Default preset is `niagara_ribbon_trail`

You can override with:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/MI_Foo --carrier sprite --preset niagara_sprite_subuv_4x4 --project UnrealAI --markdown
```

## Current Meaning Of The Preview

- `sprite` / `ribbon`
  Temporary Niagara-system harness. Closer to real Niagara renderer behavior than a plain plane.

- `sprite_card` / `ribbon_card`
  Fast approximation path for quick alpha / UV / emissive checks.

- `decal`
  Temporary wall and DecalActor.

- `post_process`
  Temporary PPV and neutral scene geometry.

## Important Limitation

Even the Niagara-oriented presets are still lightweight preview harnesses. They do not replace:

- the exact project's production Niagara system
- game-specific user parameter hookups
- final animation timing
- effect-type scalability interactions

They are for material review and iteration, not full gameplay validation and not live Niagara hookup validation.

## Contract Scan Meaning

The preflight contract scan is intentionally conservative:

- A warning means "this preset expects something the graph does not clearly prove."
- It does not mean the material is unusable.
- It does mean the user should stop and verify whether the preset choice or the material graph is mismatched.

This is meant to catch obvious preview-contract drift before trusting the screenshot.

The renderer-side preview scan is stronger than the graph-only scan, because it checks what the temporary preview harness actually wired for review. It is still harness validation, not a guarantee that the project's production Niagara system uses the same bindings.

`material_preview.py render --verify-system-path <NiagaraSystem>` can add a provided-system comparison to the preview report. Treat that as external material-side comparison evidence only; it is still not a live integration gate, parameter-write proof, or replacement for `niagara-vfx-artist`.

This skill should stop at material-side preview confidence:

- renderer class can be approximated for preview
- preview material binding can be checked
- SubUV-style preview assumptions can be checked
- obvious contract drift can be warned about

But real Niagara system binding truth, renderer binding exports, semantic channel plumbing, and live attribute ownership belong to `niagara-vfx-artist`.

## Contract Meaning

In practice, this means the preview can tell you whether the material appears compatible with the intended carrier contract, not whether a production Niagara system has correctly supplied every live attribute.
