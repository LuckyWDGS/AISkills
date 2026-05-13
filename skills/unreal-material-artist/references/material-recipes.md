# UE VFX 材质配方库

## 用途

这份文档用于沉淀 Unreal Engine 特效和实时视觉层中常见、可复用的材质做法。

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

## 7. 消融、噪声、水、火实战配方

### 7.1 Masked 消融 + 边缘发光

**适用场景**：
- 物体消失 / 召唤
- 破碎溶解
- 魔法烧蚀边缘

**推荐设置**：
- Material Domain: Surface
- Blend Mode: Masked
- Shading Model: Unlit 或 DefaultLit，取决于是否需要真实受光
- Two Sided: 只有卡片/薄片需要开

**核心节点思路**：
```text
T_DissolveNoise.R
  -> OpacityMask

abs(Noise - S_DissolveThreshold)
  -> edge band
  × V_EdgeColor
  × S_EmissiveIntensity
  -> EmissiveColor
```

**经验规则**：
- 消融形状通常比实时程序噪声更适合用贴图，因为 mask 可复用、可美术控制、跨平台更稳定。
- 缺 noise/mask 图时先查资产库；没有 approved 资产再默认调用 `cm-imagegen` 生成 POT 灰度 tileable mask。
- 消融 mask 导入 UE 后按数据图处理：`TC_Masks`、`sRGB=false`。
- `OpacityMask` 直接接整张 noise 只是结构原型；生产版通常需要 `Threshold/Step/SmoothStep` 控制切线和 clip 进度。

### 7.2 程序噪声 vs 贴图噪声

**适用场景**：
- 程序云雾
- 世界空间脏污
- 小范围随机扰动
- 与对象/世界位置强绑定的材质变化

**判断**：
- 用程序噪声：需要无缝缩放、参数化、世界空间一致性、或简单低频变化。
- 用贴图噪声：静态 breakup、消融 mask、火焰边缘、云状图案、跨平台成本更重要。

**审查重点**：
- 不要只看 sampler 数。程序噪声可能是 0 sampler 但高 ALU。
- 如果程序噪声只是为了做稳定的二维 mask，优先考虑一张 512/1024 POT 的 mask 贴图。
- 如果用 Custom HLSL 做噪声，要给低端平台 fallback 或改成纹理采样。

### 7.3 Single Layer Water 水材质

复杂水材质不要只看这一小节。实际制作前必须读取 `references/complex-water-material-playbook.md`，按其中的路线选择、节点图、纹理角色、预览 gate 和水专项审查执行。

**推荐设置**：
- Material Domain: Surface
- Blend Mode: Opaque
- Shading Model: SingleLayerWater
- 使用 `SingleLayerWaterMaterialOutput` 或等价输出合同

**核心输入**：
- BaseColor / Roughness
- Normal 或 ripple normal
- ScatteringCoefficients
- AbsorptionCoefficients
- PhaseG
- ColorScaleBehindWater

**基础节点路线**：
```text
T_WaterNormalA
  <- TextureCoordinate * S_NormalTilingA + Time * V_NormalSpeedA

T_WaterNormalB
  <- TextureCoordinate * S_NormalTilingB + Time * V_NormalSpeedB

BlendAngleCorrectedNormals(T_WaterNormalA, T_WaterNormalB)
  × S_NormalStrength
  -> Normal

DepthTerm 或手工 shallow/deep mask
  -> Lerp(V_ShallowColor, V_DeepColor)
  -> BaseColor

T_FoamMask.R
  × DepthFoamMask
  × S_FoamIntensity
  -> Lerp(BaseWaterColor, V_FoamColor)

V_ScatteringCoefficients
  -> SingleLayerWaterMaterialOutput.ScatteringCoefficients

V_AbsorptionCoefficients
  -> SingleLayerWaterMaterialOutput.AbsorptionCoefficients

S_PhaseG
  -> SingleLayerWaterMaterialOutput.PhaseG

V_ColorScaleBehindWater
  -> SingleLayerWaterMaterialOutput.ColorScaleBehindWater
```

**经验规则**：
- Single Layer Water 不是普通透明材质；不要因为“水是透明的”就默认改成 Translucent。
- Single Layer Water 的 `Opacity` 不是普通半透明 alpha；它控制 water volume BSDF 与 surface BRDF 的混合比例，调参和审查都要按水模型理解。
- 水材质要单独预算。一个结构很小的 Single Layer Water 也可能显示很高指令数，这是 shading model 成本，不应按普通 DefaultLit 或简单 VFX 预算误判。
- 定制水材质必须先读参考图：泡沫形状、caustics、深浅水颜色、透明度、浪尖、污浊/油膜/魔法感、风格化笔触或卡通边线，哪些是视觉身份，哪些只是技术辅助。
- 资产库里的普通 ripple/noise/foam 图只能在匹配参考图时作为最终视觉贴图；否则最多作为弱 normal、roughness 或 breakup 辅助，不能把参考图风格替换成“通用水”。
- AI 生成的 ripple/height 图可以做原型，但 normal/flow/vector 数据必须技术验证后才能 approved。
- 用 generated height 临时推 normal 时，要标记为 draft；生产版建议用真实 normal、flow map、或 DCC/程序生成并检查 seam。
- 复杂水的最低交付不是一个材质球，而是材质图、参数化 MI、必要贴图/候选贴图、真实水面/岸边/深浅预览和审查报告。

### 7.4 Additive Unlit 火焰 Mask

火、燃烧、余烬、烟、热扭曲、熔岩和能量火不要只看这一小节。实际制作前必须读取 `references/fire-energy-material-playbook.md`，按其中的路线选择、贴图策略、节点图、预览 gate 和专项审查执行。这里的单张 mask 方案只适合原型、细节层或明确风格化的小火焰，不是 hero fire 的默认最终方案。

**推荐设置**：
- Blend Mode: Additive
- Shading Model: Unlit
- Two Sided: sprite/card 需要时开启

**核心节点思路**：
```text
T_FireMask.R
  <- Panner(TextureCoordinate)

T_FireMask.R
  × V_FireColor
  × ParticleColor.RGB
  × S_EmissiveIntensity
  -> EmissiveColor

T_FireMask.R × ParticleColor.A
  -> Opacity
```

**经验规则**：
- 黑底火焰 mask 可用于 additive 原型，但如果材质期望 alpha，就要生成透明 alpha 或做提取/归一化。
- 单张火舌 mask + Panner 适合原型和细节层；火焰主体更适合 flipbook/SubUV。
- Additive 火材质成本不能只看 1 sampler。两面卡片、粒子数量、屏幕覆盖和 overdraw 会决定真实成本。
- 如果用户要求写实火把、篝火、爆炸火、魔法火、蓝焰、火焰包裹物体或参考图匹配，先写视觉目标和承载方式，再决定是 flipbook、mask+panner、burn edge、lava surface 还是 heat haze。不能直接套这一段。
- 做完要读回材质图并跑审查；火材质的验收至少包含可见火舌/色带/alpha 形状、运动方案、背景可读性和 shader complexity/overdraw 风险。

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

## 使用建议

当用户说“帮我做某种效果”时，可以先从这里选一个接近的材质配方，再结合：
- `references/core.md` 里的整体设计方法
- `references/platform-optimization.md` 里的平台限制
- `references/advanced-techniques.md` 里的高阶实现方式

这样输出会更快、更稳，也更像生产方案。
