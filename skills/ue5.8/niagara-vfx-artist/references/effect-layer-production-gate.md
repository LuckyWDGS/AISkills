# 效果层生产闸门：从参考图到 UE 可落地资产

## 用途

这份文档用于防止从设计图直接跳到“纹理图”，尤其适用于用户给了复杂设计图、要求拆层、要求 UE/Niagara 可实现、并且后续要生成纹理/材质/参数的任务。

核心原则：

- 先恢复/增强参考图清晰度，再拆解。
- 先做单层可落地效果图，再做贴图。
- 先判断 UE 承载方式，再决定纹理类型。
- 用户确认效果图后，才进入材质贴图、Niagara 参数、动画接入。

---

## 1. 不要直接从概念图跳到纹理

错误流程：

```text
设计图 -> 拆出“尾部流光” -> 生成 T_GoldFlow_Noise 方图 -> 交付
```

原因：

- 设计图是最终镜头效果，不等于材质输入。
- 拖尾、残影、流光通常依赖 Ribbon/Mesh/Spline/动画事件，不是一张方形图能成立。
- 如果参考图低清，模型会把羽毛、流线、金屑、云纹混在一起。

正确流程：

```text
设计图 -> 高清锚点/局部裁切 -> 层级视觉证据 -> UE 承载方式 -> 单层效果图 -> 用户确认 -> 纹理/材质/Niagara/动画接入
```

---

## 2. 高清锚点优先

当设计图不够清晰：

- 先缓存原图。
- 对目标视角/区域做单独裁切。
- 小裁切保存到 `hq-crops/`，最长边建议至少 `1536px`，只做轻锐化，不重绘细节。
- 如果仍然糊，可以用 `cm-imagegen edit` 从完整设计图 + 高清裁切生成一张更大的“层级细化参考图”，但它只能作为辅助，不能替代原始设计图。

不要把多个小图压成低清拼图作为主锚点。

---

## 3. 每一层先判定 UE 承载方式

拆层时必须先回答：这一层在 UE 里由什么承载？

### Ribbon / Trail

适合：

- 尾部流光拖尾
- 武器拖尾
- 魔法轨迹
- 飞行路径残留
- 细长连续路径

典型资产：

- 长条拖尾主纹理，不是普通方形噪声
- 长度向渐隐 Alpha
- 横向边缘破碎 Mask
- UV 流动噪声
- 可选 Flow/Distortion 纹理

典型 Niagara：

- Ribbon Renderer
- 粒子按 Socket/路径连续生成
- Ribbon Width 随生命周期或距离变化
- UV 沿长度方向流动
- 用 Anim Notify 或 Blueprint 控制生成区间

### Mesh Afterimage

适合：

- 翅膀声波残影
- 弧形能量片
- 需要稳定大轮廓的残影面片

典型资产：

- 弧形残影 mesh
- 弧形光带 alpha/mask
- 流动噪声
- 羽片破碎 mask

典型 Niagara：

- Mesh Renderer
- 在挥翅峰值 Spawn 3-5 片
- 对齐翼尖方向
- 0.45-0.75 秒淡出

### Sprite / Atlas

适合：

- 金屑
- 小火星
- 碎片
- 小型随机亮点

典型资产：

- 4x4 或 8x8 随机图集
- 每格独立居中
- 不用于连续拖尾

### Skeletal Material Mask

适合：

- 身体纹路发光
- 眼睛/纹理渐亮
- 模型表面局部 emissive

典型资产：

- UV 对应的 emissive mask
- 或可投射/贴片式 decal/mask
- 需要贴合模型 UV，不要只生成漂亮图案

---

## 4. 单层效果图闸门

复杂层必须先生成“单层可落地效果图”，不是直接生成最终贴图。

单层效果图要求：

- 只表现这一层，不混入整只角色和场景。
- 明确 UE 承载方式，例如 `Ribbon trail material preview`、`curved mesh afterimage preview`、`Niagara spark atlas preview`。
- 看起来像 UE 里能搭出来的效果，不追求电影级不可落地细节。
- 可以包含简化 mesh/ribbon 形体，用来确认轮廓、长度、密度、亮度、颜色、节奏。

用户确认后再产出：

- 需要哪些纹理
- 每张纹理的格式和用途
- 材质节点逻辑
- Niagara emitter/module 参数
- 动画或 Blueprint 接入方式

---

## 4.1 动态预览闸门

如果静态单层效果图已经成立，但用户仍然担心“动起来会不会变形、太死、太空、太乱”，可以再补一个短动态预览。

推荐做法：

- 用同一层的 3-5 张关键状态图做短帧序列。
- 时间长度控制在 2-3 秒，便于判断节奏和读图。
- 重点看起势、峰值、衰减，而不是追求完整动画制作。
- 动态预览仍然是“验证层”，不是最终交付材质本体。

适合先做动态预览的层：

- Ribbon trail
- Wing afterimage
- Spark burst
- Rune pulse

不适合直接跳到动态预览的层：

- 还没确认承载方式的层
- 还没确认轮廓的层
- 还没确认单层静态样子是否成立的层

---

## 5. 拖尾类纹理的正确目标

尾部流光这类一眼就是拖尾，不应该先生成 `T_GoldFlow_Noise` 方形图当主资产。

