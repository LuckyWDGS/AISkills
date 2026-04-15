# Niagara VFX 材质配方库

## 用途

这份文档用于沉淀 Niagara 特效里常见、可复用的材质做法。

适合在这些场景读取：
- 需要快速给出材质搭建方案
- 用户想知道某类特效常用什么节点结构
- 需要从视觉目标反推材质实现
- 需要给出适合 PC / Android 的材质简化版本

---

## 目录

1. 参数命名约定
2. 护盾类材质
3. 爆炸与能量球材质
4. 烟雾与雾气材质
5. 拖尾与流动材质
6. 冲击波材质
7. 移动端简化建议

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

## 2. 护盾类材质

### 1.1 Additive 能量护盾

**适用场景**：
- 魔法护盾
- 科技护罩
- 外轮廓能量层

**推荐设置**：
- Blend Mode: Additive
- Shading Model: Unlit
- Two Sided: On

**核心节点思路**：
```text
Fresnel
  × 主色
  × 强度参数

+ Noise Texture
  × 扰动强度

+ Panner
  驱动 UV 流动
```

**视觉重点**：
- 让边缘比中心更亮
- 加轻微噪声，避免表面太死
- 用 Panner 做缓慢能量流动

**常用参数**：
- Fresnel Exponent: 2.5 - 6
- Emissive Intensity: 2 - 10
- Panner Speed: 0.02 - 0.15

**节点搭建模板**：
```text
TextureCoordinate
  -> Panner
  -> Noise Texture Sample

Fresnel
  × Vector Parameter (V_ShieldColor)
  × Scalar Parameter (S_FresnelIntensity)

Noise Texture
  × Scalar Parameter (S_NoiseStrength)

(Fresnel Result + Noise Result)
  -> Emissive Color
```

**参数推荐值**：
- V_ShieldColor: 蓝色 / 青色 / 紫色
- S_FresnelIntensity: 2 - 6
- S_NoiseStrength: 0.1 - 0.5
- S_FlowSpeed_XY: 0.02 - 0.08

### 1.2 半透明冲击护盾

**适用场景**：
- 被攻击时的受击面
- 护盾破碎前的瞬时反馈

**推荐设置**：
- Blend Mode: Translucent
- Shading Model: Unlit

**核心节点思路**：
```text
SphereMask / Radial Gradient
  -> 做局部命中范围

Noise
  -> 打破完美圆形边缘

Fresnel
  -> 增强轮廓
```

**视觉重点**：
- 受击点要有明显的亮度峰值
- 边缘可略带锯齿感或电流感
- 命中区域向外扩散时，透明度逐渐下降

**节点搭建模板**：
```text
Radial Gradient / SphereMask
  × Scalar Parameter (S_HitMaskIntensity)

Noise Texture
  -> 扰动 Mask 边缘

Fresnel
  × Vector Parameter (V_HitColor)

(Mask + Fresnel)
  -> Emissive / Opacity
```

**参数推荐值**：
- S_HitMaskIntensity: 0.8 - 3
- V_HitColor: 白蓝 / 白紫
- S_NoiseDistortion: 0.05 - 0.25
- S_OpacityPeak: 0.3 - 0.8

---

## 3. 爆炸与能量球材质

### 2.1 爆炸火球核心

**适用场景**：
- 火焰爆炸核心
- 能量爆裂中心
- 高亮冲击团

**推荐设置**：
- Blend Mode: Additive
- Shading Model: Unlit

**核心节点思路**：
```text
Radial Gradient
  × 黑体式颜色渐变

Noise Texture
  扰动边缘

Power
  控制亮部压缩
```

**颜色建议**：
- 中心：白或浅黄
- 中层：黄橙
- 外层：橙红或红黑

**视觉重点**：
- 中心必须最亮
- 边缘不能太圆，加入不规则扰动
- 可配合粒子 Alpha 随生命周期衰减

**节点搭建模板**：
```text
Radial Gradient
  -> Power
  -> 形成高亮核心

Noise Texture
  × Scalar Parameter (S_EdgeBreakup)

Gradient Color Ramp
  × Core Mask

(Core + Noise Distortion)
  -> Emissive
```

**参数推荐值**：
- S_CorePower: 2 - 6
- S_EdgeBreakup: 0.15 - 0.6
- S_EmissiveIntensity: 4 - 20
- S_OuterFade: 0.4 - 1.0

### 2.2 能量球材质

**适用场景**：
- 法术蓄力球
- 科幻能量弹
- 电浆球

**核心节点思路**：
```text
Fresnel
  -> 做边缘发光

Noise / Voronoi
  -> 做内部纹理

Panner
  -> 做内部流动

Depth Fade
  -> 柔化与场景的交界
```

**视觉重点**：
- 内部纹理和外轮廓要分层
- 内部流动速度通常比外壳慢
- 不同颜色层可以制造更强能量感

**节点搭建模板**：
```text
Fresnel
  × V_EdgeColor

Noise / Voronoi
  <- Panner

Depth Fade
  -> soften edge intersection

(Inner Noise + Fresnel)
  -> Emissive
```

**参数推荐值**：
- S_EdgeColorIntensity: 2 - 8
- S_InnerFlowSpeed: 0.03 - 0.15
- S_NoiseContrast: 0.5 - 2
- S_DepthFadeDistance: 10 - 80

---

## 4. 烟雾与雾气材质

### 3.1 基础烟雾材质

**适用场景**：
- 爆炸余烟
- 环境雾团
- 魔法消散尾气

