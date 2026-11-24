# Variant, permutation and cost tools

Four local tools that turn a parameter schema into test tiers, keep static
switch permutations within budget and show where shader cost comes from.

| Tool | Use it when |
|---|---|
| [`material_variant_runner.py`](#material-variant-runner) | A parameter schema should become `default / low / high / extreme / gameplay-safe` instance tiers |
| [`static_switch_variant_expander.py`](#static-switch-variant-expander) | Dynamic tiers exist, but the real risk sits in static switch combinations |
| [`permutation_budget_guard.py`](#permutation-budget-guard) | Static switch growth should be stopped at the single-material stage |
| [`shader_cost_attribution.py`](#shader-cost-attribution) | Total instructions or samplers are high and you need to know which layer to cut first |

## Material variant runner

`material_variant_runner.py` reads a parameter schema from
`material_parameter_schema.py` and produces the parameter values of each tier,
a spec that `material_instance_batch.py` can run, and command skeletons for
`preview_matrix.py`. It supports scalar and vector parameters and passes
texture defaults through. Static switches are expanded by the next tool.

```powershell
python tools/material_variant_runner.py --parameter-schema D:/path/to/material-parameter-schema.json --parent-path /Game/Materials/M_WingEcho_Master --markdown
```

Output: `material_instance_batch_spec`, `variants[]` and
`preview_matrix_commands[]`.

## Static switch variant expander

`static_switch_variant_expander.py` crosses the dynamic tiers with static
switch combinations. It lists the participating switches, estimates the
permutation count, selects combinations up to `--max-permutations` and writes
a batch spec for `material_instance_batch.py`. When the count is too large it
keeps the default combination and those closest to it, and tells you to narrow
the switch range.

```powershell
python tools/static_switch_variant_expander.py --parameter-schema D:/path/to/material-parameter-schema.json --parent-path /Game/Materials/M_WingEcho_Master --tiers default,gameplay-safe --max-permutations 8 --markdown
```

## Permutation budget guard

`permutation_budget_guard.py` reads an expander report, or the static switches
of a parameter schema, and judges them against `pc`, `android` and `low_end`
budgets. It reports the estimated permutation count and warning or error
risks, and can compare against a `shader_permutation_report.py` result.

```powershell
python tools/permutation_budget_guard.py --switch-expander-report D:/path/to/static-switch-variant-expander.json --platform android --platform pc --markdown
```

## Shader cost attribution

`shader_cost_attribution.py` takes the graph and analysis of a material audit
report and attributes cost heuristically to texture samples, static switches,
function calls, Custom HLSL, expensive math, depth and scene reads, and
translucency or special-domain risk. It is offline triage, not UE's per-node
profiler: use it to choose which category to optimize first.

```powershell
python tools/shader_cost_attribution.py --audit-report D:/path/to/material-audit.json --markdown
```

Output: `attributions[].categories[]` with node count, estimated weight and
share per category.
