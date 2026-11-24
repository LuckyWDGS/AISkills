# 从玩法到可玩 Demo：UE 5.9 制作流程

用于制作完整的小型游戏、垂直切片或包含过场的关卡。共享 MCP client 是传输层，
Blueprint / CharacterMovement / AI / UMG / Sequencer 等正式运行系统负责游戏逻辑；
不能把编辑器 Python tick 或不断设置 Actor 位置的制作脚本当成游戏实现。
本页操作合同针对 5.9；设计原则可复用，但 5.8 工具名、输入字段和 Python 环境
须走该版本的参考，不能照抄本页调用。5.9 先读 [版本审计](ue-5.9-preview-audit.md)；评估 Canvas、生成动画、光照或 Web
目标时读 [生产功能矩阵](ue-5.9-production-feature-matrix.md)。

## 制作顺序与资产合同

先明确视角、移动轴、操作、目标、失败/复活、单局长度和交付平台。为玩法状态列出
允许的入口，例如 Intro → Playing ↔ Paused → Won/Lost → Restart。控制器、相机、
输入、界面和过场共享这份状态合同，避免各自维护冲突的 bool。

在独立 Content root 内先做一条可运行的最小链：GameMode → Pawn → Input →
移动/碰撞 → 一个目标 → 胜利/重开，再增加关卡、美术、AI 和演出。记录资产类、
引用、骨架、接口、默认值和拥有者；创建脚本读回已有对象，禁止用整段重跑修复
一次局部失败。正式写入前重新验证绝对工程路径、构建、live schema 和 PIE 归属。

| 模块 | 制作路线 | 完成依据 |
|---|---|---|
| 规则与状态 | GameMode / Controller / Pawn / Component；公开函数、可调变量与中文模块注释 | 状态转换、重复调用门禁、失败路径、重开初值 |
| 输入与角色 | Enhanced Input 的 IA/IMC；CharacterMovement、Capsule、SpringArm / Camera | 真实按下/释放、地面/空中、碰撞、相机与输入恢复 |
| AI 与动画 | BT/BB/Task + AIController，或任务需要的 StateTree；实际 AnimInstance | 独立决策数据、移动/转向、动画姿态、受击与清理 |
| HUD 与菜单 | Widget Blueprint / UMG；按需要选 MVVM、CommonUI | 实际 Widget 实例、值更新、输入路由、分辨率/DPI与重建 |
| 关卡与生成 | Actor / Component、碰撞、WorldSettings；需要散布时用 PCG | 可通行路线、边界/跌落、目标与检查点；生成/清理不累积 |
| 美术与效果 | sibling material / Niagara / flipbook 技能 | 可见画面、运行激活/结束、引用、平台开销 |
| 音频 | SoundWave 导入/属性；有程序音频需要时用 MetaSound | 来源、真实播放、音量/空间化、重叠与停止 |
| 过场与镜头 | sibling Sequencer；runtime possessable 绑定与 CameraCut | 自然完成/跳过/Stop/重开都恢复控制；实际 viewport 画面 |
| 进度与配置 | SaveGame、设置对象、DataAsset / Table / Registry，按需求选择 | 版本/缺失默认值、真实保存加载、重启持久化；不能用 BB 代替存档 |
| 战斗与交互 | Damage / Interface / Component；复杂可组合能力才考虑 GAS | 单次奖励、无敌/冷却、幂等销毁、owner 清理；联网另测权威 |
| 验证与交付 | compile、scoped save/reload、PIE、log、capture、目标 cook/package | 每层独立结果；编辑器通过不替代打包启动 |

这些是可选模块路线，不是宣称所有域均完成本构建的作者和 runtime 测试。
导航追踪才需要 NavMesh/EQS；简单横版巡逻无需强塞导航。复杂能力/联机才引入 GAS
或复制。插件按当前模块需要启用，处理依赖和重启后重新发现；不为“全用最新”
打开全部实验插件、联网下载模型或改项目渲染方式。

## Enhanced Input 与角色配置

创建 InputAction 并明确 Boolean / Axis1D / Axis2D；再创建 MappingContext。
本构建 IMC 的数组在 `DefaultKeyMappings.Mappings`，不在旧顶层 `Mappings`。
负向键通过自己的 `InputModifierNegate` 写 `bX/bY/bZ`。这些原生字段与 Python
API 去掉 b 的属性名是不同合同。读回所有按键、修饰器和动作引用再保存。

角色 BeginPlay 给自己的 LocalPlayer subsystem 添加自己的 IMC；EndPlay 只移除
这份映射；先检查 subsystem 仍有效，退出世界时它可能已经销毁。不要
ClearAllMappings。移动用 Triggered 的实际动作值调用
AddMovementInput；跳跃常用 Started → Jump、Completed/Canceled → StopJumping。
Triggered 每帧调用 Jump 会混淆持按与双跳。暂停允许的按键显式设置 paused 合同。

