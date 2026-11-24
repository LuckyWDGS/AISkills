# UE 5.9 MCP：技能升级与尚缺流程

针对 5.9.0 Preview / CL 60351404；对照 5.8.4 / CL 58902052 和保留的
5.8 技能基线。2026-11-11 的目录为 **98 toolsets / 1,803 registered tools**。
这是注册数，包含不同 owner 对同类操作的重叠暴露，不能当作 1,803 种新增能力
或已通过测试。没有运行 UE 5.8 live 回归。

## “没有加工具调用”应该如何判断

共享 client 已经动态发现并调用工具，无须为每个工具新增 Python wrapper。
registry 工具可用 `describe-toolset` / `describe-tool` 和带 `--toolset` 的 `call`。
顶层直接工具先查完整 `list-tools`，再走 [bare-name 描述与派发](ue-5.9-mcp-canvas-plugins.md)，
不强加 owner；search meta-tools 与直接工具可以同时存在。即使没有在技能里逐个列出
名字，也不等于不能调用。

区分以下层次：

| 层次 | 能说明什么 |
|---|---|
| live registered | 目标实例公布了 schema；不能说明前置资源/运行上下文存在 |
| 通用调用支持 | client 可以解析合同并 dispatch；不能说明某项已经执行 |
| 文档/代码名字命中 | 提供定位线索；动态组合可能没有 literal，命中也不证明工作流完整 |
| 专项工作流/helper | 已说明前置条件、依赖和验收；仍要看是否覆盖该版本 |
| 直接调用记录 | 有返回或明确错误；一次空读、symbol/schema 查询不能代表功能通过 |
| 功能验收 | 需要明确的回读/编译/编辑器求值/视觉/runtime 用例，不能混为一谈 |

2026-11-15 复查仍发现 98 个 toolset，重新取得 25 个相关 owner 的完整 schema。
本次没有重新枚举全部工具总数；1,803 是前次记录。新增参考覆盖 UI、游戏数据/
物理和测试的执行路线，不能把这些补文档的模块算成引擎新增或 runtime 通过。
Automation 状态为 Disabled，CommonUI/UMG/Slate recorder 未启动，DataRegistry
列表为空；这些只证明状态接口可读。没有开启插件、修改资产或运行 PIE。

2026-11-16 Canvas 插件补验刷新目录后为 **100 toolsets**，新增两个 Annotations
owner；顶层 `tools/list` 为 **66 个直接工具 + 4 个 meta-tools**。没有重新枚举
全部 registry 工具总数，不将旧 1,803 与这些数字相加。已验证六项 Bridge 读取及
临时标注的创建/修改/读回/gather/删除和状态恢复；sidecar ready、远端握手成功，
前端未 attach 时远端目录为空。完整流程和同实例晚注册的缓存刷新要求见
[MCP / Canvas 插件](ue-5.9-mcp-canvas-plugins.md)。这些补验不覆盖模型生成、
渲染、PIE 或 UE 5.8 回归，也不改变上一段 2026-11-15 的历史状态。

例如 MetaSound 已能发现节点和引脚，但没有 build/compile/试听交付 helper；
Deformer Graph 有 62 项注册接口，但只有类型与组件源读取证据；MRQ/MRG 是
官方 Python 技能流程，不存在另一个专用 queue 工具要“注册进 client”。

## 相比 5.8 技能，已经升级的五个包

| 包 | 5.8 基线已有什么 | 5.9 分支实际改造 | 仍需按需迁移 |
|---|---|---|---|
| `unreal-engine-mcp` | 单 toolset discovery、Programmatic composition、Remote gap route；BP/ABP/PCG/UI/GAS/Dataflow 等参考与脚本 | core 入口重写；plural / 单工具 discovery、实例绝对路径保护、官方 async Python/符号发现、native batch；Blueprint 元数据/DSL、inspector/lint、离屏 capture；补完整游戏、角色/BT/动画、Input/UMG/音效/过场生命周期路线；大型 Unicode 请求改 stdin 避免 Windows argv 限制 | 旧 normalize/layout/散布等高层 helper 不能因共享 client 更新就视为全移植；ABP 状态机节点漏读仍在 |
| `unreal-material-artist` | Material/MI/Function/Layer、图构建、HLSL/性能/视觉验收流程 | 原生 owner/参数路由、statistics、diff、对象嵌套 schema；图/MI 写入编译代表路径已测 | 所有旧 recipe/build helper、Substrate/目标平台预算未逐项移植/验收 |
| `niagara-vfx-artist` | emitter/stack/renderer/user parameters、效果制作/预览流程 | 原生路由；脚本说明保存重载；补 CPU 一次 burst、ParticleColor→材质与 gameplay 激活/自动销毁验证路线 | renderer/stack 多数是延续能力；复杂 motion/事件/目标平台帧预算仍需逐例实测 |
| `unreal-sequencer` | 序列/相机/关键帧/预览 helper 和 Control Rig 参考 | 原生 MovieScene 后台资产、曲线和帧率路径；新增 create-only native camera helper、tagged possessable/Transform/Cut/Fade 与逐帧验证；补 runtime 恢复、viewport 录屏及 MRQ 地图绑定路线 | 旧 builder/render helper 及原生 Control Rig 键控未全部迁移；后台 spawnable 仍失败；MRQ 成片未验收 |
| `vfx-flipbook-generator` | 生成/补帧/打包/alpha QA、UE 导入交付流程 | UE 手递交与 sibling import/版本路由更新 | 图像生成/打包算法未重写；5.9 atlas 导入与 Niagara 实际使用尚未验收 |

