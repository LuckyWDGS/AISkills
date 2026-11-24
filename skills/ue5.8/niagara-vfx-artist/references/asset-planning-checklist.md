# 资产规划清单

## 用途

这份文档用于把一个特效方案真正转成“制作清单”。

目标是回答：
- 这套效果最终要做哪些资产
- 哪些必须先做
- 哪些属于补充层
- 哪些应该做低配版

适合在这些场景读取：
- 用户已经确定要做某个效果
- 需要从方案阶段进入制作阶段
- 需要避免漏做资产

---

## 目录

1. 使用原则
2. 资产类型总表
3. 最小可用版清单
4. 完整版清单
5. 低配版清单
6. 命名建议
7. 实战检查项

---

## 1. 使用原则

规划资产时不要直接问“我还想加什么”，先问：

1. 主信息需要什么
2. 辅层需要什么
3. 哪些是奢侈层
4. 哪些要做低配版

不要一开始就把所有想法都做成资产。

---

## 2. 资产类型总表

一个完整特效通常会涉及这些资产类型：

### 纹理

- 单张 alpha / mask
- Flipbook / SubUV
- Atlas 图集
- Flow Map
- Normal / Foam / Distortion

### 材质

- Master Material
- Material Instance

### Niagara

- Niagara System
- Niagara Emitters

### 绑定 / 使用

- 动画通知
- 蓝图参数
- User Parameters
- 平台 Effect Type

### 文档与版本

- 方案文档
- 低配方案
- 验收清单

---

## 3. 最小可用版清单

最小可用版只做“能成立”的核心内容。

### 必做

- [ ] 一个主材质
- [ ] 一个主 Niagara System
- [ ] 必要的主 Emitter
- [ ] 至少一套主纹理
- [ ] 至少一个场景内测试

### 例子：命中特效

- 主闪光材质
- 主冲击环材质
- Niagara System
- 2 - 3 个 Emitter

### 例子：火把

- FlameCore 纹理
- Smoke 纹理
- 主材质若干
- 主 System

---

## 4. 完整版清单

完整版会在最小可用版上增加：

- [ ] 次级粒子资产
- [ ] 辅助材质实例
- [ ] 可调 User Parameters
- [ ] 更细的 atlas / flipbook
- [ ] 平台差异版本

### 推荐思路

先完成：
- 主层成立

再扩展：
- 辅层增强
- 残留层丰富
- 低配版拆分

---

## 5. 低配版清单

低配版不应该是“完整版直接弱一点”，而应该是独立规划。

### 必查项

- [ ] 哪些 Emitter 可以删
- [ ] 哪些纹理可以降级
- [ ] 哪些材质可以简化
- [ ] 哪些层必须保留

### 典型低配动作

- 删 Detail Emitter
- 删次级 sparks / smoke
- 降低 flipbook 分辨率
- 改复杂材质为单层版本

---

## 6. 命名建议

### 材质

- `M_FX_*`：主材质
- `MI_FX_*`：材质实例

### 纹理

- `T_FX_*`
- `T_FX_*_Flipbook`
- `T_FX_*_Atlas`
- `T_FX_*_FlowMap`

### Niagara

- `NS_*`：Niagara System
- `NE_*`：Niagara Emitter

### 示例

- `M_FX_TorchFlame_Core`
- `MI_FX_TorchFlame_Core_Default`
- `T_FX_TorchFlame_Flipbook`
- `NS_Torch_Fire`

---

## 7. 实战检查项

每次从方案进入制作前，先过一遍：

- [ ] 主效果资产已经明确
- [ ] 次级资产是否真的有必要
- [ ] 低配版是否已经考虑
- [ ] 纹理策略是否已确定
- [ ] 命名是否统一
- [ ] Niagara System / Emitter 结构是否已确定
- [ ] 需要的材质实例是否已列出

---

## 一句话原则

资产规划的核心不是“列得越多越专业”，而是：

把主层、辅层、低配层和最终交付边界提前划清楚。
