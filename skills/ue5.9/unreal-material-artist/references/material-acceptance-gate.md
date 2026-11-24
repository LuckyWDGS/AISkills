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
python tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

Pass extra reports when they were not included in the package:

```powershell
python tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --regression-report D:/path/to/material-regression-comparison.json --texture-set-report D:/path/to/texture-set-pipeline.json --require-ready --markdown
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

## Stock-Grade Gate (v2)

`material_acceptance_gate_v2.py` sits on top of this gate for assets that will become
reusable stock. It requires an approved v1 report first, then hard-gates:

- `material_parameter_schema.py` with `gate.schema_complete=true`
- `material_source_provenance.py` with `gate.provenance_complete=true`
- `translucency_sorting_probe.py` with `gate.sorting_proven=true` on translucent/VFX routes
- `preview_matrix.py` with `gate.ready_for_regression_coverage=true`
- `preview_readability_score.py` with `gate.readable=true`
- optionally `--require-shader-cost` and `--require-platform-scalability`

```powershell
python tools/material_acceptance_gate_v2.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
python tools/material_acceptance_gate_v2.py --acceptance-report D:/path/to/delivery.json --parameter-schema-report D:/path/to/material-parameter-schema.json --source-provenance-report D:/path/to/material-source-provenance.json --translucency-sorting-report D:/path/to/translucency-sorting-probe.json --preview-matrix-report D:/path/to/preview-matrix.json --preview-readability-report D:/path/to/preview-readability-score.json --require-ready --markdown
```

Its `delivery_summary.approved_for_reuse=true` is the stricter stock-grade approval;
`checks[]` lists the v2 gates and `v1_summary` keeps the v1 result. Then use
[library-promotion-gate.md](library-promotion-gate.md) for library promotion.

## Boundary

This gate does not prove production Niagara bindings, SubUV settings, renderer material assignment, DynamicParameter wiring, RibbonWidth, sorting, or FixedBounds. Pass the accepted material report plus the material contract/package to `niagara-vfx-artist`; it should run `niagara_material_integration_probe.py` and its own `delivery_package.py --require-ready`.
