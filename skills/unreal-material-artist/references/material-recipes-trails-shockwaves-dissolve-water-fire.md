# UE 材质配方：拖尾、冲击波、消融、水、火

## 用途

读取这份 reference 当任务是 Ribbon/流动拖尾、冲击波、消融边缘、程序噪声、水材质、Additive 火焰 mask，或需要把这些常见 VFX route 组合成可审查图。

## 目录

- [拖尾与流动材质](#5-拖尾与流动材质)
- [冲击波材质](#6-冲击波材质)
- [消融、噪声、水、火实战配方](#7-消融噪声水火实战配方)

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
- Two Sided: Niagara SubUV/sprite 默认关闭；它通常面向摄像机，只有非 camera-facing card/mesh 有明确需求时才开启

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
- `Two Sided + Additive` 不是普通“背面也可见”开关；在卡片、圆锥、壳体或重叠粒子上，前后面/多层像素会相加，可能把原本合理的 HDR 强度推成死白。先估算可见叠层，再调 `EmissiveIntensity` / `Opacity`。
- 闭合圆锥/圆柱/管状 mesh 使用 `UV.x` 环绕时，横向噪声平铺参数必须记录接缝约束；`TileU=2.0/3.0` 这种整数安全，`2.2` 这种非整数容易在 0/1 接缝处形成竖向分割线。
- 拉伸/平移噪声在闭合体上出现 mip 接缝或闪烁时，不要只继续调 `TileU`。可把噪声 `TextureSample` 切到 `MipValueMode=Derivative`，用干净 `TexCoord[0] -> DDX/DDY` 驱动导数输入，让 mip 选择不再跟随被平铺和 Panner 扭曲后的 UV。
- 低模圆锥/圆柱体积光边缘有三角面棱角时，优先判断 Fresnel 是否在吃真实低模法线。`LocalPosition -> Mask RG -> Append 0 -> Normalize -> Transform LocalToWorld -> Fresnel.Normal` 只能作为明确的视觉测试分支；如果它改变了预期光束形体或边缘衰减，要立刻回退。
- 如果用户要求写实火把、篝火、爆炸火、魔法火、蓝焰、火焰包裹物体或参考图匹配，先写视觉目标和承载方式，再决定是 flipbook、mask+panner、burn edge、lava surface 还是 heat haze。不能直接套这一段。
- 做完要读回材质图并跑审查；火材质的验收至少包含可见火舌/色带/alpha 形状、运动方案、背景可读性和 shader complexity/overdraw 风险。

---
