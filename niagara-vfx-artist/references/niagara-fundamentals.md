# Niagara 基础逻辑与分析方法

## 用途

这份文档用于补齐 Niagara 的基础逻辑、核心概念和实战分析框架。

适合在这些场景读取：
- 用户想知道 Niagara 的基本工作原理
- 用户上传参考图、设计图，想反推怎么做
- 用户想知道一个效果为什么需要 1 个、3 个或 5 个发射器
- 需要把“艺术描述”转成“Niagara 结构”

这份文档主要基于 Epic 官方 Niagara 文档整理。

---

## 目录

1. Niagara 是什么
2. 四个核心组成
3. Niagara 的基本执行逻辑
4. 数据、参数和命名空间
5. Renderer 和显示层
6. 怎么从参考图反推 Niagara
7. 怎么判断需要多少个 Emitter
8. 我拿到参考图后会怎么给方案
9. 官方参考

---

## 1. Niagara 是什么

Niagara 是 Unreal Engine 的新一代实时特效系统。

从理解上，你可以把它看成：

- **System**：一个完整特效
- **Emitter**：这个特效里的一个功能层
- **Module**：定义这一层如何生成、更新、运动、渲染
- **Parameter**：驱动所有行为和表现的数据

Niagara 的强项不是只有“做粒子”，而是它把：

- 模块化堆栈
- 节点图逻辑
- 参数驱动
- 多层级数据传递

放进了同一套系统里。

---

## 2. 四个核心组成

根据 Epic 官方 Overview / Key Concepts，Niagara 最核心的四个部分是：

### System

System 是整个特效的总容器。

一个 System 里可以有多个 Emitter，共同组合成一个完整效果。

例如一个爆炸 System，可能包含：
- 核心火球
- 冲击环
- 火星
- 烟雾

这些可以是 4 个不同的 Emitter。

### Emitter

Emitter 是一个单一职责的效果层。

一个 Emitter 最好只负责一类事情，例如：
- 只负责喷火星
- 只负责主烟雾
- 只负责拖尾
- 只负责命中闪光

这样结构更清晰，也更容易复用。

### Module

Module 决定“这一层怎么运行”。

它们通常会分布在不同的阶段中，例如：
- Spawn：生成时做什么
- Update：每帧更新时做什么
- Event：事件发生时做什么
- Render：最后怎么显示

常见模块职责包括：
- 生成数量
- 生命周期
- 速度
- 力场
- 尺寸曲线
- 颜色曲线
- 朝向

### Parameter

Parameter 是 Niagara 里最关键的数据驱动层。

它控制：
- 数值
- 颜色
- 纹理
- 开关
- 用户输入

也就是说，Niagara 并不是“把行为写死”，而是大量依赖参数去控制行为。

---

## 3. Niagara 的基本执行逻辑

Niagara 的一个重要理解点是：

**它本质上是按堆栈顺序执行模块的。**

可以把它理解成：

1. 先决定 System 层要做什么
2. 再决定 Emitter 层要做什么
3. 再决定粒子生成时要做什么
4. 再决定粒子更新时要做什么
5. 最后决定怎么渲染出来

### 常见阶段理解

#### System Spawn / System Update

处理整个 System 级别的逻辑。

适合做：
- 整体生命周期
- 系统级参数
- 对所有发射器都有效的控制

#### Emitter Spawn / Emitter Update

处理某个 Emitter 自己的逻辑。

适合做：
- 发射器自己的年龄、循环、启停
- 某个层的专属控制

#### Particle Spawn

粒子出生那一刻执行。

适合做：
- 初始位置
- 初始速度
- 初始颜色
- 初始尺寸

#### Particle Update

粒子活着的每一帧都执行。

适合做：
- 速度变化
- Drag / Gravity
- Noise
- Alpha / Size / Color 随时间变化

### 高级阶段

官方还提到：
- Event Handler
- Simulation Stages

这类更适合：
- 事件驱动
- 高级 GPU 流程
- 流体或复杂仿真

对大多数常规游戏技能特效来说，最常用还是：
- Spawn
- Update
- Render

---

## 4. 数据、参数和命名空间

Niagara 很专业的一个核心点，是它的数据不是乱流的，而是分层命名空间管理的。

官方 Key Concepts 强调了：

- System 组读写 System 数据
- Emitter 组读写 Emitter 数据
- Particle 组读写 Particle 数据

简单理解就是：

### System 层

适合放：
- 全局控制
- 整个特效统一参数

### Emitter 层

适合放：
- 某个效果层自己的控制

### Particle 层

适合放：
- 单个粒子的 Position / Velocity / Size / Color 等

这个结构很重要，因为它决定了：

- 哪些数据应该放在 System
- 哪些数据应该放在 Emitter
- 哪些数据必须在 Particle 里更新

也决定了你后面做参数设计时，不会把所有东西都堆在一层里。

---

## 5. Renderer 和显示层

