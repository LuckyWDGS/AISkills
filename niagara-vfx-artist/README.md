# Niagara VFX Artist Skill 维护说明

## 这是什么

这是一个给 Codex / AI 代理使用的自定义 Skill，主题是 Unreal Engine Niagara 特效设计、实现、分析和优化。

现在这个目录已经整理成了比较标准的 Skill 结构：

```text
D:\Skills\niagara-vfx-artist\
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
└── references/
    ├── core.md
    ├── platform-optimization.md
    ├── advanced-techniques.md
    ├── examples.md
    ├── quick-reference.md
    ├── material-recipes.md
    ├── debugging.md
    └── common-effect-patterns.md
```

另外，这个目录已经通过目录链接接入到 Codex 技能库：

`C:\Users\QY\.codex\skills\niagara-vfx-artist`

所以你以后只需要维护这一份源目录，不需要复制多份。

## 每个文件是干什么的

### `SKILL.md`

这是 **Skill 的核心入口文件**，也是最重要的文件。

它的作用：
- 定义这个 Skill 的名字和描述
- 告诉 AI “什么情况下应该使用这个 Skill”
- 告诉 AI “遇到不同类型问题时，该去读哪份 reference 文档”
- 规定输出风格和工作流程

什么时候改它：
- 你想修改这个 Skill 的定位
- 你想增强触发条件，让 AI 更容易在合适场景下用到它
- 你想调整回答结构、工作方式、优先级

不建议往里面堆太多长篇知识。
这个文件最好保持“轻入口”，详细内容放到 `references/`。

### `README.md`

这是 **给你自己看的维护说明文档**，不是主要给 AI 执行时读取的。

它的作用：
- 说明目录结构
- 解释每个文件负责什么
- 帮助你以后维护时快速定位该改哪里

什么时候改它：
- 目录结构变化了
- 你增加了新的 reference 文件
- 你想补充维护约定或使用说明

### `agents/openai.yaml`

这是 **Skill 的界面元数据文件**，主要给技能列表或 UI 展示使用。

它的作用：
- 定义 Skill 的显示名称
- 定义简短说明
- 定义默认提示词
- 控制是否允许隐式调用

什么时候改它：
- 你想改显示名
- 你想改短描述
- 你想改默认调用提示

一般不需要频繁改。

## `references/` 目录是干什么的

`references/` 里放的是 **详细知识文档**。  
原则上，AI 在真正处理任务时，会先看 `SKILL.md`，再按需要读取这里的文件。

这样做的好处：
- 结构更清晰
- 主入口更轻
- 后续扩展更容易
- 不同任务只读取需要的部分，不会把所有内容一次塞进上下文

### `references/core.md`

这是 **主知识文档**。

主要内容：
- Skill 的核心定位
- 特效设计原则
- Niagara 基础实现思路
- 材质/HLSL 方向
- 常见输出格式

什么时候改它：
- 你想补充常用的 Niagara 设计方法
- 你想调整“AI 应该怎么回答特效需求”
- 你想加入新的核心方法论

### `references/platform-optimization.md`

这是 **平台优化专用文档**。

主要内容：
- PC 平台建议
- Android 平台限制
- 粒子预算
- 材质指令预算
- LOD / Culling / Scalability 策略

什么时候改它：
- 你有新的性能预算经验
- 你想细化某个平台的优化策略
- 你想新增平台差异说明

### `references/advanced-techniques.md`

这是 **高级技巧文档**。

主要内容：
- Flipbook 工作流
- Flow Map
- 通道打包
- HLSL / Scratch Pad
- 纹理生成与优化

什么时候改它：
- 你增加新的高阶技术方案
- 你想沉淀某种成熟工作流
- 你想补充高级技巧案例

### `references/examples.md`

这是 **示例对话文档**。

主要内容：
- 用户怎么提需求
- AI 怎么组织回答
- 完整案例长什么样

什么时候改它：
- 你想让 AI 更贴近你的表达方式
- 你想补充新的典型案例
- 你发现某类任务的输出格式需要被“示范”

这是很有价值的文件，因为它会直接影响 AI 的回答风格。

### `references/quick-reference.md`

这是 **速查文档**。

主要内容：
- 技术术语速查
- 平台基准速查
- 常见能力概览

什么时候改它：
- 你想加简短规则和速记表
- 你想补充容易忘的参数范围
- 你想做成“快速翻阅”的参考页

适合放短小、密集、方便检索的信息。

