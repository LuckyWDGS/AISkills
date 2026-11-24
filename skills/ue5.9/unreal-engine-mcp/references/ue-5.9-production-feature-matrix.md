# UE 5.9 Preview：生成、动画、渲染与 Web 功能接入矩阵

基础核对日期：2026-11-11；Canvas 补验日期：2026-11-16。
目标为 **5.9.0 Preview / CL 60351404**；安装对比为
5.8.4 / CL 58902052。官方 [Preview notes][notes] 标注更新日期 2026-11-09，
[MegaJam 公告][announcement] 同日发布。这是 Preview 的功能和当前安装验证，
不能外推为正式版、其他平台或 UE 5.8 回归结果。未另注日期的实例状态属于
2026-11-11 的审计，不能代表后续进程或插件配置。

读取本页用于判断“新功能能否进入实际任务”。已验证的原生编辑器操作见
[实测总览](ue-5.9-preview-audit.md)；共享 client 能动态调用注册 schema，
没有专用 wrapper 不等于不能调用。

## 先区分四种证据

1. **官方宣布**说明目标功能；不说明本机已安装服务、模型或对应 MCP 工具。
2. **安装源码/描述文件存在**说明候选实现；不证明模块已加载、二进制依赖完整。
3. **当前 editor 注册 schema**才说明本实例的调用合同；重新启用插件/重启后重新发现。
4. **读、写、编译、视觉、runtime、打包**分别记录。读取 CVar 或创建资产不算效果验收。

2026-11-11 只读发现为 98 个 toolset，当时 Canvas、AnimGen/Kimodo、Forge、Fab、
DynamicWind、Lumen、Wasm 没有专属 live toolset；这只限定该次实例。
尤其 Fab MCP 已有官方公告，不能根据本机未注册推导“UE 5.9 没有 Fab MCP”。
2026-11-16 启用 Canvas 相关插件的实例刷新目录后为 100 个 toolset，增加两个
Annotations owner；顶层另有 66 个直接工具和 4 个 meta-tools。目录有重叠暴露，注册
数量不表示执行覆盖率。插件分工、缓存刷新、
实际读写与未测范围见 [MCP / Canvas 插件](ue-5.9-mcp-canvas-plugins.md)。

## 功能与当前控制边界

| 功能 | 5.8 → 5.9 安装/官方差别 | 当前实例证据 | 可采用的路线及本轮验收 |
|---|---|---|---|
| Unreal Canvas | 官方新增 Experimental 工作空间；本安装新增 Annotations、Bridge、Graph 三包 | 2026-11-11 三包 enabled=false；2026-11-16 已启用相关插件；sidecar v0.21.0 后续 MCP 目录为 132 项，image-generator 可执行列表为空 | 六项 Bridge 读取、Annotation scratch 生命周期、MRG 三通道静帧/原始深度及 12 帧短序列通过；Codex 外部生图另验通过且尺寸有偏差；后续已通过原生图生成程序化星形 GLB 并导入 StaticMesh，见[本地 Mesh](ue-5.9-canvas-mesh.md)；AI Mesh 模型列表为空，原生 AI 生成未测；渲染另见[生成/渲染实测](ue-5.9-canvas-generation-render.md) |
| AI 动画 | `AnimGen` 两版本已有；新增 `UAFAnimGen`、`AnimGenOffline`、`Kimodo` | 四包均未启用；AnimationAssistant 的 SequencerDirector 工具不等于文本生成 | 先核对模型/骨架/依赖，再查启用后的公开 Python 或原生 schema；未下载、未生成、未重定向 |
| Forge | 官方定义为编辑器中的一组 **web-based designer tools** | 当前安装未发现同名插件；无同名 live toolset | 先定位具体工具、入口和服务；目前没有可确认的自动化合同，不能发明 `Forge.*` 调用 |
| Fab 目录/库/安装 MCP | 官方公告新增目录搜索、库浏览、安装免费或已购资产 | 当前无 Fab toolset，`GetPluginInfo("Fab")` 明确未找到；旧 5.8 商店插件存在，5.9 安装无同名描述文件 | 先解决当前构建的官方集成/登录，再发现 schema；本轮未登录、检索、购买或安装资产 |
| Fab 图像/网格生成 | 官方 notes 另列为 generative-service integrations | 当前没有可确认的 Fab 专属生成调用合同；不能与传统商店插件或目录 MCP 混为一项 | 核对具体服务、账户、额度/费用与授权；未验 Fab 生成，另一次 Codex 图像服务调用不算 Fab 覆盖 |
| Lumen World Cache | 本安装新增渲染器实现，官方说明需 Hardware Ray Tracing、按项目开启 | 原生 Console 可读；`Supported=false`、`Allowed=true` | 当前没有启用；只读配置和能力门槛通过，画质/帧预算未测 |
| AVBOIT | 本安装新增实现；官方标题写作“ABVOIT”，正文/源码/CVar 使用 **AVBOIT** | `r.OIT.Method=0`；Support=1、Nanite=1、NonNanite=0 | 当前未选择 AVBOIT；只能确认支持配置，未做透明叠层画质/开销测试 |
| DynamicWind | 两版本都包含实验插件；5.9 notes 说明骨骼植被、局部力等行为 | discovered、enabled=false；无专属 schema | 公开源有 wind/force/push-capsule API 候选；未配植被资产、未模拟，不应把普通 WPO 摆动说成同一功能 |
| PCG | 既有功能及保留/增强的编辑控制 | main 32 + spatial 1；另有 subsystem 42，存在重叠；插件启用 | 编图、普通组件执行与精确两点 DataView 已有编辑器证据；未测 GPU/World Partition/游戏运行时 |
| Wasm / WebGPU | 官方新增 Experimental Web 目标；本安装包含 `Engine/Platforms/Wasm` | 无专属 MCP；当前未配置文档规定的 SDK 根，目标工程为 content-only | 有编译/部署文档，尚不具备本工程 Web 打包证据；未下载工具链、转 C++、cook 或浏览器运行 |

