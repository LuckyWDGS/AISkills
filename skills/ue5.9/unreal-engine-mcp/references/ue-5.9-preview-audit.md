# UE 5.9 Preview：实测能力与版本边界

2026-11-11 在 **5.9.0 Preview / CL 60351404** 的独立工程完成 MCP 实测。
比较安装为 5.8.4 / CL 58902052。本页对应该构建和插件配置，不是全部 UE 5.9
发布功能，也不是 UE 5.8 编辑器回归结论。

2026-11-11 实时发现 **98 个 toolset、1,803 个工具**。这是注册数量；仅下表代表路径完成
实测，不能称为 1,803 项测试通过。大量工具只是迁移模块、命名或实现，不能全算
新增。原始 schema、调用结果及机器路径存于忽略的 `.codex/session/`。

## 连接、发现与脚本方式

| 合同 | 本构建的实际行为与客户端支持 |
|---|---|
| 5.9 search mode | `list_toolsets`、`describe_toolsets`、`describe_tools`、`call_tool`；分别解析 `toolsets` / `tools` 字典及 `errors` |
| 5.8 search mode | 保留 singular `describe_toolset` 路由 |
| Native mode | 保留 qualified `tools/list` 及分页 |
| 实例身份 | initialize 的 `com.epicgames.unrealengine/instance` 含 PID、版本/CL、engineDir 和绝对 projectFile；连接保护另核对当前监听进程 |
| 协议 | 客户端默认 `2025-11-25`，本次可正常初始化和调用；协议支持不能代替工具 schema |
| 官方 Python | `PythonScriptingTools` 提供 `read_me`、`execute_python`、`search_symbols`、`get_symbol`；支持 top-level await 与 `await call_tool(...)` |

Plural discovery、单工具缓存与错误检查已进入共享客户端。搜索结果的说明性
bullet 不计为 toolset；schema 缺失或含 discovery error 时不 dispatch。
工具错误、写入超时不会自动重放。明确 slow-task **Not run / This call made no
changes** 与未知完成状态的超时分别处理。

官方 Python 已验证中文返回、async composition、符号查询、编译后函数调用，
以及阻塞 `time.sleep` 被拒绝。先读 `read_me` 并查符号；输入是 CodeBlock。
旧 `run-script` 保留 5.8 ProgrammaticToolset 环境，不可只换工具名。
域工具的窄缺口先查 5.9 官方 Python，再考虑 Remote。

公开 CLI 的 `python-readme`、`execute-python`、native `batch --dry-run` 与实际
批次均已执行。批次完成中文变量提示写入/回读、编译和指定保存，最终资产 clean。
dirty 查询先确认存在；查询错误不再当作“不存在/已保存”。写前失败会拒绝批次，
写后失败保留步骤结果并报告 unknown，不重放写入。

## 已验证的控制增强

以下表格是第一轮审计的历史结果：当时写入限于测试候选目录，未启动 PIE。
后续小游戏阶段的运行结果单列在下一节，不能用来填补表内其他域的未测部分。
全程未打开/聚焦资产编辑器或 timeline、未移动用户编辑相机。
结构写入、编译、编辑器求值、图像检查和运行时行为分别验收。

