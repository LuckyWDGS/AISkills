# UE 材质纹理策略、Flipbook、图集与 AI 提示词

## 用途

这份文档用于回答这些实战问题：

- 某个效果层到底要不要纹理图
- 要用单张图、Flipbook，还是图集随机格子
- 哪些纹理适合外部 AI 生成
- 给外部 AI 生成纹理时，提示词该怎么写
- UE 材质和 Niagara Renderer 里怎么正确接入这些纹理

当需要实际出图时，默认加载并使用 `C:/Users/QY/.codex/skills/cm-imagegen/SKILL.md`。本文件负责决定纹理策略和 prompt 内容，cm-imagegen 负责生成与迭代图片。如果已有设计图、参考图、已批准概念图或上一张选定输出，必须先缓存到本地，再把它作为 reference image 传入 cm-imagegen，用来锁定风格、结构、色彩和材质语言。对明显属于 Ribbon、Mesh Afterimage、Skeletal Mask 的层，先确认材质承载方式和运行时载体，再决定最终纹理长什么样。除非用户明确索要提示词，否则最终只交付图片结果、保存路径、设置和 UE 接入建议。

如果用户说的是“定制材质”、提供参考图、或明确要求匹配某个视觉风格，参考图优先级高于资产库复用。资产库搜索仍然要做，但搜索结果只是候选；只有当它同时匹配参考图的风格、尺度、图案语言、颜色/明度、运动意图和技术用途时，才能作为最终贴图复用。否则最多作为不主导外观的辅助噪声/扰动/遮罩，或者直接拒用并走 cm-imagegen 参考图生成。

---

## 目录

1. 三种常见纹理方案
2. 什么时候该用哪一种
3. UE / Niagara 接入方式
4. 真实火把的纹理决策
5. 火焰纹理 AI 提示词
6. 余烬 / 火星纹理 AI 提示词
7. 烟雾纹理 AI 提示词
8. 闪电图集与随机格子
9. 叶片 diffuse/alpha 与叶片卡
10. 定制水材质的参考图优先规则
11. 生成纹理时的硬规则

---

## 1. 三种常见纹理方案

### A. 单张静态纹理

适合：
- 小火星
- 小余烬
- 简单噪声
- 单个遮罩
- 小型拖尾图形

优点：
- 最轻
- 最容易生成
- 最容易调

缺点：
- 动画感弱
- 真实感有限

### B. Flipbook / SubUV 动画纹理

适合：
- 火焰主体
- 烟雾
- 爆炸云团
- 流体感更强的层

Epic 官方烟雾 Niagara 教程直接使用 `M_smoke_subUV`，并在 Sprite Renderer 里设置 `Sub Image Size`，再用 `SubUV Animation` 模块播放整张 8x8 图集中的 64 帧。

Epic 官方 Flipbook Baker 文档也说明：
- 可以从 Niagara 系统生成 flipbook
- 在 Sprite Renderer 中设置 `Sub Image Size`
- 用 `SubUV Animation` 设定开始帧和结束帧

优点：
- 动感最好
- 真实感最好
- 特别适合火焰、烟雾这类体积错觉

缺点：
- 贴图制作更难
- 更占纹理和内存

### C. 图集随机格子 / Atlas Variants

适合：
- 火星
- 闪电枝状变化
- 碎片形状变化
- 少量不规则图形变体

不是“按时间顺序播放”，而是：
- 一张图里切成多个格子
- 每次粒子出生随机选其中一格

Niagara Sprite Renderer 支持：
- `Sub Image Size`
- `SubImageIndex`
- `Sub UV Blending`

优点：
- 比单张图更丰富
- 比完整 flipbook 更便宜

缺点：
- 不适合长动画
- 更适合“随机变化”，不适合“连续演化”

---

## 2. 什么时候该用哪一种

### 火焰主体

推荐：
- **优先 Flipbook**

原因：
- 火焰最重要的是边缘翻卷、内部流动、向上舔舐感
- 单张图很容易做成“橙色烟”
- Flipbook 更容易有真实的生命力

### 火焰细节层

推荐：
- **不一定要 Flipbook**
- 优先考虑静态火焰遮罩 + 噪声流动
- 或小型 2x2 / 4x4 变体图集

原因：
- 细节层更多是补边缘活性
- 不一定需要完整动画
- 用 Panner + Noise 往往已经足够

### 余烬 / 火星

推荐：
- **通常不需要完整 Flipbook**
- 单张火星纹理或小型随机图集更合适

