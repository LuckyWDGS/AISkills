# UE 5.9：StateTree 编写与 PCG 组件求值

StateTree 的结构编写与编译，以及 PCG 在普通组件上的执行与求值，均走官方 MCP。
先读 [5.9 审计](ue-5.9-preview-audit.md)，用新鲜的编辑器身份、完整工程路径
保护和实时 schema 开始。结构写入、编译、编辑器求值与运行时行为是不同的
[证据等级](shared-conventions.md#evidence-levels)；实测范围见文末
[验证记录](#验证记录)。

## 目录

- [StateTree：已从读取扩展到结构编写与编译](#statetree已从读取扩展到结构编写与编译)
- [PCG：executionSource 已覆盖普通组件](#pcgexecutionsource-已覆盖普通组件)
- [验证记录](#验证记录)

## StateTree：已从读取扩展到结构编写与编译

实时所有者为 `state_tree_toolset.state_tree.StateTreeToolset`。
保留其 snake_case 工具及参数，不套用其他 native toolset 的大小写。

1. `get_root_states(state_tree)`、`get_children(state)` 返回真实状态引用。
   用 `get_tasks` / `get_enter_conditions` / `get_global_tasks` / `get_evaluators`
   获取节点描述。节点 GUID 在当前 JSON 中名为 **`iD`**；增删工具返回的 GUID
   也是有效来源。不要用显示名称定位节点或生成新的 GUID 代替它。
2. `add_child_state`、`move_child_state`、`remove_child_state` 操作拓扑。单元素
   `move_evaluator(index=0)` 返回 false，是 no-op，不是重排通过。
3. 原生任务/条件使用 schema 要求的 ScriptStruct 引用，例如
   `/Script/StateTreeModule.StateTreeDelayTask` 和
   `/Script/StateTreeModule.StateTreeCompareBoolCondition`。
   `add_task` / `add_enter_condition` 与 Blueprint 版本参数不同。
4. `get_node_instance_data` → 保留类型和其他字段 → `set_node_instance_data` → 完
   整回读。
5. 用 ObjectToolset 发现并填写状态 name/description，保留稳定模块 ID 和中文说明。
   Blueprint 评估器用 `BlueprintToolset.GetDefaultObject` 取得 CDO、
   `ObjectToolset.GetClass` 取得生成类，传给 `add_blueprint_evaluator`。
   将 Blueprint 资产引用传给泛型 ObjectToolset 会解析到 CDO，不能据此读取
   Blueprint 资产的 generatedClass 字段。
6. `mark_as_modified(state_tree)` 后调用 `compile(state_tree)`，检查真实
   **`bSuccess` 和 `messages`**。最后只 `AssetToolset.SaveAsset` 指定资产，再检
   查 `IsDirty`。

### 创建资产与参数绑定仍有窄缺口

该 StateTree toolset 没有创建资产和编辑属性绑定的专用工具。这两项通过
`PythonScriptingTools` 内的公开 Unreal API 完成，后续步骤返回原生 MCP。先读
`read_me`，对使用的符号逐项 `get_symbol`。

- 创建：`StateTreeFactory` 设置
  `state_tree_schema_class=StateTreeComponentSchema`，通过
  `AssetToolsHelpers.get_asset_tools().create_asset` 创建候选 StateTree。factory
  会自动建立一个默认根状态；创建后先读取，不再重复添加根。
- 绑定：`StateTreeEditorData.get_editor_data`、`resolve_binding_path`、
  `promote_to_parameter` 和 `get_bindings` 已实测。`parameter_state=None`
  表示全局参数；promote 会按目标当前类型/值创建参数并绑定。先读取既有绑定，
  仅处理目标节点，不重置其他绑定。

绑定步骤的公开 API 形状如下；tree、node_id 和属性路径来自当前候选的实际回读：

```python
data = unreal.StateTreeEditorData.get_editor_data(tree)
guid, success = unreal.GuidLibrary.parse_string_to_guid(node_id)
assert success
target = data.resolve_binding_path(guid, 'bLeft')
with unreal.ScopedEditorTransaction('AI.Condition.Bind 条件参数绑定'):
    source = data.promote_to_parameter(target, None, 'ConditionEnabled')
bindings = data.get_bindings()
```

随后通过 StateTree MCP mark/compile，检查绑定数量、目标/来源和诊断。 Python 文档
列出 `StateTreeEditorNode.id`，但本构建直接访问条件的 `.id` 报 AttributeError；
使用工具返回 GUID 并解析，不绕过编辑器 API 写内部字段。

### 节点模板 JSON 不能盲目往返

`get_node_template_data` 包含编译器内部字段，例如
`instanceDataHandle.source="None"`。整份结果原样交给
`set_node_template_data` 时，该构建的 enum converter 拒绝隐藏枚举值，
报 `0 is not a valid value for enum EStateTreeDataSourceType`。

setter 是结构体替换；把这一写法套到已配置节点可能恢复其他字段默认值。不要据此删
除内部字段再覆盖生产节点。先查字段 schema/公开编辑 API，保留配置并回读；实例数据
setter 与模板 setter 是不同路径。

## PCG：executionSource 已覆盖普通组件

5.8 的 PCGVolume 限制不再适用于以下 5.9 schema：

| 工具 | 当前目标与行为 |
|---|---|
| `ExecuteGraphInstance(executionSource)` | 对实现 PCGGraphExecutionSource 的对象调度生成，如 PCGComponent；已在生成时拒绝重复调度 |
| `WaitForGraphInstance(executionSource)` | 只等待该来源当前活动生成，不启动或重启；空闲时报错 |
| `GetExecutionSources(executionSource?)` | 返回执行来源、gridSize、gridCoordinates；可按组件的世界/图实例限制；不生成、不加载格子 |
| `GetNodeDataView(executionSource,node,...)` | 为目标启用 inspection，首次可能触发生成；支持 executionStack 选择一次子图/循环调用 |

普通 transient Actor 上的 PCGComponent 可以直接传给这四项，读取到精确组件来源。
无需为了显式生成把普通 Actor 改为 PCGVolume，或转到 Python generate_local。其他
工具仍可能要求 PCGVolume，例如实例参数工具；逐项检查 schema，不把
executionSource 的扩展推及整个 toolset。

### 编图、绑定组件、执行和数据检查

1. `ListNativeNodes()` 在本构建**没有 bCommonOnly 参数**。使用返回的本地化名称查
   询 `GetNativeNodeSchema`（中文编辑器中为“创建点”和“变换点”）。
2. 原生 `CreateGraph` / `AddNode` / `ConnectNodePins` 编图。图结构的 nodeType 也
   会本地化；不要用 `nodeType=="Output"` 猜出口。读取 DefaultOutputNode 的真实
   inputPins 和 properties.label（实测为 Out）。连接返回 [] 表示没有自动插入转换
   节点，成功与否看边回读。
3. `ActorToolset.AddComponent` 创建组件。ObjectToolset 先发现属性/enum，
   设置 `generationTrigger="GenerateOnDemand"`，并按测试需求关闭自动放置生成、
   editor 自动重生与分区。读组件 graphInstance，再对该真实实例的 graph 写引用。
   不把 graphInstance 当可替换的普通 JSON 值，也不修改共享图的实例重载。
4. `ExecuteGraphInstance` 的工具异步结果结束后，检查工具错误和节点消息。
   返回 [] 只表示无捕获诊断，必须另查实际输出。
5. `GetNodeDataView` 是 **write** 操作，不属于纯只读审计。首次调用可能返回
   `{status:"pending",reason:"capture"}`，允许编辑器 tick 后再查得到
   `data_version:0`、element_0/element_1；不必重复 Execute。 pending 不是零点，
   unavailable 也不证明空输出。
6. 这是**编辑器 PCG 求值**通过；未产生网格实例，也未运行 PIE。

大结果按 startIndex/endIndex 分页，endIndex 为排他上界、-1 为剩余全部。当返回
selection_required 时，使用其 executionStacks 的实际路径选择调用。多实例分支、运
行时 scheduler 与 GPU readback 未验证。

### 等待顺序与活动窗口

`await call_tool(...ExecuteGraphInstance...)` 会等待生成结果。紧接着调用 Wait 会
明确返回 `Execution source is not currently generating`。不要把这当成失败生成，
也不应在错误后再发一次 Execute 来“修复等待”。

也可以在官方 `execute_python` 内启动 Execute 的异步 task，yield 一次让其调度，再
调用 Wait：

```python
running = asyncio.create_task(call_tool(
    'PCGToolset.PCGToolset.ExecuteGraphInstance', executionSource=component))
await asyncio.sleep(0)
messages = await call_tool(
    'PCGToolset.PCGToolset.WaitForGraphInstance', executionSource=component)
execution_messages = await running
```

这是已观察到的活动窗口，快速生成仍可能在 Wait 到达前结束。调用方应接受这一 race，
核对源状态/最终输出，不用扩大负载来制造等待。不并行修改图、Execute 和 DataView。
上述仅重叠同一生成的 Execute 与 Wait 观察者。

### 临时世界测试的清理证据

需要无持久 owner 的测试时，当前原生 spawn 工具没有 transient 选项。
查明该缺口后用公开 `EditorActorSubsystem.spawn_actor_from_class(...,transient=True)`，
它会选择新 actor，立即恢复此前选择；组件创建、配置、求值和删除仍走原生 MCP。
在 finally 中精确 `LevelToolset.RemoveFromScene`，不要以类型批量删除。

删除后核对前后 actor 路径集合、选择和 dirty map/content 包集合一致；不保存世界，
不清除 dirty 标记。若请求超时，先确认脚本/生成是否仍在运行，按唯一 label/实际路
径回收，不重复创建未知残留。不要运行会清空 PCGVolume 的引擎自动化 fixture 于用户
世界。

## 验证记录

构建：UE 5.9.0 Preview / CL 60351404，2026-11-11，独立测试工程和候选资产。未做
UE 5.8 回归、PIE gameplay、打包目标或大规模程序化生成验收。

- 2026-11-11 在 UE 5.9.0 Preview、CL 60351404 上通过官方 MCP 实测。

**StateTree：已从读取扩展到结构编写与编译**

- 本次用两个子状态验证第二个移至索引 0 的真实顺序变化，再删除临时子状态。
- 本次 Delay 的 duration 从 1 秒变为 0.25 秒；这证明参数写入，不证明任务实际计
  时。
- 本次缺少 Bool 条件 bLeft 绑定时，返回 bSuccess=false 及
  severity/state/item/message 诊断；修复后为 true、空 messages。
- `set_binding`、候选绑定查询等符号虽能发现，本次没有执行其写入。
- 本次只在新建、默认配置的 Delay 任务上用 `_structType` 与 name 的最小模板成功设
  置中文名称。

**PCG：executionSource 已覆盖普通组件**

- 本次两个固定世界坐标点 (0,0,0)/(100,0,0)，经 Y+50cm 的 Transform 后，
  `$Position` 精确为 (0,50,0)/(100,50,0)。
- 本次还在官方 execute_python 内启动 Execute 的异步 task，yield 一次让其调度，然
  后 Wait 成功完成；两者结果均为 []，回读 bGenerated=true、
  bGenerationInProgress=false，随后 DataView 仍为预期两点：

### 本次验证范围

| 领域 | 读取 | 写入及回读 | 编译 / 求值 | 尚未验证 |
|---|---|---|---|---|
| StateTree | 根/子状态、任务、进入条件、全局任务、评估器、节点模板/实例数据 | 子状态增删与非平凡重排；Delay 参数；Bool 条件；全局任务增删；Blueprint 评估器增删；中文说明；公共 API 创建参数绑定 | 缺绑定时得到明确编译错误；补绑定后成功；带评估器编译成功；指定资产保存后 clean | 状态执行、任务生命周期、转换时序、consideration、subtree 写入、Blueprint task/condition、评估器非平凡重排 |
| PCG | 本地化节点 schema、引脚、边、执行来源 | 创建图与两个节点、连线、中文注释；普通 Actor 的 PCGComponent 绑定图 | 编辑器求值输出准确两点；活动生成等待成功；空闲等待明确拒绝；DataView pending 后返回数据 | PIE gameplay、Spawner/实例数、World Partition 本地格子、运行时调度、GPU readback、Loop/子图多次调用 |

当前 live inventory 中 `StateTreeToolset` 为 49 项；`PCGToolset` 为 32 项，
`PCGSpatialToolset` 为 1 项，两个 PCG toolset 合计 33 项。
数量只描述该构建和配置；不能把所有注册工具计作已测通过。

- 临时 PCG Actor 的两次测试均删除成功，前后 actor 路径集合、选择、dirty 包集合一
  致。
