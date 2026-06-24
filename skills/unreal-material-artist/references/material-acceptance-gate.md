# Material Acceptance Gate

## Use This When

- A material delivery package must become a hard approved delivery report for downstream reuse.
- Niagara delivery has a final material path and needs `delivery_summary.approved_for_reuse=true` before the final VFX package can be ready.
- You need one strict gate over contract, preview, audit, regression, texture set, budget, usage flags, and parameter-table evidence.

## Purpose

`material_acceptance_gate.py` reads an existing `delivery_packager.py` package and the reports linked from it. It does not mutate Unreal assets and does not validate real Niagara systems. It approves only material-side evidence and writes a standard report under:

```text
<project>/.codex/session/material-delivery/deliveries/<material-slug>/delivery.json
```

Niagara `delivery_package.py` can consume this report because it emits:

- `asset.ue_asset_path`
- `asset.category`
- `asset.role`
- `asset.material_domain`
- `delivery_summary.approved_for_reuse`
- `delivery_summary.errors`
- `delivery_summary.warnings`

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

Pass extra reports when they were not included in the package:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --regression-report D:/path/to/material-regression-comparison.json --texture-set-report D:/path/to/texture-set-pipeline.json --require-ready --markdown
```

## Hard Gate

By default, approval requires:

- package is a `delivery_packager` report and `gate.ready_for_handoff=true`
- final material path is present
- `material_contract` exists and validates without errors or warnings
- at least one `material_preview` exists and `outputs.shaded_ok=true`
- `material_audit` and `material_domain_audit` exist for the final material
- no compile errors, dead nodes, stale overrides, audit errors, or audit warnings
- `texture_set_pipeline` passes when texture requirements exist
- `material_regression_compare` passes
- instruction and sampler budgets exist and measured audit cost stays within them
- required usage flags exist in material audit evidence
- parameter table exists and has named, non-duplicate rows

For runtime-facing materials, run `material_parameter_schema.py` before final approval so the parameter table also has unit/range/owner/write/regression intent. The acceptance gate still checks the package/contract parameter table directly; attach the schema report to the package as supporting evidence.

Warnings block approval unless `--allow-warnings` is supplied. Use that only when the warning is intentionally accepted and documented.

## Waivers

Use waivers only for deliberate nonstandard routes:

- `--texture-set-waiver "reason"` for textureless or externally managed texture routes.
- `--parameter-table-waiver "reason"` for intentionally parameterless materials.
- `--no-require-regression` only for early iteration, not final reuse approval.

Waivers are written into the report so downstream reviewers can see that the gate was intentionally narrowed.

## Output Meaning

- `delivery_summary.approved_for_reuse=true`: material-side evidence is approved for reuse by other skills or packages.
- `delivery_summary.ready=true`: same value as `approved_for_reuse`, useful for local checks.
- `checks[]`: per-gate status, errors, warnings, evidence paths, and action needed.
- `evidence`: package, contract, preview, audit, domain audit, texture set, and regression report paths.
- `boundary`: reminder that real Niagara System/Emitter/Renderer integration proof remains in `niagara-vfx-artist`.

## Boundary

This gate does not prove production Niagara bindings, SubUV settings, renderer material assignment, DynamicParameter wiring, RibbonWidth, sorting, or FixedBounds. Pass the accepted material report plus the material contract/package to `niagara-vfx-artist`; it should run `niagara_material_integration_probe.py` and its own `delivery_package.py --require-ready`.
