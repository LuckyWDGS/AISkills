# Closed-Loop Tool Suite

This suite is core to the skill, not optional scaffolding.

## Folder Split

- `tools/`
  User-facing CLIs. These are the commands the skill should invoke directly.
- `scripts/`
  Shared Python implementation, manifest logic, image ops, and Unreal Bridge wrappers.
- `references/`
  Workflow docs, playbooks, and usage notes for the skill itself.

This separation keeps reusable logic out of the CLIs, and keeps skill documentation independent from runtime tooling.

## Tools

### `tools/reference_cache.py`

Purpose:
- cache authoritative design references locally
- separate `active / rejected / debug`
- produce cropped evidence images
- produce larger HQ clarity copies for later anchored generation

Key commands:

```powershell
python tools/reference_cache.py register C:\ref\wing.png --effect WingEcho --label transparent-anchor
python tools/reference_cache.py crop <entry_id> --left 180 --top 90 --right 920 --bottom 760
python tools/reference_cache.py hq <entry_id> --scale 2.0 --sharpen 1.1
python tools/reference_cache.py set-status <entry_id> --status rejected
```

### `tools/visual_layer_map.py`

Purpose:
- record each visual layer's evidence
- map it to its UE carrier
- record the required textures, material route, Niagara route, and self-test checks

Key commands:

```powershell
python tools/visual_layer_map.py init --effect WingEcho --anchor-reference-id ref_001
python tools/visual_layer_map.py add-layer --effect WingEcho --name 翅膀声波残影 --field ue_carrier.primary=RibbonTrail --field evidence.motion_cue=wing-peak-burst
python tools/visual_layer_map.py export-md --effect WingEcho
```

### `tools/material_audit.py`

Purpose:
- read live material graph structure through Unreal Bridge
- report output-connected chains
- report dead branches
- report stale MI overrides
- report compile findings, instruction counts, and sampler counts

### `tools/niagara_audit.py`

Purpose:
- inspect Niagara system emitter handles
- inspect likely emitter roles
- inspect renderer types, material bindings, sim target, bounds, and event-handler presence
- emit structural warnings before visual tuning

### `tools/controlled_preview.py`

Purpose:
- create deterministic preview captures that do not rely on editor UI screenshots
- support material previews, fixed-camera actor captures, and first-pass Niagara captures

### `tools/design_compare_checklist.py`

Purpose:
- generate the design-comparison checklist for a layer
- track pass / fail / needs-tuning decisions for silhouette, brightness, density, width, trail direction, echo spacing, and dynamic rhythm

### `tools/asset_cleanup.py`

Purpose:
- safely report stale local artifacts
- optionally delete tagged Unreal preview actors and disposable local artifacts after a report is reviewed

### `tools/parameter_tuning_log.py`

Purpose:
- record what was tuned
- record why it was tuned
- record which visual gap it was trying to close

## Default Data Location

When `--root` is omitted, tools auto-detect a project root and write under:

```text
<project>/.codex/session/vfx-delivery/
```

This keeps cached references, audits, previews, cleanup reports, and tuning logs tied to the active Unreal project instead of polluting the skill repo.

## Recommended Order

1. `reference_cache.py`
2. `visual_layer_map.py`
3. `controlled_preview.py`
4. `material_audit.py`
5. `niagara_audit.py`
6. `design_compare_checklist.py`
7. `parameter_tuning_log.py`
8. `asset_cleanup.py`

That order matches the closed loop:

reference anchor -> visual evidence map -> carrier-aware preview -> structural audit -> design gap review -> tuning record -> cleanup.
