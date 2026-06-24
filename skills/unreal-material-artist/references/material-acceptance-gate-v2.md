# Material Acceptance Gate v2

## Use This When

- `material_acceptance_gate.py` 已经能过，但你现在要把 `parameter_schema`、`source_provenance`、`translucency_sorting_probe`、`preview_matrix`、`preview_readability_score` 升级成真正的硬门。
- 你需要一个更严格的 `approved_for_reuse=true`，确保交付不仅“能看、能编译”，而且证据链完整、可复用、可复查。

## Purpose

`material_acceptance_gate_v2.py` 站在 v1 gate 之上。它不替代 v1，而是要求：

- 先有一个可通过的 `material_acceptance_gate.py`
- 再补齐更强的材质侧 evidence
- 最后才输出更严格的 `delivery_summary.approved_for_reuse=true`

它仍然只批准 material side evidence，不证明真实 Niagara System/Emitter/Renderer 集成。

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate_v2.py --package D:/path/to/material-delivery-package.json --require-ready --markdown
```

如果你已经先跑过 v1，也可以直接喂已有 acceptance report：

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_acceptance_gate_v2.py --acceptance-report D:/path/to/delivery.json --parameter-schema-report D:/path/to/material-parameter-schema.json --source-provenance-report D:/path/to/material-source-provenance.json --translucency-sorting-report D:/path/to/translucency-sorting-probe.json --preview-matrix-report D:/path/to/preview-matrix.json --preview-readability-report D:/path/to/preview-readability-score.json --require-ready --markdown
```

## Required v2 Evidence

默认要求：

- `material_acceptance_gate.py` 已批准
- `material_parameter_schema.py` 的 `gate.schema_complete=true`
- `material_source_provenance.py` 的 `gate.provenance_complete=true`
- 透明/VFX 路线下 `translucency_sorting_probe.py` 的 `gate.sorting_proven=true`
- `preview_matrix.py` 的 `gate.ready_for_regression_coverage=true`
- `preview_readability_score.py` 的 `gate.readable=true`

可选提升项：

- `--require-shader-cost`
- `--require-platform-scalability`

## Output Meaning

- `delivery_summary.approved_for_reuse=true`: 材质侧已经达到更高等级的可复用交付标准
- `checks[]`: v2 新增硬门逐项状态
- `v1_summary`: 保留 v1 gate 结果，方便追责和对比

## Boundary

这个 gate 不证明真实 Niagara 绑定。真实 System/Emitter/Renderer 验证仍归 `niagara-vfx-artist`。
