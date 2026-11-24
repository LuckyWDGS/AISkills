# UE 5.9 的 MCP 与 Canvas 插件分工

区分 UE 5.9 中与 MCP、Canvas 相关的几个插件：各自的方向、注册入口、连接副作用和
验证方法。参数、注册入口和副作用说明来自安装源码，调用前须与目标实例的 schema 核
对。原生 Blueprint 元数据见
[ue-5.9-blueprint-python.md](ue-5.9-blueprint-python.md)；Canvas 的产品层分工见
[ue-5.9-production-feature-matrix.md](ue-5.9-production-feature-matrix.md)。实测
结果见文末[验证记录](#验证记录)。

同日后续已完成外部 Codex 图像生成、离屏 MRG 三通道静帧与原始深度检查，发现并
规避了 actor 相机切换的时序问题。Canvas sidecar 后续目录为 132 项；原生生成模型
仍无可执行 binding。按用户选择未配置/批准模型，详见
[生成与实际渲染验收](ue-5.9-canvas-generation-render.md)。下文初始插件检查的
“前端未 attach / 零项”保留为历史观察，不能代表后续可用状态。

## 目录

- [先区分五个名字](#先区分五个名字)
- [方向与注册入口](#方向与注册入口)
- [Metadata 在 5.9 的替代范围](#metadata-在-59-的替代范围)
- [MCP Client Toolset 的连接副作用](#mcp-client-toolset-的连接副作用)
- [Annotations 的本地能力与回滚](#annotations-的本地能力与回滚)
- [Bridge 不只是工具开关](#bridge-不只是工具开关)
- [原生 server 的最小验证](#原生-server-的最小验证)
- [源码定位](#源码定位)
- [验证记录](#验证记录)

## 先区分五个名字

| 插件面板名称 | 技术名与作用 | 什么时候需要 | 源码声明的默认值 |
|---|---|---|---|
| MCP Blueprint Metadata | 项目插件 `MCPBlueprintMetadata`；Blueprint/Python 可调用的元数据辅助库 | 旧版本原生 API 缺口的兼容备用；5.9 先用原生 BlueprintToolset | `EnabledByDefault=true` |
| MCP Client Toolset | `MCPClientToolset`；让 UE 作为客户端，把外部 MCP server 的工具接入 UE ToolsetRegistry | UE 内 AI Assistant 或 Canvas 需要调用外部工具时 | `EnabledByDefault=false` |
| Unreal Canvas Bridge | `UnrealCanvasBridge`；UE 场景/MRG/资产工具、Canvas 界面与独立 server 的双向桥接 | 明确使用 Canvas 工作流、渲染、媒体或资产处理时 | 描述文件未写 EnabledByDefault |
| Unreal Canvas Spatial Annotations | `UnrealCanvasAnnotations`；空间提示、分组 matte、场景/GBuffer 采集与工具 | 需要给场景对象或空间区域附带提示、蒙版及采集时；可独立使用 | 描述文件未写 EnabledByDefault |
| Unreal MCP | `ModelContextProtocol`；UE 的 MCP server | 外部 Codex 等客户端通过原生工具控制 UE | `EnabledByDefault=true`；server 自动启动默认另为 false |

插件文件存在、`.uproject` 显式条目、默认启用、当前加载、工具注册和工具执行成功是六种
不同证据。截图中的勾选和没有 `.uproject` 条目都不足以决定当前状态；依赖还可能间接
启用插件。先核实 editor identity、版本和绝对项目路径，再查目标实例的 PluginToolset、
完整 `tools/list` 与 toolset schema。

## 方向与注册入口

`外部客户端 → Unreal MCP → UE 工具` 是本 skill 的主要路线。
`UE 工具使用者 → MCP Client Toolset → 外部 MCP server` 是相反方向，不是 Codex
控制 UE 的额外必需安装。Canvas Bridge 会同时使用这两条路线。
Codex 的 `UNREAL_MCP_URL` 指向 UE server；MCP Toolset Servers 中的 URL 是 UE
向外连接的目标。Canvas sidecar 是另一个进程/endpoint，即使也使用 `/mcp`，它的
identity 和工具目录也不等于 UE server。需要分别读取，不能互换这两个地址。

| 源码注册面 | owner / 名称候选 | 发现方式与限制 |
|---|---|---|
| Metadata | `UMCPBlueprintMetadataLibrary` | 只有 BlueprintCallable，无 AICallable，也无直接 MCP 注册；不应等待名为 Metadata 的原生 toolset |
| MCP Client Toolset | 配置的 `Name`；工具成为 `<Name>.<远端工具名>` | 连接成功后从远端 `tools/list` 动态建 schema；插件名称不是固定工具目录 |
| Bridge 的 UE 侧 | 直接名称 `GetStatus`、`GetMRGPasses`、`GetMRGVariables`、`GetAssetsByType` 等 | `IModelContextProtocolModule::AddTool`；必须查顶层 `tools/list`，只查 `list_toolsets` 会漏掉 |
| Bridge 的 Canvas server 侧 | 动态 toolset `UnrealCanvasBridge` | 经 MCP Client Toolset 连到 sidecar 的 `/mcp`；前端未 attach 时远端可以成功返回零工具，只有 synthetic reconnect 也不代表工作流可用 |
| Annotations 的直接 MCP 面 | `List3DAnnotations`、`Place3DAnnotation`、`Update3DAnnotation`、`Remove3DAnnotation`、`GatherVisibleAnnotations` 等 | 顶层 `tools/list`，参数是该直接 schema 的小写字段 |
| Annotations 的反射面 | 类 `UnrealCanvasSpatialAnnotationToolset` 与 `UnrealCanvasSpatialAnnotationEditorSubsystem`，模块 `UnrealCanvasAnnotationsEditor` | 两个注册入口；前者包装直接工具，后者还提供结构化对象及完整状态读写。精确 owner 和参数以 live schema 为准 |

`ModelContextProtocol` 的 ToolsetRegistry adapter 只负责 registry → MCP，不会自动把
任意直接 MCP 工具反向变成 Assistant toolset。Annotations 因而显式维护包装类。
Tool Search 模式用发现/派发 meta-tools 代替大量 registry 工具的顶层注册；插件直接
注册的工具仍应从完整 `tools/list` 核对，不要因未出现在 toolset catalog 就判定缺失。

同一编辑器实例中的 LateStartup、插件加载或外部连接也会增加工具。客户端可能保留启
动 slow task 期间取得的目录，即使 PID 没变也会漏掉后注册的工具。先等启动完成，再
用 `--refresh-schema` 或 `--no-cache --new-session` 重新取得完整 `list-tools` 和
`list-toolsets`；持有 client 对象的脚本可用 `reinitialize()` 清除会话内目录
/schema。 `--no-cache` 单独只关闭磁盘 schema cache，不会禁止恢复已有 session 的
目录。

对完整目录中已发现的直接名称，5.9 的 `describe_tools` 也接受 bare name；
`call_tool` 的参数只给 `tool_name` 与 `arguments`，省略 `toolset_name`。
`describe_tools` 的参数示例：

```json
{"tool_names":["GetStatus"]}
```

随后 `call_tool` 的参数：

```json
{"tool_name":"GetStatus","arguments":{}}
```

使用已核实 identity 的共享 client 时，上述两步分别是
`client.call_tool("describe_tools", 参数)` 与
`client.call_tool("call_tool", 参数)`。这是低层调用；按描述结果的 inputSchema 检
查参数，并显式检查描述结果的 `errors` 及两次工具结果的 `isError`，再解释返回值。

## Metadata 在 5.9 的替代范围

辅助库提供成员变量 Tooltip、局部变量 Tooltip、函数 Tooltip、函数 Category 的
Set/Get。Setter 使用事务、Modify/MarkBlueprintAsModified 等编辑器操作；不会替调用者
编译或保存。它的“stock UE 不暴露这些字段”描述是历史背景，不能用于否定 5.9 原生 API。

原生 `BlueprintToolsets.BlueprintToolset` 源码候选覆盖：

- `Get/SetVariableTooltip(Blueprint, VariableName, Graph)`：省略 Graph 为成员，传函数
  Graph 为局部变量；空 Tooltip 清除。
- `Get/SetVariableCategory`：同样支持 Graph 范围。
- `Get/SetFunctionFlags(Graph, Flags)`：函数提示、类别和其他 detail-panel flags；只改
  明确设置的字段，写后重新编译。新建函数还可检查 `AddFunctionGraph` 的 flags。

目标 schema 暴露这些能力时使用原生 API。本技能包不附带该项目扩展；项目里已安装的
扩展保持原状，不自动重装、移除或禁用。

## MCP Client Toolset 的连接副作用

`Editor Preferences > Plugins > MCP Toolset Servers` 使用每项目用户设置。配置支持
SSE、Streamable HTTP、Stdio；Stdio 会启动 `ExePath` 进程。启用且 Name/endpoint 有效的
配置在子系统初始化时连接，设置更改也会触发 live refresh。失败采用自动退避重连；
要停止某个配置持续连接，应禁用该配置，不能把 retry interval 设为 0 当成停止。

鉴权由所接 server 决定：可无鉴权、Bearer token，或 OAuth 2.0 Authorization Code +
PKCE。OAuth 可能打开登录流程并保存用户 token；不要为了检查插件状态读取或输出凭据。
本地自有只读 MCP fixture 不需要模型账号或云 API key。

远端 schema 保留自己的 accessMode；若缺失，适配器由 MCP hints 推导：readOnlyHint →
Read；否则 destructiveHint（缺省 true）→ Execute；否则 Write。名称含 Get 不代表
只读。适配器还会添加 synthetic `reconnect`，但远端已有同名工具时保留远端工具语义。
调用 reconnect 会重建连接，不能作为只读健康检查。

## Annotations 的本地能力与回滚

该插件不依赖 Bridge，也不要求 Canvas server 或生成账号。它包含三个 Editor 模块：
`UnrealCanvasAnnotationsCapture`、`UnrealCanvasAnnotations`、
`UnrealCanvasAnnotationsEditor`；插件依赖为 ModelContextProtocol 和
ToolsetRegistry。编辑器模块同时安装 viewport 绘制、周期 gather 和保存钩子；工具
可用还需要实际 Level Editor/world。

优先只读候选是 `ListAnnotations` / `GetAnnotations`、`FindAnnotation`、
`GatherVisibleAnnotations`、`GetVisibleGroups`、`GetActiveGroup`、
`ShouldPersistNewAnnotations`、`AreLabelsVisible`、`IsOverlayVisible`、
`GetCaptureStage`。 `GatherVisibleAnnotations` 中 visible=false 可表示视锥外或颜
色组隐藏，不等于记录被删除。

写入边界：

- 默认 `bPersistNewAnnotationsToLevel=true`，新代理 Actor/组件会随关卡保存并置脏。
  `SetPersistNewAnnotations(false)` 是本会话 scratch 模式，只影响之后创建的标注；
  不能把已有持久标注自动变回临时内容。`PersistAnnotations` 会提升全部 scratch 标注，
  不是单一 fixture 的清理工具。
- `Place3DAnnotation` / 包装层要求非空 prompt；遗漏 location 使用镜头前位置。
  fixture 应传明确 transform/location 和 group。该工具实现的 placement 使用
  bSelect=false；UI placement 可改变选择，因此仍记录测试前的选择。
- 直接/包装层 `UpdateAnnotation` 的空 prompt 被忽略，不能用它清空；不要把这一点套用
  到另一个接口的 setter。传递对象引用或 GUID 应服从所选 live schema。
- `RemoveAnnotation` 对代理标注会删除代理 Actor，对既有场景对象则移除标注/恢复相关
  matte 状态；按 selection、actors 或 all 删除的工具范围更大。仅清理测试返回的 ID。
- Isolate 会改可见组及 active group；SetVisible 会在 active 被隐藏时改为最低可见组。
  ShowAll 只显示全部，**不能恢复原先组合或 active group**。应先读并保存这两项，
  恢复可见组后再恢复 active group。overlay、labels、persist 开关也分别恢复。

独立 fixture：在隔离测试关卡读取标注列表和状态 → 会话 scratch 模式并回读开关 →
明确位置创建一个唯一提示的标注 → 读回 ID、prompt、group、位置和 gather → 修改该
标注并读回 → 按该 ID 删除 → 恢复所有捕获的状态，确认原列表、选择和 dirty 状态未
被无意改变。以 `ShouldPersistNewAnnotations` 核对新建模式，逐对象持久化及保存重
载另用目标 schema 实测。直接工具的 `prompt/group/location` 和 subsystem setter
的 `bPersist` 属于不同合同，不能因功能相近就互换参数形状。这验证标注生命周期；不
证明 GBuffer 图像、外部编辑或 AI 生成结果正确。渲染验证另列。

## Bridge 不只是工具开关

Bridge 除 Annotations/Graph、ModelContextProtocol/MCPClientToolset 外，还依赖 MRG、
LevelSnapshots、GeometryScripting/MeshModeling、Interchange/GLTF、GaussianSplat、媒体
与编解码模块、WebBrowser、Python/ML/OpenCV、AIAssistant 和资产 provenance/validation。
描述文件还列出 faster-whisper、ctranslate2、huggingface-hub、onnxruntime 等 Python
requirements。插件存在不证明依赖、包或模型已安装。普通 Blueprint/MVVM/菜单工作无需
为了获得 MCP 而启用整个 Bridge。

**Python 包安装独立于 sidecar 的 Build Source。** Bridge 明确启用 PythonMLPackages；
后者的 Win64 requirements 固定 `torch==2.5.1+cu124`、`torchaudio==2.5.1+cu124`、
`torchvision==0.20.1+cu124`，并加入 PyTorch CUDA 12.4 wheel index。PythonScriptPlugin
会汇总所有已启用插件的 PythonRequirements；默认 `bRunPipInstallOnStartup=true` 时，
有缺包就在 Python 初始化的 game thread 同步安装。因此即使 LocalPaths/Artifactory
未请求任何 sidecar build，也可能在 MCP ready 之前下载大型 CUDA wheel 与其他依赖。
这不是调用了生成节点的证据。

当前源码支持的启动安装开关位于 **Project Settings > Plugins > Python** 的 Python Pip
Install 分类：`bRunPipInstallOnStartup=false`，配置类为
`/Script/PythonScriptPlugin.PythonScriptPluginSettings`（Engine config，需重启）。它跳过
启动阶段的依赖安装，不会取消已运行的 pip，也不代表 Python 环境完全不写文件：
初始化仍会生成 requirements、准备 venv/本地安装工具并添加 site-packages 路径。
`-ForcePipInstallOnInit` 会覆盖 false；不要假定旧资料中的关闭参数受本构建支持。
`bOfflineOnly=true` 则给实际安装命令加 `--no-index`，并非关闭安装，缺包时仍可能失败。

Torch 是 Bridge 所声明 ML 功能的依赖，不是普通 Unreal MCP、独立 Annotations 或
Bridge 的纯 C++ 状态查询的直接要求。只跳过安装可以用于隔离发现/读取检查，但不能
据此承诺 Canvas ML/语音处理功能可用；实际使用前仍须验证相应包和权重。

LateStartup 会注册工具、确保 UE MCP listener、发布编辑器发现记录、启动/连接 Canvas
server、刷新版本 catalog，并设置崩溃 watchdog。现有 UE MCP listener 会被采用；并发
编辑器或特定配置可选择空闲端口。必须读实际绑定和 identity，不能把默认 8000、7777
或另一个编辑器的 endpoint 当成当前会话证据。

以下只描述 **Canvas sidecar build** 的安装与联网，不包含上述 Python 包安装或节点执行：

- 默认 LocalPaths 的 build 搜索和本地解包本身不下载远端 sidecar；源码存在从插件
  Binaries 内 release 自动安装到用户目录的路径，因此这一路径不联网仍会写文件。
- Artifactory 模式读取配置的匿名 HTTPS catalog；URL 默认空。选用 Latest 时源码可
  自动下载缺少的所选 build。不要在状态调查中替用户填 catalog 或切换来源。
- Developer Mode 连接已运行服务而不启动 bundled server；此源码开发路径使用
  localhost:7777 的 MCP server，浏览器 DeveloperModeURL 则可能是另一个地址。
- 本地 UI、场景查询、MRG 和标注不天然要求 OpenAI key。具体图像/网格生成才按所选
  provider 核对凭据、模型权限和费用；本地 ML 操作也要单独验证权重及依赖。

低副作用首轮候选：

| 直接 MCP 名称 | 源码行为 | 结果不能证明什么 |
|---|---|---|
| `GetStatus` | 加载配置的 MRG preset，返回 ready、presetConfigured 与 pass 名 | ready=true 没有检查 sidecar 健康，不能证明生成或渲染成功 |
| `GetMRGPasses` / `GetMRGVariables` | 读取 preset；前者把 variable overrides 应用到复制的 graph 后枚举预计 captures | 预计 pass 不等于已产出文件 |
| `GetAssetsByType` | Asset Registry 查询；ClassPath 必需，可用 PackagePath 限定 fixture 目录 | 资产能列出不等于其导入/渲染正确 |
| `GetSelectedAssets` | 读取 Content Browser selection | 不是关卡 actor selection |
| `GetActorsByType` / `GetCameraActors` | 读取场景对象；前者可能加载给定 Blueprint class | 不应因此移动 viewport 或改变相机 |
| `ResolveRenderResolution` | 按 preset/参数计算分辨率，不启动渲染 | 不证明渲染质量、性能或成功 |

`TriggerMRGRender`、`TriggerSequenceRender`、`SaveSceneSnapshot`、Import/Export、mesh
ops、Spawn/Remove、stencil/捕获设置、viewport streaming、console command 都有执行或
写入副作用。`AskAssistant` 会向编辑器 AI Assistant 发消息并打开其面板；不是只读工具。
Blueprint reflection 执行另受 `bAllowBlueprintFunctionExecution=false` 默认门控，
不要为普通发现切换它。此门控不等于其他写工具全部禁用。

Bridge fixture 先做上述读取并分别验证 UE 端、sidecar 版本/健康、前端 attach 和动态
工具目录。需要测渲染时再使用隔离项目中的明确相机/短序列、小分辨率和限定输出目录，
读回产物并核对画面；不移动用户 viewport 来补 QA。外部生成、模型下载及资产提升应
作为各自明确范围的测试，不能用 GetStatus 或一次工具列表替代。

## 原生 server 的最小验证

ModelContextProtocol 是 server/传输与 registry adapter；领域能力来自已注册 toolset
和插件直接工具。
安装源码默认 `/mcp`、8000、Tool Search 开启，而 `bAutoStartServer=false`。
启动参数 `-ModelContextProtocolStartServer -ModelContextProtocolPort=<port>` 或显式
StartServer 可启动监听；仅启用插件不证明 server 已启动。服务本身不需要模型账号/key。
`bDumpMediaToDisk` 默认 false；若打开，传输的图像/音频另写入项目 Saved 且不自动清理。

目标实例上的验证顺序：

1. fresh identity、精确引擎/项目/端口；5.9 使用独立缓存或 `--no-cache --new-session`。
2. 启动完成或插件/外部连接变化后刷新 client；`list-tools` 和 `list-toolsets` 都保留
   完整结果。从 live schema 描述候选 owner/工具，直接名称不强加 toolset owner。
4. 对出现的候选只做有限读取；独立记录 schema/read/write/compile/runtime/render 结果。
   Metadata 的写入另测 disposable Blueprint 的编译、保存和重新读取；Canvas 不能
   因 read 成功就记为完整工作流通过。

## 源码定位

路径相对引擎 `Engine/`，项目扩展另列；优先读取当前安装对应文件，不跨用其他版本：

```text
Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Public/ModelContextProtocolSettings.h
Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Private/ModelContextProtocolServer.cpp
Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Private/ModelContextProtocolToolSearch.cpp
Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocol/Private/ModelContextProtocolToolsetRegistryAdapter.cpp
Plugins/Experimental/Toolsets/MCPClientToolset/Source/MCPClientToolsetEditor/Public/MCPClientToolset/MCPToolsetSettings.h
Plugins/Experimental/Toolsets/MCPClientToolset/Source/MCPClientToolsetEditor/Private/MCPClientToolset/MCPClientToolsetSubsystem.cpp
Plugins/Experimental/Toolsets/MCPClientToolset/Source/MCPClientToolset/Private/MCPClientToolset/MCPClientToolset.cpp
Plugins/Experimental/Toolsets/BlueprintToolsets/Source/BlueprintToolsets/Private/BlueprintToolset.h
Plugins/Experimental/PythonMLPackages/PythonMLPackages.uplugin
Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PythonScriptPluginSettings.h
Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PythonScriptPlugin.cpp
Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/Private/PipInstall.cpp
Plugins/Developer/UnrealCanvas/UnrealCanvasBridge/Source/UnrealCanvasBridge/Private/UnrealCanvasBridgeModule.cpp
Plugins/Developer/UnrealCanvas/UnrealCanvasBridge/Source/UnrealCanvasBridge/Private/UnrealCanvasBridgeTools.cpp
Plugins/Developer/UnrealCanvas/UnrealCanvasBridge/Source/UnrealCanvasBridge/Public/UnrealCanvasBridgeSettings.h
Plugins/Developer/UnrealCanvas/UnrealCanvasAnnotations/Source/UnrealCanvasAnnotationsEditor/Private/UnrealCanvasSpatialAnnotationsEditorModule.cpp
Plugins/Developer/UnrealCanvas/UnrealCanvasAnnotations/Source/UnrealCanvasAnnotationsEditor/Private/UnrealCanvasSpatialAnnotationToolset.h
Plugins/Developer/UnrealCanvas/UnrealCanvasAnnotations/Source/UnrealCanvasAnnotationsEditor/Private/UnrealCanvasSpatialAnnotationEditorSubsystem.h
Plugins/Developer/UnrealCanvas/UnrealCanvasAnnotations/Source/UnrealCanvasAnnotationsEditor/Private/UnrealCanvasSpatialAnnotationOps.cpp
<Project>/Plugins/MCPBlueprintMetadata/Source/MCPBlueprintMetadata/Public/MCPBlueprintMetadataLibrary.h
```

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404。

- 源码与 live 核对：2026-11-16，**UE 5.9.0 Preview / CL 60351404**。下文“本次实
  测” 单列实际发现、读取和标注写入结果；其他参数、注册入口和副作用说明仍是安装源
  码候选，调用前须匹配目标实例 schema。原生 Blueprint 元数据实测另见
  [ue-5.9-blueprint-python.md](ue-5.9-blueprint-python.md)；Canvas 的产品层分
  工、模型与服务要求见
  [ue-5.9-production-feature-matrix.md](ue-5.9-production-feature-matrix.md)。
  2026-11-11 的 enabled=false 记录不能代表本次实例；本次也没有 UE 5.8 live 回
  归。

**方向与注册入口**

- 本次刷新后直接工具正常出现，无需修改编辑器的 Tool Search 设置。
- 不要把 bare name 拼成虚构 owner，或认为低层方法自带 `call_resolved_tool` 的参
  数检查；本次 fixture 验证了这条派发路线。

**Metadata 在 5.9 的替代范围**

- 既有 5.9 记录已验证成员/函数中文描述往返；**本次局部变量覆盖来自源码，未新增
  live 验证**。

**Annotations 的本地能力与回滚**

- 本次 `ListAnnotations` 的 JSON 没有 `persisted` 字段；不要从字段缺省推断持久
  化。

**原生 server 的最小验证**

- `PluginToolset.PluginToolset` 的 `GetPluginInfo`、`IsEnabled`、依赖查询为源码
  候选；本次 live 参数 `pluginName` 使用表中的技术名；其他构建先核对其 schema。

### 本次实测：发现、读取和标注生命周期

以下均为 2026-11-16 同一目标实例的记录。绝对工程路径、PID、端口、原始 schema、
调用结果和启动日志保存在忽略的 session 目录；本表不替代下一次的 fresh identity。

| 层次 | 实际结果 | 未覆盖的范围 |
|---|---|---|
| 插件状态 | 表中五个技术名的 `IsEnabled` 均为 true；PIE=false | enabled 不等于每项工具都执行过；兼容 Metadata 插件没有新增写测试 |
| 完整发现 | 刷新 client 后 `tools/list` 为 70 项：66 个直接工具和 4 个 meta-tools；`list_toolsets` 为 100 个 owner，较旧配置多两个 Annotations owner | 这是本实例的注册规模，不是能力数或测试通过数；未重新统计全部 registry 工具总数 |
| Bridge 直接读取 | `GetStatus`、`GetMRGPasses`、`GetMRGVariables`、`GetAssetsByType`、`GetActorsByType`、`ResolveRenderResolution` 均返回成功；分辨率回读 320×180 | 状态、预计 pass/capture、资产和 actor 列表不证明渲染或生成已完成 |
| Annotations 读取/写入 | `List3DAnnotations` 初始为空；scratch 模式创建一个标注，回读位置/prompt/group，更新 prompt 和 group 后再次读回，gather 返回该 ID，按 ID 删除后列表恢复为空 | fixture 在视锥外，gather 的 visible=false 符合位置；未验 GBuffer/蒙版图像、持久化保存重载或渲染 |
| 清理检查 | actor 集合、selection、dirty 包集合和编辑相机前后一致；visible groups、active group、labels、overlay、persist、capture stage 六项回读与测试前一致 | capture stage 未改变；这些状态检查不等于全部 setter 的行为覆盖 |
| Canvas sidecar / MCP Client | bundled v0.21.0 本地安装并启动 ready，MCP Client 握手成功；前端未 attach 时远端 `tools/list` 返回零项，未出现动态 `UnrealCanvasBridge` owner | 未验证前端 attach 后的远端工具、图工作流、外部模型、导入或最终生成内容 |

实测两个 registry owner 为
`UnrealCanvasAnnotationsEditor.UnrealCanvasSpatialAnnotationToolset` 与
`UnrealCanvasAnnotationsEditor.UnrealCanvasSpatialAnnotationEditorSubsystem`。
这解释了为什么只找名为 `UnrealCanvasBridge` 的 toolset 会漏掉已可调用的 UE 侧工具。
七项直接读取中六项属于 Bridge、一项是 Annotations；上述插件专项检查没有编译、
PIE、渲染或生成验收。后续渲染证据另见本页开头链接；局部读写不能描述为完整
Canvas 图工作流通过。


