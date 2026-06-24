# UE 材质配方：参数命名与移动端简化

## 用途

读取这份 reference 当任务需要统一材质参数名、Niagara/MI 绑定名、艺术家可读控制，或需要 PC/Android/低端平台的配方简化规则。

## 目录

- [参数命名约定](#1-参数命名约定)
- [移动端简化建议](#8-移动端简化建议)

---
## 1. 参数命名约定

## 目标

统一材质参数命名有几个直接好处：
- 材质实例更容易阅读
- AI 更容易稳定产出一致的参数名
- Niagara 和材质联动时更容易对接
- 团队协作时更容易复用和排错

推荐原则是：
- 一眼看出参数类型
- 一眼看出参数用途
- 同类效果尽量复用同一命名

## 基础规则

### 参数使用 PascalCase

推荐：
- `ShieldColor`
- `EmissiveIntensity`
- `NoiseStrength`
- `FlowSpeed`

不推荐：
- `shield_color`
- `noise_strength_01`
- `speedforflow`

### 避免无意义缩写

推荐：
- `OpacitySoftness`
- `EdgeBreakup`
- `DepthFadeDistance`

不推荐：
- `OpS`
- `EBrk`
- `DFD`

### 参数名尽量体现“用途”而不是“节点来源”

推荐：
- `HitMaskIntensity`
- `OuterRingWidth`
- `TrailHeadBrightness`

不推荐：
- `MultiplyValueA`
- `PannerScalar`
- `Node03Value`

## 类型前缀约定

如果项目里希望一眼看出参数类型，可以使用下面这套前缀。
如果你项目里不喜欢前缀，也可以不加，但建议整个项目保持一致。

### Scalar Parameter

前缀：`S_`

示例：
- `S_EmissiveIntensity`
- `S_NoiseStrength`
- `S_FresnelExponent`
- `S_Opacity`

### Vector Parameter

前缀：`V_`

示例：
- `V_ShieldColor`
- `V_CoreColor`
- `V_EdgeColor`
- `V_HitColor`

### Texture Parameter

前缀：`T_`

示例：
- `T_Noise`
- `T_Mask`
- `T_FlowMap`
- `T_Distortion`

### Static Switch Parameter

前缀：`SS_`

示例：
- `SS_UseFresnel`
- `SS_UseFlowMap`
- `SS_EnableDistortion`

## 用途命名建议

### 发光相关

- `S_EmissiveIntensity`
- `S_EmissiveBoost`
- `V_EmissiveColor`

### 菲涅尔相关

- `S_FresnelExponent`
- `S_FresnelIntensity`
- `V_FresnelColor`

### 噪声相关

- `T_Noise`
- `S_NoiseStrength`
- `S_NoiseContrast`
- `S_NoiseTiling`

### 流动相关

- `T_FlowMap`
- `S_FlowSpeed`
- `S_FlowStrength`
- `S_FlowTiling`

### 透明度相关

- `S_Opacity`
- `S_OpacitySoftness`
- `S_DepthFadeDistance`

### 冲击波 / 环形相关

- `S_RingWidth`
- `S_RingRadius`
- `S_RingSoftness`
- `S_HitMaskIntensity`

## 推荐命名模板

### 护盾材质

- `V_ShieldColor`
- `S_FresnelExponent`
- `S_FresnelIntensity`
- `T_Noise`
- `S_NoiseStrength`
- `S_FlowSpeed`

### 爆炸核心材质

- `V_CoreColor`
- `V_OuterColor`
- `S_CorePower`
- `S_EdgeBreakup`
- `S_EmissiveIntensity`

### 烟雾材质

- `T_Mask`
- `T_Noise`
- `S_Opacity`
- `S_NoiseStrength`
- `S_DepthFadeDistance`

### 拖尾材质

- `V_TrailColor`
- `S_TrailHeadBrightness`
- `S_TrailTailOpacity`
- `S_FlowSpeed`
- `S_NoiseStrength`

### 冲击波材质

- `V_RingColor`
- `S_RingWidth`
- `S_RingSoftness`
- `S_DistortionStrength`
- `S_EmissiveIntensity`

## Niagara 联动时的建议

如果某些参数会被 Niagara Dynamic Parameter、User Parameter 或 Material Parameter Collection 驱动，命名可以进一步统一：

- `S_UserIntensity`
- `S_UserOpacity`
- `V_UserTint`
- `S_UserPulseSpeed`

或者更明确一些：

- `S_NiagaraAlpha`
- `S_NiagaraGlow`
- `V_NiagaraTint`

重点不是必须用哪一种，而是选一种后保持一致。

## 一个推荐的实际风格

如果你想让我后续默认按一套统一规则产出，我建议优先用这一套：

- Scalar: `S_`
- Vector: `V_`
- Texture: `T_`
- Static Switch: `SS_`

然后参数主体用清晰英文名：

- `S_EmissiveIntensity`
- `S_FresnelExponent`
- `S_NoiseStrength`
- `S_FlowSpeed`
- `S_DepthFadeDistance`
- `V_ShieldColor`
- `V_CoreColor`
- `T_Noise`
- `T_FlowMap`

这套规则的优点是：
- AI 好遵循
- 人也好读
- 材质实例里会很整齐

---

---
## 8. 移动端简化建议

当目标平台是 Android 或低端硬件时，优先做这些简化：

- 少采样：尽量减少纹理采样次数
- 少分支：避免复杂条件判断
- 少层叠：不要叠太多材质效果
- 少透明开销：控制大面积半透明覆盖

### 推荐替代方案

高成本方案 -> 移动端替代方案

- Flow Map -> 单层或双层 Panner
- 折射 -> Emissive 扰动
- 多层 Noise -> 单层灰度噪声
- 复杂 Fresnel 叠加 -> 单层 Fresnel
- 高分辨率贴图 -> 512 或更低分辨率

---