原因：
- 余烬的重点是数量、亮度、轨迹，不是复杂体积动画
- 很多时候一个小圆点、尖点、破碎火星图就够

### 烟雾

推荐：
- **优先 Flipbook / SubUV**

原因：
- 烟雾最怕静态图假
- Epic 官方烟雾教程就是用 `M_smoke_subUV`
- 烟的边缘形态和体积变化非常依赖动画帧

如果预算不够：
- 可以退化成单张烟雾 Mask
- 但真实感会明显下降

### 闪电

推荐：
- **随机格子图集**
- 或短动画 flipbook + 随机起始格

原因：
- 闪电不是柔和连续演化
- 更像多种不同枝状形态的快速跳变
- 用一张 4x4 或 8x8 不同闪电分叉图集，随机选格子，非常合适

---

## 3. UE / Niagara 接入方式

### Flipbook / SubUV 动画

典型接法：

1. Sprite Renderer 设置：
- Material
- `Sub Image Size`，例如 8x8
- `Sub UV Blending`

2. 在 Spawn 或 Update 添加：
- `SubUV Animation`

3. 设置：
- Start Frame = 0
- End Frame = 最后一帧

### 随机图集格子

典型接法：

1. Sprite Renderer 设置：
- `Sub Image Size`

2. Spawn 时给 `SubImageIndex` 一个随机整数

例如：
- 4x4 图集
- 总共 16 格
- Spawn 时随机 0 - 15

### 关于黑边

Flipbook 纹理常见问题是 alpha 黑边。

对火焰、烟雾、爆炸，建议注意：
- alpha 边缘要干净
- 贴图 RGB 不要带脏黑边
- 必要时在材质中做 RGB / Alpha 修正

---

## 4. 真实火把的纹理决策

### `Emitter_FlameCore`

推荐：
- **需要纹理图**
- **优先 Flipbook**

建议：
- 4x4、8x8 都可以
- 4x4 更轻
- 8x8 更细腻

最优来源：
- 先用 Niagara Flipbook Baker 从已有火焰模拟烘
- 如果当前没有项目，也可以先用外部 AI 生成

### `Emitter_FlameDetail`

推荐：
- **建议有纹理图**
- **不强制 Flipbook**

更适合：
- 单张灰度火舌纹理
- 小型变体图集

原因：
- 这一层主要负责边缘活性
- 让火焰不那么像一个统一大块

### `Emitter_Embers`

推荐：
- **需要小纹理图**
- **通常不需要 Flipbook**

更适合：
- 单张火星 / ember alpha
- 或 4x4 小图集

是否需要 AI 生成：
- 可选
- 如果项目偏真实，单张简单 ember 纹理就足够
- 如果想更丰富，可以让 AI 生成一套不规则 ember atlas

### `Emitter_Smoke`

推荐：
- **需要纹理图**
- **优先 Flipbook / SubUV**

原因：
- 轻烟如果只用单张图，很容易假
- 烟雾需要边缘变化和内部体积错觉

如果没有 flipbook：
- 可先用单张烟雾 alpha 做原型
- 但正式方案仍建议换成 flipbook

### 持续燃烧场景的重要例外

这里有一个非常关键的判断：

**持续燃烧的火把、篝火、香炉，不应该直接把“一整段从无到有再到无的烟雾 plume flipbook”循环播在单个常驻粒子上。**

原因：
- 那类烟雾图集本质上是“一次性 puff / plume”
- 如果整段循环播，会让烟雾反复经历：
  - 凭空出现
  - 长大
  - 变淡消失
- 这更像一个一次性烟团，而不是持续不断的燃烧尾烟

### 正确做法

更合理的方式是：

#### 方法 A：持续 Spawn 短生命粒子

- 每个烟雾粒子各自播放一段“从生成到消散”的 smoke flipbook
- System 层持续不断生成新粒子
- 整体看起来就是连续燃烧的烟，而不是同一个烟团循环重播

这是最推荐、最真实的做法。

#### 方法 B：用中段帧做循环变体

如果你只有一张 plume flipbook，又不想明显看到“从无到有”，可以：

- 不使用前几帧
- 不使用最后几帧
- 只取中段较稳定的帧段循环

这样更像“持续抖动的烟形”，但真实感仍不如方法 A。

#### 方法 C：主烟形用静态图，细微变化靠噪声

如果预算很紧：
- 主烟雾用单张软烟图
- 再用 Panner / Noise / Alpha 做轻微变化

这比错误循环 plume flipbook 更自然。

