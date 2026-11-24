# 官方 MCP 开发能力与选择规则

用于判断一个程序员任务应该查哪些官方工具、是否值得启用额外插件，
以及哪些“查询”实际有副作用。插件描述、源码声明和旧数量不代表当前项目能力。

检索词：Enhanced Input、UMG、MVVM、Gameplay Tags、GAS、DataTable、Automation、
PCG、PhysicsAsset、SemanticSearch、SlateInspector、工具缺口。

实现这些域时按需读[官方领域工作流](official-domain-workflows.md)；
运行验收按[对应案例](runtime-acceptance.md)。这里用于选路，不复制完整工具 schema。

## 先确认能力层级

1. **安装源码存在**：插件/类/函数声明可见，尚未证明已加载。
2. **当前已注册**：目标项目完整 inventory 和候选工具 schema 可读。
3. **读取成功**：指定对象返回实际数据。
4. **编辑回读成功**：指定写入、连接/属性回读、目标包保存完成。
5. **编译与运行验证**：编译结果、运行时数据、视觉验收分别记录。

升级后比较同项目、同插件配置的两份 schema，才能判断工具增减。
不要把“以前没盘点到”写成热修复新增。完整动态 inventory 和项目路径保存在
忽略的 session 目录，技能中只保留可复用路线。

2026-11-04 的同一 UE 5.8.4 构建实测：按需启用下表中的 UMG、MVVM、Tags、
GAS、Automation、Physics、PCG、Dataflow、DataRegistry 和 Plugin 共 10 个插件后，
live inventory 从 35 类 / 654 项变为 48 类 / 807 项。这是**插件配置变化**，
不能据此声称引擎版本新增了 153 项能力，也不表示全部 807 项经过执行验证。
结构编辑、保存和少量官方测试已实测；界面运行时绑定、实际 GA/GE 生命周期、
Chaos 布娃娃和 Dataflow 数值求值仍需按任务单独验收。

```powershell
python scripts/builtin_mcp.py --expect-project <absolute.uproject> status
python scripts/builtin_mcp.py --expect-project <absolute.uproject> --refresh-schema inventory --output <session>/inventory.json
python scripts/builtin_mcp.py describe-toolset <live-toolset> --brief
python scripts/builtin_mcp.py describe-tool <live-toolset> <live-tool>
```

项目名称按名称匹配，项目路径按完整路径匹配；同名项目副本优先传完整路径。
每次打开连接都核对当前进程身份，接受会话令牌不代表仍是原编辑器。
`--refresh-schema` 同时刷新复用会话的工具目录，适合插件配置变更后重新发现。

## 优先复用当前 EditorToolset

| 任务 | 官方路线与用途 | 边界 |
|---|---|---|
| 蓝图逻辑、连线、函数和变量 | BlueprintTools 的现有图、节点/引脚与连接读写；ActorTools 管组件；ObjectTools 管 CDO/组件属性 | 节点类型目录可能创建临时节点，不等于现有节点只读。参见[蓝图检查](blueprint-graph-inspection.md) |
| 追踪功能入口与改动影响 | AssetTools `get_referencers` / `get_dependencies`，再查蓝图图/引脚及源码 | AssetRegistry 包引用是候选范围，不是运行时调用栈或完整字符串/反射引用证明 |
| 武器、技能、道具参数表 | DataTableTools：schema、行读取/更新、CSV/JSON 导入；CurveTableTools：曲线行和关键帧 | 不是任意结构体设计器；先确认已有行结构、列类型和导入规则 |
| 配置数据资产 | DataAssetTools `create`，ObjectTools 枚举与读写公开属性 | 类型必须是 DataAsset 子类；复杂子对象创建不等于普通属性赋值 |
| 文本条目 | StringTableTools：命名空间、key、条目与导入 | 不是完整本地化收集、翻译和打包流水线 |
| 模型、碰撞、挂点 | StaticMeshTools：LOD、Nanite、材质、凸碰撞；SkeletalMeshTools：骨架、Socket、Morph 名、PhysicsAsset 分配 | 共享模型改动影响引用者；资产设置与运行时行为分开验收 |
| 地图、实例和命中查询 | SceneTools 查 Actor、trace、目录与 LevelInstance；ActorTools 查组件/变换/Actor Tags | `load_level`、增删 Actor、提交实例是修改；外部 Actor 包要单独保存验证 |
| 日志、配置和参数排查 | LogsToolset 筛选日志；ConfigSettingsToolset 查 schema/值；EditorAppToolset `SearchCVars` | `SetSectionProperties` 会保存配置；SearchCVars 不是任意控制台执行器；错误日志需按时间/阶段归因 |

