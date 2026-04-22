# 特效案例库

## 用途

这份文档用于把前面已经沉淀下来的能力真正串成“完整方案模板”。

适合在这些场景读取：
- 用户直接要一个完整可用方案
- 需要把参考、选型、材质、Niagara、纹理、低配版串起来
- 需要给出更像 production-ready 的实现路径

这份文档不是知识点合集，而是案例模板库。

---

## 目录

1. 真实火把
2. 护盾
3. 命中特效
4. 法阵
5. 河流表面
6. 瀑布
7. 水花喷溅

---

## 1. 真实火把

### 目标

- 持续燃烧
- 偏真实
- 场景常驻
- 不要像技能爆炸

### 先做判断

这个效果的关键不是“瞬时爆发”，而是：
- 火焰的持续翻卷
- 轻烟的持续上升
- 少量 ember 提升活性

技术路线：
- 火焰主体：`2D Gas` 或 `Fluids -> Flipbook`
- 烟雾：`Flipbook / 2D Gas 烘焙`
- 余烬：单张小纹理或随机图集

### 推荐结构

#### 主层
- `Emitter_FlameCore`
- `Emitter_FlameDetail`

#### 次层
- `Emitter_Embers`

#### 残留层
- `Emitter_Smoke`

### 材质与纹理

- FlameCore：
  - 需要纹理
  - 推荐 `Flipbook`
- FlameDetail：
  - 建议单张火舌纹理或小型图集
- Embers：
  - 小单图或 4x4 atlas
- Smoke：
  - 推荐 `Flipbook`
  - 但作为“单粒子生命周期动画”使用，不直接无限循环同一粒子

### Niagara 路线

1. 先做 FlameCore
2. 再做 Smoke
3. 再补 Embers
4. 最后补 FlameDetail

### 逐步搭建手册

#### 第 1 步：先确定资产清单

最小可用版先准备：
- `T_FX_TorchFlame_Flipbook`
- `T_FX_TorchSmoke_Flipbook`
- `T_FX_TorchEmber_Atlas`
- `M_FX_TorchFlame_Core`
- `M_FX_TorchSmoke`
- `M_FX_TorchEmber`
- `NS_Torch_Fire`

#### 第 2 步：先做 FlameCore 材质

目标：
- 不考虑别的层，先让火焰本体成立

做法：
- Sprite 材质
- 接入火焰 Flipbook
- 调整 Additive 强度
- 保证中心更亮、边缘更破

验收：
- 单独看这层就像火，不像橙色烟

#### 第 3 步：创建 `Emitter_FlameCore`

模块顺序：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Curl Noise Force`
6. `Scale Sprite Size`
7. `Scale Color`
8. Sprite Renderer + SubUV

第一版目标：
- 持续上升
- 轮廓成立
- 有轻微翻卷

#### 第 4 步：创建 `Emitter_Smoke`

重点：
- 烟雾不要直接循环同一个 plume 粒子
- 用持续 Spawn 的方式，让每个粒子播自己的 flipbook 生命周期

模块顺序：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Scale Sprite Size`
6. `Scale Color`
7. Sprite Renderer + SubUV

验收：
- 轻烟上升
- 不糊屏
- 不像爆炸烟

#### 第 5 步：创建 `Emitter_Embers`

目标：
- 少量点缀，不抢主体

模块顺序：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Gravity Force`
5. `Drag`
6. `Scale Color`

验收：
- 余烬数量克制
- 增强活性但不变技能特效

#### 第 6 步：最后补 `Emitter_FlameDetail`

目标：
- 让边缘更活

做法：
- 单张火舌纹理或小型图集
- 用更快的上升和更短寿命补边缘变化

验收：
- 有提升质感
- 但删掉这层时主效果仍成立

### 低配版

- FlameDetail 可删
- Smoke 数量减半
- Embers 数量明显减少

### 风险点

- 火像橙色烟
- 烟太厚糊屏
- 亮度过爆

---

## 2. 护盾

### 目标

- 防御感强
- 轮廓明确
- 常驻克制
- 受击反馈清楚

### 先做判断

这是典型的：
- Mesh / Surface 驱动主层
- Niagara 粒子做活性和反馈

技术路线：
- 主体壳层：材质 + Mesh
- 次级流动：粒子 / 材质流动
- 受击反馈：Sprite / 冲击环

### 推荐结构

#### 主层
- 护盾壳层

#### 次层
- 表面能量点或线性流动

#### 反馈层
- 命中涟漪
- 局部冲击环

### 材质

- 主材质：
  - `Additive` 或 `Translucent`
  - `Fresnel`
  - `T_Noise`
  - `S_FlowSpeed`

### Niagara 路线

1. 先做壳层材质
2. 再补活性点缀
3. 最后单独做 Hit Feedback

### 逐步搭建手册

#### 第 1 步：先做壳层材质

最小资产：
- `M_FX_ShieldShell`
- `MI_FX_ShieldShell_Default`
- `NS_Shield_Main`

材质目标：
- 边缘有 Fresnel
- 壳层轻度流动
- 常驻状态不要过亮

验收：
- 单看材质就有防御感
- 不像纯塑料球壳

#### 第 2 步：创建 `Emitter_ShieldShell`

Renderer：
- `Mesh Renderer`

模块：
1. `Spawn Rate`
2. `Initialize Particle`
3. Mesh Renderer

目标：
- 让主壳层稳定存在

#### 第 3 步：创建 `Emitter_ShieldEnergy`

作用：
- 补表面活性

Renderer：
- `Sprite Renderer`

模块：
1. `Spawn Rate`
2. `Initialize Particle`
3. `Add Velocity`
4. `Scale Color`

验收：
- 表面更有生命力
- 但不杂乱

#### 第 4 步：创建 `Emitter_ShieldHit`

作用：
- 命中反馈

模块：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

验收：
- 被打时有明显提升
- 常驻状态和受击状态区分清楚

### 低配版

- 主壳层保留
- 表面点缀层减少
- 受击只保留一个主涟漪

### 风险点

- 太厚挡角色
- 表面太杂
- 常驻状态太抢戏

---

## 3. 命中特效

### 目标

- 短促
- 清晰
- 有打到感

### 先做判断

这是典型非流体类短促反馈。

技术路线：
- `Sprite + 小量粒子`
- 通常不需要 Fluids
- 通常不需要复杂材质体系

### 推荐结构

#### 主层
- 闪光

#### 次层
- 冲击环

#### 辅助层
- 少量碎散粒子

### Niagara 路线

1. 先做命中闪光
2. 再做冲击环
3. 最后补少量碎散粒子

### 逐步搭建手册

#### 第 1 步：先做 `Emitter_HitFlash`

目标：
- 先把命中的“峰值”做出来

模块：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

验收：
- 单看这一层，已经像“打到了”

#### 第 2 步：再做 `Emitter_HitRing`

目标：
- 补方向感和冲击感

模块：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Scale Sprite Size`
4. `Scale Color`

