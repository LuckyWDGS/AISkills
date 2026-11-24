# UE 材质配方：护盾、爆炸、能量球、烟雾

## 用途

读取这份 reference 当任务是能量护盾、冲击护盾、爆炸核心、能量球、烟雾或雾气材质，需要快速选择 Blend/Shading/节点链/参数。

## 目录

- [护盾类材质](#2-护盾类材质)
- [爆炸与能量球材质](#3-爆炸与能量球材质)
- [烟雾与雾气材质](#4-烟雾与雾气材质)

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
