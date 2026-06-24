# Project Material Health

## Use This When

- You need a project-level material triage report instead of reviewing one material at a time.
- Existing evidence already includes `material_audit.py`, `material_domain_audit.py`, `material_regression.py`, `graph_diff_refactor.py`, `graph_refactor_apply.py`, `texture_set_pipeline.py`, `texture_import_audit.py`, or `shader_permutation_report.py` reports.
- You want heatlists for instruction count, sampler count, static-switch pressure, texture risk, failed regressions, graph diffs, graph-refactor apply candidates, parameter naming collisions, or suspicious master-material candidates.

## Purpose

`project_material_health.py` is an evidence aggregator. It does not pretend to live-scan `/Game` by itself when Unreal is offline. Instead, it scans report roots, usually:

```text
<project>/.codex/session/material-delivery/
```

It builds one project health report from the reports already emitted by the material workflow.

## Table Of Contents

- [Basic Scan](#basic-scan)
- [Scan Explicit Report Roots](#scan-explicit-report-roots)
- [Budgets And Gates](#budgets-and-gates)
- [Recommended Evidence Feed](#recommended-evidence-feed)
- [Reading The Report](#reading-the-report)
- [Triage Order](#triage-order)

It ranks:

- materials by risk score
- materials by instruction count
- materials by sampler count
- materials by static-switch count
- materials by dead graph nodes
- textures by risk score
- textures by size
- texture sets by findings
- failed regressions
- graph diffs requiring review
- graph-refactor apply candidates needing review
- shader permutation groups
- repeated or colliding parameter names
- suspicious master-material candidates

## Basic Scan

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --markdown
```

Default output:

```text
<project>/.codex/session/material-delivery/project-health/project-material-health.json
```

With `--markdown`, a sidecar `.md` summary is written next to the JSON.

## Scan Explicit Report Roots

Use this when evidence is split across projects, worktrees, or copied report folders:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --report-root D:/ProjectA/.codex/session/material-delivery --report-root D:/ProjectB/.codex/session/material-delivery --markdown
```

You can also pass a single JSON report file:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --report-root D:/reports/material-audit.json --markdown
```

## Budgets And Gates

Default budgets:

- `--instruction-budget 220`
- `--sampler-budget 12`
- `--texture-max-dimension 2048`
- `--high-risk-score 80`

Use stricter budgets for mobile or project-specific performance targets:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --instruction-budget 120 --sampler-budget 6 --texture-max-dimension 1024 --high-risk-score 60 --strict --markdown
```

`--strict` returns non-zero when the project health gate fails. The gate fails when there are high-risk materials, high-risk textures, high-risk texture sets, failed regressions, or invalid report files.

## Recommended Evidence Feed

For a meaningful project report, collect these first:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Materials/M_Foo --project UnrealAI --include-raw-graph --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_domain_audit.py /Game/Materials/M_Foo --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_set_pipeline.py audit --scan D:/Textures/Foo --emit-import-fix-spec --markdown
python D:/Skills/skills/unreal-material-artist/tools/texture_import_audit.py /Game/Textures/T_Foo_BaseColor /Game/Textures/T_Foo_Normal --project UnrealAI --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_regression.py compare --effect Foo --layer Surface --preview-report D:/reports/new-preview.json --markdown
python D:/Skills/skills/unreal-material-artist/tools/graph_diff_refactor.py diff --before-audit D:/reports/before-audit.json --after-audit D:/reports/after-audit.json --regression-report D:/reports/material-regression-comparison.json --markdown
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --execute --project UnrealAI --endpoint 127.0.0.1:57404 --carrier sprite --markdown
python D:/Skills/skills/unreal-material-artist/tools/shader_permutation_report.py --path-prefix /Game --project UnrealAI --markdown
```

Then run:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/project_material_health.py scan --markdown
```

## Reading The Report

Important fields:

- `summary.tool_counts`: which report types were found.
- `summary.high_risk_material_count`: number of materials above the configured risk threshold.
- `summary.high_risk_texture_count`: number of textures above the configured risk threshold.
- `summary.high_risk_texture_set_count`: number of failed or high-risk full texture-set reports.
- `summary.graph_refactor_apply_review_count`: candidate refactors that are not ready for acceptance, including dry-run plans, skipped operations, or missing regression baselines.
- `summary.graph_refactor_apply_failed_count`: candidate refactors with operation failures, failed regression, failed preview, or domain errors.
- `hotlists.materials_by_score`: highest priority material triage list.
- `hotlists.materials_by_instructions`: shader-cost hotlist.
- `hotlists.materials_by_static_switches`: possible permutation pressure.
- `hotlists.textures_by_score`: texture/import/texture-set risk hotlist.
- `hotlists.texture_sets_by_score`: broken or warning-heavy texture sets.
- `hotlists.failed_regressions`: visual regressions that should be resolved or accepted as new baselines.
- `hotlists.graph_diffs_requiring_review`: graph changes that explain or may explain visual drift.
- `hotlists.graph_refactor_applies_needing_review`: safe-apply candidates that still need review, rollback, baseline, or promotion decisions.
- `hotlists.parameter_name_collisions`: repeated parameter names, especially suspicious when the same normalized name has mixed types.
- `hotlists.suspicious_master_candidates`: materials with large graphs, many switches, or many texture parameters.

## Triage Order

Use this order unless there is a known production fire:

1. Failed regressions, graph diffs requiring review, and graph-refactor apply candidates that are not ready for acceptance.
2. Compile errors and domain-audit errors.
3. Instruction and sampler hot materials.
4. Static-switch and permutation pressure.
5. Texture-set errors, oversized textures, wrong sRGB/compression, and packed-channel problems.
6. Parameter name collisions and stale overrides.
7. Dead branches and cleanup-only findings.

The tool is a prioritizer, not a replacement for review. Use it to pick the next material or texture set to inspect with the specialized tools.
