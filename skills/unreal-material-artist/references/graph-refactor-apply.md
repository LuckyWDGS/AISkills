# Graph Refactor Apply

## Use This When

- `graph_diff_refactor.py` or `material_toolset_builder.py refactor-plan` has identified a likely material-side fix.
- You need a reviewable apply step instead of manually editing the graph in-place.
- A refactor must leave before/after audit, preview, regression, backup, and rollback evidence.

## Purpose

`graph_refactor_apply.py` is the execution layer after graph diff explanation. It is deliberately conservative:

- It does not mutate the original material.
- It duplicates the target into a backup and a patched candidate.
- It runs UE mutations only for whitelisted operations.
- It records blocked operations instead of guessing.
- It runs before audit, after audit, after domain audit, preview, and regression when a baseline exists.
- If regression is skipped because no baseline exists, the candidate can be structurally clean but is not `ready_for_acceptance`.

## Dry Run

Dry run is the default and writes a review plan:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --markdown
```

The report includes:

- target material
- candidate material path
- backup material path
- executable operations
- blocked operations with reasons
- validation commands
- rollback notes

## Execute

Execute only after reviewing the dry-run report:

```powershell
python D:/Skills/skills/unreal-material-artist/tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --execute --project UnrealAI --endpoint 127.0.0.1:57404 --carrier sprite --markdown
```

The tool duplicates:

```text
<target> -> /Game/CodexTemp/MaterialRefactorApply/<target>_<label>_Backup
<target> -> /Game/CodexTemp/MaterialRefactorApply/<target>_<label>_Candidate
```

Then it applies only to the candidate.

## Supported Apply Operations

- `add_fresnel_layer`: adds a default-neutral Fresnel rim branch into `EmissiveColor`.
- `add_depth_fade`: inserts `DepthFade` into an existing `Opacity` output chain.
- `restore_route_contract`: restores domain, blend, shading model, two-sided, material attributes, and usage flags from graph-diff before-route evidence.
- `repair_output_chain`: reconnects outputs to before-audit source GUIDs when those GUIDs still exist in the candidate graph.

Review-only operations in the first version:

- `add_detail_normal`: blocked until texture/import evidence is available.
- `normalize_parameters`: blocked because parameter migration can affect runtime/Niagara/gameplay bindings.

## Validation Gate

Execute mode writes:

- before `material_audit.py --include-raw-graph`
- before `material_domain_audit.py`
- after `material_audit.py --include-raw-graph`
- after `material_domain_audit.py`
- after `material_preview.py render`
- `material_regression.py compare` when a baseline exists or `--baseline` is provided

Gate fields:

- `candidate_validated_without_regression`: audits and preview are clean, but no regression baseline was available.
- `ready_for_acceptance`: candidate passed apply, audits, preview, and regression.

## Rollback

The original material is untouched. If validation fails:

- ignore or delete the candidate
- keep the backup for inspection
- do not promote the candidate into the original material path

Future versions may add a separate promote/replace flow, but it should remain opt-in and require a passing regression.