### 对你这张图的判断

像你现在给的这类序列图：
- 更适合当“单个烟雾粒子的生命周期动画”
- 适合系统持续 Spawn 新粒子来拼出连续尾烟
- **不适合把同一粒子从第 1 帧播到最后一帧后再回到第 1 帧无限循环**

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

## 9. 叶片 diffuse/alpha 与叶片卡

Foliage、灌木、草叶卡片这类材质不能只靠常量颜色判断“做对了”。如果缺少叶片 diffuse/alpha 或真实叶片卡载体，流程是：

1. 先查资产库：
   - `category=foliage`
   - `role=leaf-card`、`leaf-cluster`、`albedo-alpha` 等标签
   - 优先 power-of-two、已通过 alpha QA 的 approved 资产

2. 没有合适资产再调用 `cm-imagegen`：
   - 有参考图时必须走参考图 / image-to-image
   - 明确要“贴图卡”，不是摆拍照片或渲染图
   - 要透明背景或干净 alpha，不要阴影、地面、文字、水印

3. 自审后才导入 UE：
   - `texture_asset_report.py --role foliage`
   - alpha 不是全白，也不是脏边
   - 分辨率优先 `512x512`、`1024x1024`、`2048x2048`
   - 导入后颜色 diffuse 用 sRGB，OpacityMask / packed mask 用 sRGB off

提示词模板：

```text
single foliage leaf-card diffuse alpha texture, 1024x1024 power-of-two,
top-down flat scanned leaf cluster, transparent background with clean cutout alpha,
natural green albedo, no cast shadow, no ground, no text, no watermark,
for Unreal masked TwoSidedFoliage material on a two-sided card
```

如果用户提供的是某种具体植物参考，就把物种、叶型、颜色状态、枯黄/湿润/季节特征写进去，并用参考图锁住形态。生成后要在真实 masked two-sided card 或小簇卡片上预览；单看 PNG 好看不代表进材质后能用。

---

## 10. 定制水材质的参考图优先规则

水材质尤其容易被“资产库里刚好有一张水波纹”带偏，所以要先区分两件事：

- **视觉身份**：用户参考图里真正让水成立的东西，例如泡沫形状、颜色层次、透明度、浪尖、岸边湿痕、卡通描边、油膜彩虹、深浅水过渡、caustics、污浊颗粒、风格化笔触。
- **技术辅助**：支撑 shader 的噪声、ripple height、normal、flow、foam breakup、depth mask、roughness breakup。

复用规则：

- 如果资产库水纹只是一张普通 ripple/noise，它不能替代参考图里的视觉身份。
- 普通 ripple 可以作为很弱的 normal/roughness breakup，但要防止它把最终外观变成“通用水”。
- 如果参考图决定了泡沫、caustics、颜色纹理、风格化笔触或特殊液体表面，这些贴图应从参考图生成、手工/DCC 制作、或专门程序生成。
- AI 生成的 water height / flow / normal 只能当草图；final normal/flow/vector 数据必须检查 seam、方向、通道语义和导入设置。
- 预览时要看 carrier：平面水面、河道、岸边、泳池、屏幕空间 post-process、水下体积或 stylized mesh。单看一张贴图不能证明材质匹配参考。

定制水 prompt 要先写参考读法，再写技术输出，例如：

```text
custom stylized water foam mask from reference image, preserve painterly cyan-white foam streak shapes, shallow tropical color rhythm, medium-scale shoreline breakup, seamless horizontal tiling, 1024x1024 power-of-two, grayscale mask, no text, no watermark
```

如果参考图是写实湖面、深海、浅滩、卡通水、油污水、魔法水，它们需要不同的纹理策略。不要用同一张库内通用水波纹去套所有水。

---

## 11. 生成纹理时的硬规则

- 背景纯黑，或明确透明
- 每格主体居中
- 不要文字
- 不要边框
- 不要水印
- 帧与帧之间尺度一致
- 视角固定
- 适合 alpha 提取
- 尽量高对比

### 对 Flipbook 尤其重要

- 帧间形状连续
- 不要摄像机跳动
- 不要每格大小都不一样
- 不要突然裁切

### 对随机图集尤其重要

- 各格风格统一
- 各格亮度范围接近
- 各格不要差异大到像不同资源包

---

## 一句话原则

真实感强、形态连续变化大的层，用 Flipbook。
随机变化、单体很小的层，用单张图或随机格子图集。
外部 AI 可以生成这些纹理，但必须先明确它属于哪一种。