ObjectTools 需要**对象引用**。AssetTools 搜索可能返回包路径 `/Game/X/A`，
先用官方 `load_asset` 取得返回的 `refPath` 再传给 ObjectTools。
保留 API 返回的子对象路径，不要给任意对象机械追加 `.AssetName`。
空 UObject 引用可能返回字符串 `"None"`；先归一化为空，再判断是否可传给工具。
`set_properties=true` 也不能代替读回：已审阅实现的部分嵌套对象转换会静默忽略
未知键。尤其检查 instanced 子对象确实创建、类型/Outer 正确且所需值已经写入。

### Enhanced Input

已审阅的安装源码和 live inventory 没有独立 Enhanced Input 工具集，
但 InputAction / InputMappingContext 是 DataAsset，不能把整个输入任务判为 MCP 缺口。

- 用 AssetTools 按 `/Script/EnhancedInput.InputAction` 和
  `/Script/EnhancedInput.InputMappingContext` 类型搜索，再 load 和枚举实际属性。
- ObjectTools 能读 InputAction 的 `valueType`、`triggers`、`modifiers`，
  IMC 的默认映射、Action、Key 及映射内触发器/修饰器引用。
- UE 5.8 默认映射在 **`defaultKeyMappings.mappings`**；顶层旧 `mappings`
  已弃用，可能为空。还需检查当前版本的 profile override，
  不能仅凭默认表推断玩家实际生效的映射。
- 同时追踪蓝图输入事件、添加 Mapping Context 的位置、优先级、输入模式和消费规则。
  “资产里有右键”不证明本地玩家已经应用这个 Context。
- 创建资产和可表达的属性写入仍用 MCP。某个映射/触发器操作若需要
  尚未暴露的子对象或 `map_key` 等方法，只对该操作验证公共 Epic Python 的缺口路线。
  运行时是否生效仍需单独验收。

## 对蓝图程序员值得按需加载的官方插件

名称来自已安装 UE 5.8.4 源码；类名、参数、注册情况以目标项目为准。
只启用任务需要的域，先检查依赖，不用 AllToolsets 一次加载全部。