### `references/material-recipes.md`

这是 **材质配方文档**。

主要内容：
- 参数命名约定
- 护盾类材质
- 爆炸和能量球材质
- 烟雾材质
- Ribbon 拖尾材质
- 冲击波材质
- 移动端材质简化方案
- 节点搭建模板
- 参数推荐值

什么时候改它：
- 你总结出新的成熟材质搭法
- 你想积累“某种效果一般怎么做”
- 你想让 AI 更快产出可落地的材质思路

这个文件更偏“可复用配方库”。
现在它也兼顾“节点模板库”和“参数参考库”。

### `references/debugging.md`

这是 **调试与排错文档**。

主要内容：
- 粒子不显示
- 材质异常
- 节奏和运动不对
- 排序问题
- 性能超预算
- PC / Android 表现不一致
- 快速检查清单
- 平台排查清单

什么时候改它：
- 你碰到了新的常见坑
- 你想把排查思路沉淀下来
- 你想让 AI 遇到报错或异常现象时更会定位问题

这个文件更偏“问题定位手册”。
现在它也可以当成“实战检查表”来用。

### `references/common-effect-patterns.md`

这是 **常见特效模板文档**。

主要内容：
- 爆炸模板
- 护盾模板
- 拖尾模板
- 命中特效模板
- 法阵模板
- 火焰模板
- 烟雾模板
- 能量球模板
- 每类模板的建议参数范围
- PC 版 / Android 版双版本起步方案

什么时候改它：
- 你想沉淀某一类效果的标准做法
- 你想让 AI 接到常见需求时更快进入正题
- 你想把常见效果拆成“分层 + 发射器 + 材质 + 节奏”的固定模板

这个文件更偏“方案骨架库”。
现在它也兼顾“参数起点库”。

### `references/mobile-checklist.md`

这是 **移动端落地清单文档**。

主要内容：
- Android / 低端机上线前总检查
- Niagara 系统检查
- 材质检查
- 纹理检查
- Overdraw 检查
- LOD / Culling 检查
- 多特效同屏检查
- 不同档位建议
- 红线清单

什么时候改它：
- 你想沉淀移动端上线前检查流程
- 你想把 PC 方案压成 Android 可上线版本
- 你想补充某类设备上的经验规则

这个文件更偏“移动端交付检查表”。

### `references/common-failure-cases.md`

这是 **常见翻车案例文档**。

主要内容：
- 过曝发白
- 烟雾糊屏
- 护盾像塑料壳
- 爆炸没有冲击感
- 拖尾像面条
- 能量球像灯泡
- 命中特效没打击感
- 法阵像贴图
- 移动端爆预算
- 多特效同屏一团乱

什么时候改它：
- 你想沉淀最常见的失败案例
- 你想把“症状 -> 原因 -> 修复”经验固定下来
- 你想让 AI 更像一个会复盘问题的特效搭档

这个文件更偏“失败案例复盘库”。

### `references/review-checklist.md`

这是 **特效审查清单文档**。

主要内容：
- 第一眼检查
- 视觉设计检查
- Niagara 结构检查
- 材质检查
- 可读性检查
- 性能检查
- 平台检查
- 复盘输出建议

什么时候改它：
- 你想建立统一的特效 review 标准
- 你想让 AI 更系统地审查别人做的效果
- 你想把“看感觉”变成“有结构的点评”

这个文件更偏“特效评审标准表”。

### `references/niagara-fundamentals.md`

这是 **Niagara 基础逻辑文档**。

主要内容：
- Niagara 的基本组成
- System / Emitter / Module / Parameter 的关系
- Niagara 的执行逻辑
- 数据和命名空间
- Renderer 的理解方式
- 怎么从参考图反推 Niagara 结构
- 怎么判断需要多少个 Emitter

什么时候改它：
- 你想加强这套 skill 的 Niagara 基础认知
- 你想让 AI 更稳定地从图片或设计图反推实现
- 你想沉淀官方概念和你自己的理解方式

这个文件更偏“Niagara 理论底座”。

### `references/reference-analysis-output-spec.md`

这是 **参考图分析输出规范文档**。

主要内容：
- 参考图 / 视频输入时应输出什么
- 思维导图要求
- 流程配图要求
- 具体实现路径要求
- 最终效果说明要求

什么时候改它：
- 你想规范“参考图分析交付格式”
- 你想让 AI 不只是分析，还能给出完整落地包
- 你想让输出更像方案文档，而不是零散回答