Niagara 不只是“算粒子”，还要决定怎么把它显示出来。

官方 Module Reference 里把 Render group 单独列出来，意思是：

**模拟是一回事，显示又是另一回事。**

常见 Renderer 理解：

### Sprite Renderer

最常见，适合：
- 烟雾
- 火花
- 能量点
- 爆炸片层

### Ribbon Renderer

适合：
- 拖尾
- 刀光
- 飞弹轨迹
- 流线型能量

### Mesh Renderer

适合：
- 护盾壳
- 几何法阵
- 特定 3D 形体层

### Light Renderer

适合：
- 爆发瞬间补光
- 高亮粒子带出局部光感

所以一个专业分析不能只说“用 Niagara 做”，而要说：

- 这一层用哪个 Renderer
- 为什么要用它
- 是否需要单独材质

---

## 6. 怎么从参考图反推 Niagara

如果你上传一张图片、设计图，最专业的拆法不是直接猜模块，而是先做分层。

### 我会先做这几步

#### 1. 识别视觉层

看这张图里是不是至少有这些层：
- 主体核心层
- 边缘轮廓层
- 次级粒子层
- 烟雾 / 余辉 / 残留层
- 地面 / 冲击 / 反馈层

#### 2. 判断每层的显示方式

我会判断每层更像：
- Sprite
- Ribbon
- Mesh
- Light

#### 3. 判断每层是材质主导还是 Niagara 主导

有些层主要靠材质成立，例如：
- 护盾壳
- 法阵图案
- 能量球外壳

有些层主要靠 Niagara 运动成立，例如：
- 火星
- 烟雾
- 碎散粒子

#### 4. 判断哪些层应该独立成 Emitter

如果某一层满足下面任意一种情况，通常就值得独立成一个 Emitter：
- 生命周期不同
- Renderer 不同
- 运动逻辑不同
- 材质类型不同
- 是否需要单独启停

---

## 7. 怎么判断需要多少个 Emitter

Emitter 数量不是固定答案，而是由“视觉层是否独立”决定。

### 经验判断法

#### 1 个 Emitter

适合：
- 非常简单的小火花
- 低配移动端的基础效果
- 单一视觉目的的小提示

#### 2 - 3 个 Emitter

适合：
- 中小型技能特效
- 命中特效
- 小型护盾
- 简单拖尾 + 残留

常见分法：
- 主层
- 辅助层
- 残留 / 反馈层

#### 4 - 6 个 Emitter

适合：
- 爆炸
- 大招命中
- 复杂护盾
- 法阵

常见分法：
- 主体层
- 冲击层
- 次级粒子
- 烟雾 / 残留
- 反馈层

#### 6 个以上

只有在这些情况下才值得：
- 明确的大型特效
- 多阶段 Boss 技能
- 电影感 / 宣传级表现
- PC / 高配平台专用方案

否则通常要警惕是不是拆太碎了。

### 一个专业原则

**Emitter 数量不是越多越专业，而是职责越清晰越专业。**

---

## 8. 我拿到参考图后会怎么给方案

如果你上传图片或设计图，我可以直接给你这种级别的分析：

### 我能输出的内容

1. 视觉拆层
   这个效果有几层，每层是什么作用

2. 材质建议
   每层需要什么材质
   是 Additive / Translucent / Masked
   是否需要 Fresnel / Noise / Panner / Flow

3. Niagara 结构
   这个 System 建议几个 Emitter
   每个 Emitter 负责什么

4. Emitter 级建议
   每个 Emitter 用什么 Renderer
   生命周期、生成方式、更新逻辑大概怎么设

5. 平台分版本
   PC 版怎么做
   Android 版怎么减法

### 我最适合分析的输入

- 单张参考图
- 概念设计图
- UI 标注稿
- 多张关键帧截图

### 关于视频

我可以帮你分析视频风格和实现思路，但最稳定的方式还是：

- 你给关键帧截图
- 或者给一组分镜帧

这样我能更准确地拆出：
- 分层
- 时序
- 关键峰值
- Emitter 分工

---

## 9. 官方参考

以下是这份基础逻辑整理时参考的 Epic 官方文档：

- [Overview of Niagara Effects for Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-niagara-effects-for-unreal-engine)
- [Key Concepts in Niagara Effects for Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/key-concepts-in-niagara-effects-for-unreal-engine)
- [System and Emitter Module Reference for Niagara Effects in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/system-and-emitter-module-reference-for-niagara-effects-in-unreal-engine)
- [How to Create a GPU Sprite Effect in Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-gpu-sprite-effect-in-niagara-for-unreal-engine)
- [How to Create a Smoke Effect Using Sprite Particles in Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-smoke-effect-using-sprite-particles-in-niagara-for-unreal-engine)
- [How to Create a Ribbon Effect in Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-ribbon-effect-in-niagara-for-unreal-engine)
- [How to Create Particle Effects That Emit Light in Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-particle-effects-that-emit-light-in-niagara-for-unreal-engine)