| 插件 / 工具集 | 具体功能 | 操作与证据边界 |
|---|---|---|
| **UMGToolSet** / UMGToolSet | 创建 Widget Blueprint；增删移动、重命名与包裹控件；NamedSlot；事件绑定；UIComponent；编译 | `GetWidgets` 返回 Widget/Parent/Slot；用 ObjectTools 编辑布局、锚点、Padding 等公开属性。创建会编译；没有证明完整 Widget 动画编排能力 |
| **MVVMToolset** / MVVMToolset | 创建 ViewModel、属性；向 Widget 加入 ViewModel；列出/创建/移除绑定；转换函数 | 依赖 ModelViewViewModel。部分 `List*` 有结构副作用，见下文；不擅自把现有 UI 改成 MVVM 架构 |
| **GameplayTagsToolset** / GameplayTagsToolset | 标签树、注释/来源、引用包；添加/移除/重命名标签 | 写入影响项目标签与 INI；中文注释和模块检索 ID 不需要创建 Gameplay Tag |
| **GASToolsets** / AbilitySystemInspectorToolset、AttributeSetToolset、GameplayCueToolset | 查属性定义；运行时 Base/Current 值、激活效果/叠层/剩余时间、授予能力/激活状态、当前 Tags；Cue 通知查缺失 | 需要 GameplayAbilities 与实际 ASC。不是完整 GA/GE 图设计器；普通逻辑仍走 Blueprint/ObjectTools。`ExecuteCueOnSelectedActor` 依赖当前选择并触发行为，不是只读 |
| **AutomationTestToolset** / AutomationTestToolset | 发现/筛选已注册测试；按名字/过滤器运行；取状态、耗时、错误和警告 | 发现/执行为异步，发现完成后才列出/运行。测试可能操作地图/资产；不能因检查能力就启动全部测试或停止用户的测试 |
| **DataRegistryToolset** / DataRegistryTools | 注册表、结构、条目 ID、编辑器来源和展开的运行时来源 | `GetItems` 只返回已缓存条目；遗漏不证明不存在。没有专用的注册表结构写入接口 |
| **PluginToolset** / PluginToolset | 发现/启用情况、依赖/反向依赖、资产所属插件、描述文件 | 启用/禁用、依赖/描述修改、创建插件属于配置修改，可能需要重启；只读盘点不自动加载 |

UMG/MVVM 的结构回读、编译、实际分辨率布局、输入焦点和绑定更新分别验收。
自动化测试只验证实际运行的案例，不能替代缺失的玩法验收。

### MVVM 查询的副作用

已审阅实现中，`ListWidgetViewModels` / `ListWidgetViewBindings` 调用
`GetWidgetView` → `UMVVMEditorSubsystem::RequestView`。后者请求/创建 MVVM 扩展，
并在不存在时创建 BlueprintView，因此不能保证对任意 Widget 严格只读。

仅盘点时，不对未确认具有 MVVM View 的用户资产调用这些查询。
需要严格只读且没有等价 MCP 工具时，核对公共 `MVVMEditorSubsystem.get_view`
在目标版本的可用性，按单项 MCP 缺口使用后台 Epic Python；不要换成 RequestView。
实施用户已要求的 MVVM 功能时，创建 View 属于授权编辑，仍要结构/编译/运行验收。

## 其他领域的选择范围