这个文件更偏“参考图交付规范”。

### `references/art-direction-patterns.md`

这是 **艺术方向模式库文档**。

主要内容：
- 神圣
- 黑暗
- 科幻
- 元素通用
- 治疗
- 毒
- 电
- 火
- 冰

什么时候改它：
- 你想强化这套 skill 的艺术指导能力
- 你想让 AI 更会把抽象风格词转成具体视觉语言
- 你想沉淀不同世界观下的 VFX 风格拆解方法

这个文件更偏“VFX 艺术指导库”。

### `references/texture-strategy-and-ai-prompts.md`

这是 **纹理策略与 AI 提示词文档**。

主要内容：
- 单张图 / Flipbook / 随机格子图集怎么选
- 火焰、余烬、烟雾、闪电分别适合什么纹理方案
- Niagara 中怎么接入 SubUV / 图集
- 给外部 AI 生成纹理的提示词模板

什么时候改它：
- 你想加强这套 skill 对纹理资源的判断能力
- 你想让 AI 不只是说“需要纹理”，而是说清楚“要哪种纹理”
- 你想把外部 AI 生成纹理这一步也纳入标准流程

这个文件更偏“纹理决策与素材生成指南”。

### `references/fluids-and-flowmaps.md`

这是 **流体与 Flow Map 方案文档**。

主要内容：
- 什么时候用 Flow Map
- 什么时候用 Niagara Fluids
- 什么时候该烘成 Flipbook
- Niagara Fluids 的主要模拟类型
- 流体关键参数怎么理解和怎么调
- 流体参考图该怎么分析

什么时候改它：
- 你想加强这套 skill 对高级流体特效的判断能力
- 你想让 AI 更清楚地区分“假流体”和“真流体”
- 你想沉淀 Niagara Fluids 调参与方案选择经验

这个文件更偏“高级流体决策指南”。

### `references/fluids-recipes.md`

这是 **流体效果方案库文档**。

主要内容：
- 水流表面方案
- 瀑布方案
- 水花喷溅方案
- 烟流方案
- 火流方案
- 熔岩流方案
- 每种对应的推荐路线

什么时候改它：
- 你想沉淀流体类效果的成熟做法
- 你想让 AI 针对不同流体场景直接给可执行路线
- 你想把官方能力和社区经验整合成可复用方案

这个文件更偏“流体实现路线库”。

### `references/fluids-parameters.md`

这是 **流体参数调节手册文档**。

主要内容：
- Grid Cell Size
- Pressure Iterations
- Density
- Temperature
- Buoyancy
- Turbulence / Noise
- Collision
- Dissipation
- 调大 / 调小 / 视觉变化

什么时候改它：
- 你想把 Niagara Fluids 的调参经验沉淀下来
- 你想让 AI 更像真正会调流体的人，而不只是会说概念
- 你想把“参数变化和视觉结果”的对应关系固定下来

这个文件更偏“Niagara Fluids 调参手册”。

### `references/fluids-troubleshooting.md`

这是 **流体排错手册文档**。

主要内容：
- 烟太松
- 火不往上走
- 水花不成形
- 细节太糊
- 结果太块
- 模拟很好看但游戏里太贵
- 排查顺序

什么时候改它：
- 你想沉淀 Niagara Fluids 的常见问题处理经验
- 你想让 AI 不只是会调参数，还会排错
- 你想把“症状 -> 检查项 -> 修复方向”固定下来

这个文件更偏“流体问题排查库”。

### `references/fluids-production-pipeline.md`

这是 **流体生产流程文档**。

主要内容：
- 从参考到最终资产的完整流程
- 什么时候直接材质做
- 什么时候先做流体模拟
- 什么时候烘成 Flipbook
- 什么时候进 Niagara
- 什么时候做低配版

什么时候改它：
- 你想把流体类效果的完整生产经验沉淀下来
- 你想让 AI 不只是会判断和调参，还会规划完整制作路线
- 你想把团队流程标准化

这个文件更偏“流体生产管线指南”。

### `references/non-fluid-effects-playbook.md`

这是 **非流体特效方案库文档**。

主要内容：
- 命中特效
- 刀光 / Slash
- 投射物
- 光束 / Beam
- 护盾
- 法阵
- Portal
- Buff / Aura
- Sparks / Debris
- 可读性与审美原则

什么时候改它：
- 你想加强这套 skill 对常规游戏特效的理解
- 你想让 AI 不只会做流体，也会做大量常见非流体效果
- 你想沉淀审美与结构的共性规律

