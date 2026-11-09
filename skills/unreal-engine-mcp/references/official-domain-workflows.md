# 官方 MCP 领域开发工作流

只读任务先用[能力地图](official-capability-map.md)选路。本页保留 UE 5.8.4
实测中会改变操作决策的细节；名称、字段与枚举仍需从目标项目实时发现。
不要求为普通蓝图功能采用 MVVM、GAS、PCG 或其他新架构。

检索词：UMG、MVVM、FieldNotify、GeneratedClass、GAS、ASC、GameplayCue、
DataRegistry、instanced、PhysicsAsset、PCG、中文节点、Dataflow、Automation。

## 接入插件与后台操作

- 先查 live inventory，再核对安装目录内 `.uplugin`、模块类型与依赖。
  插件已安装但未启用，和 API 没有实现，是两种不同问题。
- 已加载 PluginToolset 时，用其实际 schema 查启用情况和依赖。
  PluginToolset 自身未注册时，不假设 `unreal.load_module('PluginToolset')`
  能引导启动：实测返回 unknown module。按当前项目配置流程启用需要的官方插件。
- 项目插件启用属于配置修改。已有用户授权时备份并改动具体条目，保留其他字段；
  不为“全部能力”加载 AllToolsets。工具集插件与游戏运行时依赖分别检查。
- 若必须重启，先确认无用户 PIE、未保存包和正在执行的任务；不能通过 Save All、
  清除 dirty 标记或强杀编辑器来获得“干净”状态。正常退出后再启动目标项目，
  刷新 schema 并读编辑器状态；端口开放或 initialize 成功都不等于全部工具已就绪。
- 不移动、聚焦、缩放、最小化窗口，不自动打开资产页签，不经鼠标控制台执行代码。
  官方 SlateInspector 也不能自动充当后台操作的替代方案。

配置启用与最小验证可以在独立的开发资产目录完成，避免改主角色/关卡。
验证夹具加中文说明与稳定模块 ID；测试结果和本机路径放忽略的 session 输出。

## UMG 与 MVVM：结构、类与运行实例

### 官方编辑路线

1. UMGToolSet 创建 Widget Blueprint；GetWidgets 回读 Widget、Parent 和 Slot。
   对每种 Widget/Slot 先 ObjectTools.list_properties，再读写实际字段。
   Padding、锚点和对齐属于具体 Slot 类型，不能套用另一容器的字段。
2. AddWidget/MoveWidget 等操作后读回父子层级、同级顺序与 Slot 值。
   空 Parent/Slot 可能是字符串 `"None"`，不能因其为 truthy 就继续读属性。
3. BindToEventProperty 后同时检查对应事件节点。只有绑定入口而没有业务节点，
   不应描述成“按钮逻辑已实现”。CompileWidgetBlueprint 后保存指定 Widget 包。
4. 项目采用 MVVM 时，用 MVVMToolset 创建模型、属性、ViewModel Context 和绑定。
   AddViewModelProperty 的默认值遵循实时 schema；编译后读回实际属性值与类型。
   需要 FieldNotify 时也核对该属性的通知设置，不能仅凭属性名字判定。
5. 回读模型 Context ID、源/目标属性路径、方向和转换函数，编译并限定保存。
   健康度一类的可调参数放中文分类；模块说明放中文注释框/资产元数据。

### 已确认的陷阱

- ListViewModels 返回候选可能包含原生类型、SKEL、REINST 和不适合绑定的条目。
  不拿第一项使用；从目标 ViewModel Blueprint 的 get_default_object，再用
  ObjectTools.get_class 取得实际 GeneratedClass。重新编译后重新解析引用。
- ObjectTools 对 Blueprint 的属性操作通常解析到 CDO；UserWidget 默认实例属性
  不是 Widget Blueprint 的描述字段。运行时 Widget、WidgetTree 模板和 CDO
  也是不同对象，分别记录其完整路径。
