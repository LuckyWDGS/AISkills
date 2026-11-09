# UE runtime acceptance

Select cases matching the changed feature; these are procedures, not recorded
UE test results. Follow the [shared result record and session ownership rules](shared-conventions.md#runtime-result-record).
Use official MCP state/log reads and supported background runtime controls.
Discover the actual runtime objects and tool schemas; do not read CDO values as
live state or invent debugger APIs. A user's existing PIE session is preserved.

## BP.Jump.Double — two jumps and landing reset

- Setup: record the possessed pawn, Enhanced Input phases, JumpMaxCount,
  JumpMaxHoldTime, movement mode and any parent/custom jump logic.
- Trigger: press/release for the ground jump, press/release while airborne,
  attempt a third press, land, then jump again. Include holding the first press
  so an Enhanced Input Triggered event cannot silently consume both jumps.
- Expect: two accepted jumps, a rejected third, and a fresh first jump after
  landing. Record accepted/rejected counts, JumpCurrentCount where readable,
  movement mode, vertical velocity and game timestamps. Inspect Landed and any
  custom reset path. Walking off a ledge follows the feature's agreed policy.
- Diagnose: verify input delivery and possession before changing jump code;
  trace parent Jump/StopJumping calls and gates that bypass CharacterMovement.
  Multiplayer, if requested, also needs server and owning-client results.

## BP.Surface.Contact — contact VFX, blink and delayed reset

- Setup: two independently materialized yellow objects, one player with more
  than one overlapping component. Record baseline material slots/parameters.
- Trigger: enter, remain, exit one overlapping component, exit the last, re-enter
  at about 1 second, leave again, then wait beyond the configured 2 seconds.
- Expect: the agreed once-per-entry or repeating VFX policy; blinking only on
  the contacted object. One component's EndOverlap must not end the actor's
  remaining contact. The old reset timer is cancelled on re-entry; yellow
  returns only 2 game seconds after the last real exit, within one sampling
  interval plus timer tick tolerance. Record active overlap pairs/count,
  reset-handle state, generation/token if used, parameter values and event counts.
- Destroy the player or contact object during the wait: no stale callback,
  accessed-none error or effect on another instance. Test non-player overlap
  filtering and any collision-channel assumptions.

## BP.Throw.Physics — hold, release, fuse and destruction

- Setup: record hand socket/attachment, collision state, thrower exclusion,
  mesh/root simulating body, mass/damping, gravity and physical material.
- Trigger: hold right mouse, release, observe a bounce/roll/rest, and wait for
  the agreed fuse (for the 3-second feature, measure from release). Also cancel
  while held and try rapid repeat input.
- Expect while held: one object attached to the hand, physics disabled as
  designed, readable trajectory/landing presentation. Release detaches before
  physics/velocity are applied and removes preview components.
- Expect in flight: Chaos velocity changes under gravity/collisions; bounce,
  angular motion and sleep follow the physical material and damping. Predicted
  ballistic points need not match post-impact Chaos motion. A ProjectileMovement
  arc or transform animation does not establish rigid-body behavior.
- At fuse expiry: exactly one explosion request and one damage dispatch if
  damage is in scope; the projectile is destroyed exactly once, with no live
  collision/body afterward. VFX/SFX intended to outlive it use their own lifetime.
  Record release/fuse/explosion/destruction times, body velocity samples and
  spawn/destroy counts. Early owner/projectile destruction cancels callbacks.

## BP.Lifecycle.Async — timers, delegates and EndPlay

- Activate the module twice, deactivate, reactivate, then destroy/unpossess its
  owner during pending work. Repeat a bounded number of times.
- Expect one active subscription/timer per intended owner; cancelled generations
  cannot call a new instance. EndPlay/component shutdown clears handles and
  delegate bindings as appropriate. Observe counts after the normal grace period;
  elapsed delays alone do not prove cleanup.
- Trace failures through log module ID → asset/graph → called function/interface
  → parent/C++ implementation. Capture the first relevant warning and state
  leading to it before adding retries or replacement logic.

## ABP.StateMachine — transitions, montage interruption and data ownership

- Setup: record the actual mesh AnimClass/instance, skeleton, locomotion inputs,
  entry state, transition priorities/durations, sync groups and Slot path.
- Trigger idle → movement → jump → fall → land, plus rapid threshold changes.
  Verify reachable entry/exit states and the intended return after landing;
  neither node presence nor a true transition expression proves execution.
- Play the relevant Montage through its real gameplay entry, interrupt/blend it
  out, then replay. Record active montage/position, state and transition times,
  Notify begin/end or callback counts and the final state. A missing Slot or
  another montage/linked layer can override an otherwise correct state graph.
- Check root-motion ownership when used, invalid pawn/mesh replacement and
  reinitialization. In thread-safe update functions, use the supported property
  access/cached-data path; arbitrary actor calls must not be moved onto worker
  threads merely to make the graph shorter. Verify warnings and data age.
- If the live official interfaces cannot read executed state, add scoped debug
  logs to the authorized module or report the exact evidence gap. Graph topology
  and sampled variables alone cannot prove final pose or notify execution.

## UI.MVVM.Binding — 实例数据与界面更新

- 通过实际游戏/界面创建路径取得 Widget 实例、MVVM View、Context 和模型实例，记录
  完整对象路径。确认操作的是运行实例，而不是 Blueprint、CDO 或 WidgetTree 模板。
- 初次显示时比对模型值与目标控件值；通过正式 setter/FieldNotify 更新两次，确认
  UI 自动跟随。可用 0.75 → 0.25 → 1.0 作为进度值样例；数值以功能要求为准。
  手动设置控件值或强制 ExecuteBindings 不能单独证明通知链正常。
- 若按钮事件在范围内，通过实际输入触发，记录一次点击对应的回调/业务计数。
  事件节点存在不证明点击送达；同时检查输入模式、焦点、可见性与命中设置。
- 重建/关闭再打开界面，检查模型归属、绑定清理、订阅计数和警告。
  仅在视觉范围内验证目标分辨率/DPI 的截断、布局和可读性；结构读回不能替代此项。
  不为验收擅自将 Widget 加入用户当前视口或改变焦点。

## GAS.ASC.Lifecycle — 能力、效果与属性

- 定位实际世界、网络角色、Actor、ASC、Avatar/Owner 和已注册 AttributeSet。
  同时记录属性 Base/Current、能力授予状态、活动效果和 Tags；定义查询不代表实例状态。
- 走正式输入/事件路径激活能力，再取消/结束并重复激活；观察激活次数、消耗、冷却、
  Tags、GameplayCue 及失败原因。只测试当前功能涉及的 GA/GE，不为测试改主角色架构。
- 对范围内效果核对叠层策略、持续时间、周期、过期/移除与 Base/Current 恢复。
  销毁/替换 Avatar 后确认任务、委托、效果及表现清理。网络行为仅在需求范围内另验。
- 空效果/能力列表只证明当前无活动/授予内容。官方 transient Actor 工具单元测试
  与项目实际能力生命周期分别记录；Cue 全盘扫描等警告应保留并归因。

## DATA.Registry.Cache — 来源与缓存条目

- 记录注册表类型、ItemStruct、初始化状态、编辑器来源、展开的运行时来源与 availability。
  使用独立验证表或已授权条目，保留原扫描配置和缓存策略。
- 对已知 ID 同时查 ListItems 和 GetItems。预缓存来源应返回预期类型和值；
  非预缓存来源按实际获取流程加载后再读缓存，不能把缓存未命中当成数据丢失。
- 对任务涉及的刷新/优先级/MetaSource 检查实际生效来源，确认数据表行修改后的值
  按项目刷新流程可见；读取 UObject/表默认值不能证明注册表已经返回新值。
- 最终恢复临时扫描配置，读回值和注册表列表；只保存指定夹具包。
  记录这是编辑器子系统缓存验证，还是 PIE/打包目标的数据加载验收。

## PCG.Graph.Output — 执行、数量与属性

实现与数据读取细节见 [PCG 专项流程](pcg-mcp.md#执行与验收)。以下案例按本次功能选用，
记录编辑器生成、PIE 或打包目标，不能相互替代。

- 记录实际图、实例/组件、Seed、输入边界和生成节点，先审查是否会改世界。
  临时图实例也可能经 spawner 生成 Actor；不要把即时执行当成通用沙箱。
- 串行执行与检查，记录完成状态、警告/错误，再从支持的数据检查接口读取输出
  点数、位置/边界、属性类型与值。按图预期校验，不能从节点配置推断运行输出。
- 改一个受测参数后确认输出对应改变；有世界生成时核对生成对象与清理范围，
  保留用户原有 Actor。需要确定性时比对相同 Seed 和相同输入的结果。
- RunPCGInstantGraph 的空消息列表只证明该次没有捕获消息；未获取输出数据时明确写
  “执行完成，输出数量/属性未验收”。GetNodeDataView 可能开启 inspection 并要求重新执行。
- 散布密度改变应带来符合采样上限的数量变化，零密度应没有本 owner 的实例。
  对坡度阈值同时检查被过滤/允许的测试面；固定缩放时检查全部实际点或实例变换。
  模型重载要核对生成组件的 staticMesh，不能只看参数软路径。
- 同一 owner 和全部输入不变时重复生成，比对排序后的点/实例完整变换和数量，检查不累积。
  改 Seed 后按图约定变化，再恢复原 Seed/参数，确认原结果恢复；不同 owner 不强求相等。
- 改 Box 时回读全部半尺寸与 lastGeneratedBounds；分别验证 X/Y/Z，不能只检查一个边界。
  清理后实例/组件计数归零，再生成应恢复。普通 BP Actor 组件的异步完成状态需外部轮询。
- 对生成地表、边界/坡度和密度分布做有明确目的的视觉检查；保存本次图/BP/外部包，
  删除临时 owner，核对原 Actor、选择、页签与 dirty。保留并记录工作期间观察到的其他变化，
  不为通过现场比较而关闭用户页签或清除 dirty。

## PHYS.Body.Runtime — 刚体与约束

- 记录实际 SkeletalMeshComponent 使用的网格、PhysicsAsset、Body/骨骼、模拟/碰撞模式、
  质量与约束。确认修改的是授权实例或隔离资产，避免把共享网格的设置当实例改动。
- 走实际启用物理/布娃娃入口，施加功能范围内的运动或碰撞；采样 Body 变换/速度，
  检查约束限制、穿透、异常抖动和睡眠。资产 Shape/质量回读只能证明编辑值。
- 结束/恢复动画或销毁 Actor 后检查模拟和碰撞清理；投掷物使用前面的物理投掷案例。
  只为资产编辑验证时无需创建运行时布娃娃，未运行项应单列。

## Dataflow.Evaluation — 数值求值与失效更新

- 用最小已知输入记录节点实际类型、引脚适配、连线与预期输出；再通过目标版本
  支持的执行接口读取求值结果。图保存和 GetNodeInfo 不构成数值执行证明。
- 更新输入后重新求值，检查结果变化与缓存失效；有依赖资产时确认读到正确对象。
  若没有可用的官方执行接口，记录已检查的工具集和具体缺口，报告结构/值回读完成，
  不把尚未执行的结果标成通过。

## Automation.Scope — 案例与现场清理

- 先确认测试会话归属，发现完成后只运行已审阅源码的目标案例。
  记录每项结果、错误、警告、耗时与 fixture 清理；Success 也可能带警告。
- 比较目标世界 Actor、PIE、打开页签、选择和脏包。测试 fixture 已销毁但关卡仍脏时
  继续追踪副作用；不能清 dirty 或保存整个关卡掩盖问题。
- 报告案例实际断言的内容；工具单元测试、资产编辑验证、项目运行验收分开计数。
  不将少量抽样成功外推为全部 MCP 工具通过。
