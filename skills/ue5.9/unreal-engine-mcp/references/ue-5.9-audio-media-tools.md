# UE 5.9：MetaSound、音频、媒体与渲染工具

在 5.9.0 Preview / CL 60351404 完成第二轮只读实测。比较安装为
5.8.4 / CL 58902052；下面区分工具注册、代表读取和未执行的写入。
没有播放音频/视频、运行 PIE、录制、渲染、打开窗口或修改原资产。
原始 schema、源码对照和结果保存在忽略的 session 目录。

## 实际注册与版本差异

| 领域 / live owner | 注册数 | 与 5.8 的关系 |
|---|---:|---|
| `MetaSoundToolset.MetaSoundDiscoveryToolset` | 5 | 比较的 5.8 安装没有此工具插件 |
| `MetaSoundToolset.MetaSoundInspectionToolset` | 13 | 新 MCP 检查界面；都要求已有 `builderName` |
| `MetaSoundToolset.MetaSoundAuthoringToolset` | 24 | 新 MCP 作者界面，其中 `FindMetaSoundAssets` 是读，其余 23 项是写 |
| `EditorToolset.SoundWaveToolset` | 2 | 5.9 新原生 ImportFile / ExportWav 封装；两个都是写 |
| `MediaToolset.MediaToolset` | 4 | 比较的 5.8 安装没有此工具插件；四项都是读 |
| `animation_toolset.toolsets.controlrig.ControlRigTools` | 44 | 两版源码的 decorated 方法集合完全相同，属于延续能力 |
| `ControlRigEditor.ControlRigSequencerEditorLibrary` | 230 | 5.9 直接暴露原生函数并扩展覆盖；67 read / 163 write，不能全称为新引擎功能 |

以上 322 项已经包含在项目总注册量内，不是 322 项功能通过。
5.8 的 Control Rig 原生库已有大量公开编辑器 API，但其头文件未标注
`AICallable`；旧工具插件另有 72 个 `SequencerControlRigTools` Python 封装。
5.9 不再以该旧文件为合同，使用当前原生 owner 和完整参数。旧的
`get_float` 等名字不能靠改大小写迁移。

MRQ/MRG 在此构建**没有独立 queue/graph 工具 owner**。
`MovieRenderPipelineToolset` 提供两个可通过
`ToolsetRegistry.AgentSkillToolset.ListSkills` / `GetSkills` 读取的官方技能，
指导直接使用公开 Python API。MRQ/MRG 本身在 5.8 已存在；新增的是这里的
官方工作流接入，以及部分 API。例如 `MovieGraphConfig.get_graph_topology`
在比较的 5.8 头文件中不存在，而 5.9 已暴露并通过实际读取。

## MetaSound：先查类型和真实引脚

代表读取全部成功：

- `FindRegisteredPages` 返回 `Default`。
- `FindDataTypes(pattern="wave")` 返回 `WaveAsset`、数组及相关类型，含
  `literalHint`，可区分 UObject、UObjectArray、数值和无默认值的类型。
- `FindInterfaces` 返回当前注册接口及其最高版本。
- `FindNodeClasses(pattern="Sine", inputs=[], outputs=["Audio"])` 返回
  `UE / Sine / Audio`，版本 1.1。
- `DescribeNodeClass` 读取上述精确三元组，返回真实输入/输出、类型、
  Reference/Value 访问方式、默认值及中文语义；Frequency 默认值为 `440`。
- `FindMetaSoundAssets` 返回两个内置 source，并包含 patch/preset/read-only
  标志；没有把注册成功误当成项目中已有作者测试资产。

`FindNodeClasses` 按组分页，返回的 `totalMatches` 是组数。输入/输出类型
筛选是精确类型匹配，不能把 `Float` 当作 `Float:Array`。有 suffix 分组时
先选出真实类名，再查具体引脚；不要只凭中文显示名连线。

Inspector 的参数是**命名 builder**，不是 asset path。本轮没有 attach 或
create builder，所以没有执行 13 项图检查，也没有验证图编辑、保存、声音
输出或性能。内置 MetaSound 资产存在，并不等于已经有可用 builder fixture。

后续作者任务先读取 live 官方 `MetaSoundFundamentalsSkill`，再按需取
workflows、presets、trigger_topology、paged_graphs、recipes 或 performance。
这些由 `AgentSkillToolset.GetSkills` 返回，具体路径从 `ListSkills` 选择。
检查 builder 与资产是否 attached，再区分 `BuildToAsset`、
`CommitBuilderToAsset` 与 detach；不要把检查过程变成修改内置资产。
此分支尚无经过实测的 MetaSound build/compile/audition/性能交付 helper。

## SoundWave：导入导出封装与属性读取分开

`SoundWaveToolset` 只注册 `ImportFile` 和 `ExportWav`。本轮没有执行它们；
导入会写资产，导出会写文件。注册这两个接口不代表存在音频播放、混音、
波形编辑或听感验收工具。

