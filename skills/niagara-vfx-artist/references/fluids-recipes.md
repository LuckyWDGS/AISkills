# 流体效果方案库

## 用途

这份文档用于把常见流体类效果拆成可执行路线，而不是停留在“可以用 Niagara Fluids”这种泛泛建议。

适合在这些场景读取：
- 需要快速判断某类流体效果该用什么路线
- 需要把效果拆成主方案、辅助方案、低成本方案
- 需要结合 Unreal 官方能力和社区成熟做法来选型

这份文档结合了：
- Epic 官方 Niagara Fluids / Flipbook / Fluid Simulation 文档
- Epic Developer Community Forums
- RealTimeVFX 社区实战案例
- 80.lv 上的 Niagara Fluids / Flowmap 工作流文章

---

## 目录

1. 总体选型表
2. 水流表面方案
3. 瀑布方案
4. 水花喷溅方案
5. 烟流方案
6. 火流方案
7. 熔岩流方案
8. 通用判断原则

---

## 1. 总体选型表

| 效果类型 | 首选路线 | 辅助路线 | 高成本英雄方案 |
|---|---|---|---|
| 水流表面 | Flow Map + Material | Foam / Ripple 贴图 | Shallow Water / 3D FLIP 只在交互强时使用 |
| 瀑布 | Flow Map + Mesh + Niagara 二级粒子 | Flipbook mist / splash | 3D FLIP 仅近景英雄镜头 |
| 水花喷溅 | Flipbook + Niagara 粒子 | 2D FLIP | 3D FLIP |
| 烟流 | 2D Gas 或 Flipbook | 粒子 + Flipbook | 3D Gas |
| 火流 | 2D Gas 或 Fluids 烘焙 Flipbook | Sprite / Flipbook + Embers | 3D Gas |
| 熔岩流 | Flow Map + Material | 烟 / 火花 / 气泡二级层 | 3D FLIP 很少必要 |

---

## 2. 水流表面方案

### 推荐路线

**首选：`Flow Map + Material`**

### 为什么

水流表面大多数时候是“表面运动感”，不是“真正体积液体”。

Epic 官方 Fluid Simulation Overview 说明：
- `Shallow Water` 更适合浅水表面和交互
- `3D FLIP` 更适合复杂液体体积

这意味着如果你只是做：
- 河流表面
- 水渠
- 水面流向
- 贴地流动水

通常没必要直接上 3D FLIP。

社区经验也一致：
- Flow Map 在环境水流里非常常见
- RealTimeVFX 的河流 / 瀑布案例会把流向信息烘成 flowmap，再交给材质

### 主结构

1. 主水面网格
2. Flow Map 驱动 UV
3. Normal / Foam / Distortion 材质层
4. 必要时局部加 Niagara 白沫或碰撞水花

### 什么时候升级成 Shallow Water

如果出现这些需求，再考虑 `Shallow Water`：
- 船尾波
- 脚踩水产生波纹
- 明显物体推动水面的交互
- 需要表面波高响应

### 不推荐

- 为普通河流表面直接上 `3D FLIP`

### 一句话

**水流表面优先材质做，交互强了再考虑 Shallow Water。**

---

## 3. 瀑布方案

### 推荐路线

**首选：`Flow Map + Mesh + Niagara 二级粒子`**

### 为什么

瀑布通常不是一个“必须用完整液体模拟”的效果。

RealTimeVFX 的 `Cliffside Falls` 案例非常典型：
- 用曲线生成水流几何
- 沿长度规范化 UV
- 在几何上准备 flowmaps
- 用 FLIP quick sim 渲染出 splash / mist spritesheet
- 再在 UE5 Niagara 中把 splash / mist 当成二级层

这个思路非常成熟，也非常像真实生产。

Epic 官方水体文档和 Asher Zhu 的分享也说明：
- 白水 / 水花常常用 flipbook sprites 表达
- 主水体可以由材质和表面渲染负责

### 最优结构

#### 主层
- 瀑布网格
- 法线 / Flow Map / Foam 材质
- 可叠加折射和边缘泡沫

#### 次层
- 瀑布底部冲击 mist
- 溅射 splash
- 周围小雾气

#### 可选层
- 水面扰动贴图
- 底部涟漪

### 什么时候考虑 3D FLIP

只有这些情况下才值得：
- 极近景英雄镜头
- 镜头会环绕瀑布
- 需要真实体积断裂、卷边、冲击形变

### 社区经验重点

瀑布常见成熟路线不是“整条都模拟”，而是：
- 主体靠材质流动
- 水花和雾气靠 flipbook / Niagara

### 一句话

**瀑布主体靠 mesh + flowmap，体积感和白水靠 flipbook / Niagara 补。**

