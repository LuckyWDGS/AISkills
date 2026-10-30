# Graph Refactor Apply

Dry run (the default) writes the review plan. `--execute` duplicates the target into a
backup and a candidate through AssetTools, applies the executable operations to the
candidate with MaterialTools / ObjectTools (every connection and property is read back),
recompiles, saves both copies only when every operation succeeded, then runs the
`validation_plan` commands and fills the gate.

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
python tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --markdown
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
python tools/graph_refactor_apply.py --refactor-plan D:/reports/material-toolset-refactor-plan.json --carrier sprite --execute --markdown
```

An existing candidate or backup path refuses the run (pick new `--candidate-path` /
`--backup-path`); so does Play-In-Editor. A failed operation stops the rest and leaves the
candidate unsaved for inspection.

The tool duplicates:

```text
<target> -> /Game/CodexTemp/MaterialRefactorApply/<target>_<label>_Backup
<target> -> /Game/CodexTemp/MaterialRefactorApply/<target>_<label>_Candidate
```

Then it applies only to the candidate.

## Supported Apply Operations

- `add_fresnel_layer`: `Fresnel * V_FresnelColor * S_FresnelIntensity`, added onto the existing `EmissiveColor` source (or connected directly when there is none).
- `add_depth_fade`: `DepthFade` with `S_DepthFadeDistance` between the existing `Opacity` source and the output; refused on opaque/masked routes.
- `restore_route_contract`: restores domain, blend, shading model, two-sided, material attributes, and usage flags from graph-diff before-route evidence.
- `repair_output_chain`: reconnects each output to its before-audit source expression (matched by expression object name, which a duplicate keeps); a source missing from the candidate stops the run.

Review-only operations in the first version:

- `add_detail_normal`: blocked until texture/import evidence is available.
- `normalize_parameters`: blocked because parameter migration can affect runtime/Niagara/gameplay bindings.

## Validation Gate

Execute mode writes:

- before `material_audit.py --include-raw-graph`
- before `material_domain_audit.py`
- after `material_audit.py --include-raw-graph`
- after `material_domain_audit.py`
- after `material_preview.py capture`
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