这些修改当时在独立 5.9 分支完成（现位于 `skills/ue5.9/`，原分支存档为 tag `archive/ue5.9-mcp`）；没有改 5.8 源目录或全局 junction。
高层 helper 有价值时按实际任务移植，不建议增加一层只转发同名 native API 的
1,803 个 wrapper。详细实测见 [版本审计](ue-5.9-preview-audit.md)。

## 已有 MCP，但专项流程或测试仍不足

下表保留前两轮的基础目录并更新小游戏已覆盖的领域。完整游戏流程见
[Game production](game-production.md)，具体功能/依赖取舍见
[生产功能矩阵](ue-5.9-production-feature-matrix.md)。

| 领域 / 注册规模 | 已纳入什么 | 尚缺什么 |
|---|---|---|
| Blueprint：74 + native DSL 7 + Python DSL 4 / diff 3 | 原生编辑、元数据、revision DSL、检查/lint、CDO 求值；小游戏 Character/GameMode/交互/生命/状态/过场入口的正式蓝图实现 | ABP 状态机非 K2 节点覆盖、复杂网络 gameplay、旧高层脚本迁移 |
| StateTree 49 | 结构/任务/条件/评估器/实例数据、绑定补足与编译 | 生命周期、事件/transition runtime、完整 setter 安全编辑 helper |
| PCG 32 + spatial 1；native subsystem 另 42 | 图、普通 component 执行源、活动等待、精确 DataView 编辑器输出 | 子图/Loop/GPU/World Partition，native subsystem 扩展的逐项用例；两个 owner 有重叠 |
| Dataflow 47 + legacy 23 | 本轮补类型/路径/变量/属性/精确连线/中文框和保存流程 | 子图/ForEach、Cloth/Groom、求值与运行接入 |
| Deformer Graph 62 | 本轮补入口、类型/组件源和 HLSL/执行域选择边界 | 图作者、kernel、编译、角色绑定、真实变形/性能；尚无专项 helper |
| Geometry 6 | 本轮补 transient box 验证与无 world 修改的操作边界 | 更多 primitive、目标组件/变换/碰撞与持久化交付 |
| StaticMesh 22 / SkeletalMesh 22 / PhysicsAsset 17 | 网格基础与读取边界；新增挂点/材质/碰撞形状/约束的任务路线 | LOD/Nanite/碰撞修改后持久化和 runtime；物理作者链未实测 |
| Texture 4 / TextureGraph 18 | 本轮补纹理读取与 76 种真实 TG 节点发现 | TG fixture、连图/编译/bake/export 和纹理像素/色彩验收 |
| CurveAtlas 13 / enum 8 / struct 14 | 本轮补安全候选作者流程、数值或元数据回读与保存 | 材质/runtime 使用、枚举引用/存档、容器与嵌套类型用例 |
| MetaSound：discovery 5 / inspection 13 / authoring 24 | 本轮补 discovery、真实引脚与官方技能选择 | builder 生命周期、图作者/compile/save、试听和性能 helper |
| SoundWave 2 / Media 4 | 音频属性、ImportFile 五种原创短音效、实际主混音录制及非零验证；Media PNG 原字节读取 | 逐事件音效试听/空间化/混音预算；视频 metadata/skim/sample、真实时间戳与抽帧报告 |
| Control Rig：延续 44 / native library 230 | 真实 rig graph/hierarchy 读；原生 Reference keys；空序列读 | native track/binding/keys/spaces/layers/bake 与场景求值；旧 72 wrappers 不能简单换名 |
| MRQ / MRG | 从 AgentSkillToolset 读到两项官方技能；Python 读取空队列和默认图拓扑 | 无需另注册 queue wrapper；缺具体 job/shot/设置、输出/完成/失败/取消与真实成片验收 |
| Canvas / MCP Client / Annotations | 2026-11-16 补完整顶层发现、bare-name 描述/派发；Bridge 六项读取与 Annotation scratch 生命周期、状态恢复通过；本地 sidecar ready | 前端 attach 后的远端动态工具、图工作流、持久化标注重载、GBuffer/蒙版图像、生成/导入/渲染尚未验收 |
| Sequencer native libraries / Director 4 / validator 2 | 后台 Fade/Transform 曲线求值、tagged camera/Cut/Fade 和 Intro；新发现 Director endpoint/事件键、条件/动态绑定路线 | 原生 Director、TimeWarp/TemplateSequence、复杂子序列/Control Rig 与 MRQ 的运行验证；validator 空结果不能代替播放验收 |
| UMG / MVVM 31 / CommonUI 15 / Slate 9 | widget 树/动画/静态覆盖分析；正式游戏 HUD；新增 MVVM 作者和三层 UI 诊断流程 | FieldNotify/双向绑定、CommonUI 菜单、可点击交互与多 DPI 的实际验收；不能把 SetText 当 FieldNotify |
| BehaviorTree 25 / EQS 14 / NavMesh 21 / Input 2 | BT/BB/Task/AIController 角色作者、独立 ABP、正式巡逻/击败入口；LocalPlayer/IMC/Input 用例路线 | EQS 和真实 nav query、复杂 BT 服务/装饰器与追踪；action 与 key 映射证据须分开 |
| GAS / Tags 11 / DataRegistry 7 / 数据表 / StringTable 9 | 5.8 基础能力；补 5.9 Ability 作者、AttributeSet 发现、ASC 四类检查、标签/数据/源文本作者路线 | GAS 授予/激活/取消/复制，Registry runtime cache、存档迁移和本地化打包；这些流程本轮未执行 |
| Rewind 10 / KnowledgeBase 6 | inactive session 和空知识库入口 | 真实 recording/trace、条目检索/更新与结果验收 |
| Perf 10 / SceneCapture 14 / files 9 | 代表快照、离屏图、cursor 文件读写；另以原生 Agent 命令在独立包导出图/环境及 2 秒帧耗时分布 | CSV 数值解析有已知错误；完整 gameplay 性能、其他视图/格式仍未覆盖；Agent 截图会改变 time dilation，非只读 |
| SourceControl 38 / UndoHistory 4 / Plugins 24 | 本轮补 provider、事务详情、插件元数据代表读取 | provider 未连接；无源控写流程；不是漏注册某个工具 |
| Automation 7 / config 12 / logs / console / assistant / AgentSkill | 通用调用；补测试发现→精确选名→状态/结果→自有运行收尾，区分项目默认配置与玩家设置 | 本轮仅状态读，不做配置修改、自动测试执行或 assistant 操作；按具体任务补验收 |