| 领域 | 实际验证 | 实用改进与边界 |
|---|---|---|
| Blueprint | 原生创建、变量/函数中文元数据、参数/双向接线、注释、编译；DSL revision/edit、stale 拒绝、graph diff；CDO 输入 -3/0/2.5/42 得到 -1/2/4.5/44 | 可精确范围重写，元数据无需旧项目扩展；纯函数仍须验证 exec/return 语义；未测 BeginPlay/网络/PIE |
| Blueprint 检查器 | 原生拓扑、注释成员、分类；重复快照一致、dirty 不变；lint 无 Remote | 报告可规范化字段，但不能把规范化 pin ID 写回原生工具 |
| StateTree | 子状态增删/重排、任务/条件/全局任务、Blueprint 评估器、实例数据；公开 API 补参数绑定后 compile 成功 | 从读取扩展到可编辑结构；缺绑定时确实编译失败；未测状态生命周期/runtime |
| PCG | 编图、连线、普通 PCGComponent executionSource、生成来源、活动等待、DataView 精确两点输出 | 这些调用无需 PCGVolume；DataView 可触发生成，属 write；空闲 Wait 明确拒绝；未测 GPU/World Partition/Loop |
| 材质 / MI / Object | 图创建/连接/中文说明/编译；statistics、材质/函数 diff；MI scalar 0.8；嵌套 schema；EditCondition/uint8 非法写入拒绝 | 可量化和比较修改，避免盲写反射属性；fixture 指令数不是平台预算 |
| Niagara | 模板复制；renderer/stack 参数、user float/中文描述；script description 保存重载；compile 0 errors/0 warnings | 新增 SetNiagaraScriptDescription；未验证最终效果运动/帧预算 |
| Sequencer | 后台创建、30000/1001 rate、[0,120) range、Fade track/section、2 Linear keys、61 curve samples、frame 30=0.5、保存 | 后台资产/曲线编辑可用；spawnable 仍失败；未测摄像机切换/事件/Control Rig/PIE/MRQ |
| UMG | Canvas+中文 TextBlock、静态树/委托分析、2 秒 opacity 动画、2 keys、编译保存 | 原生 widget 和 MovieScene 可组合控制；未验布局视觉/MVVM/输入/HUD runtime |
| 场景 / 资产图像 | 显式 pose 的离屏 PNG、材质缩略图，均已解码实看；camera/world 前后一致 | 图像在 raw MCP image block，URN 不是 URL；capture 已适配，状态变化会失败并保留证据 |
| 性能快照 | GT/RT/RHI/GPU timing、CPU tree、实际 GPU Compute/Graphics pass tree | 可读当前编辑器负载；不能据此宣称游戏帧预算达标 |
| 项目文件 | scoped 多语言文件写入、两页 cursor 读取、拼接一致、精确删除 | 用真实虚拟根/返回 cursor，不推断 OS 路径 |

临时 PCG Actor 在 finally 精确移除；两次测试前后 actor 集合、选择及 dirty 包集合
一致。固定测试资产按指定包保存，没有 Save All 或清除用户 dirty 标记。

## 第三阶段：完整平台小游戏的运行验证

在独立新地图制作了原创 2.5D 平台 Demo，正式玩法由 Blueprint、
CharacterMovement、Enhanced Input、BT/BB、AnimBlueprint、UMG 与 Sequencer
执行；编辑器 Python 用于作者和测试，没有充当游戏 tick。

| 模块 | 本阶段实际结果 | 仍需区分的边界 |
|---|---|---|
| 角色与输入 | 平面移动、按键正反向、Space 起跳、双跳/第三次拒绝与落地重置；独立 action 与 key smoke | action 注入绕过 IMC；未测全部手柄/设备 |
| AI 与动画 | 两个独立 Controller/BB；BT 持续任务、位置/速度/方向、tick/turn 与动画变量采样；两只均转向 | 一只曾被砖块挡住，修实例巡逻范围后复测；不等于 NavMesh/EQS/任意 ABP 作者通过 |
| 交互与规则 | 一次金币奖励、接触扣命、无敌期间不重复、踩踏反弹/击败；延迟后敌人和 Controller 数量减少 | 边界 fixture 使用传送，和完整输入通关分列；未逐一注入所有失败引用 |
| HUD 与状态 | 真实 Widget、金币/生命/提示/进度；暂停冻结游戏时间；检查点跌落复活、胜败门禁、整局重开 | 键盘 HUD，未验 CommonUI/MVVM、鼠标菜单或全部 DPI |
| Sequencer | 4 秒 CameraCut/Transform Intro、真实运行绑定；自然结束、Enter 跳过、Stop、暂停中重开均恢复 Pawn 视角/移动 | CameraCut 实际画面已查看；Fade 曲线不当作屏幕 Fade 单独视觉通过；未做 MRQ |
| 材质与 Niagara | 参数材质族、世界高度背景；金币/胜利 burst 的实例激活和自动清理；实际游戏截图/录像 | 普通不透明材质/CPU 粒子不证明 World Cache、AVBOIT 或 GPU VFX；未测平台帧预算 |
| 音频与演示 | 5 种原创短音效导入/引用；真实主混音 WAV 非零，和 viewport 视频封装为有声演示 | viewport MP4 本身无音轨；首次后台失焦录到静音，临时忽略 app volume 后成功并恢复原值；未逐一试听全部事件/空间化 |
| 完整通关 | 最终从出生到终点仅通过正式 action 输入，保留 3 命、7 金币，Phase=Won 后自然落地；286 帧、15 fps、0 掉帧录像已解码实看 | 保留失败输入轨迹；低帧率录屏不是游戏 FPS 测试 |
| 生命周期与日志 | StopPIE 后检查本阶段日志范围，无新增 Blueprint Runtime Error / Accessed None / pending-kill 错误 | 早期定位错误和静音尝试保留，不能声称整个历史日志从未报错 |

