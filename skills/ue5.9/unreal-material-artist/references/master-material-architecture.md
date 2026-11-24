# 主材质架构指南

## 用途

这份文档用于定义 VFX 项目里的主材质体系应该怎么搭。

适合在这些场景读取：
- 项目刚开始，需要先定主材质
- 已有项目想把零散材质重构成体系
- 需要明确哪些 Master Material 必须统一

---

## 目录

1. 目标
2. 为什么需要主材质体系
3. 第一批必须统一的 Master Material
4. 参数暴露边界
5. Flipbook / Flow Map / Atlas 的统一支持
6. 材质实例策略
7. 常见错误

---

## 1. 目标

主材质体系的目标不是“做一个万能材质”，而是：

- 控制复杂度
- 降低重复劳动
- 提高一致性
- 提高可维护性

---

## 2. 为什么需要主材质体系

如果没有主材质体系，常见结果是：

- 每个效果一套独立 Master
- 参数命名混乱
- 同类效果材质做法完全不同
- 后期很难统一优化

所以主材质体系的核心价值是：
- 统一规则
- 限制随意生长

---

## 3. 第一批必须统一的 Master Material

建议新项目第一批至少统一这些：

### `M_FX_Additive_Core`

适合：
- 命中
- 核心能量层
- 小爆发

### `M_FX_Translucent_Smoke`

适合：
- 烟
- 雾
- 柔和体积假象

### `M_FX_Flipbook_Base`

适合：
- 火焰 Flipbook
- 烟雾 Flipbook
- Splash Flipbook

### `M_FX_Ribbon_Trail`

适合：
- 拖尾
- Slash
- 轨迹

### `M_FX_ShieldShell`

适合：
- 护盾壳
- 科技壳层

### `M_FX_Sigil_Main`

适合：
- 法阵
- Portal 平面图案

---

## 4. 参数暴露边界

主材质不要把所有内部值都暴露出去。

### 应该统一暴露的

- 主色
- 辅色 / 高光色
- 强度
- 透明度
- Noise 强度
- Flow 速度
- Flipbook 播放参数

### 不应该大量暴露的

- 每一个局部乘法值
- 每一个内部节点微调值
- 只给特效师自己调试的内部控制

### 原则

暴露给实例的是“常用控制”，不是“整个图”。

---

## 5. Flipbook / Flow Map / Atlas 的统一支持

### Flipbook

建议统一：
- `M_FX_Flipbook_Base`

支持：
- SubUV
- 可调播放速率
- 可调 Emissive / Opacity

### Flow Map

建议统一：
- `M_FX_SurfaceFlow_Base`

支持：
- Flow Map UV 扭曲
- Flow Strength
- Flow Speed
- Foam / Edge 补充

### Atlas

建议统一：
- `M_FX_Atlas_Base`

支持：
- 随机格子
- Atlas 采样
- 统一缩放与遮罩

---

## 6. 材质实例策略

### 推荐做法

- 主材质数量少
- 实例数量多

例如：
- `M_FX_Additive_Core`
  - `MI_FX_HitFlash_Default`
  - `MI_FX_EnergyOrb_Default`
  - `MI_FX_BeamCore_Default`

### 原则

不要一开始就复制 Master 改一份新的。

先问：
- 现有 Master 能不能覆盖

如果只是差颜色、强度、噪声、播放速率，优先实例化。

---

## 7. 常见错误

### 错误 1：万能总材质

问题：
- 过重
- 过乱
- 不可维护

### 错误 2：每个效果一个 Master

问题：
- 后期无法统一优化
- 风格和参数体系容易漂

### 错误 3：参数暴露过多

问题：
- 实例层变复杂
- 蓝图 / 用户层难控制

---

## 一句话原则

主材质架构的关键不是“做一个什么都能干的材质”，而是建立一小组边界清楚、职责明确、实例友好的基础材质。
