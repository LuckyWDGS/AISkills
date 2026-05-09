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

### `tools/reference_acceptance.py`

Purpose:
- record reference approval state
- lock one anchor as the authoritative design image
- keep clarity and authority notes attached to the anchor

### `tools/layer_evidence.py`

Purpose:
- suggest hotspot crops from a reference
- attach a crop and visible evidence to one layer
- push that evidence back into the layer map

### `tools/preview_approval.py`

Purpose:
- gate preview approval before implementation
- track pass / revise / reject state with structured difference notes

### `tools/asset_plan.py`

Purpose:
- derive a first-pass texture/material/Niagara asset plan from the layer map
- attach naming and platform budget guidance before implementation

### `tools/integration_plan.py`

Purpose:
- define notify / socket / owner / user-parameter hookup for runtime integration

### `tools/niagara_asset_assistant.py`

Purpose:
- generate reviewable Niagara asset mutation plans
- create systems from templates without losing valid emitter graphs
- create and tune material instances for planned layers
- repair existing renderer material bindings when a renderer slot is present
- render the UE Python apply script in dry-run mode
- optionally execute through `unreal-bridge` with `apply-plan --apply`
- read the Niagara system back after writing with `--verify`

Key commands:

```powershell
python tools/niagara_asset_assistant.py plan-template --effect WingEcho --template-system /Game/VFX/Templates/NS_RibbonTrail_Template --target-system /Game/VFX/WingEcho/NS_WingEcho_Assisted --material-parent /Game/VFX/Masters/MFX_RibbonTrail
python tools/niagara_asset_assistant.py repair-plan --audit .codex/session/vfx-delivery/audits/niagara/.../niagara-audit.json --default-material /Game/VFX/WingEcho/MI_Ribbon
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --verify
python tools/niagara_asset_assistant.py apply-plan --plan .codex/session/vfx-delivery/ue-mutation-plans/WingEcho/mutation-plan.json --verify --apply
```

Safety notes:
- `apply-plan` is dry-run unless `--apply` is provided.
- The generated UE Python script is saved beside the plan so it can be inspected before execution.
- Material binding repair only patches an existing renderer `Material=` slot. If an emitter has empty `RendererProperties`, the assistant records the gap instead of pretending a material swap can fix it.

### `tools/ue_write_helpers.py`

Purpose:
- provide first-pass write-side Unreal helpers for duplicate, move, MI creation, Niagara template duplication, and system property updates

### `tools/visual_diff_qa.py`

Purpose:
- compare a captured preview against a reference image
- save metrics plus heat / edge / composite outputs

### `tools/delivery_package.py`

Purpose:
- build a delivery manifest from anchors, approvals, plans, tuning logs, and final asset paths

### `tools/learning_loop.py`

Purpose:
- generate reusable lessons from approvals, anchor locks, and tuning history
- keep manual success / failure / reuse rules with the effect record

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
2. `reference_acceptance.py`
3. `layer_evidence.py`
4. `visual_layer_map.py`
5. `controlled_preview.py`
6. `preview_approval.py`
7. `asset_plan.py`
8. `integration_plan.py`
9. `material_audit.py`
10. `niagara_audit.py`
11. `niagara_asset_assistant.py`
12. `ue_write_helpers.py`
13. `visual_diff_qa.py`
14. `design_compare_checklist.py`
15. `parameter_tuning_log.py`
16. `delivery_package.py`
17. `learning_loop.py`
18. `asset_cleanup.py`

That order matches the closed loop:

reference anchor -> acceptance gate -> visible evidence -> carrier-aware preview -> preview approval -> plan -> integration -> audit -> mutation plan -> write-side implementation -> diff QA -> tuning -> delivery -> learning -> cleanup.