---

## 4. 水花喷溅方案

### 推荐路线

**常规首选：`Flipbook + Niagara 粒子`**

### 为什么

Epic / 80.lv / 社区经验都比较一致：
- splash 的主视觉经常是 flipbook sprites
- 真正重液体模拟通常只在英雄镜头才值得

Epic 官方 Fluid Simulation Overview 指出：
- `2D FLIP` 很适合 splash
- `3D FLIP` 更贵、更复杂

### 常规游戏方案

1. 水滴粒子
2. Splash flipbook
3. 地面冲击白沫
4. 少量 mist

### 推荐路线拆分

#### 轻量游戏方案
- Flipbook splash
- 单张或小图集水滴
- 少量 mist

#### 中等方案
- `2D FLIP` 先做高质量 splash
- 烘成 flipbook
- 再拿到正式系统里用

#### 英雄方案
- `3D FLIP`

### 一句话

**喷溅默认别先想实时体积液体，先想 splash flipbook。**

---

## 5. 烟流方案

### 推荐路线

**游戏常规首选：`2D Gas` 或 `Flipbook`**

### 为什么

Epic 官方文档明确指出：
- `2D Gas` 更适合游戏实时
- `3D Gas` 更适合 hero effect 和 cinematics

而且 2D Gas 可以模拟出 3D 感，尤其适合：
- 烟柱
- 火把烟
- 持续尾烟

### 常见路线

#### 轻量路线
- 单张烟图 + 噪声

#### 常规路线
- `2D Gas` 模拟
- 或 2D Gas / 3D Gas 烘焙成 flipbook

#### 英雄路线
- `3D Gas`

### 社区经验重点

RealTimeVFX 中很多成熟烟效最后都会变成：
- 渲染 flipbook
- Niagara 播放

这是因为：
- 实时成本更可控
- 更容易批量放场景

### 一句话

**烟流优先 2D Gas 或烘焙 flipbook，3D Gas 只给英雄镜头。**

---

## 6. 火流方案

### 推荐路线

**常规首选：`2D Gas` 或 `Niagara Fluids -> Flipbook`**

### 为什么

Epic 官方 Fluid Simulation Overview 里提到：
- 2D Gas 非常适合 torch 这类 flame effect
- 3D Gas 更贵，更适合 hero effect

社区上也很常见：
- 先做流体火焰
- 再烘焙成 flipbook
- 最终在 Niagara 里用 sprite 播放

RealTimeVFX 多视角 campfire 讨论甚至直接以：
- `Houdini -> flipbooks -> Unreal Niagara`
为可扩展高质量方案

### 推荐路线拆分

#### 火把 / 小型持续火流
- `2D Gas`
- 或烘成 flipbook

#### 喷火 / 大型火浪
- 高质量方案可先流体模拟
- 正式游戏版本通常还是 flipbook

#### 英雄近景火焰
- `3D Gas`

### 一句话

**火流是 Niagara Fluids 很适合的一类，但正式量产常常还是走烘焙 flipbook。**

---

## 7. 熔岩流方案

### 推荐路线

**首选：`Flow Map + Material`**

### 为什么

熔岩大多数时候更像：
- 黏稠表面流动
- 热光边缘
- 局部气泡
- 少量烟雾和火星

它通常不需要像水一样的大量液体飞溅。

所以最常见有效路线是：
- 主熔岩流靠材质
- 表面流动靠 flow map
- 热边缘、裂缝、亮核靠 emissive
- 烟和火星靠 Niagara 二级层

### 推荐结构

#### 主层
- 熔岩流动材质
- Flow Map
- Height / Crack / Emissive Mask

#### 次层
- 边缘烟气
- 零星火花
- 气泡或喷点

### 什么时候考虑真实液体模拟

只有这些情况下才值得：
- 近景熔岩倒灌
- 大型熔融物体流淌
- 明显体积断裂和碰撞

但大多数游戏里，这都不是首选。

### 一句话

**熔岩优先当“热的流动材质”做，而不是当“真实液体水”做。**

---

## 8. 通用判断原则

### 优先级最高的问题

先问自己：

1. 这是表面流动还是体积流体？
2. 这是实时长时间存在还是一次性镜头？
3. 这层需要真实交互，还是视觉成立就够？

### 最常见的成熟路线

- 表面：`Flow Map + Material`
- 烟火：`Niagara Fluids -> Flipbook`
- 水花：`Flipbook + Niagara`
- 瀑布：`Mesh + Flowmap + Niagara secondary`

### 一句话总原则

**真正重模拟只在最值得的层上使用，其余层优先用材质、flipbook 和二级粒子完成。**