小游戏流程已进入 [完整游戏制作](game-production.md) 与
[AI / 角色动画](gameplay-ai-animation.md)。Graph DSL 大型 Unicode 请求改用
UTF-8 stdin，避免 Windows argv 长度限制。新增 create-only native camera helper
保持未知完成状态不重试。玩家蓝图布局优化保留精确 node/pin/default/link 签名，
编译/保存后一致；仍有长数据线及估算穿线/交叉提示，未称 lint 全绿。

新增资产仅在独立 Demo root；测试结束保存自有包并恢复被 viewport PIE 沿用的
编辑视角。稳定 5.8 文件/junction 和原有 Content 哈希另作隔离核验；本阶段没有
UE 5.8 live 回归。Windows build/cook/package 与实际包启动另按交付记录验收，
不能从上述 PIE 结果推导。

第三阶段最终 Windows Development build/cook/stage/package/archive 成功，cook
为 0 errors、22 warnings，警告来自未修改的原有蓝图 comment NodeGuid。初包曾在
玩家 EndPlay 重复 RestoreState 时触发 MovieScene SharedPointer 断言；局部删除
该 entry 的 Stop/Restore 调用，保留正常 Finish/Stop/Skip 的恢复与自身资源清理。
8 个 sibling entries 的 canonical DSL（含位置）完全一致，重新编译保存 clean。
另做 13 项 PIE 生命周期断言和新日志检查，通过后重新打包。

新包过场中请求退出（1 秒）、自然完成后请求退出（12 秒）以及根启动器（5 秒）
均实际自然退出、返回 0；这不扩展为 packaged 完整输入通关。纯输入通关证据仍来自
PIE。首次冷启动曾在 PSO 创建收尾耗时超过 45 秒的测试 deadline，随后自行退出；
该次未取得退出码，不计通过，也未强杀。

额外实测原生 `Agent.Capture / Agent.PerfCapture / Agent.WaitForAsyncWork`：独立包
导出 960×540 图、环境 JSON、60 帧/2 秒 frame/game/render/GPU 分布，返回 0。
该截图不含 UMG，且采集会临时冻结世界；短时、限帧样本不代表整关帧预算。路线及
状态副作用见 [完整游戏制作](game-production.md)。

## 2026-11-16：菜单、存档、事件和插件补验

后续在同一引擎构建补齐普通 UMG 菜单、共享 Manual MVVM、FieldNotify 通知、
版本化存档、设置草稿和真实 Sequencer Trigger。HUD/菜单使用同一玩家持有的 VM；
过场标题与声音由 frame 6/45 的事件轨道触发，PIE 自然完成和提前跳过分别检查。

| 本轮范围 | 取得的证据 |
|---|---|
| 最终独立包完整路线 | 正式 key mapping、双跳、真实落地检查点、胜利保存；3 命/6 金币，55 项检查，退出 0 |
| 菜单与重开 | 虚拟 Slate 用户操作真实控件，OpenLevel 两次初始化，63 项跨初始化检查；修复 QA WIC 焦点延迟到 GC 释放的 ensure |
| 设置与跨进程存档 | 写进程 121 项、读进程 114 项检查；同包/同 UserDir/不同 PID，实际设置与主档哈希一致；保存退出走产品 API |
| 退出不保存 | 全新 UserDir、真实控件修改未应用画质草稿后点击退出；18 项检查，产品退出 0，主档仍不存在 |
| 存档损坏与恢复 | 11 项 codec/策略 Automation、12 组真实磁盘/API（134 断言）；备份、拒写、未来版本及真实写失败分别验证 |
| 过场 teardown | 最终包 Intro 中定时请求退出，phase=0/EndPlay 记录及自然退出 0；单列为生命周期测试 |
| Canvas 相关插件 | 新增两个 Annotation owner 后共 100 toolsets；顶层 70 项由 66 direct 和 4 meta 组成；6 项 Bridge 读取、临时标注 CRUD/聚合与恢复通过 |