表中的源码“新增”仅指所比较两份安装，不按目录数量计算功能数或覆盖率。
Forge 和 Fab 的缺失也不能用自写桥接、引擎补丁或无依据启用插件补成“已支持”。

## 其他制作功能：候选路由与未测范围

以下补充定位来自已有官方 notes、安装源码及保存的 98-toolset 目录，未再次连接
编辑器。C++ 类型/函数名只是 **source candidate**，不代表同名 MCP/Python 调用
已验证；实际任务先重新查 live schema，缺口再由官方 Python 查询符号和合同。

| 功能 | 已定位的真实名称 | 当前路由与验收边界 |
|---|---|---|
| IK 重定向：Proximity IK / Pelvis Volume / Limb Twist | `RelativeIKOp` 插件的 `FIKRetargetProximityIKOp`、`FIKRetargetPelvisVolumeOp`、`FIKRetargetLimbTwistOp` | 目录无独立 IK/Retarget owner；需确认插件、源/目标骨架、Retargeter 及公开脚本符号，再验证接触、骨盆和扭转。三项均未执行；Demo 使用同一 Manny 骨架，不需要重定向 |
| Chooser 作者 | `UChooserTableEditorLibrary` 提供类型发现、签名、列/行及单元格编辑的 Blueprint/Python 候选 | 无独立 Chooser owner；先查当前 Python 符号与真实类型，不编造 `Chooser.*` 工具。未建表、编辑或求值；使用 ABP 不等于 Chooser 已测 |
| PCG Concave Hull / custom HLSL | `UPCGConcaveHullSettings`，显示名 `Find Concave Hull 2D`、处理 XY 平面；`UPCGCustomHLSLSettings` 有 source text 读写公开声明 | 已有 PCG owner 的 `ListNativeNodes` / `GetNativeNodeSchema` / `AddNode` / `UpdateNode` 合同及普通图/DataView 实测；先查目标节点 schema，HLSL 缺口查 Python。凹包数值、HLSL 修改/编译、GPU 执行均未测 |
| Water 浅水河流 / 输入绘制 | `WaterAdvanced` 的 `ShallowWaterRiverActor.h`；notes 明确新增 capture 排除 actor、碰撞分辨率及水输入绘制 | 无独立 Water owner；仅源码/文案候选，需确认组件属性或公开 Python 符号。未建水体、采集、绘制或模拟，普通场景材质不算验证 |
| World Partition / Data Layer | `UWorldPartitionSubsystem`；`UDataLayerInstance` 的 `K2_GetChildren` / `K2_CanAddActor` 公开声明 | 无独立 WP/DataLayer owner，但已有 `LevelToolset` 的 Data Layer 查询/创建/actor 分配，以及 World Partition actors 的编辑器 `LoadActors` / `UnloadActors` 合同；后者不是 Data Layer runtime state。新子层/合法性、运行时状态和流送 API 仍需 schema/符号确认，未执行。独立小关不需要改成 World Partition |
| Sequencer 标记范围 | `MovieSceneSequenceExtensions.AddMarkedFrameRangeToSequence` / `GetMarkedFramesFromSequence` 已在目录；`start==end` 为单帧，范围为 `[start,end)` | 是已注册合同，尚未调用；帧率单位、范围回读、保存重载、吸附/播放行为分别验收。已测 Transform/CameraCut/Fade 不覆盖 marks / mark ranges |
| Nanite 剔除改进 | notes 描述简单/复杂实例分流与多层级遍历；`NaniteCullRaster.cpp` 的 simple 路线、`NaniteShared.cpp` 的 adaptive fanout 实现可定位 | 属渲染器优化，无独立 Nanite owner；已有 StaticMesh 的 Nanite 查询/启用及 Console 合同。启用网格会 rebuild，不证明新剔除收益；未做代表大场景的可见性/伪影/GPU 对照，不计性能或 runtime 通过 |