验收：
- 命中位置更清楚

#### 第 3 步：最后做 `Emitter_HitDebris`

目标：
- 只补少量碎散

模块：
1. `Spawn Burst Instantaneous`
2. `Initialize Particle`
3. `Add Velocity`
4. `Drag`
5. `Scale Color`

验收：
- 增加打击感
- 但不是主角

### 低配版

- 保留闪光和冲击环
- 可删碎散粒子

### 风险点

- 时长太长
- 太弱没有打击感
- 太亮反而看不清

---

## 4. 法阵

### 目标

- 仪式感
- 图案感
- 激活感

### 先做判断

法阵通常是：
- Plane / Mesh 主体
- 材质图案主导
- Niagara 做上升粒子和点缀

技术路线：
- 主层：材质
- 次层：粒子
- 旋转 / 呼吸：材质和少量系统节奏

### 推荐结构

#### 主层
- 法阵主图案

#### 次层
- 外环旋转层

#### 空间层
- 上升粒子

### 材质

- 主图案纹理
- 外环高光
- 轻度流动或脉冲

### 低配版

- 保留主图案
- 外环与粒子减法

### 风险点

- 像贴图
- 图案过密
- 太亮压角色

---

## 5. 河流表面

### 目标

- 清晰流向
- 长时间稳定
- 成本可控

### 先做判断

这是典型表面流动，不应默认走完整流体模拟。

技术路线：
- `Flow Map + Material`

### 推荐结构

#### 主层
- 河面 Mesh
- Flow Map
- Normal / Foam

#### 辅助层
- 局部白沫
- 岸边浪花

### 什么时候升级

如果有：
- 船尾波
- 脚踩互动
- 表面波高变化

再考虑 `Shallow Water`

### 低配版

- 减少采样
- 减少 foam 层

### 风险点

- 看起来像贴图滑动
- 流向不清楚
- 细节太均匀

---

## 6. 瀑布

### 目标

- 主体有持续下落感
- 底部有白水和 mist
- 近看不太假

### 先做判断

瀑布主体通常不该整条实时 FLIP。

技术路线：
- 主体：`Mesh + Flow Map`
- 次级：`Niagara + splash / mist flipbook`

### 推荐结构

#### 主层
- 瀑布网格流动材质

#### 次层
- 底部 mist
- splash

#### 辅层
- 周围轻雾

### 什么时候升级

只有极近景英雄镜头，才考虑更重的液体模拟

### 低配版

- 主体材质保留
- mist 和 splash 数量减半

### 风险点

- 主体像蓝色布条
- 白水不够
- 下方冲击不成立

---

## 7. 水花喷溅

### 目标

- 冲击感
- 形体清楚
- 层级分明

### 先做判断

喷溅最成熟的默认路线通常不是实时体积液体，而是：
- `Flipbook + Niagara`

### 推荐结构

#### 主层
- splash flipbook

#### 次层
- 水滴粒子

#### 辅层
- 少量 mist

### 什么时候升级

如果是英雄镜头或近景大 splash：
- 可先用 `2D FLIP`
- 再烘焙

### 低配版

- 保留 splash 主层
- 水滴和 mist 都减量

### 风险点

- 像一团湿雾
- 不成形
- 层太多太乱

---

## 一句话原则

案例库的价值不在“给你一个唯一答案”，而在：

当需求一来，能快速把它归类到一条成熟路线，然后输出一套稳定、可落地的生产方案。
