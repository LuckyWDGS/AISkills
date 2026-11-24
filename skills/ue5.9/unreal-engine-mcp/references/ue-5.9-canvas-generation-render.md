# UE 5.9 Canvas：生成与实际渲染验收

2026-11-16，UE **5.9.0 Preview / CL 60351404**、Canvas server **v0.21.0**。
用于验证生成文件、MRG 输出和后台渲染；插件启用与发现先读
[插件分工](ue-5.9-mcp-canvas-plugins.md)。所有端口、PID、项目路径、请求、失败帧和
最终文件保存在本次忽略的 session，不能拿这里的版本记录替代 fresh identity。

## 生成服务：先查真正可执行的模型

UE MCP 和 Canvas server 的 MCP 是不同端点。确认 sidecar 的父进程、实际监听和
`initialize` 身份，再发现它的目录。本次较早曾取得零工具；
后续 `merlin 0.21.0` 的 `/mcp` 返回 **132 项工具**，`get_graph_docs` 实际读取成功。
工具数量不能代表图已运行或模型有权限。

对生成任务调用 `list_models`，按类别查当前可执行 binding，使用返回的 `id` /
`authoringParams`，不要将家族 `modelId` 或节点默认值当作可执行服务。本次
`list_models({"category":"image-generator"})` 返回 `[]`；registry 中可见的六个
非 Claude 凭据 profile 均未报告 available=true。故本次未调用 Canvas 原生生成节点。
`GET /api/services/registry` 的 `authStatus.<id>.available` 可用于布尔检查；不要
为了判定可用性读取/归档 key 的值。

新增自有 provider 时，先取得 `get_service_meta_schema` 与
`get_help({"slug":"service-schema-authoring"})` 的实际合同。v0.21.0 的标准流程为独立新 ID 的
auth → provider → 必要的 media/media-out → model → service。`propose_service_schema`
只暂存一份 Draft，下一份会替换它：等待用户保存，读回后再提交下一份。凭据由用户在
Settings → Model Providers 填写；服务由用户在 Model Catalog 批准。不要直接调用
save API 跳过审阅，也不要写 `usagePolicy: Approved` 冒充用户决定。JSON schema
校验通过不证明 endpoint、输出 selector 或模型能运行。

本次用户选择先验证已有 Codex 图像服务与 UE 渲染，因此未暂存/保存上述配置，
未设置 Canvas secret，也未调用 Claude 或编辑器 Assistant。通过已有 `cm-imagegen`
执行一次 Images API 请求，得到并实际查看了原创星星道具 PNG；请求模型为
`gpt-image-2.6-sunburst`、quality=max、complexity=high、n=1。**请求 1024×1024，
实际返回 1254×1254**：生成内容通过，精确尺寸未通过。没有重试、放大或改标尺寸；
请求模型名也不独立证明网关上游实际执行的模型。这是外部生成服务证据，不能写成
Canvas Image Generator 节点、AI 动画、视频或网格生成通过。

后续原生图工作流应先读 `get_graph_docs`：顶层 canvas surface 的节点没有可连的
pins；用 `create_graph` 建 Graph card，在返回的 `childCanvasId` 内连接
prompt → generator → canvasOutput。按目标 canvas 查询节点形状，执行后核对状态、
真实输出文件与保存重载；只得到节点 ID 或 run 请求被接受不算生成完成。本段是本次
发现的合同，**未执行图创建或生成**。

## MRG 静帧：后台调用并不等于没有窗口

先在 UE 的完整 `tools/list` 找到 bare `GetStatus`、`GetMRGPasses`、
`GetMRGVariables`、`TriggerMRGRender`，再 `describe_tools`。`GetStatus.ready=true`
不是 render completion；该工具没有 job ID / status 轮询接口，最终结果来自原异步
请求。给足 timeout，超时后检查日志和该次输出，不能直接再投一次。

