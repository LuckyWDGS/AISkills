# 纹理提示词框架

## 用途

这份文档用于把纹理生成提示词做成标准框架，而不是每次临时拼 prompt。

适合在这些场景读取：
- 需要为外部 AI 生成纹理写 prompt
- 需要判断某类纹理适不适合 AI 生成
- 需要统一纹理生成输入格式

---

## 目录

1. 先判断纹理类型
2. 哪些适合 AI 生成
3. 哪些不适合直接 AI 生成
4. 通用提示词结构
5. 单张图模板
6. Flipbook 模板
7. Atlas 模板
8. 无缝纹理模板
9. 分辨率、背景、alpha 规则

---

## 1. 先判断纹理类型

在写 prompt 之前，先判断目标属于哪类：

- 单张 alpha / mask
- Flipbook
- Atlas 图集
- 无缝平铺纹理
- 技术贴图

如果类型没判断清楚，prompt 再长也不稳。

---

## 2. 哪些适合 AI 生成

比较适合直接生成的：

- 烟雾 alpha
- 火焰 flipbook 草图
- ember atlas
- 法阵图案
- 护盾纹样
- stylized 噪声 / mask 草图

这些通常允许后续再人工修或二次处理。

---

## 3. 哪些不适合直接 AI 生成

不建议直接依赖通用生成式 AI 的：

- 真正可用的 Flow Map
- 真正可用的 Normal Map
- 精确通道打包图
- 技术精度要求很高的 mask

这类更适合：
- 程序化生成
- DCC / Substance / Houdini
- 从高质量结果烘焙

---

## 4. 通用提示词结构

推荐结构：

1. 资产用途
2. 纹理类型
3. 格式要求
4. 构图要求
5. 背景要求
6. 质量要求
7. 禁止项

### 基础模板

```text
[用途], [纹理类型], [帧数或网格],
[主体描述], [构图要求], [背景要求],
[alpha / contrast / silhouette 要求],
for game VFX, no text, no watermark, no border
```

---

## 5. 单张图模板

适合：
- 单张 alpha / mask
- 单个小火星
- 单个法阵主图

### 模板

```text
[asset purpose], single VFX sprite texture,
centered object, clear silhouette, high contrast,
black background, alpha-friendly edges,
for game VFX, no text, no watermark
```

### 示例：火舌纹理

```text
flame tongue alpha mask, single VFX sprite texture,
elongated upward flame shape, centered object,
high contrast, soft broken edges, black background,
for game VFX, no text, no watermark
```

---

## 6. Flipbook 模板

适合：
- 火焰
- 烟雾
- splash
- 爆炸云团

### 模板

```text
[asset purpose] flipbook, sprite sheet, [NxN] grid, [frame count] frames,
consistent camera angle, centered in every frame,
[motion description], [shape description],
high contrast, alpha-friendly silhouette, black background,
for game VFX texture atlas, no text, no watermark, no border
```

### 示例：烟雾 Flipbook

```text
thin torch smoke flipbook, sprite sheet, 8x8 grid, 64 frames,
consistent camera angle, centered in every frame,
soft upward smoke plume, natural expansion and dissipation,
light gray smoke, alpha-friendly soft edges, black background,
for game VFX texture atlas, no text, no watermark, no border
```

---

## 7. Atlas 模板

适合：
- ember / spark 变体
- 闪电分叉变体
- 小碎片 / decal 变体

### 模板

```text
[asset purpose] sprite atlas, [NxN] grid, [count] different variants,
consistent scale, centered per cell, high contrast,
black background, clean silhouettes,
for game VFX texture atlas, no text, no border, no watermark
```

### 示例：闪电 atlas

```text
lightning bolt sprite atlas, 4x4 grid, 16 different branching electric bolt shapes,
consistent scale, centered per cell, blue white arcs, high contrast,
black background, for game VFX texture atlas, no text, no border, no watermark
```

---

## 8. 无缝纹理模板

适合：
- 河流表面噪声
- 熔岩表皮
- 护盾表面噪声

### 模板

```text
seamless tileable [texture purpose],
high contrast, evenly distributed pattern,
no directional lighting, no text, no watermark,
for game VFX surface texture
```

### 示例：无缝噪声

```text
seamless tileable organic noise texture,
high contrast, soft fractal variation,
for game VFX mask, no text, no watermark
```

---

## 9. 分辨率、背景、alpha 规则

### 分辨率建议

- 单张小粒子：`256 - 512`
- Flipbook：`1024 - 2048` 视帧数决定
- Atlas：`512 - 1024`
- 无缝纹理：`512 - 1024`

### 背景建议

- 默认纯黑
- 或明确透明背景

### alpha 规则

- 主体必须居中
- 轮廓清楚
- 不要脏边
- 不要文字
- 不要边框
- 不要水印

### 一句话原则

好 prompt 的前提不是写得多，而是先把纹理类型和用途判断对。
