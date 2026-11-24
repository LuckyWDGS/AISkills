# Niagara VFX Artist Skill - 示例对话

## 示例 1: 魔法护盾特效

### 用户输入
```
/niagara

我想做一个魔法护盾的特效，蓝紫色的，有能量波动的感觉，
当受到攻击时会产生涟漪效果。
```

### AI 输出示例

```markdown
## 🎨 视觉分析

魔法护盾特效的核心在于"防御感"与"能量流动感"的平衡。基于你的描述，我建议：

**核心视觉元素**:
- 半透明的球形或六边形几何护盾结构
- 表面持续的能量波纹扩散（类似水波）
- 边缘明显的菲涅尔高光（Fresnel），增强科技感
- 受击时从撞击点向外扩散的涟漪波纹
- 护盾表面有细微的噪声扰动，避免过于静态

**风格定位**: 科幻魔法混合风格，偏向《守望先锋》zarya 护盾的质感

## 🌈 色彩方案

**主色调**: #4A90E2 (HSV: 210°, 68%, 89%) - 科技蓝
- 代表稳定、防御、能量的核心色

**强调色**: #9B59B6 (HSV: 280°, 52%, 71%) - 神秘紫
- 用于能量流动和波纹效果

**高光色**: #FFFFFF (HSV: 0°, 0%, 100%) - 纯白
- 用于边缘菲涅尔和受击闪光

**阴影色**: #1A3A5C (HSV: 210°, 72%, 36%) - 深蓝
- 用于护盾内侧和暗部

### Color Curve 设置（用于能量波纹粒子）

```
Time 0.0 (波纹产生): RGB(155, 89, 182) - 紫色核心，高亮度
Time 0.3 (波纹扩散): RGB(74, 144, 226) - 蓝色主体，中等亮度
Time 0.7 (波纹衰减): RGB(100, 160, 230) - 淡蓝色，降低饱和度
Time 1.0 (波纹消失): RGB(200, 220, 255) - 极淡蓝，接近透明
```

## ⚡ 运动设计

### 护盾主体（静态球体 + 噪声扰动）

**持续状态**:
- 使用 Mesh Renderer（球体或六边形网格）
- 材质中添加 Panner 节点实现 UV 滚动
- Noise Texture 控制表面扰动（速度: 0.1）

### 能量波纹（粒子系统）

**生成阶段 (0.0 - 0.1)**:
- Spawn Location: 护盾表面随机点
- Initial Velocity: 0（静止产生）
- Initial Size: 5（小点）
- Initial Alpha: 1.0（完全不透明）

**扩散阶段 (0.1 - 0.6)**:
- Radial Velocity: 150（向外扩散）
- Scale Curve: 5 → 80（快速放大）
- Alpha Curve: 1.0 → 0.6（保持可见）
- Drag: 0.5（轻微阻力）

**消散阶段 (0.6 - 1.0)**:
- Scale Curve: 80 → 120（继续放大）
- Alpha Curve: 0.6 → 0.0（淡出）
- Drag: 2.0（增加阻力，减速）

### 受击涟漪（事件触发）

**冲击阶段 (0.0 - 0.15)**:
- Spawn Burst: 50 粒子
- Initial Velocity: 300（强烈爆发）
- Flash Effect: Emissive × 5（瞬间闪光）

**涟漪扩散 (0.15 - 0.8)**:
- 3-5 层同心圆波纹
- 每层延迟 0.1 秒
- Radial Velocity: 200 → 50（减速扩散）

## 🔧 Niagara 配置

### 系统 1: 护盾主体（Mesh Emitter）

#### Emitter Settings
```
Emitter State: Persistent（持续存在）
Spawn Rate: 1（只生成一个护盾网格）
Lifetime: Infinite（无限生命周期）
```

#### Particle Update Modules
1. **Mesh Renderer**
   - Mesh: Sphere (或自定义六边形网格)
   - Material: M_Shield_Base
   - Scale: 200, 200, 200

2. **Rotate Around Point**
   - Rotation Speed: (0, 0, 10) - 缓慢自转
   - Axis: Z-axis

#### Material: M_Shield_Base
```
Base Color: Constant3Vector (0.29, 0.56, 0.89) - 蓝色
Emissive: 
  - Fresnel (Exponent: 3.0) × Color (0.6, 0.8, 1.0) × 2.0
  - Noise Texture (Panner Speed: 0.1) × 0.3
Opacity: 0.4
Blend Mode: Translucent
```

### 系统 2: 能量波纹（Sprite Emitter）

#### Emitter Settings
```
Spawn Rate: 5（每秒 5 个波纹）
Lifetime: 2.0 ± 0.3（2 秒生命周期）
```

#### Initialize Particle
```
Sphere Location:
  - Sphere Radius: 200（护盾半径）
  - Surface Only: True（只在表面生成）

Initial Velocity:
  - Velocity Mode: From Point
  - Velocity: 0（初始静止）

Initial Size: 5

