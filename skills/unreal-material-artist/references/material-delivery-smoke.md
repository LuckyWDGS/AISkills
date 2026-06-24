# Material Delivery Smoke

## Use This When

- 你已经有 package、parameter schema，以及大部分材质侧证据。
- 你不想再手工一条条串 `variant_runner -> instance_batch -> preview_matrix -> readability -> regression -> acceptance -> library gate`。
- 你要一个真正的 end-to-end material-side smoke runner。

## Purpose

`material_delivery_smoke.py` 是编排层，不重新发明分析逻辑。

它会优先复用现有工具：

- `material_variant_runner.py`
- `static_switch_variant_expander.py`
- `permutation_budget_guard.py`
- `material_instance_batch.py`
- `preview_matrix.py`
- `preview_readability_score.py`
- `material_regression.py`
- `material_acceptance_gate_v2.py`
- `library_promotion_gate.py`

默认先做 planning / dry-run。
只有显式加 `--execute` 才会跑 live UE 相关步骤。

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_delivery_smoke.py --package D:/path/to/material-delivery-package.json --parameter-schema-report D:/path/to/material-parameter-schema.json --source-provenance-report D:/path/to/material-source-provenance.json --translucency-sorting-report D:/path/to/translucency-sorting-probe.json --markdown
```

执行 live smoke：

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_delivery_smoke.py --package D:/path/to/material-delivery-package.json --parameter-schema-report D:/path/to/material-parameter-schema.json --source-provenance-report D:/path/to/material-source-provenance.json --translucency-sorting-report D:/path/to/translucency-sorting-probe.json --execute --project UnrealAI --endpoint 127.0.0.1:57404 --markdown
```

## Default Behavior

- 默认 smoke tiers 是 `default` 和 `gameplay-safe`
- `material_variant_runner.py` 会先生成只供 smoke 使用的 MI batch spec
- 如果 schema 里有 static switch，`static_switch_variant_expander.py` 会把 tier 进一步扩成 permutation 变体
- `permutation_budget_guard.py` 会在真正跑 UE 前先看单材质 permutation 压力
- `preview_matrix.py` 会按每个 smoke tier 单独跑，避免把“parameter tier 标签”误当成真实参数变化
- 如果 baseline 不存在，`material_regression.py` 会被明确标成 advisory，而不是假装通过
- 如果没有 `asset_id`，`library_promotion_gate.py` 仍可做 advisory ready 判断，但不会 `--apply`
- 加 `--resume-cache` 后，会复用没变输入下已经存在的 step 报告

## Output

输出一个总报告，包含：

- 每一步的命令
- 是否执行
- report path
- pass / risk / blocked / advisory / planned 状态
- `ready_for_live_smoke`
- `smoke_passed`
- 下一步建议

## Boundary

这是材质侧 delivery smoke。

- 它不替代真实 Niagara System/Emitter/Renderer 集成验证
- 真实 Niagara 绑定和系统级 ready gate 仍属于 `niagara-vfx-artist`
