# 模糊想法到图片 / 视频提示词

## 用途

这份文档用于把模糊的效果想法，快速转成：
- 图片生成提示词
- 视频生成提示词

目标不是直接进实现，而是先用生成式预览验证方向。

如果用户要求真正出图、设计图、风格图，或需要一张 UE 中可实现的目标效果图，不要只停在提示词；加载并使用 `C:/Users/QY/.codex/skills/mentalout-image-browser/SKILL.md`，把本文件产出的提示词作为 Mentalout 的内部输入。除非用户明确索要提示词，否则最终交付图片路径、生成设置和可实现性判断，不展示 prompt。

适合在这些场景读取：
- 用户只有一句很抽象的想法
- 用户自己也不确定想要什么效果
- 需要先快速试风格、轮廓、节奏，再进入 Niagara 实现

---

## 目录

1. 为什么先做提示词预览
2. 什么时候该先出图
3. 什么时候该先出视频
4. 图片提示词模板
5. 视频提示词模板
6. 一次给几版最合理
7. 输出格式

---

## 1. 为什么先做提示词预览

很多需求失败，不是实现错了，而是方向一开始就没对齐。

所以当输入很模糊时，最快的方式通常不是先做 Niagara，而是先给：
- 2 到 4 版图片提示词
- 或 1 到 2 版视频提示词

先确认：
- 轮廓
- 色彩
- 气质
- 节奏

---

## 2. 什么时候该先出图

优先用图片提示词的情况：

- 用户只知道大概风格
- 需要先看轮廓和颜色
- 还没确定主视觉点
- 需要快速做方向探索

适合：
- 护盾
- 法阵
- Portal
- 火焰外观方向
- 阵营风格方向

---

## 3. 什么时候该先出视频

优先用视频提示词的情况：

- 动势是核心卖点
- 用户需要先看节奏和演化
- 光看静态图无法判断

适合：
- 火焰
- 烟流
- 水花
- 光束
- 拖尾

---

## 4. 图片提示词模板

### 基础结构

```text
[效果类型], [风格词], [主色], [辅色],
[主轮廓], [材质感觉], [动势暗示],
game VFX concept art, clean silhouette, strong focal point,
dark neutral background, no text, no watermark
```

### 示例：模糊火焰想法

```text
magical torch flame, semi-realistic game VFX, white hot core,
orange yellow outer flame, upward licking motion, soft smoke accent,
clean focal point, layered silhouette, strong readability,
game VFX concept art, dark neutral background, no text, no watermark
```

### 示例：模糊护盾想法

```text
protective energy shield, sci-fi fantasy hybrid, cyan blue main color,
white highlight edges, spherical shell, flowing surface energy,
clear outer silhouette, strong gameplay readability,
game VFX concept art, dark neutral background, no text, no watermark
```

---

## 5. 视频提示词模板

### 基础结构

```text
[效果类型], [风格词], [颜色], [起势],
[峰值描述], [消散描述], [镜头稳定要求],
short game VFX preview, centered composition, readable silhouette,
dark neutral background, no text, no watermark
```

### 示例：火焰视频提示词

```text
realistic torch flame game VFX preview, white hot core and orange outer flame,
gentle continuous upward licking motion, subtle smoke rising,
stable centered composition, readable layered silhouette,
short game VFX preview, dark neutral background, no text, no watermark
```

### 示例：命中特效视频提示词

```text
impact hit VFX preview, bright flash core, fast expanding ring,
small debris burst, very short peak and clean fade out,
stable centered composition, readable silhouette,
short game VFX preview, dark neutral background, no text, no watermark
```

---

## 6. 一次给几版最合理

推荐默认：

- 图片：`2 - 4` 版
- 视频：`1 - 2` 版

理由：
- 太少不够比较
- 太多会失焦

推荐策略：
- 1 版偏保守
- 1 版偏更强烈
- 1 版偏更风格化
- 1 版偏更写实

---

## 7. 输出格式

当用户给出模糊想法时，推荐这样输出：

### 我理解的方向

- [...]

### 图片提示词版本 A

```text
...
```

### 图片提示词版本 B

```text
...
```

### 如果需要动态验证，再补视频提示词

```text
...
```

### 一句话原则

先用生成式预览确认方向，再进入实现；不要在风格还没对齐时直接做 Niagara。
