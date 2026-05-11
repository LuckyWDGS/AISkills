# 特效标准工作流

## 用途

这份文档用于把需求输入、方案设计、资产规划、实现、Review、QA、交付串成一条标准工作流。

目标不是再增加知识点，而是把已有能力组织成一个稳定的生产闭环。

适合在这些场景读取：
- 用户需要一套更标准的工作方式
- 需要减少返工
- 需要把“想法”推进到“可交付”
- 需要统一团队内的特效工作流程

---

## 目录

1. 总体目标
2. 阶段 1：需求输入
3. 阶段 2：方案判断
4. 阶段 3：资产规划
5. 阶段 4：实现第一版
6. 阶段 5：艺术与结构 Review
7. 阶段 6：QA 与验收
8. 阶段 7：交付与归档
9. 失败时怎么回滚到上一步
10. 最小闭环

---

## 1. 总体目标

成熟的工作流，不是让每一步都变复杂，而是减少三种问题：

1. 需求没补齐就开始做
2. 做出来了但不成体系
3. 看起来差不多，但其实还不能交付

所以这条工作流的核心是：

`需求输入 -> 路线判断 -> 资产规划 -> 第一版实现 -> Review -> QA -> 交付`

---

## 2. 阶段 1：需求输入

目标：
- 把模糊需求补成可执行输入

使用：
- `references/request-intake-template.md`

这一步必须明确：
- 效果类型
- 使用场景
- 平台
- 时长 / 是否常驻
- 镜头距离 / 游戏视角
- 风格方向
- 是否有参考

### 通过标准

- [ ] 已能判断效果类型
- [ ] 已能判断平台和视角
- [ ] 已知是否需要低配版
- [ ] 已知有没有参考图或视频

### 如果没通过

不要继续做实现。

---

## 3. 阶段 2：方案判断

目标：
- 确定技术路线和结构方向

会用到：
- `references/case-studies.md`
- `references/common-effect-patterns.md`
- `references/non-fluid-effects-playbook.md`
- `references/fluids-recipes.md`
- `references/fluids-and-flowmaps.md`
- `references/art-direction-patterns.md`

这一步要回答：
- 主方案是什么
- 为什么这么选
- 主层、辅层、残留层分别是什么
- 是否需要纹理 / Flipbook / Flow Map / Fluids

### 通过标准

- [ ] 技术路线已经明确
- [ ] Emitter / 材质层次已经明确
- [ ] 已知哪些层是主层
- [ ] 已知哪些层是奢侈层

### 如果没通过

说明还在“想法”阶段，不要进入资产制作。

---

## 4. 阶段 3：资产规划

目标：
- 把方案转成制作清单

使用：
- `references/asset-planning-checklist.md`
- `D:/Skills/skills/unreal-material-artist/references/texture-strategy-and-ai-prompts.md`

这一步要产出：
- 主纹理清单
- 材质清单
- 材质实例清单
- Niagara System / Emitter 清单
- 命名方案
- 低配版清单

### 通过标准

- [ ] 主资产已列出
- [ ] 次级资产有必要性判断
- [ ] 低配版资产已考虑
- [ ] 命名规范已明确

### 如果没通过

实现阶段会频繁漏资产和返工。

---

## 5. 阶段 4：实现第一版

目标：
- 先搭出可运行的第一版

使用：
- `references/implementation-presets.md`
- `references/niagara-operations-and-workflows.md`
- `D:/Skills/skills/unreal-material-artist/references/material-recipes.md`

原则：
- 先主层
- 再辅层
- 再残留层

不要一上来把所有层都做满。

### 通过标准

- [ ] 主层单独成立
- [ ] 第一版能在场景里看
- [ ] 没有明显结构错误

### 如果没通过

说明还没到“Review”阶段，只是“还在搭骨架”。

---

## 6. 阶段 5：艺术与结构 Review

目标：
- 判断这个效果值不值得继续细化

使用：
- `references/review-checklist.md`
- `references/aesthetics-and-readability-strategy.md`
- `references/common-failure-cases.md`

这一步重点看：
- 好不好看
- 读不读得懂
- 结构是否合理
- 有没有明显翻车模式

### 通过标准

- [ ] 主视觉点明确
- [ ] 可读性成立
- [ ] 没有明显多余层
- [ ] 颜色、节奏、层次基本成立

### 如果没通过

不要直接进入 QA。

先回到：
- 方案判断
或
- 第一版实现

---

## 7. 阶段 6：QA 与验收

目标：
- 确认它真的可以交付

使用：
- `references/validation-and-qa.md`
- `references/mobile-checklist.md`
- `references/debugging.md`

这一步重点看：
- 距离
- 背景
- 同屏
- 平台
- 动画挂接
- 性能

### 通过标准

- [ ] 近景成立
- [ ] 远景仍可读
- [ ] 亮背景 / 暗背景都成立
- [ ] 同屏不崩
- [ ] 平台版本已覆盖
- [ ] 性能可接受

### 如果没通过

按问题类型退回：
- 表现问题 -> Review
- 结构问题 -> 实现
- 路线问题 -> 方案判断

---

## 8. 阶段 7：交付与归档

目标：
- 让成果能被复用

交付时应至少整理：
- 最终资产清单
- 使用说明
- 低配版说明
- 风险备注

归档时建议沉淀：
- 成功点
- 失败点
- 可复用参数
- 下次可直接复用的模板

### 可用来归档的文档

- `references/case-studies.md`
- `references/common-failure-cases.md`
- `references/self-training-and-iteration-loop.md`

---

## 9. 失败时怎么回滚到上一步

这一步非常重要。

不同问题，不该都回滚到最开始。

### 问题类型 A：输入不清

回到：
- 阶段 1 需求输入

### 问题类型 B：路线选错

回到：
- 阶段 2 方案判断

### 问题类型 C：资产漏了

回到：
- 阶段 3 资产规划

### 问题类型 D：主层没立住

回到：
- 阶段 4 实现第一版

### 问题类型 E：看不清、没高级感

回到：
- 阶段 5 Review

### 问题类型 F：能看但不能交付

回到：
- 阶段 6 QA

---

## 10. 最小闭环

如果时间不够，最少也要做成这个闭环：

1. 需求补齐
2. 路线判断
3. 主层实现
4. Review
5. QA

这五步缺一不可。

---

## 一句话原则

标准工作流的核心不是把事情做慢，而是让每一轮迭代都知道自己现在处在哪一步、下一步该做什么、出了问题应该退回哪里。
