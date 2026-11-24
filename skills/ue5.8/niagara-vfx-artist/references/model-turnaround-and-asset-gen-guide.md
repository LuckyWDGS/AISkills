# 模型多视图与资产生成指南

## 用途

这份文档用于规范：什么时候该做模型、什么时候不该优先做模型，以及如果要用生成式模型辅助建模，应该怎么准备多视图输入。

适合在这些场景读取：
- 需要判断某个 VFX 资产是否适合建模
- 需要为生成式资产工具准备多视图输入
- 需要统一模型参考图标准

---

## 目录

1. 什么资产适合建模
2. 什么不该优先做模型
3. 多视图标准
4. 视角要求
5. 背景、光照、比例、尺度要求
6. 多视图 prompt 模板
7. 资产生成原则

---

## 1. 什么资产适合建模

适合优先建模的：

- 火把底座 / 支架
- 护盾发生器
- Portal 框体
- 法阵承载物
- 科技装置
- 场景特效载体
- Slash 几何片（在特定风格里）

判断标准：
- 主视觉轮廓靠几何承载
- 需要稳定体积和明确边界
- Sprite 很难稳定表达

---

## 2. 什么不该优先做模型

不建议一开始就做模型的：

- 烟雾主体
- 火焰主体
- 大爆炸体积
- 大部分纯能量外发层
- 大部分小 sparks / debris

这些通常更适合：
- 贴图
- Flipbook
- Niagara 粒子
- 材质假象

---

## 3. 多视图标准

如果要生成模型参考，多视图至少应包含：

- Front
- Left
- Right
- Back
- Top
- Bottom
- Front 3/4
- Back 3/4

### 统一要求

- 同一比例
- 同一中心点
- 同一尺度基准
- 各视图不能长得像不同物体

---

## 4. 视角要求

### 优先使用

- 正交视角
- 极轻透视或无透视

### 避免

- 强透视
- 夸张镜头
- 每张图机位不一致

### 原则

多视图的目标不是“好看”，而是“可重建”。

---

## 5. 背景、光照、比例、尺度要求

### 背景

- 纯灰
- 纯白
- 纯黑

不要复杂背景。

### 光照

- 中性光照
- 阴影克制
- 不要戏剧化打光

### 比例

- 全视图一致
- 不同角度尺寸保持稳定

### 尺度

- 最好有明确基准
- 或在 prompt 中说明 asset 是：
  - small prop
  - handheld prop
  - large environment device

---

## 6. 多视图 prompt 模板

### 通用模板

```text
orthographic turnaround sheet, same object shown in multiple views,
front view, left view, right view, back view, top view, bottom view,
front 3/4 view, back 3/4 view,
consistent proportions, centered object, neutral lighting,
plain background, no perspective distortion, no text, no watermark
```

### 示例：火把支架

```text
medieval torch holder prop, forged iron and dark wood,
orthographic turnaround sheet, front left right back top bottom and 3/4 views,
consistent proportions, centered object, neutral studio lighting,
plain gray background, no perspective distortion, no text, no watermark
```

### 示例：科技传送门框体

```text
sci-fi portal frame prop, clean geometric structure, blue cyan tech design,
orthographic turnaround sheet, front left right back top bottom and 3/4 views,
consistent proportions, centered object, neutral lighting,
plain background, no text, no watermark, no perspective distortion
```

---

## 7. 资产生成原则

### 先判断是不是该建模

不要因为能生成模型，就默认该做模型。

### 多视图服务重建，不服务海报感

如果参考图很帅但不一致，就不适合当多视图输入。

### 一条最重要的原则

如果一个效果的关键价值来自：
- 烟
- 火
- 体积
- 半透明

先别建模，优先想贴图 / Flipbook / 材质 / Niagara。