**推荐设置**：
- Blend Mode: Translucent
- Shading Model: Unlit

**核心节点思路**：
```text
Alpha Mask
  × Particle Color Alpha

Soft Noise
  -> 破边

Depth Fade
  -> 柔化穿插地面或模型的边缘
```

**视觉重点**：
- 烟雾边缘不要太硬
- 透明度变化比颜色变化更关键
- 多层低对比噪声通常比单层高对比更自然

**节点搭建模板**：
```text
Alpha Mask
  × Particle Color Alpha

Soft Noise
  -> Multiply into alpha edge

Depth Fade
  -> final opacity softening

Result
  -> Opacity
```

**参数推荐值**：
- S_Opacity: 0.15 - 0.6
- S_NoiseStrength: 0.1 - 0.35
- S_DepthFadeDistance: 20 - 120
- S_NoiseContrast: 低到中

### 3.2 卡通雾气材质

**适用场景**：
- 风格化项目
- 卡通爆炸尘团
- 夸张魔法烟气

**核心节点思路**：
```text
Posterized Gradient
  -> 分段颜色

Smooth Noise
  -> 轻度形变
```

**视觉重点**：
- 轮廓清晰
- 渐变层数少
- 不追求拟真体积感，而追求图形感

**节点搭建模板**：
```text
Gradient
  -> Posterize / Step

Smooth Noise
  -> 轻度扭曲轮廓

Result
  -> Base Color / Opacity
```

**参数推荐值**：
- S_GradientSteps: 2 - 5
- S_NoiseDistortion: 0.03 - 0.12
- S_Opacity: 0.4 - 0.9

---

## 5. 拖尾与流动材质

### 4.1 Ribbon 能量拖尾

**适用场景**：
- 刀光
- 飞弹拖尾
- 能量轨迹

**推荐设置**：
- Ribbon Renderer 配合使用
- Blend Mode: Additive

**核心节点思路**：
```text
Gradient UV
  -> 控制头尾亮度

Panner
  -> 制造沿拖尾方向的流动

Noise
  -> 打破过于平滑的边缘
```

**视觉重点**：
- 头部亮、尾部散
- 沿长度方向必须有节奏变化
- 可以叠一层细高光提升速度感

**节点搭建模板**：
```text
TexCoord
  -> Gradient Along Ribbon

Panner
  -> Secondary noise flow

Gradient * Noise
  -> Emissive

Gradient
  -> Opacity
```

**参数推荐值**：
- S_TrailHeadBrightness: 3 - 12
- S_TrailTailOpacity: 0 - 0.4
- S_FlowSpeed: 0.1 - 0.8
- S_WidthHighlightStrength: 0.2 - 0.6

### 4.2 流动物质材质

**适用场景**：
- 魔法流线
- 水流能量
- 表面能量输运

**核心节点思路**：
```text
Flow Map
  -> 控制 UV 方向

Panner
  -> 基础移动

Mask
  -> 控制流动范围
```

**视觉重点**：
- 方向变化比单纯平移更像“流动”
- Flow Map 适合做高质量版
- 简化版可只用双层 Panner 叠加假装流向变化

**节点搭建模板**：
```text
Flow Map
  -> UV Offset

Base Texture
  <- Offset UV

Mask
  × Flow Result

Result
  -> Emissive / Opacity
```

**参数推荐值**：
- S_FlowStrength: 0.03 - 0.2
- S_FlowSpeed: 0.02 - 0.1
- S_MaskContrast: 0.8 - 2

---

## 6. 冲击波材质

### 5.1 圆环冲击波

**适用场景**：
- 爆炸扩散环
- 受击冲击圈
- 落地震荡波

**核心节点思路**：
```text
Radial Gradient
  - 内圈
  - 外圈
  = 细环

Noise
  -> 扰动边缘

Power / Clamp
  -> 控制宽度和锐度
```

**视觉重点**：
- 冲击波最关键的是“扩张节奏”
- 环宽不能一直不变，通常前期薄、后期稍散
- 配合折射或亮度提升会更有冲击感

**节点搭建模板**：
```text
Radial Gradient
  - Inner Gradient
  = Ring Mask

Noise
  -> Distort ring edge

Ring Mask
  -> Emissive / Opacity
```

**参数推荐值**：
- S_RingWidth: 0.03 - 0.15
- S_EdgeDistortion: 0.02 - 0.2
- S_EmissiveIntensity: 1.5 - 8

### 5.2 折射型冲击波

**适用场景**：
- 空气震荡
- 高能爆炸
- 科幻冲击面

**注意**：
- 折射在移动端风险高
- 多个折射叠加容易贵

**建议**：
- PC 版可用折射
- Android 版尽量退化为亮度扰动或假法线

**节点搭建模板**：
```text
Radial Ring Mask
  -> Refraction Amount

Noise Normal / Fake Distortion
  -> Refraction Disturbance

Optional Emissive Rim
  -> readability boost
```

**参数推荐值**：
- S_RefractionAmount: 0.01 - 0.08
- S_DistortionStrength: 0.02 - 0.12
- S_RimIntensity: 0.5 - 4

---

## 7. 移动端简化建议

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

## 使用建议

当用户说“帮我做某种效果”时，可以先从这里选一个接近的材质配方，再结合：
- `references/core.md` 里的整体设计方法
- `references/platform-optimization.md` 里的平台限制
- `references/advanced-techniques.md` 里的高阶实现方式

这样输出会更快、更稳，也更像生产方案。
