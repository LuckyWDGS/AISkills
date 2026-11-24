# Niagara VFX 高级技术指南

**版本**: v1.0.0  
**更新日期**: 2026/04/14

---

## 📋 目录

1. [纹理生成与优化](#纹理生成与优化)
2. [Flipbook 工作流](#flipbook-工作流)
3. [HLSL 自定义模块](#hlsl-自定义模块)
4. [Flow Maps 流向图](#flow-maps-流向图)
5. [通道打包优化](#通道打包优化)

---

## 纹理生成与优化

### 1.1 无缝噪声纹理生成

#### AI 生成工作流
```
推荐工具:
├── Stable Diffusion（无缝平铺扩展）
├── Substance Designer（程序化生成）
└── Photoshop（手动绘制）

关键要求:
├── 无缝平铺（Seamless Tiling）
├── 高对比度（用于遮罩）
├── 灰度图（便于通道打包）
└── 分辨率: 512x512 或 1024x1024
```

#### 提示词示例（Stable Diffusion）
```
正面提示词:
"seamless tileable texture, high contrast noise pattern, 
black and white, fractal structure, organic flow, 
for VFX alpha mask, 4K resolution"

负面提示词:
"seams, borders, text, watermark, low contrast"

设置:
├── 启用 Tiling 模式
├── CFG Scale: 7-10
├── Steps: 30-50
└── Sampler: DPM++ 2M Karras
```

### 1.2 纹理类型与用途

| 纹理类型 | 用途 | 特征 | 生成方法 |
|---------|------|------|---------|
| Perlin Noise | 大尺度扰动 | 低频，平滑 | Substance, AI |
| Voronoi Noise | 细节破碎 | 高频，细胞状 | Substance, AI |
| Flow Map | UV 流动 | RG 通道向量 | Houdini, AI |
| Alpha Mask | 透明遮罩 | 高对比度 | AI, Photoshop |
| Gradient | 径向渐变 | 中心到边缘 | Substance, 手绘 |

### 1.3 纹理验证清单

✅ **质量检查**:
- [ ] 无缝平铺（在 UE 中用 Panner 测试）
- [ ] 对比度足够（黑白分明）
- [ ] 无压缩伪影（使用 PNG 或 TGA）
- [ ] 分辨率合适（移动端 512，PC 1024）
- [ ] Mipmap 正确（避免闪烁）

---

## Flipbook 工作流

### 2.1 什么是 Flipbook？

Flipbook（序列帧纹理）是将多帧动画打包到单张纹理图集（Texture Atlas）中的技术，用于模拟复杂的 3D 流体效果。

```
典型布局:
8x8 网格 = 64 帧动画
├── 每格: 128x128 像素
├── 总纹理: 1024x1024
└── 播放速度: 由粒子生命周期控制
```

### 2.2 UE5 Niagara Baker 工具

#### 内置 Baker 优势
```
传统流程（Houdini）:
Houdini Pyro → 渲染序列 → 合成图集 → 导入 UE
⏱️ 时间: 数小时到数天

UE5 Baker 流程:
Niagara 系统 → Baker 工具 → Flipbook 纹理
⏱️ 时间: 几分钟
```

#### 使用步骤
```
1. 创建复杂的 3D Niagara 系统
   ├── 使用 Mesh Renderer
   ├── 或使用 Niagara Fluids
   └── 调整到满意的效果

2. 打开 Niagara Baker
   ├── Window → Niagara Baker
   ├── 选择要烘焙的 Niagara System
   └── 设置摄像机角度

3. 配置 Baker 设置
   ├── Texture Size: 1024x1024 或 2048x2048
   ├── Frames: 64 (8x8) 或 100 (10x10)
   ├── Frame Rate: 30 FPS
   └── Output Path: /Game/VFX/Flipbooks/

4. 烘焙并导出
   ├── 点击 "Bake"
   ├── 等待渲染完成
   └── 自动生成 Flipbook 纹理
```

### 2.3 在材质中使用 Flipbook

#### 材质节点设置
```
Material Graph:
├── Flipbook 节点
│   ├── Texture: 你的 Flipbook 纹理
│   ├── Horizontal Frames: 8
│   ├── Vertical Frames: 8
│   └── Animation: Particle.NormalizedAge
├── 连接到 Emissive Color
└── 连接到 Opacity
```

#### Niagara 模块配置
```
Sprite Renderer:
├── Sub UV Animation Mode: Linear
├── Sub Image Size: (8, 8)
├── Sub UV Blending: 启用（平滑过渡）
└── Bound Mode: Dynamic
```

### 2.4 性能优势

| 方法 | 粒子数 | GPU 时间 | 内存 |
|------|--------|---------|------|
| 3D Mesh 粒子 | 100 | ~5ms | 高 |
| Flipbook 2D | 1000 | ~1ms | 低 |
| 性能提升 | 10x | 5x | 3x |

---

## HLSL 自定义模块

### 3.1 Scratch Pad 模块基础

#### 什么是 Scratch Pad？
Scratch Pad 允许你在 Niagara 中编写自定义 HLSL 代码来控制粒子行为，突破节点系统的限制。

#### 创建 Scratch Pad 模块
```
步骤:
1. 在 Niagara System 中右键
2. 选择 "Create Scratch Pad Module"
3. 定义输入输出参数
4. 编写 HLSL 代码
5. 编译并应用到 Emitter
```

### 3.2 HLSL 代码结构

#### 基础模板
```hlsl
// 输入参数（在 Scratch Pad 中定义）
float3 Emitter.VortexCenter;
float Engine.DeltaTime;
float3 Particles.Position;
float3 Particles.Velocity;

// 输出参数
float3 OutVelocity;

// 主函数
void CustomVortex()
{
    // 计算到漩涡中心的向量
    float3 ToCenter = Emitter.VortexCenter - Particles.Position;
    float Distance = length(ToCenter);
    
    // 归一化方向
    float3 Direction = normalize(ToCenter);
    
    // 计算切线力（叉积）
    float3 TangentForce = cross(Direction, float3(0, 0, 1));
    
    // 应用力
    float Strength = 100.0 / (Distance + 1.0);
    OutVelocity = Particles.Velocity + TangentForce * Strength * Engine.DeltaTime;
}
```

### 3.3 常用 HLSL 函数

#### 向量数学
```hlsl
// 距离计算
float dist = length(PositionA - PositionB);

// 归一化
float3 dir = normalize(Vector);

// 点积（角度关系）
float dot_product = dot(VectorA, VectorB);

// 叉积（垂直向量）
float3 perpendicular = cross(VectorA, VectorB);

// 线性插值
float3 result = lerp(A, B, t);

// 平滑阶梯
float smooth = smoothstep(min, max, value);

// 硬件优化的阶梯函数（避免 if）
float condition = step(threshold, value);
```

#### 噪声与随机
```hlsl
// 伪随机（基于位置）
float random = frac(sin(dot(Position.xy, float2(12.9898, 78.233))) * 43758.5453);

// Perlin Noise（需要纹理采样）
float noise = Texture2DSample(NoiseTexture, UV + Time * Speed).r;

// 湍流（多层噪声）
float turbulence = 0;
for(int i = 0; i < 4; i++)
{
    float freq = pow(2.0, i);
    turbulence += Texture2DSample(NoiseTexture, UV * freq).r / freq;
}
```

### 3.4 使用 AI 辅助编写 HLSL

#### 提示词模板
```
你是 UE5 Niagara HLSL 专家。

环境:
- 引擎版本: UE5.5
- 模拟类型: GPU Compute Sim
- 目标: 创建粒子漩涡效果

输入参数:
- float3 Particles.Position
- float3 Particles.Velocity
- float3 Emitter.VortexCenter
- float Engine.DeltaTime

输出参数:
- float3 OutVelocity

要求:
1. 使用叉积生成切线力
2. 力的强度随距离衰减（1/r）
3. 避免使用 if/else，使用 step() 或 lerp()
4. 添加详细注释

请提供完整的 HLSL 代码。
```

---

## Flow Maps 流向图

### 4.1 什么是 Flow Map？

Flow Map 是一种特殊纹理，使用 RG 通道编码 2D 向量场，用于驱动 UV 坐标沿特定方向流动。

```
通道编码:
├── R 通道: X 方向偏移（0-1 映射到 -1 到 1）
├── G 通道: Y 方向偏移（0-1 映射到 -1 到 1）
└── 中性值: (0.5, 0.5) = 无偏移
```

### 4.2 Flow Map 生成方法

#### 方法 1: Houdini（传统）
```
Houdini 流程:
1. 创建流体模拟
2. 提取速度场
3. 投影到 2D 平面
4. 归一化并编码到 RG 通道
5. 导出为纹理
```

#### 方法 2: Substance Designer
```
节点流程:
1. Gradient Map（创建基础流向）
2. Warp（添加扰动）
3. Vector Map（编码为 RG）
4. 导出为 Flow Map
```

#### 方法 3: 手绘（简单场景）
```
Photoshop/Krita:
1. 创建 RGB 图像
2. R 通道: 绘制 X 方向（左=黑，右=白）
3. G 通道: 绘制 Y 方向（下=黑，上=白）
4. 中性灰 (128, 128, 0) = 无流动
```

### 4.3 在材质中使用 Flow Map

#### 材质节点设置
```hlsl
// 采样 Flow Map
float2 FlowVector = Texture2DSample(FlowMap, UV).rg;

// 解码（0-1 → -1 到 1）
FlowVector = (FlowVector - 0.5) * 2.0;

// 应用到 UV
float2 DistortedUV = UV + FlowVector * FlowStrength * Time;

// 采样主纹理
float4 Color = Texture2DSample(MainTexture, DistortedUV);
```

#### 在 Niagara 中使用 Flow Map
```
Niagara 模块:
├── Sample Texture 2D
│   ├── Texture: FlowMap
│   ├── UV: Particles.UV0
│   └── Output: FlowVector
├── Vector Math
│   ├── 解码: (FlowVector - 0.5) * 2.0
│   └── 应用: Position += FlowVector * Strength
└── Update Particle Position
```

### 4.4 Flow Map 应用场景

| 场景 | 用途 | 效果 |
|------|------|------|
| 魔法护盾 | 能量流动 | 符文沿路径移动 |
| 水面 | 水流方向 | 波纹沿河流动 |
| 岩浆 | 熔岩流动 | 热流沿裂缝 |
| 能量场 | 粒子轨迹 | 粒子沿力场线 |

---

## 通道打包优化

### 5.1 为什么需要通道打包？

```
问题:
├── 4 张灰度图 = 4 次纹理采样
├── 每次采样 = GPU 性能开销
└── 移动端尤其敏感

解决方案:
├── 1 张 RGBA 纹理 = 1 次采样
├── 4 个通道 = 4 张灰度图
└── 性能提升 4x
```

### 5.2 通道分配策略

#### 推荐分配
```
RGBA 通道打包:
├── R 通道: 低频噪声（Perlin）- 整体扰动
├── G 通道: 高频噪声（Voronoi）- 边缘细节
├── B 通道: 渐变遮罩 - 自发光强度
└── A 通道: Alpha 遮罩 - 透明度
```

### 5.3 打包工具和方法

#### 方法 1: Photoshop
```
步骤:
1. 打开 4 张灰度图
2. 创建新的 RGBA 文档
3. 通道面板 → 分别粘贴到 R/G/B/A
4. 保存为 PNG 或 TGA（无压缩）
```

#### 方法 2: Python 脚本
```python
from PIL import Image

# 加载 4 张灰度图
r_img = Image.open('noise_low.png').convert('L')
g_img = Image.open('noise_high.png').convert('L')
b_img = Image.open('gradient.png').convert('L')
a_img = Image.open('alpha_mask.png').convert('L')

# 合并到 RGBA
packed = Image.merge('RGBA', (r_img, g_img, b_img, a_img))
packed.save('packed_texture.png')
```

#### 方法 3: Substance Designer
```
节点流程:
1. 创建 4 个输入节点
2. 使用 Channel Shuffle 节点
3. 分配到 RGBA 通道
4. 导出为单张纹理
```

### 5.4 在材质中使用打包纹理

```hlsl
// 单次采样获取所有数据
float4 PackedData = Texture2DSample(PackedTexture, UV);

// 分离通道
float LowFreqNoise = PackedData.r;
float HighFreqNoise = PackedData.g;
float Gradient = PackedData.b;
float AlphaMask = PackedData.a;

// 组合使用
float3 Distortion = LowFreqNoise * 0.5 + HighFreqNoise * 0.1;
float Emissive = Gradient * EmissiveStrength;
float Opacity = AlphaMask * OpacityMultiplier;
```

---

## 参考资源

### 官方文档
- [Niagara Flipbook Baker Guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-flipbook-baker-quick-start-guide-in-unreal-engine)
- [Driving Niagara with Flowmaps](https://80.lv/articles/tutorial-driving-niagara-with-flowmaps-and-baked-fluidsim-data)

### 社区教程
- [HLSL Scratch Pad Discussion](https://forums.unrealengine.com/t/rant-about-niagara-scratchpad-developer-assistant/2672488)
- [Flow Map Techniques](https://briz.artstation.com/blog/gg1a/2d-sdf-gradient-flowmap-and-aa-technique-material-function-library-ue5)
- [Texture Distortion Tutorial](https://catlikecoding.com/unity/tutorials/flow/texture-distortion/)

---

**版本**: v1.0.0  
**最后更新**: 2026/04/14

