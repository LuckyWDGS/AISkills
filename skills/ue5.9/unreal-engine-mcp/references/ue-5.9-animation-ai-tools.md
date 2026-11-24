# UE 5.9：动画、AI、导航、输入与 UI 诊断

在 5.9.0 Preview / CL 60351404 的独立工程完成第二轮只读检查，比较安装为
5.8.4 / CL 58902052。随后在独立平台 Demo 中补验 BT / BB / Task / Character
作者与 ABP 副本编译保存。本页分别记录原只读检查和后续作者证据；只读轮没有
启动 PIE、应用输入、构建导航、启动日志记录或写资产。
原始 schema、源码对照、项目身份和结果保存在忽略的 session 目录。

## 目录

- [新增接入、迁移与延续能力](#新增接入迁移与延续能力)
- [AnimBlueprint：外层 pose 与规则可读，状态机容器限制仍在](#animblueprint外层-pose-与规则可读状态机容器限制仍在)
- [Behavior Tree / Blackboard / EQS：原生作者与证据范围](#behavior-tree--blackboard--eqs原生作者与证据范围)
- [NavMesh：可直接诊断配置，实际导航需要数据](#navmesh可直接诊断配置实际导航需要数据)
- [Input：资产配置读取与玩家输入控制是两条路线](#input资产配置读取与玩家输入控制是两条路线)
- [CommonUI / UMG：静态问题可查，运行诊断仍需会话](#commonui--umg静态问题可查运行诊断仍需会话)
- [技能接入边界](#技能接入边界)
- [验证记录](#验证记录)

## 新增接入、迁移与延续能力

| 当前 live owner | 注册数 | 与比较的 5.8 安装的关系 |
|---|---:|---|
| `AIModuleToolset.BehaviorTreeToolset` | 25（9 read / 16 write） | 旧 7 项 Python 检查接口迁为原生，并扩展 BT / Blackboard 作者能力 |
| `AIModuleToolset.EnvironmentQueryToolset` | 14（6 read / 8 write） | 比较的旧插件没有对应 EQS 作者合同 |
| `NavMeshToolset.NavMeshToolset` | 21，均为 read | 比较的旧 Toolsets 目录没有此插件；新增导航诊断接入 |
| `InputToolset.InputToolset` | 2（1 read / 1 write） | 新增本地玩家输入查询和按下/保持/释放接入；依赖玩家实例 |
| `CommonUIToolset.CommonUIToolset` | 15（7 read / 8 write） | 新增激活树、输入路由、焦点、绑定与事件诊断/控制接入 |
| `UMGEditor.UMGDebuggerSubsystem` | 6（2 read / 4 write） | 比较的旧 UMGEditor 源码没有该 subsystem；新增生命周期记录接入 |
| `UMGEditor.WidgetBlueprintEditorSubsystem` | 22（6 read / 16 write） | 旧 UMGToolSet 的部分作者工作流迁至原生；不能把 22 项全算新功能 |
| `WidgetAnimationToolset.WidgetAnimationToolset` | 10（3 read / 7 write） | 新的独立工具插件；与原生 MovieScene 工具组合编辑 UI 动画 |
| `WidgetStaticAnalysisToolset.WidgetStaticAnalysisToolset` | 5，均为 read | 新的静态树、委托、属性覆盖和 ViewModel 连接分析接入 |

这些注册数已包含在项目总 inventory 内，不是功能通过数。导航、Enhanced
Input、CommonUI、EQS 和 UMG 本身在旧版引擎已存在；此处“新增”指所比较安装
提供的 MCP 控制界面。插件目录变化不能替代 live schema，也不能证明完整工作流。

大量旧 Sequencer 封装已迁至原生 owner，参见
[Control Rig / 音频媒体审计](ue-5.9-audio-media-tools.md) 和
[Sequencer 版本参考](../../unreal-sequencer/references/ue-5.9-sequencer.md)。

静态盘点还应搜索 **`AIRuntimeCallable`**：本构建 Input 和 NavMesh 使用此标记。
只计 `AICallable` 会把这些已注册工具错报为零。源码声明数和 live 数仍应分开保存。

## AnimBlueprint：外层 pose 与规则可读，状态机容器限制仍在

对两个现有 AnimBlueprint 做了代表读取：父类均为 AnimInstance；
`ListGraphs` 分别返回 2 和 18 个图。逐一使用返回的图引用，而不是显示名，
通过 `ObjectToolset.GetClass`、`BlueprintToolset.FindNodes` 和 `GetNodeInfos`
检查实际类别、节点及 pin。

- Copy-pose ABP 的外层 Root / CopyPoseFromMesh / ControlRig 可读。
- 另一 ABP 的外层 Root / StateMachine / cached pose / Slot / ControlRig 可读，
  每个 state 的 pose 图和 transition-rule 图中的 K2-derived 节点也可读。
- 两个类别为 `/Script/AnimGraph.AnimationStateMachineGraph` 的容器图均返回
  `FindNodes=[]`，`ObjectToolset.ListProperties=[]`。这不表示没有状态或过渡。

5.9 原生 `FindNodes` 的实现仍以 `TArray<UK2Node*>` 接收 `ListAllNodes`。
pose 节点可派生自 UK2Node，状态机内的 state/entry/transition 节点则不是这一
继承链。schema 的返回类型写作 UEdGraphNode，也不能证明实现已枚举所有节点。

因此，扩展已有逻辑时先读取可见的 EventGraph、pose 和 rule graph；不要在空结果
基础上重建或替换生产状态机。完整 state/conduit/transition 拓扑读取和作者操作
仍须针对确切缺口查公开编辑器 API。只读轮没有验证其写入、ABP 编译或运行时
转换；后续仅复制既有 ABP 并成功编译，未据此宣称状态机拓扑作者通过。

通过官方 `get_symbol` 已找到 `AnimBlueprintFactory`、`AnimationLibrary`、
`AnimGraphNode_StateMachine`、`AnimStateNode` 和 `AnimStateTransitionNode`。
找到类名不是编辑工作流通过；本构建的 `AnimationStateMachineGraph` 没有同名
Python 顶层 symbol，不能把 UClass 路径机械改成 `unreal.<name>`。

`AnimationStateMachineLibrary` 尤其容易误判：其公开函数接受
`AnimUpdateContext` / `AnimNodeReference`，处理运行中的节点上下文，不是编辑器
state topology 作者库。比较的 5.8 / 5.9 头文件字节完全相同。仅按名字发现这个库，
不能称为 5.9 新增状态机编辑能力。对 AnimGraph、AnimationBlueprintEditor、
Persona、AnimationEditor 四个已比较源码目录的两类 Callable 标记搜索也未发现
独立作者合同；该 scoped 搜索不是“整个引擎无此 API”的证明。

现有通用资产反射路线也已复验：读取 AnimSequence 的 skeleton / rateScale、
BlendSpace 的 27 个 sample 和 Direction / Speed 轴（-180–180、0–600），以及
Montage 的 Arms slot 与 animation segment。这些是已有资产读取能力，不能算新
专用动画工具或播放验收；Notify、Montage sections 等字段若未被枚举，按实际
公开 `AnimationLibrary` API 查证，不要猜属性名。

## Behavior Tree / Blackboard / EQS：原生作者与证据范围

两类 live schema 均已取回。BT 提供创建树和 Blackboard、root/composite/task/
decorator/service 增删重排、Blackboard key 定义及节点 key selector；EQS 提供
query、option/generator、test 的创建、读取、重排、移除和启用状态。

BT 的对象层次需区分：`BehaviorTreeGraphNode` 是编辑器图节点，`GetNodeInstance`
返回实际 BTNode；不能把其中一种引用交给另一种参数。设置 selector 前先查
`GetAllowedBlackboardKeys(node, selectorPropertyName)`，并使用真实 selector
属性名。EQS 同样区分 graph node 与 option/generator/test instance。

已在独立候选范围完成过的作者路径，详见 [Gameplay AI 与动画](gameplay-ai-animation.md)：

- 创建 Character、AIController、两个 BTTask 蓝图、BT、BB，独立复制 locomotion
  ABP；五个 Blueprint/ABP 均以 `bWarningsAsErrors=true` 编译成功。
- 创建 Vector/Float/Bool/Name/Int 五个 BB key，绑定 BT；读回 Root→Sequence→
  初始化→持续任务的顺序，以及实际 task class 和 key names。
- 保存全部七个候选包并确认 clean，逐个重载；读回角色默认值、Mesh/AnimClass、
  Y 平面约束实际 normal、Pawn overlap 与 WorldStatic block。
- 原生中文分类/提示、公共函数、模块注释和仅日志诊断可作者；DSL 布局经原生
  坐标调整与前后逻辑签名比较。lint 仍有共享数据的长线/交叉提示，不能称全部通过。
- `DebugLog(Message)` 保持签名，范围 Edit 增加 ERROR 前缀强制输出；四个蓝图再次
  编译保存。CDO 编辑器求值中，debug=false 时四条 ERROR 均实际写入日志，普通
  信息均抑制。这是编辑器函数求值证据，不能替代失败路径的 PIE 触发验证。

这些是结构、编译和持久化证据。BT 执行、BB runtime 值、巡逻、动画、受击与清理
需要独立 PIE cases；EQS 作者、评分/结果仍未执行。已有 5.8 inspection-only
描述应以当前 schema 修正，不能改写为“39 项已测试可用”。

StateTree 是另一种资产与状态系统，其候选创建、绑定和编译结果见
[StateTree / PCG](ue-5.9-statetree-pcg.md)，不可据此替代 BT、EQS 或 ABP 的验证。

## NavMesh：可直接诊断配置，实际导航需要数据

六项代表读取成功：`ListWorlds`、`ListSupportedAgents`、`ListNavData`、
`ListNavBoundsVolumes`、`GetNavigationSystemInfo`、`GetNavMeshBuildStatus`。
使用 `ListWorlds` 返回的 Editor world 引用，显式传给后续操作。

当前场景存在 NavigationSystemV1，配置了 Default agent，半径 35 cm、高度
144 cm，查询 extent 为 (50,50,250)，指定 RecastNavMesh。实际 nav data、
bounds volume 和 mainNavData 均为空；没有构建任务、dirty area 或锁定。
这证明配置/空状态查询可用，没有证明场景已可寻路。

其余 schema 可以按世界/agent/navData 查询路径、投影、raycast、poly/tile、可达区
域、障碍/links/modifiers/invokers 等。

不要从工具名字推断默认参数。本构建部分参数即使源码有默认值，在 live schema 仍是
required。空 navData 的成功返回不能算寻路数值验收。

## Input：资产配置读取与玩家输入控制是两条路线

`InputToolset` / EnhancedInput 插件均启用，两项工具也已注册。但它是
`ULocalPlayerSubsystem` 的实例派发：没有 PIE/Game 本地玩家时，读取
`IsInputApplied` 会返回 dispatch target 不存在。

按当前 schema：

- `ApplyInput(entries,durationSeconds)` 同时按下若干 action/key、保持后释放，
  完成代表释放已做。每项只能设置 action 或 key；注入值非零，维数遵循
  Boolean/Axis1D/Axis2D/Axis3D。duration=0 仍有一个真实 tick，属于写入。
- `IsInputApplied` 的 Key 分支读取 PlayerInput pressed 状态；Action 分支按
  实现检查 continuous injection 是否存在，**不是任意 gameplay action 的
  Triggered/Completed 状态观测器**。不能用它单独证明输入事件逻辑通过。

这些语义来自 live schema 和对应安装实现，实际按下、持续、释放、中断与游戏
逻辑均未执行。后续输入测试先明确玩家、world、mapping context 和可观测输出，
再按任务许可运行；新工具存在不意味着输入资产作者 helper 已完成。

资产配置的旧路线仍有效：`AssetToolset.FindAssets` 搜索 InputAction / IMC，
`ObjectToolset.ListProperties` 后用真实属性名读取。实测 IA_Move 为 Axis2D，
action 级 triggers/modifiers 为空；IMC 默认表有 13 项，含 SpaceBar→Jump 与
W/S/A/D→Move 和对应 modifier 引用。

两版 InputMappingContext 头文件也字节相同，这不是 5.9 新的数据布局。继续检查
`mappingProfileOverrides`、添加 context 的逻辑/优先级、消费与输入模式；配置表不
代表玩家已启用。

## CommonUI / UMG：静态问题可查，运行诊断仍需会话

CommonUI 的事件 logger 状态读取成功：未记录、事件/丢弃数均 0、订阅玩家 0。
`GetActivatableTree` 明确返回没有 PIE。

`UMGDebuggerSubsystem` 的 lifetime logger 状态和事件读取成功：未记录、未抓
invalidation、记录/丢弃为 0、events=[]。空 recorder 是可读取的空状态，
不是 widget 构建/销毁/失效生命周期通过。后续收集应限定时段/容量，并分辨
开始记录、清空和停止等写操作。

`WidgetStaticAnalysisToolset.TraceWidgetPropertyOverrides` 对已存在的中文测试
WBP 只读运行成功：返回 2 个属性、4 段来源链、2 个确定 winner，以及 2 条预期
Redundant。Text 的生效来源是 WidgetTreeArchetype，返回原中文本地化值。
native default 被 archetype 覆盖是正常层级关系，不能把每条 Redundant 都报为 bug。

该工具将静态可发现的图写入、class defaults、archetype 和 binding 合并，按
每个 widget/property 分组。按合同，最高 Order 的 Applied 为 winner；没有
Applied 时只是 uncertain guess。保留 `applicationStatus` / `bCertain` 和来源，
不要把推断的 winner 当作实际运行时最后赋值或视觉验收。

UMG widget 作者和 animation 的首轮创建/编译/关键帧结果见
[编辑器工具审计](ue-5.9-editor-tools.md)。

## 技能接入边界

本分支可通过版本感知共享 client 使用这里的实时原生工具和官方 Python；
本页提供已验证读取的选路与失败解释，并链接实际完成的 BT / BB / Task 作者流程。
没有把未执行的 EQS 作者、Input 应用、NavMesh 空间查询、CommonUI runtime 或
完整 ABP state topology 包装成已验收 helper。
未来实现按实际需要逐项发现 schema、制作独立候选、读取回证，再分别记录编译、
编辑器求值、视觉与运行结果；不要只迁移旧工具名的大小写。

第二轮只读检查前后 actor 数为 129、选择为空、dirty map/content 为空，未运行 PIE。
这些是该轮的状态证据；后续 Demo 作者不改变其历史含义，也不提供 UE 5.8 live
回归结论。

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404。

**新增接入、迁移与延续能力**

- `AnimationAssistantToolset` 没有变成完整 gameplay ABP 编辑器：本次注册的
  `animation_toolset.toolsets.controlrig.ControlRigTools` 仍为 44 项，两版
  decorated 方法集合相同；另有 4 项 `SequencerDirectorToolset`。

**Behavior Tree / Blackboard / EQS：原生作者与证据范围**

- 只读轮在 `/Game` 和全部挂载内容中没有找到 BehaviorTree、BlackboardData 或
  EnvQuery，当时仅确认注册、schema 与空搜索。后续平台 Demo 使用独立候选范围，实
  际完成以下作者路径，详见 [Gameplay AI 与动画](gameplay-ai-animation.md)：

**NavMesh：可直接诊断配置，实际导航需要数据**

- 21 项均声明 read；本轮没有构建导航、放置 bounds，亦未执行需要 navmesh 的路径和
  空间查询。
- 使用完整 schema；本轮 build-status 调用接受 `navData:null`、 `agentName:""` 和
  显式 world。

**Input：资产配置读取与玩家输入控制是两条路线**

- 本轮实际遇到这个会话限制，没有调用 `ApplyInput`，也没有为读取而启动 PIE。
- 默认表位于 **`defaultKeyMappings.mappings`**，顶层已弃用的 `mappings` 本次为
  空。

**CommonUI / UMG：静态问题可查，运行诊断仍需会话**

- 输入路由、focus、action binding 和激活树必须结合实际 player/router；本轮没有激
  活/关闭 widget、锁输入类型、刷新焦点、打开树可视化或启动事件日志。
- 本轮只补验证上述静态覆盖分析与空诊断状态，没有 MVVM fixture、runtime
  ViewModel、HUD 布局/交互或生命周期录像。
