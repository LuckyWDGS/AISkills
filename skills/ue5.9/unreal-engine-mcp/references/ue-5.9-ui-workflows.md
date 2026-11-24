# UE 5.9：MVVM 作者与 UI 运行诊断

用于数据驱动 HUD、菜单/弹窗输入故障，以及 Widget 重建后丢焦点等问题。
2026-11-15 复核了 5.9.0 Preview / CL 60351404 的 live schema 与安装源码；
2026-11-16 补充普通 UMG、Manual ViewModel 作者/编译、PIE 绑定传播，以及独立包
实际控件、设置和读档验证。隐藏 PIE 的焦点检查与截图有缺口，后续独立包用虚拟
Slate 用户和含 UI 截图补验；CommonUI 路由、真实设备导航和全部 DPI 仍未验收。
此前静态作者证据见
[编辑器工具](ue-5.9-editor-tools.md) 与 [动画 / AI / UI](ue-5.9-animation-ai-tools.md)。
先按 [core 入口](../SKILL.md) 验证项目身份并读取每项完整 schema。

## MVVM：先作者和编译，再验证实例传播

`MVVMToolset` 已注册 31 项工具，覆盖 ViewModel、属性绑定、转换、事件、条件及
View 配置。无需为它们增加逐项转发 wrapper；按目标绑定的实际类型选择工具。

1. 在独立候选目录创建 WBP 和 `UMVVMViewModelBase` 子类。用
   `CreateViewModel` / `AddViewModelProperty` 添加所需字段；后者接受其支持的
   基础类型并设置 **FieldNotify 元数据**，不代表已实现任意复杂类型。
   添加字段后单独调用当前 `BlueprintToolset.CompileBlueprint`，检查结果并
   重新取得 authoritative GeneratedClass。不要把 SKEL、REINST 或旧 class 引用
   注册为 ViewModel；某些绑定工具会按需编译，也不能替代明确的编译记录。
2. 用 `AddViewModelToWidget` 注册该 class，并确认 ViewModel 的实例创建/提供
   方式。分别发现 source 的可读性、通知能力与 destination 的可写性：
   `ListClassBindableFields` / `ListPropertyPathBindableFields`，再按需要查询
   `ListBindingConversionOptions`。字段存在不等于有通知，名字相似不等于类型
   兼容。路径按声明类型解析；若叶字段只存在于派生类，先绑定中间对象，再在
   WBP 的 Pure Const 转换函数中转换类型，避免伪造不可解析的路径。
3. 用 `CreateViewBinding` 连接准确的 source/destination context 与 property
   path。`conversionName` 虽在说明中称 optional，实际 schema 列入 required；
   自动推断时显式传空字符串。回读非零 binding ID、方向、转换函数、enabled/compile 标志。需要时
   用 `SetBindingMode`、转换参数 literal/path 工具调整。OneTime、OneWay 与
   TwoWay 的验收不同，只制作当前产品需要的模式。
4. 检查 `GetWidgetViewConfig`，再按需要提交完整配置并回读。安装实现会在
   sources 不自动初始化时，将 bindings 自动初始化强制为 false；不能只记录
   请求值。明确初始化来源、绑定和事件的时机，避免把尚未初始化当成通知失败。
5. 需要交互时才加 `CreateViewEventBinding`；需要数值条件时才加
   `AddViewCondition`。回读比较参数、目标和边界；schema 说明数值按 32-bit
   float 比较，满足条件时调用或设置 destination。目标函数收到什么参数、
   目标属性得到什么值仍需检查生成图并实测，不能假设它与普通 property binding
   一样复制 source。条件还受项目 MVVM developer setting 控制，不要为通过
   测试偷偷修改该设置。
6. 对 WBP 单独执行 `CompileWidgetBlueprint` 并读取错误/警告，同时确认 VM
   编译成功，再保存这两个候选包。部分 literal/condition setter 会自动编译，
   但**编译失败仍保留编辑**，返回成功或非空 condition 不能当作编译通过。
   `ListViewConditions` 的编译信息可辅助定位，最终以本次独立编译结果为准。

### Manual 实例与 FieldNotify setter

本构建 `AddViewModelToWidget` 实际得到的 creation type 为 **Manual**；注册 class
不会自动提供 VM 实例。`ListWidgetViewModels` 只列 class，不能用来猜 context 名称。
先发现官方 Python 符号，再经 `unreal.get_editor_subsystem(unreal.MVVMEditorSubsystem)`
调用 `get_view(wbp)`，从 `available_view_models` 读取 `view_model_name`、
`creation_type`；名称可能带冲突后缀。