Canvas 计数来自启动完毕后的新 discovery，不与旧 1,803 简单相加；客户端复用
启动期 inventory 曾只见 4 项，`reinitialize()` 后恢复完整清单。插件作用、端点、
首次启动 Python 依赖安装和具体读取/标注边界见
[MCP / Canvas 插件](ue-5.9-mcp-canvas-plugins.md)。同日后续又验证了 Codex 外部图像
生成，以及独立离屏实例的 MRG beauty/depth/normal、RawDepth 和 SceneCapture
诊断图；发现 actor 模式可在更新视口前取到旧相机，已验证独占离屏实例中先读回
自由视口再渲染的规避路线，见[生成/渲染验收](ue-5.9-canvas-generation-render.md)。
另建独立 12 帧/24 fps 序列完成三通道 320×180 输出、相机运动与 PIE 恢复检查；
测试资产清理，原地图/游戏 Intro 文件哈希不变。短片不扩大为电影级质量或音频验收。
Canvas 原生生成模型未配置/批准，按用户选择未执行；CommonUI、全部 DPI/设备及
UE 5.8 live 回归仍未验证。详细工作流见
[UI](ue-5.9-ui-workflows.md)、[存档/设置](ue-5.9-game-systems.md) 和
[独立包验收](game-production.md#后台独立包的输入存档与退出证据)。

## 已确认问题与未测部分

- **后台 Sequencer spawnable 仍失败。** 显式 sequence 的 AddSpawnableFromClass
  返回零 GUID、sequence=null；GetBindings 为空。未标 isError 也不代表成功。
  未扩大旧 5.8 fallback 的构建白名单。
- **CSV profiler 文本读取数值错误。** 真实 10 帧 / 254 stats 录制，原文件
  FrameTime 首值 23.2072，而 ReadStatValues 为十个零；原 EVENTS 全空但
  ListEvents 返回 timing 数字，已复读确认。元数据可读、ReduceStat 与同一解析器
  一致都不证明数值正确。分析前须用正常 CSV reader 对照；未改引擎，未测 csv.bin。
- **StateTree 模板不能盲目 getter→setter。** 默认完整 JSON 含隐藏内部 enum，
  原样回放被拒绝；setter 会替换结构体，不能删字段覆盖生产配置。
- **Rewind 仅 session 查询通过。** inactive / duration=0，无真实录制，故事件、
  属性、对象及 trace 读取未测。
- **Knowledge bases 为空。** 注册 schema 不代表已有知识库；未执行条目查询/写入。
- **独立进程采集需检查真实退出码。** 一次额外 CSV + 延迟 HighResShot 测试在
  游戏日志正常收尾后返回 777003；本安装源码将其定义为 crash-reporting thread
  自身异常。普通 1/12 秒退出、根启动器与 Agent 采集均返回 0，未复现该码；
  尚不能据此断定 CSV 是原因。保留失败记录，未改引擎或关闭 crash handler 掩盖。
- 第二轮补了 Geometry transient box、CurveAtlas、枚举/结构体和 Dataflow 候选
  写入，以及 MetaSound/Media/NavMesh/UI/Rig 等代表读取，见下节。Input 应用、
  MetaSound 作者、TextureGraph 作者、MRQ 渲染、打包目标、真实 runtime 与
  UE 5.8 live 回归在前两轮结束时仍未验收；第三阶段的具体 gameplay 结果见上节，
  不扩展为其他域或版本的通过结论。

## 第二轮扩展与“尚未接入”的定义

重新发现总量保持 98 / 1,803。通用 client 已动态支持这些注册 schema 的调用；
没有逐项 wrapper 不等于不能调用。当前主要缺口是专项工作流、目标资源和验证
用例，详见 [技能升级与待补流程](ue-5.9-tool-coverage.md)。

新增 5 份按需参考，记录以下代表结果及未验收部分：

- [Dataflow / 数据类型 / Deformer / Validator](ue-5.9-dataflow-data-tools.md)：
  5 个新候选均保存 clean；渐变端点/中点、枚举稳定 name 与重排整数变化、结构体
  中文元数据/Dataflow 类型连线回读通过；Deformer 只查类型/组件源；validator
  四规则和空 findings 不代表播放验收。
- [Geometry / StaticMesh / TextureGraph](ue-5.9-geometry-texture-tools.md)：
  transient 非注册组件的 box 三角形 0→12；网格/纹理读取和 TG 76 节点类型发现。
  未验 TG 连图/compile/bake。
- [MetaSound / Media / Control Rig / MRQ](ue-5.9-audio-media-tools.md)：
  真实节点/引脚、PNG 原字节、rig hierarchy 和默认 MRG 拓扑可读；MRQ/MRG 走
  官方 Python 技能，没有另一个专用 queue owner。未做 build/试听/键控/渲染。
- [动画 / AI / Input / UI](ue-5.9-animation-ai-tools.md)：
  ABP pose/rule 可读，但状态机容器仍漏非 K2 节点；BT/EQS 作者 schema 已到，
  缺 fixture；Nav 无 nav data，Input 无 LocalPlayer，CommonUI tree 无 PIE。

枚举/结构体/Dataflow 只在新的测试包写入，原关卡/actor/选择/相机保持。
两轮新增测试资产共 19 个；通过读/写/保存的路径不扩展成 runtime 结论。
原始失败断言与明确上下文错误保留在证据中，修正后继续未执行步骤，没有重放
已成功的写入。

## 技能与版本使用

本分支重写 core 入口，并更新 material、Niagara、Sequencer、flipbook 的传输与
版本路由。共享 client、Blueprint inspector/lint、capture 已适配所述 5.9 路径。
**这不代表所有旧高层 builder/render/graph helper 已移植**；先查其版本覆盖，
未移植部分走实时原生 schema 和官方 Python。

5.8 与 5.9 现分别位于 `skills/ue5.8/`、`skills/ue5.9/`；五个 sibling 包须取自同一
版本目录，避免 import 跨版本。8000 留给原设置，测试优先 8001；使用绝对
`.uproject` guard、独立 UE_MCP_CACHE_DIR，初次发现可用 --no-cache --new-session。
本次没有切换全局 junction 或发布远端。

按需读取：

- [完整小游戏制作](game-production.md)
- [角色 AI、行为树与动画](gameplay-ai-animation.md)
- [Canvas、生成动画、渲染与 Web 功能矩阵](ue-5.9-production-feature-matrix.md)
- [Blueprint / 官方 Python](ue-5.9-blueprint-python.md)
- [StateTree / PCG](ue-5.9-statetree-pcg.md)
- [UMG / SceneCapture / profiling / files](ue-5.9-editor-tools.md)
- [全部领域的升级与待补流程](ue-5.9-tool-coverage.md)
- [材质](../../unreal-material-artist/references/ue-5.9-material-mcp.md)
- [Niagara](../../niagara-vfx-artist/references/ue-5.9-niagara-mcp.md)
- [Sequencer](../../unreal-sequencer/references/ue-5.9-sequencer.md)

## 安装源码对比的限度

此前静态扫描仅计命名插件中的 AICallable / decorated tool 声明，排除测试：
StateTree 9→49、Niagara 56→57、PCG 两个工具类合计 31→33；Experimental/Toolsets 子目录
27→50。这些只能作为候选线索，不能与 live 总量相减或换算覆盖率。目录缺失可能
是跨模块迁移，声明增加也可能尚未注册；操作结论以实测为准。
第二轮确认 Input/NavMesh 使用 AIRuntimeCallable；只计 AICallable 的旧扫描不完整，
其零声明结果不能用于认定工具缺失。live PCG 主类 32 + spatial 1，原生 subsystem
另有 42 项且与主类重叠，不能将它们当作彼此独立的新增功能。

官方背景：[5.9 Preview release notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-9-release-notes?lang=en-US)
与 [Preview announcement](https://forums.unrealengine.com/t/unreal-engine-5-9-megajam-preview/2852840)。