Initial Color: From Curve (见上方 Color Curve)
```

#### Particle Update Modules
1. **Add Velocity**
   - Velocity: Radial Direction × 150
   - Velocity Mode: From Center

2. **Scale Sprite Size**
   - Scale Curve (Normalized Age):
     - 0.0: 1.0
     - 0.1: 3.0
     - 0.6: 16.0
     - 1.0: 24.0

3. **Scale Color**
   - Alpha Curve (Normalized Age):
     - 0.0: 1.0
     - 0.6: 0.6
     - 1.0: 0.0

4. **Drag**
   - Drag: 0.5 → 2.0 (Curve)

#### Sprite Renderer
```
Material: M_Shield_Ripple
Alignment: Velocity Aligned（朝向运动方向）
Sub UV: None
```

#### Material: M_Shield_Ripple
```
Base Color: Particle Color
Emissive: Particle Color × 3.0
Opacity: Particle Alpha × Radial Gradient
Blend Mode: Additive（叠加混合）
```

### 系统 3: 受击涟漪（Event-Driven）

#### Event Receiver
```
Event Name: "OnShieldHit"
Spawn Burst: 50
Execution Mode: Spawned Particles
```

#### Initialize Particle
```
Location: Event Payload (Hit Location)
Initial Velocity: Radial from Hit Point × 300
Initial Size: 10
Initial Color: RGB(255, 255, 255) - 白色闪光
```

#### Particle Update Modules
1. **Scale Sprite Size**
   - Curve: 10 → 5 → 0（先缩小再消失）

2. **Scale Color**
   - Alpha Curve: 1.0 → 0.0 (0.3 秒内快速淡出)

3. **Drag**
   - Drag: 5.0（快速减速）

## 💡 实现建议

### 步骤 1: 创建护盾主体
1. 新建 Niagara System，命名为 `NS_MagicShield`
2. 添加 Mesh Emitter，选择球体网格
3. 创建材质 `M_Shield_Base`，设置菲涅尔和噪声
4. 调整透明度和自发光强度

### 步骤 2: 添加能量波纹
1. 在同一系统中添加 Sprite Emitter
2. 设置球面生成位置
3. 配置径向扩散速度
4. 创建 Color Curve 和 Scale Curve
5. 创建材质 `M_Shield_Ripple`（Additive 混合）

### 步骤 3: 实现受击效果
1. 在蓝图中创建 Event Dispatcher
2. 当护盾受击时，调用 `SpawnSystemAtLocation`
3. 传递撞击点位置给 Niagara Event
4. 配置爆发粒子和涟漪效果

### 步骤 4: 优化与调试
1. 调整粒子数量（移动端建议 Spawn Rate: 3）
2. 测试不同角度的视觉效果
3. 调整菲涅尔强度，确保边缘清晰
4. 添加音效配合视觉冲击

## 📊 参考曲线

### Scale Curve (能量波纹大小)
```
f(t) = 5 + 115 × (1 - e^(-5t))
```
- 快速增长后趋于平缓
- 最终大小约 120

### Alpha Curve (透明度衰减)
```
f(t) = 1.0 × (1 - t)^2  (t ∈ [0.6, 1.0])
```
- 前 60% 保持可见
- 后 40% 平方衰减

## 🎯 性能优化建议

**PC/主机平台**:
- Spawn Rate: 5-8
- Max Particles: 100
- 可以添加更多细节层

**移动平台**:
- Spawn Rate: 2-3
- Max Particles: 30
- 简化材质，移除噪声扰动
- 使用 Simple Lit 材质

## 🔄 变体建议

**火焰护盾**: 
- 颜色改为橙红色 (#FF6B35 → #FF0000)
- 添加向上飘动的火花粒子
- 增加扰动强度

**冰霜护盾**:
- 颜色改为青蓝色 (#00D9FF → #FFFFFF)
- 添加冰晶粒子
- 降低透明度，增加折射效果

**暗影护盾**:
- 颜色改为紫黑色 (#4B0082 → #000000)
- 添加烟雾效果
- 使用 Subtractive 混合模式
```

---

## 示例 2: 火焰爆炸特效

### 用户输入
```
/niagara

我想做一个火焰爆炸特效，要有蓄力、爆发、消散三个阶段，
颜色从白色到橙色再到黑烟。
```

### AI 输出示例

```markdown
## 🎨 视觉分析

火焰爆炸是经典的三阶段特效，核心在于"能量积聚 → 瞬间释放 → 余波消散"的节奏控制。

**关键视觉特征**:
- 蓄力阶段：粒子向中心聚拢，颜色偏红，有吸气感
- 爆发阶段：强烈的白色闪光，粒子高速向外扩散
- 消散阶段：橙色火焰转为黑烟，向上飘散

**参考**: 《鬼泣 5》但丁的爆炸技能，《原神》可莉的爆炸

## 🌈 色彩方案

**蓄力阶段**: #FF4500 (橙红色) - 能量积聚
**爆发阶段**: #FFFFFF (纯白) - 极高温度
**火焰阶段**: #FF6B35 → #FF0000 (橙到红)
**烟雾阶段**: #8B4513 → #2C2C2C (棕到黑)

### Color Curve 设置
```
Time 0.0-0.2 (蓄力): RGB(255, 69, 0) - 橙红
Time 0.2-0.25 (闪光): RGB(255, 255, 255) - 纯白
Time 0.25-0.5 (火焰): RGB(255, 107, 53) → RGB(255, 0, 0)
Time 0.5-1.0 (烟雾): RGB(139, 69, 19) → RGB(44, 44, 44)
```

## ⚡ 运动设计

### 蓄力阶段 (0.0 - 0.2)
- Point Attraction Force: -200（向中心吸引）
- Spawn Rate: 20 → 100（逐渐增加）
- Particle Size: 10 → 30（逐渐变大）
- Drag: 5.0（高阻力，缓慢移动）

### 爆发阶段 (0.2 - 0.3)
- Spawn Burst: 200（瞬间爆发）
- Initial Velocity: 800（极高速度）
- Emissive Multiplier: 10（强烈发光）
- Camera Shake: 强度 5.0

### 消散阶段 (0.3 - 1.0)
- Gravity: (0, 0, 50)（向上飘）
- Curl Noise Force: 100（混沌运动）
- Drag: 1.0 → 5.0（逐渐减速）
- Size: 50 → 150（膨胀）
- Alpha: 1.0 → 0.0（淡出）

## 🔧 Niagara 配置

[详细配置...]
```

---

这些示例展示了 AI 会如何响应你的需求，提供详细的艺术指导和技术参数！