更合理的纹理拆分：

- `T_TailRibbon_CoreGradient`
  长条纹理，沿 U 方向从亮到淡，中心白金核心，两侧透明。
- `T_TailRibbon_EdgeBreakup`
  长条边缘破碎 alpha，控制拖尾边缘撕裂。
- `T_GoldFlow_Noise`
  辅助流动噪声，用于 UV panner/distortion，不承担主拖尾形状。
- `T_TailRibbon_TipFlare`
  可选头尾亮点或末端卷曲 flare。

材质先看长条 Ribbon，而不是先看方形噪声。

---

## 6. 金兜雁设计图的当前层级判断

### 翅膀声波残影

设计证据：

- 正面、侧面、前后 45 度都有多道弧形金色翼波。
- 波纹和翅膀结构绑定，像挥翅留下的结构性残影，不像自由飘带。

推荐路线：

- Curved wing afterimage mesh + Mesh Renderer。
- 材质用金色 Additive/Translucent，带流动噪声和羽片状 mask。
- 动画挥翅峰值 Spawn 3-5 片，沿翼尖方向展开并淡出。

### 尾部金色流光

设计证据：

- 侧面、背面、前后 45 度都有从尾部和飞行路径拉出的长条光带。
- 形体连续、长度大、沿路径弯曲，明显是拖尾逻辑。

推荐路线：

- Niagara Ribbon Renderer 或 Spline Mesh Trail。
- 绑定尾部 socket 或由动画/蓝图持续采样尾点。
- 主资产应是长条 Ribbon 材质纹理，不是单张随机噪声方图。

### 嘴部云纹/飘带

设计证据：

- 嘴部和身体周围有更淡、更短、更软的云纹条带。
- 比尾部拖尾更轻，密度低，存在感弱。

推荐路线：

- 少量 Ribbon 或预制 mesh strip。
- 低透明度金白材质，生命周期短，跟随飞行动作轻微偏移。

### 金屑火花

设计证据：

- 翅膀、尾部周围有稀疏金屑，数量不大。

推荐路线：

- Sprite Renderer + 4x4 atlas。
- Spawn 数量少，随机速度/Drag/Size/Lifetime。

### 身体纹路发光

设计证据：

- 胸腹、颈部、眼睛区域有金属纹理和发光趋势。

推荐路线：

- 模型材质 emissive mask 或 decal/mask overlay。
- 如果没有模型 UV，只能先做效果图和概念 mask，不能声称是最终 UV 贴图。

---

## 7. 官方资料提炼

Epic 的 Ribbon 教程把 Ribbon 用于连续的 ribbon-style particle effect，并通过 Spawn Rate 形成连续粒子流；这说明拖尾层应优先先设计 Ribbon 形体和运动，而不是先生成一张静态漂亮图。

Epic 的 Ribbon Renderer 属性包含宽度、UV、材质参数、Ribbon ID、Link Order、Tessellation 等绑定项；这说明拖尾材质需要考虑沿长度方向的 UV、宽度曲线、排序和材质动态参数。

Epic 的 Timed Niagara Effect Anim Notify 可以在动画 Notify 开始激活 Niagara、结束时关闭，并支持 Socket/Bone 绑定；这说明挥翅、尾部拖尾、觉醒阶段应该接入动画事件，而不是只在场景里常驻播放。

Epic 的 Mesh Renderer 说明 Mesh particles 可以实例化 Static Mesh，Override Material 需要 Niagara Mesh Particles 标记；这支持用弧形 mesh 做翼波残影，而不是用大量 sprite 硬堆。

---

## 8. 交付格式

当用户给参考图并要继续制作时，优先输出：

```text
1. 高清参考处理结果
2. 分层视觉证据
3. 每层 UE 承载方式
4. 每层单层效果图
5. 等用户确认
6. 纹理清单
7. 材质节点/参数
8. Niagara emitter/module 参数
9. 动画/Blueprint 接入方式
```

如果用户直接要纹理，但该层其实是拖尾/mesh/材质系统：

- 先提醒这张纹理不是主形体。
- 先补单层效果图或主材质预览。
- 再生成真正适合该承载方式的纹理。

---

## 官方资料锚点

- Ribbon 相关：Epic 的 [How to Create a Ribbon Effect in Niagara for Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-create-a-ribbon-effect-in-niagara-for-unreal-engine?application_version=5.6) 明确把 Ribbon Renderer 用于连续的 ribbon-style particle effect。
- 多渲染器与性能：Epic 的 [Scalability and Best Practices for Niagara](https://dev.epicgames.com/documentation/en-us/unreal-engine/scalability-and-best-practices-for-niagara?application_version=5.6) 提到单个 emitter 可以挂多个 renderer，mesh arrays 也可减少重复 emitter。
- 动画挂接：Epic 的 [`unreal.AnimNotify_PlayNiagaraEffect`](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AnimNotify_PlayNiagaraEffect.html?application_version=5.2) 暴露了 `attached`、`socket_name`、`template` 等属性，适合骨骼/Socket 触发。
- 烘焙路径：Epic 的 [Niagara Fluids in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/niagara-fluids-in-unreal-engine?application_version=5.6) 明确建议在需要时把重的 fluid 结果烘成 flipbook 再用。
