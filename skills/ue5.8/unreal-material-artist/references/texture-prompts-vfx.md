# UE VFX 纹理 AI 提示词

## 用途

读取这份 reference 当任务需要火焰、余烬、烟雾、闪电等 VFX 纹理 prompt，或者需要把这些 prompt 接回 UE/Niagara。实际生成仍默认使用 cm-imagegen 并接受后续 QA。

## 目录

- [火焰纹理 AI 提示词](#5-火焰纹理-ai-提示词)
- [余烬 / 火星纹理 AI 提示词](#6-余烬--火星纹理-ai-提示词)
- [烟雾纹理 AI 提示词](#7-烟雾纹理-ai-提示词)
- [闪电图集与随机格子](#8-闪电图集与随机格子)

---
## 5. 火焰纹理 AI 提示词

### 火焰主体 Flipbook

提示词模板：

```text
realistic torch flame flipbook, sprite sheet, 8x8 grid, 64 frames,
consistent camera angle, centered flame, upward licking motion,
white hot core, yellow orange outer flame, clean alpha-friendly silhouette,
high contrast, black background, no text, no border, no watermark,
for game VFX texture atlas, each frame evenly aligned
```

负面提示词：

```text
smoke-heavy, explosion, sideways fire, text, watermark, frame mismatch,
inconsistent camera, cropped flame, blurry, noisy background
```

### 火焰细节层静态纹理

提示词模板：

```text
grayscale flame tongue alpha mask, elongated upward flame shape,
clean silhouette, soft broken edges, high contrast, black background,
single VFX sprite, no text, no watermark
```

---

## 6. 余烬 / 火星纹理 AI 提示词

### 单张余烬纹理

提示词模板：

```text
small ember particle alpha mask, glowing irregular spark shape,
high contrast, black background, tiny VFX sprite, clean silhouette,
single particle texture, no text, no watermark
```

### 4x4 余烬随机图集

提示词模板：

```text
ember particle sprite atlas, 4x4 grid, 16 different irregular glowing ember shapes,
small spark fragments, consistent scale, centered in each cell,
high contrast on black background, for game VFX, no text, no border, no watermark
```

---

## 7. 烟雾纹理 AI 提示词

### 烟雾 Flipbook

提示词模板：

```text
realistic smoke flipbook, sprite sheet, 8x8 grid, 64 frames,
soft volumetric smoke puff, natural expansion and dissipation,
centered in each frame, high contrast alpha-friendly edges,
black background, no text, no watermark, for game VFX subUV animation
```

负面提示词：

```text
fire, explosion core, hard edges, heavy lighting, text, border,
inconsistent frame scale, shifting camera, cropped plume
```

### 原型期单张烟雾图

提示词模板：

```text
soft smoke alpha mask, organic cloud shape, realistic soft edge,
high contrast, black background, VFX sprite texture, no text, no watermark
```

---

## 8. 闪电图集与随机格子

这是一种非常典型、非常合理的 Niagara 用法。

### 推荐做法

- 做一张 4x4 或 8x8 的闪电分叉图集
- 每个格子里都是不同形态的电弧
- 粒子 Spawn 时随机选一个格子

更适合：
- **随机变体图集**
- 而不是长时序 Flipbook

### 闪电图集 AI 提示词

```text
lightning bolt sprite atlas, 4x4 grid, 16 different branching electric bolt shapes,
blue white energy arcs, centered per cell, high contrast, black background,
for game VFX texture atlas, no text, no watermark, no border
```

### Niagara 接法

- Sprite Renderer:
  - `Sub Image Size = 4x4`
- Spawn:
  - 给 `SubImageIndex` 随机整数

---