这里的“尚缺”主要是**可复用流程、前置资源和验证用例**。运行上下文不足、
尚未执行、工具行为缺陷是不同状态；不应全部归为不能控制。

## 优先补哪些更有收益

1. **先完善可交付的小型游戏**：真实点击/手柄菜单、MVVM 数据通知、存档/设置，
   再完成最终独立包的纯输入通关/重开。建立精确选名的回归与日志证据。
2. **补演出和表现的完整链**：Director 事件→接收者、短 MRQ 出片、flipbook→
   Texture→SubUV 材质→Niagara 实播，另测 MID/MPC 与 VFX 激活/结束/owner 清理。
3. **按玩法增加系统**：追踪 AI 才加入 NavMesh/EQS；组合能力才上 GAS；场景量大
   再扩 PCG 子图/GPU/WP；有程序音频或变形需求再做 MetaSound/TG/Deformer。
4. **迁移真正会用到的旧 helper**：材质 audit/build、Niagara audit/preview、
   Sequencer builder 等。共享 client 已增加旧执行契约的明确拒绝提示；这不代表
   helper 本身已迁移。Control Rig 保留活动 timeline 的实际前提。

已知 spawnable、CSV parser、StateTree setter 和 ABP 检查盲区均保留在技能中。
它们需要精确避让或引擎修复，不能只靠补文档宣称完成。

旧 helper 的执行入口不完全相同。`run_tool_script` 的迁移提示只覆盖经过该入口
的脚本；`material_instance_batch`、`graph_refactor_executor`、`niagara_plan_apply`
等还有直接 `call_resolved_tool` / batch 路线。尤其混用仍存在的 Niagara owner 与
旧 `AssetTools` 保存路径时，可能先写入、后失败。执行这些旧计划前先核对**全部**
调用和保存合同，或改用已发现的 native batch；不可用一次运行去试探是否兼容。
本次没有把这些 helper 全部迁移，也不把新的错误提示算成它们的兼容保护。

各域具体合同与证据：

- [Blueprint / Python](ue-5.9-blueprint-python.md)
- [StateTree / PCG](ue-5.9-statetree-pcg.md)
- [Dataflow / 数据类型 / Deformer / Validator](ue-5.9-dataflow-data-tools.md)
- [Geometry / StaticMesh / TextureGraph](ue-5.9-geometry-texture-tools.md)
- [音频 / Media / MRQ / Rig](ue-5.9-audio-media-tools.md)
- [动画 / AI / Input / UI](ue-5.9-animation-ai-tools.md)
- [MVVM / CommonUI / UMG / Slate 工作流](ue-5.9-ui-workflows.md)
- [游戏数据 / 物理 / 持久化 / 自动化](ue-5.9-game-systems.md)
- [MCP / Canvas 插件与直接工具](ue-5.9-mcp-canvas-plugins.md)