这个文件更偏“非流体特效设计库”。

### `references/niagara-operations-and-workflows.md`

这是 **Niagara 操作与工作流文档**。

主要内容：
- 模板还是空白开始
- System / Emitter 组织方式
- 模块堆栈思维
- User Parameters
- Scratch Pad
- Renderer 工作流
- 动画挂接
- Effect Type 预算
- 实战工作习惯

什么时候改它：
- 你想让这套 skill 更懂 Unreal / Niagara 的实际操作
- 你想让 AI 更像会落地生产的 Niagara 使用者
- 你想沉淀团队级工作流经验

这个文件更偏“Niagara 实操工作流手册”。

### `references/aesthetics-and-readability-strategy.md`

这是 **审美与可读性策略文档**。

主要内容：
- 焦点与视觉重心
- 形状语言
- 色彩与明度层级
- 时间节奏
- 主层 / 辅层 / 残留层
- 背景适配
- 风格化与写实差异

什么时候改它：
- 你想让这套 skill 更像会判断审美的特效艺术家
- 你想加强游戏特效的可读性标准
- 你想把“高级感”变成可执行规则

这个文件更偏“VFX 审美判断手册”。

### `references/self-training-and-iteration-loop.md`

这是 **自我训练与迭代闭环文档**。

主要内容：
- 输入参考时怎么训练自己
- 输出前怎么自检
- 输出后怎么复盘
- 审美训练法
- 结构训练法
- 节奏训练法
- 长期进化策略

什么时候改它：
- 你想让这套 skill 具备更强的自我迭代能力
- 你想把经验逐步固化成稳定方法
- 你想让输出质量越来越稳

这个文件更偏“自我进化方法库”。

### `references/case-studies.md`

这是 **案例库文档**。

主要内容：
- 真实火把
- 护盾
- 命中特效
- 法阵
- 河流表面
- 瀑布
- 水花喷溅

什么时候改它：
- 你想把零散知识点真正串成完整方案模板
- 你想让 AI 更像一个成熟的案例库，而不是只会临时分析
- 你想在反复出现的需求上更快进入正题

这个文件更偏“完整方案模板库”。

### `references/implementation-presets.md`

这是 **实现预设库文档**。

主要内容：
- 命中特效预设
- 火把预设
- 护盾预设
- Slash / 拖尾预设
- 法阵预设
- 常见 Renderer 起步值

什么时候改它：
- 你想让 AI 更快从空白 Niagara 起手
- 你想沉淀团队统一的第一版实现骨架
- 你想减少“每次都从零拼 stack”的重复劳动

这个文件更偏“Niagara 起手模板库”。

### `references/asset-planning-checklist.md`

这是 **资产规划清单文档**。

主要内容：
- 资产类型总表
- 最小可用版清单
- 完整版清单
- 低配版清单
- 命名建议
- 实战检查项

什么时候改它：
- 你想把方案真正转成制作清单
- 你想减少漏资产、漏低配版、漏命名规范的问题
- 你想让 AI 更像 production planning 工具

这个文件更偏“特效资产制作清单”。

### `references/validation-and-qa.md`

这是 **特效验收与 QA 文档**。

主要内容：
- 近景 / 中景 / 远景检查
- 亮背景 / 暗背景检查
- 同屏多特效检查
- 平台版本检查
- 动画挂接检查
- 性能验收
- 可读性验收
- 最终通过标准

什么时候改它：
- 你想把“做完了”变成真正的交付标准
- 你想建立统一验收口径
- 你想让 AI 不只会做方案，也会做最终验收

这个文件更偏“特效交付验收手册”。

### `references/request-intake-template.md`

这是 **特效需求输入模板文档**。

主要内容：
- 必要信息
- 推荐补充信息
- 常见需求模板
- 缺条件时的默认假设
- 输出前确认清单

什么时候改它：
- 你想减少因为输入不完整导致的返工
- 你想让 AI 在需求阶段就更稳定
- 你想把常见特效需求补齐成可执行输入

这个文件更偏“需求收集与补全模板”。

### `references/production-workflow-map.md`

这是 **特效标准工作流文档**。

主要内容：
- 需求输入
- 方案判断
- 资产规划
- 第一版实现
- 艺术与结构 Review
- QA 与验收
- 交付与归档
- 出问题时回滚到哪一步