CDO、SCS 组件模板、已放置实例和 PIE 实例分别检查。EditCondition 先单独启用，
随后写依赖属性。SpringArm `TargetOffset` 是世界偏移，`SocketOffset` 是末端局部
偏移；横版看前方时不能把 boom 朝向下的局部 X 当世界 X。确保 mesh 的原点、
缩放、脚底和胶囊尺寸匹配。碰撞查看每个 channel 和 overlap 开关，而非只看 profile。

用本机 `InputToolset.ApplyInput` 在自己拥有的 PIE 内测试真实输入；这不同于桌面
按键或直接调用玩法函数。`entries` 每项恰好选择 action 或 key，value 非零。
`action` 直接注入增强输入动作，绕过 IMC 的键映射和映射级修饰器/触发器；动作
通关证明玩法输入路径，不能单独证明 A/D/Space 映射正确。另用 `key` 做正向、
反向与跳跃映射 smoke，记录两类证据。`durationSeconds=0` 代表一个真实 tick 的
点按；返回时已经释放。暂停测试比较游戏
时间、位置和状态，不能拿墙钟推进推断游戏仍在 tick。

## UMG、音频与交互

UMG 先创建 Widget Blueprint、根布局和真实控件，设置锚点、slot、字号、颜色与
可见性。跨蓝图引用的控件设置为变量；建立有类型的 HUD 引用。运行时 CreateWidget
并 AddToViewport，由正式状态变更推送 text/progress，而非更新 WidgetTree 模板。
菜单按钮需要自己的输入模式/焦点/光标合同与点击验收；键盘 HUD 不冒称完整鼠标菜单。
MVVM 通知链需单独测，不能用手工 SetText 当 FieldNotify 通过。
有数据绑定、菜单栈或丢焦点问题时，读 [UI 工作流](ue-5.9-ui-workflows.md)；
该页区分静态作者、CommonUI 路由与 UMG/Slate 记录器的运行证据。

SoundWaveToolset.ImportFile 可以把已准备的音频导入候选包。记录实际返回资产并
回读采样率/通道/时长；作者图中要读回非空 Sound 引用。只编译无法证明音频存在：
本构建 DSL 对不存在的对象路径曾 canonical 成 null 后仍编译成功。播放和音量需要
实际听取或明确的音频捕获，静态属性不能代替。媒体采样/MRQ路线见
[音频、媒体与渲染](ue-5.9-audio-media-tools.md)。

拾取、踩踏、受伤和终点有单一状态拥有者。DestroyActor 后立即结束该分支，避免
后续读取待销毁的 OtherActor；互斥类型用嵌套分支或单独函数。布尔 AND 的纯节点
不保证短路，不能用它隐藏一个会解引用无效对象的操作。重复 overlap、无敌期间
再接触、传送后 overlap 重入和目标销毁分别测试。奖励和结束状态先门禁后表现。

## 过场、恢复与生命周期

序列可保留 tagged empty possessable，在 CreateLevelSequencePlayer 后用独立的
LevelSequenceActor SetBindingByTag 绑定本次地图里的相机。CameraCut 必须绑定真实
camera，保存关键帧不代表观众看到该镜头。自然结束 OnFinished 与显式 Stop 的
OnStop 分别接入正常游玩中的共用 FinishIntro。保留幂等恢复：先置标记、解除自己的
委托，再按该会话需要 Stop/Restore，恢复 ViewTarget、MovementMode、游戏输入与
HUD。要覆盖自然完成、Skip、显式 Stop 和过场中重开。

世界 teardown 与正常 FinishIntro 分开。LevelSequenceActor 可先执行 EndPlay，
其内部 Stop/TearDown 后 SequencePlayer 的 UObject 仍然有效；IsValid 不能证明
MovieScene 内部共享状态仍可恢复。本次 5.9 独立包曾因玩家 EndPlay 再次调用
RestoreState，在退出时触发 SharedPointer 断言。玩家 EndPlay 不重复 Stop/
RestoreState，也不复用恢复玩法控制的 FinishIntro；只解除自己绑定的委托，移除
自己的输入映射、HUD 等资源。播放器的内部 teardown 由拥有者处理。

退出玩法时清理自己创建的 Widget、输入映射、timer、委托、AI 任务与临时对象。
重开可以用受控的 OpenLevel 重建整个单局；在解除暂停后发起，不能只把玩家传回
出生点却保留旧金币、敌人、旧 Widget 或输赢状态。调用异步工作后提前销毁也需验收。

