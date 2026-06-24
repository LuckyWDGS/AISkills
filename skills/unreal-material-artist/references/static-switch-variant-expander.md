# Static Switch Variant Expander

## Use This When

- `material_variant_runner.py` 已经给出了动态参数 tier，但真实材质风险还卡在 `static switch`。
- 你需要把 `default / gameplay-safe / high` 这些 tier 再乘上静态开关组合，变成真正可跑的 MI 批次。

## Purpose

`static_switch_variant_expander.py` 会读取 `material_parameter_schema.py`，输出：

- 参与的 static switch 清单
- 估算 permutation 数量
- 受 `--max-permutations` 控制的组合集
- 可直接喂给 `material_instance_batch.py` 的 batch spec

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/static_switch_variant_expander.py --parameter-schema D:/path/to/material-parameter-schema.json --parent-path /Game/Materials/M_WingEcho_Master --tiers default,gameplay-safe --max-permutations 8 --markdown
```

## Notes

- 它不会替代 `material_variant_runner.py`，而是补上 static switch 那半边参数空间。
- 如果组合数过大，会优先保留默认组合和偏离默认值较少的组合，再提示你收窄开关范围。
