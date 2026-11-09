# PCG：官方 MCP 编图、蓝图包装与输出检查

用于程序化散布、地表/体积/样条采样、过滤、属性处理、子图和生成内容。
遵守[共享后台规则](shared-conventions.md)；PCG 图中的数据边不是 K2 执行线。
可搜索：override、selector、零点、坡度、ISM、Box、确定性、外部包。

## 发现当前能力

先确认目标工程、PIE 状态，读取 `PCGToolset` / `PCGSpatialToolset` 的简表和所需工具
完整 schema。UE 5.8.4 CL 58902052 实测分别有 30 / 1 项；升级后以实时发现为准。
插件在安装引擎的 `Plugins/Experimental/Toolsets/PCGToolset`，依赖官方 PCG。
已启用时直接使用，不为已有能力安装桥接或重启编辑器。

| 任务 | 官方工具 |
|---|---|
| 找节点、子图与参数定义 | ListNativeNodes、GetNativeNodeSchema、ListAvailableSubgraphs、GetGraphSchema、GetGraphDescription |
| 建图与修改节点 | CreateGraph、GetGraphStructure、GetNodeInfo、AddNode、AddSubgraphNode、UpdateNode、RepositionNode、RemoveNode、SetNodeComment |
| 连线 | ConnectNodePins、DisconnectNodePins |
| 图参数与实例重载 | SetGraphParams、RemoveGraphParams、GetGraphInstanceParams、SetGraphInstanceParams、ResetGraphInstanceParams |
| 中文模块说明 | SetGraphDescription、AddCommentBox、UpdateCommentBox、RemoveCommentBox |
| 场景与输出 | SpawnGraphInstance、ListGraphInstances、ExecuteGraphInstance、GetNodeDataView |
| 交互绘制 | DrawSpline：启动视口绘制并等待用户，不用于后台自动化 |
| 即时图 | PCGSpatialToolset.RunPCGInstantGraph：执行也可能生成世界内容 |

中文环境的 `ListNativeNodes(bCommonOnly=true)` 可能为空；改用 false 并使用返回的
本地化名字查询 schema。不要猜英文节点名，也不要切换用户的编辑器语言。
Epic 的内置 AgentSkill 可以作为资料，但其中的打开编辑器、旧参数写法不能覆盖当前
后台操作规则与实时 schema。

## 只读检查：先确认真实引脚和连线

```powershell
python scripts/pcg_inspect.py /Game/PCG/MyGraph --project <full.uproject> --verify-snapshot --out <session>/pcg-inspect
```

脚本通过官方 MCP 保留图结构、参数 schema/默认值、原生节点 schema、真实引脚、
边对象及双端引用，输出 `snapshot.json`、`connections.json`、调用记录和报告。
它不执行、不启用 inspection、不生成、不保存、不打开图页签；已有 dirty 保留。
`--verify-snapshot` 复读检测并发变更，失败时保留证据，不尝试修图。
通过仅表示返回的逻辑拓扑一致，不表示点数据、生成实例或运行时验收通过。

手工检查也可以使用同一路径：

1. `GetGraphStructure` 取得节点 **path**、设置、位置和 edges；默认出口在当前构建叫
   `DefaultOutputNode`，不要猜成 Output。
2. `ObjectTools.list_properties/get_properties` 读取每个 PCGNode 的 inputPins/outputPins，
   再读每个 PCGPin 的 node、properties.label、edges。这里能看到实际 override/dynamic pins；
   `GetNativeNodeSchema` 的基本引脚列表可能没有它们。
3. 读每个 PCGEdge 的 inputPin/outputPin，并核对两端 pin.edges 都含该边、所属节点和
   方向正确，实际边集合与图结构一致。**PCGEdge.InputPin 是上游的输出引脚，
   OutputPin 是下游的输入引脚**，不要按字段名字反转方向。
4. 图默认参数可从 PCGGraph 的 `userParameters` 反射读取；先发现属性再读。
   schema 键名可能 camelCase，显示参数名可能首字母大写，使用实际返回的键。

不要仅凭节点位置推断连线。`ConnectNodePins` 返回的是**自动加入的转换/过滤节点**，
普通连接返回 [] 很正常；根据回读的边判断成功，保留工具自动加入的必要节点。
不要自动将图中回路判成错误，Loop/Feedback 等语义要结合节点类型解释。

## 编图与参数连通

- `AddNode` / `RepositionNode` 的 xPositionIdx/yPositionIdx 名字带 Idx，但该构建源码直接
  调用 `SetNodePosition(XPositionIdx, YPositionIdx)`，就是图坐标。不要使用 0、1、2
  作为列号而导致叠在一起，也不要套用 K2 引脚排版器。
- 对新模块添加中文节点说明和带稳定 ID 的注释框，写清采样来源、单位、参数范围、
  过滤条件、生成资源的所有者。移动节点后按其原 ID 更新框。
  `GetGraphStructure` 不包含注释框，不能据此判断没有注释；缺少 MCP 读取入口时，
  可通过公共 `AssetExportTask` + `ObjectExporterT3D` 后台导出并核对文本/范围。
  不打开资产页签；中文导出文件可能是 UTF-16 BOM。