MRQ 与实际游玩录屏是不同交付。不要依赖玩法 Intro 的 runtime binding 自动被
MRQ 复用；另做有地图 possessable 的 render sequence 并验证绑定解析。对排队、
失败、取消、输出帧和音频分别验收。游戏演示可以使用原生 viewport recording，
记录其 frame/drop 警告，不把低帧率录屏的观感当 GPU 性能。

本构建的 viewport MP4 不含音轨。需要有声演示时，先查询
`AudioMixerLibrary.start_recording_output/stop_recording_output`，录制同一个 game
world 的主混音；WAV 导出目录相对 `Saved/BouncedWavFiles`，不是任意绝对路径。
等待文件完成并检查时长、非零样本和峰值，再按游戏时间对齐并封装真实音轨。
后台 realtime 音频可能被应用失焦静音：本次确实生成了全零 WAV。先查 live
`au.DisableAppVolume`；为捕获临时改值时记录原值并在 finally 恢复，不改用户
长期配置，也不以合成音效代替实际游戏录音。非零混音仍不等于五种事件音效都
已逐一试听、空间化或混音预算通过。

## 运行测试与发布

存档、用户设置、数据表/标签、骨骼挂点与物理交互，以及精确选择自动化测试，
见 [游戏系统模块](ue-5.9-game-systems.md)。按当前玩法选模块；表作者、测试接口
和运行时业务逻辑属于不同层，不以工具已注册替代实际保存/输入/碰撞验收。

先记录没有用户已有 PIE，再启动自己的会话；取得 game world、真正 Pawn、
Controller、AnimInstance、HUD 和 AI/Blackboard。对每个功能采样游戏时间与实例
状态，结合实际 viewport 捕获。`SceneCaptureToolset.CaptureGameViewport` 可包含
UMG；显式 pose 的离屏 Capture 不能证明 HUD、实际 CameraCut 或屏幕 Fade。
原始 MCP image block 保存后实际查看，URN 不能当图片路径。
同时记录测试前编辑器相机；本构建停止 viewport PIE 后会沿用游戏相机位置，
测试结束应恢复已记录的编辑视角并回读。该恢复不用于取景或自动打开资产。

边界用受控 fixture/传送能快速定位，但单列为交互测试。至少一次从出生到终点的
纯输入通关，过程中不改位置、生命、金币、移动速度或胜利状态；失败也保留轨迹，
根据玩法或输入策略修正。检查静止、移动、持按/双跳、暂停/恢复、接触伤害、踩踏、
检查点、坠落、胜败、重开和退出，见 [runtime cases](runtime-acceptance.md)。

构建前核对 UAT/UBT、目标 SDK、预编译游戏或 C++ toolchain，以及各插件 Runtime /
Editor 限制。只 cook 指定地图仍需明确 GameDefaultMap 或启动地图参数；保留用户的
EditorStartupMap。content-only 项目未必需要生成 C++。构建日志、退出码、打包目录
和一次实际启动分开记录；成功启动还不证明所有玩法在 packaged target 通过。
含过场或修改 EndPlay 的最终包还要分别测试过场中请求退出、过场自然完成后再
请求退出，记录正常退出码和对应日志/崩溃记录；强制结束进程不能验收 teardown。
Cook/package 成功不能替代这些退出路径。修复后重新打包仍需用新包重测，旧包的
启动或退出结果不能转算为修复已通过。
Web/Wasm 的 C++、SDK、headers和渲染限制另按生产功能矩阵处理。

### 后台独立包的输入、存档与退出证据

Development 回归驱动应同时要求开发构建和显式 QA 参数，用单独 UserDir、槽名、
进程 ID 与日志路径；默认启动不注入输入、不生成测试 token。通过正式 key mapping
走关卡，菜单另用虚拟 Slate 用户触发真实控件，参见 [UI 工作流](ue-5.9-ui-workflows.md)。
不要调用生产 handler、设置生命/位置或直接赋 Widget 值后声称玩家流程通过。

本构建 `Input.+key` 持续注入每帧 Pressed；P、R、Enter 这类切换动作采用一帧脉冲，
不能把 0.08 秒连续注入当一次点击。模拟轴另有释放时序：直接删除非零 forced input
会注入负的 LastInjectedValue，可能留下反向输入。先更新轴为 0，让输入更新经过至少
两帧，再 `Input.-key`；清理日志记录起止帧，并在退出前确认没有未完成的释放。
这是测试驱动的输入状态处理，不应通过改变生产 CharacterMovement 来掩盖。