上述定位原文、源码行号/哈希和选定注册 schema 保存在本次 session 的
`feature-supplement-final.json`。它们不扩大既有 Demo、PCG、Sequencer 或网格测试结论。

## Canvas：编辑器工具与生成服务分别准备

官方描述覆盖文字、图片、视频和网格生成，以及用场景/参考图保留构图。
选择的外部生成模型使用用户自己的 API keys；服务、模型权限和费用取决于所选
provider。不能将“启用 Canvas”写成“已获得所有生成模型”，也不应要求不相关的
OpenAI key。独立注释和采集工具本身不等于外部生成调用。

安装源码的职责划分：

- `UnrealCanvasAnnotations`：独立空间注释、场景/GBuffer 采集核心和 MCP 工具，
  不依赖 Bridge。候选工具包括 `ListAnnotations`、`GatherVisibleAnnotations`、
  `PlaceAnnotation`、`UpdateAnnotation`、`RemoveAnnotation` 及分组可见性控制。
- `UnrealCanvasBridge`：MRG 与媒体、网格操作等桥接候选，需要 MCP 插件。
  `UnrealCanvasGraph` 提供原生 Slate/EdGraph 客户端、文档模型、导入缓存和预览。
- **Canvas server** 拥有执行和存储；插件客户端不是完整服务。设置支持已有本地
  server builds，也可选择匿名 HTTPS Artifactory builds；后者为空时不发 catalog 请求。
  这不涵盖 Python 依赖安装或节点联网；启动安装边界见上述插件参考。
  实际启动 server 可使用临时端口，不能把回退 `localhost:7777` 当成当前连接地址。
- 模型根提示包含 SAM2、DepthAnything、VGGT、LangSAM、DexiNed、pose-fit 等，
  路径提示不说明权重已下载、可运行或许可已满足。

2026-11-16 的插件状态、直接 MCP 工具读取、临时标注生命周期及 sidecar ready
已有专项证据，见 [MCP / Canvas 插件](ue-5.9-mcp-canvas-plugins.md)。启动 slow task
期间缓存的目录曾只含四个 meta-tools；刷新 client 后恢复完整发现，不能将早期
目录当作工具缺失。前端未 attach 时的零项远端目录与 UE 侧直接工具是不同注册面；
同日后续 fresh discovery 已取得 132 项 sidecar 工具，`get_graph_docs` 读取成功，
`list_models` 的 image-generator 列表仍为空。

进入实际 Canvas 任务时：先限定功能和插件，核对该步骤的依赖及需要连接的 server；
如需重启，保护当前任务和未保存资产。重连后先查 fresh identity 和 live schema。
只有调用生成模型的步骤才继续核对模型、service registry 与 provider。只提供所需
认证，不把 key、模型缓存或服务运行产物写进 skill 仓库。采集、生成、导入资产
绑定与最终画面分别验收。2026-11-11 审计没有启用或启动服务；2026-11-16 补验
的初始检查覆盖局部读写与本地 sidecar 启动。后续新增的外部 Codex 生图、真实 MRG
静帧和原始深度，以及 actor 相机时序问题，见
[生成与实际渲染验收](ue-5.9-canvas-generation-render.md)；没有据此扩大为 Canvas
原生生成节点或 AI 动画通过。

