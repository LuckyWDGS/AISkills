# Niagara VFX 常见翻车案例

## 用途

这份文档用于沉淀 Niagara 特效制作中最常见、最容易反复踩的失败案例，以及快速修复思路。

适合在这些场景读取：
- 用户说“效果看起来不对，但说不清哪里不对”
- 需要快速对照常见问题定位原因
- 需要做特效复盘
- 需要告诉团队“哪些方案最容易翻车”

这份文档和 `debugging.md` 的区别是：
- `debugging.md` 更偏检查流程
- 这份文档更偏“典型坏案例 + 为什么坏 + 怎么修”

---

## 目录

1. 过曝发白
2. 烟雾糊屏
3. 护盾像塑料壳
4. 爆炸没有冲击感
5. 拖尾像面条
6. 能量球像灯泡
7. 命中特效没打击感
8. 法阵像贴图
9. 移动端直接爆预算
10. 多特效同屏一团乱

---

## 1. 过曝发白

### 失败症状

- 看起来很亮，但没有层次
- 核心、边缘、细节全部糊成一片白
- 截图里尤其明显

### 检查步骤

1. 检查 `S_EmissiveIntensity` 是否过高
2. 检查是否有多层 Additive 同时覆盖核心区域
3. 检查亮区面积是否过大，而不是只在小范围爆亮

### 修复参数建议

- `S_EmissiveIntensity`: 往下压 20% - 50%
- `S_Opacity` 或亮区遮罩范围：缩小高亮面积
- `S_FresnelIntensity`: 只保留轮廓亮度，不要整体同亮

---

## 2. 烟雾糊屏

### 失败症状

- 画面一片灰
- 角色和技能识别都被盖住
- 性能也变差

### 检查步骤

1. 检查烟雾粒子尺寸是否过大
2. 检查烟雾生命周期是否过长
3. 检查是否有多层半透明烟雾同时覆盖屏幕中心

### 修复参数建议

- `Lifetime`: 降低 20% - 50%
- `Initial Size` / `Final Size`: 整体缩小一档
- `Spawn Rate`: 先减 30% 看可读性是否明显改善

---

## 3. 护盾像塑料壳

### 失败症状

- 有一个球壳，但没有能量感
- 看起来像静态模型，不像特效

### 检查步骤

1. 检查是否只有外轮廓，没有表面流动
2. 检查 `T_Noise` 和 `S_NoiseStrength` 是否太弱
3. 检查受击层是否存在，或者峰值是否足够

### 修复参数建议

- `S_NoiseStrength`: 提高到中等强度
- `S_FlowSpeed`: 增加轻度表面流动
- `S_FresnelIntensity`: 拉开边缘与中心差异
- `S_HitMaskIntensity`: 提高受击瞬时反馈

---

## 4. 爆炸没有冲击感

### 失败症状

- 只是亮一下，然后散开
- 没有“炸开”的感觉

### 检查步骤

1. 检查前 0.1 秒是否有明显峰值
2. 检查冲击环是否存在，或是否太弱
3. 检查火星 / 碎屑初速度是否不足

### 修复参数建议

- `Burst Count`: 核心层和火星层都可略增
- `Velocity`: 火星初速度上调
- `S_RingWidth` 与冲击环亮度：提高存在感
- 核心层 `Lifetime`: 适当缩短，让爆点更集中

---

## 5. 拖尾像面条

### 失败症状

- Ribbon 很长，但没质感
- 看起来软塌塌
- 没有速度感
- 明明调亮了，但仍然不像设计图里的分段残影或翼波

### 检查步骤

1. 先判断是形态问题还是材质问题
2. 检查头尾亮度是否一致
3. 检查宽度是否从头到尾都差不多
4. 检查是否完全没有内部流动
5. 检查 RibbonID / LinkOrder / source-receiver 数据是否把本应分开的残影连成一条

### 修复参数建议

- `S_TrailHeadBrightness`: 提高
- `S_TrailTailOpacity`: 降低
- Ribbon Width: 做头尾宽度变化
- `S_FlowSpeed`: 加入轻微内部流动
- 如果是“连续蛇形”而不是“多道残影”，优先修 Niagara 的 RibbonID 分段、LinkOrder 或触发时序，不要继续只加亮度
- 如果轮廓已经对但像塑料带，才优先修材质的软边、噪声、UV flow 和 alpha falloff
- 如果材质逻辑对但内部纹理糊，回到纹理/mask 生成质量，不要硬靠粒子数补细节

---

## 6. 能量球像灯泡

### 失败症状

- 只是一个会发光的圆球
- 没有内部结构
- 没有积蓄能量的感觉

### 检查步骤

