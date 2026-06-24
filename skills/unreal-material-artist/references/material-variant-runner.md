# Material Variant Runner

## Use This When

- 你已经有了 `material_parameter_schema.py`，想把参数契约直接变成测试档位。
- 你要自动生成 `default / low / high / extreme / gameplay-safe` 这些 MI 变体。

## Purpose

`material_variant_runner.py` 会读取参数 schema，生成：

- 每个 tier 的参数值
- `material_instance_batch.py` 可直接执行的 spec
- 可以继续喂给 `preview_matrix.py` 的命令骨架

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/material_variant_runner.py --parameter-schema D:/path/to/material-parameter-schema.json --parent-path /Game/Materials/M_WingEcho_Master --markdown
```

## Current Scope

- 支持 `scalar`
- 支持 `vector`
- 支持 `texture` 默认值透传
- `static_switch` 本体仍不会直接在这里展开；后续请接 `static_switch_variant_expander.py`

## Output

- `material_instance_batch_spec`
- `variants[]`
- `preview_matrix_commands[]`

这样参数表就不只是文档，而是测试驱动输入。