主要安装源码（均相对 `Engine/`）：

```text
Plugins/Developer/UnrealCanvas/UnrealCanvasAnnotations/Source/UnrealCanvasAnnotationsEditor/Private/UnrealCanvasSpatialAnnotationToolset.h
Plugins/Developer/UnrealCanvas/UnrealCanvasBridge/Source/UnrealCanvasBridge/Public/UnrealCanvasBridgeSettings.h
Plugins/Developer/UnrealCanvas/UnrealCanvasGraph/Source/UnrealCanvasClient/Public/UnrealCanvasServerClient.h
```

## AI 动画：模型与生成结果还需单独闭环

`AnimGen` 的训练/控制器 API、`UAFAnimGen` 的框架集成、`AnimGenOffline` 的
Sequencer 离线生成与 `Kimodo` 的文本/轨迹/姿势条件生成是相关但不同的层。
不能把现有 AnimGen 包重新计为 5.9 首次新增，也不能把普通 Sequencer/Control Rig
工具的可用性当成 Kimodo 推理可用。

Kimodo 的当前安装源码明确要求：

- Python ML packages 和 pinned 依赖；`AnimGenOffline` 还依赖 UAF、AnimGraph、
  AnimNode、Control Rig、MovieSceneAnimMixer、IKRig 等。描述文件存在不证明
  依赖解析、Python 包安装或启动成功。
- 动作权重由 Hugging Face 下载/缓存，默认候选包括 `nvidia/Kimodo-SOMA-RP-v1.1`。
  `.tps` 声明权重 **运行时下载、未随插件分发**，使用 NVIDIA Open Model License；
  Python 代码的 Apache-2.0 不代替模型许可。
- 文本编码器为本地 LLM2Vec / Llama 3 8B。`KimodoSettings.h` 指出首次下载需要
  Hugging Face read token 与 `meta-llama/Meta-Llama-3-8B-Instruct` 访问权限；可复用
  环境或本机已有登录，不需要把 token 写进项目共享配置或 skill。
- 本构建 `load_model.py` 明确忽略兼容参数 `text_encoder_url`，只选择本地编码器。
  不要因 registry 仍保留默认 `127.0.0.1:9550` 就要求启动一个当前 loader 不使用的
  服务。`LOCAL_CACHE=true` 缓存未命中时仍会尝试联网，不是严格离线开关。
- 支持 CUDA 和更慢的 CPU 路线，提供文本编码器驻留/精度选项。源码设置提示
  NF4 编码器约 6 GB、full 约 16 GB，CPU fp32 可能更多；这些是源码提示，
  不是本机内存测试、最低要求或生成速度保证。还需为动作模型和编辑器留资源。

可复用的后续验证单元应是“一条固定 seed/提示词/时长的动画”：确认模型来源、
骨架与目标约束 → 生成 → 骨骼/root motion/foot contact 读取 → 导出或绑定真实
AnimSequence/Sequencer → 播放检查 → 再测试取消、错误与重复生成。此轮只验证
描述文件、加载器和 disabled 状态，没有生成资产或声称这些阶段完成。

源码定位：

```text
Plugins/Experimental/Animation/Kimodo/Source/Kimodo/Public/KimodoSettings.h
Plugins/Experimental/Animation/Kimodo/Content/Python/kimodo/kimodo/model/load_model.py
Plugins/Experimental/Animation/Kimodo/Content/Python/Lib/Kimodo-SOMA-RP (model weights)_vv1.1.tps
Plugins/Experimental/Animation/AnimGenOffline/Source/AnimGenOffline/Private/Scripting/AnimGenOfflineMixerExtensions.h
Plugins/Experimental/UAF/UAFAnimGen/UAFAnimGen.uplugin
```

## Forge 与 Fab：按具体服务接入

Forge 的当前可靠定义来自官方 release notes：编辑器中的 web designer tools。
本轮尚未定位到当前安装的具体入口、服务端或调用 API。正确下一步是定位产品
组件和所需服务，再核对其合同；不能仅按名称将其当成 Fab，也不能给出未发现的
插件开关、端口、key 类型或下载命令。

