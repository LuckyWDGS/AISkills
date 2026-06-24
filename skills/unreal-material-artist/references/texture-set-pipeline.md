# Texture Set Pipeline

## Use This When

- A material has a full texture set rather than one isolated texture.
- BaseColor, Normal, RMA/ORM, Opacity, or Emissive files need to be checked together.
- Roughness, Metallic, and AO arrive as separate grayscale maps and should become one packed runtime texture.
- Imported UE texture assets need a batch `texture_import_fix.py` spec.
- `delivery_packager.py` needs one texture-set report instead of many disconnected single-texture reports.

## Purpose

`texture_set_pipeline.py` upgrades single-texture QA into set-level material input QA. It checks:

- slot coverage for BaseColor, Normal, packed RMA/ORM/MRA, Opacity, and Emissive
- filename role detection and expected suffixes
- required slot presence
- matching dimensions across required slots
- power-of-two and max-dimension rules
- normal-map first-pass signal sanity
- packed-channel semantics
- opacity mask signal range
- optional UE import audit reports for actual sRGB/compression mismatches
- optional import-fix batch spec emission
- optional RMA/ORM/MRA packing from Roughness/Metallic/AO, with Opacity in alpha when requested

The tool is report-first and safe by default. It only writes a packed image when `--pack-rma-out` is supplied, and it only emits an import-fix batch spec when `--emit-import-fix-spec` is supplied.

## Table Of Contents

- [Audit A Folder](#audit-a-folder)
- [Audit Explicit Files](#audit-explicit-files)
- [Emit UE Import Fix Spec](#emit-ue-import-fix-spec)
- [Merge UE Import Audit Evidence](#merge-ue-import-audit-evidence)
- [Pack Roughness Metallic AO](#pack-roughness-metallic-ao)
- [JSON Spec Shape](#json-spec-shape)
- [Gate Meaning](#gate-meaning)
- [Delivery Flow](#delivery-flow)

## Audit A Folder

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --scan D:/Textures/WingEcho --packed-convention ORM --emit-import-fix-spec --markdown
```

The report writes to:

```text
<project>/.codex/session/material-delivery/texture-sets/<effect-layer>/texture-set-pipeline.json
```

When `--markdown` is set, a sidecar `.md` summary is written next to the JSON.

## Audit Explicit Files

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --base-color D:/Textures/T_WingEcho_BaseColor.png --normal D:/Textures/T_WingEcho_Normal.png --rma D:/Textures/T_WingEcho_ORM.png --opacity D:/Textures/T_WingEcho_Opacity.png --emissive D:/Textures/T_WingEcho_Emissive.png --packed-convention ORM --markdown
```

Use `--require-opacity` or `--require-emissive` when those slots are mandatory for the material route. Use `--no-require-normal` or `--no-require-rma` for unlit/VFX routes where those inputs are intentionally absent.

For Niagara-facing VFX texture sets, use `--profile vfx-unlit`. That profile keeps the normal import expectations but also warns when texture filenames do not end with `VFX`, for example `T_FireFlipbook_VFX` or `T_SmokeOpacity_VFX`.

## Emit UE Import Fix Spec

If imported UE asset paths are known, add them to the audit:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --base-color D:/Textures/T_WingEcho_BaseColor.png --base-color-asset /Game/Textures/T_WingEcho_BaseColor --normal D:/Textures/T_WingEcho_Normal.png --normal-asset /Game/Textures/T_WingEcho_Normal --rma D:/Textures/T_WingEcho_ORM.png --rma-asset /Game/Textures/T_WingEcho_ORM --emit-import-fix-spec --markdown
```

This writes:

```text
texture-import-fix-batch-spec.json
```

Run it through the existing fixer:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_import_fix.py --batch-spec D:/path/to/texture-import-fix-batch-spec.json --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_import_fix.py --batch-spec D:/path/to/texture-import-fix-batch-spec.json --project UnrealAI --apply --markdown
```

## Merge UE Import Audit Evidence

When you already have `texture_import_audit.py` reports, pass them in:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --scan D:/Textures/WingEcho --import-audit-report D:/reports/texture-import-audit.json --emit-import-fix-spec --markdown
```

The pipeline will attach actual imported settings to slots and report sRGB/compression mismatches against each slot's expected role.

## Pack Roughness Metallic AO

When RMA/ORM is missing but source channels exist:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --effect WingEcho --layer Surface --base-color D:/Textures/T_WingEcho_BaseColor.png --normal D:/Textures/T_WingEcho_Normal.png --roughness D:/Textures/T_WingEcho_Roughness.png --metallic D:/Textures/T_WingEcho_Metallic.png --ao D:/Textures/T_WingEcho_AO.png --pack-rma-out D:/Textures/T_WingEcho_RMA.png --packed-convention RMA --markdown
```

Add opacity into alpha when the material can consume it from the packed texture:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --roughness D:/Textures/Roughness.png --metallic D:/Textures/Metallic.png --ao D:/Textures/AO.png --opacity D:/Textures/Opacity.png --pack-rma-out D:/Textures/T_WingEcho_RMAO.png --pack-opacity-alpha --packed-convention RMA --markdown
```

Conventions:

- `RMA`: `R=Roughness`, `G=Metallic`, `B=AO`
- `ORM`: `R=AO`, `G=Roughness`, `B=Metallic`
- `MRA`: `R=Metallic`, `G=Roughness`, `B=AO`

Record the convention in the material parameter name or material contract. Many teams say "RMA" loosely when they actually mean ORM; this tool makes the channel contract explicit.

## JSON Spec Shape

```json
{
  "effect": "WingEcho",
  "layer": "Surface",
  "textures": {
    "base_color": {
      "file": "D:/Textures/T_WingEcho_BaseColor.png",
      "asset_path": "/Game/Textures/T_WingEcho_BaseColor"
    },
    "normal": {
      "file": "D:/Textures/T_WingEcho_Normal.png",
      "asset_path": "/Game/Textures/T_WingEcho_Normal"
    },
    "rma": {
      "file": "D:/Textures/T_WingEcho_ORM.png",
      "asset_path": "/Game/Textures/T_WingEcho_ORM"
    },
    "opacity": "D:/Textures/T_WingEcho_Opacity.png",
    "emissive": "D:/Textures/T_WingEcho_Emissive.png"
  }
}
```

Run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --spec D:/Textures/wingecho-texture-set.json --packed-convention ORM --emit-import-fix-spec --markdown
```

## Gate Meaning

- `gate.passed=true`: no blocking errors, such as missing required slots, missing files, or failed packing.
- `gate.ready_for_import=true`: no errors and no warnings.
- Warnings are still important. Typical warnings include mismatched required resolutions, suspicious packed-channel data, missing mask signal, wrong imported sRGB, or wrong compression.

`passed=true` is not artistic approval. It only means the texture set is structurally ready enough to continue material hookup or import review.

## Delivery Flow

1. Generate, source, or receive the texture files.
2. Run `texture_set_pipeline.py audit`.
3. If RMA/ORM is missing but separate channels exist, rerun with `--pack-rma-out`.
4. If UE asset paths exist, emit the import-fix batch spec.
5. Run `texture_import_fix.py --batch-spec`.
6. Rerun `texture_import_audit.py` and pass the result back into `texture_set_pipeline.py`.
7. Add the final `texture-set-pipeline.json` to `delivery_packager.py --texture-report`.
