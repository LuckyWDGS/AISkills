# Material Asset Library

## Goal

Make reusable material-facing textures compound over time instead of re-solving the same noise, mask, distortion, atlas, or flipbook problem from scratch on every task.

The library is not a dump folder. It is a reviewed asset collection with stage, category, role, QA state, and search metadata.

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

## Promote Or Reject

When a candidate proves reusable:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_asset_library.py promote <asset-id> --stage approved --qa-status approved
```

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

If you cannot answer those, it belongs in `candidates` or `rejected`, not `approved`.

## Generation Fallback

If the library search fails:

1. Generate with `cm-imagegen`.
2. QA the generated result.
3. Regenerate if the result is not usable.
4. Only then register it into the library.

That means the library becomes stronger over time, instead of accumulating random pretty but unusable images.