Fab 至少分三件事：传统商店界面、公告中的 catalog/library/install MCP、
notes 中的 image/mesh generation integrations。当前安装旧商店插件缺失且
新工具未注册，仍可明确知道官方宣布了后两项；仅创建本地 Material/StaticMesh
或调用本地 Asset import 不能算 Fab 服务测试通过。

实际资产获取须先确认账号、目录项、许可、来源版本和免费/已购状态。已购项安装
不等于授权购买新付费项；生成服务的额度与 key 另外核对。成功后还要检查导入的
实际路径、材质/纹理/骨架引用、编译和游戏目标适配。本轮没有采购、获取或导入
外部素材，也没有未经证实的 Fab/Forge wrapper。

## 渲染增强：用读数判断当前启用状态

原生 `ConsoleToolset` 提供 `SearchCVars`、`GetCVarValue`、`SearchConsoleCommands`、
`SetCVarValue`、`RunConsoleCommand`。后两者会修改/执行；先读相关只读标志、
项目重启和 shader 条件。能执行控制台命令不证明存在独立领域 MCP 工作流。

### Lumen World Cache

`Source/Runtime/Renderer/Private/Lumen/LumenWorldCache.cpp` 定义
`r.Lumen.WorldCache.Supported` 为只读项目 shader 开关；`Allowed` 是 scalability
允许值。当前分别为 false/true，所以 **没有启用 World Cache**。

`ShouldCompileShaders` 要求项目支持、Lumen GI、wave operations、ray-tracing
shader 编译与 inline RT；`IsEnabled` 还要求当前视图实际使用 Hardware Ray Tracing
及支持所需 ray-gen/inline 路线。不能通过临时 `SetCVarValue` 绕过只读 shader 支持，
也不能仅看 Allowed=true 就承诺效果启用。真实验收需明确目标 GPU、项目配置、
重启/编译、相同机位画面对比与 GPU timing；此轮未修改设置或做性能结论。

### AVBOIT

全称为 Adaptive **Voxel-Based** Order Independent Transparency。官方标题的
ABVOIT 与正文拼写不一致，搜索/API 使用源码的 **AVBOIT**。

当前 `r.OIT.Method=0`（sorted），未选择 AVBOIT；`r.AVBOIT.Support=1` 是只读支持
开关，`Nanite=1`、`NonNanite=0` 分别控制不同路线，不能合并称为“所有透明已开启”。
源码见 `Source/Runtime/Renderer/Private/OIT/AVBOIT.cpp` 和 `OIT.cpp`。

官方说明支持 Nanite 和非 Nanite 透明、减少交叠排序跳变，并要求透明材质输出
自己的颜色以正确合成。真实任务应挑玻璃/烟雾/粒子交叠用例，检查材质、目标平台
与 shader 支持，再对照内存、overdraw、伪影和帧时。仅使用不透明平台游戏材质
无需为了展示新版本而开启它。本轮只读设置，没有这类画质或性能验收。

## DynamicWind 与 PCG：既有体系的控制范围

DynamicWind 在比较的 5.8/5.9 安装中都存在，不能全称为 5.9 新增。
5.9 描述的是 GPU 骨骼植被模拟和局部交互；当前插件 disabled。

源码 `DynamicWindSubsystem.h` 提供 `GetBlendedWindAmplitude`、
`UpdateWindParameters`、`RegisterForce/UpdateForce/ReleaseForce`、push capsule
与 external volume 的注册/更新/释放候选。它们是 BlueprintCallable 等公开 API，
尚不是当前 MCP schema 的验证。取得适当工具/公开 Python 暴露后才可调用，不能
凭 C++ 声明猜 Python 名称或绕过编辑器语义。

资产侧需要适配的 skeletal foliage / 动态风骨架数据与 transform provider；
`DynamicWindData` 是 GPU-only。USD 自动导入需要含 DynamicWindSkeletonAPI 的
骨架，且设置说明只支持 Interchange USD，不支持旧导入器。editor library 还含
PivotPainter 转换和 JSON 数据导入候选；带文件对话框的方法不适合后台自动化。
局部力/胶囊的 handle 更新、释放、owner 生命周期与边界要单独 runtime 验收。
普通材质 WPO 的廉价摆动可以用于美术目标，但不能冒充上述骨骼风场测试。

