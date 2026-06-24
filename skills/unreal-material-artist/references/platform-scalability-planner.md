# Platform Scalability Planner

## Use This When

- 你已经有 audit / texture / acceptance evidence，想系统地产出 PC / Android / low-end 材质降级计划。
- 你不想临交付时才拍脑袋决定“移动端先砍什么”。
- 你还没有 evidence，但任务一开始就要求 PC / Android / low-end 路线，需要先写可验证的预算假设。

## Purpose

`platform_scalability_planner.py` 会从现有 evidence 推出不同平台的：

- instruction 预算压力
- sampler 预算压力
- 纹理尺寸压力
- 透明 overdraw 风险
- 推荐 fallback MI / switch / 贴图降级策略

没有 evidence 时，不要假装已经验证过平台性能。先写 `planning assumptions`，然后在 material contract / parameter schema / preview plan 里标记为待验证。

## Pre-Evidence Planning

用于第一版材质设计前的保守假设：

| Platform | First-pass target | Typical fallback |
|---|---|---|
| PC hero material | richer look allowed if screen coverage is controlled; 4-8 samples only with evidence | preserve look first, then pack channels, reduce helper maps, gate optional layers |
| PC gameplay material | moderate instruction/sample count; avoid invisible complexity | one packed mask, clear MI tiers, preview matrix on busy backgrounds |
| Android / low-end VFX | 0-2 samples, preferably one packed mask; avoid refraction and scene reads | lower texture size, lower intensity/opacity, shorter lifetime, simpler distortion |
| Android / low-end surface | simplify BRDF/layering, avoid unsupported shading paths | `QualitySwitch`, lower normal/detail maps, cheaper MI tier |

Record mobile-specific material risks:

- `Full Precision Mode` can fix precision artifacts but costs more.
- `Mobile High Quality BRDF`, forward reflections, planar reflections, and some reflection paths can consume extra GPU cost or samplers.
- Translucent/additive materials are often limited by overdraw and screen coverage before instruction count.
- Unsupported or platform-qualified shading models/features must be checked against the active engine version and target renderer.
- Static switches can create permutation pressure; prefer dynamic parameters or separate explicit MIs unless a static branch is proven valuable.

## Typical Command

```powershell
python D:/Skills/skills/unreal-material-artist/tools/platform_scalability_planner.py --package D:/path/to/material-delivery-package.json --platform pc,android,low_end --markdown
```

## Output

- `platforms[]`
- 每个平台的 `ready`
- 推荐降级动作

这个工具适合接在 acceptance gate 之后，形成真正可执行的 cross-platform 交付计划。
