# Shader Cost Attribution

## Use This When

- 你知道总 instruction / sampler 已经偏高，但不知道该先砍哪一层。
- 你需要一个“成本归因图”，不是只有总数。

## Purpose

`shader_cost_attribution.py` 基于 `material_audit.py` 的图和分析做启发式归因：

- texture samples
- static switches
- function calls
- custom HLSL
- expensive math
- depth/scene reads
- 透明/特殊 domain 风险

## Important Note

这不是 UE 的精确 per-node profiler，而是离线启发式 triage。

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/shader_cost_attribution.py --audit-report D:/path/to/material-audit.json --markdown
```

## Output

- `attributions[].categories[]`
- 每类的 node 数、估算权重、占比

用它决定先优化哪类成本，而不是盲砍效果。
