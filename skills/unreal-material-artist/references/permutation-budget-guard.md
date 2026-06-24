# Permutation Budget Guard

## Use This When

- 你想在单材质阶段就拦住 static switch 组合膨胀，而不是等项目级热力榜才发现。

## Purpose

`permutation_budget_guard.py` 会读取：

- `static_switch_variant_expander.py` 报告，或
- `material_parameter_schema.py` 里的 static switch

然后按 `pc / android / low_end` 预算给出：

- 估算 permutation 数
- warning / error 级风险
- 可选的 `shader_permutation_report.py` 对照

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/permutation_budget_guard.py --switch-expander-report D:/path/to/static-switch-variant-expander.json --platform android --platform pc --markdown
```