交互编辑器中，`ExecutionMode: EditorWorld` 不启动 PIE，但引擎仍会创建并聚焦
Quick Render 进度窗口、暂时禁用已有窗口。`PlayInEditor` 还会运行游戏逻辑。
需要不影响用户编辑器时，使用单独的 `-RenderOffscreen -unattended` 编辑器进程，
独立 MCP 端口、UserDir、日志和编辑器 INI；写前核实精确 PID/项目。不要在用户实例
上为了 MRG 搬动相机、打开 timeline 或用 UI fallback。

本次离屏启动实测：

- `-UserDir` 隔离了项目 Saved、Intermediate 和生成配置。另显式覆盖
  `EditorSettingsINI`、`EditorKeyBindingsINI`、`EditorLayoutINI`。
  源码另支持 `-ForceUseProjectForEngineSavedDir`，**本次未测试该替代开关**。
- `-LiveCoding=false` 是运行时开关；`-NoLiveCoding` 不能据此当作同义参数。
  用命令行 Engine ini override 关闭本次启动的 `bRunPipInstallOnStartup`；
  仍会准备本地 venv/安装工具，不能说 Python 完全不写文件。
- 相同 `.uproject` 仍共享 authored Content、Config、插件、用户级 Canvas 数据与 DDC；
  UserDir 不是整个项目副本。静帧阶段只调整离屏实例的自由视口；序列阶段创建并
  清理独立测试资产，原有资产未保存。
  对可能保存资产的破坏性实验，应使用独立项目副本。

本次成功的 still 请求使用当前已确认的默认 preset，预期三个 capture：

```json
{
  "Resolution": {"matchAspect": false, "size": "custom", "width": 640, "height": 360},
  "CameraSource": {"mode": "viewport"},
  "ViewportLookFlags": {"visibility": false, "showFlags": false, "viewMode": false},
  "ExecutionMode": "EditorWorld",
  "CaptureSceneState": false,
  "Variables": {"UseWorldNormals": "True"}
}
```

不要把该 preset 或变量当成其他项目的默认合同。`CaptureSceneState=true` 会取 whole-world
Level Snapshot，可能很慢且很大；普通渲染验收不需要。默认 preset 的 depth 是预览图，
定量深度另验 `RawDepth.npy`。本次 NPY 为 float32、360×640，有效场景值约
1769.4–9396.7；另有约 1e13 的背景值，不能把所有有限数都当有效表面距离。

## 已复现：actor 相机注解正确，画面仍可能来自旧视口

首轮 `CameraSource.mode=actor` + `EditorWorld` 返回文件，但 beauty 只有天空条带，
depth/normal 全黑，RawDepth 全是约 1e13。相同 world、actor pose/FOV 的
`SceneCaptureToolset.Capture` 三个诊断视图正常，排除了“场景没有几何”的解释。

本构建的 Bridge 调用 `SetActorLock` 后立即开始 Quick Render；锁定相机的位姿/FOV
要到 viewport tick 才更新。EditorWorld 的 Quick Render 已先缓存旧视口值，而结果
`Camera` 注解直接读取所选 actor。因而**相机注解不是实际画面来源的证明**。

已实测的规避方式仅用于本次独占的离屏实例：

1. `GetViewportCamera` 确认 `pilot=null`。若存在 pilot，`SetViewportCamera` 可能移动
   actor 并形成 undo，不能当成自由视口调整。
2. `SetViewportCamera` 写明确 transform 和 `intrinsics.fov_h`；单独一轮
   `GetActiveEditorView` 读回 location、pitch/yaw/roll 与 FOV。
3. 以 `CameraSource.mode=viewport` 渲染，检查图像内容与深度，再恢复或关闭自有实例。

此规避验证的是本场景的位姿/FOV 与几何输出；自由视口不会因此继承 actor 相机的
景深、镜头或后处理设置。需要电影相机画面一致性时应另验这些设置，不能把它当成
actor 相机的等价渲染。

复测三个 PNG 均为 640×360，有场景结构，已逐张查看；原始深度不再只有背景值。
未修改引擎；未宣称 actor 模式在本构建或其他模式全面修复。日志中的旧
`DefaultQuickRenderGraph` variable-override 与 `/Temp/.../QuickRenderSettings` 警告
在成功复测仍出现，因此不能单凭这两个 warning 判定黑帧或成功。

