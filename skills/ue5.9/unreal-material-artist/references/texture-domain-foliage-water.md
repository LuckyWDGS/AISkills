# UE 纹理领域策略：Foliage 与 Water

## 用途

读取这份 reference 当任务涉及叶片 diffuse/alpha、叶片卡、foliage masked material、水材质参考图优先级、水面 foam/normal/flow/caustics 纹理策略。它是领域资产策略，不只是 prompt 模板。

## 目录

- [叶片 diffuse/alpha 与叶片卡](#9-叶片-diffusealpha-与叶片卡)
- [定制水材质的参考图优先规则](#10-定制水材质的参考图优先规则)

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
