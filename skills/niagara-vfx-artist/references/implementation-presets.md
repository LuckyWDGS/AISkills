# 实现预设库

## 用途

这份文档用于沉淀 Niagara 常见效果的“实现预设”。

目标不是给完整艺术方案，而是给出：
- 常见 Emitter 结构
- 常见模块顺序
- 常见 Renderer 起步参数
- 能直接落地的起始骨架

适合在这些场景读取：
- 用户要快速起一个效果
- 需要从“空 System”尽快搭到能看的第一版
- 需要统一团队里的 Niagara 起手方式

---

## 目录

1. 使用原则
2. 命中特效预设
3. 火把预设
4. 护盾预设
5. Slash / 拖尾预设
6. 法阵预设
7. 通用 Renderer 起步值

---

## 1. 使用原则

这些 preset 不是最终答案，而是：
- 第一版骨架
- 稳定起手模板
- 团队统一做法的基础

不要直接把它们当成最终效果。

正确用法是：
1. 先用 preset 起一版
2. 再按案例库和艺术方向库细化
3. 再按平台和预算收敛

---

## 2. 命中特效预设

### 推荐 Emitter 结构

#### `Emitter_HitFlash`

作用：
- 主命中峰值

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

起步值：
- Burst Count: `1 - 4`
- Lifetime: `0.05 - 0.15`
- Size: `20 - 80`

#### `Emitter_HitRing`

作用：
- 外扩冲击环

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

起步值：
- Burst Count: `1`
- Lifetime: `0.08 - 0.25`
- Radius Growth: 快速扩张

#### `Emitter_HitDebris`

作用：
- 小量碎散粒子

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Scale Color`

起步值：
- Burst Count: `6 - 20`
- Lifetime: `0.1 - 0.5`
- Velocity: `150 - 700`

---

## 3. 火把预设

### 推荐 Emitter 结构

#### `Emitter_FlameCore`

作用：
- 主火焰形体

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Curl Noise Force`
6. `Scale Sprite Size`
7. `Scale Color`

起步值：
- Spawn Rate: `18 - 40`
- Lifetime: `0.35 - 0.8`
- Upward Velocity: `35 - 90`

#### `Emitter_FlameDetail`

作用：
- 边缘活性和小火舌

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Curl Noise Force`
5. `Scale Sprite Size`
6. `Color Over Life`

起步值：
- Spawn Rate: `10 - 24`
- Lifetime: `0.2 - 0.5`

#### `Emitter_Embers`

作用：
- 余烬

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Gravity Force`
5. `Drag`
6. `Scale Color`

起步值：
- Spawn Rate: `3 - 12`
- Lifetime: `0.6 - 1.8`

#### `Emitter_Smoke`

作用：
- 轻烟

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Scale Sprite Size`
6. `Scale Color`

起步值：
- Spawn Rate: `4 - 12`
- Lifetime: `1.2 - 3.0`

---

## 4. 护盾预设

### 推荐 Emitter 结构

#### `Emitter_ShieldShell`

作用：
- 主护盾壳层

Renderer：
- `Mesh Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Mesh Renderer`

起步值：
- Spawn Rate: `1`
- Lifetime: 持续

#### `Emitter_ShieldEnergy`

作用：
- 表面活性点缀

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Scale Color`

#### `Emitter_ShieldHit`

作用：
- 受击反馈

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

---

## 5. Slash / 拖尾预设

### 推荐 Emitter 结构

#### `Emitter_SlashMain`

作用：
- 主 Slash 弧线

Renderer：
- `Ribbon Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Scale Color`

#### `Emitter_SlashResidual`

作用：
- 残留小粒子

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Scale Color`

---

## 6. 法阵预设

### 推荐 Emitter 结构

#### `Emitter_SigilMain`

作用：
- 主法阵图案

Renderer：
- `Mesh Renderer` 或 Plane

#### `Emitter_SigilOuterRing`

作用：
- 外环

Renderer：
- `Mesh Renderer`

#### `Emitter_SigilUpward`

作用：
- 上升粒子

Renderer：
- `Sprite Renderer`

模块顺序建议：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Scale Color`

---

## 7. 通用 Renderer 起步值

### Sprite Renderer

适合：
- 命中
- 烟
- 火花
- 能量点

起步建议：
- Facing Mode: Camera Facing
- Sort: 根据层级控制

### Ribbon Renderer

适合：
- 拖尾
- 刀光
- 轨迹

起步建议：
- Spawn 要连续
- 宽度沿长度变化
- 材质要有头尾区分

### Mesh Renderer

适合：
- 护盾壳
- 法阵
- Portal

起步建议：
- 优先检查 UV
- 确保材质逻辑适合 Mesh 而不是强行套 Sprite 思路

---

## 一句话原则

Preset 的价值不在“最终长什么样”，而在：

让你从空白 Niagara 更快进入一个结构合理、后续可迭代的第一版。