## 固定曝光与相机画幅

窗边厨房使用固定曝光和受约束的竖幅相机。显式 `SceneCaptureToolset.Capture` 的 Lit 帧过曝，自由视口只同步位姿和水平 FOV 时还出现过黑边。要保留已保存相机的构图与后处理，在本任务独占的离屏编辑器使用下列路线。

1. 核对地图和相机的完整对象路径。读 `GetViewportCamera` 确认当前是自由视口，再按上节设定位姿和 FOV。按完整路径解析已摆好的 CameraActor，调用公开的 `LevelEditorSubsystem.pilot_level_actor(actor)`。让编辑器至少更新一次，在后续 MCP 调用中确认 `GetViewportCamera.pilot.path` 正是该 actor。
2. 调用 `TriggerMRGRender`，选择 `CameraSource.mode=viewport` 和 `ExecutionMode=EditorWorld`，请求与相机画幅相符的像素尺寸。在 `finally` 中调用 `eject_pilot_level_actor()` 解除本次 pilot。为每个机位单独留存 beauty PNG 及返回的 Camera 注解，核对位姿、水平 FOV、实际宽高、四边黑带和画面内容。
3. 本构建有一次将奇数宽高各缩减一像素。如果要求精确比例，可以请求等比的偶数尺寸，例如 579 × 589 的参考图取 1158 × 1178。检查 PNG 原帧左上角，显存超预算的诊断字样也会进入成图。对照这一次的 `MRG memory report for frame` 核实显存用量。如果降低尺寸仍超预算，可以在自有包已保存、PIE 已停止后，重启该专用离屏实例并重新核实身份。本次相同机位和分辨率在新进程重拍后得到了干净原帧。

## 输出合同与验收

本次 `TriggerMRGRender` schema 描述 PNG image，但**真实响应为带 annotations 的
text blocks，text 是本地文件绝对路径**；另一个 SceneCapture 工具才返回 raw MCP
image block。应同时处理实际出现的形状，不要只 unwrap structured result 后丢失
媒体，也不能把文件路径当 URL。只读取已核实项目/独立输出根内的文件。

still 默认写 `Saved/UnrealCanvasBridgeRender/beauty.png`、`depth.png`、`normal.png` 和
`RawDepth.npy`，下一次可覆盖同名文件。收到结果后立即复制到唯一任务目录，保留
失败输出；不要从旧文件存在推断新 render 已完成。以 `(branchName, subResourceName)`
关联 `GetMRGPasses.captures`，核实可解码、尺寸、内容、原始深度和本次完成日志。
本次首轮客户端还因误等 image block 报错；确认原请求已完成后读取原文件，未因此
重投渲染。只有后来为验证相机修正才提交第二次请求。

`SceneCaptureToolset.ListModes` 在此构建要求 `bIncludeUnavailable`；`DescribeMode`
解释各输出，再以相同显式 camera 分别捕获 Lit、Normal、SceneDepth。本次三图已解码
查看，无 UI、无相机移动。它们是独立的 8-bit display-encoded 快照，深度亮度不是
厘米，法线字节不是有符号向量，也没有序列求值/temporal history；不能替代 MRG 或
电影序列验收。

同轮还完成独立新序列的 12 帧/24 fps 渲染：beauty/depth/normal 各 12 张连续的
320×180 PNG，0/5/11 帧已实看，局部 H.264 预览已解码。PIE 结束、原队列与资产保持，
自有测试序列已删除；离屏 viewport 像素尺寸有变化，不能称全部 UI 状态一致。
这只是 0.5 秒渲染合同验收。序列的绑定、队列和 PIE 所有权另读
[MRQ/MRG 路线](../../unreal-sequencer/references/ue-5.9-mrq-bindings.md)。

同日后续的 Mesh 请求已通过 Canvas 原生图执行本地 GeometryScript，生成星形
GLB 并导入 StaticMesh；动态参数、结果锁与验收见 [Canvas Mesh](ue-5.9-canvas-mesh.md)。
这是新增的程序化图执行证据，不能改写本次未执行 AI 生成节点的历史结论。