1. 检查是否只有边缘光，没有内部噪声层
2. 检查 `S_InnerFlowSpeed` 是否太低或完全没有
3. 检查颜色是否只有单层，没有核心和外壳差异

### 修复参数建议

- `S_InnerFlowSpeed`: 增加内部动势
- `S_NoiseContrast`: 提高一点内部结构感
- `S_EdgeColorIntensity`: 保持边缘存在感，但不要压过内部
- 核心和边缘颜色拆分成两层控制

---

## 7. 命中特效没打击感

### 失败症状

- 命中了，但像没打到
- 信息出来了，但不疼

### 检查步骤

1. 检查命中闪光峰值是否足够
2. 检查生命周期是否太长
3. 检查是否缺少外扩或碎散反馈

### 修复参数建议

- `Lifetime`: 压缩到更短
- `S_EmissiveIntensity`: 只强化击中瞬间
- `Burst Count`: 给碎散层少量增加
- 冲击环半径增长速度：提高一点

---

## 8. 法阵像贴图

### 失败症状

- 图案是有了，但没有“激活感”
- 像地上放了一张图

### 检查步骤

1. 检查主环和外环是否完全同速或静止
2. 检查是否完全没有上升粒子或边缘能量
3. 检查图案密度是否过满

### 修复参数建议

- `Rotation Speed`: 主环和外环拉开差异
- `S_EmissiveIntensity`: 做轻微呼吸变化
- `Spawn Rate`: 给上升粒子层增加适量存在感
- `Opacity`: 降一点，让主图案更清晰

---

## 9. 移动端直接爆预算

### 失败症状

- 编辑器里好看
- 手机上掉帧严重

### 检查步骤

1. 检查是否直接复用了 PC 版
2. 检查粒子数和 Emitter 数是否超移动端预算
3. 检查材质采样数和透明覆盖是否过大

### 修复参数建议

- `Spawn Rate` / `Burst Count`: 先砍 30% - 60%
- `Lifetime`: 缩短
- 粒子尺寸：缩小
- 材质采样层数：优先减半

---

## 10. 多特效同屏一团乱

---

## 11. 官方 Stack Fix 只会读不会修

### 失败症状

- `GetStackIssues` 能返回问题
- 但一直没有真实验证过 `ApplyOfficialStackIssueFix`
- 或者只看到 `Info`，没有 `Fix` 按钮类问题

### 常见误判

- 把“wrapper 编译成功”当成“fix 真可用”
- 把 `Info` 注释类 issue 当成 fix-style 证据
- 在没有 compile settle 的情况下立刻读 issue，误以为 fix 没生效

### 已验证的真实 fix-case

2026-05-15 已在 `/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke` 跑通两个真实 fix：

- `GPU上不支持事件处理器`
  - 造法：把 emitter `Smoke` 设成 `GPUComputeSim`，再给它挂粒子 event handler
  - 官方 fix：`设置CPU模拟`
  - 结果：`ApplyOfficialStackIssueFix` 后，`Smoke.SimTarget` 真读回为 `CPUSim`

- `堆栈数据无效`
  - 同一个 event-handler 测试路线上产生
  - 官方 fix：`修复无效堆栈图表`
  - 结果：应用后最终 stack issue 收敛到 `0 errors / 0 warnings`

### 修复建议

1. 先造一个源码里明确会给 `Fix` 的问题，不要在 `Info`-only 系统上空等
2. `ApplyOfficialStackIssueFix` 之后必须做三次验证：
   - 返回结果里 `applied=true`
   - 目标属性或结构真读回变化
   - compile settle 后重新读 `GetStackIssues`
3. 如果 `GetStackIssues` 提示正在编译，不要立即下结论，先等 compile 完

### 一句话经验

`ApplyOfficialStackIssueFix` 只有在“造出真实 fix-style 问题 -> 应用 fix -> 读回结构和 issue 状态”三步都闭环后，才算真的可用。

### 失败症状

- 单个看还行
- 一多起来完全看不清

### 检查步骤

1. 检查每个效果是否都同时很亮、很多烟、很多残留
2. 检查是否缺少群战降级策略
3. 检查多个效果叠加后是否覆盖屏幕中心

### 修复参数建议

- `Lifetime`: 群战版本整体下调
- `Spawn Rate`: 次级层批量降低
- 大尺寸烟雾粒子：删减或缩小
- 只保留命中和核心识别层，次级装饰层自动关闭

---

## 使用建议

当用户描述的问题比较抽象时，可以先从这里找最接近的翻车类型，再结合：
- `references/debugging.md` 的检查清单
- `references/mobile-checklist.md` 的移动端约束
- `references/common-effect-patterns.md` 的正确模板骨架

这样更容易从“症状”倒推到“方案修正”。