每个进程保留已核对范围的包文件哈希、启动参数、创建/退出时间、最终状态与对应日志，拒绝任何
failed check、Blueprint runtime error、ensure、超时或强杀。退出码 0 单独不足以通过。
本次清单覆盖运行 exe 与 PAK/UTOC/UCAS，不是每个散装 DLL/文件；需要完整发行物
完整性验收时另列全包 manifest，不把一个 exe 的 SHA 当作整个包的身份。
跨进程存档要求第二进程复用同一个隔离 UserDir，核对磁盘哈希、设置、检查点和金币 ID；
OpenLevel、内存对象和 fixture 字节往返不能替代。设置 Apply/Discard/Defaults、保存失败
提示、保存后退出与退出不保存应按产品分别验收。

路线验收使用产品行为，不要求测试脚本执行恰好某个次数的跳跃。此次修正了过度
固定的跳跃次数断言，保留旧失败记录；最终额外匹配同帧的 SpaceBar keydown 与
跳跃事件，以及后续 Playing 状态的 jumpcount=2 样本。每项证据应位于本 case 的
boot 与 result 之间，不能用旧日志、另一个 case 或退出后的记录满足断言。

2026-11-16 的最终同一 Windows Development 包，实际通过正式映射输入通关
（3 命、6 金币、真实落地检查点、胜利保存）、菜单重开、设置保存退出及独立
进程读档。两个模拟轴释放均经过两帧零值；各进程自然退出 0，未出现本轮 runtime
error 或 ensure。完整路线、设置写/读、重开分别验收，不将成功退出单独当通关。
过场中 1 秒主动结束的独立用例仅验 teardown，保留 phase=Intro 和 EndPlay 记录，
不要求它产出通关 result，也不能用这种定时结束代替正常玩家退出路径。

首次 D3D12 PSO 清理可能在正式退出请求后继续较久。区分带时间戳的 QA 成功、退出动作、
`RequestExitWithStatus`、`PreExit` 与真实进程终止；完整证据可解释较长 teardown。
仅总墙钟接近 `-seconds` 既不能证明 watchdog 触发，也不能证明它无关。实际 watchdog
标记、缺少动作/请求顺序或失败检查仍拒绝通过；不要为了绿灯放宽运行时错误检查。

此次 UAT 曾尝试重建被编辑器加载的项目插件 DLL，失败后按已单独编译成功的 Editor
模块使用 `-nocompileeditor`。Cook 的 Zen store 还出现失效 oplog；本构建官方参数是
`-SkipZenStore`，可经 UAT 的 `-AdditionalCookerOptions=-SkipZenStore` 传递，而不是
猜测 `-NoZenStore`。保留失败日志，仅处理已核对归属的 cook 进程与本次生成的 store
描述文件；不修改引擎或全局缓存，不将这种本地恢复方式作为每次打包的默认清理。

### 独立进程的原生 Agent 采集

本构建通过 `ConsoleToolset.SearchConsoleCommands` 实际发现 `Agent.Capture`、
`Agent.PerfCapture` 与 `Agent.WaitForAsyncWork`。它们是原生 console/命令行路线，
无需新注册 MCP wrapper。独立 Development 包已验证：

```text
-AgentCapture=<unique-name> -AgentCaptureFrames=30 -AgentPerf=2 -AgentCaptureExit
```

导出 `Saved/Agent/<name>.png`、环境 `.json` 和 `.perf.json`；后者含 frame/game/
render/GPU 的 avg/p50/p95/p99/max。检查文件、实际图片、上下文、采样数与进程退出码。
另外读取 `LogAgentBarrier` / `UE_RUN BARRIER` 的 `complete`、shader jobs 和
streaming left；当前 capture 实现忽略 barrier 的完成返回值，退出 0 / PNG 存在
只证明截图写入，不能单独证明资源已稳定。本次 barrier 明确 complete=true，
shader jobs / streaming left 均为 0。
本次独立包生成 960×540 图、D3D12/SM6/map/GameMode 上下文及 60 帧/2 秒统计，
正常返回 0。30 fps limiter 下的短样本不是整关性能或目标平台预算。

`Agent.Capture` 会把全局 time dilation 暂改为 0.0001，等待异步工作，再恢复为
1.0；它不是无状态截图，也不保留任意原始 dilation。用于新起的测试进程，不能
当作不影响用户现有 PIE 的只读采集。当前源码截图不含 UI，并可能冻结在 Intro
Fade 中；不能代替 HUD、连续动画或完整游玩验收。其异步 barrier 默认可等待
300 秒，应在进程外设有界 deadline，不能在短 MCP 请求中盲目阻塞等待。

交付应包含启动/控制说明、地图或包、可见截图/视频、已验收用例和明确缺口。
本机脚本、schema、日志和绝对路径放 ignored session；可复用的合同与陷阱进入技能，
实验资产不提交进技能仓库。5.9 测试不能冒称 5.8 runtime 回归。