已在普通 Blueprint 验证的链为：`|GenericCreateObject` 创建并强引用 VM →
`|CreateWidget` 创建 HUD/菜单 → `MVVMSubsystem.SetViewModelByNameOnAllViews`
按准确 context 名提供 VM 并检查 bool → `AddToViewport`。HUD 与菜单可共享同一 VM。
运行时从 engine `MVVMSubsystem` 实例调用 `k2_get_view_from_user_widget` 取得 View，读
`get_view_model(name)`、`are_sources_initialized()`、`are_bindings_initialized()`，
核对 VM 对象身份。只看 class 或绑定配置不能证明当前实例已连接。

FieldNotify 属性的普通 Blueprint Set 会编译成带通知的 setter。外部属性赋值的
pin 顺序有实测陷阱：不要把“目标、值”的常见调用顺序套到 Set。先查目标字段的
live `Schema`，作者时显式命名 `self` 与字段值 pin，例如以下示意路径：

```lisp
(set `/Game/UI/VM_HUD.Status` :`self` (`self.ViewModel`) :`Status` "READY")
```

本构建 canonical 回读将值放在目标之前；命名 pin 写入后以本次读回为准，
不把正确的 value-first 读回再次“修正”为 target-first。
安装源码仅在新旧值不同时广播；相同值通知次数仍需单独测试。此次 PIE 的实际
金币拾取经玩家 setter 改变 VM 后，HUD 文本同步变化；没有以直接 `SetText`
代替通知验证。打包前另核对 `ModelViewViewModel` runtime 插件被纳入 Game target；
编辑器专用 `MVVMToolset` 可用不能证明运行模块随包存在。

MVVM 的部分查询会请求创建缺失的 View：本构建
`ListWidgetViewModels`、`ListWidgetViewBindings`、`ListWidgetViewEventBindings`
使用 `RequestView`。对已有生产 WBP 的纯只读审计不要盲调这些查询；先确认 View
已存在或把该步骤视为编辑。`ListViewConditions` 使用不创建 View 的读取路线。
`FixupMVVMData` 会重建生成图，只用于已定位的绑定图不一致，不是通用重试步骤。

作者与 runtime 分开：创建、添加字段/绑定以及多项配置工具拒绝 PIE。先结束
自有测试会话并完成资产编辑，再在明确的玩家/world 内实例化候选 Widget 和 VM。
通过正式 Blueprint setter 或公开 API 的 FieldNotify 路径改变 VM 数据，读取
**实际 Widget 实例**的目标值并记录传播时刻。直接反射写字段或直接 `SetText`
不证明 FieldNotify 传播；若用它们布置 fixture，要与正式通知用例分列。

按产品选取有意义的用例：初始值、一次改变、重复相同值、禁用再启用绑定、
条件临界值、实例重建；TwoWay 还需输入反向更新且无反馈循环。将 VM 值、
通知路径、Widget 值及对象身份一并记录。事件绑定核对 handler 实际次数与参数，
不要以静态连线替代触发结果。布局、DPI、键盘/手柄操作另按需要验收。

`SetWidgetPreviewActive` 只控制 design-time 预览状态，还受用户 preview preference
影响；`ReadPreviewWidgetProperty` 需要已打开 Designer 产生的 preview widget，
缺失时会报错。它不能创建后台运行实例，也不能替代 runtime 验收。遵循当前
后台约束，不为补预览打开/聚焦 Designer；使用自有运行实例回读。

## 普通 UMG 菜单：作者、游戏输入与 Slate 分开

本构建 `BlueprintDslToolset.Read` 对 `WidgetBlueprint` 返回
`unsupported-asset-class`，只支持 plain Blueprint。不要继续向 WBP 写 DSL 图。
已验证的替代结构是用官方 Widget/MVVM 工具作者控件树和绑定，将交互逻辑放在
普通 Player/Controller Blueprint，绑定暴露控件的 `Button.OnClicked`、
`Slider.OnValueChanged` 到签名匹配的函数。每个菜单实例绑定一次，EndPlay/重建时
清理本轮绑定与旧 Widget 引用；不为普通菜单额外引入 CommonUI stack。

暂停菜单可保留同一个 Widget，打开时设置可见性、暂停、鼠标与
`SetInputMode_GameAndUIEx`，给首个按钮设置焦点；关闭时恢复先前玩法状态、
`SetInputMode_GameOnly` 和鼠标状态。调用这些 setter 仅表示提出请求，仍要读取
实际焦点、暂停与输入恢复。此次隐藏 PIE 中菜单可见/暂停/鼠标状态成立，
`has_user_focus` 仍为 false，不能报告键盘导航通过。