什么时候改它：
- 你想把这套 skill 从知识库推进成更标准的生产系统
- 你想减少返工
- 你想把输入、实现、Review、QA、交付串成固定闭环

这个文件更偏“特效生产工作流手册”。

### `references/engine-integration-checklist.md`

这是 **引擎接入检查清单文档**。

主要内容：
- 动画 Notify 接入
- 蓝图参数驱动
- User Parameters 暴露
- 挂点与空间检查
- Effect Type / Scalability
- 平台与低配接入
- 最终接入检查表

什么时候改它：
- 你想减少“特效本身没问题，但接进游戏就出问题”的情况
- 你想把 Unreal 内的最后一公里接入流程标准化
- 你想让 AI 更像真正懂落地集成的人

这个文件更偏“特效引擎接入手册”。

### `references/style-consistency-guide.md`

这是 **项目级特效风格统一指南**。

主要内容：
- 什么叫同一套视觉语言
- 项目级必须统一的规则
- 技能级必须区分的规则
- 阵营 / 属性 / 职业的统一与差异
- 风格漂移的典型症状
- 项目级检查清单

什么时候改它：
- 你想让这套 skill 从“单效果专家”提升到“项目级 VFX 指导”
- 你想统一一整套技能和场景特效的风格
- 你想建立阵营、属性、功能之间的统一与差异规则

这个文件更偏“项目级 VFX 风格控制手册”。

### `references/vfx-direction-bible-template.md`

这是 **VFX Direction Bible 模板文档**。

主要内容：
- 世界观风格
- 阵营差异
- 属性映射
- 技能等级差异
- 常驻 / 爆发边界
- UI / 场景 / 技能三类特效关系
- 技术路线边界

什么时候改它：
- 你想让这套 skill 具备更强的 VFX Lead / 项目负责人视角
- 你想在项目立项阶段就把风格和规则定清楚
- 你想统一多个特效师、多条资产线的输出

这个文件更偏“项目级 VFX 总纲模板”。

## 以后怎么维护最合适

推荐你按下面这个原则维护：

- 改定位、改规则、改入口：改 `SKILL.md`
- 改详细知识：改 `references/` 下对应文件
- 改展示名称和默认 prompt：改 `agents/openai.yaml`
- 改维护说明：改 `README.md`

## 推荐维护习惯

### 1. 不要把所有内容都塞进 `SKILL.md`

`SKILL.md` 最好只保留：
- 触发说明
- 工作流程
- 输出要求
- reference 导航

### 2. 长文尽量放进 `references/`

比如这些内容就适合放在 `references/`：
- 平台优化细节
- HLSL 经验
- 特定效果拆解
- 大量案例

### 3. 一个文件只做一类事情

这样以后你会非常好找：
- 核心规则看 `SKILL.md`
- 平台优化看 `platform-optimization.md`
- 高级技巧看 `advanced-techniques.md`
- 示例看 `examples.md`
- 材质配方看 `material-recipes.md`
- 排错看 `debugging.md`
- 常见模板看 `common-effect-patterns.md`

### 4. 新增内容时优先想“应该归到哪类”

如果你以后还要扩展，可以继续往 `references/` 新增文件，例如：
- `references/material-recipes.md`
- `references/common-effect-patterns.md`
- `references/debugging.md`
- `references/mobile-checklist.md`

然后在 `SKILL.md` 里把它们加进导航即可。

## 如果你以后持续修改

你现在修改的主目录是：

`D:\Skills\niagara-vfx-artist`

由于技能库中挂的是这个目录的链接，所以：

- 你改这里
- Codex 读到的就是最新版本
- 不需要额外同步副本

## 当前建议

如果你后面继续加强这个 Skill，我建议优先补这几类内容：

1. 常见特效类型模板
   例如：爆炸、护盾、拖尾、命中特效、法阵、火焰、能量球、烟雾。

2. 材质配方库
   例如：Additive 护盾、Fresnel 外轮廓、噪声扰动、UV 流动、冲击波遮罩。

3. 调试与排错文档
   例如：粒子不显示、排序问题、过曝、移动端丢效果、性能超预算。

4. 更贴近你工作习惯的案例
   让 AI 学会你喜欢的表达方式、参数粒度和设计思路。

## 一句话总结

你以后可以把这个目录理解成：

- `SKILL.md`：AI 的总入口
- `references/`：AI 的知识库
- `agents/openai.yaml`：Skill 的展示配置
- `README.md`：给你自己看的维护说明