PCG 的原生编图/执行不要求模型 key 或外部生成服务；GPU、世界分区、Loop、
植被/水/其他插件互操作则需各自启用条件和数据。已验证的普通组件和两点输出
见 [StateTree / PCG](ue-5.9-statetree-pcg.md)。不要把工具计数相加为新增，或将
编辑器生成的结果外推为 packaged runtime。

## Wasm / WebGPU：构建目标需要独立工具链

官方 MegaJam 公告将 Web 标为 Experimental，说明 C++ 工程、mobile renderer 和
Chrome 优先，并提到 source build。当前安装的支持矩阵进一步允许**含 Web 库和
headers 的 Preview Launcher build 或 source build**；不能把“必须自己编译引擎”
当作所有安装的统一要求。安装文档位于
`Engine/Platforms/Wasm/Docs/`，应以目标发行包的 `GettingStarted.md`、
`SupportMatrix.md` 和 SDK 描述为准，不按旧 UE4 HTML5 教程安装。

本安装规定：

- **C++ 工程**；content-only 不受支持。当前测试工程无 Modules/Build.cs，未转换。
- **Emscripten 6.0.10**，`Config/Wasm_SDK.json` 的 Main/Min/Max 都相同。
  SDK 根按 first-defined 的 `WASM_EMSDK_ROOT` → `EMSDK` →
  `UE_SDKS_ROOT/HostWin64/Wasm/6.0.10` 解析。先定义的无效路径会遮住后项；
  改环境需重启读取它的进程。当前三个根均未定义；这不能证明整台机器没有任何
  SDK，但当前工作流尚无已配置/已验证工具链。
- Python 3 构建/页面工具，浏览器验证 harness 还需 Playwright。浏览器侧检查
  WebGPU、所需纹理压缩、Memory64，以及跨域隔离/SharedArrayBuffer 等目标要求。
- Preview 支持的渲染 tier 是 ES3_1 forward `SP_WEBGPU_ES3_1` 与 deferred
  `SP_WEBGPU_ES3_1_DEFERRED`；`SP_WEBGPU_SM5` 属额外实验路径。
  不能承诺 desktop Lumen/Nanite/VSM/Hardware RT 在 Web 上直接保留。
- 手机 Safari、设备内存、线程、音频、页面安全头和部署方式都有版本限制。
  公告还持续列已知问题；本地文档的支持矩阵不是所有设备通过的证据。

这属于编译/cook/打包/部署工作流，当前没有一个 Wasm MCP 工具替代 SDK。
进入该任务时先验证 C++ target 和工具链，再做最小目标 cook、页面部署、实际
浏览器输入/画面/音频/重载存档检查，最后才衡量性能与资源预算。本轮没有下载
SDK、构建、发布或运行 Web 包。

## 本页验证记录与使用约束

2026-11-11 已收集：当时 toolset 清单及选定完整 schema、插件 discovered/enabled 状态、
上述六个渲染 CVar、两版精确文件存在/哈希、所引用安装源码、官方 notes/公告
正文与 SDK/project 只读检查。没有批量启用插件、改 shader 项目开关、安装模型、
启动外部服务或修改引擎。运行记录和绝对路径保存在忽略的 `.codex/session/`。
2026-11-16 Canvas 补验另见上述专项链接；它不更新其他功能的旧日期状态。

独立样例中的参数材质、MI 和短寿命 CPU Niagara burst 可以验证现有 MCP 作者
能力；它们不验证 Canvas/AI 动画/Fab/World Cache/AVBOIT/Wind/Web 服务。
材质“图中无纹理采样节点”也不保证编译统计采样数为零，统计可能包含引擎 pass
开销。Niagara 声明 User 参数不等于已绑定；模板中多出的 ribbon/事件消费者要
按实际目标检查。专项方法见
[材质](../../unreal-material-artist/references/ue-5.9-material-mcp.md) 与
[Niagara](../../niagara-vfx-artist/references/ue-5.9-niagara-mcp.md)。

官方文案与安装可不完全一致。例如 notes 说旧 Python Foundation Packages 移除，
本构建仍发现 disabled 的同名描述文件，AnimGen 描述文件也引用它；不得仅根据
宣传文案推断依赖已就绪。将具体失败/缺依赖作为当前构建事实记录，然后使用
真实注册接口；不把静态源码候选升级成完成状态。

[notes]: https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-9-release-notes?lang=en-US
[announcement]: https://forums.unrealengine.com/t/unreal-engine-5-9-megajam-preview/2852840