| 驱动方式 | 能证明什么 | 不能代验什么 |
|---|---|---|
| `ApplyInput` 的 key 项 | 经 `UPlayerInput::InputKey` 进入游戏按键/映射处理 | 绕过 Slate，不证明鼠标点击、按钮消费或键盘 UI 导航 |
| `ApplyInput` 的 action 项 | Enhanced Input action 注入后的玩法响应 | 绕过 IMC 选键与 Slate 路由 |
| 直接调用菜单 handler | 设置草稿、应用/取消等业务逻辑和 VM 输出 | 不证明控件委托、命中测试或真实用户操作 |
| `WidgetInteractionComponent` 虚拟 Slate 用户 | 给实际 Widget 设置虚拟焦点后，以 PressKey/ReleaseKey 走 Slate 和控件委托 | 不证明 OS 鼠标命中、真实设备焦点、手柄导航或无障碍支持 |

`CaptureGameViewport` 在能重绘所属 Slate 窗口时可包含 UMG；重绘失败会降级为
scene-only 并给 warning。隐藏 PIE 的本次结果确实只有场景，即使菜单实例已是
Visible。同时检查工具 warning、返回元数据和实际图像；成功 PNG 不等于 UI
截图。无法取得合成 UI 或正式 Slate 输入时，将视觉/点击/导航列为未验证，
不要用场景截图或 handler 调用填补，也不突破 core 的后台操作边界。

2026-11-16 的独立 Development 包补验了后台路线：`-RenderOffscreen` 配合
`shot -showui` 实际得到含 UMG 的菜单 PNG，并已检查完整布局；WIC 的 Enter 按下/
释放触发了真正 Resume 按钮委托，handler 恰好一次，菜单隐藏且解除暂停。
游戏按键 P 的暂停及游戏时间冻结另有检查。首轮虽然控件检查通过，路线仍失败，
该失败记录保留。最终同一包的通关、重开、设置写入与独立进程读取均通过：实际
控件覆盖 Resume、Restart、Load Checkpoint、Quality、Discard、Defaults、音量
滑块 Left 输入、Apply 和 Save & Quit；后者走产品正常退出而非测试 SoftQuit。
Quit Without Saving 另以全新 UserDir 实测：修改画质草稿但不 Apply，经真实按钮
委托调用产品退出，18 项检查通过且没有生成主档；不以 Save & Quit 代验。

已实看 1280×720 的设置菜单：音量 95%、画质 3、保存状态均可读，控件没有溢出。
截图仍需逐张检查：OpenLevel 前后请求的截图可能是模糊过渡帧或已切换的下一状态，
不能只凭文件名认定捕获了菜单或检查点；等待新 world、相机和渲染稳定，再结合
实际实例读回。此次读取流程的 final 图清晰显示检查点恢复后 4 金币、3 条命。
这些结果不保证所有隐藏窗口、DPI 和渲染后端都能捕获 UMG。

WIC 设独立 VirtualUserIndex/PointerIndex，清理自己按下的键；ReleaseKey 可能同步
触发 OpenLevel 或退出，先清测试持键标记，再派发 release，避免重入重复释放。
在 Development 且显式 QA 参数同时成立时才安装这类驱动，正式玩法仍由产品输入
和控件委托执行。不要将自动化的虚拟焦点写成隐藏 PIE 的 user focus 已通过。

旅行前还要释放 WIC 的虚拟用户焦点。本次独立包重开曾触发
`SObjectWidget destroyed while collecting garbage`；调用栈显示 WIC 和虚拟用户
handle 到 GC 析构时才注销焦点路径。修复是在自有 QA EndPlay 中，先释放按键，
再对有效 WIC 调用 `ActorComponent.Deactivate`，然后按原顺序移除 Widget。
该构建 Deactivate 会注销虚拟用户并清空 handle；独立包的两次关卡初始化和正常
退出复测通过，相关 ensure 不再出现。不要用 `SetFocus(None)` 清焦点，此构建
实现直接解引用 Widget；也不因这个测试资源问题向 Sequencer EndPlay 加恢复调用。

## CommonUI、UMG 与 Slate：把三层事件对齐

