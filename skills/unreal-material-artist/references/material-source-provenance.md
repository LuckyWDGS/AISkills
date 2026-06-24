# Material Source Provenance

## Use This When

- Texture origin, generation prompt, original file, import settings, or packed-channel history may be lost during delivery.
- A material should become reusable stock and needs source/rights/import metadata.
- RMA/ORM/Opacity/Emissive inputs were generated, repaired, packed, or imported through several tools.

## Purpose

`material_source_provenance.py` builds a texture provenance manifest for material delivery. It combines:

- material contract texture requirements
- delivery package texture requirements
- `texture_set_pipeline.py` slots and RMA pack records
- `texture_asset_report.py` file QA
- `texture_import_audit.py` and `texture_import_fix.py` import settings
- `channel_packer.py` channel-source manifests
- optional source manifest JSON with prompts, originals, rights, and reuse notes

It is read-only and does not import or edit textures.

## Typical Commands

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_source_provenance.py --package D:/reports/material-delivery-package.json --texture-set-report D:/reports/texture-set-pipeline.json --import-audit-report D:/reports/texture-import-audit.json --source-manifest D:/reports/source-manifest.json --markdown
```

Require complete provenance before reuse:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_source_provenance.py --source-manifest D:/reports/source-manifest.json --texture-set-report D:/reports/texture-set-pipeline.json --import-audit-report D:/reports/texture-import-audit.json --require-complete --require-license --markdown
```

## Source Manifest Shape

```json
{
  "textures": [
    {
      "slot": "opacity",
      "role": "mask",
      "file_path": "D:/Textures/T_WingEcho_Opacity_VFX.png",
      "asset_path": "/Game/Textures/T_WingEcho_Opacity_VFX",
      "source_kind": "cm-imagegen",
      "source_prompt": "cyan ribbon opacity mask with broken energetic edge",
      "original_file": "D:/Refs/wingecho-reference.png",
      "license": "project-owned",
      "reuse_notes": "Approved for WingEcho VFX material reuse."
    }
  ]
}
```

## Output

Reports write under:

```text
<project>/.codex/session/material-delivery/source-provenance/<effect>/material-source-provenance.json
```

Important fields:

- `textures[]`: one provenance record per texture or packed output.
- `textures[].packed_sources[]`: source-channel origin for packed textures.
- `textures[].import_settings`: expected, audited, or fixed UE import settings.
- `textures[].reuse_eligibility`: whether the texture is ready for reuse review.
- `gate.provenance_complete`: true only when no provenance warning/error remains.