- 先读本地化原生 schema，再设置 `jsonParams`；写后回读 `GetNodeInfo`，对象字段继续
  用 ObjectTools。节点的默认值正常并不能证明参数重载实际生效。
- **属性选择器使用当前 DSL 字符串**，如 `"RockMesh"`、`"$Density"`、`"@Elements.X"`。
  当前 converter 调用 Selector.Update，不使用旧示例的 `PCGBegin(...)PCGEnd` 包装。
- **重载引脚按同名属性取值**。例如将 Graph Parameter `Density` 用 Get Graph Parameter
  节点输出为 `PointsPerSquaredMeter`，再连 Surface Sampler 的同名 override pin。
  计算出的坡度阈值要输出为 `LowerBound`，向量要输出为 `ScaleMin` / `ScaleMax`。
  不是任意单属性接上就能重载；名称错时可能警告并沿用默认值。
- Static Mesh Spawner 使用 By Attribute 时，把模型软路径写到点的目标属性。
  `GetNodeInfo.paramOverrides.meshSelectorParameters` 提供真实 instanced selector 引用，
  可用 ObjectTools 设置 attributeName、templateDescriptor 等已发现属性。
  不为选择模型而修改官方共享网格资产。

### 地表石块散布参考结构

`World Ray Hit Query → Surface Sampler → Normal To Density → Density Filter
→ Transform Points → Copy Attribute → Static Mesh Spawner → 输出`

图参数可包括密度、统一缩放上下限、最大坡度和模型软路径；Seed 放原生 PCG 组件。

- Surface Sampler 的 Point Extents 与 Looseness 决定网格间距；密度是保留格子的比例来源，
  增大 PointsPerSquaredMeter 不保证无限增多或精确得到“面积×密度”个点。
- 保留地表法线，`dot(normal, worldUp) >= cos(degreesToRadians(maxSlope))` 过滤陡坡。
  角度与弧度必须转换；使用 Normal To Density 后说明 Density 的新含义，避免后续节点
  再把它当随机生成概率。旋转/缩放需要说明是在世界轴还是点的局部轴上应用。
- World Ray Hit Query 的 collisionChannel 当前是**对象类型查询**，源码使用
  `FCollisionObjectQueryParams` / `SweepMultiByObjectType`。普通地表匹配 WorldStatic；
  Visibility 即使不报错也可能零点，不能照搬 LineTrace 的通道习惯。
- 未覆盖射线参数时，射线起点/长度从 owner bounds 计算，并沿 Actor 的局部 -Z 查询；
  不要假定旋转 Actor 后仍沿世界 -Z。开启需要的命中法线，排查实际地表碰撞。
- 根据图的依赖关系设置忽略 PCG/self hits，防止重新生成时采到自身旧实例。
  装饰散布可明确使用 NoCollision；需要玩家碰撞、导航或物理时按具体功能配置并验收。

## 包装为开发者可用的蓝图

优先普通 Actor Blueprint + 无碰撞 BoxComponent + 原生 PCGComponent。
Box 控制明确的生成边界，PCG 组件管理生成/清理，Graph Parameters 管理内容参数。
这类纯 PCG 工具不需要为了演示而复制一套 K2 Tick、BeginPlay 或 Python 运行时逻辑。

- 用 BlueprintTools/ActorTools 创建资产、组件，用 ObjectTools 设置已发现的默认属性。
  PCGComponent 的 graphInstance 是 instanced 子对象：先读真实引用，再写其 graph 字段，
  不因缺少专用 SetGraph 工具就转 Python。
- 默认参数与实例重载分开；改变图默认值会影响其他使用者。实例重载还包含参数 ID
  的 overridden 集合，不能只写 parameters 数值而宣称已设置持久重载。对 Volume
  使用专用 SetGraphInstanceParams；普通 Actor 上先检查实际 GraphInstance 属性和工具，
  不够时才用公开的 PCG 参数 helper，并回读有效值与重载标记。不要猜造 GUID。
- 原生 Box 的 boxExtent 是**半尺寸**，单位 cm；读取实际 owner/组件变换和生成 bounds，
  不仅检查编辑框数字。多个有体积的组件可能共同影响 Actor bounds。
- 当前 ObjectTools 会对普通结构体逐字段通知；在蓝图实例组件上实测多成员 FVector 写入
  返回 true 但只保留第一项。源码通知路径可能重建构造脚本组件。遇到这类部分生效，
  重新解析组件，按实际支持的单字段写入并逐次完整回读；不要盲目重放同一整个结构体。
  仍不可用才对该项使用公开 setter。CDO、组件模板和实例的行为不要混为一谈。
- 当前 `ExecuteGraphInstance` / `GetNodeDataView` / 实例参数工具的 schema 目标是
  **PCGVolume**，不要将普通 Actor 或 PCGComponent 强塞进去。
  `ListGraphInstances` 在该构建源码中也只枚举 APCGVolume；空列表不能证明普通蓝图
  Actor 没有 PCG。用 SceneTools 定位 Actor，再由 ActorTools.get_components 查询组件。
  Actor 上可优先测试组件原生的属性变化/自动重新生成。若要显式 Generate/Cleanup，
  确认 MCP 没有组件方法工具后，使用公开 `PCGComponent.generate_local(True)` /
  `cleanup_local(True)`，再回 MCP 轮询状态与真实实例；它们可能异步返回。