| 观测层 | 合适的读取 | 能回答的问题 |
|---|---|---|
| CommonUI | `GetActivatableTree`、`GetInputRoutingState`、`GetActionBindings`、`GetFocusState` | 哪个 root/弹窗激活，输入走向哪里，路由期望谁获得焦点 |
| UMG | `GetWidgetLifetimeEvents` | 哪个 Widget 实例何时 Constructed、Destructed、Rebuilt，是否频繁 invalidation |
| Slate | `GetCurrentFocus`、`GetFocusTimeline`、`GetFocusEventDetail`、`ReconstructFocusPath` | 实际焦点路径，以及输入/导航到焦点变化的原因链 |

CommonUI 非 event-log 工具需要正在运行的 PIE，并需正确的 LocalPlayer/router。
普通 `UUserWidget` HUD 的存在不能证明已配置 CommonUI 激活树。对 CommonUI 菜单测试，
先使用真正的 CommonActivatableWidget、容器和应用输入策略；明确 player index、
root、弹窗和返回行为。`ActivateWidget` / `DeactivateWidget` 操作的是现存实例，
不能代替菜单创建和 stack 接入；按完整 schema 的寻址规则处理同名实例。

先读激活树、路由、action bindings 和实际/期望焦点，再触发一次产品操作。
失败时关联 CommonUI timeline、UMG 对象 path/ID、Slate event `seq` 和时间窗口，
不要把各 recorder 的 `seq` 当成全局同一序号。Slate 名字可能重复，定位后用
具体 `GetFocusEventDetail(seq)` 取原因链。保留 player、PIE instance、时间基准
和 dropped count；有限缓冲丢失事件时不能断言事件从未发生。

对自有 fixture 验证菜单打开、弹窗覆盖、Back/关闭、重复打开与 Widget 重建，
核对顶部激活节点、消费/恢复输入和预期焦点。`RefreshActiveRootFocus`、
输入类型 lock 与显式激活会修改运行状态，只在已识别原因后用于验证假设。
使用本轮独有的 lock reason，清理时仅移除该 lock。不要先“刷新焦点”再采集，
否则会覆盖原始故障证据。停止自有 PIE；保留用户原本的会话。

UMG Destructed 是 Widget 生命周期事件，不等于 UObject 已被 GC；重新加入
视口可以有多次 Construct/Destruct。按实例与期望复用方式解释计数，不把
“销毁次数必须等于创建次数”套在仍需保留的 Widget 上。静态属性 winner 的
确定性解释见 [静态覆盖分析](ue-5.9-animation-ai-tools.md)，不能替代实际值或焦点路径。

## Recording 归属、缓冲与清理

`StartEventLogging`、`StartWidgetLifetimeLogging`、`StartFocusRecording` 是写操作。
本构建三者重启都会清空旧缓冲；Stop 保留当前缓冲，不会恢复旧内容。采集前
读取各自 status：若已有他人 recorder 在运行，优先使用其保留数据，不停止或
重配它。若需新的独立采集，先导出有关旧证据并协调 recording 归属；不得把
重启 recorder 当作可回滚操作，也不在 finally 中调用 Clear。

对本轮拥有的 recorder 设置有界容量和短时间窗口；默认只收必要上下文，遇到
问题再考虑 callstack/invalidation。先开始记录，再触发一次操作；用短调用读取
timeline/status，结束时只 Stop 本轮启动的 recorder 并导出数据。UMG events
为 newest-first，CommonUI/Slate timeline 为 oldest-first，合并前先统一顺序。
Slate 过滤参数和 MaxCount 受 schema 限制；无匹配/空记录不代表用例通过。

安装实现另有一个清理细节：`StartFocusRecording` 会设置
`SlateNav.CaptureCallstack`，`StopFocusRecording` 只取消订阅，**不恢复该 cvar**。
若要启动自有 Slate recording，先通过已发现的 console 读取路线记录原值；
停止后恢复本轮改变的值并回读。未确认该值与录制归属前，不声称状态已完整恢复。

采集 API 不要求打开日志窗口。当前后台流程跳过
`ShowWidgetLifetimeLogWindow` 和 `SetTreeVisualization`，不切换资产编辑器，
也不拿编辑器外的键盘/鼠标自动化补缺口。Slate recorder 是否可用还受构建的
`WITH_SLATE_DEBUGGING` 控制；编译关闭是明确能力限制，空状态不是替代证据。

报告分别列出作者/读回、VM/WBP 编译、绑定传播、输入/焦点、生命周期及视觉
结果；未执行部分标 `not_run`。独立包仅限上列普通 UMG 用例，不扩展为 CommonUI、
全部 UI 记录器或 UE 5.8 的回归通过。
