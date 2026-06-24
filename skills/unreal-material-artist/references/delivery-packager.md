# Delivery Packager

## Use This When

- A material route has a plan and needs one handoff bundle instead of scattered JSON/Markdown reports.
- You need to check whether plan, contract, texture QA, preview, and audit evidence are complete enough for delivery.
- You want a stable input for later `material_regression` or higher-level Niagara/feature packaging.

## Purpose

`delivery_packager.py` gathers the material work evidence for one effect/layer and writes a package under:

```text
<project>/.codex/session/material-delivery/packages/<effect-layer>/material-delivery-package.json
```

The package summarizes:

- reference-to-material plan
- material contract
- material route
- texture requirements and texture report coverage
- preview reports and captured preview paths
- audit/domain-audit reports
- warning/error counts
- missing required evidence
- risk notes and generated next actions

The packager does not create the material or rerun audits. It records the evidence that already exists and tells you what is still missing.

## Table Of Contents

- [Typical Command](#typical-command)
- [Evidence Gate](#evidence-gate)
- [Report Inputs](#report-inputs)
- [Reading The Package](#reading-the-package)
- [Regression Baseline](#regression-baseline)
- [Acceptance Gate](#acceptance-gate)
- [Limits](#limits)

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/delivery_packager.py build --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/material-preview.json --audit-report D:/path/to/material-audit.json --audit-report D:/path/to/material-domain-audit.json --texture-report D:/path/to/texture-asset-report.json --material-path /Game/Materials/M_WingEcho_RibbonTrail --markdown
```

If `--plan` and `--contract` are omitted, the tool looks for the default paths created by `reference_to_material_plan.py --emit-contract`:

```text
material-delivery/plans/<effect-layer>/reference-to-material-plan.json
material-delivery/contracts/<effect-layer>/material-contract.json
```

Validate an existing package:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/delivery_packager.py validate D:/path/to/material-delivery-package.json --markdown
```

Use `--strict` when the package should fail the command if it is not ready:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/delivery_packager.py build --effect WingEcho --layer RibbonTrail --strict --markdown
```

## Evidence Gate

By default, the gate expects:

- plan present
- contract present
- final material path supplied with `--material-path`
- at least one preview report
- at least one audit report
- texture reports covering every planned texture requirement
- no report errors

The command still writes a package when evidence is missing. In that case `gate.ready_for_handoff` is `false`, `gate.missing_required` lists the missing evidence, and Markdown `Next Actions` gives the next commands to run.

Use these flags for early prototypes or partial reviews:

- `--no-require-preview`
- `--no-require-audit`
- `--no-require-textures`
- `--no-require-material`

## Report Inputs

Use specific flags when possible:

- `--texture-report` for `texture_asset_report.py` output
- `--preview-report` for `material_preview.py` output
- `--audit-report` for `material_audit.py`, `material_domain_audit.py`, function lints, permutation reports, or similar audit evidence

Use `--report` for extra JSON reports. The group is inferred from the report's `tool` field.

Useful extra reports include `material_parameter_schema.py`, `preview_matrix.py`, `translucency_sorting_probe.py`, and `material_source_provenance.py`. The packager records them as evidence; downstream gates still decide which reports are required for a specific delivery.

## Reading The Package

Important JSON fields:

- `gate.ready_for_handoff`: true only when required evidence exists and there are no report errors.
- `gate.missing_required`: missing plan, contract, preview, audit, or texture evidence.
- `summaries.texture_coverage`: which planned textures have matching texture reports.
- `summaries.reports`: grouped report summaries with warning/error counts.
- `route`: carrier, domain, blend mode, shading model, expected outputs, and usage flags.
- `risk_notes`: manual risk notes supplied by `--risk-note`.
- `next_actions`: generated and manual follow-up actions.

## Regression Baseline

After a package contains an accepted preview report, lock that preview for later drift checks:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py baseline --package D:/path/to/material-delivery-package.json --label accepted-v001 --markdown
```

Run regression after material edits:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --effect WingEcho --layer RibbonTrail --preview-report D:/path/to/new-material-preview.json --strict --markdown
```

## Acceptance Gate

When the package, regression comparison, texture set, audit, budgets, usage flags, and parameter table are complete, approve material-side reuse with:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

This writes the downstream-facing report under:

```text
<project>/.codex/session/material-delivery/deliveries/<material-slug>/delivery.json
```

Only this acceptance report should be treated as material-side `approved_for_reuse=true` evidence for Niagara `delivery_package.py`.

## Limits

- Texture coverage is first-pass matching by planned texture name or simple role evidence. If a texture was renamed intentionally, add a specific texture report and note the mapping in `--note` or regenerate the plan.
- Preview and audit reports are trusted as provided. The packager does not connect to Unreal or verify live assets.
- `ready_for_handoff=true` means evidence completeness, not artistic approval. The material still needs visual acceptance against the reference.
