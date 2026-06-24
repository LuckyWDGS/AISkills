# Material Asset Library

## Goal

Make reusable material-facing textures compound over time instead of re-solving the same noise, mask, distortion, atlas, or flipbook problem from scratch on every task.

The library is not a dump folder. It is a reviewed asset collection with stage, category, role, QA state, and search metadata.

## Table Of Contents

- [Hard Workflow](#hard-workflow)
- [Reference Fidelity Gate](#reference-fidelity-gate)
- [Library Layout](#library-layout)
- [Search First](#search-first)
- [Register A Candidate](#register-a-candidate)
- [Promote Or Reject](#promote-or-reject)
- [Review Standard](#review-standard)
- [Generation Fallback](#generation-fallback)

Related lifecycle step: before registering generated stock, use [generated-texture-qa.md](generated-texture-qa.md) to decide whether the image is a draft, candidate, rejected asset, or UE-ready texture.

## Hard Workflow

For material tasks that may need textures:

1. Search the asset library first.
2. Reuse an `approved` asset if it already fits the job closely enough.
3. If no suitable reusable asset exists, generate or source a candidate.
4. Run QA on the candidate:
   - `texture_asset_report.py` for file-level checks
   - `texture_import_audit.py` after UE import when relevant
   - visual self-review against the material contract
5. Reject or regenerate if it is not good enough.
6. Promote only reviewed assets into `approved`.

Do not silently treat every generated image as reusable library material.

## Reference Fidelity Gate

When the user provides a reference image, online example, approved concept, or asks for a custom material, the reference outranks the asset library.

In that mode, asset-library search is still required, but it only returns candidates. Before reuse, explicitly compare each candidate against the reference contract:

- Style family: realistic, stylized, painterly, anime, graphic, technical, horror, sci-fi, natural, or other stated art direction.
- Pattern language: wave shape, noise frequency, foam breakup, cracks, veins, brush strokes, leaf silhouettes, fire tongues, or other recognizable forms.
- Scale and tiling: texel density, repeat scale, large/medium/small detail balance, visible repetition risk, and whether the material is meant to tile at all.
- Color and value: hue range, contrast, opacity/alpha shape, emissive brightness, roughness/wetness read, and whether color belongs in the texture or in parameters.
- Motion intent: panning, flow, SubUV, distortion, ripple travel, dissolve direction, or whether the texture is static data.
- Technical role: albedo, mask, opacity, foam mask, ripple height, normal source, flow map, packed data, atlas, flipbook, or pure helper noise.
- Carrier fit: plane, mesh, landscape, water surface, decal, UI, card, sprite/ribbon preview harness, or other material carrier.

Reject the candidate if it only matches the category name. A generic `water ripple` texture is not acceptable for a custom water reference if the reference shows stylized brushy foam, shallow tropical caustics, dark storm waves, painterly anime water, oily sci-fi liquid, or a specific shoreline pattern.

Allowed reuse levels:

- **Final reuse**: the asset matches both the technical role and the reference style closely enough after preview.
- **Helper reuse**: the asset can drive subtle breakup, perturbation, or masking without defining the visible style. Record that it is a helper, not the visual identity.
- **Reject/regenerate**: the asset is generic, too simple, wrong scale, wrong style, wrong channel semantics, or would make the material look unlike the reference.

If no approved asset passes this gate, use `cm-imagegen` with the reference image or create a custom texture by DCC/script. Do not simplify the material to fit the library.

## Library Layout

Skill-local root:

```text
D:/Skills/skills/unreal-material-artist/assets/library/
```

Stages:

- `approved/`: default reuse pool
- `candidates/`: promising but not approved yet
- `rejected/`: known bad or misleading assets that should not be reused casually
- `catalog/material-asset-catalog.json`: searchable metadata index

Categories:

- `noise`
- `mask`
- `distortion`
- `flipbook`
- `atlas`
- `ramp`
- `packed`
- `surface`
- `foliage`
- `decal`
- `post_process`
- `other`

## Search First

Search the approved pool:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py search --category distortion --role sprite --tag flow --power-of-two --markdown
```

If the search returns a good fit, reuse it before generating a new one.

For leaf cards or vegetation cutouts:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py search --category foliage --role leaf-card --tag alpha --power-of-two --markdown
```

## Register A Candidate

Register a generated or external file into the library:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py register D:/Temp/new_noise.png --stage candidates --category noise --role surface --tags seamless,organic,mask --qa-status candidate --source-kind generated
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py register D:/Temp/leaf_card.png --stage candidates --category foliage --role leaf-card --tags alpha,two-sided,masked --qa-status candidate --source-kind generated --audit-role foliage
```

This stores the asset under the skill-local library, indexes it, and records searchable metadata.

Register a UE material asset directly into the reusable library:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py register-material /Game/Materials/M_Foo_Decal --stage candidates --category decal --role decal-material --project UnrealAI --endpoint 127.0.0.1:8628
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py register-material /Game/Materials/M_Foo_PostProcess --stage candidates --category post_process --role post-process-material --project UnrealAI --endpoint 127.0.0.1:8628
```

For auto-rebuilt legal materials, use the direct rebuild path:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_domain_rebuilder.py /Game/Materials/M_SurfaceLike DeferredDecal --register-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_domain_rebuilder.py /Game/Materials/M_SurfaceLike PostProcess --register-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --markdown
```

Or let preview recovery rebuild and register in one pass:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_SurfaceLike --carrier decal --register-rebuilt-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_preview.py render /Game/Materials/M_SurfaceLike --carrier post_process --register-rebuilt-candidate --project UnrealAI --endpoint 127.0.0.1:8628 --width 320 --height 180 --markdown
```

## Promote Or Reject

When a candidate proves reusable:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py promote <asset-id> --stage approved --qa-status approved
```

Or gate it through report-backed self-review:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py auto-promote <asset-id> --self-review approved --report-path D:/path/to/material-preview.json --apply
```

When a material asset reaches `approved`, the library now also writes a higher-level delivery report under the session material-delivery folder. That report summarizes:

- whether the asset is approved for reuse
- the rebuilt source and target material
- the preview carrier and preview image used for approval
- gate warnings/errors
- the review gate decision

This means rebuilt-material approval is no longer only visible inside the catalog state change.

When it turns out misleading or poor:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py promote <asset-id> --stage rejected --qa-status rejected
```

## Review Standard

An asset is reusable only when you can answer:

- What category is it?
- What role is it for?
- Is it power-of-two?
- Does it tile or not?
- Does it need alpha?
- If it is atlas/flipbook, what is the grid?
- What UE import settings does it want?
- What kind of material job is it actually good for?
- For foliage, does it contain a real cutout alpha and avoid visible edge halos on a two-sided masked card?
- If the task is custom/reference-driven, what exact reference traits does it match, and what traits does it not match?

If you cannot answer those, it belongs in `candidates` or `rejected`, not `approved`.

## Generation Fallback

If the library search fails:

1. Generate with `cm-imagegen`.
2. QA the generated result.
3. Regenerate if the result is not usable.
4. Only then register it into the library.

That means the library becomes stronger over time, instead of accumulating random pretty but unusable images.
