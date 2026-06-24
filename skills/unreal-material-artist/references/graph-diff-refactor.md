# Graph Diff Refactor

## Use This When

- `material_regression.py compare` fails and you need to explain what changed.
- A material optimization, texture swap, parameter tune, master-material migration, tutorial recreation, or graph rebuild may have altered the look.
- You have `material_audit.py` reports from before and after the change, ideally with `material_domain_audit.py` reports too.

## Purpose

`graph_diff_refactor.py` is the explanation layer after visual regression. It compares two offline audit reports and turns raw changes into a material-side cause list:

- render route changes: domain, blend mode, shading model, two-sided, Material Attributes, usage flags
- parameter default changes: scalar, vector, texture, static switch
- Material Instance override changes and stale override count changes
- budget changes: instructions, samplers, expression count, shader stats readiness, compile errors
- graph changes: output chain changes, dead node deltas, node class count deltas
- raw graph changes when audits were captured with `--include-raw-graph`
- domain-audit changes: wired outputs, node evidence, findings
- regression-aware likely causes for brightness drift, alpha/coverage drift, centroid shift, texture/input drift, and budget drift

This tool is intentionally offline and report-first. It does not mutate UE assets. Treat its output as a refactor/debug plan before deciding whether to revert, patch, or accept a new baseline. When a guarded candidate apply is needed, pass the resulting refactor plan to `graph_refactor_apply.py`.

## Recommended Input Reports

Minimum:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Materials/M_WingEcho --project UnrealAI --markdown
```

Best for exact graph diffs:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_audit.py /Game/Materials/M_WingEcho --project UnrealAI --include-raw-graph --markdown
python D:/Skills/skills/unreal-material-artist/tools/material_domain_audit.py /Game/Materials/M_WingEcho --project UnrealAI --markdown
```

`--include-raw-graph` enables GUID-level node, node-property, connection, and output-connection comparisons. Without it, the tool still compares route, parameters, budgets, output chains, dead nodes, and class-count evidence when domain audits are supplied.

## Diff After A Failed Regression

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_diff_refactor.py diff --before-audit D:/reports/before/material-audit.json --after-audit D:/reports/after/material-audit.json --before-domain-audit D:/reports/before/material-domain-audit.json --after-domain-audit D:/reports/after/material-domain-audit.json --regression-report D:/reports/material-regression-comparison.json --effect WingEcho --layer RibbonTrail --label optimize-pass-01 --markdown
```

The report is written under:

```text
<project>/.codex/session/material-delivery/graph-diffs/<effect-layer-label>/graph-diff-refactor.json
```

When `--markdown` is set, a sidecar `.md` summary is written next to the JSON.

Use `--strict` when the command should return non-zero if the diff requires review:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_diff_refactor.py diff --before-audit D:/reports/before/material-audit.json --after-audit D:/reports/after/material-audit.json --regression-report D:/reports/material-regression-comparison.json --strict --markdown
```

## Report Meaning

Key sections:

- `regression`: copied summary of the failed or passed regression report, including metrics and gate findings.
- `diffs.route`: material domain, blend, shading model, two-sided, Material Attributes, and usage-flag changes.
- `diffs.parameters`: added, removed, and changed parameter defaults plus MI overrides.
- `diffs.budget`: instruction, sampler, expression, compile error, and shader-stats changes.
- `diffs.graph`: output-chain changes, class-count changes, dead nodes, and raw graph diffs when available.
- `diffs.domain`: domain-audit contract and node evidence changes.
- `likely_causes`: ranked human-readable explanation of the most likely material-side causes.
- `refactor_recommendations`: next steps for safe revert, focused patching, or evidence gathering.
- `gate.explains_regression`: `true` when a failed regression has at least one high or medium material-side cause.

## Interpretation Rules

- Route or output-chain changes outrank parameter tweaks. Domain, blend, shading model, two-sided, Material Attributes, and output pins can invalidate the whole visual comparison.
- Brightness drift usually points first to BaseColor, Emissive, shading model, lighting route, roughness/specular/coat, or color/intensity parameters.
- Alpha or coverage drift usually points first to Blend Mode, Opacity, OpacityMask, cutoff/mask params, mask textures, and output-chain changes.
- Centroid or composition drift often points to WPO/PDO, UV or mask changes, output wiring, or a mismatched preview carrier/camera.
- Budget drift is not always visual drift, but it explains changed complexity evidence and can reveal accidental graph growth.
- If the tool says raw graph diff is unavailable, rerun both material audits with `--include-raw-graph` before doing a node-by-node refactor.

## Closed Loop

Recommended sequence:

1. Lock an accepted preview with `material_regression.py baseline`.
2. Change the material.
3. Rerender `material_preview.py`.
4. Run `material_regression.py compare --strict`.
5. If regression fails, run `graph_diff_refactor.py diff` with before/after audits.
6. Convert likely causes into `material_toolset_builder.py refactor-plan`.
7. Run `graph_refactor_apply.py` dry-run, then `--execute` only after reviewing candidate/backup paths and executable operations.
8. Accept the candidate only after after-audit, preview, and regression evidence passes.