| 官方域 | 可以用于什么 | 边界 |
|---|---|---|
| AnimationAssistantToolset | Control Rig 层级/图/连线/变量；Sequencer 轨道/绑定、关键帧、Control Rig、导入导出/烘焙、条件和 Outliner | 不是完整 Gameplay AnimBlueprint 状态机编辑器。部分显式 sequence 接口仍依赖打开时间轴，例如 add_spawnable_from_class；按 Sequencer 技能的后台封装处理。详见[动画与状态机](animation-state-machines-mcp.md) |
| StateTreeToolset / AIModuleToolset | StateTree 状态/任务/条件/过渡/全局任务/评估器；BehaviorTree 节点/子树/Blackboard/装饰器 | 当前 inspection 接口没有专用拓扑写入；不是完整导航或 AI 感知调试器 |
| NiagaraToolsets | 系统/发射器/堆栈/Renderer 的 schema、拓扑、值、模块/变量编辑、依赖、编译和问题 | 结构正常不证明效果好看或运行时已触发；按 Niagara 技能验收 |
| Material / MI / Texture | 材质图、函数/MPC、参数/实例、导入、公开纹理设置与尺寸 | Shader 统计与目标设备 GPU 时长分开，不能代替所有平台性能实测 |
| PhysicsToolsets / PhysicsAssetToolset | 骨骼 PhysicsAsset 的 Body、球/胶囊/Box、质量缩放、模式、约束和限制 | 不是所有 Chaos 运行时的控制器；物理投掷仍需组件、力/速度、碰撞和销毁验证 |
| PCGToolset / PCGSpatialToolset | PCG 图/schema/节点/真实连接/参数/子图/注释、散布工具与蓝图组件包装、实例执行与输出；见 [PCG 专项流程](pcg-mcp.md) | 执行、Spawn、DrawSpline 涉及世界或 UI；专用执行/数据工具当前限 PCGVolume，普通 Actor 先查组件接口 |
| SequencerAnimMixerToolset | MovieSceneAnimMixer 图层、动画、过渡及 decoration | 属于时间轴体系，不是 Gameplay AnimGraph 状态混合器 |
| GameFeaturesToolset | 发现/状态检查、请求激活/停用已有 Game Feature | 激活/停用可能创建/销毁内容；不是任意插件热加载器，也没有专用创建功能 |
| ConversationToolset / WorldConditionsToolset | 对话入口/说话人/节点/连线；世界条件描述与排查 | 不是完整对话或条件图 authoring API |
| DataflowAgent | Dataflow 图、节点/连线/schema、变量/注释、模板和兼容资产创建 | Blueprint/Material/PCG 图不能与 Dataflow 图互换 |
| ChaosClothAssetToolset | 衣物资产创建、Section 分配/移除、查询与转换到 Chaos Cloth Asset | 不是完整布料求解参数或所有布料图编辑器 |
| SemanticSearchToolset | 已索引资产的语义/相似搜索，按类型/路径限定 | 不是全项目源码或蓝图连线语义搜索。核对索引、支持类型和服务依赖，不自动开外部索引服务 |
| LiveCodingToolset | 触发 Live Coding 并返回状态/编译器诊断 | 不能处理所有 UHT/类布局变更或替代正常构建；纯蓝图任务无需引入 C++ 热编译 |
| MetaHumanGenerator | 基于编辑会话创建角色、读写体型/皮肤/眼睛 | 不是通用角色绑定/动画管线；先核对会话的资产编辑/UI行为 |
| AIAssistantToolset | 项目与 Docked context | 不代表所有操作与 UI 独立，也不要求使用 Epic 内置聊天助手 |
| ToolsetRegistry.AgentSkillToolset | 项目 AgentSkill 资产的列出/读取/创建/更新 | 与本机 Codex `skills/*/SKILL.md` 不同，不擅自迁移或重复维护两套知识 |

## 官方来源和后台操作分别判断

**SlateInspectorToolset** 提供 Snapshot/Observe、Screenshot、Click、Hover、Type、PressKey、
SelectOption、Drag、Windows、WaitFor 和 FillForm。它用 Slate 事件驱动 UI；
`Windows(select)` 切换窗口，`Type` 聚焦控件。来自 Epic 不代表符合后台资产操作要求。

按用户偏好，不为普通蓝图/资产修改启用它，不在数据接口失败后自动用它兜底。
仅在用户明确请求相应 UI 操作时评估；Observe 会留下周期观察者，要对应清理。
同样约束适用于 `OpenEditorForAsset`、Sequencer 打开/聚焦、相机锁定/视口切换。

对耗时的编译、Niagara 问题修复、测试和生成操作，采用有界调用与状态/日志回读。
超时后先核实结果，不自动重发写入。

## 推荐增量顺序

- 先利用已有的资产引用追踪、输入配置、数据表、模型/碰撞/挂点和日志，通常无需加插件。
- UI 任务加 UMGToolSet，有 ViewModel 架构时再用 MVVMToolset。
- 标签和能力系统先 GameplayTagsToolset，项目采用 GAS 时再用 GASToolsets。
- 有回归测试时用 AutomationTestToolset，筛选目标案例。
- 有对应内容任务时，再加载 PCG、PhysicsAsset、DataRegistry、Dataflow 等域。

先组合现有 Blueprint、Object、DataAsset、Scene 工具。
只有明确到某一步仍无法表达时，才记录并使用公共 Epic Python 的单项缺口路线。
