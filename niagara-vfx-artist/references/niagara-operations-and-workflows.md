# Niagara 操作与工作流手册

## 用途

这份文档用于沉淀 Niagara 的常见操作、工作流和生产习惯，让回答更像一个真正熟悉 UE Niagara 的人，而不是只会讲概念。

适合在这些场景读取：
- 用户问 Niagara 具体怎么操作
- 需要解释系统 / 发射器 / 模块怎么组织
- 需要更成熟的 Niagara 工作流建议

这份文档结合了：
- Epic 官方 System / Emitter Module Reference
- Epic 官方 Sparks / Ribbon / Quick Start / Scratch Pad 文档
- Epic 官方 Effect Type 性能预算文档
- Timed Niagara Effect Anim Notify 文档
- 社区实战工作流经验

---

## 目录

1. 先从模板还是空白开始
2. System 与 Emitter 的组织方式
3. 模块堆栈思维
4. User Parameters
5. Scratch Pad 与自定义模块
6. 常见 Renderer 的工作流
7. 动画挂接
8. 性能预算与 Effect Type
9. 实战工作习惯

---

## 1. 先从模板还是空白开始

官方 Ribbon 教程强调了：
- 推荐从 emitter template 或 selected emitters 创建 system

这条很实用。

### 推荐策略

- 已知效果类型明确时：
  从模板开始

- 结构复杂、需求特殊时：
  从最小 system 开始

### 实战建议

- 学习阶段多用模板
- 正式生产阶段，复杂效果通常会做自己的基础 emitter 模板库

---

## 2. System 与 Emitter 的组织方式

### 一条非常重要的原则

Emitter 不是越多越专业。

更成熟的标准是：
- 每个 emitter 职责清晰
- 生命周期和 Renderer 差异足够大时才拆

### 推荐拆分依据

- Renderer 不同
- 生命周期不同
- 运动逻辑不同
- 材质类型不同
- 是否需要独立开关

---

## 3. 模块堆栈思维

Epic 官方 Module Reference 反复强调：
- Niagara 是 stack-based
- 按组执行

### 实战理解

- 先看 Emitter Update
- 再看 Particle Spawn
- 再看 Particle Update
- 最后看 Render

### 实战建议

- 不要乱插模块
- 模块顺序会影响最终结果
- 先做骨架模块，再补修饰模块

---

## 4. User Parameters

### 为什么重要

成熟 Niagara 系统不应该所有值都写死。

User Parameters 适合暴露：
- 颜色
- 强度
- 尺寸倍率
- 生命周期倍率
- 启停控制

### 推荐暴露策略

只暴露真正需要项目侧改的参数。

不要把所有参数都暴露，否则维护会很乱。

---

## 5. Scratch Pad 与自定义模块

Epic 官方 Scratch Pad 文档说明：
- 可以在 system / emitter 内做本地模块
- 适合快速搭逻辑

### 什么时候用

- 某个逻辑会反复用
- 现有模块组合起来太啰嗦
- 需要封装自己的团队规则

### 什么时候别急着用

- 只是简单效果
- 还没搞清楚现有模块能不能解决

### 实战建议

- 先会用现成模块
- 再考虑封装 Scratch Pad

---

## 6. 常见 Renderer 的工作流

### Sprite Renderer

适合：
- 烟
- 火花
- 命中
- 能量点

工作流重点：
- 材质先成立
- SubUV / 单图 / 图集策略先想清楚

### Ribbon Renderer

官方 Ribbon 教程非常适合作为基础操作参考。

适合：
- 拖尾
- 刀光
- 轨迹

工作流重点：
- Spawn 连续
- Lifetime 合理
- Ribbon 宽度和材质沿长度变化

### Mesh Renderer

适合：
- 护盾壳
- 法阵
- Portal

工作流重点：
- Mesh UV 质量很重要
- 不是所有几何层都该用 Sprite 勉强解决

---

## 7. 动画挂接

Epic 官方 `Timed Niagara Effect` 文档说明：
- 可以在动画 notify 中启停循环 Niagara

### 适合

- 武器附着特效
- 持续挥刀特效
- 技能蓄力
- 角色状态光效

### 实战建议

- 短促爆点可用普通 notify
- 持续循环效果更适合 timed notify

---

## 8. 性能预算与 Effect Type

Epic 官方 `Effect Type` 文档很重要，但很多人忽略。

### 它的价值

- 统一管理 Niagara 系统预算
- 距离裁剪
- 实例数缩放
- 全局预算控制

### 实战建议

项目稍微大一点，就应该尽早用 Effect Type。

不要等效果铺满关卡后才想起预算问题。

---

## 9. 实战工作习惯

### 1. 先把效果拖进场景里看

官方 Ribbon 教程明确建议：
- 一边放进关卡，一边改

这是非常对的。

因为特效脱离场景看，很多判断会失真。

### 2. 优先用一个主材质 + 多实例

80.lv 和很多艺术家 breakdown 里都反复出现这个习惯：
- 先有一个主材质
- 再大量用实例

这比到处复制 master material 更好维护。

### 3. 先做主层，再补辅层

不要一开始就做：
- 主层
- 烟
- sparks
- 拖尾
- 残留

正确顺序通常是：
- 先让主层成立
- 再一层层补

### 4. 先做能读懂，再做好看

这条是官方教程没有明说、但社区经验非常一致的共识。

---

## 一句话原则

真正像专家的 Niagara 工作流，不是知道更多按钮，而是知道：

什么时候该拆、什么时候该收、什么时候该暴露参数、什么时候该封装模块、什么时候该优先看场景里的结果。