通过现有 `AssetToolset.FindAssets` 和 `ObjectToolset`，已读取工程中的一个
SoundWave：时长约 1.702154 秒，双声道，采样率/导入采样率 44100，
volume 约 0.05、pitch 1。属性先由 `ListProperties` 发现，再使用真实名字
交给 `GetProperties`。读取前后该资产均为 clean。

这是通用资产/反射读取的实测，不应算成 SoundWave 两项写工具已验收。
音频导入格式、循环/压缩设置、导出字节一致性、MetaSound 播放及听感仍需
单独候选资产和测试用例；当前技能没有这条完整交付工作流。

## Media：读文件与视频帧，不是媒体播放器控制

四个 live 工具：

| 工具 | 合同与本轮覆盖 |
|---|---|
| `ReadImageFile` | 读取 PNG/JPEG/GIF/BMP/WebP 编码，最多 64 MiB；实际读 PNG，返回字节与文件 SHA-256 完全一致 |
| `GetVideoInfo` | Windows Media Foundation 容器元数据；需要视频 fixture，本轮未测 |
| `SkimVideo` | 按已知时长取中点间隔帧；本轮未测 |
| `SampleFrames` | 在半开时间段取中点间隔帧、消除相邻重复；本轮未测 |

视频采样 schema 的帧数上限 30，最长边限制 64–1568 且不放大。
输出声明为带实际 presentation time 的 JPEG；只有执行后检查实际帧/时间
才可声称视频分析成功。

图片返回仍遵循 5.9 raw MCP `image` block 合同：JSON 中的
`urn:toolresult` 是关联标记，不能当作可下载文件。保留 raw 结果，再提取
base64 bytes；仅 unwrap JSON 会丢失图像。

对本测试工程 Content、Engine Content 和 Engine/Plugins/Media 的视频扩展名
搜索没有找到 fixture，故不以空/错误结果冒充视频解码覆盖。当前尚无媒体
抽帧报告 helper，也没有测试 MediaPlayer、MediaTexture 或播放同步。

## MRQ / MRG：官方 Python 只读路径已通

已从 live `AgentSkillToolset` 取回 MovieRenderQueueSkill 和
MovieRenderGraphSkill。文案中的 `execute_python_in_editor` 名称不是此 MCP
会话的可调用工具；本轮使用实际发现的 `PythonScriptingTools.execute_python`，
先读 `read_me`，并逐项 `get_symbol` 检查公开 API。

只读结果：

- `MoviePipelineQueueSubsystem.get_queue()` 返回当前 transient 队列，jobs
  为空、origin=null、dirty=false、rendering=false；检查前后完全一致。
- 资产搜索没有发现 queue fixture；发现三张内置 MRG graph。
- 读取 `DefaultRenderGraph` 的 `Globals` / `DefaultLayer` 分支、6 个普通
  节点（不含 Inputs/Outputs），以及带中文节点名、类、精确 pin 连接的完整
  `get_graph_topology()` 快照；图的 dirty 状态前后均 false。

`get_all_nodes` 不包含 Inputs/Outputs；`get_graph_topology` 则包含它们和
不连接到 Outputs 的节点。后续定位节点应使用对象名/引用，不能把本地化
显示名当唯一 ID。分支名与 Render Layer 名也是不同概念。

未创建 job、加载/替换队列、改图、求值 render settings 或启动渲染。
未来流程应保留 active transient queue 与 origin asset 的区别，拒绝覆盖
dirty 队列，并验证输出路径、任务/shot、取消/错误、完成回调和真实成片。
现有 `unreal-sequencer/sequence_render.py` 是旧预览采集，不能替代 MRQ/MRG
生产渲染验收；本分支尚无经过实测的 MRQ 自动交付 helper。

## Control Rig：延续读取已复验，原生序列路径仍需 fixture

通过保留的 `ControlRigTools` 读取了真实第一人称 rig：1 个图、13 个节点、
161 个 bone、5 个 control、空成员变量列表；读取前后 dirty=false。
这些延续了 5.8 技能已有的 hierarchy/graph/node 读取能力。

原生 `ControlRigSequencerEditorLibrary.GetDefaultParentKey` /
`GetWorldSpaceReferenceKey` 返回对应的 Reference keys。
`GetControlRigs(explicitSequence)` 对当前无 rig track 的序列返回空数组。
这验证了调用合同，没有验证任何控制值、绑定、层、空间切换或求解结果。

本轮没有合适的 sequencer rig binding fixture，也没有调用可能评估场景的
逐帧 transform getters。名字带 Get/Find 不代表纯读，尤其是 GetOrCreate /
FindOrCreate；检查 live accessMode、文档和实际状态。
写 rig graph、bake、FBX、Control Rig timeline evaluation 以及 runtime
变形仍未覆盖。后续使用官方 SequencerControlRigSkill 与
[Sequencer 版本参考](../../unreal-sequencer/references/ue-5.9-sequencer.md)，
逐项移植所需合同，不能把旧 72 个 wrapper 和新 230 个注册函数直接相减。

这些代表读取没有 UE 5.8 编辑器回归含义。新增接口、已迁移合同、通用反射
读取和完整工作流，应在任务报告中分别说明。