- 提供中文模块框、组件说明和参数表，完成 BP 编译与严格 lint。日志以 PCG 执行消息、
  生成状态和原生日志为准；无 K2 业务逻辑的包装不必添加无意义的游戏日志函数。

## 执行与验收

采用 [PCG.Graph.Output 案例](runtime-acceptance.md#pcggraphoutput--执行数量与属性)，
区分编辑器生成、PIE 和打包目标。执行、点数据、生成实例与截图各有不同证据。

- 检查是否会改世界，只执行当前授权的 owner。`RunPCGInstantGraph` 不是无副作用
  沙箱；Spawner 仍能生成内容。不要运行
  `AI.Toolsets.PCGToolset.Execution.*` 于用户工作世界，其 fixture 会删除全部 APCGVolume。
- 同一图的执行和 DataView **串行**。DataView 会开启 inspection，第一次没缓存时需要
  重新执行；先核对 owner 和已完成状态。Loop/多实例化节点当前不支持逐迭代 DataView，
  报限制而不是重复执行到“成功”。不要在 UE 主线程里 sleep 等生成。
- `ExecuteGraphInstance` 返回 [] 仅表示没捕获消息。读取 `GetNodeDataView` 的实际输出，
  全量用 endIndex=-1；该构建全量格式是 `data_version:0` 和 `element_0...`。
  分页返回 totalElements，endIndex 为排他上界；空数据集不要发 startIndex=0 的分页请求。
  先从全量小样本了解结构，大输出再按边界分页，不把截断页面当全部点数。
- ISM/HISM 可通过 ActorTools 获取组件，ObjectTools 读取 staticMesh、perInstanceSMData
  与组件变换，核对真实数量/矩阵。不必为 get_instance_count 转 Python。
  点数不一定等于实例数，多模型、过滤/合批、空路径都可能改变对应关系。
- 同一 owner、Seed、变换、输入与参数重生成应符合图的确定性约定；不同 Actor/Volume
  的 Seed 派生、变换不同，不能强求数量或矩阵相等。验证重复生成不累积。
- 至少测试相关参数的实际效果、零密度、边界/坡度、固定缩放、模型变更、清理与恢复；
  全部默认恢复后再比对实例签名。截图用于贴地、间距、遮挡和视觉范围。
- 保存图/BP 指定包，检查 Actor 和文件夹的外部包。当前 SceneTools.save_actor 委托
  AssetTools.save_assets，后者可能将新建/隐藏外部包判成“不存在”；is_dirty 也可能不支持。
  确认精确包归属和基线后，使用公开 `EditorLoadingAndSavingUtils.save_packages` 只保存
  这些包，核对返回值、剩余 dirty 和实际文件。不要传空资产列表，空列表意味着 Save All。
  保留原有 Actor，记录 PCG 自动创建的 PCGWorldActor，删除仅本次临时 owner。

## 常见失败的下一步

| 现象 | 优先检查 |
|---|---|
| 零点且没有执行错误 | owner/边界、地表对象类型与碰撞、射线方向/起点、采样间距、密度、过滤前后的 DataView |
| 参数连了线却没变化 | 动态引脚确实存在；属性同名；有效实例重载；执行消息；新输出而非旧缓存 |
| 重生后越堆越多或点漂移 | 生成资源的 owner、忽略自身查询、清理结果与同 Seed 矩阵，而非只看图设置 |
| Box 数字/面积不对 | 半尺寸与世界变换、完整 Vector 回读、组件重建、lastGeneratedBounds |
| 没有 inspection 数据 | 正确 Volume、先启用再重新执行、是否有缓存/多迭代限制；不自动换 owner |
| Blueprint Actor 不能 Execute | 实时 schema 的 PCGVolume 限制；组件自动生成/公开 Generate 方法；不新增桥接 |
| 节点或注释框重叠 | PositionIdx 的实际坐标语义；原 ID 更新框；不通过打开编辑器排版 |
| 保存成功感知与文件不一致 | 普通资产和外部包分别核验；隐藏包存在检查限制；不 Save All/清 dirty |

## 官方资料与源码核对点

- [PCG 概览](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview)：组件、图参数、实例与生成所有权。
- [原生节点参考](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-framework-node-reference-in-unreal-engine)：采样、属性、变换和生成语义。
- [PCG 与 World Partition](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-pcg-with-world-partition-in-unreal-engine)：Data Layers、HLOD 及 Spawn Actor 的归属设置。

这些是领域资料；MCP 参数取实时 schema。升级时核对安装引擎的 PCGToolset.cpp、
PCGAttributePropertySelectorConverter.cpp、PCGWorldData.cpp、PCGEdge.h、
ToolsetLibraryImpl.cpp 与 EditorToolset 的 object.py/scene.py/asset.py。
不要将本例资产路径、点数或某版本观察写成所有项目的固定要求。
