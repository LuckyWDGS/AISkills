# Gameplay AI 与角色动画：UE 5.9 作者流程

本页操作合同针对 5.9，5.8 须按该版本工具和 Python 参考实现，不能照抄调用。
用于交付可放入关卡的 AI 角色、Behavior Tree / Blackboard / Blueprint Task 和
配套动画。先读 [5.9 动画与 AI 合同](ue-5.9-animation-ai-tools.md)；Blueprint
语法和 revision 编辑见 [Graph DSL](ue-5.9-blueprint-python.md)，完整交付要求见
[Blueprint delivery standards](blueprint-delivery-standards.md)。

本流程在 5.9.0 Preview / CL 60351404 的独立平台 Demo 中验证了四个角色/控制器/
任务蓝图、BT、BB 和独立 ABP 副本的创建、结构读回、编译、指定保存及重载。
这不证明任意骨架、状态机作者、寻路或 multiplayer 已通过；运行证据单独记录。

## 目录

- [先明确 gameplay 合同](#先明确-gameplay-合同)
- [原生 BT / BB 作者与读回](#原生-bt--bb-作者与读回)
- [Task 生命周期与可观测行为](#task-生命周期与可观测行为)
- [反射默认值、EditCondition 与碰撞](#反射默认值editcondition-与碰撞)
- [Native Graph DSL 的实际参数陷阱](#native-graph-dsl-的实际参数陷阱)
- [独立 ABP 与动画验收](#独立-abp-与动画验收)
- [分层验收记录](#分层验收记录)
- [Windows 打包前的静态检查](#windows-打包前的静态检查)
- [验证记录](#验证记录)

## 先明确 gameplay 合同

把行为数据、移动、决策和动画分开：

| 资产/组件 | 职责与必要接口 |
|---|---|
| Character Blueprint | 公开初始化/更新/受击入口；出生位置、方向、速度、状态和可观测计数；调用 CharacterMovement |
| AIController Blueprint | 占有时 `RunBehaviorTree`；处理启动失败；解除占有与销毁时完成自己拥有的清理 |
| BTTask Blueprint | 任务生命周期、类型/引用检查、调用角色接口、同步此控制器自己的 Blackboard |
| Blackboard | 任务间的决策数据；定义类型、初值和实例共享规则，不当作持久存档 |
| AnimBlueprint | 从实际速度/加速度/MovementMode 推导动画；不在动画图中偷偷移动角色 |
| CharacterMovement / Capsule | 重力、地面、平面约束、移动模式、碰撞与 overlap |

例如横版巡逻先约定 X 为前进轴、Y 平面、Z 高度，公开 `InitializePatrol()`、
`PatrolStep()`、幂等 `Defeat()` 和 `bDefeated`。速度用 cm/s、范围用 cm；让范围/
速度/调试开关可实例编辑。平台宽度要容纳角色尺寸和刹车距离。修正关卡实例范围后，
两只 AI 均在带时间的采样中移动并转向；不能只凭 Brain 正在运行验收巡逻。

纯横版往返可以由 BT Task 调用 `AddMovementInput`，交给 CharacterMovement
积分、重力和扫掠碰撞；这种方案没有路径规划，不能声称验证了 NavMesh。
需要绕障/追踪/可达性时再使用导航，先确认 nav data 和 agent 配置。

踩踏判定由玩家统一处理：同一事件中读取敌人标记、双方高度和玩家下降速度，
调用敌人的公共受击接口，再反弹玩家。不要同时让两个 overlap handler 各自扣血。
碰撞策略应让 Pawn overlap 与 WorldStatic block 同时成立，视觉 Mesh 可无碰撞，
实际胶囊保持地面阻挡；还须启用双方相关组件的 overlap 生成。

踩踏失败时同时核对 CDO、组件模板、关卡实例和 PIE 实例的 profile、object type、
enabled、Pawn/WorldStatic response 与 overlap 开关。`MOVE_Walking` 本身不能证明
站在敌人头上；读取 CharacterMovement 的 `currentFloor` 或公开
`get_movement_base_object()`，确认实际支持面。台阶边缘与胶囊半径也可能使玩家
先落到邻近平台，尚未进入敌人的 overlap。先排除几何遮挡，再修改碰撞配置。

## 原生 BT / BB 作者与读回

从目标编辑器逐项获取完整 schema：`BehaviorTreeToolset`、`BlueprintToolset`、
`BlueprintDslToolset`、`ObjectToolset`、`AssetToolset`。写前确认项目绝对路径、
UE 构建、PIE=false 和候选包范围；没有完整 schema 时不猜参数。

本构建实际使用的原生路线：

1. `BlueprintToolset.Create` 以 `Character`、`AIController`、
   `BTTask_BlueprintBase` 为父类创建独立候选。
2. `BehaviorTreeToolset.CreateBehaviorTree` / `CreateBlackboardData` 创建数据资产；
   `AddBlackboardKey` 指定 `/Script/AIModule.BlackboardKeyType_<Type>`。
   实例数据默认 `bInstanceSynced=false`，除非共享确实是需求。
3. `SetBlackboard` 绑定树。`AddRootComposite` 添加 Sequence，`AddTask` 按顺序
   添加已编译的初始化任务和持续任务。不要重复运行无存在检查的 Add 脚本。
4. 用 `GetRootGraphNode` → `GetChildGraphNodes` 逐层验证兄弟顺序；用
   `GetNodeInstance` 取得实际 BTNode，再通过 `ObjectToolset` 读配置。
5. `GetBlackboard` 与 `GetBlackboardKeyNames` 证明绑定和 keys。引擎可能额外提供
   `SelfActor`，不能把它算成自建 key；同名还需核对类型和 parent-chain。

工具的 `folderPath` 不全是字符串：本构建 BT/BB 创建接受 `{ "path": ... }`，
Blueprint 创建则是字符串。不要复制相邻工具的参数形状。所有 `refPath` 都用
实际返回值，尤其是图节点和其内部任务实例；二者是不同对象。

`customDescription` 在本构建的 BTTask 实例不可编辑，只能写类默认对象；
`nodeName` 可写实际树里的任务实例。多属性 setter 可能先应用合法字段再报错，
所以遇到错误先读回，不能认为整次未写入。类默认值和已有实例分别验证。

## Task 生命周期与可观测行为

一次性初始化任务在 `ReceiveExecuteAI` 中验证 Pawn 和 Blackboard，记录出生中心、
设置状态后 `FinishExecute(true)`。失败分支明确 `FinishExecute(false)` 并输出诊断。

持续任务在 `ReceiveExecuteAI` 启动后保持 Running，通过 `ReceiveTickAI` 更新；
不要每帧 FinishExecute 造成整棵树反复初始化。实现 `ReceiveAbortAI` 时明确调用
`FinishAbort`，并释放本任务创建的 timer/委托。未使用 timer 不代表可以忽略别的
模块创建的生命周期资源。

初始化必须幂等。巡逻边界使用保存的出生中心；运行途中转向不重置中心。让
`PatrolTickCount`、`TurnCount`、当前方向和状态可读取，避免仅凭模型位置猜 BT
是否执行。控制器启动失败、Cast/引用失败等破坏合同的情况即使调试关闭也应留下
诊断；普通转向可受 `bDebugLog` 控制，不输出屏幕文字。

击败入口先改状态并停止移动/输入，立即禁用碰撞，再播放死亡表现并安排销毁；
重复调用不得重复发奖励或累加销毁任务。`SetLifeSpan` 只安排角色销毁，控制器、
任务资源和计分去重都须分别验证，不能从角色消失推断清理完整。

## 反射默认值、EditCondition 与碰撞

先 `ListProperties` / `GetPropertySchema`，再读、写、读回。CDO、组件模板和
已放置实例是不同作用域；编译和重载后重复核对真正使用的作用域。

- `ObjectToolset.SetProperties` 不是事务。一个字段失败不保证其他字段未写入。
  只修复观察到的差异；不重放整段创建/加节点步骤。
- EditCondition 开关单独设置并读回，例如先 `bConstrainToPlane=true`，随后再设
  `bSnapToPlaneAtStart` / 轴/原点；同一批里包含开关与依赖字段可能被拒绝。
- 读取实际 plane normal。轴 setting 的字符串读回不证明 movement 实际约束正确。
- 反射合同不覆盖的碰撞 channel 用官方 Python 公共 API，先查 `get_symbol`。
  本构建 setter 接受 `unreal.CollisionResponseType`；`CollisionResponse` 是另一
  struct，不能互换。读回每个关键 channel，而不只读取 profile 名。
- 本构建没有 `PrimitiveComponent.set_generate_overlap_events` /
  `get_generate_overlap_events` Python 方法。使用已发现的原生
  `bGenerateOverlapEvents` 属性合同，不猜方法。
- `GetPropertySchema` 描述 root 的子属性，scalar root（例如 `bDebugLog`）会拒绝；
  从其父对象/struct 查询，再取目标字段。schema 中没有实例编辑标志不能证明
  CDO 与 runtime 实例都允许相同写入。

## Native Graph DSL 的实际参数陷阱

先创建并编译函数签名，再作者其调用者。本构建在同一次全 DSL 写入中修改函数
参数并从其他图调用时，可能仍解析到旧 UFunction；先 `AddFunctionParam` 和编译
后再写调用图已验证可行。编译后重新获取 node/pin 引用。

外部 setter 的文档语序与实际 value/self 引脚语序可能不同。混用一个位置参数
Target 与后续关键字，也可能让 Target 被省略并接到第一个业务参数。使用真实
`Schema` 中的显式引脚名，例如：

```lisp
(set `CharacterMovementComponent.MaxWalkSpeed`
  :`self` (`self.CharacterMovement`)
  :`MaxWalkSpeed` (`self.MoveSpeed`))

(`SkeletalMeshComponent.PlayAnimation`
  :`self` (`self.Mesh`)
  :`NewAnimToPlay` "/Game/<Scope>/<DeathSequence>.<DeathSequence>"
  :`bLooping` false)

(`BlackboardComponent.SetValueAsFloat`
  :`self` (`AIController.Blackboard` OwnerController)
  :`KeyName` "Direction"
  :`FloatValue` Direction)
```

示例中的引用需替换为存在的资产；实际 pin 名仍以目标 schema 为准。写完 `Read`
canonical DSL，并读 native 两端连接；编译成功不能单独证明 Target 归属正确。
使用当前 revision 做范围编辑，拒绝根据旧文本覆盖整份生产图。

DSL 自动布局也需复核。此构建的自动排版曾产生逆向线和节点重叠；
`blueprint_lint.py` 的 native 读取可用，`blueprint_layout.py` 的写入为
`unported`。可复用其只读 `plan_layout` 算法后，用实时 `SetNodePosition` 写坐标，
并比较前后 node/pin/default/link 签名。重新包围自己移动的模块时，原生
`AddCommentBox(nodes=...)` 会建立成员；验证新框的文本/成员后才移除旧框。重载后的
空成员缓存只代表未知，不能为消除提示而打开编辑器或任意改生产注释框。

原生 comment 对象的 `GetPropertySchema` 还暴露 `nodeDetails`、`commentColor`、
`fontSize` 与 `moveMode`，本构建可由 `ObjectToolset` 写入并读回。使用短标题，
把用途、调用者、输入/输出及原模块说明放到 `nodeDetails`；重建框时一并保留样式。
以每个事件入口/函数为独立框可避免外层分发框与内层分支框互相覆盖；原分支 ID
可保留在说明中。完整 node/pin/default/link 签名还应在编译及保存后的新快照再次
比较，而不只在最后一次坐标写入后比较。

## 独立 ABP 与动画验收

复用现有 locomotion 时先复制 ABP 到候选范围，保持原始状态机。确认骨架、Mesh、
AnimClass、AnimationMode、相对位置/朝向/缩放，以及 EventGraph 取得的角色类别。
同骨架不代表脚底高度正确；相对 Z 应结合实际胶囊 half-height 与模型原点调节。

旧 Python `read_graph_dsl` 对这份非空 EventGraph 却返回空文本，native
`FindNodes` / `GetNodeInfos` 可读其实际节点。因此空 DSL 不授权重建 ABP；完整
state/transition 容器仍有已记录的可见性限制。

ABP 编译和 AnimClass 读回只证明配置。运行时必须取得当前 AnimInstance，读取
速度/状态变量并检查可见姿态；角色移动而动画不动可能是动画更新、实例或 Pose
问题，不能直接把它当成巡逻算法失败。死亡使用单次 AnimationAsset 会切换 Mesh
动画模式；只在相应状态使用，恢复/复活时要显式恢复 ABP。

## 分层验收记录

每个 case 按 [runtime record](shared-conventions.md#runtime-result-record) 保存构建、
world、角色、触发、时间基准、预期/容差、样本和 cleanup。以下项目分别给结果：

| 层级 | 有效证据 |
|---|---|
| 结构 | BT 顺序/类、Blackboard 类型与绑定、真实 Target 接线、组件与 Mesh/AnimClass 读回 |
| 编译 | 四个 Blueprint 和候选 ABP 的编译结果；记录是否 warnings-as-errors |
| 持久化 | 指定包保存、clean、重载后再读关键默认值和引用 |
| Runtime 初始化 | Controller 类、BT/Brain 正在运行、initialized、每个 AI 的独立 BB；实例数 >1 |
| Runtime 巡逻 | 带游戏时间的 X/Y/Z、速度、方向、tick/turn 计数；覆盖正向、反向、至少一次边界转向 |
| Runtime 动画 | 当前 AnimInstance、GroundSpeed/ShouldMove/IsFalling 及命名视觉问题的捕获 |
| 受击/清理 | 立即败退状态与碰撞关闭；延迟后 Pawn、Controller、任务资源和奖励计数；重复触发 |
| 重入/失败 | 再进 PIE 初值重置；缺失/错误 Pawn、树启动失败和提前销毁的诊断 |

采样间隔与转向容差考虑真实帧率、速度和制动距离；不要求边界误差严格为零。
授权 PIE 后只拥有自己启动的会话；结束后确认会话停止、候选保存和用户状态。
离屏截图或变化的图片 hash 不能替代行为计数、碰撞、计时和销毁证据。

## Windows 打包前的静态检查

编辑器启动和 PIE 通过不证明可以 cook/package。读取目标安装的
`Engine/Config/Windows/Windows_SDK.json`、UAT/UBT runtimeconfig、已安装 compiler
和 SDK，而不沿用旧 UE 的版本要求。

MSVC 的目录 family 与实际 `cl.exe` 版本不同。此构建 UBT 用 family 排 preferred
顺序，用实际版本检查 banned/minimum；例如 family 14.44.35207 内的已更新
14.44.35229 compiler 不能按目录名误判为被禁补丁。最终选中版本仍要以真实
UBT 日志确认，静态文件存在不能算构建通过。

检查 `.uproject` 的 Modules、Source、项目 C++ 插件及 runtime 插件依赖。
Editor target 过滤的 MCP/toolset 不应成为 gameplay 依赖；Blueprint-only 项目也
可能因非默认 runtime 插件生成临时 Game target。插件有 Development/Shipping
precompiled manifest 仅是可用性证据，不授权跳过实际 build/cook。

显式 cook 地图与发布包默认启动地图分别验证：`-map` 加入 cook 目标不等于改好
`GameDefaultMap`。打包后用实际产物检查启动地图、输入/HUD、AI/动画、销毁清理、
资源依赖与性能；把静态预检、build、cook、package 和 packaged runtime 分别记录。

复制工程的旧 `Saved/Cooked/<Platform>/ue.projectstore` 可能指向已经不存在的 Zen
oplog。若目标无需 Zen 输出，当前 `CookCommandlet` 的官方 `SkipZenStore` 开关可经
UAT `-AdditionalCookerOptions=-SkipZenStore` 传入，选择 loose package writer；它
会关闭 Zen 依赖的 incremental cook 并做完整 Cook。不要为此删原 Content、重置全局
Zen 服务、改引擎或把这项恢复措施设成所有工程的默认配置。后续
Stage/IoStore/Archive 仍须实际完成并测试启动，进到 Cook 不等于打包通过。

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404。

**先明确 gameplay 合同**

- 还须检查整段巡逻走廊的砖块和其他阻挡；本次一只 AI 的范围穿过跳跃砖块， BT 虽在
  Running、tick 虽增长，实际速度却为零。

**独立 ABP 与动画验收**

- 本次复用 ABP 的 native EventGraph 可见 Initialize/UpdateAnimation、
  `CastToCharacter`、CharacterMovement、velocity、GroundSpeed、ShouldMove、
  IsFalling 和 Direction 路线。

**Windows 打包前的静态检查**

- 本次 CL 60351404 的 UAT/UBT 使用 .NET 10， Windows SDK 最低 22621、主版本
  26100；14.51 MSVC 在该构建被禁用。
- 本次 Cook 在所有本地地址得到 HTTP 404 后阻塞于旧 hostname；保留日志，核对并停
  止自己的 cook 进程，再隔离确认为旧缓存的单个 marker。