- ListWidgetViewModels / ListWidgetViewBindings 可能 RequestView 并创建扩展。
  仅审计任意用户 Widget 时遵循[查询副作用规则](official-capability-map.md#mvvm-查询的副作用)。
- 实测 BlueprintTools 没有注释框创建接口。只对注释这一缺口用公共
  BlueprintGraphEditor.add_comment_to_nodes，经后台 Epic Remote Execution；
  回读中文文字/成员，并比较原有 K2 节点、位置、引脚、值和连接，随后回到 MCP 保存。
  `node_details` 是 Unreal Text，写 JSON 报告时转为 `str`。
  重载后 native 成员缓存可能为空；`blueprint_lint.py` 会只读导出框的可序列化坐标，
  结合 UE 节点尺寸验证完整包含，并核对 MCP 快照的节点集合和位置。
  这是模型几何验证，不是 Slate 像素测量，也不会填充原生缓存。
  读取失败、捕获状态变化或入口仅部分相交，仍报告“成员未验证”；
  明确在框外则报告缺少覆盖。细节见[注释读取](blueprint-programming-mcp.md#chinese-module-annotations)。

结构回读和编译不证明实时绑定更新、点击、焦点或布局通过。
按 [UI.MVVM.Binding](runtime-acceptance.md#uimvvmbinding--实例数据与界面更新)验收。
不要用未初始化的 `new_object(UserWidget)` 代替 CreateWidget/实际生命周期来证明运行结果。

## Gameplay Tags 与 GAS：字典、定义与实际 ASC

- GameplayTagsToolset 可读标签树、来源、注释和引用，写入会影响标签 INI。
  独立往返测试要用唯一来源文件和标签，先记原值，再添加/读取/删除/复查。
  中文模块 ID 和资产说明无需创建全局 Gameplay Tag。
- AttributeSetToolset 查的是属性**定义**；AbilitySystemInspectorToolset 需要带 ASC 的
  实际 Actor，读取 Base/Current、能力、效果、叠层/剩余时间与 Tags。
  查不到数据时先核对目标世界、Actor、ASC 初始化和已注册 AttributeSet。
  普通蓝图 Actor 加一个组件并不自动等于完整 GAS 初始化流程。
- 工具单元测试可验证独立 Actor fixture 的 ASC 检查路径，但没有授予能力/应用效果
  的空列表案例，不能证明激活、预测、叠层、过期或网络复制正常。
- GameplayCueToolset 的选中 Actor 执行接口依赖用户选择并触发行为；不用于只读探测。
  遇到未配置 GameplayCueNotifyPaths 而扫描整个 `/Game` 的提示，记录原因。
  只有项目实际使用 GAS/Cue 且在任务范围内，才配置正确目录；不为消除测试警告改全局配置。
- GA/GE 公开属性和蓝图逻辑仍用现有 Blueprint/Object 工具；检查工具不等于完整
  GA/GE 编辑器。按 [GAS.ASC.Lifecycle](runtime-acceptance.md#gasasclifecycle--能力效果与属性)验收实际玩法。

### GameplayCue 扫描目录与旧会话缓存

在用户要求配置或修复 Cue 扫描时，先用 FindCueNotifyAssets 查现有 CueNotify 资产，
保留覆盖这些资产的既有路径。UE 5.8.4 实测设置位置是
`Project / Game / GameplayAbilitiesDeveloperSettings`，MCP JSON 属性为
`gameplayCueNotifyPaths`。先读 schema/原值，再用 ConfigSettingsToolset 写明确的
内容目录并回读；需要的空目录可用 AssetTools.create_folder 创建，不造假 Cue 资产。
原生设置/INI 使用 `GameplayCueNotifyPaths`，不要照搬 MCP 的 JSON 大小写。

例如，项目约定 CueNotify 存在 `/Game/Gameplay/GameplayCues` 时，对应最小配置是：

```ini
[/Script/GameplayAbilities.AbilitySystemGlobals]
; [GAS.GameplayCue.ScanPaths] 玩法提示扫描目录；CueNotify 资产放在此目录下。
+GameplayCueNotifyPaths=/Game/Gameplay/GameplayCues
```

目录按项目实际资产确定，不把这个示例强加给其他项目。该设置会保存配置；
本机构建的集合属性写入会一并物化 section 默认值。先保存原文件并审查实际差异，
若收敛为最小配置，只能移除本次产生且已证实等于默认值的行，保留原始配置和并发编辑。

此设置标记 `ConfigRestartRequired`。已初始化的 GAS 单例可能仍在进程内保留之前
回退添加的 `/Game`，不会因 INI 回读正确而自动清除。不要写私有数组或重建用户单例，
也不要为验证擅自重启用户编辑器。需要本轮验收时，可用独立无窗口 commandlet
读取实际配置，并在自己的临时世界初始化 ASC/CueManager，核对实际运行路径和启动日志。
不保存世界，清理自建 fixture。报告要区分“新进程初始化通过”和“原会话需下次正常重启刷新”；
同一旧会话没有再次报警不足以证明配置生效。

## DataTable 与 DataRegistry：创建、注册、缓存

DataTableTools 可创建已有 TableRowBase 结构的数据表，先 get_schema 再 add_rows /
set_rows / get_rows。它不等于任意结构体编辑器。参数表与注册表采用项目已有结构。

DataRegistryTools 提供注册表、schema、ID、数据来源和缓存查询。已确认的创建缺口：
UDataRegistry 直接继承 UObject；DataAssetTools.create 明确要求 UDataAsset 子类，
不能把它用于 DataRegistry。没有专用创建工具时，公共 Epic 路线是：

```python
registry_class = unreal.load_class(None, '/Script/DataRegistry.DataRegistry')
registry = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
    asset_name, folder_path, registry_class, unreal.DataRegistryFactory())
```

先确认目标不存在，检查工厂可用性；不调用会显示类选择 UI 的 ConfigureProperties。
目标版本未把 `unreal.DataRegistry` 暴露为 Python 类型，不代表 load_class 路线不可用。
创建后**回到 MCP**，用 load_asset 和 ObjectTools 枚举/设置 registryType、itemStruct、
dataSources，限定保存。类型与字段以 live schema 为准。

### Instanced 来源子对象

UE 5.8.4 实测的官方 JSON 是类的 **refPath**，例如：

```json
{"dataSources":[{"refPath":"/Script/DataRegistry.DataRegistrySource_DataTable"}]}
```

不要按旧 docstring 猜成 `{"instance":"类路径"}`：该形式实测返回 true，
数组元素却仍为 `"None"`。正确写入后得到注册表内的实际子对象 refPath；
再对该子对象 list_properties、设置 sourceTable/tableRules，检查其 Outer 和类型。
预缓存测试可选 bPrecacheTable=true；不把测试缓存策略强加给正式项目。

### 注册与还原

- 资产存在/已加载不等于已注册。先查 ListRegistries，再查初始化和来源 availability。
- 实测设置位置是 `Project / Game / DataRegistrySettings`。设置扫描路径会保存配置，
  PostEditChangeProperty 会触发重新初始化；不必为此强制重启或启动 PIE。
- 独立验证时保存原 directoriesToScan，只临时追加验证目录；用 try/finally 恢复并读回。
  检查注册表列表也恢复，避免让测试资源长期加入项目数据来源。
- ListItems 是已知 ID；GetItems 只含当前缓存命中。缺少条目时核对来源、初始化、
  预缓存/获取与实际 ID；不能推断条目被删除。ListRuntimeSources 可能展开 MetaSource，
  不一定与编辑器 dataSources 一一对应。

按 [DATA.Registry.Cache](runtime-acceptance.md#dataregistrycache--来源与缓存条目)记录来源、
值和清理；独立表使用 GameplayTagTableRow 也不需要把它加入全局标签导入源。

## PhysicsAsset：隔离共享模型改动

- PhysicsAssetToolset 的 CreateFromMesh 在网格同目录使用固定后缀生成资产。
  创建前查重；需要独立样例就先复制网格/资产，不让验证改写共享资源。
- 设置 bAssignToMesh=false 可避免把新 PhysicsAsset 分配到原网格；操作前后仍核对
  原网格的绑定和 dirty 状态。新 Body/Shape 取唯一名称，并回读骨骼、尺寸和质量缩放。
- 约束、碰撞模式和 Body 资产参数正常，不证明 Chaos 运行稳定，也不是物理投掷的验收。
  正式改动按 [PHYS.Body.Runtime](runtime-acceptance.md#physbodyruntime--刚体与约束)检查实际 SkeletalMeshComponent。

## PCG 与 Dataflow：图编辑、执行与输出分开

### PCG

使用 [PCG 专项流程](pcg-mcp.md)完成原生节点/schema、真实引脚与双端连线、图参数重载、
中文模块注释、蓝图组件包装、执行/点数据/ISM 验收及保存。`scripts/pcg_inspect.py` 只读
检查结构，不执行图，也不启用 inspection。

UE 5.8.4 的 xPositionIdx/yPositionIdx **直接写图坐标**；ConnectNodePins 返回的是
自动加入的转换/过滤节点，[] 通常是普通连接的正常结果。当前实现与旧索引/冲突节点
解释不同，升级时按源码和回读确认。即时图仍可能生成世界内容，执行和 DataView 串行。

### Dataflow

DataflowAgentToolset 可创建图、按实时 typeName 建节点、连接、更新属性并添加中文框。
连接时可能自动适配数值引脚类型，随后检查两端类型、值与实际连接。
GetNodeInfo 回读的属性可能是格式化字符串（如 `3.500000`），应按类型比较实际数值。
当前审阅接口没有显式数值求值工具；保存/拓扑成功不能写成计算结果通过。
在任务需要求值时继续查当前执行接口和公共 API，精确记录缺口，不新增求值桥接。

## Automation：只运行经过审阅的目标案例

1. GetTestStatus 确认没有用户正在运行的测试。DiscoverTests 后等发现完成再 ListTests。
2. 按名字/域筛选，检查案例源码的 BeforeEach/AfterEach、世界、资产写入、窗口行为和耗时。
   EditorContext 测试也可能改当前世界；RF_Transient 不保证没有其他副作用。
3. RunTests 只传审阅过的具体名字；超时后查状态和结果，不重复启动、不停止未知任务。
4. 回读每项 state、errors、warnings 和耗时。测试状态 Success 不等于零警告。
   Actor/图 fixture 检查清理，用户场景、PIE、页签、选择和脏包前后对照。

UE 5.8.4 CL 58902052 的 `AI.Toolsets.PCGToolset.Execution.*` 是具体反例：
`PCGToolsetExecutionTest.cpp` 的 BeforeEach 会枚举当前编辑器世界并 Destroy **所有**
`APCGVolume`，再创建自己的 Volume。不要在用户工作关卡运行这一组；需要测执行或
点数时，在专用测试世界审阅并运行，或选择已证实可隔离的公共 API。不能因图本身
使用 TransientPackage 就推断 fixture 不会删除场景对象。升级后重读实际源码。

`live_smoke.py --out <report.json>` 会在报告旁保留唯一 artifacts 目录，报告中有路径。
其中 `live_asset_verify` 对默认的三个独立资产可能返回 `verification_passed=false`；
这记为 **collected**，不计为材质/纹理/Renderer 链路通过。报告分别统计 pass、
collected、skipped、fail，检查数量不能作为通过数量。

测试报告注明“官方工具单元测试”还是“目标项目实际玩法验收”。
少量案例通过不代表整个工具集通过；不启动全部测试来代替能力盘点。
